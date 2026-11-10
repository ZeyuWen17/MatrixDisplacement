@echo off
cd /d "%~dp0"
python -m matrix_displacement.gui
if errorlevel 1 (
    echo.
    echo GUI start failed. Please run: python -m pip install -r requirements-gui.txt
    pause
)
