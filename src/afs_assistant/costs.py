"""Cost tracking and budget guard.

Every LLM call is priced from its usage and appended to outputs/spend.json (committed), with the
phase (SPEND_PHASE in .env or --phase on the CLI), case, stage and model. Before a call, a
worst-case estimate is checked against BUDGET_LIMIT_USD: a call that could push the ledger total
over the limit is refused.

Prices in USD per million tokens (team budget sheet, Sat 17 Oct). Thinking tokens are billed as
output. Haiku 5.5 prices are for prompts up to 100k tokens; above that the long-prompt price applies.
"""

import json
import os
from collections import defaultdict
from datetime import datetime, timezone

from afs_assistant import config

LEDGER_PATH = config.OUTPUTS_DIR / "spend.json"
BUDGET_LIMIT_USD = float(os.getenv("BUDGET_LIMIT_USD", "55"))

PRICES = {  # input, output, cache read, cache write (5-minute TTL)
    "claude-haiku-5-5": {"in": 0.10, "out": 0.50, "cache_read": 0.01, "cache_write": 0.125},
    "claude-sonnet-5-5": {"in": 2.00, "out": 10.00, "cache_read": 0.10, "cache_write": 2.50},
    "claude-opus-5-5": {"in": 4.00, "out": 20.00, "cache_read": 0.20, "cache_write": 5.00},
}
HAIKU_LONG_PROMPT = {"in": 0.50, "out": 2.50, "cache_read": 0.05, "cache_write": 0.625}  # prompts > 100k tokens


class BudgetExceeded(RuntimeError):
    pass


def _prices(model: str, prompt_tokens: int) -> dict:
    if model not in PRICES:
        return {"in": 0.0, "out": 0.0, "cache_read": 0.0, "cache_write": 0.0}  # e.g. Gemini free tier
    if model == "claude-haiku-5-5" and prompt_tokens > 100_000:
        return HAIKU_LONG_PROMPT
    return PRICES[model]


def call_cost(model: str, usage: dict) -> float:
    uncached = usage.get("input_tokens", 0)
    read = usage.get("cache_read_input_tokens", 0)
    write = usage.get("cache_creation_input_tokens", 0)
    out = usage.get("output_tokens", 0)
    p = _prices(model, uncached + read + write)
    return (uncached * p["in"] + read * p["cache_read"] + write * p["cache_write"] + out * p["out"]) / 1e6


def worst_case_cost(model: str, prompt_chars: int, max_tokens: int) -> float:
    """Upper bound before the call: whole prompt written to cache (the most expensive input) + max output."""
    prompt_tokens = int(prompt_chars / 3)  # conservative: ~3 characters per token
    p = _prices(model, prompt_tokens)
    return (prompt_tokens * max(p["in"], p["cache_write"]) + max_tokens * p["out"]) / 1e6


def load_ledger() -> list[dict]:
    if not LEDGER_PATH.exists():
        return []
    return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))


def total_spent() -> float:
    return sum(e["cost_usd"] for e in load_ledger())


def check_budget(model: str, prompt_chars: int, max_tokens: int) -> None:
    estimate = worst_case_cost(model, prompt_chars, max_tokens)
    spent = total_spent()
    if spent + estimate > BUDGET_LIMIT_USD:
        raise BudgetExceeded(
            f"Refused: ${spent:.2f} spent + worst case ${estimate:.2f} for this call would exceed BUDGET_LIMIT_USD=${BUDGET_LIMIT_USD:.2f}"
        )


def record(model: str, provider: str, stage: str, usage: dict, duration_s: float) -> float:
    cost = round(call_cost(model, usage), 6)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "phase": os.getenv("SPEND_PHASE", "dev"),
        "case": os.getenv("SPEND_CASE", ""),
        "stage": stage,
        "provider": provider,
        "model": model,
        "input_tokens": usage.get("input_tokens", 0),
        "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
        "cache_write_tokens": usage.get("cache_creation_input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "duration_s": duration_s,
        "cost_usd": cost,
    }
    ledger = load_ledger()
    ledger.append(entry)
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(ledger, indent=1) + "\n", encoding="utf-8")
    return cost


def summary() -> str:
    ledger = load_ledger()
    by_phase, by_model = defaultdict(float), defaultdict(float)
    for e in ledger:
        by_phase[e["phase"]] += e["cost_usd"]
        by_model[e["model"]] += e["cost_usd"]
    total = sum(by_phase.values())
    lines = [f"Spent ${total:.4f} of ${BUDGET_LIMIT_USD:.2f} limit · remaining ${BUDGET_LIMIT_USD - total:.4f} · {len(ledger)} calls"]
    lines += [f"  phase {k}: ${v:.4f}" for k, v in sorted(by_phase.items())]
    lines += [f"  model {k}: ${v:.4f}" for k, v in sorted(by_model.items())]
    return "\n".join(lines)
