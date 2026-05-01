# PrepCore - Quick Build Guide

## Build Your First Executable

### Step 1: Open Command Prompt

Press `Windows Key + R`, type `cmd`, and press Enter.

### Step 2: Navigate to Project

```bash
cd /path/to/BOARDEXAMAPP
```

Example:
```bash
cd F:\Projects\Coding\BOARDEXAMAPP
```

### Step 3: Run the Build

**Option A - Quickest (Batch File):**
```bash
build.bat
```

**Option B - Python Script:**
```bash
python build.py
```

### Step 4: Wait for Build

The build process will:
1. ✓ Install dependencies (PyInstaller, Pillow)
2. ✓ Create rounded logo icon
3. ✓ Build the executable
4. ✓ Package all files

**This may take 5-15 minutes depending on your computer.**

### Step 5: Run Your App

After the build completes:

```bash
dist\PrepCore.exe
```

Or navigate to the `dist` folder and double-click `PrepCore.exe`

## First Launch Experience

✨ **Important**: On first launch, the app will start **completely blank** (no existing data).

This gives your users a fresh start to:
- Add their own subjects
- Import their own questions
- Customize their study materials

## What's New

✓ **Rounded Icon**: Modern looking app icon with rounded corners  
✓ **Taskbar Icon**: Beautiful icon in Windows taskbar  
✓ **Bundled Audio**: Alarm sound included in exe  
✓ **Bundled Images**: All images included  
✓ **Single File**: Everything in one `.exe` file  
✓ **No Installation**: Users just download and run  

## Distribute to Others

To share your app:

1. Open the `dist` folder
2. Right-click `PrepCore.exe` 
3. Select "Send to" > "Compressed (zipped) folder"
4. Share the `.zip` file

Users can:
1. Download and extract the zip
2. Run `PrepCore.exe`
3. No installation needed!

## File Sizes

- `PrepCore.exe`: ~250-350 MB (includes Python runtime)
- Complete `dist` folder: ~300-400 MB

This is normal for PyInstaller executables.

## Troubleshooting

**Build fails with "PyInstaller not found"**
```bash
pip install pyinstaller
```

**Build fails with "Pillow not found"**
```bash
pip install pillow
```

**Missing icon in built exe**
- Ensure `icon.png` exists before building
- Run `build.bat` or `build.py` again

**App window icon looks wrong**
- The rounded logo (Logo_rounded.png) is created automatically
- If it's missing, run `python prepare_assets.py`

## Advanced: Custom Configuration

To modify the build:

1. Edit `build.py` or `build.bat`
2. Change `--onefile` to `--onedir` for one-folder instead of single-file
3. Remove `--windowed` to show a console window
4. Modify `--icon=icon.png` to use a different icon

## Reverting to Development

To go back to development mode:

```bash
python main.py
```

This runs the app directly from source without building an exe.

---

**Need more help?** Check `BUILD_README.md` for detailed information.
