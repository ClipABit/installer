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
# Clean previous builds
# -------------------------------------------------------------------
echo "Cleaning previous builds..."
rm -rf "${BUILD_DIR}"
rm -rf "${OUTPUT_DIR}"

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
for d in clipabit assets; do
    if [ ! -d "${PLUGIN_DIR}/$d" ]; then
        echo "ERROR: plugin/$d directory missing."
        exit 1
    fi
done
echo "Plugin validated."

# -------------------------------------------------------------------
# Build payload
# -------------------------------------------------------------------
echo "Creating build directories..."
mkdir -p "${PAYLOAD_DIR}/ClipABit"
mkdir -p "${OUTPUT_DIR}"

echo "Copying files into payload..."
cp "${SCRIPT_DIR}/installer-script.py" "${PAYLOAD_DIR}/ClipABit/"
cp -R "${PLUGIN_DIR}" "${PAYLOAD_DIR}/ClipABit/plugin"

# -------------------------------------------------------------------
# Template Auth0 values into postinstall
# -------------------------------------------------------------------
echo "Preparing postinstall script..."
cp "${SCRIPTS_DIR}/postinstall" "${SCRIPTS_DIR}/postinstall.bak" 2>/dev/null || true

sed -i.tmp \
    -e "s|__AUTH0_DOMAIN__|${CLIPABIT_AUTH0_DOMAIN}|g" \
    -e "s|__AUTH0_CLIENT_ID__|${CLIPABIT_AUTH0_CLIENT_ID}|g" \
    -e "s|__AUTH0_AUDIENCE__|${CLIPABIT_AUTH0_AUDIENCE}|g" \
    -e "s|__ENVIRONMENT__|${CLIPABIT_ENVIRONMENT}|g" \
    "${SCRIPTS_DIR}/postinstall"
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
# Restore postinstall from backup (undo sed templating)
# -------------------------------------------------------------------
if [ -f "${SCRIPTS_DIR}/postinstall.bak" ]; then
    mv "${SCRIPTS_DIR}/postinstall.bak" "${SCRIPTS_DIR}/postinstall"
fi

# -------------------------------------------------------------------
# Done
# -------------------------------------------------------------------
if [ -f "${OUTPUT_DIR}/${PKG_NAME}.pkg" ]; then
    echo ""
    echo "  Package built successfully!"
    echo "  Location: ${OUTPUT_DIR}/${PKG_NAME}.pkg"
    echo "  Size: $(du -h "${OUTPUT_DIR}/${PKG_NAME}.pkg" | cut -f1)"
    echo ""
else
    echo "ERROR: Package build failed!"
    exit 1
fi
