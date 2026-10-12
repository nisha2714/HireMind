@echo off
REM Use Python 3.13 to run Streamlit app
REM This fixes the Python environment issue

echo Starting AI Interview Agent...
echo Using Python 3.13...
echo.

cd /d "%~dp0"
C:\Users\admin\AppData\Local\Programs\Python\Python313\python.exe -m streamlit run app.py

pause
