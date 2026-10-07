@echo off
title Yaqiz - landing page (close this window to stop)
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep 2; Start-Process 'http://127.0.0.1:4180'"
"%PY%" scripts\serve_landing.py 4180
pause
