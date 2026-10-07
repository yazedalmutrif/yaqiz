#!/bin/bash
# Serve the landing page on a Mac. Close this window to stop it.
cd "$(dirname "$0")" || exit 1
PY=.venv/bin/python
[ -x "$PY" ] || PY=python3
(sleep 2; open "http://127.0.0.1:4180") &
"$PY" scripts/serve_landing.py 4180
