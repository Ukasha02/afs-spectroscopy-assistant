import json

import pytest
from pydantic import ValidationError

from afs_assistant import schema


@pytest.mark.parametrize("model", [schema.ExtractedEnquiry, schema.Questionnaire, schema.Assessment])
def test_llm_schemas_are_non_recursive(model):
    """Structured outputs reject recursive schemas; $defs must not reference themselves."""
    js = model.model_json_schema()
    for name, definition in js.get("$defs", {}).items():
        assert f'"#/$defs/{name}"' not in json.dumps(definition), f"{name} is recursive"


def test_questionnaire_length_is_enforced():
    q = {"id": "Q1", "question": "?", "why": "w", "impact": "method", "assumption_if_unanswered": "a"}
    with pytest.raises(ValidationError):
        schema.Questionnaire(questions=[q] * 4)
    with pytest.raises(ValidationError):
        schema.Questionnaire(questions=[q] * 11)
    assert len(schema.Questionnaire(questions=[q] * 5).questions) == 5
