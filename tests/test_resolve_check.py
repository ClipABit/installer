"""Tests for DaVinci Resolve running detection."""

import subprocess
from unittest import mock

from tests.conftest import installer_script


def test_resolve_not_running():
    """When Resolve is not running, check returns True (safe to install)."""
    with mock.patch("platform.system", return_value="Darwin"), \
         mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.MagicMock(returncode=1)
        assert installer_script.check_resolve_running() is True


def test_resolve_running_aborts():
    """When Resolve is running, check returns False (not safe)."""
    with mock.patch("platform.system", return_value="Darwin"), \
         mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.MagicMock(returncode=0)
        assert installer_script.check_resolve_running() is False


def test_resolve_check_skipped():
    """With skip=True, always returns True regardless."""
    assert installer_script.check_resolve_running(skip=True) is True


def test_resolve_check_darwin_process_name():
    """On macOS, verifies correct pgrep command is used."""
    with mock.patch("platform.system", return_value="Darwin"), \
         mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.MagicMock(returncode=1)
        installer_script.check_resolve_running()
        args = mock_run.call_args[0][0]
        assert "pgrep" in args
        # Should check for the Resolve process
        assert any("Resolve" in a or "DaVinci" in a for a in args)


def test_resolve_check_windows_process_name():
    """On Windows, verifies tasklist command is used."""
    with mock.patch("platform.system", return_value="Windows"), \
         mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.MagicMock(returncode=1, stdout="")
        installer_script.check_resolve_running()
        args = mock_run.call_args[0][0]
        assert "tasklist" in args
        assert any("Resolve" in a for a in args)
