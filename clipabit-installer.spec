# ClipABit Installer - PyInstaller Spec File
# This creates a standalone .exe that doesn't require Python installed

# Build with: pyinstaller clipabit-installer.spec

# -*- mode: python ; coding: utf-8 -*-
import hashlib
import json
import os
import shutil
import tarfile
import urllib.request
from pathlib import Path

block_cipher = None

SPEC_FILE = globals().get('__file__', 'clipabit-installer.spec')
ROOT = Path(SPEC_FILE).resolve().parent
BUILD_DIR = ROOT / 'build'


def _resolve_plugin_dir() -> Path:
    # Prefer staged plugin/ when present; fallback to repo frontend/plugin for local dev.
    candidates = [ROOT / 'plugin', ROOT / 'frontend' / 'plugin']
    for candidate in candidates:
        if (candidate / 'clipabit.py').exists() and (candidate / 'pyproject.toml').exists():
            return candidate
    raise FileNotFoundError(
        "Could not locate plugin directory. Expected 'plugin/' or 'frontend/plugin/' with clipabit.py and pyproject.toml"
    )


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def _ensure_bundled_python() -> Path:
    # Keep defaults aligned with build-exe.bat.
    python_version = os.environ.get('CLIPABIT_BUNDLED_PYTHON_VERSION', '3.11.15')
    python_build_tag = os.environ.get('CLIPABIT_BUNDLED_PYTHON_BUILD_TAG', '20260303')
    expected_sha = os.environ.get(
        'CLIPABIT_BUNDLED_PYTHON_SHA256',
        '6f194e1ede02260fd3d758893bbf1d3bb4084652d436a8300a229da721c3ddf8',
    )

    # Honor explicit cache dir if set; otherwise use build/python so spec can run standalone.
    cache_base = Path(os.environ.get('PYTHON_CACHE_DIR', str(BUILD_DIR / 'python')))
    python_root = cache_base / 'python'
    python_exe = python_root / 'python.exe'
    if python_exe.exists():
        return python_root

    cache_base.mkdir(parents=True, exist_ok=True)
    archive_name = f'cpython-{python_version}+{python_build_tag}-x86_64-pc-windows-msvc-install_only.tar.gz'
    archive_path = cache_base / archive_name
    url = (
        'https://github.com/astral-sh/python-build-standalone/releases/download/'
        f'{python_build_tag}/{archive_name}'
    )

    print(f'[spec] Downloading bundled Python from {url}...')
    urllib.request.urlretrieve(url, archive_path)

    actual_sha = _sha256_file(archive_path)
    if actual_sha.lower() != expected_sha.lower():
        archive_path.unlink(missing_ok=True)
        raise RuntimeError(
            'Bundled Python checksum mismatch: '
            f'expected {expected_sha}, got {actual_sha}'
        )

    # Remove stale extraction before unpacking.
    shutil.rmtree(python_root, ignore_errors=True)
    with tarfile.open(archive_path, 'r:gz') as tf:
        tf.extractall(cache_base)
    archive_path.unlink(missing_ok=True)

    if not python_exe.exists():
        raise RuntimeError(f'Bundled Python extraction failed; missing {python_exe}')
    return python_root


def _ensure_release_json() -> Path:
    release_path = ROOT / 'release.json'
    if release_path.exists():
        return release_path

    payload = {
        'tag': os.environ.get('CLIPABIT_PLUGIN_RELEASE', 'local-build'),
        'environment': os.environ.get('CLIPABIT_ENVIRONMENT', 'prod'),
    }
    release_path.write_text(json.dumps(payload), encoding='utf-8')
    return release_path


PLUGIN_DIR = _resolve_plugin_dir()
BUNDLED_PYTHON_DIR = _ensure_bundled_python()
RELEASE_JSON = _ensure_release_json()

a = Analysis(
    ['installer-script.py'],
    pathex=[],
    binaries=[],
    datas=[
        (str(PLUGIN_DIR), 'plugin'),
        (str(BUNDLED_PYTHON_DIR), 'python'),
        (str(RELEASE_JSON), '.'),
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
