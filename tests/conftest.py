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
        prop = lambda element, text: {"element": element, "text": text, "basis": "proposal", "citations": []}
        data = {
            "decision_status": "provisional_assessment",
            "status_reason": "r",
            "requirements_stated": ["powder blend"],
            "key_unknowns": ["concentration range"],
            "premise_checks": [],
            "report_questions": [{"question": f"q{i}?", "covers": c} for i, c in enumerate(["measured", "reference", "variation", "requirements"])],
            "recommendations": [],
            "method_table_screening": [],
            "measurement_concept": {"items": [], "fiber_family": "f", "fiber_compatible": None, "architecture": "undecided", "needs_afs_confirmation": []},
            "spectral_ranges": [],
            "risks": [],
            "assumptions": [],
            "feasibility_plan": {
                "steps": [
                    prop("representative_samples", "Representative samples across the client-agreed range."),
                    prop("spectra_with_reference", "Spectra with independent reference measurements and timing information."),
                    prop("models_and_validation", "Single-method models first, validated on held-out batches."),
                    prop("comparison", "Compare prediction error and bias against the client's requirements."),
                ],
                "afs_next_path": "A", "afs_next_path_reason": "r",
            },
            "decision_basis": st("Criteria agreed with the client; choose the simplest configuration.", "proposal"),
        }
        data.update(over)
        return schema.Assessment.model_validate(data)

    return _make
