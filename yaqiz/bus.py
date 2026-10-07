"""Thread-safe fan-out from camera threads to WebSocket clients on the asyncio loop."""
from __future__ import annotations

import asyncio
from typing import Any


class Bus:
    MAX_QUEUE = 256  # a slow client loses messages instead of slowing the cameras down

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subs: set[asyncio.Queue] = set()

    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish(self, msg: dict[str, Any]) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(self._fanout, msg)
        except RuntimeError:  # loop shutting down
            pass

    def _fanout(self, msg: dict[str, Any]) -> None:
        for q in list(self._subs):
            if q.qsize() < self.MAX_QUEUE:
                q.put_nowait(msg)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

    @property
    def subscribers(self) -> int:
        return len(self._subs)
