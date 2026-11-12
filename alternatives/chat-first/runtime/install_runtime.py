"""Compatibility entry point: compare the preserved runtime; --apply is explicit.

The runtime already exists. Reinstalling it or changing launch configuration is
not part of source relocation. See ../README.md for current operations.
"""
from sync_runtime import main

if __name__ == '__main__':
    raise SystemExit(main())
