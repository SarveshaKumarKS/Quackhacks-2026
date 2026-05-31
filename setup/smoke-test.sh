#!/usr/bin/env bash
set -u

ORCHESTRATOR_URL="${ORCHESTRATOR_URL:-http://127.0.0.1:8420}"
AGENT_URL="${AGENT_URL:-http://127.0.0.1:8421}"
CDP_URL="${CDP_URL:-http://127.0.0.1:9222}"

PASS=0
FAIL=0

ok() {
  printf "[PASS] %s\n" "$1"
  PASS=$((PASS + 1))
}

bad() {
  printf "[FAIL] %s\n" "$1"
  FAIL=$((FAIL + 1))
}

check_http() {
  local name="$1"
  local url="$2"
  local body
  body="$(curl -fsS --max-time 5 "$url" 2>/dev/null)"
  if [ $? -eq 0 ] && [ -n "$body" ]; then
    ok "$name"
    printf "%s\n" "$body" | head -c 300
    printf "\n"
    return 0
  fi
  bad "$name ($url)"
  return 1
}

echo "Doppelganger OS smoke test"
echo "=========================="

check_http "Orchestrator /" "$ORCHESTRATOR_URL/"
check_http "Orchestrator /state" "$ORCHESTRATOR_URL/state"
check_http "Agent server /" "$AGENT_URL/"

frame_type="$(curl -fsS --max-time 5 -o /dev/null -w '%{content_type}' "$AGENT_URL/frame.jpg" 2>/dev/null)"
if printf "%s" "$frame_type" | grep -qi 'image/jpeg'; then
  ok "Agent /frame.jpg returns image/jpeg"
else
  bad "Agent /frame.jpg image check"
fi

check_http "Chrome CDP /json/version" "$CDP_URL/json/version"

extract_payload='{"type":"action","path":"browser_use","action":"extract","args":{"url":"https://example.com"}}'
extract_result="$(curl -fsS --max-time 30 -X POST "$AGENT_URL/command" \
  -H 'Content-Type: application/json' \
  -d "$extract_payload" 2>/dev/null)"
if [ $? -eq 0 ] && printf "%s" "$extract_result" | grep -Eq '"success"[[:space:]]*:[[:space:]]*true'; then
  ok "Browser extract through agent-server"
  printf "%s\n" "$extract_result" | head -c 300
  printf "\n"
else
  bad "Browser extract through agent-server"
fi

workspace_dir="$(cd "$(dirname "$0")/.." && pwd)"
if [ -w "$workspace_dir" ]; then
  ok "Workspace writable for local Docs/Sheets fallbacks"
else
  bad "Workspace writable for local Docs/Sheets fallbacks"
fi

echo
echo "Result: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
