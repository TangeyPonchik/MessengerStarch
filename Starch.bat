@echo off
cd /d "%~dp0"
start "Starch Server" cmd /k python server.py
timeout /t 2 /nobreak >nul
python client.py
pause