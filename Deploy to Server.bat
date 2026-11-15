@echo off
REM Pay Logger -- one-click deploy to ac-server.
REM Commits + pushes everything, then on the server: git pull, rebuild the
REM container image, restart the service. Double-click it, or run it from a
REM terminal with a message:  "Deploy to Server.bat" "fixed the popup"

REM ---- settings -----------------------------------------------------------
set SERVER=achen@192.168.1.253
REM Where the repo is cloned on ac-server (change if yours is elsewhere):
set REPO=~/pay-logger
REM -------------------------------------------------------------------------

cd /d "%~dp0"

set MSG=%~1
if "%MSG%"=="" set /p MSG=What changed? (Enter for "Update"):
if "%MSG%"=="" set MSG=Update

echo.
echo === Committing and pushing ===
git add -A
git commit -m "%MSG%"
git push || goto :fail

echo.
echo === Updating ac-server ===
ssh %SERVER% "cd %REPO% && git pull && podman build -t paylogger -f web/Containerfile . && systemctl --user restart paylogger && systemctl --user is-active paylogger" || goto :fail

echo.
echo === Done. Refresh the app on your phone. ===
pause
exit /b 0

:fail
echo.
echo *** Something failed -- see the messages above. ***
pause
exit /b 1
