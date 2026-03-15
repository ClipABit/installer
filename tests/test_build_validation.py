"""Tests for build-time wheel validation.

These tests require network access and a bundled Python to be available.
Marked @pytest.mark.network.
"""

import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLED_PYTHON = REPO_ROOT / "build" / "python" / "python" / "bin" / "python3"
PLUGIN_DIR = REPO_ROOT / "plugin"

network = pytest.mark.network


def _have_bundled_python():
    return BUNDLED_PYTHON.exists() and BUNDLED_PYTHON.is_file()


def _have_plugin():
    return (PLUGIN_DIR / "pyproject.toml").exists()


@network
def test_wheel_validation_passes_current_deps():
    """Dry-run pip resolve succeeds for all current deps (binary wheels only)."""
    if not _have_bundled_python():
        pytest.skip("Bundled Python not found (run build-pkg.sh first)")
    if not _have_plugin():
        pytest.skip("plugin/ not found (download plugin first)")

    # Read deps from pyproject.toml
    result = subprocess.run(
        [str(BUNDLED_PYTHON), "-c",
         "import tomllib; "
         f"data = tomllib.load(open('{PLUGIN_DIR / 'pyproject.toml'}', 'rb')); "
         "print('\\n'.join(data['project']['dependencies']))"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"Failed to read deps: {result.stderr}"
    deps = [d.strip() for d in result.stdout.strip().split("\n") if d.strip()]

    with tempfile.TemporaryDirectory() as tmpdir:
        pip_result = subprocess.run(
            [str(BUNDLED_PYTHON), "-m", "pip", "install",
             "--dry-run", "--only-binary=:all:",
             "--target", tmpdir] + deps,
            capture_output=True, text=True,
        )
    assert pip_result.returncode == 0, \
        f"Wheel validation failed:\n{pip_result.stderr}"


@network
def test_wheel_validation_fails_sdist_only():
    """A known sdist-only package fails the binary-only check."""
    if not _have_bundled_python():
        pytest.skip("Bundled Python not found (run build-pkg.sh first)")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Use a package known to only have sdist (C extension, no wheels)
        result = subprocess.run(
            [str(BUNDLED_PYTHON), "-m", "pip", "install",
             "--dry-run", "--only-binary=:all:",
             "--target", tmpdir, "uwsgi"],
            capture_output=True, text=True,
        )
    # Should fail because --only-binary rejects sdist
    assert result.returncode != 0


@network
def test_python_version_validation():
    """Bundled Python reports 3.11.x."""
    if not _have_bundled_python():
        pytest.skip("Bundled Python not found (run build-pkg.sh first)")

    result = subprocess.run(
        [str(BUNDLED_PYTHON), "--version"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    version = result.stdout.strip()
    assert "3.11" in version, f"Expected 3.11.x, got: {version}"
