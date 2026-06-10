"""Phase 2 unit tests — scorer, gate, reasoner (flag off)."""
from __future__ import annotations

import pytest

from app import config
from app.brain import gate as gate_mod
from app.brain import scorer as scorer_mod
from app.brain.reasoner import ReasonResult, reason as reason_fn


def test_scorer_weights_sum_to_one():
    r = ReasonResult(
        keep=True, confidence=1.0,
        subject_importance=1.0, time_urgency=1.0, novelty=1.0,
    )
    assert scorer_mod.score(r) == pytest.approx(1.0, abs=1e-6)


def test_scorer_zero():
    r = ReasonResult(keep=False)
    assert scorer_mod.score(r) == 0.0


def test_scorer_ranks_confidence_heavier_than_novelty():
    r_conf = ReasonResult(keep=True, confidence=1.0)
    r_novel = ReasonResult(keep=True, novelty=1.0)
    assert scorer_mod.score(r_conf) > scorer_mod.score(r_novel)


def test_reasoner_flag_off_short_circuits(monkeypatch):
    monkeypatch.setattr(config, "GENIOS_REASONER_ENABLED", False, raising=False)
    out = reason_fn(db=None, candidate={"org_id": "x", "title": "t"})
    assert out.keep is False
    assert out.reason == "reasoner_disabled"


def test_gate_blocks_when_reasoner_said_no(monkeypatch):
    r = ReasonResult(keep=False)
    allowed, reason = gate_mod.allow(candidate={}, reason_result=r, priority=0.9)
    assert not allowed
    assert reason == "reasoner_keep_false"


def test_gate_blocks_low_confidence(monkeypatch):
    monkeypatch.setattr(config, "GENIOS_MIN_PUSH_CONFIDENCE", 0.5, raising=False)
    r = ReasonResult(keep=True, confidence=0.3)
    allowed, reason = gate_mod.allow(candidate={}, reason_result=r, priority=0.9)
    assert not allowed
    assert reason == "below_min_confidence"


def test_gate_blocks_low_priority(monkeypatch):
    monkeypatch.setattr(config, "GENIOS_MIN_PUSH_PRIORITY", 0.6, raising=False)
    monkeypatch.setattr(config, "GENIOS_MIN_PUSH_CONFIDENCE", 0.5, raising=False)
    r = ReasonResult(keep=True, confidence=0.8)
    allowed, reason = gate_mod.allow(candidate={}, reason_result=r, priority=0.4)
    assert not allowed
    assert reason == "below_min_priority"
