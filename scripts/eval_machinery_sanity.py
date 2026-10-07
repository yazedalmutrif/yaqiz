"""Sanity checks for the machinery class and the machine-proximity rule (run after training PPE v2).

1. False machinery on worker photos: run the PPE model at the live system's settings (det_conf, imgsz)
   on the TEST splits of the sources that contain no labelled machinery (worker photos), count images
   with any machinery box, and save the most confident boxes as a review sheet. Real machines do appear
   in a few of these photos, so the count is an upper bound on false alarms, not an exact rate.
2. Proximity rule on real scenes: on the machinery test splits, run the COCO person detector and the
   PPE model, apply yaqiz.vision.analysis.near_machine, and save a sheet (red = near, green = not near).

Usage (repo root):  .venv\\Scripts\\python scripts\\eval_machinery_sanity.py [--weights models\\ppe_v2.pt]
Writes runs/eval/machinery_sanity.json and runs/eval/machinery_*.jpg (internal only: dataset images
show identifiable people, do not publish).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from data_common import SOURCES, SOURCES_DIR, images_in  # noqa: E402
from yaqiz.config import RuntimeSettings, Settings  # noqa: E402

OUT = ROOT / "runs" / "eval"
WORKER_SOURCES = [s for s, src in SOURCES.items() if "machinery" not in src.labelled]
MACHINE_SOURCES = [s for s, src in SOURCES.items() if "machinery" in src.labelled]


def tile(img: np.ndarray, size: int = 360) -> np.ndarray:
    h, w = img.shape[:2]
    s = size / max(h, w)
    im = cv2.resize(img, (round(w * s), round(h * s)))
    canvas = np.full((size, size, 3), 40, np.uint8)
    canvas[: im.shape[0], : im.shape[1]] = im
    return canvas


def sheet(tiles: list[np.ndarray], cols: int = 4) -> np.ndarray:
    blank = np.zeros_like(tiles[0])
    rows = [np.hstack(tiles[i:i + cols] + [blank] * (cols - len(tiles[i:i + cols]))) for i in range(0, len(tiles), cols)]
    return np.vstack(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default=str(ROOT / "models" / "ppe_v2.pt"))
    ap.add_argument("--device", default="0", help='GPU index, or "cpu"')
    args = ap.parse_args()
    from ultralytics import YOLO
    from yaqiz.vision.analysis import near_machine
    from yaqiz.vision.engine import CANONICAL, Det

    settings, rt = Settings(), RuntimeSettings()
    ppe = YOLO(args.weights)
    person = YOLO(str(settings.model_path(settings.person_weights)))
    mach_ids = [i for i, n in ppe.names.items() if CANONICAL.get(str(n).lower()) == "machinery"]
    if not mach_ids:
        raise SystemExit(f"{args.weights} has no machinery class")
    report: dict = {"weights": args.weights, "det_conf": rt.det_conf, "imgsz": settings.imgsz,
                    "machine_gap": rt.machine_gap, "worker_photo_test_sets": {}, "machine_test_sets": {}}
    OUT.mkdir(parents=True, exist_ok=True)

    # 1) machinery boxes on worker photos
    worst = []
    for src in WORKER_SOURCES:
        imgs = images_in(SOURCES_DIR / src / "images" / "test")
        n_img = n_box = 0
        for i in range(0, len(imgs), 16):
            res = ppe.predict([str(p) for p in imgs[i:i + 16]], imgsz=settings.imgsz, conf=rt.det_conf,
                              classes=mach_ids, device=args.device, verbose=False)
            for p, r in zip(imgs[i:i + 16], res):
                k = len(r.boxes)
                n_box += k
                n_img += k > 0
                for b, c in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy()):
                    worst.append((float(c), p, tuple(map(int, b))))
        report["worker_photo_test_sets"][src] = {"images": len(imgs), "images_with_machinery_box": n_img,
                                                 "machinery_boxes": n_box}
        print(src, report["worker_photo_test_sets"][src], flush=True)
    worst.sort(key=lambda x: -x[0])
    tiles = []
    for c, p, (x1, y1, x2, y2) in worst[:16]:
        im = cv2.imread(str(p))
        cv2.rectangle(im, (x1, y1), (x2, y2), (0, 140, 255), max(2, im.shape[1] // 300))
        cv2.putText(im, f"machinery {c:.2f}", (x1, max(14, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 140, 255), 2)
        tiles.append(tile(im))
    if tiles:
        cv2.imwrite(str(OUT / "machinery_on_worker_photos_top16.jpg"), sheet(tiles), [cv2.IMWRITE_JPEG_QUALITY, 80])

    # 2) the proximity rule on machinery scenes
    tiles = []
    for src in MACHINE_SOURCES:
        imgs = images_in(SOURCES_DIR / src / "images" / "test")
        stats = {"images": len(imgs), "images_with_person_and_machine": 0, "persons_near": 0, "persons_not_near": 0}
        examples = []
        for i in range(0, len(imgs), 16):
            chunk = imgs[i:i + 16]
            rp = person.predict([str(p) for p in chunk], classes=[0], conf=rt.pose_conf, imgsz=settings.imgsz,
                                device=args.device, verbose=False)
            rm = ppe.predict([str(p) for p in chunk], classes=mach_ids, conf=rt.det_conf, imgsz=settings.imgsz,
                             device=args.device, verbose=False)
            for p, a, b in zip(chunk, rp, rm):
                people = [tuple(map(float, x)) for x in a.boxes.xyxy.cpu().numpy()]
                machines = [Det("machinery", float(c), tuple(map(float, x)))
                            for x, c in zip(b.boxes.xyxy.cpu().numpy(), b.boxes.conf.cpu().numpy())]
                if not people or not machines:
                    continue
                stats["images_with_person_and_machine"] += 1
                flags = [near_machine(pb, ((pb[0] + pb[2]) / 2, pb[3]), machines, rt.machine_gap) for pb in people]
                stats["persons_near"] += sum(flags)
                stats["persons_not_near"] += len(flags) - sum(flags)
                examples.append((p, people, machines, flags))
        report["machine_test_sets"][src] = stats
        print(src, stats, flush=True)
        random.Random(0).shuffle(examples)
        for p, people, machines, flags in examples[:8]:
            im = cv2.imread(str(p))
            t = max(2, im.shape[1] // 300)
            for m in machines:
                x1, y1, x2, y2 = map(int, m.xyxy)
                cv2.rectangle(im, (x1, y1), (x2, y2), (0, 140, 255), t)
            for pb, f in zip(people, flags):
                x1, y1, x2, y2 = map(int, pb)
                cv2.rectangle(im, (x1, y1), (x2, y2), (40, 40, 230) if f else (80, 200, 80), t)
            tiles.append(tile(im))
    if tiles:
        cv2.imwrite(str(OUT / "machine_proximity_examples.jpg"), sheet(tiles), [cv2.IMWRITE_JPEG_QUALITY, 80])
    (OUT / "machinery_sanity.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
