import json

import pytest
from google import genai
from google.genai import _transformers as t
from pydantic import ValidationError

from afs_assistant import schema


@pytest.mark.parametrize("model", [schema.Intake, schema.Assessment])
def test_llm_schemas_are_non_recursive(model):
    js = model.model_json_schema()
    for name, definition in js.get("$defs", {}).items():
        assert f'"#/$defs/{name}"' not in json.dumps(definition), f"{name} is recursive"


@pytest.mark.parametrize("model", [schema.Intake, schema.Assessment])
def test_llm_schemas_convert_for_gemini(model):
    t.t_schema(genai.Client(api_key="offline-check"), model)


def test_questionnaire_length_is_enforced(extraction):
    q = {"id": "Q1", "topic": "pain_goal", "question": "?", "why": "w", "assumption_if_unanswered": "a"}
    with pytest.raises(ValidationError):
        schema.Intake(extraction=extraction, questions=[q] * 4)
    with pytest.raises(ValidationError):
        schema.Intake(extraction=extraction, questions=[q] * 11)
    assert len(schema.Intake(extraction=extraction, questions=[q] * 5).questions) == 5
