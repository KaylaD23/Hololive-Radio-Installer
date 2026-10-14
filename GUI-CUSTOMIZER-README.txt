Grand Theft Auto Hololive Radio Installer — GUI Customizer

WHAT IT DOES
GUI Customizer.py is a separate Tkinter application that edits gui_customization.json. The installer reads this file on startup to customize the window title, main heading, window size, theme, accent colour, font size, banner visibility/image/scaling, and tab labels/visibility. These are visual settings only; they do not change game patching, disc-ID checks, asset paths, or installation rules.

HOW TO USE
1. Keep GUI Customizer.py in the same folder as the installer source or built installer EXE.
2. Run GUI Customizer.py with Python 3.10+ (Windows: `py "GUI Customizer.py"`).
3. Choose the target application folder at the top. It should be the folder containing `Grand Theft Auto Hololive Radio Installer.py` or the built installer EXE.
4. Customize the title, heading, dimensions, theme, accent colour, font size, banner visibility/image/scaling, tab labels, and which tabs are shown.
5. In “Tab order (top to bottom)”, select a tab and use Move up / Move down to change its left-to-right position in the installer. “Reset order” restores the default sequence. The order list updates to show your custom tab labels.
6. Click Save customisation. Close and reopen the installer to apply the changes.
6. Alternatively use Save and launch installer to save settings and try to launch the installer from the selected folder.

The customizer writes gui_customization.json next to the installer. The saved tab_order array determines the left-to-right order of game tabs; existing settings files without tab_order use the default sequence. If no configuration file exists, the installer uses its normal defaults. Use Reset defaults and then Save customisation to restore the default appearance and tab order.

NOTES
- GTA Vice City PS2 remains disabled/Coming Soon; the customizer does not add game support.
- Hiding a tab does not remove the underlying code or change any patching safeguards.
- This is a Python/Tkinter tool and needs Python 3.10+ to run unless packaged separately.

BANNER CUSTOMISATION
- Turn the banner image on or off. When disabled, the main heading is shown as text instead.
- Choose a PNG/JPG/WebP/BMP/GIF image. GUI Customizer copies and converts it to hololive_radio_banner_custom.png beside the installer.
- The custom image is included in the EXE on the next build when selected in gui_customization.json.
- Proportional mode scales to the available width and preserves image aspect ratio. Crop mode fills a fixed-height banner area without distorting artwork; adjust height from 60 to 260 pixels.
- Use bundled restores the built-in banner selection; it does not delete the custom PNG file.
The tab visibility, label, and ordering editor also includes the GTA III PS2 tab (gta3_ps2). Reordering affects presentation only; each tab remains connected to its original game-specific patching logic and bundled asset folder.

The main installer and GUI Customizer both use hololive_radio_icon.ico, with hololive_radio_icon.png as a Tk window-icon fallback. The Windows EXE build sets the Hololive ICO as the executable icon and the main app applies a stable AppUserModelID for correct taskbar grouping.

Definitive Edition tabs: GUI Customizer includes visibility, label editing, and ordering for GTA Vice City - The Definitive Edition and GTA San Andreas - The Definitive Edition. The configured VC_DE/SA_DE payload-to-game mapping is documented in the main README.txt.
