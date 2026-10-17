# PRD: AFS Spectroscopy Assistant

## Context
SchubKI Hackathon, Challenge 01 (Art Fiber Systems). We're building an assistant that helps an AFS expert make a first technical assessment of a customer enquiry. For each enquiry it gives requirements, clarification questions, recommended methods, a probe concept, risks and uncertainty, and a feasibility plan, with traceable citations to the AFS materials. Deadline is **Sun 18 Oct 23:59**. The team is one person (solo). The repo exists: `github.com/Ukasha02/afs-spectroscopy-assistant`.

**What I learned from reading all the materials** (these findings shape the design):
- **The H01–H06 cases test judgement more than method lookup.** They probe a calibration reused after a formulation change, two streams with different optical behaviour, fluorescence with no fluorophore, silica fiber requested for MIR, an undefined problem, and an in-vitro study quoted as proof for surgical use. The organizers say so directly: *"Some enquiries ask for more certainty than the facts allow. A good answer notices this."* So the core of the system is **premise checking, scope discipline and honest uncertainty**, not retrieving the right method.
- **The docx sets the expected answer contract.** It has a section structure; a decision status (*provisional / insufficient information / outside scope*); a "do not invent" list (no performance figures, fiber lengths, product codes or guarantees); a citation format (`S01 p.10`, `S01 Table 1 (p.6)`, `S02 p.13`); and a common-mistakes list. D01 and D02 are worked reference answers.
- **The corpus is small**, about 50 pages in total. S02 is mostly images and needs a vision transcription. The xlsx is a clean version of S01 Table 1.
- **S01 p.19 forbids redistribution:** "No part of this publication may be reproduced, distributed…". So full-text knowledge-base dumps stay out of git.

## 1. Users and success criteria
The user is an AFS application expert preparing a first customer call. Success criteria, mapped to the jury weights:
| Criterion (weight) | How we meet it |
|---|---|
| Technical quality (30%) | Deterministic domain checks (fiber vs. spectral range, sample type vs. Table 1 geometry) feed the LLM. A critic pass reviews the result against the common-mistakes list. |
| Use of AFS knowledge (20%) | The whole AFS corpus sits in context. Every claim carries `source/page + quote`, and the quote is **checked automatically** against the page text. |
| Feasibility plan (15%) | A fixed plan schema covering representative samples, an independent reference method, single-method then fused comparison, and go/no-go criteria agreed with the client (never invented numbers). The plan ends with the AFS Path A/B/C. |
| Clarification & uncertainty (15%) | A premise-check section; prioritised questions, each tagged with what its answer could change; a decision status; claims labelled `client_fact / sourced / general_knowledge / assumption`. |
| Explainability (10%) | Client facts, sourced claims, assumptions and proposals are kept visibly separate. The Streamlit view has a clickable sources panel and a verification report. |
| Prototype (10%) | A Streamlit app with free-text input, a D/H case picker, and run times under about 2 minutes. |

## 2. Output schema (one scenario, validated with pydantic, JSON + Markdown)
`case_id, enquiry, decision_status ∈ {provisional_assessment, insufficient_information, outside_supported_scope}, status_reason`
- `requirements`: `stated_facts[{fact, enquiry_quote}]`, `constraints[]`, `key_unknowns[]`
- `premise_checks[{client_claim, verdict ∈ supported|contradicted|unverifiable, explanation, citations}]`
- `clarification_questions[{question, why, could_change ∈ method|setup|feasibility, priority 1–3}]`
- `recommendations[{method, technique_geometry, role ∈ primary|comparison|combination|not_recommended, rationale, conditions, spectral_range{value, unit, note: "nominal method range, not instrument range"}, confidence, citations}]`
- `measurement_concept{probe_type, geometry, location, fiber_link{family, compatible: bool, check_note}, architecture ∈ centralized|iot|undecided, citations}`
- `risks[{risk, type ∈ technical|assumption|evidence_scope, mitigation}]`, `assumptions[]`
- `feasibility_plan{objective, samples, reference_measurements, steps[], comparison, decision_basis, afs_next_path}`
- `citations[{id, source ∈ S01..S06|TABLE|DOCX|EXTERNAL, page, quote, url?, verified: bool}]`, where each claim references a citation id
- `verification{citations_verified, unverified[], unsupported_numbers[], critic_issues[]}`, `run_meta{model, effort, prompt_hash, git_commit, timestamp}`

## 3. Knowledge base design
- **`kb/build.py`** (run locally; output in a gitignored `kb/cache/`):
  - PDFs are split into one chunk per page (`S01:p10`) with pypdf.
  - The docx is split per section and per D-case.
  - The xlsx becomes one structured row per measurement technique.
  - **S02 is transcribed once per slide by a vision call to Claude** and cached. A human spot-checks the result.
- **`kb/facts.yaml`** (committed, written by us, short paraphrases plus page references, no long verbatim text):
  - Methods, with nominal range, typical samples and limitations.
  - Fiber families and their ranges (S02 p.6).
  - Probe types: ATR, diffuse reflection, transmission/transflection, Raman, fluorescence, combi-probes.
  - Application cases (S01 p.13–18; S02 p.13–14).
  - Architectures (S02 p.18) and the AFS pathway A/B/C (S02 p.20, S05).
  - **General rules**, each with a source, for example:
    - Fluorescence needs a defined fluorescent species [S01 p.5].
    - Calibrations are matrix-specific [S01 p.10; D01].
    - Optical density is not a viable cell count [DOCX §5].
    - A lab or in-vitro study is not proof of process or clinical readiness [DOCX §3; S03 p.10, 14].
    - A nominal method range is not the range of an instrument or fiber [DOCX §3].
    - Any gain from combining methods is a hypothesis to test [S01 p.7–9; D01].
    - Fiber family determines which wavelengths reach the probe [S02 p.6].
- **Retrieval:** none. The full corpus (about 60–80k tokens) goes into the prompt as a **prompt-cached** prefix with chunk IDs, so nothing is missed by retrieval. `facts.yaml` drives the deterministic checks.

## 4. Reasoning pipeline (three options compared)
| Option | Pros | Cons |
|---|---|---|
| A. One prompt with all documents | Fastest to build | Not checkable; overconfident; citations can't be verified |
| B. Vector-store RAG | Scales to large corpora | Retrieval misses tables and slides; the corpus is too small to need it; harder to explain |
| **C. Staged pipeline: full-context KB, deterministic checks, verifier (recommended)** | Grounded and checkable; the rules are transparent and testable | More components (manageable) |

**Pipeline C:**
1. **Extract** (LLM, structured output). Pulls out stated facts with exact quotes from the enquiry, targets, matrix and optical state, location and distance, existing equipment, **client claims and premises**, and unknowns.
2. **Pre-analysis** (`rules.py`, pure Python, data-driven from `facts.yaml`; nothing in it is specific to any case):
   - Shortlists Table 1 rows that match the sample type.
   - Builds a fiber×method spectral compatibility matrix and flags any fiber the client stated.
   - Lists the general rules that may apply.
3. **Assess** (`claude-opus-5-5`, adaptive thinking, effort `high`, structured output). The prompt contains the system contract and do-not-invent list, the cached KB, `facts.yaml`, the pre-analysis output and the extraction. The result is the full schema.
4. **Verify:**
   - Each citation's quote is fuzzy-matched (rapidfuzz ≥ 90) against the cited page text, with the result marked verified or unverified.
   - Numbers and units are cross-checked against the sources and the enquiry.
   - A **critic call** checks the answer against the docx common-mistakes list. If it finds issues, one revision pass runs.
5. **Render:** Markdown and JSON to `outputs/`, plus the Streamlit view.

The native Citations API can't be combined with structured outputs, so we use our own quote-verification step instead. That is also more transparent for the jury.

## 5. Citations and uncertainty
- Citation format follows the docx: `S01 p.10`, `S01 Table 1 (p.6)`, `S02 p.13`.
- External sources are allowed only with `quote + url`, are labelled EXTERNAL, and are kept to a minimum.
- **When to ask and when to answer.** Always give a conditional shortlist with the assumptions stated. Set `insufficient_information` when the target or matrix is undefined, and `outside_supported_scope` when the request goes beyond what the evidence covers (for example clinical use). Questions that could change the method come first.
- Confidence (low/med/high) is attached to each recommendation, with a reason.

## 6. Evaluation plan
- **Development set:** D01–D08 (reference answers exist for D01 and D02 only), plus the brief's soil example and 3–4 generic probes we write ourselves: an out-of-scope request, an enquiry with too little information, and an enquiry with a false premise. These are deliberately **not** modelled on H cases.
- **`eval/run_eval.py` automatic metrics:** schema validity, share of citations verified, unsupported numbers, number of questions, decision-status sanity.
- **LLM judge rubric:** built from the docx §3 checklist and the jury weights, plus a comparison against the D01 and D02 references.
- **Manual review** of the D outputs by you for technical correctness.
- **H-blind rule:** no prompt or rule change may be motivated by H outputs. H01–H06 are generated once from a tagged commit with `python -m afs_assistant run-all --set H`, logged in `outputs/run_log.json`, and **never edited**. The README states this policy.

## 7. Prototype, stack and keys
- **Python 3.11 in a venv:**
  - `anthropic`, `pydantic`, `pypdf`, `python-docx`, `openpyxl`, `pyyaml`, `rapidfuzz`, `streamlit`.
- **`src/afs_assistant/`:**
  - `llm.py` is a provider wrapper. `LLM_PROVIDER=anthropic|bedrock` selects `Anthropic()` or `AnthropicBedrockMantle`, so the provider stays open.
  - The other modules are `kb/`, `schema.py`, `rules.py`, `pipeline.py`, `verify.py`, `render.py` and `cli.py`.
- **App and evaluation folders:** `app/streamlit_app.py`, `eval/`.
- **Model:** `claude-opus-5-5` with adaptive thinking, streaming, and the KB prefix cached. The model ID and settings are logged with every run.
- Keys live in `.env` (gitignored), and `.env.example` documents both providers.
- One-command reproduction: `make kb && make h` (or the equivalent CLI commands).

## 8. Timeline (solo)
| When | Work |
|---|---|
| Sat → 12:00 | PRD approved; final Q&A questions; scaffold and venv |
| Sat 12–15:39 | **Q&A slot (10 min)**; knowledge-base build (extraction, S02 transcription, `facts.yaml`) |
| Sat 16–20 | Schema, extract, rules, assess; first D01 end to end |
| Sat 20–24 | Verifier, critic, renderer; full D01–D08 run; iteration |
| Sun 09–13 | Evaluation harness and judge; generic probes; iteration; Streamlit app |
| Sun 13–14 | **Freeze, tag, generate H01–H06**, commit outputs |
| Sun 14–20 | README, `architecture.md`, slides (PDF), demo video under 5 min |
| Sun 20–23:59 | Buffer and submission |

## 9. Risks and open questions
- **Risks:**
  - S02 transcription errors. *Mitigation:* manual spot-check of the key slides 6, 7, 13, 14, 16 and 18.
  - Over-cautious answers that recommend nothing. *Mitigation:* the contract requires at least one method or experiment worth testing.
  - Cost and latency. *Mitigation:* prompt caching and one revision round at most.
  - Perception of hard-coding. *Mitigation:* rules are general, each cites a source, and the policy is documented.
  - Copyright. *Mitigation:* the KB cache is gitignored and outputs contain only short quotes.
  - The LLM provider is still undecided. *Mitigation:* the provider wrapper.
- **Q&A questions** (written to `docs/qa-questions.md`):
  1. S01 states all rights reserved. May our public repo contain short quoted passages in the outputs and our own notes and transcriptions of the slides?
  2. Should recommendations name specific art photonics/AFS probe models, or stay at probe-type level? Are typical CIR/PIR fiber link lengths citable from you, or should the assistant always ask?
  3. For the live new enquiry, which format and time limit should we expect? Is a cached knowledge base with live LLM calls acceptable?

## Verification (end to end)
1. `python -m afs_assistant.kb.build` produces chunk counts per source; spot-check S02 slides 6 and 13.
2. `python -m afs_assistant run --case D01` produces valid JSON and Markdown, with ≥ 90% of citations verified, compared against the D01 reference.
3. `python eval/run_eval.py --set D` produces a metrics table and judge scores; we iterate until D01–D08 have no unverified central claims.
4. `streamlit run app/streamlit_app.py` runs a free-text enquiry live in under about 2 minutes.
5. From a clean clone: follow the README, run `run-all --set H`, and get identical structure in `outputs/`.

## Status
Approved Sat 17 Oct 2026. Implementation follows the timeline in §8.
