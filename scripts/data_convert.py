"""Convert every source to YOLO format with the unified classes (helmet, head, vest, machinery).

Output per source (original labels only, no pseudo-labels):
    data/datasets/ppe_v2/sources/<source>/images/{train,val,test}/<file>
    data/datasets/ppe_v2/sources/<source>/labels/{train,val,test}/<stem>.txt
    data/datasets/ppe_v2/sources/<source>/manifest.csv   (one row per image)
    data/datasets/ppe_v2/sources/<source>/stats.json     (class counts, mapping counts, fixes)

Images are hard-linked from data/datasets/<source>/raw (copied if linking fails). Images
whose EXIF orientation tag would make Ultralytics rotate them away from the annotation
frame are re-saved without the tag (pixels unchanged) and counted in stats.json.

Usage:  .venv\\Scripts\\python scripts\\data_convert.py [--only chvg,gdut_hwd] [--force]
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_common import (  # noqa: E402
    CLASSES, CLS_ID, DATASETS_DIR, KR_SPLIT_BY_DATE, SOURCES, SOURCES_DIR, seeded_split, yolo_line)

ORIENTATION_TAG = 0x0112


def image_size_and_orientation(path: Path) -> tuple[int, int, int]:
    with Image.open(path) as im:
        w, h = im.size
        try:
            o = int(im.getexif().get(ORIENTATION_TAG, 1))
        except Exception:  # noqa: BLE001 (corrupt EXIF: treat as upright)
            o = 1
    return w, h, o


def place_image(src: Path, dst: Path, orientation: int) -> bool:
    """Hard-link (or copy) src to dst. If the EXIF orientation is not 1, re-save the raw
    pixels without the tag so loaders and annotations agree. Returns True if re-saved."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return orientation not in (0, 1)
    if orientation not in (0, 1):
        with Image.open(src) as im:
            exif = im.getexif()
            exif[ORIENTATION_TAG] = 1
            im.save(dst, quality=95, exif=exif.tobytes()) if dst.suffix.lower() in (".jpg", ".jpeg") else im.save(dst)
        return True
    import os
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)
    return False


# ---- Readers: yield (split, image_path, [(raw_name, x1, y1, x2, y2)], ann_w, ann_h) -------------
def read_voc(xml_path: Path) -> tuple[list[tuple[str, float, float, float, float]], int, int]:
    root = ET.parse(xml_path).getroot()
    size = root.find("size")
    aw = int(float(size.findtext("width") or 0)) if size is not None else 0
    ah = int(float(size.findtext("height") or 0)) if size is not None else 0
    boxes = []
    for o in root.findall("object"):
        name = (o.findtext("name") or "").strip()
        bb = o.find("bndbox")
        if bb is None:
            continue
        x1, y1, x2, y2 = (float(bb.findtext(k) or 0) for k in ("xmin", "ymin", "xmax", "ymax"))
        boxes.append((name, x1, y1, x2, y2))
    return boxes, aw, ah


def items_hardhat(raw: Path):
    base = raw / "Hardhat"
    train_ids = sorted(p.stem for p in (base / "Train" / "Annotation").glob("*.xml"))
    split = seeded_split(train_ids, {"train": 0.9, "val": 0.1}, seed=0)
    for part, folder in (("Train", "Train"), ("Test", "Test")):
        for xml in sorted((base / folder / "Annotation").glob("*.xml")):
            img = base / folder / "JPEGImage" / f"{xml.stem}.jpg"
            s = split[xml.stem] if part == "Train" else "test"
            yield s, img, *read_voc(xml)


def items_gdut(raw: Path):
    trainval = (raw / "ImageSets" / "Main" / "trainval.txt").read_text().split()
    test = (raw / "ImageSets" / "Main" / "test.txt").read_text().split()
    split = seeded_split(trainval, {"train": 0.9, "val": 0.1}, seed=0)
    split.update(seeded_split(test, {"test": 500 / len(test), "train": 1 - 500 / len(test)}, seed=0))
    imgs = {p.stem: p for p in (raw / "JPEGImages").iterdir()}
    for sid in sorted(split):
        yield split[sid], imgs[sid], *read_voc(raw / "Annotations" / f"{sid}.xml")


def items_chvg(raw: Path):
    folder = raw / "CHVG-Dataset"
    stems = sorted(p.stem for p in folder.glob("*.xml"))
    split = seeded_split(stems, {"train": 0.75, "val": 0.10, "test": 0.15}, seed=0)
    for st in stems:
        yield split[st], folder / f"{st}.jpg", *read_voc(folder / f"{st}.xml")


def items_coco(raw: Path, video_frames_to_train: bool = False):
    for part, s in (("train", "train"), ("valid", "val"), ("test", "test")):
        d = json.loads((raw / part / "_annotations.coco.json").read_text(encoding="utf-8"))
        cats = {c["id"]: c["name"] for c in d["categories"]}
        anns = collections.defaultdict(list)
        for a in d["annotations"]:
            x, y, w, h = a["bbox"]
            anns[a["image_id"]].append((cats[a["category_id"]], x, y, x + w, y + h))
        for im in sorted(d["images"], key=lambda i: i["file_name"]):
            split = s
            if video_frames_to_train and re.search(r"_mp4-\d+_jpg", im["file_name"]):
                split = "train"
            yield split, raw / part / im["file_name"], anns[im["id"]], im["width"], im["height"]


def items_kr(raw: Path):
    """raw/<date>_<weather>/<camera>/{JPEGImages,Annotations_xml}; split by recording date."""
    for xml in sorted(raw.glob("*/*/Annotations_xml/*.xml")):
        date = xml.parts[-4].split("_")[0]
        img = xml.parent.parent / "JPEGImages" / f"{xml.stem}.jpg"
        yield KR_SPLIT_BY_DATE.get(date, "train"), img, *read_voc(xml)


def items_cppe(_raw: Path):
    import yaml
    ds = DATASETS_DIR / "construction-ppe"
    names = yaml.safe_load((DATASETS_DIR / "construction-ppe.yaml").read_text(encoding="utf-8"))["names"]
    for img in sorted((ds / "images" / "test").iterdir()):
        w, h, _ = image_size_and_orientation(img)
        boxes = []
        lab = ds / "labels" / "test" / f"{img.stem}.txt"
        for line in (lab.read_text().splitlines() if lab.exists() else []):
            c, xc, yc, bw, bh = line.split()[:5]
            xc, yc, bw, bh = float(xc) * w, float(yc) * h, float(bw) * w, float(bh) * h
            boxes.append((names[int(c)], xc - bw / 2, yc - bh / 2, xc + bw / 2, yc + bh / 2))
        yield "test", img, boxes, w, h


READERS = {
    "hardhat_xie": items_hardhat,
    "gdut_hwd": items_gdut,
    "chvg": items_chvg,
    "rf100_construction_safety": lambda raw: items_coco(raw),
    "rf100_excavators": lambda raw: items_coco(raw, video_frames_to_train=True),
    "kr_site_machinery": items_kr,
    "cppe_test": items_cppe,
}


def convert(name: str, force: bool) -> dict:
    src = SOURCES[name]
    out = SOURCES_DIR / name
    if out.exists():
        if not force:
            print(f"skip {name}: {out} exists (use --force to rebuild)")
            return json.loads((out / "stats.json").read_text(encoding="utf-8"))
        shutil.rmtree(out)
    raw = DATASETS_DIR / name / "raw"
    unknown = collections.Counter()
    mapped = collections.Counter()
    per_split = {s: collections.Counter() for s in ("train", "val", "test")}
    images_per_split = collections.Counter()
    resaved = size_mismatch = dropped_degenerate = 0
    rows = []
    for split, img, boxes, aw, ah in READERS[name](raw):
        w, h, orient = image_size_and_orientation(img)
        if (aw, ah) != (w, h) and aw and ah:
            size_mismatch += 1  # annotation header disagrees with the pixels: rescale boxes
        sx, sy = (w / aw, h / ah) if aw and ah else (1.0, 1.0)
        lines = []
        counts = collections.Counter()
        for raw_name, x1, y1, x2, y2 in boxes:
            if raw_name not in src.class_map:
                unknown[raw_name] += 1
                continue
            uni = src.class_map[raw_name]
            mapped[f"{raw_name} -> {uni or 'dropped'}"] += 1
            if uni is None:
                continue
            line = yolo_line(CLS_ID[uni], x1 * sx, y1 * sy, x2 * sx, y2 * sy, w, h)
            if line is None:
                dropped_degenerate += 1
                continue
            lines.append(line)
            counts[uni] += 1
        fname = re.sub(r"[^\w.\-]", "_", img.name)
        dst_img = out / "images" / split / fname
        if place_image(img, dst_img, orient):
            resaved += 1
        lab = out / "labels" / split / f"{Path(fname).stem}.txt"
        lab.parent.mkdir(parents=True, exist_ok=True)
        lab.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        per_split[split].update(counts)
        images_per_split[split] += 1
        orig = img.relative_to(raw) if raw in img.parents else img.relative_to(DATASETS_DIR)
        rows.append({"split": split, "image": dst_img.relative_to(out).as_posix(), "original": orig.as_posix(),
                     "width": w, "height": h, **{c: counts.get(c, 0) for c in CLASSES}})
    if unknown:
        raise SystemExit(f"{name}: unmapped raw classes {dict(unknown)}; add them to the class_map")
    with (out / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    stats = {
        "source": name, "licence": src.licence, "labelled_classes": sorted(src.labelled),
        "split_policy": src.split_note,
        "images": dict(images_per_split),
        "boxes": {s: dict(per_split[s]) for s in per_split if images_per_split[s]},
        "mapping_counts": dict(sorted(mapped.items())),
        "exif_rotated_resaved": resaved, "annotation_size_mismatch_rescaled": size_mismatch,
        "degenerate_boxes_dropped": dropped_degenerate,
    }
    (out / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=1))
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description="Convert sources to unified YOLO labels")
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    names = [n for n in (args.only.split(",") if args.only else SOURCES) if n]
    for n in names:
        convert(n, args.force)
    allstats = {p.parent.name: json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(SOURCES_DIR.glob("*/stats.json"))}
    (SOURCES_DIR / "all_stats.json").write_text(json.dumps(allstats, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
