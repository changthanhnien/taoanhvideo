@echo off
cd /d "%~dp0"
start "" ".\.venv\Scripts\pythonw.exe" main.py > NAVTools.log 2>&1
