#!/usr/bin/env python3
"""Launch either protected variant with the same national L01 adapter.

No source synchronization, profile migration, new database or budget reset.
The alternate's own build function owns its runtime, cookies, profiles and AI.
"""
import argparse
from pathlib import Path
import sys

SHARED_SCRIPTS = Path(__file__).resolve().parent
ALTERNATE_SOURCE = Path('/Users/cep4u/Documents/Codex/2026-10-23/task/daylight-chat-alternative')
ALTERNATE_RUNTIME = Path('/Users/cep4u/daylight-chat-alternative-runtime')


def build(variant, port, fixture=False, database=None):
    # Import shared adapter before selecting variant-specific modules.
    from l01_http import attach
    if variant == 'original':
        from ten_server import build as original
        return attach(original(port, fixture=fixture, database=database))
    if variant != 'alternate' or port == 8890:
        raise ValueError('Use a supported variant and preserve original port')
    source = ALTERNATE_SOURCE if fixture else ALTERNATE_RUNTIME
    sys.path.insert(0, str(source / 'cms-slice/scripts'))
    from chat_server import build as alternate
    return attach(alternate(port, fixture=fixture, database=database))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--variant', choices=['original', 'alternate'], required=True)
    p.add_argument('--port', type=int, required=True)
    p.add_argument('--fixture', action='store_true')
    p.add_argument('--database', type=Path)
    a = p.parse_args()
    server = build(a.variant, a.port, a.fixture, a.database)
    print(f'Daylight {a.variant} + gated national L01 at http://127.0.0.1:{server.server_port}/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
