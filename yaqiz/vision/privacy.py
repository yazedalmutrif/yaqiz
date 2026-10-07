"""Privacy: pixelate faces using the pose keypoints (nose, eyes, ears), or the top of the box as a fallback.

Stored snapshots are always pixelated; live streams follow the `blur_stream` setting.
"""
from __future__ import annotations

from typing import Sequence

import cv2
import numpy as np

from .engine import PersonDet


def face_rect(p: PersonDet, kp_conf: float) -> tuple[int, int, int, int] | None:
    x1, y1, x2, y2 = p.xyxy
    bw, bh = x2 - x1, y2 - y1
    if bh < 12 or bw < 6:
        return None
    k = p.kpts
    pts = [k[i, :2] for i in range(5) if k.shape[0] > i and k[i, 2] >= kp_conf]
    if pts:
        arr = np.asarray(pts)
        cx, cy = arr.mean(axis=0)
        span = float(max(np.ptp(arr[:, 0]), np.ptp(arr[:, 1]), 0.0))
        size = max(span * 2.4, 0.16 * bh, 0.5 * bw, 12.0)
        return (int(cx - size / 2), int(cy - size * 0.6), int(cx + size / 2), int(cy + size * 0.5))
    return (int(x1 + 0.15 * bw), int(y1), int(x2 - 0.15 * bw), int(y1 + 0.2 * bh))


def pixelate(frame: np.ndarray, rect: tuple[int, int, int, int], block: int = 9) -> None:
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = max(0, rect[0]), max(0, rect[1]), min(w, rect[2]), min(h, rect[3])
    if x2 - x1 < 2 or y2 - y1 < 2:
        return
    roi = frame[y1:y2, x1:x2]
    small = cv2.resize(roi, (max(1, (x2 - x1) // block), max(1, (y2 - y1) // block)), interpolation=cv2.INTER_LINEAR)
    frame[y1:y2, x1:x2] = cv2.resize(small, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)


def blur_faces(frame: np.ndarray, persons: Sequence[PersonDet], kp_conf: float) -> np.ndarray:
    for p in persons:
        r = face_rect(p, kp_conf)
        if r:
            pixelate(frame, r)
    return frame
