GTA Vice City Stories PS2 payloads

Place all required replacements in this folder before building the Windows EXE:
  AMERICAN.GXT -> ISO root /AMERICAN.GXT
  ENGLISH.GXT  -> ISO root /ENGLISH.GXT
  FRENCH.GXT   -> ISO root /FRENCH.GXT
  GERMAN.GXT   -> ISO root /GERMAN.GXT
  SPANISH.GXT  -> ISO root /SPANISH.GXT
  VCPR.VB      -> AUDIO/MUSIC/VCPR.VB
  GAME.DTZ     -> PS2/GAME.DTZ

The build script embeds every present file under Assets/VCS_PS2 into the EXE, preserving this folder path. All seven files must be present and non-empty to enable patching. The installer creates a separate output ISO/CSO and leaves the source image unchanged. This workflow is experimental; test output in PCSX2.
