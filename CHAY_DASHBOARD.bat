@echo off
echo Starting SLTP Dashboard...
echo.
echo Open browser: http://localhost:3000
echo Press Ctrl+C to stop.
echo.
cd /d "%~dp0dashboard"
npm run dev
pause
