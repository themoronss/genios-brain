"""Verb selection — pure, ordered, pack-configurable. The order IS the contract."""
from __future__ import annotations

from genios_engine.executive.verbs import DEFAULTS, VERBS, band_of, select_verb


def v(**kw):
    base = dict(level="prescriptive", band="high", confidence_pct=80)
    base.update(kw)
    return select_verb(**base)[0]


def test_policy_block_outranks_everything():
    assert v(policy_blocked=True, preventive=True, band="critical") == "dont"


def test_preventive_maps_to_delay():
    assert v(preventive=True, band="critical") == "delay"


def test_hopeless_prediction_rejects():
    assert v(close_probability_pct=10, confidence_pct=85) == "reject"
    # ... but only when confident enough to say so
    assert v(close_probability_pct=10, confidence_pct=50) != "reject"


def test_critical_band_escalates():
    assert v(band="critical") == "escalate"


def test_prescriptive_high_confident_is_do():
    assert v(level="prescriptive", band="high", confidence_pct=80) == "do"


def test_low_confidence_downgrades_to_consider():
    assert v(confidence_pct=50) == "consider"


def test_diagnostic_never_do():
    assert v(level="diagnostic") == "consider"


def test_thresholds_come_from_config():
    # a tenant that loosens do_c_min via pack data changes the verdict — no deploy
    assert v(confidence_pct=50, cfg={"do_c_min": 40}) == "do"
    assert v(band="high", cfg={"escalate_band": "high"}) == "escalate"


def test_every_verb_is_declared():
    assert set(DEFAULTS) and all(isinstance(x, str) for x in VERBS)
    assert v() in VERBS


def test_band_cuts_match_delivery_semantics():
    assert band_of(84) == "high" and band_of(85) == "critical"
    assert band_of(69) == "standard" and band_of(70) == "high"
    assert band_of(80, {"high": 60, "critical": 79}) == "critical"   # pack override wins
