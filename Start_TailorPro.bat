@echo off
title TailorPro App
cd /d "%~dp0"
echo ==============================================
echo        STARTING TAILORPRO CLOUD TUNNEL
echo ==============================================
start "" /b ".\venv\Scripts\python.exe" app.py
timeout /t 2 >nul
echo App running on port 5000.
echo Launching Cloudflare Tunnel...
".\cloudflared.exe" tunnel --url http://127.0.0.1:5000
pause
