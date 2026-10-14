GTA Liberty City Stories PSP replacement payloads

Required files for the LCS PSP patch action:
- KJAH.AT3 -> PSP_GAME/USRDIR/AUDIO/MUSIC/KJAH.AT3
- ENGLISH.GXT -> PSP_GAME/USRDIR/TEXT/ENGLISH.GXT
- SPANISH.GXT -> PSP_GAME/USRDIR/TEXT/SPANISH.GXT
- FRENCH.GXT -> PSP_GAME/USRDIR/TEXT/FRENCH.GXT
- GERMAN.GXT -> PSP_GAME/USRDIR/TEXT/GERMAN.GXT
- ITALIAN.GXT -> PSP_GAME/USRDIR/TEXT/ITALIAN.GXT
- GAME.DTZ -> PSP_GAME/USRDIR/CHK/PSPHR/GAME.DTZ

Place the required files here before building the EXE. Every file present under Assets/ is embedded in the EXE with its folder path preserved. All seven files must be present and non-empty to enable patching. The GUI shows only ISO/CSO input/output fields and patch/safety controls, not replacement-file pickers.
