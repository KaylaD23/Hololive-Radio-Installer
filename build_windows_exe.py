#!/usr/bin/env python3
"""Build the Windows GUI EXE; game payloads under Assets are optional."""
from __future__ import annotations

from pathlib import Path
import json
import os
import sys
import tempfile

# Keep the generated EXE filename short for Windows MAX_PATH compatibility.
# The visible title inside the application remains unchanged.
APP_NAME = "GrandTheftAutoHololiveRadioInstaller"
SCRIPT_NAME = "Grand Theft Auto Hololive Radio Installer.py"
DATA_FILES = (
    "hololive_radio_icon.ico",
    "hololive_radio_icon.png",  # Tk window/taskbar icon fallback.
    "hololive_radio_banner.png",  # Legacy fallback for older custom projects.
    "hololive_radio_banner_default.png",
    "hololive_radio_banner_fullscreen.png",
)

def find_asset(base: Path, game_folder: str, filename: str) -> Path:
    """Find a payload only under its intended game-specific Assets folder."""
    folder = base / "Assets" / game_folder
    direct = folder / filename
    if direct.exists():
        return direct
    try:
        for child in folder.iterdir():
            if child.name.casefold() == filename.casefold():
                return child
    except OSError:
        pass
    return direct


def main() -> int:
    base = Path(__file__).resolve().parent
    required = [base / SCRIPT_NAME, base / "hololive_radio_icon.ico"]
    missing = [str(p.name) for p in required if not p.is_file()]
    if missing:
        print("Missing required project files: " + ", ".join(missing), file=sys.stderr)
        return 1

    # Every payload belongs in Assets/<game-folder>/<filename>. All files under
    # Assets are embedded preserving their relative paths. Missing required files
    # disable only their game's patch/install action.

    # Keep process temp files and PyInstaller intermediate files in the included
    # project-local Temp folder, rather than the system temp directory.
    temp_root = base / "Temp"
    temp_root.mkdir(parents=True, exist_ok=True)
    for variable in ("TEMP", "TMP", "TMPDIR"):
        os.environ[variable] = str(temp_root)
    os.environ["PYTHONPYCACHEPREFIX"] = str(temp_root / "pycache")
    tempfile.tempdir = str(temp_root)

    try:
        import PIL  # noqa: F401 — Pillow resizes the fullscreen banner cleanly.
    except ImportError:
        print("Pillow is not installed. Run build_windows_exe.bat to install build dependencies.", file=sys.stderr)
        return 1

    try:
        from PyInstaller.__main__ import run
    except ImportError:
        print("PyInstaller is not installed. Run build_windows_exe.bat to install build dependencies.", file=sys.stderr)
        return 1

    # Use Temp for PyInstaller's working files and spec files as requested.
    short_build_root = temp_root / "PyInstallerBuild"
    work_path = short_build_root / "work"
    spec_path = short_build_root / "spec"
    work_path.mkdir(parents=True, exist_ok=True)
    spec_path.mkdir(parents=True, exist_ok=True)

    dist_path = base / "dist"
    dist_path.mkdir(parents=True, exist_ok=True)
    output_exe = dist_path / f"{APP_NAME}.exe"
    if len(str(output_exe)) >= 240:
        print(
            "Warning: the final EXE path is unusually long. Move the project "
            "closer to the drive root (for example C:\\GTA_Hololive) if the "
            "build still fails.",
            file=sys.stderr,
        )

    args = [
        "--clean", "--noconfirm", "--onefile", "--windowed",
        "--name", APP_NAME, "--icon", str(base / "hololive_radio_icon.ico"),
        "--distpath", str(dist_path), "--workpath", str(work_path),
        "--specpath", str(spec_path),
    ]
    included = []
    for filename in DATA_FILES:
        path = base / filename
        if path.is_file():
            args.extend(["--add-data", f"{path};."])
            included.append(filename)

    # Bundle a custom banner selected through GUI Customizer. The customizer
    # copies/converts it to a portable PNG beside the app; config stores only
    # the basename so the image can also be found beside the EXE at runtime.
    try:
        customization = json.loads((base / "gui_customization.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        customization = {}
    custom_banner_name = customization.get("banner_custom_image", "") if isinstance(customization, dict) else ""
    if isinstance(custom_banner_name, str) and custom_banner_name and Path(custom_banner_name).name == custom_banner_name:
        custom_banner_path = base / custom_banner_name
        if custom_banner_path.is_file() and custom_banner_path.name not in DATA_FILES:
            args.extend(["--add-data", f"{custom_banner_path};."])
            included.append(custom_banner_path.name)

    # Add every file under Assets individually. This makes the bundle manifest
    # explicit and preserves each file's exact Assets/<subfolder>/... path in
    # PyInstaller's one-file EXE, including newly added and deeply nested folders.
    # Empty directories cannot be represented in PyInstaller data; folders with
    # README placeholders are retained because those files are bundled too.
    assets_root = base / "Assets"
    asset_files = sorted(p for p in assets_root.rglob("*") if p.is_file()) if assets_root.is_dir() else []
    asset_dirs = sorted(p for p in assets_root.rglob("*") if p.is_dir()) if assets_root.is_dir() else []
    for path in asset_files:
        destination = path.parent.relative_to(base).as_posix()
        args.extend(["--add-data", f"{path};{destination}"])
        included.append(path.relative_to(base).as_posix())

    args.append(str(base / SCRIPT_NAME))


    asset_file_count = len(asset_files)
    print("Embedding files: " + (", ".join(included) if included else "no optional payload assets found"))
    print(f"Assets bundled from Assets/: {asset_file_count} file(s) across {len(asset_dirs)} folder(s). Every file is added individually with its relative folder path preserved.")
    for folder in sorted({p.parent.relative_to(assets_root).as_posix() for p in asset_files}):
        print("  Assets/" + (folder if folder != "." else "") + (" (root)" if folder == "." else ""))
    print("Bundled asset platforms: PSP (VCS_PSP, LCS_PSP), PC (VC_PC, SA_PC), PS2 (III_PS2, VCS_PS2, VC_PS2, LCS_PS2, SA_PS2), and Definitive Edition (VC_DE, SA_DE), plus any other files under Assets/.")
    print("Assets are optional at build time. Every file present under Assets/ is embedded into the EXE. Missing game payloads disable only their corresponding install/patch action.")
    print("Both PC tabs show only the game install-folder selector and Install PC Files button; payload file pickers are not displayed.")
    print("Hololive ICO/PNG icons are embedded, and the Windows AppUserModelID is set so the taskbar groups the installer under its Hololive icon.")
    print("Pillow is bundled so the high-resolution banner scales proportionally to the available width at every window size.")
    print("No lower-right watermark/decoration asset is loaded by the GUI.")
    print("GTA VCS PS2 assets are bundled from Assets/VCS_PS2 when present.")
    vcs_required = ("AMERICAN.GXT", "ENGLISH.GXT", "FRENCH.GXT", "GERMAN.GXT", "SPANISH.GXT", "VCPR.VB", "GAME.DTZ")
    vcs_missing = [name for name in vcs_required if not find_asset(base, "VCS_PS2", name).is_file() or find_asset(base, "VCS_PS2", name).stat().st_size <= 0]
    print("  VCS_PS2 bundled payloads: " + ("all seven found" if not vcs_missing else "missing/empty: " + ", ".join(vcs_missing)))
    print("GTA San Andreas PS2 assets are bundled into the EXE from Assets/SA_PS2 when present.")
    sa_required = ("FRONTEN1.TXD", "AMERICAN.GXT", "TK.PAK", "TRAKLKUP.DAT")
    sa_missing = [name for name in sa_required if not find_asset(base, "SA_PS2", name).is_file() or find_asset(base, "SA_PS2", name).stat().st_size <= 0]
    print("  SA_PS2 bundled payloads: " + ("all four found" if not sa_missing else "missing/empty: " + ", ".join(sa_missing)))
    print("GTA LCS PS2 patching uses optional Assets/LCS_PS2 payloads: KJAH.VB, ENGLISH.GXT, and GAME.DTZ.")
    print("GTA III PS2 patching uses optional Assets/III_PS2 payloads: AMERICAN.GXT, FRONTEND.TXD, and KJAH.VB.")
    iii_required = ("AMERICAN.GXT", "FRONTEND.TXD", "KJAH.VB")
    iii_missing = [name for name in iii_required if not find_asset(base, "III_PS2", name).is_file() or find_asset(base, "III_PS2", name).stat().st_size <= 0]
    print("  III_PS2 bundled payloads: " + ("all three found" if not iii_missing else "missing/empty: " + ", ".join(iii_missing)))
    print("GTA Vice City PS2 patching uses optional Assets/VC_PS2 payloads: AMERICAN.GXT, VCPR.VB, and FRONTEN2.TXD.")
    vc_required = ("AMERICAN.GXT", "VCPR.VB", "FRONTEN2.TXD")
    vc_missing = [name for name in vc_required if not find_asset(base, "VC_PS2", name).is_file() or find_asset(base, "VC_PS2", name).stat().st_size <= 0]
    print("  VC_PS2 bundled payloads: " + ("all three found" if not vc_missing else "missing/empty: " + ", ".join(vc_missing)))
    other_payload_sets = {
        "III_PS2": ("AMERICAN.GXT", "FRONTEND.TXD", "KJAH.VB"),
        "LCS_PS2": ("KJAH.VB", "ENGLISH.GXT", "GAME.DTZ"),
        "VCS_PSP": ("VCPR.AT3", "ENGLISH.GXT", "GAME.DTZ"),
        "LCS_PSP": ("KJAH.AT3", "ENGLISH.GXT", "SPANISH.GXT", "FRENCH.GXT", "GERMAN.GXT", "ITALIAN.GXT", "GAME.DTZ"),
        "VC_PC": ("american.gxt", "fronten2.txd", "VCPR.adf"),
        "SA_PC": ("TK", "TrakLkup.dat", "fronten1.txd", "american.gxt"),
        # Per project requirements: VC_DE is the source folder for the San Andreas DE tab;
        # SA_DE is the source folder for the Vice City DE tab.
        "VC_DE": ("500-HololiveRadio_P.pak",),
        "SA_DE": ("500-HololiveRadio_P.pak",),
    }
    for folder, required_names in other_payload_sets.items():
        missing_names = [name for name in required_names if not find_asset(base, folder, name).is_file() or find_asset(base, folder, name).stat().st_size <= 0]
        summary = "all required files found" if not missing_names else "missing/empty: " + ", ".join(missing_names)
        print(f"  {folder} bundled payloads: {summary}")
    print("All files in every Assets subfolder are bundled into the one-file EXE when present; no game asset folder is excluded.")
    print("Definitive Edition payload mappings: Assets/VC_DE/500-HololiveRadio_P.pak -> GTA San Andreas - The Definitive Edition/Gameface/Content/Paks/~mods/500-HololiveRadio_P.pak.")
    print("Definitive Edition payload mappings: Assets/SA_DE/500-HololiveRadio_P.pak -> GTA Vice City - The Definitive Edition/Gameface/Content/Paks/~mods/500-HololiveRadio_P.pak.")
    print("Definitive Edition .pak files are optional at build time and bundled automatically from their matching Assets subfolders when present.")
    print("GTA San Andreas PC installation is available when its optional payload set is included.")
    run(args)
    print("\nBuild complete. See dist/ for the EXE.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
