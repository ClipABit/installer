# ClipABit Installer

Builds macOS `.pkg` and Windows `.exe` installers for the ClipABit DaVinci Resolve plugin.

## Architecture

The installer deploys files into two locations:

**1. DaVinci Resolve Fusion directory** (plugin code):
```
Fusion/
├── Scripts/Utility/
│   └── ClipABit.py              # Bootstrap shim (generated at install)
└── Modules/
    ├── clipabit/                 # Plugin package (from GitHub release)
    └── assets/                   # Logo SVGs
```

**2. ClipABit application directory** (runtime + dependencies):
```
# macOS: ~/Library/Application Support/ClipABit/
ClipABit/
├── python/                       # Bundled Python 3.11 runtime
├── deps/                         # pip dependencies (PyQt6, requests, etc.)
└── config.dat                    # Obfuscated Auth0 config

# Windows (split between LOCALAPPDATA and APPDATA):
%LOCALAPPDATA%\ClipABit\          # Non-roaming (large files)
├── python\                       # Bundled Python 3.11 runtime
└── deps\                         # pip dependencies (PyQt6, requests, etc.)

%APPDATA%\ClipABit\               # Roaming (small config)
└── config.dat                    # Obfuscated Auth0 config
```

**Why split locations?** Heavy, stable components (Python runtime ~100MB, dependencies) live outside Resolve so they survive Resolve updates/reinstalls. Lightweight plugin code (~few MB) lives in Resolve's Modules directory where it can be easily updated. On Windows, large files use `%LOCALAPPDATA%` (non-roaming) while config uses `%APPDATA%` (roaming) so it follows the user between machines.

**Bootstrap shim**: Prepends a config-loader and dependency-path-adder to the original `clipabit.py` shim. This loads Auth0 credentials from the obfuscated `config.dat` and adds the `deps/` directory to `sys.path` before the plugin starts.

## Prerequisites

- Python 3.12+
- Internet access (to download the plugin from GitHub releases)

## Auth0 Configuration

Auth0 values are provided as environment variables at **build time**:

```bash
export CLIPABIT_AUTH0_DOMAIN="your-domain.auth0.com"
export CLIPABIT_AUTH0_CLIENT_ID="your-client-id"
export CLIPABIT_AUTH0_AUDIENCE="your-audience"
export CLIPABIT_ENVIRONMENT="prod"  # optional, defaults to "prod"
```

These get baked into the macOS postinstall script via `sed` substitution during `build-pkg.sh`.

## Building

### macOS (.pkg)

```bash
# Set Auth0 env vars (see above), then:
chmod +x build-pkg.sh post-install-scripts/postinstall
./build-pkg.sh
```

Output: `dist/ClipABit.pkg`

### Windows (.exe)

```bat
build-exe.bat
```

Output: `dist/ClipABit-Installer.exe`

### CI (GitHub Actions)

The workflow at `.github/workflows/build-installers.yml` builds both installers automatically. It:

1. Downloads the plugin from the latest `Resolve-Plugin` release
2. Builds macOS .pkg and Windows .exe
3. Uploads both as artifacts (and creates a release on main)

Auth0 secrets must be set in the GitHub repo settings.

## Standalone Installer Script

You can also run the installer script directly:

```bash
# Download and install (needs Resolve installed)
python3 installer-script.py

# Download and install without Resolve check
python3 installer-script.py --skip-checks

# Download only (for build scripts)
python3 installer-script.py --download-only

# Install from local plugin directory
python3 installer-script.py --local /path/to/plugin

# Use a specific release tag
python3 installer-script.py --tag v1.2.3
```

## Verification

After installation, check these paths exist:

```bash
# macOS - Resolve directories
ls ~/Library/Application\ Support/Blackmagic\ Design/DaVinci\ Resolve/Fusion/Scripts/Utility/ClipABit.py
ls ~/Library/Application\ Support/Blackmagic\ Design/DaVinci\ Resolve/Fusion/Modules/clipabit/__init__.py
ls ~/Library/Application\ Support/Blackmagic\ Design/DaVinci\ Resolve/Fusion/Modules/assets/

# macOS - ClipABit application directory
ls ~/Library/Application\ Support/ClipABit/python/bin/python3.11
ls ~/Library/Application\ Support/ClipABit/deps/
ls ~/Library/Application\ Support/ClipABit/config.dat

# Windows - Resolve directories
dir "%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\ClipABit.py"
dir "%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Modules\clipabit"

# Windows - ClipABit application directory
dir "%LOCALAPPDATA%\ClipABit\python\python.exe"
dir "%LOCALAPPDATA%\ClipABit\deps"
dir "%APPDATA%\ClipABit\config.dat"
```
