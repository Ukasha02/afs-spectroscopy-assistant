"""Evaluate the assistant on the development cases (D01-D08).

  python eval/run_eval.py --set D            # run all D cases, then score
  python eval/run_eval.py --cases D01,D02    # run selected cases
  python eval/run_eval.py --set D --no-run   # re-score existing outputs only (no API calls)

Prints the rubric pass/fail table. For cases with a worked answer (DOCX §2: D01, D02) it also
prints a section-by-section comparison. The worked-answer text is shown on the console only;
outputs/eval/eval_report.md keeps scores, word counts and citation differences (no docx text).
"""

import argparse
import json
import re
import sys

from rapidfuzz import fuzz

from afs_assistant import config
from afs_assistant.cli import _run_and_save
from afs_assistant.kb.load import load_cases, load_chunks
from afs_assistant.render import RANGE_CAVEAT, report_body, sources_used, word_count
from afs_assistant.schema import CaseResult

SECTIONS = [
    "Decision status", "Requirements stated", "Key unknowns", "Clarification questions", "Recommendation",
    "Measurement concept", "Spectral range", "Risks and uncertainty", "First feasibility experiment",
    "Decision basis", "Sources",
]
_REF = re.compile(r"S0\d (?:Table 1 \(p\.6\)|p\.\s?\d+(?:[–-]\d+)?)")


def worked_sections(case_id: str) -> dict[str, str] | None:
    chunk = next((c for c in load_chunks() if c.id == f"DOCX:§2/{case_id}"), None)
    if not chunk:
        return None
    text, out = chunk.text, {}
    positions = [(text.find(s), s) for s in SECTIONS if text.find(s) >= 0]
    positions.sort()
    for i, (pos, name) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        out[name] = text[pos + len(name):end].strip()
    return out


def our_sections(r: CaseResult) -> dict[str, str]:
    a = r.assessment
    j = lambda claims: " ".join(f"{c.text} [{'; '.join(x.ref for x in c.citations)}]" for c in claims)
    return {
        "Decision status": f"{a.decision_status} {a.status_reason}",
        "Requirements stated": "; ".join(a.requirements_stated),
        "Key unknowns": "; ".join(a.key_unknowns),
        "Clarification questions": " ".join(q.question for q in a.report_questions),
        "Recommendation": " ".join(f"{x.method} ({x.geometry}). {j([x.reason, x.caveat])}" for x in a.recommendations),
        "Measurement concept": j(a.measurement_concept.items) + " Needs AFS confirmation: " + ", ".join(a.measurement_concept.needs_afs_confirmation),
        "Spectral range": "; ".join(f"{e.method}: {e.nominal_range} [{e.citation.ref}] {e.note or ''}" for e in a.spectral_ranges) + " " + RANGE_CAVEAT,
        "Risks and uncertainty": " ".join(f"({x.category}) {x.text} [{'; '.join(c.ref for c in x.citations)}]" for x in a.risks),
        "First feasibility experiment": " ".join(f"({s.element}) {s.text}" for s in a.feasibility_plan.steps),
        "Decision basis": j([a.decision_basis]),
        "Sources": ", ".join(sources_used(a)),
    }


def refs(text: str) -> set[str]:
    return {re.sub(r"\s+", " ", m).replace("p. ", "p.") for m in _REF.findall(text.replace("–", "-"))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=["D", "H"])
    ap.add_argument("--cases")
    ap.add_argument("--no-run", action="store_true")
    ap.add_argument("--phase", help="label for the spend ledger")
    args = ap.parse_args()
    if args.phase:
        import os
        os.environ["SPEND_PHASE"] = args.phase
    cases = load_cases()
    ids = args.cases.split(",") if args.cases else sorted(c for c in cases if c.startswith(args.set or "D"))
    if any(c.startswith("H") for c in ids) and not args.no_run:
        print("H cases are generated only by `run-all --set H` from a frozen commit, not by the eval loop.", file=sys.stderr)
        return 1

    if not args.no_run:
        for cid in ids:
            _run_and_save(cid, cases[cid]["enquiry"])

    results = {cid: CaseResult.model_validate_json((config.OUTPUTS_DIR / f"{cid}.json").read_text()) for cid in ids}
    checks = [i.check for i in next(iter(results.values())).rubric]
    lines = ["# Evaluation report", "", "## Rubric", ""]
    header = "| Check | " + " | ".join(ids) + " |"
    lines += [header, "|" + "---|" * (len(ids) + 1)]
    for ch in checks:
        row = [next(("✅" if i.passed else "❌") for i in results[c].rubric if i.check == ch) for c in ids]
        lines.append(f"| {ch} | " + " | ".join(row) + " |")
    lines.append("| **passed** | " + " | ".join(f"**{sum(i.passed for i in results[c].rubric)}/{len(results[c].rubric)}**" for c in ids) + " |")
    lines.append("| open verifier flags | " + " | ".join(str(len(results[c].verification.flags)) for c in ids) + " |")
    lines.append("| flags fixed by revision | " + " | ".join(str(len(results[c].verification.flags_before_revision)) for c in ids) + " |")
    lines.append("| status | " + " | ".join(results[c].assessment.decision_status.replace("_", " ") for c in ids) + " |")
    lines.append("| duration (s) | " + " | ".join(str(results[c].run_meta.duration_s) for c in ids) + " |")
    lines.append("| cost (USD) | " + " | ".join(f"{results[c].run_meta.cost_usd:.4f}" for c in ids) + " |")
    lines.append("| words | " + " | ".join(str(word_count(report_body(results[c].assessment, c))) for c in ids) + " |")
    lines += ["", "Failures:", ""]
    for c in ids:
        for i in results[c].rubric:
            if not i.passed:
                lines.append(f"- {c} · {i.check}: {i.detail}")

    for cid in ids:
        worked = worked_sections(cid)
        if not worked:
            continue
        ours = our_sections(results[cid])
        lines += ["", f"## {cid} vs worked answer (DOCX §2)", "", "| Section | words worked / ours | similarity | refs only in worked | refs only in ours |", "|---|---|---|---|---|"]
        print(f"\n===== {cid}: section-by-section vs worked answer =====")
        for name in SECTIONS:
            w, o = worked.get(name, ""), ours.get(name, "")
            sim = round(fuzz.token_set_ratio(w.lower(), o.lower())) if w and o else "-"
            rw, ro = refs(w), refs(o)
            lines.append(f"| {name} | {word_count(w)} / {word_count(o)} | {sim} | {', '.join(sorted(rw - ro)) or '–'} | {', '.join(sorted(ro - rw)) or '–'} |")
            if name != "Sources":
                print(f"\n--- {name} (similarity {sim})\n  WORKED: {w[:400]}\n  OURS:   {o[:400]}")

    out = config.OUTPUTS_DIR / "eval"
    out.mkdir(parents=True, exist_ok=True)
    (out / "eval_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines))
    print(f"\nSaved {out / 'eval_report.md'}")
    from afs_assistant import costs
    print(costs.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
