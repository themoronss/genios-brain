"""Step 15 · "no follow-up found" means nothing until you know whether you searched 100% or 8%.

    pytest tests/capture/test_a_negative_claim_carries_its_proof.py -q

**THE LESSON THE BENCHMARK TEACHES MOST CLEARLY, and it is epistemic rather than technical.**
Gemini's worst failure was reporting the size of its context as the size of the mailbox — *"18
threads read of 18 that exist"* against ~465. Claude's strongest behaviour was publishing a coverage
table **before** any finding.

`coverage/declaration.py` already makes the argument one level up, for CHANNELS:

> *"It is the difference between 'this customer has no support tickets' and 'we have no source that
> could carry a support ticket.' The first is a finding; the second is a blind spot wearing a
> finding's clothes."*

**FIVE REALITIES THAT ALL LOOK LIKE "NOTHING FOUND":**

    A  no such email exists
    B  it exists but was never indexed          ← step 5's denominator separates this
    C  it exists, was indexed, the query missed it     ← L2's
    D  it exists but entity resolution failed          ← L2's
    E  it exists but L1 filtered it             ← the drop ledger already records this

A, B and E are separable with data L1 already has. **C and D are not ours, and this step must at
least stop CLAIMING them.**

⛔ **THE ALIGNMENT WITH STEP 12, which is what makes this worth building now.** Step 12 built the
rule that `BROKEN` requires a coverage figure ≥ 9000 bp — and had **no figure to feed it**.
`CommitmentFacts.coverage_bp` has been an input a caller had to supply from somewhere. This step is
that somewhere.

    step 5   built the denominator on the sweep
    step 12  built the gate that consumes it, with nothing wired in
    step 15  carries it onto the signal, frozen at capture

**E4 IS THE SUBTLE ONE AND §9 FORBIDS GETTING IT WRONG.** Coverage is a property of the
**observation moment**, not of the tenant. Storing a live pointer would make yesterday's claim
silently change its meaning tonight — a backfill would retroactively strengthen a claim nobody
re-examined.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.unit

FROM = datetime(2026, 8, 1, tzinfo=timezone.utc)
TO = datetime(2026, 9, 1, tzinfo=timezone.utc)


# =============================================================================================
# 15-U1 · the coverage block — per source, integer, and never blended
# =============================================================================================
def test_a_source_reports_what_it_indexed_against_what_exists():
    """Step 5's three numbers, per source: how many we read, how many the provider says exist, and
    whether the cursor ran out."""
    from genios_engine.capture.coverage.signal_coverage import SourceCoverage

    covered = SourceCoverage(source="gmail", indexed=465, claimed_total=465,
                             is_estimate=True, cursor_exhausted=True)

    assert covered.completeness_bp == 10_000


def test_completeness_is_integer_basis_points():
    """E6 / V-7. A ratio reaching jsonb as a float comes back as a number nobody can trace to two
    counts. 8 of 465 is 172 bp, truncated — never 0.0172 and never 1.7%."""
    from genios_engine.capture.coverage.signal_coverage import SourceCoverage

    covered = SourceCoverage(source="gmail", indexed=8, claimed_total=465,
                             is_estimate=True, cursor_exhausted=False)

    assert covered.completeness_bp == 172
    assert isinstance(covered.completeness_bp, int)


def test_an_unknown_total_reports_unknown_completeness_and_never_a_hundred_percent():
    """⛔ **§9's first rule: do not default coverage to 100%. That is the exact failure this whole
    step exists to prevent.**

    `claimed_total=None` means the provider gave us no count. It is not zero and it is not
    everything — it is *"we do not know the denominator"*, and a completeness of 10000 would be
    Gemini's 18-of-18 written into our own contract.
    """
    from genios_engine.capture.coverage.signal_coverage import SourceCoverage

    blind = SourceCoverage(source="notion", indexed=40, claimed_total=None,
                           is_estimate=False, cursor_exhausted=False)

    assert blind.completeness_bp is None
    assert blind.is_unknown is True


def test_an_estimate_is_labelled_on_the_signal():
    """E1 / T3. Gmail's total is `resultSizeEstimate` and Google named it that. An estimate stored
    without its label becomes a fact at the first reader, and *"465 of 465"* then reads as a count
    somebody could be held to."""
    from genios_engine.capture.coverage.signal_coverage import SourceCoverage

    assert SourceCoverage(source="gmail", indexed=465, claimed_total=465,
                          is_estimate=True, cursor_exhausted=True).is_estimate is True


def test_fetching_more_than_the_estimate_is_legal_and_caps_at_full():
    """E2 of step 5, inherited. Gmail's estimate runs low, so `indexed > claimed_total` happens on
    correct sweeps. Reporting 11000 bp would be arithmetic nobody can defend; refusing it would
    raise on a healthy mailbox."""
    from genios_engine.capture.coverage.signal_coverage import SourceCoverage

    over = SourceCoverage(source="gmail", indexed=470, claimed_total=465,
                          is_estimate=True, cursor_exhausted=True)

    assert over.completeness_bp == 10_000


def test_coverage_is_per_source_and_never_blended():
    """E5 / §9. A tenant with complete calendar coverage and 8% email coverage has **two**
    different licences to make a negative claim, and one blended number would grant the stronger
    one to both.

    *"No meeting was booked"* and *"no follow-up was sent"* rest on different evidence.
    """
    from genios_engine.capture.coverage.signal_coverage import SignalCoverage, SourceCoverage

    coverage = SignalCoverage(window_from=FROM, window_to=TO, sources=(
        SourceCoverage(source="gcal", indexed=42, claimed_total=42,
                       is_estimate=False, cursor_exhausted=True),
        SourceCoverage(source="gmail", indexed=37, claimed_total=465,
                       is_estimate=True, cursor_exhausted=False)))

    assert coverage.for_source("gcal").completeness_bp == 10_000
    assert coverage.for_source("gmail").completeness_bp == 795
    assert not hasattr(coverage, "completeness_bp"), (
        "a blended number exists — it would grant the calendar's licence to the mailbox")


def test_the_window_is_carried_because_completeness_is_meaningless_without_it():
    """*"465 of 465"* over what? A claim that nothing was found needs the period it searched, or
    the number is a ratio over an unstated set."""
    from genios_engine.capture.coverage.signal_coverage import SignalCoverage

    coverage = SignalCoverage(window_from=FROM, window_to=TO, sources=())

    assert (coverage.window_from, coverage.window_to) == (FROM, TO)


# =============================================================================================
# 15-U3 · unknown is the DEFAULT and is representable
# =============================================================================================
def test_a_signal_with_no_coverage_block_reports_unknown_not_complete():
    """T2. Every signal published before this step has no coverage, and the honest reading of that
    is `unknown`. Defaulting to complete would retroactively license every historical negative
    claim in the corpus."""
    from genios_engine.contracts.signal import QualifiedEnterpriseSignal

    field = QualifiedEnterpriseSignal.model_fields.get("coverage")
    assert field is not None, "the signal has nowhere to carry its proof"
    assert field.default is None, "coverage defaults to something — it must default to UNKNOWN"


def test_an_empty_coverage_block_is_unknown():
    """A block with no sources in it is not full coverage of nothing — it is a block that learned
    nothing."""
    from genios_engine.capture.coverage.signal_coverage import SignalCoverage

    assert SignalCoverage(window_from=FROM, window_to=TO, sources=()).is_unknown is True


# =============================================================================================
# ⛔ E4 · frozen at capture — the subtle one
# =============================================================================================
def test_coverage_is_frozen_and_a_later_backfill_cannot_rewrite_it():
    """T4 / E4, and §9: *"do not let a later backfill rewrite an old signal's coverage."*

    **Coverage is a property of the observation moment, not of the tenant.** A signal that said
    *"no follow-up found, 8% of the window indexed"* must keep saying 8% after a backfill takes the
    tenant to 100%. The claim was made with 8% of the evidence and its strength has not changed —
    only our ability to make a NEW and better claim has.

    Storing a live pointer would make yesterday's finding silently change meaning tonight, and
    nobody would be told.
    """
    from genios_engine.capture.coverage.signal_coverage import SignalCoverage, SourceCoverage

    coverage = SignalCoverage(window_from=FROM, window_to=TO, sources=(
        SourceCoverage(source="gmail", indexed=37, claimed_total=465,
                       is_estimate=True, cursor_exhausted=False),))

    with pytest.raises(Exception):
        coverage.sources = ()                    # type: ignore[misc]
    with pytest.raises(Exception):
        coverage.sources[0].indexed = 465        # type: ignore[misc]


def test_the_block_is_a_value_and_not_a_pointer_to_live_state():
    """The mechanism behind E4. A block holding an org id or a query would resolve against
    TODAY's numbers every time it was read — which is the live pointer §9 forbids, wearing a
    value's clothes."""
    from genios_engine.capture.coverage.signal_coverage import SignalCoverage, SourceCoverage

    fields = set(SignalCoverage.__dataclass_fields__) | set(SourceCoverage.__dataclass_fields__)
    for forbidden in ("org_id", "connection_id", "query", "run_id", "store", "fetch"):
        assert forbidden not in fields, (
            f"`{forbidden}` makes the block resolve against live state — an old claim would "
            f"silently restate itself after a backfill")


# =============================================================================================
# 15-U2 · it reaches the gate step 12 built and left unfed
# =============================================================================================
def test_the_coverage_figure_feeds_step_twelves_broken_gate():
    """⛔ **THE ALIGNMENT.** Step 12 built the rule that `BROKEN` requires coverage ≥ 9000 bp and
    had nothing wired into `CommitmentFacts.coverage_bp`. This is that wire.

    At 8% the same overdue promise must read `UNKNOWN`; at 95% it may read `BROKEN`. Nothing about
    the promise changed — only what we can prove about having looked.
    """
    from genios_engine.capture.coverage.signal_coverage import SignalCoverage, SourceCoverage

    def mailbox(indexed: int) -> int | None:
        return SignalCoverage(window_from=FROM, window_to=TO, sources=(
            SourceCoverage(source="gmail", indexed=indexed, claimed_total=465,
                           is_estimate=True, cursor_exhausted=False),)).coverage_bp_for("gmail")

    from genios_engine.capture.esqe.signal_states import (BROKEN_REQUIRES_COVERAGE_BP,
                                                          CommitmentFacts, CommitmentState,
                                                          resolve_commitment_state)

    thin, thick = mailbox(37), mailbox(460)
    assert thin is not None and thin < BROKEN_REQUIRES_COVERAGE_BP
    assert thick is not None and thick >= BROKEN_REQUIRES_COVERAGE_BP

    def state(coverage_bp):
        return resolve_commitment_state(CommitmentFacts(
            due_latest=TO - timedelta(days=5), fulfilment_event_id=None,
            coverage_bp=coverage_bp, eval_time=TO))

    assert state(thin) is CommitmentState.UNKNOWN
    assert state(thick) is CommitmentState.BROKEN


def test_an_unknown_source_returns_no_figure_rather_than_zero():
    """Asking about a source this signal has no coverage for is *"we do not know"*, not *"we read
    none of it"*. Zero would feed step 12's gate a figure that means the opposite of the truth."""
    from genios_engine.capture.coverage.signal_coverage import SignalCoverage

    coverage = SignalCoverage(window_from=FROM, window_to=TO, sources=())

    assert coverage.coverage_bp_for("gmail") is None
    assert coverage.for_source("gmail") is None


# =============================================================================================
# 15-U4 · it crosses the seam
# =============================================================================================
def test_the_migration_adds_the_column_nullably():
    """Every signal written before this has no coverage, and a NOT NULL would refuse the migration
    on any live tenant — and would have to invent a value, which is the one thing §9 forbids."""
    import re
    from pathlib import Path

    sql = Path("migrations/0180_signal_coverage.sql").read_text()

    assert "coverage" in sql and "jsonb" in sql.lower()
    assert not re.findall(r"add column if not exists\s+\w+\s+jsonb\s+not\s+null", sql, re.I)


def test_the_store_names_the_column_in_its_insert():
    """A column no writer names is null in every row forever — `started_at` on `l1_sync_runs` is
    the cautionary tale, and step 14 had to fix the same shape in this same file."""
    import inspect

    from genios_engine.capture.esqe import signal_store

    source = inspect.getsource(signal_store)
    assert "coverage" in source and '"cvg"' in source, (
        "the coverage block never reaches storage")


# =============================================================================================
# Guards
# =============================================================================================
def test_no_float_survives_the_round_trip():
    """T5. The block is serialised to jsonb; every number in it must come back an int."""
    import json

    from genios_engine.capture.coverage.signal_coverage import SignalCoverage, SourceCoverage

    coverage = SignalCoverage(window_from=FROM, window_to=TO, sources=(
        SourceCoverage(source="gmail", indexed=37, claimed_total=465,
                       is_estimate=True, cursor_exhausted=False),))

    payload = json.loads(json.dumps(coverage.as_dict(), default=str))
    for key, value in payload["sources"][0].items():
        assert not isinstance(value, float), f"{key} crossed as a float"


def test_the_extraction_cache_fingerprint_is_untouched():
    """Coverage is post-extraction bookkeeping. No prompt, no vocabulary, no model."""
    from genios_engine.capture.semantic.vocabulary import vocabulary_fingerprint

    assert vocabulary_fingerprint() == "a3d5496aa0d3"


# =============================================================================================
# 15-U5 · a negative claim cannot publish without its proof
# =============================================================================================
def test_the_negative_states_are_named_and_unknown_is_not_one():
    """`broken` asserts *"the deadline passed and we found no fulfilment"* — a claim about an
    ABSENCE, and an absence is evidence only when you can show you looked.

    **`unknown` is deliberately NOT a negative state.** It asserts nothing, it is the honest answer
    when we could not tell, and requiring proof of a non-claim would make the conservative answer
    the expensive one — which is exactly how a system learns to say `broken` instead.
    """
    from genios_engine.contracts.signal import QualifiedEnterpriseSignal

    negative = QualifiedEnterpriseSignal._NEGATIVE_STATES
    assert "broken" in negative
    assert "unknown" not in negative, (
        "requiring proof for `unknown` prices caution above assertion — the wrong way round")
    assert "active" not in negative and "fulfilled" not in negative


def test_the_guard_is_a_second_lock_and_not_a_duplicate_of_step_twelves():
    """Step 12 refuses to RESOLVE to `broken` below 9000 bp. This refuses to PUBLISH one with no
    coverage at all. They are different locks on different doors:

    * step 12's gate acts on the figure it is handed, and a caller that hands it nothing gets
      `unknown` — good, but it only guards the resolver;
    * a caller constructing a `QualifiedEnterpriseSignal` directly bypasses the resolver entirely.

    Two locks, because the cost of being wrong is telling a founder they broke a promise they
    actually kept.
    """
    import inspect

    from genios_engine.contracts import signal

    source = inspect.getsource(signal.QualifiedEnterpriseSignal)
    assert "_a_negative_claim_carries_its_proof" in source
    from genios_engine.capture.esqe.signal_states import BROKEN_REQUIRES_COVERAGE_BP

    assert BROKEN_REQUIRES_COVERAGE_BP >= 9000, "step 12's gate moved — the two must stay aligned"


# =============================================================================================
# 15-U2 · the producer — six steps running, a field added and nothing filling it
# =============================================================================================
def test_the_publisher_reads_coverage_off_the_sweep():
    """A field on the contract that nothing fills is the defect this plan has found in six
    consecutive steps. `coverage` defaults to None, so a suite of unit tests on the value type
    passes whether or not a single signal ever carries one."""
    import inspect

    from genios_engine.capture.esqe import publisher

    source = inspect.getsource(publisher)
    assert "coverage=_coverage_of(summary)" in source, (
        "no signal ever gets a coverage block — the field is a place to put one")
    assert "coverage=inputs.coverage" in source, (
        "the block stops at SignalInputs and never reaches the signal")


def test_a_sweep_that_cannot_state_a_window_produces_no_block_rather_than_a_full_one():
    """§9's rule at the producer. A sweep with no `started_at` has no window, and a completeness
    with no window is a ratio over an unstated set.

    `None` — never a block claiming complete coverage, which is the one value this step exists to
    stop anyone inventing.
    """
    from genios_engine.capture.esqe.publisher import _coverage_of

    class _NoWindow:
        source = "gmail"
        started_at = None
        scanned = 400
        claimed_total = 465

    assert _coverage_of(_NoWindow()) is None


def test_a_sweep_with_no_denominator_produces_no_block_either():
    """`claimed_total=None` means the provider gave us no count. The block would be all-unknown,
    and an all-unknown block is indistinguishable from no block — so it is no block, and the
    signal reads `unknown` for the right reason."""
    from datetime import datetime, timezone

    from genios_engine.capture.esqe.publisher import _coverage_of

    class _Blind:
        source = "notion"
        started_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
        finished_at = datetime(2026, 9, 1, tzinfo=timezone.utc)
        scanned = 40
        claimed_total = None
        claimed_is_estimate = False
        cursor_exhausted = False

    assert _coverage_of(_Blind()) is None


def test_a_real_sweep_produces_a_real_block():
    """SENSITIVITY. A producer that returned None for everything would satisfy both rows above and
    leave the step delivering nothing."""
    from datetime import datetime, timezone

    from genios_engine.capture.esqe.publisher import _coverage_of

    class _Real:
        source = "gmail"
        started_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
        finished_at = datetime(2026, 9, 1, tzinfo=timezone.utc)
        scanned = 37
        claimed_total = 465
        claimed_is_estimate = True
        cursor_exhausted = False

    block = _coverage_of(_Real())

    assert block is not None
    assert block.coverage_bp_for("gmail") == 795
    assert block.for_source("gmail").is_estimate is True
