@echo off
setlocal

cd /d "%~dp0"

echo Starting remote-service...
docker compose up -d

echo.
docker compose ps

endlocal
pause
