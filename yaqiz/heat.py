"""Heat stress: NWS heat index, categories, the Saudi midday outdoor-work ban, and current weather.

Midday ban (HRSD, 2026): 12:00–15:00 from 15 June to 15 September for private-sector outdoor work.
Weather comes from Open-Meteo (no API key); an operator can enter values manually when offline.
"""
from __future__ import annotations

import math
import threading
import time
from datetime import datetime, timezone

import httpx

from .config import SITE_TZ, RuntimeSettings

# NWS heat-index bands, converted to °C: caution 80°F, extreme caution 90°F, danger 103°F, extreme danger 125°F.
CATEGORIES: tuple[tuple[float, int, str, str], ...] = (
    (51.7, 4, "خطر شديد", "Extreme danger"),
    (39.4, 3, "خطر", "Danger"),
    (32.2, 2, "حذر شديد", "Extreme caution"),
    (26.7, 1, "حذر", "Caution"),
)


def heat_index_c(temp_c: float, rh: float) -> float:
    """US National Weather Service heat index (Rothfusz regression with NWS adjustments), in °C."""
    t = temp_c * 9.0 / 5.0 + 32.0
    simple = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + rh * 0.094)
    if (simple + t) / 2.0 < 80.0:
        hi = simple
    else:
        hi = (
            -42.379 + 2.04901523 * t + 10.14333127 * rh - 0.22475541 * t * rh
            - 0.00683783 * t * t - 0.05481717 * rh * rh + 0.00122874 * t * t * rh
            + 0.00085282 * t * rh * rh - 0.00000199 * t * t * rh * rh
        )
        if rh < 13 and 80.0 <= t <= 112.0:
            hi -= ((13.0 - rh) / 4.0) * math.sqrt((17.0 - abs(t - 95.0)) / 17.0)
        elif rh > 85 and 80.0 <= t <= 87.0:
            hi += ((rh - 85.0) / 10.0) * ((87.0 - t) / 5.0)
    return (hi - 32.0) * 5.0 / 9.0


def heat_category(hi_c: float) -> tuple[int, str, str]:
    for threshold, idx, ar, en in CATEGORIES:
        if hi_c >= threshold:
            return idx, ar, en
    return 0, "طبيعي", "Normal"


def _mmdd(s: str) -> tuple[int, int]:
    m, d = s.split("-")
    return int(m), int(d)


def midday_ban_active(now_local: datetime, rt: RuntimeSettings) -> bool:
    day = (now_local.month, now_local.day)
    in_season = _mmdd(rt.midday_ban_from) <= day <= _mmdd(rt.midday_ban_to)
    in_hours = rt.midday_ban_start_hour <= now_local.hour < rt.midday_ban_end_hour
    return in_season and in_hours


class WeatherService:
    URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, ttl_s: float = 600.0, timeout_s: float = 6.0) -> None:
        self.ttl_s, self.timeout_s = ttl_s, timeout_s
        self._lock = threading.Lock()
        self._cached: tuple[float, float, float, str] | None = None  # (temp, rh, fetched monotonic, iso)
        self._manual: tuple[float, float, str] | None = None

    def set_manual(self, temp_c: float, rh: float) -> None:
        with self._lock:
            self._manual = (float(temp_c), float(rh), datetime.now(timezone.utc).isoformat())

    def clear_manual(self) -> None:
        with self._lock:
            self._manual = None

    def _fetch(self, lat: float, lon: float) -> tuple[float, float] | None:
        try:
            r = httpx.get(
                self.URL,
                params={"latitude": lat, "longitude": lon, "current": "temperature_2m,relative_humidity_2m"},
                timeout=self.timeout_s,
            )
            r.raise_for_status()
            cur = r.json()["current"]
            return float(cur["temperature_2m"]), float(cur["relative_humidity_2m"])
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            return None

    def current(self, lat: float, lon: float, rt: RuntimeSettings, now: datetime | None = None) -> dict:
        now_local = (now or datetime.now(timezone.utc)).astimezone(SITE_TZ)
        with self._lock:
            manual, cached = self._manual, self._cached
        source = "unavailable"
        temp = rh = None
        fetched_at = None
        if manual:
            temp, rh, fetched_at = manual
            source = "manual"
        else:
            if cached is None or time.monotonic() - cached[2] > self.ttl_s:
                got = self._fetch(lat, lon)
                if got:
                    cached = (got[0], got[1], time.monotonic(), datetime.now(timezone.utc).isoformat())
                    with self._lock:
                        self._cached = cached
            if cached:
                temp, rh, _, fetched_at = cached
                source = "open-meteo"
        out = {
            "temperature_c": temp, "humidity": rh, "heat_index_c": None,
            "category": None, "category_ar": None, "category_en": None,
            "midday_ban_active": midday_ban_active(now_local, rt),
            "midday_ban": {"from": rt.midday_ban_from, "to": rt.midday_ban_to,
                           "start_hour": rt.midday_ban_start_hour, "end_hour": rt.midday_ban_end_hour},
            "source": source, "fetched_at": fetched_at, "local_time": now_local.strftime("%H:%M"),
        }
        if temp is not None and rh is not None:
            hi = heat_index_c(temp, rh)
            idx, ar, en = heat_category(hi)
            out.update(heat_index_c=round(hi, 1), category=idx, category_ar=ar, category_en=en)
        return out
