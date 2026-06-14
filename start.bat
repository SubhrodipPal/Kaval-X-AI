@echo off
title KAVAL-X Advanced Fraud Detection Platform
color 0A

echo.
echo  ██╗  ██╗ █████╗ ██╗   ██╗ █████╗ ██╗     ██╗  ██╗
echo  ██║ ██╔╝██╔══██╗██║   ██║██╔══██╗██║     ╚██╗██╔╝
echo  █████╔╝ ███████║██║   ██║███████║██║      ╚███╔╝
echo  ██╔═██╗ ██╔══██║╚██╗ ██╔╝██╔══██║██║      ██╔██╗
echo  ██║  ██╗██║  ██║ ╚████╔╝ ██║  ██║███████╗██╔╝ ██╗
echo  ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
echo.
echo  Advanced Fraud Detection ^& Banking Security
echo  ─────────────────────────────────────────────
echo.

:: Check if Node.js is installed
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo  [ERROR] Node.js is not installed or not in PATH.
    echo  Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

:: Check if dependencies are installed
if not exist "%~dp0frontend\node_modules" (
    echo  [INFO] Installing frontend dependencies...
    echo.
    cd /d "%~dp0frontend"
    call npm install
    if %errorlevel% neq 0 (
        echo  [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
    echo.
    echo  [OK] Dependencies installed successfully.
    echo.
)

:: Start the frontend dev server
echo  [START] Launching Kaval-X Frontend...
echo.
echo  Dashboard:    http://localhost:3000
echo  Graph View:   http://localhost:3000/graph
echo  AMADP Debate: http://localhost:3000/amadp
echo  Biometrics:   http://localhost:3000/biometrics
echo  Compliance:   http://localhost:3000/compliance
echo  OSINT Feed:   http://localhost:3000/osint
echo.
echo  ─────────────────────────────────────────────
echo  Press Ctrl+C to stop the server.
echo  ─────────────────────────────────────────────
echo.

cd /d "%~dp0frontend"
start "" http://localhost:3000
call npm run dev
