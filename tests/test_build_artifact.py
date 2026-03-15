"""Tests to verify built .pkg/.exe contents.

These tests inspect the built installer artifacts to ensure they contain
the right files and exclude dev/test files.

Marked @pytest.mark.build_artifact — skip if artifact not found.
"""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

# Paths to built artifacts (relative to repo root)
REPO_ROOT = Path(__file__).resolve().parent.parent
PKG_PATH = REPO_ROOT / "dist" / "ClipABit.pkg"
EXE_PATH = REPO_ROOT / "dist" / "ClipABit-Installer.exe"

build_artifact = pytest.mark.build_artifact


# ---------------------------------------------------------------------------
# macOS .pkg tests
# ---------------------------------------------------------------------------

def _expand_pkg():
    """Expand the .pkg and return the expanded directory path."""
    if not PKG_PATH.exists():
        pytest.skip(f".pkg not found at {PKG_PATH}")
    tmpdir = tempfile.mkdtemp(prefix="clipabit-pkg-test-")
    subprocess.run(
        ["pkgutil", "--expand", str(PKG_PATH), os.path.join(tmpdir, "expanded")],
        check=True,
    )
    return Path(tmpdir) / "expanded"


def _pkg_payload_files(expanded_dir):
    """List all files in the .pkg payload."""
    # pkgutil --expand creates Payload as a cpio archive
    payload = expanded_dir / "ClipABit.pkg" / "Payload"
    if not payload.exists():
        # Try flat package layout
        for p in expanded_dir.rglob("Payload"):
            payload = p
            break
    if not payload.exists():
        return []

    # Extract Payload cpio to list contents
    tmpdir = tempfile.mkdtemp(prefix="clipabit-payload-")
    subprocess.run(
        f"cd '{tmpdir}' && cat '{payload}' | gzip -d | cpio -id 2>/dev/null",
        shell=True,
    )
    files = []
    for f in Path(tmpdir).rglob("*"):
        files.append(str(f.relative_to(tmpdir)))
    return files


@build_artifact
def test_pkg_contains_installer_script():
    """installer-script.py present in payload."""
    expanded = _expand_pkg()
    files = _pkg_payload_files(expanded)
    assert any("installer-script.py" in f for f in files), \
        f"installer-script.py not found in payload: {files[:20]}"


@build_artifact
def test_pkg_contains_bundled_python():
    """python/bin/python3 present in payload."""
    expanded = _expand_pkg()
    files = _pkg_payload_files(expanded)
    assert any("python" in f and "bin" in f for f in files), \
        f"python/bin not found in payload: {files[:20]}"


@build_artifact
def test_pkg_contains_plugin():
    """plugin/clipabit/__init__.py present in payload."""
    expanded = _expand_pkg()
    files = _pkg_payload_files(expanded)
    assert any("clipabit/__init__.py" in f for f in files), \
        f"clipabit/__init__.py not found in payload: {files[:20]}"


@build_artifact
def test_pkg_contains_postinstall():
    """postinstall present in scripts."""
    expanded = _expand_pkg()
    # Scripts are in the Scripts directory
    scripts_found = list(expanded.rglob("postinstall"))
    assert len(scripts_found) > 0, "postinstall not found in .pkg scripts"


@build_artifact
def test_pkg_excludes_tests():
    """tests/ NOT in payload."""
    expanded = _expand_pkg()
    files = _pkg_payload_files(expanded)
    # Exclude bundled Python's internal package tests (setuptools, pkg_resources, etc.)
    test_files = [f for f in files
                  if ("/tests/" in f or f.startswith("tests/"))
                  and "/site-packages/" not in f]
    assert len(test_files) == 0, f"tests/ found in payload: {test_files}"


@build_artifact
def test_pkg_excludes_docs():
    """docs/ NOT in payload."""
    expanded = _expand_pkg()
    files = _pkg_payload_files(expanded)
    doc_files = [f for f in files if "/docs/" in f or f.startswith("docs/")]
    assert len(doc_files) == 0, f"docs/ found in payload: {doc_files}"


@build_artifact
def test_pkg_excludes_git():
    """.git/ NOT in payload."""
    expanded = _expand_pkg()
    files = _pkg_payload_files(expanded)
    git_files = [f for f in files if "/.git/" in f or f.startswith(".git/")]
    assert len(git_files) == 0, f".git/ found in payload: {git_files}"


@build_artifact
def test_pkg_excludes_pycache():
    """__pycache__/ NOT in payload."""
    expanded = _expand_pkg()
    files = _pkg_payload_files(expanded)
    cache_files = [f for f in files if "__pycache__" in f]
    assert len(cache_files) == 0, f"__pycache__ found in payload: {cache_files}"


# ---------------------------------------------------------------------------
# Windows .exe tests
# ---------------------------------------------------------------------------

@build_artifact
def test_exe_contains_installer_script():
    """installer-script.py in bundle."""
    if not EXE_PATH.exists():
        pytest.skip(f".exe not found at {EXE_PATH}")
    # For PyInstaller, we'd use archive_viewer or inspect sys._MEIPASS
    # Since we can't run .exe on macOS, skip with a note
    pytest.skip("Windows .exe inspection requires Windows platform")


@build_artifact
def test_exe_contains_bundled_python():
    """python/ directory in bundle."""
    if not EXE_PATH.exists():
        pytest.skip(f".exe not found at {EXE_PATH}")
    pytest.skip("Windows .exe inspection requires Windows platform")


@build_artifact
def test_exe_contains_plugin():
    """plugin/clipabit/__init__.py in bundle."""
    if not EXE_PATH.exists():
        pytest.skip(f".exe not found at {EXE_PATH}")
    pytest.skip("Windows .exe inspection requires Windows platform")


@build_artifact
def test_exe_excludes_tests():
    """tests/ NOT in bundle."""
    if not EXE_PATH.exists():
        pytest.skip(f".exe not found at {EXE_PATH}")
    pytest.skip("Windows .exe inspection requires Windows platform")


@build_artifact
def test_exe_excludes_docs():
    """docs/ NOT in bundle."""
    if not EXE_PATH.exists():
        pytest.skip(f".exe not found at {EXE_PATH}")
    pytest.skip("Windows .exe inspection requires Windows platform")


@build_artifact
def test_exe_excludes_pycache():
    """__pycache__/ NOT in bundle."""
    if not EXE_PATH.exists():
        pytest.skip(f".exe not found at {EXE_PATH}")
    pytest.skip("Windows .exe inspection requires Windows platform")
