"""Pipeline (PRD §5): intake -> pre-analysis -> assess -> verify -> (one revision) -> result.

One-shot mode runs everything at once. Interactive mode calls run_intake(), lets the client
answer the questions, then calls run_assessment() with those answers.
"""

import subprocess
import time
from datetime import datetime, timezone

from afs_assistant import prompts, rules
from afs_assistant.llm import call_llm
from afs_assistant.schema import Assessment, CaseResult, Intake, RunMeta
from afs_assistant.verify import verify, verify_questions

PIPELINE_VERSION = "0.3.0"
_REVISE_ON = {"quote", "number", "unsupported_sourced_claim", "scope", "basis", "table_coverage"}


def _git_commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "src", "kb"], capture_output=True, text=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run_intake(enquiry: str) -> tuple[Intake, list[dict]]:
    """Extraction + questionnaire, verified; one revision if a question invents numbers or breaks the order."""
    res = call_llm(prompts.intake_system(), prompts.intake_user(enquiry), Intake)
    intake = Intake.model_validate(res["output"])
    calls = [{"stage": "intake", **res["meta"]}]
    flags = verify_questions(intake.questions, enquiry)
    if flags:
        res = call_llm(prompts.revise_intake_system(), prompts.revise_intake_user(intake.model_dump(), [f.model_dump() for f in flags]), Intake)
        intake = Intake.model_validate(res["output"])
        calls.append({"stage": "revise_intake", "flags_fixed": len(flags), **res["meta"]})
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

    res = call_llm(prompts.assess_system(), prompts.assess_user(enquiry, intake_dict, pre), Assessment)
    calls.append({"stage": "assess", **res["meta"]})
    assessment = Assessment.model_validate(res["output"])
    report = verify(assessment, enquiry, intake.questions, pre["table_shortlist"])

    revisable = [f.model_dump() for f in report.flags if f.kind in _REVISE_ON]
    if revisable:
        res = call_llm(prompts.revise_system(), prompts.revise_user(assessment.model_dump(), revisable), Assessment)
        calls.append({"stage": "revise", **res["meta"]})
        revised = Assessment.model_validate(res["output"])
        new_report = verify(revised, enquiry, intake.questions, pre["table_shortlist"])
        new_report.revised = True
        new_report.flags_before_revision = report.flags
        assessment, report = revised, new_report

    return CaseResult(
        case_id=case_id,
        mode=mode,
        enquiry=enquiry,
        facts_stated=intake.extraction.stated_facts,
        clarification_questions=intake.questions,
        assessment=assessment,
        verification=report,
        extraction=intake.extraction,
        pre_analysis=pre,
        run_meta=RunMeta(
            pipeline_version=PIPELINE_VERSION,
            calls=calls,
            prompt_hash=prompts.prompt_hash(),
            git_commit=_git_commit(),
            timestamp=timestamp,
            duration_s=round(time.monotonic() - started + sum(c.get("duration_s", 0) for c in intake_calls), 1),
        ),
    )


def run_case(case_id: str, enquiry: str) -> CaseResult:
    """One-shot mode: questionnaire + provisional assessment in a single result."""
    intake, calls = run_intake(enquiry)
    return run_assessment(case_id, enquiry, intake, calls)
