@echo off
title AI Student Companion Launcher

echo ==========================================
echo   Starting AI Student Companion System
echo ==========================================

set BASE_DIR=%~dp0
echo Base Directory: %BASE_DIR%

REM ------------------------------------------
REM BACKEND
REM ------------------------------------------
echo Starting Backend...

start "Backend Server" cmd /k "cd /d %BASE_DIR%backend && echo Current Dir: %cd% && if exist app\main.py (echo Starting FastAPI... && uvicorn app.main:app --reload) else (echo ERROR: app\main.py not found & pause)"


echo Waiting for backend to start...
timeout /t 8 /nobreak >nul

REM ------------------------------------------
REM FRONTEND
REM ------------------------------------------
echo Starting Frontend...

start "Frontend App" cmd /k "cd /d %BASE_DIR%frontend && echo Current Dir: %cd% && if exist package.json (echo Installing dependencies... && npm install && echo Starting React... && npm start) else (echo ERROR: package.json not found & pause)"

echo ==========================================
echo   Both services launched
echo ==========================================

pause