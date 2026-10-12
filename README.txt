# Grand Theft Auto Hololive Radio Installer

A Windows Tkinter GUI utility with tabs ordered as **GTA VCS PS2**, **GTA San Andreas PS2**, **GTA LCS PS2**, **GTA VCS PSP**, **GTA LCS PSP**, **GTA Vice City PC**, **GTA Vice City PS2 [Coming Soon]**, and **GTA San Andreas PC**. VCS PS2, San Andreas PS2, VCS PSP, LCS PSP, and LCS PS2 are experimental ISO/CSO patchers; Vice City PC and San Andreas PC install their bundled files into an existing PC game folder. Only classic Vice City PS2 remains blank and disabled as Coming Soon.

**PS2 support status:** the GTA VCS PS2 and GTA LCS PS2 tabs are experimental patchers that check `SYSTEM.CNF` against recognized disc serials before changing anything. Classic **GTA: Vice City (PS2) is not supported** by the VCS PS2 tab. A separate **GTA Vice City PS2 [Coming Soon]** tab is present but blank and disabled; it does not patch or modify ISOs.

## Portable game-specific asset folders (development checkpoint)

The project includes an optional `Assets` folder split by game/platform. Every game payload file is optional at build time; most payloads are embedded when present, but VCS_PS2 and SA_PS2 payloads deliberately remain local beside the built EXE. If a game’s required set is incomplete, only that game’s patch/install action is disabled and the GUI remains usable. Vice City PC also accepts its three legacy root-level files. The GUI does not ask the user to browse for individual PC mod files; the user selects only the PC game folder and clicks **Install PC Files**.

```text
Assets/
├── VCS_PS2/   # five root GXT files, VCPR.VB, GAME.DTZ (local PS2 payloads)
├── SA_PS2/    # FRONTEN1.TXD, AMERICAN.GXT, TK.PAK, TRAKLKUP.DAT (local PS2 payloads)
├── VCS_PSP/   # optional payloads; all three needed to enable VCS PSP patching
├── LCS_PSP/   # optional payloads; all three needed to enable LCS PSP patching
├── VC_PC/     # american.gxt / fronten2.txd / VCPR.adf
├── VC_PS2/    # future support; not currently implemented
└── SA_PC/     # TK station: TK / TrakLkup.dat / fronten1.txd / american.gxt
```

The VCS PSP tab verifies the recognized GTA: Vice City Stories disc ID in `PSP_GAME/PARAM.SFO` before applying all three bundled assets to their matching ISO entries. `Assets/VCS_PSP/VCPR.AT3`, `ENGLISH.GXT`, and `GAME.DTZ` are all required. These files are optional when building. Place your local copies there on the PC that builds the EXE; all three must be present to enable this patch action, and any present files are embedded. The tab has no replacement-file pickers and displays only the Input ISO/CSO and Output ISO/CSO paths plus the usual patch/safety controls. The patcher writes a separate output ISO or CSO, refuses to overwrite the source, relocates replacements that exceed the original file extent to new sector-aligned space at the end of the ISO, updates the ISO9660 extent/size/volume-space fields, and rejects unsupported interleaved/multi-extent files. It supports ISO images and CSO v1 or v2 images that contain a plain 2048-byte-sector ISO9660 filesystem. This PSP path is experimental and has not been tested in PPSSPP or on hardware.

## GTA Liberty City Stories PSP tab

Place all three local files in `Assets/LCS_PSP/` on the Windows PC used to build the EXE:

| Payload file | ISO destination |
|---|---|
| `KJAH.AT3` | `PSP_GAME/USRDIR/AUDIO/MUSIC/KJAH.AT3` |
| `ENGLISH.GXT` | `PSP_GAME/USRDIR/TEXT/ENGLISH.GXT` |
| `GAME.DTZ` | `PSP_GAME/USRDIR/CHK/PSPHR/GAME.DTZ` |

These files are optional when building. All three must be present to enable this patch action; any present files are embedded into the one-file EXE. The LCS PSP tab does not show payload pickers. It verifies the recognized LCS PSP disc ID in `PSP_GAME/PARAM.SFO` and writes a separate output ISO or CSO without modifying the input. Replacements larger than their original extents are relocated to new sector-aligned space and ISO9660 metadata is updated. This is experimental and has not been verified in PPSSPP; test the result with a copy of your own game image.

## GTA Vice City PC tab

Select **GTA Vice City PC**, click **Locate…**, and select the main game installation folder. The folder must contain `gta-vc.exe` and the `text`, `models`, and `Audio` directories (folder-name matching is case-insensitive).

To enable Vice City PC installation, place these three files in `Assets/VC_PC/` before building (they are optional for building the GUI):

| Payload file | Destination in the selected PC game folder |
|---|---|
| `american.gxt` | `text/american.gxt` |
| `fronten2.txd` | `models/fronten2.txd` |
| `VCPR.adf` | `Audio/VCPR.adf` |

Older projects may still keep those three Vice City payload files beside `build_windows_exe.bat`; the build script accepts that legacy placement and embeds them under `Assets/VC_PC` in the EXE. The GUI only displays the game-folder chooser and **Install PC Files** button. It loads the bundled assets automatically, backs up existing target files, and attempts rollback if installation fails.

## GTA San Andreas PC tab

Select **GTA San Andreas PC**, click **Locate…**, and choose the main game folder containing `gta_sa.exe`, `audio`, `models`, and `text`. Before building, place all four local mod files inside `Assets/SA_PC/`:

| Payload file | Destination |
|---|---|
| `TK` | `audio/streams/TK` |
| `TrakLkup.dat` | `audio/CONFIG/TrakLkup.dat` |
| `fronten1.txd` | `models/fronten1.txd` |
| `american.gxt` | `text/american.gxt` |

The `TK` stream and `TrakLkup.dat` must come from the same mod package. The build script rejects `TrakLkup.dat` if it does not contain complete 12-byte lookup records. The EXE bundles the files automatically; the GUI shows only the PC install folder and **Install PC Files** button. It creates timestamped backups of overwritten files and attempts rollback if installation fails.

PC mod payloads are user-supplied and are not included in this project ZIP. Only add files you are entitled to use and distribute.

## Experimental GTA San Andreas PS2 ISO workflow

The **GTA San Andreas PS2** tab mirrors the VCS PS2 ISO/CSO controls. Keep these four user-supplied files in `Assets/SA_PS2/` beside `Grand Theft Auto Hololive Radio Installer.py` or beside `GrandTheftAutoHololiveRadioInstaller.exe`; they are not embedded into the EXE:

| Local file | ISO destination |
|---|---|
| `FRONTEN1.TXD` | `MODELS/FRONTEN1.TXD` |
| `AMERICAN.GXT` | `TEXT/AMERICAN.GXT` |
| `TK.PAK` | `AUDIO/STREAMS/TK.PAK` |
| `TRAKLKUP.DAT` | `AUDIO/CONFIG/TRAKLKUP.DAT` |

All four files must exist and be non-empty for patching to be enabled. The tab checks `SYSTEM.CNF` against recognized San Andreas PS2 serials, validates each target entry, and writes a separate ISO/CSO copy without overwriting the source. Replacement files larger than the original extents are relocated to appended sectors and ISO9660 metadata is updated. ISO and CSO v1 are supported; CSO v2 is experimental. Test the output in PCSX2 before use.

## Experimental GTA Vice City Stories PS2 ISO workflow

The VCS PS2 tab replaces seven files in a copy of a supported GTA: Vice City Stories PS2 ISO/CSO. All seven are loaded from the local `Assets/VCS_PS2/` folder beside `Grand Theft Auto Hololive Radio Installer.py` or beside the built `GrandTheftAutoHololiveRadioInstaller.exe`; they are deliberately NOT bundled into the EXE:

| Local file | ISO destination |
|---|---|
| `AMERICAN.GXT` | ISO root `/AMERICAN.GXT` |
| `ENGLISH.GXT` | ISO root `/ENGLISH.GXT` |
| `FRENCH.GXT` | ISO root `/FRENCH.GXT` |
| `GERMAN.GXT` | ISO root `/GERMAN.GXT` |
| `SPANISH.GXT` | ISO root `/SPANISH.GXT` |
| `VCPR.VB` | `AUDIO/MUSIC/VCPR.VB` |
| `GAME.DTZ` | `PS2/GAME.DTZ` |

All seven files must be present and non-empty for the patch button to enable. The app validates `SYSTEM.CNF` against known VCS PS2 serials; classic GTA Vice City PS2 and unknown serials are rejected. Oversized replacements are relocated to new ISO sectors and ISO9660 metadata is updated. ISO/CSO v1 and experimental CSO v2 are supported when the image contains a plain 2048-byte-sector ISO9660 filesystem. The source image is left unchanged. The patch is experimental; test in PCSX2.

## Build on Windows

1. Install Python 3.10 or newer from <https://www.python.org/downloads/windows/>. Enable **Add Python to PATH**.
2. On the PC that will build the EXE, place the three VCS PSP files in `Assets/VCS_PSP/` (`VCPR.AT3`, `ENGLISH.GXT`, `GAME.DTZ`) and the three LCS PSP files in `Assets/LCS_PSP/` (`KJAH.AT3`, `ENGLISH.GXT`, `GAME.DTZ`). For VCS PS2, keep the seven files listed above in `Assets/VCS_PS2/`; they stay beside the EXE and are not embedded. For San Andreas PS2, keep `FRONTEN1.TXD`, `AMERICAN.GXT`, `TK.PAK`, and `TRAKLKUP.DAT` in `Assets/SA_PS2/`; they also stay beside the EXE and are not embedded.
3. Place the GTA: Vice City PC files `american.gxt`, `fronten2.txd`, and `VCPR.adf` in `Assets/VC_PC/`. For backwards compatibility, these three files may instead be beside `build_windows_exe.bat`; the build script embeds them under `Assets/VC_PC` in the EXE.
4. Place the GTA: San Andreas PC files `TK`, `TrakLkup.dat`, `fronten1.txd`, and `american.gxt` in `Assets/SA_PC/`. Make sure TK and TrakLkup.dat are a matching pair and the latter is a multiple of 12 bytes.
5. Run `build_windows_exe.bat`. The build script checks that all listed payloads exist and are non-empty, checks the TrakLkup.dat record size, and stops with a clear error if required files are missing.
6. Find the generated EXE at `dist/GrandTheftAutoHololiveRadioInstaller.exe`.

A Windows EXE must be built on Windows. The build scripts use the short output name `GrandTheftAutoHololiveRadioInstaller.exe` and a short temporary build path to avoid the Windows resource-update path-length error reported during an earlier build. Running the Python script directly is also possible:

```powershell
py "Grand Theft Auto Hololive Radio Installer.py"
```

## License and assets

The **source code** is licensed under **GNU General Public License v3.0 only**; see [`LICENSE`](LICENSE).

The PNG/ICO application artwork, Hololive materials, mod payload files, GTA-related assets, trademarks and audio are not automatically relicensed by the source-code license. Check ownership and redistribution permissions before publishing or distributing them. The bundled `Assets/VCS_PSP/VCPR.AT3` is a user-provided audio payload; ensure you have the rights to distribute it. Do not add the three PC files or `VCPR.VB` to Git history unless you have the rights to redistribute them; keep them as local build inputs.

## Current support

- **GTA: San Andreas (PS2):** experimental ISO/CSO patcher for FRONTEN1.TXD, AMERICAN.GXT, TK.PAK, and TRAKLKUP.DAT; all four payloads stay local in Assets/SA_PS2 and are not embedded in the EXE.
- **GTA: Vice City Stories (PS2):** experimental ISO/CSO patcher for five root-level language GXT files, `AUDIO/MUSIC/VCPR.VB`, and `PS2/GAME.DTZ`; all seven payloads remain local in `Assets/VCS_PS2` and are not embedded in the EXE.
- **GTA: Vice City (classic PC):** installs the three assets above.
- **GTA: Vice City (PS2):** not implemented.
- **GTA: Vice City Stories (PSP):** experimental ISO/CSO patcher for all three bundled files `VCPR.AT3`, `ENGLISH.GXT`, and `GAME.DTZ`. All three are needed to enable patching, but are optional at EXE-build time. The tab has no replacement-file pickers; the input ISO is preserved and a separate output ISO or CSO is created.
- **GTA: Liberty City Stories (PSP):** experimental ISO/CSO patcher for KJAH.AT3, ENGLISH.GXT, and GAME.DTZ. All three local files are needed to enable patching but are optional at EXE-build time; present files are embedded into the one-file EXE and applied automatically to the configured ISO targets. The tab shows only Input ISO/CSO / Output ISO/CSO path fields and standard patch/safety controls.
- **GTA: San Andreas (PC):** Enabled PC installer for the bundled TK station files. It expects a valid installation folder containing `gta_sa.exe`, `audio/streams`, `audio/CONFIG`, `models`, and `text`.


## GTA Vice City PS2 placeholder

The GTA Vice City PS2 tab is deliberately blank and disabled. No classic Vice City PS2 ISO modification is implemented. It will remain disabled until the game-specific ISO layout and a safe patch workflow have been validated.

Optional GTA VCS PSP payloads
Place VCPR.AT3, ENGLISH.GXT, and GAME.DTZ in Assets\VCS_PSP if you want to enable PSP patching.
These files are optional at build time. The PSP patch action is enabled only when all three are present and non-empty; present files are bundled into the EXE. GTA LCS PSP is enabled and requires KJAH.AT3, ENGLISH.GXT, and GAME.DTZ in Assets/LCS_PSP on the PC used to build the EXE.


## Latest UI text update

The application window and in-app heading are titled **Grand Theft Auto Hololive Radio Installer**. The GTA VCS PS2 action button reads **Create Patched PS2 ISO**. The button command and patching behavior are unchanged.

Troubleshooting “Permission denied” during image patching
The patcher creates a separate output image. It does not preserve a source ISO's read-only file attribute on the new output, so a read-only source should no longer cause the output copy to fail when opened for writing. If Windows still denies access, choose an output folder you can write to (for example, Documents) and close any program that may be holding the output file open.

## GUI Customizer (separate application)

Run `GUI Customizer.py` with Python 3.10+ to edit the installer window title, heading, dimensions, theme, accent colour, font size, tab labels, and tab visibility. Save the settings to `gui_customization.json` in the same folder as the source app or built EXE, then restart the installer. The customizer changes visual settings only; it does not change patching rules, supported formats, or disc-ID safeguards. See `GUI-CUSTOMIZER-README.txt` for details.


GTA Liberty City Stories PS2 tab
-------------------------------
The LCS PS2 tab mirrors the existing PS2 ISO/CSO controls and is configurable in GUI Customizer. It verifies recognized LCS PS2 serials and replaces Assets/LCS_PS2/KJAH.VB → AUDIO/MUSIC/KJAH.VB, ENGLISH.GXT → TEXT/ENGLISH.GXT, and GAME.DTZ → CHK/PS2/GAME.DTZ. All three payloads are required to enable patching. Larger replacement files are relocated to new ISO sectors and directory entries are updated. This patch is experimental and has not been verified in-game.


## LCS PS2 assets

Place `KJAH.VB`, `ENGLISH.GXT`, and `GAME.DTZ` in `Assets/LCS_PS2`. These map to `AUDIO/MUSIC/KJAH.VB`, `TEXT/ENGLISH.GXT`, and `CHK/PS2/GAME.DTZ`. The build script embeds any files present under `Assets`; missing payloads disable only the corresponding patch button.


Asset path troubleshooting (updated):
For VCS PS2 and San Andreas PS2, the app now searches Assets/<game folder> beside the running app, one folder above the app (useful when the EXE is in dist/), beside the source script, one folder above the source script, and the current working directory. The folder must be named exactly Assets\SA_PS2 or Assets\VCS_PS2, with the expected filenames. Restart the installer after moving files.
