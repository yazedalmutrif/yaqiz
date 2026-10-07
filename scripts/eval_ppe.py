"""Evaluate the fine-tuned PPE model on a held-out split (default: test).

Prints Ultralytics' per-class table (P, R, mAP50, mAP50-95) and saves the same
numbers to runs/eval/<split>_<weights-stem>/metrics.json.

Usage:  .venv\\Scripts\\python scripts\\eval_ppe.py --split test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import (  # noqa: E402
    DATASET_NAME,
    DATASETS_DIR,
    PPE_WEIGHTS,
    PROJECT_NAME,
    RUNS_DIR,
    configure_ultralytics,
)


def main() -> int:
    p = argparse.ArgumentParser(description=f"{PROJECT_NAME}: evaluate the PPE detector")
    p.add_argument("--weights", default=str(PPE_WEIGHTS))
    p.add_argument("--split", default="test", choices=["val", "test"])
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--device", default="0")
    p.add_argument("--force", action="store_true", help="overwrite an existing metrics.json for this split/weights")
    args = p.parse_args()

    name = f"{args.split}_{Path(args.weights).stem}"
    existing = RUNS_DIR / "eval" / name / "metrics.json"
    if existing.exists() and not args.force:
        print(f"{existing} already exists (published numbers depend on it). Use --force to overwrite.")
        return 1

    from ultralytics import YOLO

    configure_ultralytics()  # no telemetry; datasets_dir inside the repo
    data_yaml = DATASETS_DIR / f"{DATASET_NAME}.yaml"
    model = YOLO(args.weights)
    m = model.val(data=str(data_yaml), split=args.split, imgsz=args.imgsz, device=args.device,
                  project=str(RUNS_DIR / "eval"), name=name, exist_ok=True, plots=True)

    per_class = {}
    for i, c in enumerate(m.ap_class_index):
        pi, ri, ap50, ap = m.box.class_result(i)
        per_class[model.names[int(c)]] = {
            "precision": round(float(pi), 4), "recall": round(float(ri), 4),
            "mAP50": round(float(ap50), 4), "mAP50-95": round(float(ap), 4),
        }
    out = {
        "weights": str(args.weights),
        "weights_sha256": hashlib.sha256(Path(args.weights).read_bytes()).hexdigest(),
        "split": args.split,
        "imgsz": args.imgsz,
        "all": {
            "precision": round(float(m.box.mp), 4), "recall": round(float(m.box.mr), 4),
            "mAP50": round(float(m.box.map50), 4), "mAP50-95": round(float(m.box.map), 4),
        },
        "per_class": per_class,
    }
    out_path = Path(m.save_dir) / "metrics.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Saved {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
