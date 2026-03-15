"""Tests for platform detection and path resolution."""

from pathlib import Path
from unittest import mock

from tests.conftest import installer_script


# --- Tests that pass against existing code ---

def test_resolve_dirs_darwin():
    """macOS returns correct Fusion path."""
    with mock.patch("platform.system", return_value="Darwin"):
        scripts, modules = installer_script.get_resolve_directories()
    assert "Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility" in str(scripts)
    assert "Blackmagic Design/DaVinci Resolve/Fusion/Modules" in str(modules)


def test_resolve_dirs_windows():
    """Windows returns correct Fusion path (mock APPDATA)."""
    with mock.patch("platform.system", return_value="Windows"), \
         mock.patch.dict("os.environ", {"APPDATA": "C:\\Users\\test\\AppData\\Roaming"}):
        scripts, modules = installer_script.get_resolve_directories()
    assert "Blackmagic Design" in str(scripts)
    assert "Support\\Fusion\\Scripts\\Utility" in str(scripts) or "Support/Fusion/Scripts/Utility" in str(scripts)


def test_config_dir_darwin():
    """macOS config dir is ~/Library/Application Support/ClipABit."""
    with mock.patch("platform.system", return_value="Darwin"):
        config = installer_script.get_config_directory()
    assert str(config).endswith("Library/Application Support/ClipABit")


def test_config_dir_windows():
    """Windows config dir uses APPDATA."""
    with mock.patch("platform.system", return_value="Windows"), \
         mock.patch.dict("os.environ", {"APPDATA": "C:\\Users\\test\\AppData\\Roaming"}):
        config = installer_script.get_config_directory()
    assert "ClipABit" in str(config)
    assert "Roaming" in str(config) or "AppData" in str(config)


def test_check_platform_supported():
    """Darwin and Windows return True."""
    with mock.patch("platform.system", return_value="Darwin"), \
         mock.patch("platform.mac_ver", return_value=("14.0", ("", "", ""), "")):
        assert installer_script.check_platform() is True
    with mock.patch("platform.system", return_value="Windows"), \
         mock.patch("platform.version", return_value="10.0.19041"):
        assert installer_script.check_platform() is True


def test_check_platform_unsupported():
    """Linux returns False."""
    with mock.patch("platform.system", return_value="Linux"):
        assert installer_script.check_platform() is False


# --- Tests that require new code ---

def test_resolve_dirs_override():
    """Path overrides are returned directly."""
    s = Path("/custom/scripts")
    m = Path("/custom/modules")
    scripts, modules = installer_script.get_resolve_directories(scripts_dir=s, modules_dir=m)
    assert scripts == s
    assert modules == m


def test_config_dir_override():
    """Config dir override is returned directly."""
    override = Path("/custom/config")
    result = installer_script.get_config_directory(override=override)
    assert result == override


def test_clipabit_dir_darwin():
    """macOS ClipABit dir is ~/Library/Application Support/ClipABit."""
    with mock.patch("platform.system", return_value="Darwin"):
        result = installer_script.get_clipabit_directory()
    assert str(result).endswith("Library/Application Support/ClipABit")


def test_clipabit_dir_windows():
    """Windows ClipABit dir uses LOCALAPPDATA."""
    with mock.patch("platform.system", return_value="Windows"), \
         mock.patch.dict("os.environ", {"LOCALAPPDATA": "C:\\Users\\test\\AppData\\Local"}):
        result = installer_script.get_clipabit_directory()
    assert "ClipABit" in str(result)
    assert "Local" in str(result)


def test_clipabit_dir_override():
    """ClipABit dir override is returned directly."""
    override = Path("/custom/clipabit")
    result = installer_script.get_clipabit_directory(override=override)
    assert result == override


def test_get_python_exe_returns_bundled():
    """When bundled path is provided, it is returned."""
    bundled = Path("/custom/python/bin/python3")
    result = installer_script.get_python_exe(bundled_python_path=bundled)
    assert result == str(bundled)
