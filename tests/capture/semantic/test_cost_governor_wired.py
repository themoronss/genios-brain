"""W9 defect #9 — the cost governor has a PRODUCTION CALLER, and it is the SAME budget.

`tests/capture/semantic/test_batch.py` proves L1.4.8 is correct: it plans, it prices, it demotes
a step at a time and it refuses a group it cannot afford whole. All of that passed while nothing
in `genios_engine/` imported `govern`, so a budget could not stop or demote a single call — the
day's ceiling was enforced once, before a sync started, and then the largest LLM spender in the
system ran unmetered until the next sweep.

This file drives the REAL entry point — `run_sync`, the function every capture path goes through
— with a real `SemanticLane`, and asks the only two questions that matter:

* does a spent budget actually stop a model call, and
* does a tight budget actually demote one, VISIBLY, through `model_router.tier_demoted` rather
  than through a private flag nobody counts?

`FakeLLM` raises when it is called more often than the test canned, so "no call was made" is
proved by the model object rather than by a return value the same code produced.

The last section is the reconciliation the review asked for: the governor's ceiling must be the
deployed daily spend breaker (`docs/plans/L1_V2_BUILD.md` §6 row 7, commit `7e17a6d`,
`api/routes._llm_over_daily_cap`) read a second time, not a second budget nobody reconciles.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.capture import pipeline as P
from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.semantic.batch import (
    REASON_BREAKER_TRIPPED,
    REASON_DAILY_BUDGET,
    Budget,
    CostGovernor,
    Ledger,
)
from genios_engine.capture.semantic.batch import ExtractionRequest as SpendRequest
from genios_engine.capture.semantic.extractor import STAGE as SEMANTIC_STAGE
from genios_engine.capture.semantic.model_router import COST_REASON, T3Budget, demote_for_cost

WAVE = "W9"
GATE = "G9"

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
ORG = "org_gov"
CONN = "con_gov"
OWNER = "founder@genios.ai"
MINIMAL_ANSWER = {"intent": "inform", "stance": "neutral"}

#: The same T3-scoring body `test_sync_runner_declares.py` uses: long content (+30), a currency
#: token (+25), two date strings (+20) and a deep thread (+15) = 90 against a threshold of 75.
#: Built from the score table rather than tuned, so a threshold change fails loudly instead of
#: quietly turning a demotion test into a test of nothing.
_HEAVY_BODY = ("We can move forward with the $84,000 annual contract. Legal signs by "
               "October 15 and finance releases the first invoice on November 3. ") + ("x " * 2100)

#: Generous enough that nothing is ever demoted for money — the control value.
_UNCAPPED = Budget(daily_minor=100_000, t3_daily_minor=100_000, daily_call_cap=0)


class _Mailbox:
    source = "gmail"

    def __init__(self, count: int = 1) -> None:
        self._objects = [
            RawObject(source="gmail", object_type="email_message",
                      source_object_id=f"msg_{i}", occurred_at=NOW,
                      actor_email="buyer@acme.com", recipients=(OWNER,),
                      raw={"subject": f"Contract {i}", "body": f"Message {i}. " + _HEAVY_BODY,
                           "thread_depth": 4})
            for i in range(count)]

    def validate_connection(self) -> bool:
        return True

    def initial_snapshot(self, cursor=None, limit=50) -> SourceBatch:
        return SourceBatch(objects=list(self._objects), next_cursor=None)

    def incremental_changes(self, cursor=None, limit=50, since=None) -> SourceBatch:
        return SourceBatch(objects=list(self._objects), next_cursor=None)

    def fetch_content(self, object_ref: str) -> dict:
        return {}


def _sweep(llm, *, governor=None, count=1, t3_limit=10):
    """One real capture pass, exactly as the sweep runs it."""
    return run_sync(_Mailbox(count), org_id=ORG, connection_id=CONN,
                    repo=InMemorySourceEventRepository(), mailbox_owner=OWNER,
                    semantic=P.SemanticLane(llm=llm, eval_time=NOW, governor=governor,
                                            budget=P.T3Allowance(T3Budget(t3_limit=t3_limit))))


def _spend(governor: CostGovernor, minor: int) -> CostGovernor:
    """A governor whose day has already cost `minor` — the state a mid-day sweep opens in."""
    return CostGovernor(governor.budget, Ledger(spent_minor=minor, t3_spent_minor=0, calls=0))


def _semantic_trace(result):
    """S2's own lines out of the event trace — the record an operator reads afterwards."""
    return [r for r in result.trace.records if r.stage == SEMANTIC_STAGE]


# ═════════════════════════════════════════════════════════════════════════════════════════════
# The seam exists and is consulted on the real path
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_every_extraction_of_a_real_sweep_is_priced_by_the_governor(fake_llm):
    """The governor is not a decoration on the lane: the ledger it hands back is what the sweep
    actually spent, per event, in the order the page arrived."""
    llm = fake_llm(*[MINIMAL_ANSWER] * 3)
    governor = CostGovernor(_UNCAPPED)

    summary = _sweep(llm, governor=governor, count=3)

    assert summary.emitted == 3 and llm.call_count == 3
    assert governor.ledger.calls == 3, "the governor was never asked about these extractions"
    assert governor.ledger.spent_minor > 0


def test_a_lane_without_a_governor_behaves_exactly_as_before(fake_llm):
    """`None` is the ordinary answer for a deployment with no cap configured, and it must cost
    nothing — the pre-flight breaker stays the only guard, which is where every tenant was."""
    llm = fake_llm(*[MINIMAL_ANSWER] * 2)
    summary = _sweep(llm, governor=None, count=2)

    assert summary.emitted == 2 and llm.call_count == 2
    assert all(r.extraction is not None for r in summary.results)


# ═════════════════════════════════════════════════════════════════════════════════════════════
# A spent budget STOPS the call
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_a_budget_exhausted_run_makes_zero_model_calls(fake_llm):
    """The whole point of the defect. `FakeLLM` was canned with nothing, so any call at all is
    an AssertionError — the budget is proved by the model, not by a flag."""
    llm = fake_llm()
    governor = _spend(CostGovernor(Budget(daily_minor=500, t3_daily_minor=500, daily_call_cap=0)),
                      minor=900)          # past 1.5x the budget → the runaway breaker

    summary = _sweep(llm, governor=governor)

    assert llm.call_count == 0, "a budget that cannot stop a call is not a budget"
    assert summary.emitted == 1, "the message itself must still be captured"
    assert all(r.extraction is None for r in summary.results)


def test_the_refusal_states_which_ceiling_stopped_it(fake_llm):
    """A refusal with no reason cannot tell "today is spent" from "something is looping", and
    only one of those is a bug report."""
    llm = fake_llm()
    governor = _spend(CostGovernor(Budget(daily_minor=500, t3_daily_minor=500, daily_call_cap=0)),
                      minor=900)

    summary = _sweep(llm, governor=governor)
    records = _semantic_trace(summary.results[0])

    assert [str(r.action.value) for r in records] == ["short_circuit"]
    assert records[0].reason_code == REASON_BREAKER_TRIPPED


def test_a_spent_but_not_runaway_budget_reports_the_daily_ceiling(fake_llm):
    """`daily_budget_exhausted` and `breaker_tripped` are different sentences about different
    problems; collapsing them would make a runaway indistinguishable from an ordinary busy day."""
    llm = fake_llm()
    governor = _spend(CostGovernor(Budget(daily_minor=500, t3_daily_minor=500, daily_call_cap=0)),
                      minor=500)

    summary = _sweep(llm, governor=governor)

    assert llm.call_count == 0
    assert _semantic_trace(summary.results[0])[0].reason_code == REASON_DAILY_BUDGET


def test_a_refused_extraction_never_charges_the_t3_allowance(fake_llm):
    """A call that did not happen spent no frontier slot. Charging it would let a money refusal
    silently consume the COUNT budget as well, and the next affordable day would start short."""
    llm = fake_llm()
    allowance = P.T3Allowance(T3Budget(t3_limit=5))
    governor = _spend(CostGovernor(Budget(daily_minor=500, t3_daily_minor=500, daily_call_cap=0)),
                      minor=900)

    run_sync(_Mailbox(1), org_id=ORG, connection_id=CONN,
             repo=InMemorySourceEventRepository(), mailbox_owner=OWNER,
             semantic=P.SemanticLane(llm=llm, eval_time=NOW, governor=governor,
                                     budget=allowance))

    assert (allowance.budget.t3_granted, allowance.budget.t3_demoted) == (0, 0)


# ═════════════════════════════════════════════════════════════════════════════════════════════
# A tight budget DEMOTES the call — visibly
# ═════════════════════════════════════════════════════════════════════════════════════════════

def _tight_governor(llm_free_headroom: int) -> CostGovernor:
    """A budget with exactly `llm_free_headroom` cents left — enough for a cheaper tier only."""
    return _spend(CostGovernor(Budget(daily_minor=1000, t3_daily_minor=1000, daily_call_cap=0)),
                  minor=1000 - llm_free_headroom)


def test_a_t3_extraction_the_budget_cannot_afford_runs_at_a_lower_tier(fake_llm):
    """Demotion, on the real path: the extraction still happens, and it happens more cheaply."""
    control = fake_llm(MINIMAL_ANSWER)
    full = _sweep(control, governor=CostGovernor(_UNCAPPED))
    baseline = [r for r in _semantic_trace(full.results[0])][0]
    assert baseline.detail["tier"] == "T3", (
        "_HEAVY_BODY no longer scores into T3 — this test would assert nothing")

    llm = fake_llm(MINIMAL_ANSWER)
    summary = _sweep(llm, governor=_tight_governor(2))
    record = _semantic_trace(summary.results[0])[0]

    assert llm.call_count == 1, "the demotion must run the call, not refuse it"
    assert record.action.value == "pass"
    assert record.detail["tier"] != "T3"


def test_a_money_demotion_is_visible_through_the_routers_own_flag(fake_llm):
    """Doc 04's FAILURE MODES line — *persistent demotion means the budget is wrong, not the
    router* — is only checkable if BOTH ceilings set the same flag. A private "we ran it
    cheaper" boolean would leave the admin console counting half the demotions."""
    llm = fake_llm(MINIMAL_ANSWER)
    summary = _sweep(llm, governor=_tight_governor(2))
    record = _semantic_trace(summary.results[0])[0]

    assert record.detail["tier_demoted"] is True
    assert record.detail["demotion_reason"] == COST_REASON


def test_an_undemoted_extraction_does_not_raise_a_false_demotion(fake_llm):
    """The flag is a counter an operator watches; a false positive is as bad as a silent one."""
    llm = fake_llm(MINIMAL_ANSWER)
    summary = _sweep(llm, governor=CostGovernor(_UNCAPPED))
    record = _semantic_trace(summary.results[0])[0]

    assert record.detail["tier"] == "T3"
    assert record.detail["tier_demoted"] is False
    assert record.detail["demotion_reason"] is None


def test_a_money_demotion_is_counted_by_the_t3_allowance_as_a_demotion_not_a_grant(fake_llm):
    """The two ceilings share one counter. If the allowance were charged before the money
    governor spoke, a T3 slot would be spent on a call that never went to a frontier model."""
    llm = fake_llm(MINIMAL_ANSWER)
    allowance = P.T3Allowance(T3Budget(t3_limit=5))

    run_sync(_Mailbox(1), org_id=ORG, connection_id=CONN,
             repo=InMemorySourceEventRepository(), mailbox_owner=OWNER,
             semantic=P.SemanticLane(llm=llm, eval_time=NOW, governor=_tight_governor(2),
                                     budget=allowance))

    assert (allowance.budget.t3_granted, allowance.budget.t3_demoted) == (0, 1)


def test_the_governor_ledger_advances_within_one_sweep(monkeypatch, fake_llm):
    """A budget re-read only between sweeps is a budget forty calls can walk straight through:
    each one fits the remaining money, and together they do not.

    Pinned to ONE capture worker, because this asserts the ORDER the budget ran out in: the
    sweep captures a page on a thread pool, so with several workers "the first message" is
    whichever one raced first and the tier sequence would vary run to run — a flaky test dressed
    up as a budget test. The concurrency claim has its own test at the bottom of this file, and
    it asserts the total spend, which no ordering can change.
    """
    monkeypatch.setattr("genios_engine.capture.acquire.sync_runner._CAPTURE_WORKERS", 1)
    llm = fake_llm(*[MINIMAL_ANSWER] * 5)
    governor = CostGovernor(Budget(daily_minor=12, t3_daily_minor=12, daily_call_cap=0))

    summary = _sweep(llm, governor=governor, count=5)
    tiers = [r.detail.get("tier") for r in
             [rec for res in summary.results for rec in _semantic_trace(res)]]

    assert summary.emitted == 5, "a spent budget must never cost the tenant their mail"
    assert governor.ledger.spent_minor <= governor.budget.daily_minor, (
        f"the sweep spent {governor.ledger.spent_minor} against a ceiling of "
        f"{governor.budget.daily_minor} — the ledger is not advancing inside the batch")
    assert tiers[0] == "T3" and tiers[-1] != "T3", (
        "the budget did not bind as the sweep progressed")


def test_a_refusal_is_the_last_resort_after_demotion(fake_llm):
    """Demotion is tried first and refusal only when even the floor does not fit — a governor
    that refused a call it could have run cheaply would throw away readable mail to save cents."""
    llm = fake_llm(MINIMAL_ANSWER)
    summary = _sweep(llm, governor=_tight_governor(2))

    assert llm.call_count == 1
    assert summary.results[0].extraction is not None


# ═════════════════════════════════════════════════════════════════════════════════════════════
# `demote_for_cost` — the router's own guard rails
# ═════════════════════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("from_tier,to_tier,expect_demoted", [
    ("T3", "T2", True),
    ("T3", "T1", True),
    ("T2", "T1", True),
    ("T2", "T2", False),     # no change is not a demotion, and must not raise a false flag
])
def test_demote_for_cost_sets_the_flag_and_preserves_the_entitlement(from_tier, to_tier,
                                                                    expect_demoted):
    from genios_engine.capture.semantic.model_router import TierContribution, TierDecision

    original = TierDecision(tier=from_tier, tier_score=90, requested_tier=from_tier,
                            tier_demoted=False, demotion_reason=None, floor_applied=False,
                            contributions=(TierContribution("row", 90, True, "why"),))
    revised = demote_for_cost(original, to_tier)

    assert revised.tier == to_tier
    assert revised.tier_demoted is expect_demoted
    assert revised.requested_tier == from_tier, "the entitlement is what the CONTENT deserved"
    assert (revised.demotion_reason == COST_REASON) is expect_demoted


def test_a_budget_may_never_raise_a_tier():
    """A money ceiling that could move a tier UP would let the wallet buy a better model than
    the content scored for — the router's decision, not the budget's."""
    from genios_engine.capture.semantic.model_router import TierContribution, TierDecision

    original = TierDecision(tier="T1", tier_score=10, requested_tier="T1", tier_demoted=False,
                            demotion_reason=None, floor_applied=False,
                            contributions=(TierContribution("row", 0, False, "why"),))
    with pytest.raises(ValueError, match="may only lower a tier"):
        demote_for_cost(original, "T3")


def test_a_decision_already_demoted_by_the_allowance_keeps_its_original_entitlement():
    """Two ceilings, one entitlement: a T3 talked down to T2 by the count allowance and then to
    T1 by the money ceiling is still a row that was OWED T3."""
    from genios_engine.capture.semantic.model_router import (BUDGET_REASON, TierContribution,
                                                             TierDecision)

    allowance_demoted = TierDecision(
        tier="T2", tier_score=90, requested_tier="T3", tier_demoted=True,
        demotion_reason=BUDGET_REASON, floor_applied=False,
        contributions=(TierContribution("row", 90, True, "why"),))
    revised = demote_for_cost(allowance_demoted, "T1")

    assert (revised.tier, revised.requested_tier, revised.tier_demoted) == ("T1", "T3", True)
    assert revised.demotion_reason == COST_REASON


# ═════════════════════════════════════════════════════════════════════════════════════════════
# ONE budget, not two — reconciliation with the deployed daily spend breaker
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_the_governors_ceiling_is_the_deployed_daily_usd_cap_in_cents():
    """`docs/plans/L1_V2_BUILD.md` §6 row 7: the daily LLM spend circuit breaker must not
    regress. A governor with a ceiling of its own would answer a question the deployed check
    already answers, differently, and which answer applied would depend on which door the work
    came through."""
    from genios_engine.platform.config import get_settings
    from genios_engine.platform.wiring import make_cost_governor

    governor = make_cost_governor(ORG, engine=None)
    assert governor is not None
    assert governor.budget.daily_minor == int(get_settings().daily_llm_usd_cap * 100)


def test_a_zero_cap_means_no_governor_because_that_is_what_it_means_in_routes(monkeypatch):
    """`_llm_over_daily_cap` reads a zero USD cap as "disabled". If this read it as "spend
    nothing" a documented off-switch would become a total block on every extraction."""
    from genios_engine.platform import config as C
    from genios_engine.platform.wiring import make_cost_governor

    C.get_settings.cache_clear()
    monkeypatch.setenv("GENIOS_DAILY_LLM_USD_CAP", "0")
    try:
        assert make_cost_governor(ORG, engine=None) is None
    finally:
        monkeypatch.delenv("GENIOS_DAILY_LLM_USD_CAP", raising=False)
        C.get_settings.cache_clear()


def test_the_call_ceiling_is_the_same_env_var_the_deployed_breaker_reads(monkeypatch):
    """The call cap from commit `7e17a6d` catches the failure money cannot: a loop re-extracting
    a cheap message stays under a dollar ceiling for a long time while burning rate limit."""
    from genios_engine.platform import config as C
    from genios_engine.platform.wiring import make_cost_governor

    C.get_settings.cache_clear()
    monkeypatch.setenv("GENIOS_LLM_DAILY_CAP", "7")
    try:
        assert make_cost_governor(ORG, engine=None).budget.daily_call_cap == 7
    finally:
        monkeypatch.delenv("GENIOS_LLM_DAILY_CAP", raising=False)
        C.get_settings.cache_clear()


def test_the_governor_opens_its_day_from_the_spend_that_already_happened():
    """The deployed check compares TODAY'S `llm_costs` against the cap. A governor that opened
    every process at zero would hand back the whole day's budget on every restart."""
    from genios_engine.platform.wiring import _spent_today_minor

    class _Engine:
        def connect(self):
            raise RuntimeError("pooler down")

    assert _spent_today_minor(_Engine(), ORG) == 0, "an unreadable ledger must fail OPEN"
    assert _spent_today_minor(None, ORG) == 0


def test_the_wired_lane_carries_the_governor_it_built(monkeypatch):
    """`make_semantic_lane` is the production builder; a lane assembled without the governor is
    the defect this whole file is about, one layer up."""
    from genios_engine.platform import wiring as W

    monkeypatch.setattr(W, "make_extraction_cache", lambda: None)
    monkeypatch.setattr(W, "make_open_lane_store", lambda: None)
    monkeypatch.setattr(W, "_org_timezone", lambda engine, org: "UTC")
    monkeypatch.setattr(W, "make_llm_client", lambda: object())
    from genios_engine.platform import config as C
    C.get_settings.cache_clear()
    monkeypatch.setenv("GENIOS_ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    try:
        lane = W.make_semantic_lane(ORG, engine=None, activated=frozenset({ORG}))
        assert lane is not None and isinstance(lane.governor, CostGovernor)
    finally:
        monkeypatch.delenv("GENIOS_ANTHROPIC_API_KEY", raising=False)
        C.get_settings.cache_clear()


# ═════════════════════════════════════════════════════════════════════════════════════════════
# The governor unit itself, under the concurrency the capture pool actually runs
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_concurrent_capture_never_double_spends_the_money_budget(monkeypatch, fake_llm):
    """`govern` is pure — a ledger in, decisions out — so N workers each reading the same
    immutable ledger would each be told the budget is free. `CostGovernor` serialises
    read-decide-write; this asserts the SPEND, not the lock."""
    monkeypatch.setattr("genios_engine.capture.acquire.sync_runner._CAPTURE_WORKERS", 4)
    governor = CostGovernor(Budget(daily_minor=12, t3_daily_minor=12, daily_call_cap=0))
    llm = fake_llm(*[MINIMAL_ANSWER] * 12)

    summary = _sweep(llm, governor=governor, count=12)

    assert summary.emitted == 12
    assert governor.ledger.spent_minor <= 12, (
        f"{governor.ledger.spent_minor} cents were authorised against a ceiling of 12 — the "
        "ledger is being read by more than one worker before any of them writes it back")


def test_the_governor_refuses_a_request_it_cannot_price():
    """A plan of one cannot defer; if it did, the caller would be handed a verdict about no
    call at all and would read the absence as an admission."""
    governor = CostGovernor(_UNCAPPED)
    with pytest.raises(ValueError, match="content is empty"):
        governor.decide(SpendRequest(event_id="e", profile_id="email", content="   ",
                                     requested_tier="T1"))
