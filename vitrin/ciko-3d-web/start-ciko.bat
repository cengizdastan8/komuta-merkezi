@echo off
cd /d "%~dp0"
start "Ciko demo server" /min cmd /c "python -m http.server 8764 --bind 127.0.0.1"
timeout /t 2 /nobreak >nul
start "Ciko local demo" http://127.0.0.1:8764/
