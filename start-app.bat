@echo off
setlocal

set "LAUNCHER=%~dp0start-dev.bat"

if not exist "%LAUNCHER%" (
  echo [ERROR] Launcher not found at "%LAUNCHER%".
  exit /b 1
)

call "%LAUNCHER%" %*
exit /b %ERRORLEVEL%
