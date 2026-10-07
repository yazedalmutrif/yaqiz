"""Per-track state: smooth noisy per-frame results and emit one event per violation.

ByteTrack gives each person a stable ID, so a violation is reported once when
it starts (not on every frame), and short flickers are ignored.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class TrackState:
    track_id: int
    window: int = 15          # frames of helmet history kept per track
    min_votes: int = 3        # observations needed before deciding helmet / no helmet
    enter_frames: int = 3     # consecutive frames inside a zone before flagging
    exit_frames: int = 5      # consecutive frames outside before clearing the flag
    helmet_hist: deque = field(default_factory=deque)
    in_streak: int = 0
    out_streak: int = 0
    in_zone: bool = False
    zone_name: str | None = None
    frames_in_zone: int = 0
    no_helmet_reported: bool = False

    def update_helmet(self, state: str | None) -> None:
        if state is None:
            return
        self.helmet_hist.append(state)
        while len(self.helmet_hist) > self.window:
            self.helmet_hist.popleft()

    @property
    def helmet(self) -> str:
        """'helmet', 'no_helmet' or 'unknown' after majority vote over the window."""
        n_ok = sum(1 for s in self.helmet_hist if s == "helmet")
        n_bad = sum(1 for s in self.helmet_hist if s == "no_helmet")
        if n_bad >= self.min_votes and n_bad > n_ok:
            return "no_helmet"
        if n_ok >= self.min_votes and n_ok >= n_bad:
            return "helmet"
        return "unknown"

    def update_zone(self, zone_name: str | None) -> bool:
        """Feed this frame's zone hit. Returns True on the frame the person is flagged as entering."""
        entered = False
        if zone_name is not None:
            self.in_streak += 1
            self.out_streak = 0
            if not self.in_zone and self.in_streak >= self.enter_frames:
                self.in_zone, self.zone_name, entered = True, zone_name, True
        else:
            self.out_streak += 1
            self.in_streak = 0
            if self.in_zone and self.out_streak >= self.exit_frames:
                self.in_zone, self.zone_name = False, None
        if self.in_zone:
            self.frames_in_zone += 1
        return entered


class TrackRegistry:
    def __init__(self, **kwargs) -> None:
        self._kwargs = kwargs
        self.tracks: dict[int, TrackState] = {}
        self.events: list[dict] = []

    def get(self, track_id: int) -> TrackState:
        if track_id not in self.tracks:
            self.tracks[track_id] = TrackState(track_id=track_id, **self._kwargs)
        return self.tracks[track_id]

    def log(self, frame_idx: int, t_sec: float, track_id: int, kind: str, detail: str) -> None:
        self.events.append(
            {"frame": frame_idx, "t_sec": round(t_sec, 2), "track_id": track_id, "event": kind, "detail": detail}
        )
