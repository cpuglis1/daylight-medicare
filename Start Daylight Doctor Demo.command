#!/bin/zsh
# Isolated local doctor preview with an offline conversation and temporary guest store.
umask 077
cd "$(dirname "$0")" || exit 1
foundation="$PWD/infrastructure/daylight-data/.state"
local_pg="host=$foundation/socket port=55485 user=$(id -un)"
export DAYLIGHT_FOUNDATION_SOURCE_DSN="${DAYLIGHT_FOUNDATION_SOURCE_DSN:-$local_pg dbname=daylight_research_2026_r2}"
export DAYLIGHT_FOUNDATION_PACKAGE_DSN="${DAYLIGHT_FOUNDATION_PACKAGE_DSN:-$local_pg dbname=daylight_pilot_foundation_2026_r1}"
exec infrastructure/daylight-data/.venv/bin/python alternatives/advisor-first/demo_server.py \
  --fixture --port 8898 --doctor-foundation "$foundation/pilot-foundation-2026-r1/binding.json"
