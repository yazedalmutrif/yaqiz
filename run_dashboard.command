#!/bin/bash
# Start Yaqiz on a Mac. Close this window to stop it.
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "Run setup_mac.command first."
  read -r -p "Press Enter to close this window."
  exit 1
fi
export PYTORCH_ENABLE_MPS_FALLBACK=1   # an operation the Apple GPU lacks runs on the CPU instead of failing
(sleep 15; open "http://127.0.0.1:8000") &
.venv/bin/python -m yaqiz serve
