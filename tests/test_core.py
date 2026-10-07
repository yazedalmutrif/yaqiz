"""Unit tests for zone geometry, PPE association and per-track rules (no GPU needed)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import ZONES_DIR  # noqa: E402
from core.ppe import Det, associate  # noqa: E402
from core.rules import TrackState  # noqa: E402
from core.zones import Zone, foot_point, load_zones, zones_hit  # noqa: E402


def square_zone() -> Zone:
    # 100x100 frame -> pixel square (10,10)-(50,50)
    return Zone("sq", "no_entry", [(0.1, 0.1), (0.5, 0.1), (0.5, 0.5), (0.1, 0.5)]).bind(100, 100)


def test_foot_point_is_bottom_centre():
    assert foot_point((10, 20, 30, 80)) == (20.0, 80.0)


def test_zone_inside_outside_and_border():
    z = square_zone()
    assert z.contains_point(30, 30)
    assert not z.contains_point(70, 30)
    assert z.contains_point(50, 30)  # border counts as inside (covers)


def test_zones_hit_uses_foot_point_not_box_centre():
    z = square_zone()
    # Box centre (30, 30) is inside, but the feet (30, 60) are below the zone.
    assert zones_hit((20, 0, 40, 60), [z]) == []
    # Feet at (30, 45) are inside.
    assert zones_hit((20, 0, 40, 45), [z]) == [z]


def test_zone_rejects_degenerate_polygon():
    with pytest.raises(ValueError):
        Zone("line", "no_entry", [(0.1, 0.1), (0.2, 0.2), (0.3, 0.3)]).bind(100, 100)


def test_zone_configs_load_and_bind():
    files = sorted(ZONES_DIR.glob("*.yaml"))
    assert files, "expected at least one zone config"
    for f in files:
        for z in load_zones(f):
            z.bind(1920, 1080)
            assert z.polygon.area > 0


def test_associate_helmet_to_correct_person():
    persons = [(0, 0, 100, 300), (200, 0, 300, 300)]
    dets = [
        Det("helmet", 0.9, (30, 0, 70, 40)),        # head of person 0
        Det("no_helmet", 0.8, (230, 10, 270, 50)),  # head of person 1
        Det("vest", 0.7, (210, 80, 290, 180)),      # torso of person 1
        Det("vest", 0.6, (20, 260, 80, 300)),       # near feet of person 0 -> ignored
        Det("gloves", 0.9, (0, 150, 20, 170)),      # class not used
    ]
    out = associate(persons, dets)
    assert out[0].helmet_state == "helmet" and out[0].vest == 0.0
    assert out[1].helmet_state == "no_helmet" and out[1].vest == pytest.approx(0.7)


def test_associate_no_detections_gives_unknown():
    out = associate([(0, 0, 100, 300)], [])
    assert out[0].helmet_state is None


def test_track_helmet_majority_vote():
    t = TrackState(track_id=1, min_votes=3)
    for s in ["helmet", "no_helmet", None, "no_helmet"]:
        t.update_helmet(s)
    assert t.helmet == "unknown"  # only 2 no_helmet votes
    t.update_helmet("no_helmet")
    assert t.helmet == "no_helmet"


def test_track_zone_debounce():
    t = TrackState(track_id=1, enter_frames=3, exit_frames=2)
    assert [t.update_zone("Z") for _ in range(3)] == [False, False, True]
    assert t.in_zone and t.zone_name == "Z"
    t.update_zone(None)
    assert t.in_zone  # one frame outside is not enough
    t.update_zone(None)
    assert not t.in_zone
