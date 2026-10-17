import pytest

from afs_assistant import costs


@pytest.fixture(autouse=True)
def tmp_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(costs, "LEDGER_PATH", tmp_path / "spend.json")


def test_call_cost_uses_cache_prices():
    usage = {"input_tokens": 1_000, "cache_creation_input_tokens": 50_000, "cache_read_input_tokens": 0, "output_tokens": 4_000}
    # Opus 5.5: 1k*$4 + 50k*$5 + 4k*$20 per MTok
    assert costs.call_cost("claude-opus-5-5", usage) == pytest.approx((1_000 * 4 + 50_000 * 5 + 4_000 * 20) / 1e6)
    read = {**usage, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 50_000}
    assert costs.call_cost("claude-opus-5-5", read) < costs.call_cost("claude-opus-5-5", usage)


def test_haiku_long_prompt_price():
    short = costs.call_cost("claude-haiku-5-5", {"input_tokens": 90_000})
    long = costs.call_cost("claude-haiku-5-5", {"input_tokens": 120_000})
    assert short == pytest.approx(90_000 * 0.10 / 1e6) and long == pytest.approx(120_000 * 0.50 / 1e6)


def test_gemini_is_free_and_logged():
    assert costs.record("gemini-3.8-flash", "gemini", "assess", {"input_tokens": 50_000}, 1.0) == 0
    assert len(costs.load_ledger()) == 1


def test_budget_guard_refuses(monkeypatch):
    monkeypatch.setattr(costs, "BUDGET_LIMIT_USD", 1.0)
    costs.record("claude-opus-5-5", "anthropic", "assess", {"output_tokens": 45_000}, 1.0)  # $0.90
    costs.check_budget("claude-haiku-5-5", 3_000, 1_000)  # tiny call still fits
    with pytest.raises(costs.BudgetExceeded):
        costs.check_budget("claude-opus-5-5", 200_000, 16_000)


def test_summary_reports_remaining(monkeypatch):
    monkeypatch.setattr(costs, "BUDGET_LIMIT_USD", 55.0)
    costs.record("claude-haiku-5-5", "anthropic", "intake", {"input_tokens": 10_000, "output_tokens": 2_000}, 1.0)
    assert "remaining $54.99" in costs.summary()
