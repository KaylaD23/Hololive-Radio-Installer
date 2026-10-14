#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Separate appearance/layout editor for Grand Theft Auto Hololive Radio Installer."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

try:
    from PIL import Image
except ImportError:
    Image = None

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
    "banner_enabled": True,
    "banner_custom_image": "",
    "banner_fit_mode": "proportional",
    "banner_fixed_height": 120,
    "visible_tabs": {"gta3_ps2": True, "vcs_ps2": True, "sa_ps2": True, "lcs_ps2": True, "vcs_psp": True, "lcs_psp": True, "vc_pc": True, "vc_ps2": True, "sa_pc": True, "vc_de": True, "sa_de": True},
    "tab_order": ["gta3_ps2", "vcs_ps2", "vcs_psp", "lcs_ps2", "lcs_psp", "vc_ps2", "vc_pc", "sa_ps2", "sa_pc", "vc_de", "sa_de"],
    "tab_labels": {
        "gta3_ps2": "GTA III PS2",
        "vcs_ps2": "GTA VCS PS2", "sa_ps2": "GTA San Andreas PS2", "lcs_ps2": "GTA LCS PS2",
        "vcs_psp": "GTA VCS PSP", "lcs_psp": "GTA LCS PSP",
        "vc_pc": "GTA Vice City PC", "vc_ps2": "GTA Vice City PS2 [Coming Soon]", "sa_pc": "GTA San Andreas PC",
        "vc_de": "GTA Vice City - The Definitive Edition", "sa_de": "GTA San Andreas - The Definitive Edition",
    },
}
# Keep this list in the same order as the main installer's tab strip.
TAB_INFO = [
    ("gta3_ps2", "GTA III — PS2"),
    ("vcs_ps2", "GTA Vice City Stories — PS2"),
    ("vcs_psp", "GTA Vice City Stories — PSP"),
    ("lcs_ps2", "GTA Liberty City Stories — PS2"),
    ("lcs_psp", "GTA Liberty City Stories — PSP"),
    ("vc_ps2", "GTA Vice City — PS2"),
    ("vc_pc", "GTA Vice City — PC"),
    ("sa_ps2", "GTA San Andreas — PS2"),
    ("sa_pc", "GTA San Andreas — PC"),
    ("vc_de", "GTA Vice City — Definitive Edition"),
    ("sa_de", "GTA San Andreas — Definitive Edition"),
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
        if sys.platform == "win32":
            try:
                import ctypes
                set_app_id = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
                set_app_id.argtypes = [ctypes.c_wchar_p]
                set_app_id.restype = ctypes.c_long
                set_app_id("HololiveRadio.Customizer")
            except (AttributeError, OSError, TypeError):
                pass
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        folder = Path(__file__).resolve().parent
        ico = folder / "hololive_radio_icon.ico"
        png = folder / "hololive_radio_icon.png"
        try:
            if ico.is_file():
                self.root.iconbitmap(default=str(ico))
                self.root.iconbitmap(str(ico))
        except (tk.TclError, OSError):
            pass
        try:
            if png.is_file():
                self._hololive_icon_photo = tk.PhotoImage(file=str(png))
                self.root.iconphoto(True, self._hololive_icon_photo)
            else:
                self._hololive_icon_photo = None
        except (tk.TclError, OSError):
            self._hololive_icon_photo = None
        self.root.geometry("860x800")
        self.root.minsize(700, 560)
        self.target_dir = tk.StringVar(value=find_installer_folder())
        self.window_title = tk.StringVar(value=DEFAULTS["window_title"])
        self.header_text = tk.StringVar(value=DEFAULTS["header_text"])
        self.width = tk.IntVar(value=DEFAULTS["window_width"])
        self.height = tk.IntVar(value=DEFAULTS["window_height"])
        self.theme = tk.StringVar(value=DEFAULTS["theme"])
        self.accent = tk.StringVar(value=DEFAULTS["accent_color"])
        self.font_size = tk.IntVar(value=DEFAULTS["font_size"])
        self.banner_enabled = tk.BooleanVar(value=DEFAULTS["banner_enabled"])
        self.banner_custom_image = tk.StringVar(value=DEFAULTS["banner_custom_image"])
        self.banner_fit_mode = tk.StringVar(value=DEFAULTS["banner_fit_mode"])
        self.banner_fit_mode_display = tk.StringVar(value="Proportional — resize smoothly, keep proportions")
        self.banner_fixed_height = tk.IntVar(value=DEFAULTS["banner_fixed_height"])
        self.tab_labels = {key: tk.StringVar(value=label) for key, label in DEFAULTS["tab_labels"].items()}
        self.tab_visible = {key: tk.BooleanVar(value=True) for key, _ in TAB_INFO}
        self.tab_order = list(DEFAULTS["tab_order"])
        self._build()
        for variable in self.tab_labels.values():
            variable.trace_add("write", self._on_tab_label_changed)
        self._load_existing()

    def _build(self):
        # A scrollable editor keeps the Save buttons reachable on smaller laptop
        # displays after the banner options are added.
        viewport = ttk.Frame(self.root)
        viewport.pack(fill="both", expand=True)
        self._scroll_canvas = tk.Canvas(viewport, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=self._scroll_canvas.yview)
        self._scroll_canvas.configure(yscrollcommand=scrollbar.set)
        self._scroll_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        root = ttk.Frame(self._scroll_canvas, padding=14)
        self._canvas_content = root
        self._canvas_window = self._scroll_canvas.create_window((0, 0), window=root, anchor="nw")
        root.bind("<Configure>", self._update_scroll_region, add="+")
        self._scroll_canvas.bind("<Configure>", self._resize_canvas_content, add="+")
        self.root.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.root.bind_all("<Button-4>", self._on_mousewheel_linux, add="+")
        self.root.bind_all("<Button-5>", self._on_mousewheel_linux, add="+")
        ttk.Label(root, text="GUI Customizer", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(root, text="Customize the installer’s appearance, banner, tab order, and tab labels. These settings do not change patching rules. Save beside the installer .py or .exe, then reopen the installer to apply them.", wraplength=760).pack(anchor="w", pady=(2, 12))

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

        banner = ttk.LabelFrame(root, text="Banner customisation", padding=10)
        banner.pack(fill="x", pady=(0, 10))
        ttk.Checkbutton(banner, text="Show banner image", variable=self.banner_enabled).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 5))
        ttk.Label(banner, text="Custom banner image").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(banner, textvariable=self.banner_custom_image, state="readonly").grid(
            row=1, column=1, sticky="ew", padx=(8, 6), pady=4)
        banner_buttons = ttk.Frame(banner)
        banner_buttons.grid(row=1, column=2, sticky="e", pady=4)
        ttk.Button(banner_buttons, text="Choose image…", command=self._browse_banner_image).pack(side="left")
        ttk.Button(banner_buttons, text="Use bundled", command=self._use_bundled_banner).pack(side="left", padx=(5, 0))
        ttk.Label(banner, text="Scaling").grid(row=2, column=0, sticky="w", pady=4)
        self.banner_mode_box = ttk.Combobox(
            banner, textvariable=self.banner_fit_mode_display, state="readonly", width=42,
            values=("Proportional — resize smoothly, keep proportions",
                    "Fill fixed-height slot — crop edges"),
        )
        self.banner_mode_box.grid(row=2, column=1, sticky="w", padx=(8, 6), pady=4)
        self.banner_mode_box.bind("<<ComboboxSelected>>", self._on_banner_mode_selected)
        ttk.Label(banner, text="Banner height (crop mode)").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Spinbox(banner, from_=60, to=260, increment=5, width=8,
                    textvariable=self.banner_fixed_height).grid(row=3, column=1, sticky="w", padx=(8, 6), pady=4)
        ttk.Label(banner, text="The selected image is copied beside the installer and bundled on the next EXE build.",
                  wraplength=650).grid(row=4, column=0, columnspan=3, sticky="w", pady=(3, 0))
        banner.columnconfigure(1, weight=1)
        self._set_banner_mode_display(self.banner_fit_mode.get())

        order_box = ttk.LabelFrame(root, text="Tab order (top to bottom)", padding=10)
        order_box.pack(fill="x", pady=(0, 10))
        ttk.Label(
            order_box,
            text="Select a game tab and move it up or down. The installer uses this order from left to right.",
            wraplength=700,
        ).pack(anchor="w", pady=(0, 6))
        order_row = ttk.Frame(order_box)
        order_row.pack(fill="x", expand=True)
        list_frame = ttk.Frame(order_row)
        list_frame.pack(side="left", fill="x", expand=True)
        self._tab_order_listbox = tk.Listbox(
            list_frame, height=min(9, len(TAB_INFO)), exportselection=False,
            activestyle="dotbox", selectmode="browse",
        )
        order_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self._tab_order_listbox.yview)
        self._tab_order_listbox.configure(yscrollcommand=order_scroll.set)
        self._tab_order_listbox.pack(side="left", fill="x", expand=True)
        order_scroll.pack(side="right", fill="y")
        order_buttons = ttk.Frame(order_row)
        order_buttons.pack(side="left", fill="y", padx=(8, 0))
        ttk.Button(order_buttons, text="Move up ↑", command=lambda: self._move_tab_order(-1)).pack(fill="x", pady=(0, 5))
        ttk.Button(order_buttons, text="Move down ↓", command=lambda: self._move_tab_order(1)).pack(fill="x", pady=(0, 5))
        ttk.Button(order_buttons, text="Reset order", command=self._reset_tab_order).pack(fill="x")
        self._tab_order_listbox.bind("<Alt-Up>", lambda _event: self._move_tab_order(-1))
        self._tab_order_listbox.bind("<Alt-Down>", lambda _event: self._move_tab_order(1))
        self._refresh_tab_order_listbox()

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

    def _on_tab_label_changed(self, *_args):
        # Keep the order preview in sync with labels as the user edits them.
        self._refresh_tab_order_listbox()

    def _tab_display_text(self, key):
        label = self.tab_labels.get(key)
        if label is not None:
            current = label.get().strip()
            if current:
                return current
        return dict(TAB_INFO).get(key, key)

    def _refresh_tab_order_listbox(self, selected_index=None):
        """Redraw the visible order list from the stable tab IDs."""
        if not hasattr(self, "_tab_order_listbox"):
            return
        box = self._tab_order_listbox
        if selected_index is None:
            current = box.curselection()
            selected_index = current[0] if current else 0
        box.delete(0, "end")
        for key in self.tab_order:
            box.insert("end", self._tab_display_text(key))
        if self.tab_order:
            selected_index = max(0, min(int(selected_index), len(self.tab_order) - 1))
            box.selection_clear(0, "end")
            box.selection_set(selected_index)
            box.activate(selected_index)
            box.see(selected_index)

    def _move_tab_order(self, direction):
        box = getattr(self, "_tab_order_listbox", None)
        if box is None or not self.tab_order:
            return "break"
        selected = box.curselection()
        if not selected:
            return "break"
        old_index = selected[0]
        new_index = old_index + (-1 if direction < 0 else 1)
        if 0 <= new_index < len(self.tab_order):
            self.tab_order[old_index], self.tab_order[new_index] = self.tab_order[new_index], self.tab_order[old_index]
            self._refresh_tab_order_listbox(new_index)
        return "break"

    def _reset_tab_order(self):
        self.tab_order = list(DEFAULTS["tab_order"])
        self._refresh_tab_order_listbox(0)

    def _normalized_tab_order(self, value):
        """Drop malformed/duplicate IDs and append any new tabs in default order."""
        allowed = [key for key, _description in TAB_INFO]
        cleaned = []
        if isinstance(value, list):
            for key in value:
                if isinstance(key, str) and key in allowed and key not in cleaned:
                    cleaned.append(key)
        return cleaned + [key for key in DEFAULTS["tab_order"] if key not in cleaned]

    def _update_scroll_region(self, _event=None):
        try:
            self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))
        except tk.TclError:
            pass

    def _resize_canvas_content(self, event):
        try:
            self._scroll_canvas.itemconfigure(self._canvas_window, width=max(1, event.width))
        except tk.TclError:
            pass

    def _on_mousewheel(self, event):
        # Windows/macOS wheel delta; only scroll this customizer viewport.
        try:
            self._scroll_canvas.yview_scroll(int(-event.delta / 120), "units")
        except (tk.TclError, AttributeError):
            pass

    def _on_mousewheel_linux(self, event):
        try:
            self._scroll_canvas.yview_scroll(-1 if event.num == 4 else 1, "units")
        except (tk.TclError, AttributeError):
            pass

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

    def _set_banner_mode_display(self, mode):
        """Synchronize the friendly display label with the stable JSON value."""
        mode = mode if mode in ("proportional", "crop") else "proportional"
        label = ("Fill fixed-height slot — crop edges" if mode == "crop"
                 else "Proportional — resize smoothly, keep proportions")
        self.banner_fit_mode.set(mode)
        if hasattr(self, "banner_fit_mode_display"):
            self.banner_fit_mode_display.set(label)

    def _on_banner_mode_selected(self, _event=None):
        selected = self.banner_fit_mode_display.get()
        self.banner_fit_mode.set("crop" if selected.startswith("Fill fixed-height") else "proportional")

    def _browse_banner_image(self):
        try:
            target_folder = self._config_path().parent
        except (OSError, ValueError) as exc:
            messagebox.showerror("Choose installer folder first", str(exc), parent=self.root)
            return
        selected = filedialog.askopenfilename(
            parent=self.root, title="Choose a banner image",
            filetypes=(("Image files", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"), ("PNG files", "*.png"), ("All files", "*.*")),
        )
        if not selected:
            return
        source_path = Path(selected)
        destination = target_folder / "hololive_radio_banner_custom.png"
        try:
            if source_path.resolve() == destination.resolve() and destination.is_file():
                self.banner_custom_image.set(destination.name)
                self.banner_enabled.set(True)
                return
            if Image is not None:
                with Image.open(source_path) as source:
                    source.load()
                    source.convert("RGBA").save(destination, format="PNG", optimize=True)
            elif source_path.suffix.casefold() == ".png":
                shutil.copy2(source_path, destination)
            else:
                raise ValueError("Converting JPG, WebP, BMP, and GIF banners requires Pillow. Install it with: py -m pip install pillow")
            self.banner_custom_image.set(destination.name)
            self.banner_enabled.set(True)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not load banner image", str(exc), parent=self.root)

    def _use_bundled_banner(self):
        self.banner_custom_image.set("")

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
        fit_mode = self.banner_fit_mode.get()
        if fit_mode not in ("proportional", "crop"):
            fit_mode = "proportional"
        banner_height = int(self.banner_fixed_height.get())
        if not 60 <= banner_height <= 260:
            raise ValueError("Banner height must be between 60 and 260 pixels.")
        custom_banner = self.banner_custom_image.get().strip()
        if custom_banner and Path(custom_banner).name != custom_banner:
            raise ValueError("Choose the custom banner using the Browse button so it is copied beside the installer.")
        if custom_banner:
            target_folder = Path(self.target_dir.get()).expanduser()
            if not (target_folder / custom_banner).is_file():
                raise ValueError("The custom banner image is missing beside the installer. Choose it again.")
        return {
            "window_title": self.window_title.get().strip() or DEFAULTS["window_title"],
            "header_text": self.header_text.get().strip() or DEFAULTS["header_text"],
            "window_width": width, "window_height": height, "theme": self.theme.get(),
            "accent_color": color, "font_size": font_size,
            "banner_enabled": bool(self.banner_enabled.get()),
            "banner_custom_image": custom_banner,
            "banner_fit_mode": fit_mode,
            "banner_fixed_height": banner_height,
            "visible_tabs": {key: bool(var.get()) for key, var in self.tab_visible.items()},
            "tab_order": self._normalized_tab_order(self.tab_order),
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
                for key in ("window_title", "header_text", "window_width", "window_height", "theme", "accent_color", "font_size", "banner_enabled", "banner_custom_image", "banner_fit_mode", "banner_fixed_height", "tab_order"):
                    if key in saved:
                        data[key] = saved[key]
                data["visible_tabs"].update(saved.get("visible_tabs", {}))
                data["tab_labels"].update(saved.get("tab_labels", {}))
            data["tab_order"] = self._normalized_tab_order(data.get("tab_order"))
            self.window_title.set(data["window_title"])
            self.header_text.set(data["header_text"])
            self.width.set(int(data["window_width"]))
            self.height.set(int(data["window_height"]))
            self.theme.set(data["theme"])
            self.accent.set(data["accent_color"])
            self.font_size.set(int(data["font_size"]))
            self.banner_enabled.set(bool(data.get("banner_enabled", True)))
            self.banner_custom_image.set(str(data.get("banner_custom_image", "")))
            self.banner_fixed_height.set(int(data.get("banner_fixed_height", 120)))
            self._set_banner_mode_display(data.get("banner_fit_mode", "proportional"))
            for key in self.tab_labels:
                self.tab_labels[key].set(data["tab_labels"].get(key, DEFAULTS["tab_labels"][key]))
                self.tab_visible[key].set(bool(data["visible_tabs"].get(key, True)))
            self.tab_order = list(data["tab_order"])
            self._refresh_tab_order_listbox(0)
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
        self.banner_enabled.set(data["banner_enabled"])
        self.banner_custom_image.set(data["banner_custom_image"])
        self.banner_fixed_height.set(data["banner_fixed_height"])
        self._set_banner_mode_display(data["banner_fit_mode"])
        for key in self.tab_labels:
            self.tab_labels[key].set(data["tab_labels"][key])
            self.tab_visible[key].set(True)
        self.tab_order = list(data["tab_order"])
        self._refresh_tab_order_listbox(0)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Customizer().run()
