"""Text normalisation shared by the KB build and the citation verifier."""

import re
import unicodedata

_HYPHEN_BREAK = re.compile(r"(\w)-\s*\n\s*(\w)")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:)\]])")
_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """NFKC (fixes ligatures like 'ﬁ'), rejoin hyphenated line breaks, collapse whitespace."""
    text = unicodedata.normalize("NFKC", text)
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    text = _WS.sub(" ", text)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    return text.strip()


def match_key(text: str) -> str:
    """Aggressive form for fuzzy quote matching: lowercase, alphanumerics only, single spaces."""
    text = normalize(text).lower()
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)  # keep only decimal points
    text = re.sub(r"[^a-z0-9µ%.]+", " ", text)
    return _WS.sub(" ", text).strip()
