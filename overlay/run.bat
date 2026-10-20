@echo off
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt
if errorlevel 1 pause & exit /b 1
start "FlyChess local bridge" cmd /k py -3 bridge.py
timeout /t 2 /nobreak >nul
start "FlyChess overlay app" py -3 app.py
start "FlyChess overlay mode" http://localhost:5180/external-overlay
echo Keep the FlyChess pnpm dev terminal running in the repository root.
pause
