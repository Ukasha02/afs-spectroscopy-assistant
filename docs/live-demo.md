# Live mode: checklist for the presentation and the jury window

The hosted app runs in library mode by default (`LIVE_ENABLED=false`: no API key, no cost). Live mode
lets someone type a new enquiry and run the full pipeline. There are two ways to use it.

## A. We run an enquiry during the presentation (always available)

```bash
.venv/bin/streamlit run app/streamlit_app.py
```

Local `.env` needs `LIVE_ENABLED=true`, `ACCESS_CODE=...` and the final models (`MODEL_ASSESS` and
`MODEL_REVISE` = `claude-opus-5-5`). A run takes about 2 minutes and costs about $0.35–0.50. Toggle
"Ask clarification questions first" to show the diagnostic questionnaire.

## B. The jury types their own enquiries into the hosted app (19–20 Oct)

**Switch on** (Streamlit Community Cloud → the app → Settings → Secrets; the app restarts in seconds):

```toml
KB_REPO = "Ukasha02/afs-kb-private"
KB_TOKEN = "github_pat_..."              # read-only token for the private KB repo
LIVE_ENABLED = "true"
ACCESS_CODE = "<code given in the submission>"
ANTHROPIC_API_KEY = "<key>"
LLM_PROVIDER = "anthropic"
MODEL_INTAKE = "claude-haiku-5-5"
MODEL_CRITIC = "claude-haiku-5-5"
MODEL_ASSESS = "claude-opus-5-5"
MODEL_REVISE = "claude-opus-5-5"
EFFORT_INTAKE = "low"
EFFORT_CRITIC = "low"
EFFORT_ASSESS = "medium"
EFFORT_REVISE = "medium"
LIVE_RUNS_PER_SESSION = "3"
BUDGET_LIMIT_USD = "<committed ledger total + 10>"   # see `python -m afs_assistant.cli spend`
```

**Guards:**
- The access code, shared only with the jury.
- 3 live runs per browser session.
- The app's budget cap. The deployed app starts from the committed ledger (`outputs/spend.json`), so
  "total + 10" stops live runs after about $10. This resets only if Streamlit restarts the container.
- The Anthropic Console spend limit on the key, if set.

**Text for the submission form:**
> Web app: https://afs-spectroscopy-assistant.streamlit.app/ · Results library: all generated answers
> (H01–H06, D01–D08, our hard cases), no login. Live mode: open "Assessment", enter the access code
> `<code>`, type an enquiry, and press "Run assessment" (about 2 minutes; optionally answer the
> clarification questions first).

**Before the window:**
1. Open the app (it may be asleep: first load takes about 1 minute).
2. Enter a wrong access code: "Wrong access code" appears.
3. Enter the right code and run one short enquiry. The progress steps appear and the report renders,
   with the cost shown in the footer.
4. Check that the "x of 3 live runs left" counter decreases.

**After the window:** set `LIVE_ENABLED = "false"` and remove `ANTHROPIC_API_KEY`.
