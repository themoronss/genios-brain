"""STEP-15 · the brief's writer is a named site at the Haiku-class tier, with a Sonnet-class
escalation that is never Opus (12 Oct direction; `06` D8/s15-D1 in the plan).

    .venv/bin/python -m pytest -q tests/reason/test_the_brief_sites.py tests/reason/test_llm_policy.py

Tree `yc2_w27_s15` M45.C1.L-contract.V0.U01. Doc 11's tier discipline again, same pattern as R-6's
own note: a cheap model is safe here because a deterministic check holds it
(`executive/morning_check`, M45.C2), not because the task is unimportant. So the morning brief
writes on Haiku-class first (R-8) and escalates to Sonnet-class exactly once when the check fails
it twice or the answer is malformed past its one repair (R-8E) — never further, and never Opus
(STEP-15 §8.3 point 3: "the template stands... Never Opus").
"""
from __future__ import annotations

import pytest

from genios_engine.context.llm.client import THINKING_OFF
from genios_engine.reason.bundle import sites as S

pytestmark = pytest.mark.unit


def test_the_writer_is_a_site_in_the_closed_list():
    assert S.SITE_BRIEF == "R-8"
    assert S.SITE_BRIEF in S.R_SITES
    assert S.require_site(S.SITE_BRIEF) == S.SITE_BRIEF
    assert len(set(S.R_SITES)) == len(S.R_SITES), "no id is registered twice"


def test_the_escalation_is_a_separate_site_in_the_closed_list():
    assert S.SITE_BRIEF_ESCALATE == "R-8E"
    assert S.SITE_BRIEF_ESCALATE in S.R_SITES
    assert S.SITE_BRIEF_ESCALATE != S.SITE_BRIEF
    assert S.require_site(S.SITE_BRIEF_ESCALATE) == S.SITE_BRIEF_ESCALATE


def test_an_unregistered_brief_id_is_refused():
    """A typo must be a refusal, not a ledger row — the module's own first lesson (R-7's)."""
    with pytest.raises(ValueError, match="unknown R-site"):
        S.require_site("R-8X")


def test_the_writer_is_haiku_class_the_escalation_sonnet_class():
    assert S.tier_for(S.SITE_BRIEF) == S.TIER_T1
    assert S.tier_for(S.SITE_BRIEF_ESCALATE) == S.TIER_T2


def test_no_third_tier_exists_for_the_brief():
    """Doc 11 and the plan agree: the ladder stops at Sonnet-class. STEP-15 §8.3: 'never Opus.'"""
    assert set(S.SITE_TIERS.values()) == {S.TIER_T1, S.TIER_T2}


def test_the_ceilings_have_headroom_over_the_planned_output_and_under_the_experts_review():
    """The plan caps a brief at 600 words and models its output at ~800 tokens `[MODELLED]` —
    unmeasured until the live look (s15-D1, M45.C5). `SITE_MAX_OUTPUT_TOKENS`'s own lesson from R-2
    (`03` F140) is that a ceiling equal to the estimate truncates a real answer two times in three;
    this one has headroom instead of hoping. It still sits well under a fourteen-section review's
    ceiling (R-7, 6,000) because a 600-word note is not a review."""
    for site in (S.SITE_BRIEF, S.SITE_BRIEF_ESCALATE):
        ceiling = S.max_output_tokens(site)
        assert ceiling >= 2 * 800, "no real headroom over the plan's own modelled estimate"
        assert ceiling < S.max_output_tokens(S.SITE_EXPERT), (
            "a 600-word brief line is not a fourteen-section review")
    assert set(S.SITE_MAX_OUTPUT_TOKENS) == set(S.SITE_TIERS) == set(S.R_SITES)


def test_the_writer_and_its_escalation_think_off():
    """`06` D71: every site asks with thinking off until a measurement says otherwise; the brief's
    two new sites are no exception."""
    assert S.thinking_mode(S.SITE_BRIEF) == THINKING_OFF
    assert S.thinking_mode(S.SITE_BRIEF_ESCALATE) == THINKING_OFF
    assert set(S.SITE_THINKING) == set(S.R_SITES)


def test_the_brief_sites_keep_the_clients_own_timeout():
    """Only the expert's review measured past the client's own 60s (s5t-F10); the brief's ceiling is
    smaller than the expert's, so nothing here has earned a timeout of its own yet."""
    assert S.timeout_s(S.SITE_BRIEF) is None
    assert S.timeout_s(S.SITE_BRIEF_ESCALATE) is None
    assert {site for site in S.R_SITES if S.timeout_s(site) is not None} == {S.SITE_EXPERT}
