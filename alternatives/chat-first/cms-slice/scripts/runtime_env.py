"""Load only model settings from an explicitly selected local env file."""

import os
from pathlib import Path
import re

ALLOWED = {"OPENAI_API_KEY", "OPENAI_MODEL"}


def load_model_env(path):
    path = Path(path).expanduser()
    if not path.is_file() or path.stat().st_size > 100_000:
        raise ValueError("Model environment file is missing or too large")
    found = {}
    for line in path.read_text().splitlines():
        match = re.fullmatch(r"\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*", line)
        if not match or match[1] not in ALLOWED:
            continue
        value = match[2]
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError("Malformed model setting")
            value = value[1:-1]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
        if value and "\x00" not in value and len(value) <= 1000:
            found[match[1]] = value
    for name, value in found.items():
        if not os.environ.get(name):
            os.environ[name] = value
    return {name: bool(os.environ.get(name)) for name in ALLOWED}
