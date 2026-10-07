"""Measure Yaqiz's fallen-posture rule on the GMDCSA-24 clips (79 falls, 81 daily activities).

Same code path as a camera worker (yaqiz/vision/worker.py):
  * people: COCO detector + ByteTrack (yaqiz.vision.engine.PersonTracker), a fresh tracker per clip
  * keypoints: YOLO11-pose on every 2nd processed frame, matched to tracks (attach_keypoints)
  * posture: yaqiz.posture.pose_features (torso within 30 degrees of horizontal, or a box much wider
    than tall when the torso keypoints are not visible)
  * clips (~30 fps) are processed at the worker's rate (Settings.max_fps, 10 fps)

For every processed frame the script records two signals (any person in view):
  * recognised: the lying rule has held for >= --hold s (default 0.5 s; gaps < 0.8 s bridged)
  * alert:      the full man-down rule (yaqiz.posture.ManDownDetector: lying AND still for man_down_s)

Scores:
  * fall clips: detected = recognised at some frame at/after the annotated fall start;
    latency = first such frame - fall start; a recognition before the fall start is a false trigger
    (reported with the activity annotated at that moment). The full alert is scored only on fall clips
    that continue >= man_down_s + 1 s after the fall start ("alert-eligible"): most GMDCSA-24 clips end
    a few seconds after the fall, so the person is not down long enough for the 5 s hold.
  * daily-activity (ADL) clips: any recognition or alert is false, reported with the activity at that
    moment ("Sleeping" is a person lying on a bed, which the posture rule flags by design).

GMDCSA-24 is indoor footage of 4 people at home (CC BY 4.0 / MIT, see docs/DATA.md), not a construction
site: the numbers describe the posture rule, not on-site performance.

Usage (repo root):
    .venv\\Scripts\\python scripts\\eval_posture.py [--hold 0.5] [--still-tol 0.25] [--limit N]
    .venv\\Scripts\\python scripts\\eval_posture.py --sweep 0.10,0.15,0.20,0.25 --subjects "Subject 1,Subject 2"
Writes runs/eval/posture_gmdcsa24.json (summary) and runs/eval/posture_gmdcsa24.csv (one row per clip);
a sweep writes runs/eval/posture_stillness_sweep.json (the full man-down alert at each tolerance).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402

from yaqiz.config import RuntimeSettings, Settings  # noqa: E402
from yaqiz.posture import STILL_TOL, HoldTimer, ManDownDetector, PoseFeatures, pose_features  # noqa: E402

FALLS_DIR = ROOT / "data" / "eval" / "falls"
INDEX = FALLS_DIR / "gmdcsa24_index.csv"
OUT_DIR = ROOT / "runs" / "eval"
FALL_LABEL = re.compile(r"^fall", re.I)
DIRECTION = re.compile(r"\((SW|BW|FW)", re.I)
DIRECTION_NAME = {"SW": "sideways", "BW": "backward", "FW": "forward"}


def activity_at(intervals: list, t: float) -> str:
    for label, start, end in intervals:
        if start <= t <= end:
            return label
    return "unlabelled"


def extract_features(path: Path, settings: Settings, rt: RuntimeSettings, pose) -> list[tuple[float, list]]:  # noqa: ANN001
    """Process one clip like a camera worker; return [(t, [(track_id, PoseFeatures)])] per processed frame."""
    from yaqiz.vision.engine import PersonTracker, attach_keypoints

    tracker = PersonTracker(settings)  # fresh ByteTrack state per clip
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, round(fps / settings.max_fps))
    cache: dict = {}
    frames: list[tuple[float, list[tuple[int, PoseFeatures]]]] = []
    idx, n_proc = -1, 0
    while cap.grab():
        idx += 1
        if idx % step:
            continue
        ok, frame = cap.retrieve()
        if not ok:
            break
        t = idx / fps
        tracks = tracker.track(frame, rt.pose_conf)
        poses = pose.estimate(frame, rt.pose_conf) if tracks and n_proc % max(1, settings.pose_every) == 0 else None
        n_proc += 1
        persons = attach_keypoints(tracks, poses, cache, t)
        frames.append((t, [(p.track_id, pose_features(p.kpts, p.xyxy, rt.kp_conf)) for p in persons]))
    cap.release()
    return frames


def replay(frames: list, hold_s: float, man_down_s: float, still_tol: float) -> list[tuple[float, bool, bool]]:
    """Run the posture timer and the man-down detector over extracted features: [(t, recognised, alert)]."""
    posture: dict[int, HoldTimer] = {}
    alerts: dict[int, ManDownDetector] = {}
    out = []
    for t, people in frames:
        rec = alert = False
        for tid, f in people:
            rec |= posture.setdefault(tid, HoldTimer(hold_s, grace_s=0.8)).update(f.lying, t)
            alert |= alerts.setdefault(tid, ManDownDetector(man_down_s, still_tol)).update(f, t)
        out.append((t, rec, alert))
    return out


def sweep(clips: list[dict], settings: Settings, rt: RuntimeSettings, pose, args) -> int:  # noqa: ANN001
    """The full man-down alert at several stillness tolerances, from one feature pass."""
    tols = [float(x) for x in args.sweep.split(",")]
    res = {tol: {"eligible_falls": 0, "alert_on_eligible": 0, "adl_clips": 0, "adl_minutes": 0.0,
                 "adl_false_alerts": 0, "false_alert_activities": Counter()} for tol in tols}
    for i, r in enumerate(clips, 1):
        intervals = [(a, float(b), float(c)) for a, b, c in json.loads(r["intervals"])]
        falls = [iv for iv in intervals if FALL_LABEL.match(iv[0])]
        frames = extract_features(FALLS_DIR / r["clip"], settings, rt, pose)
        for tol in tols:
            tl = replay(frames, args.hold, rt.man_down_s, tol)
            if r["type"] == "fall" and falls:
                fs = min(iv[1] for iv in falls)
                if float(r["duration_s"]) - fs >= rt.man_down_s + 1.0:
                    res[tol]["eligible_falls"] += 1
                    res[tol]["alert_on_eligible"] += first(tl, 2, since=fs) is not None
            elif r["type"] == "adl":
                res[tol]["adl_clips"] += 1
                res[tol]["adl_minutes"] += float(r["duration_s"]) / 60.0
                fa = first(tl, 2)
                if fa is not None:
                    res[tol]["adl_false_alerts"] += 1
                    res[tol]["false_alert_activities"][activity_at(intervals, fa)] += 1
        print(f"[{i}/{len(clips)}] {r['clip']}", flush=True)
    out = {"generated_utc": datetime.now(timezone.utc).isoformat(), "subjects": args.subjects or "all",
           "posture_hold_s": args.hold, "man_down_s": rt.man_down_s,
           "results": {f"{tol:.2f}": {**v, "adl_minutes": round(v["adl_minutes"], 1),
                                      "false_alert_activities": dict(v["false_alert_activities"])}
                       for tol, v in res.items()}}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "posture_stillness_sweep.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


def first(timeline, which: int, since: float = float("-inf"), until: float = float("inf")) -> float | None:
    return next((t for t, *sig in timeline if since <= t < until and sig[which - 1]), None)


def pct(a: int, b: int) -> float | None:
    return round(100.0 * a / b, 1) if b else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate the fallen-posture rule on GMDCSA-24")
    ap.add_argument("--hold", type=float, default=0.5, help="seconds the lying rule must hold to count")
    ap.add_argument("--limit", type=int, default=0, help="only the first N clips (smoke test)")
    ap.add_argument("--still-tol", type=float, default=STILL_TOL, help="stillness tolerance of the man-down rule")
    ap.add_argument("--sweep", default="", help="comma-separated stillness tolerances to compare (alert only)")
    ap.add_argument("--subjects", default="", help='comma-separated, e.g. "Subject 1,Subject 2"')
    args = ap.parse_args()
    if not INDEX.exists():
        raise SystemExit("Run scripts/data_falls_index.py first (needs data/eval/falls/GMDCSA24).")

    from yaqiz.vision.engine import PoseEstimator

    settings, rt = Settings(), RuntimeSettings()
    pose = PoseEstimator(settings)
    clips = list(csv.DictReader(INDEX.open(encoding="utf-8")))
    if args.subjects:
        wanted = {x.strip() for x in args.subjects.split(",")}
        clips = [r for r in clips if r["subject"] in wanted]
    if args.limit:
        clips = clips[: args.limit]
    if args.sweep:
        return sweep(clips, settings, rt, pose, args)
    rows = []
    t0 = time.perf_counter()
    for i, r in enumerate(clips, 1):
        intervals = [(a, float(b), float(c)) for a, b, c in json.loads(r["intervals"])]
        tl = replay(extract_features(FALLS_DIR / r["clip"], settings, rt, pose), args.hold, rt.man_down_s, args.still_tol)
        dt = (tl[1][0] - tl[0][0]) if len(tl) > 1 else 0.1
        row = {"clip": r["clip"], "subject": r["subject"], "type": r["type"], "duration_s": float(r["duration_s"]),
               "resolution": f"{r['width']}x{r['height']}", "processed_frames": len(tl),
               "recognised_s": round(sum(dt for _, rec, _ in tl if rec), 2)}
        falls = [iv for iv in intervals if FALL_LABEL.match(iv[0])]
        if r["type"] == "fall" and falls:
            fs = min(iv[1] for iv in falls)
            m = DIRECTION.search(falls[0][0])
            pre = first(tl, 1, until=fs)
            hit = first(tl, 1, since=fs)
            after = round(row["duration_s"] - fs, 2)
            row.update({
                "fall_direction": DIRECTION_NAME.get(m.group(1).upper(), "unknown") if m else "unknown",
                "fall_start_s": fs, "seconds_after_fall_start": after,
                "detected": hit is not None, "latency_s": None if hit is None else round(hit - fs, 2),
                "pre_fall_trigger": pre is not None, "pre_fall_activity": activity_at(intervals, pre) if pre is not None else None,
                "alert_eligible": after >= rt.man_down_s + 1.0, "alert_fired": first(tl, 2, since=fs) is not None,
            })
        elif r["type"] == "adl":
            fp, fa = first(tl, 1), first(tl, 2)
            row.update({"false_trigger": fp is not None,
                        "false_trigger_activity": activity_at(intervals, fp) if fp is not None else None,
                        "false_alert": fa is not None,
                        "false_alert_activity": activity_at(intervals, fa) if fa is not None else None})
        else:
            row["excluded"] = "fall clip without an annotated fall interval in its CSV"
        rows.append(row)
        if "fall_start_s" in row:
            brief = f"fall@{row['fall_start_s']} detected={row['detected']} latency={row['latency_s']} pre={row['pre_fall_trigger']}"
        elif "false_trigger" in row:
            brief = f"adl false={row['false_trigger']} ({row['false_trigger_activity']}) alert={row['false_alert']}"
        else:
            brief = row["excluded"]
        print(f"[{i}/{len(clips)}] {r['clip']}: {brief}", flush=True)
    wall = time.perf_counter() - t0

    falls = [x for x in rows if "fall_start_s" in x]
    adls = [x for x in rows if "false_trigger" in x]
    det = [x for x in falls if x["detected"]]
    lat = sorted(x["latency_s"] for x in det)
    by_dir = {}
    for d in sorted({x["fall_direction"] for x in falls}):
        g = [x for x in falls if x["fall_direction"] == d]
        by_dir[d] = {"clips": len(g), "detected": sum(x["detected"] for x in g),
                     "detection_rate_pct": pct(sum(x["detected"] for x in g), len(g))}
    eligible = [x for x in falls if x["alert_eligible"]]
    adl_min = sum(x["duration_s"] for x in adls) / 60.0
    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": ("GMDCSA-24 v2.1 (Alam et al. 2024; CC BY 4.0 on Zenodo, MIT LICENSE file in the repository): "
                    "indoor, 4 subjects, one person per clip"),
        "excluded_clips": [x["clip"] for x in rows if "excluded" in x],
        "pipeline": {"person_model": settings.person_weights, "pose_model": settings.pose_weights,
                     "imgsz": settings.imgsz, "pose_imgsz": settings.pose_imgsz, "pose_every": settings.pose_every,
                     "processed_fps": settings.max_fps, "pose_conf": rt.pose_conf, "kp_conf": rt.kp_conf,
                     "posture_hold_s": args.hold, "man_down_s": rt.man_down_s, "still_tol": args.still_tol},
        "fall_clips": {
            "clips": len(falls),
            "detected": len(det), "detection_rate_pct": pct(len(det), len(falls)),
            "by_direction": by_dir,
            "latency_s": {"median": round(statistics.median(lat), 2) if lat else None,
                          "p90": lat[min(len(lat) - 1, int(0.9 * len(lat)))] if lat else None,
                          "max": lat[-1] if lat else None},
            "clips_with_false_trigger_before_fall": sum(x["pre_fall_trigger"] for x in falls),
            "false_trigger_before_fall_by_activity": dict(Counter(x["pre_fall_activity"] for x in falls if x["pre_fall_trigger"])),
            "seconds_from_fall_start_to_clip_end": {
                "median": round(statistics.median(x["seconds_after_fall_start"] for x in falls), 2) if falls else None,
                "max": max((x["seconds_after_fall_start"] for x in falls), default=None)},
            "alert_eligible_clips": len(eligible),
            "alert_fired_on_eligible": sum(x["alert_fired"] for x in eligible),
        },
        "adl_clips": {
            "clips": len(adls),
            "minutes": round(adl_min, 1),
            "clips_with_false_posture": sum(x["false_trigger"] for x in adls),
            "false_posture_by_activity": dict(Counter(x["false_trigger_activity"] for x in adls if x["false_trigger"])),
            "seconds_flagged_lying": round(sum(x["recognised_s"] for x in adls), 1),
            "clips_with_false_man_down_alert": sum(x["false_alert"] for x in adls),
            "false_alert_by_activity": dict(Counter(x["false_alert_activity"] for x in adls if x["false_alert"])),
        },
        "by_subject_group": {
            name: {
                "fall_clips": len(g := [x for x in falls if x["subject"] in subs]),
                "fall_detected": sum(x["detected"] for x in g),
                "alert_eligible": sum(x["alert_eligible"] for x in g),
                "alert_fired_on_eligible": sum(x["alert_fired"] for x in g if x["alert_eligible"]),
                "adl_clips": len(a := [x for x in adls if x["subject"] in subs]),
                "adl_false_alerts": sum(x["false_alert"] for x in a),
            }
            for name, subs in (("development: Subject 1-2 (used to diagnose the 2026-10-07 stillness bug)",
                                {"Subject 1", "Subject 2"}),
                               ("held out: Subject 3-4", {"Subject 3", "Subject 4"}))
        },
        "not_measured": "The full man-down alert on fall clips that end less than man_down_s + 1 s after the fall "
                        "start (the person is not down long enough for the hold).",
        "wall_clock_min": round(wall / 60.0, 1),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tag = "" if not args.limit else f"_first{args.limit}"
    (OUT_DIR / f"posture_gmdcsa24{tag}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    keys: list[str] = []
    for x in rows:
        keys += [k for k in x if k not in keys]
    with (OUT_DIR / f"posture_gmdcsa24{tag}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
