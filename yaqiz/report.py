"""Daily HSE report data (the dashboard renders and prints it in Arabic)."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone

from .config import SITE_TZ
from .risk import risk_grid, to_local
from .serialize import event_dict
from .store import Store, today_local

KIND_AR = {
    "zone_intrusion": "دخول منطقة خطر",
    "ppe_missing": "نقص معدات الوقاية",
    "man_down": "سقوط عامل",
    "sos": "نداء استغاثة",
    "midday_exposure": "عمل وقت حظر الظهيرة",
    "machine_proximity": "اقتراب من معدة",
}


def _rate(yes: int, no: int) -> float | None:
    return None if yes + no == 0 else round(100.0 * yes / (yes + no), 1)


def daily_report(store: Store, day: date, heat: dict | None = None) -> dict:
    events = store.events_for_day(day)
    zones = store.list_zones()
    cams = {c.id: c.name for c in store.list_cameras()}
    stats = store.stats_for_day(day)

    by_kind = Counter(e.kind for e in events)
    by_sev = Counter(e.severity for e in events)
    by_zone = Counter(e.zone_id for e in events)
    by_hour = Counter(to_local(e.ts, SITE_TZ).hour for e in events)
    zone_names = {z.id: z.name for z in zones}

    tot = Counter()
    minutes_by_cam = Counter()
    for s in stats:
        for f in ("frames", "people", "in_zone", "helmet_yes", "helmet_no", "vest_yes", "vest_no"):
            tot[f] += getattr(s, f)
        minutes_by_cam[s.camera_id] += 1

    heat_by_hour = None
    if heat and heat.get("category") is not None and day == today_local():
        heat_by_hour = {datetime.now(timezone.utc).astimezone(SITE_TZ).hour: heat["category"]}
    risk = risk_grid(
        [{"ts": e.ts, "kind": e.kind, "severity": e.severity, "zone_id": e.zone_id} for e in events],
        [{"id": z.id, "name": z.name, "outdoor": z.outdoor} for z in zones],
        day, SITE_TZ, hours=tuple(range(24)), heat_by_hour=heat_by_hour,  # same 24 h as the totals
    )
    critical = [event_dict(e) for e in events if e.severity == "critical"]
    acked = sum(1 for e in events if e.acknowledged)
    return {
        "date": day.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "totals": {"events": len(events), "critical": by_sev.get("critical", 0), "warning": by_sev.get("warning", 0),
                   "acknowledged": acked},
        "by_kind": [{"kind": k, "label": KIND_AR.get(k, k), "count": n} for k, n in by_kind.most_common()],
        "by_zone": [{"zone_id": zid, "name": zone_names.get(zid, "خارج المناطق"), "count": n}
                    for zid, n in by_zone.most_common()],
        "by_hour": [by_hour.get(h, 0) for h in range(24)],
        "compliance": {"helmet_pct": _rate(tot["helmet_yes"], tot["helmet_no"]),
                       "vest_pct": _rate(tot["vest_yes"], tot["vest_no"]),
                       "observations": tot["helmet_yes"] + tot["helmet_no"]},
        "coverage": [{"camera_id": cid, "name": cams.get(cid, f"CAM-{cid}"), "minutes": m}
                     for cid, m in sorted(minutes_by_cam.items())],
        "critical_events": critical,
        "risk": risk,
        "heat": heat,
    }
