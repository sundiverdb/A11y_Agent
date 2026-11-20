#!/bin/bash
# Double-click to start the A11y Agent server and open a11yagent.html.
# Close this window (or press Ctrl-C) to stop the server.

cd "$(dirname "$0")" || exit 1
PAGE="$PWD/a11yagent.html"
HEALTH="http://127.0.0.1:5001/health"

if curl -s --max-time 1 "$HEALTH" >/dev/null 2>&1; then
  echo "The A11y Agent server is already running. Opening the page."
  open "$PAGE"
  exit 0
fi

if [ ! -x .venv/bin/python ]; then
  echo "Can't find .venv in $PWD."
  echo "Set it up with: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  read -r -p "Press Return to close."
  exit 1
fi

# Open the page as soon as the server answers (up to 15 seconds).
(
  for _ in $(seq 1 30); do
    if curl -s --max-time 1 "$HEALTH" >/dev/null 2>&1; then open "$PAGE"; exit 0; fi
    sleep 0.5
  done
  echo "The server didn't start. See the messages above."
) &

echo "Starting the A11y Agent. Close this window or press Ctrl-C to stop it."
exec .venv/bin/python audit_server.py
