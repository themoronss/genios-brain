"""The moment lanes that build their own request send `temperature` only where it is taken, and thinking off.

    pytest tests/reason/moments/test_the_raw_lanes_ask_without_thinking.py -q

⛔ `yc2_w27_s18` M50.C3.L-logic.V1.U12–U14 (the 13 Oct audit's T5-12, s5t-F9). Four moment lanes call the
Anthropic SDK themselves — the seat profile and the reply draft (`seat_profile.t1_text`), draft review,
and the screen-memory batch — and each sent `temperature` with no model check. On Haiku (the T1 model
today) that is right; under a Claude 5 `GENIOS_ANTHROPIC_MODEL` it is a 400 on every call, as the narrator
measured 13–25 Sep, and Claude 5 would think unasked from a ceiling sized for a model that does not. Each
now asks `context/llm/client.request_controls`: the same answer `LLMClient` sends.
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit

_DISABLED = {"type": "disabled"}


def _sdk(monkeypatch) -> list[dict]:
    """Stand in the SDK's transport: every request's keywords land in the list."""
    sent: list[dict] = []

    class FakeAnthropic:
        def __init__(self, **_kw):
            self.messages = SimpleNamespace(create=self._create)

        def _create(self, **kw):
            sent.append(kw)
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text='{"notes": []}')],
                usage=SimpleNamespace(input_tokens=10, output_tokens=2,
                                      cache_read_input_tokens=0, cache_creation_input_tokens=0))

    monkeypatch.setattr("anthropic.Anthropic", FakeAnthropic)
    monkeypatch.setattr("genios_engine.platform.config.get_settings",
                        lambda: SimpleNamespace(use_real_llm=True, anthropic_api_key="sk-test"))
    return sent


def _t1(monkeypatch, model: str) -> None:
    monkeypatch.setattr("genios_engine.reason.llm_sites.tier_model", lambda tier: model)


# ── seat_profile.t1_text — the seat profile's and the reply draft's call (U12) ───────────────────
def _t1_text(monkeypatch, model):
    from genios_engine.reason.moments import seat_profile as SP
    sent = _sdk(monkeypatch)
    _t1(monkeypatch, model)
    SP.t1_text(None, org_id="org_t5", prompt="hello", max_tokens=200, timeout_s=3.0,
               purpose="moment.reply_draft", temperature=0.3)
    (kw,) = sent
    return kw


def test_t1_text_on_a_claude_5_model_sends_no_temperature_and_thinking_off(monkeypatch):
    kw = _t1_text(monkeypatch, "claude-sonnet-5")
    assert "temperature" not in kw and kw["thinking"] == _DISABLED


def test_t1_text_on_haiku_keeps_its_temperature_and_sends_nothing_new(monkeypatch):
    kw = _t1_text(monkeypatch, "claude-haiku-4-5-20251001")
    assert kw["temperature"] == 0.3
    assert set(kw) == {"model", "max_tokens", "temperature", "messages"}


# ── draft_review.llm_notes (U13) ─────────────────────────────────────────────────────────────────
def _notes(monkeypatch, model):
    from genios_engine.reason.moments import draft_review as DR
    sent = _sdk(monkeypatch)
    _t1(monkeypatch, model)
    DR.llm_notes(None, org_id="org_t5", facts=[{"node_id": "n", "name": "Acme deal",
                                                 "field": "deal.stage", "value": "closed lost"}],
                 findings=[], draft="Hi Priya, sending the order form today.",
                 digest=DR.draft_digest("x"), deadline=time.monotonic() + 3)
    (kw,) = sent
    return kw


def test_draft_review_on_a_claude_5_model_sends_no_temperature_and_thinking_off(monkeypatch):
    kw = _notes(monkeypatch, "claude-sonnet-5")
    assert "temperature" not in kw and kw["thinking"] == _DISABLED


def test_draft_review_on_haiku_is_asked_exactly_as_before(monkeypatch):
    kw = _notes(monkeypatch, "claude-haiku-4-5-20251001")
    assert kw["temperature"] == 0 and set(kw) == {"model", "max_tokens", "temperature", "messages"}


# ── screen_memory_batch.submit — each request of the batch (U14) ─────────────────────────────────
def _batch_params(monkeypatch, model):
    from contextlib import contextmanager
    from datetime import datetime, timedelta, timezone

    from genios_engine.contracts.company_brief import CompanyBrief
    from genios_engine.platform.config import get_settings
    from genios_engine.platform.crypto import encrypt
    from genios_engine.reason.moments import screen_memory_batch as MB

    created_at = datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc)
    key = get_settings().crypto_key
    rows = [SimpleNamespace(id="smj_t5", org_id="org_t5", seat_id="seat_1", app="whatsapp",
                            text_enc=encrypt("Priya: send the pricing?", key), created_at=created_at)]

    class _Result:
        rowcount = 0

        def __init__(self, first=None, rows=()):
            self._first, self._rows = first, list(rows)

        def first(self):
            return self._first

        def fetchall(self):
            return list(self._rows)

    class _Claim:
        def execute(self, statement, params=None):
            sql = str(statement)
            if "min(created_at)" in sql:
                return _Result(first=SimpleNamespace(oldest=created_at, n=1))
            if "for update skip locked" in sql:
                return _Result(rows=rows)
            return _Result()

    class _Engine:
        @contextmanager
        def begin(self):
            yield _Claim()

    created: list = []

    def create(*, requests):
        created.append(list(requests))
        return SimpleNamespace(id="msgbatch_t5")
    _t1(monkeypatch, model)
    monkeypatch.setattr("genios_engine.platform.company_brief.current",
                        lambda source, org_id: CompanyBrief(org_id=org_id))
    monkeypatch.setattr(MB, "_Seats", lambda conn: SimpleNamespace(
        get=lambda org, seat: (None, ["Arjun Rao"], "Asia/Kolkata")))
    client = SimpleNamespace(messages=SimpleNamespace(batches=SimpleNamespace(create=create)))
    assert MB.submit(_Engine(), client=client, now=created_at + timedelta(hours=2), crypto_key=key,
                     wait_minutes=0, max_jobs=10) == 1
    ((request,),) = created
    return request["params"]


def test_the_batch_on_a_claude_5_model_sends_no_temperature_and_thinking_off(monkeypatch):
    params = _batch_params(monkeypatch, "claude-sonnet-5")
    assert "temperature" not in params and params["thinking"] == _DISABLED


def test_the_batch_on_haiku_is_asked_exactly_as_before(monkeypatch):
    params = _batch_params(monkeypatch, "claude-haiku-4-5-20251001")
    assert params["temperature"] == 0
    assert set(params) == {"model", "max_tokens", "temperature", "messages"}
