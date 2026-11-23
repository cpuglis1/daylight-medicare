"""Checked-block release for :8895 (Chris, November 17, 2026).

While the composer streams, each finished reply block is shown only after it
passes the same single-block checks the recovery path already uses
(composition_recovery.independent_blocks). Blocks are released in order; the
first block that fails stops release for the turn. A released block is never
taken back: say-once keeps it and a failed or repaired composition keeps it.

Off unless the :8895 launcher sets DAYLIGHT_BLOCK_RELEASE=on.
"""
import json
import os
import re
import time

ENV = 'DAYLIGHT_BLOCK_RELEASE'
SPEED_ENV = 'DAYLIGHT_REVEAL_WPS'
MAX_BLOCKS = 4
_KEY = re.compile(r'"reply_blocks"\s*:\s*\[')
_DECODER = json.JSONDecoder()


def enabled():
    return os.environ.get(ENV, '').strip() == 'on'


def reveal_speed():
    """Words per second for the page's reveal; 3 unless the launcher sets 1 to 30."""
    try:
        value = float(os.environ.get(SPEED_ENV, '3'))
    except ValueError:
        return 3.0
    return value if 1 <= value <= 30 else 3.0


def scan(text):
    """Return (fields_before_blocks, finished_blocks) from a partial composer reply.

    The composer's strict JSON lists its fields in schema order, so everything
    before "reply_blocks" is complete once that key appears. A block counts as
    finished only when its JSON string has closed. Anything unexpected returns
    (None, []) and nothing is released.
    """
    match = _KEY.search(text)
    if not match:
        return None, []
    head = text[:match.start()].rstrip()
    if not head.endswith(','):
        return None, []
    try:
        fields = json.loads(head[:-1] + '}')
    except ValueError:
        return None, []
    if not isinstance(fields, dict):
        return None, []
    blocks, at = [], match.end()
    while len(blocks) < MAX_BLOCKS:
        while at < len(text) and text[at] in ' \t\r\n,':
            at += 1
        if at >= len(text) or text[at] != '"':
            break
        try:
            value, at = _DECODER.raw_decode(text, at)
        except ValueError:
            break  # this block is still being written
        if not isinstance(value, str):
            break
        blocks.append(value)
    return fields, blocks


class Releaser:
    """Called with the composer's text so far; publishes checked blocks in order.

    check(fields, block) is the single-block check; a block that fails it stops
    release for the turn. guard(block, refs) is say-once: a block it holds back
    is skipped (the final reply holds it back too) and release continues.
    """

    def __init__(self, check, publish, guard=None, clock=time.perf_counter):
        self.check, self.publish, self.guard, self.clock = check, publish, guard, clock
        self.started = clock()
        self.fields = None
        self.released = []
        self.held = 0
        self.next = 0
        self.stopped = False
        self.first_ms = None
        self._seen = 0

    def _refs(self, index):
        refs = (self.fields or {}).get('block_refs')
        if isinstance(refs, list) and index < len(refs) and isinstance(refs[index], list):
            return [item for item in refs[index] if isinstance(item, str)]
        return None

    def __call__(self, text):
        if self.stopped or len(text) == self._seen:
            return
        self._seen = len(text)
        fields, blocks = scan(text)
        if fields is None:
            return
        if self.fields is None:
            self.fields = fields
        while self.next < len(blocks):
            block, index = blocks[self.next], self.next
            self.next += 1
            try:
                passed = bool(block.strip()) and self.check(self.fields, block)
            except Exception:  # a check that cannot run is a failed check
                passed = False
            if not passed:
                self.stopped = True
                return
            if self.guard is not None:
                try:
                    keep = self.guard(block, self._refs(index))
                except Exception:
                    self.stopped = True
                    return
                if not keep:
                    self.held += 1
                    continue
            self.released.append(block.strip())
            if self.first_ms is None:
                self.first_ms = round((self.clock() - self.started) * 1000)
            self.publish(list(self.released))

    def summary(self):
        """Counts only; never text."""
        return {'released': len(self.released), 'held': self.held, 'first_ms': self.first_ms,
                'stopped': self.stopped}
