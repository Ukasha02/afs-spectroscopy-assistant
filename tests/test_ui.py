"""UI smoke tests: render saved reports and the app headless, without any API call."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from afs_assistant.schema import CaseResult  # noqa: E402

SAVED = sorted((ROOT / "outputs").glob("D0*.json"))
needs_saved = pytest.mark.skipif(not SAVED, reason="no saved outputs")


@needs_saved
def test_report_html_renders_all_sections():
    from report_html import report_html, rule_panel

    r = CaseResult.model_validate_json(SAVED[0].read_text())
    html = report_html(r)
    for section in ("Requirements stated", "Key unknowns", "Clarification questions", "recommendation",
                    "Measurement concept", "Spectral range", "Risks and uncertainty", "First feasibility experiment",
                    "Decision basis", "Sources"):
        assert section in html, section
    assert 'class="chip' in html and "<summary>" in html  # clickable citation chips
    assert "banner st-" in html
    assert "rule-row" in rule_panel(r)


@needs_saved
def test_excerpts_are_short():
    from report_html import EXCERPT_CHARS, _excerpt

    assert len(_excerpt("S01 p.10", None)) <= EXCERPT_CHARS + 1


def test_app_runs_headless_in_library_mode(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.delenv("ACCESS_CODE", raising=False)
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=60).run()
    assert not at.exception
    assert any("First technical assessment" in t.value for t in at.title)
