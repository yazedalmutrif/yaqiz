"""Danger-zone geometry: load polygons, compute foot points, test membership (Shapely).

Zone files live in configs/zones/*.yaml. Points are normalised (0..1) image
coordinates so one file works at any resolution:

    clip: pexels_11798561.mp4
    zones:
      - name: "Rebar work area"
        rule: no_entry
        points: [[0.60, 0.30], [0.99, 0.30], [0.99, 0.45], [0.60, 0.45]]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

import yaml
from shapely import prepared
from shapely.geometry import Point, Polygon


@dataclass
class Zone:
    name: str
    rule: str
    points_norm: list[tuple[float, float]]
    polygon: Polygon | None = field(default=None, repr=False)
    _prepared: object | None = field(default=None, repr=False)

    def bind(self, width: int, height: int) -> "Zone":
        """Convert normalised points to pixel coordinates for a given frame size."""
        pts = [(x * width, y * height) for x, y in self.points_norm]
        poly = Polygon(pts)
        if not poly.is_valid or poly.area <= 0:
            raise ValueError(f"Zone '{self.name}' is not a valid polygon: {self.points_norm}")
        self.polygon = poly
        self._prepared = prepared.prep(poly)
        return self

    @property
    def pixel_points(self) -> list[tuple[int, int]]:
        if self.polygon is None:
            raise RuntimeError("call bind(width, height) first")
        return [(int(round(x)), int(round(y))) for x, y in self.polygon.exterior.coords[:-1]]

    def contains_point(self, x: float, y: float) -> bool:
        """True if (x, y) is inside the zone or on its border."""
        if self._prepared is None:
            raise RuntimeError("call bind(width, height) first")
        return self._prepared.covers(Point(x, y))


def load_zones(path: str | Path) -> list[Zone]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    zones = []
    for z in data.get("zones", []):
        pts = [(float(x), float(y)) for x, y in z["points"]]
        if len(pts) < 3:
            raise ValueError(f"Zone '{z.get('name')}' needs at least 3 points")
        for x, y in pts:
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise ValueError(f"Zone '{z.get('name')}' has a point outside 0..1: {(x, y)}")
        zones.append(Zone(name=str(z["name"]), rule=str(z.get("rule", "no_entry")), points_norm=pts))
    if not zones:
        raise ValueError(f"No zones defined in {path}")
    return zones


def foot_point(box_xyxy: Sequence[float]) -> tuple[float, float]:
    """Bottom-centre of an (x1, y1, x2, y2) box: where the person stands."""
    x1, _y1, x2, y2 = box_xyxy
    return ((x1 + x2) / 2.0, float(y2))


def zones_hit(box_xyxy: Sequence[float], zones: Iterable[Zone]) -> list[Zone]:
    fx, fy = foot_point(box_xyxy)
    return [z for z in zones if z.contains_point(fx, fy)]
