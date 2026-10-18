"""Final summary table for the slides: H01-H06 (outputs/), D01-D08 and A01-A08 (outputs/runs/final/).

  python eval/summary_table.py      # prints Markdown and writes outputs/eval/final_summary.md
"""

import statistics
from pathlib import Path

import yaml

from afs_assistant import config
from afs_assistant.render import report_body, word_count
from afs_assistant.schema import CaseResult

EXPECT = {cid: c["expect"] for cid, c in yaml.safe_load((Path(__file__).parent / "adversarial" / "cases.yaml").read_text()).items()}
SUITES = [
    ("H01–H06 (final evaluation)", config.OUTPUTS_DIR, "H0*.json"),
    ("D01–D08 (development)", config.OUTPUTS_DIR / "runs" / "final" / "D", "D0*.json"),
    ("A01–A08 (own hard cases)", config.OUTPUTS_DIR / "runs" / "final" / "adversarial", "A0*.json"),
]


def row(name: str, results: list[CaseResult]) -> dict:
    checks = [i for r in results for i in r.rubric]
    words = [word_count(report_body(r.assessment, r.case_id)) for r in results]
    adv = [r for r in results if r.case_id in EXPECT]
    adv_ok = sum(
        (any(p.verdict in ("contradicted", "unverifiable") for p in r.assessment.premise_checks)
         if EXPECT[r.case_id]["premise_flagged"] else not any(p.verdict == "contradicted" for p in r.assessment.premise_checks))
        + (r.assessment.decision_status in EXPECT[r.case_id]["status_in"])
        for r in adv
    )
    citations = sum(sum(n for k, n in r.verification.counts.items() if k.startswith("citations_")) for r in results)
    return {
        "Cases": name,
        "Rubric passed": f"{sum(i.passed for i in checks)}/{len(checks)} ({100 * sum(i.passed for i in checks) / len(checks):.0f}%)",
        "Open flags": sum(len(r.verification.flags) for r in results),
        "Issues fixed by revision": sum(len(r.verification.flags_before_revision) for r in results),
        "Citations checked": citations,
        "Trap checks": f"{adv_ok}/{2 * len(adv)}" if adv else "–",
        "Words (median, range)": f"{int(statistics.median(words))} ({min(words)}–{max(words)})",
        "Time / answer (median)": f"{round(statistics.median(r.run_meta.duration_s for r in results))} s",
        "Cost / answer (mean)": f"${statistics.mean(r.run_meta.cost_usd for r in results):.2f}",
        "Cost total": f"${sum(r.run_meta.cost_usd for r in results):.2f}",
    }


def main() -> None:
    rows = []
    for name, folder, pattern in SUITES:
        results = [CaseResult.model_validate_json(p.read_text()) for p in sorted(folder.glob(pattern))]
        if results:
            rows.append(row(name, results))
    keys = list(rows[0])
    lines = ["| " + " | ".join(keys) + " |", "|" + "---|" * len(keys)]
    lines += ["| " + " | ".join(str(r[k]) for k in keys) + " |" for r in rows]
    meta = CaseResult.model_validate_json(next(config.OUTPUTS_DIR.glob("H0*.json")).read_text()).run_meta
    models = sorted({f"{c['stage']}: {c['model']}" for c in meta.calls})
    lines += ["", f"Models: {', '.join(models)} · pipeline {meta.pipeline_version} · commit {meta.git_commit}"]
    text = "\n".join(lines)
    (config.OUTPUTS_DIR / "eval" / "final_summary.md").write_text("# Final summary\n\n" + text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
