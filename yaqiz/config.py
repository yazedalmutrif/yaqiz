"""Service settings (environment / .env, prefix YAQIZ_) and operator-tunable runtime settings."""
from __future__ import annotations

import os
from datetime import timedelta, timezone
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
# Ultralytics keeps its settings/fonts inside the repo instead of %APPDATA% (set before it is imported).
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))

APP_NAME = "Yaqiz"
# Saudi Arabia has no daylight saving time; a fixed offset avoids needing the tzdata package on Windows.
SITE_TZ = timezone(timedelta(hours=3), "AST")


class Settings(BaseSettings):
    """Deployment settings. Override with YAQIZ_* environment variables or a .env file."""

    model_config = SettingsConfigDict(
        env_prefix="YAQIZ_", env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    host: str = "127.0.0.1"
    port: int = 8000
    data_dir: Path = ROOT / "data"
    models_dir: Path = ROOT / "models"
    app_dist: Path = ROOT / "app" / "dist"
    voices_dir: Path = ROOT / "app" / "public" / "voices"
    ppe_weights: str = "ppe_v2.pt"
    ppe_fallback_weights: str = "ppe_yolo11s_best.pt"
    pose_weights: str = "yolo11s-pose.pt"
    person_weights: str = "yolo11s.pt"     # COCO detector + ByteTrack: best recall on small, distant workers
    pose_imgsz: int = 1280                  # keypoints for SOS / man down (frames are at most 1280 px)
    pose_every: int = 2                     # run pose on every Nth analysed frame (keypoints cached between)
    ppe_every: int = 2                      # run the PPE detector on every Nth analysed frame
    device: str = ""            # "" = first CUDA GPU if available, else CPU
    imgsz: int = 960           # small, distant workers need a larger input than 640
    max_side: int = 1280        # frames with a longer side are downscaled before analysis
    max_fps: float = 10.0       # analysis rate cap per camera
    stream_fps: float = 12.0    # MJPEG rate cap per viewer
    jpeg_quality: int = 80
    mqtt_url: str = ""          # e.g. "mqtt://127.0.0.1:1883"; empty = simulated operator signal
    start_workers: bool = True  # tests switch the camera workers off
    cors_origins: list[str] = ["http://localhost:5174", "http://127.0.0.1:5174"]

    @property
    def db_path(self) -> Path:
        return self.data_dir / "yaqiz.db"

    @property
    def snapshots_dir(self) -> Path:
        return self.data_dir / "snapshots"

    @property
    def site_dir(self) -> Path:
        return self.data_dir / "site"

    def model_path(self, name: str) -> Path:
        p = Path(name)
        return p if p.is_absolute() else self.models_dir / p

    def resolve_ppe_weights(self) -> Path:
        """The newest PPE model that exists on disk (v2 after the data work, else Sprint 0)."""
        for name in (self.ppe_weights, self.ppe_fallback_weights):
            path = self.model_path(name)
            if path.exists():
                return path
        raise FileNotFoundError(
            f"No PPE weights found ({self.ppe_weights}, {self.ppe_fallback_weights}) in {self.models_dir}"
        )


class RuntimeSettings(BaseModel):
    """Behaviour the HSE operator can tune from the dashboard (stored in the database)."""

    voice_enabled: bool = True
    voice_languages: list[str] = Field(default_factory=lambda: ["ar", "en", "ur", "hi", "bn"])
    blur_stream: bool = True                 # blur faces in live streams too (snapshots are always blurred)
    site_require_helmet: bool = True         # helmet required everywhere on site
    site_require_vest: bool = False          # vest required everywhere on site
    enter_frames: int = Field(3, ge=1, le=60)
    exit_frames: int = Field(6, ge=1, le=120)
    escalate_s: float = Field(10.0, ge=1, le=600)
    ppe_hold_s: float = Field(2.0, ge=0.2, le=60)
    man_down_s: float = Field(5.0, ge=1, le=120)
    sos_hold_s: float = Field(1.5, ge=0.3, le=30)
    cooldown_s: float = Field(30.0, ge=1, le=3600)
    lost_s: float = Field(3.0, ge=0.5, le=30)
    det_conf: float = Field(0.35, ge=0.05, le=0.95)
    pose_conf: float = Field(0.30, ge=0.05, le=0.95)
    kp_conf: float = Field(0.40, ge=0.05, le=0.95)
    min_person_px: int = Field(90, ge=20, le=2000)
    machine_gap: float = Field(1.0, ge=0.2, le=4.0)  # "near a machine", in worker body heights (1.0 ~ 1.7 m)
    midday_ban_from: str = "06-15"
    midday_ban_to: str = "09-15"
    midday_ban_start_hour: int = Field(12, ge=0, le=23)
    midday_ban_end_hour: int = Field(15, ge=1, le=24)

    @field_validator("voice_languages")
    @classmethod
    def _known_languages(cls, v: list[str]) -> list[str]:
        allowed = {"ar", "en", "ur", "hi", "bn"}
        bad = [x for x in v if x not in allowed]
        if bad:
            raise ValueError(f"unknown voice languages: {bad}")
        return v

    @field_validator("midday_ban_from", "midday_ban_to")
    @classmethod
    def _mmdd(cls, v: str) -> str:
        m, d = v.split("-")
        if not (1 <= int(m) <= 12 and 1 <= int(d) <= 31):
            raise ValueError("expected MM-DD")
        return f"{int(m):02d}-{int(d):02d}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
