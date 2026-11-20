#!/bin/bash
# Double-click to open your contacts CRM in the browser.
# Leave this window open while you use it; close it to stop the CRM.
cd "$(dirname "$0")/app" || exit 1
for PY in python3 "$HOME/anaconda3/bin/python3" /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if command -v "$PY" >/dev/null 2>&1 && "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 7) else 1)' >/dev/null 2>&1; then
    exec "$PY" server.py
  fi
done
echo "Couldn't find Python 3. Install it from https://www.python.org/downloads/ and double-click this file again."
read -n 1 -s -r -p "Press any key to close."
