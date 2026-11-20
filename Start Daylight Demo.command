#!/bin/zsh
# One local process serves the current UI and API at localhost:8895.
umask 077
cd "$(dirname "$0")" || exit 1
foundation="$PWD/infrastructure/daylight-data/.state"
local_pg="host=$foundation/socket port=55485 user=$(id -un)"
export DAYLIGHT_FOUNDATION_SOURCE_DSN="${DAYLIGHT_FOUNDATION_SOURCE_DSN:-$local_pg dbname=daylight_research_2026_r2}"
export DAYLIGHT_FOUNDATION_PACKAGE_DSN="${DAYLIGHT_FOUNDATION_PACKAGE_DSN:-$local_pg dbname=daylight_pilot_foundation_2026_r1}"
# D187: return the demo to GPT-6.1 Sol; both API stages use low reasoning.
export DAYLIGHT_DEFAULT_MODEL="gpt-6.1-sol"
# Reserve budget from a local input ceiling instead of a token-count round trip (:8895 only, Nov 17, 2026).
# Set to provider_count to go back to exact counting.
export DAYLIGHT_TOKEN_PREFLIGHT="${DAYLIGHT_TOKEN_PREFLIGHT:-local_bound}"
# Checked-block release with the word-by-word reveal (:8895 only, Nov 17, 2026). Set to off to go back.
export DAYLIGHT_BLOCK_RELEASE="${DAYLIGHT_BLOCK_RELEASE:-on}"
export DAYLIGHT_REVEAL_WPS="${DAYLIGHT_REVEAL_WPS:-20}"
# Interpreter-notes experiment: standard or compact. A one-word file at
# alternatives/advisor-first/var/demo-8895/interpreter-notes overrides it without a restart.
export DAYLIGHT_INTERPRETER_NOTES="${DAYLIGHT_INTERPRETER_NOTES:-standard}"
exec infrastructure/daylight-data/.venv/bin/python alternatives/advisor-first/demo_server.py \
  --doctor-chat --doctor-foundation "$foundation/pilot-foundation-2026-r1/binding.json" \
  --conversation-checks
