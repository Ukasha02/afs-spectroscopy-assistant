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
RANGE_CAVEAT = "Usable range depends on the selected instrument and fiber; no optimal band without sample spectra."


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


_RULE_PREFIXES = ("Rule check", "No fiber link stated")
_FIBER_SHORT = {"UV_SILICA": "UV-Vis silica fiber", "VISNIR_SILICA": "Vis-NIR silica fiber", "CIR": "chalcogenide IR fiber",
                "PIR": "polycrystalline IR fiber", "HWG": "hollow glass waveguide", "INF3": "indium fluoride fiber",
                "ZRF4": "zirconium fluoride fiber"}
_METHOD_LABEL = {"MIR": "mid-IR", "NIR": "NIR", "RAMAN": "Raman", "FLUO": "fluorescence", "UVVIS": "UV/Vis"}


def is_rule_item(item) -> bool:
    """The deterministic fiber check appended by the pipeline (shown in detail in the side panel)."""
    return item.text.startswith(_RULE_PREFIXES)


def _fmt_range(lo_um: float, hi_um: float) -> str:
    """Fiber range as written on S02 p.6 (nm up to 6.5 um, um above)."""
    if hi_um <= 6.5:
        return f"{lo_um * 1000:g}–{hi_um * 1000:g} nm"
    return f"{lo_um * 1000:g} nm–{hi_um:g} µm"


def fiber_sentence(a: Assessment) -> str | None:
    """One plain sentence for the report, built from the rule result (render only).

    - client fiber stated: its S02 p.6 range and whether it can carry the method
    - no fiber stated, MIR recommended: MIR needs an IR fiber
    - no fiber stated, no MIR: silica covers UV/Vis and NIR
    """
    rule = next((i for i in a.measurement_concept.items if is_rule_item(i)), None)
    if rule is None:
        return None
    if rule.text.startswith("Rule check of the stated fiber"):
        from afs_assistant.kb.load import load_facts

        fibers = load_facts()["fibers"]
        for part in rule.text.split(":", 1)[1].split(";"):
            method, _, rest = part.strip().partition(":")
            for f in sorted(fibers, key=lambda f: -len(f["name"])):
                if f["name"] in rest:
                    rng = _fmt_range(*f["range_um"])
                    name = _FIBER_SHORT.get(f["id"], f["name"])
                    label = _METHOD_LABEL.get(method.strip(), method.strip())
                    if rest.split(f["name"], 1)[1].strip().startswith("none"):
                        return f"The stated {name} transmits {rng}, so it cannot carry {label}."
                    return f"The stated {name} transmits {rng}; its fit to the {label} range must be confirmed."
        return None
    if "MIR" in rule.text.split("Rule check", 1)[-1] and not rule.text.startswith("No fiber link stated;"):
        return "No link stated; MIR needs an IR fiber such as chalcogenide or polycrystalline, not silica."
    return "No link stated; silica fibers cover UV/Vis and NIR."


def sources_used(a: Assessment) -> list[str]:
    refs = set(re.findall(r"'ref': '([^']+)'", str(a.model_dump())))
    return sorted(refs, key=lambda r: (r.startswith(("DOCX", "EXTERNAL")), r))


# Word budgets per section (rubric): together about 430 words + title and sources.
SECTION_BUDGETS = {
    "Decision status": 18, "Requirements stated": 28, "Key unknowns": 22, "Clarification questions": 55,
    "Recommendation": 110, "Measurement concept": 45, "Spectral range": 30, "Risks and uncertainty": 48,
    "First feasibility experiment": 60, "Decision basis": 22,
}


def report_sections(a: Assessment) -> dict[str, str]:
    """The 11 report sections as Markdown, in output order (Sources last)."""
    S: dict[str, str] = {}
    S["Decision status"] = f"**Decision status.** {STATUS_LABEL[a.decision_status]}. {a.status_reason}"
    S["Requirements stated"] = f"**Requirements stated.** {_join(a.requirements_stated)}."
    S["Key unknowns"] = f"**Key unknowns.** {_join(a.key_unknowns)}."
    S["Clarification questions"] = "\n".join(["### Clarification questions", ""] + [f"{i}. {q.question}" for i, q in enumerate(a.report_questions, 1)])
    rec = ["### Recommendation", ""]
    for pc in a.premise_checks:
        if pc.verdict != "supported":
            refs = list(dict.fromkeys(c.ref for s in pc.explanation for c in s.citations))
            cites = f" [{'; '.join(refs)}]" if refs else ""
            rec.append(f"- **Premise {pc.verdict.replace('_', ' ')}:** {pc.client_claim.rstrip('.')}{cites}.")
    for r in sorted(a.recommendations, key=lambda r: (_ROLE_ORDER[r.role], r.simplicity_rank)):
        prefix = "Not recommended: " if r.role == "not_recommended" else ""
        rec.append(f"- **{prefix}{r.method} ({r.geometry}).** {_text(r.reason)} {_text(r.caveat)}")
    S["Recommendation"] = "\n".join(rec)
    mc = a.measurement_concept
    concept = " ".join(_text(i) for i in mc.items if not is_rule_item(i))
    if sentence := fiber_sentence(a):
        concept += f" {sentence[:-1]} [S02 p.6]."
    confirm = f" Needs AFS confirmation: {_join(mc.needs_afs_confirmation, ', ')}." if mc.needs_afs_confirmation else ""
    S["Measurement concept"] = f"**Measurement concept.** {concept.strip()}{confirm}"
    ranges = "; ".join(
        f"{e.method}: {e.nominal_range} nominal [{e.citation.ref}]" + (f" ({e.note.strip().rstrip('.')})" if e.note else "") for e in a.spectral_ranges
    )
    S["Spectral range"] = f"**Spectral range.** {ranges + '. ' if ranges else ''}{RANGE_CAVEAT}"
    S["Risks and uncertainty"] = "\n".join(["### Risks and uncertainty", ""] + [f"- {_text(r)}" for r in a.risks])
    S["First feasibility experiment"] = "\n".join(["### First feasibility experiment", ""] + [f"{i}. {_text(s)}" for i, s in enumerate(a.feasibility_plan.steps, 1)])
    S["Decision basis"] = f"**Decision basis.** {_text(a.decision_basis)}"
    S["Sources"] = f"**Sources.** {', '.join(sources_used(a))}."
    return S


def report_body(a: Assessment, case_id: str) -> str:
    return "\n\n".join([f"# {case_id} · First technical assessment"] + list(report_sections(a).values())) + "\n"


def section_overruns(a: Assessment) -> list[str]:
    out = []
    for name, md in report_sections(a).items():
        budget = SECTION_BUDGETS.get(name)
        words = word_count(re.sub(r"\[[^\]]*\]", "", md))  # citations do not count against the budget
        if budget and words > budget:
            out.append(f"{name} {words}/{budget}")
    return out


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
    models = ", ".join(f"{c.get('stage')}: {c.get('model')} ({c.get('effort', c.get('thinking_level'))})" for c in m.calls)
    footer += ["", f"<sub>afs-assistant {m.pipeline_version} · {models} · prompt {m.prompt_hash} · commit {m.git_commit} · {m.timestamp} · {m.duration_s} s · ${m.cost_usd:.4f}</sub>", ""]
    return body + "\n".join(footer)
