#!/bin/bash
# Create a DMG from the built .app bundle.
# Usage: ./create_dmg.sh [path/to/TaxFlow Pro.app]
set -e

APP_NAME="TaxFlow Pro"
VERSION="3.11.6"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/dist"

APP_PATH="${1:-$BUILD_DIR/$APP_NAME.app}"
DMG_PATH="$BUILD_DIR/TaxFlowPro-$VERSION.dmg"

if [ ! -d "$APP_PATH" ]; then
    echo "[create_dmg] .app not found at $APP_PATH"
    exit 1
fi

echo "[create_dmg] Creating DMG at $DMG_PATH"

# Remove existing DMG
rm -f "$DMG_PATH"

# Create the DMG
hdiutil create -srcfolder "$APP_PATH" \
    -volname "$APP_NAME" \
    -fs HFS+ \
    -format UDZO \
    "$DMG_PATH"

echo "[create_dmg] DMG created: $DMG_PATH"