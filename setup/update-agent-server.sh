#!/usr/bin/env bash
set -euo pipefail

SECOND_USER="${SECOND_USER:-clone}"
SECOND_HOME="/Users/$SECOND_USER"
SECOND_REPO_DIR="${SECOND_REPO_DIR:-$SECOND_HOME/Quackhacks-2026}"
PRIMARY_REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "Updating Profile B repo at $SECOND_REPO_DIR"

if sudo -u "$SECOND_USER" test -d "$SECOND_REPO_DIR/.git"; then
  sudo -H -u "$SECOND_USER" bash -lc "cd '$SECOND_REPO_DIR' && git pull --ff-only origin main"
else
  echo "No git checkout found for clone; syncing from primary repo with rsync."
  sudo mkdir -p "$SECOND_REPO_DIR"
  sudo rsync -a --delete \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='.build' \
    --exclude='*.pyc' \
    --exclude='orchestrator/.env' \
    "$PRIMARY_REPO_DIR/" "$SECOND_REPO_DIR/"
  sudo chown -R "$SECOND_USER:staff" "$SECOND_REPO_DIR"
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
sudo -H -u "$SECOND_USER" bash -lc "cd '$SECOND_REPO_DIR' && $PYTHON_BIN -m pip install --user -r agent-server/requirements.txt"

"$PRIMARY_REPO_DIR/setup/restart-agent.sh"
