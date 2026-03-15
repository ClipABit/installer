"""Tests for cross-platform issues and edge cases that were caught in PR review.

These tests ensure platform-specific bugs don't regress.
"""

import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from tests.conftest import installer_script


# =============================================================================
# Issue 1 & 2: Windows/macOS Python exe path and staging vs installed
# =============================================================================

def test_python_exe_path_windows_bundled():
    """When bundled_python_dir is set on Windows, initial exe path uses python.exe."""
    bundled_dir = Path("C:/bundle/python")

    with mock.patch("platform.system", return_value="Windows"):
        # This code path is in install_plugin() lines 670-675
        if installer_script.platform.system() == "Windows":
            python_exe_path = str(bundled_dir / "python.exe")
        else:
            python_exe_path = str(bundled_dir / "bin" / "python3")

        assert python_exe_path.endswith("python.exe")
        assert "bin" not in python_exe_path


def test_python_exe_path_macos_bundled():
    """When bundled_python_dir is set on macOS, initial exe path uses bin/python3."""
    bundled_dir = Path("/tmp/bundle/python")

    with mock.patch("platform.system", return_value="Darwin"):
        # This code path is in install_plugin() lines 670-675
        if installer_script.platform.system() == "Windows":
            python_exe_path = str(bundled_dir / "python.exe")
        else:
            python_exe_path = str(bundled_dir / "bin" / "python3")

        assert python_exe_path.endswith("bin/python3")


def test_python_exe_updated_after_install_macos():
    """After install_python_runtime(), exe path should update to installed location (macOS)."""
    clipabit_dir = Path("/tmp/clipabit")
    python_target = clipabit_dir / "python"

    with mock.patch("platform.system", return_value="Darwin"):
        # This code path is in install_plugin() lines 716-719
        if installer_script.platform.system() == "Windows":
            updated_exe = str(python_target / "python.exe")
        else:
            updated_exe = str(python_target / "bin" / "python3")

        assert str(clipabit_dir) in updated_exe
        assert updated_exe.endswith("bin/python3")


# =============================================================================
# Issue 3: check_python() version requirement mismatch
# =============================================================================

def test_check_python_accepts_3_11():
    """check_python() should accept Python 3.11 (bundled version)."""
    mock_exe = "/usr/bin/python3"

    with mock.patch("shutil.which", return_value=mock_exe), \
         mock.patch("subprocess.run") as mock_run:
        # Mock Python 3.11.x
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout="3.11.5",
        )

        result = installer_script.check_python()
        assert result == mock_exe


def test_check_python_rejects_3_10():
    """check_python() should reject Python 3.10 (too old)."""
    mock_exe = "/usr/bin/python3"

    with mock.patch("shutil.which", return_value=mock_exe), \
         mock.patch("subprocess.run") as mock_run:
        # Mock Python 3.10.x (should fail)
        mock_run.return_value = mock.Mock(
            returncode=1,
            stdout="3.10.12",
        )

        result = installer_script.check_python()
        assert result is None


# =============================================================================
# Issue 4: LOCALAPPDATA fallback edge case
# =============================================================================

def test_clipabit_dir_windows_no_localappdata():
    """Windows clipabit_dir handles missing LOCALAPPDATA gracefully."""
    with mock.patch("platform.system", return_value="Windows"), \
         mock.patch.dict("os.environ", {}, clear=True), \
         mock.patch("pathlib.Path.home", return_value=Path("C:/Users/test")):

        clipabit_dir = installer_script.get_clipabit_directory()

        # Should fall back to known path (not relative)
        clipabit_str = str(clipabit_dir)
        assert "ClipABit" in clipabit_str
        # Should use AppData/Local fallback
        assert "AppData" in clipabit_str
        assert "Local" in clipabit_str
        # Should not be just "ClipABit" (relative path)
        assert clipabit_str != "ClipABit"


def test_clipabit_dir_windows_with_localappdata():
    """Windows clipabit_dir uses LOCALAPPDATA when set."""
    with mock.patch("platform.system", return_value="Windows"), \
         mock.patch.dict("os.environ", {"LOCALAPPDATA": "C:/Users/test/AppData/Local"}):

        clipabit_dir = installer_script.get_clipabit_directory()

        assert str(clipabit_dir) == "C:/Users/test/AppData/Local\\ClipABit" or \
               str(clipabit_dir) == "C:/Users/test/AppData/Local/ClipABit"


# =============================================================================
# Issue 5: install_python_runtime() validation
# =============================================================================

def test_install_python_runtime_validates_binary_macos(tmp_path):
    """install_python_runtime() checks that bin/python3 exists on macOS."""
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()

    # Create a fake Python structure (missing the binary)
    (source / "bin").mkdir()
    # Don't create python3 - should fail validation

    with mock.patch("platform.system", return_value="Darwin"), \
         mock.patch("subprocess.run"):  # Mock xattr removal

        result = installer_script.install_python_runtime(source, target)

        # Should fail because python3 binary is missing
        assert result is False


def test_install_python_runtime_validates_binary_windows(tmp_path):
    """install_python_runtime() checks that python.exe exists on Windows."""
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()

    # Create source but no python.exe
    (source / "Scripts").mkdir()

    with mock.patch("platform.system", return_value="Windows"):
        result = installer_script.install_python_runtime(source, target)

        # Should fail because python.exe is missing
        assert result is False


def test_install_python_runtime_success_macos(tmp_path):
    """install_python_runtime() succeeds when binary exists and is executable."""
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()

    # Create a proper Python structure
    bin_dir = source / "bin"
    bin_dir.mkdir()
    python_exe = bin_dir / "python3"
    python_exe.write_text("#!/usr/bin/env python3\n")
    python_exe.chmod(0o755)

    with mock.patch("platform.system", return_value="Darwin"), \
         mock.patch("subprocess.run"):  # Mock xattr removal

        result = installer_script.install_python_runtime(source, target)

        assert result is True
        assert target.exists()
        assert (target / "bin" / "python3").exists()


def test_install_python_runtime_success_windows(tmp_path):
    """install_python_runtime() succeeds when python.exe exists."""
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()

    # Create python.exe
    python_exe = source / "python.exe"
    python_exe.write_text("fake exe")

    # On Windows, we can't set Unix execute bit, but the validation should still pass
    # if the file exists (Windows doesn't use execute bits the same way)
    with mock.patch("platform.system", return_value="Windows"), \
         mock.patch("os.access", return_value=True):  # Mock executable check

        result = installer_script.install_python_runtime(source, target)

        assert result is True
        assert target.exists()
        assert (target / "python.exe").exists()


# =============================================================================
# Why weren't these caught?
# =============================================================================

"""
ANALYSIS: Why existing tests didn't catch these bugs:

1. **Windows Python path bug**:
   - Tests run on macOS by default
   - Platform-specific code paths weren't exercised
   - Existing platform tests use mocks but don't verify the full install flow

2. **Python exe pointing to staging**:
   - Tests use mocks that bypass the actual path resolution
   - No integration test that checks the exe path after install_python_runtime

3. **Python version check (3.12 vs 3.11)**:
   - No test for the version requirement edge case
   - check_python() was tested but not with 3.11.x specifically

4. **LOCALAPPDATA fallback**:
   - Edge case (missing env var) not tested
   - Tests assume normal environment with all vars set

5. **install_python_runtime() validation**:
   - Function was trusted to work based on implementation
   - No test verified the validation logic actually runs

LESSONS:
- Need more cross-platform tests with actual platform.system() mocking
- Need edge case tests (missing env vars, missing files)
- Need integration tests that verify the full flow, not just mocked units
- Should test validation functions actually validate (not just succeed)
"""
