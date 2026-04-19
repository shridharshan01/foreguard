@echo off
echo.
echo  ╔══════════════════════════════════════╗
echo  ║   ForeGuard v2 — Document Forensics  ║
echo  ╚══════════════════════════════════════╝
echo.
cd /d "%~dp0backend"
echo [1/2] Installing dependencies...
pip install -r requirements.txt --quiet
echo [2/2] Starting ForeGuard server...
echo.
echo  Open http://localhost:8000 in your browser
echo.
python -m uvicorn app.main:app --reload --port 8000
pause