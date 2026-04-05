@echo off
setlocal

set "PS_SCRIPT=%~dp0start-dev.ps1"

if not exist "%PS_SCRIPT%" (
  echo [ERROR] PowerShell launcher not found at "%PS_SCRIPT%".
  exit /b 1
)

if /I "%~1"=="help" goto :usage
if /I "%~1"=="--help" goto :usage
if /I "%~1"=="-h" goto :usage

powershell.exe -NoLogo -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*
exit /b %ERRORLEVEL%

:usage
echo AI Student Companion launcher
echo.
echo Double-click this file for the interactive menu.
echo.
echo Common commands:
echo   start-dev.bat                ^(interactive start/stop menu^)
echo   start-dev.bat -Start         ^(start immediately^)
echo   start-dev.bat -Stop          ^(stop the running app^)
echo   start-dev.bat -Help          ^(show PowerShell options^)
echo.
echo The interactive launcher will:
echo   - ask before killing ports 3000 and 8000
echo   - ask about debug mode, background mode, and reindex mode
echo   - let you choose full, incremental, or skipped startup reindex
echo   - open a live log tail window
exit /b 0
