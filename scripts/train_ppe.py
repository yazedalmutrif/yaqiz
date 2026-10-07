"""Fine-tune YOLO11 on Construction-PPE and copy the best weights to models/.

Usage (from the repo root):
    .venv\\Scripts\\python scripts\\train_ppe.py --epochs 100 --model yolo11s.pt

Prints Ultralytics' own training log; writes runs/train/<name>/train_summary.json
with the settings and wall-clock time.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import (  # noqa: E402
    DATASET_NAME,
    DATASETS_DIR,
    MODELS_DIR,
    PPE_BASE_WEIGHTS,
    PPE_WEIGHTS,
    PROJECT_NAME,
    RUNS_DIR,
    configure_ultralytics,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=f"{PROJECT_NAME}: fine-tune YOLO11 on {DATASET_NAME}")
    p.add_argument("--model", default=PPE_BASE_WEIGHTS, help="base weights, e.g. yolo11n.pt / yolo11s.pt")
    p.add_argument("--epochs", type=int, default=100)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--patience", type=int, default=30, help="early-stopping patience (epochs)")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--name", default=None, help="run name (default: ppe_<model>_e<epochs>)")
    p.add_argument("--device", default="0")
    p.add_argument("--force", action="store_true", help="overwrite the existing weights in models/")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    from ultralytics import YOLO

    configure_ultralytics()  # no telemetry; datasets_dir inside the repo

    data_yaml = DATASETS_DIR / f"{DATASET_NAME}.yaml"
    if not data_yaml.exists():
        print(f"Missing {data_yaml}. Run scripts/get_dataset.py first.")
        return 1

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    base = MODELS_DIR / args.model  # Ultralytics downloads the asset to this path if missing
    name = args.name or f"ppe_{Path(args.model).stem}_e{args.epochs}"
    project = RUNS_DIR / "train"

    model = YOLO(str(base))
    t0 = time.perf_counter()
    started = datetime.now(timezone.utc).isoformat()
    model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        patience=args.patience,
        workers=args.workers,
        seed=args.seed,
        deterministic=True,
        device=args.device,
        project=str(project),
        name=name,
        exist_ok=False,
        cache="ram",
        plots=True,
    )
    elapsed = time.perf_counter() - t0

    run_dir = Path(model.trainer.save_dir)
    best = run_dir / "weights" / "best.pt"
    summary = {
        "project": PROJECT_NAME,
        "dataset": DATASET_NAME,
        "base_model": args.model,
        "epochs_requested": args.epochs,
        "epochs_completed": int(model.trainer.epoch) + 1,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "patience": args.patience,
        "seed": args.seed,
        "started_utc": started,
        "wall_clock_seconds": round(elapsed, 1),
        "best_weights": str(best),
    }
    (run_dir / "train_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if best.exists():
        dest = PPE_WEIGHTS if Path(args.model).name == PPE_BASE_WEIGHTS else (
            MODELS_DIR / f"ppe_{Path(args.model).stem}_best.pt"
        )
        if dest.exists() and not args.force:
            print(f"Kept existing {dest} (published numbers depend on it). New weights stay in {best}; "
                  "rerun with --force to replace.")
        else:
            shutil.copy2(best, dest)
            print(f"Copied best weights -> {dest}")
    print(f"TRAINING WALL-CLOCK: {elapsed / 60:.1f} min ({summary['epochs_completed']} epochs)")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
