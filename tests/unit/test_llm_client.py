"""Unit tests for app.llm.client. No network — Groq/Gemini are monkeypatched."""
from __future__ import annotations

import pytest

from app.llm import client as llm_mod
from app.llm import cost as cost_mod


class _FakeUsage:
    def __init__(self, p, c):
        self.prompt_tokens = p
        self.completion_tokens = c


class _FakeChoice:
    def __init__(self, content):
        self.message = type("m", (), {"content": content})


class _FakeResp:
    def __init__(self, content, p_tok, c_tok):
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage(p_tok, c_tok)


class _FakeGroq:
    class chat:
        class completions:
            @staticmethod
            def create(**kwargs):
                return _FakeResp("hello world", p_tok=100, c_tok=50)


@pytest.fixture
def patched_client(monkeypatch):
    """LLMClient with Groq patched out and DB writes captured in a list."""
    c = llm_mod.LLMClient()
    c._groq = _FakeGroq()

    writes = []

    def fake_log(self, **kwargs):
        writes.append(kwargs)

    def fake_guard(self, org_id):
        return None

    monkeypatch.setattr(llm_mod.LLMClient, "_log_usage", fake_log, raising=True)
    monkeypatch.setattr(llm_mod.LLMClient, "_check_cost_guardrail", fake_guard, raising=True)
    return c, writes


def test_groq_call_logs_usage_and_returns_text(patched_client):
    c, writes = patched_client
    out = c.call(org_id="org-1", purpose="extract_entities", prompt="x")
    assert out == "hello world"
    assert len(writes) == 1
    w = writes[0]
    assert w["provider"] == "groq"
    assert w["in_tok"] == 100 and w["out_tok"] == 50
    # llama-3.3-70b-versatile: 0.59 in, 0.79 out per 1M
    expected = cost_mod.calc_cost_usd("groq", "llama-3.3-70b-versatile", 100, 50)
    assert w["cost_usd"] == pytest.approx(expected, rel=1e-6)


def test_unknown_purpose_raises(patched_client):
    c, _ = patched_client
    with pytest.raises(ValueError):
        c.call(org_id="org-1", purpose="not_a_real_purpose", prompt="x")


def test_missing_prompt_and_messages_raises(patched_client):
    c, _ = patched_client
    with pytest.raises(ValueError):
        c.call(org_id="org-1", purpose="extract_entities")


def test_anthropic_disabled_raises(monkeypatch):
    c = llm_mod.LLMClient()
    monkeypatch.setattr(llm_mod.LLMClient, "_check_cost_guardrail", lambda s, o: None)
    monkeypatch.setattr(llm_mod.LLMClient, "_log_usage", lambda self, **k: None)
    monkeypatch.setattr(llm_mod.config, "GENIOS_ANTHROPIC_ENABLED", False, raising=False)
    monkeypatch.setattr(llm_mod.config, "ANTHROPIC_API_KEY", "dummy_not_configured", raising=False)
    # Re-route reason_haiku to anthropic to exercise the stub
    monkeypatch.setitem(
        llm_mod.ROUTES, "reason_haiku", ("anthropic", "claude-haiku-4-5-20251001")
    )
    with pytest.raises(Exception):
        c.call(org_id="org-1", purpose="reason_haiku", prompt="x")


def test_cost_table_roundtrip():
    assert cost_mod.calc_cost_usd("groq", "llama-3.3-70b-versatile", 1_000_000, 0) == pytest.approx(0.59)
    assert cost_mod.calc_cost_usd("unknown", "unknown", 1_000_000, 1_000_000) == 0.0
