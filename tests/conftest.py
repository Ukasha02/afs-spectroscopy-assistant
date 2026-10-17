import pytest

from afs_assistant import schema


def st(text, basis="sourced", refs=(), quote=None):
    return {"text": text, "basis": basis, "citations": [{"ref": r, "quote": quote, "url": None} for r in refs]}


@pytest.fixture
def extraction():
    return schema.ExtractedEnquiry(
        summary="s",
        stated_facts=[],
        targets=["moisture"],
        sample_description="bulk powder",
        sample_state="powder",
        process_context="production",
        conditions=[],
        measurement_location=None,
        remote_measurement=True,
        contact_with_sample="unknown",
        analyzer_distance=None,
        existing_equipment=[],
        methods_mentioned=["MIR"],
        fibers_mentioned=["SILICA_UNSPECIFIED"],
        client_premises=[],
        requested_decision="d",
        unknowns=[],
    )


@pytest.fixture
def make_assessment():
    """Minimal valid Assessment; override parts via keyword arguments."""

    def _make(**over):
        plan_st = st("agree with client", "assumption")
        data = {
            "decision_status": "provisional_assessment",
            "status_reason": "r",
            "summary_for_expert": "s",
            "constraints": [],
            "key_unknowns": [],
            "premise_checks": [],
            "method_table_screening": [],
            "recommendations": [],
            "measurement_concept": {
                "probe_type": "p", "geometry": "g", "location": "l", "fiber_family": "f",
                "fiber_compatible": None, "architecture": "undecided", "rationale": [],
            },
            "risks": [],
            "assumptions": [],
            "feasibility_plan": {
                "objective": "o", "methods_screened": [], "methods_compared": [],
                "steps": [{"stage": "lab_screening", "aspect": "samples", **plan_st}],
                "afs_next_path": "A", "afs_next_path_reason": "r",
            },
        }
        data.update(over)
        return schema.Assessment.model_validate(data)

    return _make
