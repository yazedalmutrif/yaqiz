"""Camera worker: read → track people + detect PPE → analyse → rules → events → annotated stream.

One thread per camera. Events are written to SQLite (short sessions) and pushed to the
dashboard through the bus; snapshots are always face-pixelated.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import cv2
import numpy as np

from ..config import ROOT, SITE_TZ
from ..geometry import calibration_coverage, clip_to_coverage, covers, invert, project_visible
from ..heat import midday_ban_active
from ..models import Camera, Event, Zone
from ..rules import Candidate, RuleEngine, ZoneRule
from ..serialize import event_dict
from .analysis import analyse_frame
from .engine import PersonTracker, PoseEstimator, attach_keypoints
from .overlay import COL_CRIT, draw_overlay
from .privacy import blur_faces
from .sources import FrameSource

if TYPE_CHECKING:
    from ..context import Context

log = logging.getLogger("yaqiz.worker")

MAX_FAILURES = 20  # consecutive failed frames before the camera shows "error" (it keeps retrying)
STALL_S = 5.0      # no processed frame for this long while "running" -> "stalled"


@dataclass
class _Loop:
    """State carried from one frame to the next inside a camera thread."""

    period: float
    next_t: float
    fps_t: float
    last_seq: int = -1
    zkey: tuple | None = None
    zones_img: dict = field(default_factory=dict)
    fps_n: int = 0
    minute: datetime | None = None
    counters: dict | None = None
    last_stats: float = 0.0
    last_pos: float = 0.0
    n_frame: int = 0
    kp_cache: dict = field(default_factory=dict)
    dets: list = field(default_factory=list)
    failures: int = 0


def zone_polygons_for_camera(H: np.ndarray | None, zones: list[Zone], w: int, h: int,
                             coverage=None) -> dict[int, np.ndarray]:  # noqa: ANN001
    """Project plan zones into the image: each zone is first clipped to the camera's calibrated
    ground area (coverage), then kept only if it is in view and not wildly extrapolated."""
    out: dict[int, np.ndarray] = {}
    if H is None:
        return out
    for z in zones:
        if not z.points or len(z.points) < 3:
            continue
        clipped = clip_to_coverage(z.points, coverage)
        if clipped is None:
            continue
        pts = project_visible(H, clipped)
        if pts is None or not np.all(np.isfinite(pts)):
            continue
        xs, ys = pts[:, 0], pts[:, 1]
        if xs.max() < 0 or xs.min() > w or ys.max() < 0 or ys.min() > h:
            continue
        if np.ptp(xs) > 4 * w or np.ptp(ys) > 4 * h:
            continue
        out[z.id] = pts.astype(np.float32)
    return out


class CameraWorker:
    def __init__(self, ctx: "Context", camera: Camera) -> None:
        self.ctx = ctx
        self.id = camera.id
        self.name = camera.name
        self.source = FrameSource(camera.source, ctx.settings.max_side, ROOT)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._jpeg: bytes | None = None
        self._jpeg_seq = 0
        self._raw_blurred: np.ndarray | None = None
        self._cfg_lock = threading.Lock()
        self._cfg_version = 0
        self._open: dict[tuple, int] = {}
        self.state, self.error = "stopped", None
        self.fps = 0.0
        self.people = self.in_zone = 0
        self._latency: deque[float] = deque(maxlen=300)  # ms per processed frame
        self.last_frame_at: float | None = None          # time.monotonic() of the last processed frame
        self.frame_size: tuple[int, int] | None = None
        self.zones_in_view: list[int] = []
        self.engine: RuleEngine | None = None
        self.reload()

    # ------------------------------------------------------------------ config
    def reload(self) -> None:
        cam = self.ctx.store.get_camera(self.id)
        zones = self.ctx.store.list_zones()
        rt = self.ctx.store.get_runtime()
        rules = [ZoneRule(id=z.id, name=z.name, kind=z.kind, active=z.active, outdoor=z.outdoor,
                          require_helmet=z.require_helmet, require_vest=z.require_vest,
                          require_harness=z.require_harness, interlock=z.interlock) for z in zones]
        H = np.asarray(cam.homography, dtype=np.float64) if cam and cam.homography else None
        coverage = calibration_coverage([p["plan"] for p in (cam.calib_pairs or [])]) if cam and H is not None else None
        with self._cfg_lock:
            self.rt, self.H, self.zones, self.coverage = rt, H, zones, coverage
            self.H_inv = invert(H) if H is not None else None
            self.zone_rules = {r.id: r for r in rules}
            if self.engine is None:
                self.engine = RuleEngine(rt, rules)
            else:
                self.engine.configure(rt, rules)
            if cam:
                self.name = cam.name
            self._cfg_version += 1

    # ------------------------------------------------------------------ lifecycle
    @property
    def alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.alive:
            return
        self._stop.clear()
        self.state, self.error = "loading", None
        self._thread = threading.Thread(target=self._run, name=f"camera:{self.id}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)
        self.source.stop()
        self._close_open("camera_stopped")  # the thread closes them on exit; this covers a join timeout
        self.state = "stopped"
        self.ctx.bus.publish({"type": "camera_status", "camera": self.status()})

    def _close_open(self, reason: str) -> None:
        now = datetime.now(timezone.utc)
        for key, ev_id in list(self._open.items()):
            self._open.pop(key, None)
            try:
                ev = self.ctx.store.update_event(ev_id, ended_at=now, detail={"closed_reason": reason})
                if ev:
                    self.ctx.bus.publish({"type": "event", "action": "close", "event": event_dict(ev)})
            except Exception:  # noqa: BLE001
                log.exception("camera %s: closing event %s failed", self.id, ev_id)

    # ------------------------------------------------------------------ outputs
    def latest_jpeg(self) -> tuple[bytes | None, int]:
        with self._lock:
            return self._jpeg, self._jpeg_seq

    def snapshot_jpeg(self) -> bytes | None:
        """Latest frame without overlays (faces pixelated), used for calibration."""
        with self._lock:
            frame = None if self._raw_blurred is None else self._raw_blurred.copy()
        if frame is None:
            return None
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return buf.tobytes() if ok else None

    def latency(self) -> dict:
        """Frame decode -> events published and stream frame ready, over the last 300 processed frames (ms)."""
        lat = sorted(self._latency)
        if not lat:
            return {"latency_ms": None, "latency_p95_ms": None}
        return {"latency_ms": round(lat[len(lat) // 2], 1),
                "latency_p95_ms": round(lat[min(len(lat) - 1, int(0.95 * len(lat)))], 1)}

    def status(self) -> dict:
        state = self.state
        if state in ("running", "waiting") and self.source.state in ("error", "reconnecting", "connecting"):
            state = self.source.state
        if state == "running" and self.last_frame_at and time.monotonic() - self.last_frame_at > STALL_S:
            state = "stalled"
        if state in ("running", "waiting", "loading", "stalled") and self._thread and not self._thread.is_alive():
            state = "error"
        return {
            "id": self.id, "name": self.name, "state": state, "error": self.error or self.source.error,
            "fps": round(self.fps, 1), "people": self.people, "in_zone": self.in_zone, **self.latency(),
            "frame_size": list(self.frame_size) if self.frame_size else None,
            "calibrated": self.H is not None, "zones_in_view": self.zones_in_view,
        }

    # ------------------------------------------------------------------ events
    def _handle(self, c: Candidate, snap: np.ndarray, wall: datetime) -> None:
        store, bus = self.ctx.store, self.ctx.bus
        if c.action == "open":
            detail = dict(c.detail)
            if c.kind == "zone_intrusion" and detail.get("interlock") and c.zone_id is not None:
                detail["operator_signal"] = self.ctx.interlock.signal(c.zone_id, detail.get("zone_name"), self.id, c.kind)
            ev = store.add_event(Event(
                ts=wall, kind=c.kind, severity=c.severity, camera_id=self.id, zone_id=c.zone_id,
                track_id=c.track_id, item=c.item, detail=detail,
                plan_x=c.foot_plan[0] if c.foot_plan else None, plan_y=c.foot_plan[1] if c.foot_plan else None,
                img_x=c.foot_img[0] if c.foot_img else None, img_y=c.foot_img[1] if c.foot_img else None,
            ))
            self._open[c.key] = ev.id  # tracked at once, so a failure below can never orphan the row
            rel = self._save_snapshot(ev.id, snap, c.box, wall)
            if rel:
                try:
                    ev = store.update_event(ev.id, snapshot=rel) or ev
                except Exception:  # noqa: BLE001
                    log.exception("camera %s: saving the snapshot path of event %s failed", self.id, ev.id)
            bus.publish({"type": "event", "action": "open", "event": event_dict(ev)})
        elif c.action == "update":
            ev_id = self._open.get(c.key)
            if ev_id:
                ev = store.update_event(ev_id, severity=c.severity, duration_s=c.duration_s, detail=c.detail)
                if ev:
                    bus.publish({"type": "event", "action": "update", "event": event_dict(ev)})
        elif c.action == "close":
            ev_id = self._open.pop(c.key, None)
            if ev_id:
                ev = store.update_event(ev_id, ended_at=wall, duration_s=c.duration_s,
                                        detail={"closed_reason": c.detail.get("reason")})
                if ev:
                    bus.publish({"type": "event", "action": "close", "event": event_dict(ev)})

    def _save_snapshot(self, event_id: int, img: np.ndarray, box, wall: datetime) -> str | None:
        try:
            day = wall.astimezone(SITE_TZ).strftime("%Y-%m-%d")
            folder = self.ctx.settings.snapshots_dir / day
            folder.mkdir(parents=True, exist_ok=True)
            out = img.copy()
            if box:
                x1, y1, x2, y2 = (int(v) for v in box)
                pad = 6
                cv2.rectangle(out, (x1 - pad, y1 - pad), (x2 + pad, y2 + pad), COL_CRIT, 3)
            path = folder / f"{event_id}.jpg"
            cv2.imwrite(str(path), out, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return f"{day}/{event_id}.jpg"
        except Exception:  # snapshots must never stop detection
            log.exception("snapshot failed for event %s", event_id)
            return None

    # ------------------------------------------------------------------ main loop
    def _run(self) -> None:
        s = self.ctx.settings
        try:
            tracker = PersonTracker(s)
            pose = PoseEstimator(s)
            ppe = self.ctx.ppe()
        except Exception as exc:  # noqa: BLE001
            log.exception("model load failed")
            self.state, self.error = "error", f"تعذّر تحميل النموذج: {exc}"
            return
        self.source.start()
        self.state = "waiting"
        t0 = time.monotonic()
        lp = _Loop(period=1.0 / max(s.max_fps, 0.5), next_t=t0, fps_t=t0)
        try:
            while not self._stop.is_set():
                got = self.source.read()
                if got is None or got[1] == lp.last_seq:
                    if self.source.state != "live":
                        self.state = self.source.state
                    time.sleep(0.01)
                    continue
                now = time.monotonic()
                if now < lp.next_t:
                    time.sleep(min(lp.next_t - now, 0.02))
                    continue
                lp.next_t = max(lp.next_t + lp.period, now - lp.period)
                frame, lp.last_seq, t_captured = got
                try:
                    self._process(frame, t_captured, now, lp, tracker, pose, ppe)
                except Exception as exc:  # noqa: BLE001  one bad frame must never stop the camera
                    lp.failures += 1
                    log.exception("camera %s: frame failed (%d in a row)", self.id, lp.failures)
                    self.error = f"تعذّرت معالجة الإطار: {exc}"
                    if lp.failures >= MAX_FAILURES:
                        self.state = "error"
                    time.sleep(0.5)
                    continue
                lp.failures = 0
                self.last_frame_at = time.monotonic()
                if self.error:
                    self.error = None
        finally:
            if lp.minute is not None and lp.counters and lp.counters["frames"]:
                try:
                    self.ctx.store.add_stats(self.id, lp.minute, lp.counters)
                except Exception:  # noqa: BLE001
                    log.exception("camera %s: saving the last minute of stats failed", self.id)
            self._close_open("camera_stopped")
            self.source.stop()
            self.state = "stopped" if self._stop.is_set() else "error"

    def _process(self, frame: np.ndarray, t_captured: float, now: float, lp: _Loop,
                 tracker: PersonTracker, pose: PoseEstimator, ppe) -> None:  # noqa: ANN001
        """One frame: detect, analyse, apply the rules, publish events, the stream and the live numbers."""
        s = self.ctx.settings
        self.state = "running"
        h, w = frame.shape[:2]
        with self._cfg_lock:
            rt, H, H_inv, engine = self.rt, self.H, self.H_inv, self.engine
            zones, zrules, version, coverage = self.zones, self.zone_rules, self._cfg_version, self.coverage
        if lp.zkey != (w, h, version):
            lp.zones_img = zone_polygons_for_camera(H, zones, w, h, coverage)
            lp.zkey = (w, h, version)
            self.zones_in_view = sorted(lp.zones_img)
            if self.frame_size != (w, h):
                self.frame_size = (w, h)
                self.ctx.store.set_frame_size(self.id, w, h)
        tracks = tracker.track(frame, rt.pose_conf)
        poses = pose.estimate(frame, rt.pose_conf) if tracks and lp.n_frame % max(1, s.pose_every) == 0 else None
        persons = attach_keypoints(tracks, poses, lp.kp_cache, now)
        if lp.n_frame % max(1, s.ppe_every) == 0:
            lp.dets = ppe.detect(frame, rt.det_conf)
        lp.n_frame += 1
        obs = analyse_frame(persons, lp.dets, lp.zones_img, H_inv, rt, ppe.capabilities)
        wall = datetime.now(timezone.utc)
        cands = engine.update(obs, now, midday_ban_active(wall.astimezone(SITE_TZ), rt), ppe.capabilities)
        status = {p.track_id: engine.track_status(p.track_id) for p in persons}
        blurred = blur_faces(frame.copy(), persons, rt.kp_conf)
        kw = dict(camera_id=self.id, zones_img=lp.zones_img, zones=zrules, persons=persons, obs=obs,
                  status=status, fps=self.fps, kp_conf=rt.kp_conf,
                  machines=[d for d in lp.dets if d.cls == "machinery"])
        annotated = draw_overlay(blurred.copy() if rt.blur_stream else frame.copy(), **kw)
        if cands:
            snap = annotated if rt.blur_stream else draw_overlay(blurred.copy(), **kw)
            for c in cands:
                try:
                    self._handle(c, snap, wall)
                except Exception:  # noqa: BLE001
                    log.exception("camera %s: event handling failed", self.id)
        ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, s.jpeg_quality])
        with self._lock:
            if ok:
                self._jpeg, self._jpeg_seq = buf.tobytes(), self._jpeg_seq + 1
            self._raw_blurred = blurred
        if t_captured:
            self._latency.append((time.monotonic() - t_captured) * 1000.0)

        # live numbers
        self.people = len(obs)
        self.in_zone = sum(
            1 for o in obs
            if any((zr := zrules.get(z)) and zr.kind == "no_entry" and zr.active for z in engine.inside_zones(o.track_id))
        )
        lp.fps_n += 1
        if now - lp.fps_t >= 1.0:
            self.fps, lp.fps_n, lp.fps_t = lp.fps_n / (now - lp.fps_t), 0, now
        m = wall.replace(second=0, microsecond=0)
        if lp.minute != m:
            prev, prev_counters = lp.minute, lp.counters
            lp.minute = m
            lp.counters = dict(frames=0, people=0, in_zone=0, helmet_yes=0, helmet_no=0, vest_yes=0, vest_no=0)
            if prev is not None and prev_counters:
                self.ctx.store.add_stats(self.id, prev, prev_counters)  # the new minute has already started
        lp.counters["frames"] += 1
        lp.counters["people"] += len(obs)
        lp.counters["in_zone"] += self.in_zone
        ppe_now = {"helmet_yes": 0, "helmet_no": 0, "vest_yes": 0, "vest_no": 0}
        for o in obs:
            for item in ("helmet", "vest"):
                st = engine.ppe_state(o.track_id, item)
                if st in ("yes", "no"):
                    ppe_now[f"{item}_{st}"] += 1
        for k, v in ppe_now.items():
            lp.counters[k] += v
        if now - lp.last_stats >= 1.0:
            lp.last_stats = now
            self.ctx.bus.publish({"type": "stats", "camera_id": self.id, "fps": round(self.fps, 1),
                                  "people": self.people, "in_zone": self.in_zone, "state": self.state,
                                  **self.latency(), **ppe_now})
        if H_inv is not None and now - lp.last_pos >= 0.25:
            lp.last_pos = now
            self.ctx.bus.publish({"type": "positions", "camera_id": self.id, "tracks": [
                {"id": o.track_id, "x": round(o.foot_plan[0], 1), "y": round(o.foot_plan[1], 1),
                 "status": status.get(o.track_id, "ok")}
                for o in obs if o.foot_plan is not None and covers(coverage, o.foot_plan)]})


class WorkerManager:
    def __init__(self, ctx: "Context") -> None:
        self.ctx = ctx
        self.workers: dict[int, CameraWorker] = {}
        self._lock = threading.Lock()

    def start_all(self) -> None:
        for cam in self.ctx.store.list_cameras():
            if cam.enabled:
                self.start(cam.id)

    def start(self, camera_id: int) -> None:
        cam = self.ctx.store.get_camera(camera_id)
        if cam is None:
            return
        with self._lock:
            w = self.workers.get(camera_id)
            if w and w.alive:
                return
            w = CameraWorker(self.ctx, cam)
            self.workers[camera_id] = w
        w.start()
        self.ctx.bus.publish({"type": "camera_status", "camera": w.status()})

    def stop(self, camera_id: int) -> None:
        with self._lock:
            w = self.workers.pop(camera_id, None)
        if w:
            w.stop()

    def restart(self, camera_id: int) -> None:
        self.stop(camera_id)
        self.start(camera_id)

    def reload(self, camera_id: int) -> None:
        w = self.workers.get(camera_id)
        if w:
            w.reload()

    def reload_all(self) -> None:
        for w in list(self.workers.values()):
            w.reload()

    def get(self, camera_id: int) -> CameraWorker | None:
        return self.workers.get(camera_id)

    def stop_all(self) -> None:
        for cid in list(self.workers):
            self.stop(cid)

    def status(self, camera_id: int) -> dict | None:
        w = self.workers.get(camera_id)
        return w.status() if w else None
