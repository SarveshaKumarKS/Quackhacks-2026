#!/usr/bin/env bash
set -euo pipefail

# Creates the lightweight, manually editable Doppelganger identity files.
# Run as either the primary user or clone; pass DOPPELGANGER_HOME to override.

DOPPELGANGER_HOME="${DOPPELGANGER_HOME:-$HOME/.doppelganger}"
USER_NAME="${USER_NAME:-$(id -un)}"

mkdir -p "$DOPPELGANGER_HOME"

write_if_missing() {
  local path="$1"
  local content="$2"
  if [ ! -f "$path" ]; then
    printf "%s\n" "$content" > "$path"
    echo "Created $path"
  else
    echo "Exists  $path"
  fi
}

write_if_missing "$DOPPELGANGER_HOME/identity.md" "# Identity

Name: $USER_NAME

## Role
Describe the user's work, current projects, and responsibilities.

## Voice
Describe how the user writes: tone, formality, greetings, sign-offs, and recurring phrases.

## Interests
List recurring topics the agent should remember."

write_if_missing "$DOPPELGANGER_HOME/preferences.md" "# Preferences

## Work Style
- Keep outputs concise unless asked for depth.
- Ask before irreversible actions like sending email.

## Tools
- Google Docs for research notes.
- Google Sheets for activity tracking.
- Gmail for approved outbound email.

## Scheduling
Describe meeting preferences, focus blocks, and calendar habits."

write_if_missing "$DOPPELGANGER_HOME/relationships.json" '{
  "contacts": []
}'

write_if_missing "$DOPPELGANGER_HOME/episodic.md" "# Episodic Memory

Timestamped notable events can be appended here by the user or future agent tooling."

echo
echo "Persona files are ready in $DOPPELGANGER_HOME"
