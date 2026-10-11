@echo off
setlocal
cd /d "%~dp0"
echo ================================================================
echo   Building GTA Vice City ^& Vice City Stories Hololive Installer
echo ================================================================
echo.
if not exist "VCPR.VB" (
  echo ERROR: Required payload VCPR.VB was not found in this folder.
  echo Obtain the matching audio payload from the project's release, if available,
  echo and copy VCPR.VB next to this build script. The large audio payload is
  echo intentionally not tracked in the source repository.
  echo.
  pause
  exit /b 1
)
where py >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.10 or newer from https://www.python.org/downloads/windows/
  echo During installation, enable "Add python.exe to PATH".
  pause
  exit /b 1
)
py -m pip install --upgrade pip pyinstaller
if errorlevel 1 goto failed
py -m PyInstaller --clean --noconfirm --onefile --windowed --name "GTA Vice City & Vice City Stories Hololive Radio Installer" --icon "hololive_radio_icon.ico" --add-data "VCPR.VB;." --add-data "hololive_radio_icon.ico;." --add-data "0865a12018fbd34f84b2c05c.png;." "GTA_Vice_City_Vice_City_Stories_Hololive_Radio_Installer.py"
if errorlevel 1 goto failed
echo.
echo Build complete: dist\GTA Vice City ^& Vice City Stories Hololive Radio Installer.exe
echo The EXE includes the replacement audio payload and Hololive application icon.
echo NOTE: This build currently supports GTA: Vice City Stories PS2 only; Vice City is not supported yet.
pause
exit /b 0
:failed
echo.
echo Build failed. Check the error above and try again.
pause
exit /b 1
