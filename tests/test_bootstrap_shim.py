"""Tests for bootstrap shim generation."""

import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

from tests.conftest import installer_script


def test_shim_has_valid_syntax(fake_plugin_dir):
    """Generated shim compiles without syntax errors."""
    shim = installer_script.generate_bootstrap_shim(fake_plugin_dir / "clipabit.py")
    compile(shim, "ClipABit.py", "exec")


def test_shim_starts_with_preamble(fake_plugin_dir):
    """Shim starts with the bootstrap marker comment."""
    shim = installer_script.generate_bootstrap_shim(fake_plugin_dir / "clipabit.py")
    assert shim.startswith("# === ClipABit Installer Bootstrap ===")


def test_shim_ends_with_original(fake_plugin_dir):
    """Original clipabit.py content is appended verbatim after preamble."""
    original = (fake_plugin_dir / "clipabit.py").read_text()
    shim = installer_script.generate_bootstrap_shim(fake_plugin_dir / "clipabit.py")
    assert shim.endswith(original)


def test_shim_contains_obfuscation_key(fake_plugin_dir):
    """The obfuscation key string is embedded in the preamble."""
    shim = installer_script.generate_bootstrap_shim(fake_plugin_dir / "clipabit.py")
    assert installer_script.OBFUSCATION_KEY in shim


def test_shim_config_loading(fake_plugin_dir, tmp_path):
    """Exec the preamble with a real config.dat — env vars should be set."""
    # Write a config.dat
    config = {"CLIPABIT_AUTH0_DOMAIN": "test.auth0.com", "CLIPABIT_ENVIRONMENT": "test"}
    encoded = installer_script.encode_config(config)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_dat = config_dir / "config.dat"
    config_dat.write_text(encoded)

    shim = installer_script.generate_bootstrap_shim(fake_plugin_dir / "clipabit.py")
    # Extract just the preamble (before original content)
    original = (fake_plugin_dir / "clipabit.py").read_text()
    preamble = shim[: shim.index(original)]

    # Patch config_locations to use our temp path (macOS form)
    patched = preamble.replace(
        'os.path.expanduser(\n            "~/Library/Application Support/ClipABit/config.dat")',
        f'r"{config_dat}"',
    )
    patched = patched.replace(
        'os.path.expanduser("~/Library/Application Support/ClipABit/config.dat")',
        f'r"{config_dat}"',
    )
    # Patch the fallback path too (used on Linux CI where sys.platform is 'linux')
    patched = patched.replace(
        'os.path.expanduser("~/.config/clipabit/config.dat")',
        f'r"{config_dat}"',
    )

    # Clear any existing env var
    env_backup = os.environ.pop("CLIPABIT_AUTH0_DOMAIN", None)
    try:
        exec(patched, {"__file__": str(fake_plugin_dir / "ClipABit.py")})
        assert os.environ.get("CLIPABIT_AUTH0_DOMAIN") == "test.auth0.com"
    finally:
        if env_backup is not None:
            os.environ["CLIPABIT_AUTH0_DOMAIN"] = env_backup
        else:
            os.environ.pop("CLIPABIT_AUTH0_DOMAIN", None)


def test_shim_missing_config_no_crash(fake_plugin_dir, tmp_path):
    """Preamble exec'd with no config.dat doesn't raise."""
    shim = installer_script.generate_bootstrap_shim(fake_plugin_dir / "clipabit.py")
    original = (fake_plugin_dir / "clipabit.py").read_text()
    preamble = shim[: shim.index(original)]

    # Point config at a nonexistent file
    patched = preamble.replace(
        'os.path.expanduser(\n            "~/Library/Application Support/ClipABit/config.dat")',
        f'r"{tmp_path / "nonexistent" / "config.dat"}"',
    )
    patched = patched.replace(
        'os.path.expanduser("~/Library/Application Support/ClipABit/config.dat")',
        f'r"{tmp_path / "nonexistent" / "config.dat"}"',
    )
    # Should not raise
    exec(patched, {"__file__": str(tmp_path / "ClipABit.py")})


def test_shim_corrupt_config_no_crash(fake_plugin_dir, tmp_path):
    """Preamble exec'd with garbage config.dat doesn't raise (silent pass)."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_dat = config_dir / "config.dat"
    config_dat.write_text("this-is-not-valid-base64-!@#$%^")

    shim = installer_script.generate_bootstrap_shim(fake_plugin_dir / "clipabit.py")
    original = (fake_plugin_dir / "clipabit.py").read_text()
    preamble = shim[: shim.index(original)]

    patched = preamble.replace(
        'os.path.expanduser(\n            "~/Library/Application Support/ClipABit/config.dat")',
        f'r"{config_dat}"',
    )
    patched = patched.replace(
        'os.path.expanduser("~/Library/Application Support/ClipABit/config.dat")',
        f'r"{config_dat}"',
    )
    # Should not raise
    exec(patched, {"__file__": str(tmp_path / "ClipABit.py")})


def test_shim_deps_path_darwin(fake_plugin_dir):
    """On macOS, deps path should resolve to ~/Library/Application Support/ClipABit/deps."""
    shim = installer_script.generate_bootstrap_shim(fake_plugin_dir / "clipabit.py")
    original = (fake_plugin_dir / "clipabit.py").read_text()
    preamble = shim[: shim.index(original)]
    assert "~/Library/Application Support/ClipABit/deps" in preamble


def test_shim_deps_path_win32(fake_plugin_dir):
    """On Windows, deps path should use LOCALAPPDATA."""
    shim = installer_script.generate_bootstrap_shim(fake_plugin_dir / "clipabit.py")
    original = (fake_plugin_dir / "clipabit.py").read_text()
    preamble = shim[: shim.index(original)]
    assert "LOCALAPPDATA" in preamble
    assert "ClipABit" in preamble
    assert "deps" in preamble
