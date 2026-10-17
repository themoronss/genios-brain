"""STEP-13b · one day for every rung: each consult priced at its own rung's tier, a ceiling per rung.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/expert/test_every_rung_spends_one_day.py

Tree `yc2_w27_s13b` M38.C1.L-contract.V1.U03. The expert's $2 a day (`06` D7) is spent by every rung of its
ladder (`reason/bundle/sites.EXPERT_LADDER`): a Haiku consult, its repair, a Sonnet consult and an Opus one draw
on the same R-7 day. Each is priced at its OWN rung's tier — not at R-7's — and held to its rung's per-call
ceiling: $0.10 for T1 and T2, $0.20 for T3 (measured: the costliest of Haiku's 110 answers would cost $0.151 at
Opus prices, over the old $0.10).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.platform import l4_activation as ACT
from genios_engine.reason.bundle import budget as B
from genios_engine.reason.bundle import gate as G
from genios_engine.reason.bundle import sites as S

ORG = "org_scratch_tests"
NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
CEILING = S.max_output_tokens(S.SITE_EXPERT)


def _estimate(tier, chars=60_000):
    return B.estimate_micro_usd(site=S.SITE_EXPERT, prompt_chars=chars, max_output_tokens=CEILING, tier=tier)


def test_a_consult_is_estimated_at_its_own_rungs_price():
    t1, t2, t3 = _estimate(S.TIER_T1), _estimate(S.TIER_T2), _estimate(S.TIER_T3)
    assert (t1, t2, t3) == (45_000, 90_000, 225_000)             # 15k in + 6k out at 1/5, 2/10 and 5/25 $/Mtok
    assert B.estimate_micro_usd(site=S.SITE_EXPERT, prompt_chars=60_000, max_output_tokens=CEILING) == t2, (
        "no rung named: the site's own tier, as before")


def test_the_per_call_ceiling_is_ten_cents_for_haiku_and_sonnet_and_twenty_for_opus():
    assert B.EXPERT_RUNG_PER_CALL == {S.TIER_T1: "0.10", S.TIER_T2: "0.10", S.TIER_T3: "0.20"}
    own = B.NarrativeBudget.for_site(S.SITE_EXPERT, org_id=ORG)
    assert own.per_call_cap_micro_usd == 100_000, "the site's own number is the T1/T2 one"
    assert own.check(100_000, tier=S.TIER_T1).allowed and own.check(100_000, tier=S.TIER_T2).allowed
    assert not own.check(100_001, tier=S.TIER_T2).allowed
    assert own.check(200_000, tier=S.TIER_T3).allowed
    refused = own.check(200_001, tier=S.TIER_T3)
    assert not refused.allowed and refused.reason == B.REASON_PER_CALL and refused.per_call_cap_micro_usd == 200_000
    assert not own.check(150_000, tier=S.TIER_T2).allowed and own.check(150_000, tier=S.TIER_T3).allowed


def test_a_rung_ceiling_is_the_experts_only():
    brief = B.NarrativeBudget.for_site(S.SITE_BRIEF, org_id=ORG)
    assert not brief.check(60_000, tier=S.TIER_T3).allowed, "R-8 keeps its own three cents whatever tier is named"
    assert not B.NarrativeBudget(org_id=ORG).check(60_000, tier=S.TIER_T3).allowed


class _Client:
    model = "claude-haiku-4-5"

    def __init__(self, model):
        self.model, self.calls = model, 0

    def call(self, prompt, *, max_tokens=400):
        from genios_engine.context.llm.client import LLMResult
        self.calls += 1
        return LLMResult(parsed={"mode": "wait"}, raw="", ok=True, model=self.model, input_tokens=10_000,
                         output_tokens=2_000, error=None)


def _gate(budget, model):
    client = _Client(model)
    return G.RSiteGate(org_id=ORG, engine=None, client=client, activated=frozenset({ACT.FEATURE_EXPERT_REVIEW}),
                       budget=budget), client


def _consult(gate, tier):
    return gate.consult(site=S.SITE_EXPERT, cache_key=f"k-{tier}", build_prompt=lambda fb: "x" * 20_000,
                        validate=lambda payload: (dict(payload), (), {"accepted": True}),
                        feature=ACT.FEATURE_EXPERT_REVIEW, tier=tier)


def test_a_consult_records_and_charges_its_rungs_tier():
    budget = B.NarrativeBudget.for_site(S.SITE_EXPERT, org_id=ORG)
    for tier, model in ((S.TIER_T1, "claude-haiku-4-5"), (S.TIER_T2, "claude-sonnet-5")):
        gate, _ = _gate(budget, model)
        result = _consult(gate, tier)
        assert result.outcome == S.OUTCOME_RAN and result.tier == tier
        assert result.cost_micro_usd == B.cost_micro_usd(tier=tier, input_tokens=10_000, output_tokens=2_000)
    assert budget.spent_micro_usd == (B.cost_micro_usd(tier="T1", input_tokens=10_000, output_tokens=2_000)
                                      + B.cost_micro_usd(tier="T2", input_tokens=10_000, output_tokens=2_000))


def test_the_rungs_draw_on_one_day_and_the_last_is_refused_when_it_is_spent():
    budget = B.NarrativeBudget(org_id=ORG, site=S.SITE_EXPERT, daily_cap_micro_usd=90_000, per_call_cap_micro_usd=100_000)
    gate, client = _gate(budget, "claude-haiku-4-5")
    first = _consult(gate, S.TIER_T1)
    assert first.outcome == S.OUTCOME_RAN and budget.spent_micro_usd == 20_000
    second = _consult(gate, S.TIER_T2)                      # 20,000 spent + a Sonnet consult estimated at 70,000: 90,000
    assert second.outcome == S.OUTCOME_RAN and budget.spent_micro_usd == 60_000
    third = _consult(gate, S.TIER_T1)
    assert third.outcome == S.OUTCOME_NO_BUDGET and third.reason_codes == (B.REASON_DAILY_EXHAUSTED,)
    assert client.calls == 2, "a refused rung calls nothing"


def test_a_consult_with_no_rung_named_is_the_sites_own_tier_as_before():
    budget = B.NarrativeBudget.for_site(S.SITE_EXPERT, org_id=ORG)
    gate, _ = _gate(budget, "claude-sonnet-5")
    result = gate.consult(site=S.SITE_EXPERT, cache_key="k", build_prompt=lambda fb: "x" * 20_000,
                          validate=lambda payload: (dict(payload), (), {"accepted": True}),
                          feature=ACT.FEATURE_EXPERT_REVIEW)
    assert result.tier == S.TIER_T2


@pytest.mark.parametrize("tier", ["T0", "T4", "", "t1"])
def test_a_rung_the_ladder_does_not_have_is_refused_before_anything_is_spent(tier):
    gate, client = _gate(B.NarrativeBudget.for_site(S.SITE_EXPERT, org_id=ORG), "claude-sonnet-5")
    with pytest.raises(ValueError):
        _consult(gate, tier)
    assert client.calls == 0


def test_an_opus_consult_is_held_to_twenty_cents_not_ten():
    """The gate hands the budget the rung: a T3 consult estimated between $0.10 and $0.20 runs."""
    from genios_engine.context.llm.client import output_ceiling
    # ⛔ A model that can turn thinking off (so no headroom on the ceiling): at `claude-opus-5-5`, which cannot,
    # the ceiling is 6,000 + its headroom and the pre-flight estimate at T3's price is above $0.20 for any dossier —
    # s13b-F20, said in the plan; the rung is off for every tenant and its number moves with the lead's Opus pass.
    model = "claude-sonnet-5"
    est = B.estimate_micro_usd(site=S.SITE_EXPERT, prompt_chars=20_000, tier=S.TIER_T3,
                               max_output_tokens=output_ceiling(model, CEILING, S.thinking_mode(S.SITE_EXPERT)))
    assert 100_000 < est <= 200_000, est
    gate, client = _gate(B.NarrativeBudget.for_site(S.SITE_EXPERT, org_id=ORG), model)
    result = _consult(gate, S.TIER_T3)
    assert result.outcome == S.OUTCOME_RAN and result.tier == S.TIER_T3 and client.calls == 1


def test_the_retry_of_a_consult_is_estimated_at_the_same_rung():
    from genios_engine.context.llm.client import output_ceiling
    model = "claude-sonnet-5"                  # no headroom on the ceiling (see above)
    ceiling = output_ceiling(model, CEILING, S.thinking_mode(S.SITE_EXPERT))
    est_t3 = B.estimate_micro_usd(site=S.SITE_EXPERT, prompt_chars=20_000, max_output_tokens=ceiling, tier=S.TIER_T3)
    first_cost = B.cost_micro_usd(tier=S.TIER_T3, input_tokens=10_000, output_tokens=2_000)
    budget = B.NarrativeBudget(org_id=ORG, site=S.SITE_EXPERT, daily_cap_micro_usd=first_cost + est_t3 - 1,
                               per_call_cap_micro_usd=100_000)
    gate, client = _gate(budget, model)
    result = gate.consult(site=S.SITE_EXPERT, cache_key="k", build_prompt=lambda fb: "x" * 20_000,
                          validate=lambda payload: (None, ("unsupported",), {"feedback": "fix it"}),
                          feature=ACT.FEATURE_EXPERT_REVIEW, tier=S.TIER_T3)
    assert client.calls == 1, "the retry is priced as the rung it is on: Opus's estimate no longer fits the day"
    assert B.REASON_DAILY_EXHAUSTED in result.reason_codes


def test_at_opus_5_5s_own_ceiling_the_preflight_estimate_is_over_the_rung_ceiling():
    """s13b-F20, held so it is a number somebody has to change on purpose: Opus 5.5 cannot turn thinking off, so
    its ceiling carries headroom, and priced at the ceiling (the budget's rule) one consult is above $0.20."""
    from genios_engine.context.llm.client import output_ceiling
    ceiling = output_ceiling("claude-opus-5-5", CEILING, S.thinking_mode(S.SITE_EXPERT))
    assert ceiling > CEILING
    assert B.estimate_micro_usd(site=S.SITE_EXPERT, prompt_chars=0, max_output_tokens=ceiling,
                                tier=S.TIER_T3) > B.usd_to_micro(B.EXPERT_RUNG_PER_CALL[S.TIER_T3])
