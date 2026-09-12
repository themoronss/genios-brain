"""G0 · the Layer 1 v2 contract surface — the acceptance gate for Wave W0.

Doc 09's gate is three commands and this file is the first of them::

    pytest tests/contracts/test_l1_contracts.py -q      # 0 skips
    pytest tests/test_layer_topology.py -q
    grep -rn "float" genios_engine/contracts/signal.py genios_engine/contracts/extraction.py

What the gate is actually asserting is not "the twelve classes exist" — an import would prove
that. It is that each one REFUSES the object it was written to refuse, at construction, and that
the refusal survives a serialize/reparse cycle. Every type here becomes a stored row (a
`qualified_signals` record, a `signal_conflicts` claim, an `l1_extraction_results` cache entry),
so a contract that validates on the way in and not on the way back out is a contract that holds
for exactly as long as the process that built the object.

Four properties run through the whole file, and each maps to a universal rule from doc 08:

* **Every score is integer basis points.** A ratio is not a different spelling of a confidence:
  it composes irreproducibly across replays, and pydantic's lax mode will happily round `0.87`
  to `0` and store it as one. Every `*_bp` field is tested against a float, a bool and an
  out-of-range integer.
* **Money is integer minor units plus an ISO code.** The Globe Worked fault — a card reading
  "$84K" against a contract reading "$8.4K" — is a locale bug that nothing normalized once.
* **A claim with no receipt is a guess.** Every claim-bearing type is tested with an empty
  `evidence` list and must refuse to be built.
* **No float appears in the SERIALIZED object.** Asserted by walking the JSON of a
  fully-populated `QualifiedEnterpriseSignal`, because the `Any`-typed lanes (`versions`,
  `ConflictClaim.value`, `roles`) are exactly where an annotation proves nothing.

The V-1..V-7 half tests `contracts/publication.py`, the L1.6.10 gate. Those rules are tested
through the gate rather than through the constructor on purpose: three of the seven have
outcomes a constructor cannot express — V-1 PARKS (reviewable, recoverable), V-5 DOWNGRADES and
emits anyway, and V-6 needs a second input the signal does not carry. Their fixtures use
`model_construct`, which is pydantic's documented way past a validator and therefore the exact
route the gate exists to catch; `publication._envelope_failure` says so in its own docstring.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from genios_engine.contracts.conflict import (MAX_AUTHORITY_RANK, Authority, Conflict,
                                              ConflictClaim, ConflictResolution,
                                              require_no_float)
from genios_engine.contracts.evidence import MAX_QUOTE_CHARS, EvidenceSpan
from genios_engine.contracts.extraction import (Commitment, DecisionState, Dependency,
                                                EntityMention, ExtractionResult,
                                                UnclassifiedObservation)
from genios_engine.contracts.gated_event import DomainHint
from genios_engine.contracts.publication import (UNVERIFIED_EVIDENCE_FLAG, VISIBILITY_UNKNOWN,
                                                 PublicationOutcome, PublicationRule,
                                                 downgrade_for_unverified, validate_publication)
from genios_engine.contracts.signal import (CONFIDENCE_COMPONENTS, QualifiedEnterpriseSignal,
                                            SignalType)
from genios_engine.contracts.units import UNKNOWN_CURRENCY, DateCertainty, Money, ResolvedDate
from genios_engine.contracts.visibility import Visibility

#: Hermetic by construction: no network, no database, no model, and — see `EVAL_TIME` — no wall
#: clock. Applied at module level so a test added later cannot forget it and silently escape the
#: `-m "not pg"` lane selector that keeps the default suite offline.
pytestmark = pytest.mark.unit

#: Every timestamp in this file is derived from one frozen instant. `ResolvedDate` refuses to
#: default `resolved_against` from the clock for exactly this reason — "next week" resolved
#: against a March event has to keep resolving to March forever — and a test that read
#: `datetime.now()` would be a test whose fixtures mean something different every day it runs.
EVAL_TIME = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)

#: The 14 members doc 08's C-11 block declares, written out as literals rather than derived from
#: the enum. Deriving it would make the assertion a tautology; spelling it out is what makes
#: adding a member a DELIBERATE test edit — which is the doc's own rule for this taxonomy, since
#: ALG-16 owns a precedence order over these names and ALG-17 owns a per-type weight for each,
#: and a fifteenth member added without touching either is a type that can be classified and
#: then scored as if it were nothing in particular.
DOC_SIGNAL_TYPES: frozenset[str] = frozenset({
    "commitment_made", "commitment_due", "deadline_stated", "decision_pending", "decision_made",
    "approval_requested", "contract_renewal", "financial_obligation", "risk_flagged",
    "opportunity_signal", "relationship_change", "information_conflict", "escalation", "anomaly",
    # Member fifteen, added deliberately with migration 0139 (see SignalType.AVAILABILITY_CHANGE).
    "availability_change",
})

#: The three inputs that must never be accepted by a `*_bp` field, with the reason each is its
#: own case rather than a variant of the others — and the exception each raises. Kept as data so
#: every scored field on every contract is tested against the identical set and none can quietly
#: accept one of them.
#:
#: The exception column is not incidental. `validators.py` distinguishes a wrong-KIND value
#: (`TypeError`) from a wrong-VALUE one (`ValueError`), and pydantic converts only the second
#: into a `ValidationError` — a `TypeError` raised inside a validator is, by pydantic's own
#: contract, a bug in the validator and propagates untouched. So the two strictest checks in the
#: whole document surface as bare `TypeError`s. That is deliberate and repo-wide, not local drift
#: (`tests/test_reasoning_orchestrator.py` and `tests/test_reason_store.py` pin the same grammar
#: on the same helpers), and it is exactly why `publication._refusal` catches
#: `(TypeError, ValueError)` — see `test_the_gate_absorbs_both_refusal_grammars`, which asserts
#: nothing escapes at the one seam where an escape would become a traceback instead of a row.
BP_VIOLATIONS: tuple[tuple[str, Any, type[BaseException]], ...] = (
    # A ratio. `int` alone does not stop it: pydantic's lax mode rounds it and stores the result
    # as a confidence, so 0.87 becomes 0 and reads as "we believe none of this".
    ("ratio", 0.87, TypeError),
    # A bool. `isinstance(True, int)` is True in Python, so an annotation admits it as 1 bp.
    ("bool", True, TypeError),
    # Out of range. 10000 bp is the ceiling; 10001 is a number no composition can produce.
    ("over_range", 10_001, ValidationError),
)

#: Ids for the parametrisations over `BP_VIOLATIONS`, so a failure names the input rather than
#: printing `bad0`.
BP_IDS = [row[0] for row in BP_VIOLATIONS]


# --------------------------------------------------------------------------- fixture builders

def span(quote: str, *, start: int = 0, verified: bool = True,
         source_ref: str = "prepared_content:evt_7f31") -> EvidenceSpan:
    """One coherent `EvidenceSpan` over `quote`.

    The offsets are DERIVED from the quote's own length rather than typed, because CV-01 is the
    invariant most of this file leans on and a fixture that computed them by hand would
    eventually drift from it — at which point every test using the fixture would fail for a
    reason that has nothing to do with what it was asserting.
    """
    return EvidenceSpan(source_ref=source_ref, quote=quote, start_offset=start,
                        end_offset=start + len(quote), verified=verified)


def money(minor_units: int, as_written: str, currency: str = "USD") -> Money:
    return Money(minor_units=minor_units, currency=currency, as_written=as_written)


def resolved_date(as_written: str, *, days_out: int = 7,
                  certainty: DateCertainty = DateCertainty.RANGE) -> ResolvedDate:
    """A window `days_out` days wide starting at `EVAL_TIME`, resolved against `EVAL_TIME`."""
    earliest = EVAL_TIME + timedelta(days=days_out)
    latest = earliest if certainty is DateCertainty.EXACT else earliest + timedelta(days=6)
    return ResolvedDate(as_written=as_written, earliest=earliest, latest=latest,
                        certainty=certainty, resolved_against=EVAL_TIME,
                        evidence=[span(as_written, start=120)])


def entity_mention() -> EntityMention:
    return EntityMention(surface_form="Globe Worked", entity_type="organization",
                         canonical_hint="globeworked.com",
                         evidence=[span("Globe Worked", start=4)], confidence_bp=9_200)


def commitment() -> Commitment:
    return Commitment(actor="Deepthi", action="send the countersigned MSA",
                      beneficiary="Rohit", due=resolved_date("by next Friday"),
                      is_conditional=True, condition_text="once legal confirms",
                      evidence=[span("I'll send the countersigned MSA once legal confirms",
                                     start=40)],
                      confidence_bp=8_600)


def decision_state() -> DecisionState:
    return DecisionState(subject="AWS renewal", state="blocked", blocked_on="legal review",
                         owner="Deepthi", evidence=[span("still with legal", start=200)],
                         confidence_bp=7_400)


def dependency() -> Dependency:
    return Dependency(blocker="legal review", blocked="countersigned MSA",
                      dependency_type="approval",
                      evidence=[span("once legal confirms", start=74)], confidence_bp=8_100)


def unclassified_observation() -> UnclassifiedObservation:
    return UnclassifiedObservation(
        proposed_kind="procurement_freeze_hint",
        description="The sender mentions a company-wide spend pause we have no word for.",
        evidence=[span("we're pausing all new spend until Q2", start=260)],
        confidence_bp=6_300)


def extraction_result() -> ExtractionResult:
    """A fully-populated C-09 — every list non-empty, including all three untyped lanes.

    Fully populated on purpose: the no-float walk below is only worth running over an object
    that actually exercises `roles`, `relationships` and `scheduling_proposals`, since those are
    the lanes where an annotation proves nothing and a ratio would otherwise reach jsonb.
    """
    return ExtractionResult(
        intent="commit",
        topics=["AWS renewal", "legal review"],
        stance="cautious",
        entity_mentions=[entity_mention()],
        amounts=[money(8_400_000, "$84K"), money(7_400_000, "$74,000")],
        dates_mentioned=[resolved_date("by next Friday")],
        commitments=[commitment()],
        decision_states=[decision_state()],
        dependencies=[dependency()],
        implied_actions=["confirm which contract value is current"],
        questions=["Is the $84K figure the amended number?"],
        roles=[{"person": "Deepthi", "role_hint": "signer", "seen_count": 3}],
        relationships=[{"from": "Deepthi", "to": "Globe Worked", "kind": "works_at"}],
        scheduling_proposals=[{"when": "2026-03-09", "where": "Zoom", "attendees": 2}],
        unclassified_observations=[unclassified_observation()],
        field_confidence={"amounts": 9_900, "commitments": 8_600},
        all_evidence=[span("I'll send the countersigned MSA once legal confirms", start=40)],
        model_snapshot="claude-3-5-haiku-20241022",
        prompt_version="l1.s2.email.v3",
        schema_version="l1.v2.0",
        extraction_profile="email",
        input_tokens=2_411,
        output_tokens=486)


def conflict_74k_vs_84k() -> Conflict:
    """The headline fixture: a signed PDF says $74,000, an email says "the $84K annual contract".

    This is the fault C-10 was written for — v1 wrote whichever landed last into the graph and
    told the founder one number with no indication the other existed. The resolution is by
    authority (rank 6 against rank 2, a gap of four), and the assertion that matters is that
    resolving it does not DELETE the losing side: the founder routinely knows what the ranking
    does not, namely that the PDF is the superseded draft.
    """
    return Conflict(
        field="contract.value",
        claims=[
            ConflictClaim(value=money(7_400_000, "$74,000"),
                          authority=Authority.SIGNED_DOCUMENT, authority_rank=6,
                          evidence=[span("Total annual commitment: $74,000",
                                         source_ref="chunk:doc_msa_2026:3")]),
            ConflictClaim(value=money(8_400_000, "$84K"),
                          authority=Authority.EMAIL_PROSE, authority_rank=2,
                          evidence=[span("the $84K annual contract", start=310)]),
        ],
        resolution=ConflictResolution.RESOLVED_BY_AUTHORITY,
        resolved_value=money(7_400_000, "$74,000"),
        detected_at=EVAL_TIME)


def signal_kwargs(**overrides: Any) -> dict[str, Any]:
    """Every C-12 field, valid, as a dict — so a fixture can break exactly one of them.

    Returned as kwargs rather than as a built object because the V-rule fixtures need
    `model_construct`, and `model_construct` must be handed the COMPLETE field set: it does not
    run validators, but it also does not invent the fields it was not given, so a partially
    constructed signal raises `AttributeError` inside V-7's walk instead of being rejected as
    the malformed object the gate is meant to record.
    """
    base: dict[str, Any] = dict(
        org_id="org_7173",
        schema_version=1,
        trace_id="trace_9c2a1f",
        visibility=Visibility(scope="participants",
                              principals=["deepthi@globeworked.com", "rohit@antler.co"],
                              derived_from="gmail:recipients"),
        signal_id="sig_0f21ab",
        event_id="evt_7f31",
        source="gmail",
        object_type="message",
        occurred_at=EVAL_TIME - timedelta(days=1),
        signal_type=SignalType.INFORMATION_CONFLICT,
        domain_hints=[DomainHint(domain="sales", source="keyword"),
                      DomainHint(domain="legal", source="scope")],
        importance_bp=7_800,
        triage_lane="P1",
        extraction=extraction_result(),
        evidence_refs=[span("the $84K annual contract", start=310),
                       span("Total annual commitment: $74,000",
                            source_ref="chunk:doc_msa_2026:3")],
        conflicts=[conflict_74k_vs_84k()],
        confidence_bp=6_200,
        confidence_vector={"evidence": 9_000, "expertise": 5_500, "freshness": 8_800,
                           "coverage": 4_100},
        coverage_ready=True,
        state="active",
        supersedes="sig_0e88cd",
        expires_at=EVAL_TIME + timedelta(days=180),
        internal_kind=None,
        recipients=("deepthi@globeworked.com", "rohit@antler.co"),
        versions={"prompt": "l1.s2.email.v3", "schema": "l1.v2.0",
                  "model": "claude-3-5-haiku-20241022", "vocabulary": "vocab.v7",
                  "pack": "sales@1.10.0"},
    )
    base.update(overrides)
    return base


def qualified_signal(**overrides: Any) -> QualifiedEnterpriseSignal:
    return QualifiedEnterpriseSignal(**signal_kwargs(**overrides))


def bypassed_signal(**overrides: Any) -> QualifiedEnterpriseSignal:
    """A C-12 that skipped the constructor — pydantic's `model_construct`, which runs no
    validator. This is not a contrived route: `publication._envelope_failure` names it as one of
    the two documented ways past a contract, and V-1..V-7 exist precisely so that an object
    which took it is parked or rejected rather than published."""
    return QualifiedEnterpriseSignal.model_construct(**signal_kwargs(**overrides))


def assert_round_trips(obj: Any) -> Any:
    """Serialize, reparse, and prove BOTH directions.

    Object equality alone is not enough: a field that rehydrated as a near-equal value would
    still pass it. Re-dumping and comparing the bytes is what proves the stored row is stable
    under a read-modify-write cycle, which is the operation every one of these types actually
    undergoes in `qualified_signals`, `signal_conflicts` and `l1_extraction_results`.
    """
    raw = obj.model_dump_json()
    back = type(obj).model_validate_json(raw)
    assert back == obj, f"{type(obj).__name__} did not survive a JSON round-trip"
    assert back.model_dump_json() == raw, f"{type(obj).__name__} re-serialized differently"
    from_dict = type(obj).model_validate(json.loads(raw))
    assert from_dict == obj, f"{type(obj).__name__} did not survive model_validate(dict)"
    return back


def walk_json(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    """Every scalar in a decoded JSON document, with the path that reaches it."""
    if isinstance(value, dict):
        return [leaf for key, item in value.items()
                for leaf in walk_json(item, f"{path}.{key}")]
    if isinstance(value, list):
        return [leaf for index, item in enumerate(value)
                for leaf in walk_json(item, f"{path}[{index}]")]
    return [(path, value)]


# ------------------------------------------------------------------- C-01 · EvidenceSpan

def test_c01_constructs_and_round_trips():
    """The receipt survives serialization — it is copied into audit rows and rendered cards."""
    original = span("the $84K annual contract", start=310)
    back = assert_round_trips(original)
    assert back.end_offset - back.start_offset == len(back.quote)


def test_c01_is_frozen_and_hashable():
    """Frozen is what lets many claims from one sentence share ONE receipt instead of each
    carrying a near-identical copy — and what stops a span being edited after the audit row that
    quotes it was written. ALG-08 rewrites a corrected span through the constructor instead."""
    one = span("the $84K annual contract", start=310)
    with pytest.raises(ValidationError):
        one.quote = "something else"
    assert len({one, span("the $84K annual contract", start=310)}) == 1


def test_c01_rejects_inverted_or_empty_range():
    """CV-01. An inverted or empty range highlights nothing, and ALG-08 would be comparing
    against characters the span never named."""
    for end in (310, 300):
        with pytest.raises(ValidationError, match="end_offset must be greater"):
            EvidenceSpan(source_ref="prepared_content:evt_7f31", quote="the $84K",
                         start_offset=310, end_offset=end)


def test_c01_rejects_quote_length_mismatch():
    """The doc's own listed case. A quote whose length disagrees with its range means the model
    reported a sentence it did not measure, so every offset-based check downstream compares the
    wrong characters — silently, and with a receipt that still looks legitimate."""
    with pytest.raises(ValidationError, match="quote length must equal"):
        EvidenceSpan(source_ref="prepared_content:evt_7f31", quote="the $84K annual contract",
                     start_offset=310, end_offset=320)


def test_c01_rejects_negative_offset():
    """ALG-08's INVALID_BOUNDS. A negative position could not have come from real text, so the
    validator never has to reason about it."""
    with pytest.raises(ValidationError, match="must be a non-negative integer"):
        EvidenceSpan(source_ref="prepared_content:evt_7f31", quote="abc",
                     start_offset=-3, end_offset=0)


def test_c01_rejects_missing_source_ref_and_empty_quote():
    """A span that does not say what it points into cannot be resolved by anyone, ever; a span
    quoting nothing cites nothing."""
    with pytest.raises(ValidationError, match="source_ref is required"):
        EvidenceSpan(source_ref="   ", quote="abc", start_offset=0, end_offset=3)
    with pytest.raises(ValidationError, match="quote is required"):
        EvidenceSpan(source_ref="prepared_content:evt_7f31", quote="   ",
                     start_offset=0, end_offset=3)


def test_c01_rejects_quote_over_the_cap():
    """A receipt that quotes everything proves nothing — it moves the reader's work from "is
    this true" to "where in this wall of text"."""
    long_quote = "x" * (MAX_QUOTE_CHARS + 1)
    with pytest.raises(ValidationError, match="at most"):
        EvidenceSpan(source_ref="prepared_content:evt_7f31", quote=long_quote,
                     start_offset=0, end_offset=len(long_quote))


def test_c01_rejects_truthy_verified():
    """`verified=1` is exactly how an unchecked span acquires a checkmark by accident, and the
    flag then means "claimed" rather than "checked" — the one distinction the type exists for."""
    with pytest.raises(TypeError, match="verified must be boolean"):
        EvidenceSpan(source_ref="prepared_content:evt_7f31", quote="abc",
                     start_offset=0, end_offset=3, verified=1)


# ------------------------------------------------------------------------- C-02 · Money

def test_c02_constructs_and_round_trips():
    back = assert_round_trips(money(8_400_000, "$84K"))
    assert back.minor_units == 8_400_000 and back.currency_known


def test_c02_rejects_lowercase_currency():
    """The doc's own listed case. A contract that quietly title-cases "usd" is a contract that
    lets a malformed value reach a human with the repair invisible."""
    with pytest.raises(ValidationError, match="ISO 4217"):
        Money(minor_units=8_400_000, currency="usd", as_written="$84K")


def test_c02_rejects_float_and_bool_minor_units():
    """Binary floating point cannot hold 84000.10 exactly, and a cent that drifts inside a sum
    is a cent nobody can trace back to a source string. `True` is refused with it because
    `isinstance(True, int)` would otherwise store a boolean as one minor unit."""
    for bad in (84_000.10, True):
        with pytest.raises(TypeError, match="exact integer"):
            Money(minor_units=bad, currency="USD", as_written="$84,000.10")


def test_c02_rejects_missing_as_written():
    """A dimensioned value with no source string is a value nobody wrote."""
    with pytest.raises(ValidationError, match="as_written is required"):
        Money(minor_units=8_400_000, currency="USD", as_written="   ")


def test_c02_unknown_currency_is_recorded_never_defaulted():
    """ALG-10 step 1: an ambiguous "$" with no declared locale resolves to UNKNOWN and never
    defaults to USD — guessing between USD, CAD and AUD is how a 40% error enters a renewal
    number with no warning. The amount is still worth keeping; only the currency is missing."""
    ambiguous = Money(minor_units=8_400_000, currency=UNKNOWN_CURRENCY, as_written="$84K")
    assert ambiguous.currency_known is False
    assert_round_trips(ambiguous)


def test_c02_same_amount_ignores_as_written_but_not_currency():
    """ALG-12's money comparison: "$84K" and "USD 84,000" are one amount written twice, while
    84,000 JPY is not 84,000 USD however well the integers line up."""
    assert money(8_400_000, "$84K").same_amount(money(8_400_000, "USD 84,000"))
    assert not money(8_400_000, "$84K").same_amount(money(8_400_000, "¥84,000", "JPY"))


# ------------------------------------------------------------------- C-03 · ResolvedDate

def test_c03_constructs_and_round_trips():
    back = assert_round_trips(resolved_date("by next Friday"))
    assert back.window is not None and back.certainty is DateCertainty.RANGE


def test_c03_exact_with_unequal_bounds_raises():
    """The doc's own listed case. EXACT means a single instant; an "exact" date spanning nine
    days is a claim of precision the source never carried."""
    with pytest.raises(ValidationError, match="EXACT means a single instant"):
        ResolvedDate(as_written="October 15, 2026", earliest=EVAL_TIME,
                     latest=EVAL_TIME + timedelta(days=9), certainty=DateCertainty.EXACT,
                     resolved_against=EVAL_TIME, evidence=[span("October 15, 2026")])


def test_c03_unresolved_with_a_window_raises():
    """The doc's own listed case. UNRESOLVED means no cascade row matched; a window attached to
    it is a guess wearing a derivation's clothes."""
    with pytest.raises(ValidationError, match="UNRESOLVED date carries no window"):
        ResolvedDate(as_written="at some point", earliest=EVAL_TIME, latest=None,
                     certainty=DateCertainty.UNRESOLVED, resolved_against=EVAL_TIME,
                     evidence=[span("at some point")])


def test_c03_half_a_window_raises():
    """Only UNRESOLVED may omit the window. A RANGE with one bound is a deadline that reads as
    open-ended to the proximity term of ALG-17."""
    with pytest.raises(ValidationError, match="only UNRESOLVED may omit the window"):
        ResolvedDate(as_written="next week", earliest=EVAL_TIME, latest=None,
                     certainty=DateCertainty.RANGE, resolved_against=EVAL_TIME,
                     evidence=[span("next week")])


def test_c03_backwards_window_raises():
    with pytest.raises(ValidationError, match="earliest must not be later than latest"):
        ResolvedDate(as_written="next week", earliest=EVAL_TIME + timedelta(days=9),
                     latest=EVAL_TIME, certainty=DateCertainty.RANGE,
                     resolved_against=EVAL_TIME, evidence=[span("next week")])


def test_c03_naive_datetime_raises():
    """A naive datetime is an unanswered timezone question, and the silent offset it carries
    expresses itself later as a reminder that fires on the wrong day."""
    with pytest.raises(ValidationError, match="timezone-aware"):
        ResolvedDate(as_written="Friday", earliest=datetime(2026, 3, 6),
                     latest=datetime(2026, 3, 6), certainty=DateCertainty.EXACT,
                     resolved_against=EVAL_TIME, evidence=[span("Friday")])


def test_c03_requires_a_receipt():
    with pytest.raises(ValidationError, match="requires evidence"):
        ResolvedDate(as_written="next week", earliest=EVAL_TIME,
                     latest=EVAL_TIME + timedelta(days=7), certainty=DateCertainty.RANGE,
                     resolved_against=EVAL_TIME, evidence=[])


def test_c03_past_window_is_derived_not_stored():
    """ALG-09 rule 6: "the renewal was Friday", said on Monday, is a fact about a date that was
    missed — rolling it forward erases the only interesting thing about it. Derived from the
    window and the eval time, so it cannot drift out of agreement with them after a correction."""
    past = ResolvedDate(as_written="last Friday", earliest=EVAL_TIME - timedelta(days=5),
                        latest=EVAL_TIME - timedelta(days=5), certainty=DateCertainty.EXACT,
                        resolved_against=EVAL_TIME, evidence=[span("last Friday")])
    assert past.date_in_past is True
    assert resolved_date("by next Friday").date_in_past is False


def test_c03_unresolved_overlaps_nothing():
    """Silence about a deadline is not a competing claim about it — which is why a caller reads
    False from `overlaps` as a conflict only after confirming both windows exist."""
    unresolved = ResolvedDate(as_written="soon", earliest=None, latest=None,
                              certainty=DateCertainty.UNRESOLVED, resolved_against=EVAL_TIME,
                              evidence=[span("soon")])
    assert unresolved.window is None
    assert unresolved.overlaps(resolved_date("by next Friday")) is False
    assert resolved_date("by next Friday").overlaps(resolved_date("Friday")) is True


# --------------------------------------------------- C-04..C-08 · the five claim types

CLAIM_BUILDERS = {
    "C-04": entity_mention,
    "C-05": commitment,
    "C-06": decision_state,
    "C-07": dependency,
    "C-08": unclassified_observation,
}


@pytest.mark.parametrize("contract_id", sorted(CLAIM_BUILDERS))
def test_claim_types_round_trip(contract_id):
    assert_round_trips(CLAIM_BUILDERS[contract_id]())


@pytest.mark.parametrize("contract_id", sorted(CLAIM_BUILDERS))
def test_claim_types_refuse_an_empty_receipt(contract_id):
    """Universal rule 4, enforced at the seam that produced the claim. Refusing here costs one
    malformed object; letting it reach V-4 at the publishing gate costs a whole signal."""
    claim = CLAIM_BUILDERS[contract_id]()
    with pytest.raises(ValidationError, match="requires at least one evidence span"):
        type(claim).model_validate({**claim.model_dump(), "evidence": []})


@pytest.mark.parametrize("contract_id", sorted(CLAIM_BUILDERS))
@pytest.mark.parametrize("label,bad,raises", BP_VIOLATIONS, ids=BP_IDS)
def test_claim_types_refuse_non_basis_point_confidence(contract_id, label, bad, raises):
    """CV-BP on every claim type. A 0.87 does not merely spell a confidence differently — lax
    coercion rounds it to 0 and the claim then reads as one nobody believes."""
    claim = CLAIM_BUILDERS[contract_id]()
    with pytest.raises(raises):
        type(claim).model_validate({**claim.model_dump(), "confidence_bp": bad})


def test_c05_requires_an_explicit_conditional_flag():
    """A defaulted `False` is a silent assertion that an unconditional promise was made. The
    concrete cost is a false overdue — we chase a founder about a deliverable that was never
    due, and the second false chase is the last time that founder reads a nudge from us."""
    payload = commitment().model_dump()
    payload.pop("is_conditional")
    with pytest.raises(ValidationError):
        Commitment.model_validate(payload)
    with pytest.raises(TypeError, match="is_conditional must be boolean"):
        Commitment.model_validate({**commitment().model_dump(), "is_conditional": 1})


def test_c05_undated_commitment_is_legal_and_is_not_due_now():
    """`due is None` means no date was stated. It does not mean "due now", and an undated
    commitment is tracked as an open loop rather than escalated as a missed one."""
    undated = Commitment(actor="Deepthi", action="look into the pricing question",
                         is_conditional=False, evidence=[span("I'll look into it", start=12)],
                         confidence_bp=7_000)
    assert undated.due is None
    assert_round_trips(undated)


# ------------------------------------------------------------- C-09 · ExtractionResult

def test_c09_constructs_and_round_trips():
    assert_round_trips(extraction_result())


@pytest.mark.parametrize("forbidden", ["importance_bp", "priority_bp"])
def test_c09_refuses_the_two_scored_field_names(forbidden):
    """Rejected loudly, not ignored quietly. Pydantic's default is to drop an unknown key, so a
    prompt edited to emit `importance_bp` would be accepted forever with the field vanishing at
    the boundary and nobody learning the extractor now produces a score nothing reads.

    Importance is computed at L1.6.7 from facts already span-validated, money-normalised and
    date-resolved; priority is a Layer 4 decision about what to do next."""
    with pytest.raises(ValidationError, match=f"{forbidden} may never appear"):
        ExtractionResult.model_validate({**extraction_result().model_dump(), forbidden: 7_800})


@pytest.mark.parametrize("label,bad,raises", BP_VIOLATIONS, ids=BP_IDS)
def test_c09_field_confidence_is_basis_points_inside_the_dict(label, bad, raises):
    """The `dict[str, int]` annotation stops nothing on its own — lax coercion would round a
    ratio and store it as a per-field confidence."""
    with pytest.raises(raises):
        ExtractionResult.model_validate(
            {**extraction_result().model_dump(), "field_confidence": {"amounts": bad}})


@pytest.mark.parametrize("lane", ["roles", "relationships", "scheduling_proposals"])
def test_c09_untyped_lanes_refuse_a_fractional_number(lane):
    """The three lanes are untyped by design, and an untyped lane is exactly where a 0.85 gets
    in. It matters because these dicts are embedded verbatim in the QES: a ratio here survives
    to the seam where V-7 scans the serialized object and rejects the ENTIRE signal, so catching
    it while the extraction is being built names the offending key instead of condemning the
    message."""
    with pytest.raises(TypeError, match="fractional number"):
        ExtractionResult.model_validate(
            {**extraction_result().model_dump(), lane: [{"nested": {"score": 0.85}}]})


def test_c09_refuses_negative_token_counts():
    """A count of things that happened. Negative is a different kind of value, and it propagates
    straight into cost attribution against `llm_costs`."""
    with pytest.raises(ValidationError, match="non-negative"):
        ExtractionResult.model_validate({**extraction_result().model_dump(), "input_tokens": -1})


def test_c09_evidence_from_claims_dedups_and_includes_the_due_date():
    """Frozen spans are hashable, so the many claims extracted from one sentence share a single
    receipt and ALG-08 verifies each distinct span once. The commitment's `due` window carries
    its own evidence and is walked too — a span attached only to a date would otherwise never be
    verified at all."""
    shared = span("one sentence two claims", start=500)
    twice = entity_mention().model_copy(update={"evidence": [shared]}).model_dump()
    result = ExtractionResult.model_validate({
        **extraction_result().model_dump(), "entity_mentions": [twice, twice]})
    spans = result.evidence_from_claims()
    assert spans.count(shared) == 1
    assert any(s.quote == "by next Friday" for s in spans), "the due date's own span was dropped"


def test_c09_structured_lane_is_visible_but_shape_identical():
    """The L1.3.9 mapping lane produces this SAME type with every mapped field at 10000 and no
    tokens spent. Readable for cost attribution; never a branch, because everything from S3
    onward must treat the two lanes identically or the split this shared shape removes comes
    straight back."""
    mapped = ExtractionResult.model_validate({
        **extraction_result().model_dump(),
        "field_confidence": {"amount": 10_000}, "input_tokens": 0, "output_tokens": 0})
    assert mapped.is_structured_lane is True
    assert extraction_result().is_structured_lane is False


# ------------------------------------------------------- C-10 · Conflict / ConflictClaim

def test_c10_the_74k_vs_84k_fixture_retains_both_claims():
    """The whole doctrine, in one assertion. Resolution is a recommendation with its reasoning
    attached, never a deletion: the signed PDF outranks the email by four ranks and the card
    will say so, and the "$84K" claim is STILL in the row — because the founder routinely knows
    what the ranking does not, that the PDF is the superseded draft or that the email quotes an
    amendment nobody uploaded."""
    conflict = conflict_74k_vs_84k()
    assert len(conflict.claims) == 2
    assert conflict.is_resolved is True
    assert conflict.authority_gap == 4
    amounts = {claim.value.minor_units for claim in conflict.claims}
    assert amounts == {7_400_000, 8_400_000}, "a claim was dropped by resolution"
    written = {claim.value.as_written for claim in conflict.claims}
    assert written == {"$74,000", "$84K"}, "the literal source strings must both survive"
    assert not hasattr(conflict, "winner")


def test_c10_round_trips_with_typed_values_intact():
    """A conflict is stored in `signal_conflicts.claims` as jsonb and read back to be re-judged.
    The value must return as the normalized `Money` it was written as: `Money.same_amount` IS
    ALG-12's money comparison, and it does not exist on a bare dict."""
    back = assert_round_trips(conflict_74k_vs_84k())
    assert isinstance(back.claims[0].value, Money)
    assert isinstance(back.resolved_value, Money)
    assert back.resolved_value.same_amount(back.claims[0].value)


def test_c10_open_values_still_pass_through_untouched():
    """The `Any` tail of `ClaimValue` is not narrowed by naming the two normalized types first —
    a disputed owner name or a nested mapping of contract terms validates and re-serializes
    unchanged, which is what doc 08's bare `Any` was protecting."""
    conflict = Conflict(
        field="renewal.owner",
        claims=[
            ConflictClaim(value="Deepthi", authority=Authority.STRUCTURED_SOURCE,
                          authority_rank=4, evidence=[span("Owner: Deepthi")]),
            ConflictClaim(value={"name": "Rohit", "seen": 3},
                          authority=Authority.CHAT_ASIDE, authority_rank=1,
                          evidence=[span("rohit owns this now", start=20)]),
        ],
        resolution=ConflictResolution.RESOLVED_BY_AUTHORITY,
        resolved_value="Deepthi",
        detected_at=EVAL_TIME)
    back = assert_round_trips(conflict)
    assert back.claims[0].value == "Deepthi"
    assert back.claims[1].value == {"name": "Rohit", "seen": 3}


def test_c10_single_claim_raises():
    """The doc's own listed case. One claim is a fact, not a disagreement — and the type that
    exists to stop facts being silently replaced must not itself be constructible as one."""
    with pytest.raises(ValidationError, match="needs at least 2 claims"):
        Conflict(field="contract.value",
                 claims=[ConflictClaim(value=money(7_400_000, "$74,000"),
                                       authority=Authority.SIGNED_DOCUMENT, authority_rank=6,
                                       evidence=[span("Total: $74,000")])],
                 resolution=ConflictResolution.UNRESOLVED_SURFACE_BOTH,
                 resolved_value=None, detected_at=EVAL_TIME)


def test_c10_unresolved_carrying_a_resolved_value_raises():
    """The doc's own listed case. Surfacing both sides and naming a resolved value at once is
    picking a winner silently — the precise behaviour this contract exists to prevent."""
    conflict = conflict_74k_vs_84k()
    with pytest.raises(ValidationError, match="must carry resolved_value=None"):
        Conflict.model_validate({
            **conflict.model_dump(),
            "resolution": ConflictResolution.UNRESOLVED_SURFACE_BOTH.value})


def test_c10_resolution_without_a_value_raises():
    """The converse. A `resolved_by_*` naming no value renders as "the signed document has
    higher authority" next to a blank, and nothing downstream would catch it."""
    with pytest.raises(ValidationError, match="requires a resolved_value"):
        Conflict.model_validate({**conflict_74k_vs_84k().model_dump(), "resolved_value": None})


def test_c10_authority_rank_is_a_rank_not_a_score():
    """ALG-12 step 4 subtracts two ranks and compares the difference to 2 — arithmetic that is
    meaningless the moment a 7,500 bp confidence is pasted into the field, since 7500 vs 2
    resolves every conflict it touches in favour of whichever side leaked a bp value."""
    for bad in (MAX_AUTHORITY_RANK + 1, 7_500):
        with pytest.raises(ValidationError, match="a rank is not a basis-point score"):
            ConflictClaim(value="x", authority=Authority.EMAIL_PROSE, authority_rank=bad,
                          evidence=[span("x")])
    with pytest.raises(ValidationError, match="non-negative"):
        ConflictClaim(value="x", authority=Authority.EMAIL_PROSE, authority_rank=4.0,
                      evidence=[span("x")])


def test_c10_claim_requires_a_receipt():
    """Without this the cheapest way to win a conflict is to assert a value with nothing behind
    it and a high authority string."""
    with pytest.raises(ValidationError, match="conflict claim requires evidence"):
        ConflictClaim(value=money(8_400_000, "$84K"), authority=Authority.SIGNED_DOCUMENT,
                      authority_rank=6, evidence=[])


def test_c10_refuses_a_float_at_any_depth():
    """V-7 at the seam that produced the object. `mode="before"` so the float is refused before
    it is ever bound to the `Any` field and written to jsonb, where it comes back out as a
    number nobody can trace to a source string."""
    with pytest.raises(TypeError, match="must not contain a float"):
        ConflictClaim(value={"terms": [{"uplift": 0.07}]}, authority=Authority.ATTACHMENT,
                      authority_rank=3, evidence=[span("uplift")])
    with pytest.raises(TypeError, match="must not contain a float"):
        Conflict.model_validate({**conflict_74k_vs_84k().model_dump(),
                                 "resolved_value": 74_000.10})


def test_c10_forbids_a_winner_field():
    """`extra="forbid"` is load-bearing, not hygiene: the single most likely future edit is
    somebody adding `winner=...` because it would make a renderer simpler, and pydantic's
    default silently ignores the kwarg while the caller believes it stored something."""
    with pytest.raises(ValidationError):
        Conflict.model_validate({**conflict_74k_vs_84k().model_dump(), "winner": "signed"})


def test_c10_is_frozen():
    """A record of a disagreement that happened. A record that can be edited afterwards is not
    one, and the evidence would still point at text the claim no longer asserts."""
    conflict = conflict_74k_vs_84k()
    with pytest.raises(ValidationError):
        conflict.resolution = ConflictResolution.UNRESOLVED_SURFACE_BOTH


# ------------------------------------------------------------------- C-11 · SignalType

@pytest.mark.gate
def test_c11_has_exactly_the_documented_member_set():
    """The taxonomy is CLOSED, and this assertion is what makes adding a member deliberate.

    Compared against a hand-written literal set rather than against the enum itself: deriving
    the expectation from the thing under test would make the assertion true by construction and
    a fifteenth member would land silently. Downstream, ALG-16 owns a precedence order over
    these names and ALG-17 a per-type weight for each, so a member added without touching both
    is a type that can be classified and then scored as if it were nothing in particular. The
    sanctioned route for something genuinely new is the OPEN LANE (C-08), never a coercion to
    the nearest neighbour.
    """
    assert {member.value for member in SignalType} == DOC_SIGNAL_TYPES
    assert len(SignalType) == 15
    assert all(isinstance(member.value, str) for member in SignalType)
    assert SignalType("information_conflict") is SignalType.INFORMATION_CONFLICT


def test_c11_an_unknown_kind_is_refused_never_coerced():
    """The nearest neighbour of an unrecognised kind is exactly where a novel pattern would be
    silently absorbed and never noticed."""
    with pytest.raises(ValueError, match="not a valid SignalType"):
        SignalType("renewal_probably")
    with pytest.raises(ValidationError, match="not a valid SignalType"):
        qualified_signal(signal_type="renewal_probably")


# ------------------------------------------------- C-12 · QualifiedEnterpriseSignal

def test_c12_constructs_and_round_trips_identically():
    """Doc 08's own W0 acceptance line. This object becomes one `qualified_signals` row, so a
    reparse that is not identical is a row that means something different the second time it is
    read than it did when it was written."""
    back = assert_round_trips(qualified_signal())
    assert back.recipients == ("deepthi@globeworked.com", "rohit@antler.co")
    assert isinstance(back.recipients, tuple), "recipients must rehydrate hashable, not a list"
    assert back.is_live is True
    assert back.conflicts[0].claims[1].value.as_written == "$84K"


def test_c12_requires_a_receipt():
    """V-4 at construction, which is stricter and earlier than the gate: an unpublishable signal
    cannot be built, stored, or handed to L2 by a caller that forgot to run L1.6.10."""
    with pytest.raises(ValidationError, match="evidence_refs must be non-empty"):
        qualified_signal(evidence_refs=[])


def test_c12_visibility_is_required():
    """The only field whose absence PARKS rather than rejects. Typing it non-optional is what
    makes V-1 unbypassable instead of merely documented — an audience we cannot name is not an
    audience we may assume."""
    with pytest.raises(ValidationError):
        qualified_signal(visibility=None)


@pytest.mark.parametrize("field", ["importance_bp", "confidence_bp"])
@pytest.mark.parametrize("label,bad,raises", BP_VIOLATIONS, ids=BP_IDS)
def test_c12_scores_are_basis_points(field, label, bad, raises):
    """V-3 and CV-BP. Lax coercion would round 0.87 to 0 and call it a confidence."""
    with pytest.raises(raises):
        qualified_signal(**{field: bad})


@pytest.mark.parametrize("vector,raises", [
    ({"evidence": 9_000, "expertise": 5_500, "freshness": 8_800}, ValidationError),
    ({"evidence": 9_000, "expertise": 5_500, "freshness": 8_800, "coverage": 4_100,
      "vibes": 5_000}, ValidationError),
    ({"evidence": 9_000, "expertise": 5_500, "freshness": 8_800, "coverage": 0.41}, TypeError),
], ids=["missing", "unknown", "ratio"])
def test_c12_confidence_vector_carries_exactly_four_components(vector, raises):
    """ALG-13 composes `confidence_bp` from these four, and a vector missing one does not
    compose to a smaller number — it composes to a DIFFERENTLY-DERIVED number that still looks
    like a confidence. An absent key also reads as zero to every consumer doing `.get(key, 0)`,
    so "we did not measure freshness" would be indistinguishable from "freshness was zero"."""
    assert CONFIDENCE_COMPONENTS == frozenset({"evidence", "expertise", "freshness", "coverage"})
    with pytest.raises(raises):
        qualified_signal(confidence_vector=vector)


def test_c12_triage_lane_and_state_are_closed_sets():
    """Neither failure is loud on its own. An unknown lane sorts unpredictably in the runner's
    ORDER BY — the queue is simply worked in an order nobody designed — and an unknown state
    disappears from every query written against ALG-19's four."""
    with pytest.raises(ValidationError, match="triage_lane must be one of"):
        qualified_signal(triage_lane="P9")
    with pytest.raises(ValidationError, match="state must be one of"):
        qualified_signal(state="dead")


def test_c12_expired_without_a_clock_raises():
    """A signal marked expired with no `expires_at` claims a clock ran out and names no clock.
    ALG-19 expires only when that timestamp has passed, so the state cannot honestly exist
    without the field, and the card would read "this expired" next to a blank."""
    with pytest.raises(ValidationError, match="must carry the expires_at"):
        qualified_signal(state="expired", expires_at=None)


def test_c12_self_supersede_raises():
    """`supersedes` is walked to reconstruct a subject's history, so a self-pointer makes that
    walk non-terminating while looking perfectly ordinary in a single row."""
    with pytest.raises(ValidationError, match="may not supersede itself"):
        qualified_signal(supersedes="sig_0f21ab")


def test_c12_versions_must_be_present_and_float_free():
    """An unversioned signal cannot be replayed at all — there is no way to know which prompt,
    vocabulary or model produced it, so a September re-run silently re-derives it with today's
    code and calls the result the same decision. The float guard is V-7 over the one field wide
    enough to smuggle one."""
    with pytest.raises(ValidationError, match="versions is required"):
        qualified_signal(versions={})
    with pytest.raises(TypeError, match="must not contain a float"):
        qualified_signal(versions={"prompt": "v3", "calibration": {"weight": 0.9}})


def test_c12_recipients_reject_a_bare_string_and_blank_entries():
    """"Nobody else was on this" and "we never populated this" are different facts, and a blank
    entry inflates every "was this a broadcast" count by one without naming anybody. A bare
    string would iterate into characters."""
    with pytest.raises(TypeError, match="sequence of addresses"):
        qualified_signal(recipients="deepthi@globeworked.com")
    with pytest.raises(ValidationError):
        qualified_signal(recipients=("deepthi@globeworked.com", "  "))


def test_c12_unverified_span_reads_are_available_to_the_publisher():
    """The two reads L1.6.10 needs for V-5. The DOWNGRADE policy deliberately lives with the
    publisher, not frozen into a boundary type every stored row was validated against — what a
    contract can honestly say is whether the condition holds, and which quote to go look at."""
    signal = qualified_signal(evidence_refs=[span("verified quote"),
                                             span("invented quote", start=50, verified=False)])
    assert signal.all_spans_verified is False
    assert [s.quote for s in signal.unverified_spans] == ["invented quote"]
    assert qualified_signal().all_spans_verified is True


def test_c12_expiry_is_evaluated_against_a_passed_instant():
    """The instant is a PARAMETER, never `datetime.now()` read inside the object: a clock read
    here would make a replay of a March signal answer differently in September, and this object
    is evidence. `expires_at is None` returns False — nothing expires it on a clock — which is
    not the same as "it is still true", a question `state` answers."""
    signal = qualified_signal()
    assert signal.has_expired_by(EVAL_TIME) is False
    assert signal.has_expired_by(EVAL_TIME + timedelta(days=181)) is True
    assert qualified_signal(expires_at=None).has_expired_by(EVAL_TIME) is False


def test_c12_lifecycle_transition_revalidates_instead_of_bypassing():
    """`validate_assignment=True` is what stops ALG-19 writing a state no rule allows. Freezing
    the object would push every transition through `model_copy(update=...)`, which skips
    validators entirely — so the lifecycle manager would gain exactly the power the closed state
    set exists to deny it."""
    signal = qualified_signal()
    signal.state = "superseded"
    assert signal.is_live is False
    with pytest.raises(ValidationError):
        signal.state = "closed"


def test_c12_forbids_an_unknown_field():
    """With 24 fields, a mistyped kwarg under pydantic's default is a value that silently never
    arrives."""
    with pytest.raises(ValidationError):
        qualified_signal(priority_bp=9_000)


# --------------------------------------------------------- the four universal rules, once

@pytest.mark.gate
def test_no_float_anywhere_in_a_fully_populated_serialized_signal():
    """Universal rule: no `float` appears in the SERIALIZED object — walked, not annotated.

    The annotations cannot carry this rule on their own. `versions`, `ConflictClaim.value`,
    `Conflict.resolved_value` and the three untyped extraction lanes are all `Any`-wide, and a
    ratio nested three keys deep inside one of them reaches `qualified_signals` as jsonb and
    comes back out as a number nobody can trace to a source string. So the assertion is made
    against the bytes that actually get stored: decode the JSON and refuse a float at any depth.

    The fixture is deliberately maximal — every list non-empty, every optional assigned, both
    conflict claims carrying `Money`, all three open lanes populated — because a walk over a
    sparse object proves the rule for the fields that happened to be filled in.
    """
    signal = qualified_signal()
    document = json.loads(signal.model_dump_json())
    leaves = walk_json(document)

    floats = [(path, value) for path, value in leaves if isinstance(value, float)]
    assert floats == [], f"float(s) reached the serialized signal: {floats}"

    # The walk must have had something to walk. Without this the assertion above would pass just
    # as loudly over an object whose every interesting lane was empty.
    paths = {path for path, _ in leaves}
    for required in ("$.versions.prompt", "$.conflicts[0].claims[0].value.minor_units",
                     "$.extraction.roles[0].seen_count",
                     "$.extraction.scheduling_proposals[0].attendees",
                     "$.extraction.field_confidence.amounts", "$.confidence_vector.coverage",
                     "$.importance_bp", "$.evidence_refs[0].start_offset"):
        assert required in paths, f"the no-float fixture never populated {required}"
    assert len(leaves) > 100, "the no-float fixture is too sparse to prove anything"

    # And the live object, not only its JSON form — `require_no_float` has a BaseModel branch,
    # so it sees values `mode="json"` would have coerced on the way out.
    assert require_no_float(signal, "signal") is signal


@pytest.mark.gate
def test_every_l1_contract_round_trips():
    """C-01..C-12, each constructed and reparsed. C-11 is an enum rather than a model, so it
    round-trips as the wire literal its `str` base exists to guarantee."""
    surface = {
        "C-01": span("the $84K annual contract", start=310),
        "C-02": money(8_400_000, "$84K"),
        "C-03": resolved_date("by next Friday"),
        "C-04": entity_mention(),
        "C-05": commitment(),
        "C-06": decision_state(),
        "C-07": dependency(),
        "C-08": unclassified_observation(),
        "C-09": extraction_result(),
        "C-10": conflict_74k_vs_84k(),
        "C-12": qualified_signal(),
    }
    assert set(surface) | {"C-11"} == {f"C-{n:02d}" for n in range(1, 13)}
    for contract_id, obj in surface.items():
        assert_round_trips(obj), contract_id
    assert json.loads(json.dumps(SignalType.CONTRACT_RENEWAL.value)) == "contract_renewal"


# --------------------------------------------------------- V-1..V-7 · the publication gate

def test_v1_missing_visibility_parks_and_stays_recoverable():
    """V-1 is the ONLY rule whose failure parks, and park is not delete.

    An event whose audience was never established is not a bad signal, it is an unanswered
    question — and the answer is frequently recoverable (the connector re-syncs the thread, an
    admin maps the workspace) in a way a hallucinated quote never is. The reason code is spelled
    exactly as S0.6 spells it so one filter over `parked_events` finds every event with an
    unestablished audience rather than the half that failed early.
    """
    decision = validate_publication(bypassed_signal(visibility=None))

    assert decision.outcome is PublicationOutcome.PARK
    assert decision.failed_rules == (PublicationRule.V1,)
    assert decision.signal is None, "a parked signal must be unpublishable by construction"
    assert decision.parked is not None
    assert decision.parked.reason_code == VISIBILITY_UNKNOWN
    assert decision.parked.event_id == "evt_7f31"
    assert decision.parked.status == "pending"
    assert "visibility is not established" in decision.failures[0].detail
    assert decision.should_emit is False


def test_v1_short_circuits_the_rest_of_the_gate():
    """Every rule after V-1 reads an envelope V-1 has just established is not there."""
    decision = validate_publication(bypassed_signal(visibility=None, importance_bp=10_001))
    assert decision.failed_rules == (PublicationRule.V1,)


def test_v2_unknown_signal_type_rejects():
    """Reject, never a coercion to a near neighbour — the nearest neighbour of an unrecognised
    kind is exactly where a novel pattern gets silently absorbed."""
    decision = validate_publication(bypassed_signal(signal_type="renewal_probably"))

    assert decision.outcome is PublicationOutcome.REJECT
    assert PublicationRule.V2 in decision.blocking_rules
    assert decision.signal is None, "a rejected signal must not be reachable through the result"
    assert "renewal_probably" in decision.failures[0].detail


def test_v3_importance_outside_basis_points_rejects():
    """`require_bp` refuses the bool and the ratio as well as the range, which is what stops a
    0.87 pydantic would have rounded to 0 from passing as a legal importance."""
    for bad in (10_001, 0.87, True):
        decision = validate_publication(bypassed_signal(importance_bp=bad))
        assert decision.outcome is PublicationOutcome.REJECT
        assert PublicationRule.V3 in decision.blocking_rules


def test_v4_empty_evidence_rejects():
    """A claim with no receipt is a guess, and a guess must not reach a human wearing the same
    typography as a fact. Checked at the gate as well as at construction because this is the
    seam that has to record WHY nothing was published."""
    decision = validate_publication(bypassed_signal(evidence_refs=[]))

    assert decision.outcome is PublicationOutcome.REJECT
    assert decision.failed_rules == (PublicationRule.V4,)
    assert "a claim with no receipt is a guess" in decision.failures[0].detail


def test_v5_unverified_evidence_downgrades_and_emits_it_does_not_reject():
    """V-5 is the ONE non-blocking rule: an unverified span degrades trust, it does not destroy
    the signal — the claim may be perfectly true and merely quoted loosely, which is why ALG-08
    keeps such a claim at halved confidence rather than dropping it.

    So the assertion is three-part and all three matter: the outcome is EMIT, the published
    confidence is STRICTLY LOWER than the input's, and the signal carries a flag naming what a
    human should go check. The input object is left untouched — a caller that logs what it
    handed over must log what it handed over.
    """
    signal = qualified_signal(
        confidence_bp=8_000,
        evidence_refs=[span("Total annual commitment: $74,000",
                            source_ref="chunk:doc_msa_2026:3"),
                       span("the $84K annual contract", start=310, verified=False)])

    decision = validate_publication(signal)

    assert decision.outcome is PublicationOutcome.EMIT
    assert decision.should_emit is True
    assert decision.failed_rules == (PublicationRule.V5,)
    assert decision.blocking_rules == (), "V-5 must never block"
    assert decision.flags == (UNVERIFIED_EVIDENCE_FLAG,)
    assert decision.unverified_span_count == 1

    assert decision.signal is not None
    assert decision.signal.confidence_bp == 6_000, "one of two spans unverified -> three quarters"
    assert decision.published_confidence_bp == 6_000
    assert decision.confidence_downgrade_bp == 2_000
    assert decision.signal.confidence_bp < signal.confidence_bp
    assert signal.confidence_bp == 8_000, "the gate must not mutate its argument"
    assert decision.signal is not signal


def test_v5_downgrade_is_integer_arithmetic_at_both_ends():
    """Every span unverified gives ALG-08's exact halving; every span verified leaves the number
    alone (and V-5 did not fire at all). Floor division rounds DOWN, the one direction that
    cannot manufacture certainty on the margins."""
    assert downgrade_for_unverified(8_000, total_spans=2, verified_spans=0) == 4_000
    assert downgrade_for_unverified(8_000, total_spans=2, verified_spans=2) == 8_000
    assert downgrade_for_unverified(8_001, total_spans=3, verified_spans=1) == 5_334
    assert isinstance(downgrade_for_unverified(8_001, total_spans=3, verified_spans=1), int)
    with pytest.raises(ValueError, match="cannot exceed"):
        downgrade_for_unverified(8_000, total_spans=2, verified_spans=3)


def test_v6_confidence_above_the_weakest_source_rejects():
    """Rule 11 (ALG-13, L1.5.7). Several weak sources repeating one weak thing is not
    corroboration, and without this ceiling composition becomes a machine for manufacturing
    certainty out of sources that all say the same weak thing."""
    signal = qualified_signal(confidence_bp=8_000)

    decision = validate_publication(signal, source_confidences=[6_000, 9_000])

    assert decision.outcome is PublicationOutcome.REJECT
    assert decision.failed_rules == (PublicationRule.V6,)
    assert decision.waived == ()
    assert "exceeds the weakest source" in decision.failures[0].detail
    assert signal.confidence_respects_sources([6_000, 9_000]) is False


def test_v6_passes_at_the_ceiling_and_is_not_in_play_without_sources():
    """The ceiling is `min`, inclusive. An empty source list means the rule DID NOT APPLY —
    which a caller must not read as "V-6 passed", and which is why the sources are the inputs to
    the composition and never the composed result fed back in."""
    at_ceiling = validate_publication(qualified_signal(confidence_bp=6_000),
                                      source_confidences=[6_000, 9_000])
    assert at_ceiling.outcome is PublicationOutcome.EMIT
    assert at_ceiling.failed_rules == ()

    not_in_play = validate_publication(qualified_signal(confidence_bp=9_900))
    assert not_in_play.outcome is PublicationOutcome.EMIT
    assert qualified_signal(confidence_bp=9_900).confidence_respects_sources([]) is True


def test_v6_named_independent_evidence_waives_the_ceiling_and_is_recorded():
    """The exception the rule itself names. Two genuinely separate sources agreeing is
    corroboration; two copies of one weak source agreeing is an echo, and only the caller can
    tell them apart. The waiver is RECORDED rather than merely honoured — a confidence that
    exceeded its sources because somebody passed a name must stay auditable, since "we named
    independent evidence" is exactly the claim that would otherwise be invisible in the row."""
    decision = validate_publication(
        qualified_signal(confidence_bp=8_000),
        source_confidences=[6_000, 9_000],
        independent_evidence=["countersigned MSA chunk:doc_msa_2026:3"])

    assert decision.outcome is PublicationOutcome.EMIT
    assert decision.waived == (PublicationRule.V6,)
    assert PublicationRule.V6 not in decision.failed_rules
    assert decision.published_confidence_bp == 8_000


def test_v7_a_float_anywhere_rejects():
    """No float anywhere in the serialized object — and the walk reaches the `Any` lanes an
    annotation cannot. Both a top-level ratio and one nested three keys deep are refused."""
    for versions in ({"prompt": "v3", "calibration": 0.87},
                     {"prompt": "v3", "calibration": {"weights": [{"recency": 0.4}]}}):
        decision = validate_publication(bypassed_signal(versions=versions))
        assert decision.outcome is PublicationOutcome.REJECT
        assert decision.failed_rules == (PublicationRule.V7,)
        assert "must not contain a float" in decision.failures[0].detail


def test_the_gate_records_every_broken_thing_not_just_the_first():
    """Fixing failures one release apart is how a pipeline stays broken for three releases. V-5
    is recorded alongside the blocking rules even though it does not block — it changed nothing
    here because nothing was published, but it is still a fact about the object."""
    decision = validate_publication(bypassed_signal(
        signal_type="renewal_probably",
        importance_bp=10_001,
        evidence_refs=[span("invented quote", verified=False)],
        versions={"prompt": 0.87}))

    assert decision.outcome is PublicationOutcome.REJECT
    assert set(decision.failed_rules) == {PublicationRule.V2, PublicationRule.V3,
                                          PublicationRule.V5, PublicationRule.V7}
    assert PublicationRule.V5 not in decision.blocking_rules
    assert decision.unverified_span_count == 1


def test_the_gate_absorbs_both_refusal_grammars():
    """A refusal must become a ROW, never a traceback — in BOTH of the grammars a contract uses.

    `validators.py` fails closed by raising, and it raises two different exceptions: `TypeError`
    for a wrong-KIND value (a ratio where basis points were promised, a bool where an integer
    was) and `ValueError` for a wrong-VALUE one (10001 bp, an unknown enum member). Pydantic
    converts only the second into a `ValidationError`; a `TypeError` inside a validator is, by
    pydantic's own contract, a bug in the validator and propagates untouched. So a caller writing
    the natural `except ValidationError` around a rehydration would catch the out-of-range case
    and crash on the ratio.

    At the one seam where that distinction can do damage it is closed, and this asserts it:
    `publication._refusal` catches exactly `(TypeError, ValueError)`, so both arrive as a
    `RuleFailure` carrying the rule id a rejection ledger stores. "The engine produced nothing
    for that email" is unanswerable otherwise, and a traceback inside a publisher loop is a log
    line nobody joins to a signal that never appeared.

    Everything ABOVE the gate is on notice, which is why this is pinned rather than papered over:
    W1..W8 must catch `(TypeError, ValidationError)` — or call `validate_publication` — when
    rehydrating a stored row, because `except ValidationError` alone is a half-open handler.
    """
    ratio = validate_publication(bypassed_signal(importance_bp=0.87))      # TypeError inside
    out_of_range = validate_publication(bypassed_signal(importance_bp=10_001))  # ValueError

    for decision in (ratio, out_of_range):
        assert decision.outcome is PublicationOutcome.REJECT
        assert PublicationRule.V3 in decision.blocking_rules
        assert all(failure.detail for failure in decision.failures), \
            "a refusal with no sentence is not reviewable"

    # The ratio trips V-7 as well, and that is right rather than noise: a float in a scored field
    # is BOTH a bad basis point and a float in the serialized object, and the rejection row should
    # name both so fixing the score does not leave the jsonb hole open. The out-of-range integer
    # is a legal JSON number, so it trips V-3 alone.
    assert set(ratio.failed_rules) == {PublicationRule.V3, PublicationRule.V7}
    assert out_of_range.failed_rules == (PublicationRule.V3,)

    # And the grammars really are the two claimed — asserted here so this test fails loudly if a
    # future pydantic release starts wrapping TypeError, rather than the parametrisations above
    # silently testing nothing.
    with pytest.raises(TypeError):
        qualified_signal(importance_bp=0.87)
    with pytest.raises(ValidationError):
        qualified_signal(importance_bp=10_001)


def test_a_clean_signal_emits_unchanged():
    """The whole surface, end to end: a validly constructed C-12 passes all seven rules, is
    emitted as the same object it went in as, and carries no flag."""
    signal = qualified_signal()
    decision = validate_publication(signal, source_confidences=[6_200, 8_800])

    assert decision.outcome is PublicationOutcome.EMIT
    assert decision.failures == ()
    assert decision.flags == ()
    assert decision.signal is signal, "an unmodified signal must not be needlessly copied"
    assert decision.published_confidence_bp == signal.confidence_bp
    assert decision.confidence_downgrade_bp == 0
