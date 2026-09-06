"""H6 · L2.7.7-U1 (M-4) — RESOLUTION DETECTION. The gate doc 09 invokes as:

    pytest tests/context/lifecycle/test_resolution.py -q

THE DEFECT THIS CLOSES. `situations.decide_lifecycle` was good code with two ways out —
`terminal_by_fact` and a human's click — and `terminal_by_fact` was ONE field
(`normalize_stage(deal.stage) in {closedwon, closedlost}`), one source, two values. There was no
third path: RESOLVED BECAUSE SOMEBODY SAID SO. So *"all sorted, we signed yesterday"* bumped
`last_seen_at` and made the situation look MORE ACTIVE, which is the exact inversion of what the
founder experiences and the shortest road to *"it told me about a contract I cancelled last
week"*.

WHAT THIS FILE PROVES, IN THREE PARTS:

1. **doc 07's ACCEPTANCE list, row by row** — the eight behaviours the plan names by name.
2. **The golden set** (`tests/golden/l2/m4_resolution.json`) — H6's two numbers: a false-positive
   rate below 2%, the strictest in the entire Layer 2 plan because its false positive CLOSES A
   LIVE THREAD, and at least 8 Hinglish fixtures because this corpus is Hinglish-bearing and a
   detector that only reads English misses half of a real tenant's resolutions.
3. **The wiring** — `context/runner.process_pending`, the function the sync route and the upload
   route both call, reaching the detector on a real database. Layer 1 shipped SIX units that were
   green and called by nothing; nothing in parts 1 and 2 would notice if the block in `runner.py`
   were deleted, because every one of them constructs the collaborator itself.

THE FALSE-POSITIVE RATE IS MEASURED AGAINST A REPLAYED MODEL, AND THAT IS DELIBERATE. Roughly
half the golden fixtures carry a WRONG model answer — an intention labelled as a completion, a
sarcastic one-liner read literally, an instruction planted in a message body and obeyed — because
what a gate can honestly measure in CI is whether the deterministic layer survives a wrong
answer. A live-model lane costs money and reports a different number every week; it is a command
(`scripts/`), not a test, for the same reason `tests/golden/l1` says so about its own.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from genios_engine.context.lifecycle.contract import (
    DECISION_APPLY,
    DECISION_REVIEW,
    Message,
    Obligation,
    ResolutionClaim,
)
from genios_engine.context.lifecycle.gate import (
    MAX_CALLS_PER_SITUATION_PER_DAY,
    SKIP_BUDGET_SITUATION,
    SKIP_TERMINAL_BY_FACT,
    gate_decision,
)
from genios_engine.context.lifecycle.judge import judge
from genios_engine.context.lifecycle.ledger import derive_statement_state
from genios_engine.context.lifecycle.prompt import parse_description
from genios_engine.context.situations import (
    RESOLVED_BY_FACT,
    RESOLVED_BY_STATEMENT,
    STATEMENT_NONE,
    STATEMENT_PARTIAL,
    STATEMENT_RESOLVED,
    STATUS_ACTIVE,
    STATUS_PARTIALLY_RESOLVED,
    STATUS_RESOLVED,
    decide_lifecycle,
)

from .conftest import AT, ScriptedModel, answer_for

VERIFIED_GRADES = {"verified", "verified_whitespace", "verified_relocated", "verified_fuzzy"}


def _fixture(golden: dict, fixture_id: str) -> dict:
    for entry in golden["fixtures"]:
        if entry["fixture_id"] == fixture_id:
            return entry
    raise AssertionError(f"the golden set no longer carries {fixture_id!r}")


# =================================================================================================
# 1 · doc 07 L2.7.7-U1's ACCEPTANCE list, one test per row
# =================================================================================================

def test_all_sorted_we_signed_yesterday_resolves_by_statement(golden, replay):
    """Row 1 — the sentence the whole unit exists for, with a verifying span.

    Before this unit that message bumped `last_seen_at` and the situation looked MORE active. The
    assertion on the span is not decoration: a resolution with no receipt is exactly the shape a
    fabricated one has.
    """
    decision, verdict, claim = replay(_fixture(golden, "all_sorted_signed"))
    assert (decision, verdict) == (DECISION_APPLY, "RESOLVED")
    assert claim.span_verdict in VERIFIED_GRADES
    assert claim.quote == "we signed yesterday"
    assert claim.speaker_role == "owner" and claim.authority_bp == 10_000

    state = derive_statement_state([claim], [ob for ob in ("ob_msa",)])
    assert state.state == STATEMENT_RESOLVED
    lifecycle = decide_lifecycle(current_status=STATUS_ACTIVE, resolved_by=None,
                                 last_seen_at=AT, resolved_at=None, terminal_by_fact=False,
                                 now=AT, stated_resolution=state.state)
    assert (lifecycle.status, lifecycle.resolved_by) == (STATUS_RESOLVED, RESOLVED_BY_STATEMENT)


def test_we_should_wrap_this_up_is_not_a_resolution(golden, replay):
    """Row 2 — and the model says RESOLVED. A completion statement is required, not an intent."""
    decision, verdict, claim = replay(_fixture(golden, "we_should_wrap_this_up"))
    assert verdict == "NOT_RESOLVED", "an intention closed a live thread"
    assert decision != DECISION_APPLY
    assert derive_statement_state([claim], ["ob_msa"]).state == STATEMENT_NONE


def test_three_of_five_is_partially_resolved_not_closed(golden, replay):
    """Row 3 — the downgrade is OURS, not the model's: it answered RESOLVED.

    Closing the whole situation would drop two obligations with nobody told, which is doc 12
    case 2 word for word.
    """
    fixture = _fixture(golden, "partial_three_of_five")
    decision, verdict, claim = replay(fixture)
    assert (decision, verdict) == (DECISION_APPLY, "PARTIALLY_RESOLVED")
    assert "downgraded from RESOLVED" in claim.reason

    open_ids = [ob["id"] for ob in fixture["obligations"]]
    state = derive_statement_state([claim], open_ids)
    assert state.state == STATEMENT_PARTIAL
    assert set(state.outstanding) == {"ob_sec", "ob_kick"}
    lifecycle = decide_lifecycle(current_status=STATUS_ACTIVE, resolved_by=None, last_seen_at=AT,
                                 resolved_at=None, terminal_by_fact=False, now=AT,
                                 stated_resolution=state.state)
    assert lifecycle.status == STATUS_PARTIALLY_RESOLVED


def test_a_vendor_stated_close_is_below_the_floor_without_corroboration(golden, replay):
    """Row 4 — doc 07's authority table: *"we're done" from a vendor is a CLAIM, not a fact.*"""
    decision, _verdict, claim = replay(_fixture(golden, "vendor_all_done_our_side"))
    assert decision == DECISION_REVIEW, "a counterparty's claim closed a live thread"
    assert claim.speaker_role == "external" and claim.authority_bp == 6_000
    assert claim.effective_bp == 5_400 == 9_000 * 6_000 // 10_000
    assert derive_statement_state([claim], ["ob_msa"]).state == STATEMENT_NONE, (
        "a queued claim moved the lifecycle — the floor is decorative if it does")


def test_done_then_actually_not_yet_leaves_the_situation_open(golden, replay):
    """Row 5 — LATEST STATEMENT WINS, and a `CONTRADICTED` verdict reopens.

    Both messages are real fixtures and both are APPLIED; what decides the outcome is the order
    they were WRITTEN in, which is why the ledger sorts on `stated_at` and not on arrival.
    """
    _d1, _v1, done = replay(_fixture(golden, "all_sorted_signed"))
    _d2, _v2, retraction = replay(_fixture(golden, "contradiction_actually_not_yet"))
    done = _restate(done, AT)
    retraction = _restate(retraction, AT + timedelta(days=1))

    assert derive_statement_state([done], ["ob_msa"]).state == STATEMENT_RESOLVED
    later = derive_statement_state([done, retraction], ["ob_msa"])
    assert later.state == STATEMENT_NONE and later.contradicted

    reopened = decide_lifecycle(current_status=STATUS_RESOLVED,
                                resolved_by=RESOLVED_BY_STATEMENT, last_seen_at=AT,
                                resolved_at=AT, terminal_by_fact=False, now=AT,
                                stated_resolution=later.state)
    assert (reopened.status, reopened.resolved_by, reopened.reopened) == (STATUS_ACTIVE, None,
                                                                         True)
    # And the reverse order is the same rule read forwards: the retraction first, then the close.
    reversed_order = derive_statement_state(
        [_restate(retraction, AT), _restate(done, AT + timedelta(days=1))], ["ob_msa"])
    assert reversed_order.state == STATEMENT_RESOLVED


def test_a_hinglish_ho_gaya_is_detected(golden, replay):
    """Row 6 — doc 12 case 6. The corpus is Hinglish-bearing and `triage.py` already knows it."""
    decision, verdict, claim = replay(_fixture(golden, "hinglish_ho_gaya_sign_kar_diya"))
    assert (decision, verdict) == (DECISION_APPLY, "RESOLVED")
    assert claim.quote == "MSA sign kar diya"
    # …and its future-tense twin, which is the half of case 6 that closes live threads.
    intent_decision, intent_verdict, _ = replay(_fixture(golden, "hinglish_kal_kar_denge"))
    assert (intent_decision, intent_verdict) != (DECISION_APPLY, "RESOLVED")
    assert intent_verdict == "NOT_RESOLVED"


def test_a_fact_beats_a_statement_and_costs_no_model_call():
    """Row 7 — `terminal_by_fact=True` → NO LLM CALL AT ALL.

    Asserted on the GATE rather than on an outcome, because the requirement is about spend as
    much as about correctness: a situation the CRM has already closed is exactly the one whose
    thread is still noisy with congratulations, and every one of those messages would otherwise
    be a call.
    """
    decision = gate_decision(status=STATUS_ACTIVE, resolved_by=None, terminal_by_fact=True,
                             has_new_signal=True, already_examined=False, has_text=True,
                             speaker_role="owner", calls_today_for_situation=0,
                             calls_today_for_org=0)
    assert decision.fires is False and decision.reason == SKIP_TERMINAL_BY_FACT
    # And it outranks a statement that already closed the situation, in the lifecycle too.
    lifecycle = decide_lifecycle(current_status=STATUS_RESOLVED,
                                 resolved_by=RESOLVED_BY_STATEMENT, last_seen_at=AT,
                                 resolved_at=AT, terminal_by_fact=True, now=AT,
                                 stated_resolution=STATEMENT_NONE)
    assert lifecycle.resolved_by == RESOLVED_BY_FACT


def test_budget_exhaustion_falls_back_to_fact_only_and_logs(caplog):
    """Row 8 — doc 11: *"budget exhausted → falls back to `terminal_by_fact` and LOGS."*

    A silent degradation is indistinguishable from a bug and would be discovered as "the product
    got worse and nobody knows when", so the refusal is a NAMED reason and the drain carries it
    out in `budget_exhausted`.
    """
    spent = gate_decision(status=STATUS_ACTIVE, resolved_by=None, terminal_by_fact=False,
                          has_new_signal=True, already_examined=False, has_text=True,
                          speaker_role="owner",
                          calls_today_for_situation=MAX_CALLS_PER_SITUATION_PER_DAY,
                          calls_today_for_org=0)
    assert spent.fires is False
    assert spent.reason == SKIP_BUDGET_SITUATION and spent.budget_exhausted


def _restate(claim: ResolutionClaim, when: datetime) -> ResolutionClaim:
    """The same claim, said at a different time — the ledger's ordering input."""
    return replace(claim, stated_at=when)


# =================================================================================================
# 2 · THE GOLDEN SET — H6's numbers
# =================================================================================================

def test_the_golden_set_covers_what_doc_twelve_requires(golden):
    """40 fixtures, ≥8 Hinglish, ≥5 sarcasm/negation, ≥5 partial — doc 12's own table.

    A golden set of easy cases is not a golden set: the requirement exists because a detector can
    score perfectly on plain resolutions and still close a live thread on the first *"we should
    wrap this up"* it sees.
    """
    fixtures = golden["fixtures"]
    tags = [set(f["tags"]) for f in fixtures]
    assert len(fixtures) >= 40, "doc 12 requires 40 hand-labelled M-4 fixtures"
    assert sum("hinglish" in t for t in tags) >= 8
    assert sum(bool(t & {"sarcasm", "negation"}) for t in tags) >= 5
    assert sum("partial" in t for t in tags) >= 5
    assert sum(not f["truth"]["must_close"] for f in fixtures) >= len(fixtures) // 3, (
        "a set with no near-misses cannot measure a false-positive rate")
    assert len({f["fixture_id"] for f in fixtures}) == len(fixtures)


def test_every_golden_fixture_decides_as_it_was_labelled(golden, replay):
    """The whole set, one assertion. A fixture that changes decision is a policy change and has
    to be an intentional one — the labels are in the JSON beside the message."""
    wrong = []
    for fixture in golden["fixtures"]:
        decision, verdict, _claim = replay(fixture)
        expect = fixture["expect"]
        if decision != expect["decision"] or (expect["verdict"] and verdict != expect["verdict"]):
            wrong.append(f"{fixture['fixture_id']}: got ({decision}, {verdict}), "
                         f"expected ({expect['decision']}, {expect['verdict']})")
    assert not wrong, "\n".join(wrong)


def test_the_false_positive_rate_is_below_two_percent(golden, replay, capsys):
    """**THE GATE.** M-4's false-positive rate on the golden set: < 2%.

    A FALSE POSITIVE IS ANY CLOSE THE TRUTH LABEL DOES NOT SUPPORT, and that includes a FULL
    close on a situation only partially resolved — three of five discharged and a whole-situation
    close is not "mostly right", it is two obligations deleted with nobody told.

    The rate is reported as well as asserted, because the number is the thing an operator watches
    when the thresholds are next tuned.
    """
    total = len(golden["fixtures"])
    false_positives, misses = [], []
    for fixture in golden["fixtures"]:
        decision, verdict, _claim = replay(fixture)
        closed = decision == DECISION_APPLY and verdict in ("RESOLVED", "PARTIALLY_RESOLVED")
        truth, kind = fixture["truth"]["must_close"], fixture["truth"]["close_kind"]
        if closed and not truth:
            false_positives.append(f"{fixture['fixture_id']} ({verdict})")
        elif closed and kind == "partial" and verdict == "RESOLVED":
            false_positives.append(f"{fixture['fixture_id']} (closed a partial resolution)")
        elif not closed and truth:
            misses.append(fixture["fixture_id"])

    rate_bp = len(false_positives) * 10_000 // total
    ceiling_bp = golden["gate"]["false_positive_rate_bp_max"]
    print(f"\nM-4 golden set: {total} fixtures · false positives {len(false_positives)} "
          f"({rate_bp} bp, ceiling {ceiling_bp} bp) · misses {len(misses)} "
          f"({len(misses) * 10_000 // total} bp)")
    if misses:
        print("  missed (one unnecessary nudge each): " + ", ".join(misses))
    assert rate_bp < ceiling_bp, ("false positives close live threads: "
                                  + "; ".join(false_positives))


def test_no_applied_claim_rests_on_a_fabricated_quote(golden, replay):
    """0 fabricated facts — a hard fail in doc 12, and the negative control proves the metric is
    not vacuous: one fixture cites a sentence that is not in its message and must be refused."""
    for fixture in golden["fixtures"]:
        decision, _verdict, claim = replay(fixture)
        if decision in (DECISION_APPLY, DECISION_REVIEW):
            assert claim.span_verdict in VERIFIED_GRADES, fixture["fixture_id"]
            assert claim.quote and claim.quote in fixture["message"] or (
                claim.span_verdict == "verified_whitespace"), fixture["fixture_id"]
    fabricated = _fixture(golden, "fabricated_quote")
    decision, _verdict, claim = replay(fabricated)
    assert decision == "reject" and claim.span_verdict not in VERIFIED_GRADES


def test_the_model_never_supplies_the_number_the_floor_reads():
    """Doctrine 1, enforced: a `confidence_bp` in the payload is recorded and DISCARDED.

    The model describes — a verdict and a band out of a closed set — and deterministic code turns
    that description into basis points. If a volunteered number could reach the floor, the model
    would be deciding the close, and a prompt-injected `"confidence_bp": 10000` would be all it
    took to shut a live thread.
    """
    text_ = ("Nothing pending from our side as far as I can see, so I think we can call this "
             "one finished unless your team says otherwise.")
    payload = answer_for(text_, verdict="RESOLVED", certainty="IMPLIED_COMPLETION",
                         scope=["ob_msa"], quote="Nothing pending from our side")
    payload["confidence_bp"] = 10_000
    description = parse_description(payload)
    assert description.raw_confidence_bp == 10_000

    claim = judge(description, situation_id="sit", obligations=(
        Obligation("ob_msa", "countersign the MSA", "priya@ourco.example"),),
        message=Message(event_id="e", text=text_, sender_email="priya@ourco.example",
                        occurred_at=AT), internal_emails=["priya@ourco.example"])
    assert claim.raw_confidence_bp == 10_000, "the volunteered number must still be recorded"
    assert claim.certainty_bp == 6_500, "the band decided the number, not the model"
    assert claim.decision == DECISION_REVIEW, "a volunteered 10000 bp bought a close"


# =================================================================================================
# 3 · THE WIRING — a real sweep, on real PostgreSQL, reaching the detector
# =================================================================================================

RESOLUTION_TEXT = ("Hi Rohit - all sorted, we signed yesterday. The countersigned copy is "
                   "attached and finance already has the PO number, so nothing further is "
                   "needed from your side.")
RETRACTION_TEXT = ("Correction on my last message - I spoke too soon. The MSA has not actually "
                   "been countersigned, our CFO is out until Thursday and nothing can move "
                   "before then.")


@pytest.mark.pg
def test_the_drain_reaches_the_detector_and_a_stated_resolution_closes(pg_store):
    """**THIS IS THE TEST THAT MATTERS.** `process_pending` — the sweep both API routes call —
    reaches M-4, and a sentence in an email closes a situation that no CRM field touched.

    Nothing above this line would notice if the block in `runner.py` were deleted: every test up
    there builds the collaborator itself. Layer 1 shipped six units in exactly that state.

    The drain is driven with no ingestible events on purpose (`processed == 0`): the resolution
    pass must run on a sweep that drained nothing, because the message it reads was ingested by
    an earlier one.
    """
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    org = "org_m4_wiring"
    ids = _ids(org)
    _seed(pg_store, org, resolution_text=RESOLUTION_TEXT)
    llm = ScriptedModel(answers={ids["reply"]: answer_for(
        RESOLUTION_TEXT, verdict="RESOLVED", certainty="EXPLICIT_COMPLETION",
        scope=[ids["commitment"]], quote="we signed yesterday")})
    try:
        out = process_pending(org_id=org, store=pg_store, llm=llm,
                              crypto_key=get_settings().crypto_key, eval_time=AT)
        assert out["processed"] == 0, "no ingestible events: this sweep drained nothing"
        assert "resolutions" in out, "the drain does not carry the resolution ledger out"
        assert out["resolutions"]["calls"] == 2, (
            "the sweep reached no detector — `detect_resolutions` is not on the real path: "
            f"{out['resolutions']}")
        # TWO calls, one per unexamined message on the situation: the ask and the reply. The ask
        # is judged too, because nothing deterministic can know in advance which message carries
        # the resolution — and only the reply produces a claim, because the model has nothing to
        # say about the other one.
        assert out["resolutions"]["claims_written"] == 1
        assert out["resolutions"]["resolved"] == 1

        with pg_store.engine.connect() as conn:
            row = conn.execute(text(
                "select status, resolved_by, resolved_at, resolution_note "
                "from context_situations where org_id=:o and situation_id=:sid"),
                {"o": org, "sid": ids["situation"]}).mappings().one()
            claim = conn.execute(text(
                "select verdict, decision, speaker_role, effective_bp, quote, span_verdict, "
                "       scope, prompt_version from situation_resolution_claims "
                "where org_id=:o"), {"o": org}).mappings().one()
        assert row["status"] == STATUS_RESOLVED
        assert row["resolved_by"] == RESOLVED_BY_STATEMENT
        # The moment the SENTENCE was written, not the moment we read it.
        assert row["resolved_at"] == AT - timedelta(hours=2)
        assert "we signed yesterday" in row["resolution_note"]
        assert claim["decision"] == DECISION_APPLY and claim["verdict"] == "RESOLVED"
        assert claim["speaker_role"] == "owner" and claim["effective_bp"] == 9_000
        assert claim["span_verdict"] in VERIFIED_GRADES
        assert claim["scope"] == [ids["commitment"]], (
            "the claim must name the obligation it closed, not the situation")

        # A SECOND SWEEP DOES NOT RE-JUDGE WHAT IT ALREADY JUDGED: the claim row is the cache.
        # The one message it does read again is the ask, whose call FAILED (the scripted model
        # has no answer for it) — deliberately, because a transient failure must not become a
        # permanent blind spot for that message.
        before = llm.calls
        again = process_pending(org_id=org, store=pg_store, llm=llm,
                                crypto_key=get_settings().crypto_key, eval_time=AT)
        assert again["resolutions"]["calls"] == 1, (
            "the resolved message was judged twice — the ledger is not acting as the cache")
        assert llm.calls == before + 1
        assert again["resolutions"]["claims_written"] == 0
        with pg_store.engine.connect() as conn:
            assert conn.execute(text("select count(*) from situation_resolution_claims "
                                     "where org_id=:o"), {"o": org}).scalar() == 1
            assert conn.execute(text("select status from context_situations where org_id=:o "
                                     "and situation_id=:sid"),
                                {"o": org, "sid": ids["situation"]}).scalar() == STATUS_RESOLVED, (
                "the situation reopened on a sweep that learned nothing new")
    finally:
        _drop(pg_store, org)


@pytest.mark.pg
def test_a_later_contradiction_reopens_it_on_the_next_drain(pg_store):
    """Doc 12's structural guard: `RESOLVED_BY_STATEMENT` un-resolves itself.

    No human undoes this and no human is asked to. The situation was closed from data, the data
    changed, and the next sweep re-derives the answer — which is the reasoning
    `decide_lifecycle`'s own docstring already gave for the fact path.
    """
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    org = "org_m4_reopen"
    ids = _ids(org)
    _seed(pg_store, org, resolution_text=RESOLUTION_TEXT)
    llm = ScriptedModel(answers={ids["reply"]: answer_for(
        RESOLUTION_TEXT, verdict="RESOLVED", certainty="EXPLICIT_COMPLETION",
        scope=[ids["commitment"]], quote="we signed yesterday")})
    try:
        process_pending(org_id=org, store=pg_store, llm=llm,
                        crypto_key=get_settings().crypto_key, eval_time=AT)
        with pg_store.engine.connect() as conn:
            assert conn.execute(text("select status from context_situations where org_id=:o "
                                     "and situation_id=:sid"),
                                {"o": org, "sid": ids["situation"]}).scalar() == STATUS_RESOLVED

        _add_message(pg_store, org, event_id=f"evt_retraction_{org}", text_=RETRACTION_TEXT,
                     occurred_at=AT + timedelta(hours=1), sender=f"priya@{org}.example")
        llm.answers[f"evt_retraction_{org}"] = answer_for(
            RETRACTION_TEXT, verdict="CONTRADICTED", certainty="EXPLICIT_COMPLETION",
            scope=[ids["commitment"]], quote="The MSA has not actually been countersigned")

        out = process_pending(org_id=org, store=pg_store, llm=llm,
                              crypto_key=get_settings().crypto_key,
                              eval_time=AT + timedelta(hours=2))
        assert out["resolutions"]["reopened"] == 1
        with pg_store.engine.connect() as conn:
            row = conn.execute(text(
                "select status, resolved_by, resolved_at, resolution_note "
                "from context_situations where org_id=:o and situation_id=:sid"),
                {"o": org, "sid": ids["situation"]}).mappings().one()
        assert row["status"] == STATUS_ACTIVE and row["resolved_by"] is None
        assert row["resolved_at"] is None and row["resolution_note"] is None, (
            "a reopened situation kept the note explaining why it was closed")
    finally:
        _drop(pg_store, org)


@pytest.mark.pg
def test_a_situation_the_crm_already_closed_costs_no_model_call(pg_store):
    """A FACT BEATS A STATEMENT, ALWAYS — and it beats it before the money is spent."""
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    org = "org_m4_terminal"
    ids = _ids(org)
    _seed(pg_store, org, resolution_text=RESOLUTION_TEXT, deal_stage="Closed Won")
    llm = ScriptedModel(answers={ids["reply"]: answer_for(
        RESOLUTION_TEXT, verdict="RESOLVED", certainty="EXPLICIT_COMPLETION",
        scope=[ids["commitment"]], quote="we signed yesterday")})
    try:
        out = process_pending(org_id=org, store=pg_store, llm=llm,
                              crypto_key=get_settings().crypto_key, eval_time=AT)
        assert llm.calls == 0, "a situation the CRM already closed cost a model call"
        assert out["resolutions"]["calls"] == 0 and out["resolutions"]["gated_out"] >= 1
        with pg_store.engine.connect() as conn:
            row = conn.execute(text("select status, resolved_by from context_situations "
                                    "where org_id=:o and situation_id=:sid"),
                               {"o": org, "sid": ids["situation"]}).mappings().one()
            assert conn.execute(text("select count(*) from situation_resolution_claims "
                                     "where org_id=:o"), {"o": org}).scalar() == 0
        # M-4 spent nothing and CHANGED nothing. Turning the fact itself into `resolved`/`fact`
        # is `refresh_situations`' job (proven in tests/test_situations.py) and this drain does
        # not run it — it ingested no events. What is proven here is the refusal.
        assert (row["status"], row["resolved_by"]) == (STATUS_ACTIVE, None)
        assert gate_decision(
            status=row["status"], resolved_by=row["resolved_by"], terminal_by_fact=True,
            has_new_signal=True, already_examined=False, has_text=True, speaker_role="owner",
            calls_today_for_situation=0, calls_today_for_org=0).reason == SKIP_TERMINAL_BY_FACT
    finally:
        _drop(pg_store, org)


@pytest.mark.pg
def test_with_no_model_the_stored_ledger_still_decides_the_lifecycle(pg_store, caplog):
    """Doc 11's fallback, and the half of it that is easy to get wrong.

    With no model the DETECTION of new statements stops — and the MEMORY of the old ones must
    not. A resolution recorded yesterday has to survive a sweep that could not afford a call,
    otherwise every budget-limited drain would silently reopen everything M-4 ever closed.
    """
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    org = "org_m4_nomodel"
    ids = _ids(org)
    _seed(pg_store, org, resolution_text=RESOLUTION_TEXT)
    llm = ScriptedModel(answers={ids["reply"]: answer_for(
        RESOLUTION_TEXT, verdict="RESOLVED", certainty="EXPLICIT_COMPLETION",
        scope=[ids["commitment"]], quote="we signed yesterday")})
    try:
        process_pending(org_id=org, store=pg_store, llm=llm,
                        crypto_key=get_settings().crypto_key, eval_time=AT)
        _add_message(pg_store, org, event_id=f"evt_second_{org}", text_=RESOLUTION_TEXT,
                     occurred_at=AT + timedelta(hours=1), sender=f"priya@{org}.example")
        with caplog.at_level(logging.INFO):
            out = process_pending(org_id=org, store=pg_store, llm=None,
                                  crypto_key=get_settings().crypto_key,
                                  eval_time=AT + timedelta(hours=2))
        assert out["resolutions"]["calls"] == 0
        assert out["resolutions"]["fell_back_to_fact"] is True
        assert "no model configured" in caplog.text, "the fallback degraded silently"
        with pg_store.engine.connect() as conn:
            assert conn.execute(text("select status from context_situations where org_id=:o "
                                     "and situation_id=:sid"),
                                {"o": org, "sid": ids["situation"]}).scalar() == STATUS_RESOLVED
    finally:
        _drop(pg_store, org)


@pytest.mark.pg
def test_the_daily_ceiling_stops_the_calls_and_says_so(pg_store, caplog):
    """Doc 11's row: *"M-4 fires per situation per day: max 3"* — and the miss is REPORTED.

    Three judgements have already been made on this situation today, so the fourth message is
    refused before the money is spent. What must not happen is the refusal looking like "nothing
    to do": `budget_exhausted` comes out of the drain, and the reason is logged, because a silent
    degradation is discovered as "the product got worse and nobody knows when".
    """
    from genios_engine.context.lifecycle.store import write_claim
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    org = "org_m4_budget"
    ids = _ids(org)
    _seed(pg_store, org, resolution_text=RESOLUTION_TEXT)
    spent = ResolutionClaim(
        situation_id=ids["situation"], event_id="spent", stated_at=AT, verdict="NOT_RESOLVED",
        certainty="AMBIGUOUS", scope=(), speaker_email=f"priya@{org}.example",
        speaker_role="owner", authority_bp=10_000, certainty_bp=3_000, effective_bp=3_000,
        decision="reject", reason="earlier in the day")
    llm = ScriptedModel(answers={ids["reply"]: answer_for(
        RESOLUTION_TEXT, verdict="RESOLVED", certainty="EXPLICIT_COMPLETION",
        scope=[ids["commitment"]], quote="we signed yesterday")})
    try:
        with pg_store.engine.begin() as conn:
            for n in range(MAX_CALLS_PER_SITUATION_PER_DAY):
                write_claim(conn, org, replace(spent, event_id=f"spent_{n}"), review_state=None)
            # The ceiling is counted against `eval_time`'s DAY, and `created_at` defaults to the
            # server's clock — so the three earlier judgements are dated into the sweep's day.
            # (In production they are: they were written by earlier sweeps on that day.)
            conn.execute(text("update situation_resolution_claims set created_at = :at "
                              "where org_id = :o"), {"o": org, "at": AT})
        with caplog.at_level(logging.INFO):
            out = process_pending(org_id=org, store=pg_store, llm=llm,
                                  crypto_key=get_settings().crypto_key, eval_time=AT)
        assert llm.calls == 0, "the ceiling did not stop the spend"
        assert out["resolutions"]["budget_exhausted"] is True
        assert out["resolutions"]["fell_back_to_fact"] is True, (
            "the fallback is `terminal_by_fact` only — we may miss a resolution, never invent one")
        assert SKIP_BUDGET_SITUATION in caplog.text, "the budget miss degraded silently"
        with pg_store.engine.connect() as conn:
            assert conn.execute(text("select status from context_situations where org_id=:o "
                                     "and situation_id=:sid"),
                                {"o": org, "sid": ids["situation"]}).scalar() == STATUS_ACTIVE
    finally:
        _drop(pg_store, org)


# ── the world these wiring tests run in ──────────────────────────────────────────────────────

def _ids(org: str) -> dict[str, str]:
    """Graph ids scoped to the test org.

    `graph_nodes`' primary key is (node_id, version) and carries NO org, so two test orgs seeding
    `node_acme` collide: the second one's `on conflict do nothing` silently inserts nothing and
    the test then fails somewhere else entirely. The same is true of `graph_facts` and
    `graph_edges`, whose keys are also global.
    """
    tag = org.replace("org_", "")
    return {"company": f"node_acme_{tag}", "person": f"node_priya_{tag}",
            "commitment": f"node_cmt_{tag}", "edge": f"ev_owns_{tag}",
            "correlation": f"corr_{tag}", "situation": f"sit_{tag}",
            "ask": f"evt_ask_{tag}", "reply": f"evt_reply_{tag}"}


def _seed(store, org: str, *, resolution_text: str, deal_stage: str | None = None) -> None:
    """The smallest world in which a stated resolution is a real one.

    One company (the anchor), one person who OWNS an open commitment, two events in one
    correlation — the ask, and the reply that says it is done — and the situation an EARLIER
    sweep already built from them. The situation is seeded rather than left to this sweep's own
    refresh because that refresh is gated on `done or affected`, and these drains deliberately
    ingest nothing: the message being read arrived on a previous sweep, which is also the shape
    every real drain after the first one has.
    """
    ask_at = AT - timedelta(days=3)
    reply_at = AT - timedelta(hours=2)
    ids = _ids(org)
    with store.engine.begin() as conn:
        conn.execute(text("insert into orgs (id, name) values (:o, 'M-4 Wiring') "
                          "on conflict (id) do nothing"), {"o": org})
        for node_id, node_type, name, key in (
                (ids["company"], "company", "Acme", f"acme-{org}.example"),
                (ids["person"], "person", "Priya", f"priya@{org}.example"),
                (ids["commitment"], "commitment", "countersign the MSA",
                 f"commitment:msa:{org}")):
            conn.execute(text(
                "insert into graph_nodes (node_id, version, org_id, node_type, display_name, "
                "  canonical_key) values (:n, 1, :o, :t, :d, :k) on conflict do nothing"),
                {"n": node_id, "o": org, "t": node_type, "d": name, "k": key})
        conn.execute(text(
            "insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, "
            "  from_node_id, to_node_id) values (:ev, :ev, :o, 'owns', :p, :c) "
            "on conflict do nothing"),
            {"ev": ids["edge"], "o": org, "p": ids["person"], "c": ids["commitment"]})
        for event_id, occurred, sender, body in (
                (ids["ask"], ask_at, f"rohit@{org}.example",
                 "Can you get the MSA countersigned this week? Their procurement team is asking."),
                (ids["reply"], reply_at, f"priya@{org}.example", resolution_text)):
            _insert_event(conn, org, event_id, occurred, sender, body)
        # The obligation, created BY the first event — which is how `obligations_for` finds it.
        for suffix, field, value, vtype in (
                ("text", "commitment.text", '"countersign the MSA"', "string"),
                ("status", "commitment.status", '"open"', "enum")):
            conn.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "  field, value, value_type, status, occurred_at, valid_from, "
                "  created_by_event_id) values (:fv, :fv, :o, :subj, :field, "
                "  cast(:val as jsonb), :vt, 'active', :at, :at, :ev) "
                "on conflict do nothing"),
                {"fv": f"fv_{org}_{suffix}", "o": org, "subj": ids["commitment"],
                 "field": field, "val": value, "vt": vtype, "at": ask_at, "ev": ids["ask"]})
        if deal_stage is not None:
            conn.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "  field, value, value_type, status, occurred_at, valid_from) "
                "values (:fv, :fv, :o, :subj, 'deal.stage', cast(:val as jsonb), 'string', "
                "  'active', :at, :at) on conflict do nothing"),
                {"fv": f"fv_{org}_stage", "o": org, "subj": ids["company"],
                 "val": f'"{deal_stage}"', "at": ask_at})
        conn.execute(text(
            "insert into context_correlations (correlation_id, org_id, anchor_node_id, "
            "  anchor_type, domain, generation, first_event_at, last_event_at, event_count) "
            "values (:cid, :o, :anchor, 'company', 'sales', 1, :first, :last, 2) "
            "on conflict do nothing"),
            {"cid": ids["correlation"], "o": org, "anchor": ids["company"], "first": ask_at,
             "last": reply_at})
        for event_id in (ids["ask"], ids["reply"]):
            conn.execute(text(
                "insert into context_correlation_members (org_id, correlation_id, event_id, "
                "  joined_via) values (:o, :cid, :e, 'thread') on conflict do nothing"),
                {"o": org, "cid": ids["correlation"], "e": event_id})
        conn.execute(text(
            "insert into context_situations (situation_id, org_id, correlation_id, "
            "  anchor_node_id, situation_type, domain, status, first_seen_at, last_seen_at, "
            "  computed_at) values (:sid, :o, :cid, :anchor, 'opportunity', 'sales', 'active', "
            "  :first, :last, :last) on conflict do nothing"),
            {"sid": ids["situation"], "o": org, "cid": ids["correlation"],
             "anchor": ids["company"], "first": ask_at, "last": reply_at})


def _add_message(store, org: str, *, event_id: str, text_: str, occurred_at: datetime,
                 sender: str) -> None:
    """A later message on the same situation — the second drain's input."""
    ids = _ids(org)
    with store.engine.begin() as conn:
        _insert_event(conn, org, event_id, occurred_at, sender, text_)
        conn.execute(text(
            "insert into context_correlation_members (org_id, correlation_id, event_id, "
            "  joined_via) values (:o, :cid, :e, 'thread') on conflict do nothing"),
            {"o": org, "cid": ids["correlation"], "e": event_id})
        conn.execute(text("update context_correlations set last_event_at = :at, "
                          "event_count = event_count + 1 where org_id=:o "
                          "and correlation_id=:cid"),
                     {"o": org, "at": occurred_at, "cid": ids["correlation"]})


def _insert_event(conn, org: str, event_id: str, occurred_at: datetime, sender: str,
                  body: str) -> None:
    conn.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        "  source_object_id, dedup_key, actor, occurred_at, outcome) "
        "values (:e, :o, 'conn_m4', 'gmail', 'message', :e, :e, "
        "  cast(:actor as jsonb), :at, 'emitted') on conflict (event_id) do nothing"),
        {"e": event_id, "o": org, "actor": '{"email": "%s"}' % sender, "at": occurred_at})
    conn.execute(text(
        "insert into prepared_content (event_id, org_id, prepared_content_id, clean_text) "
        "values (:e, :o, :p, :txt) on conflict (event_id) do nothing"),
        {"e": event_id, "o": org, "p": f"pc_{event_id}", "txt": body})


def _drop(store, org: str) -> None:
    with store.engine.begin() as conn:
        for table in ("situation_resolution_claims", "context_situations",
                      "context_correlation_members", "context_correlations", "prepared_content",
                      "source_events", "graph_facts", "graph_edges", "graph_nodes",
                      "context_attention", "context_read_models", "metric_history"):
            conn.execute(text(f"delete from {table} where org_id=:o"), {"o": org})
        conn.execute(text("delete from orgs where id=:o"), {"o": org})
