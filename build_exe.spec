# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for PrepCore Study App
This file defines how to build the executable
"""
import sys
from pathlib import Path

block_cipher = None

# Define data to be included in the build
datas = [
    # JSON schema and sample files
    ('gant_chart/', 'gant_chart/'),
    ('notebooks/', 'notebooks/'),
    ('quiz_banks/', 'quiz_banks/'),
    ('sample_data/', 'sample_data/'),
    ('app_state/', 'app_state/'),
    
    # Image files
    ('Logo.png', '.'),
    ('Logo_rounded.png', '.'),
    ('icon.png', '.'),
    
    # Audio files
    ('Classic Alarm Clock - Sound Effect  ProSounds.mp3', '.'),
    
    # UI files
    ('board_exam.ui', '.'),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PrepCore',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.png',  # Taskbar icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PrepCore'
)
