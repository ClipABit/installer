#!/usr/bin/env python3
"""
ClipABit Plugin Installer for DaVinci Resolve
Installs the ClipABit plugin on macOS and Windows with proper
Auth0 configuration, dependency isolation, and bootstrap shim.
"""

import sys
import os
import subprocess
import shutil
import platform
import json
import base64
import argparse
import tempfile
import urllib.request
import urllib.error
import zipfile
from pathlib import Path

import tomllib

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLUGIN_GITHUB_REPO = "ClipABit/Resolve-Plugin"
OBFUSCATION_KEY = "clipabit-resolve-plugin-2026"

# Bootstrap preamble prepended to the original shim.
# Double braces {{ }} are literal braces (needed for .format()).
BOOTSTRAP_PREAMBLE = '''\
# === ClipABit Installer Bootstrap ===
def _clipabit_bootstrap():
    import base64, json, os, sys
    _KEY = "{obf_key}"
    def _xor(data, key):
        kb = key.encode("utf-8")
        return bytes(b ^ kb[i % len(kb)] for i, b in enumerate(data))
    config_locations = {{
        "darwin": os.path.expanduser(
            "~/Library/Application Support/ClipABit/config.dat"),
        "win32": os.path.join(
            os.environ.get("APPDATA", ""), "ClipABit", "config.dat"),
    }}
    config_path = config_locations.get(
        sys.platform,
        os.path.expanduser("~/.config/clipabit/config.dat"),
    )
    if os.path.exists(config_path):
        try:
            raw = open(config_path, "r").read().strip()
            cfg = json.loads(_xor(base64.b64decode(raw), _KEY).decode("utf-8"))
            for k, v in cfg.items():
                os.environ.setdefault(k, str(v))
        except Exception:
            pass
    try:
        _sd = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        _sd = os.getcwd()
    _deps = os.path.abspath(os.path.join(_sd, "..", "..", "Modules", "clipabit_deps"))
    if os.path.isdir(_deps) and _deps not in sys.path:
        sys.path.insert(0, _deps)
_clipabit_bootstrap()
del _clipabit_bootstrap
# === End Installer Bootstrap ===

'''


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(message):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}\n")


def print_success(message):
    print(f"{Colors.OKGREEN}  {message}{Colors.ENDC}")


def print_error(message):
    print(f"{Colors.FAIL}  {message}{Colors.ENDC}")


def print_warning(message):
    print(f"{Colors.WARNING}  {message}{Colors.ENDC}")


def print_info(message):
    print(f"{Colors.OKCYAN}  {message}{Colors.ENDC}")


# ---------------------------------------------------------------------------
# Config obfuscation
# ---------------------------------------------------------------------------

def xor_bytes(data: bytes, key: str) -> bytes:
    kb = key.encode("utf-8")
    return bytes(b ^ kb[i % len(kb)] for i, b in enumerate(data))


def encode_config(config_dict: dict, key: str = OBFUSCATION_KEY) -> str:
    raw = json.dumps(config_dict).encode("utf-8")
    return base64.b64encode(xor_bytes(raw, key)).decode("ascii")


def decode_config(encoded: str, key: str = OBFUSCATION_KEY) -> dict:
    return json.loads(xor_bytes(base64.b64decode(encoded), key).decode("utf-8"))


# ---------------------------------------------------------------------------
# Platform helpers
# ---------------------------------------------------------------------------

def get_python_cmd() -> str:
    """Return the Python command name for the current platform."""
    if platform.system() == "Windows":
        return "python"
    return "python3"


# Resolved interpreter path; set by check_python() so all subprocess calls use the same interpreter.
_python_exe: str | None = None


def get_python_exe() -> str:
    """Return the resolved Python executable path. Use this for subprocess calls after check_python()."""
    global _python_exe
    if _python_exe is not None:
        return _python_exe
    cmd = get_python_cmd()
    exe = shutil.which(cmd)
    return exe or cmd


def get_resolve_directories():
    """Return (scripts_utility_dir, modules_dir) for the current platform."""
    system = platform.system()
    if system == "Darwin":
        base = Path.home() / "Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion"
    elif system == "Windows":
        appdata = os.getenv("APPDATA", "")
        base = Path(appdata) / "Blackmagic Design/DaVinci Resolve/Support/Fusion"
    else:
        print_error(f"Unsupported platform: {system}")
        sys.exit(1)
    return base / "Scripts" / "Utility", base / "Modules"


def get_config_directory() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library/Application Support/ClipABit"
    elif system == "Windows":
        return Path(os.getenv("APPDATA", "")) / "ClipABit"
    return Path.home() / ".config" / "clipabit"


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

def check_platform():
    system = platform.system()
    if system == "Darwin":
        print_success(f"Running on macOS {platform.mac_ver()[0]}")
        return True
    elif system == "Windows":
        print_success(f"Running on Windows {platform.version()}")
        return True
    print_error(f"Unsupported platform: {system}")
    return False


def check_davinci_resolve():
    print_info("Checking for DaVinci Resolve installation...")
    system = platform.system()
    if system == "Darwin":
        paths = [
            "/Applications/DaVinci Resolve/DaVinci Resolve.app",
            "/Applications/DaVinci Resolve Studio/DaVinci Resolve Studio.app",
        ]
    elif system == "Windows":
        paths = [
            r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe",
            r"C:\Program Files\Blackmagic Design\DaVinci Resolve Studio\Resolve.exe",
        ]
    else:
        return False

    for p in paths:
        if os.path.exists(p):
            print_success(f"Found DaVinci Resolve at: {p}")
            return True
    print_error("DaVinci Resolve not found.")
    print_info("Download from: https://www.blackmagicdesign.com/products/davinciresolve/")
    return False


def check_python():
    global _python_exe
    print_info("Checking Python installation...")
    cmd = get_python_cmd()
    exe = shutil.which(cmd)
    if not exe:
        print_error(f"'{cmd}' not found in PATH.")
        return False
    _python_exe = exe
    print_success(f"Found: {exe}")

    try:
        result = subprocess.run(
            [exe, "-c", "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}.{v.micro}'); sys.exit(0 if v >= (3,12) else 1)"],
            capture_output=True, text=True,
        )
        version = result.stdout.strip()
        if result.returncode != 0:
            print_error(f"Python {version} found but 3.12+ is required.")
            return False
        print_success(f"Python {version}")
        return True
    except Exception as e:
        print_error(f"Python check failed: {e}")
        return False


def check_pip():
    print_info("Checking pip...")
    exe = get_python_exe()
    try:
        result = subprocess.run(
            [exe, "-m", "pip", "--version"],
            capture_output=True, text=True, check=True,
        )
        print_success(f"pip: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError:
        print_warning("pip not found, trying ensurepip...")
        try:
            subprocess.run([exe, "-m", "ensurepip", "--default-pip"], check=True)
            print_success("pip installed via ensurepip.")
            return True
        except subprocess.CalledProcessError:
            print_error("Failed to install pip.")
            return False


# ---------------------------------------------------------------------------
# Plugin download
# ---------------------------------------------------------------------------

def download_plugin_release(staging_dir: Path, tag: str | None = None):
    """Download and extract the plugin from a GitHub release."""
    print_info(f"Downloading plugin from {PLUGIN_GITHUB_REPO}...")

    if tag:
        archive_url = f"https://github.com/{PLUGIN_GITHUB_REPO}/archive/refs/tags/{tag}.zip"
        print_info(f"Using tag: {tag}")
    else:
        api_url = f"https://api.github.com/repos/{PLUGIN_GITHUB_REPO}/releases/latest"
        try:
            req = urllib.request.Request(api_url, headers={"Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                tag = data["tag_name"]
                print_info(f"Latest release: {tag}")
        except urllib.error.URLError as e:
            if "timed out" in str(e).lower():
                print_error("Request to GitHub API timed out. Check your network and try again.")
            else:
                print_error(f"Failed to fetch latest release: {e}")
            return False
        except Exception as e:
            print_error(f"Failed to fetch latest release: {e}")
            return False
        archive_url = f"https://github.com/{PLUGIN_GITHUB_REPO}/archive/refs/tags/{tag}.zip"

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "plugin.zip"
        try:
            print_info(f"Downloading {archive_url}...")
            req = urllib.request.Request(archive_url)
            with urllib.request.urlopen(req, timeout=60) as resp, open(zip_path, "wb") as f:
                shutil.copyfileobj(resp, f)
        except urllib.error.URLError as e:
            if "timed out" in str(e).lower():
                print_error("Download timed out. Check your network and try again.")
            else:
                print_error(f"Download failed: {e}")
            return False
        except Exception as e:
            print_error(f"Download failed: {e}")
            return False

        with zipfile.ZipFile(zip_path, "r") as zf:
            tmp_path = Path(tmp)
            for info in zf.infolist():
                # Guard against zip-slip: ensure no path traversal
                name = info.filename
                if ".." in name or name.startswith("/") or (name.startswith("\\") and ".." in name):
                    print_error(f"Rejecting unsafe archive member: {name}")
                    return False
                dest = (tmp_path / name).resolve()
                if not str(dest).startswith(str(tmp_path.resolve())):
                    print_error(f"Rejecting path traversal: {name}")
                    return False
                zf.extract(info, tmp)

        # Find the extracted root (Resolve-Plugin-<tag>)
        roots = [d for d in Path(tmp).iterdir() if d.is_dir() and d.name.startswith("Resolve-Plugin")]
        if not roots:
            print_error("Could not find extracted plugin root directory.")
            return False
        archive_root = roots[0]

        # Validate required files
        if not (archive_root / "clipabit.py").exists():
            print_error("clipabit.py not found in release archive.")
            return False

        # Clear and populate staging_dir/plugin/
        plugin_dir = staging_dir / "plugin"
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)
        plugin_dir.mkdir(parents=True)

        shutil.copy2(archive_root / "clipabit.py", plugin_dir / "clipabit.py")
        for folder in ["clipabit", "scripts"]:
            src = archive_root / folder
            if src.is_dir():
                shutil.copytree(src, plugin_dir / folder)
            else:
                print_error(f"Required directory missing from release: {folder}")
                return False
        # Copy top-level assets if present (not required — plugin uses clipabit/assets/)
        top_assets = archive_root / "assets"
        if top_assets.is_dir():
            shutil.copytree(top_assets, plugin_dir / "assets")

        # Copy pyproject.toml (required for dependency resolution)
        pyproject = archive_root / "pyproject.toml"
        if not pyproject.exists():
            print_error("pyproject.toml not found in release archive.")
            return False
        shutil.copy2(pyproject, plugin_dir / "pyproject.toml")

    print_success("Plugin downloaded and staged.")
    return True


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------

def get_dependencies(plugin_dir: Path) -> list[str]:
    """Read dependencies from pyproject.toml. Fails if not found."""
    pyproject_path = plugin_dir / "pyproject.toml"
    if not pyproject_path.exists():
        print_error(f"pyproject.toml not found at {pyproject_path}")
        print_error("Cannot determine dependencies. Aborting.")
        sys.exit(1)

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    deps = data.get("project", {}).get("dependencies", [])
    if not deps:
        print_error("No dependencies listed in pyproject.toml [project].dependencies")
        sys.exit(1)
    print_success(f"Loaded {len(deps)} dependencies from pyproject.toml")
    return deps


def install_dependencies(target_dir: Path, plugin_dir: Path):
    """Install Python dependencies to target_dir."""
    print_info(f"Installing dependencies to {target_dir}...")
    if target_dir.exists():
        print_info("Clearing previous dependencies...")
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    deps = get_dependencies(plugin_dir)

    exe = get_python_exe()
    for dep in deps:
        print_info(f"  Installing {dep}...")
        try:
            subprocess.run(
                [exe, "-m", "pip", "install",
                 "--target", str(target_dir),
                 "--no-user",
                 "--no-cache-dir",
                 dep],
                check=True, capture_output=True,
            )
            print_success(f"  Installed {dep}")
        except subprocess.CalledProcessError as e:
            print_error(f"  Failed to install {dep}")
            stderr = e.stderr.decode() if e.stderr else "Unknown error"
            print_error(f"  {stderr}")
            return False

    print_success("All dependencies installed.")
    return True


# ---------------------------------------------------------------------------
# Bootstrap shim generation
# ---------------------------------------------------------------------------

def generate_bootstrap_shim(original_shim_path: Path) -> str:
    """Prepend the bootstrap preamble to the original plugin shim."""
    original = original_shim_path.read_text(encoding="utf-8")
    preamble = BOOTSTRAP_PREAMBLE.format(obf_key=OBFUSCATION_KEY)
    return preamble + original


# ---------------------------------------------------------------------------
# Config file
# ---------------------------------------------------------------------------

def write_config(config_dir: Path, auth0_domain: str, auth0_client_id: str,
                 auth0_audience: str, environment: str):
    """Write obfuscated config.dat."""
    config_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "CLIPABIT_AUTH0_DOMAIN": auth0_domain,
        "CLIPABIT_AUTH0_CLIENT_ID": auth0_client_id,
        "CLIPABIT_AUTH0_AUDIENCE": auth0_audience,
        "CLIPABIT_ENVIRONMENT": environment,
    }
    encoded = encode_config(config)
    config_path = config_dir / "config.dat"
    config_path.write_text(encoded, encoding="utf-8")
    print_success(f"Config written to {config_path}")
    return True


# ---------------------------------------------------------------------------
# Install logic
# ---------------------------------------------------------------------------

def install_plugin(plugin_dir: Path, skip_checks: bool = False):
    """Full installation from a local plugin directory."""

    # --- Pre-flight ---
    if not check_platform():
        return False

    if not skip_checks:
        if not check_davinci_resolve():
            return False
    else:
        print_warning("Skipping DaVinci Resolve check (--skip-checks).")

    if not check_python():
        return False
    if not check_pip():
        return False

    # --- Resolve directories ---
    scripts_dir, modules_dir = get_resolve_directories()
    print_info(f"Scripts dir: {scripts_dir}")
    print_info(f"Modules dir: {modules_dir}")

    # --- Generate bootstrap shim ---
    original_shim = plugin_dir / "clipabit.py"
    if not original_shim.exists():
        print_error(f"Plugin shim not found: {original_shim}")
        return False

    print_info("Generating bootstrap shim...")
    shim_content = generate_bootstrap_shim(original_shim)

    # Validate generated shim has valid Python syntax
    try:
        compile(shim_content, "ClipABit.py", "exec")
    except SyntaxError as e:
        print_error(f"Generated bootstrap shim has syntax error: {e}")
        return False

    shim_target = scripts_dir / "ClipABit.py"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    shim_target.write_text(shim_content, encoding="utf-8")
    os.chmod(shim_target, 0o755)
    print_success(f"Bootstrap shim installed: {shim_target}")

    # --- Copy plugin package to Modules/clipabit/ ---
    pkg_source = plugin_dir / "clipabit"
    pkg_target = modules_dir / "clipabit"
    if not pkg_source.is_dir():
        print_error(f"Plugin package not found: {pkg_source}")
        return False

    if pkg_target.exists():
        print_warning("Removing existing clipabit package...")
        shutil.rmtree(pkg_target)
    modules_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(pkg_source, pkg_target)
    print_success(f"Plugin package installed: {pkg_target}")

    # --- Install dependencies to Modules/clipabit_deps/ ---
    deps_target = modules_dir / "clipabit_deps"
    if not install_dependencies(deps_target, plugin_dir):
        return False

    # --- Write config ---
    auth0_domain = os.environ.get("CLIPABIT_AUTH0_DOMAIN", "")
    auth0_client_id = os.environ.get("CLIPABIT_AUTH0_CLIENT_ID", "")
    auth0_audience = os.environ.get("CLIPABIT_AUTH0_AUDIENCE", "")
    environment = os.environ.get("CLIPABIT_ENVIRONMENT", "prod")

    if auth0_domain and auth0_client_id and auth0_audience:
        config_dir = get_config_directory()
        write_config(config_dir, auth0_domain, auth0_client_id, auth0_audience, environment)
    else:
        print_warning("Auth0 env vars not set. Skipping config.dat generation.")
        print_info("Set CLIPABIT_AUTH0_DOMAIN, CLIPABIT_AUTH0_CLIENT_ID, CLIPABIT_AUTH0_AUDIENCE to enable.")

    return True


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_installation(plugin_dir: Path | None = None):
    """Verify the installation is complete and functional."""
    print_info("Verifying installation...")
    scripts_dir, modules_dir = get_resolve_directories()
    ok = True

    # Shim
    shim = scripts_dir / "ClipABit.py"
    if shim.exists():
        print_success(f"Shim: {shim}")
    else:
        print_error(f"Shim missing: {shim}")
        ok = False

    # Package
    pkg_init = modules_dir / "clipabit" / "__init__.py"
    if pkg_init.exists():
        print_success(f"Package: {modules_dir / 'clipabit'}")
    else:
        print_error(f"Package missing: {pkg_init}")
        ok = False

    # Deps
    deps_dir = modules_dir / "clipabit_deps"
    if deps_dir.is_dir() and any(deps_dir.iterdir()):
        print_success(f"Dependencies: {deps_dir}")
    else:
        print_error(f"Dependencies missing: {deps_dir}")
        ok = False

    # Assets (inside clipabit package, not separate)
    assets_dir = modules_dir / "clipabit" / "assets"
    if assets_dir.is_dir():
        print_success(f"Assets: {assets_dir}")
    else:
        print_warning(f"Assets missing: {assets_dir}")

    # Config
    config_path = get_config_directory() / "config.dat"
    if config_path.exists():
        try:
            encoded = config_path.read_text(encoding="utf-8").strip()
            cfg = decode_config(encoded)
            if cfg.get("CLIPABIT_AUTH0_DOMAIN"):
                print_success(f"Config: {config_path}")
            else:
                print_warning("Config exists but appears incomplete.")
        except Exception:
            print_warning("Config exists but could not be decoded.")
    else:
        print_warning(f"Config missing: {config_path}")

    # Import test — derive import targets from pyproject.toml when available
    print_info("Running import test...")
    exe = get_python_exe()
    # Map pip package names (or name prefixes) to Python import names
    package_to_import = {
        "pyqt6": "PyQt6",
        "auth0-python": "auth0",
        "auth0": "auth0",
        "watchdog": "watchdog",
        "requests": "requests",
        "keyring": "keyring",
    }
    # Try the provided plugin_dir first, then fall back to script_dir/plugin/
    pyproject_path = None
    if plugin_dir and (plugin_dir / "pyproject.toml").exists():
        pyproject_path = plugin_dir / "pyproject.toml"
    else:
        fallback = Path(__file__).parent.resolve() / "plugin" / "pyproject.toml"
        if fallback.exists():
            pyproject_path = fallback
    imports = []
    if pyproject_path:
        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
            deps_raw = data.get("project", {}).get("dependencies", [])
            seen = set()
            for spec in deps_raw:
                # PEP 508: package name is before ';' or '['; strip version (>=, ==, etc.)
                name_part = spec.split(";")[0].split("[")[0].strip().lower()
                pkg_key = name_part.split(">=")[0].split("==")[0].split("~=")[0].strip().replace("_", "-")
                for pkg_name, import_name in package_to_import.items():
                    if pkg_key == pkg_name or pkg_key == pkg_name.replace("_", "-"):
                        if import_name not in seen:
                            imports.append(import_name)
                            seen.add(import_name)
                        break
        except Exception:
            pass
    if not imports:
        imports = ["PyQt6", "requests", "keyring", "watchdog", "auth0"]
    test_script = (
        f"import sys; sys.path.insert(0, r'{deps_dir}'); "
        + "; ".join(f"import {mod}" for mod in imports)
        + "; print('OK')"
    )
    try:
        result = subprocess.run(
            [exe, "-c", test_script],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            print_success("Import test passed.")
        else:
            print_error(f"Import test failed: {result.stderr.strip()}")
            ok = False
    except Exception as e:
        print_warning(f"Import test error: {e}")

    return ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ClipABit Plugin Installer")
    parser.add_argument("--download-only", action="store_true",
                        help="Download the plugin to staging dir and exit.")
    parser.add_argument("--local", type=str, default=None,
                        help="Install from a local plugin directory instead of downloading.")
    parser.add_argument("--skip-checks", action="store_true",
                        help="Skip DaVinci Resolve check (useful for building on machines without Resolve).")
    parser.add_argument("--tag", type=str, default=None,
                        help="Specific release tag to download (e.g. v1.2.3).")
    parser.add_argument("--staging-dir", type=str, default=None,
                        help="Directory to stage the downloaded plugin into.")
    args = parser.parse_args()

    print_header("ClipABit Plugin Installer")

    # Determine staging directory
    script_dir = Path(__file__).parent.absolute()
    staging_dir = Path(args.staging_dir) if args.staging_dir else script_dir

    if args.local:
        # Install from local path
        plugin_dir = Path(args.local)
        if not plugin_dir.is_dir():
            print_error(f"Local plugin directory not found: {plugin_dir}")
            sys.exit(1)
    else:
        # Download if plugin/ doesn't exist yet
        plugin_dir = staging_dir / "plugin"
        if not plugin_dir.is_dir() or not (plugin_dir / "clipabit.py").exists():
            if not download_plugin_release(staging_dir, tag=args.tag):
                print_error("Failed to download plugin.")
                sys.exit(1)

    if args.download_only:
        print_success("Download complete. Exiting (--download-only).")
        sys.exit(0)

    # Run full install
    if not install_plugin(plugin_dir, skip_checks=args.skip_checks):
        print_error("Installation failed.")
        sys.exit(1)

    # Verify
    if not verify_installation(plugin_dir):
        print_warning("Installation completed with warnings.")
    else:
        print_header("Installation Complete!")
        print_success("ClipABit plugin has been installed successfully.")
        print()
        print_info("To use the plugin in DaVinci Resolve:")
        print("  1. Open DaVinci Resolve")
        print("  2. Go to Workspace > Scripts")
        print("  3. Select 'ClipABit'")
        print()

    sys.exit(0)


if __name__ == "__main__":
    main()
