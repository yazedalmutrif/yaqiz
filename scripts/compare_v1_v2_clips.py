"""Compare the v1 (Sprint 0) and v2 PPE models on frames from the three demo clips, at the live settings.

Six evenly spaced frames per clip; detections at the live confidence (RuntimeSettings.det_conf) and image
size (Settings.imgsz), counted per class. There are no labels for these clips, so this is a qualitative
check: the side-by-side sheet shows which detections are right.

Usage (repo root):  .venv\\Scripts\\python scripts\\compare_v1_v2_clips.py
Writes runs/eval/demo_clips_v1_vs_v2.json (counts) and runs/eval/demo_clips_v1_vs_v2.jpg (internal only:
stock footage with people; do not publish without blurring brand marks, see MEDIA_SOURCES.md).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from yaqiz.config import RuntimeSettings, Settings  # noqa: E402
from yaqiz.vision.engine import CANONICAL  # noqa: E402
from yaqiz.vision.sources import resize_max_side  # noqa: E402

CLIPS = {"CAM-01 slab edge": "data/videos/pexels_11798561.mp4",
         "CAM-02 pour (portrait)": "data/videos/derived/pexels_35631533_720p.mp4",
         "CAM-03 entrance": "data/videos/derived/pexels_5434223_720p.mp4"}
MODELS = {"v1": "models/ppe_yolo11s_best.pt", "v2": "models/ppe_v2.pt"}
COLORS = {"helmet": (0, 200, 255), "head": (0, 0, 255), "vest": (0, 255, 0), "machinery": (255, 128, 0)}


def main() -> int:
    from ultralytics import YOLO

    s, rt = Settings(), RuntimeSettings()
    models = {k: YOLO(str(ROOT / v)) for k, v in MODELS.items()}
    summary: dict = {"generated_utc": datetime.now(timezone.utc).isoformat(), "det_conf": rt.det_conf,
                     "imgsz": s.imgsz, "frames_per_clip": 6, "models": MODELS, "clips": {}}
    rows = []
    for name, rel in CLIPS.items():
        cap = cv2.VideoCapture(str(ROOT / rel))
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        counts: dict[str, dict[str, int]] = {m: {} for m in models}
        for k, idx in enumerate(np.linspace(0, n - 1, 6).astype(int)):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ok, frame = cap.read()
            if not ok:
                continue
            frame = resize_max_side(frame, s.max_side)
            pair = []
            for m, model in models.items():
                r = model.predict(frame, imgsz=s.imgsz, conf=rt.det_conf, device=0, verbose=False)[0]
                img = frame.copy()
                for b, c, cf in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.cls.cpu().numpy(), r.boxes.conf.cpu().numpy()):
                    canon = CANONICAL.get(str(model.names[int(c)]).lower())
                    if not canon:
                        continue
                    counts[m][canon] = counts[m].get(canon, 0) + 1
                    x1, y1, x2, y2 = map(int, b)
                    cv2.rectangle(img, (x1, y1), (x2, y2), COLORS[canon], 2)
                    cv2.putText(img, f"{canon} {cf:.2f}", (x1, max(12, y1 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                                COLORS[canon], 1)
                cv2.putText(img, m, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
                pair.append(cv2.resize(img, (640, int(640 * img.shape[0] / img.shape[1]))))
            if k in (1, 4):
                h = max(p.shape[0] for p in pair)
                rows.append(np.hstack([np.vstack([p, np.zeros((h - p.shape[0], p.shape[1], 3), np.uint8)]) for p in pair]))
        cap.release()
        summary["clips"][name] = {"file": rel, **{f"{m}_detections": counts[m] for m in models}}
        print(name, json.dumps(summary["clips"][name]), flush=True)
    out_dir = ROOT / "runs" / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "demo_clips_v1_vs_v2.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    w = max(r.shape[1] for r in rows)
    sheet = np.vstack([np.hstack([r, np.zeros((r.shape[0], w - r.shape[1], 3), np.uint8)]) for r in rows])
    cv2.imwrite(str(out_dir / "demo_clips_v1_vs_v2.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 75])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
