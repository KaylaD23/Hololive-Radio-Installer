@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0Temp" mkdir "%~dp0Temp"
set "TEMP=%~dp0Temp"
set "TMP=%~dp0Temp"
set "PIP_CACHE_DIR=%~dp0Temp\pip-cache"
set "PYTHONPYCACHEPREFIX=%~dp0Temp\pycache"
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
py -m pip install --upgrade pip pyinstaller pillow
if errorlevel 1 goto failed
py build_windows_exe.py
if errorlevel 1 goto failed
echo.
echo Build complete. Look for dist\GrandTheftAutoHololiveRadioInstaller.exe.
echo The Hololive icon is embedded in the EXE and assigned to the Windows taskbar.
echo The banner scales proportionally to the available content width at every window size.
echo A custom banner selected in GUI Customizer is embedded when listed in gui_customization.json.
echo There is no lower-right corner watermark in this source build.
echo.
echo All files under Assets\ are OPTIONAL at build time.
echo Every file present under Assets\ is bundled individually with its relative folder path preserved: PSP, PC, PS2 (including GTA III), and future asset folders.
echo Game tabs whose required payloads are missing will be unavailable until
echo you add the files to the matching Assets subfolder and rebuild.
echo Expected optional payload folders include:
echo   Assets\VCS_PSP: VCPR.AT3, ENGLISH.GXT, GAME.DTZ
echo   Assets\LCS_PSP: KJAH.AT3, ENGLISH.GXT, GAME.DTZ
echo   Assets\III_PS2: AMERICAN.GXT, FRONTEND.TXD, KJAH.VB ^(GTA III PS2 tab^)
echo   Assets\VCS_PS2: AMERICAN.GXT, ENGLISH.GXT, FRENCH.GXT, GERMAN.GXT, SPANISH.GXT, VCPR.VB, GAME.DTZ
echo   Assets\VC_PS2: AMERICAN.GXT, VCPR.VB, FRONTEN2.TXD
echo   Assets\LCS_PS2: KJAH.VB, ENGLISH.GXT, GAME.DTZ
echo   Assets\SA_PS2: FRONTEN1.TXD, AMERICAN.GXT, TK.PAK, TRAKLKUP.DAT
echo   Assets\VC_PC: american.gxt, fronten2.txd, VCPR.adf
echo   Assets\SA_PC: TK, TrakLkup.dat, fronten1.txd, american.gxt
echo   Assets\VC_DE: 500-HololiveRadio_P.pak - installs into GTA San Andreas - The Definitive Edition
echo   Assets\SA_DE: 500-HololiveRadio_P.pak - installs into GTA Vice City - The Definitive Edition
echo Definitive Edition destination: Gameface\Content\Paks\~mods\500-HololiveRadio_P.pak
echo All build temporary files and PyInstaller intermediates go under the included Temp folder.
echo The PC tab installs them to TEXT/american.gxt, models/fronten2.txd, audio/VCPR.adf.
echo All files under Assets are recursively bundled when present.
echo Tabs requiring missing payloads remain visible but their action is disabled.
pause
exit /b 0
:failed
echo.
echo Build failed. Check the error above and try again.
pause
exit /b 1
