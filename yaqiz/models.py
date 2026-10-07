"""Database tables (SQLModel on SQLite). Timestamps are timezone-aware UTC."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Site(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = "موقع تجريبي"
    plan_file: str | None = None
    plan_width: int = 1600
    plan_height: int = 1000
    lat: float = 24.7136          # Riyadh
    lon: float = 46.6753
    updated_at: datetime = Field(default_factory=utcnow)


class Zone(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    kind: str = "no_entry"        # "no_entry" | "ppe"
    points: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))  # plan px [[x, y], ...]
    active: bool = True
    outdoor: bool = False
    require_helmet: bool = False
    require_vest: bool = False
    require_harness: bool = False
    interlock: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class Camera(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    source: str                   # file path, rtsp:// or http(s):// URL, or a webcam index
    enabled: bool = True
    homography: list | None = Field(default=None, sa_column=Column(JSON))   # 3x3, plan -> image
    calib_pairs: list | None = Field(default=None, sa_column=Column(JSON))  # [{"plan":[x,y],"image":[u,v]}]
    calib_error_px: float | None = None
    frame_width: int | None = None
    frame_height: int | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Event(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=utcnow, index=True)
    ended_at: datetime | None = None
    kind: str = Field(index=True)
    severity: str = "warning"     # "warning" | "critical"
    camera_id: int | None = Field(default=None, index=True)
    zone_id: int | None = Field(default=None, index=True)
    track_id: int | None = None
    item: str | None = None
    detail: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    plan_x: float | None = None
    plan_y: float | None = None
    img_x: float | None = None
    img_y: float | None = None
    snapshot: str | None = None
    acknowledged: bool = False
    ack_at: datetime | None = None
    duration_s: float = 0.0


class StatMinute(SQLModel, table=True):
    """Per-camera, per-minute counters for compliance and uptime (filled by the camera workers)."""

    id: int | None = Field(default=None, primary_key=True)
    camera_id: int = Field(index=True)
    minute: datetime = Field(index=True)
    frames: int = 0
    people: int = 0               # sum over analysed frames
    in_zone: int = 0
    helmet_yes: int = 0
    helmet_no: int = 0
    vest_yes: int = 0
    vest_no: int = 0


class SettingRow(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
