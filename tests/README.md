# Test Suite

## Running Tests

This project uses `uv` for fast Python package management and `pytest` for testing.

### Quick Start

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run all tests (excluding network and build artifact tests)
uv run pytest tests/ -m "not network and not build_artifact" --tb=short

# Run with verbose output
uv run pytest tests/ -m "not network and not build_artifact" -v

# Run with coverage
uv run pytest tests/ -m "not network and not build_artifact" --cov=. --cov-report=term

# Quick run (quiet mode)
uv run pytest tests/ -m "not network and not build_artifact" -q
```

### Test Categories

Tests are organized with pytest markers:

- **No marker**: Basic unit tests (always run, ~68 tests)
- **`@pytest.mark.network`**: Requires internet (downloads from GitHub)
- **`@pytest.mark.build_artifact`**: Requires built .pkg/.exe (run after building)

### Run Specific Test Categories

```bash
# Run only network tests (requires internet)
uv run pytest tests/ -m "network" --tb=short

# Run only build artifact tests (requires built installer)
uv run pytest tests/ -m "build_artifact" --tb=short

# Run a specific test file
uv run pytest tests/test_install_flow.py --tb=short

# Run a specific test function
uv run pytest tests/test_config.py::test_encode_decode_roundtrip -v
```

### Useful Options

```bash
# Stop on first failure
uv run pytest tests/ -m "not network and not build_artifact" -x

# Show local variables on failure
uv run pytest tests/ -m "not network and not build_artifact" -l

# Run tests in parallel (requires pytest-xdist)
uv pip install pytest-xdist --system
uv run pytest tests/ -m "not network and not build_artifact" -n auto

# Show print statements
uv run pytest tests/ -m "not network and not build_artifact" -s
```

## Test Files

| File | Description | Count |
|------|-------------|-------|
| `test_backup_rollback.py` | Atomic install backup/rollback logic | 8 |
| `test_bootstrap_shim.py` | Bootstrap shim generation & validation | 9 |
| `test_build_artifact.py` | Built .pkg/.exe contents verification | 12 |
| `test_build_validation.py` | Build-time wheel validation | 3 |
| `test_config.py` | Config obfuscation encode/decode | 5 |
| `test_dependencies.py` | Dependency parsing from pyproject.toml | 6 |
| `test_install_flow.py` | End-to-end installation scenarios | 16 |
| `test_platform.py` | Platform detection & path resolution | 12 |
| `test_plugin_download.py` | Plugin download & zip-slip protection | 7 |
| `test_resolve_check.py` | DaVinci Resolve running detection | 5 |

**Total:** 68 unit/integration tests

## Writing New Tests

```python
import pytest
from pathlib import Path

# Basic test
def test_something():
    assert True

# Network test (requires internet)
@pytest.mark.network
def test_download():
    # Downloads from GitHub
    pass

# Build artifact test (requires built .pkg/.exe)
@pytest.mark.build_artifact
def test_pkg_contents():
    # Inspects built installer
    pass

# Use fixtures from conftest.py
def test_with_fixture(tmp_path, fake_pyproject_toml):
    # tmp_path: pytest built-in fixture
    # fake_pyproject_toml: custom fixture from conftest.py
    pass
```

## Continuous Integration

Tests run automatically on:
- Every pull request
- Every push to `main`
- Manual workflow dispatch

See `.github/workflows/ci.yml` for the full CI configuration.

## Coverage

To generate a detailed coverage report:

```bash
# Terminal report
uv run pytest tests/ -m "not network and not build_artifact" --cov=. --cov-report=term-missing

# HTML report (opens in browser)
uv run pytest tests/ -m "not network and not build_artifact" --cov=. --cov-report=html
open htmlcov/index.html  # macOS
```

## Troubleshooting

### Tests fail with "ModuleNotFoundError"

Install test dependencies:
```bash
uv pip install pytest pytest-cov --system
```

### Tests fail with "installer-script.py not found"

The conftest.py uses `importlib` to import the hyphenated filename. This should work automatically, but if not, ensure you're running from the repo root:
```bash
cd /path/to/installer
uv run pytest tests/
```

### Network tests timeout

Increase pytest timeout or skip network tests:
```bash
uv run pytest tests/ -m "not network and not build_artifact" --tb=short
```
