"""Body-posture rules on COCO-17 keypoints (from YOLO11-pose).

* SOS: both wrists raised above the shoulders and **crossed** (the wrists' left/right order is
  the opposite of the shoulders' order), held for `sos_hold_s`. Works for front and back views.
* Man down: lying (torso within 30° of horizontal, or a box much wider than tall when the
  keypoints are not visible) **and** still, held for `man_down_s`.

These are geometric rules plus time persistence, so they need no training data; they are
evaluated on public fall clips and on staged clips.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

import numpy as np

L_SH, R_SH, L_WR, R_WR, L_HIP, R_HIP = 5, 6, 9, 10, 11, 12
STILL_TOL = 0.18  # "still": the box centre stays within STILL_TOL x scale over 2 s; chosen on GMDCSA-24 subjects 1-2 (docs/DATA.md section 8)


@dataclass(frozen=True)
class PoseFeatures:
    sos: bool | None        # None = cannot judge (side view or wrists not visible)
    lying: bool | None
    anchor: tuple[float, float]   # box centre (the point tracked for stillness)
    scale: float            # 0.35 x the box's longer side (~ torso length, standing or lying), the yardstick for "still"


def pose_features(kpts: np.ndarray | None, box, kp_conf: float = 0.4) -> PoseFeatures:
    x1, y1, x2, y2 = (float(v) for v in box)
    bw, bh = max(x2 - x1, 0.0), max(y2 - y1, 0.0)
    k = None if kpts is None else np.asarray(kpts, dtype=np.float64)

    def ok(i: int) -> bool:
        return k is not None and k.ndim == 2 and k.shape[0] > i and k.shape[1] >= 3 and k[i, 2] >= kp_conf

    torso: float | None = None
    if ok(L_SH) and ok(R_SH) and ok(L_HIP) and ok(R_HIP):
        sx, sy = (k[L_SH, 0] + k[R_SH, 0]) / 2, (k[L_SH, 1] + k[R_SH, 1]) / 2
        hx, hy = (k[L_HIP, 0] + k[R_HIP, 0]) / 2, (k[L_HIP, 1] + k[R_HIP, 1]) / 2
        torso = math.hypot(hx - sx, hy - sy)
        tilt = math.degrees(math.atan2(abs(hx - sx), abs(hy - sy) + 1e-6))  # 0° upright, 90° flat
        lying: bool | None = tilt > 60.0 and torso > 1.0
    else:
        lying = (bw > 1.25 * bh) if bw > 0 and bh > 0 else None

    sos: bool | None = None
    if ok(L_SH) and ok(R_SH) and ok(L_WR) and ok(R_WR):
        ref = torso if torso else 0.3 * bh
        shoulder_w = abs(k[L_SH, 0] - k[R_SH, 0])
        if ref > 0 and shoulder_w >= 0.25 * ref:  # frontal or back view; side views are ambiguous
            top = min(k[L_SH, 1], k[R_SH, 1]) - 0.05 * ref
            raised = k[L_WR, 1] < top and k[R_WR, 1] < top
            crossed = (k[L_WR, 0] - k[R_WR, 0]) * (k[L_SH, 0] - k[R_SH, 0]) < 0
            sos = bool(raised and crossed and not lying)

    # Stillness is judged on the same point in every frame (the box centre) against a body-size yardstick
    # that does not shrink when the person lies down. Switching between a keypoint anchor and a box anchor,
    # and a 0.35 x box-height yardstick, made a motionless worker on the ground look like he was moving.
    anchor = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
    scale = 0.35 * max(bw, bh, 1.0)
    return PoseFeatures(sos=sos, lying=lying, anchor=anchor, scale=scale)


class HoldTimer:
    """Becomes True once a condition has held for `hold_s`; gaps shorter than `grace_s` are bridged."""

    def __init__(self, hold_s: float, grace_s: float = 0.5) -> None:
        self.hold_s, self.grace_s = hold_s, grace_s
        self.since: float | None = None
        self.last_true: float | None = None

    def update(self, cond: bool | None, t: float) -> bool:
        if cond:
            if self.since is None:
                self.since = t
            self.last_true = t
        elif self.last_true is None or t - self.last_true > self.grace_s:
            self.since = self.last_true = None
        return self.active(t)

    def active(self, t: float) -> bool:
        return self.since is not None and t - self.since >= self.hold_s

    def held_for(self, t: float) -> float:
        return 0.0 if self.since is None else t - self.since


class StillnessMeter:
    """Is the anchor point (hips/torso centre) still over the last `window_s` seconds?"""

    def __init__(self, window_s: float = 2.0, tolerance: float = 0.25) -> None:
        self.window_s, self.tolerance = window_s, tolerance
        self.hist: deque[tuple[float, float, float]] = deque()

    def update(self, anchor: tuple[float, float], scale: float, t: float) -> bool | None:
        self.hist.append((t, anchor[0], anchor[1]))
        while self.hist and t - self.hist[0][0] > self.window_s:
            self.hist.popleft()
        if t - self.hist[0][0] < 0.6 * self.window_s:
            return None  # not enough history yet
        xs = np.array([h[1] for h in self.hist])
        ys = np.array([h[2] for h in self.hist])
        spread = float(np.max(np.hypot(xs - xs.mean(), ys - ys.mean())))
        return spread < self.tolerance * max(scale, 1.0)


class ManDownDetector:
    def __init__(self, man_down_s: float, still_tol: float = STILL_TOL) -> None:
        self.timer = HoldTimer(man_down_s, grace_s=0.8)
        self.still = StillnessMeter(tolerance=still_tol)

    def update(self, f: PoseFeatures, t: float) -> bool:
        still = self.still.update(f.anchor, f.scale, t)
        return self.timer.update(bool(f.lying) and still is not False, t)


class SosDetector:
    def __init__(self, hold_s: float) -> None:
        self.timer = HoldTimer(hold_s, grace_s=0.4)

    def update(self, f: PoseFeatures, t: float) -> bool:
        return self.timer.update(f.sos, t)
