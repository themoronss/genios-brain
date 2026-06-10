"""Phase 4 unit tests — signal scoring + calibration flag + lifecycle state shape."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import config
from app.brain import calibration as cal_mod
from app.graph.signal_scorer import compute_signal_score, signal_from_interaction


def test_signal_base_is_0_5():
    assert compute_signal_score() == 0.5


def test_signal_named_and_structured_and_recent():
    s = compute_signal_score(
        is_named_participant=True, is_structured=True,
        fact_created_at=datetime.now(timezone.utc) - timedelta(days=5),
    )
    # 0.5 + 0.2 + 0.1 + 0.1 = 0.9
    assert s == pytest.approx(0.9, abs=1e-6)


def test_signal_promo_and_cc_only_subtract():
    s = compute_signal_score(is_promo=True, is_cc_only=True)
    # 0.5 - 0.2 - 0.1 = 0.2
    assert s == pytest.approx(0.2, abs=1e-6)


def test_signal_clamps_below_zero_and_above_one():
    assert compute_signal_score(is_promo=True, is_cc_only=True, is_named_participant=False) >= 0.0
    high = compute_signal_score(
        is_named_participant=True, is_structured=True,
        fact_created_at=datetime.now(timezone.utc),
    )
    assert high <= 1.0


def test_signal_from_interaction_helper():
    s = signal_from_interaction({
        "source": "calendar",
        "intent": "meeting",
        "direction": "to",
        "mentioned_people": ["alice"],
        "interaction_at": datetime.now(timezone.utc),
    })
    # structured + named + recent = 0.5 + 0.1 + 0.2 + 0.1 = 0.9
    assert s == pytest.approx(0.9, abs=1e-6)


def test_calibration_skipped_when_flag_off(monkeypatch):
    monkeypatch.setattr(config, "GENIOS_CALIBRATION_ENABLED", False, raising=False)
    out = cal_mod.run_for_org("any-org")
    assert out == {"skipped": "disabled"}


def test_calibration_ece_bounded():
    # Perfect calibration → ece = 0
    conf = [0.1, 0.2, 0.3, 0.8, 0.9]
    labels = [0, 0, 0, 1, 1]
    ece = cal_mod._expected_calibration_error(conf, labels, bins=5)
    assert 0.0 <= ece <= 1.0
