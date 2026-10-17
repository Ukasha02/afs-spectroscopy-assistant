# PRD: AFS Spectroscopy Assistant

> Revision 2 (Sat 17 Oct): updated after the AFS expert Q&A. See [domain-and-qa-reference.md](domain-and-qa-reference.md) §A. If this PRD and that file disagree on product intent, that file wins. If either disagrees with the supplied AFS materials on technical facts, the materials win.

## Context
SchubKI Hackathon, Challenge 01 (Art Fiber Systems). We're building an **MVP**, not a proof of concept: it works end to end and can scale later. The assistant helps an AFS expert make a first technical assessment of a customer enquiry.

AFS describes itself as a **"process doctor"**: first diagnose the process with a few targeted questions, then suggest a sensor. The assistant therefore **opens with a short diagnostic questionnaire (5–10 questions)**. It then gives requirements, a premise check, the simplest sufficient method(s), a probe concept, risks and uncertainty, and a staged feasibility plan. Every claim is traceable to the AFS materials.

Deadline is **Sun 18 Oct 23:59**. The team is one person (solo). Repo: `github.com/Ukasha02/afs-spectroscopy-assistant`.

**What shapes the design:**
- **The H01–H06 cases test judgement more than method lookup.** The organizers say: *"Some enquiries ask for more certainty than the facts allow. A good answer notices this."* So the core is **premise checking, scope discipline, honest uncertainty and the simplest sufficient method**.
- **The docx sets the answer contract.** It defines a section structure; a decision status (*provisional / insufficient information / outside scope*); a "do not invent" list; a citation format; and common mistakes. D01 and D02 are the quality bar (Q&A A6).
- **The experts gave us the decision logic:**
  - **"As simple as possible, as complicated as necessary."** Don't upsell.
  - Combine methods only when a single method isn't precise or robust enough.
  - Chemometrics comes last.
  - The feasibility plan is a *comparison design*, not sample counts.
- **Out of scope** (Q&A A1): real-time spectral analysis, external spectral databases and predictive or chemometric modelling. IHM-style modelling is nice to have only.
- **The corpus is small**, about 50 pages. S02 is mostly images. **S01 p.19 forbids redistribution**, so full-text knowledge-base dumps stay out of git.

## 1. Users and success criteria
The users are an AFS application expert preparing or running a first customer conversation, and also R&D customers, not only production plants (Q&A A2).

| Criterion (weight) | How we meet it |
|---|---|
| Technical quality (30%) | Deterministic domain checks (fiber vs. spectral range, sample type vs. Table 1 geometry); a **simplicity ladder** with cost awareness; a critic pass against the common-mistakes list. |
| Use of AFS knowledge (20%) | The whole AFS corpus is in context. Every claim cites `document + page` (the page must directly support the claim). A short quote is added where possible, and checked automatically when present. |
| Feasibility plan (15%) | A fixed **four-stage plan**: lab screening → method comparison against the customer's reference lab method → in-line trial → scale-up. It is a comparison design, with no invented numbers. |
| Clarification & uncertainty (15%) | A **5–10 question diagnostic questionnaire ordered by decision impact**; a premise check; a decision status; labels on every claim (`client_fact / sourced / general_knowledge / assumption`). |
| Explainability (10%) | **"No hallucination" is a demoed feature**: every claim carries a citation, and the self-check removes or flags unsupported claims. The verification report is visible in the UI. |
| Prototype (10%) | A Streamlit app with interactive questionnaire mode, a D/H case picker, and run times under about 2 minutes. |

## 2. Two modes, one pipeline (new)
- **Interactive mode** (demo and live enquiry):
  1. The user enters the enquiry.
  2. The assistant asks **≤10 prioritized diagnostic questions**.
  3. The user answers any of them or skips.
  4. The assistant gives its recommendation. Answers become `client_fact`; skipped questions become explicit assumptions.
- **One-shot mode** (H01–H06 submission and CLI): one structured answer that contains the questionnaire *and* a **provisional** recommendation. The recommendation lists the assumptions it makes about each unanswered question that matters.
- Both modes share the same steps (extract → questionnaire → pre-analysis → assess → verify). The only difference is whether the assistant waits for answers before assessing.

**Question ordering** (by decision impact; at most 10 questions in total):
1. **What could change the method:** sample type and optical state (clear, turbid, opaque, powder); the target analyte or variable; concentration level (**ppm vs %**); whether a fluorescent species or marker exists, when relevant.
2. **What could change the setup:** temperature and pressure, fouling, distance from analyzer to probe and existing fibers, sterilization or cleaning, safety area.
3. **The requirements:** accuracy, response time, budget, the existing reference lab method, and the R&D vs production context.

## 3. Output schema (one scenario, pydantic, JSON + Markdown)
`case_id, mode ∈ {one_shot, interactive}, enquiry, decision_status ∈ {provisional_assessment, insufficient_information, outside_supported_scope}, status_reason`
- `requirements`: `stated_facts[{fact, enquiry_quote}]`, `constraints[]`, `key_unknowns[]`
- `premise_checks[{client_claim, verdict ∈ supported|contradicted|unverifiable, explanation, citations}]`
- `questionnaire[{id, question, why, impact ∈ method|setup|requirements, priority 1–10, answer?: str, assumption_if_unanswered}]` (5–10 items)
- `recommendations[{method, technique_geometry, role ∈ primary|alternative|add_on_if_needed|not_recommended, simplicity_rank, cost_complexity ∈ low|average|high (from Table 1), rationale, why_not_simpler?, combination_trigger?, conditions, spectral_range{value, unit, note}, confidence, citations}]`
  - A combination is only allowed with a stated `combination_trigger`, i.e. the condition under which a single method would not be precise or robust enough.
- `measurement_concept{probe_type, geometry, location, fiber_link{family, compatible: bool, check_note}, architecture ∈ centralized|iot|undecided, citations}`
- `risks[{risk, type ∈ technical|assumption|evidence_scope, mitigation}]`, `assumptions[]`
- `feasibility_plan`:
  1. `lab_screening{samples, establish: [spectral range, spectral resolution, concentration level ppm vs %], methods_screened}`
  2. `method_comparison{methods (only as many as needed), reference_method (the customer's existing lab method), compare_on, decision_basis (criteria agreed with the client; no invented numbers)}`
  3. `inline_trial{location, interface, what_to_verify}`
  4. `scale_up{robustness, sterilizability/cleaning, industry standards, few_wavelength_simplification}`
  5. `afs_next_path ∈ A|B|C` (S02 p.20)
- `citations[{id, source ∈ S01..S06|TABLE|DOCX|EXTERNAL, page, quote?, url?, support_check ∈ verified|page_only|unverified}]`
  - For **EXTERNAL** sources, `quote` and `url` are mandatory.
- `verification{citations_checked, unsupported_claims_removed[], flagged[], unsupported_numbers[], critic_issues[]}`, `run_meta{model, effort, prompt_hash, git_commit, timestamp}`

## 4. Knowledge base design
- **`kb/build.py`** (run locally; output in a gitignored `kb/cache/`):
  - PDFs are split into one chunk per page (`S01:p10`) with pypdf.
  - The docx is split into sections and D-cases.
  - The xlsx becomes structured rows, including the **cost / sensitivity / selectivity** ratings.
  - S02 is transcribed once per slide by a vision call to Claude, then spot-checked.
- **`kb/facts.yaml`** (committed; written by us as short paraphrases with page references):
  - Methods, fiber families (S02 p.6), probe types, application cases, architectures (S02 p.18) and the AFS pathway A/B/C (S02 p.20, S05).
  - **General rules, each with a source:**
    - Fluorescence needs a defined fluorescent species [S01 p.5].
    - Sensitivity ≠ selectivity [S01 Table 1].
    - Calibrations are matrix-specific [S01 p.10].
    - Optical density ≠ viable cell count [DOCX §5].
    - A lab or in-vitro study is not proof of process or clinical readiness [DOCX §3; S03 p.10, 14].
    - A nominal method range is not the range of an instrument or fiber [DOCX §3].
    - Any gain from combining methods is a hypothesis to test [S01 p.7–9].
    - Fiber family determines which wavelengths reach the probe [S02 p.6].
    - Few-wavelength sensors can replace full spectra after lab work [S01 p.9; S03 p.2, 14; S04 p.4].
    - Simple sensors suffice once a process is stable [S02 p.4].
- **Expert guidance from the Q&A** (domain reference §A) goes into the **system prompt as design principles**: the process-doctor approach, the simplicity ladder, chemometrics last, the plan stages, and the GMP and sterilizability considerations for scale-up. **It is not a citable source in outputs.** Technical claims must still cite the materials.
- **The domain primer** (§B) informs how we write prompts and schemas. If it disagrees with the materials, the materials win.
- **No case-specific notes about H01–H06 exist in the repo or the prompts** (see §7).
- **Retrieval:** none. The full corpus (about 60–80k tokens) goes in as a prompt-cached prefix with chunk IDs.

## 5. Reasoning pipeline
| Option | Pros | Cons |
|---|---|---|
| A. One prompt with all documents | Fastest | Not checkable; overconfident |
| B. Vector-store RAG | Scales | Misses tables and slides; the corpus is too small to need it |
| **C. Staged pipeline: full-context KB, deterministic checks, verifier (recommended)** | Grounded, checkable, transparent | More components |

1. **Extract** (LLM, structured output): stated facts with exact enquiry quotes, targets, matrix and optical state, conditions, distance, existing equipment, **client premises**, unknowns.
2. **Questionnaire** (LLM, structured output): **5–10 questions** ordered method → setup → requirements. Each question records the assumption to use if it goes unanswered. In interactive mode, the pipeline pauses here for answers.
3. **Pre-analysis** (`rules.py`, pure Python, driven by `facts.yaml`; no case-specific logic):
   - Shortlists Table 1 rows by sample type.
   - Builds a fiber×method spectral compatibility matrix and flags any fiber the client stated.
   - Runs the **simplicity ladder**: candidates are ordered by Table 1 cost, the number of methods, and the fiber or probe complexity.
   - Lists the general rules that may apply.
4. **Assess** (`claude-opus-5-5`, adaptive thinking, effort `high`, structured output):
   - Recommends the **simplest single method that plausibly fits**.
   - Adds a second method only with a stated `combination_trigger`.
   - Never recommends the expensive option without a reason, and doesn't default to Raman because it's popular.
5. **Verify** (the no-hallucination self-check):
   - Each citation must name an existing page.
   - An LLM support check asks: does this page directly support this claim? Where a quote is given, it is fuzzy-matched against the page text (rapidfuzz ≥ 90).
   - Claims that fail are **removed or flagged**, never silently kept.
   - Numbers and units are cross-checked against the sources and the enquiry.
   - A critic call checks the answer against the docx common mistakes and the simplicity ladder. One revision runs at most.
6. **Render:** JSON + Markdown to `outputs/`, plus the Streamlit view.

## 6. Citations and uncertainty
- **AFS materials:** `document + page` is enough, if that page directly supports the claim (Q&A A5). Use the format `S01 p.10`, `S01 Table 1 (p.6)`, `S02 p.13`. Quotes are optional but encouraged, since they enable automatic checking.
- **External sources:** the citation **and** the quoted passage + URL are mandatory. Keep them to a minimum.
- **Decision status:**
  - `insufficient_information` when the target, matrix or contaminant is undefined. Even then, the answer still includes the questionnaire and a lab screening step.
  - `outside_supported_scope` when the request goes beyond the evidence, for example clinical use.
  - Otherwise `provisional_assessment`, with its assumptions listed.
- Each recommendation carries a confidence level (low/med/high) with a reason.

## 7. Evaluation plan
- **Development set:**
  - D01–D08 (D01 and D02 are the quality bar).
  - The brief's soil example.
  - 3–4 generic probe enquiries written by us: out of scope, too little information, a false premise, and an **upsell trap** where a simple method suffices.
- **Automatic metrics** (`eval/run_eval.py`):
  - schema validity, and a questionnaire of 5–10 items in the correct impact order
  - citation support rate; unsupported numbers
  - **a combination recommended without a trigger counts as a failure**
  - decision-status sanity
- **LLM judge rubric:** the docx §3 checklist, the common mistakes and the jury weights, plus "simplest sufficient method" and "plan follows the four stages".
- **Manual review** of the D outputs.
- **H-blind rule:**
  - No prompt or rule change may be motivated by H outputs.
  - No H-specific expectations are written down in the repo or used for tuning.
  - H01–H06 are generated once from a tagged commit (`run-all --set H`, one-shot mode), logged, and **never edited**.

## 8. Prototype, stack and keys
- **Stack:** Python 3.11 venv with `anthropic`, `pydantic`, `pypdf`, `python-docx`, `openpyxl`, `pyyaml`, `rapidfuzz`, `streamlit`.
- **`src/afs_assistant/`:** `llm.py` (provider wrapper: `LLM_PROVIDER=anthropic|bedrock`), `kb/`, `schema.py`, `questionnaire.py`, `rules.py`, `pipeline.py`, `verify.py`, `render.py`, `cli.py`.
- **Streamlit flow:**
  1. Enter an enquiry, or pick a D/H case.
  2. The questionnaire appears, with an answer box per question and a skip option.
  3. The recommendation is shown in tabs, with a sources panel and the verification report.
  4. A "one-shot" toggle skips the questionnaire pause.
- **Model:** `claude-opus-5-5` with adaptive thinking, streaming and the cached KB prefix; settings are logged per run.
- Keys live in `.env`. One-command reproduction: `make kb && make h`.

## 9. Timeline (solo)
| When | Work |
|---|---|
| Sat (done) | PRD, Q&A slot, domain reference |
| Sat → 20 | Scaffold; knowledge-base build (extraction, S02 transcription, `facts.yaml`); schema; extract + questionnaire + rules; D01 one-shot end to end |
| Sat 20–24 | Assess with simplicity ladder; verifier + critic; renderer; full D01–D08 run |
| Sun 09–13 | Evaluation harness and judge; probe enquiries; iteration; Streamlit with interactive mode |
| Sun 13–14 | **Freeze, tag, generate H01–H06** (one-shot), commit outputs |
| Sun 14–20 | README, `architecture.md`, slides (PDF), demo video under 5 min (show interactive mode + the no-hallucination check) |
| Sun 20–23:59 | Buffer and submission |

## 10. Risks and open points
- **Risks:**
  - S02 transcription errors. *Mitigation:* spot-check slides 6, 7, 13, 14, 16 and 18.
  - Over-cautious answers. *Mitigation:* the contract requires the simplest method worth testing plus a lab screening step.
  - The questionnaire grows too long or generic. *Mitigation:* a hard cap of 10 questions, each with a `why`, ordered by impact.
  - Cost and latency (now one extra LLM step). *Mitigation:* caching; at most one revision.
  - Perception of hard-coding. *Mitigation:* general rules with sources; no H-specific notes in the repo; the policy is documented.
  - Copyright. *Mitigation:* the KB cache is gitignored, outputs carry page citations with short quotes only, and **the publishing question remains open**. We stay conservative.
  - The LLM provider is undecided. *Mitigation:* the wrapper.
- **Still open after the Q&A:**
  - Permission to publish quotes and slide notes.
  - Whether to name products at model level (default: probe-type level).
  - MIR fiber link lengths (default: never state a length; ask the client).

## Verification (end to end)
1. The knowledge-base build produces chunk counts per source; spot-check S02.
2. `run --case D01` (one-shot) produces valid JSON and Markdown: 5–10 questions, a plan with four stages, every citation support-checked. Compare with the D01 reference.
3. `eval/run_eval.py --set D` produces metrics and judge scores; iterate.
4. Streamlit interactive mode: a free-text enquiry, then the questions, the answers, and a recommendation in under about 2 minutes.
5. A clean clone plus the README reproduces `run-all --set H`.

## Status
Rev 1 approved Sat 17 Oct. Rev 2 (post-Q&A) approved Sat 17 Oct.
