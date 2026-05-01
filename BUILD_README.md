# Building PrepCore.exe

This document explains how to build the PrepCore application into an executable file.

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Windows OS (for building .exe)

## Quick Start

### Method 1: Using the Batch Script (Easiest)

1. Open Command Prompt or PowerShell in the project directory
2. Run: `build.bat`
3. Wait for the build to complete (may take several minutes)
4. The executable will be in the `dist` folder

### Method 2: Using Python Build Script

1. Open Command Prompt or PowerShell in the project directory
2. Run: `python build.py`
3. Wait for the build to complete
4. The executable will be in the `dist` folder

### Method 3: Manual Build with PyInstaller

```bash
# Install dependencies
pip install pyinstaller pillow PySide6

# Prepare assets
python prepare_assets.py

# Build executable
pyinstaller --onefile --windowed --name PrepCore --icon=icon.png main.py
```

## Build Features

✅ **Single .exe File**: The entire application is bundled into one executable
✅ **Rounded Icon**: The Logo_rounded.png provides a modern app icon with rounded corners
✅ **Taskbar Icon**: The icon.png is used for the taskbar
✅ **First-Run Experience**: On first launch, the app starts with a blank slate (no sample data)
✅ **Bundled Assets**: All images, audio, and data files are included
✅ **No Console Window**: Runs as a GUI application

## Output Structure

After building, the `dist` folder will contain:

```
dist/
├── PrepCore.exe          # The main executable
└── [other support files]
```

To distribute, simply copy the entire `dist` folder to users.

## First-Run Detection

When users first launch the app:
- The app will start completely blank (no subjects loaded)
- Users can add subjects and import their own data
- On subsequent launches, the app will remember their data
- The `.firstrun` marker file ensures first-run only happens once

## Troubleshooting

### "PyInstaller not found" error
```bash
pip install pyinstaller
```

### "Pillow not found" error
```bash
pip install pillow
```

### Large file size
The executable may be 200-500MB because it includes Python and all dependencies. This is normal.

### Missing files in executable
Make sure all data files exist before building:
- `Logo.png` (will be converted to `Logo_rounded.png`)
- `icon.png`
- `board_exam.ui`
- `Classic Alarm Clock - Sound Effect  ProSounds.mp3`

## Development vs Distribution

- **For Development**: Run `python main.py` directly
- **For Distribution**: Create the .exe using this build process and share the `dist` folder

## Tips

1. Run `build.py` or `build.bat` regularly during development to ensure the executable builds correctly
2. Clean old builds before rebuilding to avoid issues
3. Test the executable thoroughly before distributing
4. Keep a backup of the development directory

## Need Help?

If you encounter issues:
1. Ensure Python 3.10+ is installed
2. Run `pip install -r requirements.txt` (if available)
3. Check that all image and audio files exist
4. Verify the project structure is intact

---

**Build Date**: Generated automatically by build scripts
**PrepCore Version**: See main.py for version info
