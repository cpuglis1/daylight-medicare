#!/bin/bash
# Restarts the Daylight 8893 background service so server code changes take effect.
# 8894 forwards to it, so both pick up the change. Your open visit will need a reload.
cd "$(dirname "$0")" || exit 1
label="com.daylight.advisor-first.8893"
echo "Restarting $label …"
if launchctl kickstart -k "gui/$(id -u)/$label" 2>/dev/null; then
  echo "Restart requested."
else
  echo "Service not found under launchd; stopping any running 8893 server instead."
  pkill -f "advisor-first/server.py --port 8893" && echo "Stopped; launchd will start it again."
fi
for i in $(seq 1 40); do
  if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8893/api/status | grep -q 200; then echo "8893 is back up."; exit 0; fi
  sleep 1
done
echo "8893 did not answer within 40 seconds. Check alternatives/advisor-first/var/logs/errors.log."
