@echo off
cd /d "%~dp0"
python -m pip install -r requirements-gui.txt
if errorlevel 1 (
    echo.
    echo Dependency installation failed. Check Python and Internet connection.
)
pause
