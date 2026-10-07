"""Zone-violation demo: track people, check PPE and danger zones, save annotated output.

Pipeline per frame:
  1. COCO YOLO11 person detection + ByteTrack  -> stable person IDs
  2. Fine-tuned Construction-PPE YOLO11        -> helmet / no_helmet / vest boxes
  3. PPE boxes -> persons (head / torso regions), smoothed per track
  4. Foot point (bottom-centre of the person box) vs zone polygons (Shapely)
  5. Overlay labels, write MP4 + PNG frames + events.json + fps.json

Usage (repo root):
  .venv\\Scripts\\python scripts\\zone_demo.py --video data\\videos\\pexels_11798561.mp4 ^
      --zones configs\\zones\\pexels_11798561.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import overlay  # noqa: E402
from core.config import (  # noqa: E402
    COCO_PERSON_CLASS,
    MODELS_DIR,
    PERSON_WEIGHTS,
    PPE_WEIGHTS,
    PROJECT_NAME,
    ROOT,
    RUNS_DIR,
    configure_ultralytics,
)
from core.ppe import Det, associate  # noqa: E402
from core.rules import TrackRegistry  # noqa: E402
from core.zones import foot_point, load_zones  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=f"{PROJECT_NAME}: zone + PPE demo on a video clip")
    p.add_argument("--video", required=True)
    p.add_argument("--zones", required=True, help="zone YAML (normalised polygon points)")
    p.add_argument("--ppe-weights", default=str(PPE_WEIGHTS))
    p.add_argument("--person-weights", default=str(MODELS_DIR / PERSON_WEIGHTS))
    p.add_argument("--imgsz", type=int, default=960, help="inference size for both models")
    p.add_argument("--person-conf", type=float, default=0.30,
                   help="person detector threshold fed to ByteTrack (0.10 gave more duplicate boxes on our clips)")
    p.add_argument("--tracker", default=str(ROOT / "configs" / "bytetrack_site.yaml"))
    p.add_argument("--ppe-conf", type=float, default=0.35)
    p.add_argument("--max-side", type=int, default=1920, help="downscale so the long side is at most this (0 = off)")
    p.add_argument("--save-every", type=int, default=10, help="save a PNG every N frames")
    p.add_argument("--max-frames", type=int, default=0, help="stop after N frames (0 = whole clip)")
    p.add_argument("--warmup", type=int, default=10, help="frames excluded from steady-state FPS")
    p.add_argument("--show-ppe", action="store_true", help="also draw raw helmet / vest boxes")
    p.add_argument("--min-label-frac", type=float, default=0.05,
                   help="label compliant people only if box height >= this fraction of frame height")
    p.add_argument("--note", default="Demo zone drawn for illustration; stock footage, no real violation implied.",
                   help="footer note on every frame ('' to hide)")
    p.add_argument("--out", default=None, help="output dir (default runs/zone_demo/<clip>)")
    p.add_argument("--device", default="0")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    from ultralytics import YOLO

    configure_ultralytics()  # no telemetry; datasets_dir inside the repo

    video = Path(args.video)
    if not video.exists():
        print(f"Video not found: {video}")
        return 1
    if not Path(args.ppe_weights).exists():
        print(f"PPE weights not found: {args.ppe_weights}. Train first (scripts/train_ppe.py).")
        return 1

    out_dir = Path(args.out) if args.out else RUNS_DIR / "zone_demo" / video.stem
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    person_model = YOLO(args.person_weights)
    ppe_model = YOLO(args.ppe_weights)
    ppe_names = ppe_model.names

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        print(f"Cannot open {video}")
        return 1
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    scale = 1.0
    if args.max_side and max(src_w, src_h) > args.max_side:
        scale = args.max_side / max(src_w, src_h)
    W, H = int(round(src_w * scale)), int(round(src_h * scale))

    zones = [z.bind(W, H) for z in load_zones(args.zones)]
    writer = cv2.VideoWriter(str(out_dir / f"{video.stem}_annotated.mp4"), cv2.VideoWriter_fourcc(*"mp4v"),
                             src_fps, (W, H))
    reg = TrackRegistry()

    proc_times: list[float] = []   # model + logic + overlay, per frame
    t_start = time.perf_counter()
    idx = 0
    saved = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if args.max_frames and idx >= args.max_frames:
            break
        if scale != 1.0:
            frame = cv2.resize(frame, (W, H), interpolation=cv2.INTER_AREA)

        t0 = time.perf_counter()
        pr = person_model.track(frame, persist=True, tracker=args.tracker, classes=[COCO_PERSON_CLASS],
                                conf=args.person_conf, imgsz=args.imgsz, device=args.device, verbose=False)[0]
        rr = ppe_model.predict(frame, conf=args.ppe_conf, imgsz=args.imgsz, device=args.device, verbose=False)[0]

        boxes, ids = [], []
        if pr.boxes is not None and pr.boxes.id is not None:
            boxes = pr.boxes.xyxy.cpu().numpy().tolist()
            ids = pr.boxes.id.int().cpu().numpy().tolist()
        dets = [Det(ppe_names[int(c)], float(s), tuple(b))
                for b, c, s in zip(rr.boxes.xyxy.cpu().numpy().tolist(), rr.boxes.cls.cpu().numpy().tolist(),
                                   rr.boxes.conf.cpu().numpy().tolist())]
        ppe_per_person = associate(boxes, dets)

        t_sec = idx / src_fps
        n_in_zone = n_no_helmet = 0
        persons = []
        for box, tid, ppe in zip(boxes, ids, ppe_per_person):
            st = reg.get(tid)
            st.update_helmet(ppe.helmet_state)
            fx, fy = foot_point(box)
            hit = next((z.name for z in zones if z.contains_point(fx, fy)), None)
            if st.update_zone(hit):
                reg.log(idx, t_sec, tid, "zone_entry", hit)
            helmet = st.helmet
            if helmet == "no_helmet" and not st.no_helmet_reported:
                st.no_helmet_reported = True
                reg.log(idx, t_sec, tid, "no_helmet", "")
            n_in_zone += st.in_zone
            n_no_helmet += helmet == "no_helmet"
            persons.append((box, tid, st.in_zone, helmet, ppe.vest > 0))

        vis = frame.copy()
        taken: list = []  # label rectangles already drawn (avoid overlapping chips)
        for z in zones:
            overlay.draw_zone(vis, z.pixel_points, active=n_in_zone > 0)
        if args.show_ppe:
            overlay.draw_ppe_boxes(vis, [d for p in ppe_per_person for d in p.matched])
        # Violations first so their chips get the best positions.
        for box, tid, in_zone, helmet, vest in sorted(persons, key=lambda q: not (q[2] or q[3] == "no_helmet")):
            big = (box[3] - box[1]) >= args.min_label_frac * H
            overlay.draw_person(vis, box, tid, in_zone, helmet, vest, taken=taken, show_label=big)
        for z in zones:  # zone names last so no box is drawn over them
            overlay.draw_zone_label(vis, z.pixel_points, z.name, taken=taken)
        proc_times.append(time.perf_counter() - t0)
        steady = proc_times[args.warmup:] or proc_times
        fps_now = len(steady) / sum(steady)
        overlay.draw_header(
            vis,
            f"people {len(persons)}  |  in zone {n_in_zone}  |  no helmet {n_no_helmet}",
            f"t={t_sec:4.1f}s | processing {fps_now:4.1f} FPS",
        )
        overlay.draw_legend(vis, show_ppe=args.show_ppe, note=args.note)

        writer.write(vis)
        if idx % args.save_every == 0:
            cv2.imwrite(str(frames_dir / f"frame_{idx:05d}.png"), vis)
            saved += 1
        idx += 1

    wall = time.perf_counter() - t_start
    cap.release()
    writer.release()

    import torch

    steady = proc_times[args.warmup:] or proc_times
    stats = {
        "project": PROJECT_NAME,
        "video": video.name,
        "source_resolution": f"{src_w}x{src_h}",
        "processed_resolution": f"{W}x{H}",
        "source_fps": round(src_fps, 2),
        "frames_processed": idx,
        "frames_in_file": n_frames,
        "imgsz": args.imgsz,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        "processing_fps_all_frames": round(len(proc_times) / sum(proc_times), 2) if proc_times else None,
        f"processing_fps_after_{args.warmup}_warmup_frames": round(len(steady) / sum(steady), 2) if steady else None,
        "end_to_end_fps_incl_decode_and_writing": round(idx / wall, 2) if wall else None,
        "unique_track_ids": len(reg.tracks),
        "events": len(reg.events),
        "png_frames_saved": saved,
    }
    (out_dir / "events.json").write_text(json.dumps(reg.events, indent=2), encoding="utf-8")
    (out_dir / "fps.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    for e in reg.events:
        print(f"EVENT frame={e['frame']:5d} t={e['t_sec']:6.2f}s id={e['track_id']:3d} {e['event']} {e['detail']}")
    print(f"Output: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
