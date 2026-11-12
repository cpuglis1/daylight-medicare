"""Reviewed model choices for the local advisor, with one shared spending cap."""
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
    'claude-opus-5-5': Model('Claude Opus 5.5', 'Anthropic', 2400, 4000, 200, 20000),
}
DEFAULT_MODEL = 'gpt-6.1-sol'


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
    return {
        'gpt-5.4': baseline,
        DEFAULT_MODEL: ResponsesClient(key=baseline.key or '', model=DEFAULT_MODEL,
                                       transport=baseline.transport),
        'claude-opus-5-5': ClaudeClient(claude_key(env_path)),
    }
