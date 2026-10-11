#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 contributors to this project
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3. See LICENSE.
"""Grand Theft Auto Hololive Radio Installer.

Includes bundled-asset PC installers for GTA: Vice City and GTA: San Andreas,
plus experimental GTA: Vice City Stories PS2/PSP and GTA: Liberty City Stories PSP
ISO patchers. Classic GTA: Vice City PS2 remains a blank, disabled Coming Soon tab.
PC mod files are loaded from Assets/<game> and installed with backups and rollback.
ISO patchers create new images and support ordinary 2048-byte-sector ISO9660 images only.
"""
from __future__ import annotations

import os
import re
import queue
import shutil
import struct
import sys
import threading
import traceback
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

SECTOR_SIZE = 2048
PVD_FIRST_SECTOR = 16
MAX_DIRECTORY_DEPTH = 64
APP_TITLE = "Grand Theft Auto Hololive Radio Installer"


def asset_path(name: str) -> Path:
    """Locate a game-specific asset folder first, then legacy bundled assets.

    Folder layout is deliberately portable so the installer can be run from an
    extracted directory or packaged with PyInstaller. Existing root-level assets
    remain supported for backwards compatibility.
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    game_folders = {
        "VCPR.VB": ("Assets", "VCS_PS2"),
        "american.gxt": ("Assets", "VC_PC"),
        "fronten2.txd": ("Assets", "VC_PC"),
        "VCPR.adf": ("Assets", "VC_PC"),
        "VCPR.AT3": ("Assets", "VCS_PSP"),
        "ENGLISH.GXT": ("Assets", "VCS_PSP"),
        "GAME.DTZ": ("Assets", "VCS_PSP"),
    }
    if name in game_folders:
        candidate = base.joinpath(*game_folders[name], name)
        if candidate.is_file():
            return candidate
    # Legacy root-level assets and app resources (icon, etc.) remain supported.
    return base / name


def asset_path_in_game_folder(name: str, game_folder: str) -> Path:
    """Resolve a payload from its game-specific Assets folder.

    Legacy root-level files are accepted only for Vice City PC, whose earlier
    builds placed these three payloads beside the build script. PSP and San
    Andreas assets never fall back across game folders because filenames may
    match while the contents are not interchangeable.
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    candidate = base / "Assets" / game_folder / name
    if candidate.is_file():
        return candidate
    if game_folder == "VC_PC" and (base / name).is_file():
        return base / name
    return candidate


def read_be32(data: bytes) -> int:
    return struct.unpack(">I", data)[0]


def read_le32(data: bytes) -> int:
    return struct.unpack("<I", data)[0]


def read_both32(data: bytes, what: str) -> int:
    if len(data) != 8:
        raise ValueError(f"Malformed ISO {what} field.")
    little = read_le32(data[:4])
    big = read_be32(data[4:])
    if little != big:
        raise ValueError(f"ISO has inconsistent little-/big-endian {what} values.")
    return little


def write_both32(value: int) -> bytes:
    return struct.pack("<I", value) + struct.pack(">I", value)


def clean_iso_name(raw: bytes) -> str:
    if raw == b"\x00":
        return "."
    if raw == b"\x01":
        return ".."
    name = raw.decode("ascii", errors="replace").rstrip(" .")
    # Strip ISO9660 version suffix such as ;1.
    if ";" in name:
        name = name.rsplit(";", 1)[0]
    return name


@dataclass
class Record:
    path: str
    name: str
    directory: bool
    extent: int
    size: int
    flags: int
    ext_attr_length: int
    file_unit_size: int
    interleave_gap: int
    record_offset: int
    record_length: int
    identifier_raw: bytes

    @property
    def data_extent(self) -> int:
        return self.extent + self.ext_attr_length

    @property
    def sectors(self) -> int:
        return (self.size + SECTOR_SIZE - 1) // SECTOR_SIZE

    @property
    def end_sector(self) -> int:
        return self.data_extent + self.sectors


class Iso9660:
    def __init__(self, path: Path):
        self.path = path
        self.file_size = path.stat().st_size
        self.total_sectors = self.file_size // SECTOR_SIZE
        if self.file_size % SECTOR_SIZE:
            raise ValueError(
                "This image is not a plain 2048-byte-sector ISO9660 image. "
                "Convert it to a normal ISO first; compressed ISZ and raw 2352-byte images are not supported."
            )
        if self.total_sectors <= PVD_FIRST_SECTOR:
            raise ValueError("The selected file is too small to be a valid ISO image.")
        self.records: list[Record] = []
        self.visited_dirs: set[tuple[int, int]] = set()
        self.root: Record | None = None

    def _read_exact_at(self, fh, offset: int, size: int) -> bytes:
        if offset < 0 or size < 0 or offset + size > self.file_size:
            raise ValueError("ISO directory points outside the image; refusing to patch it.")
        fh.seek(offset)
        data = fh.read(size)
        if len(data) != size:
            raise ValueError("Unexpected end of ISO image.")
        return data

    def _find_pvd_root(self, fh) -> Record:
        pvd = None
        for sector in range(PVD_FIRST_SECTOR, min(self.total_sectors, 128)):
            desc = self._read_exact_at(fh, sector * SECTOR_SIZE, SECTOR_SIZE)
            if desc[1:6] != b"CD001" or desc[6] != 1:
                continue
            dtype = desc[0]
            if dtype == 1:
                pvd = desc
                break
            if dtype == 255:
                break
        if pvd is None:
            raise ValueError("No ISO9660 Primary Volume Descriptor found at the standard location.")
        rec = pvd[156:190]
        if not rec or rec[0] < 34 or rec[32] != 1 or rec[33] != 0:
            raise ValueError("The ISO9660 root directory record is malformed.")
        extent = read_both32(rec[2:10], "root extent")
        size = read_both32(rec[10:18], "root size")
        flags = rec[25]
        return Record("", ".", True, extent, size, flags, rec[1], rec[26], rec[27],
                      16 * SECTOR_SIZE + 156, rec[0], rec[33:34])

    def _scan_dir(self, fh, directory: Record, path_parts: tuple[str, ...], depth: int) -> None:
        if depth > MAX_DIRECTORY_DEPTH:
            raise ValueError("ISO directory nesting is unexpectedly deep; refusing to patch.")
        if not directory.directory:
            return
        key = (directory.data_extent, directory.size)
        if key in self.visited_dirs:
            return
        self.visited_dirs.add(key)
        dir_start = directory.data_extent * SECTOR_SIZE
        if dir_start + directory.size > self.file_size:
            raise ValueError("An ISO directory points outside the image.")
        pos = 0
        entries: list[Record] = []
        with open(self.path, "rb") as source:
            while pos < directory.size:
                absolute = dir_start + pos
                first = self._read_exact_at(source, absolute, 1)[0]
                if first == 0:
                    # Directory records cannot cross a logical-sector boundary.
                    pos = ((pos // SECTOR_SIZE) + 1) * SECTOR_SIZE
                    continue
                if first < 34 or pos + first > directory.size:
                    raise ValueError(f"Malformed directory record in {'/'.join(path_parts) or 'root'}.")
                raw = self._read_exact_at(source, absolute, first)
                ident_len = raw[32]
                if 33 + ident_len > first:
                    raise ValueError("Malformed ISO filename field.")
                identifier = raw[33:33 + ident_len]
                name = clean_iso_name(identifier)
                extent = read_both32(raw[2:10], "extent")
                size = read_both32(raw[10:18], "file size")
                flags = raw[25]
                entry_path_parts = path_parts if name in (".", "..") else path_parts + (name,)
                entry_path = "/".join(entry_path_parts)
                entry = Record(
                    entry_path, name, bool(flags & 0x02), extent, size, flags,
                    raw[1], raw[26], raw[27], absolute, first, identifier
                )
                if name not in (".", ".."):
                    entries.append(entry)
                    self.records.append(entry)
                pos += first
        # Scan children after finishing current directory to avoid open-handle recursion.
        for entry in entries:
            if entry.directory:
                self._scan_dir(fh, entry, tuple(entry.path.split("/")) if entry.path else (), depth + 1)

    def scan(self) -> list[Record]:
        with open(self.path, "rb") as fh:
            self.root = self._find_pvd_root(fh)
            self._scan_dir(fh, self.root, (), 0)
        return self.records

    def find_vcpr(self) -> Record:
        if not self.records:
            self.scan()
        matches = []
        for rec in self.records:
            if rec.directory or rec.name.upper() != "VCPR.VB":
                continue
            components = [part.upper() for part in rec.path.split("/") if part]
            # The supported GTA: Vice City Stories (PS2) workflow targets AUDIO/MUSIC/VCPR.VB.
            # Match the exact parent path rather than any VCPR.VB under AUDIO.
            if len(components) >= 3 and components[-3:-1] == ["AUDIO", "MUSIC"]:
                matches.append(rec)
        if not matches:
            any_matches = [r.path for r in self.records if not r.directory and r.name.upper() == "VCPR.VB"]
            extra = f" Found VCPR.VB elsewhere: {', '.join(any_matches[:5])}." if any_matches else ""
            raise ValueError("Could not find AUDIO/MUSIC/VCPR.VB in the ISO's ISO9660 filesystem." + extra)
        unique = {(m.data_extent, m.size, m.record_offset): m for m in matches}
        if len(unique) != 1:
            choices = ", ".join(m.path for m in unique.values())
            raise ValueError("More than one AUDIO/MUSIC/VCPR.VB entry was found; refusing an ambiguous patch. " + choices)
        return next(iter(unique.values()))


# Known retail PS2 serials for GTA: Vice City Stories. These help prevent the
# VCS-labeled tab from silently accepting classic GTA: Vice City PS2 discs.
VCS_PS2_SERIALS = {
    "SLUS-21590",  # North America
    "SLES-54622",  # Europe / Australia variants
    "SLES-54623",  # Europe variants
    "SLPM-66917",  # Japan
    "SLPM-55135",  # Japan budget release
}
VICE_CITY_PS2_SERIALS = {
    "SLUS-20552", "SLES-51061", "SLES-51316", "SLES-51595",
    "SLPM-65488", "SLPM-66034", "SLPM-66790", "SLPM-55291",
}

# Known retail PSP disc IDs for Grand Theft Auto: Vice City Stories.
# PARAM.SFO stores these IDs without the usual hyphen in many disc dumps.
VCS_PSP_SERIALS = {
    "ULUS10160",  # North America
    "ULES00502",  # Europe
    "ULES00503",  # Germany
    "ULJM05297",  # Japan
    "ULJM05884",  # Japan / Rockstar Classics
}

# All three VCS PSP replacement payloads are required at build time and
# patched into their fixed ISO locations by the one-file executable.
PSP_TARGET_PATHS = {
    "VCPR.AT3": "PSP_GAME/USRDIR/AUDIO/MUSIC/VCPR.AT3",
    "ENGLISH.GXT": "PSP_GAME/USRDIR/RUNDATA/ENGLISH.GXT",
    "GAME.DTZ": "PSP_GAME/USRDIR/RUNDATA/PSP/GAME.DTZ",
}

# Retail GTA: Liberty City Stories PSP disc IDs, as stored in PARAM.SFO.
LCS_PSP_SERIALS = {
    "ULUS10041",  # North America
    "ULES00151",  # Europe multi-language
    "ULES00182",  # German release
    "ULJM05255",  # Japan
    "ULJM05885",  # Japan / Rockstar Classics
}

# All three LCS PSP replacement payloads are required locally at EXE build time.
# The user specified these exact target paths for KJAH radio, text, and game data.
LCS_PSP_TARGET_PATHS = {
    "KJAH.AT3": "PSP_GAME/USRDIR/AUDIO/MUSIC/KJAH.AT3",
    "ENGLISH.GXT": "PSP_GAME/USRDIR/TEXT/ENGLISH.GXT",
    "GAME.DTZ": "PSP_GAME/USRDIR/CHK/PSPHR/GAME.DTZ",
}


def identify_vcs_ps2_iso(image: Iso9660) -> str:
    """Confirm the ISO's SYSTEM.CNF boot serial matches a known VCS PS2 release."""
    cnf_entries = [r for r in image.records if not r.directory and r.path.upper() == "SYSTEM.CNF"]
    if len(cnf_entries) != 1:
        raise ValueError(
            "Could not uniquely identify the game's SYSTEM.CNF in the ISO. "
            "This tab only supports GTA: Vice City Stories (PS2) discs."
        )
    record = cnf_entries[0]
    if record.file_unit_size or record.interleave_gap or (record.flags & 0x80):
        raise ValueError("SYSTEM.CNF uses an unsupported ISO layout; refusing to guess the game identity.")
    with open(image.path, "rb") as fh:
        offset = record.data_extent * SECTOR_SIZE
        if offset < 0 or offset + record.size > image.file_size or record.size > 1024 * 1024:
            raise ValueError("SYSTEM.CNF has an invalid or unexpectedly large ISO directory entry.")
        fh.seek(offset)
        content = fh.read(record.size)
    if len(content) != record.size:
        raise ValueError("Could not read SYSTEM.CNF from the selected ISO.")
    text = content.decode("ascii", errors="ignore").upper()
    found = set()
    for match in re.finditer(r"\b(SLUS|SLES|SLPM)[_-]?(\d{3})[._-]?(\d{2})\b", text):
        found.add(f"{match.group(1)}-{match.group(2)}{match.group(3)}")
    if found & VCS_PS2_SERIALS:
        return sorted(found & VCS_PS2_SERIALS)[0]
    if found & VICE_CITY_PS2_SERIALS:
        serial = sorted(found & VICE_CITY_PS2_SERIALS)[0]
        raise ValueError(
            f"This ISO identifies as classic GTA: Vice City (PS2) ({serial}), which is not supported by this tab. "
            "Select a GTA: Vice City Stories (PS2) ISO instead."
        )
    detected = ", ".join(sorted(found)) if found else "no recognized PS2 serial"
    raise ValueError(
        f"Could not verify this as a supported GTA: Vice City Stories (PS2) ISO ({detected}). "
        "Only recognized VCS PS2 disc versions are accepted by this tab."
    )


def check_image_and_patch(iso_path: Path, output_path: Path, payload_path: Path, status_callback=lambda s: None) -> str:
    if not iso_path.is_file():
        raise ValueError("Please choose an existing ISO image.")
    if not payload_path.is_file():
        raise ValueError("The embedded VCPR.VB payload is missing from this package.")
    if iso_path.resolve() == output_path.resolve():
        raise ValueError("The output path must differ from the source ISO. The source will never be overwritten.")
    if output_path.exists():
        raise FileExistsError(f"The output file already exists: {output_path}\nChoose a different output filename.")
    payload_size = payload_path.stat().st_size
    if payload_size <= 0:
        raise ValueError("The embedded replacement audio file is empty.")

    status_callback("Checking ISO9660 structure…")
    image = Iso9660(iso_path)
    records = image.scan()
    game_serial = identify_vcs_ps2_iso(image)
    status_callback(f"Verified GTA: Vice City Stories (PS2) disc ({game_serial}).")
    target = image.find_vcpr()
    if target.file_unit_size != 0 or target.interleave_gap != 0:
        raise ValueError("The target audio file uses ISO interleaving, which this patcher does not support.")
    if target.flags & 0x80:
        raise ValueError("The target file is split across multiple ISO extents; this patcher will not modify it.")
    if target.size < payload_size:
        raise ValueError(
            f"The ISO's VCPR.VB is only {target.size:,} bytes, but the replacement is {payload_size:,} bytes. "
            "The replacement would not fit in the original extent, so no changes were made."
        )
    if target.end_sector > image.total_sectors:
        raise ValueError("The VCPR.VB extent extends beyond the ISO image; refusing to patch it.")

    # Safety check: no other file/directory extent may overlap the target allocation.
    for rec in records:
        if rec.record_offset == target.record_offset:
            continue
        if rec.sectors == 0:
            continue
        overlaps = rec.data_extent < target.end_sector and target.data_extent < rec.end_sector
        if overlaps:
            raise ValueError(
                f"ISO layout check failed: '{rec.path}' overlaps the VCPR.VB data extent. "
                "No changes were made."
            )

    status_callback(f"Creating patched copy (target: {target.path})…")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(iso_path, output_path)
        status_callback("Writing replacement audio…")
        with open(output_path, "r+b") as out, open(payload_path, "rb") as payload:
            out.seek(target.data_extent * SECTOR_SIZE)
            shutil.copyfileobj(payload, out, length=1024 * 1024)
            # Keep the ISO9660 directory entry's two-endian file length in sync.
            out.seek(target.record_offset + 10)
            out.write(write_both32(payload_size))
            out.flush()
            os.fsync(out.fileno())
    except Exception:
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    return (
        f"Patch completed.\n\nSource: {iso_path}\nPatched copy: {output_path}\n"
        f"Target: {target.path}\nOld size: {target.size:,} bytes\nNew size: {payload_size:,} bytes\n\n"
        "The source ISO was left unchanged. This audio conversion is experimental and has not been verified in-game. "
        "Test the patched ISO in PCSX2 before using it on hardware."
    )



def identify_vcs_psp_iso(image: Iso9660) -> str:
    """Verify a PSP image using PSP_GAME/PARAM.SFO rather than guessing by filename."""
    if not image.records:
        image.scan()
    entries = [r for r in image.records if not r.directory and r.path.upper() == "PSP_GAME/PARAM.SFO"]
    if len(entries) != 1:
        raise ValueError(
            "Could not uniquely find PSP_GAME/PARAM.SFO. This tab only supports GTA: Vice City Stories (PSP) ISO images."
        )
    record = entries[0]
    if record.file_unit_size or record.interleave_gap or (record.flags & 0x80):
        raise ValueError("PARAM.SFO uses an unsupported ISO layout; refusing to guess the game identity.")
    if record.size <= 0 or record.size > 1024 * 1024:
        raise ValueError("PARAM.SFO has an invalid or unexpectedly large file size.")
    with open(image.path, "rb") as fh:
        offset = record.data_extent * SECTOR_SIZE
        if offset < 0 or offset + record.size > image.file_size:
            raise ValueError("PARAM.SFO points outside the ISO image.")
        fh.seek(offset)
        content = fh.read(record.size)
    if len(content) != record.size:
        raise ValueError("Could not read PARAM.SFO from the selected ISO.")
    # SFO values are NUL-terminated strings. Scan the binary payload for a known
    # PSP DISC_ID while accepting the common forms ULUS10160 / ULUS-10160.
    text = content.decode("ascii", errors="ignore").upper()
    found = set()
    for match in re.finditer(r"\b(ULUS|ULES|ULJM)[-_ ]?(\d{5})\b", text):
        found.add(match.group(1) + match.group(2))
    matched = sorted(found & VCS_PSP_SERIALS)
    if matched:
        return matched[0]
    detected = ", ".join(sorted(found)) if found else "no recognized PSP disc ID"
    raise ValueError(
        f"Could not verify this as a supported GTA: Vice City Stories (PSP) ISO ({detected}). "
        "Only recognized VCS PSP releases are accepted by this tab."
    )


def check_psp_image_and_patch(
    iso_path: Path,
    output_path: Path,
    payload_paths: dict[str, Path],
    status_callback=lambda s: None,
) -> str:
    """Patch all required bundled VCS PSP assets into a copy, never the source.

    VCPR.AT3, ENGLISH.GXT, and GAME.DTZ must all be bundled in the executable.
    """
    if not iso_path.is_file():
        raise ValueError("Please choose an existing PSP ISO image.")
    if iso_path.resolve() == output_path.resolve():
        raise ValueError("The output path must differ from the source ISO. The source will never be overwritten.")
    if output_path.exists():
        raise FileExistsError(f"The output file already exists: {output_path}\nChoose a different output filename.")

    resolved_payloads: dict[str, Path] = {}
    for name in PSP_TARGET_PATHS:
        selected = payload_paths.get(name)
        if selected is None:
            raise ValueError(f"The required embedded VCS PSP replacement '{name}' is missing from this installer build.")
        if not str(selected).strip():
            raise ValueError(f"The required embedded VCS PSP replacement '{name}' is missing from this installer build.")
        selected = Path(selected).expanduser().resolve()
        if not selected.is_file():
            raise ValueError(f"The bundled replacement file '{name}' was not found. Rebuild with the required asset in Assets/VCS_PSP.")
        if selected.stat().st_size <= 0:
            raise ValueError(f"The replacement file '{name}' is empty.")
        if selected == iso_path.resolve():
            raise ValueError(f"The ISO image itself cannot be used as the '{name}' replacement.")
        resolved_payloads[name] = selected

    active_target_paths = dict(PSP_TARGET_PATHS)

    status_callback("Checking PSP ISO9660 structure…")
    image = Iso9660(iso_path)
    records = image.scan()
    game_serial = identify_vcs_psp_iso(image)
    status_callback(f"Verified GTA: Vice City Stories (PSP) disc ({game_serial}).")

    records_by_path: dict[str, list[Record]] = {}
    for rec in records:
        records_by_path.setdefault(rec.path.upper(), []).append(rec)

    targets: dict[str, Record] = {}
    for payload_name, target_path in active_target_paths.items():
        matches = records_by_path.get(target_path.upper(), [])
        if len(matches) != 1:
            if not matches:
                raise ValueError(f"Could not find the required target '{target_path}' in this PSP ISO.")
            raise ValueError(f"More than one '{target_path}' entry was found; refusing an ambiguous patch.")
        target = matches[0]
        if target.directory:
            raise ValueError(f"The target '{target_path}' is a directory, not a file.")
        if target.file_unit_size or target.interleave_gap:
            raise ValueError(f"The target '{target_path}' uses ISO interleaving, which this patcher does not support.")
        if target.flags & 0x80:
            raise ValueError(f"The target '{target_path}' is split across multiple ISO extents; this patcher will not modify it.")
        if target.size <= 0 or target.end_sector > image.total_sectors:
            raise ValueError(f"The target '{target_path}' has an invalid extent; refusing to patch it.")

        payload_size = resolved_payloads[payload_name].stat().st_size
        allocated_bytes = target.sectors * SECTOR_SIZE
        if payload_size > allocated_bytes:
            raise ValueError(
                f"Replacement '{payload_name}' is {payload_size:,} bytes, but the original ISO reserves only "
                f"{allocated_bytes:,} bytes for '{target_path}'. This build will not relocate ISO file data. "
                "Use a replacement no larger than the existing allocated space; no changes were made."
            )
        # Ensure no other file/directory extent overlaps this target allocation.
        for rec in records:
            if rec.record_offset == target.record_offset or rec.sectors == 0:
                continue
            overlaps = rec.data_extent < target.end_sector and target.data_extent < rec.end_sector
            if overlaps:
                raise ValueError(
                    f"ISO layout check failed: '{rec.path}' overlaps '{target_path}'. No changes were made."
                )
        targets[payload_name] = target

    # Distinct source files and target allocations are required; a duplicate ISO
    # entry or overlapping target could otherwise make one replacement corrupt another.
    target_intervals = sorted(
        (rec.data_extent, rec.end_sector, name) for name, rec in targets.items()
    )
    for left, right in zip(target_intervals, target_intervals[1:]):
        if left[1] > right[0]:
            raise ValueError(f"The ISO has overlapping target extents ({left[2]} and {right[2]}). No changes were made.")

    status_callback("Creating a patched ISO copy…")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(iso_path, output_path)
        with open(output_path, "r+b") as out:
            for index, payload_name in enumerate(active_target_paths, start=1):
                target = targets[payload_name]
                payload_path = resolved_payloads[payload_name]
                payload_size = payload_path.stat().st_size
                status_callback(f"Writing file {index}/{len(active_target_paths)}: {payload_name}…")
                with open(payload_path, "rb") as payload:
                    out.seek(target.data_extent * SECTOR_SIZE)
                    shutil.copyfileobj(payload, out, length=1024 * 1024)
                # Keep the two-endian ISO9660 directory entry size in sync.
                out.seek(target.record_offset + 10)
                out.write(write_both32(payload_size))
            out.flush()
            os.fsync(out.fileno())
    except Exception:
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    details = "\n".join(
        f"  {active_target_paths[name]}\n    {targets[name].size:,} → {resolved_payloads[name].stat().st_size:,} bytes"
        for name in active_target_paths
    )
    return (
        f"Patch completed.\n\nSource: {iso_path}\nPatched copy: {output_path}\nVerified disc: {game_serial}\n\n"
        f"Files replaced:\n{details}\n\nThe source ISO was left unchanged. The patch is experimental and has not been verified in-game. "
        "Test the new ISO in PPSSPP before using it with hardware."
    )


def identify_lcs_psp_iso(image: Iso9660) -> str:
    """Verify the LCS PSP PARAM.SFO against supported retail disc IDs."""
    if not image.records:
        image.scan()
    entries = [r for r in image.records if not r.directory and r.path.upper() == "PSP_GAME/PARAM.SFO"]
    if len(entries) != 1:
        raise ValueError(
            "Could not uniquely find PSP_GAME/PARAM.SFO. This tab only supports GTA: Liberty City Stories (PSP) ISOs."
        )
    record = entries[0]
    if record.file_unit_size or record.interleave_gap or (record.flags & 0x80):
        raise ValueError("PARAM.SFO uses an unsupported ISO layout; refusing to guess the game identity.")
    if record.size <= 0 or record.size > 1024 * 1024:
        raise ValueError("PARAM.SFO has an invalid or unexpectedly large file size.")
    with open(image.path, "rb") as fh:
        offset = record.data_extent * SECTOR_SIZE
        if offset < 0 or offset + record.size > image.file_size:
            raise ValueError("PARAM.SFO points outside the ISO image.")
        fh.seek(offset)
        content = fh.read(record.size)
    if len(content) != record.size:
        raise ValueError("Could not read PARAM.SFO from the selected ISO.")
    text = content.decode("ascii", errors="ignore").upper()
    found = {m.group(1) + m.group(2) for m in re.finditer(r"\b(ULUS|ULES|ULJM)[-_ ]?(\d{5})\b", text)}
    matched = sorted(found & LCS_PSP_SERIALS)
    if matched:
        return matched[0]
    detected = ", ".join(sorted(found)) if found else "no recognized PSP disc ID"
    raise ValueError(
        f"Could not verify this as a supported GTA: Liberty City Stories (PSP) ISO ({detected}). "
        "Only recognized LCS PSP retail releases are accepted by this tab."
    )


def check_lcs_psp_image_and_patch(
    iso_path: Path,
    output_path: Path,
    payload_paths: dict[str, Path],
    status_callback=lambda s: None,
) -> str:
    """Patch the bundled LCS PSP KJAH.AT3, ENGLISH.GXT, and GAME.DTZ files."""
    iso_path = Path(iso_path).expanduser()
    output_path = Path(output_path).expanduser()
    if not iso_path.is_file():
        raise ValueError("Please choose an existing GTA: Liberty City Stories (PSP) ISO image.")
    if iso_path.resolve() == output_path.resolve():
        raise ValueError("The output path must differ from the source ISO. The source will never be overwritten.")
    if output_path.exists():
        raise FileExistsError(f"The output file already exists: {output_path}\nChoose a different output filename.")

    resolved_payloads: dict[str, Path] = {}
    for name in LCS_PSP_TARGET_PATHS:
        selected = payload_paths.get(name)
        if selected is None or not str(selected).strip():
            raise ValueError(
                f"The required embedded LCS PSP replacement '{name}' is missing from this installer build. "
                "Rebuild with all three files in Assets/LCS_PSP."
            )
        selected = Path(selected).expanduser().resolve()
        if not selected.is_file():
            raise ValueError(
                f"The bundled replacement file '{name}' was not found. "
                "Rebuild with the required asset in Assets/LCS_PSP."
            )
        if selected.stat().st_size <= 0:
            raise ValueError(f"The replacement file '{name}' is empty.")
        if selected == iso_path.resolve():
            raise ValueError(f"The ISO image itself cannot be used as the '{name}' replacement.")
        resolved_payloads[name] = selected

    status_callback("Checking LCS PSP ISO9660 structure…")
    image = Iso9660(iso_path)
    records = image.scan()
    game_serial = identify_lcs_psp_iso(image)
    status_callback(f"Verified GTA: Liberty City Stories (PSP) disc ({game_serial}).")

    records_by_path: dict[str, list[Record]] = {}
    for rec in records:
        records_by_path.setdefault(rec.path.upper(), []).append(rec)

    targets: dict[str, Record] = {}
    for payload_name, target_path in LCS_PSP_TARGET_PATHS.items():
        matches = records_by_path.get(target_path.upper(), [])
        if len(matches) != 1:
            if not matches:
                raise ValueError(f"Could not find the required target '{target_path}' in this LCS PSP ISO.")
            raise ValueError(f"More than one '{target_path}' entry was found; refusing an ambiguous patch.")
        target = matches[0]
        if target.directory:
            raise ValueError(f"The target '{target_path}' is a directory, not a file.")
        if target.file_unit_size or target.interleave_gap:
            raise ValueError(f"The target '{target_path}' uses ISO interleaving, which this patcher does not support.")
        if target.flags & 0x80:
            raise ValueError(f"The target '{target_path}' is split across multiple ISO extents; this patcher will not modify it.")
        if target.size <= 0 or target.end_sector > image.total_sectors:
            raise ValueError(f"The target '{target_path}' has an invalid extent; refusing to patch it.")
        payload_size = resolved_payloads[payload_name].stat().st_size
        allocated_bytes = target.sectors * SECTOR_SIZE
        if payload_size > allocated_bytes:
            raise ValueError(
                f"Replacement '{payload_name}' is {payload_size:,} bytes, but the ISO reserves only "
                f"{allocated_bytes:,} bytes for '{target_path}'. This patcher will not relocate ISO file data. "
                "No changes were made."
            )
        # Don't overwrite an allocation shared by another ISO file/directory.
        for other in records:
            if other.record_offset == target.record_offset or other.sectors == 0:
                continue
            if other.data_extent < target.end_sector and target.data_extent < other.end_sector:
                raise ValueError(
                    f"ISO layout check failed: '{other.path}' overlaps '{target_path}'. No changes were made."
                )
        targets[payload_name] = target

    intervals = sorted((rec.data_extent, rec.end_sector, name) for name, rec in targets.items())
    for left, right in zip(intervals, intervals[1:]):
        if left[1] > right[0]:
            raise ValueError(f"The ISO has overlapping target extents ({left[2]} and {right[2]}). No changes were made.")

    status_callback("Creating a patched LCS PSP ISO copy…")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(iso_path, output_path)
        with open(output_path, "r+b") as out:
            for index, payload_name in enumerate(LCS_PSP_TARGET_PATHS, start=1):
                target = targets[payload_name]
                payload_path = resolved_payloads[payload_name]
                payload_size = payload_path.stat().st_size
                status_callback(f"Writing file {index}/{len(LCS_PSP_TARGET_PATHS)}: {payload_name}…")
                with open(payload_path, "rb") as payload:
                    out.seek(target.data_extent * SECTOR_SIZE)
                    shutil.copyfileobj(payload, out, length=1024 * 1024)
                # Update ISO9660 directory entry size (little-endian + big-endian).
                out.seek(target.record_offset + 10)
                out.write(write_both32(payload_size))
            out.flush()
            os.fsync(out.fileno())
    except Exception:
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    details = "\n".join(
        f"  {LCS_PSP_TARGET_PATHS[name]}\n    {targets[name].size:,} → {resolved_payloads[name].stat().st_size:,} bytes"
        for name in LCS_PSP_TARGET_PATHS
    )
    return (
        f"Patch completed.\n\nSource: {iso_path}\nPatched copy: {output_path}\nVerified disc: {game_serial}\n\n"
        f"Files replaced:\n{details}\n\nThe source ISO was left unchanged. This patch is experimental and has not been verified in-game. "
        "Test the patched ISO in PPSSPP first."
    )


def _find_child_case_insensitive(parent: Path, name: str, want_directory: bool) -> Path:
    """Find a child path without depending on Windows' case-insensitive filesystem."""
    direct = parent / name
    if direct.exists() and (direct.is_dir() if want_directory else direct.is_file()):
        return direct
    try:
        for child in parent.iterdir():
            if child.name.casefold() == name.casefold() and (child.is_dir() if want_directory else child.is_file()):
                return child
    except OSError as exc:
        raise ValueError(f"Could not read the selected game folder: {exc}") from exc
    kind = "folder" if want_directory else "file"
    raise ValueError(f"Could not find the required {kind} '{name}' inside '{parent}'.")


def prepare_pc_install(game_dir: Path, payload_paths: dict[str, Path]):
    """Validate a classic PC install and return (root, operations, all destinations)."""
    root = game_dir.expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Choose the existing root folder of your GTA: Vice City PC installation.")
    exe = None
    try:
        exe = next((child for child in root.iterdir() if child.is_file() and child.name.casefold() == "gta-vc.exe"), None)
    except OSError as exc:
        raise ValueError(f"Could not read the selected game folder: {exc}") from exc
    if exe is None:
        raise ValueError("The selected folder does not contain gta-vc.exe. Choose the main GTA: Vice City PC installation folder, not a subfolder.")

    directories = {
        "TEXT": _find_child_case_insensitive(root, "TEXT", True),
        "models": _find_child_case_insensitive(root, "models", True),
        "audio": _find_child_case_insensitive(root, "audio", True),
    }
    mapping = (
        ("american.gxt", Path("text") / "american.gxt", directories["TEXT"]),
        ("fronten2.txd", Path("models") / "fronten2.txd", directories["models"]),
        ("VCPR.adf", Path("Audio") / "VCPR.adf", directories["audio"]),
    )
    operations = []
    destinations = []
    for asset_name, relative_path, parent in mapping:
        try:
            source = Path(payload_paths[asset_name]).expanduser().resolve()
        except (KeyError, TypeError) as exc:
            raise ValueError(f"Choose the required mod file '{asset_name}'.") from exc
        if not source.is_file():
            raise ValueError(f"The required mod file '{asset_name}' was not found. Use Browse to select it.")
        if source.stat().st_size <= 0:
            raise ValueError(f"The selected mod file '{asset_name}' is empty.")
        destination = parent / relative_path.name
        if destination.exists() and destination.is_dir():
            raise ValueError(f"The destination '{destination}' is a folder, not a file.")
        destinations.append((relative_path, source, destination))
        if source != destination.resolve():
            operations.append((relative_path, source, destination))
    return root, operations, destinations


def install_pc_assets(game_dir: Path, payload_paths: dict[str, Path]) -> str:
    """Install three PC assets safely, backing up overwritten files and rolling back on error."""
    root, operations, destinations = prepare_pc_install(game_dir, payload_paths)
    if not operations:
        return f"No files needed copying; the selected source files are already at their destination paths in:\n{root}"

    existing = [(relative, source, dest) for relative, source, dest in operations if dest.exists()]
    backup_root = None
    backups: dict[Path, Path] = {}
    staged: list[tuple[Path, Path, Path]] = []
    committed: list[Path] = []
    if existing:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_root = root / f"HololiveRadioInstaller_Backup_{stamp}"
        suffix = 1
        while backup_root.exists():
            backup_root = root / f"HololiveRadioInstaller_Backup_{stamp}_{suffix:02d}"
            suffix += 1

    try:
        # Stage each payload before replacing anything.
        for relative, source, destination in operations:
            temporary = destination.with_name(f".{destination.name}.hololive-tmp-{os.getpid()}-{threading.get_ident()}")
            if temporary.exists():
                temporary.unlink()
            shutil.copy2(source, temporary)
            staged.append((relative, temporary, destination))

        # Preserve all existing target files before committing replacements.
        if backup_root is not None:
            for relative, _source, destination in existing:
                backup_path = backup_root / relative
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, backup_path)
                backups[destination] = backup_path

        for _relative, temporary, destination in staged:
            os.replace(temporary, destination)
            committed.append(destination)
    except Exception as exc:
        rollback_errors = []
        for destination in reversed(committed):
            try:
                if destination in backups:
                    shutil.copy2(backups[destination], destination)
                else:
                    destination.unlink(missing_ok=True)
            except Exception as rollback_exc:
                rollback_errors.append(f"{destination}: {rollback_exc}")
        for _relative, temporary, _destination in staged:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        extra = ""
        if rollback_errors:
            extra = "\nRollback also reported: " + "; ".join(rollback_errors)
        if backup_root is not None and backup_root.exists():
            extra += f"\nAny backups successfully created remain at: {backup_root}"
        raise RuntimeError(f"Install failed: {exc}. Changes were rolled back where possible.{extra}") from exc

    backup_note = f"\n\nExisting files were backed up to:\n{backup_root}" if backup_root else "\n\nNo existing target files needed backing up."
    installed = "\n".join(f"  • {relative.as_posix()}" for relative, _source, _destination in operations)
    return f"GTA: Vice City PC files installed successfully.\n\nGame folder: {root}\nFiles installed:\n{installed}{backup_note}"


def prepare_sa_pc_install(game_dir: Path, payload_paths: dict[str, Path]):
    """Validate a GTA: San Andreas PC folder and fixed TK-station payload destinations."""
    root = game_dir.expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Choose the existing root folder of your GTA: San Andreas PC installation.")
    try:
        executable_names = {"gta_sa.exe", "gta-sa.exe"}
        exe = next((child for child in root.iterdir()
                    if child.is_file() and child.name.casefold() in executable_names), None)
    except OSError as exc:
        raise ValueError(f"Could not read the selected game folder: {exc}") from exc
    if exe is None:
        raise ValueError("The selected folder does not contain gta_sa.exe. Choose the main GTA: San Andreas installation folder, not a subfolder.")

    audio_dir = _find_child_case_insensitive(root, "audio", True)
    streams_dir = _find_child_case_insensitive(audio_dir, "streams", True)
    config_dir = _find_child_case_insensitive(audio_dir, "CONFIG", True)
    models_dir = _find_child_case_insensitive(root, "models", True)
    text_dir = _find_child_case_insensitive(root, "text", True)
    mapping = (
        ("TK", Path("audio") / "streams" / "TK", streams_dir),
        ("TrakLkup.dat", Path("audio") / "CONFIG" / "TrakLkup.dat", config_dir),
        ("fronten1.txd", Path("models") / "fronten1.txd", models_dir),
        ("american.gxt", Path("text") / "american.gxt", text_dir),
    )
    operations = []
    destinations = []
    for asset_name, relative_path, parent in mapping:
        try:
            source = Path(payload_paths[asset_name]).expanduser().resolve()
        except (KeyError, TypeError) as exc:
            raise ValueError(f"Choose the required San Andreas mod file '{asset_name}'.") from exc
        if not source.is_file():
            raise ValueError(f"The required mod file '{asset_name}' was not found. Use Browse to select it.")
        if source.stat().st_size <= 0:
            raise ValueError(f"The selected mod file '{asset_name}' is empty.")
        # TrakLkup.dat stores one 12-byte lookup record per indexed audio track.
        # A partial record usually indicates a broken/incomplete payload.
        if asset_name.casefold() == "traklkup.dat" and source.stat().st_size % 12 != 0:
            raise ValueError("TrakLkup.dat has an invalid size: it must contain complete 12-byte track lookup records. Make sure you selected the matching file from the same radio mod.")
        destination = parent / relative_path.name
        if destination.exists() and destination.is_dir():
            raise ValueError(f"The destination '{destination}' is a folder, not a file.")
        destinations.append((relative_path, source, destination))
        if source != destination.resolve():
            operations.append((relative_path, source, destination))
    return root, operations, destinations


def install_sa_pc_assets(game_dir: Path, payload_paths: dict[str, Path]) -> str:
    """Install the four GTA: San Andreas TK station assets, with backup and rollback."""
    root, operations, destinations = prepare_sa_pc_install(game_dir, payload_paths)
    if not operations:
        return f"No files needed copying; the selected source files are already at their destination paths in:\n{root}"

    existing = [(relative, source, dest) for relative, source, dest in operations if dest.exists()]
    backup_root = None
    backups: dict[Path, Path] = {}
    staged: list[tuple[Path, Path, Path]] = []
    committed: list[Path] = []
    if existing:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_root = root / f"HololiveRadioInstaller_SA_Backup_{stamp}"
        suffix = 1
        while backup_root.exists():
            backup_root = root / f"HololiveRadioInstaller_SA_Backup_{stamp}_{suffix:02d}"
            suffix += 1

    try:
        for relative, source, destination in operations:
            temporary = destination.with_name(f".{destination.name}.hololive-tmp-{os.getpid()}-{threading.get_ident()}")
            if temporary.exists():
                temporary.unlink()
            shutil.copy2(source, temporary)
            staged.append((relative, temporary, destination))

        if backup_root is not None:
            for relative, _source, destination in existing:
                backup_path = backup_root / relative
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, backup_path)
                backups[destination] = backup_path

        for _relative, temporary, destination in staged:
            os.replace(temporary, destination)
            committed.append(destination)
    except Exception as exc:
        rollback_errors = []
        for destination in reversed(committed):
            try:
                if destination in backups:
                    shutil.copy2(backups[destination], destination)
                else:
                    destination.unlink(missing_ok=True)
            except Exception as rollback_exc:
                rollback_errors.append(f"{destination}: {rollback_exc}")
        for _relative, temporary, _destination in staged:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        extra = ""
        if rollback_errors:
            extra = "\nRollback also reported: " + "; ".join(rollback_errors)
        if backup_root is not None and backup_root.exists():
            extra += f"\nAny backups successfully created remain at: {backup_root}"
        raise RuntimeError(f"San Andreas install failed: {exc}. Changes were rolled back where possible.{extra}") from exc

    backup_note = f"\n\nExisting files were backed up to:\n{backup_root}" if backup_root else "\n\nNo existing target files needed backing up."
    installed = "\n".join(f"  • {relative.as_posix()}" for relative, _source, _destination in operations)
    return f"GTA: San Andreas PC TK station files installed successfully.\n\nGame folder: {root}\nFiles installed:\n{installed}{backup_note}"


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        try:
            self.root.iconbitmap(str(asset_path("hololive_radio_icon.ico")))
        except (tk.TclError, OSError):
            pass
        self.root.geometry("780x560")
        self.root.minsize(700, 500)
        self.iso_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Choose a GTA: Vice City Stories (PS2) ISO image to begin.")
        self.psp_iso_var = tk.StringVar()
        self.psp_out_var = tk.StringVar()
        self.psp_status_var = tk.StringVar(value="Choose a GTA: Vice City Stories (PSP) ISO image to begin.")
        self.psp_events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.lcs_iso_var = tk.StringVar()
        self.lcs_out_var = tk.StringVar()
        self.lcs_status_var = tk.StringVar(value="Choose a GTA: Liberty City Stories (PSP) ISO image to begin.")
        self.lcs_events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.pc_dir_var = tk.StringVar()
        self.pc_status_var = tk.StringVar(value="Choose your GTA: Vice City PC installation folder to begin.")
        self.sa_pc_dir_var = tk.StringVar()
        self.sa_pc_status_var = tk.StringVar(value="Choose your GTA: San Andreas PC installation folder to begin.")
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._build_ui()
        self.root.after(100, self._poll_events)
        self.root.after(100, self._poll_psp_events)
        self.root.after(100, self._poll_lcs_events)

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(
            outer,
            text="Grand Theft Auto Hololive Radio Installer",
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)
        # Requested platform order: VCS PS2, VCS PSP, LCS PSP, then PC targets.
        # The VCS PS2 workflow is implemented; classic GTA: Vice City PS2 is not supported.
        ps2_tab = ttk.Frame(notebook, padding=14)
        vcs_psp_tab = ttk.Frame(notebook, padding=14)
        lcs_psp_tab = ttk.Frame(notebook, padding=14)
        pc_tab = ttk.Frame(notebook, padding=14)
        vc_ps2_tab = ttk.Frame(notebook, padding=14)
        sa_pc_tab = ttk.Frame(notebook, padding=14)
        notebook.add(ps2_tab, text="GTA VCS PS2")
        notebook.add(vcs_psp_tab, text="GTA VCS PSP")
        notebook.add(lcs_psp_tab, text="GTA LCS PSP")
        notebook.add(pc_tab, text="GTA Vice City PC")
        # Classic Vice City PS2 support is not implemented. Keep the tab
        # completely blank and disabled until a tested patcher exists.
        notebook.add(vc_ps2_tab, text="GTA Vice City PS2 [Coming Soon]")
        notebook.tab(vc_ps2_tab, state="disabled")
        notebook.add(sa_pc_tab, text="GTA San Andreas PC")
        self._build_ps2_tab(ps2_tab)
        self._build_vcs_psp_tab(vcs_psp_tab)
        self._build_lcs_psp_tab(lcs_psp_tab)
        self._build_pc_tab(pc_tab)
        self._build_sa_pc_tab(sa_pc_tab)

    def _build_ps2_tab(self, parent):
        ttk.Label(
            parent,
            text="Experimental ISO workflow for GTA: Vice City Stories (PS2). Classic GTA: Vice City (PS2) is not supported by this tab.",
            wraplength=690,
        ).pack(anchor="w", pady=(0, 12))

        row1 = ttk.Frame(parent)
        row1.pack(fill="x", pady=4)
        ttk.Label(row1, text="Input ISO", width=11).pack(side="left")
        ttk.Entry(row1, textvariable=self.iso_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row1, text="Browse…", command=self._choose_iso).pack(side="left")

        row2 = ttk.Frame(parent)
        row2.pack(fill="x", pady=4)
        ttk.Label(row2, text="Output ISO", width=11).pack(side="left")
        ttk.Entry(row2, textvariable=self.out_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row2, text="Save as…", command=self._choose_output).pack(side="left")

        buttons = ttk.Frame(parent)
        buttons.pack(fill="x", pady=(14, 8))
        self.patch_button = ttk.Button(buttons, text="Create Patched PS2 ISO", command=self._start_patch)
        self.patch_button.pack(side="left")
        if not asset_path("VCPR.VB").is_file():
            self.patch_button.configure(state="disabled")
            self.status_var.set("VCS PS2 audio payload VCPR.VB is not bundled; the PC installer tab is still available.")
        ttk.Button(buttons, text="About / Safety", command=self._about).pack(side="left", padx=8)

        self.progress = ttk.Progressbar(parent, mode="indeterminate")
        self.progress.pack(fill="x", pady=(4, 8))
        ttk.Label(parent, textvariable=self.status_var, wraplength=690).pack(anchor="w")
        ttk.Label(
            parent,
            text="Supports plain 2048-byte-sector ISO9660 images. Compressed ISZ and raw 2352-byte images are not supported.",
            foreground="#555555", wraplength=690,
        ).pack(anchor="w", pady=(12, 0))

    def _build_vcs_psp_tab(self, parent):
        ttk.Label(
            parent,
            text="GTA: Vice City Stories (PSP). The EXE contains all three built-in replacement files.",
            wraplength=690,
        ).pack(anchor="w", pady=(0, 12))

        row1 = ttk.Frame(parent)
        row1.pack(fill="x", pady=4)
        ttk.Label(row1, text="Input ISO", width=11).pack(side="left")
        ttk.Entry(row1, textvariable=self.psp_iso_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row1, text="Browse…", command=self._choose_psp_iso).pack(side="left")

        row2 = ttk.Frame(parent)
        row2.pack(fill="x", pady=4)
        ttk.Label(row2, text="Output ISO", width=11).pack(side="left")
        ttk.Entry(row2, textvariable=self.psp_out_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row2, text="Save as…", command=self._choose_psp_output).pack(side="left")

        buttons = ttk.Frame(parent)
        buttons.pack(fill="x", pady=(14, 8))
        self.psp_patch_button = ttk.Button(buttons, text="Create Patched PSP ISO", command=self._start_psp_patch)
        self.psp_patch_button.pack(side="left")
        missing_psp_assets = [
            name for name in PSP_TARGET_PATHS
            if not asset_path(name).is_file() or asset_path(name).stat().st_size <= 0
        ]
        if missing_psp_assets:
            self.psp_patch_button.configure(state="disabled")
            self.psp_status_var.set(
                "Required VCS PSP assets are missing: " + ", ".join(missing_psp_assets) +
                ". Rebuild with all three files in Assets\\VCS_PSP."
            )
        ttk.Button(buttons, text="About / Safety", command=self._about_psp).pack(side="left", padx=8)

        self.psp_progress = ttk.Progressbar(parent, mode="indeterminate")
        self.psp_progress.pack(fill="x", pady=(4, 8))
        ttk.Label(parent, textvariable=self.psp_status_var, wraplength=690).pack(anchor="w")
        ttk.Label(
            parent,
            text="Plain 2048-byte-sector ISO9660 only. Built-in assets must fit the ISO's existing allocated space; the original ISO is not modified.",
            foreground="#555555", wraplength=690,
        ).pack(anchor="w", pady=(12, 0))

    def _build_lcs_psp_tab(self, parent):
        ttk.Label(
            parent,
            text="GTA: Liberty City Stories (PSP). The EXE contains all three built-in replacement files.",
            wraplength=690,
        ).pack(anchor="w", pady=(0, 12))

        row1 = ttk.Frame(parent)
        row1.pack(fill="x", pady=4)
        ttk.Label(row1, text="Input ISO", width=11).pack(side="left")
        ttk.Entry(row1, textvariable=self.lcs_iso_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row1, text="Browse…", command=self._choose_lcs_iso).pack(side="left")

        row2 = ttk.Frame(parent)
        row2.pack(fill="x", pady=4)
        ttk.Label(row2, text="Output ISO", width=11).pack(side="left")
        ttk.Entry(row2, textvariable=self.lcs_out_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row2, text="Save as…", command=self._choose_lcs_output).pack(side="left")

        buttons = ttk.Frame(parent)
        buttons.pack(fill="x", pady=(14, 8))
        self.lcs_patch_button = ttk.Button(buttons, text="Create Patched LCS PSP ISO", command=self._start_lcs_patch)
        self.lcs_patch_button.pack(side="left")
        missing_lcs_assets = [
            name for name in LCS_PSP_TARGET_PATHS
            if not asset_path_in_game_folder(name, "LCS_PSP").is_file()
            or asset_path_in_game_folder(name, "LCS_PSP").stat().st_size <= 0
        ]
        if missing_lcs_assets:
            self.lcs_patch_button.configure(state="disabled")
            self.lcs_status_var.set(
                "Required LCS PSP assets are missing: " + ", ".join(missing_lcs_assets) +
                ". Rebuild with all three files in Assets\\LCS_PSP."
            )
        ttk.Button(buttons, text="About / Safety", command=self._about_lcs_psp).pack(side="left", padx=8)

        self.lcs_progress = ttk.Progressbar(parent, mode="indeterminate")
        self.lcs_progress.pack(fill="x", pady=(4, 8))
        ttk.Label(parent, textvariable=self.lcs_status_var, wraplength=690).pack(anchor="w")
        ttk.Label(
            parent,
            text="Plain 2048-byte-sector ISO9660 only. Built-in assets must fit the ISO's existing allocated space; the original ISO is not modified.",
            foreground="#555555", wraplength=690,
        ).pack(anchor="w", pady=(12, 0))

    def _build_pc_tab(self, parent):
        ttk.Label(
            parent,
            text="Install the bundled Hololive radio files into your classic GTA: Vice City PC installation. Choose the folder containing gta-vc.exe, text, models and audio.",
            wraplength=690,
        ).pack(anchor="w", pady=(0, 12))

        root_row = ttk.Frame(parent)
        root_row.pack(fill="x", pady=4)
        ttk.Label(root_row, text="PC install folder", width=16).pack(side="left")
        ttk.Entry(root_row, textvariable=self.pc_dir_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(root_row, text="Locate…", command=self._choose_pc_dir).pack(side="left")

        ttk.Label(
            parent,
            text="Built-in files: american.gxt → text/american.gxt   •   fronten2.txd → models/fronten2.txd   •   VCPR.adf → Audio/VCPR.adf",
            wraplength=690, foreground="#555555",
        ).pack(anchor="w", pady=(12, 8))

        self.pc_install_button = ttk.Button(parent, text="Install PC Files", command=self._start_pc_install)
        self.pc_install_button.pack(anchor="w", pady=(8, 8))
        ttk.Button(parent, text="About / Safety", command=self._about_pc).pack(anchor="w")
        ttk.Label(parent, textvariable=self.pc_status_var, wraplength=690).pack(anchor="w", pady=(10, 0))

        missing = [name for name in ("american.gxt", "fronten2.txd", "VCPR.adf")
                   if not asset_path_in_game_folder(name, "VC_PC").is_file()
                   or asset_path_in_game_folder(name, "VC_PC").stat().st_size <= 0]
        if missing:
            self.pc_install_button.configure(state="disabled")
            self.pc_status_var.set(
                "Built-in Vice City PC file(s) missing: " + ", ".join(missing)
                + ". Put all three in Assets/VC_PC and rebuild the EXE."
            )

    def _build_sa_pc_tab(self, parent):
        ttk.Label(
            parent,
            text="Install the bundled Hololive Radio files into your classic GTA: San Andreas PC Installation. Choose the main game folder containing gta_sa.exe, audio, models and text.",
            wraplength=690,
        ).pack(anchor="w", pady=(0, 12))

        root_row = ttk.Frame(parent)
        root_row.pack(fill="x", pady=4)
        ttk.Label(root_row, text="PC install folder", width=16).pack(side="left")
        ttk.Entry(root_row, textvariable=self.sa_pc_dir_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(root_row, text="Locate…", command=self._choose_sa_pc_dir).pack(side="left")

        ttk.Label(
            parent,
            text="Built-in files: TK → audio/streams/TK   •   TrakLkup.dat → audio/CONFIG/TrakLkup.dat   •   fronten1.txd → models/fronten1.txd   •   american.gxt → text/american.gxt",
            wraplength=690, foreground="#555555",
        ).pack(anchor="w", pady=(12, 8))

        self.sa_pc_install_button = ttk.Button(parent, text="Install PC Files", command=self._start_sa_pc_install)
        self.sa_pc_install_button.pack(anchor="w", pady=(8, 8))
        ttk.Button(parent, text="About / Safety", command=self._about_sa_pc).pack(anchor="w")
        ttk.Label(parent, textvariable=self.sa_pc_status_var, wraplength=690).pack(anchor="w", pady=(10, 0))

        missing = [name for name in ("TK", "TrakLkup.dat", "fronten1.txd", "american.gxt")
                   if not asset_path_in_game_folder(name, "SA_PC").is_file()
                   or asset_path_in_game_folder(name, "SA_PC").stat().st_size <= 0]
        if missing:
            self.sa_pc_install_button.configure(state="disabled")
            self.sa_pc_status_var.set(
                "Built-in San Andreas PC file(s) missing: " + ", ".join(missing)
                + ". Put all four in Assets/SA_PC and rebuild the EXE."
            )

    def _choose_iso(self):
        path = filedialog.askopenfilename(
            title="Select GTA: Vice City Stories (PS2) ISO",
            filetypes=[("PS2 disc images", "*.iso *.bin *.img"), ("All files", "*.*")],
        )
        if path:
            self.iso_var.set(path)
            p = Path(path)
            suggestion = p.with_name(p.stem + "_HOLOLIVE_RADIO_PATCHED.iso")
            if not self.out_var.get():
                self.out_var.set(str(suggestion))

    def _choose_output(self):
        initial = self.out_var.get() or "HOLOLIVE_RADIO_PATCHED.iso"
        path = filedialog.asksaveasfilename(
            title="Save patched ISO as", initialfile=Path(initial).name,
            defaultextension=".iso", filetypes=[("ISO image", "*.iso"), ("All files", "*.*")],
        )
        if path:
            self.out_var.set(path)

    def _choose_psp_iso(self):
        path = filedialog.askopenfilename(
            title="Select GTA: Vice City Stories (PSP) ISO",
            filetypes=[("PSP ISO images", "*.iso"), ("All files", "*.*")],
        )
        if path:
            self.psp_iso_var.set(path)
            p = Path(path)
            if not self.psp_out_var.get():
                self.psp_out_var.set(str(p.with_name(p.stem + "_HOLOLIVE_RADIO_PATCHED.iso")))

    def _choose_psp_output(self):
        initial = self.psp_out_var.get() or "VCS_PSP_HOLOLIVE_RADIO_PATCHED.iso"
        path = filedialog.asksaveasfilename(
            title="Save patched PSP ISO as", initialfile=Path(initial).name,
            defaultextension=".iso", filetypes=[("ISO image", "*.iso"), ("All files", "*.*")],
        )
        if path:
            self.psp_out_var.set(path)

    def _about_psp(self):
        messagebox.showinfo(
            "GTA Vice City Stories PSP / Safety",
            "The PSP tab verifies PSP_GAME/PARAM.SFO against known GTA: Vice City Stories PSP disc IDs, then replaces the bundled radio audio at:\n\n"
            "• PSP_GAME\\USRDIR\\AUDIO\\MUSIC\\VCPR.AT3\n"
            "• PSP_GAME\\USRDIR\\RUNDATA\\ENGLISH.GXT\n"
            "• PSP_GAME\\USRDIR\\RUNDATA\\PSP\\GAME.DTZ\n\n"
            "All three replacement files must be present in Assets\\VCS_PSP when the EXE is built. They are bundled into the EXE and applied automatically; the PSP tab does not show replacement-file pickers. "
            "It creates a new ISO and never overwrites the input. The audio must fit within the target's existing sector allocation. "
            "This ISO patch is experimental and has not been verified in-game; test in PPSSPP first. Use only with a game image you are entitled to modify.",
        )

    def _start_psp_patch(self):
        iso_text = self.psp_iso_var.get().strip()
        out_text = self.psp_out_var.get().strip()
        if not iso_text or not out_text:
            messagebox.showwarning("Choose files", "Choose a PSP input ISO and output filename first.")
            return
        payloads = {name: asset_path(name) for name in PSP_TARGET_PATHS}
        missing = [
            name for name, path in payloads.items()
            if not path.is_file() or path.stat().st_size <= 0
        ]
        if missing:
            messagebox.showerror(
                "Required VCS PSP assets missing",
                "This installer build is missing required file(s): " + ", ".join(missing) +
                "\n\nPlace VCPR.AT3, ENGLISH.GXT, and GAME.DTZ in Assets\\VCS_PSP and rebuild the EXE.",
            )
            return
        iso_path = Path(iso_text).expanduser()
        out_path = Path(out_text).expanduser()
        if out_path.exists():
            messagebox.showwarning("Output already exists", "Choose a new output filename. Existing files will not be overwritten.")
            return
        try:
            for name, path in payloads.items():
                if not path.is_file() or path.stat().st_size <= 0:
                    raise ValueError(f"Embedded replacement file '{name}' is missing or empty: {path}")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Invalid replacement file", str(exc))
            return
        if not messagebox.askyesno(
            "Confirm experimental PSP patch",
            "Create a new patched GTA: Vice City Stories (PSP) ISO?\n\n"
            "The input ISO must have a recognized VCS PSP disc ID. The embedded VCPR.AT3, ENGLISH.GXT, and GAME.DTZ files will all replace their matching ISO entries if each fits its existing allocation.\n\n"
            "The original ISO will not be modified. This patch has not been verified in-game.",
        ):
            return

        self.psp_patch_button.configure(state="disabled")
        self.psp_progress.start(12)
        self.psp_status_var.set("Starting PSP ISO check…")

        def status(msg: str):
            self.psp_events.put(("status", msg))

        def worker():
            try:
                result = check_psp_image_and_patch(iso_path, out_path, payloads, status)
            except Exception as exc:
                self.psp_events.put(("error", f"{exc}\n\n{traceback.format_exc()}"))
            else:
                self.psp_events.put(("done", result))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_psp_events(self):
        try:
            while True:
                kind, value = self.psp_events.get_nowait()
                if kind == "status":
                    self.psp_status_var.set(str(value))
                else:
                    self.psp_progress.stop()
                    self.psp_patch_button.configure(state="normal")
                    if kind == "done":
                        self.psp_status_var.set("PSP ISO patch completed successfully.")
                        messagebox.showinfo("PSP patch complete", str(value))
                    else:
                        self.psp_status_var.set("PSP patch stopped; no completed output was kept.")
                        messagebox.showerror("Could not patch PSP ISO", str(value))
        except queue.Empty:
            pass
        self.root.after(100, self._poll_psp_events)

    def _choose_lcs_iso(self):
        path = filedialog.askopenfilename(
            title="Select GTA: Liberty City Stories (PSP) ISO",
            filetypes=[("PSP ISO images", "*.iso"), ("All files", "*.*")],
        )
        if path:
            self.lcs_iso_var.set(path)
            p = Path(path)
            if not self.lcs_out_var.get():
                self.lcs_out_var.set(str(p.with_name(p.stem + "_HOLOLIVE_RADIO_PATCHED.iso")))

    def _choose_lcs_output(self):
        initial = self.lcs_out_var.get() or "LCS_PSP_HOLOLIVE_RADIO_PATCHED.iso"
        path = filedialog.asksaveasfilename(
            title="Save patched LCS PSP ISO as", initialfile=Path(initial).name,
            defaultextension=".iso", filetypes=[("ISO image", "*.iso"), ("All files", "*.*")],
        )
        if path:
            self.lcs_out_var.set(path)

    def _about_lcs_psp(self):
        messagebox.showinfo(
            "GTA Liberty City Stories PSP / Safety",
            "The LCS PSP tab verifies PSP_GAME/PARAM.SFO against recognized GTA: Liberty City Stories (PSP) disc IDs, then automatically replaces all three bundled assets at these exact locations:\n\n"
            "• PSP_GAME\\USRDIR\\AUDIO\\MUSIC\\KJAH.AT3\n"
            "• PSP_GAME\\USRDIR\\TEXT\\ENGLISH.GXT\n"
            "• PSP_GAME\\USRDIR\\CHK\\PSPHR\\GAME.DTZ\n\n"
            "All three files must be present in Assets\\LCS_PSP when the EXE is built. They are embedded and applied automatically; the LCS tab does not show replacement-file pickers. "
            "It creates a new ISO and never overwrites the input. Each replacement must fit the target's existing sector allocation; ISO file data is not relocated. "
            "This ISO patch is experimental and has not been verified in-game. Test in PPSSPP first.",
        )

    def _start_lcs_patch(self):
        iso_text = self.lcs_iso_var.get().strip()
        out_text = self.lcs_out_var.get().strip()
        if not iso_text or not out_text:
            messagebox.showwarning("Choose files", "Choose an LCS PSP input ISO and output filename first.")
            return

        payloads = {name: asset_path_in_game_folder(name, "LCS_PSP") for name in LCS_PSP_TARGET_PATHS}
        missing = [name for name, path in payloads.items() if not path.is_file() or path.stat().st_size <= 0]
        if missing:
            messagebox.showerror(
                "Required LCS PSP assets missing",
                "This installer build is missing required file(s): " + ", ".join(missing) +
                "\n\nPlace KJAH.AT3, ENGLISH.GXT, and GAME.DTZ in Assets\\LCS_PSP on the PC used to build the EXE, then rebuild.",
            )
            return

        iso_path = Path(iso_text).expanduser()
        out_path = Path(out_text).expanduser()
        if out_path.exists():
            messagebox.showwarning("Output already exists", "Choose a new output filename. Existing files will not be overwritten.")
            return
        if not messagebox.askyesno(
            "Confirm experimental LCS PSP patch",
            "Create a new patched GTA: Liberty City Stories (PSP) ISO?\n\n"
            "The input ISO must have a recognized LCS PSP disc ID. The embedded KJAH.AT3, ENGLISH.GXT, and GAME.DTZ files will replace their matching ISO entries if each fits its existing allocation.\n\n"
            "The original ISO will not be modified. This patch has not been verified in-game.",
        ):
            return

        self.lcs_patch_button.configure(state="disabled")
        self.lcs_progress.start(12)
        self.lcs_status_var.set("Starting LCS PSP ISO check…")

        def status(msg: str):
            self.lcs_events.put(("status", msg))

        def worker():
            try:
                result = check_lcs_psp_image_and_patch(iso_path, out_path, payloads, status)
            except Exception as exc:
                self.lcs_events.put(("error", f"{exc}\n\n{traceback.format_exc()}"))
            else:
                self.lcs_events.put(("done", result))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_lcs_events(self):
        try:
            while True:
                kind, value = self.lcs_events.get_nowait()
                if kind == "status":
                    self.lcs_status_var.set(str(value))
                else:
                    self.lcs_progress.stop()
                    self.lcs_patch_button.configure(state="normal")
                    if kind == "done":
                        self.lcs_status_var.set("LCS PSP ISO patch completed successfully.")
                        messagebox.showinfo("LCS PSP patch complete", str(value))
                    else:
                        self.lcs_status_var.set("LCS PSP patch stopped; no completed output was kept.")
                        messagebox.showerror("Could not patch LCS PSP ISO", str(value))
        except queue.Empty:
            pass

    def _choose_pc_dir(self):
        path = filedialog.askdirectory(title="Locate your GTA: Vice City PC installation", mustexist=True)
        if path:
            self.pc_dir_var.set(path)
            self.pc_status_var.set("Game folder selected. Click Install PC Files to install the bundled Vice City assets.")

    def _about(self):
        messagebox.showinfo(
            "About / Safety",
            "The GTA VCS PS2 tab checks SYSTEM.CNF against known GTA: Vice City Stories (PS2) disc serials, then replaces AUDIO/MUSIC/VCPR.VB with the bundled experimental audio file.\n\n"
            "Classic GTA: Vice City (PS2) is not supported by this tab. The patch is experimental and has not been verified in-game. It creates a new output ISO and leaves the source image unchanged.\n\n"
            "Use only with a game image you are entitled to modify.",
        )


    def _choose_sa_pc_dir(self):
        path = filedialog.askdirectory(title="Locate your GTA: San Andreas PC installation", mustexist=True)
        if path:
            self.sa_pc_dir_var.set(path)
            self.sa_pc_status_var.set("Game folder selected. Click Install PC Files to install the bundled San Andreas TK assets.")

    def _about_sa_pc(self):
        messagebox.showinfo(
            "GTA San Andreas PC / Safety",
            "This tab installs the four bundled TK station files for GTA: San Andreas PC:\n\n"
            "• TK → audio/streams/TK\n"
            "• TrakLkup.dat → audio/CONFIG/TrakLkup.dat\n"
            "• fronten1.txd → models/fronten1.txd\n"
            "• american.gxt → text/american.gxt\n\n"
            "All four assets are loaded from Assets/SA_PC and bundled into the EXE at build time. The stream and TrakLkup.dat must come from the same mod package. TrakLkup.dat must contain complete 12-byte records. Existing files are backed up before replacement, and the installer attempts rollback if an install step fails. Back up the game folder too."
        )

    def _start_sa_pc_install(self):
        game_text = self.sa_pc_dir_var.get().strip()
        if not game_text:
            messagebox.showwarning("Choose installation", "Click Locate… and choose your GTA: San Andreas PC installation folder first.")
            return
        payloads = {name: asset_path_in_game_folder(name, "SA_PC")
                    for name in ("TK", "TrakLkup.dat", "fronten1.txd", "american.gxt")}
        missing = [name for name, path in payloads.items()
                   if not path.is_file() or path.stat().st_size <= 0]
        if missing:
            messagebox.showerror(
                "Required San Andreas PC assets missing",
                "This installer build is missing required file(s): " + ", ".join(missing)
                + "\n\nPut all four files in Assets\\SA_PC on the PC used to build the EXE, then rebuild.",
            )
            return
        game_dir = Path(game_text).expanduser()
        try:
            root, operations, destinations = prepare_sa_pc_install(game_dir, payloads)
        except Exception as exc:
            messagebox.showerror("Invalid San Andreas installation or mod files", str(exc))
            self.sa_pc_status_var.set("Installation stopped; no files were changed.")
            return
        if not operations:
            self.sa_pc_status_var.set("The selected source files are already at their destination paths.")
            messagebox.showinfo("Nothing to install", f"The files are already at their destination paths.\n\n{root}")
            return
        overwrites = [relative.as_posix() for relative, _source, destination in operations if destination.exists()]
        details = "\n".join(f"  • {relative.as_posix()}" for relative, _source, _destination in operations)
        warning = "\n\nExisting files will be backed up inside the game folder." if overwrites else "\n\nNo existing target files need replacing."
        if not messagebox.askyesno(
            "Confirm San Andreas mod installation",
            f"Install the four bundled TK station files into this GTA: San Andreas PC folder?\n\n{root}\n\n{details}{warning}\n\nContinue?",
        ):
            return
        self.sa_pc_install_button.configure(state="disabled")
        self.sa_pc_status_var.set("Installing San Andreas PC files…")
        self.root.update_idletasks()
        try:
            result = install_sa_pc_assets(root, payloads)
        except Exception as exc:
            self.sa_pc_status_var.set("Installation failed; rollback was attempted.")
            messagebox.showerror("San Andreas install failed", str(exc))
        else:
            self.sa_pc_status_var.set("San Andreas PC files installed successfully.")
            messagebox.showinfo("San Andreas install complete", result)
        finally:
            self.sa_pc_install_button.configure(state="normal")

    def _about_pc(self):
        messagebox.showinfo(
            "GTA Vice City PC / Safety",
            "The PC tab installs these bundled mod files into a classic GTA: Vice City PC folder:\n\n"
            "• american.gxt → text/american.gxt\n"
            "• fronten2.txd → models/fronten2.txd\n"
            "• VCPR.adf → Audio/VCPR.adf\n\n"
            "Put all three files in Assets/VC_PC before building the EXE. The installer uses those embedded copies automatically; only the game install folder is selected in the app. Existing target files are backed up before replacement, and the installer attempts to roll back changes if an install step fails. Back up the game folder before modding."
        )

    def _start_patch(self):
        iso_text = self.iso_var.get().strip()
        out_text = self.out_var.get().strip()
        if not iso_text or not out_text:
            messagebox.showwarning("Choose files", "Choose an input ISO and an output filename first.")
            return
        iso_path = Path(iso_text).expanduser()
        out_path = Path(out_text).expanduser()
        payload_path = asset_path("VCPR.VB")
        if out_path.exists():
            messagebox.showwarning("Output already exists", "Choose a new output filename. Existing files will not be overwritten.")
            return
        if not messagebox.askyesno(
            "Confirm experimental patch",
            "Create a new patched GTA: Vice City Stories (PS2) ISO?\n\nThe ISO's SYSTEM.CNF must identify a supported VCS PS2 release. Classic GTA: Vice City (PS2) is not supported.\n\nThe original ISO will not be modified. The audio patch is experimental and has not been verified in-game.",
        ):
            return
        self.patch_button.configure(state="disabled")
        self.progress.start(12)
        self.status_var.set("Starting…")

        def status(msg: str):
            self.events.put(("status", msg))

        def worker():
            try:
                result = check_image_and_patch(iso_path, out_path, payload_path, status)
                self.events.put(("done", result))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _start_pc_install(self):
        game_text = self.pc_dir_var.get().strip()
        if not game_text:
            messagebox.showwarning("Choose installation", "Click Locate… and choose your GTA: Vice City PC installation folder first.")
            return
        payloads = {name: asset_path_in_game_folder(name, "VC_PC")
                    for name in ("american.gxt", "fronten2.txd", "VCPR.adf")}
        missing = [name for name, path in payloads.items()
                   if not path.is_file() or path.stat().st_size <= 0]
        if missing:
            messagebox.showerror(
                "Required Vice City PC assets missing",
                "This installer build is missing required file(s): " + ", ".join(missing)
                + "\n\nPut all three files in Assets\\VC_PC on the PC used to build the EXE, then rebuild.",
            )
            return
        game_dir = Path(game_text).expanduser()
        try:
            root, operations, destinations = prepare_pc_install(game_dir, payloads)
        except Exception as exc:
            messagebox.showerror("Invalid PC installation or mod files", str(exc))
            self.pc_status_var.set("Installation stopped; no files were changed.")
            return
        if not operations:
            self.pc_status_var.set("The selected source files are already at their destination paths.")
            messagebox.showinfo("Nothing to install", f"The files are already at their destination paths.\n\n{root}")
            return
        overwrites = [relative.as_posix() for relative, _source, destination in operations if destination.exists()]
        details = "\n".join(f"  • {relative.as_posix()}" for relative, _source, _destination in operations)
        warning = "\n\nExisting files will be backed up inside the game folder." if overwrites else "\n\nNo existing target files need replacing."
        if not messagebox.askyesno(
            "Confirm PC mod installation",
            f"Install these files into this GTA: Vice City PC folder?\n\n{root}\n\n{details}{warning}\n\nContinue?",
        ):
            return
        self.pc_install_button.configure(state="disabled")
        self.pc_status_var.set("Installing PC files…")
        self.root.update_idletasks()
        try:
            result = install_pc_assets(root, payloads)
        except Exception as exc:
            self.pc_status_var.set("Installation failed; rollback was attempted.")
            messagebox.showerror("PC install failed", str(exc))
        else:
            self.pc_status_var.set("PC files installed successfully.")
            messagebox.showinfo("PC install complete", result)
        finally:
            self.pc_install_button.configure(state="normal")

    def _poll_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "status":
                    self.status_var.set(str(value))
                else:
                    self.progress.stop()
                    self.patch_button.configure(state="normal")
                    if kind == "done":
                        self.status_var.set("Completed successfully.")
                        messagebox.showinfo("Patch complete", str(value))
                    else:
                        self.status_var.set("Patch stopped; no completed output was kept.")
                        messagebox.showerror("Could not patch ISO", str(value))
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def run(self):
        self.root.mainloop()


def main():
    try:
        App().run()
    except Exception as exc:
        try:
            messagebox.showerror("GTA Hololive Radio Installer error", f"{exc}\n\n{traceback.format_exc()}")
        except Exception:
            print(f"Error: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
