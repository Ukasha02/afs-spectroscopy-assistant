"""LLM critic: does each cited page support the claim IN THE SAME CONTEXT?

The deterministic verifier can tell that a number or quote is on the cited page, but not whether
the page talks about the same sample type, setting (lab / process / clinical) or application.
The critic sees only the sourced claims and the text of the pages they cite (not the full corpus).
Its findings become 'context' flags for the single revision pass.
"""

import json
from typing import Literal

from pydantic import BaseModel

from afs_assistant.kb.load import resolve_ref
from afs_assistant.llm import call_llm
from afs_assistant.schema import Assessment, Flag
from afs_assistant.verify import _claim_text, _iter_claims

CRITIC_SYSTEM = """You are a strict reviewer of a spectroscopy assessment for Art Fiber Systems.
For each claim you get the claim text and the text of the pages it cites. Report a problem ONLY if:
- different_context: the page supports a similar statement but for another sample type, setting (lab vs in-line \
process vs clinical), or application, and the claim transfers it without saying so;
- not_supported: the cited pages do not say what the claim says;
- overstated: the claim is more certain than the page (e.g. 'will work', 'proven', 'ensures' where the page shows \
an example or a possibility).
Do not report style issues, missing extra information, or claims that are correct. Be precise: quote the part of \
the claim that is wrong. If everything is fine, return an empty list."""


class CriticIssue(BaseModel):
    claim_id: str
    problem: Literal["different_context", "not_supported", "overstated"]
    explanation: str
    fix: str


class CriticOutput(BaseModel):
    issues: list[CriticIssue]


def _claims_with_pages(assessment: Assessment) -> tuple[list[dict], dict[str, str]]:
    claims, pages = [], {}
    for path, claim in _iter_claims(assessment.model_dump()):
        if claim["basis"] != "sourced" or not claim["citations"]:
            continue
        refs = []
        for c in claim["citations"]:
            chunks = resolve_ref(c["ref"])
            for ch in chunks:
                pages.setdefault(ch.cite if ch.source != "TABLE" else ch.id, ch.text[:4000])
                refs.append(ch.cite if ch.source != "TABLE" else ch.id)
        if refs:
            claims.append({"claim_id": path, "claim": _claim_text(claim), "cited_pages": sorted(set(refs))})
    return claims, pages


def critique(assessment: Assessment) -> tuple[list[Flag], dict | None]:
    claims, pages = _claims_with_pages(assessment)
    if not claims:
        return [], None
    user = (
        "Pages:\n" + "\n\n".join(f'<page id="{pid}">\n{text}\n</page>' for pid, text in pages.items())
        + "\n\nClaims:\n" + json.dumps(claims, indent=1, ensure_ascii=False)
    )
    res = call_llm(CRITIC_SYSTEM, user, CriticOutput, thinking_level="low")
    out = CriticOutput.model_validate(res["output"])
    flags = [
        Flag(path=i.claim_id, kind="context", detail=f"{i.problem}: {i.explanation} Fix: {i.fix}")
        for i in out.issues
    ]
    return flags, {"stage": "critic", "claims_checked": len(claims), **res["meta"]}
