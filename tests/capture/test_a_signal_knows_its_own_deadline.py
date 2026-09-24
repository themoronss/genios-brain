"""Step 14 · a timestamp is not temporal meaning, and reply pairing has no owner in Layer 1.

    pytest tests/capture/test_a_signal_knows_its_own_deadline.py -q

**A SIGNAL CANNOT SAY "8 DAYS OVERDUE".** `QualifiedEnterpriseSignal` carries three `_at` fields —
`occurred_at`, `expires_at`, `ingested_at` — and the last is a PROCESSING fact, not a world one. The
deadline lives inside `Commitment.due`, a claim nested in the extraction, so **nothing can sort or
sweep by it**. P2's *"8 days overdue"* is unanswerable from the object L2 receives.

**AND REPLY PAIRING BELONGS HERE.** `structural/threads.py` already computes `last_inbound_at`,
`last_outbound_at`, `turn_index` and `ball_in_court`. The LATENCY is computed in
`context/waiting.py` — Layer 2. But the pairing itself (this inbound, that outbound, Δt) is
**mechanical**: no judgement, no context, no model. The *judgement* — Claude's *"binary responder:
9 of 14 under 30 minutes"* — is a pattern over many pairs and is correctly L2's.

⛔ **§8 REQUIRES READING `context/waiting.py` BEFORE WRITING ANYTHING**, and §5's 14-U5 says the two
rules are *"honoured by READING the existing logic, then moving it — not writing a second version"*.
So here it is, as it actually stands:

    pending = None
    for direction, at in timeline:
        if direction == "out":
            if pending is None:        # ← consecutive outbounds: only the FIRST is pending
                pending = at
        elif pending is not None:      # ← only the FIRST reply after an outbound counts
            gaps.append(...)
            pending = None

Its docstring states both in words: *"a thread where they answered once and then sent four more
messages describes one reply latency, not five. Consecutive outbounds with no reply between them
contribute nothing — an unanswered message has no latency yet, and **scoring it as zero would make
a silent counterparty look fast**."*

**E7's rule also already exists**: `gate/rules.availability_marker` returns `AUTO_REPLY`, and the
module says *"an auto-reply additionally never counts as the counterparty answering"*. This file
REUSES it rather than writing a second regex.

**ONE DIFFERENCE FROM L2's VERSION, DELIBERATE.** `waiting.py` returns `float` days
(`total_seconds() / 86400.0`). V-7 forbids a float reaching storage, so L1 emits **integer
seconds**. Same pairing, same rules, a unit that survives jsonb.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


# =============================================================================================
# 14-U1 + 14-U3 · the four missing world instants
# =============================================================================================
def test_the_signal_carries_the_four_missing_instants():
    """`due_at` · `effective_at` · `resolved_at` · `superseded_at`.

    `superseded_at` is the one that looks redundant and is not: `supersedes` is a POINTER, so
    *"when did this stop being current"* is implied by another row's existence rather than stored.
    A sweep cannot filter on an implication.
    """
    from genios_engine.contracts.signal import QualifiedEnterpriseSignal

    fields = QualifiedEnterpriseSignal.model_fields
    for name in ("due_at", "effective_at", "resolved_at", "superseded_at"):
        assert name in fields, f"{name} still has nowhere to live on the signal"


def test_a_naive_datetime_is_refused():
    """E2. A naive instant is a claim about a moment with no moment in it, and it compares wrongly
    against every tz-aware value in the system rather than failing. `eval_time` already refuses
    one; these must too."""
    from genios_engine.contracts.signal import instants_are_ordered

    with pytest.raises(ValueError, match="timezone|naive|aware"):
        instants_are_ordered(occurred_at=NOW, resolved_at=datetime(2026, 9, 25, 12, 0))


def test_resolved_before_occurred_is_refused():
    """E4. A signal resolved before it happened is not a late row, it is a wrong one — the same
    reasoning as the existing self-supersede check."""
    from genios_engine.contracts.signal import instants_are_ordered

    with pytest.raises(ValueError, match="resolved_at"):
        instants_are_ordered(occurred_at=NOW, resolved_at=NOW - timedelta(days=1))


def test_a_due_date_in_the_past_is_legal():
    """E3. **A stale promise is still a promise**, and refusing it at the contract would delete
    exactly the overdue commitments P2 asks about."""
    from genios_engine.contracts.signal import instants_are_ordered

    assert instants_are_ordered(occurred_at=NOW, due_at=NOW - timedelta(days=8)) is True


def test_every_instant_is_optional():
    """Most signals have no deadline and were never resolved. A required field would force every
    caller to invent one, and an invented instant is worse than an absent one."""
    from genios_engine.contracts.signal import instants_are_ordered

    assert instants_are_ordered(occurred_at=NOW) is True


# =============================================================================================
# 14-U2 · LIFTED from the typed claim, never re-derived
# =============================================================================================
def test_the_due_date_is_lifted_from_the_commitment_that_already_holds_it():
    """§9: *"Do not re-derive a value that a typed claim already holds — lift it."*

    `Commitment.due` is a `ResolvedDate` ALG-09 already produced, with a certainty and a window. A
    second derivation here would be a second answer to a question the extraction has answered, and
    the two drift the first time ALG-09's cascade changes.
    """
    from genios_engine.capture.esqe.instants import due_at_of

    class _Due:
        latest = NOW + timedelta(days=3)
        earliest = NOW + timedelta(days=1)

    class _Commitment:
        due = _Due()

    assert due_at_of([_Commitment()]) == NOW + timedelta(days=3)


def test_a_range_deadline_keeps_its_far_end_and_never_collapses_to_a_point():
    """T4 / E1. *"Next Friday" is a range with a certainty, not a point.*

    `due_at` takes the FAR end, and the reason is step 12's: a promise is overdue when the range
    the speaker actually committed to has passed. Taking the near end invents a deadline, which is
    the failure `Commitment`'s own contract warns about — *"an invented deadline must not be able
    to produce a false overdue."*

    The range itself is not destroyed: it is still on the claim, where ALG-09 put it.
    """
    from genios_engine.capture.esqe.instants import due_at_of

    class _Range:
        earliest = NOW + timedelta(days=1)
        latest = NOW + timedelta(days=7)

    class _Commitment:
        due = _Range()

    assert due_at_of([_Commitment()]) == NOW + timedelta(days=7)


def test_the_soonest_deadline_wins_when_a_signal_carries_several():
    """One signal can rest on two commitments. The signal's `due_at` is the one that comes first —
    a sweep asking *"what is overdue"* must not miss the earlier of two because the later one was
    stored."""
    from genios_engine.capture.esqe.instants import due_at_of

    class _C:
        def __init__(self, days):
            self.due = type("D", (), {"latest": NOW + timedelta(days=days),
                                      "earliest": NOW})()

    assert due_at_of([_C(9), _C(2)]) == NOW + timedelta(days=2)


def test_a_commitment_with_no_date_contributes_nothing():
    """A promise with no deadline is an open loop, not a deadline of now. `None` is the answer."""
    from genios_engine.capture.esqe.instants import due_at_of

    class _NoDate:
        due = None

    assert due_at_of([_NoDate()]) is None
    assert due_at_of([]) is None


# =============================================================================================
# 14-U4 + 14-U5 · reply pairing, with `waiting.py`'s two rules preserved EXACTLY
# =============================================================================================
def _turn(direction: str, minutes: int, mid: str, auto: bool = False):
    from genios_engine.capture.esqe.instants import ReplyTurn

    return ReplyTurn(message_id=mid, direction=direction,
                     at=NOW + timedelta(minutes=minutes), is_auto_reply=auto)


def test_a_simple_exchange_produces_one_pair_with_both_ids():
    """14-U4. Both message ids, because E6: *"the pair is by message id, not by content"* — a reply
    that quotes the whole thread is still one message answering one message."""
    from genios_engine.capture.esqe.instants import pair_replies

    pairs = pair_replies([_turn("out", 0, "m1"), _turn("in", 30, "m2")])

    assert len(pairs) == 1
    assert (pairs[0].outbound_message_id, pairs[0].inbound_message_id) == ("m1", "m2")
    assert pairs[0].latency_seconds == 1800


def test_consecutive_outbounds_produce_ONE_latency_not_several():
    """T5 / E5 — **the rule `waiting.py` states in its own words** and this must not re-derive
    differently:

    > *"Consecutive outbounds with no reply between them contribute nothing — an unanswered message
    > has no latency yet, and **scoring it as zero would make a silent counterparty look fast**."*

    Three outbounds then one reply is ONE pair, measured from the FIRST outbound.
    """
    from genios_engine.capture.esqe.instants import pair_replies

    pairs = pair_replies([_turn("out", 0, "m1"), _turn("out", 10, "m2"),
                          _turn("out", 20, "m3"), _turn("in", 60, "m4")])

    assert len(pairs) == 1
    assert pairs[0].outbound_message_id == "m1", "the pair moved to a later outbound"
    assert pairs[0].latency_seconds == 3600


def test_only_the_first_reply_after_an_outbound_counts():
    """The other half of the same rule: *"a thread where they answered once and then sent four more
    messages describes one reply latency, not five."*"""
    from genios_engine.capture.esqe.instants import pair_replies

    pairs = pair_replies([_turn("out", 0, "m1"), _turn("in", 30, "m2"),
                          _turn("in", 40, "m3"), _turn("in", 50, "m4")])

    assert len(pairs) == 1 and pairs[0].inbound_message_id == "m2"


def test_an_unanswered_outbound_produces_no_pair_at_all():
    """Not a pair with a zero latency — **no pair.** A silent counterparty has no reply latency
    yet, and recording one would make them look instant."""
    from genios_engine.capture.esqe.instants import pair_replies

    assert pair_replies([_turn("out", 0, "m1")]) == ()


def test_an_auto_reply_is_never_the_counterparty_answering():
    """T6 / E7 — N-05's existing rule, reused rather than rewritten. `gate/rules.py`:
    *"an auto-reply additionally never counts as the counterparty answering."*

    An out-of-office arriving four minutes after a pitch is not a four-minute response time, and
    letting it pair would make every unreachable counterparty the fastest in the graph.
    """
    from genios_engine.capture.esqe.instants import pair_replies

    pairs = pair_replies([_turn("out", 0, "m1"), _turn("in", 4, "ooo", auto=True),
                          _turn("in", 600, "m2")])

    assert len(pairs) == 1
    assert pairs[0].inbound_message_id == "m2", "an auto-reply was counted as an answer"
    assert pairs[0].latency_seconds == 36000


def test_the_auto_reply_rule_reuses_the_gate_and_does_not_restate_it():
    """14-U5: *"not writing a second version"*. Two regexes for one rule is how the gate and this
    module come to disagree about what an out-of-office is."""
    import inspect

    from genios_engine.capture.esqe import instants

    source = inspect.getsource(instants)
    assert "auto[- ]?reply" not in source, (
        "a second auto-reply regex lives here — reuse `gate/rules.availability_marker`")


def test_the_latency_is_an_integer_and_never_a_float():
    """V-7. `waiting.py` returns float days (`total_seconds() / 86400.0`), which is fine inside L2
    and not fine crossing a seam: a float reaches jsonb and comes back as a number nobody can trace
    to two timestamps. Integer SECONDS — same pairing, same rules, a unit that survives."""
    from genios_engine.capture.esqe.instants import pair_replies

    pairs = pair_replies([_turn("out", 0, "m1"), _turn("in", 90, "m2")])

    assert isinstance(pairs[0].latency_seconds, int)
    assert pairs[0].latency_seconds == 5400


def test_pairs_are_ordered_by_time_not_by_input_order():
    """A page can arrive newest-first. Pairing an out-of-order timeline would produce negative
    latencies, which is the shape of bug that reads as "they replied before we wrote"."""
    from genios_engine.capture.esqe.instants import pair_replies

    pairs = pair_replies([_turn("in", 30, "m2"), _turn("out", 0, "m1")])

    assert len(pairs) == 1 and pairs[0].latency_seconds == 1800


# =============================================================================================
# 14-U6 + T7 · no clock, and no judgement
# =============================================================================================
def test_the_module_reads_no_clock():
    """T7 / 14-U6. Every instant is a parameter, so a replay of last week produces last week's
    answer — the rule `finalize.py` states for everything downstream of capture."""
    import inspect

    from genios_engine.capture.esqe import instants

    source = inspect.getsource(instants)
    for forbidden in ("datetime.now", "date.today", "utcnow"):
        assert forbidden not in source, f"`{forbidden}` in a module that must be replayable"


def test_layer_one_emits_pairs_and_never_the_judgement():
    """§9: *"Do not compute the latency JUDGEMENT ('binary responder') in L1; that is a pattern
    over pairs and belongs to L2."*

    L1 emits `(outbound, inbound, Δ)`. It does not compute a median, a percentile or a label — one
    pair cannot support any of them, and a module that offered `is_fast_responder()` would invite a
    caller to ask it of a single exchange.
    """
    from genios_engine.capture.esqe import instants

    # THE PUBLIC SURFACE, not the prose. The first version of this row grepped the whole source
    # and failed on the docstring that EXPLAINS the rule — a guard that punishes a module for
    # documenting its own boundary is a guard somebody deletes. What matters is what a caller can
    # reach: `pair_replies` returns pairs, and nothing here offers an aggregate to ask of one.
    surface = {name.lower() for name in instants.__all__}
    for forbidden in ("median", "percentile", "p50", "p90", "responder", "is_fast", "cadence"):
        assert not any(forbidden in name for name in surface), (
            f"`{forbidden}` is exposed — a pattern over many pairs is Layer 2's judgement, and "
            f"offering it here invites a caller to ask it of a single exchange")

    # And the pair itself carries two ids and a gap. Nothing else — a field like `is_fast` on the
    # pair would be the same violation one level down.
    assert set(instants.ReplyPair.__dataclass_fields__) == {
        "outbound_message_id", "inbound_message_id", "latency_seconds"}


def test_the_extraction_cache_fingerprint_is_untouched():
    """Instants are lifted from claims the model already produced. No prompt, no vocabulary."""
    from genios_engine.capture.semantic.vocabulary import vocabulary_fingerprint

    assert vocabulary_fingerprint() == "a3d5496aa0d3"


# =============================================================================================
# THE WIRING — six steps running, a field added and nothing filling it
# =============================================================================================
def test_the_publisher_lifts_the_deadline_onto_the_signal():
    """`due_at` on the contract proves nothing if `build_signal` never sets it. Asserted against
    the shipping function, because every optional field defaults to None and a suite of unit tests
    on the dataclass passes either way."""
    import inspect

    from genios_engine.capture.esqe import publisher

    source = inspect.getsource(publisher.build_signal)
    assert "due_at=due_at_of(" in source, (
        "the signal is published with no deadline — '8 days overdue' is still unanswerable")


def test_the_store_names_all_four_instants_in_its_insert():
    """A column no writer names is null in every row forever. `started_at` on `l1_sync_runs` is the
    cautionary tale — the column existed from the day the table did, the insert never mentioned it,
    and every row in production recorded a finish with no start."""
    import inspect

    from genios_engine.capture.esqe import signal_store

    source = inspect.getsource(signal_store)
    for column in ("due_at", "effective_at", "resolved_at", "superseded_at"):
        assert f'"{column}' in source or f"{column}," in source, f"{column} never reaches storage"
    assert '"due": self.due_at' in source, "the parameter map drops the deadline"
    assert "due_at=excluded.due_at" in source, (
        "a re-published commitment keeps its FIRST deadline — a promise re-promised with a new "
        "date would go on being chased against the old one")


def test_the_migration_adds_the_columns_nullably():
    """Every row written before 0179 has no deadline, and a NOT NULL would refuse the migration on
    any live tenant."""
    from pathlib import Path

    sql = Path("migrations/0179_signal_world_instants.sql").read_text()

    import re

    for column in ("due_at", "effective_at", "resolved_at", "superseded_at"):
        assert column in sql

    # A COLUMN DECLARED not null — not the phrase. `where due_at is not null` is the partial
    # index's predicate and is exactly right: the rows that matter are the minority carrying a
    # deadline. A blunt substring check flagged it, which would have made the guard unkeepable.
    declared = re.findall(r"add column if not exists\s+\w+\s+timestamptz\s+not\s+null", sql, re.I)
    assert not declared, (
        f"{declared} is NOT NULL — that invents a deadline for every signal ever written and "
        f"refuses the migration on any live tenant")


def test_superseded_at_is_deliberately_not_set_at_publish_time():
    """A DELIBERATE ABSENCE, recorded because it looks like an omission.

    The first version read `getattr(stamp, "superseded_at", None)` — and `LifecycleStamp` has three
    fields, so that was **dead code that could never fire**: precisely the
    `getattr`-against-your-own-contract smell step 5 named. It cannot fail, so it cannot tell you
    the field is missing.

    A signal is superseded by a LATER sweep. ALG-19 stamps it when the replacement arrives, which
    is a different write — filling it here would mean guessing at publish time when a future event
    will occur.
    """
    from genios_engine.capture.esqe.publisher import LifecycleStamp

    assert "superseded_at" not in LifecycleStamp.__dataclass_fields__


def test_the_domain_confidence_reaches_storage():
    """A STEP 6 LEAK, FOUND WHILE WIRING STEP 14.

    `build_signal`'s row builder constructed `domain_hints` by hand with `{domain, source}`, so
    `DomainHint.confidence_bp` — added in step 6 and carried correctly by `DomainTagging.as_dicts`
    — **never reached `qualified_signals`**. Two hand-written copies of one projection, and only
    one of them learned the new field.

    That is the exact drift `situation_bso.py` warns about at the other end of this pipe, and step
    3 built a test for it there. This is the same test at this end.
    """
    import inspect

    from genios_engine.capture.esqe import publisher

    source = inspect.getsource(publisher)
    assert '"confidence_bp": getattr(h, "confidence_bp", 0)' in source, (
        "the stored domain hint has no confidence — step 6's field stops at the seam")
