@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo SupeRR Selector - Dashboard launcher
echo ================================================

if not exist ".venv\Scripts\python.exe" (
    echo Creating a local Python virtual environment...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo Could not create the virtual environment. Install Python 3.10-3.13 and try again.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo Could not activate the virtual environment.
    pause
    exit /b 1
)

echo Installing/checking dashboard dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency installation failed. Check your internet connection and Python installation.
    pause
    exit /b 1
)

echo Checking that the existing project outputs are present...
python validate_frontend.py
if errorlevel 1 (
    echo The project data check failed. Make sure frontend is beside the outputs folder.
    pause
    exit /b 1
)

echo Starting the dashboard. Keep this window open while using it.
python -m streamlit run app.py
pause
