"""
LLM wrapper for the AFS Spectroscopy Assistant.

- Gemini via the google-genai SDK (generate_content API)
- No web search: AFS materials are passed in the prompt as the knowledge base
- Structured JSON output validated with Pydantic
- Model + settings read from .env so you can swap models without code changes

Setup:
    pip install -r requirements.txt

.env:
    GEMINI_API_KEY=...
    LLM_MODEL=gemini-3.8-flash
    LLM_THINKING_LEVEL=medium     # minimal | low | medium | high  (try high for final runs)
    LLM_MAX_OUTPUT_TOKENS=16384
    LLM_SEED=42

Run the smoke test (needs `make kb` and a key):
    python -m afs_assistant.llm
"""

import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from google import genai
from google.genai import types
from pydantic import BaseModel

from afs_assistant import config  # noqa: F401  (loads .env from the repo root)
from afs_assistant.schema import Assessment

PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
MODEL = os.getenv("LLM_MODEL", "gemini-3.8-flash")
THINKING_LEVEL = os.getenv("LLM_THINKING_LEVEL", "medium")
MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "16384"))
SEED = int(os.getenv("LLM_SEED", "42"))


@lru_cache(maxsize=1)
def _client() -> genai.Client:
    # Created on first use, so the module can be imported (tests, UI) without a key.
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def call_llm(system_prompt: str, user_prompt: str, schema: type[BaseModel] = Assessment) -> dict:
    """Call the model and return parsed, schema-validated output plus run metadata.

    Single entry point for every pipeline stage. Other providers (OpenRouter, Claude) are
    added behind LLM_PROVIDER here, so callers never change.
    """
    if PROVIDER != "gemini":
        raise NotImplementedError(f"LLM_PROVIDER={PROVIDER!r} is not implemented yet (only 'gemini').")

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        # No tools: no google_search. The knowledge base goes into the prompt.
        response_mime_type="application/json",
        response_schema=schema,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel(THINKING_LEVEL.upper())),
        seed=SEED,
        # Temperature left at the default: Google recommends keeping the
        # default (1.0) for Gemini 3 models, since lowering it can cause looping.
    )

    started = datetime.now(timezone.utc)
    response = _client().models.generate_content(
        model=MODEL,
        contents=user_prompt,
        config=config,
    )

    parsed = response.parsed  # Pydantic object when response_schema is set
    if parsed is None:  # fall back to raw text if parsing failed
        parsed = schema.model_validate_json(response.text)

    return {
        "output": parsed.model_dump(),
        "meta": {  # logged for reproducibility
            "provider": PROVIDER,
            "model": MODEL,
            "thinking_level": THINKING_LEVEL,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "seed": SEED,
            "timestamp": started.isoformat(),
            "duration_s": round((datetime.now(timezone.utc) - started).total_seconds(), 1),
            "finish_reason": str(response.candidates[0].finish_reason) if response.candidates else None,
            "usage": response.usage_metadata.model_dump(exclude_none=True) if response.usage_metadata else None,
        },
    }


if __name__ == "__main__":
    from afs_assistant.kb.load import render_corpus

    SYSTEM = (
        "You are an assistant that helps an Art Fiber Systems (AFS) expert make a first technical "
        "assessment of a customer's in-line spectroscopy problem. Use ONLY the supplied AFS materials "
        "as your source. Never invent figures, specs, results or customer facts. Check the customer's "
        "premise. If information is insufficient, say so.\n\n"
        "=== AFS KNOWLEDGE BASE ===\n"
        + render_corpus()
    )
    ENQUIRY = (
        "We need to monitor moisture and hydrocarbon contamination in soil. Measurements should be "
        "remote and the environment may be humid and dirty."
    )
    result = call_llm(SYSTEM, ENQUIRY)
    print(json.dumps(result, indent=2, ensure_ascii=False))
