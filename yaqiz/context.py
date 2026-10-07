"""Application context: one store, bus, weather service, interlock and camera manager per process."""
from __future__ import annotations

import threading

from .bus import Bus
from .config import Settings
from .heat import WeatherService
from .interlock import Interlock
from .store import Store
from .vision.worker import WorkerManager


class Context:
    def __init__(self, settings: Settings) -> None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings = settings
        self.store = Store(settings.db_path)
        self.bus = Bus()
        self.weather = WeatherService()
        self.interlock = Interlock(settings.mqtt_url)
        self.manager = WorkerManager(self)
        self._ppe = None
        self._ppe_lock = threading.Lock()

    def ppe(self):  # noqa: ANN201  (lazy: loading the model needs the GPU stack)
        from .vision.engine import PPEDetector

        with self._ppe_lock:
            if self._ppe is None:
                self._ppe = PPEDetector(self.settings)
            return self._ppe

    @property
    def ppe_loaded(self):  # noqa: ANN201
        return self._ppe

    def heat_now(self) -> dict:
        site = self.store.get_site()
        return self.weather.current(site.lat, site.lon, self.store.get_runtime())
