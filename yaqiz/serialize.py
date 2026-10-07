"""JSON shapes shared by the API and the live bus."""
from __future__ import annotations

from datetime import datetime, timezone

from .models import Camera, Event, Zone


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def event_dict(ev: Event) -> dict:
    return {
        "id": ev.id, "ts": iso(ev.ts), "ended_at": iso(ev.ended_at), "kind": ev.kind, "severity": ev.severity,
        "camera_id": ev.camera_id, "zone_id": ev.zone_id, "track_id": ev.track_id, "item": ev.item,
        "detail": ev.detail or {},
        "plan": [ev.plan_x, ev.plan_y] if ev.plan_x is not None and ev.plan_y is not None else None,
        "image": [ev.img_x, ev.img_y] if ev.img_x is not None and ev.img_y is not None else None,
        "snapshot_url": f"/api/events/{ev.id}/snapshot.jpg" if ev.snapshot else None,
        "acknowledged": ev.acknowledged, "ack_at": iso(ev.ack_at), "duration_s": round(ev.duration_s or 0.0, 1),
    }


def zone_dict(z: Zone) -> dict:
    return {
        "id": z.id, "name": z.name, "kind": z.kind, "points": z.points, "active": z.active, "outdoor": z.outdoor,
        "require_helmet": z.require_helmet, "require_vest": z.require_vest, "require_harness": z.require_harness,
        "interlock": z.interlock,
    }


def camera_dict(c: Camera, status: dict | None) -> dict:
    return {
        "id": c.id, "name": c.name, "source": c.source, "enabled": c.enabled,
        "calibrated": c.homography is not None, "calib_error_px": c.calib_error_px,
        "calib_pairs": c.calib_pairs or [], "homography": c.homography,
        "frame_size": [c.frame_width, c.frame_height] if c.frame_width else None,
        "status": status or {"state": "stopped" if not c.enabled else "starting"},
    }
