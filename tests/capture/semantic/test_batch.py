"""L1.4.8 · the batch planner and cost governor — Wave W4.

    pytest tests/capture/semantic/test_batch.py -q

Doc 04 gives this component a row and no specification, so its acceptance is assembled from the
two things it must not break and the one line the plan does state about it:

* **must-not-regress item 7 — the daily LLM spend circuit breaker (`7e17a6d`).** Three
  properties are asserted directly: it is PRE-FLIGHT (it decides whether a batch may start and
  refuses whole calls, never a call in progress); it bounds CALLS as well as money, because a
  loop re-extracting one cheap message stays under a dollar ceiling for a long time; and a
  configured zero cap means "no ceiling", which is how `_llm_over_daily_cap` already reads it —
  changing that meaning silently disables a control;
* **doc 04, L1.4.10-U1 — `budget exhausted -> T3 request comes back T2 with tier_demoted set`.**
  That is `test_a_t3_request_comes_back_t2_with_tier_demoted_set`, written to the doc's words.

The rows that matter most are the ones nobody wrote down:

* **demotion has a floor.** `document` and `transcript` never fall to T1. A contract read by
  the cheapest model produces a confident wrong renewal date, which costs more than an unread
  contract — so an unaffordable document is REFUSED, and the test asserts that a squeeze
  produces a refusal rather than a cheap answer;
* **a group is all-or-nothing.** Admitting chunk 1 of an agreement and refusing chunk 7 yields
  a contract with its termination clause missing and nothing saying so;
* **the ledger advances inside the batch.** Forty calls that each fit the remaining budget
  individually and blow it together is the exact failure a per-call check cannot see.

Budgets in this file are DERIVED from `PlannedCall.cost_minor`, never typed as literals. A
budget literal is a number that stops meaning what the test intended the day a rate, a token
estimate or a prompt length changes — and the test then passes for a new reason.
"""

from __future__ import annotations

import pytest

from genios_engine.capture.documents.chunking import chunk_document
from genios_engine.capture.semantic.batch import (ADMITTED, BP_FULL, CHARS_PER_TOKEN,
                                                  DEFAULT_ENVELOPE_CHARS, DEFAULT_TIER_PRICES,
                                                  FENCE_OVERHEAD_CHARS, OUTPUT_CAP_TOKENS,
                                                  OUTPUT_FLOOR_TOKENS, REASON_BREAKER_TRIPPED,
                                                  REASON_CALL_CAP, REASON_DAILY_BUDGET,
                                                  REASON_OVERSIZED, REASON_T3_BUDGET, TIER_FLOORS,
                                                  Budget, ExtractionRequest, GovernedCall, Ledger,
                                                  PlannedCall, TierPrice, breaker,
                                                  fixed_prompt_tokens, govern,
                                                  plan_batch)
from genios_engine.capture.semantic.injection import NONCE_CHARS, fence
from genios_engine.capture.semantic.profiles import (PROFILE_IDS, TIERS, get_profile,
                                                     render_prompt)
from genios_engine.capture.semantic.schema_gen import generate_schema_block
from genios_engine.capture.semantic.vocabulary import vocabulary_block
from genios_engine.contracts.extraction import ExtractionResult

pytestmark = pytest.mark.unit

WAVE = "W4"

EMAIL = ("Hi Rohit, we can probably move forward with the $84,000 annual contract, but I still "
         "need Finance to confirm before the 15th.")
CHAT = "sounds good, let's do 10am"
#: One heading and a body far past the `document` profile's 40,000-char cap. The chunker's rule
#: 3 is absolute — a detected clause is never split — so this comes back as ONE oversized chunk,
#: which is the input `render_prompt` refuses and therefore the input `govern` must refuse.
OVERSIZED_DOC = "## Termination\n" + ("The parties agree that this section is long. " * 2600)
#: A real document, comfortably inside the `document` profile's 40,000-char cap, and long
#: enough that T1 and T2 are genuinely different prices. A short document costs one minor unit
#: at every tier once rounding is applied, which would make a floor test pass whether or not
#: the floor existed.
DOCUMENT = "1. Term\n" + ("The agreement renews annually unless either party gives notice. " * 300)
#: A short section followed by an oversized one. The governor refuses the oversized chunk the
#: moment it sees it and admits the rest of the group afterwards, so the DECIDED order is the
#: reverse of the plan's — which is exactly the reshuffle `_in_plan_order` has to undo.
MIXED_DOC = ("## Notice\nEither party may give notice in writing.\n## Termination\n"
             + "The parties agree that this section is long. " * 2600)
#: Long enough that the `email` profile's 24,000-char cap divides it into several calls.
LONG_EMAIL = ("We reviewed the proposal and have notes on the pricing schedule. " * 800)

FULL_BUDGET = Budget(daily_minor=10_000_000, t3_daily_minor=10_000_000, daily_call_cap=0)
EMPTY_LEDGER = Ledger(spent_minor=0, t3_spent_minor=0, calls=0)


def _plan(*requests, **kwargs):
    return plan_batch(list(requests), **kwargs)


def _cost(plan, tier) -> int:
    """What the whole plan costs at one tier, at list price. Every budget below is built from
    this, so a rate change re-derives the thresholds instead of invalidating the test."""
    return sum(call.cost_minor(tier, DEFAULT_TIER_PRICES) for call in plan.calls)


# ── U1 · the plan ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("profile_id, content, calls, why", [
    ("chat", CHAT, 1, "a chat line is one call under the `none` strategy"),
    ("crm_note", CHAT, 1, "so is a CRM note"),
    ("email", EMAIL, 1, "an email that fits its 24,000-char cap is one call"),
    ("email", LONG_EMAIL, 3, "an email past the cap is sentence-packed into several"),
    ("document", OVERSIZED_DOC, 1, "rule 3: a detected clause is emitted whole, never split"),
])
def test_a_request_becomes_one_call_per_chunk_of_its_own_profile(profile_id, content, calls, why):
    """The planner does not chunk; `chunk_document` does, with the profile's own strategy and
    cap. One splitter, so the planner and the extractor cannot disagree about where a document
    divides."""
    profile = get_profile(profile_id)
    expected = chunk_document(content, max_chars=profile.max_input_chars,
                              strategy=profile.chunk_strategy)
    plan = _plan(ExtractionRequest("e1", profile_id, content, "T2"))
    assert len(plan.calls) == len(expected) == calls, why
    assert {call.chunk_count for call in plan.calls} == {len(expected)}


def test_each_call_carries_the_offset_that_makes_its_evidence_resolvable():
    """`prepared = view + chunk_start` is L1.4.6's rule. A plan that dropped `chunk_start` would
    produce calls whose quotes cannot be aligned — invisible until a span fails to verify."""
    plan = _plan(ExtractionRequest("e1", "email", LONG_EMAIL, "T2"))
    profile = get_profile("email")
    chunks = chunk_document(LONG_EMAIL, max_chars=profile.max_input_chars,
                            strategy=profile.chunk_strategy)
    for call, chunk in zip(plan.calls, chunks):
        assert call.chunk_start == chunk.start_offset
        assert LONG_EMAIL[call.chunk_start:call.chunk_start + call.content_chars] == chunk.text


@pytest.mark.parametrize("profile_id", PROFILE_IDS)
def test_every_profile_carries_its_demotion_floor_onto_the_call(profile_id):
    """The governor enforces the floor, so the floor has to travel with the call. Read off
    `TIER_FLOORS` rather than retyped, and doc 04's own override is the assertion below."""
    plan = _plan(ExtractionRequest("e1", profile_id, EMAIL, "T3"))
    assert {call.floor_tier for call in plan.calls} == {TIER_FLOORS[profile_id]}


@pytest.mark.parametrize("profile_id", ["document", "transcript"])
def test_doc_04s_override_is_a_floor_the_budget_cannot_walk_through(profile_id):
    """*"OVERRIDE: profile in {document, transcript} always >= T2."* Stated for the router; a
    floor only the router enforced would be a floor the cost governor demoted straight past."""
    assert TIER_FLOORS[profile_id] == "T2"


def test_token_estimates_include_the_prompt_and_are_bounded():
    """Input is body plus the profile's own spine — measured off the registered template, so a
    prompt that grows re-prices itself. Output is bounded, because the open-lane cap and the
    quote cap bound how much a single extraction can say."""
    plan = _plan(ExtractionRequest("e1", "email", EMAIL, "T2"))
    call = plan.calls[0]
    body_tokens = -(-call.content_chars // CHARS_PER_TOKEN)
    template_tokens = -(-len(get_profile("email").prompt_template) // CHARS_PER_TOKEN)
    assert call.input_tokens > body_tokens + template_tokens
    assert OUTPUT_FLOOR_TOKENS <= call.output_tokens <= OUTPUT_CAP_TOKENS
    for value in (call.input_tokens, call.output_tokens):
        assert isinstance(value, int) and not isinstance(value, bool)


def test_a_huge_body_does_not_produce_an_unbounded_output_estimate():
    """The share term alone would price this completion at more than 4,000 tokens; the cap is
    what stops a 100,000-character clause from being budgeted as if the model would quote all
    of it back."""
    plan = _plan(ExtractionRequest("e1", "document", OVERSIZED_DOC, "T3"))
    body_tokens = -(-plan.calls[0].content_chars // CHARS_PER_TOKEN)
    assert OUTPUT_FLOOR_TOKENS + body_tokens * 1500 // BP_FULL > OUTPUT_CAP_TOKENS
    assert plan.calls[0].output_tokens == OUTPUT_CAP_TOKENS


def test_an_oversized_chunk_is_planned_and_flagged_rather_than_truncated():
    """`render_prompt` refuses content over the cap, and truncating would produce a
    complete-looking extraction missing the paragraph the number was in. So it is planned,
    flagged, and refused by the governor — never shortened."""
    profile = get_profile("document")
    chunks = chunk_document(OVERSIZED_DOC, max_chars=profile.max_input_chars,
                            strategy=profile.chunk_strategy)
    plan = _plan(ExtractionRequest("e1", "document", OVERSIZED_DOC, "T3"))
    assert plan.calls[0].oversized
    assert plan.calls[0].content_chars == len(chunks[0].text) > profile.max_input_chars


def test_groups_hold_one_events_calls_together_in_chunk_order():
    plan = _plan(ExtractionRequest("a", "email", LONG_EMAIL, "T2"),
                 ExtractionRequest("b", "chat", CHAT, "T1"),
                 ExtractionRequest("c", "email", LONG_EMAIL, "T2"))
    groups = plan.groups()
    assert [group[0].event_id for group in groups] == ["a", "b", "c"]
    assert [len(group) for group in groups] == [3, 1, 3]
    for group in groups:
        assert [call.chunk_index for call in group] == list(range(len(group)))


def test_a_request_that_does_not_fit_the_wave_is_deferred_whole():
    """Never split across waves: a half-planned document is the partial read `groups()` exists
    to prevent, and the caller re-plans the deferred request against a ledger it has re-read."""
    small = ExtractionRequest("small", "chat", CHAT, "T1")
    big = ExtractionRequest("big", "email", LONG_EMAIL, "T2")
    plan = _plan(small, big, max_calls=2)
    assert [call.event_id for call in plan.calls] == ["small"]
    assert [request.event_id for request in plan.deferred] == ["big"]


def test_deferral_preserves_arrival_order_rather_than_packing_the_wave():
    """Best-fit packing would let a stream of one-chunk chats starve a long document forever.
    Once a request is deferred, everything after it defers with it."""
    plan = _plan(ExtractionRequest("big", "email", LONG_EMAIL, "T2"),
                 ExtractionRequest("small", "chat", CHAT, "T1"), max_calls=2)
    assert plan.calls == ()
    assert [request.event_id for request in plan.deferred] == ["big", "small"]


def test_planned_chars_counts_what_will_be_sent():
    plan = _plan(ExtractionRequest("a", "email", EMAIL, "T2"),
                 ExtractionRequest("b", "chat", CHAT, "T1"))
    assert plan.planned_chars == sum(call.content_chars for call in plan.calls)


@pytest.mark.parametrize("max_calls", [0, -1])
def test_a_wave_that_can_hold_no_calls_is_refused(max_calls):
    with pytest.raises(ValueError, match="max_calls must be positive"):
        _plan(ExtractionRequest("a", "chat", CHAT, "T1"), max_calls=max_calls)


@pytest.mark.parametrize("kwargs, fragment", [
    (dict(event_id=" ", profile_id="email", content=EMAIL, requested_tier="T2"),
     "event_id is required"),
    (dict(event_id="a", profile_id="email", content=EMAIL, requested_tier="T4"),
     "unknown tier"),
    (dict(event_id="a", profile_id="email", content="   ", requested_tier="T2"),
     "content is empty"),
])
def test_a_request_that_cannot_be_planned_is_refused_at_construction(kwargs, fragment):
    with pytest.raises(ValueError, match=fragment):
        ExtractionRequest(**kwargs)


# ── U3 · the breaker (must-not-regress item 7) ───────────────────────────────────────────────

@pytest.mark.parametrize("spent, calls, cap, tripped, reason, why", [
    (0, 0, 100, False, ADMITTED, "a fresh day starts"),
    (9_999, 0, 100, False, ADMITTED, "one minor unit of the 10,000 budget is left"),
    # This row REPLACES `(14_999, ..., False, ADMITTED, "under the 1.5x threshold")`. That row
    # encoded a real gap rather than a decision: the deployed control
    # (`api/routes._llm_over_daily_cap`) refuses to start work at `usd >= daily_llm_usd_cap` —
    # at 1x — so a pre-flight here that admitted a batch at 1.4999x was a SECOND, laxer money
    # ceiling for the same money, and which one applied depended on which door the work came
    # through. `govern` refused those calls anyway, which is why nothing was visibly broken; the
    # verdict a caller reads was the part that disagreed.
    (10_000, 0, 100, True, REASON_DAILY_BUDGET, "at the budget the deployed breaker already "
                                                "refuses at; this one must not admit past it"),
    (14_999, 0, 100, True, REASON_DAILY_BUDGET, "past the budget, under the runaway threshold — "
                                                "still refused, and named as spend not runaway"),
    (15_000, 0, 100, True, REASON_BREAKER_TRIPPED, "at the threshold, not merely past it"),
    (99_999, 0, 100, True, REASON_BREAKER_TRIPPED, "far past it"),
    (0, 100, 100, True, REASON_CALL_CAP, "money is fine and the call ceiling is not — the "
                                         "runaway 7e17a6d was built for"),
    (0, 99, 100, False, ADMITTED, "one call left"),
    (0, 10_000_000, 0, False, ADMITTED, "a zero cap means NO ceiling, as GENIOS_LLM_DAILY_CAP=0 "
                                        "already reads; changing that disables a control"),
])
def test_the_breaker_trips_on_whichever_ceiling_is_reached(spent, calls, cap, tripped, reason,
                                                           why):
    budget = Budget(daily_minor=10_000, t3_daily_minor=5_000, daily_call_cap=cap)
    verdict = breaker(budget, Ledger(spent_minor=spent, t3_spent_minor=0, calls=calls))
    assert verdict.tripped is tripped, why
    assert verdict.reason == reason
    assert verdict.threshold_minor == 15_000


def test_the_threshold_is_integer_basis_points_of_the_budget():
    """1.5x, the multiple the old `CostGuard` used, expressed so it cannot be a float."""
    budget = Budget(daily_minor=3_333, t3_daily_minor=0, daily_call_cap=0, breaker_bp=15_000)
    assert budget.breaker_threshold_minor == 3_333 * 15_000 // BP_FULL == 4_999


@pytest.mark.parametrize("kwargs, exc, fragment", [
    (dict(daily_minor=-1, t3_daily_minor=0, daily_call_cap=0), ValueError, "must not be negative"),
    (dict(daily_minor=100, t3_daily_minor=101, daily_call_cap=0), ValueError, "never binds"),
    (dict(daily_minor=100, t3_daily_minor=0, daily_call_cap=0, breaker_bp=9_999), ValueError,
     "makes daily_minor unreachable"),
    (dict(daily_minor=10.5, t3_daily_minor=0, daily_call_cap=0), TypeError, "minor units"),
    (dict(daily_minor=True, t3_daily_minor=0, daily_call_cap=0), TypeError, "minor units"),
])
def test_a_budget_that_could_not_be_enforced_is_refused(kwargs, exc, fragment):
    """A breaker below 1x makes the approved daily number unreachable; a float budget re-rounds
    differently on every worker and the enforced ceiling stops being one number."""
    with pytest.raises(exc, match=fragment):
        Budget(**kwargs)


@pytest.mark.parametrize("kwargs, exc, fragment", [
    (dict(spent_minor=-1, t3_spent_minor=0, calls=0), ValueError, "must not be negative"),
    (dict(spent_minor=10, t3_spent_minor=11, calls=0), ValueError, "part of the total"),
    (dict(spent_minor=1.5, t3_spent_minor=0, calls=0), TypeError, "must be an integer"),
])
def test_a_ledger_that_cannot_be_true_is_refused(kwargs, exc, fragment):
    with pytest.raises(exc, match=fragment):
        Ledger(**kwargs)


# ── U2 · the governor ────────────────────────────────────────────────────────────────────────

def test_a_healthy_budget_admits_every_call_at_the_tier_the_router_asked_for():
    plan = _plan(ExtractionRequest("a", "email", EMAIL, "T2"),
                 ExtractionRequest("b", "chat", CHAT, "T1"))
    batch = govern(plan, budget=FULL_BUDGET, ledger=EMPTY_LEDGER)
    assert batch.admitted == len(plan.calls) and batch.refused == 0 and batch.demoted == 0
    assert [call.tier for call in batch.calls] == ["T2", "T1"]
    assert all(call.reason == ADMITTED for call in batch.calls)
    assert batch.estimated_cost_minor == _cost(plan, "T2") - plan.calls[1].cost_minor(
        "T2", DEFAULT_TIER_PRICES) + plan.calls[1].cost_minor("T1", DEFAULT_TIER_PRICES)


def test_a_t3_request_comes_back_t2_with_tier_demoted_set():
    """DOC 04'S OWN ACCEPTANCE LINE for the budget path of L1.4.10:

        budget exhausted -> T3 request comes back T2 with tier_demoted set

    The call runs. It runs cheaper. And the fact that it did is on the record, because
    *"persistent demotion means the budget is wrong, not the router"* is only observable if
    somebody counted the demotions.
    """
    plan = _plan(ExtractionRequest("a", "email", EMAIL, "T3"))
    budget = Budget(daily_minor=_cost(plan, "T3"), t3_daily_minor=0, daily_call_cap=0)

    batch = govern(plan, budget=budget, ledger=EMPTY_LEDGER)

    decided = batch.calls[0]
    assert decided.admitted and decided.tier == "T2"
    assert decided.tier_demoted is True
    assert decided.reason == REASON_T3_BUDGET
    assert batch.demoted == 1
    assert decided.estimated_cost_minor == plan.calls[0].cost_minor("T2", DEFAULT_TIER_PRICES)


def test_a_demotion_is_never_silent():
    """The negative half of the same property: an UNdemoted call must not claim it was, or the
    counter the admin console watches becomes noise."""
    plan = _plan(ExtractionRequest("a", "email", EMAIL, "T1"))
    batch = govern(plan, budget=FULL_BUDGET, ledger=EMPTY_LEDGER)
    assert batch.calls[0].tier_demoted is False
    assert batch.demoted == 0


def test_a_document_is_refused_rather_than_demoted_below_its_floor():
    """A contract read by the cheapest model produces a confident wrong renewal date. The
    squeeze must produce a REFUSAL, not a cheap answer — and the refusal keeps the requested
    tier so tomorrow's wave need not re-run the router over content nothing has read."""
    plan = _plan(ExtractionRequest("d", "document", DOCUMENT, "T3"))
    at_floor = _cost(plan, TIER_FLOORS["document"])
    assert _cost(plan, "T1") < at_floor, ("the row is only meaningful if T1 WOULD have been "
                                          "affordable — otherwise it passes with no floor at all")
    batch = govern(plan, budget=Budget(daily_minor=at_floor - 1, t3_daily_minor=0,
                                       daily_call_cap=0), ledger=EMPTY_LEDGER)
    decided = batch.calls[0]
    assert not decided.admitted
    assert decided.reason == REASON_DAILY_BUDGET
    assert decided.tier == "T3"
    assert decided.estimated_cost_minor == 0
    assert not any(call.admitted and call.tier == "T1" for call in batch.calls)


def test_a_document_still_demotes_down_to_its_floor():
    """The floor is a floor, not a refusal to demote at all: T3 -> T2 is allowed and expected."""
    plan = _plan(ExtractionRequest("d", "document", DOCUMENT, "T3"))
    budget = Budget(daily_minor=_cost(plan, "T3"), t3_daily_minor=0, daily_call_cap=0)
    decided = govern(plan, budget=budget, ledger=EMPTY_LEDGER).calls[0]
    assert decided.admitted and decided.tier == "T2" and decided.tier_demoted


def test_a_group_is_admitted_or_refused_whole():
    """Chunk 1 admitted and chunk 7 refused is a contract with its termination clause missing
    and nothing in the output saying so."""
    plan = _plan(ExtractionRequest("a", "email", LONG_EMAIL, "T1"))
    assert len(plan.calls) > 1
    one_chunk = plan.calls[0].cost_minor("T1", DEFAULT_TIER_PRICES)
    budget = Budget(daily_minor=one_chunk, t3_daily_minor=0, daily_call_cap=0)

    batch = govern(plan, budget=budget, ledger=EMPTY_LEDGER)

    assert batch.admitted == 0
    assert {call.reason for call in batch.calls} == {REASON_DAILY_BUDGET}


def test_the_ledger_advances_inside_the_batch():
    """Forty calls that each fit the remaining budget and blow it together is the failure a
    per-call check is blind to: it is correct on every call and wrong on the batch."""
    requests = [ExtractionRequest(f"e{i}", "chat", CHAT, "T1") for i in range(6)]
    plan = _plan(*requests)
    each = plan.calls[0].cost_minor("T1", DEFAULT_TIER_PRICES)
    budget = Budget(daily_minor=each * 3, t3_daily_minor=0, daily_call_cap=0)

    batch = govern(plan, budget=budget, ledger=EMPTY_LEDGER)

    assert batch.admitted == 3
    assert batch.estimated_cost_minor == each * 3 <= budget.daily_minor
    assert [call.admitted for call in batch.calls] == [True, True, True, False, False, False]


def test_spend_already_on_the_ledger_counts_against_the_batch():
    plan = _plan(ExtractionRequest("a", "chat", CHAT, "T1"))
    each = plan.calls[0].cost_minor("T1", DEFAULT_TIER_PRICES)
    budget = Budget(daily_minor=each, t3_daily_minor=0, daily_call_cap=0)
    ledger = Ledger(spent_minor=each, t3_spent_minor=0, calls=1)
    assert govern(plan, budget=budget, ledger=ledger).calls[0].reason == REASON_DAILY_BUDGET


def test_a_tripped_breaker_refuses_everything_and_prices_nothing():
    """Pre-flight and all-or-nothing. There is no partial answer to a hard stop, and a refused
    call must cost zero or the batch total counts money nobody spent."""
    plan = _plan(ExtractionRequest("a", "email", EMAIL, "T2"),
                 ExtractionRequest("b", "chat", CHAT, "T1"))
    budget = Budget(daily_minor=100, t3_daily_minor=0, daily_call_cap=0)
    batch = govern(plan, budget=budget, ledger=Ledger(spent_minor=1_000, t3_spent_minor=0,
                                                      calls=0))
    assert batch.breaker_verdict.tripped
    assert batch.refused == len(plan.calls) and batch.admitted == 0
    assert batch.estimated_cost_minor == 0
    assert {call.reason for call in batch.calls} == {REASON_BREAKER_TRIPPED}
    assert all(call.estimated_cost_minor == 0 for call in batch.calls)


def test_the_call_ceiling_refuses_a_group_that_would_cross_it():
    """Money is not the only runaway. A loop re-extracting one cheap message stays under a
    dollar ceiling for a very long time."""
    plan = _plan(ExtractionRequest("a", "chat", CHAT, "T1"),
                 ExtractionRequest("b", "chat", CHAT, "T1"))
    budget = Budget(daily_minor=10_000_000, t3_daily_minor=10_000_000, daily_call_cap=1)
    batch = govern(plan, budget=budget, ledger=EMPTY_LEDGER)
    assert [call.reason for call in batch.calls] == [ADMITTED, REASON_CALL_CAP]


def test_an_oversized_chunk_is_refused_without_being_priced():
    """It cannot run at any tier — `render_prompt` raises on it — so refusing it here keeps it
    from displacing a call that could have run."""
    plan = _plan(ExtractionRequest("d", "document", OVERSIZED_DOC, "T3"),
                 ExtractionRequest("c", "chat", CHAT, "T1"))
    batch = govern(plan, budget=FULL_BUDGET, ledger=EMPTY_LEDGER)
    by_event = {call.call.event_id: call for call in batch.calls}
    assert by_event["d"].reason == REASON_OVERSIZED and not by_event["d"].admitted
    assert by_event["c"].admitted, "an unrunnable chunk must not refuse the rest of the batch"
    assert batch.estimated_cost_minor == by_event["c"].estimated_cost_minor


def test_decisions_come_back_in_plan_order():
    """A caller zipping `plan.calls` against `batch.calls` is the obvious thing to do, and
    per-group control flow would otherwise pair a decision with the wrong call in silence."""
    plan = _plan(ExtractionRequest("a", "document", MIXED_DOC, "T3"),
                 ExtractionRequest("b", "chat", CHAT, "T1"))
    assert [call.oversized for call in plan.calls[:2]] == [False, True], (
        "the fixture must put a runnable chunk BEFORE an unrunnable one, or the governor never "
        "reorders and this test cannot fail")
    batch = govern(plan, budget=FULL_BUDGET, ledger=EMPTY_LEDGER)
    assert [decided.call for decided in batch.calls] == list(plan.calls)
    assert [decided.reason for decided in batch.calls] == [ADMITTED, REASON_OVERSIZED, ADMITTED]
    assert batch.admitted_calls() == tuple(c for c in batch.calls if c.admitted)


def test_totals_add_up_to_the_admitted_calls():
    plan = _plan(ExtractionRequest("a", "email", EMAIL, "T3"),
                 ExtractionRequest("b", "chat", CHAT, "T1"))
    batch = govern(plan, budget=FULL_BUDGET, ledger=EMPTY_LEDGER)
    assert batch.estimated_cost_minor == sum(c.estimated_cost_minor
                                             for c in batch.admitted_calls())
    assert batch.estimated_t3_cost_minor == sum(c.estimated_cost_minor
                                                for c in batch.admitted_calls() if c.tier == "T3")
    assert batch.admitted + batch.refused == len(batch.calls)
    assert batch.currency == FULL_BUDGET.currency


# ── money ────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("tier", TIERS)
def test_every_cost_is_a_whole_number_of_minor_units(tier):
    plan = _plan(ExtractionRequest("a", "email", EMAIL, "T2"))
    cost = plan.calls[0].cost_minor(tier, DEFAULT_TIER_PRICES)
    assert isinstance(cost, int) and not isinstance(cost, bool)
    assert cost > 0


def test_cost_rounds_up_so_the_governor_never_under_estimates():
    """A rounding error in our favour, taken once per call across forty thousand calls, is a
    spend nobody approved. One token at 100 minor units per million must cost 1, not 0."""
    call = PlannedCall(event_id="a", profile_id="email", chunk_index=0, chunk_count=1,
                       chunk_start=0, content_chars=1, requested_tier="T1", floor_tier="T1",
                       input_tokens=1, output_tokens=1, oversized=False)
    prices = {"T1": TierPrice("T1", 100, 500, "test")}
    assert call.cost_minor("T1", prices) == 2


def test_tiers_are_priced_in_ascending_order():
    """T3 must cost more than T2 must cost more than T1, or demotion is not a saving and the
    whole governor is arithmetic that changes nothing."""
    costs = [DEFAULT_TIER_PRICES[tier].input_per_mtok for tier in TIERS]
    assert costs == sorted(costs) and len(set(costs)) == len(TIERS)


def test_prices_are_injectable_so_the_router_can_supply_the_real_table():
    """L1.4.10 owns the tier-to-snapshot mapping. When it lands it supplies the rates for the
    snapshots it actually calls, and the default table stops being load-bearing."""
    plan = _plan(ExtractionRequest("a", "email", EMAIL, "T2"))
    free = {tier: TierPrice(tier, 0, 0, "free") for tier in TIERS}
    priced = govern(plan, budget=Budget(daily_minor=1, t3_daily_minor=0, daily_call_cap=0),
                    ledger=EMPTY_LEDGER)
    free_batch = govern(plan, budget=Budget(daily_minor=1, t3_daily_minor=0, daily_call_cap=0),
                        ledger=EMPTY_LEDGER, prices=free)
    assert priced.admitted == 0, "one cent of budget does not buy a T2 email at list price"
    assert free_batch.admitted == 1 and free_batch.estimated_cost_minor == 0


@pytest.mark.parametrize("kwargs, fragment", [
    (dict(tier="T4", input_per_mtok=1, output_per_mtok=1, priced_against="x"), "unknown tier"),
    (dict(tier="T1", input_per_mtok=-1, output_per_mtok=1, priced_against="x"), "earn money"),
])
def test_an_impossible_price_is_refused(kwargs, fragment):
    with pytest.raises(ValueError, match=fragment):
        TierPrice(**kwargs)


@pytest.mark.parametrize("kwargs, fragment", [
    (dict(admitted=False, tier="T2", tier_demoted=False, estimated_cost_minor=7,
          reason=REASON_DAILY_BUDGET), "refused call must cost nothing"),
    (dict(admitted=False, tier="T2", tier_demoted=True, estimated_cost_minor=0,
          reason=REASON_DAILY_BUDGET), "was not demoted, it was refused"),
    (dict(admitted=True, tier="T2", tier_demoted=False, estimated_cost_minor=7,
          reason=REASON_OVERSIZED), "may not carry the refusal reason"),
])
def test_a_decision_that_contradicts_itself_is_refused(kwargs, fragment):
    """A refused call carrying a cost would be counted against a budget by a call that never
    ran; a refused call marked demoted would double-count in the counter that is supposed to
    tell an operator their budget is too small."""
    call = PlannedCall(event_id="a", profile_id="email", chunk_index=0, chunk_count=1,
                       chunk_start=0, content_chars=10, requested_tier="T2", floor_tier="T1",
                       input_tokens=10, output_tokens=10, oversized=False)
    with pytest.raises(ValueError, match=fragment):
        GovernedCall(call=call, **kwargs)


# ── D10 · the estimator is measured against a really assembled call ──────────────────────────
#
# The governor priced every call as `template/4 + 900` tokens and the assembled prompt is not
# that. `render_prompt` substitutes four blocks into the template, and two of them — the
# generated JSON schema and the closed vocabularies — are together ~7,800 characters, roughly
# 1,050 tokens MORE than the 900 the estimator assumed. A budget that under-counts by 1,050
# tokens on every call trips its breaker late, which means the org is already over spend before
# anything demotes; the demotion path is fine, the accounting feeding it was wrong.
#
# So the tolerance below is asserted against a prompt this test ASSEMBLES through the real
# `render_prompt`, never against a constant. A hard-coded expected size would drift silently the
# next time a field is added to `ExtractionResult` or a word is added to a closed set — the two
# edits most likely to move this number — and the test would then pass for a new reason.

def _assembled(profile_id: str, body: str, envelope: str) -> str:
    """The exact string the extractor sends for `body` under `profile_id`.

    Built from the same four calls `extractor._build_prompt` makes, in the same order, so the
    estimate is compared with the real thing rather than with a second model of it.
    """
    fenced = fence(body, nonce="0" * NONCE_CHARS)
    return render_prompt(profile_id, schema=generate_schema_block(), vocab=vocabulary_block(),
                         envelope=envelope, content=fenced.text).text


#: A realistic envelope, as `extractor._envelope_block` builds it: five keys, one line each.
ENVELOPE = ("direction: inbound\nsender: rohit@acme.com\nrecipients: harsh@genios.ai\n"
            "subject: Renewal and the pricing schedule\nthread position: message 2 of 5")

#: How far the estimate may sit from the assembled call, in basis points. Five per cent, and it
#: is a ONE-SIDED bound in the direction that matters: the estimate may never be BELOW the
#: assembled size, because an under-estimate is the defect, and it may not be more than 5% above
#: it, because an estimator that simply guesses high stops being a budget and starts being a
#: refusal generator.
ESTIMATE_TOLERANCE_BP = 500


@pytest.mark.parametrize("profile_id, body", [
    ("email", EMAIL),
    ("chat", CHAT),
    ("crm_note", CHAT),
    ("document", DOCUMENT),
    ("transcript", "Rohit: we can move forward.\nHarsh: I will send the schedule by Friday.\n"),
])
def test_the_input_estimate_matches_a_really_assembled_call(profile_id, body):
    """The estimate is what the call actually costs, within a stated tolerance, and never less."""
    request = ExtractionRequest(f"e-{profile_id}", profile_id, body, "T2",
                                envelope_chars=len(ENVELOPE))
    call = _plan(request).calls[0]
    assembled = -(-len(_assembled(profile_id, body, ENVELOPE)) // CHARS_PER_TOKEN)

    assert call.input_tokens >= assembled, (
        f"{profile_id}: the governor priced {call.input_tokens} tokens for a call that assembles "
        f"to {assembled}. It is short by {assembled - call.input_tokens} tokens on EVERY call, "
        "so the daily breaker trips after the money is already spent")
    slack = assembled * ESTIMATE_TOLERANCE_BP // BP_FULL
    assert call.input_tokens - assembled <= slack, (
        f"{profile_id}: {call.input_tokens} estimated against {assembled} assembled is more than "
        f"{ESTIMATE_TOLERANCE_BP}bp high; a governor that over-refuses is not a budget")


def test_the_fixed_overhead_is_measured_off_the_real_blocks_not_assumed():
    """Every substituted block is counted: the spine, the schema, the vocabularies, the fence.

    Asserted as an identity over the real generators rather than as a number, so adding a field
    to `ExtractionResult` re-prices the call instead of quietly widening the gap.
    """
    profile = get_profile("email")
    spine = len(profile.prompt_template.format(schema="", vocab="", envelope="", content=""))
    expected = -(-(spine + len(generate_schema_block()) + len(vocabulary_block())
                   + FENCE_OVERHEAD_CHARS) // CHARS_PER_TOKEN)
    assert fixed_prompt_tokens("email") == expected


def test_the_fence_overhead_is_a_constant_the_module_measured():
    """The nonce fence is fixed-length by construction, so its cost is measured once, not guessed."""
    for body in ("x", "y" * 5_000):
        assert len(fence(body).text) - len(body) == FENCE_OVERHEAD_CHARS


def test_a_declared_envelope_is_priced_and_an_undeclared_one_is_allowed_for():
    """The envelope is per-call content, so the caller declares it; the default is an ALLOWANCE
    that errs high, because a caller who did not declare must not be under-charged."""
    small = _plan(ExtractionRequest("a", "email", EMAIL, "T2", envelope_chars=0)).calls[0]
    large = _plan(ExtractionRequest("a", "email", EMAIL, "T2", envelope_chars=4_000)).calls[0]
    assert large.input_tokens - small.input_tokens == 4_000 // CHARS_PER_TOKEN
    default = _plan(ExtractionRequest("a", "email", EMAIL, "T2")).calls[0]
    assert default.input_tokens > small.input_tokens
    assert DEFAULT_ENVELOPE_CHARS > len(ENVELOPE), (
        "the default is an allowance, so it must sit above a real envelope rather than below it")


@pytest.mark.parametrize("envelope_chars, fragment", [
    (-1, "must not be negative"),
    (1.5, "must be an integer"),
])
def test_an_envelope_length_that_cannot_be_true_is_refused(envelope_chars, fragment):
    with pytest.raises((ValueError, TypeError)) as excinfo:
        ExtractionRequest("a", "email", EMAIL, "T2", envelope_chars=envelope_chars)
    assert fragment in str(excinfo.value)


def test_the_output_floor_covers_the_json_envelope_the_model_must_emit():
    """Even an extraction that finds nothing pays for the response shape's own key skeleton."""
    skeleton = 2 + sum(len(name) + 8 for name in ExtractionResult.model_fields)
    assert OUTPUT_FLOOR_TOKENS >= -(-skeleton // CHARS_PER_TOKEN)


# ── D10 · this governor agrees with the deployed breaker rather than shadowing it ─────────────

def test_the_deployed_daily_spend_ceiling_stops_calls_here_too():
    """`api/routes._llm_over_daily_cap` refuses to START work at `spent >= cap`. A governor whose
    own hard stop sits at 1.5x would admit calls the deployed control has already refused, so
    the money ceiling is asserted at 1x: at the budget, nothing is admitted and the refusal
    names the budget rather than the runaway threshold."""
    plan = _plan(ExtractionRequest("a", "email", EMAIL, "T1"))
    budget = Budget(daily_minor=_cost(plan, "T1"), t3_daily_minor=0, daily_call_cap=0)
    at_ceiling = Ledger(spent_minor=budget.daily_minor, t3_spent_minor=0, calls=0)

    verdict = breaker(budget, at_ceiling)
    assert verdict.tripped, ("the deployed breaker refuses a sync at this ledger; a pre-flight "
                             "here that admits it is a second, laxer ceiling")
    assert verdict.reason == REASON_DAILY_BUDGET
    assert verdict.budget_minor == budget.daily_minor

    batch = govern(plan, budget=budget, ledger=at_ceiling)
    assert batch.admitted == 0 and batch.refused == len(plan.calls)
    assert batch.estimated_cost_minor == 0


def test_the_runaway_threshold_still_names_itself_separately():
    """1x is the budget and 1.5x is the runaway; both trip, and a reader can tell which."""
    budget = Budget(daily_minor=10_000, t3_daily_minor=0, daily_call_cap=0)
    assert breaker(budget, Ledger(9_999, 0, 0)).reason == ADMITTED
    assert breaker(budget, Ledger(10_000, 0, 0)).reason == REASON_DAILY_BUDGET
    assert breaker(budget, Ledger(15_000, 0, 0)).reason == REASON_BREAKER_TRIPPED
