"""Contact sheets for eyeballing labels: original labels (solid) and pseudo-labels (dashed, with confidence).

Usage:
    .venv\\Scripts\\python scripts\\data_review.py --root sources --source chvg --split train -n 12
    .venv\\Scripts\\python scripts\\data_review.py --root merged --source gdut_hwd --split train --pseudo-only -n 16

Sheets go to runs/ppe_v2/review/. Do not publish them: dataset images show identifiable people.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_common import CLASSES, MERGED_DIR, SOURCES_DIR, V2_RUN_DIR, images_in, label_for, pseudo_path, read_yolo  # noqa: E402

COLORS = {"helmet": (0, 200, 255), "head": (0, 0, 255), "vest": (0, 255, 0), "machinery": (255, 128, 0)}


def load_pseudo(source: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    p = pseudo_path(source)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            out.setdefault(r["image"], []).append(r)
    return out


def dashed_rect(img, p1, p2, color, thickness=2, dash=8):
    (x1, y1), (x2, y2) = p1, p2
    for x in range(x1, x2, dash * 2):
        cv2.line(img, (x, y1), (min(x + dash, x2), y1), color, thickness)
        cv2.line(img, (x, y2), (min(x + dash, x2), y2), color, thickness)
    for y in range(y1, y2, dash * 2):
        cv2.line(img, (x1, y), (x1, min(y + dash, y2)), color, thickness)
        cv2.line(img, (x2, y), (x2, min(y + dash, y2)), color, thickness)


def render(img_path: Path, orig: list, pseudo: list[dict], tile: int = 480) -> np.ndarray:
    im = cv2.imread(str(img_path))
    h, w = im.shape[:2]
    s = tile / max(h, w)
    im = cv2.resize(im, (round(w * s), round(h * s)))
    h, w = im.shape[:2]
    for c, xc, yc, bw, bh in orig:
        name = CLASSES[c]
        p1 = (int((xc - bw / 2) * w), int((yc - bh / 2) * h))
        p2 = (int((xc + bw / 2) * w), int((yc + bh / 2) * h))
        cv2.rectangle(im, p1, p2, COLORS[name], 2)
        cv2.putText(im, name, (p1[0], max(10, p1[1] - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLORS[name], 1)
    for r in pseudo:
        x1, y1, x2, y2 = r["xyxyn"]
        p1, p2 = (int(x1 * w), int(y1 * h)), (int(x2 * w), int(y2 * h))
        dashed_rect(im, p1, p2, COLORS[r["cls"]], 2)
        cv2.putText(im, f"P:{r['cls']} {r['conf']:.2f}", (p1[0], min(h - 3, p2[1] + 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLORS[r["cls"]], 1)
    canvas = np.full((tile, tile, 3), 40, np.uint8)
    canvas[:h, :w] = im
    cv2.putText(canvas, img_path.name[:60], (4, tile - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    return canvas


def sheet(tiles: list[np.ndarray], cols: int = 4) -> np.ndarray:
    rows = [np.hstack(tiles[i:i + cols] + [np.zeros_like(tiles[0])] * (cols - len(tiles[i:i + cols])))
            for i in range(0, len(tiles), cols)]
    return np.vstack(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", choices=["sources", "merged"], default="sources")
    ap.add_argument("--source", required=True)
    ap.add_argument("--split", default="train")
    ap.add_argument("-n", type=int, default=12)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--pseudo-only", action="store_true", help="only images that received pseudo-labels")
    ap.add_argument("--cls", default="", help="with --pseudo-only: only images with pseudo-labels of this class")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    base = (SOURCES_DIR if args.root == "sources" else MERGED_DIR) / args.source
    imgs = images_in(base / "images" / args.split)
    pseudo = load_pseudo(args.source)
    if args.pseudo_only:
        keep = {k for k, v in pseudo.items() if not args.cls or any(r["cls"] == args.cls for r in v)}
        imgs = [p for p in imgs if p.name in keep]
    elif args.cls:  # images whose ORIGINAL labels contain this class
        cid = CLASSES.index(args.cls)
        imgs = [p for p in imgs
                if any(r[0] == cid for r in read_yolo(label_for(SOURCES_DIR / args.source / "images" / args.split / p.name)))]
    random.Random(args.seed).shuffle(imgs)
    imgs = imgs[: args.n]
    if not imgs:
        print("nothing to show")
        return 1
    orig_root = SOURCES_DIR / args.source
    tiles = []
    for p in imgs:
        orig = read_yolo(label_for(orig_root / "images" / args.split / p.name))
        tiles.append(render(p, orig, pseudo.get(p.name, []) if args.root == "merged" else []))
    out = V2_RUN_DIR / "review" / f"{args.root}_{args.source}_{args.split}{'_' + args.tag if args.tag else ''}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), sheet(tiles), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
