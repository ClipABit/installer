"""Tests for dependency parsing from pyproject.toml."""

import pytest

from tests.conftest import installer_script


def test_get_dependencies_valid(tmp_path, fake_pyproject_toml):
    """Valid pyproject.toml returns a dep list."""
    deps = ["requests>=2.31.0", "keyring>=24.0.0", "auth0-python>=4.7.0"]
    fake_pyproject_toml(deps=deps, path=tmp_path)
    result = installer_script.get_dependencies(tmp_path)
    assert result == deps


def test_get_dependencies_missing_file(tmp_path):
    """Missing pyproject.toml raises SystemExit."""
    with pytest.raises(SystemExit):
        installer_script.get_dependencies(tmp_path)


def test_get_dependencies_empty_list(tmp_path):
    """Empty dependencies list raises SystemExit."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "test"\ndependencies = []\n')
    with pytest.raises(SystemExit):
        installer_script.get_dependencies(tmp_path)


def test_get_dependencies_missing_key(tmp_path):
    """Missing [project] section raises SystemExit."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.setuptools]\npackages = ["clipabit"]\n')
    with pytest.raises(SystemExit):
        installer_script.get_dependencies(tmp_path)


def test_get_dependencies_preserves_markers(tmp_path, fake_pyproject_toml):
    """PEP 508 markers are kept verbatim."""
    deps = ['pywin32-ctypes>=0.2.0; sys_platform == "win32"']
    fake_pyproject_toml(deps=deps, path=tmp_path)
    result = installer_script.get_dependencies(tmp_path)
    assert result == deps


def test_get_dependencies_preserves_version_specs(tmp_path, fake_pyproject_toml):
    """Version specs (>=, ==, ~=) are preserved."""
    deps = ["requests>=2.31.0", "keyring==24.0.0", "auth0-python~=4.7"]
    fake_pyproject_toml(deps=deps, path=tmp_path)
    result = installer_script.get_dependencies(tmp_path)
    assert result == deps
