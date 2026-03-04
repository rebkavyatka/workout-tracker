#!/usr/bin/env bash
# ── Workout Tracker — Ubuntu startup script ──────────────────────────────────
# Run once to set up, then again to start.
# Usage: bash start.sh

set -e
cd "$(dirname "$0")"

APP_DIR="$(pwd)"
VENV="$APP_DIR/venv"
PORT=5173

echo "==> Workout Tracker startup"

# 1. Create virtualenv if missing
if [ ! -d "$VENV" ]; then
  echo "==> Creating Python virtualenv..."
  python3 -m venv "$VENV"
fi

# 2. Install/update dependencies
echo "==> Installing dependencies..."
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r requirements.txt

# 3. Run the app
echo "==> Starting app on http://0.0.0.0:$PORT"
exec "$VENV/bin/python" app.py
