"""One frame: match PPE to tracked people, read each person's foot point, zones and posture.

PPE is matched to a person when its centre falls in the person's head region (helmet / head)
or torso region (vest / harness); ties go to the nearest region centre (as in Sprint 0).
A missing vest/harness is only inferred when the torso is clearly visible (shoulders and hips
detected) and the person is large enough; a missing helmet comes from an explicit "head" box.
Machine proximity is judged in the image, scaled by the worker's own height (see near_machine).
"""
from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np

from ..config import RuntimeSettings
from ..geometry import foot_point, point_in_polygon, project
from ..posture import pose_features
from ..rules import PersonObs
from .engine import Det, PersonDet

ON_MACHINE_OVERLAP = 0.85   # share of a person's box inside a machine's box ...
OPERATOR_FEET_FRAC = 0.35   # ... with the feet above this share of the machine's height -> the operator
MAX_SCALE_RATIO = 6.0       # a person this many times smaller than the machine is far behind it
HEAD_REGION = (0.0, 0.35)
TORSO_REGION = (0.15, 0.75)
X_MARGIN = 0.15


def _region(box: Sequence[float], frac: tuple[float, float]) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    return (x1 - X_MARGIN * w, y1 + frac[0] * h, x2 + X_MARGIN * w, y1 + frac[1] * h)


def associate(persons: Sequence[PersonDet], dets: Sequence[Det]) -> list[dict[str, float]]:
    """Best confidence per gear class for each person (same order as persons)."""
    out: list[dict[str, float]] = [{} for _ in persons]
    for d in dets:
        if d.cls in ("helmet", "head"):
            frac = HEAD_REGION
        elif d.cls in ("vest", "harness"):
            frac = TORSO_REGION
        else:
            continue
        cx, cy = d.center
        best, best_d = None, float("inf")
        for i, p in enumerate(persons):
            r = _region(p.xyxy, frac)
            if r[0] <= cx <= r[2] and r[1] <= cy <= r[3]:
                rc = ((r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0)
                dist = (cx - rc[0]) ** 2 + (cy - rc[1]) ** 2
                if dist < best_d:
                    best, best_d = i, dist
        if best is not None:
            out[best][d.cls] = max(out[best].get(d.cls, 0.0), d.conf)
    return out


def near_machine(box: Sequence[float], foot: tuple[float, float], machines: Sequence[Det], gap: float,
                 lying: bool = False) -> bool:
    """Is the worker within about `gap` body lengths of a machine, on the ground?

    Image-space approximation, scaled by the worker's size in the frame (one body length is about 1.7 m;
    for a worker lying down it is the box width). A machine's ground footprint is taken as the band from
    its box bottom (nearest ground contact) up to 60% of its box height (its far side), capped at
    3 x `gap` body lengths. The worker is near when their foot point is in that band, widened by `gap`
    body lengths sideways and 0.3 x `gap` in depth (ground depth is foreshortened in the image).

    Not counted:
    - the operator: mostly inside the machine's box, feet above 35% of its height, and at most half its
      height. A worker standing right behind or beside the machine has feet near its ground line and still counts.
    - a person more than 6 times smaller than the machine: someone far behind it, seen past its outline.
    """
    x1, y1, x2, y2 = box
    bw, bh = max(x2 - x1, 0.0), max(y2 - y1, 0.0)
    ph = max(max(bw, bh) if lying else bh, 1.0)
    area = max(bw * bh, 1.0)
    fx, fy = foot
    for m in machines:
        mx1, my1, mx2, my2 = m.xyxy
        mh = max(my2 - my1, 1.0)
        if ph * MAX_SCALE_RATIO < mh:
            continue
        ix = max(0.0, min(x2, mx2) - max(x1, mx1))
        iy = max(0.0, min(y2, my2) - max(y1, my1))
        if ix * iy >= ON_MACHINE_OVERLAP * area and fy < my2 - OPERATOR_FEET_FRAC * mh and ph <= 0.5 * mh:
            continue
        dx, dy = gap * ph, 0.3 * gap * ph
        band = min(0.6 * mh, 3.0 * gap * ph)
        if mx1 - dx <= fx <= mx2 + dx and my2 - band - dy <= fy <= my2 + dy:
            return True
    return False


def torso_visible(kpts: np.ndarray, kp_conf: float) -> bool:
    return bool(kpts is not None and kpts.shape[0] >= 13 and all(kpts[i, 2] >= kp_conf for i in (5, 6, 11, 12)))


def analyse_frame(persons: Sequence[PersonDet], dets: Sequence[Det], zones_img: Mapping[int, np.ndarray],
                  H_inv: np.ndarray | None, rt: RuntimeSettings, capabilities: frozenset[str]) -> list[PersonObs]:
    gear = associate(persons, dets)
    machines = [d for d in dets if d.cls == "machinery"] if "machinery" in capabilities else None
    obs: list[PersonObs] = []
    for p, g in zip(persons, gear):
        x1, y1, x2, y2 = p.xyxy
        big = (y2 - y1) >= rt.min_person_px
        h_yes, h_no = g.get("helmet", 0.0), g.get("head", 0.0)
        helmet = "yes" if h_yes and h_yes >= h_no else ("no" if h_no > h_yes else None)
        visible = big and torso_visible(p.kpts, rt.kp_conf)
        vest = "yes" if g.get("vest") else ("no" if visible else None)
        harness = None
        if "harness" in capabilities:
            harness = "yes" if g.get("harness") else ("no" if visible else None)
        foot = foot_point(p.xyxy, p.kpts, rt.kp_conf)
        zone_ids = frozenset(zid for zid, poly in zones_img.items() if point_in_polygon(foot, poly))
        plan = None
        if H_inv is not None:
            q = project(H_inv, [foot])[0]
            if np.all(np.isfinite(q)):
                plan = (float(q[0]), float(q[1]))
        pose = pose_features(p.kpts, p.xyxy, rt.kp_conf)
        near = None if machines is None else near_machine(p.xyxy, foot, machines, rt.machine_gap, bool(pose.lying))
        obs.append(PersonObs(p.track_id, p.xyxy, foot, plan, zone_ids, helmet, vest, harness, pose, near))
    return obs
