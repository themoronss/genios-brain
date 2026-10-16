"""STEP-15 · the morning brief's writer is behind a switch no tenant gets by default.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/platform/test_the_morning_brief_feature.py

Tree `yc2_w27_s15` M45.C1.L-contract.V0.U03. s15-D1: a cheap model (R-8, Haiku-class) writes the brief
from the day's checked material, a strong one (R-8E, Sonnet-class) only when the cheap one fails the
check — never Opus — and both are armed per tenant only after the live look on the golden set (58
briefs, under $1 `[MODELLED]`). Off — the default, and the only default until that look runs — the brief
is `executive/morning_template`'s own words and nothing is spent (`06` D12d's reasoning: a template
costs nothing and is always correct about what it says). The tenth feature `L4_FEATURES` names, the
same closed vocabulary `expert_review` joined in STEP-12 — a feature not in it cannot be switched on by
anyone (the L3-19 lesson). `reason/bundle/sites.py`'s own R-8/R-8E registration is a later unit's
(M45.C1.L-contract.V0.U01, waiting on the Claude 5 thinking fix's merge); this one is the switch alone.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from genios_engine.platform import intelligence_onboarding as ONB
from genios_engine.platform import l4_activation as ACT

ORG = "org_scratch_tests"                       # seeded by tests/conftest.py; satisfies the FK

pytestmark = pytest.mark.unit


def _engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the activation table is not exercised")
    from genios_engine.platform.db import get_engine
    return get_engine(url)


@pytest.fixture
def engine():
    eng = _engine()
    with eng.begin() as c:
        c.execute(text("delete from l4_activation where org_id = :o"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from l4_activation where org_id = :o"), {"o": ORG})


# ── the vocabulary: named, waved, effected, no switch it waits on ──────────────────────────────

def test_the_switch_is_a_named_feature_with_its_wave_and_effect():
    assert ACT.FEATURE_MORNING_BRIEF == "morning_brief"
    assert ACT.require_feature("morning_brief") == "morning_brief"
    assert ACT.L4_FEATURES[-1] == ACT.FEATURE_MORNING_BRIEF
    assert ACT.FEATURE_WAVES[ACT.FEATURE_MORNING_BRIEF] == "STEP-15"
    assert ACT.PRECONDITIONS[ACT.FEATURE_MORNING_BRIEF] == ()
    assert ACT.FEATURE_MORNING_BRIEF not in ACT.CROSS_LAYER_PRECONDITIONS
    effect = ACT.EFFECTS[ACT.FEATURE_MORNING_BRIEF]
    for says in ("Haiku", "Sonnet", "checked", "template"):
        assert says in effect, says


def test_the_closed_vocabulary_is_exactly_what_it_was_plus_this_one():
    """The L3-19 lesson, restated for the tenth time: a feature not in `L4_FEATURES` cannot be
    switched on by anyone, and `require_feature` refuses it rather than writing a row nothing
    reads."""
    assert set(ACT.EFFECTS) == set(ACT.L4_FEATURES) == set(ACT.FEATURE_WAVES)
    assert set(ACT.PRECONDITIONS) == set(ACT.L4_FEATURES)
    with pytest.raises(ValueError):
        ACT.require_feature("brief_writer")


def test_no_tenant_gets_the_morning_brief_writer_by_default():
    """A default-on switch that costs a model call every morning is a bill nobody agreed to; it is
    armed per tenant only after the live look s15-D1 names."""
    assert ACT.FEATURE_MORNING_BRIEF in ONB.NOT_DEFAULT_ON
    assert ACT.FEATURE_MORNING_BRIEF not in ONB.L4_DEFAULT_FEATURES
    assert "s15-D1" in ONB.NOT_DEFAULT_ON[ACT.FEATURE_MORNING_BRIEF]


# ── the gate, on a real tenant ──────────────────────────────────────────────────────────────

def test_off_until_a_tenant_is_switched_on(engine):
    assert ACT.is_l4_activated(engine, ORG, ACT.FEATURE_MORNING_BRIEF) is False
    ACT.activate(engine, ORG, feature=ACT.FEATURE_MORNING_BRIEF, by="golden pass, 58/58")
    assert ACT.is_l4_activated(engine, ORG, ACT.FEATURE_MORNING_BRIEF) is True
    assert ACT.deactivate(engine, ORG, feature=ACT.FEATURE_MORNING_BRIEF, by="test") is True
    assert ACT.is_l4_activated(engine, ORG, ACT.FEATURE_MORNING_BRIEF) is False


def test_switching_it_on_does_not_switch_on_the_book_level_rerank(engine):
    """`brief` (the Z6 book-level re-rank) and `morning_brief` (the writer) are two different
    switches a reader could otherwise confuse by name."""
    ACT.activate(engine, ORG, feature=ACT.FEATURE_MORNING_BRIEF, by="test")
    assert ACT.is_l4_activated(engine, ORG, ACT.FEATURE_BRIEF) is False
    assert ACT.activated_features(engine, ORG) == {ACT.FEATURE_MORNING_BRIEF}
