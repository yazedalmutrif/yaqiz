"""Event log, risk index and the daily report."""
from __future__ import annotations

from datetime import date as Date
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ..config import SITE_TZ
from ..report import daily_report
from ..risk import risk_grid
from ..serialize import event_dict
from ..store import today_local
from .deps import CtxDep

router = APIRouter(tags=["events"])
KINDS = {"zone_intrusion", "ppe_missing", "man_down", "sos", "midday_exposure", "machine_proximity"}


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:  # treat naive query times as site-local
        dt = dt.replace(tzinfo=SITE_TZ)
    return dt.astimezone(timezone.utc)


@router.get("/events")
def list_events(ctx: CtxDep, since: datetime | None = None, until: datetime | None = None,
                kind: str | None = None, zone_id: int | None = None, camera_id: int | None = None,
                unacked: bool = False, limit: int = Query(50, ge=1, le=500),
                offset: int = Query(0, ge=0)) -> dict:
    if kind and kind not in KINDS:
        raise HTTPException(422, "نوع حدث غير معروف")
    rows, total = ctx.store.list_events(_utc(since), _utc(until), kind, zone_id, camera_id,
                                        unacked, limit, offset)
    return {"total": total, "items": [event_dict(e) for e in rows]}


@router.post("/events/{event_id}/ack")
def ack_event(event_id: int, ctx: CtxDep) -> dict:
    ev = ctx.store.ack_event(event_id)
    if ev is None:
        raise HTTPException(404, "الحدث غير موجود")
    data = event_dict(ev)
    ctx.bus.publish({"type": "event", "action": "update", "event": data})
    return data


@router.get("/events/{event_id}/snapshot.jpg")
def event_snapshot(event_id: int, ctx: CtxDep) -> FileResponse:
    ev = ctx.store.get_event(event_id)
    if ev is None or not ev.snapshot:
        raise HTTPException(404, "لا توجد لقطة لهذا الحدث")
    root = ctx.settings.snapshots_dir.resolve()
    path = (root / ev.snapshot).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(404, "لا توجد لقطة لهذا الحدث")
    return FileResponse(path, media_type="image/jpeg")


@router.get("/risk")
def risk(ctx: CtxDep, date: Date | None = None, shift: Literal["day", "full"] = "day") -> dict:
    """shift=day: 06:00–18:00 hourly grid; shift=full: all 24 hours (night work)."""
    day = date or today_local()
    hours = tuple(range(6, 18)) if shift == "day" else tuple(range(24))  # 06:00–17:59
    events = ctx.store.events_for_day(day)
    heat_by_hour = None
    if day == today_local():
        heat = ctx.heat_now()
        if heat.get("category") is not None:
            heat_by_hour = {datetime.now(timezone.utc).astimezone(SITE_TZ).hour: heat["category"]}
    return risk_grid(
        [{"ts": e.ts, "kind": e.kind, "severity": e.severity, "zone_id": e.zone_id} for e in events],
        [{"id": z.id, "name": z.name, "outdoor": z.outdoor} for z in ctx.store.list_zones()],
        day, SITE_TZ, hours=hours, heat_by_hour=heat_by_hour,
    )


@router.get("/report")
def report(ctx: CtxDep, date: Date | None = None) -> dict:
    day = date or today_local()
    return daily_report(ctx.store, day, ctx.heat_now() if day == today_local() else None)
