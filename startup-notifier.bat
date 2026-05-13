@echo off
setlocal

cd /d "%~dp0"

echo Starting remote-service with notifier...
docker compose --profile notifier up -d

echo.
docker compose ps

endlocal
pause
