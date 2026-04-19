@echo off
echo =========================================
echo ForeGuard - Explanable AI Forgery Detection
echo =========================================

echo 1. Checking backend directory...
if not exist "backend" (
    echo Error: backend directory not found.
    pause
    exit /b
)

cd backend

echo 2. Installing requirements if necessary...
pip install -r requirements.txt

echo.
echo 3. Starting FastAPI Server...
echo The app will be available at http://localhost:8000
echo.
python -m uvicorn app.main:app --reload --port 8000
pause
