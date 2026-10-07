"""Unit tests for the Yaqiz core logic: geometry, posture, heat, risk and the rule engine."""
from __future__ import annotations

from datetime import date, datetime, timezone

import numpy as np
import pytest

from yaqiz.config import SITE_TZ, RuntimeSettings
from yaqiz.geometry import fit_homography, foot_point, invert, point_in_polygon, project, project_visible, validate_polygon
from yaqiz.heat import heat_category, heat_index_c, midday_ban_active
from yaqiz.posture import HoldTimer, ManDownDetector, SosDetector, pose_features
from yaqiz.risk import level_of, risk_grid
from yaqiz.rules import PersonObs, RuleEngine, ZoneRule

# ----------------------------------------------------------------------------- geometry
PLAN = [(1100, 200), (1100, 650), (1040, 650), (1040, 200)]
IMG = [(748.8, 266.4), (1273.6, 266.4), (1273.6, 338.4), (748.8, 338.4)]


def test_homography_four_points_is_exact_and_invertible():
    H, err = fit_homography(PLAN, IMG)
    assert err < 1e-3  # sub-thousandth of a pixel (float precision of cv2.findHomography)
    assert np.allclose(project(H, PLAN), IMG, atol=1e-3)
    assert np.allclose(project(invert(H), IMG), PLAN, atol=1e-3)


def test_homography_rejects_bad_input():
    with pytest.raises(ValueError):
        fit_homography(PLAN[:3], IMG[:3])
    with pytest.raises(ValueError):
        fit_homography([(0, 0), (1, 1), (2, 2), (3, 3)], IMG)  # collinear


def test_project_visible_flags_points_behind_camera():
    H = np.array([[1, 0, 0], [0, 1, 0], [0, -0.01, 1.0]])  # horizon at y = 100
    assert project_visible(H, [(0, 50)]) is not None
    assert project_visible(H, [(0, 150)]) is None


def test_polygon_helpers():
    poly = validate_polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    assert point_in_polygon((5, 5), poly) and point_in_polygon((10, 5), poly)
    assert not point_in_polygon((11, 5), poly)
    with pytest.raises(ValueError):
        validate_polygon([(0, 0), (1, 1), (2, 2)])


def test_foot_point_prefers_ankles_for_x():
    k = np.zeros((17, 3))
    k[15] = (40, 95, 0.9)
    k[16] = (60, 96, 0.9)
    assert foot_point((0, 0, 200, 100), k) == (50.0, 100.0)
    assert foot_point((0, 0, 200, 100), None) == (100.0, 100.0)


# ----------------------------------------------------------------------------- posture
def _standing(cx=100.0):
    k = np.zeros((17, 3))
    k[:, 2] = 0.9
    k[0] = (cx, 30, 0.9)
    k[5], k[6] = (cx + 20, 60, 0.9), (cx - 20, 60, 0.9)        # left shoulder appears on image right (front view)
    k[9], k[10] = (cx + 28, 140, 0.9), (cx - 28, 140, 0.9)      # wrists down
    k[11], k[12] = (cx + 12, 140, 0.9), (cx - 12, 140, 0.9)
    k[15], k[16] = (cx + 14, 240, 0.9), (cx - 14, 240, 0.9)
    return k


def _sos(cx=100.0):
    k = _standing(cx)
    k[9], k[10] = (cx - 15, 10, 0.9), (cx + 15, 10, 0.9)        # wrists above head, swapped sides
    return k


def _hands_up_not_crossed(cx=100.0):
    k = _standing(cx)
    k[9], k[10] = (cx + 15, 10, 0.9), (cx - 15, 10, 0.9)
    return k


def _lying():
    k = np.zeros((17, 3))
    k[:, 2] = 0.9
    k[5], k[6] = (60, 200, 0.9), (60, 220, 0.9)
    k[11], k[12] = (150, 205, 0.9), (150, 222, 0.9)
    k[9], k[10] = (40, 215, 0.9), (45, 210, 0.9)
    return k


BOX = (60, 0, 140, 250)


def test_sos_requires_raised_and_crossed_wrists():
    assert pose_features(_sos(), BOX).sos is True
    assert pose_features(_hands_up_not_crossed(), BOX).sos is False
    assert pose_features(_standing(), BOX).sos is False


def test_lying_posture_detected():
    f = pose_features(_lying(), (30, 190, 170, 235))
    assert f.lying is True and not f.sos
    assert pose_features(_standing(), BOX).lying is False


def test_hold_timer_bridges_short_gaps():
    t = HoldTimer(1.0, grace_s=0.3)
    assert not t.update(True, 0.0)
    assert not t.update(False, 0.2)   # short gap bridged
    assert t.update(True, 1.05)
    assert not t.update(False, 2.0)   # long gap resets


def test_sos_and_man_down_detectors_need_time():
    sos, md = SosDetector(1.5), ManDownDetector(5.0)
    fs, fl = pose_features(_sos(), BOX), pose_features(_lying(), (30, 190, 170, 235))
    assert not any(sos.update(fs, t / 10) for t in range(0, 14))
    assert sos.update(fs, 1.6)
    assert not md.update(fl, 0.0)
    assert any(md.update(fl, t / 10) for t in range(1, 61))



def test_man_down_fires_for_still_worker_with_jittery_box_and_sparse_keypoints():
    """Regression (GMDCSA-24 subject 2, Fall/10): a motionless lying worker must raise man-down even when the
    person box jitters by a few pixels and keypoints are found only now and then. The stillness yardstick
    used to be 0.35 x box height, which is tiny for someone lying down, and the anchor jumped between the
    torso centre (keypoint frames) and the box centre (other frames)."""
    box0 = (30.0, 190.0, 260.0, 235.0)             # lying: 230 px long, 45 px tall
    md = ManDownDetector(2.0)
    fired = False
    for i in range(60):
        j = 4.0 if i % 2 else -4.0                 # detector jitter
        box = (box0[0] + j, box0[1], box0[2] + j, box0[3])
        f = pose_features(_lying() if i % 15 == 0 else None, box)  # keypoints every 1.5 s only
        assert f.lying
        fired |= md.update(f, i / 10)
    assert fired

# ----------------------------------------------------------------------------- heat
def test_heat_index_matches_nws():
    assert heat_index_c(35, 50) == pytest.approx(40.7, abs=0.2)   # 95°F / 50% → 105.2°F
    assert heat_index_c(25, 40) == pytest.approx(24.6, abs=0.2)   # simple formula branch
    assert heat_category(40.7)[0] == 3 and heat_category(20)[0] == 0


def test_midday_ban_window():
    rt = RuntimeSettings()
    at = lambda m, d, h, mi=0: datetime(2026, m, d, h, mi, tzinfo=SITE_TZ)  # noqa: E731
    assert midday_ban_active(at(7, 1, 13), rt)
    assert midday_ban_active(at(9, 15, 12, 30), rt)
    assert not midday_ban_active(at(7, 1, 15), rt)
    assert not midday_ban_active(at(6, 14, 13), rt)
    assert not midday_ban_active(at(10, 7, 13), rt)


# ----------------------------------------------------------------------------- risk
def test_risk_grid_scores_and_levels():
    day = date(2026, 10, 7)
    ts = lambda h: datetime(2026, 10, 7, h, 30, tzinfo=SITE_TZ).astimezone(timezone.utc)  # noqa: E731
    events = [
        {"ts": ts(9), "kind": "zone_intrusion", "severity": "warning", "zone_id": 1},
        {"ts": ts(9), "kind": "zone_intrusion", "severity": "critical", "zone_id": 1},
        {"ts": ts(10), "kind": "man_down", "severity": "critical", "zone_id": 2},
        {"ts": ts(11), "kind": "ppe_missing", "severity": "warning", "zone_id": None},
        {"ts": ts(22), "kind": "sos", "severity": "critical", "zone_id": 1},  # outside the 06–18 shift
    ]
    zones = [{"id": 1, "name": "A", "outdoor": False}, {"id": 2, "name": "B", "outdoor": True}]
    g = risk_grid(events, zones, day, SITE_TZ, heat_by_hour={10: 2})
    rows = {r["zone_id"]: r for r in g["zones"]}
    assert rows[1]["scores"][3] == 8.0 and rows[1]["levels"][3] == 3          # 3 + (3 + 2)
    assert rows[2]["scores"][4] == pytest.approx(18.0) and rows[2]["levels"][4] == 4  # 12 × 1.5 heat
    assert rows[None]["total"] == 2.0
    assert g["top"]["zone_id"] == 2
    assert level_of(0) == 1 and level_of(3) == 2 and level_of(15) == 4


# ----------------------------------------------------------------------------- rules
ZONE = ZoneRule(id=1, name="الحافة", kind="no_entry")
PPE_ZONE = ZoneRule(id=2, name="التشوين", kind="ppe", require_vest=True, outdoor=True)


def _obs(tid=1, zones=(), helmet="yes", vest="yes", pose=None, foot=(100.0, 100.0)):
    return PersonObs(track_id=tid, box=(80, 0, 120, 100), foot_img=foot, foot_plan=None,
                     zone_ids=frozenset(zones), helmet=helmet, vest=vest, pose=pose)


def _run(engine, frames, start=0.0, dt=0.1, **kw):
    out = []
    for i, persons in enumerate(frames):
        out += engine.update(persons, start + i * dt, **kw)
    return out


def test_intrusion_opens_after_enter_frames_escalates_and_closes():
    rt = RuntimeSettings(enter_frames=3, exit_frames=2, escalate_s=1.0, cooldown_s=5)
    e = RuleEngine(rt, [ZONE])
    out = _run(e, [[_obs(zones={1})]] * 2)
    assert out == []
    out = _run(e, [[_obs(zones={1})]] * 13, start=0.2)
    kinds = [(c.action, c.kind, c.severity) for c in out]
    assert kinds[0] == ("open", "zone_intrusion", "warning")
    assert ("update", "zone_intrusion", "critical") in kinds
    out = _run(e, [[_obs(zones=())]] * 3, start=1.6)
    assert [c.action for c in out] == ["close"] and out[0].duration_s > 0
    # cooldown: re-entering at once does not open a new event
    assert not [c for c in _run(e, [[_obs(zones={1})]] * 5, start=2.0) if c.action == "open"]


def test_inactive_zone_never_alerts():
    e = RuleEngine(RuntimeSettings(), [ZoneRule(id=1, name="الرافعة", kind="no_entry", active=False)])
    assert _run(e, [[_obs(zones={1})]] * 20) == []


def test_ppe_missing_needs_votes_and_hold_time():
    rt = RuntimeSettings(ppe_hold_s=0.5, site_require_helmet=True)
    e = RuleEngine(rt, [PPE_ZONE])
    out = _run(e, [[_obs(helmet="no")]] * 12)
    opened = [c for c in out if c.action == "open"]
    assert len(opened) == 1 and opened[0].item == "helmet" and opened[0].zone_id is None
    out = _run(e, [[_obs(zones={2}, vest="no")]] * 20, start=2.0)
    assert any(c.action == "open" and c.item == "vest" and c.zone_id == 2 for c in out)


def test_midday_exposure_only_in_outdoor_zones_during_ban():
    e = RuleEngine(RuntimeSettings(site_require_helmet=False), [PPE_ZONE])
    assert not _run(e, [[_obs(zones={2})]] * 10, midday_ban=False)
    out = _run(e, [[_obs(zones={2})]] * 10, start=2, midday_ban=True)
    assert any(c.kind == "midday_exposure" and c.action == "open" for c in out)


def test_sos_and_man_down_events_are_critical():
    e = RuleEngine(RuntimeSettings(site_require_helmet=False, sos_hold_s=1.0, man_down_s=2.0), [])
    sos = pose_features(_sos(), BOX)
    out = _run(e, [[_obs(pose=sos)]] * 15)
    assert any(c.kind == "sos" and c.severity == "critical" and c.action == "open" for c in out)
    e2 = RuleEngine(RuntimeSettings(site_require_helmet=False, man_down_s=2.0), [])
    lying = pose_features(_lying(), (30, 190, 170, 235))
    out = _run(e2, [[_obs(pose=lying)]] * 40)
    assert any(c.kind == "man_down" and c.action == "open" for c in out)


def test_lost_track_closes_open_events():
    e = RuleEngine(RuntimeSettings(enter_frames=1, lost_s=0.5), [ZONE])
    _run(e, [[_obs(zones={1})]] * 3)
    out = _run(e, [[]] * 10, start=0.3)
    assert any(c.action == "close" and c.detail.get("reason") == "lost" for c in out)


def test_new_track_id_next_to_open_event_is_deduplicated():
    e = RuleEngine(RuntimeSettings(enter_frames=1), [ZONE])
    _run(e, [[_obs(tid=1, zones={1})]] * 2)
    out = _run(e, [[_obs(tid=1, zones={1}), _obs(tid=2, zones={1}, foot=(110.0, 100.0))]] * 3, start=0.2)
    assert not [c for c in out if c.action == "open" and c.track_id == 2]


def test_recently_closed_event_suppresses_reopen_by_new_track_id():
    e = RuleEngine(RuntimeSettings(enter_frames=1, lost_s=0.5, cooldown_s=10), [ZONE])
    out = _run(e, [[_obs(tid=1, zones={1})]] * 2)
    assert sum(c.action == "open" for c in out) == 1
    closed = _run(e, [[]] * 8, start=0.2)              # track 1 lost -> event closed
    assert any(c.action == "close" for c in closed)
    out = _run(e, [[_obs(tid=7, zones={1}, foot=(130.0, 100.0))]] * 3, start=1.0)
    assert not [c for c in out if c.action == "open"]  # same spot, new ID: not a new event


def test_attach_keypoints_matches_by_iou_and_uses_recent_cache():
    from yaqiz.vision.engine import attach_keypoints

    k = np.ones((17, 3))
    cache: dict = {}
    persons = attach_keypoints([(5, 0.9, (0, 0, 10, 20))], [((1, 1, 10, 20), k)], cache, 0.0)
    assert persons[0].kpts[0, 2] == 1.0
    moved = attach_keypoints([(5, 0.9, (2, 0, 12, 20))], None, cache, 0.3)
    assert moved[0].kpts[0, 0] == pytest.approx(3.0)  # shifted with the box
    stale = attach_keypoints([(5, 0.9, (2, 0, 12, 20))], None, cache, 2.0)
    assert stale[0].kpts[0, 2] == 0.0


def test_zones_are_clipped_to_calibration_coverage():
    from yaqiz.geometry import calibration_coverage, clip_to_coverage

    cov = calibration_coverage([(1040, 200), (1100, 200), (1100, 650), (1040, 650)])
    assert clip_to_coverage([(460, 200), (780, 200), (780, 350), (460, 350)], cov) is None
    clipped = clip_to_coverage([(1000, 300), (1300, 300), (1300, 400), (1000, 400)], cov)
    assert clipped and max(x for x, _ in clipped) < 1300


# ----------------------------------------------------------------------------- machine proximity
def _machine(xyxy, conf=0.8):
    from yaqiz.vision.engine import Det
    return Det("machinery", conf, xyxy)


EXCAVATOR = (400.0, 200.0, 800.0, 500.0)  # box bottom (ground contact) at y=500


def test_near_machine_uses_the_workers_height_and_the_ground_band():
    from yaqiz.vision.analysis import near_machine
    worker = lambda x, foot_y, h=170.0: ((x - 25, foot_y - h, x + 25, foot_y), (x, foot_y))  # noqa: E731
    m = [_machine(EXCAVATOR)]
    assert near_machine(*worker(820, 495), m, gap=1.0)          # beside the tracks, 20 px out
    assert near_machine(*worker(960, 495), m, gap=1.0)          # 160 px out < 1 body height (170 px)
    assert not near_machine(*worker(1000, 495), m, gap=1.0)     # 200 px out > 1 body height
    assert not near_machine(*worker(600, 640), m, gap=1.0)      # far in front of the machine (closer to camera)
    assert near_machine(*worker(1000, 495), m, gap=1.5)         # wider setting reaches 255 px
    assert not near_machine(*worker(960, 495), [], gap=1.0)     # no machine in view


def test_operator_inside_the_machine_box_is_not_near_machine():
    from yaqiz.vision.analysis import near_machine
    cab = (560.0, 260.0, 620.0, 360.0)                           # fully inside, feet 140 px above ground line
    assert not near_machine(cab, (590.0, 360.0), [_machine(EXCAVATOR)], gap=1.0)
    beside = (560.0, 330.0, 620.0, 498.0)                        # inside the box but standing on the ground
    assert near_machine(beside, (590.0, 498.0), [_machine(EXCAVATOR)], gap=1.0)


def test_machine_proximity_opens_after_enter_frames_and_closes_after_exit_frames():
    rt = RuntimeSettings(enter_frames=3, exit_frames=2, site_require_helmet=False)
    e = RuleEngine(rt, [])
    near = PersonObs(track_id=1, box=(80, 0, 120, 100), foot_img=(100.0, 100.0), foot_plan=None,
                     zone_ids=frozenset(), near_machine=True)
    away = PersonObs(track_id=1, box=(80, 0, 120, 100), foot_img=(100.0, 100.0), foot_plan=None,
                     zone_ids=frozenset(), near_machine=False)
    assert _run(e, [[near]] * 2) == []
    out = _run(e, [[near]] * 2, start=0.2)
    assert [(c.action, c.kind, c.severity) for c in out] == [("open", "machine_proximity", "warning")]
    out = _run(e, [[away]] * 2, start=0.5)
    assert [(c.action, c.detail.get("reason")) for c in out] == [("close", "moved_away")]


def test_no_machinery_class_means_no_machine_events():
    e = RuleEngine(RuntimeSettings(enter_frames=1, site_require_helmet=False), [])
    unknown = PersonObs(track_id=1, box=(80, 0, 120, 100), foot_img=(100.0, 100.0), foot_plan=None,
                        zone_ids=frozenset(), near_machine=None)
    assert _run(e, [[unknown]] * 10) == []


def test_nested_machinery_boxes_are_merged_into_the_most_confident_one():
    from yaqiz.vision.engine import Det, suppress_nested
    body = Det("machinery", 0.9, (100.0, 100.0, 500.0, 400.0))
    bucket = Det("machinery", 0.6, (120.0, 120.0, 260.0, 260.0))        # fully inside the body box
    other = Det("machinery", 0.7, (480.0, 300.0, 700.0, 450.0))         # a second machine, mostly outside
    helmet = Det("helmet", 0.8, (150.0, 150.0, 170.0, 170.0))           # other classes are untouched
    kept = suppress_nested([bucket, body, other, helmet], "machinery", 0.6)
    assert body in kept and other in kept and helmet in kept and bucket not in kept
