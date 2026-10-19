from datetime import date

from spotwise import ai
from spotwise.ai import auth_headers, build_facts, explain, numbers_ok, rule_parse, template_text
from spotwise.backtest import BacktestParams, run_backtest
from tests.test_backtest import make_series


def test_rule_parse_basic():
    p = rule_parse("gold in INR, 15000 a month, last 3 years, 5% below sell 20%", date(2026, 10, 16))
    assert p.metal == "gold" and p.currency == "INR"
    assert p.monthly_amount == 15000
    assert p.dip_pct == 5 and p.sell_fraction == 0.2
    assert p.start == date(2023, 10, 17) or p.start.year == 2023


def test_rule_parse_garbage_gives_defaults():
    p = rule_parse("hello???", date(2026, 10, 16))
    assert p.metal == "gold" and p.monthly_amount == 10000


def test_numbers_ok_accepts_facts_and_rejects_invented():
    facts = {"a": "1,234", "b": "5.5", "d": "2024-01-01"}
    assert numbers_ok("You put in 1,234 and gained 5.5% from 2024-01-01.", facts)
    assert not numbers_ok("You gained 7.2%.", facts)


def test_template_passes_its_own_number_check():
    s = make_series(n=400, f=lambda i: 100 + i * 0.1)
    p = BacktestParams(monthly_amount=1000)
    facts = build_facts(p, run_backtest(s, p))
    assert numbers_ok(template_text(facts), facts)


def test_explain_falls_back_without_model():
    s = make_series(n=400, f=lambda i: 100 + i * 0.1)
    p = BacktestParams(monthly_amount=1000)
    text, src = explain(build_facts(p, run_backtest(s, p)))
    assert src == "template" and "Backtest of gold" in text


def test_auth_headers_only_with_key():
    assert auth_headers("") == {}
    assert auth_headers("k1") == {"Authorization": "Bearer k1"}


class _FakeResponse:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def _fake_model(monkeypatch, content):
    """Point the AI layer at a fake hosted model; return the list of captured requests."""
    calls = []

    def fake_post(url, json, headers, timeout):
        calls.append({"url": url, "body": json, "headers": headers})
        return _FakeResponse(content)

    monkeypatch.setattr(ai, "LLM_URL", "https://llm.example/v1")
    monkeypatch.setattr(ai, "LLM_MODEL", "gemma-test")
    monkeypatch.setattr(ai, "LLM_API_KEY", "secret")
    monkeypatch.setattr(ai.httpx, "post", fake_post)
    return calls


def test_hosted_model_gets_key_and_no_system_message(monkeypatch):
    calls = _fake_model(monkeypatch, '{"metal": "silver", "monthly_amount": 5000}')
    p, src = ai.parse_request("silver 5000 a month", date(2026, 10, 16))
    assert src == "model" and p.metal == "silver" and p.monthly_amount == 5000
    sent = calls[0]
    assert sent["url"] == "https://llm.example/v1/chat/completions"
    assert sent["headers"] == {"Authorization": "Bearer secret"}
    assert sent["body"]["model"] == "gemma-test"
    assert [m["role"] for m in sent["body"]["messages"]] == ["user"]
    assert "silver 5000 a month" in sent["body"]["messages"][0]["content"]


def test_hosted_model_explanation_still_number_checked(monkeypatch):
    s = make_series(n=400, f=lambda i: 100 + i * 0.1)
    p = BacktestParams(monthly_amount=1000)
    facts = build_facts(p, run_backtest(s, p))
    _fake_model(monkeypatch, "You would have made 99.9% more.")  # invented number
    text, src = explain(facts)
    assert src == "template" and "Backtest of gold" in text
