"""STEP-12 · the expert is a named site with a budgeted tier and ceiling, behind a switch no tenant gets by default.

    .venv/bin/python -m pytest -q tests/reason/expert/test_the_expert_site_and_feature.py

Tree `yc2_w27_s12` M32.C1.L-contract.V0.U03. A model call that is not in the closed site list is refused
by `require_site` (a typo is a refusal, not a ledger row); a feature that is not in `L4_FEATURES` cannot
be switched on by anyone (the L3-19 lesson: `cards_from_situations` existed as a literal and no tenant
could hold it). So the expert lands as both at once: `SITE_EXPERT`, Sonnet-class only (`06` D7), with an
output ceiling sized for a whole review — and `expert_review`, with its wave, its effect, no switch it
waits on, and NOT default-on: it spends a strong-model call per changed file.
"""
from __future__ import annotations

import pytest

from genios_engine.platform import intelligence_onboarding as ONB
from genios_engine.platform import l4_activation as ACT
from genios_engine.reason.bundle import sites as S

pytestmark = pytest.mark.unit


def test_the_expert_is_a_site_in_the_closed_list():
    assert S.SITE_EXPERT == "R-7"
    # STEP-15 registered R-8/R-8E after it (`tests/reason/test_the_brief_sites.py`) — this file's
    # own claim is only that the seventh is registered at all, never that it is last forever.
    assert S.SITE_EXPERT in S.R_SITES
    assert S.require_site(S.SITE_EXPERT) == S.SITE_EXPERT
    assert len(set(S.R_SITES)) == len(S.R_SITES)


def test_the_expert_thinks_on_the_sonnet_class_tier_only():
    """`06` D7, answered 10 Oct: Sonnet-class only — no Opus tier exists, and none is added."""
    assert S.tier_for(S.SITE_EXPERT) == S.TIER_T2
    assert set(S.SITE_TIERS.values()) == {S.TIER_T1, S.TIER_T2}


def test_the_ceiling_holds_a_whole_review():
    """A review is fourteen sections and a draft; the narrative's 1,400-token cap cut two answers
    in three mid-JSON before it was measured (`SITE_MAX_OUTPUT_TOKENS`' own comment). The expert's
    ceiling is set above every other site's, and a truncated answer is a recorded refusal
    (`03` F140), never a parse."""
    ceiling = S.max_output_tokens(S.SITE_EXPERT)
    # 4,000 → 6,000 (`yc2_w27_s18` M50.C2.L-contract.V1.U02): Haiku's reviews measured p90 3,509, max
    # 3,990, six cut at 4,000 — and Sonnet 5 asked with thinking off (`06` D71).
    assert ceiling == 6000
    # GeniOS-008: every site but R-9 — the L2 judgment pass, which IS this review plus its judgment half, and so
    # sits above it (R-9's own ceiling is pinned in tests/reason/l2).
    assert ceiling > max(v for k, v in S.SITE_MAX_OUTPUT_TOKENS.items() if k not in (S.SITE_EXPERT, S.SITE_REASON))
    assert S.max_output_tokens(S.SITE_REASON) > ceiling
    assert set(S.SITE_MAX_OUTPUT_TOKENS) == set(S.SITE_TIERS) == set(S.R_SITES)


def test_the_switch_is_a_named_feature_with_its_wave_and_effect():
    assert ACT.FEATURE_EXPERT_REVIEW == "expert_review"
    assert ACT.require_feature("expert_review") == "expert_review"
    # STEP-15 added `morning_brief` after it (tests/test_l4_pilot_activation.py pins the full,
    # ordered tuple) — this file's own claim is only that the ninth is registered at all.
    assert ACT.FEATURE_EXPERT_REVIEW in ACT.L4_FEATURES
    assert ACT.FEATURE_WAVES[ACT.FEATURE_EXPERT_REVIEW] == "STEP-12"
    assert ACT.PRECONDITIONS[ACT.FEATURE_EXPERT_REVIEW] == ()
    assert ACT.FEATURE_EXPERT_REVIEW not in ACT.CROSS_LAYER_PRECONDITIONS
    effect = ACT.EFFECTS[ACT.FEATURE_EXPERT_REVIEW]
    # ⛔ "no card changes" was M32's (shadow); from M33 a valid review DECIDES its file.
    for says in ("once per fingerprint", "expert_reviews", "DECIDES its file", "Off,"):
        assert says in effect, says


def test_no_tenant_gets_the_expert_by_default():
    """A default-on switch that costs a strong-model call per changed file is a bill nobody agreed
    to; it is armed per tenant, after the live golden pass on the D7 model (`06` D50)."""
    assert ACT.FEATURE_EXPERT_REVIEW in ONB.NOT_DEFAULT_ON
    assert ACT.FEATURE_EXPERT_REVIEW not in ONB.L4_DEFAULT_FEATURES
    assert "D50" in ONB.NOT_DEFAULT_ON[ACT.FEATURE_EXPERT_REVIEW]
