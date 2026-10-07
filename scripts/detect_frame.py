"""Run the fine-tuned PPE detector on one frame of a video (or an image) and save an annotated PNG.

Shows the raw detector output (class + confidence), with no tracking or zones.

Usage:
  .venv\\Scripts\\python scripts\\detect_frame.py --video data\\videos\\pexels_5434223.mp4 --time 10
  .venv\\Scripts\\python scripts\\detect_frame.py --image some.jpg
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import overlay  # noqa: E402
from core.config import PPE_WEIGHTS, PROJECT_NAME, RUNS_DIR, configure_ultralytics  # noqa: E402

SHOW = {"helmet", "no_helmet", "vest", "Person"}
COLOURS = {"helmet": (60, 190, 60), "no_helmet": (0, 165, 255), "vest": (0, 220, 230), "Person": (200, 200, 200)}


def main() -> int:
    p = argparse.ArgumentParser(description=f"{PROJECT_NAME}: PPE detector on a single frame")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--video")
    src.add_argument("--image")
    p.add_argument("--time", type=float, default=0.0, help="seconds into the video")
    p.add_argument("--weights", default=str(PPE_WEIGHTS))
    p.add_argument("--imgsz", type=int, default=960)
    p.add_argument("--conf", type=float, default=0.35)
    p.add_argument("--max-side", type=int, default=1920)
    p.add_argument("--out", default=None)
    p.add_argument("--device", default="0")
    args = p.parse_args()

    from ultralytics import YOLO

    configure_ultralytics()  # no telemetry; datasets_dir inside the repo

    if args.video:
        cap = cv2.VideoCapture(args.video)
        cap.set(cv2.CAP_PROP_POS_MSEC, args.time * 1000.0)
        ok, frame = cap.read()
        cap.release()
        stem = f"{Path(args.video).stem}_t{args.time:.1f}"
    else:
        frame = cv2.imread(args.image)
        ok = frame is not None
        stem = Path(args.image).stem
    if not ok:
        print("Could not read the frame")
        return 1
    h, w = frame.shape[:2]
    if args.max_side and max(h, w) > args.max_side:
        s = args.max_side / max(h, w)
        frame = cv2.resize(frame, (int(round(w * s)), int(round(h * s))), interpolation=cv2.INTER_AREA)

    model = YOLO(args.weights)
    r = model.predict(frame, conf=args.conf, imgsz=args.imgsz, device=args.device, verbose=False)[0]
    vis = frame.copy()
    sc = max(0.5, max(vis.shape[:2]) / 1920.0)
    counts: dict[str, int] = {}
    for b, c, conf in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.cls.cpu().numpy(), r.boxes.conf.cpu().numpy()):
        name = model.names[int(c)]
        if name not in SHOW:
            continue
        counts[name] = counts.get(name, 0) + 1
        x1, y1, x2, y2 = (int(v) for v in b)
        col = COLOURS[name]
        cv2.rectangle(vis, (x1, y1), (x2, y2), col, max(2, int(3 * sc)), cv2.LINE_AA)
        overlay.label(vis, f"{name} {conf:.2f}", (x1, y1 - int(3 * sc)), col, fg=(20, 20, 20))
        print(f"{name:10s} conf={conf:.3f} box=({x1},{y1},{x2},{y2})")
    summary = "  ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "no detections"
    overlay.draw_header(vis, "PPE detector (YOLO11s fine-tuned)", summary)

    out = Path(args.out) if args.out else RUNS_DIR / "detect" / f"{stem}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), vis)
    print(f"Saved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
