#!/usr/bin/env python3
"""Build the Windows GUI EXE after validating and embedding all required local mod payloads."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

# Keep the generated EXE filename short for Windows MAX_PATH compatibility.
# The visible title inside the application remains unchanged.
APP_NAME = "HololiveRadioInstaller"
SCRIPT_NAME = "GTA Hololive Radio Installer.py"
DATA_FILES = (
    "hololive_radio_icon.ico",
    "0865a12018fbd34f84b2c05c.png",
    "VCPR.VB",
)

def main() -> int:
    base = Path(__file__).resolve().parent
    required = [base / SCRIPT_NAME, base / "hololive_radio_icon.ico"]
    missing = [str(p.name) for p in required if not p.is_file()]
    if missing:
        print("Missing required project files: " + ", ".join(missing), file=sys.stderr)
        return 1

    psp_asset_dir = base / "Assets" / "VCS_PSP"
    required_psp_names = ("VCPR.AT3", "ENGLISH.GXT", "GAME.DTZ")
    missing_psp_assets = [
        name for name in required_psp_names
        if not (psp_asset_dir / name).is_file() or (psp_asset_dir / name).stat().st_size <= 0
    ]
    if missing_psp_assets:
        print(
            "Cannot build EXE: required VCS PSP asset(s) are missing or empty: "
            + ", ".join(missing_psp_assets),
            file=sys.stderr,
        )
        print(
            "Place all three files (VCPR.AT3, ENGLISH.GXT, GAME.DTZ) in "
            "Assets\\VCS_PSP on this PC, then run build_windows_exe.bat again.",
            file=sys.stderr,
        )
        return 1
    psp_asset_files = sorted(p for p in psp_asset_dir.rglob("*") if p.is_file()) if psp_asset_dir.is_dir() else []

    lcs_asset_dir = base / "Assets" / "LCS_PSP"
    required_lcs_names = ("KJAH.AT3", "ENGLISH.GXT", "GAME.DTZ")
    missing_lcs_assets = [
        name for name in required_lcs_names
        if not (lcs_asset_dir / name).is_file() or (lcs_asset_dir / name).stat().st_size <= 0
    ]
    if missing_lcs_assets:
        print(
            "Cannot build EXE: required LCS PSP asset(s) are missing or empty: "
            + ", ".join(missing_lcs_assets),
            file=sys.stderr,
        )
        print(
            "Place KJAH.AT3, ENGLISH.GXT, and GAME.DTZ in Assets\\LCS_PSP on this PC, "
            "then run build_windows_exe.bat again.",
            file=sys.stderr,
        )
        return 1
    lcs_asset_files = sorted(p for p in lcs_asset_dir.rglob("*") if p.is_file()) if lcs_asset_dir.is_dir() else []

    # These PC payloads are also embedded at build time. The PC tabs show only
    # a game-folder selector and Install PC Files; no per-file pickers remain.
    pc_required_assets = {
        "VC_PC": ("american.gxt", "fronten2.txd", "VCPR.adf"),
        "SA_PC": ("TK", "TrakLkup.dat", "fronten1.txd", "american.gxt"),
    }
    missing_pc_assets = {}
    for folder, filenames in pc_required_assets.items():
        folder_path = base / "Assets" / folder
        missing = []
        for name in filenames:
            in_game_folder = folder_path / name
            legacy_vc_file = (base / name) if folder == "VC_PC" else None
            candidate = in_game_folder if in_game_folder.is_file() else legacy_vc_file
            if candidate is None or not candidate.is_file() or candidate.stat().st_size <= 0:
                missing.append(name)
        if missing:
            missing_pc_assets[folder] = missing
    if missing_pc_assets:
        print("Cannot build EXE: required PC game assets are missing or empty:", file=sys.stderr)
        for folder, names in missing_pc_assets.items():
            print(f"  Assets\\{folder}: " + ", ".join(names), file=sys.stderr)
        print("Copy the required local mod files into the folders above, then run build_windows_exe.bat again.", file=sys.stderr)
        return 1

    sa_config = base / "Assets" / "SA_PC" / "TrakLkup.dat"
    if sa_config.stat().st_size % 12 != 0:
        print("Cannot build EXE: Assets\\SA_PC\\TrakLkup.dat must contain complete 12-byte lookup records and must match the TK stream file.", file=sys.stderr)
        return 1

    try:
        from PyInstaller.__main__ import run
    except ImportError:
        print("PyInstaller is not installed. Run build_windows_exe.bat to install build dependencies.", file=sys.stderr)
        return 1

    # Keep temporary PyInstaller paths very short. A deeply nested extracted
    # project folder can otherwise push generated filenames beyond Windows'
    # traditional 260-character MAX_PATH limit and cause WinError 122 while
    # PyInstaller edits executable resources.
    short_build_root = Path(tempfile.gettempdir()) / "HVRInstallerBuild"
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

    # For backwards compatibility, root-level Vice City PC payloads are
    # rehomed in the EXE under Assets/VC_PC. This keeps runtime lookup and
    # same-named San Andreas files strictly separated.
    for filename in ("american.gxt", "fronten2.txd", "VCPR.adf"):
        game_path = base / "Assets" / "VC_PC" / filename
        legacy_path = base / filename
        if not game_path.is_file() and legacy_path.is_file():
            args.extend(["--add-data", f"{legacy_path};Assets/VC_PC"])
            included.append(f"{filename} -> Assets/VC_PC")

    # Include the portable game-specific asset tree in the one-file EXE while
    # preserving its relative Assets/<game-folder>/<filename> paths.
    assets_root = base / "Assets"
    if assets_root.is_dir():
        for path in sorted(assets_root.rglob("*")):
            if path.is_file():
                relative_parent = path.parent.relative_to(base)
                args.extend(["--add-data", f"{path};{relative_parent.as_posix()}"])
                included.append(path.relative_to(base).as_posix())

    args.append(str(base / SCRIPT_NAME))

    vcs_ps2_payload_present = (base / "Assets" / "VCS_PS2" / "VCPR.VB").is_file() or (base / "VCPR.VB").is_file()
    if not vcs_ps2_payload_present:
        print("NOTE: VCPR.VB was not found in Assets/VCS_PS2 or the project root; the VCS PS2 patch action may be unavailable.")

    print("Embedding files: " + (", ".join(included) if included else "no root-level optional payloads"))
    print("VCS PSP assets verified and bundled: VCPR.AT3, ENGLISH.GXT, GAME.DTZ")
    print("LCS PSP assets verified and bundled: KJAH.AT3, ENGLISH.GXT, GAME.DTZ")
    print("Vice City PC assets verified and bundled from Assets/VC_PC: american.gxt, fronten2.txd, VCPR.adf")
    print("San Andreas PC assets verified and bundled from Assets/SA_PC: TK, TrakLkup.dat, fronten1.txd, american.gxt")
    print("Both PC tabs show only the game install-folder selector and Install PC Files button; payload file pickers are not displayed.")
    print("GTA Vice City PS2 tab is disabled as Coming Soon; classic Vice City PS2 ISO patching is not implemented.")
    print("GTA San Andreas PC tab is enabled and installs the bundled TK station payloads.")
    run(args)
    print("\nBuild complete. See dist/ for the EXE.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
