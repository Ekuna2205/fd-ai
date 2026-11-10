@echo off
REM FaceGuard AI: double-click to start (needs Python 3.11+ from python.org). Data: backend\data
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3 run.py %*) else (python run.py %*)
pause
