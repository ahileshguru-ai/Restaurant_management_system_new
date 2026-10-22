@echo off
title Restaurant DBMS - Test Suite
echo ======================================================================
echo 1. RUNNING DATABASE CONSTRAINTS & ACID VERIFICATION SUITE
echo ======================================================================
".venv\Scripts\python.exe" database\test_constraints.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Database tests failed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ======================================================================
echo 2. RUNNING LIVE HTTP END-TO-END API SUITE (Requires Server on Port 8000)
echo ======================================================================
".venv\Scripts\python.exe" test_e2e_api.py

echo.
pause
