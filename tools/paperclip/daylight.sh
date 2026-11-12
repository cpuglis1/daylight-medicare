#!/bin/sh
# Controls only the separate local Paperclip instance, never the Daylight app.
set -eu
export PATH="$HOME/.paperclip/runtime/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PAPERCLIP_TELEMETRY_DISABLED=1
export DO_NOT_TRACK=1
action="${1:-status}"
case "$action" in
  status|start|stop|restart)
    exec paperclipai service "$action" --instance daylight
    ;;
  backup)
    export PAPERCLIP_INSTANCE_ID=daylight
    exec paperclipai db:backup
    ;;
  *)
    printf '%s\n' 'Usage: daylight.sh status|start|stop|restart|backup'
    exit 2
    ;;
esac
