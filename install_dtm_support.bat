@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
where py >nul 2>nul
if %errorlevel%==0 (py -3 -m venv .venv) else (python -m venv .venv)
if errorlevel 1 goto fail
:install
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install --only-binary=:all: -r requirements-dtm.txt
if errorlevel 1 goto fail
echo DTM support installed. Run start_windows.bat.
pause
exit /b 0
:fail
echo Install failed. Use 64-bit Python 3.10 or newer and check your internet connection.
pause
exit /b 1
