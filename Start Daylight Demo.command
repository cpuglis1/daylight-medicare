#!/bin/zsh
# One local process serves the current UI and API at localhost:8895.
umask 077
cd "$(dirname "$0")" || exit 1
exec infrastructure/daylight-data/.venv/bin/python alternatives/advisor-first/demo_server.py
