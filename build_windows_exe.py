#!/usr/bin/env python3
"""Build the Windows GUI EXE; game payloads under Assets are optional."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

# Keep the generated EXE filename short for Windows MAX_PATH compatibility.
# The visible title inside the application remains unchanged.
APP_NAME = "GrandTheftAutoHololiveRadioInstaller"
SCRIPT_NAME = "Grand Theft Auto Hololive Radio Installer.py"
DATA_FILES = (
    "hololive_radio_icon.ico",
    "0865a12018fbd34f84b2c05c.png",
)

def main() -> int:
    base = Path(__file__).resolve().parent
    required = [base / SCRIPT_NAME, base / "hololive_radio_icon.ico"]
    missing = [str(p.name) for p in required if not p.is_file()]
    if missing:
        print("Missing required project files: " + ", ".join(missing), file=sys.stderr)
        return 1

    # Every game payload is optional at build time. The app embeds any assets
    # that are present; individual game actions are disabled with an explanation
    # at runtime when their required files are absent. This lets users build and
    # launch the GUI without distributing copyrighted/mod payload files.

    try:
        from PyInstaller.__main__ import run
    except ImportError:
        print("PyInstaller is not installed. Run build_windows_exe.bat to install build dependencies.", file=sys.stderr)
        return 1

    # Keep temporary PyInstaller paths very short. A deeply nested extracted
    # project folder can otherwise push generated filenames beyond Windows'
    # traditional 260-character MAX_PATH limit and cause WinError 122 while
    # PyInstaller edits executable resources.
    short_build_root = Path(tempfile.gettempdir()) / "GrandTheftAutoHololiveRadioInstallerBuild"
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

    # Keep legacy root-level Vice City PC payloads compatible by copying them
    # into the expected Assets/VC_PC bundle path when the folder copy is absent.
    for filename in ("american.gxt", "fronten2.txd", "VCPR.adf"):
        game_path = base / "Assets" / "VC_PC" / filename
        legacy_path = base / filename
        if not game_path.is_file() and legacy_path.is_file():
            args.extend(["--add-data", f"{legacy_path};Assets/VC_PC"])
            included.append(f"{filename} -> Assets/VC_PC (legacy root-level file)")

    # Bundle the entire Assets directory as one recursive data tree. This
    # explicitly includes PSP, PC, PS2, and future game payload folders in
    # PyInstaller's one-file EXE while preserving Assets/<game>/<filename>.
    assets_root = base / "Assets"
    asset_files = sorted(p for p in assets_root.rglob("*") if p.is_file()) if assets_root.is_dir() else []
    if assets_root.is_dir() and asset_files:
        args.extend(["--add-data", f"{assets_root};Assets"])
        included.extend(p.relative_to(base).as_posix() for p in asset_files)

    args.append(str(base / SCRIPT_NAME))


    asset_file_count = len(asset_files)
    print("Embedding files: " + (", ".join(included) if included else "no optional payload assets found"))
    print(f"Assets bundled from Assets/: {asset_file_count} file(s). The complete Assets directory is added recursively to the EXE.")
    print("Bundled asset platforms: PSP (VCS_PSP, LCS_PSP), PC (VC_PC, SA_PC), and PS2 (VCS_PS2, LCS_PS2, SA_PS2), plus any other files under Assets/.")
    print("Assets are optional at build time. Every file present under Assets/ is embedded into the EXE. Missing game payloads disable only their corresponding install/patch action.")
    print("Both PC tabs show only the game install-folder selector and Install PC Files button; payload file pickers are not displayed.")
    print("GTA VCS PS2 assets are bundled from Assets/VCS_PS2 when present.")
    vcs_local = ("AMERICAN.GXT", "ENGLISH.GXT", "FRENCH.GXT", "GERMAN.GXT", "SPANISH.GXT", "VCPR.VB", "GAME.DTZ")
    vcs_missing = [name for name in vcs_local if not (base / "Assets" / "VCS_PS2" / name).is_file() or (base / "Assets" / "VCS_PS2" / name).stat().st_size <= 0]
    print("  VCS_PS2 local files: " + ("all seven found" if not vcs_missing else "missing/empty: " + ", ".join(vcs_missing)))
    print("GTA San Andreas PS2 assets are bundled into the EXE from Assets/SA_PS2 when present.")
    sa_local = ("FRONTEN1.TXD", "AMERICAN.GXT", "TK.PAK", "TRAKLKUP.DAT")
    sa_missing = [name for name in sa_local if not (base / "Assets" / "SA_PS2" / name).is_file() or (base / "Assets" / "SA_PS2" / name).stat().st_size <= 0]
    print("  SA_PS2 local files: " + ("all four found" if not sa_missing else "missing/empty: " + ", ".join(sa_missing)))
    print("GTA LCS PS2 patching uses optional Assets/LCS_PS2 payloads: KJAH.VB, ENGLISH.GXT, and GAME.DTZ.")
    print("GTA Vice City PS2 tab is disabled as Coming Soon; classic Vice City PS2 ISO patching is not implemented.")
    print("All files in every Assets subfolder are bundled into the one-file EXE when present; no game asset folder is excluded.")
    print("GTA San Andreas PC installation is available when its optional payload set is included.")
    run(args)
    print("\nBuild complete. See dist/ for the EXE.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
