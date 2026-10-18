"""Deterministic rubric: does an answer follow the worked-answer recipe? Runs on every answer.

Failures that the model can fix are passed to the single revision pass as 'rubric' flags.
Keyword checks look for the recipe's elements (e.g. 'hypothesis' for combinations), never for
case content.
"""

import re

from afs_assistant.render import report_body, section_overruns, word_count
from afs_assistant.schema import PLAN_REQUIRED, Assessment, Flag, RubricItem

WORDS_MIN, WORDS_MAX = 250, 550  # 450 proved unreachable without dropping required content
_Q_ORDER = ("measured", "reference", "variation", "requirements", "context")


def _has(text: str, *patterns: str) -> bool:
    return all(re.search(p, text, re.I) for p in patterns)


def rubric(a: Assessment, case_id: str, required_risks: list[str], fiber_findings: list[str] = ()) -> list[RubricItem]:
    items: list[RubricItem] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        items.append(RubricItem(check=name, passed=bool(ok), detail="" if ok else detail))

    check("decision status + reason", a.decision_status and a.status_reason.strip(), "missing reason")
    check("requirements stated", a.requirements_stated, "empty")
    check("key unknowns", a.key_unknowns, "empty")

    order = [_Q_ORDER.index(q.covers) for q in a.report_questions]
    check("4-10 prioritised questions", 4 <= len(a.report_questions) <= 10 and order == sorted(order),
          f"{len(a.report_questions)} questions, order {[q.covers for q in a.report_questions]}")

    recs = [r for r in a.recommendations if r.role != "not_recommended"]
    if a.decision_status in ("insufficient_information", "outside_supported_scope") and not recs:
        check("recommendations: cited reason + caveat", True)
    else:
        bad = [r.method for r in recs if r.reason.basis != "sourced" or not r.reason.citations or not r.caveat.text.strip()]
        check("recommendations: cited reason + caveat", recs and not bad, f"missing for {bad or 'all (no recommendation)'}")
    combos = [r for r in recs if r.role == "combination" or "+" in r.method]
    unframed = [r.method for r in combos if not _has(r.reason.text + " " + r.caveat.text, r"hypothes")]
    check("combination framed as hypothesis", not unframed, f"not framed as a hypothesis to test: {unframed}")

    if a.decision_status in ("provisional_assessment", "premise_not_supported"):
        check("nominal spectral range cited", a.spectral_ranges and all(e.citation.ref for e in a.spectral_ranges), "no cited nominal range")
    else:
        check("nominal spectral range cited", True)

    present = {r.category for r in a.risks}
    missing = [c for c in required_risks if c not in present]
    check("standard risk categories", not missing, f"missing {missing}")

    elements = [s.element for s in a.feasibility_plan.steps]
    missing_steps = [alt[0] for alt in PLAN_REQUIRED if not any(e in elements for e in alt)]
    texts = {s.element: s.text for s in a.feasibility_plan.steps}
    content = []
    if not _has(texts.get("spectra_with_reference", ""), r"referen|laborator|\blab\b|assay|label|ground truth", r"tim"):
        content.append("spectra need independent reference + timing")
    several = len(recs) > 1
    if not _has(texts.get("models_and_validation", ""), r"single|on its own|alone|\bfirst\b" if several else r".", r"held.out|independent|validat"):
        content.append("single-method first + held-out validation" if several else "held-out validation")
    if not _has(texts.get("comparison", ""), r"error", r"bias"):
        content.append("compare prediction error and bias")
    not_proposal = [s.element for s in a.feasibility_plan.steps if s.basis != "proposal"]
    check("feasibility plan: 4 elements", not missing_steps and not content and not not_proposal,
          f"missing {missing_steps}; content {content}; not labelled proposal {not_proposal}")

    check("decision basis: client-agreed + simplest", _has(a.decision_basis.text, r"client|agree", r"simpl"), "must say client-agreed criteria and simplest configuration")

    over = [r.method for r in a.recommendations if r.confidence == "high" and a.key_unknowns]
    check("no 'high' confidence while unknowns remain", not over, f"high confidence: {over}")

    unquoted = [r.method for r in recs if not any(c.quote and len(c.quote.split()) <= 40 for c in r.reason.citations)]
    check("recommendation reasons quoted", not unquoted, f"no short verbatim quote for {unquoted}")

    if fiber_findings:
        fiber_premise = any(pc.verdict != "supported" and _has(pc.client_claim + " " + " ".join(s.text for s in pc.explanation), r"fib|link|cable")
                            for pc in a.premise_checks)
        fiber_risk = any(r.category == "fiber_link" for r in a.risks)
        check("fiber issue in premise check + risk", fiber_premise and fiber_risk,
              f"premise check {'ok' if fiber_premise else 'missing'}, risk {'ok' if fiber_risk else 'missing'}: {fiber_findings[0][:90]}")
    else:
        check("fiber issue in premise check + risk", True)

    words = word_count(report_body(a, case_id))
    over = section_overruns(a)
    check(f"report length {WORDS_MIN}-{WORDS_MAX} words", WORDS_MIN <= words <= WORDS_MAX,
          f"{words} words; over budget: {', '.join(over) or 'none'} (citations excluded)")
    return items


def rubric_flags(items: list[RubricItem]) -> list[Flag]:
    """Failures the revision pass should fix."""
    return [Flag(path="rubric", kind="rubric", detail=f"{i.check}: {i.detail}") for i in items if not i.passed]


