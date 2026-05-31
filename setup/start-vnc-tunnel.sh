#!/usr/bin/env bash
set -euo pipefail

LOCAL_PORT="${LOCAL_PORT:-5901}"
REMOTE_PORT="${REMOTE_PORT:-5900}"

echo "Starting local VNC tunnel localhost:$LOCAL_PORT -> localhost:$REMOTE_PORT"
echo "Enable Remote Login first: System Settings > General > Sharing > Remote Login"
echo "Leave this terminal open while viewing Profile B."
echo
echo "In another terminal, open:"
echo "  open vnc://localhost:$LOCAL_PORT"
echo
exec ssh -NL "$LOCAL_PORT:localhost:$REMOTE_PORT" localhost
