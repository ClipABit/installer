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
import ssl
from pathlib import Path

# ---------------------------------------------------------------------------
# SSL Workaround for macOS (urllib.request fails if certs aren't installed)
# ---------------------------------------------------------------------------
def get_ssl_context():
    """Return an SSL context. Falls back to unverified if needed on macOS."""
    try:
        # On macOS, many Python installations (e.g. from python.org) don't include
        # root certificates. We fall back to an unverified context to ensure
        # downloads work out of the box for developers and CI.
        if platform.system() == "Darwin":
            return ssl._create_unverified_context()
        return ssl.create_default_context()
    except Exception:
        if hasattr(ssl, '_create_unverified_context'):
            return ssl._create_unverified_context()
        return None


try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        import pip._vendor.tomli as tomllib

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
    _deps_locations = {{
        "darwin": os.path.expanduser(
            "~/Library/Application Support/ClipABit/deps"),
        "win32": os.path.join(
            os.environ.get("LOCALAPPDATA", ""), "ClipABit", "deps"),
    }}
    _deps = _deps_locations.get(sys.platform, "")
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


def get_python_exe(bundled_python_path=None) -> str:
    """Return the Python executable path.

    If *bundled_python_path* is given it is returned directly (used when a
    standalone Python runtime is bundled with the installer).  Otherwise falls
    back to the system Python.
    """
    if bundled_python_path is not None:
        return str(bundled_python_path)
    cmd = get_python_cmd()
    exe = shutil.which(cmd)
    return exe or cmd


def get_resolve_directories(scripts_dir=None, modules_dir=None):
    """Return (scripts_utility_dir, modules_dir) for the current platform.

    Accepts optional overrides so callers (and tests) can redirect to temp dirs.
    """
    if scripts_dir is not None and modules_dir is not None:
        return scripts_dir, modules_dir
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


def get_config_directory(override=None) -> Path:
    """Return the config directory.  Accepts an optional override."""
    if override is not None:
        return override
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library/Application Support/ClipABit"
    elif system == "Windows":
        return Path(os.getenv("APPDATA", "")) / "ClipABit"
    return Path.home() / ".config" / "clipabit"


def get_clipabit_directory(override=None) -> Path:
    """Return the ClipABit application directory (python runtime + deps).

    On macOS: ~/Library/Application Support/ClipABit
    On Windows: %LOCALAPPDATA%\\ClipABit  (machine-local, not roaming)
    """
    if override is not None:
        return override
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library/Application Support/ClipABit"
    elif system == "Windows":
        # Fall back to known absolute path if LOCALAPPDATA is unset
        localappdata = os.getenv("LOCALAPPDATA")
        if not localappdata:
            localappdata = str(Path.home() / "AppData" / "Local")
        return Path(localappdata) / "ClipABit"
    return Path.home() / ".local" / "share" / "clipabit"


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

def check_resolve_running(skip=False) -> bool:
    """Check if DaVinci Resolve is currently running.

    Returns True if Resolve is running, False otherwise.
    This is used to display a warning, not to block installation.
    """
    if skip:
        return False

    system = platform.system()
    try:
        if system == "Darwin":
            result = subprocess.run(
                ["pgrep", "-x", "DaVinci Resolve"],
                capture_output=True, text=True,
            )
        elif system == "Windows":
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Resolve.exe"],
                capture_output=True, text=True,
            )
        else:
            return False

        if result.returncode == 0:
            if system == "Windows" and "Resolve.exe" not in result.stdout:
                return False
            print_warning("DaVinci Resolve is currently running.")
            print_warning("Installation will proceed, but you must restart Resolve for changes to take effect.")
            return True
        return False
    except FileNotFoundError:
        # Could not check - assume not running
        return False

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
    """Verify that a suitable system Python exists and return its path (or None)."""
    print_info("Checking Python installation...")
    cmd = get_python_cmd()
    exe = shutil.which(cmd)
    if not exe:
        print_error(f"'{cmd}' not found in PATH.")
        return None
    print_success(f"Found: {exe}")

    try:
        # Require Python 3.11+ (aligned with bundled Python version)
        result = subprocess.run(
            [exe, "-c", "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}.{v.micro}'); sys.exit(0 if v >= (3,11) else 1)"],
            capture_output=True, text=True,
        )
        version = result.stdout.strip()
        if result.returncode != 0:
            print_error(f"Python {version} found but 3.11+ is required.")
            return None
        print_success(f"Python {version}")
        return exe
    except Exception as e:
        print_error(f"Python check failed: {e}")
        return None


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
            with urllib.request.urlopen(req, timeout=30, context=get_ssl_context()) as resp:
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
            with urllib.request.urlopen(req, timeout=60, context=get_ssl_context()) as resp, open(zip_path, "wb") as f:
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
                # Guard against zip-slip vulnerability: malicious archives can contain
                # paths like "../../../etc/passwd" to write outside the extraction dir.
                # We validate each entry before extracting to prevent path traversal.
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


def install_python_runtime(source: Path, target: Path):
    """Copy the bundled Python runtime from *source* to *target*.

    Preserves symlinks, removes macOS quarantine xattr, and validates
    that the copied python3 binary exists.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, symlinks=True)

    # Remove macOS quarantine xattr - macOS sets this on downloaded/extracted files.
    # The bundled Python is unsigned, so Gatekeeper would block execution without
    # removing this attribute. Similar to postinstall script behavior.
    if platform.system() == "Darwin":
        try:
            subprocess.run(
                ["xattr", "-dr", "com.apple.quarantine", str(target)],
                capture_output=True,
            )
        except FileNotFoundError:
            pass

    # Validate the Python binary exists and is executable
    if platform.system() == "Windows":
        python_exe = target / "python.exe"
    else:
        python_exe = target / "bin" / "python3"

    if not python_exe.exists():
        print_error(f"Python binary not found after copy: {python_exe}")
        return False

    if not os.access(python_exe, os.X_OK):
        print_error(f"Python binary is not executable: {python_exe}")
        return False

    print_success(f"Bundled Python installed: {target}")
    return True


def install_dependencies(target_dir: Path, plugin_dir: Path, python_exe=None):
    """Install Python dependencies to target_dir."""
    print_info(f"Installing dependencies to {target_dir}...")
    if target_dir.exists():
        print_info("Clearing previous dependencies...")
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    deps = get_dependencies(plugin_dir)

    exe = python_exe or get_python_exe()
    for dep in deps:
        print_info(f"  Installing {dep}...")
        try:
            # --only-binary=:all: ensures we only install prebuilt wheels.
            # The bundled Python has no C compiler, so source-only packages
            # (sdist) would fail to build. This flag forces pip to reject them.
            subprocess.run(
                [exe, "-m", "pip", "install",
                 "--target", str(target_dir),
                 "--only-binary=:all:",
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
# Backup / rollback / cleanup  (atomic install support)
# ---------------------------------------------------------------------------

# The five artifacts we back up:
#   1. scripts_dir/ClipABit.py        (file)
#   2. modules_dir/clipabit/           (dir)
#   3. clipabit_dir/python/            (dir)
#   4. clipabit_dir/deps/              (dir)
#   5. config_dir/config.dat           (file)

def _backup_item(path: Path, is_dir: bool = False):
    """Rename *path* to *path*.bak. Removes stale .bak first if present."""
    bak = Path(str(path) + ".bak")
    if bak.exists():
        if bak.is_dir():
            shutil.rmtree(bak)
        else:
            bak.unlink()
    if path.exists():
        path.rename(bak)


def backup_existing(scripts_dir, modules_dir, clipabit_dir, config_dir):
    """Snapshot current installation so a failed upgrade can roll back."""
    _backup_item(scripts_dir / "ClipABit.py")
    _backup_item(modules_dir / "clipabit", is_dir=True)
    _backup_item(clipabit_dir / "python", is_dir=True)
    _backup_item(clipabit_dir / "deps", is_dir=True)
    _backup_item(config_dir / "config.dat")


def rollback(scripts_dir, modules_dir, clipabit_dir, config_dir):
    """Remove partially-written new files and restore .bak originals."""
    items = [
        (scripts_dir / "ClipABit.py", False),
        (modules_dir / "clipabit", True),
        (clipabit_dir / "python", True),
        (clipabit_dir / "deps", True),
        (config_dir / "config.dat", False),
    ]
    for path, is_dir in items:
        bak = Path(str(path) + ".bak")
        # Remove the (potentially partial) new file/dir
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        # Restore from .bak if available
        if bak.exists():
            bak.rename(path)
    print_info("Rolled back to previous installation state.")


def cleanup_backups(scripts_dir, modules_dir, clipabit_dir, config_dir):
    """Delete all .bak files/dirs after a successful install."""
    bak_paths = [
        scripts_dir / "ClipABit.py.bak",
        modules_dir / "clipabit.bak",
        clipabit_dir / "python.bak",
        clipabit_dir / "deps.bak",
        config_dir / "config.dat.bak",
    ]
    for bak in bak_paths:
        if bak.exists():
            if bak.is_dir():
                shutil.rmtree(bak)
            else:
                bak.unlink()


# ---------------------------------------------------------------------------
# Install logic
# ---------------------------------------------------------------------------

def install_plugin(plugin_dir: Path, skip_checks: bool = False,
                   scripts_dir=None, modules_dir=None, config_dir=None,
                   clipabit_dir=None, bundled_python_dir=None) -> tuple[bool, bool]:
    """Full installation from a local plugin directory.

    All path parameters accept overrides for testability.  When *None*,
    platform defaults are used.

    Returns (success, resolve_was_running) tuple.
    """

    # --- Pre-flight ---
    print_info("Verifying system compatibility...")
    if not check_platform():
        return False, False

    resolve_was_running = False
    if not skip_checks:
        if not check_davinci_resolve():
            return False, False
        resolve_was_running = check_resolve_running()
    else:
        print_warning("Skipping DaVinci Resolve / Resolve-running checks (--skip-checks).")

    # --- Resolve directories ---
    scripts_dir, modules_dir = get_resolve_directories(scripts_dir, modules_dir)
    config_dir = get_config_directory(override=config_dir)
    clipabit_dir = get_clipabit_directory(override=clipabit_dir)
    print_info(f"Scripts dir:  {scripts_dir}")
    print_info(f"Modules dir:  {modules_dir}")
    print_info(f"ClipABit dir: {clipabit_dir}")

    # Determine Python exe (bundled takes priority)
    if bundled_python_dir is not None:
        # Windows bundled Python is at python.exe, macOS at bin/python3
        if platform.system() == "Windows":
            python_exe_path = str(bundled_python_dir / "python.exe")
        else:
            python_exe_path = str(bundled_python_dir / "bin" / "python3")
    else:
        python_exe_path = check_python()
        if not python_exe_path:
            return False, False
        if not check_pip():
            return False, False

    # Validate plugin source
    original_shim = plugin_dir / "clipabit.py"
    if not original_shim.exists():
        print_error(f"Plugin shim not found: {original_shim}")
        return False, False
    pkg_source = plugin_dir / "clipabit"
    if not pkg_source.is_dir():
        print_error(f"Plugin package not found: {pkg_source}")
        return False, False

    # --- Backup existing installation ---
    print_info("Backing up existing ClipABit installation...")
    backup_existing(scripts_dir, modules_dir, clipabit_dir, config_dir)

    try:
        # --- Install bundled Python runtime ---
        if bundled_python_dir is not None:
            print_info("Installing ClipABit Python runtime...")
            python_target = clipabit_dir / "python"
            install_python_runtime(bundled_python_dir, python_target)

            # Update python_exe_path to point to the installed runtime (after quarantine removal)
            if platform.system() == "Windows":
                python_exe_path = str(python_target / "python.exe")
            else:
                python_exe_path = str(python_target / "bin" / "python3")

        # --- Install dependencies ---
        print_info("Installing ClipABit dependencies...")
        deps_target = clipabit_dir / "deps"
        if not install_dependencies(deps_target, plugin_dir, python_exe=python_exe_path):
            raise RuntimeError("Dependency installation failed")

        # --- Copy plugin package to Modules/clipabit/ ---
        print_info("Installing ClipABit plugin files...")
        pkg_target = modules_dir / "clipabit"
        if pkg_target.exists():
            shutil.rmtree(pkg_target)
        modules_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(pkg_source, pkg_target)
        
        # Copy pyproject.toml inside the package so version tracking works
        shutil.copy2(plugin_dir / "pyproject.toml", pkg_target / "pyproject.toml")
        
        print_success(f"Plugin package installed: {pkg_target}")

        # --- Write config ---
        print_info("Configuring ClipABit...")
        auth0_domain = os.environ.get("CLIPABIT_AUTH0_DOMAIN", "")
        auth0_client_id = os.environ.get("CLIPABIT_AUTH0_CLIENT_ID", "")
        auth0_audience = os.environ.get("CLIPABIT_AUTH0_AUDIENCE", "")
        environment = os.environ.get("CLIPABIT_ENVIRONMENT", "prod")

        # Detect partial Auth0 config (some set, some not).
        # Partial config indicates a build-time error (env vars not fully set)
        # and will cause confusing runtime auth failures. We fail loudly here
        # to catch this at install time instead of letting users hit it later.
        auth0_vars = [auth0_domain, auth0_client_id, auth0_audience]
        any_set = any(auth0_vars)
        all_set = all(auth0_vars)
        if any_set and not all_set:
            print_error("Auth0 config partially set. All three must be set or none.")
            raise RuntimeError("Partial Auth0 config")

        if all_set:
            write_config(config_dir, auth0_domain, auth0_client_id, auth0_audience, environment)
        else:
            print_warning("Auth0 env vars not set. Skipping config.dat generation.")

        # --- Generate bootstrap shim (LAST) ---
        # CRITICAL: We write the shim LAST in the install process. This ensures
        # that if any earlier step fails (Python, deps, plugin files), Resolve
        # won't show a broken "ClipABit" menu entry. The shim is the user-facing
        # entry point, so it should only exist when the full installation is ready.
        print_info("Finalizing ClipABit installation...")
        shim_content = generate_bootstrap_shim(original_shim)
        try:
            # Validate syntax before writing to catch template/merge errors.
            # We don't want to write a broken Python file that would crash when
            # Resolve tries to load it from the Scripts menu.
            compile(shim_content, "ClipABit.py", "exec")
        except SyntaxError as e:
            print_error(f"Generated bootstrap shim has syntax error: {e}")
            raise RuntimeError("Shim syntax error")

        shim_target = scripts_dir / "ClipABit.py"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        shim_target.write_text(shim_content, encoding="utf-8")
        os.chmod(shim_target, 0o755)
        print_success(f"Bootstrap shim installed: {shim_target}")

    except Exception as e:
        print_error(f"Installation failed: {e}")
        rollback(scripts_dir, modules_dir, clipabit_dir, config_dir)
        return False, False

    # --- Success: clean up backups ---
    cleanup_backups(scripts_dir, modules_dir, clipabit_dir, config_dir)
    return True, resolve_was_running


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_installation(plugin_dir: Path | None = None, scripts_dir=None,
                        modules_dir=None, config_dir=None, clipabit_dir=None,
                        bundled_python_path=None) -> bool:
    """Verify the installation is complete and functional.

    All path parameters accept overrides for testability.
    """
    print_info("Verifying installation...")
    scripts_dir, modules_dir = get_resolve_directories(scripts_dir, modules_dir)
    config_dir = get_config_directory(override=config_dir)
    clipabit_dir = get_clipabit_directory(override=clipabit_dir)
    ok = True

    # Shim
    shim = scripts_dir / "ClipABit.py"
    if shim.exists():
        try:
            compile(shim.read_text(encoding="utf-8"), "ClipABit.py", "exec")
            print_success(f"Shim: {shim}")
        except SyntaxError:
            print_error(f"Shim has syntax error: {shim}")
            ok = False
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
    deps_dir = clipabit_dir / "deps"
    if deps_dir.is_dir() and any(deps_dir.iterdir()):
        print_success(f"Dependencies: {deps_dir}")
    else:
        print_error(f"Dependencies missing or empty: {deps_dir}")
        ok = False

    # Assets (inside clipabit package, not separate)
    assets_dir = modules_dir / "clipabit" / "assets"
    if assets_dir.is_dir():
        print_success(f"Assets: {assets_dir}")
    else:
        print_warning(f"Assets missing: {assets_dir}")

    # Config
    config_path = config_dir / "config.dat"
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

    return ok


# ---------------------------------------------------------------------------
# Uninstall logic
# ---------------------------------------------------------------------------

def get_dir_size(path: Path) -> int:
    """Return total size of a directory in bytes."""
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except OSError:
        pass
    return total


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def enumerate_installed_paths(scripts_dir=None, modules_dir=None,
                               config_dir=None, clipabit_dir=None):
    """Return a list of (path, is_dir, description) for all installed artifacts."""
    scripts_dir, modules_dir = get_resolve_directories(scripts_dir, modules_dir)
    config_dir = get_config_directory(override=config_dir)
    clipabit_dir = get_clipabit_directory(override=clipabit_dir)

    paths = [
        (scripts_dir / "ClipABit.py", False, "Bootstrap shim"),
        (modules_dir / "clipabit", True, "Plugin package"),
        (clipabit_dir / "python", True, "Python runtime"),
        (clipabit_dir / "deps", True, "Dependencies"),
        (config_dir / "config.dat", False, "Configuration"),
    ]

    # Also check for .bak variants
    for path, is_dir, desc in list(paths):
        bak = Path(str(path) + ".bak")
        if bak.exists():
            paths.append((bak, is_dir or bak.is_dir(), f"{desc} (backup)"))

    return [(p, d, desc) for p, d, desc in paths if p.exists()]


def clear_keyring():
    """Attempt to clear ClipABit keyring credentials.

    Tries platform-native commands since the bundled Python/deps may already
    be deleted by the time this runs.
    """
    system = platform.system()
    try:
        if system == "Darwin":
            result = subprocess.run(
                ["security", "delete-generic-password",
                 "-s", "clipabit-plugin", "-a", "tokens"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                print_success("Keychain credentials removed.")
            else:
                if "could not be found" in result.stderr.lower():
                    print_info("No keychain credentials found.")
                else:
                    print_warning(f"Keychain cleanup: {result.stderr.strip()}")
        elif system == "Windows":
            result = subprocess.run(
                ["cmdkey", "/delete:clipabit-plugin"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                print_success("Credential Manager entry removed.")
            else:
                print_info("No Credential Manager entry found.")
    except FileNotFoundError:
        print_warning("Could not clear keyring (command not found).")


def forget_pkg_receipt():
    """Remove the macOS installer pkg receipt."""
    if platform.system() != "Darwin":
        return
    try:
        result = subprocess.run(
            ["pkgutil", "--forget", "com.clipabit.plugin.installer"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print_success("Package receipt removed.")
        else:
            print_info("No package receipt found.")
    except FileNotFoundError:
        pass


def uninstall(yes: bool = False, scripts_dir=None, modules_dir=None,
              config_dir=None, clipabit_dir=None) -> bool:
    """Uninstall ClipABit from the current system.

    All path parameters accept overrides for testability.
    Returns True if uninstall completed, False otherwise.
    """
    print_header("ClipABit Uninstaller")

    # Check if Resolve is running
    resolve_running = check_resolve_running()
    if resolve_running:
        print_warning("Please close DaVinci Resolve before uninstalling.")
        if not yes:
            response = input("\n  Continue anyway? [y/N]: ").strip().lower()
            if response not in ("y", "yes"):
                print_info("Uninstall cancelled.")
                return False

    # Enumerate what exists
    installed = enumerate_installed_paths(scripts_dir, modules_dir,
                                          config_dir, clipabit_dir)

    if not installed:
        print_info("No ClipABit installation found. Nothing to remove.")
        return True

    # Display summary
    print_info("The following will be removed:\n")
    total_size = 0
    for path, is_dir, desc in installed:
        if is_dir:
            size = get_dir_size(path)
        else:
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
        total_size += size
        print(f"    {desc}: {path} ({format_size(size)})")
    print(f"\n    Total: {format_size(total_size)}")
    print()
    print_info("Keyring credentials (clipabit-plugin) will also be cleared.")
    if platform.system() == "Darwin":
        print_info("Package receipt (com.clipabit.plugin.installer) will be removed.")

    # Confirmation
    if not yes:
        response = input("\n  Proceed with uninstall? [y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            print_info("Uninstall cancelled.")
            return False

    # Delete artifacts — shim first (removes Resolve menu entry)
    removed = []
    failed = []
    for path, is_dir, desc in installed:
        try:
            if is_dir:
                shutil.rmtree(path)
            else:
                path.unlink()
            removed.append(desc)
            print_success(f"Removed: {desc}")
        except OSError as e:
            failed.append((desc, str(e)))
            print_error(f"Failed to remove {desc}: {e}")

    # Clear keyring credentials
    clear_keyring()

    # Remove pkg receipt (macOS only)
    forget_pkg_receipt()

    # Clean up staging leftovers
    staging = Path(tempfile.gettempdir()) / "clipabit-staging"
    if staging.exists():
        try:
            shutil.rmtree(staging)
            print_success("Removed staging leftovers.")
        except OSError:
            pass

    # Clean up empty parent directories
    scripts_dir_resolved, modules_dir_resolved = get_resolve_directories(scripts_dir, modules_dir)
    config_dir_resolved = get_config_directory(override=config_dir)
    clipabit_dir_resolved = get_clipabit_directory(override=clipabit_dir)
    for d in [clipabit_dir_resolved, config_dir_resolved]:
        if d.exists() and not any(d.iterdir()):
            try:
                d.rmdir()
                print_success(f"Removed empty directory: {d}")
            except OSError:
                pass

    # Summary
    print()
    if failed:
        print_warning(f"Uninstall completed with {len(failed)} error(s).")
        for desc, err in failed:
            print_error(f"  {desc}: {err}")
        return False
    else:
        print_header("ClipABit Uninstall Complete")
        print_success(f"Removed {len(removed)} item(s).")
        if resolve_running:
            print_warning("Restart DaVinci Resolve to clear the ClipABit menu entry.")
        return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ClipABit Plugin Installer")
    parser.add_argument("--uninstall", action="store_true",
                        help="Uninstall ClipABit from this system.")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip confirmation prompts (use with --uninstall).")
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

    # Handle uninstall mode
    if args.uninstall:
        success = uninstall(yes=args.yes)
        sys.exit(0 if success else 1)

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

    # Determine bundled Python path
    if getattr(sys, 'frozen', False):
        bundled_python_dir = Path(sys._MEIPASS) / "python"
    else:
        bundled_python_dir = script_dir / "python"
    if not bundled_python_dir.is_dir():
        bundled_python_dir = None

    # Run full install
    success, resolve_was_running = install_plugin(
        plugin_dir, skip_checks=args.skip_checks,
        bundled_python_dir=bundled_python_dir
    )
    if not success:
        print_error("Installation failed.")
        sys.exit(1)

    # Verify
    if not verify_installation(plugin_dir):
        print_warning("Installation completed with warnings.")
    else:
        print_header("ClipABit Installation Complete!")
        print_success("ClipABit has been installed successfully.")
        print()

        if resolve_was_running:
            print_warning("⚠️  DaVinci Resolve was running during installation.")
            print_warning("⚠️  You MUST restart DaVinci Resolve for ClipABit to work properly.")
            print()

        print_info("To access ClipABit in DaVinci Resolve:")
        print("  1. Open DaVinci Resolve")
        print("  2. Go to Workspace > Scripts > ClipABit")
        print()
        print_info("The ClipABit plugin will appear in the Scripts menu.")
        print()

    sys.exit(0)


if __name__ == "__main__":
    main()
