"""Command line.

  python -m afs_assistant.cli run --case D01          # one case from kb/cache/cases.json
  python -m afs_assistant.cli run --text "We need..."  # a new enquiry (case id NEW)
  python -m afs_assistant.cli run-all --set H          # all H cases (or D)
  python -m afs_assistant.cli spend                    # spend ledger summary

--phase <name> labels the spend ledger entries (default: SPEND_PHASE from .env, else 'dev').
"""

import argparse
import json
import os
import sys

from afs_assistant import config, costs
from afs_assistant.kb.load import load_cases
from afs_assistant.pipeline import run_case
from afs_assistant.render import to_markdown


def _run_and_save(case_id: str, enquiry: str, out_dir=None) -> None:
    os.environ["SPEND_CASE"] = case_id
    print(f"[{case_id}] running...", file=sys.stderr, flush=True)
    result = run_case(case_id, enquiry)
    out_dir = out_dir or config.OUTPUTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{case_id}.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    (out_dir / f"{case_id}.md").write_text(to_markdown(result), encoding="utf-8")
    v = result.verification
    print(
        f"[{case_id}] {result.assessment.decision_status} · {result.run_meta.duration_s}s · ${result.run_meta.cost_usd:.4f} · "
        f"flags {len(v.flags)} (before revision {len(v.flags_before_revision)}) · {json.dumps(v.counts)}",
        file=sys.stderr,
    )


def main() -> int:
    parser = argparse.ArgumentParser(prog="afs-assistant")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    group = run.add_mutually_exclusive_group(required=True)
    group.add_argument("--case")
    group.add_argument("--text")
    run_all = sub.add_parser("run-all")
    run_all.add_argument("--set", choices=["D", "H"], required=True)
    for p in (run, run_all):
        p.add_argument("--phase", help="label for the spend ledger")
    sub.add_parser("spend")
    args = parser.parse_args()
    if getattr(args, "phase", None):
        os.environ["SPEND_PHASE"] = args.phase
    if args.cmd == "spend":
        print(costs.summary())
        return 0

    cases = load_cases()
    if args.cmd == "run":
        if args.case:
            _run_and_save(args.case, cases[args.case]["enquiry"])
        else:
            _run_and_save("NEW", args.text)
    else:
        for case_id in sorted(c for c in cases if c.startswith(args.set)):
            _run_and_save(case_id, cases[case_id]["enquiry"])
    print(costs.summary(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
