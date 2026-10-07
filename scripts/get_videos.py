"""Check the demo clips listed in MEDIA_SOURCES.md (presence + SHA-256). Does not download.

The Pexels Terms of Service forbid automated collection ("programs or robots"),
so download each clip by hand with the "Free download" button on its Pexels page
and save it as data\\videos\\pexels_<id>.mp4. Then run:

    .venv\\Scripts\\python scripts\\get_videos.py

The clips are only used to run the demo (inference); they are never used to train a model.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import VIDEOS_DIR  # noqa: E402

# pexels id -> (page URL, SHA-256 of the file used on 2026-10-06, purpose)
CLIPS = {
    "35631533": (
        "https://www.pexels.com/video/construction-workers-on-building-site-35631533/",
        "d1865af00a9dded8cfdaa8584aa3e28e70f5320959ad232c8f5d94abf4746421",
        "zone demo, clip 1 (high-angle rebar mat, portrait)",
    ),
    "11798561": (
        "https://www.pexels.com/video/workers-on-construction-11798561/",
        "fcce622402a62bd3412114ffd0aca25e6d205552d079f041b0bb5821dce41dce",
        "zone demo, clip 2 (static camera, upper slab)",
    ),
    "5434223": (
        "https://www.pexels.com/video/workers-walking-in-construction-site-5434223/",
        "df2f645caad8d90eee93ad1c5b012de4394981e5eeabd92e37bfc16101ea2fa4",
        "PPE detector still, clip 3 (workers from behind)",
    ),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ok = True
    for vid, (url, expected, purpose) in CLIPS.items():
        path = VIDEOS_DIR / f"pexels_{vid}.mp4"
        if not path.exists():
            ok = False
            print(f"MISSING  {path.name}  ({purpose})\n         download by hand: {url}")
            continue
        got = sha256(path)
        if got == expected:
            print(f"OK       {path.name}  ({purpose})")
        else:
            # Pexels may serve a different encode later; the demo would still run, but numbers may differ.
            ok = False
            print(f"DIFFERS  {path.name}  sha256 {got[:12]}... (expected {expected[:12]}...)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
