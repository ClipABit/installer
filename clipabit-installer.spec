# ClipABit Installer - PyInstaller Spec File
# This creates a standalone .exe that doesn't require Python installed

# Build with: pyinstaller clipabit-installer.spec

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['installer-script.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('plugin', 'plugin'),
        # Windows build downloads Python to build/python/python, not ./python
        ('build/python/python', 'python'),
    ],
    hiddenimports=['tomllib'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['.venv', '__pycache__'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Filter out unwanted files from datas
a.datas = [
    (dest, source, type_) for dest, source, type_ in a.datas
    if not any(excl in dest for excl in ['.venv', '__pycache__', '.pyc', '.git', 'tests', 'docs'])
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ClipABit-Installer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Set to False for GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
