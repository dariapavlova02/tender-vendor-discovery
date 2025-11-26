@echo off
setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
set "VENV_DIR=%PROJECT_DIR%\.dashboard-venv"
set "DEPS_SENTINEL=%VENV_DIR%\.deps_installed"

echo [TenderAI] Preparing Tender Vendor AI Dashboard (Windows)
echo.

echo [TenderAI] Checking Python installation...

py -3.11 --version >NUL 2>&1
if %ERRORLEVEL%==0 (
    set "PYTHON_CMD=py -3.11"
    echo [TenderAI] Using Python 3.11
) else (
    py -3.10 --version >NUL 2>&1
    if %ERRORLEVEL%==0 (
        set "PYTHON_CMD=py -3.10"
        echo [TenderAI] Using Python 3.10
    ) else (
        py -3.12 --version >NUL 2>&1
        if %ERRORLEVEL%==0 (
            set "PYTHON_CMD=py -3.12"
            echo [TenderAI] Using Python 3.12
        ) else (
            py -3 --version >NUL 2>&1
            if %ERRORLEVEL%==0 (
                echo [TenderAI] WARNING: Python 3.11 is recommended for best compatibility
                echo [TenderAI] Found other Python 3.x version - attempting to use it
                set "PYTHON_CMD=py -3"
                pause
            ) else (
                echo [TenderAI] Python 3.10, 3.11, or 3.12 required. Install from https://www.python.org/downloads/windows/
                echo [TenderAI] Note: Python 3.11 is recommended for best compatibility
                pause
                exit /b 1
            )
        )
    )
)

if not exist "%PROJECT_DIR%\.env" (
    echo [TenderAI] Missing .env file with API keys. Please add it and rerun.
    pause
    exit /b 1
)

if not exist "%VENV_DIR%" (
    echo [TenderAI] Creating isolated environment at %VENV_DIR%
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if !ERRORLEVEL! NEQ 0 (
        echo [TenderAI] Error: Failed to create virtual environment
        pause
        exit /b 1
    )
) else (
    echo [TenderAI] Checking virtual environment validity...
    if not exist "%VENV_DIR%\Scripts\python.exe" (
        echo [TenderAI] Virtual environment is corrupted, recreating...
        rmdir /s /q "%VENV_DIR%"
        if exist "%DEPS_SENTINEL%" del "%DEPS_SENTINEL%"
        %PYTHON_CMD% -m venv "%VENV_DIR%"
        if !ERRORLEVEL! NEQ 0 (
            echo [TenderAI] Error: Failed to create virtual environment
            pause
            exit /b 1
        )
    )
)

call "%VENV_DIR%\Scripts\activate.bat"
if !ERRORLEVEL! NEQ 0 (
    echo [TenderAI] Error: Failed to activate virtual environment
    pause
    exit /b 1
)

if not exist "%DEPS_SENTINEL%" (
    echo [TenderAI] Installing dashboard dependencies (one-time step)
    "%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
    if !ERRORLEVEL! NEQ 0 (
        echo [TenderAI] Error: Failed to upgrade pip
        pause
        exit /b 1
    )
    
    echo [TenderAI] Installing Poetry...
    "%VENV_DIR%\Scripts\python.exe" -m pip install poetry
    if !ERRORLEVEL! NEQ 0 (
        echo [TenderAI] Error: Failed to install Poetry
        pause
        exit /b 1
    )
    
    echo [TenderAI] Installing project dependencies...
    cd /d "%PROJECT_DIR%"
    "%VENV_DIR%\Scripts\python.exe" -m poetry install
    if !ERRORLEVEL! NEQ 0 (
        echo [TenderAI] Error: Failed to install dependencies
        pause
        exit /b 1
    )
    
    echo [TenderAI] Installing project package...
    "%VENV_DIR%\Scripts\python.exe" -m pip install -e "%PROJECT_DIR%"
    if !ERRORLEVEL! NEQ 0 (
        echo [TenderAI] Error: Failed to install project package
        pause
        exit /b 1
    )
    
    type NUL > "%DEPS_SENTINEL%"
) else (
    echo [TenderAI] Dependencies already installed. Skipping.
)

echo [TenderAI] Starting dashboard -> http://localhost:8501
cd /d "%PROJECT_DIR%"
"%VENV_DIR%\Scripts\python.exe" -m streamlit run src\vendor_ai_agent\dashboard.py
if !ERRORLEVEL! NEQ 0 (
    echo [TenderAI] Error: Failed to start dashboard
    pause
    exit /b 1
)
