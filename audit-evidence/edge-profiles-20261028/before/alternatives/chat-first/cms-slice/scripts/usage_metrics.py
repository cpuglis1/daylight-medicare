"""Request-local, content-free usage; never retain prompts or responses."""
from contextvars import ContextVar
import json
import logging
from pathlib import Path
import time

RATES = json.loads((Path(__file__).resolve().parents[1] / "config/model_rates.json").read_text())["models"]
CURRENT = ContextVar("milkman_turn_usage", default=None)


class TurnUsage:
    def __init__(self, model):
        self.started = time.monotonic()
        self.value = dict(model=model, model_calls=0, input_tokens=0, cached_input_tokens=0,
                          output_tokens=0, reasoning_tokens=0, tool_names=[], retry_count=0,
                          estimated_cost_usd=0 if model in RATES else None, usage_missing_calls=0)

    def __enter__(self):
        self.token = CURRENT.set(self)
        return self

    def __exit__(self, *args):
        CURRENT.reset(self.token)

    def capture(self, response):
        usage = response.get("usage") or {}
        if not usage:
            self.value["usage_missing_calls"] += 1
        amounts = {"input_tokens": usage.get("input_tokens", 0),
                   "cached_input_tokens": (usage.get("input_tokens_details") or {}).get("cached_tokens", 0),
                   "output_tokens": usage.get("output_tokens", 0),
                   "reasoning_tokens": (usage.get("output_tokens_details") or {}).get("reasoning_tokens", 0)}
        for name, count in amounts.items():
            self.value[name] += count
        rates = RATES.get(self.value["model"])
        if rates:
            self.value["estimated_cost_usd"] += ((amounts["input_tokens"] - amounts["cached_input_tokens"]) * rates["input"] +
                amounts["cached_input_tokens"] * rates["cached_input"] + amounts["output_tokens"] * rates["output"]) / 1_000_000

    def finish(self, result):
        self.value.update(latency_ms=round((time.monotonic() - self.started) * 1000),
                          tool_names=result.get("tool_calls", self.value["tool_names"]), retry_count=result.pop("_retry_count", self.value["retry_count"]))
        if not self.value["model_calls"]:
            self.value["estimated_cost_usd"] = 0
        if self.value["estimated_cost_usd"] is not None:
            self.value["estimated_cost_usd"] = round(self.value["estimated_cost_usd"], 8)
        logging.getLogger("milkman.usage").warning(json.dumps(self.value, separators=(",", ":")))
        return dict(self.value)
