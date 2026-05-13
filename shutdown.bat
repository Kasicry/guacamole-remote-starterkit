@echo off
setlocal

cd /d "%~dp0"

echo Stopping and removing remote-service containers...
docker compose down

echo.
docker compose ps

endlocal
pause
