#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Separate appearance/layout editor for Grand Theft Auto Hololive Radio Installer."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

APP_TITLE = "Grand Theft Auto Hololive Radio Installer — GUI Customizer"
CONFIG_NAME = "gui_customization.json"
DEFAULTS = {
    "window_title": "Grand Theft Auto Hololive Radio Installer",
    "header_text": "Grand Theft Auto Hololive Radio Installer",
    "window_width": 965,
    "window_height": 540,
    "theme": "Dark",
    "accent_color": "#7c3aed",
    "font_size": 10,
    "visible_tabs": {"vcs_ps2": True, "sa_ps2": True, "lcs_ps2": True, "vcs_psp": True, "lcs_psp": True, "vc_pc": True, "vc_ps2": True, "iii_ps2": True, "sa_pc": True},
    "tab_labels": {
        "vcs_ps2": "GTA VCS PS2", "sa_ps2": "GTA San Andreas PS2", "lcs_ps2": "GTA LCS PS2",
        "vcs_psp": "GTA VCS PSP", "lcs_psp": "GTA LCS PSP",
        "vc_pc": "GTA Vice City PC", "vc_ps2": "GTA Vice City PS2", "iii_ps2": "GTA III PS2", "sa_pc": "GTA San Andreas PC",
    },
}
# Keep this list in the same order as the main installer's tab strip.
TAB_INFO = [
    ("vcs_ps2", "GTA Vice City Stories — PS2"),
    ("vcs_psp", "GTA Vice City Stories — PSP"),
    ("lcs_ps2", "GTA Liberty City Stories — PS2"),
    ("lcs_psp", "GTA Liberty City Stories — PSP"),
    ("vc_ps2", "GTA Vice City — PS2"),
    ("vc_pc", "GTA Vice City — PC"),
    ("iii_ps2", "GTA III — PS2"),
    ("sa_ps2", "GTA San Andreas — PS2"),
    ("sa_pc", "GTA San Andreas — PC"),
]


def copy_defaults():
    return json.loads(json.dumps(DEFAULTS))


def find_installer_folder() -> str:
    """Prefer a folder that actually contains the installer the config belongs to."""
    here = Path(__file__).resolve().parent
    candidates = [here, here.parent, Path.cwd()]
    installer_names = (
        "Grand Theft Auto Hololive Radio Installer.py",
        "GrandTheftAutoHololiveRadioInstaller.exe",
        "Grand Theft Auto Hololive Radio Installer.exe",
    )
    for folder in candidates:
        if folder.is_dir() and any((folder / name).is_file() for name in installer_names):
            return str(folder)
    # Blank is intentional: a standalone customizer must ask the user to select
    # the real installer folder instead of silently saving settings beside itself.
    return ""


class Customizer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("760x790")
        self.root.minsize(680, 650)
        self.target_dir = tk.StringVar(value=find_installer_folder())
        self.window_title = tk.StringVar(value=DEFAULTS["window_title"])
        self.header_text = tk.StringVar(value=DEFAULTS["header_text"])
        self.width = tk.IntVar(value=DEFAULTS["window_width"])
        self.height = tk.IntVar(value=DEFAULTS["window_height"])
        self.theme = tk.StringVar(value=DEFAULTS["theme"])
        self.accent = tk.StringVar(value=DEFAULTS["accent_color"])
        self.font_size = tk.IntVar(value=DEFAULTS["font_size"])
        self.tab_labels = {key: tk.StringVar(value=label) for key, label in DEFAULTS["tab_labels"].items()}
        self.tab_visible = {key: tk.BooleanVar(value=True) for key, _ in TAB_INFO}
        self._build()
        self._load_existing()

    def _build(self):
        root = ttk.Frame(self.root, padding=14)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="GUI Customizer", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(root, text="Change the installer's appearance and tab labels. These settings do not change patching rules. Save to the exact folder containing the installer .py or .exe, then restart it.", wraplength=700).pack(anchor="w", pady=(2, 12))

        location = ttk.LabelFrame(root, text="Target application folder", padding=8)
        location.pack(fill="x", pady=(0, 10))
        ttk.Entry(location, textvariable=self.target_dir).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(location, text="Browse…", command=self._browse_folder).pack(side="left")

        appearance = ttk.LabelFrame(root, text="Window and appearance", padding=10)
        appearance.pack(fill="x", pady=(0, 10))
        self._field(appearance, "Window title", self.window_title, 0)
        self._field(appearance, "Main heading", self.header_text, 1)
        ttk.Label(appearance, text="Window size (width × height)").grid(row=2, column=0, sticky="w", pady=5)
        dimensions = ttk.Frame(appearance)
        dimensions.grid(row=2, column=1, sticky="w", pady=5)
        ttk.Spinbox(dimensions, from_=650, to=1600, increment=10, width=8, textvariable=self.width).pack(side="left")
        ttk.Label(dimensions, text=" × ").pack(side="left")
        ttk.Spinbox(dimensions, from_=450, to=1200, increment=10, width=8, textvariable=self.height).pack(side="left")
        ttk.Label(appearance, text="Theme").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Combobox(appearance, textvariable=self.theme, values=("Default", "Light", "Dark"), state="readonly", width=18).grid(row=3, column=1, sticky="w", pady=5)
        ttk.Label(appearance, text="Accent colour").grid(row=4, column=0, sticky="w", pady=5)
        colorrow = ttk.Frame(appearance)
        colorrow.grid(row=4, column=1, sticky="w", pady=5)
        ttk.Entry(colorrow, textvariable=self.accent, width=14).pack(side="left", padx=(0, 6))
        ttk.Button(colorrow, text="Choose…", command=self._choose_color).pack(side="left")
        ttk.Label(appearance, text="Font size").grid(row=5, column=0, sticky="w", pady=5)
        ttk.Spinbox(appearance, from_=8, to=18, width=8, textvariable=self.font_size).grid(row=5, column=1, sticky="w", pady=5)
        appearance.columnconfigure(1, weight=1)

        tabs = ttk.LabelFrame(root, text="Tab names and visibility", padding=10)
        tabs.pack(fill="both", expand=True, pady=(0, 10))
        ttk.Label(tabs, text="Show", width=7).grid(row=0, column=0, sticky="w")
        ttk.Label(tabs, text="Game tab / custom label").grid(row=0, column=1, sticky="w")
        for row, (key, description) in enumerate(TAB_INFO, start=1):
            ttk.Checkbutton(tabs, variable=self.tab_visible[key]).grid(row=row, column=0, sticky="w", padx=(8, 12), pady=3)
            line = ttk.Frame(tabs)
            line.grid(row=row, column=1, sticky="ew", pady=3)
            ttk.Label(line, text=description, width=39).pack(side="left")
            ttk.Entry(line, textvariable=self.tab_labels[key]).pack(side="left", fill="x", expand=True)
        tabs.columnconfigure(1, weight=1)
        buttons = ttk.Frame(root)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Load saved settings", command=self._load_existing).pack(side="left")
        ttk.Button(buttons, text="Reset defaults", command=self._reset).pack(side="left", padx=6)
        ttk.Button(buttons, text="Save customisation", command=self._save).pack(side="right")
        ttk.Button(buttons, text="Save and launch installer", command=self._save_and_launch).pack(side="right", padx=6)

    def _field(self, parent, label, variable, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=5)
        parent.columnconfigure(1, weight=1)

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Choose the folder containing the installer")
        if folder:
            self.target_dir.set(folder)
            self._load_existing(silent=True)

    def _choose_color(self):
        chosen = colorchooser.askcolor(color=self.accent.get(), parent=self.root, title="Choose accent colour")
        if chosen and chosen[1]:
            self.accent.set(chosen[1])

    def _config_path(self):
        folder = Path(self.target_dir.get()).expanduser()
        if not folder.is_dir():
            raise ValueError("Choose the folder containing the installer .py or .exe.")
        installer_names = (
            "Grand Theft Auto Hololive Radio Installer.py",
            "GrandTheftAutoHololiveRadioInstaller.exe",
            "Grand Theft Auto Hololive Radio Installer.exe",
        )
        if not any((folder / name).is_file() for name in installer_names):
            raise ValueError(
                "This folder does not contain the installer. Select the folder containing "
                "'Grand Theft Auto Hololive Radio Installer.py' or 'GrandTheftAutoHololiveRadioInstaller.exe'.\n\n"
                "The settings file must be beside the installer, not just beside the customizer."
            )
        return folder / CONFIG_NAME

    def _read_values(self):
        width, height, font_size = int(self.width.get()), int(self.height.get()), int(self.font_size.get())
        if not 650 <= width <= 1600 or not 450 <= height <= 1200:
            raise ValueError("Window width must be 650–1600 and height 450–1200.")
        if not 8 <= font_size <= 18:
            raise ValueError("Font size must be between 8 and 18.")
        color = self.accent.get().strip()
        if len(color) != 7 or not color.startswith("#"):
            raise ValueError("Accent colour must be a hex colour, for example #7c3aed.")
        try:
            int(color[1:], 16)
        except ValueError as exc:
            raise ValueError("Accent colour must be a hex colour, for example #7c3aed.") from exc
        return {
            "window_title": self.window_title.get().strip() or DEFAULTS["window_title"],
            "header_text": self.header_text.get().strip() or DEFAULTS["header_text"],
            "window_width": width, "window_height": height, "theme": self.theme.get(),
            "accent_color": color, "font_size": font_size,
            "visible_tabs": {key: bool(var.get()) for key, var in self.tab_visible.items()},
            "tab_labels": {key: (var.get().strip() or DEFAULTS["tab_labels"][key])[:80] for key, var in self.tab_labels.items()},
        }

    def _save(self, quiet=False):
        try:
            path = self._config_path()
            data = self._read_values()
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            if not quiet:
                messagebox.showinfo("Customisation saved", f"Settings saved to:\n{path}\n\nClose and reopen the installer to apply the changes.", parent=self.root)
            return path
        except (OSError, ValueError, tk.TclError) as exc:
            messagebox.showerror("Could not save settings", str(exc), parent=self.root)
            return None

    def _save_and_launch(self):
        path = self._save(quiet=True)
        if not path:
            return
        folder = path.parent
        candidates = [folder / "GrandTheftAutoHololiveRadioInstaller.exe", folder / "Grand Theft Auto Hololive Radio Installer.exe", folder / "Grand Theft Auto Hololive Radio Installer.py"]
        app = next((candidate for candidate in candidates if candidate.is_file()), None)
        if app is None:
            messagebox.showinfo("Settings saved", f"Settings saved to:\n{path}\n\nI couldn't find the installer executable or Python file in that folder. Open the installer manually to apply the changes.", parent=self.root)
            return
        try:
            if app.suffix.lower() == ".py":
                subprocess.Popen([sys.executable, str(app)], cwd=str(folder))
            else:
                subprocess.Popen([str(app)], cwd=str(folder))
        except OSError as exc:
            messagebox.showerror("Could not launch installer", str(exc), parent=self.root)
            return
        messagebox.showinfo("Installer launched", "Your saved settings will be used by the installer that just opened.", parent=self.root)

    def _load_existing(self, silent=False):
        try:
            path = self._config_path()
            data = copy_defaults()
            if path.exists():
                saved = json.loads(path.read_text(encoding="utf-8"))
                for key in ("window_title", "header_text", "window_width", "window_height", "theme", "accent_color", "font_size"):
                    if key in saved:
                        data[key] = saved[key]
                data["visible_tabs"].update(saved.get("visible_tabs", {}))
                data["tab_labels"].update(saved.get("tab_labels", {}))
            self.window_title.set(data["window_title"])
            self.header_text.set(data["header_text"])
            self.width.set(int(data["window_width"]))
            self.height.set(int(data["window_height"]))
            self.theme.set(data["theme"])
            self.accent.set(data["accent_color"])
            self.font_size.set(int(data["font_size"]))
            for key in self.tab_labels:
                self.tab_labels[key].set(data["tab_labels"].get(key, DEFAULTS["tab_labels"][key]))
                self.tab_visible[key].set(bool(data["visible_tabs"].get(key, True)))
            if not silent and path.exists():
                messagebox.showinfo("Settings loaded", f"Loaded settings from:\n{path}", parent=self.root)
        except (OSError, ValueError, TypeError, tk.TclError) as exc:
            if not silent:
                messagebox.showerror("Could not load settings", str(exc), parent=self.root)

    def _reset(self):
        data = copy_defaults()
        self.window_title.set(data["window_title"])
        self.header_text.set(data["header_text"])
        self.width.set(data["window_width"])
        self.height.set(data["window_height"])
        self.theme.set(data["theme"])
        self.accent.set(data["accent_color"])
        self.font_size.set(data["font_size"])
        for key in self.tab_labels:
            self.tab_labels[key].set(data["tab_labels"][key])
            self.tab_visible[key].set(True)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Customizer().run()
