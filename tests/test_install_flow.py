"""Tests for install flow: python runtime, dependencies, full integration."""

import os
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from tests.conftest import installer_script


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def install_dirs(tmp_path):
    """Create the override directories for installation."""
    scripts_dir = tmp_path / "Scripts" / "Utility"
    modules_dir = tmp_path / "Modules"
    clipabit_dir = tmp_path / "ClipABit"
    config_dir = tmp_path / "Config"
    for d in [scripts_dir, modules_dir, clipabit_dir, config_dir]:
        d.mkdir(parents=True)
    return scripts_dir, modules_dir, clipabit_dir, config_dir


@pytest.fixture
def fake_bundled_python(tmp_path):
    """Create a fake bundled Python directory."""
    python_dir = tmp_path / "bundled_python"
    python_dir.mkdir()
    bin_dir = python_dir / "bin"
    bin_dir.mkdir()
    (bin_dir / "python3").write_text("#!/bin/sh\necho 'Python 3.11.0'\n")
    (bin_dir / "python3").chmod(0o755)
    return python_dir


# ---------------------------------------------------------------------------
# Round 7: install_python_runtime + updated install_dependencies
# ---------------------------------------------------------------------------

def test_install_bundled_python_copied(fake_bundled_python, install_dirs):
    """Python dir exists in target after copy."""
    _, _, clipabit_dir, _ = install_dirs
    target = clipabit_dir / "python"
    installer_script.install_python_runtime(fake_bundled_python, target)
    assert target.is_dir()
    assert (target / "bin" / "python3").exists()


def test_install_quarantine_removed(fake_bundled_python, install_dirs):
    """On macOS, xattr -dr is called to remove quarantine."""
    _, _, clipabit_dir, _ = install_dirs
    target = clipabit_dir / "python"
    with mock.patch("platform.system", return_value="Darwin"), \
         mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.MagicMock(returncode=0)
        installer_script.install_python_runtime(fake_bundled_python, target)
        # Verify xattr was called
        xattr_calls = [
            c for c in mock_run.call_args_list
            if c[0][0][0] == "xattr"
        ]
        assert len(xattr_calls) > 0
        assert "com.apple.quarantine" in str(xattr_calls[0])


def test_deps_installed_with_only_binary(tmp_path, fake_plugin_dir):
    """pip is invoked with --only-binary=:all:."""
    deps_dir = tmp_path / "deps"
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.MagicMock(returncode=0)
        installer_script.install_dependencies(
            deps_dir, fake_plugin_dir, python_exe="/usr/bin/python3"
        )
        # Check that --only-binary=:all: is in the pip call args
        for call in mock_run.call_args_list:
            args = call[0][0]
            if "-m" in args and "pip" in args:
                assert "--only-binary=:all:" in args, f"Missing --only-binary in: {args}"


def test_install_creates_directories(fake_bundled_python, tmp_path):
    """Non-existent target directories are created."""
    target = tmp_path / "nonexistent" / "deep" / "python"
    installer_script.install_python_runtime(fake_bundled_python, target)
    assert target.is_dir()


def test_fresh_install_no_config_when_unset(fake_plugin_dir, install_dirs):
    """No Auth0 vars -> no config.dat."""
    scripts_dir, modules_dir, clipabit_dir, config_dir = install_dirs

    with mock.patch.dict(os.environ, {}, clear=True), \
         mock.patch("platform.system", return_value="Darwin"), \
         mock.patch("platform.mac_ver", return_value=("14.0", ("", "", ""), "")), \
         mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.MagicMock(returncode=0, stdout="Python 3.11.0\n")

        # Create a minimal bundled python for install
        bundled = clipabit_dir / "bundled_python"
        bundled.mkdir()
        (bundled / "bin").mkdir()
        (bundled / "bin" / "python3").write_text("fake")

        installer_script.install_plugin(
            fake_plugin_dir,
            skip_checks=True,
            scripts_dir=scripts_dir,
            modules_dir=modules_dir,
            config_dir=config_dir,
            clipabit_dir=clipabit_dir,
            bundled_python_dir=bundled,
        )

    assert not (config_dir / "config.dat").exists()


# ---------------------------------------------------------------------------
# Round 8: Full install flow integration
# ---------------------------------------------------------------------------

def _run_install(fake_plugin_dir, install_dirs, env_extra=None, fail_at=None):
    """Helper: run install_plugin with mocked subprocess and optional failure injection."""
    scripts_dir, modules_dir, clipabit_dir, config_dir = install_dirs

    bundled = clipabit_dir / "bundled_python"
    bundled.mkdir(exist_ok=True)
    (bundled / "bin").mkdir(exist_ok=True)
    (bundled / "bin" / "python3").write_text("fake")

    env = {
        "HOME": "/tmp/fakehome",
    }
    if env_extra:
        env.update(env_extra)

    call_count = [0]
    original_fail_at = fail_at

    def _mock_run(args, **kwargs):
        result = mock.MagicMock(returncode=0, stdout="OK\n", stderr=b"")
        if original_fail_at is not None:
            call_count[0] += 1
            if call_count[0] >= original_fail_at:
                raise subprocess.CalledProcessError(1, args, stderr=b"mock failure")
        return result

    with mock.patch.dict(os.environ, env, clear=True), \
         mock.patch("platform.system", return_value="Darwin"), \
         mock.patch("platform.mac_ver", return_value=("14.0", ("", "", ""), "")), \
         mock.patch("subprocess.run", side_effect=_mock_run):
        result = installer_script.install_plugin(
            fake_plugin_dir,
            skip_checks=True,
            scripts_dir=scripts_dir,
            modules_dir=modules_dir,
            config_dir=config_dir,
            clipabit_dir=clipabit_dir,
            bundled_python_dir=bundled,
        )
    return result


def test_fresh_install_succeeds(fake_plugin_dir, install_dirs):
    """All artifacts exist after a clean install."""
    scripts_dir, modules_dir, clipabit_dir, config_dir = install_dirs
    assert _run_install(fake_plugin_dir, install_dirs) is True
    assert (scripts_dir / "ClipABit.py").exists()
    assert (modules_dir / "clipabit" / "__init__.py").exists()
    assert (clipabit_dir / "python").is_dir()
    assert (clipabit_dir / "deps").is_dir()


def test_fresh_install_shim_valid_syntax(fake_plugin_dir, install_dirs):
    """Installed shim passes compile() check."""
    scripts_dir, _, _, _ = install_dirs
    _run_install(fake_plugin_dir, install_dirs)
    shim = (scripts_dir / "ClipABit.py").read_text()
    compile(shim, "ClipABit.py", "exec")


def test_fresh_install_plugin_package_complete(fake_plugin_dir, install_dirs):
    """__init__.py exists in installed clipabit/."""
    _, modules_dir, _, _ = install_dirs
    _run_install(fake_plugin_dir, install_dirs)
    assert (modules_dir / "clipabit" / "__init__.py").exists()


def test_fresh_install_config_written(fake_plugin_dir, install_dirs):
    """config.dat exists and decodes correctly when Auth0 vars are set."""
    _, _, _, config_dir = install_dirs
    auth0 = {
        "CLIPABIT_AUTH0_DOMAIN": "test.auth0.com",
        "CLIPABIT_AUTH0_CLIENT_ID": "test-client-id",
        "CLIPABIT_AUTH0_AUDIENCE": "https://api.test.com",
    }
    _run_install(fake_plugin_dir, install_dirs, env_extra=auth0)
    config_path = config_dir / "config.dat"
    assert config_path.exists()
    decoded = installer_script.decode_config(config_path.read_text())
    assert decoded["CLIPABIT_AUTH0_DOMAIN"] == "test.auth0.com"


def test_fresh_install_auth0_partial_fails(fake_plugin_dir, install_dirs):
    """Partial Auth0 config (domain only) causes install to fail."""
    partial_auth0 = {
        "CLIPABIT_AUTH0_DOMAIN": "test.auth0.com",
        # Missing CLIENT_ID and AUDIENCE
    }
    result = _run_install(fake_plugin_dir, install_dirs, env_extra=partial_auth0)
    assert result is False


def test_upgrade_replaces_all_artifacts(fake_plugin_dir, install_dirs):
    """Second install overwrites first — old content gone."""
    scripts_dir, modules_dir, clipabit_dir, _ = install_dirs

    # First install
    _run_install(fake_plugin_dir, install_dirs)
    shim_v1 = (scripts_dir / "ClipABit.py").read_text()

    # Modify the original shim to simulate an upgrade
    (fake_plugin_dir / "clipabit.py").write_text("# upgraded v2\nprint('v2')\n")

    # Second install
    _run_install(fake_plugin_dir, install_dirs)
    shim_v2 = (scripts_dir / "ClipABit.py").read_text()

    assert "v2" in shim_v2
    assert shim_v1 != shim_v2


def test_upgrade_rollback_on_failure(fake_plugin_dir, install_dirs):
    """Failed install mid-way restores the previous installation."""
    scripts_dir, modules_dir, clipabit_dir, _ = install_dirs

    # First (successful) install
    _run_install(fake_plugin_dir, install_dirs)
    shim_v1 = (scripts_dir / "ClipABit.py").read_text()

    # Second install with failure during dep install (fail_at=1 means first subprocess call fails)
    _run_install(fake_plugin_dir, install_dirs, fail_at=1)

    # Original shim should be restored
    restored_shim = (scripts_dir / "ClipABit.py").read_text()
    assert restored_shim == shim_v1


def test_verify_installation_passes(fake_plugin_dir, install_dirs):
    """Verification succeeds after clean install."""
    scripts_dir, modules_dir, clipabit_dir, config_dir = install_dirs
    _run_install(fake_plugin_dir, install_dirs)

    # The mocked pip doesn't create real files, so add a placeholder to deps
    deps_dir = clipabit_dir / "deps"
    deps_dir.mkdir(exist_ok=True)
    (deps_dir / "requests.py").write_text("# placeholder\n")

    with mock.patch("platform.system", return_value="Darwin"):
        ok = installer_script.verify_installation(
            plugin_dir=fake_plugin_dir,
            scripts_dir=scripts_dir,
            modules_dir=modules_dir,
            config_dir=config_dir,
            clipabit_dir=clipabit_dir,
        )
    assert ok is True


def test_verify_installation_catches_missing_shim(fake_plugin_dir, install_dirs):
    """Verification fails if shim is deleted."""
    scripts_dir, modules_dir, clipabit_dir, config_dir = install_dirs
    _run_install(fake_plugin_dir, install_dirs)
    (scripts_dir / "ClipABit.py").unlink()

    with mock.patch("platform.system", return_value="Darwin"):
        ok = installer_script.verify_installation(
            plugin_dir=fake_plugin_dir,
            scripts_dir=scripts_dir,
            modules_dir=modules_dir,
            config_dir=config_dir,
            clipabit_dir=clipabit_dir,
        )
    assert ok is False


def test_verify_installation_catches_missing_package(fake_plugin_dir, install_dirs):
    """Verification fails if clipabit/ package is deleted."""
    scripts_dir, modules_dir, clipabit_dir, config_dir = install_dirs
    _run_install(fake_plugin_dir, install_dirs)
    import shutil
    shutil.rmtree(modules_dir / "clipabit")

    with mock.patch("platform.system", return_value="Darwin"):
        ok = installer_script.verify_installation(
            plugin_dir=fake_plugin_dir,
            scripts_dir=scripts_dir,
            modules_dir=modules_dir,
            config_dir=config_dir,
            clipabit_dir=clipabit_dir,
        )
    assert ok is False


def test_verify_installation_catches_missing_deps(fake_plugin_dir, install_dirs):
    """Verification fails if deps/ is empty."""
    scripts_dir, modules_dir, clipabit_dir, config_dir = install_dirs
    _run_install(fake_plugin_dir, install_dirs)
    # Empty out deps
    import shutil
    deps_dir = clipabit_dir / "deps"
    if deps_dir.exists():
        shutil.rmtree(deps_dir)
    deps_dir.mkdir()

    with mock.patch("platform.system", return_value="Darwin"):
        ok = installer_script.verify_installation(
            plugin_dir=fake_plugin_dir,
            scripts_dir=scripts_dir,
            modules_dir=modules_dir,
            config_dir=config_dir,
            clipabit_dir=clipabit_dir,
        )
    assert ok is False
