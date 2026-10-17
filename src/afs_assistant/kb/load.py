"""Load the KB cache and resolve citation references like 'S01 p.17-18' to chunks."""

import json
import re
from dataclasses import dataclass
from functools import lru_cache

import yaml

from afs_assistant import config


@dataclass(frozen=True)
class KBChunk:
    id: str
    cite: str
    source: str
    page: int | None
    kind: str
    title: str
    text: str
    in_corpus: bool


@lru_cache(maxsize=1)
def load_chunks() -> tuple[KBChunk, ...]:
    if not config.CHUNKS_PATH.exists():
        raise FileNotFoundError(f"{config.CHUNKS_PATH} not found. Run `make kb` first.")
    with config.CHUNKS_PATH.open(encoding="utf-8") as f:
        return tuple(KBChunk(**json.loads(line)) for line in f if line.strip())


@lru_cache(maxsize=1)
def load_facts() -> dict:
    return yaml.safe_load(config.FACTS_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_cases() -> dict[str, dict]:
    raw = json.loads((config.KB_CACHE_DIR / "cases.json").read_text(encoding="utf-8"))
    return {**raw["D"], **raw["H"]}


# --- reference parsing ----------------------------------------------------------------------

_SOURCE = re.compile(r"\b(S0[1-6]|DOCX|TABLE)\b")
_TABLE1 = re.compile(r"S01\s+Table\s*1", re.I)
_PAGES = re.compile(r"p\.?\s*(\d+)(?:\s*[-–]\s*(\d+))?")
_DOCX_SEC = re.compile(r"(?:§|section\s*)(\d)(?:\s*(D0\d))?", re.I)


def split_refs(text: str) -> list[str]:
    """'S01 p.10; DOCX §5' -> ['S01 p.10', 'DOCX §5']. Commas continue the previous source."""
    return [part.strip() for part in re.split(r";", text) if part.strip()]


def resolve_ref(ref: str) -> list[KBChunk]:
    """Map one citation reference to the chunks it covers. Empty list = unknown reference."""
    chunks = load_chunks()
    if _TABLE1.search(ref) or ref.strip().upper().startswith("TABLE"):
        return [c for c in chunks if c.source == "TABLE" or c.id == "S01:p6"]
    src = _SOURCE.search(ref)
    if not src:
        return []
    source = src.group(1)
    if source == "DOCX":
        sec = _DOCX_SEC.search(ref)
        if not sec:
            return []
        key = f"DOCX:§{sec.group(1)}" + (f"/{sec.group(2)}" if sec.group(2) else "")
        hits = [c for c in chunks if c.id == key]
        # 'DOCX §2' without a case also covers its worked examples.
        return hits + [c for c in chunks if not sec.group(2) and c.id.startswith(key + "/")]
    if source == "S06":
        return [c for c in chunks if c.source == "S06"]
    pages: set[int] = set()
    for start, end in _PAGES.findall(ref[src.end():]):
        lo = int(start)
        hi = int(end) if end else lo
        pages.update(range(lo, hi + 1))
    if not pages:  # whole document, e.g. 'S04'
        return [c for c in chunks if c.source == source]
    return [c for c in chunks if c.source == source and c.page in pages]


# --- prompt rendering -----------------------------------------------------------------------


def render_corpus() -> str:
    """All evidence chunks as tagged blocks. Stable order and content, so it can be prompt-cached."""
    scopes = load_facts().get("sources", {})
    parts = []
    for c in load_chunks():
        if not c.in_corpus:
            continue
        title = f' title="{c.title}"' if c.title else ""
        scope = scopes.get(c.source, {}).get("evidence")
        scope_attr = f' scope="{scope}"' if scope else ""
        parts.append(f'<source cite="{c.cite}"{title}{scope_attr}>\n{c.text}\n</source>')
    return "\n\n".join(parts)
