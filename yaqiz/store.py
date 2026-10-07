"""Data access: one short-lived session per call, safe to use from camera threads and API workers."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import event as sa_event
from sqlalchemy import func
from sqlmodel import Session, SQLModel, create_engine, select

from .config import SITE_TZ, RuntimeSettings
from .models import Camera, Event, SettingRow, Site, StatMinute, Zone, utcnow
from .rules import ZoneRule

RUNTIME_KEY = "runtime"


class Store:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False})

        @sa_event.listens_for(self.engine, "connect")
        def _pragmas(dbapi_conn, _record):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.close()

        SQLModel.metadata.create_all(self.engine)

    def session(self) -> Session:
        return Session(self.engine, expire_on_commit=False)

    # ------------------------------------------------------------------ site
    def get_site(self) -> Site:
        with self.session() as s:
            site = s.exec(select(Site).order_by(Site.id)).first()
            if site is None:
                site = Site()
                s.add(site)
                s.commit()
                s.refresh(site)
            return site

    def update_site(self, **fields: Any) -> Site:
        with self.session() as s:
            site = s.exec(select(Site).order_by(Site.id)).first() or Site()
            for k, v in fields.items():
                if v is not None:
                    setattr(site, k, v)
            site.updated_at = utcnow()
            s.add(site)
            s.commit()
            s.refresh(site)
            return site

    # ------------------------------------------------------------------ runtime settings
    def get_runtime(self) -> RuntimeSettings:
        with self.session() as s:
            row = s.get(SettingRow, RUNTIME_KEY)
            return RuntimeSettings(**(row.value if row else {}))

    def put_runtime(self, rt: RuntimeSettings) -> RuntimeSettings:
        with self.session() as s:
            row = s.get(SettingRow, RUNTIME_KEY) or SettingRow(key=RUNTIME_KEY)
            row.value = rt.model_dump(mode="json")
            s.add(row)
            s.commit()
        return rt

    # ------------------------------------------------------------------ zones
    def list_zones(self) -> list[Zone]:
        with self.session() as s:
            return list(s.exec(select(Zone).order_by(Zone.id)))

    def zone_rules(self) -> list[ZoneRule]:
        return [ZoneRule(id=z.id, name=z.name, kind=z.kind, active=z.active, outdoor=z.outdoor,
                         require_helmet=z.require_helmet, require_vest=z.require_vest,
                         require_harness=z.require_harness, interlock=z.interlock) for z in self.list_zones()]

    def save_zone(self, zone: Zone) -> Zone:
        with self.session() as s:
            s.add(zone)
            s.commit()
            s.refresh(zone)
            return zone

    def get_zone(self, zone_id: int) -> Zone | None:
        with self.session() as s:
            return s.get(Zone, zone_id)

    def update_zone(self, zone_id: int, **fields: Any) -> Zone | None:
        with self.session() as s:
            z = s.get(Zone, zone_id)
            if z is None:
                return None
            for k, v in fields.items():
                setattr(z, k, v)
            s.add(z)
            s.commit()
            s.refresh(z)
            return z

    def delete_zone(self, zone_id: int) -> bool:
        with self.session() as s:
            z = s.get(Zone, zone_id)
            if z is None:
                return False
            s.delete(z)
            s.commit()
            return True

    # ------------------------------------------------------------------ cameras
    def list_cameras(self) -> list[Camera]:
        with self.session() as s:
            return list(s.exec(select(Camera).order_by(Camera.id)))

    def get_camera(self, camera_id: int) -> Camera | None:
        with self.session() as s:
            return s.get(Camera, camera_id)

    def save_camera(self, cam: Camera) -> Camera:
        with self.session() as s:
            s.add(cam)
            s.commit()
            s.refresh(cam)
            return cam

    def update_camera(self, camera_id: int, **fields: Any) -> Camera | None:
        with self.session() as s:
            c = s.get(Camera, camera_id)
            if c is None:
                return None
            for k, v in fields.items():
                setattr(c, k, v)
            s.add(c)
            s.commit()
            s.refresh(c)
            return c

    def delete_camera(self, camera_id: int) -> bool:
        with self.session() as s:
            c = s.get(Camera, camera_id)
            if c is None:
                return False
            s.delete(c)
            s.commit()
            return True

    def set_frame_size(self, camera_id: int, w: int, h: int) -> None:
        with self.session() as s:
            c = s.get(Camera, camera_id)
            if c and (c.frame_width, c.frame_height) != (w, h):
                c.frame_width, c.frame_height = w, h
                s.add(c)
                s.commit()

    # ------------------------------------------------------------------ events
    def add_event(self, ev: Event) -> Event:
        with self.session() as s:
            s.add(ev)
            s.commit()
            s.refresh(ev)
            return ev

    def update_event(self, event_id: int, **fields: Any) -> Event | None:
        with self.session() as s:
            ev = s.get(Event, event_id)
            if ev is None:
                return None
            for k, v in fields.items():
                if k == "detail":
                    ev.detail = {**(ev.detail or {}), **v}
                else:
                    setattr(ev, k, v)
            s.add(ev)
            s.commit()
            s.refresh(ev)
            return ev

    def close_orphan_events(self, reason: str = "server_restart") -> int:
        """Close events left open by a previous server process (no camera thread tracks them any more).
        The end time is the start time plus the duration recorded so far."""
        with self.session() as s:
            rows = s.exec(select(Event).where(Event.ended_at.is_(None))).all()  # type: ignore[union-attr]
            for ev in rows:
                ev.ended_at = ev.ts + timedelta(seconds=ev.duration_s or 0.0)
                ev.detail = {**(ev.detail or {}), "closed_reason": reason}
                s.add(ev)
            s.commit()
            return len(rows)

    def get_event(self, event_id: int) -> Event | None:
        with self.session() as s:
            return s.get(Event, event_id)

    def list_events(self, since: datetime | None = None, until: datetime | None = None, kind: str | None = None,
                    zone_id: int | None = None, camera_id: int | None = None, unacked: bool = False,
                    limit: int = 100, offset: int = 0) -> tuple[list[Event], int]:
        def where(q):  # noqa: ANN001, ANN202
            if since:
                q = q.where(Event.ts >= since)
            if until:
                q = q.where(Event.ts < until)
            if kind:
                q = q.where(Event.kind == kind)
            if zone_id is not None:
                q = q.where(Event.zone_id == zone_id)
            if camera_id is not None:
                q = q.where(Event.camera_id == camera_id)
            if unacked:
                q = q.where(Event.acknowledged == False)  # noqa: E712
            return q

        with self.session() as s:
            total = s.exec(where(select(func.count(Event.id)))).one()
            rows = s.exec(where(select(Event)).order_by(Event.ts.desc(), Event.id.desc()).offset(offset).limit(limit))
            return list(rows), int(total)

    def ack_event(self, event_id: int) -> Event | None:
        return self.update_event(event_id, acknowledged=True, ack_at=utcnow())

    def events_for_day(self, day: date) -> list[Event]:
        start, end = local_day_bounds_utc(day)
        with self.session() as s:
            return list(s.exec(select(Event).where(Event.ts >= start, Event.ts < end).order_by(Event.ts)))

    # ------------------------------------------------------------------ stats
    def add_stats(self, camera_id: int, minute: datetime, counters: dict[str, int]) -> None:
        with self.session() as s:
            row = s.exec(select(StatMinute).where(StatMinute.camera_id == camera_id,
                                                  StatMinute.minute == minute)).first()
            if row is None:
                row = StatMinute(camera_id=camera_id, minute=minute)
            for k, v in counters.items():
                setattr(row, k, getattr(row, k) + int(v))
            s.add(row)
            s.commit()

    def stats_for_day(self, day: date) -> list[StatMinute]:
        start, end = local_day_bounds_utc(day)
        with self.session() as s:
            return list(s.exec(select(StatMinute).where(StatMinute.minute >= start, StatMinute.minute < end)))


def local_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """[start, end) of a local (site) calendar day, as UTC datetimes."""
    start_local = datetime.combine(day, time.min, tzinfo=SITE_TZ)
    start = start_local.astimezone(timezone.utc)
    return start, start + timedelta(days=1)


def today_local() -> date:
    return datetime.now(timezone.utc).astimezone(SITE_TZ).date()
