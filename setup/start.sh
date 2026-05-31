#!/usr/bin/env bash
# 🦆 Quacky — start the orchestrator ("the duck's brain") on Profile A.
# Installs Python deps on first run, then serves the FastAPI orchestrator on :8420.
# (Profile B's agent-server + permissions are covered in RUNBOOK.md.)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR/orchestrator"

echo "🦆 Installing Quacky's dependencies (first run can take a minute)..."
python3 -m pip install -q -r requirements.txt

echo "🦆 Quacky's brain is waking up on http://127.0.0.1:8420 ..."
echo "   Leave this running, then open Quacky.app. Press Ctrl+C to stop."
exec python3 -m uvicorn main:app --host 127.0.0.1 --port 8420
