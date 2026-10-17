"""Compare model runs stored in outputs/runs/<tag>/{D,adversarial}/ (written by run_eval.py --tag).

  python eval/compare_models.py haiku opus sonnet

Per model and suite: rubric pass rate (current rubric), open verifier flags, flags fixed by the
revision, adversarial premise/status checks, words, time and cost per answer. Writes
outputs/eval/model_comparison.md.
"""

import statistics
import sys
from pathlib import Path

import yaml

from afs_assistant import config
from afs_assistant.render import report_body, word_count
from afs_assistant.rubric import rubric
from afs_assistant.schema import CaseResult

EXPECT = {cid: c["expect"] for cid, c in yaml.safe_load((Path(__file__).parent / "adversarial" / "cases.yaml").read_text()).items()}


def load(tag: str, suite: str) -> dict[str, CaseResult]:
    d = config.OUTPUTS_DIR / "runs" / tag / suite
    return {p.stem: CaseResult.model_validate_json(p.read_text()) for p in sorted(d.glob("*.json"))} if d.exists() else {}


def stats(results: dict[str, CaseResult], ids: list[str]) -> dict:
    rows = [results[i] for i in ids if i in results]
    if not rows:
        return {}
    passed, total, adv_ok, adv_n = 0, 0, 0, 0
    for r in rows:
        pre = r.pre_analysis
        items = rubric(r.assessment, r.case_id, pre["required_risk_categories"], pre.get("fiber_findings_required_in_premise_check", []))
        passed += sum(i.passed for i in items)
        total += len(items)
        if r.case_id in EXPECT:
            e, a = EXPECT[r.case_id], r.assessment
            flagged = any(p.verdict in ("contradicted", "unverifiable") for p in a.premise_checks)
            contradicted = any(p.verdict == "contradicted" for p in a.premise_checks)
            adv_ok += (flagged if e["premise_flagged"] else not contradicted) + (a.decision_status in e["status_in"])
            adv_n += 2
    words = [word_count(report_body(r.assessment, r.case_id)) for r in rows]
    return {
        "n": len(rows),
        "rubric": f"{passed}/{total} ({100 * passed / total:.0f}%)",
        "adversarial": f"{adv_ok}/{adv_n}" if adv_n else "–",
        "open flags": sum(len(r.verification.flags) for r in rows),
        "fixed by revision": sum(len(r.verification.flags_before_revision) for r in rows),
        "words (median)": int(statistics.median(words)),
        "time s (median)": round(statistics.median(r.run_meta.duration_s for r in rows)),
        "cost $/answer (mean)": f"{statistics.mean(r.run_meta.cost_usd for r in rows):.3f}",
    }


def main(tags: list[str]) -> int:
    lines = ["# Model comparison", ""]
    for suite in ("D", "adversarial"):
        runs = {t: load(t, suite) for t in tags}
        common = sorted(set.intersection(*(set(r) for r in runs.values() if r))) if any(runs.values()) else []
        if not common:
            continue
        lines += [f"## {suite} (cases run by every model: {', '.join(common)})", ""]
        table = {t: stats(runs[t], common) for t in tags if runs[t]}
        keys = list(next(iter(table.values())).keys())
        lines += ["| | " + " | ".join(table) + " |", "|---|" + "---|" * len(table)]
        lines += [f"| {k} | " + " | ".join(str(table[t][k]) for t in table) + " |" for k in keys]
        lines.append("")
        lines += ["Premise verdicts per case:", ""]
        for cid in common:
            lines.append(f"- {cid}: " + " · ".join(f"{t}: {', '.join(p.verdict for p in runs[t][cid].assessment.premise_checks)} → {runs[t][cid].assessment.decision_status}" for t in table))
        lines.append("")
    out = config.OUTPUTS_DIR / "eval" / "model_comparison.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"Saved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["haiku", "opus", "sonnet"]))
