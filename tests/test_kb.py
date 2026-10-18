import re

import pytest

from afs_assistant import config
from afs_assistant.kb import load
from afs_assistant.kb.text import match_key, normalize

needs_cache = pytest.mark.skipif(not config.CHUNKS_PATH.exists(), reason="run `make kb` first (needs materials/)")


def test_normalize_fixes_ligatures_and_hyphen_breaks():
    assert normalize("ﬂuorescence con-\nﬁrmed") == "fluorescence confirmed"
    assert match_key("NIR (780–2500 nm).") == match_key("nir 780 2500 nm.")


@needs_cache
def test_every_source_has_chunks():
    sources = {c.source for c in load.load_chunks()}
    assert {"S01", "S02", "S03", "S04", "S05", "S06", "TABLE", "DOCX"} <= sources
    assert sum(1 for c in load.load_chunks() if c.source == "S01") == 19
    assert sum(1 for c in load.load_chunks() if c.source == "S02") == 20
    assert sum(1 for c in load.load_chunks() if c.source == "TABLE" and c.id != "TABLE:notes") == 19


@needs_cache
def test_cases_parsed():
    cases = load.load_cases()
    assert sorted(cases) == [f"D0{i}" for i in range(1, 9)] + [f"H0{i}" for i in range(1, 7)]
    assert all(len(c["enquiry"]) > 150 for c in cases.values())


@needs_cache
def test_dev_scenarios_are_not_evidence():
    """D-case enquiry texts (with their 'useful sources' hints) must not be in the assessment corpus."""
    corpus = load.render_corpus()
    assert "Useful sources" not in corpus
    assert "H01" not in corpus


@needs_cache
@pytest.mark.parametrize(
    "ref,expected_ids",
    [
        ("S01 p.10", {"S01:p10"}),
        ("S01 p.17-18", {"S01:p17", "S01:p18"}),
        ("S03 p.3, p.10, p.14", {"S03:p3", "S03:p10", "S03:p14"}),
        ("DOCX §2 D01", {"DOCX:§2/D01"}),
        ("S02 p.13", {"S02:p13"}),
    ],
)
def test_resolve_ref(ref, expected_ids):
    assert {c.id for c in load.resolve_ref(ref)} == expected_ids


@needs_cache
def test_resolve_table_ref():
    ids = {c.id for c in load.resolve_ref("S01 Table 1 (p.6)")}
    assert "TABLE:r1" in ids and "S01:p6" in ids


@needs_cache
def test_resolve_unknown_ref():
    assert load.resolve_ref("S09 p.1") == []
    assert load.resolve_ref("S01 p.99") == []


def _facts_refs(node):
    """Yield every citation reference found in facts.yaml (src fields and [..] brackets)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("src", "range_src") and isinstance(value, str) and value != "guidance":
                yield from load.split_refs(value)
            else:
                yield from _facts_refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _facts_refs(item)
    elif isinstance(node, str):
        for bracket in re.findall(r"\[([^\]]+)\]", node):
            yield from load.split_refs(bracket)


@needs_cache
def test_every_facts_reference_resolves():
    refs = set(_facts_refs(load.load_facts()))
    assert refs, "no references found"
    unresolved = sorted(r for r in refs if not load.resolve_ref(r))
    assert not unresolved, f"facts.yaml cites pages that do not exist: {unresolved}"


def test_fiber_ranges_are_sane():
    for fiber in load.load_facts()["fibers"]:
        lo, hi = fiber["range_um"]
        assert 0.1 < lo < hi < 20, fiber
