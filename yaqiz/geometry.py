"""Plan ↔ camera geometry: homographies, polygon tests and foot points.

Zones are drawn once on the site plan. A camera is calibrated with >= 4 point pairs
(plan point ↔ the same ground point in the camera image); the fitted homography H maps
plan → image, and its inverse maps a worker's foot point back onto the plan. This is
valid for points on the ground plane, which is exactly where feet are.
"""
from __future__ import annotations

from typing import Sequence

import cv2
import numpy as np
from shapely.geometry import MultiPoint, Point as ShapelyPoint, Polygon

Point = tuple[float, float]


def _as_points(pts: Sequence[Sequence[float]]) -> np.ndarray:
    arr = np.asarray(pts, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != 2:
        raise ValueError("expected a list of [x, y] points")
    return arr


def _degenerate(pts: np.ndarray) -> bool:
    """True if the points span (almost) no area, e.g. all on one line."""
    hull = cv2.convexHull(pts.astype(np.float32))
    span = np.ptp(pts, axis=0)
    box = max(float(span[0] * span[1]), 1.0)
    return cv2.contourArea(hull) < 1e-3 * box or max(span) < 1e-6


def fit_homography(plan_pts: Sequence[Sequence[float]], image_pts: Sequence[Sequence[float]]) -> tuple[np.ndarray, float]:
    """Fit H (plan → image). Returns (H normalised so H[2,2] == 1, mean reprojection error in image px)."""
    src, dst = _as_points(plan_pts), _as_points(image_pts)
    if src.shape != dst.shape:
        raise ValueError("plan and image point lists must have the same length")
    if len(src) < 4:
        raise ValueError("at least 4 point pairs are needed")
    if _degenerate(src) or _degenerate(dst):
        raise ValueError("the points are (nearly) on one line; spread them over the ground")
    method = cv2.RANSAC if len(src) > 4 else 0
    H, _mask = cv2.findHomography(src, dst, method, 4.0)
    if H is None or not np.all(np.isfinite(H)) or abs(H[2, 2]) < 1e-12 or abs(np.linalg.det(H)) < 1e-12:
        raise ValueError("could not fit a homography from these points")
    H = H / H[2, 2]
    err = float(np.mean(np.linalg.norm(project(H, src) - dst, axis=1)))
    return H, err


def _apply(H: np.ndarray, pts: Sequence[Sequence[float]]) -> tuple[np.ndarray, np.ndarray]:
    p = _as_points(pts)
    hom = np.hstack([p, np.ones((len(p), 1))])
    q = hom @ np.asarray(H, dtype=np.float64).T
    return q[:, :2], q[:, 2]


def project(H: np.ndarray, pts: Sequence[Sequence[float]]) -> np.ndarray:
    """Map points through H. Points that land on the horizon (w ≈ 0) come back as inf."""
    xy, w = _apply(H, pts)
    with np.errstate(divide="ignore", invalid="ignore"):
        return xy / w[:, None]


def project_visible(H: np.ndarray, pts: Sequence[Sequence[float]]) -> np.ndarray | None:
    """Like project(), but None if any point maps behind the camera (w <= 0), e.g. a zone out of view."""
    xy, w = _apply(H, pts)
    if np.any(w <= 1e-9):
        return None
    return xy / w[:, None]


def invert(H: np.ndarray) -> np.ndarray:
    Hi = np.linalg.inv(np.asarray(H, dtype=np.float64))
    return Hi / Hi[2, 2]


def calibration_coverage(plan_points: Sequence[Sequence[float]], margin_frac: float = 0.12) -> Polygon | None:
    """The plan area a calibration can be trusted for: hull of the calibration points plus a margin.

    A homography fitted on a few points extrapolates badly far from them, so zones and positions
    outside this area are ignored for that camera.
    """
    if not plan_points or len(plan_points) < 3:
        return None
    hull = MultiPoint([tuple(map(float, p)) for p in plan_points]).convex_hull
    if hull.geom_type != "Polygon":
        return None
    minx, miny, maxx, maxy = hull.bounds
    return hull.buffer(margin_frac * max(maxx - minx, maxy - miny), join_style=2)


def clip_to_coverage(points: Sequence[Sequence[float]], coverage: Polygon | None) -> list[Point] | None:
    """Zone polygon ∩ coverage (largest piece), or None if they do not overlap."""
    poly = Polygon([tuple(map(float, p)) for p in points])
    if not poly.is_valid:
        poly = poly.buffer(0)
    if coverage is not None:
        poly = poly.intersection(coverage)
    parts = [g for g in getattr(poly, "geoms", [poly]) if g.geom_type == "Polygon" and g.area >= 1.0]
    if not parts:
        return None
    best = max(parts, key=lambda g: g.area)
    return [(float(x), float(y)) for x, y in list(best.exterior.coords)[:-1]]


def covers(coverage: Polygon | None, pt: Point) -> bool:
    return coverage is None or coverage.covers(ShapelyPoint(float(pt[0]), float(pt[1])))


def polygon_area(points: Sequence[Sequence[float]]) -> float:
    p = _as_points(points)
    x, y = p[:, 0], p[:, 1]
    return float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2.0)


def validate_polygon(points: Sequence[Sequence[float]]) -> list[Point]:
    """Return the polygon as a list of (x, y) or raise ValueError if it is unusable."""
    p = _as_points(points)
    if len(p) < 3:
        raise ValueError("a zone needs at least 3 points")
    if not np.all(np.isfinite(p)):
        raise ValueError("zone points must be finite numbers")
    if polygon_area(p) < 1.0:
        raise ValueError("the zone has no area")
    return [(float(x), float(y)) for x, y in p]


def point_in_polygon(pt: Point, polygon: Sequence[Sequence[float]] | np.ndarray) -> bool:
    """True if pt is inside the polygon or on its border."""
    poly = np.asarray(polygon, dtype=np.float32).reshape(-1, 1, 2)
    return cv2.pointPolygonTest(poly, (float(pt[0]), float(pt[1])), False) >= 0


def foot_point(box: Sequence[float], kpts: np.ndarray | None = None, kp_conf: float = 0.4) -> Point:
    """Where a person stands in the image: x from the ankles when visible, y = bottom of the box."""
    x1, _y1, x2, y2 = (float(v) for v in box)
    x = (x1 + x2) / 2.0
    if kpts is not None:
        k = np.asarray(kpts, dtype=np.float64)
        if k.ndim == 2 and k.shape[0] >= 17 and k.shape[1] >= 3:
            ankles = [k[i] for i in (15, 16) if k[i, 2] >= kp_conf]
            if ankles:
                x = float(np.mean([a[0] for a in ankles]))
    return (x, y2)
