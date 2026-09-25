@echo off
rem damo - double-click to open the app; run "damo.cmd -Down" to stop it.
rem All the real logic (and all the comments) live in scripts\damo-app.ps1.
setlocal
set "PS1=%~dp0scripts\damo-app.ps1"
if not exist "%PS1%" (
  echo [damo] scripts\damo-app.ps1 not found next to this file.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%PS1%" %*
