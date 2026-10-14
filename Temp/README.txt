Temporary build output folder

The Windows build scripts place Python temporary files, pip cache, PyInstaller work files, and generated spec files under this directory. The final executable is still written to dist/. This folder is included so the build does not rely on the machine-wide TEMP directory.
