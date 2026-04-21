"""Phase 3 unit tests — cascade flag logic + narrative budget guard."""
from __future__ import annotations

import pytest

from app import config
from app.brain import cascade as cascade_mod
from app.brain import narrative as narr_mod
from app.brain.reasoner import ReasonResult
from app.llm.client import ROUTES


def test_cascade_disabled_when_flag_off(monkeypatch):
    monkeypatch.setattr(config, "GENIOS_CASCADE_ENABLED", False, raising=False)
    r = ReasonResult(keep=True, confidence=0.6)
    assert cascade_mod.should_escalate(r) is False


def test_cascade_disabled_when_sonnet_on_groq(monkeypatch):
    monkeypatch.setattr(config, "GENIOS_CASCADE_ENABLED", True, raising=False)
    # Default ROUTES puts reason_sonnet on groq — should NOT escalate
    assert ROUTES["reason_sonnet"][0] == "groq"
    r = ReasonResult(keep=True, confidence=0.6)
    assert cascade_mod.should_escalate(r) is False


def test_cascade_enabled_when_anthropic_and_grey_band(monkeypatch):
    monkeypatch.setattr(config, "GENIOS_CASCADE_ENABLED", True, raising=False)
    monkeypatch.setitem(ROUTES, "reason_sonnet", ("anthropic", "claude-sonnet-4-6"))
    # grey band is (0.45, 0.75)
    r = ReasonResult(keep=True, confidence=0.6)
    assert cascade_mod.should_escalate(r) is True
    # outside band — skip
    r2 = ReasonResult(keep=True, confidence=0.9)
    assert cascade_mod.should_escalate(r2) is False


def test_narrative_skipped_when_budget_low():
    out = narr_mod.build_narrative(
        org_id="x", entity="A",
        facts=[{"summary": "s"}], pack_size="medium",
        remaining_ms=50,  # below 150ms guard
    )
    assert out is None


def test_narrative_skipped_when_no_facts():
    out = narr_mod.build_narrative(
        org_id="x", entity="A",
        facts=[], pack_size="medium", remaining_ms=10_000,
    )
    assert out is None
