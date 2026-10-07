"""Measure the running system: per-camera processing rate and capture -> processed latency.

Run while `python -m yaqiz serve` is running with the cameras on. Every second it reads /api/health
(camera status, model, GPU) and keeps the samples taken while each camera reports state "running".
Latency = from the moment a frame is decoded to the moment its events are published and its stream
frame is ready (median and 95th percentile over each camera's last 300 frames). The rule's own
confirmation time (e.g. 3 frames for a zone entry) comes on top of this and is set in S-08.

Usage (repo root):  .venv\\Scripts\\python scripts\\measure_live.py [--seconds 60] [--url http://127.0.0.1:8000]
Writes runs/eval/live_<YYYYMMDD_HHMMSS>.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parent.parent / "runs" / "eval"


def main() -> int:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")  # camera names are Arabic
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    samples: dict[int, list[dict]] = {}
    health = {}
    t_end = time.monotonic() + args.seconds
    with httpx.Client(base_url=args.url, timeout=10) as client:
        while time.monotonic() < t_end:
            r = client.get("/api/health")
            r.raise_for_status()
            health = r.json()
            for cam in health["cameras"]:
                if cam.get("state") == "running":
                    samples.setdefault(cam["id"], []).append(cam)
            time.sleep(1.0)
    result = {
        "measured_utc": datetime.now(timezone.utc).isoformat(),
        "seconds": args.seconds,
        "gpu": health.get("gpu"),
        "ppe_model": health.get("ppe_model"),
        "cameras_running": len(samples),
        "per_camera": {},
    }
    for cid, rows in sorted(samples.items()):
        fps = [r["fps"] for r in rows if r.get("fps")]
        lat = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None]
        p95 = [r["latency_p95_ms"] for r in rows if r.get("latency_p95_ms") is not None]
        result["per_camera"][cid] = {
            "name": rows[-1].get("name"), "samples": len(rows),
            "fps_median": round(statistics.median(fps), 1) if fps else None,
            "fps_min": min(fps) if fps else None,
            "latency_ms_median": round(statistics.median(lat), 1) if lat else None,
            "latency_p95_ms_max": max(p95) if p95 else None,
            "people_median": statistics.median([r.get("people", 0) for r in rows]),
        }
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"live_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"saved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
