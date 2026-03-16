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
# -------------------------------------------------------------------
# IMPORTANT FOR DEVELOPERS:
# The bundled Python runtime is sourced from python-build-standalone:
# https://github.com/astral-sh/python-build-standalone/releases
#
# If you update PYTHON_VERSION or PYTHON_BUILD_TAG, you MUST update the
# SHA256 checksums below. This is a security feature (Dependency Pinning)
# that prevents supply-chain attacks and ensures every installer uses the
# exact same byte-for-byte runtime.
#
# To get new SHAs:
# 1. Visit the release page for the PYTHON_BUILD_TAG on GitHub.
# 2. IMPORTANT: Look ONLY for the "install_only" variants (e.g. cpython-...-install_only.tar.gz).
#    Ignore "debug", "pgo", "lto", or "full" variants as they are much larger and not needed.
# 3. Find the .sha256 file for the corresponding platform archive OR
#    calculate it manually after downloading:
#    shasum -a 256 cpython-<version>+<tag>-<platform>-install_only.tar.gz
# -------------------------------------------------------------------
PYTHON_VERSION="3.11.15"
PYTHON_BUILD_TAG="20260303"
PYTHON_SHA256_ARM64="0d29ed7cb6711890b3c6da27b6258c4ad3b506bf8d5a381bff531ca8fa67417f"
PYTHON_SHA256_X64="6ea2168c4e18cb31d9dc8486634dc375929bcc2adde0957399ce59d90b52297a"
# -------------------------------------------------------------------
PYTHON_CACHE_DIR="${BUILD_DIR}/python"

echo "=================================="
echo "  ClipABit Package Builder"
echo "=================================="
echo ""

# -------------------------------------------------------------------
# Validate Auth0 env vars
# -------------------------------------------------------------------
CLIPABIT_ENVIRONMENT="${CLIPABIT_ENVIRONMENT:-prod}"

if [ -z "$CLIPABIT_AUTH0_DOMAIN" ] || [ -z "$CLIPABIT_AUTH0_CLIENT_ID" ] || [ -z "$CLIPABIT_AUTH0_AUDIENCE" ] || [ -z "$CLIPABIT_ENVIRONMENT" ]; then
    echo "ERROR: Auth0 environment variables are not fully set."
    echo "  CLIPABIT_AUTH0_DOMAIN=${CLIPABIT_AUTH0_DOMAIN:-(missing)}"
    echo "  CLIPABIT_AUTH0_CLIENT_ID=${CLIPABIT_AUTH0_CLIENT_ID:-(missing)}"
    echo "  CLIPABIT_AUTH0_AUDIENCE=${CLIPABIT_AUTH0_AUDIENCE:-(missing)}"
    echo "  CLIPABIT_ENVIRONMENT=${CLIPABIT_ENVIRONMENT:-(missing)}"
    echo ""
    echo "The installer requires these values to be 'baked in' at build time."
    echo "Please export them in your terminal before running this script."
    exit 1
fi
echo "Auth0 configuration validated."

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
# Plugin retrieval
# -------------------------------------------------------------------
# Fetch the latest release tag metadata if in staging/prod environment.
# This ensures even local builds are correctly labeled with the tag they represent.
if [ "$CLIPABIT_ENVIRONMENT" = "staging" ]; then
    echo "  Staging environment detected. Fetching latest pre-release/release metadata..."
    API_URL="https://api.github.com/repos/ClipABit/Resolve-Plugin/releases"
    LATEST_TAG=$(curl -s "$API_URL" | jq -r '.[0].tag_name')
elif [ "$CLIPABIT_ENVIRONMENT" = "prod" ]; then
    echo "  Production environment. Fetching latest production release metadata..."
    API_URL="https://api.github.com/repos/ClipABit/Resolve-Plugin/releases/latest"
    LATEST_TAG=$(curl -s "$API_URL" | jq -r '.tag_name')
fi

if [ -n "$LATEST_TAG" ] && [ "$LATEST_TAG" != "null" ]; then
    echo "  Latest release tag: ${LATEST_TAG}"
fi

PLUGIN_DIR="${SCRIPT_DIR}/plugin"

if [ ! -f "${PLUGIN_DIR}/clipabit.py" ]; then
    echo "Plugin not found locally. Downloading from GitHub..."
    
    # Check for jq (required for parsing GitHub API response)
    if ! command -v jq &> /dev/null; then
        echo "ERROR: 'jq' is not installed. It is required to parse GitHub API responses."
        echo "Please install it (e.g., 'brew install jq' or 'sudo apt-get install jq')."
        exit 1
    fi
    
    if [ -z "$LATEST_TAG" ] || [ "$LATEST_TAG" = "null" ]; then
        echo "ERROR: Could not fetch release tag from GitHub API: $API_URL"
        exit 1
    fi
    
    ARCHIVE_URL="https://github.com/ClipABit/Resolve-Plugin/archive/refs/tags/${LATEST_TAG}.zip"
    
    TEMP_DIR=$(mktemp -d)
    echo "  Downloading ${ARCHIVE_URL}..."
    if ! curl -fSL -o "${TEMP_DIR}/plugin.zip" "${ARCHIVE_URL}"; then
        echo "ERROR: Failed to download plugin archive."
        rm -rf "${TEMP_DIR}"
        exit 1
    fi
    
    echo "  Extracting..."
    unzip -q "${TEMP_DIR}/plugin.zip" -d "${TEMP_DIR}"
    
    # Find the extracted folder (it will be named Resolve-Plugin-<tag>)
    EXTRACTED_DIR=$(find "${TEMP_DIR}" -maxdepth 1 -type d -name "Resolve-Plugin-*" | head -n 1)
    
    mkdir -p "${PLUGIN_DIR}"
    # Use rsync for better handling of file copies and excludes
    rsync -av --progress "${EXTRACTED_DIR}/" "${PLUGIN_DIR}/" --exclude ".git"
    rm -rf "${TEMP_DIR}"
    echo "  Plugin downloaded and staged."
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
echo "Packaging Plugin Release: ${LATEST_TAG:-local-build}"
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
    -e "s|__PLUGIN_RELEASE__|${LATEST_TAG:-local-build}|g" \
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

# 1. Build the component package
# This contains the actual files (payload) and the postinstall script.
COMPONENT_PKG="${BUILD_DIR}/${PKG_NAME}-Component.pkg"
pkgbuild \
    --root "${PAYLOAD_DIR}" \
    --scripts "${SCRIPTS_DIR}" \
    --identifier "${PKG_IDENTIFIER}" \
    --version "${PKG_VERSION}" \
    --install-location "${INSTALL_LOCATION}" \
    "${COMPONENT_PKG}"

# 2. Synthesize distribution file
# This is the 'blueprint' for the final installer UI.
DISTRIBUTION_XML="${BUILD_DIR}/distribution.xml"
productbuild --synthesize --package "${COMPONENT_PKG}" "${DISTRIBUTION_XML}"

# 3. Modify distribution.xml to include conclusion resource
# (sed -i on macOS needs an empty string for the extension)
sed -i '' "s|</installer-gui-script>|<conclusion file=\"conclusion.html\" mime-type=\"text/html\" />\n</installer-gui-script>|" "${DISTRIBUTION_XML}"

# 4. Build the final distribution package
# This combines the component package with resources like conclusion.html.
FINAL_PKG="${OUTPUT_DIR}/${PKG_NAME}.pkg"
productbuild \
    --distribution "${DISTRIBUTION_XML}" \
    --resources "${SCRIPT_DIR}/installer-resources" \
    --package-path "${BUILD_DIR}" \
    --version "${PKG_VERSION}" \
    "${FINAL_PKG}"

# -------------------------------------------------------------------
# Post-build verification
# -------------------------------------------------------------------
# Expand and inspect the .pkg before shipping to catch missing files or
# accidentally-included bloat (tests, docs, .git). This is a sanity check
# that runs before the package reaches end users.
if [ -f "${FINAL_PKG}" ]; then
    echo ""
    echo "  Verifying .pkg contents..."
    PKG_EXPAND_DIR=$(mktemp -d)
    pkgutil --expand "${FINAL_PKG}" "${PKG_EXPAND_DIR}/expanded"

    # Find all 'Bom' (Bill of Materials) files in the expanded package.
    # For productbuild, the component packages are expanded into subdirectories.
    BOM_FILES=$(find "${PKG_EXPAND_DIR}/expanded" -name "Bom")
    
    # Check for required files
    for required in "installer-script.py" "python" "clipabit/__init__.py"; do
        FOUND=0
        for bom in ${BOM_FILES}; do
            if lsbom "${bom}" | grep -q "${required}"; then
                FOUND=1
                break
            fi
        done
        if [ $FOUND -eq 1 ]; then
            echo "    OK: $required found in payload"
        else
            echo "    WARNING: ${required} not found in payload"
        fi
    done
    
    # Check excluded files (ensure bloat was correctly removed)
    for excluded in "tests/" "docs/" ".git/"; do
        FOUND_EXCLUDED=0
        for bom in ${BOM_FILES}; do
            if lsbom "${bom}" | grep -q "${excluded}"; then
                FOUND_EXCLUDED=1
                break
            fi
        done
        if [ $FOUND_EXCLUDED -eq 1 ]; then
            echo "    WARNING: $excluded found in payload (should be excluded)"
        else
            echo "    OK: ${excluded} not in payload"
        fi
    done

    rm -rf "${PKG_EXPAND_DIR}"

    echo ""
    echo "  Package built successfully!"
    echo "  Location: ${FINAL_PKG}"
    echo "  Size: $(du -h "${FINAL_PKG}" | cut -f1)"
    echo ""
else
    echo "ERROR: Package build failed!"
    exit 1
fi
