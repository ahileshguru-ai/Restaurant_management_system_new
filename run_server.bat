@echo off
title Restaurant DBMS - FastAPI Server
echo ======================================================================
echo Starting Restaurant Management System on http://127.0.0.1:8000
echo ======================================================================
echo.
echo Opening browser to http://127.0.0.1:8000 ...
timeout /t 2 /nobreak >nul
start http://127.0.0.1:8000
echo Server is running. Press CTRL+C to stop.
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
