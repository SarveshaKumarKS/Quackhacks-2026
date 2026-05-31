#!/usr/bin/env bash
# Build the notch app, brand the bundle as "Quacky.app", and zip it into
# landing/downloads/Quacky-macOS.zip so the landing page's Download button works.
set -euo pipefail

LANDING_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$LANDING_DIR/.." && pwd)"
UI_DIR="$REPO_DIR/doppelganger-ui"
OUT_DIR="$LANDING_DIR/downloads"
ZIP_PATH="$OUT_DIR/Quacky-macOS.zip"

echo "==> Building the app..."
"$UI_DIR/build-app.sh" >/dev/null

SRC_APP="$UI_DIR/.build/app/DoppelgangerOS.app"
[ -d "$SRC_APP" ] || { echo "Build output not found: $SRC_APP" >&2; exit 1; }

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
QUACKY_APP="$STAGE/Quacky.app"

echo "==> Branding bundle as Quacky.app..."
cp -R "$SRC_APP" "$QUACKY_APP"   # CFBundleExecutable stays DoppelgangerOS (binary inside is unchanged)

mkdir -p "$OUT_DIR"
rm -f "$ZIP_PATH"
echo "==> Zipping -> $ZIP_PATH"
# ditto preserves macOS app structure & permissions better than plain zip.
( cd "$STAGE" && ditto -c -k --sequesterRsrc --keepParent "Quacky.app" "$ZIP_PATH" )

SIZE="$(du -h "$ZIP_PATH" | cut -f1)"
echo "==> Done: $ZIP_PATH ($SIZE)"
