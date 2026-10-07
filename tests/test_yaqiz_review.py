"""Tests added after the 2026-10-07 code review: worker resilience, orphaned events, de-duplication of
nearby workers, machine-proximity edge cases, risk-grid boundaries and nested machinery boxes."""
from __future__ import annotations

import time
from datetime import date, datetime, timezone

import numpy as np

from yaqiz.config import SITE_TZ, RuntimeSettings, Settings
from yaqiz.models import Camera, Event
from yaqiz.risk import risk_grid
from yaqiz.rules import PersonObs, RuleEngine, ZoneRule
from yaqiz.vision.engine import Det, suppress_nested

ZONE = ZoneRule(id=1, name="الحافة", kind="no_entry")
EXCAVATOR = (400.0, 200.0, 800.0, 500.0)


def _machine(xyxy, conf=0.8):
    return Det("machinery", conf, xyxy)


def _p(tid, box, zones=(1,)):
    x1, y1, x2, y2 = box
    return PersonObs(track_id=tid, box=box, foot_img=((x1 + x2) / 2, y2), foot_plan=None, zone_ids=frozenset(zones))


def _run(engine, frames, start=0.0, dt=0.1):
    out = []
    for i, persons in enumerate(frames):
        out += engine.update(persons, start + i * dt)
    return out


# ----------------------------------------------------------------------------- de-duplication
def test_two_workers_side_by_side_each_get_an_event():
    e = RuleEngine(RuntimeSettings(enter_frames=1, site_require_helmet=False), [ZONE])
    a, b = _p(1, (80.0, 0.0, 120.0, 100.0)), _p(2, (125.0, 0.0, 165.0, 100.0))   # feet 45 px apart
    out = _run(e, [[a, b]] * 3)
    assert {c.track_id for c in out if c.action == "open"} == {1, 2}


def test_a_new_id_for_a_hidden_worker_is_still_the_same_event():
    e = RuleEngine(RuntimeSettings(enter_frames=1, lost_s=3.0, site_require_helmet=False), [ZONE])
    _run(e, [[_p(1, (80.0, 0.0, 120.0, 100.0))]] * 3)
    out = _run(e, [[_p(9, (95.0, 0.0, 135.0, 100.0))]] * 3, start=0.3)   # track 1 gone, within lost_s
    assert not [c for c in out if c.action == "open"]


def test_one_worker_detected_twice_in_the_same_frame_is_one_event():
    e = RuleEngine(RuntimeSettings(enter_frames=1, site_require_helmet=False), [ZONE])
    a, b = _p(1, (80.0, 0.0, 120.0, 100.0)), _p(2, (82.0, 2.0, 121.0, 101.0))  # boxes overlap almost fully
    out = _run(e, [[a, b]] * 3)
    assert len([c for c in out if c.action == "open"]) == 1


# ----------------------------------------------------------------------------- machine proximity
def test_worker_right_behind_the_machine_counts_but_a_distant_one_does_not():
    from yaqiz.vision.analysis import near_machine
    m = [_machine(EXCAVATOR)]
    behind = (570.0, 320.0, 630.0, 440.0)             # 120 px tall, feet 20% up the machine's box
    assert near_machine(behind, (600.0, 440.0), m, gap=1.0)
    far_small = (790.0, 370.0, 810.0, 400.0)          # 30 px tall next to a 300 px machine: far behind it
    assert not near_machine(far_small, (800.0, 400.0), m, gap=1.0)


def test_a_lying_worker_is_measured_by_body_length():
    from yaqiz.vision.analysis import near_machine
    lying = (820.0, 470.0, 1000.0, 500.0)             # 180 x 30 px, beside the tracks
    assert near_machine(lying, (910.0, 500.0), [_machine(EXCAVATOR)], gap=1.0, lying=True)
    assert not near_machine(lying, (910.0, 500.0), [_machine(EXCAVATOR)], gap=1.0, lying=False)


def test_near_machine_survives_degenerate_boxes():
    from yaqiz.vision.analysis import near_machine
    for box in ((10.0, 10.0, 10.0, 10.0), (5.0, 5.0, 1.0, 1.0)):
        for m in ((0.0, 0.0, 0.0, 0.0), EXCAVATOR):
            assert near_machine(box, (box[2], box[3]), [_machine(m)], gap=1.0) in (True, False)


def test_analyse_frame_reports_near_machine_only_with_the_machinery_class():
    from yaqiz.vision.analysis import analyse_frame
    from yaqiz.vision.engine import PersonDet
    person = PersonDet(1, 0.9, (795.0, 325.0, 845.0, 495.0), np.zeros((17, 3)))
    rt = RuntimeSettings()
    assert analyse_frame([person], [], {}, None, rt, frozenset({"helmet"}))[0].near_machine is None
    assert analyse_frame([person], [], {}, None, rt, frozenset({"machinery"}))[0].near_machine is False
    assert analyse_frame([person], [_machine(EXCAVATOR)], {}, None, rt, frozenset({"machinery"}))[0].near_machine is True


# ----------------------------------------------------------------------------- nested machinery boxes
def test_suppress_nested_edge_cases():
    whole = Det("machinery", 0.8, (0.0, 0.0, 100.0, 100.0))
    assert suppress_nested([], "machinery") == []
    assert suppress_nested([whole, Det("machinery", 0.8, (0.0, 0.0, 100.0, 100.0))], "machinery") == [whole]
    part = Det("machinery", 0.9, (10.0, 10.0, 40.0, 40.0))     # a part MORE confident than the whole
    assert len(suppress_nested([whole, part], "machinery")) == 2


# ----------------------------------------------------------------------------- risk grid boundaries
def test_day_shift_grid_is_06_00_to_17_59():
    def ev(h, m=0, s=0):
        local = datetime(2026, 7, 1, h, m, s, tzinfo=SITE_TZ)
        return {"ts": local.astimezone(timezone.utc), "kind": "zone_intrusion", "severity": "warning", "zone_id": 1}
    g = risk_grid([ev(17, 59, 59), ev(18), ev(5, 59, 59)], [{"id": 1, "name": "z", "outdoor": False}],
                  date(2026, 7, 1), SITE_TZ)
    row = next(r for r in g["zones"] if r["zone_id"] == 1)
    assert g["hours"] == list(range(6, 18)) and row["total"] == 3.0   # only 17:59:59 counts


# ----------------------------------------------------------------------------- orphaned events
def test_events_left_open_by_a_previous_run_are_closed(tmp_path):
    from yaqiz.store import Store
    st = Store(tmp_path / "y.db")
    ev = st.add_event(Event(kind="zone_intrusion", duration_s=4.0))
    assert st.close_orphan_events() == 1
    got = st.get_event(ev.id)
    assert got.ended_at is not None and got.detail["closed_reason"] == "server_restart"
    assert st.close_orphan_events() == 0


# ----------------------------------------------------------------------------- frame source
def test_frame_source_read_returns_frame_sequence_and_capture_time():
    from yaqiz.vision.sources import FrameSource
    src = FrameSource("missing.mp4")
    assert src.read() is None
    src._frame, src._seq, src._t_frame = np.zeros((2, 2, 3), np.uint8), 7, 123.0
    _, seq, t = src.read()
    assert (seq, t) == (7, 123.0)


# ----------------------------------------------------------------------------- worker resilience
class _FakeSource:
    def __init__(self) -> None:
        self.state, self.error, self.seq = "live", None, 0

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def read(self):
        self.seq += 1
        return np.zeros((120, 160, 3), np.uint8), self.seq, time.monotonic()


class _FakeModel:
    capabilities = frozenset()

    def __init__(self, *_a, **_k) -> None: ...

    def track(self, *_a):
        return []

    def estimate(self, *_a):
        return []

    def detect(self, *_a):
        return []


def test_camera_keeps_running_after_a_failing_frame(tmp_path, monkeypatch):
    import yaqiz.vision.worker as worker_mod
    from yaqiz.context import Context

    ctx = Context(Settings(data_dir=tmp_path / "data", start_workers=False, max_fps=20.0))
    cam = ctx.store.save_camera(Camera(name="test", source="none.mp4"))
    monkeypatch.setattr(worker_mod, "PersonTracker", _FakeModel)
    monkeypatch.setattr(worker_mod, "PoseEstimator", _FakeModel)
    ctx._ppe = _FakeModel()
    real = worker_mod.analyse_frame
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return real(*a, **k)

    monkeypatch.setattr(worker_mod, "analyse_frame", flaky)
    w = worker_mod.CameraWorker(ctx, cam)
    w.source = _FakeSource()
    w.start()
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and (w.latest_jpeg()[1] < 3 or w.error):
        time.sleep(0.05)
    try:
        assert calls["n"] >= 4, "the loop stopped after the failing frame"
        assert w.latest_jpeg()[1] >= 3 and w.error is None and w.alive
        assert w.status()["state"] == "running"
    finally:
        w.stop()
    assert w.status()["state"] == "stopped"



# ----------------------------------------------------------------------------- man-down: moving is not "still"
def test_man_down_does_not_fire_for_a_lying_worker_who_keeps_moving():
    import math

    from yaqiz.posture import ManDownDetector, pose_features
    box0 = (30.0, 190.0, 260.0, 235.0)                      # lying, 230 px long
    motions = (lambda t: 19.0 * math.sin(2 * math.pi * t),  # +-19 px at 1 Hz: working on the floor
               lambda t: 20.0 * t)                          # a 20 px/s crawl
    for motion in motions:
        md, fired = ManDownDetector(5.0), False
        for i in range(100):                                # 10 s at 10 fps
            dx = motion(i / 10)
            fired |= md.update(pose_features(None, (box0[0] + dx, box0[1], box0[2] + dx, box0[3])), i / 10)
        assert not fired


# ----------------------------------------------------------------------------- device choice (Windows GPU, Mac GPU, CPU)
def test_pick_device_prefers_cuda_then_apple_gpu_then_cpu(monkeypatch):
    import torch

    from yaqiz.vision.engine import pick_device
    s = Settings()
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "get_device_capability", lambda i=0: (8, 9))   # RTX 40 series
    monkeypatch.setattr(torch.cuda, "get_arch_list", lambda: ["sm_75", "sm_86", "sm_120"])
    assert pick_device(s) == 0
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)
    assert pick_device(s) == "mps"
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    assert pick_device(s) == "cpu"


def test_pick_device_falls_back_to_cpu_on_a_gpu_this_pytorch_build_cannot_run(monkeypatch):
    """The CUDA 13 build (sm_75 to sm_120) has no kernels for GTX 10-series (6.1) or Volta (7.0) GPUs:
    is_available() is True there, but every model call would fail, so Yaqiz must use the CPU."""
    import torch

    from yaqiz.vision.engine import pick_device
    s = Settings()
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "get_arch_list", lambda: ["sm_75", "sm_80", "sm_86", "sm_90", "sm_100", "sm_120"])
    monkeypatch.setattr(torch.cuda, "get_device_name", lambda i=0: "Test GPU")
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    cases = {(8, 9): 0, (7, 5): 0, (8, 0): 0, (12, 0): 0, (10, 3): 0, (6, 1): "cpu", (7, 0): "cpu", (5, 2): "cpu"}
    for cap, expected in cases.items():
        monkeypatch.setattr(torch.cuda, "get_device_capability", lambda i=0, c=cap: c)
        assert pick_device(s) == expected, cap
    monkeypatch.setattr(torch.cuda, "get_arch_list", lambda: ["sm_90", "compute_90"])      # PTX: newer GPUs run
    monkeypatch.setattr(torch.cuda, "get_device_capability", lambda i=0: (13, 0))
    assert pick_device(s) == 0

    def unqueryable(i=0):
        raise RuntimeError("CUDA error: no kernel image is available for execution on the device")

    monkeypatch.setattr(torch.cuda, "get_device_capability", unqueryable)
    assert pick_device(s) == "cpu"
    assert pick_device(Settings(device="cuda:0")) == "cuda:0"                            # an explicit setting wins
