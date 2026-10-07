"""Fill the classes a source does not label, using teacher models trained only on sources that DO label them.

Why: the sources label different class subsets (data_common.SOURCES[...].labelled). Merging them
as-is would teach the detector that, e.g., every vest in GDUT-HWD is background. So:

  1. teacher   Train two teachers on permissive data only:
                 ppe  = helmet/head/vest on CHVG + RF100 construction-safety (both label all three)
                 mach = machinery on RF100 excavators (labels machinery)
               (The Sprint-0 model is not used as a teacher: it was trained on AGPL-3.0 data.)
  2. check     Measure each teacher on held-out TEST splits of sources that label its classes:
               precision/recall per class at conf 0.25 / 0.5 / 0.7 (IoU >= 0.5, greedy matching).
               This is the expected quality of the pseudo-labels.
  3. label     For every train/val image of every training source, run the teacher(s) that cover the
               source's missing classes; keep boxes with conf >= --conf (0.5) as pseudo-labels.
               Test splits are never pseudo-labelled and are scored only on their own labelled classes.

  4. filter    Sanity filter (pseudo/<source>.filtered.jsonl, used for training): drop the classes in
               data_common.PSEUDO_DROP_CLASSES, and keep a helmet/head (vest) pseudo-box only if its centre is
               in the head (torso) region of a person found by the COCO detector, exactly as the live system
               associates gear with people.

Records: data/datasets/ppe_v2/pseudo/<source>.jsonl (one line per pseudo box, with confidence),
pseudo/<source>.filtered.jsonl and pseudo/summary.json. Spot-check sheets: scripts/data_review.py
--root merged --pseudo-only.

Usage:
    .venv\\Scripts\\python scripts\\data_pseudolabel.py teacher --which ppe   (or mach)
    .venv\\Scripts\\python scripts\\data_pseudolabel.py check
    .venv\\Scripts\\python scripts\\data_pseudolabel.py label --conf 0.5
    .venv\\Scripts\\python scripts\\data_pseudolabel.py filter
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import configure_ultralytics  # noqa: E402
from data_common import (  # noqa: E402
    CLASSES, MODELS_DIR, PERSON_FILTER, PSEUDO_DIR, PSEUDO_DROP_CLASSES, SOURCES, SOURCES_DIR, TRAIN_SOURCES,
    V2_DIR, V2_RUN_DIR, images_in, label_for, read_yolo, write_yaml)
from data_dedupe import excluded_for  # noqa: E402

TEACHERS = {
    "ppe": {"sources": ("chvg", "rf100_construction_safety"), "classes": ("helmet", "head", "vest"), "epochs": 60},
    "mach": {"sources": ("rf100_excavators",), "classes": ("machinery",), "epochs": 40},
}


def teacher_weights(which: str) -> Path:
    return V2_RUN_DIR / f"teacher_{which}" / "weights" / "best.pt"


def write_list(path: Path, imgs: list[Path]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(p.as_posix() for p in imgs) + "\n", encoding="utf-8")
    return path


def split_images(sources, split: str, excluded) -> list[Path]:
    out = []
    for s in sources:
        drop = excluded.get(s, {}).get(split, set())
        out += [p for p in images_in(SOURCES_DIR / s / "images" / split) if p.name not in drop]
    return out


def cmd_teacher(args) -> int:
    from ultralytics import YOLO
    configure_ultralytics()
    t = TEACHERS[args.which]
    ex = excluded_for(set(t["sources"]))
    lists = V2_DIR / "lists"
    train = write_list(lists / f"teacher_{args.which}_train.txt", split_images(t["sources"], "train", ex))
    val = write_list(lists / f"teacher_{args.which}_val.txt", split_images(t["sources"], "val", ex))
    data = V2_DIR / f"teacher_{args.which}.yaml"
    write_yaml(data, {"path": V2_DIR.as_posix(), "train": train.as_posix(), "val": val.as_posix(),
                      "names": dict(enumerate(CLASSES))})
    print(f"teacher {args.which}: {sum(1 for _ in open(train))} train / {sum(1 for _ in open(val))} val images")
    model = YOLO(str(MODELS_DIR / "yolo11s.pt"))
    t0 = time.perf_counter()
    model.train(data=str(data), epochs=args.epochs or t["epochs"], imgsz=640, batch=16, patience=15,
                workers=args.workers, seed=0, deterministic=True, device="0", amp=True, cache="ram",
                project=str(V2_RUN_DIR), name=f"teacher_{args.which}", exist_ok=False, plots=True)
    print(f"TEACHER {args.which} WALL-CLOCK: {(time.perf_counter() - t0) / 60:.1f} min")
    return 0


# ---- matching -------------------------------------------------------------------
def iou_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    x1 = np.maximum(a[:, None, 0], b[None, :, 0]); y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2]); y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area = lambda r: (r[:, 2] - r[:, 0]) * (r[:, 3] - r[:, 1])  # noqa: E731
    return inter / (area(a)[:, None] + area(b)[None, :] - inter + 1e-9)


def xywhn_to_xyxyn(rows) -> np.ndarray:
    return np.array([[x - w / 2, y - h / 2, x + w / 2, y + h / 2] for _, x, y, w, h in rows]).reshape(-1, 4)


def pr_counts(preds, gts, thr_conf: float, iou_thr: float = 0.5):
    """preds: list of (cls_id, conf, xyxyn); gts: list of (cls_id, xyxyn). Returns {cls: [tp, fp, fn]}."""
    out = collections.defaultdict(lambda: [0, 0, 0])
    for c in {p[0] for p in preds} | {g[0] for g in gts}:
        P = sorted([p for p in preds if p[0] == c and p[1] >= thr_conf], key=lambda p: -p[1])
        G = [g for g in gts if g[0] == c]
        used = set()
        if P and G:
            ious = iou_matrix(np.array([p[2] for p in P]), np.array([g[1] for g in G]))
            for i in range(len(P)):
                j = int(np.argmax(np.where([k in used for k in range(len(G))], -1, ious[i])))
                if ious[i, j] >= iou_thr and j not in used:
                    used.add(j)
                    out[c][0] += 1
                else:
                    out[c][1] += 1
        else:
            out[c][1] += len(P)
        out[c][2] += len(G) - len(used)
    return out


def predict(model, imgs: list[Path], conf: float = 0.25, batch: int = 32):
    for i in range(0, len(imgs), batch):
        chunk = imgs[i:i + batch]
        res = model.predict([str(p) for p in chunk], imgsz=640, conf=conf, iou=0.6, agnostic_nms=True,
                            device="0", half=True, verbose=False)
        for p, r in zip(chunk, res):
            b = r.boxes
            yield p, [(int(c), float(s), xy.tolist()) for c, s, xy in
                      zip(b.cls.cpu().numpy(), b.conf.cpu().numpy(), b.xyxyn.cpu().numpy())]


def cmd_check(args) -> int:
    from ultralytics import YOLO
    configure_ultralytics()
    report = {}
    for which, t in TEACHERS.items():
        if args.which and which != args.which:
            continue
        model = YOLO(str(teacher_weights(which)))
        cls_ids = {CLASSES.index(c) for c in t["classes"]}
        for src in [s for s in SOURCES if SOURCES[s].labelled & set(t["classes"])]:
            imgs = images_in(SOURCES_DIR / src / "images" / "test")
            gts_all = {p: [(r[0], xywhn_to_xyxyn([r])[0]) for r in read_yolo(label_for(p))] for p in imgs}
            preds_all = dict(predict(model, imgs))
            res = {}
            for thr in (0.25, 0.5, 0.7):
                tot = collections.defaultdict(lambda: [0, 0, 0])
                for p in imgs:
                    labelled = {CLASSES.index(c) for c in SOURCES[src].labelled} & cls_ids
                    preds = [x for x in preds_all[p] if x[0] in labelled]
                    gts = [g for g in gts_all[p] if g[0] in labelled]
                    for c, v in pr_counts(preds, gts, thr).items():
                        for k in range(3):
                            tot[c][k] += v[k]
                res[f"conf>={thr}"] = {CLASSES[c]: {"tp": v[0], "fp": v[1], "fn": v[2],
                                                     "precision": round(v[0] / max(1, v[0] + v[1]), 4),
                                                     "recall": round(v[0] / max(1, v[0] + v[2]), 4)}
                                        for c, v in sorted(tot.items())}
            report[f"teacher_{which} on {src}/test ({len(imgs)} images)"] = res
            print(f"teacher_{which} on {src}/test:", json.dumps(res["conf>=0.5"]))
    out = V2_RUN_DIR / f"teacher_check{'_' + args.which if args.which else ''}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"saved {out}")
    return 0


def cmd_label(args) -> int:
    from ultralytics import YOLO
    configure_ultralytics()
    PSEUDO_DIR.mkdir(parents=True, exist_ok=True)
    for old in PSEUDO_DIR.glob("*.filtered.jsonl"):  # they describe the previous labels: run `filter` again
        old.unlink()
    excluded = excluded_for(set(TRAIN_SOURCES))
    models = {w: YOLO(str(teacher_weights(w))) for w in TEACHERS}
    summary = {"conf_threshold": args.conf, "teachers": {w: str(teacher_weights(w)) for w in TEACHERS}, "sources": {}}
    for src in TRAIN_SOURCES:
        missing = [c for c in CLASSES if c not in SOURCES[src].labelled]
        stats = collections.Counter()
        near = collections.Counter()
        lines = []
        for split in ("train", "val"):
            imgs = split_images([src], split, excluded)
            stats[f"{split}_images"] = len(imgs)
            for which, t in TEACHERS.items():
                want = [c for c in t["classes"] if c in missing]
                if not want:
                    continue
                want_ids = {CLASSES.index(c) for c in want}
                for p, preds in predict(models[which], imgs, conf=0.25):
                    for c, s, xy in preds:
                        if c not in want_ids:
                            continue
                        if s >= args.conf:
                            lines.append(json.dumps({"image": p.name, "split": split, "cls": CLASSES[c],
                                                     "conf": round(s, 4), "xyxyn": [round(v, 6) for v in xy],
                                                     "teacher": which}))
                            stats[f"{split}_{CLASSES[c]}"] += 1
                        else:
                            near[f"{split}_{CLASSES[c]}_conf_0.25-{args.conf}"] += 1
        (PSEUDO_DIR / f"{src}.jsonl").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        summary["sources"][src] = {"missing_classes": missing, "pseudo_boxes": dict(stats),
                                   "not_used_low_conf_boxes": dict(near)}
        print(src, json.dumps(summary["sources"][src]))
    (PSEUDO_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0


def cmd_filter(args) -> int:
    """Write pseudo/<source>.filtered.jsonl: class policy + person-consistency check."""
    from ultralytics import YOLO
    from yaqiz.vision.analysis import HEAD_REGION, TORSO_REGION, _region
    configure_ultralytics()
    person = YOLO(str(MODELS_DIR / PERSON_FILTER["weights"]))
    summary_path = PSEUDO_DIR / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["filter"] = {"dropped_classes": PSEUDO_DROP_CLASSES, "person_filter": PERSON_FILTER,
                         "rule": "gear box centre inside the head region (helmet, head) or torso region (vest) "
                                 "of a detected person, regions as in yaqiz/vision/analysis.py", "sources": {}}
    for src in TRAIN_SOURCES:
        raw = PSEUDO_DIR / f"{src}.jsonl"
        recs = [json.loads(x) for x in raw.read_text(encoding="utf-8").splitlines()] if raw.exists() else []
        stats = collections.Counter()
        kept = []
        gear = collections.defaultdict(list)
        for r in recs:
            if r["cls"] in PSEUDO_DROP_CLASSES:
                stats[f"dropped_policy_{r['cls']}"] += 1
            else:
                gear[(r["split"], r["image"])].append(r)
        keys = sorted(gear)
        for i in range(0, len(keys), 32):
            chunk = keys[i:i + 32]
            paths = [str(SOURCES_DIR / src / "images" / sp / name) for sp, name in chunk]
            res = person.predict(paths, classes=[0], conf=PERSON_FILTER["conf"], imgsz=PERSON_FILTER["imgsz"],
                                 device="0", verbose=False)
            for key, r in zip(chunk, res):
                h, w = r.orig_shape
                people = [tuple(map(float, b)) for b in r.boxes.xyxy.cpu().numpy()]
                for rec in gear[key]:
                    x1, y1, x2, y2 = rec["xyxyn"]
                    cx, cy = (x1 + x2) / 2 * w, (y1 + y2) / 2 * h
                    frac = HEAD_REGION if rec["cls"] in ("helmet", "head") else TORSO_REGION
                    on_person = any(rx1 <= cx <= rx2 and ry1 <= cy <= ry2
                                    for rx1, ry1, rx2, ry2 in (_region(p, frac) for p in people))
                    if on_person:
                        kept.append(rec)
                        stats[f"kept_{rec['cls']}"] += 1
                    else:
                        stats[f"dropped_no_person_{rec['cls']}"] += 1
        out = PSEUDO_DIR / f"{src}.filtered.jsonl"
        out.write_text("".join(json.dumps(r) + "\n" for r in kept), encoding="utf-8")
        summary["filter"]["sources"][src] = dict(sorted(stats.items()))
        print(src, json.dumps(dict(sorted(stats.items()))))
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("teacher")
    t.add_argument("--which", choices=list(TEACHERS), required=True)
    t.add_argument("--epochs", type=int, default=0)
    t.add_argument("--workers", type=int, default=4)
    chk = sub.add_parser("check")
    chk.add_argument("--which", choices=list(TEACHERS), default="")
    lab = sub.add_parser("label")
    lab.add_argument("--conf", type=float, default=0.5)
    sub.add_parser("filter")
    args = ap.parse_args()
    return {"teacher": cmd_teacher, "check": cmd_check, "label": cmd_label, "filter": cmd_filter}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
