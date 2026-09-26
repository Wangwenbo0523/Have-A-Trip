@echo off
rem Have-A-Trip installer entry point: double-click this file.
rem Uninstall: install.cmd -Uninstall (or the "uninstall damo" entry in the Start menu).
rem All the real logic lives in installer\install.ps1 -- this only finds it and forwards args.
rem Plain ASCII on purpose: cmd.exe reads .cmd files with the OEM code page, so Chinese
rem text here would turn into mojibake on a code page 936 machine. Same reason damo.cmd
rem is English-only.
setlocal
set "PS1=%~dp0installer\install.ps1"
if not exist "%PS1%" (
  echo [damo-install] installer\install.ps1 not found next to this file.
  echo Make sure the archive was fully extracted: installer\ must sit beside backend\ and frontend\.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo [damo-install] install did not finish. Exit code: %RC%
  echo [damo-install] See the output above.
  pause
)
exit /b %RC%