"""Render a CaseResult as Markdown, following the answer structure in the docx §3."""

from afs_assistant.schema import CaseResult

_BASIS = {"client_fact": "client", "sourced": "source", "general_knowledge": "general knowledge", "assumption": "assumption"}
_STATUS = {
    "provisional_assessment": "Provisional assessment",
    "insufficient_information": "Insufficient information",
    "outside_supported_scope": "Outside the supported scope",
}


def _flagged_paths(result: CaseResult) -> set[str]:
    return {f.path.split(".citations")[0] for f in result.verification.flags}


def _st(s, path: str = "", flagged: set[str] | None = None) -> str:
    if s is None:
        return "–"
    cites = "; ".join(c.ref + (f" ({c.url})" if c.url else "") for c in s.citations)
    tag = _BASIS[s.basis] + (f": {cites}" if cites else "")
    warn = " ⚠ *see verification*" if flagged and path in flagged else ""
    return f"{s.text} `[{tag}]`{warn}"


def to_markdown(r: CaseResult) -> str:
    a, fl = r.assessment, _flagged_paths(r)
    L = [f"# {r.case_id}: first technical assessment", ""]
    L += [f"**Decision status:** {_STATUS[a.decision_status]}. {a.status_reason}", "", f"> {a.summary_for_expert}", ""]
    L += ["## Requirements", "", "**Facts stated by the client**", ""]
    L += [f"- {f.fact} — *“{f.enquiry_quote}”*" for f in r.facts_stated]
    L += ["", "**Constraints**", ""] + [f"- {_st(s, f'constraints[{i}]', fl)}" for i, s in enumerate(a.constraints)]
    L += ["", "**Key unknowns**", ""] + [f"- {u}" for u in a.key_unknowns]
    L += ["", "## Premise check", ""]
    for i, p in enumerate(a.premise_checks):
        L.append(f"- **{p.client_claim}** → `{p.verdict}`")
        L += [f"  - {_st(s, f'premise_checks[{i}].explanation[{j}]', fl)}" for j, s in enumerate(p.explanation)]
    L += ["", "## Clarification questions (by decision impact)", "", "| # | Topic | Question | Why it matters | If unanswered we assume |", "|---|---|---|---|---|"]
    for q in r.clarification_questions:
        ans = f" **Answer:** {q.answer}" if q.answer else ""
        L.append(f"| {q.id} | {q.topic.replace('_', ' ')} | {q.question}{ans} | {q.why} | {q.assumption_if_unanswered} |")
    L += ["", "## Recommendation", ""]
    note_label = {"condition": "Condition", "why_not_simpler": "Why not simpler", "combination_trigger": "Combine only if", "spectral_range_note": "Range note"}
    for i, rec in enumerate(a.recommendations):
        p = f"recommendations[{i}]"
        L.append(f"### {rec.simplicity_rank}. {rec.method} — {rec.technique_geometry} (`{rec.role}`, cost {rec.cost_complexity}, confidence {rec.confidence})")
        if rec.spectral_range:
            L.append(f"- *Spectral range (nominal):* {rec.spectral_range}")
        L += [f"- {_st(s, f'{p}.rationale[{j}]', fl)}" for j, s in enumerate(rec.rationale)]
        L += [f"- *{note_label[n.kind]}:* {_st(n, f'{p}.notes[{j}]', fl)}" for j, n in enumerate(rec.notes)]
        L += [f"- *Confidence:* {rec.confidence_reason}", ""]
    L += ["**Method table screening (S01 Table 1, p.6)**", "", "| Row | Decision | Reason |", "|---|---|---|"]
    L += [f"| {d.table_row} | {d.decision} | {d.reason} |" for d in a.method_table_screening]
    mc = a.measurement_concept
    L += ["", "## Measurement concept", "", f"- **Probe:** {mc.probe_type} · **Geometry:** {mc.geometry} · **Location:** {mc.location} · **Architecture:** {mc.architecture}"]
    L.append(f"- **Fiber link:** {mc.fiber_family} (compatible: {mc.fiber_compatible})")
    L += [f"- {_st(s, f'measurement_concept.rationale[{j}]', fl)}" for j, s in enumerate(mc.rationale)]
    L += ["", "## Risks and uncertainty", ""]
    for i, rk in enumerate(a.risks):
        cites = "; ".join(c.ref for c in rk.citations)
        tag = _BASIS[rk.basis] + (f": {cites}" if cites else "")
        warn = " ⚠ *see verification*" if f"risks[{i}]" in fl else ""
        L.append(f"- **[{rk.type}]** {rk.risk} → *Mitigation:* {rk.mitigation} `[{tag}]`{warn}")
    L += ["", "**Assumptions**", ""] + [f"- {x}" for x in a.assumptions]
    fp = a.feasibility_plan
    L += ["", "## Feasibility plan", "", f"**Objective:** {fp.objective}", ""]
    L += [f"- Methods screened in the lab: {', '.join(fp.methods_screened)}", f"- Methods compared: {', '.join(fp.methods_compared)}", ""]
    stages = [("lab_screening", "1. Lab screening"), ("method_comparison", "2. Method comparison against the reference"), ("inline_trial", "3. In-line / in-situ trial"), ("scale_up", "4. Scale-up")]
    for key, title in stages:
        L.append(f"**{title}**")
        L += [f"- *{st.aspect.replace('_', ' ')}:* {_st(st, f'feasibility_plan.steps[{j}]', fl)}" for j, st in enumerate(fp.steps) if st.stage == key]
        L.append("")
    L += [f"**AFS next path: {fp.afs_next_path}.** {fp.afs_next_path_reason}", ""]

    v = r.verification
    L += ["## Verification report", ""]
    L.append("Citations: " + ", ".join(f"{k.replace('citations_', '')} {n}" for k, n in sorted(v.counts.items()) if k.startswith("citations_")))
    if v.revised:
        L.append(f"One revision pass ran ({len(v.flags_before_revision)} flags before, {len(v.flags)} after).")
    if v.flags:
        L += ["", "| Where | Check | Detail |", "|---|---|---|"] + [f"| `{f.path}` | {f.kind} | {f.detail} |" for f in v.flags]
    else:
        L.append("No open flags: every quote matched its page, every number traced to the enquiry or a cited page.")
    used = sorted({s.ref for s in v.sources})
    L += ["", f"**Sources used:** {', '.join(used)}", ""]
    m = r.run_meta
    models = ", ".join(sorted({f"{c.get('model')} ({c.get('thinking_level')})" for c in m.calls}))
    L += [f"<sub>Generated by afs-assistant {m.pipeline_version} · {models} · prompt {m.prompt_hash} · commit {m.git_commit} · {m.timestamp} · {m.duration_s} s</sub>", ""]
    return "\n".join(L)
