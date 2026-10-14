GTA Liberty City Stories PS2 replacement payloads

Required files for the LCS PS2 patch action:
- KJAH.VB -> AUDIO/MUSIC/KJAH.VB
- ENGLISH.GXT -> TEXT/ENGLISH.GXT
- GAME.DTZ -> CHK/PS2/GAME.DTZ

Put these files in this folder before building. The build script embeds each file present under Assets/ into the EXE, preserving the game-specific directory. All three files must be present and non-empty to enable patching. Larger replacements are relocated to new ISO sectors and the ISO directory entries are updated.
