"""STEP-12 · `06` D7 in the machinery: a cached answer never answers another model, and the expert spends its own money.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_tiers_and_the_cache_key.py -q

Tree `yc2_w27_s12` M32.C1.L-contract.V0.U04. Two gaps STEP-12 §8.3 N4 measured:

* the R-site cache key left the MODEL out, so an answer cached from one model would be served when the
  site's model changes — now the model is in the key;
* every consult was held to the narrative's $0.05 per-call ceiling, which a whole review (a dossier and
  a 4,000-token answer on the Sonnet-class tier) can never pass — so it would have been refused on
  every call, recorded as a budget skip. D7 (answered 10 Oct): Sonnet-class only, **$2 a day per org**
  — the expert's OWN budget, with its own per-call ceiling; its spend never comes out of the
  narrative's day, and the narrative's never out of its.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.platform import l4_activation as ACT
from genios_engine.reason import llm_sites as L
from genios_engine.reason.bundle import budget as B
from genios_engine.reason.bundle import gate as G
from genios_engine.reason.bundle import sites as S

ORG = "org_scratch_tests"                       # seeded by tests/conftest.py; satisfies the FK
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
SEED = {"file_id": "node_fund_neel", "fingerprint": "fp_1"}


# ── the cache key ──────────────────────────────────────────────────────────────────────────────

def test_the_same_consult_has_the_same_key():
    assert L.cache_key(site=S.SITE_EXPERT, org_id=ORG, seed=SEED) == \
        L.cache_key(site=S.SITE_EXPERT, org_id=ORG, seed=dict(SEED))


def test_a_cached_answer_never_answers_another_model(monkeypatch):
    before = L.cache_key(site=S.SITE_EXPERT, org_id=ORG, seed=SEED)
    monkeypatch.setattr(L, "tier_model", lambda tier: "claude-sonnet-6")
    assert L.cache_key(site=S.SITE_EXPERT, org_id=ORG, seed=SEED) != before


def test_the_model_in_the_key_is_the_one_the_site_calls(monkeypatch):
    seen: list[str] = []

    def _model(tier):
        seen.append(tier)
        return "claude-sonnet-5"
    monkeypatch.setattr(L, "tier_model", _model)
    L.cache_key(site=S.SITE_EXPERT, org_id=ORG, seed=SEED)
    L.cache_key(site=S.SITE_ALTERNATIVES, org_id=ORG, seed=SEED)
    assert seen == [S.TIER_T2, S.TIER_T1]


def test_two_sites_and_two_tenants_never_share_a_key():
    keys = {L.cache_key(site=site, org_id=org, seed=SEED)
            for site in (S.SITE_EXPERT, S.SITE_ALTERNATIVES) for org in (ORG, "org_other")}
    assert len(keys) == 4


def test_no_opus_tier_exists():
    """D7 is Sonnet-class only: the expert's tier names the Sonnet-class model, and no site's tier
    is anything but T1 or T2."""
    assert L.tier_model(S.tier_for(S.SITE_EXPERT)) == "claude-sonnet-5"
    assert set(S.SITE_TIERS.values()) <= {S.TIER_T1, S.TIER_T2}


# ── the expert's own budget ────────────────────────────────────────────────────────────────────

def test_the_expert_has_its_own_ceilings():
    assert B.OWN_BUDGETS == {S.SITE_EXPERT: ("2.00", "0.10")}
    own = B.NarrativeBudget.for_site(S.SITE_EXPERT, org_id=ORG)
    assert own.daily_cap_micro_usd == 2_000_000 and own.per_call_cap_micro_usd == 100_000
    assert own.site == S.SITE_EXPERT
    shared = B.NarrativeBudget(org_id=ORG)
    assert shared.site is None and shared.per_call_cap_micro_usd == 50_000


def test_a_site_without_a_budget_of_its_own_is_refused():
    with pytest.raises(ValueError, match="no budget of its own"):
        B.NarrativeBudget.for_site(S.SITE_NARRATE, org_id=ORG)


def _whole_review_estimate() -> int:
    """A review at its bound: a 60,000-character dossier (15,000 tokens at T2's 200 cents a million:
    3 cents) and the 6,000-token ceiling (at 1,000 cents a million: 6 cents) — 9 cents, under the
    expert's own 10 (`yc2_w27_s18` M50.C2.L-contract.V1.U02: 4,000 → 6,000)."""
    return B.estimate_micro_usd(site=S.SITE_EXPERT, prompt_chars=60_000,
                                max_output_tokens=S.max_output_tokens(S.SITE_EXPERT))


def test_a_whole_review_passes_its_own_ceiling_and_never_the_narratives():
    estimate = _whole_review_estimate()
    assert estimate == 90_000
    assert B.NarrativeBudget.for_site(S.SITE_EXPERT, org_id=ORG).check(estimate).allowed
    refused = B.NarrativeBudget(org_id=ORG).check(estimate)
    assert not refused.allowed and refused.reason == B.REASON_PER_CALL


def test_a_runaway_prompt_is_still_refused_by_the_experts_ceiling():
    estimate = B.estimate_micro_usd(site=S.SITE_EXPERT, prompt_chars=200_000,
                                    max_output_tokens=S.max_output_tokens(S.SITE_EXPERT))
    verdict = B.NarrativeBudget.for_site(S.SITE_EXPERT, org_id=ORG).check(estimate)
    assert not verdict.allowed and verdict.reason == B.REASON_PER_CALL


class _Client:
    model = "claude-sonnet-5"

    def __init__(self):
        self.calls = 0

    def call(self, prompt, *, max_tokens=400):
        from genios_engine.context.llm.client import LLMResult
        self.calls += 1
        return LLMResult(parsed={"mode": "wait"}, raw="", ok=True, model=self.model,
                         input_tokens=15_000, output_tokens=1_500, error=None)


def _consult(budget):
    client = _Client()
    gate = G.RSiteGate(org_id=ORG, engine=None, client=client,
                       activated=frozenset({ACT.FEATURE_EXPERT_REVIEW}), budget=budget)
    result = gate.consult(site=S.SITE_EXPERT, cache_key="k", build_prompt=lambda fb: "x" * 60_000,
                          validate=lambda payload: (dict(payload), (), {"accepted": True}),
                          feature=ACT.FEATURE_EXPERT_REVIEW)
    return result, client


def test_the_gate_runs_the_expert_on_its_own_budget():
    result, client = _consult(B.NarrativeBudget.for_site(S.SITE_EXPERT, org_id=ORG))
    assert result.outcome == S.OUTCOME_RAN and client.calls == 1
    assert result.cost_micro_usd == B.cost_micro_usd(tier=S.TIER_T2, input_tokens=15_000,
                                                     output_tokens=1_500)


def test_on_the_narratives_budget_the_expert_would_never_run():
    result, client = _consult(B.NarrativeBudget(org_id=ORG))
    assert result.outcome == S.OUTCOME_NO_BUDGET and client.calls == 0
    assert result.reason_codes == (B.REASON_PER_CALL,)


# ── the two days are kept apart, on the ledger ─────────────────────────────────────────────────

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
def test_the_expert_spends_its_own_day_and_the_narrative_its_own(engine):
    _spent(engine, S.SITE_NARRATE, 1_900_000)
    _spent(engine, S.SITE_INTERPRET, 50_000)
    _spent(engine, S.SITE_EXPERT, 500_000)
    _spent(engine, S.SITE_EXPERT, 900_000, at=datetime(2026, 10, 9, 23, 0, tzinfo=timezone.utc))
    shared = B.NarrativeBudget(org_id=ORG, engine=engine, now=NOW)
    own = B.NarrativeBudget.for_site(S.SITE_EXPERT, org_id=ORG, engine=engine, now=NOW)
    assert shared.spent_micro_usd == 1_950_000            # R-2 and R-1 — never the expert's
    assert own.spent_micro_usd == 500_000                 # today's R-7 — never the narrative's
    assert own.check(_whole_review_estimate()).allowed


@pytest.mark.pg
def test_the_experts_day_ends_at_its_cap(engine):
    _spent(engine, S.SITE_EXPERT, 1_950_000)
    verdict = B.NarrativeBudget.for_site(S.SITE_EXPERT, org_id=ORG, engine=engine,
                                         now=NOW).check(_whole_review_estimate())
    assert not verdict.allowed and verdict.reason == B.REASON_DAILY_EXHAUSTED
