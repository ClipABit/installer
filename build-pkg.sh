#!/bin/bash
#
# Build ClipABit macOS .pkg Installer
#
# Required env vars for Auth0 config baking:
#   CLIPABIT_AUTH0_DOMAIN
#   CLIPABIT_AUTH0_CLIENT_ID
#   CLIPABIT_AUTH0_AUDIENCE
#   CLIPABIT_ENVIRONMENT  (optional, defaults to "prod")
#

set -e

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------
PKG_NAME="ClipABit"
PKG_VERSION="${CLIPABIT_PKG_VERSION:-1.0.0}"
PKG_IDENTIFIER="com.clipabit.plugin.installer"
INSTALL_LOCATION="/tmp/clipabit-staging"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BUILD_DIR="${SCRIPT_DIR}/build"
PAYLOAD_DIR="${BUILD_DIR}/payload"
SCRIPTS_DIR="${SCRIPT_DIR}/post-install-scripts"
OUTPUT_DIR="${SCRIPT_DIR}/dist"

# Bundled Python version
PYTHON_VERSION="3.11.12"
PYTHON_BUILD_TAG="20250529"
PYTHON_SHA256_ARM64="77d16e24444fa12096818064fcc3c12b041b0746f4481e3652fc60ee027a7fb5"
PYTHON_SHA256_X64="1fc7ee75b37a309443d5a214b83733cfda5ae7597559fb39ab8906f09c997c93"
PYTHON_CACHE_DIR="${BUILD_DIR}/python"

echo "=================================="
echo "  ClipABit Package Builder"
echo "=================================="
echo ""

# -------------------------------------------------------------------
# Validate Auth0 env vars
# -------------------------------------------------------------------
CLIPABIT_ENVIRONMENT="${CLIPABIT_ENVIRONMENT:-prod}"

if [ -z "$CLIPABIT_AUTH0_DOMAIN" ] || [ -z "$CLIPABIT_AUTH0_CLIENT_ID" ] || [ -z "$CLIPABIT_AUTH0_AUDIENCE" ]; then
    echo "WARNING: Auth0 env vars not fully set."
    echo "  CLIPABIT_AUTH0_DOMAIN=${CLIPABIT_AUTH0_DOMAIN:-(empty)}"
    echo "  CLIPABIT_AUTH0_CLIENT_ID=${CLIPABIT_AUTH0_CLIENT_ID:-(empty)}"
    echo "  CLIPABIT_AUTH0_AUDIENCE=${CLIPABIT_AUTH0_AUDIENCE:-(empty)}"
    echo ""
    echo "The installer will still build but config.dat won't be written at install time."
    echo ""
fi

# -------------------------------------------------------------------
# Clean previous builds (preserve python cache)
# -------------------------------------------------------------------
# NOTE: We preserve PYTHON_CACHE_DIR to avoid re-downloading ~100MB Python
# on every build. Only payload/ and dist/ are cleaned.
echo "Cleaning previous builds..."
rm -rf "${PAYLOAD_DIR}"
rm -rf "${OUTPUT_DIR}"

# -------------------------------------------------------------------
# Download standalone Python 3.11 (if not cached)
# -------------------------------------------------------------------
echo "Setting up bundled Python ${PYTHON_VERSION}..."

ARCH=$(uname -m)
case "$ARCH" in
    arm64)
        PYTHON_PLATFORM="aarch64-apple-darwin"
        PYTHON_SHA256="${PYTHON_SHA256_ARM64}"
        ;;
    x86_64)
        PYTHON_PLATFORM="x86_64-apple-darwin"
        PYTHON_SHA256="${PYTHON_SHA256_X64}"
        ;;
    *)
        echo "ERROR: Unsupported architecture: ${ARCH}"
        echo "Supported: arm64, x86_64"
        exit 1
        ;;
esac

PYTHON_ARCHIVE="cpython-${PYTHON_VERSION}+${PYTHON_BUILD_TAG}-${PYTHON_PLATFORM}-install_only.tar.gz"
PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_BUILD_TAG}/${PYTHON_ARCHIVE}"

mkdir -p "${PYTHON_CACHE_DIR}"

if [ -d "${PYTHON_CACHE_DIR}/python" ] && [ -x "${PYTHON_CACHE_DIR}/python/bin/python3" ]; then
    echo "  Using cached Python from ${PYTHON_CACHE_DIR}/python"
else
    echo "  Downloading ${PYTHON_URL}..."
    DOWNLOAD_PATH="${PYTHON_CACHE_DIR}/${PYTHON_ARCHIVE}"
    curl -fSL -o "${DOWNLOAD_PATH}" "${PYTHON_URL}"

    # Verify checksum to ensure download integrity (corrupted/MITM detection)
    echo "  Verifying checksum..."
    ACTUAL_SHA256=$(shasum -a 256 "${DOWNLOAD_PATH}" | awk '{print $1}')
    if [ "${ACTUAL_SHA256}" != "${PYTHON_SHA256}" ]; then
        echo "ERROR: Checksum mismatch for ${PYTHON_ARCHIVE}"
        echo "  Expected: ${PYTHON_SHA256}"
        echo "  Actual:   ${ACTUAL_SHA256}"
        rm -f "${DOWNLOAD_PATH}"
        exit 1
    fi
    echo "  Checksum OK."

    # Extract
    echo "  Extracting..."
    rm -rf "${PYTHON_CACHE_DIR}/python"
    tar xzf "${DOWNLOAD_PATH}" -C "${PYTHON_CACHE_DIR}"
    rm -f "${DOWNLOAD_PATH}"
fi

# Validate extracted Python (BUILD-TIME smoke test on developer machine)
# This catches corrupted downloads before packaging. Install-time validation
# happens separately on the end user's machine (see postinstall script).
BUNDLED_PYTHON="${PYTHON_CACHE_DIR}/python/bin/python3"
PYTHON_REPORTED=$("${BUNDLED_PYTHON}" --version 2>&1 | awk '{print $2}')
if [[ ! "${PYTHON_REPORTED}" == 3.11.* ]]; then
    echo "ERROR: Bundled Python reports ${PYTHON_REPORTED}, expected 3.11.x"
    exit 1
fi
echo "  Bundled Python: ${PYTHON_REPORTED}"

# Validate pip
if ! "${BUNDLED_PYTHON}" -m pip --version >/dev/null 2>&1; then
    echo "  pip not found, trying ensurepip..."
    "${BUNDLED_PYTHON}" -m ensurepip --default-pip
fi
echo "  pip: $("${BUNDLED_PYTHON}" -m pip --version 2>&1)"

# -------------------------------------------------------------------
# Ensure plugin/ exists (download if needed)
# -------------------------------------------------------------------
PLUGIN_DIR="${SCRIPT_DIR}/plugin"

if [ ! -f "${PLUGIN_DIR}/clipabit.py" ]; then
    echo "Plugin not found locally. Downloading from GitHub..."
    python3 "${SCRIPT_DIR}/installer-script.py" --download-only --staging-dir "${SCRIPT_DIR}"
fi

# Validate plugin
if [ ! -f "${PLUGIN_DIR}/clipabit.py" ]; then
    echo "ERROR: plugin/clipabit.py not found after download."
    exit 1
fi
if [ ! -f "${PLUGIN_DIR}/pyproject.toml" ]; then
    echo "ERROR: plugin/pyproject.toml not found. Required for dependency resolution."
    exit 1
fi
for d in clipabit scripts; do
    if [ ! -d "${PLUGIN_DIR}/$d" ]; then
        echo "ERROR: plugin/$d directory missing."
        exit 1
    fi
done
echo "Plugin validated."

# -------------------------------------------------------------------
# Build-time wheel validation
# -------------------------------------------------------------------
# IMPORTANT: The bundled Python has NO C compiler. We must verify that all
# dependencies have pre-built binary wheels (no source-only packages).
# If this check passes at build time, we guarantee install-time won't fail
# trying to compile C extensions.
echo "Validating all dependencies have binary wheels..."
WHEEL_CHECK_DIR=$(mktemp -d)
trap "rm -rf '${WHEEL_CHECK_DIR}'" EXIT

if ! "${BUNDLED_PYTHON}" -m pip install --dry-run --only-binary=:all: \
    --target "${WHEEL_CHECK_DIR}" \
    -r <("${BUNDLED_PYTHON}" -c "
import tomllib
with open('${PLUGIN_DIR}/pyproject.toml', 'rb') as f:
    data = tomllib.load(f)
for d in data['project']['dependencies']:
    print(d)
") 2>&1; then
    echo "ERROR: Not all dependencies have binary wheels."
    echo "The bundled Python has no C compiler — sdist-only packages will fail at install time."
    exit 1
fi
rm -rf "${WHEEL_CHECK_DIR}"
echo "  All dependencies have binary wheels."

# -------------------------------------------------------------------
# Build payload
# -------------------------------------------------------------------
echo "Creating build directories..."
mkdir -p "${PAYLOAD_DIR}/ClipABit"
mkdir -p "${OUTPUT_DIR}"

echo "Copying files into payload..."
cp "${SCRIPT_DIR}/installer-script.py" "${PAYLOAD_DIR}/ClipABit/"
cp -R "${PLUGIN_DIR}" "${PAYLOAD_DIR}/ClipABit/plugin"
cp -R "${PYTHON_CACHE_DIR}/python" "${PAYLOAD_DIR}/ClipABit/python"

# Exclude tests, docs, __pycache__, .git from payload to reduce installer size
# and avoid shipping unnecessary files to end users.
rm -rf "${PAYLOAD_DIR}/ClipABit/plugin/__pycache__"
find "${PAYLOAD_DIR}" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "${PAYLOAD_DIR}" -name ".git" -type d -exec rm -rf {} + 2>/dev/null || true
# Strip test suites from bundled Python's site-packages (setuptools, pkg_resources, etc.)
find "${PAYLOAD_DIR}/ClipABit/python" -path "*/site-packages/*/tests" -type d -exec rm -rf {} + 2>/dev/null || true

# -------------------------------------------------------------------
# Template Auth0 values into postinstall
# -------------------------------------------------------------------
echo "Preparing postinstall script..."
cp "${SCRIPTS_DIR}/postinstall" "${SCRIPTS_DIR}/postinstall.bak"

# Always restore postinstall from backup on exit to prevent leaking Auth0
# credentials. If pkgbuild fails mid-build, the templated postinstall file
# would remain in the repo with secrets embedded. This trap ensures cleanup.
restore_postinstall() {
    if [ -f "${SCRIPTS_DIR}/postinstall.bak" ]; then
        mv "${SCRIPTS_DIR}/postinstall.bak" "${SCRIPTS_DIR}/postinstall"
    fi
}
trap restore_postinstall EXIT

sed -i.tmp \
    -e "s|__AUTH0_DOMAIN__|${CLIPABIT_AUTH0_DOMAIN}|g" \
    -e "s|__AUTH0_CLIENT_ID__|${CLIPABIT_AUTH0_CLIENT_ID}|g" \
    -e "s|__AUTH0_AUDIENCE__|${CLIPABIT_AUTH0_AUDIENCE}|g" \
    -e "s|__ENVIRONMENT__|${CLIPABIT_ENVIRONMENT}|g" \
    "${SCRIPTS_DIR}/postinstall"

if [ $? -ne 0 ]; then
    echo "ERROR: sed templating failed"
    exit 1
fi
rm -f "${SCRIPTS_DIR}/postinstall.tmp"

chmod +x "${SCRIPTS_DIR}/postinstall"
chmod +x "${PAYLOAD_DIR}/ClipABit/installer-script.py"

# -------------------------------------------------------------------
# Build .pkg
# -------------------------------------------------------------------
echo "Building package..."
pkgbuild \
    --root "${PAYLOAD_DIR}" \
    --scripts "${SCRIPTS_DIR}" \
    --identifier "${PKG_IDENTIFIER}" \
    --version "${PKG_VERSION}" \
    --install-location "${INSTALL_LOCATION}" \
    "${OUTPUT_DIR}/${PKG_NAME}.pkg"

# -------------------------------------------------------------------
# Post-build verification
# -------------------------------------------------------------------
# Expand and inspect the .pkg before shipping to catch missing files or
# accidentally-included bloat (tests, docs, .git). This is a sanity check
# that runs before the package reaches end users.
#
# NOTE: This is different from postinstall validation:
#   - Build-time (here): QA on developer machine, catches build script bugs
#   - Install-time (postinstall): corruption detection on end user machine
# Both are needed - fail fast at build time, fail safe at install time.
if [ -f "${OUTPUT_DIR}/${PKG_NAME}.pkg" ]; then
    echo ""
    echo "  Verifying .pkg contents..."
    PKG_EXPAND_DIR=$(mktemp -d)
    pkgutil --expand "${OUTPUT_DIR}/${PKG_NAME}.pkg" "${PKG_EXPAND_DIR}/expanded"

    # Check for required files
    PAYLOAD_CONTENTS=$(cd "${PKG_EXPAND_DIR}/expanded" && find . -type f 2>/dev/null || true)
    for required in "installer-script.py" "python" "clipabit/__init__.py"; do
        if echo "$PAYLOAD_CONTENTS" | grep -q "$required"; then
            echo "    OK: $required found in payload"
        else
            echo "    WARNING: $required not found in payload"
        fi
    done
    # Check excluded files
    for excluded in "tests/" "docs/" ".git/"; do
        if echo "$PAYLOAD_CONTENTS" | grep -q "$excluded"; then
            echo "    WARNING: $excluded found in payload (should be excluded)"
        else
            echo "    OK: $excluded not in payload"
        fi
    done

    rm -rf "${PKG_EXPAND_DIR}"

    echo ""
    echo "  Package built successfully!"
    echo "  Location: ${OUTPUT_DIR}/${PKG_NAME}.pkg"
    echo "  Size: $(du -h "${OUTPUT_DIR}/${PKG_NAME}.pkg" | cut -f1)"
    echo ""
else
    echo "ERROR: Package build failed!"
    exit 1
fi
