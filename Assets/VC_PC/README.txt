GTA Vice City classic PC installer payloads

Required files for the VC PC install action:
- american.gxt -> text/american.gxt
- fronten2.txd -> models/fronten2.txd
- VCPR.adf -> Audio/VCPR.adf

Place all three files in this folder before building the EXE. The build script embeds files only from their game-specific Assets folders; root-level legacy files are not used. The app selects the game installation folder, uses embedded copies automatically, backs up overwritten target files, and attempts rollback if an install step fails.
