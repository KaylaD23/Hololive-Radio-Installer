GTA Vice City Stories PSP replacement payloads

Required files for the VCS PSP patch action:
- VCPR.AT3 -> PSP_GAME/USRDIR/AUDIO/MUSIC/VCPR.AT3
- ENGLISH.GXT -> PSP_GAME/USRDIR/RUNDATA/ENGLISH.GXT
- GAME.DTZ -> PSP_GAME/USRDIR/RUNDATA/PSP/GAME.DTZ

Place the files here before building the EXE. Every file present under Assets/ is embedded into the one-file EXE with its folder path preserved. All three files must be present and non-empty to enable patching; the build can still run if any game-specific payload is missing.
