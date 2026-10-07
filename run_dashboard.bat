@echo off
title Yaqiz - dashboard (close this window to stop)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup_windows.bat first.
  pause
  exit /b 1
)
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep 15; Start-Process 'http://127.0.0.1:8000'"
".venv\Scripts\python.exe" -m yaqiz serve
pause
