@echo off
setlocal

cd /d "%~dp0"

echo Stopping remote-service containers...
docker compose stop

echo.
docker compose ps

endlocal
pause
