@echo off
title X BIST Bot Web Dashboard
echo ========================================================
echo   X (Twitter) BIST 100 AI Web Yonetim Paneli Baslatiliyor
echo   Adres: http://localhost:8000
echo ========================================================
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
pause
