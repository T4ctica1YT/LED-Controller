@echo off
REM Double-click this file (or run it in a terminal) to check for a
REM working Python install and, if you confirm, install/update
REM everything the LED Controller app needs on Windows.
REM
REM Windows installs can expose Python under a few different command
REM names depending on how it was installed (python.org installer, the
REM py launcher, Microsoft Store, etc). This script checks all the
REM common ones instead of assuming just "python".
REM
REM setup.py itself lives in the "Setup" subfolder next to this script.

setlocal enabledelayedexpansion

set "PYTHON_CMD="
set "MIN_MAJOR=3"
set "MIN_MINOR=9"
set "DOWNLOAD_URL=https://www.python.org/downloads/"

REM 1) Try the "py" launcher (installed by python.org's installer by
REM    default, and the most reliable way to find Python on Windows)
py -3 --version >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
    goto :found
)

REM 2) Try a plain "python" on PATH
python --version >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=python"
    goto :found
)

REM 3) Try "python3" on PATH
python3 --version >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=python3"
    goto :found
)

echo.
echo No Python installation was found on this computer.
echo (Checked for "py", "python", and "python3".)
echo This app needs Python %MIN_MAJOR%.%MIN_MINOR% or newer.
echo.
set /p DOWNLOAD_PY="Would you like to open the Python download page now? [Y/n] "
if /i "%DOWNLOAD_PY%"=="n" (
    echo You can install Python later from %DOWNLOAD_URL%
    pause
    exit /b 1
)
start "" "%DOWNLOAD_URL%"
echo Opened %DOWNLOAD_URL% in your browser.
echo Install Python - any 3.9 or newer version works fine with this app,
echo so you don't need to chase the very latest release.
echo Once it's installed, run this script again.
pause
exit /b 1

:found
echo Found a Python installation via: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

REM Check whether it meets the minimum supported version (3.9+)
%PYTHON_CMD% -c "import sys; sys.exit(0 if sys.version_info >= (%MIN_MAJOR%, %MIN_MINOR%) else 1)" >nul 2>nul
if not %errorlevel%==0 (
    echo.
    echo This Python installation looks older than %MIN_MAJOR%.%MIN_MINOR%.
    echo This app needs Python %MIN_MAJOR%.%MIN_MINOR% or newer.
    echo.
    set /p DOWNLOAD_PY="Would you like to open the Python download page to get a newer version? [Y/n] "
    if /i "!DOWNLOAD_PY!"=="n" (
        echo Continuing with the current Python installation - some things may not work correctly.
    ) else (
        start "" "%DOWNLOAD_URL%"
        echo Opened %DOWNLOAD_URL% in your browser.
        echo Any 3.9 or newer version works fine with this app - you don't need
        echo the very latest release, just something at or above %MIN_MAJOR%.%MIN_MINOR%.
        echo Install it, then run this script again.
        pause
        exit /b 1
    )
) else (
    echo Python version meets the minimum requirement of %MIN_MAJOR%.%MIN_MINOR%+.
)

set "SETUP_SCRIPT=%~dp0Setup\setup.py"
if not exist "%SETUP_SCRIPT%" (
    echo.
    echo ERROR: Could not find setup.py at:
    echo   %SETUP_SCRIPT%
    echo Make sure the "Setup" folder is next to this script.
    pause
    exit /b 1
)

set /p RUN_SETUP="Run setup.py now to install/update dependencies? [Y/n] "
if /i "%RUN_SETUP%"=="n" (
    echo Skipping setup.py. You can run it later with:
    echo   %PYTHON_CMD% "%SETUP_SCRIPT%"
    pause
    exit /b 0
)

%PYTHON_CMD% "%SETUP_SCRIPT%" %*

echo.
pause
