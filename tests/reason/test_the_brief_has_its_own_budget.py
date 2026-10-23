"""STEP-15 · the brief's own day: R-8 and R-8E spend $0.25 a day per org, $0.03 a call each — never
out of the expert's $2 (`06` D7) and never out of the narrative's.

    .venv/bin/python -m pytest -q tests/reason/test_the_brief_has_its_own_budget.py

Tree `yc2_w27_s15` M45.C1.L-contract.V1.U02. Same architecture as R-7's own budget
(`tests/reason/expert/test_tiers_and_the_cache_key.py`, STEP-12 M32.C1.L-contract.V0.U04): each site
in `OWN_BUDGETS` gets its own opening balance, read from `l4_r_site_calls` filtered to that one site,
so a busy day of narration cannot silence the brief and a busy day of briefs cannot silence the
narrative or the expert. R-8 and R-8E are two SEPARATE entries, each with the plan's own numbers —
not one pool split between the Haiku draft and its Sonnet escalation, the same way R-7 did not share
a bucket with anything either.

⛔ A MARGIN WORTH WATCHING, NOT A DEFECT: the plan models a brief at 6,000 tokens in, 800 out
(`$0.01 on T1 and $0.02 on T2`); at R-8E's actual ceiling (1,600 out, `sites.SITE_MAX_OUTPUT_TOKENS`)
a worst-case Sonnet-class call estimates at $0.028 of the $0.03 per-call cap — 93% of it, on the
SAME modelled input size. A day whose prompt runs larger than modelled would refuse the escalation
exactly on the day the escalation is wanted. `test_the_escalations_worst_case_still_fits_its_own_cap`
pins today's margin so a ceiling or input-size change that erases it is caught here, not live; the
live look (s15-D1, M45.C5) is where this gets a real number instead of a model.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.reason.bundle import budget as B
from genios_engine.reason.bundle import sites as S

pytestmark = pytest.mark.unit

ORG = "org_scratch_tests"                       # seeded by tests/conftest.py; satisfies the FK
NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


# ── the registration ──────────────────────────────────────────────────────────────────────────

def test_the_own_budgets_set_is_pinned_exactly():
    """Restate, don't loosen (the lead's correction, 14 Oct): `test_tiers_and_the_cache_key.py`'s
    `OWN_BUDGETS == {SITE_EXPERT: (...)}` broke the moment R-8/R-8E were added and was loosened to
    that one entry, which means nothing anywhere pins the WHOLE set any more — a fourth site could
    gain a budget of its own silently. This is that pin: a new entry must be added here, in this
    assertion, in the same change that registers it."""
    assert B.OWN_BUDGETS == {
        S.SITE_EXPERT: ("2.00", "0.10"),
        S.SITE_BRIEF: ("0.25", "0.03"),
        S.SITE_BRIEF_ESCALATE: ("0.25", "0.03"),
        S.SITE_REASON: ("2.00", "0.15"),
        # GeniOS-011 S34.U3 (23 Oct): the card writer (R-10), 50 cents a day and 2 cents a call of its own.
        S.SITE_CARD_COPY: ("0.50", "0.02"),
    }


def test_the_writer_and_its_escalation_each_have_their_own_ceilings():
    assert B.OWN_BUDGETS[S.SITE_BRIEF] == ("0.25", "0.03")
    assert B.OWN_BUDGETS[S.SITE_BRIEF_ESCALATE] == ("0.25", "0.03")
    for site in (S.SITE_BRIEF, S.SITE_BRIEF_ESCALATE):
        own = B.NarrativeBudget.for_site(site, org_id=ORG)
        assert own.daily_cap_micro_usd == 250_000
        assert own.per_call_cap_micro_usd == 30_000
        assert own.site == site


def test_the_two_brief_sites_do_not_share_one_bucket():
    """R-8 and R-8E are separate entries — a busy escalation day does not borrow from the draft's
    day, the same way the expert's budget never borrows from the narrative's."""
    brief = B.NarrativeBudget.for_site(S.SITE_BRIEF, org_id=ORG)
    escalate = B.NarrativeBudget.for_site(S.SITE_BRIEF_ESCALATE, org_id=ORG)
    assert brief.site != escalate.site
    assert brief.spent_micro_usd == 0 and escalate.spent_micro_usd == 0       # no engine: opens at 0


def test_the_brief_never_spends_the_experts_or_the_narratives_cap():
    assert B.OWN_BUDGETS[S.SITE_BRIEF] != B.OWN_BUDGETS[S.SITE_EXPERT]
    assert B.OWN_BUDGETS[S.SITE_BRIEF_ESCALATE] != B.OWN_BUDGETS[S.SITE_EXPERT]
    # unchanged by this unit — the narrative's own default ceilings stay what they were
    assert B.usd_to_micro(B.DEFAULT_DAILY_USD_CAP) == 2_000_000
    assert B.usd_to_micro(B.DEFAULT_PER_DECISION_USD_CAP) == 50_000


# ── the sizing (`[MODELLED]`, watched by the live look) ──────────────────────────────────────────

def test_the_modelled_call_costs_about_a_cent_on_haiku_two_on_sonnet():
    """The plan's own words: 'about a cent a day on Haiku, two on Sonnet [MODELLED]' — 6,000 tokens
    in, 800 out."""
    haiku = B.cost_micro_usd(tier=S.TIER_T1, input_tokens=6000, output_tokens=800)
    sonnet = B.cost_micro_usd(tier=S.TIER_T2, input_tokens=6000, output_tokens=800)
    assert haiku == 10_000          # $0.01
    assert sonnet == 20_000         # $0.02


def test_the_escalations_worst_case_still_fits_its_own_cap():
    """Priced at R-8E's real ceiling (not the modelled 800), on the modelled input size: the
    narrowest margin this unit has. See the module docstring's ⛔ note."""
    worst = B.estimate_micro_usd(site=S.SITE_BRIEF_ESCALATE, prompt_chars=6000 * 4,
                                 max_output_tokens=S.max_output_tokens(S.SITE_BRIEF_ESCALATE))
    cap = B.usd_to_micro(B.OWN_BUDGETS[S.SITE_BRIEF_ESCALATE][1])
    assert worst == 28_000 and cap == 30_000
    assert worst < cap, "R-8E's own worst-case estimate must clear its own per-call cap"
    verdict = B.NarrativeBudget.for_site(S.SITE_BRIEF_ESCALATE, org_id=ORG).check(worst)
    assert verdict.allowed


def test_the_writers_worst_case_fits_its_own_cap_with_more_room():
    worst = B.estimate_micro_usd(site=S.SITE_BRIEF, prompt_chars=6000 * 4,
                                 max_output_tokens=S.max_output_tokens(S.SITE_BRIEF))
    cap = B.usd_to_micro(B.OWN_BUDGETS[S.SITE_BRIEF][1])
    assert worst < cap
    assert B.NarrativeBudget.for_site(S.SITE_BRIEF, org_id=ORG).check(worst).allowed


# ── the two days are kept apart, on the ledger ────────────────────────────────────────────────

@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from genios_engine.platform.db import get_engine
    eng = get_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from l4_r_site_calls where org_id = :o"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from l4_r_site_calls where org_id = :o"), {"o": ORG})


def _spent(eng, site: str, micro: int, at: datetime = NOW) -> None:
    with eng.begin() as c:
        c.execute(text(
            "insert into l4_r_site_calls (org_id, site, outcome, tier, cache_key, cost_micro_usd, "
            "created_at) values (:o, :s, 'ran', :t, 'k', :m, :at)"),
            {"o": ORG, "s": site, "t": S.tier_for(site), "m": micro, "at": at})


@pytest.mark.pg
def test_the_brief_and_the_escalation_and_the_narrative_each_keep_their_own_day(engine):
    _spent(engine, S.SITE_NARRATE, 1_000_000)
    _spent(engine, S.SITE_EXPERT, 500_000)
    _spent(engine, S.SITE_BRIEF, 90_000)
    _spent(engine, S.SITE_BRIEF_ESCALATE, 20_000)
    # yesterday's R-8 spend must not count toward today's opening balance
    _spent(engine, S.SITE_BRIEF, 200_000, at=datetime(2026, 10, 13, 23, 0, tzinfo=timezone.utc))

    narrative = B.NarrativeBudget(org_id=ORG, engine=engine, now=NOW)
    expert = B.NarrativeBudget.for_site(S.SITE_EXPERT, org_id=ORG, engine=engine, now=NOW)
    brief = B.NarrativeBudget.for_site(S.SITE_BRIEF, org_id=ORG, engine=engine, now=NOW)
    escalate = B.NarrativeBudget.for_site(S.SITE_BRIEF_ESCALATE, org_id=ORG, engine=engine, now=NOW)

    assert narrative.spent_micro_usd == 1_000_000      # R-2 alone — never R-7, R-8 or R-8E
    assert expert.spent_micro_usd == 500_000           # never the brief's, never the narrative's
    assert brief.spent_micro_usd == 90_000             # today's R-8 only, not yesterday's
    assert escalate.spent_micro_usd == 20_000          # R-8E alone, not R-8's


@pytest.mark.pg
def test_the_briefs_day_ends_at_its_own_cap_not_the_experts(engine):
    _spent(engine, S.SITE_BRIEF, 240_000)
    verdict = B.NarrativeBudget.for_site(S.SITE_BRIEF, org_id=ORG, engine=engine, now=NOW).check(
        B.estimate_micro_usd(site=S.SITE_BRIEF, prompt_chars=6000 * 4,
                             max_output_tokens=S.max_output_tokens(S.SITE_BRIEF)))
    assert not verdict.allowed and verdict.reason == B.REASON_DAILY_EXHAUSTED
    # the expert's own, much larger cap is untouched by R-8's spend
    assert B.NarrativeBudget.for_site(S.SITE_EXPERT, org_id=ORG, engine=engine,
                                      now=NOW).spent_micro_usd == 0
