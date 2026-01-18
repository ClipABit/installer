#!/bin/bash
#
# Build ClipABit Installer Package
# This script creates a macOS .pkg installer
#

set -e

# Configuration
PKG_NAME="ClipABit"
PKG_VERSION="1.0.0"
PKG_IDENTIFIER="com.clipabit.plugin.installer"
INSTALL_LOCATION="/tmp/clipabit-staging"

# Directories
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BUILD_DIR="${SCRIPT_DIR}/build"
PAYLOAD_DIR="${BUILD_DIR}/payload"
SCRIPTS_DIR="${SCRIPT_DIR}/scripts"
OUTPUT_DIR="${SCRIPT_DIR}/dist"

echo "=================================="
echo "ClipABit Package Builder"
echo "=================================="

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf "${BUILD_DIR}"
rm -rf "${OUTPUT_DIR}"

# Create directories
echo "Creating build directories..."
mkdir -p "${PAYLOAD_DIR}/ClipABit"
mkdir -p "${OUTPUT_DIR}"
mkdir -p "${SCRIPTS_DIR}"

# Copy installer files to payload
echo "Copying installer files..."
cp "${SCRIPT_DIR}/installer-script.py" "${PAYLOAD_DIR}/ClipABit/"
cp -r "${SCRIPT_DIR}/frontend" "${PAYLOAD_DIR}/ClipABit/"

# Make postinstall script executable
echo "Setting script permissions..."
chmod +x "${SCRIPTS_DIR}/postinstall"
chmod +x "${PAYLOAD_DIR}/ClipABit/installer-script.py"

# Build the package
echo "Building package..."
pkgbuild \
    --root "${PAYLOAD_DIR}" \
    --scripts "${SCRIPTS_DIR}" \
    --identifier "${PKG_IDENTIFIER}" \
    --version "${PKG_VERSION}" \
    --install-location "${INSTALL_LOCATION}" \
    "${OUTPUT_DIR}/${PKG_NAME}.pkg"

# Check if build was successful
if [ -f "${OUTPUT_DIR}/${PKG_NAME}.pkg" ]; then
    echo ""
    echo "✓ Package built successfully!"
    echo "  Location: ${OUTPUT_DIR}/${PKG_NAME}.pkg"
    echo "  Size: $(du -h "${OUTPUT_DIR}/${PKG_NAME}.pkg" | cut -f1)"
    echo ""
    echo "To install, double-click: ${PKG_NAME}.pkg"
else
    echo "✗ Package build failed!"
    exit 1
fi
