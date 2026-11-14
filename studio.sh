#!/usr/bin/env bash
# Start the Studio: one command, one local page.
#
# Unlike demo.sh this is not a static file server -- uploads are parsed on this
# machine, so a Python process has to be running. It binds 127.0.0.1 and prints
# where the uploads land, because "never leaves the machine" is the whole point.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${1:-8788}"
URL="http://localhost:${PORT}/"
PY="${PYTHON:-python3}"

# A stale server on this port would answer with a different build, which is a
# confusing thing to debug at a demo. Say so rather than half-starting.
if command -v fuser >/dev/null 2>&1 && fuser "${PORT}/tcp" >/dev/null 2>&1; then
  echo "Port ${PORT} is already in use. Either it is a Studio you left running," >&2
  echo "or something else is. Stop it with:" >&2
  echo "  fuser -k ${PORT}/tcp" >&2
  exit 1
fi

if [ ! -f atlas/studio_server.py ]; then
  echo "atlas/studio_server.py is missing; run this from the repository root." >&2
  exit 1
fi

echo
echo "  Studio -> ${URL}"
echo "  (Ctrl-C to stop)"
echo

# Best effort, same as demo.sh: a headless session should not fail to start.
if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
  ( sleep 1
    xdg-open "$URL" >/dev/null 2>&1 || \
    chromium "$URL" >/dev/null 2>&1 || \
    google-chrome "$URL" >/dev/null 2>&1 || true ) &
fi

exec "$PY" -m atlas.cli studio --port "$PORT" --no-open
