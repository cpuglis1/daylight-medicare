"""D178: bounded, owner/request-scoped progress. Never a model or result channel.

Only the :8895 builder enables receipts. Source boundaries elsewhere are no-ops
without an accepted turn context. Reads use their own lock, never the flow lock.
"""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from threading import RLock
from time import monotonic

STAGES = frozenset({'working', 'doctors', 'medicines', 'plans', 'composing'})
_current = ContextVar('daylight_turn_progress', default=None)


class Progress:
    def __init__(self, *, clock=monotonic, ttl=600, limit=512):
        self.clock, self.ttl, self.limit = clock, ttl, limit
        self.lock = RLock()
        self.receipts = OrderedDict()

    def _prune(self):
        cutoff = self.clock() - self.ttl
        for key, value in list(self.receipts.items()):
            if value['at'] <= cutoff:
                del self.receipts[key]

    def begin(self, key):
        with self.lock:
            self._prune()
            self.receipts[key] = {'state': 'working', 'stage': 'working', 'at': self.clock()}
            self.receipts.move_to_end(key)
            while len(self.receipts) > self.limit:
                self.receipts.popitem(last=False)

    def update(self, key, *, stage=None, state=None):
        if stage is not None and stage not in STAGES:
            raise ValueError('Use a supported progress stage.')
        if state is not None and state not in {'complete', 'failed'}:
            raise ValueError('Use a terminal progress state.')
        with self.lock:
            item = self.receipts.get(key)
            if item and item['state'] == 'working':
                item.update(at=self.clock())
                if stage is not None:
                    item['stage'] = stage
                if state is not None:
                    item['state'] = state

    def read(self, owner, request_id):
        with self.lock:
            self._prune()
            item = self.receipts.get((owner, request_id))
            if not item:
                return {'state': 'unknown'}
            return ({'state': 'working', 'stage': item['stage']} if item['state'] == 'working'
                    else {'state': item['state']})


@contextmanager
def track(progress, owner, request_id):
    context = {'progress': progress, 'key': (owner, request_id), 'accepted': False,
               'stage': 'working'} if progress else None
    token = _current.set(context)
    try:
        yield
    except BaseException:
        if context and context['accepted']:
            progress.update(context['key'], state='failed')
        raise
    else:
        if context and context['accepted']:
            progress.update(context['key'], state='complete')
    finally:
        _current.reset(token)


def accepted():
    context = _current.get()
    if context and not context['accepted']:
        context['progress'].begin(context['key'])
        context['accepted'] = True


def run(stage, operation, *args, **kwargs):
    """Report only while this real operation is executing; preserve exceptions."""
    context = _current.get()
    if not context or not context['accepted']:
        return operation(*args, **kwargs)
    before = context['stage']
    context['progress'].update(context['key'], stage=stage)
    context['stage'] = stage
    try:
        return operation(*args, **kwargs)
    finally:
        context['stage'] = before
        context['progress'].update(context['key'], stage=before)
