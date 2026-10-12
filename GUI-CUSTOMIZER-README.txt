Grand Theft Auto Hololive Radio Installer — GUI Customizer

WHAT IT DOES
GUI Customizer.py is a separate Tkinter application that edits gui_customization.json. The installer reads this file on startup to customize the window title, main heading, window size, theme, accent colour, font size, and tab labels/visibility. These are visual settings only; they do not change game patching, disc-ID checks, asset paths, or installation rules.

HOW TO USE
1. Keep GUI Customizer.py in the same folder as the installer source or built installer EXE.
2. Run GUI Customizer.py with Python 3.10+ (Windows: `py "GUI Customizer.py"`).
3. Choose the target application folder at the top. It should be the folder containing `Grand Theft Auto Hololive Radio Installer.py` or the built installer EXE.
4. Customize the title, heading, dimensions, theme, accent colour, font size, tab labels, and which tabs are shown.
5. Click Save customisation. Close and reopen the installer to apply the changes.
6. Alternatively use Save and launch installer to save settings and try to launch the installer from the selected folder.

The customizer writes gui_customization.json next to the installer. If no configuration file exists, the installer uses its normal defaults. Use Reset defaults and then Save customisation to restore the default appearance.

NOTES
- GTA Vice City PS2 remains disabled/Coming Soon; the customizer does not add game support.
- Hiding a tab does not remove the underlying code or change any patching safeguards.
- This is a Python/Tkinter tool and needs Python 3.10+ to run unless packaged separately.
