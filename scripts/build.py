#!/usr/bin/env python3
"""
Build script for PrepCore - Creates PrepCore.exe using PyInstaller
Usage: python build.py
"""

import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_ROOT = PROJECT_ROOT / "assets"
IMAGES_ROOT = ASSETS_ROOT / "images"
ENTRYPOINT = PROJECT_ROOT / "src" / "main.py"


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n[STEP] {description}")
    print(f"       Command: {' '.join(str(part) for part in cmd)}")
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
        subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], check=False)
        print("[OK] PyInstaller is installed")
    except ImportError:
        print("[INSTALL] PyInstaller not found, installing...")
        if not run_command(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            "Installing PyInstaller",
        ):
            return False

    try:
        import PIL  # noqa: F401

        print("[OK] Pillow is installed")
    except ImportError:
        print("[INSTALL] Pillow not found, installing...")
        if not run_command(
            [sys.executable, "-m", "pip", "install", "pillow"],
            "Installing Pillow",
        ):
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
            shutil.rmtree(folder_path)
    print("[OK] Old builds cleaned")


def build_executable():
    """Build the executable using PyInstaller."""
    print("\n[BUILD] Creating PrepCore.exe...")
    print("        This may take a few minutes...")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name",
        "PrepCore",
        f"--icon={IMAGES_ROOT / 'icon.png'}",
        "--add-data",
        f"{ASSETS_ROOT}:assets",
        "--hidden-import=PySide6",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=PySide6.QtMultimedia",
        str(ENTRYPOINT),
    ]

    if sys.platform == "win32":
        fixed_cmd = []
        for arg in cmd:
            if isinstance(arg, str) and arg.startswith("--add-data"):
                fixed_cmd.append(arg.replace(":", ";"))
            else:
                fixed_cmd.append(arg)
        cmd = fixed_cmd

    return run_command(cmd, "Building executable")


def main():
    """Main build process."""
    print("\n" + "=" * 60)
    print("           PrepCore Build Script")
    print("=" * 60)

    if not (PROJECT_ROOT / "main.py").exists():
        print("[ERROR] main.py not found. Please run this from the project root directory.")
        sys.exit(1)

    if not install_dependencies():
        sys.exit(1)

    if not prepare_assets():
        print("[WARN] Asset preparation had issues, but continuing...")

    clean_old_builds()

    if not build_executable():
        print("\n[FAILED] Build process failed!")
        sys.exit(1)

    exe_path = PROJECT_ROOT / "dist" / "PrepCore.exe"
    if exe_path.exists():
        print("\n" + "=" * 60)
        print("[SUCCESS] Build completed successfully!")
        print("=" * 60)
        print(f"\nExecutable ready at: {exe_path}")
        print("\nYou can now:")
        print("  1. Run: dist\\PrepCore.exe")
        print("  2. Share the .exe from the dist folder")
        print()
    else:
        print("\n[ERROR] Executable was not created in the expected location!")
        sys.exit(1)


if __name__ == "__main__":
    main()
