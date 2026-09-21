@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment not found.
  echo Create it with: python -m venv .venv
  echo Then install: .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)
.venv\Scripts\python.exe main.py
