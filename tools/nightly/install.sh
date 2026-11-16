#!/bin/bash
# Install or refresh the 3 AM Daylight nightly sync for the current macOS user.
# Re-run after changing tools/nightly/*. Remove with: install.sh --uninstall
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/Library/Application Support/daylight-nightly"
LABEL="com.daylight.nightly-sync"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
HOUR="${NIGHTLY_HOUR:-3}"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if [ "${1:-}" = "--uninstall" ]; then rm -f "$PLIST"; echo "Removed $LABEL (state kept in $APP)."; exit 0; fi

mkdir -p "$APP/bin" "$APP/runs" "$HOME/Library/LaunchAgents"
install -m 0755 "$SRC/run.sh" "$SRC/select_files.py" "$APP/bin/"
install -m 0644 "$SRC/prompt.md" "$APP/bin/"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$APP/bin/run.sh</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$APP/launchd.log</string>
  <key>StandardErrorPath</key><string>$APP/launchd.log</string>
  <key>ProcessType</key><string>Background</string>
</dict>
</plist>
EOF
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed $LABEL: runs daily at $HOUR:00 (or on next wake). Logs: $APP/runs/"
