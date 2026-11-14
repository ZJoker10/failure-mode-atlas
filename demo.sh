#!/usr/bin/env bash
# Serve the atlas locally. Opening web/index.html by double-click works too --
# the file is self-contained -- but a local server makes the "next page" links,
# PDF page links and browser history behave exactly like a normal site.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${1:-8787}"
URL="http://localhost:${PORT}/"

if [ ! -f web/index.html ]; then
  echo "web/index.html is missing. Build it first:" >&2
  echo "  python -m atlas.view" >&2
  exit 1
fi

echo
echo "  Failure-Mode Atlas -> ${URL}"
echo "  (Ctrl-C to stop)"
echo

# Best effort: open a browser if this is a desktop session. Never fail on it.
if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
  ( sleep 1
    xdg-open "$URL" >/dev/null 2>&1 || \
    chromium "$URL" >/dev/null 2>&1 || \
    google-chrome "$URL" >/dev/null 2>&1 || true ) &
fi

exec python3 -m http.server "$PORT" --bind 127.0.0.1
