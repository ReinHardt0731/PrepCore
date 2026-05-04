#!/usr/bin/env python3
"""
Build script for PrepCore - Creates PrepCore.exe using PyInstaller
Usage: python build.py
"""

import subprocess
import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_ROOT = PROJECT_ROOT / "assets"
IMAGES_ROOT = ASSETS_ROOT / "images"
ENTRYPOINT = PROJECT_ROOT / "src" / "main.py"

def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n[STEP] {description}")
    print(f"       Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, shell=False, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"[ERROR] {description} failed with code {result.returncode}")
        return False
    print(f"[OK] {description} completed")
    return True


def install_dependencies():
    """Install required packages."""
    print("\n[SETUP] Checking dependencies...")
    
    try:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--version"])
        print("[OK] PyInstaller is installed")
    except ImportError:
        print("[INSTALL] PyInstaller not found, installing...")
        if not run_command([sys.executable, "-m", "pip", "install", "pyinstaller"], 
                         "Installing PyInstaller"):
            return False
    
    try:
        import PIL
        print("[OK] Pillow is installed")
    except ImportError:
        print("[INSTALL] Pillow not found, installing...")
        if not run_command([sys.executable, "-m", "pip", "install", "pillow"],
                         "Installing Pillow"):
            return False
    
    return True


def prepare_assets():
    """Prepare app assets (round corners on logo)."""
    print("\n[ASSETS] Preparing assets...")
    prepare_script = Path(__file__).resolve().parent / "prepare_assets.py"
    result = subprocess.run([sys.executable, str(prepare_script)], cwd=PROJECT_ROOT)
    return result.returncode == 0


def clean_old_builds():
    """Remove old build artifacts."""
    print("\n[CLEAN] Removing old builds...")
    for folder in ["build", "dist", "__pycache__"]:
        folder_path = PROJECT_ROOT / folder
        if folder_path.exists():
            print(f"       Removing {folder}...")
            shutil.rmtree(folder)
    print("[OK] Old builds cleaned")


def build_executable():
    """Build the executable using PyInstaller."""
    print("\n[BUILD] Creating PrepCore.exe...")
    print("        This may take a few minutes...")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "PrepCore",
        f"--icon={IMAGES_ROOT / 'icon.png'}",
        "--add-data", f"{ASSETS_ROOT}:assets",
        "--hidden-import=PySide6",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=PySide6.QtMultimedia",
        str(ENTRYPOINT),
    ]
    
    if sys.platform == "win32":
        # Adjust path separators for Windows
        fixed_cmd = []
        for arg in cmd:
            if arg.startswith("--add-data"):
                fixed_cmd.append(arg.replace(":", ";"))
            else:
                fixed_cmd.append(arg)

        cmd = fixed_cmd
    
        return run_command(cmd, "Building executable")


def organize_deployment_structure():
    """Organize dist folder into deployment-ready structure."""
    print("\n[DEPLOY] Organizing deployment structure...")
    
    dist_path = PROJECT_ROOT / "dist"
    prepcore_exe = dist_path / "PrepCore.exe"
    
    if not prepcore_exe.exists():
        print("[ERROR] PrepCore.exe not found in dist folder!")
        return False
    
    # Create main app directory
    app_root = dist_path / "PrepCore"
    app_root.mkdir(exist_ok=True)
    print(f"       Created: {app_root}")
    
    # Create directory structure
    dirs_to_create = [
        "src",
        "bin",
        "config",
        "docs",
        "tests",
        "assets",
        "scripts",
        "logs",
        "temp"
    ]
    
    for dir_name in dirs_to_create:
        dir_path = app_root / dir_name
        dir_path.mkdir(exist_ok=True)
        print(f"       Created: {dir_path}")
    
    # Move executable to bin/
    exe_dest = app_root / "bin" / "PrepCore.exe"
    if prepcore_exe != exe_dest:
        print(f"       Moving PrepCore.exe to bin/...")
        shutil.move(str(prepcore_exe), str(exe_dest))
    
    # Move all other files from dist root to assets/ (these are runtime files)
    print(f"       Organizing runtime files to assets/...")
    for file in dist_path.glob("*"):
        if file.is_file() and file.name != "PrepCore":
            dest = app_root / "assets" / file.name
            shutil.move(str(file), str(dest))
    
    # Create README.md
    readme_path = app_root / "README.md"
    readme_content = """# PrepCore - Board Exam Preparation Application

## Directory Structure

```
PrepCore/
├── bin/                    # Application executable
│   └── PrepCore.exe       # Main application launcher
├── assets/                # Runtime assets (libraries, icons, sounds, data)
├── config/                # Configuration files (for future use)
├── docs/                  # Documentation
├── scripts/               # Utility scripts
├── logs/                  # Application logs
├── temp/                  # Temporary files
├── tests/                 # Test files
└── README.md             # This file
```

## Quick Start

1. Double-click `bin/PrepCore.exe` to launch the application
2. On first launch, the app will start blank
3. Add subjects and chapters through the UI
4. Import quiz banks and create study plans

## Features

- 📚 **Subject Management**: Organize studies by subject and chapter
- 🎯 **Multiple Quiz Types**: Long quizzes, short quizzes, and notebooks
- ⏱️ **Time Management**: Gantt charts, calendar, and Pomodoro timer
- 🎨 **Modern UI**: Midnight blue theme with intuitive design
- 💾 **Data Persistence**: All progress saved locally

## First-Run Setup

When you first launch PrepCore:
- The application starts with no pre-loaded subjects
- Create subjects and add chapters manually, or use the Import feature
- Your data is saved in: `%APPDATA%/Local/PrepCore/`

## System Requirements

- Windows 7 or later
- No additional software required (all dependencies bundled)

## Support

For issues or questions, refer to the documentation in the `docs/` folder.

## Data Storage

User data is automatically saved to:
```
%APPDATA%\\Local\\PrepCore\\
├── subjects.json         # Your subjects and chapters
├── preferences.json      # App preferences
└── window_state.json     # Window size and position
```

## Files Included

The `assets/` folder contains:
- Application runtime libraries
- Icons and images
- Alarm sound for timer notifications
- Configuration schemas
"""
    
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)
    print(f"       Created: README.md")
    
    # Clean up empty dist root (keep only PrepCore folder)
    for item in dist_path.iterdir():
        if item.name != "PrepCore":
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
    
    print("[OK] Deployment structure organized")
    return True


def main():
    """Main build process."""
    print("\n" + "="*60)
    print("           PrepCore Build Script")
    print("="*60)
    
    # Check we're in the right directory
    if not Path("main.py").exists():
        print("[ERROR] main.py not found. Please run this from the project root directory.")
        sys.exit(1)
    
    # Execute build steps
    if not install_dependencies():
        sys.exit(1)
    
    if not prepare_assets():
        print("[WARN] Asset preparation had issues, but continuing...")
    
    clean_old_builds()
    
    if not build_executable():
        print("\n[FAILED] Build process failed!")
        sys.exit(1)
    
    # Organize deployment structure
    if not organize_deployment_structure():
        print("\n[FAILED] Deployment structure organization failed!")
        sys.exit(1)
    
    # Success!
    exe_path = Path("dist") / "PrepCore" / "bin" / "PrepCore.exe"
    if exe_path.exists():
        print("\n" + "="*60)
        print("[SUCCESS] Build completed successfully!")
        print("="*60)
        print(f"\nDeployment package ready at: dist/PrepCore/")
        print("\nDirectory Structure:")
        print("  dist/PrepCore/")
        print("  ├── bin/PrepCore.exe          (Application)")
        print("  ├── assets/                   (Runtime files)")
        print("  ├── config/                   (Configuration)")
        print("  ├── docs/                     (Documentation)")
        print("  ├── logs/                     (Application logs)")
        print("  ├── scripts/                  (Utility scripts)")
        print("  ├── temp/                     (Temporary files)")
        print("  ├── tests/                    (Tests)")
        print("  └── README.md                 (Instructions)")
        print("\nYou can now:")
        print("  1. Run: dist\\PrepCore\\bin\\PrepCore.exe")
        print("  2. Zip dist/PrepCore folder for distribution")
        print("  3. Share with others!")
        print()
    else:
        print("\n[ERROR] Executable was not created in expected location!")
        sys.exit(1)


if __name__ == "__main__":
    main()
