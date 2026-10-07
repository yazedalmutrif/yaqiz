"""Index the GMDCSA-24 fall clips (data/eval/falls/GMDCSA24) for the later man-down evaluation.

Reads each subject's Fall.csv / ADL.csv and every clip's video header, and writes
data/eval/falls/gmdcsa24_index.csv + gmdcsa24_summary.json. Class intervals such as
"Falling (SW)[3.4 to 6]; Sitting[0 to 3.4]" are parsed into (label, start_s, end_s).

Usage:  .venv\\Scripts\\python scripts\\data_falls_index.py
"""
from __future__ import annotations

import collections
import csv
import json
import re
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_common import FALLS_DIR  # noqa: E402

ROOT = FALLS_DIR / "GMDCSA24"
INTERVAL = re.compile(r"\s*([^\[;]+?)\s*\[\s*([\d.]+)\s*to\s*([\d.]+)\s*\]")


def main() -> int:
    rows = []
    labels = collections.Counter()
    for subj in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        for kind in ("Fall", "ADL"):
            meta_csv = subj / f"{kind}.csv"
            meta = {}
            if meta_csv.exists():
                with meta_csv.open(encoding="utf-8-sig", errors="replace") as f:
                    for r in csv.reader(f):
                        if r and r[0].strip().lower().endswith(".mp4"):
                            meta[r[0].strip()] = [c.strip() for c in r]
            for clip in sorted((subj / kind).glob("*.mp4")):
                cap = cv2.VideoCapture(str(clip))
                fps = cap.get(cv2.CAP_PROP_FPS)
                n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                m = meta.get(clip.name, [])
                classes = m[5] if len(m) > 5 else ""
                intervals = [(a.strip(), float(b), float(c)) for a, b, c in INTERVAL.findall(classes)]
                for a, _, _ in intervals:
                    labels[a] += 1
                rows.append({
                    "subject": subj.name, "type": kind.lower(), "clip": clip.relative_to(FALLS_DIR).as_posix(),
                    "fps": round(fps, 2), "frames": n, "duration_s": round(n / fps, 2) if fps else None,
                    "width": w, "height": h,
                    "time_of_recording": m[2] if len(m) > 2 else "", "attire": m[3] if len(m) > 3 else "",
                    "description": m[4] if len(m) > 4 else "",
                    "intervals": json.dumps(intervals),
                })
    out = FALLS_DIR / "gmdcsa24_index.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    by = collections.Counter((r["subject"], r["type"]) for r in rows)
    summary = {
        "clips": len(rows),
        "fall_clips": sum(1 for r in rows if r["type"] == "fall"),
        "adl_clips": sum(1 for r in rows if r["type"] == "adl"),
        "per_subject": {f"{s} {t}": c for (s, t), c in sorted(by.items())},
        "resolutions": dict(collections.Counter(f"{r['width']}x{r['height']}" for r in rows)),
        "fps": dict(collections.Counter(str(r["fps"]) for r in rows)),
        "total_duration_s": round(sum(r["duration_s"] or 0 for r in rows), 1),
        "clips_without_csv_row": sum(1 for r in rows if not r["description"]),
        "interval_labels": dict(labels.most_common()),
    }
    (FALLS_DIR / "gmdcsa24_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
