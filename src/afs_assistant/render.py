"""Markdown report in the worked-answer layout (docx §2/§3): 11 sections, inline citations, short.

The body (what an expert reads) is word-counted by the rubric. The footer with verification and
run metadata is extra; the full labelled data stays in outputs/<case>.json.
"""

import re

from afs_assistant.schema import Assessment, CaseResult

STATUS_LABEL = {
    "provisional_assessment": "Provisional feasibility assessment",
    "insufficient_information": "Insufficient information",
    "premise_not_supported": "Premise not supported / concept not approved",
    "outside_supported_scope": "Outside the supported scope",
}
_MARK = {"general_knowledge": " *(general knowledge)*", "assumption": " *(assumption)*"}
_ROLE_ORDER = {"primary": 0, "comparison": 1, "alternative": 2, "combination": 3, "not_recommended": 4}
RANGE_CAVEAT = "Specify only the usable range of the selected instrument and fiber; do not pick an optimal band without sample spectra."


def _cite(claim) -> str:
    """Inline citation + label for anything that is not a client fact, sourced claim or proposal."""
    refs = "; ".join(c.ref + (f" {c.url}" if c.url else "") for c in claim.citations)
    return (f" [{refs}]" if refs else "") + _MARK.get(claim.basis, "")


_INLINE_REF = re.compile(r"\s*\[(?:S0\d|DOCX|TABLE|EXTERNAL)[^\]]*\]")


def _text(claim) -> str:
    """Claim text with its citations appended once (refs the model wrote into the text are removed)."""
    text = _INLINE_REF.sub("", claim.text).strip()
    if claim.citations and text.endswith("."):
        text = text[:-1]
    return f"{text}{_cite(claim)}" + ("." if claim.citations else "")


def _join(items: list[str], sep: str = "; ") -> str:
    return sep.join(i.strip().rstrip(".;,") for i in items if i.strip())


def sources_used(a: Assessment) -> list[str]:
    refs = set(re.findall(r"'ref': '([^']+)'", str(a.model_dump())))
    return sorted(refs, key=lambda r: (r.startswith(("DOCX", "EXTERNAL")), r))


def report_body(a: Assessment, case_id: str) -> str:
    L = [f"# {case_id} · First technical assessment", ""]
    L += [f"**Decision status.** {STATUS_LABEL[a.decision_status]}. {a.status_reason}", ""]
    L += [f"**Requirements stated.** {_join(a.requirements_stated)}.", ""]
    L += [f"**Key unknowns.** {_join(a.key_unknowns)}.", ""]

    L += ["### Clarification questions", ""]
    L += [f"{i}. {q.question}" for i, q in enumerate(a.report_questions, 1)] + [""]

    L += ["### Recommendation", ""]
    for pc in a.premise_checks:
        if pc.verdict != "supported":
            why = " ".join(_text(s) for s in pc.explanation)
            L.append(f"- **Premise: {pc.client_claim}** — {pc.verdict.replace('_', ' ')}. {why}")
    for rec in sorted(a.recommendations, key=lambda r: (_ROLE_ORDER[r.role], r.simplicity_rank)):
        prefix = "Not recommended: " if rec.role == "not_recommended" else ""
        L.append(f"- **{prefix}{rec.method} ({rec.geometry}).** {_text(rec.reason)} {_text(rec.caveat)}")
    L.append("")

    mc = a.measurement_concept
    concept = " ".join(_text(i) for i in mc.items)
    confirm = f" Needs AFS confirmation: {_join(mc.needs_afs_confirmation, ', ')}." if mc.needs_afs_confirmation else ""
    L += [f"**Measurement concept.** {concept}{confirm}", ""]

    ranges = "; ".join(
        f"{e.method}: {e.nominal_range} nominal [{e.citation.ref}]" + (f" ({e.note.strip().rstrip('.')})" if e.note else "") for e in a.spectral_ranges
    )
    L += [f"**Spectral range.** {ranges + '. ' if ranges else ''}{RANGE_CAVEAT}", ""]

    L += ["### Risks and uncertainty", ""] + [f"- {_text(r)}" for r in a.risks] + [""]
    L += ["### First feasibility experiment", ""]
    L += [f"{i}. {_text(s)}" for i, s in enumerate(a.feasibility_plan.steps, 1)] + [""]
    L += [f"**Decision basis.** {_text(a.decision_basis)}", ""]
    L += [f"**Sources.** {', '.join(sources_used(a))}.", ""]
    return "\n".join(L)


def word_count(md: str) -> int:
    return len(re.findall(r"[A-Za-z0-9µ][\w\-–/.%µ]*", re.sub(r"[#*`>|]", " ", md)))


def to_markdown(r: CaseResult) -> str:
    body = report_body(r.assessment, r.case_id)
    v, m = r.verification, r.run_meta
    checked = sum(n for k, n in v.counts.items() if k.startswith("citations_"))
    passed = sum(i.passed for i in r.rubric)
    footer = [
        "---",
        f"<sub>Verification: {checked} citations checked, {len(v.flags)} open flags"
        + (f" ({len(v.flags_before_revision)} found before the revision pass)" if v.revised else "")
        + f" · rubric {passed}/{len(r.rubric)} · {word_count(body)} words · full labelled data in `{r.case_id}.json`</sub>",
    ]
    if v.flags:
        footer += ["", "| Open flag | Check | Detail |", "|---|---|---|"] + [f"| `{f.path}` | {f.kind} | {f.detail} |" for f in v.flags]
    failed = [i for i in r.rubric if not i.passed]
    if failed:
        footer += ["", "Rubric not met: " + "; ".join(f"{i.check} ({i.detail})" for i in failed)]
    models = ", ".join(sorted({f"{c.get('model')} ({c.get('thinking_level')})" for c in m.calls}))
    footer += ["", f"<sub>afs-assistant {m.pipeline_version} · {models} · prompt {m.prompt_hash} · commit {m.git_commit} · {m.timestamp} · {m.duration_s} s</sub>", ""]
    return body + "\n".join(footer)
