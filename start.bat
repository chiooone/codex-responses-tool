@echo off
setlocal
cd /d "%~dp0"
python app.py
if errorlevel 1 (
  echo.
  echo Failed to start Codex Responses Tool.
  echo Make sure Python is installed and available in PATH.
  pause
)
