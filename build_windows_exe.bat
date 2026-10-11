@echo off
setlocal
cd /d "%~dp0"
echo ================================================================
echo   Building Grand Theft Auto Hololive Radio Installer
echo ================================================================
echo.
where py >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.10 or newer from https://www.python.org/downloads/windows/
  echo During installation, enable "Add python.exe to PATH".
  pause
  exit /b 1
)
py -m pip install --upgrade pip pyinstaller
if errorlevel 1 goto failed
py build_windows_exe.py
if errorlevel 1 goto failed
echo.
echo Build complete. Look for dist\HololiveRadioInstaller.exe.
echo.
echo For a self-contained PC installer, put these three files in Assets\VC_PC or beside this BAT:
echo   american.gxt
echo   fronten2.txd
echo   VCPR.adf
echo The build script checks both locations and embeds found files.
echo Required VCS PSP assets must be present in Assets\VCS_PSP on this PC:
echo   VCPR.AT3
echo   ENGLISH.GXT
echo   GAME.DTZ
echo The build script stops if any of those three files is missing or empty.
echo All three are embedded in the EXE and patched automatically.
echo The VCS PSP tab only asks for Input ISO and Output ISO; its files are embedded.
echo Required LCS PSP assets must also be present in Assets\LCS_PSP on this PC:
echo   KJAH.AT3
echo   ENGLISH.GXT
echo   GAME.DTZ
echo The build script stops if any of the three LCS files is missing or empty.
echo All three are embedded in the EXE and patched automatically.
echo The LCS PSP tab only asks for Input ISO and Output ISO; no replacement-file pickers are shown.
echo PyInstaller temporary build files are placed in your TEMP folder to keep paths short.
echo The PC tab installs them to TEXT/american.gxt, models/fronten2.txd, audio/VCPR.adf.
echo VCS PS2 ISO support requires VCPR.VB; classic GTA Vice City PS2 is not supported by this tab.
echo GTA Vice City PS2 and GTA SA PC tabs remain disabled as Coming Soon.
pause
exit /b 0
:failed
echo.
echo Build failed. Check the error above and try again.
pause
exit /b 1
