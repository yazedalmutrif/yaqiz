"""Frame sources with a background reader that always holds only the newest frame.

A source spec is one of:
  * a video file path (relative paths resolve against the project root); looped and paced at its own FPS,
  * an rtsp:// / rtmp:// / http(s):// URL (IP camera, or a phone running an IP-camera app),
  * a webcam index such as "0".
Streams reconnect with exponential backoff.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

STREAM_PREFIXES = ("rtsp://", "rtmp://", "http://", "https://")


def resize_max_side(frame: np.ndarray, max_side: int) -> np.ndarray:
    h, w = frame.shape[:2]
    side = max(h, w)
    if max_side <= 0 or side <= max_side:
        return frame
    scale = max_side / side
    return cv2.resize(frame, (int(round(w * scale)), int(round(h * scale))), interpolation=cv2.INTER_AREA)


def open_capture(spec: str, base_dir: Path | None = None) -> tuple[cv2.VideoCapture, bool]:
    """Return (capture, is_file)."""
    s = spec.strip()
    if s.isdigit():
        backend = (cv2.CAP_DSHOW if os.name == "nt"
                   else cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY)
        return cv2.VideoCapture(int(s), backend), False
    if s.lower().startswith(STREAM_PREFIXES):
        return cv2.VideoCapture(s, cv2.CAP_FFMPEG), False
    path = Path(s)
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    return cv2.VideoCapture(str(path)), True


def grab_one_frame(spec: str, base_dir: Path | None, max_side: int, timeout_s: float = 6.0) -> np.ndarray | None:
    """Open a source just long enough to read one frame (calibrating a stopped camera)."""
    cap, _ = open_capture(spec, base_dir)
    try:
        deadline = time.monotonic() + timeout_s
        while cap.isOpened() and time.monotonic() < deadline:
            ok, frame = cap.read()
            if ok and frame is not None:
                return resize_max_side(frame, max_side)
            time.sleep(0.05)
        return None
    finally:
        cap.release()


class FrameSource:
    def __init__(self, spec: str, max_side: int = 1280, base_dir: Path | None = None) -> None:
        self.spec, self.max_side, self.base_dir = spec, max_side, base_dir
        self._lock = threading.Lock()
        self._frame: np.ndarray | None = None
        self._seq = 0
        self._t_frame = 0.0  # time.monotonic() when the newest frame was decoded
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.state = "stopped"
        self.error: str | None = None
        self.fps_in = 0.0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=f"source:{self.spec}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        self.state = "stopped"

    def read(self) -> tuple[np.ndarray, int, float] | None:
        """The newest frame, its sequence number and the time.monotonic() at which it was decoded,
        taken under one lock so the timestamp always belongs to the frame."""
        with self._lock:
            return None if self._frame is None else (self._frame, self._seq, self._t_frame)

    def _run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            self.state = "connecting"
            cap, is_file = open_capture(self.spec, self.base_dir)
            if not cap.isOpened():
                cap.release()
                self.state, self.error = "error", "تعذّر فتح مصدر الكاميرا"
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 10.0)
                continue
            backoff, self.state, self.error = 1.0, "live", None
            file_fps = cap.get(cv2.CAP_PROP_FPS) if is_file else 0.0
            period = 1.0 / file_fps if is_file and 1.0 < file_fps < 121.0 else 0.0
            next_t = time.monotonic()
            failures, count, t_win = 0, 0, time.monotonic()
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    failures += 1
                    if is_file and failures < 3:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # loop the demo clip
                        continue
                    self.state, self.error = "reconnecting", "انقطع البث، جارٍ إعادة الاتصال"
                    break
                failures = 0
                frame = resize_max_side(frame, self.max_side)
                with self._lock:
                    self._frame = frame
                    self._seq += 1
                    self._t_frame = time.monotonic()
                count += 1
                now = time.monotonic()
                if now - t_win >= 1.0:
                    self.fps_in, count, t_win = count / (now - t_win), 0, now
                if period:
                    next_t += period
                    delay = next_t - time.monotonic()
                    if delay > 0:
                        self._stop.wait(delay)
                    elif delay < -1.0:
                        next_t = time.monotonic()  # fell behind (slow decode): resync instead of bursting
            cap.release()
            if not self._stop.is_set():
                self._stop.wait(backoff)
        self.state = "stopped"
