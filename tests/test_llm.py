from types import SimpleNamespace as NS

from afs_assistant.llm import _json_from_text


def test_json_extraction_ignores_trailing_text():
    reply = NS(content=[NS(type="text", text='Sure: {"a": {"b": 1}} }extra {"x": 2}')])
    assert _json_from_text(reply) == '{"a": {"b": 1}}'
