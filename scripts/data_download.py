"""Download, verify and unpack the permissively licensed PPE v2 sources and the GMDCSA-24 fall clips.

Every URL works without an account, login or API key (checked 2026-10-07). Each file is
downloaded to a .part file, verified against a recorded checksum (the publisher's MD5/SHA-256 where
one is published; for GDUT-HWD on Google Drive, the hash of our first download), then unpacked into
data/datasets/<source>/raw/.
Already-present files are only re-verified. Nothing is overwritten.

Usage:  .venv\\Scripts\\python scripts\\data_download.py [--only hardhat_xie,chvg] [--skip-falls]
"""
from __future__ import annotations

import argparse
import shutil
import threading
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_common import (  # noqa: E402
    DATASETS_DIR, DOWNLOADS_DIR, FALLS, FALLS_DIR, KR_FRAME_STRIDE, SOURCES, TRAIN_SOURCES, Download, file_hash)

UNRAR_CANDIDATES = (Path(r"C:\Program Files\WinRAR\UnRAR.exe"), Path(r"C:\Program Files (x86)\WinRAR\UnRAR.exe"))


def fetch(dl: Download, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / dl.filename
    if not path.exists():
        if not dl.url:
            raise SystemExit(f"{dl.filename}: no automated download. {dl.manual}")
        part = path.with_name(path.name + ".part")
        print(f"downloading {dl.url}")
        req = urllib.request.Request(dl.url, headers={"User-Agent": "Yaqiz-data-script/1.0 (research)"})
        with urllib.request.urlopen(req, timeout=120) as r, part.open("wb") as f:  # noqa: S310 (fixed URLs)
            shutil.copyfileobj(r, f, 1 << 20)
        part.replace(path)
    if dl.size is not None and path.stat().st_size != dl.size:
        raise SystemExit(f"{path}: size {path.stat().st_size} != expected {dl.size}. Delete it and retry.")
    if dl.md5 and file_hash(path, "md5") != dl.md5:
        raise SystemExit(f"{path}: MD5 mismatch. Delete it and retry.")
    if dl.sha256 and file_hash(path, "sha256") != dl.sha256:
        raise SystemExit(f"{path}: SHA-256 mismatch. Delete it and retry.")
    print(f"ok  {path.name} ({path.stat().st_size / 1e6:.1f} MB) verified")
    return path


def _guard(root: Path, names: list[str]) -> None:
    root = root.resolve()
    for m in names:
        t = (root / m).resolve()
        if t != root and root not in t.parents:
            raise RuntimeError(f"unsafe path in archive: {m}")


def unpack(archive: Path, out: Path, strip: int = 0) -> None:
    if out.exists() and any(out.iterdir()):
        print(f"ok  {out} already unpacked")
        return
    tmp = out.with_name(out.name + ".extracting")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    name = archive.name.lower()
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            _guard(tmp, z.namelist())
            z.extractall(tmp)
    elif name.endswith(".tar.gz"):
        with tarfile.open(archive) as t:
            members = []
            for m in t.getmembers():
                parts = Path(m.name).parts[strip:]
                if not parts or m.issym() or m.islnk():
                    continue
                m.name = str(Path(*parts))
                members.append(m)
            _guard(tmp, [m.name for m in members])
            t.extractall(tmp, members=members)
    elif name.endswith(".rar"):
        unrar = next((p for p in UNRAR_CANDIDATES if p.exists()), None)
        cmd = ([str(unrar), "x", "-o-", "-idq", str(archive), str(tmp) + "\\"] if unrar
               else ["tar", "-xf", str(archive), "-C", str(tmp)])  # Windows 11 bsdtar reads RAR4
        subprocess.run(cmd, check=True)
    else:
        raise ValueError(f"unknown archive type: {archive}")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.rmdir()
    tmp.rename(out)
    print(f"ok  unpacked -> {out}")


STRIP = {"rf100_construction_safety": 8, "rf100_excavators": 8}  # tarballs carry /home/zuppif/... prefixes
_ZIP_PATCH_LOCK = threading.Lock()  # zipfile is patched process-wide while the archive is opened


def read_split_last_part(archive: Path):
    """Open the last part of a split ZIP on its own and return (ZipFile, members stored in that part).

    Python's zipfile refuses archives whose ZIP64 locator names another disk ("span multiple disks").
    The central directory and every member whose data starts in this part are complete, so we read the
    ZIP64 end record without the disk check and keep only members of the last disk."""
    import struct
    import zipfile

    def end_record_any_disk(fpin, offset, endrec):
        fpin.seek(offset - zipfile.sizeEndCentDir64Locator - zipfile.sizeEndCentDir64, 2)
        data = fpin.read(zipfile.sizeEndCentDir64)
        sig, _sz, _cv, _rv, disk_num, disk_dir, n_disk, n_total, cd_size, cd_off = struct.unpack(zipfile.structEndArchive64, data)
        if sig != zipfile.stringEndArchive64:
            return endrec
        endrec[zipfile._ECD_SIGNATURE] = sig
        endrec[zipfile._ECD_DISK_NUMBER] = disk_num
        endrec[zipfile._ECD_DISK_START] = disk_dir
        endrec[zipfile._ECD_ENTRIES_THIS_DISK] = n_disk
        endrec[zipfile._ECD_ENTRIES_TOTAL] = n_total
        endrec[zipfile._ECD_SIZE] = cd_size
        endrec[zipfile._ECD_OFFSET] = cd_off
        return endrec

    with _ZIP_PATCH_LOCK:
        original = zipfile._EndRecData64
        zipfile._EndRecData64 = end_record_any_disk
        try:
            z = zipfile.ZipFile(archive)
        finally:
            zipfile._EndRecData64 = original
    last = max(i.volume for i in z.infolist())
    return z, [i for i in z.infolist() if i.volume == last]


def unpack_kr(archive: Path, out: Path, stride: int = KR_FRAME_STRIDE) -> None:
    """Unpack every `stride`-th frame (with its VOC XML) of the readable part of the KR machinery archive."""
    import re
    if out.exists() and any(out.iterdir()):
        print(f"ok  {out} already unpacked")
        return
    z, members = read_split_last_part(archive)
    names = {i.filename for i in members}
    frame = re.compile(r"_(\d+)\.jpg$")
    picked = no_label = 0
    tmp = out.with_name(out.name + ".extracting")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    with z:
        _guard(tmp, [str(Path(*Path(i.filename).parts[1:])) for i in members if len(Path(i.filename).parts) > 1])
        for i in members:
            m = frame.search(i.filename)
            if "/JPEGImages/" not in i.filename or not m or int(m.group(1)) % stride:
                continue
            xml = i.filename.replace("/JPEGImages/", "/Annotations_xml/")[:-4] + ".xml"
            if xml not in names:
                no_label += 1  # its label is stored in an unpublished part of the archive
                continue
            for member in (i.filename, xml):
                rel = Path(*Path(member).parts[1:])  # drop the top folder "Bbox_dataset_classified"
                dst = tmp / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(z.read(member))
            picked += 1
    if picked == 0:
        shutil.rmtree(tmp)
        raise SystemExit(f"{archive}: no labelled frames found in the readable part of the archive")
    print(f"    {no_label} frames skipped: their labels are in an unpublished part of the archive")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.rmdir()
    tmp.rename(out)
    print(f"ok  unpacked {picked} frames (every {stride}th, with labels) -> {out}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Download + verify the PPE v2 datasets (no accounts needed)")
    ap.add_argument("--only", default="", help="comma-separated source names")
    ap.add_argument("--skip-falls", action="store_true")
    args = ap.parse_args()
    wanted = [s for s in (args.only.split(",") if args.only else TRAIN_SOURCES) if s]
    for name in wanted:
        src = SOURCES[name]
        archive = fetch(src.download, DOWNLOADS_DIR)
        if name == "kr_site_machinery":
            unpack_kr(archive, DATASETS_DIR / name / "raw")
        else:
            unpack(archive, DATASETS_DIR / name / "raw", strip=STRIP.get(name, 0))
    if not args.skip_falls:
        archive = fetch(FALLS, FALLS_DIR)
        target = FALLS_DIR / "GMDCSA24"
        if not target.exists():
            tmp = FALLS_DIR / "_gmdcsa_unpack"
            unpack(archive, tmp)
            inner = next(tmp.iterdir())  # single top-level folder (GitHub release zip)
            inner.rename(target)
            tmp.rmdir()
        print(f"ok  falls clips in {target}")
    print("\nNot downloadable by script (see docs/DATA.md, 'Still needed from Yazeed'): Peru construction-site "
          "machinery dataset (Cloudflare browser check), Roboflow/Kaggle datasets (account or API key).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
