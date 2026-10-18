"""Report view as HTML (pure functions, no Streamlit calls, so it can be tested offline).

Follows the worked-answer order (render.report_sections). Claims carry a left border by basis
(docx §4: keep client facts, sourced claims, assumptions and proposals visibly separate).
Citation chips are native <details> elements: click to see the source title, page, scope and the
verified quote or a short page excerpt (max ~300 characters, never the full AFS text).
"""

from html import escape

from afs_assistant.kb.load import resolve_ref
from afs_assistant.kb.text import match_key
from afs_assistant.render import _INLINE_REF, STATUS_LABEL, fiber_sentence, is_rule_item, sources_used
from afs_assistant.schema import CitationRef
from afs_assistant.schema import CaseResult

BASIS_LABEL = {
    "client_fact": "Client fact", "sourced": "AFS source", "general_knowledge": "General knowledge",
    "assumption": "Assumption", "proposal": "Proposal",
}
SOURCE_LABEL = {
    "S01": "Multispectral laboratory overview & application cases", "S02": "AFS process-control slides",
    "S03": "Research paper · in-vitro proof of concept", "S04": "Research paper · lab study on model tissues",
    "S05": "AFS flyer · business context", "S06": "Laboratory website · business context",
    "TABLE": "Method comparison table (S01 p.6) · qualitative ratings", "DOCX": "Challenge reference document",
    "EXTERNAL": "External source",
}
EXCERPT_CHARS = 300
_ROLE_ORDER = {"primary": 0, "comparison": 1, "alternative": 2, "combination": 3, "not_recommended": 4}


def _source_id(ref: str) -> str:
    r = ref.strip().upper()
    if r.startswith("S01 TABLE"):
        return "TABLE"
    return r.split()[0] if r else "?"


class _Checks:
    """Verification status per (ref, quote) from the stored report."""

    def __init__(self, result: CaseResult):
        self.by_key = {(s.ref, s.quote or ""): s.status for s in result.verification.sources}

    def status(self, ref: str, quote: str | None) -> str:
        return self.by_key.get((ref, quote or ""), "")


def _excerpt(ref: str, quote: str | None) -> str:
    try:
        chunks = resolve_ref(ref)
    except FileNotFoundError:  # KB cache not available: show title/scope/quote only
        return ""
    if not chunks:
        return ""
    text = chunks[0].text
    for marker in ("[Figure/slide content, team transcription]", "[Page content, team transcription]"):
        if marker in text:  # image-only page: show our transcription, labelled as such
            text = "Team transcription: " + text.split(marker, 1)[1].strip()
            break
    if quote:
        pos = match_key(text).find(match_key(quote)[:40])
        if pos > 0:
            start = max(0, int(pos * len(text) / max(1, len(match_key(text)))) - 80)
            text = text[start:]
    text = " ".join(text.split())
    return text[:EXCERPT_CHARS] + ("…" if len(text) > EXCERPT_CHARS else "")


def _title(ref: str) -> str:
    try:
        chunks = resolve_ref(ref)
    except FileNotFoundError:
        chunks = []
    return chunks[0].title if chunks and chunks[0].title else ""


def chip(c, checks: _Checks) -> str:
    src = _source_id(c.ref)
    status = checks.status(c.ref, c.quote)
    badge = {"verified": "quote verified", "page_only": "page cited", "quote_not_found": "quote not found",
             "unknown_source": "unknown source"}.get(status, "")
    title = _title(c.ref) if src == "S02" else ""  # slide titles are real; S01 page titles come from our figure notes
    body = [f'<div class="pop-src">{escape(SOURCE_LABEL.get(src, src))}</div>']
    if title:
        body.append(f'<div class="pop-title">{escape(title)}</div>')
    if c.quote:
        body.append(f'<blockquote>{escape(c.quote)}</blockquote>')
    elif ex := _excerpt(c.ref, None):
        body.append(f'<div class="pop-excerpt">{escape(ex)}</div>')
    if c.url:
        body.append(f'<div class="pop-url">{escape(c.url)}</div>')
    if badge:
        body.append(f'<div class="pop-check {status}">{badge}</div>')
    return (f'<details class="chip chip-{src.lower()}"><summary>{escape(c.ref)}</summary>'
            f'<div class="pop">{"".join(body)}</div></details>')


def claim(text: str, basis: str, citations, checks: _Checks, tag: bool = True) -> str:
    text = _INLINE_REF.sub("", text).strip()
    chips = "".join(chip(c, checks) for c in citations)
    label = f'<span class="tag">{BASIS_LABEL.get(basis, basis)}</span>' if tag and basis in ("general_knowledge", "assumption") else ""
    return f'<div class="claim b-{basis}"><span class="ctext">{escape(text)}</span> {chips}{label}</div>'


def banner(r: CaseResult) -> str:
    a = r.assessment
    return (f'<div class="banner st-{a.decision_status}"><div class="banner-label">{STATUS_LABEL[a.decision_status]}</div>'
            f'<div class="banner-reason">{escape(a.status_reason)}</div></div>')


def verification_badge(r: CaseResult) -> str:
    v = r.verification
    verified = v.counts.get("citations_verified", 0)
    page = v.counts.get("citations_page_only", 0)
    numbers = sum(1 for f in v.flags if f.kind == "number")
    fixed = len(v.flags_before_revision)
    passed = sum(i.passed for i in r.rubric)
    return (f'<div class="vbadge">{verified + page} citations checked ({verified} quotes verified) · '
            f'{numbers} unsupported numbers · {len(v.flags)} open flags · {fixed} issues fixed by revision · '
            f'rubric {passed}/{len(r.rubric)}</div>')


def legend() -> str:
    items = "".join(f'<span class="lg b-{k}">{v}</span>' for k, v in BASIS_LABEL.items())
    return f'<div class="legend">{items}</div>'


def report_html(r: CaseResult) -> str:
    a, ck = r.assessment, _Checks(r)
    H = [banner(r), verification_badge(r), legend()]

    def section(title: str, inner: str) -> None:
        H.append(f'<section><h4>{title}</h4>{inner}</section>')

    section("Requirements stated", "<ul>" + "".join(f"<li>{escape(x)}</li>" for x in a.requirements_stated) + "</ul>")
    section("Key unknowns", "<ul>" + "".join(f"<li>{escape(x)}</li>" for x in a.key_unknowns) + "</ul>")
    section("Clarification questions", "<ol>" + "".join(f"<li>{escape(q.question)}</li>" for q in a.report_questions) + "</ol>")

    rec = []
    for pc in a.premise_checks:
        why = "".join(claim(s.text, s.basis, s.citations, ck) for s in pc.explanation)
        rec.append(f'<details class="premise v-{pc.verdict}"><summary class="premise-head"><span class="verdict">'
                   f'{pc.verdict.replace("_", " ")}</span> {escape(pc.client_claim)}</summary>{why}</details>')
    for x in sorted(a.recommendations, key=lambda x: (_ROLE_ORDER[x.role], x.simplicity_rank)):
        role = x.role.replace("_", " ")
        rec.append(f'<div class="rec"><div class="rec-head"><b>{escape(x.method)}</b> <span class="muted">({escape(x.geometry)})</span>'
                   f'<span class="pill">{role}</span><span class="pill">cost {x.cost_complexity}</span><span class="pill">confidence {x.confidence}</span></div>'
                   f'{claim(x.reason.text, x.reason.basis, x.reason.citations, ck)}{claim(x.caveat.text, x.caveat.basis, x.caveat.citations, ck)}</div>')
    section("Premise check & recommendation", "".join(rec) or '<p class="muted">No method recommended at this stage.</p>')

    mc = a.measurement_concept
    items = "".join(claim(i.text, i.basis, i.citations, ck) for i in mc.items if not is_rule_item(i))
    if sentence := fiber_sentence(a):  # plain sentence; the detailed rule check is in the side panel
        items += claim(sentence, "sourced", [CitationRef(ref="S02 p.6")], ck)
    confirm = f'<p class="muted">Needs AFS confirmation: {escape(", ".join(mc.needs_afs_confirmation))}</p>' if mc.needs_afs_confirmation else ""
    section("Measurement concept", items + confirm)

    ranges = "".join(
        f'<div class="claim b-sourced"><span class="ctext"><b>{escape(e.method)}</b>: {escape(e.nominal_range)}{"" if "nominal" in e.nominal_range.lower() else " (nominal)"}'
        f'{" · " + escape(e.note) if e.note else ""}</span> {chip(e.citation, ck)}</div>' for e in a.spectral_ranges
    )
    section("Spectral range", ranges + '<p class="muted">Usable range depends on the selected instrument and fiber; no optimal band without sample spectra.</p>')
    section("Risks and uncertainty", "".join(claim(k.text, k.basis, k.citations, ck) for k in a.risks))
    steps = "".join(f'<li>{claim(s.text, s.basis, s.citations, ck, tag=False)}</li>' for s in a.feasibility_plan.steps)
    section("First feasibility experiment", f"<ol class='plan'>{steps}</ol>")
    section("Decision basis", claim(a.decision_basis.text, a.decision_basis.basis, a.decision_basis.citations, ck))
    section("Sources", f'<p class="muted">{escape(", ".join(sources_used(a)))}</p>')
    return f'<div class="report">{"".join(H)}</div>'


def rule_panel(r: CaseResult) -> str:
    pre, a = r.pre_analysis, r.assessment
    decisions = {match_key(d.table_row): d for d in a.method_table_screening}
    rows = []
    for row in pre.get("table_shortlist", []):
        d = decisions.get(match_key(row["row"]))
        decision = (d.decision if d else "not screened").replace("_", " ")
        rows.append(f'<div class="rule-row dec-{decision.split()[0]}"><div class="rule-name">{escape(row["row"])}</div>'
                    f'<div class="rule-meta"><b>{escape(decision)}</b> · cost {row["cost"]} · selectivity {row["selectivity"]}</div></div>')
    findings = pre.get("fiber_findings_required_in_premise_check", [])
    fiber = next((i.text for i in a.measurement_concept.items if is_rule_item(i)), "")
    return (
        '<div class="rules"><div class="rule-title">S01 Table 1 shortlist (cheapest first)</div>'
        + "".join(rows)
        + (f'<p><b>Fiber check:</b> {escape(fiber)}</p>' if fiber else "")
        + "".join(f'<p class="warn">⚠ {escape(f)}</p>' for f in findings)
        + f'<p class="muted">Required risk categories: {", ".join(pre.get("required_risk_categories", []))}</p></div>'
    )


def footer(r: CaseResult) -> str:
    m = r.run_meta
    stages = " · ".join(f"{c.get('stage')}: {c.get('model')} ({c.get('effort', '')})" for c in m.calls)
    return (f'<div class="footer">{escape(stages)}<br>{m.duration_s} s · ${m.cost_usd:.3f} · pipeline {m.pipeline_version} · '
            f'prompt {m.prompt_hash} · commit {m.git_commit} · {m.timestamp[:19]}Z</div>')
