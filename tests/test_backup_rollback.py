"""Tests for atomic install: backup, rollback, cleanup."""

from pathlib import Path

import pytest

from tests.conftest import installer_script


@pytest.fixture
def install_dirs(tmp_path):
    """Create the 4 override directories used by backup/rollback/cleanup."""
    scripts_dir = tmp_path / "Scripts" / "Utility"
    modules_dir = tmp_path / "Modules"
    clipabit_dir = tmp_path / "ClipABit"
    config_dir = tmp_path / "Config"
    for d in [scripts_dir, modules_dir, clipabit_dir, config_dir]:
        d.mkdir(parents=True)
    return scripts_dir, modules_dir, clipabit_dir, config_dir


@pytest.fixture
def installed_state(install_dirs):
    """Create a fully installed state: shim, plugin package, deps, python, config."""
    scripts_dir, modules_dir, clipabit_dir, config_dir = install_dirs

    # Shim
    shim = scripts_dir / "ClipABit.py"
    shim.write_text("# original shim v1\n")

    # Plugin package
    pkg = modules_dir / "clipabit"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("# v1\n")

    # Python runtime
    python_dir = clipabit_dir / "python"
    python_dir.mkdir()
    (python_dir / "python3").write_text("# fake python\n")

    # Deps
    deps = clipabit_dir / "deps"
    deps.mkdir()
    (deps / "requests.py").write_text("# fake\n")

    # Config
    config = config_dir / "config.dat"
    config.write_text("encoded-config-v1")

    return install_dirs


def test_backup_creates_bak_files(installed_state):
    """All 5 artifacts get .bak copies."""
    scripts_dir, modules_dir, clipabit_dir, config_dir = installed_state
    installer_script.backup_existing(scripts_dir, modules_dir, clipabit_dir, config_dir)

    assert (scripts_dir / "ClipABit.py.bak").exists()
    assert (modules_dir / "clipabit.bak").is_dir()
    assert (clipabit_dir / "python.bak").is_dir()
    assert (clipabit_dir / "deps.bak").is_dir()
    assert (config_dir / "config.dat.bak").exists()


def test_backup_fresh_install_no_bak(install_dirs):
    """Fresh install (nothing exists) creates no .bak files."""
    scripts_dir, modules_dir, clipabit_dir, config_dir = install_dirs
    installer_script.backup_existing(scripts_dir, modules_dir, clipabit_dir, config_dir)

    assert not (scripts_dir / "ClipABit.py.bak").exists()
    assert not (modules_dir / "clipabit.bak").exists()
    assert not (clipabit_dir / "python.bak").exists()
    assert not (clipabit_dir / "deps.bak").exists()
    assert not (config_dir / "config.dat.bak").exists()


def test_cleanup_removes_bak_on_success(installed_state):
    """After successful install, all .bak files/dirs are deleted."""
    scripts_dir, modules_dir, clipabit_dir, config_dir = installed_state
    installer_script.backup_existing(scripts_dir, modules_dir, clipabit_dir, config_dir)

    # Verify .bak exist first
    assert (scripts_dir / "ClipABit.py.bak").exists()

    installer_script.cleanup_backups(scripts_dir, modules_dir, clipabit_dir, config_dir)

    assert not (scripts_dir / "ClipABit.py.bak").exists()
    assert not (modules_dir / "clipabit.bak").exists()
    assert not (clipabit_dir / "python.bak").exists()
    assert not (clipabit_dir / "deps.bak").exists()
    assert not (config_dir / "config.dat.bak").exists()


def test_rollback_restores_previous_install(installed_state):
    """Simulate failure after backup — originals restored from .bak."""
    scripts_dir, modules_dir, clipabit_dir, config_dir = installed_state
    installer_script.backup_existing(scripts_dir, modules_dir, clipabit_dir, config_dir)

    # Simulate new (partial) files overwriting originals
    (scripts_dir / "ClipABit.py").write_text("# new shim v2\n")

    installer_script.rollback(scripts_dir, modules_dir, clipabit_dir, config_dir)

    # Original content should be restored
    assert (scripts_dir / "ClipABit.py").read_text() == "# original shim v1\n"
    assert (modules_dir / "clipabit" / "__init__.py").read_text() == "# v1\n"
    assert (config_dir / "config.dat").read_text() == "encoded-config-v1"
    # .bak should be gone after rollback
    assert not (scripts_dir / "ClipABit.py.bak").exists()


def test_rollback_partial_new_files_deleted(installed_state):
    """Simulate failure mid-install — partially-written new files are removed."""
    scripts_dir, modules_dir, clipabit_dir, config_dir = installed_state
    installer_script.backup_existing(scripts_dir, modules_dir, clipabit_dir, config_dir)

    # New shim was written, but plugin copy hasn't happened yet
    (scripts_dir / "ClipABit.py").write_text("# new shim v2\n")

    installer_script.rollback(scripts_dir, modules_dir, clipabit_dir, config_dir)

    # Originals restored
    assert (scripts_dir / "ClipABit.py").read_text() == "# original shim v1\n"


def test_rollback_fresh_install_cleans_up(install_dirs):
    """On fresh install failure, no .bak exists — just remove partial new files."""
    scripts_dir, modules_dir, clipabit_dir, config_dir = install_dirs
    installer_script.backup_existing(scripts_dir, modules_dir, clipabit_dir, config_dir)

    # Simulate partial install creating new files
    (scripts_dir / "ClipABit.py").write_text("# partial\n")
    pkg = modules_dir / "clipabit"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("# partial\n")

    installer_script.rollback(scripts_dir, modules_dir, clipabit_dir, config_dir)

    # New files should be removed (no .bak to restore from)
    assert not (scripts_dir / "ClipABit.py").exists()
    assert not (modules_dir / "clipabit").exists()


def test_rollback_with_missing_bak_no_error(install_dirs):
    """Rollback doesn't crash if some .bak files don't exist (mixed state)."""
    scripts_dir, modules_dir, clipabit_dir, config_dir = install_dirs

    # Only create a shim .bak (simulating partial previous install)
    (scripts_dir / "ClipABit.py.bak").write_text("# old shim\n")

    # This should not raise
    installer_script.rollback(scripts_dir, modules_dir, clipabit_dir, config_dir)

    # Restored from .bak
    assert (scripts_dir / "ClipABit.py").read_text() == "# old shim\n"


def test_concurrent_bak_exists_at_start(installed_state):
    """If stale .bak files exist from a previous failed install, they're cleaned first."""
    scripts_dir, modules_dir, clipabit_dir, config_dir = installed_state

    # Create stale .bak files
    (scripts_dir / "ClipABit.py.bak").write_text("# stale bak\n")

    installer_script.backup_existing(scripts_dir, modules_dir, clipabit_dir, config_dir)

    # The .bak should contain the CURRENT content, not the stale one
    assert (scripts_dir / "ClipABit.py.bak").read_text() == "# original shim v1\n"
