"""Train PPE detector v2 (helmet, head, vest, machinery) on the merged permissive data, then
evaluate it per source, per class across sources, and against the Sprint-0 model (v1).

Steps before this one: data_download.py -> data_convert.py -> data_dedupe.py ->
data_pseudolabel.py (teacher ppe, teacher mach, check, label, filter) -> data_build.py. See docs/DATA.md.

Usage (repo root):
    .venv\\Scripts\\python scripts\\train_ppe_v2.py --epochs 80 --patience 15
    .venv\\Scripts\\python scripts\\train_ppe_v2.py --eval-only --weights runs\\train\\ppe_v2_yolo11s\\weights\\best.pt

Outputs: runs/train/<name>/ (Ultralytics run), runs/ppe_v2/eval/ (one folder per test set),
runs/ppe_v2_metrics.json (all numbers below, copied from Ultralytics' validator), and
models/ppe_v2.pt (best weights; refuses to overwrite without --force).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import RUNS_DIR, configure_ultralytics  # noqa: E402
from data_common import (  # noqa: E402
    CLASSES, MODELS_DIR, SOURCES, TRAIN_SOURCES, V1_WEIGHTS, V2_DIR, V2_RUN_DIR, V2_WEIGHTS, file_hash)

METRICS_JSON = RUNS_DIR / "ppe_v2_metrics.json"
V1_CLASS_FOR = {"helmet": "helmet", "head": "no_helmet", "vest": "vest"}


def val_table(model, data: Path, name: str, imgsz: int, batch: int) -> dict:
    """Run Ultralytics val on the 'test' entry of `data`; return per-class rows exactly as the validator reports."""
    m = model.val(data=str(data), split="test", imgsz=imgsz, batch=batch, device="0", plots=True,
                  project=str(V2_RUN_DIR / "eval"), name=name, exist_ok=True, verbose=True)
    rows = {}
    for i, c in enumerate(m.box.ap_class_index):
        p, r, ap50, ap = m.box.class_result(i)
        rows[model.names[int(c)]] = {"images": int(m.nt_per_image[int(c)]), "instances": int(m.nt_per_class[int(c)]),
                                     "precision": round(float(p), 4), "recall": round(float(r), 4),
                                     "mAP50": round(float(ap50), 4), "mAP50-95": round(float(ap), 4)}
    return {"rows": rows, "speed_ms_per_image": {k: round(v, 2) for k, v in m.speed.items()}}


def evaluate(weights: Path, imgsz: int, batch: int) -> dict:
    from ultralytics import YOLO
    v2 = YOLO(str(weights))
    v1 = YOLO(str(V1_WEIGHTS))
    tag = weights.parent.parent.name if weights.parent.name == "weights" else weights.stem
    out: dict = {"per_source": {}, "combined": {}, "v1_vs_v2": {}}
    for src, s in SOURCES.items():
        res = val_table(v2, V2_DIR / f"test_{src}.yaml", f"{tag}__{src}", imgsz, batch)
        rows = {c: v for c, v in res["rows"].items() if c in s.labelled}  # score only what the source labels
        out["per_source"][src] = {
            "test_images": sum(1 for _ in open(V2_DIR / "lists" / f"test_{src}.txt", encoding="utf-8")),
            "labelled_classes": sorted(s.labelled), "classes": rows,
            "mean_mAP50_over_labelled": round(sum(v["mAP50"] for v in rows.values()) / max(1, len(rows)), 4),
            "speed_ms_per_image": res["speed_ms_per_image"]}
        shared = [c for c in V1_CLASS_FOR if c in s.labelled]
        if shared:
            r1 = val_table(v1, V2_DIR / "v1space" / f"test_{src}.yaml", f"v1__{src}", imgsz, batch)["rows"]
            out["v1_vs_v2"][src] = {c: {"v1": r1.get(V1_CLASS_FOR[c]), "v2": rows.get(c)} for c in shared}
    for cls in CLASSES:
        srcs = [s for s in TRAIN_SOURCES if cls in SOURCES[s].labelled]
        res = val_table(v2, V2_DIR / f"test_combined_{cls}.yaml", f"{tag}__combined_{cls}", imgsz, batch)
        out["combined"][cls] = {"sources": srcs, **(res["rows"].get(cls) or {})}
        if cls in V1_CLASS_FOR:
            r1 = val_table(v1, V2_DIR / "v1space" / f"test_combined_{cls}.yaml", f"v1__combined_{cls}", imgsz, batch)
            out["v1_vs_v2"][f"combined_{cls}"] = {cls: {"v1": r1["rows"].get(V1_CLASS_FOR[cls]),
                                                       "v2": res["rows"].get(cls)}}
    vals = [v["mAP50"] for v in out["combined"].values() if "mAP50" in v]
    out["combined_mean_mAP50"] = round(sum(vals) / len(vals), 4) if vals else None
    return out


def print_tables(ev: dict) -> None:
    print("\nPer-source test splits (v2, only the classes each source labels):")
    print(f"{'source':28s} {'class':10s} {'imgs':>5s} {'inst':>6s} {'P':>6s} {'R':>6s} {'mAP50':>6s} {'mAP50-95':>8s}")
    for src, d in ev["per_source"].items():
        for c, v in d["classes"].items():
            print(f"{src:28s} {c:10s} {v['images']:5d} {v['instances']:6d} {v['precision']:6.3f} {v['recall']:6.3f} "
                  f"{v['mAP50']:6.3f} {v['mAP50-95']:8.3f}")
    print("\nCombined (union of the test splits of every source that labels the class):")
    for c, v in ev["combined"].items():
        if "mAP50" in v:
            print(f"  {c:10s} inst {v['instances']:6d}  P {v['precision']:.3f}  R {v['recall']:.3f}  "
                  f"mAP50 {v['mAP50']:.3f}  mAP50-95 {v['mAP50-95']:.3f}   sources: {', '.join(v['sources'])}")
    print("\nv1 (Sprint 0, models/ppe_yolo11s_best.pt) vs v2 on the same test boxes (mAP50 / mAP50-95):")
    for test, d in ev["v1_vs_v2"].items():
        for c, pair in d.items():
            f = lambda r: f"{r['mAP50']:.3f} / {r['mAP50-95']:.3f}" if r else "n/a"  # noqa: E731
            print(f"  {test:28s} {c:7s} v1 {f(pair['v1']):>15s}   v2 {f(pair['v2']):>15s}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Train/evaluate the PPE v2 detector")
    ap.add_argument("--model", default="yolo11s.pt")
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--patience", type=int, default=15)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--cache", default="disk", choices=["disk", "ram", "none"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--name", default="ppe_v2_yolo11s")
    ap.add_argument("--data", default=str(V2_DIR / "ppe_v2.yaml"))
    ap.add_argument("--eval-only", action="store_true")
    ap.add_argument("--weights", default="")
    ap.add_argument("--force", action="store_true", help="overwrite models/ppe_v2.pt and runs/ppe_v2_metrics.json")
    args = ap.parse_args()

    from ultralytics import YOLO
    configure_ultralytics()
    command = "python " + " ".join(Path(a).name if i == 0 else a for i, a in enumerate(sys.argv))
    train_info: dict = {}
    if args.eval_only:
        weights = Path(args.weights)
    else:
        model = YOLO(str(MODELS_DIR / args.model))
        t0 = time.perf_counter()
        started = datetime.now(timezone.utc).isoformat()
        model.train(data=args.data, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
                    patience=args.patience, workers=args.workers, seed=args.seed, deterministic=True,
                    amp=True, device="0", cache=False if args.cache == "none" else args.cache,
                    project=str(RUNS_DIR / "train"), name=args.name, exist_ok=False, plots=True)
        elapsed = time.perf_counter() - t0
        run_dir = Path(model.trainer.save_dir)
        weights = run_dir / "weights" / "best.pt"
        import csv
        rows = list(csv.DictReader(open(run_dir / "results.csv", encoding="utf-8")))
        key = next(k for k in rows[0] if "mAP50-95" in k)
        best = max(rows, key=lambda r: float(r[key]))  # Ultralytics 8.4 fitness = val mAP50-95 (picks best.pt)
        train_info = {"run_dir": str(run_dir), "started_utc": started, "wall_clock_minutes": round(elapsed / 60, 1),
                      "epochs_requested": args.epochs, "epochs_completed": len(rows),
                      "best_epoch_by_fitness": int(float(best["epoch"])), "patience": args.patience,
                      "imgsz": args.imgsz, "batch": args.batch, "seed": args.seed, "amp": True,
                      "deterministic": True, "cache": args.cache, "base_model": args.model,
                      "val_at_best_epoch": {k.split("/")[-1]: float(v) for k, v in best.items() if k.startswith("metrics/")}}
        print(f"TRAINING WALL-CLOCK: {elapsed / 60:.1f} min, {len(rows)} epochs")

    ev = evaluate(weights, args.imgsz, args.batch)
    print_tables(ev)
    build = json.loads((V2_DIR / "build_stats.json").read_text(encoding="utf-8"))
    pseudo = json.loads((V2_DIR / "pseudo" / "summary.json").read_text(encoding="utf-8"))
    result = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "weights": str(weights), "weights_sha256": file_hash(weights),
        "classes": list(CLASSES),
        "note": "All numbers copied from Ultralytics' validator (conf 0.001, IoU 0.7, imgsz 640). "
                "Per-source rows score only the classes that source labels; test splits carry original labels only.",
        "training": train_info,
        "data": {"train_images": build["train_images"], "val_images": build["val_images"],
                 "test_images": build["test_images"], "box_totals": build["totals"],
                 "pseudo_label_conf_threshold": pseudo["conf_threshold"]},
        "test": ev,
    }
    if METRICS_JSON.exists() and not args.force:
        alt = METRICS_JSON.with_name(f"ppe_v2_metrics_{datetime.now():%Y%m%d_%H%M%S}.json")
        print(f"{METRICS_JSON} exists; writing {alt} instead (use --force to replace).")
        alt.write_text(json.dumps(result, indent=2), encoding="utf-8")
    else:
        METRICS_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"saved {METRICS_JSON}")
    if not args.eval_only:
        if V2_WEIGHTS.exists() and not args.force:
            print(f"Kept existing {V2_WEIGHTS}; new weights stay in {weights} (use --force to replace).")
        else:
            shutil.copy2(weights, V2_WEIGHTS)
            print(f"Copied best weights -> {V2_WEIGHTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
