#!/bin/bash
# Yaqiz one-time setup on a Mac (Apple Silicon M1 or newer, macOS 14 or newer).
# Double-click this file, or in Terminal:  bash setup_mac.command
cd "$(dirname "$0")" || exit 1
pause() { read -r -p "Press Enter to close this window."; }
echo "Yaqiz setup: creates a Python environment in this folder and installs the packages (needs internet)."
if [ "$(uname -m)" != "arm64" ]; then
  echo "This Mac has an Intel processor. The PyTorch version Yaqiz uses needs Apple Silicon (M1 or newer)."
  pause; exit 1
fi
major="$(sw_vers -productVersion | cut -d. -f1)"
if [ "${major:-0}" -lt 14 ]; then
  echo "macOS 14 (Sonoma) or newer is needed. This Mac has macOS $(sw_vers -productVersion)."
  pause; exit 1
fi
PY=""
for c in python3.10 python3.11 python3.12 python3.13; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ] && command -v python3 >/dev/null 2>&1 \
   && python3 -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)'; then
  PY="python3"
fi
if [ -z "$PY" ]; then
  echo "Python 3.10 to 3.13 is needed. Install it from https://www.python.org/downloads/macos/ and run this again."
  pause; exit 1
fi
echo "Using $("$PY" --version)"
if [ ! -x .venv/bin/python ]; then
  "$PY" -m venv .venv || { echo "Could not create the Python environment."; pause; exit 1; }
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt || { echo "Installing the packages failed (see the messages above)."; pause; exit 1; }
.venv/bin/python -m yaqiz seed --reset
chmod +x run_dashboard.command run_landing.command 2>/dev/null
echo
echo "Setup finished. Now open run_dashboard.command (or: bash run_dashboard.command)."
echo "Demo clips are not included: see MEDIA_SOURCES.md, or add the Mac camera (source 0) on the Settings page."
pause
