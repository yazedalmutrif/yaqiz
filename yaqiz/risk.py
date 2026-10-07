"""Risk index per zone per hour, built from the event log.

Score = sum of event weights (critical events add a bonus); outdoor zones are amplified by
the hour's heat category. Levels: 1 low (<3), 2 medium (3–7.9), 3 high (8–14.9), 4 critical (>=15).
The weights are a transparent starting point for the pilot and can be tuned with site data.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone, tzinfo
from typing import Iterable, Mapping, Sequence

WEIGHTS: dict[str, float] = {
    "zone_intrusion": 3.0,
    "ppe_missing": 2.0,
    "man_down": 10.0,
    "sos": 10.0,
    "midday_exposure": 3.0,
    "machine_proximity": 4.0,
}
CRITICAL_BONUS = 2.0
LEVEL_THRESHOLDS: tuple[tuple[float, int], ...] = ((15.0, 4), (8.0, 3), (3.0, 2))
UNZONED = "خارج المناطق"


def level_of(score: float) -> int:
    for threshold, level in LEVEL_THRESHOLDS:
        if score >= threshold:
            return level
    return 1


def event_weight(kind: str, severity: str) -> float:
    return WEIGHTS.get(kind, 1.0) + (CRITICAL_BONUS if severity == "critical" else 0.0)


def to_local(ts: datetime, tz: tzinfo) -> datetime:
    """Event timestamps are UTC (a naive value is read as UTC)."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(tz)


def risk_grid(
    events: Iterable[Mapping],
    zones: Sequence[Mapping],
    day: date,
    tz: tzinfo,
    hours: Sequence[int] = tuple(range(6, 18)),
    heat_by_hour: Mapping[int, int] | None = None,
) -> dict:
    """events: mappings with ts, kind, severity, zone_id. zones: mappings with id, name, outdoor."""
    hour_index = {h: i for i, h in enumerate(hours)}
    meta = {z["id"]: z for z in zones}
    scores: dict[int | None, list[float]] = defaultdict(lambda: [0.0] * len(hours))
    for z in zones:
        scores[z["id"]]  # every zone gets a row, even with no events
    for e in events:
        local = to_local(e["ts"], tz)
        if local.date() != day or local.hour not in hour_index:
            continue
        zid = e.get("zone_id")
        w = event_weight(e["kind"], e.get("severity", "warning"))
        if zid in meta and meta[zid].get("outdoor") and heat_by_hour:
            w *= 1.0 + 0.25 * heat_by_hour.get(local.hour, 0)
        scores[zid if zid in meta else None][hour_index[local.hour]] += w

    rows = []
    for zid, vals in scores.items():
        rows.append({
            "zone_id": zid,
            "name": meta[zid]["name"] if zid in meta else UNZONED,
            "scores": [round(v, 1) for v in vals],
            "levels": [level_of(v) for v in vals],
            "total": round(sum(vals), 1),
        })
    rows.sort(key=lambda r: (-r["total"], r["name"]))
    top = rows[0] if rows and rows[0]["total"] > 0 else None
    return {"date": day.isoformat(), "hours": list(hours), "zones": rows,
            "top": {"zone_id": top["zone_id"], "name": top["name"], "total": top["total"]} if top else None,
            "weights": WEIGHTS, "critical_bonus": CRITICAL_BONUS}
