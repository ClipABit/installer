"""Shared fixtures for ClipABit installer tests."""

import importlib.util
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import installer-script.py (hyphenated filename not valid as Python module)
# ---------------------------------------------------------------------------

_INSTALLER_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "installer-script.py"


def _load_installer_module():
    spec = importlib.util.spec_from_file_location("installer_script", _INSTALLER_SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    # Prevent main() from running on import
    mod.__name__ = "installer_script"
    spec.loader.exec_module(mod)
    sys.modules["installer_script"] = mod
    return mod


installer_script = _load_installer_module()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_pyproject_toml(tmp_path):
    """Factory fixture: writes a pyproject.toml with given deps list."""
    def _make(deps=None, path=None):
        if deps is None:
            deps = ['requests>=2.31.0', 'keyring>=24.0.0']
        target = path or tmp_path
        content = '[project]\nname = "clipabit"\nversion = "0.1.0"\ndependencies = [\n'
        for d in deps:
            # Use single quotes (TOML literal strings) to avoid escaping issues
            # with PEP 508 markers that contain double quotes
            content += f"    '{d}',\n"
        content += ']\n'
        pyproject = target / "pyproject.toml"
        pyproject.write_text(content)
        return pyproject
    return _make


@pytest.fixture
def fake_plugin_dir(tmp_path, fake_pyproject_toml):
    """Create a minimal valid plugin directory structure."""
    plugin = tmp_path / "plugin"
    plugin.mkdir()

    # clipabit.py (original shim)
    (plugin / "clipabit.py").write_text(
        '"""ClipABit Plugin"""\nimport sys\nprint("ClipABit loaded")\n'
    )

    # clipabit package
    pkg = plugin / "clipabit"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""ClipABit package"""\n')
    assets = pkg / "assets"
    assets.mkdir()
    (assets / "placeholder.txt").write_text("asset\n")

    # scripts dir
    scripts = plugin / "scripts"
    scripts.mkdir()
    (scripts / "example.py").write_text("# script\n")

    # pyproject.toml
    fake_pyproject_toml(path=plugin)

    return plugin
