"""Stream annotations (OpenCV cannot shape Arabic, so on-frame text is short Latin; the dashboard is Arabic)."""
from __future__ import annotations

from typing import Mapping, Sequence

import cv2
import numpy as np

from ..rules import PersonObs, ZoneRule
from .engine import Det, PersonDet

# BGR
COL_OK = (96, 200, 72)
COL_WARN = (20, 170, 255)
COL_CRIT = (50, 50, 230)
COL_ZONE = (60, 60, 220)
COL_ZONE_OFF = (150, 150, 150)
COL_PPE_ZONE = (40, 200, 240)
COL_BONE = (230, 245, 74)
COL_MACH = (0, 140, 255)
SKELETON = ((5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16))
FONT = cv2.FONT_HERSHEY_SIMPLEX


def _label(img: np.ndarray, text: str, org: tuple[int, int], color: tuple[int, int, int], scale: float) -> None:
    (tw, th), base = cv2.getTextSize(text, FONT, scale, 1)
    x, y = org
    y = max(th + 4, y)
    cv2.rectangle(img, (x, y - th - 4), (x + tw + 6, y + base - 2), color, -1)
    cv2.putText(img, text, (x + 3, y - 3), FONT, scale, (255, 255, 255), 1, cv2.LINE_AA)


def draw_overlay(img: np.ndarray, *, camera_id: int, zones_img: Mapping[int, np.ndarray],
                 zones: Mapping[int, ZoneRule], persons: Sequence[PersonDet], obs: Sequence[PersonObs],
                 status: Mapping[int, str], fps: float, kp_conf: float,
                 machines: Sequence[Det] = ()) -> np.ndarray:
    h, w = img.shape[:2]
    scale = max(0.4, min(0.8, w / 1600))
    thick = max(1, int(round(w / 640)))

    if zones_img:
        layer = img.copy()
        for zid, poly in zones_img.items():
            z = zones.get(zid)
            if z is None:
                continue
            col = COL_PPE_ZONE if z.kind == "ppe" else (COL_ZONE if z.active else COL_ZONE_OFF)
            cv2.fillPoly(layer, [poly.astype(np.int32)], col)
        cv2.addWeighted(layer, 0.22, img, 0.78, 0, dst=img)
        for zid, poly in zones_img.items():
            z = zones.get(zid)
            if z is None:
                continue
            col = COL_PPE_ZONE if z.kind == "ppe" else (COL_ZONE if z.active else COL_ZONE_OFF)
            pts = poly.astype(np.int32)
            cv2.polylines(img, [pts], True, col, thick + 1, cv2.LINE_AA)
            top = pts[np.argmin(pts[:, 1])]
            _label(img, f"Z{zid}" + ("" if z.active or z.kind == "ppe" else " off"), (int(top[0]), int(top[1]) - 4), col, scale)

    for m in machines:
        mx1, my1, mx2, my2 = (int(v) for v in m.xyxy)
        cv2.rectangle(img, (mx1, my1), (mx2, my2), COL_MACH, thick + 1)
        _label(img, f"machine {m.conf:.2f}", (mx1, my2 + int(18 * scale / 0.6)), COL_MACH, scale * 0.8)

    by_id = {o.track_id: o for o in obs}
    for p in persons:
        k = p.kpts
        for a, b in SKELETON:
            if k[a, 2] >= kp_conf and k[b, 2] >= kp_conf:
                cv2.line(img, (int(k[a, 0]), int(k[a, 1])), (int(k[b, 0]), int(k[b, 1])), COL_BONE, 1, cv2.LINE_AA)
        st = status.get(p.track_id, "ok")
        col = COL_CRIT if st == "critical" else (COL_WARN if st == "warn" else COL_OK)
        x1, y1, x2, y2 = (int(v) for v in p.xyxy)
        cv2.rectangle(img, (x1, y1), (x2, y2), col, thick + (1 if st != "ok" else 0))
        o = by_id.get(p.track_id)
        tags = [f"#{p.track_id}"]
        if o is not None:
            if o.helmet == "yes":
                tags.append("helmet")
            elif o.helmet == "no":
                tags.append("NO helmet")
            if o.vest == "yes":
                tags.append("vest")
            if o.near_machine:
                tags.append("NEAR MACHINE")
            fx, fy = (int(v) for v in o.foot_img)
            cv2.circle(img, (fx, fy), max(3, thick + 2), col, -1, cv2.LINE_AA)
        _label(img, " ".join(tags), (x1, y1 - 3), col, scale * 0.85)

    bar_h = int(26 * scale / 0.6)
    cv2.rectangle(img, (0, 0), (w, bar_h), (34, 38, 42), -1)
    in_zone = sum(1 for o in obs if o.zone_ids)
    text = f"YAQIZ  CAM-{camera_id:02d}   people {len(persons)}   in zone {in_zone}   {fps:4.1f} FPS"
    cv2.putText(img, text, (10, bar_h - 8), FONT, scale, (237, 239, 234), 1, cv2.LINE_AA)
    return img
