"""Tests for ClipABit uninstall functionality."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import installer_script


@pytest.fixture
def install_dirs(tmp_path):
    """Create the 4 override directories used by uninstall."""
    scripts_dir = tmp_path / "Scripts" / "Utility"
    modules_dir = tmp_path / "Modules"
    clipabit_dir = tmp_path / "ClipABit"
    config_dir = tmp_path / "Config"
    for d in [scripts_dir, modules_dir, clipabit_dir, config_dir]:
        d.mkdir(parents=True)
    return scripts_dir, modules_dir, clipabit_dir, config_dir


@pytest.fixture
def installed_state(install_dirs):
    """Create a fully installed state."""
    scripts_dir, modules_dir, clipabit_dir, config_dir = install_dirs

    # Shim
    (scripts_dir / "ClipABit.py").write_text("# shim\n")

    # Plugin package
    pkg = modules_dir / "clipabit"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("# pkg\n")

    # Python runtime
    python_dir = clipabit_dir / "python"
    python_dir.mkdir()
    (python_dir / "python3").write_text("# fake python\n")

    # Deps
    deps = clipabit_dir / "deps"
    deps.mkdir()
    (deps / "requests.py").write_text("# fake\n")

    # Config
    (config_dir / "config.dat").write_text("encoded-config")

    return install_dirs


# ---------------------------------------------------------------------------
# enumerate_installed_paths
# ---------------------------------------------------------------------------

class TestEnumerateInstalledPaths:
    def test_all_paths_found(self, installed_state):
        scripts_dir, modules_dir, clipabit_dir, config_dir = installed_state
        paths = installer_script.enumerate_installed_paths(
            scripts_dir, modules_dir, config_dir, clipabit_dir
        )
        descriptions = [desc for _, _, desc in paths]
        assert "Bootstrap shim" in descriptions
        assert "Plugin package" in descriptions
        assert "Python runtime" in descriptions
        assert "Dependencies" in descriptions
        assert "Configuration" in descriptions

    def test_empty_install_returns_empty(self, install_dirs):
        scripts_dir, modules_dir, clipabit_dir, config_dir = install_dirs
        paths = installer_script.enumerate_installed_paths(
            scripts_dir, modules_dir, config_dir, clipabit_dir
        )
        assert paths == []

    def test_partial_install(self, install_dirs):
        scripts_dir, modules_dir, clipabit_dir, config_dir = install_dirs
        # Only shim exists
        (scripts_dir / "ClipABit.py").write_text("# shim\n")
        paths = installer_script.enumerate_installed_paths(
            scripts_dir, modules_dir, config_dir, clipabit_dir
        )
        assert len(paths) == 1
        assert paths[0][2] == "Bootstrap shim"

    def test_includes_bak_files(self, install_dirs):
        scripts_dir, modules_dir, clipabit_dir, config_dir = install_dirs
        (scripts_dir / "ClipABit.py").write_text("# shim\n")
        (scripts_dir / "ClipABit.py.bak").write_text("# old shim\n")
        paths = installer_script.enumerate_installed_paths(
            scripts_dir, modules_dir, config_dir, clipabit_dir
        )
        descriptions = [desc for _, _, desc in paths]
        assert "Bootstrap shim" in descriptions
        assert "Bootstrap shim (backup)" in descriptions


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------

class TestUninstall:
    def test_uninstall_removes_all_files(self, installed_state):
        scripts_dir, modules_dir, clipabit_dir, config_dir = installed_state
        with patch.object(installer_script, "check_resolve_running", return_value=False), \
             patch.object(installer_script, "clear_keyring"), \
             patch.object(installer_script, "forget_pkg_receipt"):
            result = installer_script.uninstall(
                yes=True,
                scripts_dir=scripts_dir, modules_dir=modules_dir,
                config_dir=config_dir, clipabit_dir=clipabit_dir,
            )
        assert result is True
        assert not (scripts_dir / "ClipABit.py").exists()
        assert not (modules_dir / "clipabit").exists()
        assert not (clipabit_dir / "python").exists()
        assert not (clipabit_dir / "deps").exists()
        assert not (config_dir / "config.dat").exists()

    def test_uninstall_nothing_installed(self, install_dirs):
        scripts_dir, modules_dir, clipabit_dir, config_dir = install_dirs
        with patch.object(installer_script, "check_resolve_running", return_value=False):
            result = installer_script.uninstall(
                yes=True,
                scripts_dir=scripts_dir, modules_dir=modules_dir,
                config_dir=config_dir, clipabit_dir=clipabit_dir,
            )
        assert result is True

    def test_uninstall_calls_clear_keyring(self, installed_state):
        scripts_dir, modules_dir, clipabit_dir, config_dir = installed_state
        with patch.object(installer_script, "check_resolve_running", return_value=False), \
             patch.object(installer_script, "clear_keyring") as mock_keyring, \
             patch.object(installer_script, "forget_pkg_receipt"):
            installer_script.uninstall(
                yes=True,
                scripts_dir=scripts_dir, modules_dir=modules_dir,
                config_dir=config_dir, clipabit_dir=clipabit_dir,
            )
        mock_keyring.assert_called_once()

    def test_uninstall_calls_forget_pkg_receipt(self, installed_state):
        scripts_dir, modules_dir, clipabit_dir, config_dir = installed_state
        with patch.object(installer_script, "check_resolve_running", return_value=False), \
             patch.object(installer_script, "clear_keyring"), \
             patch.object(installer_script, "forget_pkg_receipt") as mock_receipt:
            installer_script.uninstall(
                yes=True,
                scripts_dir=scripts_dir, modules_dir=modules_dir,
                config_dir=config_dir, clipabit_dir=clipabit_dir,
            )
        mock_receipt.assert_called_once()

    def test_uninstall_removes_bak_files(self, installed_state):
        scripts_dir, modules_dir, clipabit_dir, config_dir = installed_state
        # Add .bak files
        (scripts_dir / "ClipABit.py.bak").write_text("# old\n")
        with patch.object(installer_script, "check_resolve_running", return_value=False), \
             patch.object(installer_script, "clear_keyring"), \
             patch.object(installer_script, "forget_pkg_receipt"):
            result = installer_script.uninstall(
                yes=True,
                scripts_dir=scripts_dir, modules_dir=modules_dir,
                config_dir=config_dir, clipabit_dir=clipabit_dir,
            )
        assert result is True
        assert not (scripts_dir / "ClipABit.py.bak").exists()

    def test_uninstall_cleans_empty_parent_dirs(self, installed_state):
        scripts_dir, modules_dir, clipabit_dir, config_dir = installed_state
        with patch.object(installer_script, "check_resolve_running", return_value=False), \
             patch.object(installer_script, "clear_keyring"), \
             patch.object(installer_script, "forget_pkg_receipt"):
            installer_script.uninstall(
                yes=True,
                scripts_dir=scripts_dir, modules_dir=modules_dir,
                config_dir=config_dir, clipabit_dir=clipabit_dir,
            )
        # clipabit_dir should be removed since it's empty after cleanup
        assert not clipabit_dir.exists()

    def test_uninstall_prompt_cancelled(self, installed_state):
        """Without --yes, declining the prompt cancels uninstall."""
        scripts_dir, modules_dir, clipabit_dir, config_dir = installed_state
        with patch.object(installer_script, "check_resolve_running", return_value=False), \
             patch("builtins.input", return_value="n"):
            result = installer_script.uninstall(
                yes=False,
                scripts_dir=scripts_dir, modules_dir=modules_dir,
                config_dir=config_dir, clipabit_dir=clipabit_dir,
            )
        assert result is False
        # Files should still exist
        assert (scripts_dir / "ClipABit.py").exists()


# ---------------------------------------------------------------------------
# clear_keyring
# ---------------------------------------------------------------------------

class TestClearKeyring:
    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run")
    def test_macos_keyring_success(self, mock_run, _):
        mock_run.return_value = MagicMock(returncode=0)
        installer_script.clear_keyring()
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "security" in args
        assert "clipabit-plugin" in args

    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run")
    def test_macos_keyring_not_found(self, mock_run, _):
        mock_run.return_value = MagicMock(
            returncode=44, stderr="The specified item could not be found"
        )
        # Should not raise
        installer_script.clear_keyring()

    @patch("platform.system", return_value="Windows")
    @patch("subprocess.run")
    def test_windows_keyring_success(self, mock_run, _):
        mock_run.return_value = MagicMock(returncode=0)
        installer_script.clear_keyring()
        args = mock_run.call_args[0][0]
        assert "cmdkey" in args

    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_command_not_found(self, mock_run, _):
        # Should not raise
        installer_script.clear_keyring()


# ---------------------------------------------------------------------------
# forget_pkg_receipt
# ---------------------------------------------------------------------------

class TestForgetPkgReceipt:
    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run")
    def test_macos_receipt_removed(self, mock_run, _):
        mock_run.return_value = MagicMock(returncode=0)
        installer_script.forget_pkg_receipt()
        args = mock_run.call_args[0][0]
        assert "pkgutil" in args
        assert "com.clipabit.plugin.installer" in args

    @patch("platform.system", return_value="Windows")
    def test_windows_noop(self, _):
        # Should not call anything on Windows
        installer_script.forget_pkg_receipt()

    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run")
    def test_no_receipt(self, mock_run, _):
        mock_run.return_value = MagicMock(returncode=1)
        # Should not raise
        installer_script.forget_pkg_receipt()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_get_dir_size(self, tmp_path):
        d = tmp_path / "test_dir"
        d.mkdir()
        (d / "file1.txt").write_bytes(b"x" * 100)
        (d / "file2.txt").write_bytes(b"y" * 200)
        assert installer_script.get_dir_size(d) == 300

    def test_get_dir_size_empty(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        assert installer_script.get_dir_size(d) == 0

    def test_get_dir_size_nonexistent(self, tmp_path):
        assert installer_script.get_dir_size(tmp_path / "nope") == 0

    def test_format_size_bytes(self):
        assert installer_script.format_size(500) == "500 B"

    def test_format_size_kb(self):
        assert installer_script.format_size(2048) == "2.0 KB"

    def test_format_size_mb(self):
        assert installer_script.format_size(5 * 1024 * 1024) == "5.0 MB"
