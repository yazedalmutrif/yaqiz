"""Request bodies (responses use the shared dict shapes in yaqiz.serialize)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..geometry import validate_polygon

Pt = tuple[float, float]


class SiteIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class ZoneIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["no_entry", "ppe"] = "no_entry"
    points: list[Pt] = Field(min_length=3, max_length=200)
    active: bool = True
    outdoor: bool = False
    require_helmet: bool = False
    require_vest: bool = False
    require_harness: bool = False
    interlock: bool = False

    @field_validator("points")
    @classmethod
    def _polygon(cls, v: list[Pt]) -> list[Pt]:
        return validate_polygon(v)


class ZonePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    kind: Literal["no_entry", "ppe"] | None = None
    points: list[Pt] | None = Field(default=None, min_length=3, max_length=200)
    active: bool | None = None
    outdoor: bool | None = None
    require_helmet: bool | None = None
    require_vest: bool | None = None
    require_harness: bool | None = None
    interlock: bool | None = None

    @field_validator("points")
    @classmethod
    def _polygon(cls, v: list[Pt] | None) -> list[Pt] | None:
        return None if v is None else validate_polygon(v)


class CameraIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    source: str = Field(min_length=1, max_length=500)
    enabled: bool = True


class CameraPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    source: str | None = Field(default=None, min_length=1, max_length=500)
    enabled: bool | None = None


class CalibPair(BaseModel):
    plan: Pt
    image: Pt


class CalibrationIn(BaseModel):
    pairs: list[CalibPair] = Field(min_length=4, max_length=40)


class HeatManualIn(BaseModel):
    temperature_c: float = Field(ge=-20, le=70)
    humidity: float = Field(ge=0, le=100)
