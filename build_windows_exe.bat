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
echo Build complete. Look for dist\GrandTheftAutoHololiveRadioInstaller.exe.
echo.
echo All files under Assets\ are OPTIONAL at build time.
echo Every file present under Assets\ is bundled individually with its relative folder path preserved: PSP, PC, PS2, and future asset folders.
echo Game tabs whose required payloads are missing will be unavailable until
echo you add the files to the matching Assets subfolder and rebuild.
echo Expected optional payload folders include:
echo   Assets\VCS_PSP: VCPR.AT3, ENGLISH.GXT, GAME.DTZ
echo   Assets\LCS_PSP: KJAH.AT3, ENGLISH.GXT, GAME.DTZ
echo   Assets\VCS_PS2: AMERICAN.GXT, ENGLISH.GXT, FRENCH.GXT, GERMAN.GXT, SPANISH.GXT, VCPR.VB, GAME.DTZ
echo   Assets\III_PS2: AMERICAN.GXT, KJAH.VB, FRONTEND.TXD
echo   Assets\VC_PS2: AMERICAN.GXT, VCPR.VB, FRONTEN2.TXD
echo   Assets\LCS_PS2: KJAH.VB, ENGLISH.GXT, GAME.DTZ
echo   Assets\SA_PS2: FRONTEN1.TXD, AMERICAN.GXT, TK.PAK, TRAKLKUP.DAT
echo   Assets\VC_PC: american.gxt, fronten2.txd, VCPR.adf
echo   Assets\SA_PC: TK, TrakLkup.dat, fronten1.txd, american.gxt
echo PyInstaller temporary build files are placed in your TEMP folder to keep paths short.
echo The PC tab installs them to TEXT/american.gxt, models/fronten2.txd, audio/VCPR.adf.
echo All files under Assets are recursively bundled when present, including Assets\III_PS2.
echo Existing ISO/CSO outputs can be overwritten after confirmation; input images are protected.
echo Tabs requiring missing payloads remain visible but their action is disabled.
pause
exit /b 0
:failed
echo.
echo Build failed. Check the error above and try again.
pause
exit /b 1
