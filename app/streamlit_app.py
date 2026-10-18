"""AFS Spectroscopy Assistant · web UI (Streamlit).

  streamlit run app/streamlit_app.py

Library mode (default, no API calls): browse pre-generated reports.
Live mode: runs the real pipeline; gated by an access code (secret ACCESS_CODE) and limited per
session (LIVE_RUNS_PER_SESSION, default 3) on top of the spend-ledger budget guard.
The UI only calls the existing pipeline and reads existing outputs; no assessment logic lives here.
"""

import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(Path(__file__).parent)]

# Hosted secrets -> environment, BEFORE the pipeline modules read their settings.
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k, _v)
except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
    pass

from kb_access import ensure_kb  # noqa: E402
from report_html import footer, report_html, rule_panel  # noqa: E402

from afs_assistant import config, costs  # noqa: E402
from afs_assistant.render import to_markdown  # noqa: E402
from afs_assistant.schema import CaseResult  # noqa: E402

st.set_page_config(page_title="AFS Spectroscopy Assistant · prototype", page_icon=":material/biotech:", layout="wide")
st.markdown(f"<style>{(Path(__file__).parent / 'style.css').read_text()}</style>", unsafe_allow_html=True)

LABEL = "Prototype built for Art Fiber Systems · SchubKI National AI Hackathon 2026 · not an official AFS product"
LIVE_RUNS = int(os.getenv("LIVE_RUNS_PER_SESSION", "3"))
LIVE_ENABLED = os.getenv("LIVE_ENABLED", "false").strip().lower() == "true"  # off on the hosted app: zero API spend
LIBRARY_RUN = os.getenv("LIBRARY_RUN", "final")  # frozen-version runs (outputs/runs/final/), same config as H01-H06
STEPS = ["Intake", "Rule checks", "Assessment", "Verification", "Revision"]
KB_STATE = ensure_kb()


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def library() -> list[dict]:
    """Pre-generated results: D (development), A (adversarial), H (final evaluation, once frozen)."""
    run = config.OUTPUTS_DIR / "runs" / LIBRARY_RUN
    d_dir = run / "D" if (run / "D").exists() else config.OUTPUTS_DIR
    a_dir = run / "adversarial" if (run / "adversarial").exists() else config.OUTPUTS_DIR / "adversarial"
    groups = [("Final evaluation (H)", config.OUTPUTS_DIR, "H*.json"),
              ("Development (D)", d_dir, "D*.json"),
              ("Adversarial (own hard cases)", a_dir, "A*.json")]
    items = []
    for group, folder, pattern in groups:
        for p in sorted(folder.glob(pattern)):
            r = CaseResult.model_validate_json(p.read_text())
            items.append({"group": group, "id": r.case_id, "path": str(p), "status": r.assessment.decision_status,
                          "rubric": f"{sum(i.passed for i in r.rubric)}/{len(r.rubric)}",
                          "open_flags": len(r.verification.flags), "enquiry": r.enquiry})
    return items


def load_result(path: str) -> CaseResult:
    return CaseResult.model_validate_json(Path(path).read_text())


def examples() -> dict[str, dict]:
    """Example enquiries for the dropdown. H cases open their pre-generated report (no live run)."""
    out = {}
    try:
        from afs_assistant.kb.load import load_cases

        for cid, c in sorted(load_cases().items()):
            out[f"{cid} · {c['title']}"] = {"id": cid, "enquiry": c["enquiry"], "library_only": cid.startswith("H")}
    except FileNotFoundError:
        pass
    adv = ROOT / "eval" / "adversarial" / "cases.yaml"
    if adv.exists():
        import yaml

        for cid, c in yaml.safe_load(adv.read_text()).items():
            out[f"{cid} · {c['title']}"] = {"id": cid, "enquiry": c["enquiry"], "library_only": False}
    return out


# ---------------------------------------------------------------------------
# views
# ---------------------------------------------------------------------------

def show_report(r: CaseResult, before: CaseResult | None = None) -> None:
    if before and before.assessment.decision_status != r.assessment.decision_status:
        st.info(f"Your answers changed the decision status: **{before.assessment.decision_status.replace('_', ' ')}** → "
                f"**{r.assessment.decision_status.replace('_', ' ')}**")
    left, right = st.columns([2.2, 1], gap="large")
    with left:
        st.markdown(report_html(r), unsafe_allow_html=True)
    with right:
        st.markdown("##### Enquiry")
        st.caption(r.enquiry)
        with st.expander("Verification details"):
            v = r.verification
            st.markdown("**Fixed in the revision pass**")
            for f in v.flags_before_revision or []:
                st.markdown(f"- `{f.kind}` {f.detail}")
            if not v.flags_before_revision:
                st.caption("Nothing needed fixing.")
            st.markdown("**Still open**")
            for f in v.flags:
                st.markdown(f"- `{f.kind}` {f.detail}")
            if not v.flags:
                st.caption("No open flags.")
            st.markdown("**Rubric**")
            for i in r.rubric:
                st.markdown(f"{'✓' if i.passed else '✗'} {i.check}" + (f" — {i.detail}" if i.detail else ""))
        with st.expander("Rule checks (table shortlist, fiber)"):
            st.markdown(rule_panel(r), unsafe_allow_html=True)
        with st.expander("Diagnostic questionnaire (interactive mode)"):
            for q in r.clarification_questions:
                st.markdown(f"**{q.id}** {q.question}  \n*If unanswered:* {q.assumption_if_unanswered}" + (f"  \n**Answer:** {q.answer}" if q.answer else ""))
        st.download_button("Download report (Markdown)", to_markdown(r), f"{r.case_id}.md", use_container_width=True)
        st.download_button("Download data (JSON)", r.model_dump_json(indent=2), f"{r.case_id}.json", use_container_width=True)
    st.markdown(footer(r), unsafe_allow_html=True)


def live_allowed() -> bool:
    code = os.getenv("ACCESS_CODE")
    if not code:
        st.info("Live mode is not configured on this deployment. Browse the results library instead.")
        return False
    if st.session_state.get("unlocked"):
        return True
    entered = st.text_input("Access code for live mode (provided in the submission)", type="password")
    if entered and entered == code:
        st.session_state.unlocked = True
        st.rerun()
    elif entered:
        st.error("Wrong access code.")
    return False


def runs_left() -> int:
    return LIVE_RUNS - st.session_state.get("live_runs", 0)


def run_live(fn, *args, **kwargs):
    """Run a pipeline function with a step-by-step progress display and readable errors."""
    with st.status("Running the assessment…", expanded=True) as status:
        done = []

        def progress(step: str) -> None:
            if done:
                status.write(f"✓ {done[-1]}")
            done.append(step)
            status.update(label=f"{step}…")

        try:
            result = fn(*args, progress=progress, **kwargs)
        except costs.BudgetExceeded:
            status.update(label="Budget limit reached", state="error")
            st.error("The demo budget for live runs is used up. The results library still works.")
            return None
        except Exception as e:  # noqa: BLE001 (show a readable message, never a stack trace)
            status.update(label="The run did not complete", state="error")
            st.error(f"The assessment could not be completed ({type(e).__name__}). Please try again in a minute.")
            return None
        if done:
            status.write(f"✓ {done[-1]}")
        status.update(label="Done", state="complete", expanded=False)
        return result


def page_assess() -> None:
    from afs_assistant.pipeline import run_assessment, run_intake

    st.title("First technical assessment")
    st.markdown(f'<div class="proto-label">{LABEL}</div>', unsafe_allow_html=True)
    ex = examples()
    choice = st.selectbox("Load example", ["—"] + list(ex), index=0)
    if choice != "—" and ex[choice]["library_only"]:
        match = [i for i in library() if i["id"] == ex[choice]["id"]]
        if match:
            st.caption("Final evaluation cases are shown as their pre-generated report (no live run).")
            show_report(load_result(match[0]["path"]))
        else:
            st.info("This final-evaluation case has not been generated yet.")
        return
    enquiry = st.text_area("Customer enquiry", value=ex[choice]["enquiry"] if choice != "—" else "", height=140,
                           placeholder="Describe the process, what should be monitored, and any constraints…")
    saved = [i for i in library() if choice != "—" and i["id"] == ex[choice]["id"]]
    if saved and st.button("Show pre-generated report (free)"):
        show_report(load_result(saved[0]["path"]))
        return

    st.divider()
    st.subheader("Live run")
    if not LIVE_ENABLED:
        st.info("Live runs are switched off on this deployment (no API calls, no cost). Every example above has a "
                "pre-generated report; the Results library shows them all. The demo video shows a live run.")
        return
    if KB_STATE == "missing":
        st.warning("The knowledge base is not available on this deployment, so live runs are disabled.")
        return
    if not live_allowed():
        return
    st.caption(f"{runs_left()} of {LIVE_RUNS} live runs left in this session · model: {os.getenv('MODEL_ASSESS', 'claude-haiku-5-5')}")
    interactive = st.toggle("Ask clarification questions first")
    if runs_left() <= 0:
        st.warning("Live-run limit for this session reached. The results library is still available.")
        return
    key = hash(enquiry)

    if not interactive:
        if st.button("Run assessment", type="primary", disabled=len(enquiry.strip()) < 30):
            from afs_assistant.pipeline import run_case

            r = run_live(run_case, "LIVE", enquiry.strip())
            if r:
                st.session_state.live_runs = st.session_state.get("live_runs", 0) + 1
                st.session_state.last = {"key": key, "result": r}
        last = st.session_state.get("last")
        if last and last["key"] == key:
            show_report(last["result"])
        return

    # Interactive: questions first, then the assessment with the client's answers.
    if st.button("Get clarification questions", disabled=len(enquiry.strip()) < 30):
        with st.spinner("Reading the enquiry…"):
            try:
                st.session_state.intake = {"key": key, "data": run_intake(enquiry.strip())}
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not read the enquiry ({type(e).__name__}). Please try again.")
    it = st.session_state.get("intake")
    if not (it and it["key"] == key):
        return
    intake, calls = it["data"]
    with st.form("questions"):
        st.markdown("Answer what you can. Leave a field empty to use the fallback assumption.")
        answers = {}
        for q in intake.questions:
            answers[q.id] = st.text_input(f"{q.id} · {q.question}", help=f"Why: {q.why}\n\nIf unanswered: {q.assumption_if_unanswered}")
        submitted = st.form_submit_button("Run assessment with these answers", type="primary")
    if submitted:
        before = st.session_state.get("last", {}).get("result") if st.session_state.get("last", {}).get("key") == key else None
        r = run_live(run_assessment, "LIVE", enquiry.strip(), intake, calls, answers={k: v for k, v in answers.items() if v.strip()}, mode="interactive")
        if r:
            st.session_state.live_runs = st.session_state.get("live_runs", 0) + 1
            st.session_state.last = {"key": key, "result": r, "before": before}
    last = st.session_state.get("last")
    if last and last["key"] == key:
        show_report(last["result"], last.get("before"))


def page_library() -> None:
    st.title("Results library")
    st.markdown(f'<div class="proto-label">{LABEL}</div>', unsafe_allow_html=True)
    if st.session_state.get("open_report"):
        if st.button("← Back to library"):
            st.session_state.open_report = None
            st.rerun()
        show_report(load_result(st.session_state.open_report))
        return
    items = library()
    if not items:
        st.info("No pre-generated results found.")
        return
    for group in dict.fromkeys(i["group"] for i in items):
        st.markdown(f"#### {group}")
        for i in [x for x in items if x["group"] == group]:
            c1, c2, c3, c4 = st.columns([0.8, 4, 1.6, 1])
            c1.markdown(f"**{i['id']}**")
            c2.caption(i["enquiry"][:150] + "…")
            c3.markdown(f"{i['status'].replace('_', ' ')}  \nrubric {i['rubric']} · {i['open_flags']} open flags")
            if c4.button("Open", key=f"open-{i['path']}"):
                st.session_state.open_report = i["path"]
                st.rerun()


def page_how() -> None:
    st.title("How it works")
    st.markdown(f'<div class="proto-label">{LABEL}</div>', unsafe_allow_html=True)
    st.graphviz_chart("""
    digraph { rankdir=LR; node [shape=box, style="rounded", fontname="Inter", fontsize=11, color="#185BA9"];
      E [label="Customer enquiry"]; I [label="1 Intake\\nfacts + 5-10 questions"]; R [label="2 Rule checks\\nTable 1 shortlist · fiber · risks"];
      A [label="3 Assessment\\nfull AFS corpus (cached)"]; V [label="4 Verification\\nquotes · numbers · scope\\n+ context critic + rubric"];
      X [label="5 One revision"]; O [label="Report + JSON\\n+ verification"];
      E -> I -> R -> A -> V -> X -> O; V -> O [style=dashed, label="no flags"]; }""")
    st.markdown("""
**How the AFS materials are used**
- **Corpus:** every page of S01–S05, the method table and the reference document are text-extracted into citable pieces (`S01 p.10`, `S01 Table 1 (p.6)`). Image-only slides are covered by our own transcriptions. The whole corpus is in the model's context, so nothing is missed by retrieval.
- **Structured facts** (`kb/facts.yaml`): method and fiber ranges, probe types, application examples, source scopes and 15 general rules, each with its page reference.
- **Rule checks in code:** the Table 1 shortlist (cheapest first), fiber compatibility, and the risk categories every answer must cover.
- **Verifier in code:** every quote must be on the cited page, every number must come from the client or the cited page, lab studies never prove process or clinical readiness, and business-context sources never back technical claims. An LLM critic checks that each citation is used in the same context. One revision fixes what was flagged; anything still open is shown, never hidden.
""")
    for name, title in [("eval_report.md", "Development cases (D01–D08)"), ("adversarial_report.md", "Adversarial cases"), ("model_comparison.md", "Model comparison")]:
        p = config.OUTPUTS_DIR / "eval" / name
        if p.exists():
            with st.expander(title):
                text = p.read_text()
                st.markdown(text.split("\n## D0")[0] if "## D01 vs" in text else text)
    with st.expander("Spend ledger"):
        st.code(costs.summary())


nav = st.navigation([st.Page(page_assess, title="Assessment", default=True), st.Page(page_library, title="Results library"),
                     st.Page(page_how, title="How it works")])
nav.run()
