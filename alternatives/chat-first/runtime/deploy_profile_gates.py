"""Compatibility entry point for the canonical source-only sync workflow.

Defaults to comparison. Pass --apply --restart only for an authorized update.
"""
from sync_runtime import main

if __name__ == '__main__':
    raise SystemExit(main())
