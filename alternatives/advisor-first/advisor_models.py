"""Reviewed model prices; local daily allowances are shared within each provider."""
from dataclasses import dataclass
import os
import re

from chat import ResponsesClient
from claude_client import ClaudeClient


@dataclass(frozen=True)
class Model:
    label: str
    provider: str
    output_tokens: int
    input_rate: int
    cached_rate: int
    output_rate: int
    cache_write_rate: int = 0


MODELS = {
    'gpt-5.4': Model('GPT-5.4', 'OpenAI', 900, 2500, 250, 15000),
    'gpt-6.1-sol': Model('GPT-6.1 Sol', 'OpenAI', 2400, 2000, 100, 10000, cache_write_rate=2500),
    # Released 2026-11-17 at GPT-6.1 Sol's $2/$10 rates (Chris, Nov 17). Cached-input and
    # cache-write rates are not yet published separately; they mirror GPT-6.1 Sol.
    'gpt-6.2-sol': Model('GPT-6.2 Sol', 'OpenAI', 2400, 2000, 100, 10000, cache_write_rate=2500),
    'claude-opus-5-5': Model('Claude Opus 5.5', 'Anthropic', 2400, 4000, 200, 20000),
}
# :8895 sets DAYLIGHT_DEFAULT_MODEL in its launcher; :8893/:8894 keep GPT-6.1 Sol.
DEFAULT_MODEL = os.environ.get('DAYLIGHT_DEFAULT_MODEL', 'gpt-6.1-sol').strip() or 'gpt-6.1-sol'
if DEFAULT_MODEL not in MODELS or MODELS[DEFAULT_MODEL].provider != 'OpenAI':
    raise ValueError('DAYLIGHT_DEFAULT_MODEL must name a reviewed OpenAI model.')


def claude_key(env_path):
    for name in ('ANTHROPIC_API_KEY', 'CLAUDE_API_KEY'):
        if value := os.environ.get(name):
            return value.strip()
    if env_path.is_file() and env_path.stat().st_size <= 100_000:
        for line in env_path.read_text().splitlines():
            match = re.fullmatch(r'\s*(?:export\s+)?(?:ANTHROPIC_API_KEY|CLAUDE_API_KEY)\s*=\s*(.+?)\s*', line)
            if match:
                value = re.split(r'\s+#', match[1], maxsplit=1)[0].strip().strip('"\'')
                if value and len(value) <= 1000 and not any(char.isspace() for char in value):
                    return value
    return ''


def model_clients(baseline, env_path):
    clients = {'gpt-5.4': baseline}
    # GPT-6.1 Sol stays selectable when the default moves, so a run can go back.
    for identifier in dict.fromkeys((DEFAULT_MODEL, 'gpt-6.1-sol')):
        clients[identifier] = ResponsesClient(key=baseline.key or '', model=identifier,
                                              transport=baseline.transport)
    clients['claude-opus-5-5'] = ClaudeClient(claude_key(env_path))
    return clients
