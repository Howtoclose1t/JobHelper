@echo off
setlocal
cd /d "%~dp0"
title JobHelper
set "JOBHELPER_PYTHON=%~dp0.venv\Scripts\python.exe"
if exist "%JOBHELPER_PYTHON%" goto ready
if exist "%~dp0..\.venv\Scripts\python.exe" (
    "%~dp0..\.venv\Scripts\python.exe" -c "import streamlit; assert streamlit.__version__ == '1.67.0'" >nul 2>&1
    if not errorlevel 1 (
        set "JOBHELPER_PYTHON=%~dp0..\.venv\Scripts\python.exe"
        goto ready
    )
)
where py >nul 2>&1
if errorlevel 1 (
    python -m venv .venv
) else (
    py -3 -m venv .venv
)
if errorlevel 1 goto failed

:ready
"%JOBHELPER_PYTHON%" -c "import streamlit; assert streamlit.__version__ == '1.67.0'" >nul 2>&1
if errorlevel 1 (
    echo Installing JobHelper dependencies...
    "%JOBHELPER_PYTHON%" -m pip install -r requirements.txt
    if errorlevel 1 goto failed
)
if /i "%~1"=="--check" exit /b 0
"%JOBHELPER_PYTHON%" -m streamlit run app.py --server.showEmailPrompt=false
if errorlevel 1 goto failed
exit /b 0

:failed
echo JobHelper could not start. Check the error above and the setup instructions in README.md.
if /i not "%~1"=="--check" pause
exit /b 1
