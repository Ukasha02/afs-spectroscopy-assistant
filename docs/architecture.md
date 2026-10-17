# System architecture

_Skeleton. This will be finalized once the pipeline is built. The design rationale is in [PRD.md](PRD.md) §3–5._

```
enquiry (free text)
   │
   ▼
1. Extract        LLM, structured output → stated facts (with quotes from the enquiry), targets, matrix,
                  conditions, existing equipment, client premises, unknowns
   │
   ▼
2. Pre-analysis   Pure Python, driven by kb/facts.yaml (no logic for specific cases):
                  Table 1 technique shortlist · fiber × spectral-range compatibility · applicable general rules
   │
   ▼
3. Assess         claude-opus-5-5, full AFS corpus as a cached context prefix (no retrieval)
                  → full answer schema; every claim cites source + page + quote
   │
   ▼
4. Verify         quote ↔ page text fuzzy match · unsupported-number check · critic pass (1 revision max)
   │
   ▼
5. Render         outputs/<case>.json + .md · Streamlit view with a sources panel
```

## How the AFS materials are used

| Material | Processing | Role |
|---|---|---|
| S01, S03, S04, S05 (PDF) | Text per page (pypdf) → `kb/cache/` (gitignored) | Main evidence; cited as `S01 p.N` |
| S02 slides | Vision transcription per slide → `kb/cache/` | Fiber ranges, probes, applications; cited as `S02 p.N` |
| `AFS_method_comparison_table.xlsx` | Structured rows | Technique shortlist; cited as `S01 Table 1 (p.6)` |
| `AFS_Examples_and_Reference.docx` | Sections + D-cases | Answer contract, good practice, dev set |
| `kb/facts.yaml` (committed, written by us) | Hand-curated facts and general rules, each with a page reference | Deterministic checks |

_To be completed: prompts, schema, verification metrics, cost/latency._
