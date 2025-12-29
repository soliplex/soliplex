@echo off
setlocal enabledelayedexpansion

echo Building Soliplex Ingester UI...

REM Navigate to UI directory
cd ui

REM Install dependencies
echo Installing dependencies...
call npm install
if errorlevel 1 (
    echo Failed to install dependencies
    exit /b 1
)

REM Build the UI
echo Building production UI...
call npm run build
if errorlevel 1 (
    echo Failed to build UI
    exit /b 1
)

REM Copy build artifacts to server static directory
echo Copying build artifacts...
if not exist "..\src\soliplex\ingester\server\static" mkdir "..\src\soliplex\ingester\server\static"
xcopy /E /I /Y build\* "..\src\soliplex\ingester\server\static\"
if errorlevel 1 (
    echo Failed to copy build artifacts
    exit /b 1
)

echo UI build complete!
echo UI artifacts copied to src\soliplex\ingester\server\static\

endlocal
