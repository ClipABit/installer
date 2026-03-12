# ClipABit Installer

Builds macOS `.pkg` and Windows `.exe` installers for the ClipABit DaVinci Resolve plugin.

## Architecture

The installer deploys files into the DaVinci Resolve Fusion directory:

```
Fusion/
├── Scripts/Utility/
│   └── ClipABit.py              # Bootstrap shim (generated at install)
└── Modules/
    ├── clipabit/                 # Plugin package (from GitHub release)
    ├── clipabit_deps/            # pip dependencies (PyQt6, requests, etc.)
    └── assets/                   # Logo SVGs
```

**Bootstrap shim**: Prepends a config-loader and dependency-path-adder to the original `clipabit.py` shim. This loads Auth0 credentials from an obfuscated `config.dat` and adds `clipabit_deps/` to `sys.path` before the plugin starts.

**Config file**: `~/Library/Application Support/ClipABit/config.dat` (macOS) or `%APPDATA%/ClipABit/config.dat` (Windows). XOR + base64 encoded to prevent casual env switching.

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
# macOS
ls ~/Library/Application\ Support/Blackmagic\ Design/DaVinci\ Resolve/Fusion/Scripts/Utility/ClipABit.py
ls ~/Library/Application\ Support/Blackmagic\ Design/DaVinci\ Resolve/Fusion/Modules/clipabit/__init__.py
ls ~/Library/Application\ Support/Blackmagic\ Design/DaVinci\ Resolve/Fusion/Modules/clipabit_deps/
ls ~/Library/Application\ Support/Blackmagic\ Design/DaVinci\ Resolve/Fusion/Modules/assets/
ls ~/Library/Application\ Support/ClipABit/config.dat
```
