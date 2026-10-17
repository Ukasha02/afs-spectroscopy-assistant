"""Pipeline (PRD §5): intake -> pre-analysis -> assess -> verify -> (one revision) -> result.

One-shot mode runs everything at once. Interactive mode calls run_intake(), lets the client
answer the questions, then calls run_assessment() with those answers.
"""

import subprocess
import time
from datetime import datetime, timezone

from afs_assistant import prompts, rules
from afs_assistant.llm import call_llm
from afs_assistant.schema import Assessment, CaseResult, CitationRef, ConceptItem, Intake, RunMeta
from afs_assistant.critic import critique
from afs_assistant.rubric import rubric, rubric_flags
from afs_assistant.verify import verify, verify_questions

PIPELINE_VERSION = "0.6.0"
_REVISE_ON = {"quote", "number", "unsupported_sourced_claim", "scope", "basis", "table_coverage"}


def _git_commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "src", "kb"], capture_output=True, text=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _apply_fiber_verdict(assessment: Assessment, ex, pre: dict) -> Assessment:
    """Fill the fiber verdict from the rule step (not the model) and show it in the concept."""
    methods = [r.method for r in assessment.recommendations if r.role != "not_recommended"]
    compatible, text = rules.fiber_verdict(methods, ex, pre["fiber_checks"])
    mc = assessment.measurement_concept
    mc.fiber_compatible = compatible
    mc.items = [i for i in mc.items if not i.text.startswith(("Rule check", "No fiber link stated. Rule check"))]
    if text:
        mc.items.append(ConceptItem(aspect="fiber_link", text=text, basis="sourced", citations=[CitationRef(ref="S02 p.6")]))
    return assessment


def run_intake(enquiry: str) -> tuple[Intake, list[dict]]:
    """Extraction + questionnaire, verified; one revision if a question invents numbers or breaks the order."""
    res = call_llm(prompts.intake_system(), prompts.intake_user(enquiry), Intake, stage="intake")
    intake = Intake.model_validate(res["output"])
    calls = [res["meta"]]
    flags = verify_questions(intake.questions, enquiry)
    if flags:
        res = call_llm(prompts.revise_intake_system(), prompts.revise_intake_user(intake.model_dump(), [f.model_dump() for f in flags]), Intake, stage="revise_intake")
        intake = Intake.model_validate(res["output"])
        calls.append({"flags_fixed": len(flags), **res["meta"]})
    return intake, calls


def run_assessment(
    case_id: str,
    enquiry: str,
    intake: Intake,
    intake_calls: list[dict],
    answers: dict[str, str] | None = None,
    mode: str = "one_shot",
) -> CaseResult:
    started = time.monotonic()
    timestamp = datetime.now(timezone.utc).isoformat()
    for q in intake.questions:
        if answers and answers.get(q.id):
            q.answer = answers[q.id]
    pre = rules.pre_analysis(intake.extraction)
    intake_dict = intake.model_dump()
    calls = list(intake_calls)

    res = call_llm(prompts.assess_system(), prompts.assess_user(enquiry, intake_dict, pre), Assessment, stage="assess")
    calls.append(res["meta"])
    ex = intake.extraction
    assessment = _apply_fiber_verdict(Assessment.model_validate(res["output"]), ex, pre)
    required = pre["required_risk_categories"]

    report = verify(assessment, enquiry, intake.questions, pre["table_shortlist"], ex.process_context)
    context_flags, critic_meta = critique(assessment)
    if critic_meta:
        calls.append(critic_meta)
    checks = rubric(assessment, case_id, required, pre["fiber_findings_required_in_premise_check"])
    to_fix = [f for f in report.flags if f.kind in _REVISE_ON] + context_flags + rubric_flags(checks)

    if to_fix:
        res = call_llm(prompts.revise_system(), prompts.revise_user(assessment.model_dump(), [f.model_dump() for f in to_fix]), Assessment, stage="revise")
        calls.append({"flags_sent": len(to_fix), **res["meta"]})
        assessment = _apply_fiber_verdict(Assessment.model_validate(res["output"]), ex, pre)
        new_report = verify(assessment, enquiry, intake.questions, pre["table_shortlist"], ex.process_context)
        new_report.revised = True
        new_report.flags_before_revision = report.flags + context_flags
        report = new_report
        checks = rubric(assessment, case_id, required, pre["fiber_findings_required_in_premise_check"])

    return CaseResult(
        case_id=case_id,
        mode=mode,
        enquiry=enquiry,
        facts_stated=intake.extraction.stated_facts,
        clarification_questions=intake.questions,
        assessment=assessment,
        verification=report,
        rubric=checks,
        extraction=intake.extraction,
        pre_analysis=pre,
        run_meta=RunMeta(
            pipeline_version=PIPELINE_VERSION,
            calls=calls,
            prompt_hash=prompts.prompt_hash(),
            git_commit=_git_commit(),
            timestamp=timestamp,
            duration_s=round(time.monotonic() - started + sum(c.get("duration_s", 0) for c in intake_calls), 1),
            cost_usd=round(sum(c.get("cost_usd", 0) for c in calls), 4),
        ),
    )


def run_case(case_id: str, enquiry: str) -> CaseResult:
    """One-shot mode: questionnaire + provisional assessment in a single result."""
    intake, calls = run_intake(enquiry)
    return run_assessment(case_id, enquiry, intake, calls)
