"""Tests for plugin download and zip-slip protection."""

import io
import zipfile
from pathlib import Path
from unittest import mock

import pytest

from tests.conftest import installer_script


def _make_zip_bytes(members: dict[str, str]) -> bytes:
    """Create an in-memory zip from {filename: content} dict."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _make_valid_plugin_zip(tag="v1.0.0"):
    """Create a well-formed plugin zip matching GitHub release format."""
    prefix = f"Resolve-Plugin-{tag}/"
    members = {
        f"{prefix}clipabit.py": "# shim\n",
        f"{prefix}pyproject.toml": '[project]\nname = "clipabit"\ndependencies = ["requests"]\n',
        f"{prefix}clipabit/__init__.py": "",
        f"{prefix}clipabit/main.py": "# main\n",
        f"{prefix}scripts/run.py": "# run\n",
    }
    return _make_zip_bytes(members)


def _mock_urlopen(zip_bytes):
    """Create a mock urlopen that works with both .read() and shutil.copyfileobj."""
    def _urlopen_side_effect(req, **kwargs):
        buf = io.BytesIO(zip_bytes)
        response = mock.MagicMock()
        response.read = buf.read
        response.__enter__ = lambda s: s
        response.__exit__ = mock.MagicMock(return_value=False)
        return response

    return _urlopen_side_effect


def test_zip_slip_dotdot_rejected(tmp_path):
    """Archive member with ../../ path is rejected."""
    zip_bytes = _make_zip_bytes({
        "Resolve-Plugin-v1/../../etc/passwd": "pwned",
        "Resolve-Plugin-v1/clipabit.py": "# shim\n",
    })
    staging = tmp_path / "staging"
    staging.mkdir()
    with mock.patch("urllib.request.urlopen", _mock_urlopen(zip_bytes)):
        result = installer_script.download_plugin_release(staging, tag="v1.0.0")
    assert result is False


def test_zip_slip_absolute_path_rejected(tmp_path):
    """Archive member starting with / is rejected."""
    zip_bytes = _make_zip_bytes({
        "/etc/passwd": "pwned",
        "Resolve-Plugin-v1/clipabit.py": "# shim\n",
    })
    staging = tmp_path / "staging"
    staging.mkdir()
    with mock.patch("urllib.request.urlopen", _mock_urlopen(zip_bytes)):
        result = installer_script.download_plugin_release(staging, tag="v1.0.0")
    assert result is False


def test_zip_slip_traversal_rejected(tmp_path):
    """Resolved path escaping tmpdir is rejected."""
    # Use a subtle traversal that resolved might escape
    zip_bytes = _make_zip_bytes({
        "Resolve-Plugin-v1/foo/../../../../../../tmp/pwned": "pwned",
        "Resolve-Plugin-v1/clipabit.py": "# shim\n",
    })
    staging = tmp_path / "staging"
    staging.mkdir()
    with mock.patch("urllib.request.urlopen", _mock_urlopen(zip_bytes)):
        result = installer_script.download_plugin_release(staging, tag="v1.0.0")
    assert result is False


def test_valid_archive_extracts(tmp_path):
    """Well-formed archive extracts and stages files."""
    zip_bytes = _make_valid_plugin_zip("v1.0.0")
    staging = tmp_path / "staging"
    staging.mkdir()
    with mock.patch("urllib.request.urlopen", _mock_urlopen(zip_bytes)):
        result = installer_script.download_plugin_release(staging, tag="v1.0.0")
    assert result is True
    plugin_dir = staging / "plugin"
    assert (plugin_dir / "clipabit.py").exists()
    assert (plugin_dir / "pyproject.toml").exists()
    assert (plugin_dir / "clipabit" / "__init__.py").exists()
    assert (plugin_dir / "scripts" / "run.py").exists()


def test_missing_clipabit_py_rejected(tmp_path):
    """Archive without clipabit.py is rejected."""
    prefix = "Resolve-Plugin-v1.0.0/"
    zip_bytes = _make_zip_bytes({
        f"{prefix}pyproject.toml": '[project]\ndependencies = ["requests"]\n',
        f"{prefix}clipabit/__init__.py": "",
        f"{prefix}scripts/run.py": "",
    })
    staging = tmp_path / "staging"
    staging.mkdir()
    with mock.patch("urllib.request.urlopen", _mock_urlopen(zip_bytes)):
        result = installer_script.download_plugin_release(staging, tag="v1.0.0")
    assert result is False


def test_missing_pyproject_toml_rejected(tmp_path):
    """Archive without pyproject.toml is rejected."""
    prefix = "Resolve-Plugin-v1.0.0/"
    zip_bytes = _make_zip_bytes({
        f"{prefix}clipabit.py": "# shim\n",
        f"{prefix}clipabit/__init__.py": "",
        f"{prefix}scripts/run.py": "",
    })
    staging = tmp_path / "staging"
    staging.mkdir()
    with mock.patch("urllib.request.urlopen", _mock_urlopen(zip_bytes)):
        result = installer_script.download_plugin_release(staging, tag="v1.0.0")
    assert result is False


def test_missing_required_dirs_rejected(tmp_path):
    """Archive without clipabit/ or scripts/ dir is rejected."""
    prefix = "Resolve-Plugin-v1.0.0/"
    zip_bytes = _make_zip_bytes({
        f"{prefix}clipabit.py": "# shim\n",
        f"{prefix}pyproject.toml": '[project]\ndependencies = ["requests"]\n',
        # No clipabit/ or scripts/ directories
    })
    staging = tmp_path / "staging"
    staging.mkdir()
    with mock.patch("urllib.request.urlopen", _mock_urlopen(zip_bytes)):
        result = installer_script.download_plugin_release(staging, tag="v1.0.0")
    assert result is False
