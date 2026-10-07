@echo off
title Yaqiz - one-time setup
cd /d "%~dp0"
echo Yaqiz setup: creates a Python 3.10 environment here and installs the packages (needs internet).
where py >nul 2>&1
if errorlevel 1 (
  echo Python 3.10 was not found. Install it from https://www.python.org/downloads/release/python-31011/
  echo and tick "Add python.exe to PATH", then run this file again.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.10 -m venv .venv
  if errorlevel 1 (
    echo Could not create a Python 3.10 environment. Install Python 3.10 and run this file again.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
echo Installing PyTorch for NVIDIA GPUs (about 3 GB). Without an NVIDIA GPU it still runs, but slowly.
".venv\Scripts\python.exe" -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu130
".venv\Scripts\python.exe" -m pip install -r requirements.txt
".venv\Scripts\python.exe" -m yaqiz seed --reset
echo.
echo Setup finished. Double-click run_dashboard.bat to start Yaqiz.
echo Demo clips are not included: see MEDIA_SOURCES.md, or add a webcam (source 0) on the Settings page.
pause
