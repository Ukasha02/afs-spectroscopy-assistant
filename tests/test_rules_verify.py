import pytest

from afs_assistant import config, rules, schema
from afs_assistant.kb.text import match_key
from afs_assistant.verify import _number_known, _numbers, verify, verify_questions
from conftest import st

needs_cache = pytest.mark.skipif(not config.CHUNKS_PATH.exists(), reason="run `make kb` first")
ENQ = "We measure moisture in a bulk powder from a control room."


def claims(statements):
    """Wrap test claims in a premise check (any labelled claim is verified the same way)."""
    return [{"client_claim": "c", "verdict": "plausible_to_be_tested", "explanation": statements}]


def flags(a, shortlist=()):
    """Verifier flags, ignoring the questionnaire-count check (these tests pass no questions)."""
    return [f for f in verify(a, ENQ, [], list(shortlist)).flags if f.kind != "questionnaire"]


@needs_cache
def test_shortlist_uses_table_rows_and_keeps_distance_row(extraction):
    rows = [r["row"] for r in rules.table_shortlist(extraction)]
    assert "NIR spectroscopy / surface at a distance" in rows
    assert "NIR spectroscopy / diffuse reflection probe" in rows
    assert not any(r.startswith("IR spectroscopy / ATR") for r in rows)  # ATR is for liquid/paste/soft


@needs_cache
def test_shortlist_is_ordered_by_cost(extraction):
    order = {"low": 0, "average": 1, "high": 2}
    costs = [order[r["cost"]] for r in rules.table_shortlist(extraction)]
    assert costs == sorted(costs)


@needs_cache
def test_silica_fiber_conflicts_with_mir(extraction):
    conflicts = rules.fiber_checks(extraction)["client_fiber_conflicts"]
    assert conflicts and all("coverage none" in c for c in conflicts)
    assert rules.fiber_checks(extraction)["per_method"]["NIR"]["fibers"]["VISNIR_SILICA"].startswith("partial")


@needs_cache
def test_verified_quote_and_sourced_number_pass(make_assessment):
    a = make_assessment(premise_checks=claims([st("NIR covers 780-2500 nm.", refs=["S01 p.10"], quote="NIR spectra (780–2500 nm) contain predominantly overtones")]))
    v = verify(a, ENQ, [], [])
    assert flags(a) == []
    assert v.counts["citations_verified"] == 1


@needs_cache
def test_invented_number_is_flagged(make_assessment):
    a = make_assessment(premise_checks=claims([st("Moisture between 0-30% is typical.", refs=["S01 p.10"])]))
    kinds = {(f.kind, f.detail.split("'")[1]) for f in flags(a)}
    assert ("number", "30%") in kinds


@needs_cache
def test_number_from_uncited_page_is_flagged(make_assessment):
    """100-300 m is on S02 p.7, but this statement cites S01 p.10."""
    a = make_assessment(premise_checks=claims([st("Cables reach 100-300 m.", refs=["S01 p.10"])]))
    assert any(f.kind == "number" for f in verify(a, ENQ, [], []).flags)


@needs_cache
def test_fake_quote_and_unknown_source_are_flagged(make_assessment):
    a = make_assessment(
        premise_checks=claims([
            st("x", refs=["S01 p.10"], quote="Raman is always the best method for powders"),
            st("y", refs=["S09 p.3"]),
        ])
    )
    v = verify(a, ENQ, [], [])
    assert {"quote", "unsupported_sourced_claim"} <= {f.kind for f in v.flags}
    assert v.counts["citations_quote_not_found"] == 1 and v.counts["citations_unknown_source"] == 1


@needs_cache
def test_supported_verdict_on_limited_scope_source_is_flagged(make_assessment):
    a = make_assessment(
        premise_checks=[{"client_claim": "c", "verdict": "supported", "explanation": [st("study shows it", refs=["S03 p.14"])]}]
    )
    assert any(f.kind == "scope" for f in verify(a, ENQ, [], []).flags)


@needs_cache
def test_business_source_cannot_back_technical_claim(make_assessment):
    a = make_assessment(premise_checks=claims([st("covers 0.3-16 um", refs=["S05 p.1"])]))
    assert any(f.kind == "scope" for f in verify(a, ENQ, [], []).flags)


@needs_cache
def test_unscreened_table_row_is_flagged(make_assessment, extraction):
    shortlist = rules.table_shortlist(extraction)
    v = verify(make_assessment(), ENQ, [], shortlist)
    assert sum(f.kind == "table_coverage" for f in v.flags) == len(shortlist)


def q(i, topic, text="?", fallback="unknown"):
    return schema.Question(id=f"Q{i}", topic=topic, question=text, why="w", assumption_if_unanswered=fallback)


def test_unit_conversion_and_small_numbers_with_units():
    assert ("3", "m") in _numbers("Assume 3 to 10 m of cable") and ("10", "m") in _numbers("Assume 3 to 10 m of cable")
    assert _numbers("compare 2 methods") == []
    assert _number_known("2.5", "um", match_key("4000–400 cm-1"))
    assert _number_known("2400", "nm", match_key("silica 0.35-2.4 um"))


def test_questionnaire_numbers_and_order_are_flagged():
    good = [q(1, "pain_goal"), q(2, "target_and_level"), q(3, "sample_form_optics"), q(4, "process_conditions"), q(5, "requirements")]
    assert verify_questions(good, ENQ) == []
    bad = [q(1, "requirements"), q(2, "pain_goal", fallback="Assume 2-5% w/w API"), *good[2:5]]
    kinds = [f.kind for f in verify_questions(bad, ENQ)]
    assert kinds.count("questionnaire") == 1 and kinds.count("number") == 2


@needs_cache
def test_strict_assumption_numbers(make_assessment):
    a = make_assessment(assumptions=["Fat is between 4% and 15% w/w."])
    assert any(f.kind == "number" and f.path.startswith("assumptions") for f in flags(a))


def rec(method="NIR", role="primary", basis="sourced", reason="Supported by an application example.", caveat="Calibration must be built.", confidence="medium"):
    return {"method": method, "geometry": "g", "role": role, "simplicity_rank": 1, "cost_complexity": "average",
            "reason": st(reason, basis, refs=["S01 p.17"] if basis == "sourced" else [], quote="Inline NIR Reflection is primarily used for opaque or highly concentrated dairy products"), "caveat": st(caveat, "sourced", refs=["S01 p.10"]),
            "confidence": confidence, "confidence_reason": "r"}


@needs_cache
def test_recommendation_needs_sourced_reason(make_assessment):
    assert any(f.kind == "basis" for f in flags(make_assessment(recommendations=[rec(basis="general_knowledge")])))


@needs_cache
def test_worked_examples_are_not_citable(make_assessment):
    from afs_assistant.kb.load import render_corpus

    assert 'cite="DOCX §2' not in render_corpus()
    a = make_assessment(premise_checks=claims([st("A calibration must be built.", refs=["DOCX §2 D01"])]))
    assert any(f.kind == "scope" and "worked answer" in f.detail for f in flags(a))


@needs_cache
def test_lab_study_supports_premise_only_in_stated_research_context(make_assessment):
    pc = [{"client_claim": "c", "verdict": "supported", "explanation": [st("fused data separated the tissues", refs=["S04 p.4"])]}]
    a = make_assessment(premise_checks=pc)
    assert not [f for f in verify(a, ENQ, [], [], "research_lab").flags if f.kind == "scope"]
    assert [f for f in verify(a, ENQ, [], [], "production").flags if f.kind == "scope"]
    assert [f for f in verify(a, ENQ, [], [], "clinical_or_medical").flags if f.kind == "scope"]


@needs_cache
def test_fiber_conflict_only_without_coverage(extraction):
    fc = rules.fiber_checks(extraction)  # MIR over silica: no coverage -> conflict
    assert fc["client_fiber_conflicts"] and rules.fiber_findings(fc)
    nir = extraction.model_copy(update={"methods_mentioned": ["NIR"]})
    fc = rules.fiber_checks(nir)  # NIR over silica: partial (0.78-2.4 of 2.5 um) -> note, not conflict
    assert not fc["client_fiber_conflicts"] and fc["client_fiber_notes"]
    ok, text, refs = rules.fiber_verdict(["NIR (diffuse reflection)"], nir, fc)
    assert ok is True and "partial" in text and "S01 p.10" in refs  # client named a fiber: detailed check
    none = nir.model_copy(update={"fibers_mentioned": []})
    ok, text, refs = rules.fiber_verdict(["NIR"], none, rules.fiber_checks(none))
    assert ok is None and text == rules.DEFAULT_FIBER_LINE and refs == ["S02 p.6"]  # default: one short line
    ok, text, refs = rules.fiber_verdict(["MIR ATR"], none, rules.fiber_checks(none))
    assert "PIR" in text  # MIR recommended: detailed check


@needs_cache
def test_any_docx_citation_is_flagged_and_docx_is_not_in_corpus(make_assessment):
    from afs_assistant.kb.load import render_corpus

    assert 'cite="DOCX' not in render_corpus()
    for ref in ("DOCX §3", "DOCX §5"):
        a = make_assessment(premise_checks=claims([st("guidance claim", refs=[ref])]))
        assert any(f.kind == "scope" and "challenge reference" in f.detail for f in flags(a))
