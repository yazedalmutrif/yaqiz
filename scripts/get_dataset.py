"""Download, verify and unpack the Ultralytics Construction-PPE dataset into data/datasets/.

- Downloads to a .part file and renames it only when complete.
- Checks the SHA-256 against the value recorded in DATASETS.md and stops if it differs.
- Extracts into a temporary folder (with a path-traversal guard), then renames it.
- Writes data/datasets/construction-ppe.yaml with an absolute `path`, so training
  never touches the global Ultralytics datasets folder.

Usage:  .venv\\Scripts\\python scripts\\get_dataset.py
"""
from __future__ import annotations

import hashlib
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import DATASET_CLASSES, DATASET_NAME, DATASET_URL, DATASETS_DIR  # noqa: E402

EXPECTED_SHA256 = "bef8dcb599aa4e9d9f5e602cb6fa7143d3c84d7f6a0ff40463d7f2a4c2632ccc"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DATASETS_DIR / f"{DATASET_NAME}.zip"
    ds_dir = DATASETS_DIR / DATASET_NAME

    if not zip_path.exists():
        part = zip_path.with_suffix(".zip.part")
        print(f"Downloading {DATASET_URL}")
        urllib.request.urlretrieve(DATASET_URL, part)  # noqa: S310 (fixed https URL)
        part.replace(zip_path)
    digest = sha256(zip_path)
    print(f"zip: {zip_path} ({zip_path.stat().st_size / 1e6:.1f} MB) sha256={digest}")
    if digest != EXPECTED_SHA256:
        print(f"ERROR: sha256 differs from the recorded {EXPECTED_SHA256}. "
              "Delete the zip and retry, or update DATASETS.md if Ultralytics changed the file.")
        return 1

    if not ds_dir.exists():
        # The zip has no top-level folder (images/, labels/, LICENSE, data.yaml).
        tmp = DATASETS_DIR / f"{DATASET_NAME}.extracting"
        if tmp.exists():
            shutil.rmtree(tmp)  # leftover from an interrupted run of this script
        with zipfile.ZipFile(zip_path) as zf:
            root = tmp.resolve()
            for member in zf.namelist():  # guard against path traversal
                target = (tmp / member).resolve()
                if root not in target.parents and target != root:
                    raise RuntimeError(f"Unsafe path in zip: {member}")
            zf.extractall(tmp)
        tmp.rename(ds_dir)

    for split in ("train", "val", "test"):
        imgs = list((ds_dir / "images" / split).glob("*"))
        labels = list((ds_dir / "labels" / split).glob("*.txt"))
        print(f"{split:5s}: {len(imgs)} images, {len(labels)} label files")

    yaml_path = DATASETS_DIR / f"{DATASET_NAME}.yaml"
    lines = [
        f"path: {ds_dir.resolve().as_posix()}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "names:",
        *[f"  {i}: {n}" for i, n in DATASET_CLASSES.items()],
    ]
    yaml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {yaml_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
