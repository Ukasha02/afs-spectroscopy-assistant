import pytest

from afs_assistant import config
from afs_assistant.rubric import rubric
from conftest import st
from test_rules_verify import rec

needs_cache = pytest.mark.skipif(not config.CHUNKS_PATH.exists(), reason="run `make kb` first")


def failed(a, required=()):
    return {i.check for i in rubric(a, "T", list(required)) if not i.passed}


@needs_cache
def test_fixture_passes_structure_checks(make_assessment):
    a = make_assessment(recommendations=[rec()], spectral_ranges=[{"method": "NIR", "nominal_range": "780-2500 nm", "citation": {"ref": "S01 p.10", "quote": None, "url": None}, "note": None}])
    # Only length fails for the tiny fixture.
    assert failed(a) == {"report length 250-450 words"}


@needs_cache
def test_combination_must_be_a_hypothesis(make_assessment):
    a = make_assessment(recommendations=[rec(), rec("NIR + Raman", "combination", caveat="Gives better accuracy.")])
    assert "combination framed as hypothesis" in failed(a)
    a = make_assessment(recommendations=[rec(), rec("NIR + Raman", "combination", caveat="Only after each method is assessed alone; a hypothesis to test.")])
    assert "combination framed as hypothesis" not in failed(a)


@needs_cache
def test_high_confidence_with_unknowns_fails(make_assessment):
    assert "no 'high' confidence while unknowns remain" in failed(make_assessment(recommendations=[rec(confidence="high")]))


@needs_cache
def test_required_risks_and_plan_elements(make_assessment):
    a = make_assessment(risks=[{"category": "nothing_confirmed", "text": "t", "basis": "general_knowledge", "citations": []}])
    assert "standard risk categories" in failed(a, ["calibration_validity", "nothing_confirmed"])
    plan = {"steps": [{"element": "comparison", "text": "compare", "basis": "proposal", "citations": []}], "afs_next_path": "A", "afs_next_path_reason": "r"}
    assert "feasibility plan: 4 elements" in failed(make_assessment(feasibility_plan=plan))


@needs_cache
def test_question_order(make_assessment):
    qs = [{"question": "q?", "covers": c} for c in ["reference", "measured", "variation", "requirements"]]
    assert "4-10 prioritised questions" in failed(make_assessment(report_questions=qs))
