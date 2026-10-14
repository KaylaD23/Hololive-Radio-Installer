# Grand Theft Auto Hololive Radio Installer

A compact Windows Tkinter application with a light-cyan Hololive radio theme. The installer supports the following game-specific workflows: experimental ISO/CSO patchers for GTA III PS2, GTA Vice City Stories PS2, San Andreas PS2, Liberty City Stories PS2, Vice City Stories PSP, Liberty City Stories PSP, and classic Vice City PS2; plus bundled-file installers for classic Vice City PC and San Andreas PC, and optional Definitive Edition .pak installers for Vice City and San Andreas.

The banner now scales continuously at every window size: `hololive_radio_banner_fullscreen.png` is the preferred high-resolution source and is resized to the actual available banner-container width on every resize, preserving its aspect ratio. There is no compact/maximized switching threshold, so intermediate window sizes are handled the same way and the artwork does not jump between variants. `hololive_radio_banner_default.png` and `hololive_radio_banner.png` remain bundled as compatibility fallbacks. Pillow is required for dynamic resizing and is installed/bundled by the Windows build process. The GUI does not load or draw a lower-right city/watermark image.

## Game-specific assets and EXE bundling

**All game payloads belong under `Assets/<game folder>/`.** The Windows build script embeds every file found under `Assets/` into the one-file EXE while preserving the folder structure. Payload files are not loaded from beside the executable at runtime and are not copied across game folders. File/folder name matching is case-insensitive, but duplicate filenames are resolved only within the selected game's folder. If a required payload is missing or empty, only the matching install/patch action is disabled.

```text
Assets/
├── III_PS2/  # AMERICAN.GXT, FRONTEND.TXD, KJAH.VB (GTA III PS2 patch tab; KJAH.VB must be supplied)
├── VCS_PS2/  # AMERICAN.GXT, ENGLISH.GXT, FRENCH.GXT, GERMAN.GXT, SPANISH.GXT, VCPR.VB, GAME.DTZ
├── SA_PS2/   # FRONTEN1.TXD, AMERICAN.GXT, TK.PAK, TRAKLKUP.DAT
├── LCS_PS2/  # KJAH.VB, ENGLISH.GXT, GAME.DTZ
├── VC_PS2/   # AMERICAN.GXT, VCPR.VB, FRONTEN2.TXD
├── VCS_PSP/  # VCPR.AT3, ENGLISH.GXT, GAME.DTZ
├── LCS_PSP/  # KJAH.AT3, ENGLISH.GXT, SPANISH.GXT, FRENCH.GXT, GERMAN.GXT, ITALIAN.GXT, GAME.DTZ
├── VC_PC/    # american.gxt, fronten2.txd, VCPR.adf
├── SA_PC/    # TK, TrakLkup.dat, fronten1.txd, american.gxt (+ optional language GXT variants)
├── VC_DE/    # 500-HololiveRadio_P.pak -> GTA San Andreas - The Definitive Edition
└── SA_DE/    # 500-HololiveRadio_P.pak -> GTA Vice City - The Definitive Edition
```

The build includes **all files actually present** in every Assets subfolder, including language GXT variants, `FRONTEND.TXD`, `FRONTEN1.TXD`, `FRONTEN2.TXD`, and `TrakLkup.dat` / `TRAKLKUP.DAT`. Files named `TK` and `TK.PAK` will also be bundled when placed in their respective `SA_PC` and `SA_PS2` folders; they are not present in this supplied project snapshot. The build does not invent missing payloads. This snapshot also lacks GTA III PS2 `Assets/III_PS2/KJAH.VB`, plus `Assets/VCS_PS2/VCPR.VB`, `Assets/SA_PS2/TK.PAK`, `Assets/LCS_PS2/KJAH.VB`, `Assets/VC_PS2/VCPR.VB`, `Assets/VCS_PSP/VCPR.AT3`, `Assets/LCS_PSP/KJAH.AT3`, and `Assets/VC_PC/VCPR.adf`. Add any missing, licensed payloads to their matching game folders before building to enable those actions.

### Payloads required by each action

| Game / platform | Required payloads in its `Assets` folder | Target |
|---|---|---|
| GTA: Vice City Stories (PS2) | `AMERICAN.GXT`, `ENGLISH.GXT`, `FRENCH.GXT`, `GERMAN.GXT`, `SPANISH.GXT`, `VCPR.VB`, `GAME.DTZ` in `Assets/VCS_PS2` | ISO root language files, `AUDIO/MUSIC/VCPR.VB`, `PS2/GAME.DTZ` |
| GTA: San Andreas (PS2) | `FRONTEN1.TXD`, `AMERICAN.GXT`, `TK.PAK`, `TRAKLKUP.DAT` in `Assets/SA_PS2` | `MODELS`, `TEXT`, `AUDIO/STREAMS`, `AUDIO/CONFIG` |
| GTA: Liberty City Stories (PS2) | `KJAH.VB`, `ENGLISH.GXT`, `GAME.DTZ` in `Assets/LCS_PS2` | `AUDIO/MUSIC/KJAH.VB`, `TEXT/ENGLISH.GXT`, `CHK/PS2/GAME.DTZ` |
| GTA: Vice City (PS2) | `AMERICAN.GXT`, `VCPR.VB`, `FRONTEN2.TXD` in `Assets/VC_PS2` | `TEXT/AMERICAN.GXT`, `AUDIO/MUSIC/VCPR.VB`, `MODELS/FRONTEN2.TXD` |
| GTA: Vice City Stories (PSP) | `VCPR.AT3`, `ENGLISH.GXT`, `GAME.DTZ` in `Assets/VCS_PSP` | `PSP_GAME/USRDIR/AUDIO/MUSIC/VCPR.AT3`, `RUNDATA/ENGLISH.GXT`, `RUNDATA/PSP/GAME.DTZ` |
| GTA: Liberty City Stories (PSP) | `KJAH.AT3`, five language GXT files, and `GAME.DTZ` in `Assets/LCS_PSP` | `PSP_GAME/USRDIR/AUDIO/MUSIC`, `TEXT`, and `CHK/PSPHR` |
| GTA: Vice City (classic PC) | `american.gxt`, `fronten2.txd`, `VCPR.adf` in `Assets/VC_PC` | `text`, `models`, `Audio` |
| GTA: San Andreas (PC) | `TK`, `TrakLkup.dat`, `fronten1.txd`, `american.gxt` in `Assets/SA_PC` | `audio/streams`, `audio/CONFIG`, `models`, `text` |

PC install actions ask for the game installation folder only; they use the bundled payloads, back up files they overwrite, and attempt rollback if an install step fails. `TK` and `TrakLkup.dat` must be from the same San Andreas mod package. `TrakLkup.dat` is checked for complete 12-byte lookup records.

All ISO/CSO patchers write a separate output image and leave the input image unchanged. They validate the game's disc identifiers and ISO entries; larger replacement files may be relocated to new sectors with ISO9660 metadata updated. These workflows are experimental and should be tested in PCSX2 or PPSSPP before use.

## Build on Windows

1. Install Python 3.10 or newer from <https://www.python.org/downloads/windows/> and enable **Add Python to PATH**. The build script installs Pillow and PyInstaller automatically.
2. Put each available payload in its matching `Assets/<game folder>/` directory. Names are resolved case-insensitively; keep duplicate filenames in their respective game folders.
3. Run `build_windows_exe.bat`.
4. Find the resulting EXE at `dist/GrandTheftAutoHololiveRadioInstaller.exe`.

The included top-level `Temp/` folder is used for Python temporary files, the pip cache, PyInstaller work files, and generated spec files during the build. The final EXE is written to `dist/`. Every file under `Assets/` is added individually to the EXE with the original relative directory structure intact. Missing payloads are reported by the build diagnostics and leave only the corresponding action disabled in the GUI.

You can also run the source GUI directly with `py "Grand Theft Auto Hololive Radio Installer.py"` (install Pillow first with `py -m pip install pillow` for dynamic banner scaling). Use `GUI Customizer.py` to alter the window title, dimensions, theme, accent colour, font size, banner options, tab visibility/labels, and the left-to-right tab order via `gui_customization.json`. In the Tab order section, select a game and use Move up / Move down; Reset order restores the default sequence.

## License and redistribution

The source code is licensed under **GNU GPL v3.0 only**; see `LICENSE`. The PNG/ICO artwork, Hololive materials, game-related assets, mod payloads, trademarks, and audio may have separate owners or licences. Confirm you have the necessary rights before sharing payload files or compiled builds.

GUI Customizer also supports banner visibility, a custom banner image, proportional resizing, and fixed-height cropped banners. The saved `tab_order` list determines the tabs’ left-to-right order; old settings without this key continue to use the default order.


GTA III (PS2) tab: requires Assets/III_PS2/AMERICAN.GXT, Assets/III_PS2/FRONTEND.TXD, and Assets/III_PS2/KJAH.VB. These are patched to TEXT/AMERICAN.GXT, MODELS/FRONTEND.TXD, and AUDIO/MUSIC/KJAH.VB respectively. The build script bundles every file present under Assets/ with its game-specific path preserved. KJAH.VB is not fabricated; place the desired payload in Assets/III_PS2 before building the EXE.

Windows taskbar icon: hololive_radio_icon.ico is embedded as the EXE icon, with hololive_radio_icon.png as the Tk window icon fallback. The installer sets a stable Windows AppUserModelID before creating its main window. If Windows shows an old cached icon after replacing an EXE with the same name, close all old instances and rebuild/relaunch the new EXE; Windows Explorer may cache previously seen icons.

## Definitive Edition installs

Two optional tabs install `500-HololiveRadio_P.pak` to `Gameface/Content/Paks/~mods/500-HololiveRadio_P.pak` inside the selected game root. Per the supplied mapping, `Assets/VC_DE/500-HololiveRadio_P.pak` is used by the **GTA San Andreas - The Definitive Edition** tab, and `Assets/SA_DE/500-HololiveRadio_P.pak` is used by the **GTA Vice City - The Definitive Edition** tab. The installer checks the selected game's `Gameface/Content/Paks` folder, creates `~mods` if needed, and backs up an existing destination before replacing it.

These `.pak` files were not present in this supplied project snapshot. Add each licensed file to its matching source folder before running `build_windows_exe.bat`; the build script automatically bundles every file under `Assets/` preserving its relative path, and the relevant install button is enabled when its payload is present.
