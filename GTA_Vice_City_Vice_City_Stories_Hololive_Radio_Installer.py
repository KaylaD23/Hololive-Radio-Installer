#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 contributors to this project
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3. See LICENSE.
"""GTA Vice City & Vice City Stories Hololive Radio Installer.
Current experimental build: GTA: Vice City (PS2) VCPR.VB only.

Creates a new patched ISO and never modifies the selected source image.
Designed for ordinary 2048-byte-sector ISO9660 images; compressed ISZ and
raw 2352-byte CD images are intentionally rejected.
"""
from __future__ import annotations

import os
import queue
import shutil
import struct
import sys
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

SECTOR_SIZE = 2048
PVD_FIRST_SECTOR = 16
MAX_DIRECTORY_DEPTH = 64
APP_TITLE = "GTA Vice City & Vice City Stories Hololive Radio Installer"


def asset_path(name: str) -> Path:
    """Locate packaged asset in source mode or PyInstaller one-file mode."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


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
            # GTA: Vice City (PS2) stores this station at AUDIO/MUSIC/VCPR.VB.
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


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        # Use the bundled Hololive artwork for the GUI window icon.
        try:
            self.root.iconbitmap(str(asset_path("hololive_radio_icon.ico")))
        except (tk.TclError, OSError):
            pass
        self.root.geometry("680x330")
        self.root.minsize(600, 300)
        self.iso_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Choose a GTA: Vice City Or Vice City Stories PS2 ISO image to begin.")
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._build_ui()
        self.root.after(100, self._poll_events)

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="GTA Vice City & Vice City Stories Hololive Radio Installer", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Current build patches GTA: Vice City (PS2) only. Vice City Stories support is not included yet. Creates a separate ISO; experimental mod.",
            wraplength=635,
        ).pack(anchor="w", pady=(6, 14))

        row1 = ttk.Frame(outer)
        row1.pack(fill="x", pady=4)
        ttk.Label(row1, text="Input ISO", width=11).pack(side="left")
        ttk.Entry(row1, textvariable=self.iso_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row1, text="Browse…", command=self._choose_iso).pack(side="left")

        row2 = ttk.Frame(outer)
        row2.pack(fill="x", pady=4)
        ttk.Label(row2, text="Output ISO", width=11).pack(side="left")
        ttk.Entry(row2, textvariable=self.out_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row2, text="Save as…", command=self._choose_output).pack(side="left")

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(14, 8))
        self.patch_button = ttk.Button(buttons, text="Create Patched ISO", command=self._start_patch)
        self.patch_button.pack(side="left")
        ttk.Button(buttons, text="About / Safety", command=self._about).pack(side="left", padx=8)

        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.pack(fill="x", pady=(4, 8))
        ttk.Label(outer, textvariable=self.status_var, wraplength=635).pack(anchor="w")

        ttk.Label(outer, text="Supports plain 2048-byte-sector ISO9660 images. Compressed ISZ and raw 2352-byte images are not supported.",
                  foreground="#555555", wraplength=635).pack(anchor="w", pady=(12, 0))

    def _choose_iso(self):
        path = filedialog.askopenfilename(
            title="Select GTA: Vice City (PS2) ISO",
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
            title="Save patched ISO as",
            initialfile=Path(initial).name,
            defaultextension=".iso",
            filetypes=[("ISO image", "*.iso"), ("All files", "*.*")],
        )
        if path:
            self.out_var.set(path)

    def _about(self):
        messagebox.showinfo(
            "About / Safety",
            "This installer replaces AUDIO/MUSIC/VCPR.VB in a plain GTA: Vice City (PS2) ISO with the bundled experimental audio file.\n\n"
            "Although the installer is named for both Vice City and Vice City Stories, this build does NOT patch Vice City Stories yet.\n\n"
            "It creates a new output ISO and leaves the original alone. It does not include a game ISO.\n\n"
            "The replacement was converted from a supplied WAV-style VCPR.VB, but compatibility has not been confirmed in-game. "
            "Back up your disc image and test in PCSX2 first. Use only with a game image you are entitled to modify.",
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
            "Create a new patched ISO?\n\nThe original ISO will not be modified.\n\nThe audio patch is experimental and has not been verified in-game.",
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
