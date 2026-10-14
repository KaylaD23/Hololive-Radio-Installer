GTA San Andreas PS2 payloads

Place all four required replacement files in this folder before building the EXE:
- FRONTEN1.TXD -> MODELS/FRONTEN1.TXD
- AMERICAN.GXT -> TEXT/AMERICAN.GXT
- TK.PAK -> AUDIO/STREAMS/TK.PAK
- TRAKLKUP.DAT -> AUDIO/CONFIG/TRAKLKUP.DAT

The build script bundles every present file under Assets/SA_PS2 into the EXE. All four files must be present and non-empty to enable patching. The source ISO is never overwritten; this experimental patch should be tested in PCSX2.
