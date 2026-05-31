#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="DoppelgangerOS"
APP_DIR="$SCRIPT_DIR/.build/app/$APP_NAME.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

cd "$SCRIPT_DIR"

echo "Building $APP_NAME..."
swift build

BIN_PATH="$(swift build --show-bin-path)/$APP_NAME"
if [ ! -x "$BIN_PATH" ]; then
  echo "Built executable not found: $BIN_PATH" >&2
  exit 1
fi

rm -rf "$APP_DIR"
mkdir -p "$MACOS" "$RESOURCES"
cp "$BIN_PATH" "$MACOS/$APP_NAME"
cp "Info.plist" "$CONTENTS/Info.plist"

# Copy SwiftPM resource bundles (e.g. the mascot sprite sheet) so Bundle.module resolves
# them inside the .app — into both Resources/ and next to the executable to be safe.
BIN_DIR="$(swift build --show-bin-path)"
for b in "$BIN_DIR"/*.bundle; do
  [ -e "$b" ] || continue
  cp -R "$b" "$RESOURCES/"
  cp -R "$b" "$MACOS/"
done

cat > "$CONTENTS/PkgInfo" <<'EOF'
APPL????
EOF

echo "Built app bundle:"
echo "  $APP_DIR"
echo
echo "Launch with:"
echo "  open '$APP_DIR'"
