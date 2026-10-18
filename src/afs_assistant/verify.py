"""Deterministic verifier (PRD §5 step 5): the 'no hallucination' self-check. No LLM involved.

quote     every citation resolves to a KB page; a given quote must fuzzy-match that page's text
number    every number must trace to the enquiry / client answers, or (for a cited claim) to the
          pages that claim cites. Unit conversions nm <-> um <-> cm-1 are accepted. Assumptions,
          unknowns and the questionnaire carry no citations, so their numbers must come from the
          client: missing numbers become questions or lab-screening items, never estimates (A8.2).
sourced   every 'sourced' claim keeps at least one valid citation
basis     a recommendation must not rest on general knowledge alone (A8.1)
scope     business-context sources never back technical claims; 'supported' premise verdicts need
          a source outside the limited-scope ones (S03 in-vitro, S04 model tissue, S05/S06)
table     every shortlisted S01 Table 1 row is screened
questions 5-10 questions, ordered by topic (A8.3)
"""

import re
from collections import Counter

from rapidfuzz import fuzz

from afs_assistant.kb.load import load_facts, resolve_ref
from afs_assistant.kb.text import match_key
from afs_assistant.schema import QUESTION_TOPICS, Assessment, Flag, Question, SourceCheck, Verification

QUOTE_MATCH_THRESHOLD = 85
_LIMITED_SCOPE = {"S03", "S04", "S05", "S06"}
_LAB_STUDIES = {"S03", "S04"}
_UNIT = r"(?:%|°\s*C|nm|µm|um|mm|cm\s*-\s*1|cm⁻¹|cm|m|meters?|metres?|km|s|sec|seconds?|min|minutes?|h|hours?|ppm|ppb|bar|psi|w/w|mg|g|kg|mM|µM|uM|nM|Hz|kHz|K|V|A|W)"
_NUM = r"\d+(?:[.,]\d+)?"
_TOKEN = re.compile(
    rf"(?<![A-Za-z0-9./])(?P<a>{_NUM})(?:\s*(?:-|–|to)\s*(?P<b>{_NUM}))?\s*(?P<unit>{_UNIT})?(?![A-Za-z0-9])"
)


def _numbers(text: str) -> list[tuple[str, str]]:
    """(number, unit) pairs worth checking. A bare small integer without unit or range
    ('2 methods', 'Path 1') is skipped; everything with a unit, %, or a range is checked."""
    out = []
    for m in _TOKEN.finditer(text):
        unit = re.sub(r"\s+", "", m.group("unit") or "").replace("cm⁻¹", "cm-1")
        values = [m.group("a")] + ([m.group("b")] if m.group("b") else [])
        values = [v.replace(",", ".") for v in values]
        if not unit and not m.group("b") and "." not in values[0] and int(values[0]) <= 10:
            continue
        out += [(v, unit) for v in values]
    return out


def _alternatives(value: str, unit: str) -> set[str]:
    """Equivalent spellings across nm / um / cm-1, so '2.5-25 um' matches '4000-400 cm-1'."""
    alts = {value}
    v = float(value)
    if v == 0:
        return alts
    if unit in ("µm", "um"):
        alts |= {f"{v * 1000:g}", f"{10000 / v:g}"}
    elif unit == "nm":
        alts |= {f"{v / 1000:g}", f"{1e7 / v:g}"}
    elif unit == "cm-1":
        alts |= {f"{10000 / v:g}", f"{1e7 / v:g}"}
    return alts


def _number_known(value: str, unit: str, haystack_key: str) -> bool:
    return any(
        re.search(r"(?<![\d.])" + re.escape(alt) + r"(?![\d])", haystack_key) for alt in _alternatives(value, unit)
    )


def _is_claim(node) -> bool:
    """Any labelled claim: Statement, RecNote, PlanStep, Risk (all carry basis + citations)."""
    return isinstance(node, dict) and {"basis", "citations"} <= node.keys()


def _claim_text(node: dict) -> str:
    return " ".join(str(node[k]) for k in ("text", "risk", "mitigation") if node.get(k))


def _iter_claims(node, path=""):
    if isinstance(node, dict):
        if _is_claim(node):
            yield path, node
        for k, v in node.items():
            yield from _iter_claims(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _iter_claims(v, f"{path}[{i}]")


def _iter_plain_strings(node, path=""):
    """Strings outside labelled claims (summary, reasons, assumptions, labels)."""
    if isinstance(node, dict):
        if _is_claim(node):
            return
        for k, v in node.items():
            yield from _iter_plain_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _iter_plain_strings(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


def _check_citation(path: str, c: dict) -> tuple[SourceCheck, str]:
    """Return the check and the page text it may vouch for ('' if not valid)."""
    ref, quote = c["ref"], c.get("quote")
    if ref.strip().upper().startswith("EXTERNAL") or c.get("url"):
        status = "verified" if quote and c.get("url") else "external_missing_quote"
        return SourceCheck(path=path, ref=ref, quote=quote, status=status), (quote or "")
    chunks = resolve_ref(ref)
    if not chunks:
        return SourceCheck(path=path, ref=ref, quote=quote, status="unknown_source"), ""
    page_text = " ".join(ch.text for ch in chunks)
    if not quote:
        return SourceCheck(path=path, ref=ref, quote=None, status="page_only"), page_text
    score = max(fuzz.partial_ratio(match_key(quote), match_key(ch.text)) for ch in chunks)
    status = "verified" if score >= QUOTE_MATCH_THRESHOLD else "quote_not_found"
    return SourceCheck(path=path, ref=ref, quote=quote, status=status, score=round(score, 1)), (
        page_text if status == "verified" else ""
    )


def _source_id(ref: str) -> str:
    if re.match(r"\s*S01\s+Table", ref, re.I):
        return "TABLE"
    m = re.match(r"\s*(S0\d|DOCX|TABLE|EXTERNAL)", ref, re.I)
    return m.group(1).upper() if m else "?"


def _client_key(enquiry: str, questions: list[Question]) -> str:
    return match_key(" ".join([enquiry] + [q.answer for q in questions if q.answer]))


def verify_questions(questions: list[Question], enquiry: str) -> list[Flag]:
    """Questionnaire: count, topic order, and no numbers the client did not give (A8.2, A8.3)."""
    flags = []
    if not 5 <= len(questions) <= 10:
        flags.append(Flag(path="clarification_questions", kind="questionnaire", detail=f"{len(questions)} questions (expected 5-10)"))
    order = [QUESTION_TOPICS.index(q.topic) for q in questions]
    if order != sorted(order):
        flags.append(Flag(path="clarification_questions", kind="questionnaire", detail=f"not in topic order: {[q.topic for q in questions]}"))
    client = _client_key(enquiry, questions)
    for i, q in enumerate(questions):
        for field in ("question", "why", "assumption_if_unanswered"):
            for value, unit in _numbers(getattr(q, field)):
                if not _number_known(value, unit, client):
                    flags.append(Flag(path=f"clarification_questions[{i}].{field}", kind="number",
                                      detail=f"'{value}{unit}' is not from the client; ask for it or make it a lab-screening item: {getattr(q, field)[:120]}"))
    return flags


def verify(assessment: Assessment, enquiry: str, questions: list[Question], table_shortlist: list[dict],
           process_context: str = "unknown") -> Verification:
    data = assessment.model_dump()
    client = _client_key(enquiry, questions)
    facts_sources = load_facts()["sources"]
    sources: list[SourceCheck] = []
    flags: list[Flag] = []
    cited_page_text: list[str] = []

    for path, claim in _iter_claims(data):
        valid_text = []
        for i, c in enumerate(claim["citations"]):
            check, text = _check_citation(f"{path}.citations[{i}]", c)
            sources.append(check)
            if check.status in ("quote_not_found", "unknown_source", "external_missing_quote"):
                flags.append(Flag(path=check.path, kind="quote", detail=f"{c['ref']}: {check.status} (score {check.score})"))
            if text:
                valid_text.append(text)
            if re.match(r"\s*DOCX\s*§\s*2", c["ref"]):
                flags.append(Flag(path=check.path, kind="scope", detail=f"{c['ref']} is a worked answer to another enquiry, not evidence; cite the AFS page instead"))
            meta = facts_sources.get(_source_id(c["ref"]), {})
            if claim["basis"] == "sourced" and meta and not meta.get("technical", True):
                flags.append(Flag(path=path, kind="scope", detail=f"{c['ref']} is business context only; it cannot back a technical claim"))
        if claim["basis"] == "sourced" and not valid_text:
            flags.append(Flag(path=path, kind="unsupported_sourced_claim", detail=f"labelled 'sourced' but no valid citation: {_claim_text(claim)[:120]}"))
        cited_page_text += valid_text
        allowed = client + " " + match_key(" ".join(valid_text))
        for value, unit in _numbers(_claim_text(claim)):
            if not _number_known(value, unit, allowed):
                flags.append(Flag(path=path, kind="number", detail=f"'{value}{unit}' not in the enquiry or the pages this claim cites: {_claim_text(claim)[:120]}"))

    # Free text. Assumptions and unknowns have no citations: their numbers must come from the client.
    all_cited = client + " " + match_key(" ".join(cited_page_text))
    for path, s in _iter_plain_strings(data):
        if path.endswith("table_row"):  # copied from S01 Table 1 itself
            continue
        if path.startswith("spectral_ranges"):  # checked against their own citation below
            continue
        strict = path.startswith(("assumptions", "key_unknowns", "requirements_stated", "report_questions"))
        for value, unit in _numbers(s):
            if not _number_known(value, unit, client if strict else all_cited):
                where = "the enquiry (assumptions need client numbers)" if strict else "the enquiry or any cited page"
                flags.append(Flag(path=path, kind="number", detail=f"'{value}{unit}' not in {where}: {s[:120]}"))

    # A8.1: a recommendation needs AFS evidence, not general knowledge alone.
    for i, rec in enumerate(data["recommendations"]):
        if rec["role"] != "not_recommended" and rec["reason"]["basis"] != "sourced":
            flags.append(Flag(path=f"recommendations[{i}].reason", kind="basis", detail=f"'{rec['method']}': the reason must be sourced (an AFS application example); general knowledge may only support"))

    # Spectral ranges: the nominal range must be on the page it cites.
    for i, entry in enumerate(data["spectral_ranges"]):
        check, text = _check_citation(f"spectral_ranges[{i}].citation", entry["citation"])
        sources.append(check)
        if not text:
            flags.append(Flag(path=check.path, kind="quote", detail=f"{entry['citation']['ref']}: {check.status}"))
        for value, unit in _numbers(entry["nominal_range"]):
            if not _number_known(value, unit, client + " " + match_key(text)):
                flags.append(Flag(path=f"spectral_ranges[{i}]", kind="number", detail=f"'{value}{unit}' not on the cited page {entry['citation']['ref']}"))
        for value, unit in _numbers(entry.get("note") or ""):
            if not _number_known(value, unit, all_cited + " " + match_key(text)):
                flags.append(Flag(path=f"spectral_ranges[{i}].note", kind="number", detail=f"'{value}{unit}' not on any cited page"))

    for i, pc in enumerate(data["premise_checks"]):
        if pc["verdict"] != "supported":
            continue
        cited = {_source_id(c["ref"]) for st in pc["explanation"] for c in st["citations"]}
        # Lab studies (S03 in vitro, S04 model tissue) can support a premise only for a client who
        # stated a research-lab context; they never support process or clinical readiness.
        lab_ok = process_context == "research_lab" and cited and cited <= _LAB_STUDIES
        if not cited or (cited <= _LIMITED_SCOPE and not lab_ok):
            flags.append(Flag(path=f"premise_checks[{i}]", kind="scope", detail=f"verdict 'supported' rests only on limited-scope sources {sorted(cited) or 'none'} for a {process_context} context; use 'plausible_to_be_tested'"))

    screened = {match_key(d["table_row"]) for d in data["method_table_screening"]}
    for row in table_shortlist:
        if match_key(row["row"]) not in screened:
            flags.append(Flag(path="method_table_screening", kind="table_coverage", detail=f"shortlisted row not screened: {row['row']}"))

    flags += verify_questions(questions, enquiry)
    counts = Counter(f"citations_{s.status}" for s in sources) + Counter(f"flag_{f.kind}" for f in flags)
    return Verification(sources=sources, flags=flags, counts=dict(counts))
