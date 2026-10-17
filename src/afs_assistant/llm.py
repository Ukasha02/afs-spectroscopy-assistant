"""
LLM gateway for the AFS Spectroscopy Assistant: call_llm() is the single entry point.

Providers (LLM_PROVIDER):
  anthropic  Claude via the Anthropic SDK (default). Structured output with messages.parse
             (Pydantic schema), adaptive thinking with per-stage effort, prompt caching of the
             static system block (AFS corpus + facts + rules + exemplars).
  gemini     fallback: Gemini via google-genai (free tier is limited to 20 requests/day).

Per-stage settings (.env): MODEL_INTAKE / MODEL_ASSESS / MODEL_CRITIC / MODEL_REVISE and
EFFORT_<STAGE> (low | medium | high). Every call is priced and logged in outputs/spend.json, and
refused if it could exceed BUDGET_LIMIT_USD (see costs.py). No web or search tools: the AFS
materials in the prompt are the knowledge base.

Smoke test (needs `make kb` and a key):  python -m afs_assistant.llm
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from functools import lru_cache

from pydantic import BaseModel

from afs_assistant import config  # noqa: F401  (loads .env from the repo root)
from afs_assistant import costs
from afs_assistant.schema import Assessment

PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "16000"))
_DEFAULT_EFFORT = {"intake": "low", "revise_intake": "low", "critic": "low", "assess": "medium", "revise": "medium"}

# Gemini fallback settings
GEMINI_MODEL = os.getenv("LLM_MODEL", "gemini-3.8-flash")
SEED = int(os.getenv("LLM_SEED", "42"))
GEMINI_RETRY_DELAYS_S = (20, 60, 120)  # 5xx only; quota errors (429) are not retried


def _env_key(stage: str) -> str:
    return {"revise_intake": "INTAKE"}.get(stage, stage.upper())


def stage_model(stage: str) -> str:
    return os.getenv(f"MODEL_{_env_key(stage)}", "claude-haiku-5-5")


def stage_effort(stage: str) -> str:
    return os.getenv(f"EFFORT_{_env_key(stage)}", _DEFAULT_EFFORT.get(stage, "medium"))


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _anthropic():
    import anthropic

    # The SDK retries 408/409/429/5xx/529 with exponential backoff and honours retry-after.
    return anthropic.Anthropic(max_retries=6)


def _call_anthropic(system: list[str], user_prompt: str, schema: type[BaseModel], stage: str) -> tuple[BaseModel, dict]:
    model, effort = stage_model(stage), stage_effort(stage)
    costs.check_budget(model, sum(map(len, system)) + len(user_prompt), MAX_OUTPUT_TOKENS)
    blocks = [{"type": "text", "text": system[0], "cache_control": {"type": "ephemeral"}}]
    blocks += [{"type": "text", "text": t} for t in system[1:]]
    started = time.monotonic()
    response = _anthropic().messages.parse(
        model=model,
        max_tokens=MAX_OUTPUT_TOKENS,
        system=blocks,
        messages=[{"role": "user", "content": user_prompt}],
        output_format=schema,
        output_config={"effort": effort},  # adaptive thinking is on by default; effort sets its depth
    )
    duration = round(time.monotonic() - started, 1)
    usage = {
        k: getattr(response.usage, k, 0) or 0
        for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    }
    cost = costs.record(model, "anthropic", stage, usage, duration)
    if response.stop_reason == "refusal":
        raise RuntimeError(f"{model} declined the request ({getattr(response.stop_details, 'category', None)})")
    if response.stop_reason == "max_tokens":
        raise RuntimeError(f"{model} hit max_tokens={MAX_OUTPUT_TOKENS}; output truncated")
    if response.parsed_output is None:
        raise RuntimeError(f"{model} returned no parsable output (stop_reason={response.stop_reason})")
    meta = {"provider": "anthropic", "model": model, "effort": effort, "thinking_level": effort, "duration_s": duration,
            "stop_reason": response.stop_reason, "usage": usage, "cost_usd": cost}
    return response.parsed_output, meta


# ---------------------------------------------------------------------------
# Gemini (fallback)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _gemini():
    from google import genai

    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def _call_gemini(system: list[str], user_prompt: str, schema: type[BaseModel], stage: str) -> tuple[BaseModel, dict]:
    from google.genai import errors, types

    level = stage_effort(stage)
    cfg = types.GenerateContentConfig(
        system_instruction="\n\n".join(system),
        response_mime_type="application/json",
        response_schema=schema,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel(level.upper())),
        seed=SEED,  # temperature left at the Gemini 3 default
    )
    started = time.monotonic()
    for attempt, delay in enumerate((*GEMINI_RETRY_DELAYS_S, None)):
        try:
            response = _gemini().models.generate_content(model=GEMINI_MODEL, contents=user_prompt, config=cfg)
            break
        except errors.ServerError as e:
            if delay is None:
                raise
            print(f"[llm] {e.code} from {GEMINI_MODEL}, retry {attempt + 1} in {delay}s", file=sys.stderr, flush=True)
            time.sleep(delay)
    duration = round(time.monotonic() - started, 1)
    parsed = response.parsed or schema.model_validate_json(response.text)
    um = response.usage_metadata
    usage = {"input_tokens": um.prompt_token_count or 0,
             "output_tokens": (um.candidates_token_count or 0) + (um.thoughts_token_count or 0)} if um else {}
    cost = costs.record(GEMINI_MODEL, "gemini", stage, usage, duration)
    meta = {"provider": "gemini", "model": GEMINI_MODEL, "effort": level, "thinking_level": level, "seed": SEED,
            "duration_s": duration, "stop_reason": str(response.candidates[0].finish_reason) if response.candidates else None,
            "usage": usage, "cost_usd": cost}
    return parsed, meta


# ---------------------------------------------------------------------------
# Single entry point
# ---------------------------------------------------------------------------

def call_llm(system: str | list[str], user_prompt: str, schema: type[BaseModel] = Assessment, stage: str = "assess") -> dict:
    """Call the configured provider; return schema-validated output plus run metadata.

    system: one string, or a list whose FIRST element is the static, cacheable block (AFS corpus,
    facts, rules, exemplars) followed by stage-specific instructions.
    """
    system = [system] if isinstance(system, str) else list(system)
    started = datetime.now(timezone.utc).isoformat()
    if PROVIDER == "anthropic":
        parsed, meta = _call_anthropic(system, user_prompt, schema, stage)
    elif PROVIDER == "gemini":
        parsed, meta = _call_gemini(system, user_prompt, schema, stage)
    else:
        raise NotImplementedError(f"LLM_PROVIDER={PROVIDER!r} (use 'anthropic' or 'gemini')")
    return {"output": parsed.model_dump(), "meta": {"stage": stage, "timestamp": started, "max_output_tokens": MAX_OUTPUT_TOKENS, **meta}}


if __name__ == "__main__":
    from afs_assistant import prompts
    from afs_assistant.schema import Intake

    enquiry = (
        "We need to monitor moisture and hydrocarbon contamination in soil. Measurements should be "
        "remote and the environment may be humid and dirty."
    )
    result = call_llm(prompts.intake_system(), prompts.intake_user(enquiry), Intake, stage="intake")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(costs.summary(), file=sys.stderr)
