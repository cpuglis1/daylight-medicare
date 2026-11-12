# Local Daylight restart shortcut

`Restart Daylight and Reload 8894.command` restarts the :8893 launch agent,
checks both local status endpoints, and asks Firefox to reload the existing
:8894 tab. The Firefox step requires macOS Accessibility access for Terminal.

- `/bin/bash -n` passed, and `/usr/bin/osacompile -l JavaScript` compiled the embedded script.
- A Node simulation passed four cases: selected :8894 tab, background :8894 tab,
  wrong port, and missing Accessibility access.
- After opening the command from Finder, a new :8893 process was listening and
  both `/api/status` endpoints returned HTTP 200. The live Firefox reload was
  not observed. The first run with Terminal's Accessibility access remains to
  be verified.
