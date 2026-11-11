"""Additive read-only adapters for selected 2026 layer sources."""
from importlib import import_module
from .common import DomainProjection, SourceRecord, account, canonical_json

TYPED_LAYERS = tuple(f'L{number:02}' for number in range(1, 16))


def _module(layer_id):
    if layer_id not in TYPED_LAYERS:
        raise NotImplementedError(f'{layer_id} is outside the fixed 2026 fifteen-layer composition')
    return import_module('.' + layer_id.lower(), __name__)


def iter_layer_records(root, layer_id):
    yield from _module(layer_id).iter_records(root)


def iter_layer_projections(root, layer_id):
    yield from _module(layer_id).iter_projections(root)
