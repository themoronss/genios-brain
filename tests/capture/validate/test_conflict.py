"""G5 · ALG-12, the conflict detector — Wave W5.

The gate fixture is fixed by doc 05: \\$74K in the signed contract against \\$84K in an email
body must produce a `Conflict` that RETAINS BOTH claims, resolves by authority, and lands on
\\$74K. Retaining both is not politeness — a card that shows only the winner cannot explain
itself, and the loser is the evidence that the winner was contested.

The headline fixture presents the two claims as SEPARATE EVENTS — an `email_message` and its
`email_attachment` joined by `parent_object_id`, which is how the Gmail connector emits them
(`capture/connectors/composio.py:562`). A fixture that put both amounts inside one event would
pass for the wrong reason and hide the exact defect this gate exists to catch, so the wired
test at the bottom drives `capture_event` TWICE and the pure tests carry two `event_id`s.

    ./.venv/bin/python -m pytest tests/capture/validate/test_conflict.py -q
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.capture import pipeline as P
from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.validate import conflict as C
from genios_engine.capture.validate.authority import Provenance, weigh_authority
from genios_engine.contracts.conflict import Authority, Conflict, ConflictResolution
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import ExtractionResult
from genios_engine.contracts.signal import SignalType
from genios_engine.contracts.units import DateCertainty, Money, ResolvedDate

WAVE = "W5"
GATE = "G5"

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
EARLIER = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 1, 20, 9, 0, tzinfo=timezone.utc)
DETECTED = datetime(2026, 1, 21, 12, 0, tzinfo=timezone.utc)

SUBJECT = "contract:aws-enterprise-agreement"
OWNER = "founder@genios.ai"


# ---------------------------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------------------------

def span(quote: str, ref: str = "chunk:aws_agreement.pdf:42", *,
         verified: bool = True) -> EvidenceSpan:
    """A receipt ALG-08 has already graded.

    `verified=True` by DEFAULT and that default is load-bearing, not convenience. Every fixture
    below is a claim being weighed against another claim, and D3 says a receipt ALG-08 could not
    find in the source is not admissible as one side of a disagreement — so a helper that
    produced `verified=False` (the `EvidenceSpan` constructor default, correct for an extractor's
    raw output) would be building the one shape this unit refuses, and every test using it would
    then pass or fail for a reason it never states. Unverified receipts are constructed
    EXPLICITLY, in the D3 block, where that is the point.
    """
    return EvidenceSpan(source_ref=ref, quote=quote, start_offset=0, end_offset=len(quote),
                        verified=verified)


def usd(minor_units: int, as_written: str, currency: str = "USD") -> Money:
    return Money(minor_units=minor_units, currency=currency, as_written=as_written)


def day(as_written: str, first: datetime, last: datetime | None = None) -> ResolvedDate:
    last = first if last is None else last
    certainty = DateCertainty.EXACT if last == first else DateCertainty.RANGE
    return ResolvedDate(as_written=as_written, earliest=first, latest=last,
                        certainty=certainty, resolved_against=NOW,
                        evidence=[span(as_written, "email:thread-8f2a")])


def unresolved_date(as_written: str) -> ResolvedDate:
    return ResolvedDate(as_written=as_written, earliest=None, latest=None,
                        certainty=DateCertainty.UNRESOLVED, resolved_against=NOW,
                        evidence=[span(as_written, "email:thread-8f2a")])


def claim(claim_id: str, value, authority: Authority, *, quote: str = "as stated",
          field: str = "contract.value", subject: str = SUBJECT,
          at: datetime = NOW, event_id: str | None = None,
          supersedes: str | None = None, ref: str = "chunk:aws_agreement.pdf:42"
          ) -> C.NormalizedClaim:
    return C.NormalizedClaim(
        claim_id=claim_id, subject_key=subject, field=field, value=value,
        authority=authority, evidence=(span(quote, ref),), asserted_at=at,
        event_id=event_id or f"evt_{claim_id}", supersedes=supersedes)


#: The headline pair, as two SEPARATE events: the signed PDF and the email that quotes it.
SIGNED_74K = claim("c_pdf", usd(7_400_000, "$74,000"), Authority.SIGNED_DOCUMENT,
                   quote="total annual commitment of $74,000", at=EARLIER,
                   event_id="evt_attachment")
EMAIL_84K = claim("c_mail", usd(8_400_000, "$84K"), Authority.EMAIL_PROSE,
                  quote="the $84K annual contract", at=LATER, event_id="evt_message",
                  ref="email:thread-8f2a")


def detect(*claims, **over) -> C.ConflictDetection:
    kwargs = {"detected_at": DETECTED}
    kwargs.update(over)
    return C.detect_conflicts(claims, **kwargs)


def only(detection: C.ConflictDetection) -> Conflict:
    assert len(detection.conflicts) == 1, f"expected one conflict, got {detection.conflicts}"
    return detection.conflicts[0].conflict


# ---------------------------------------------------------------------------------------------
# U1 · the headline fixture
# ---------------------------------------------------------------------------------------------

@pytest.mark.gate
def test_signed_contract_beats_email_body_and_both_claims_survive():
    """\\$74K attachment vs \\$84K body, as two linked events: resolved_by_authority to \\$74K,
    with BOTH claims retained on the Conflict."""
    detection = detect(EMAIL_84K, SIGNED_74K)
    conflict = only(detection)

    assert conflict.field == "contract.value"
    assert conflict.resolution is ConflictResolution.RESOLVED_BY_AUTHORITY
    assert conflict.resolved_value.minor_units == 7_400_000

    assert len(conflict.claims) == 2, "the losing claim was deleted — the whole defect"
    kept = {c.value.minor_units for c in conflict.claims}
    assert kept == {7_400_000, 8_400_000}
    loser = next(c for c in conflict.claims if c.value.minor_units == 8_400_000)
    assert loser.evidence[0].quote == "the $84K annual contract", "the loser lost its receipt"
    assert loser.authority is Authority.EMAIL_PROSE

    assert detection.conflicts[0].event_ids == ("evt_attachment", "evt_message"), (
        "a conflict that lives inside one event is not the case this unit exists for")
    assert conflict.detected_at == DETECTED, "detected_at must be the caller's, not a clock's"


def test_the_stronger_claim_is_rendered_first_but_nothing_is_dropped():
    """Ordering is a presentation decision; retention is the doctrine. Both hold at once."""
    conflict = only(detect(EMAIL_84K, SIGNED_74K))
    assert [c.authority for c in conflict.claims] == [Authority.SIGNED_DOCUMENT,
                                                      Authority.EMAIL_PROSE]
    assert [c.authority_rank for c in conflict.claims] == [6, 2]


def test_the_input_order_does_not_change_the_answer():
    """Determinism: the sweep that reads the attachment first must produce the same row."""
    first = detect(EMAIL_84K, SIGNED_74K).conflicts[0].conflict
    second = detect(SIGNED_74K, EMAIL_84K).conflicts[0].conflict
    assert first.model_dump_json() == second.model_dump_json()


# ---------------------------------------------------------------------------------------------
# U1 · steps 2 and 3, the tolerance ladder
# ---------------------------------------------------------------------------------------------

AGREEMENT_ROWS = (
    # id, left value, right value, is_conflict
    ("the same amount asserted twice",
     usd(8_400_000, "$84,000"), usd(8_400_000, "$84K"), False),
    ("the same amount written in two locales",
     usd(8_400_000, "84.000,00"), usd(8_400_000, "84,000.00"), False),
    ("two different amounts",
     usd(8_400_000, "$84K"), usd(7_400_000, "$74,000"), True),
    ("one amount, two currencies",
     usd(8_400_000, "$84,000"), usd(8_400_000, "€84,000", currency="EUR"), True),
    ("an amount whose currency nobody wrote down",
     usd(8_400_000, "$84,000"), usd(8_400_000, "84,000", currency="UNKNOWN"), False),
    ("a range and a point inside it",
     day("Oct 10-17", datetime(2026, 10, 10, tzinfo=timezone.utc),
         datetime(2026, 10, 17, tzinfo=timezone.utc)),
     day("Oct 15", datetime(2026, 10, 15, tzinfo=timezone.utc)), False),
    ("two windows that touch at one endpoint",
     day("Oct 10-15", datetime(2026, 10, 10, tzinfo=timezone.utc),
         datetime(2026, 10, 15, tzinfo=timezone.utc)),
     day("Oct 15-20", datetime(2026, 10, 15, tzinfo=timezone.utc),
         datetime(2026, 10, 20, tzinfo=timezone.utc)), False),
    ("two dates a month apart",
     day("Oct 15", datetime(2026, 10, 15, tzinfo=timezone.utc)),
     day("Nov 15", datetime(2026, 11, 15, tzinfo=timezone.utc)), True),
    ("silence about a deadline is not a competing claim",
     unresolved_date("pretty soon"),
     day("Oct 15", datetime(2026, 10, 15, tzinfo=timezone.utc)), False),
    ("the same text, differently spaced and cased",
     "Net  30  DAYS", "net 30 days", False),
    ("two different terms",
     "net 30 days", "net 60 days", True),
    ("two values nothing can compare",
     usd(8_400_000, "$84K"), "eighty-four thousand", False),
)


@pytest.mark.parametrize("left,right,is_conflict",
                         [pytest.param(*row[1:], id=row[0]) for row in AGREEMENT_ROWS])
def test_only_a_provable_disagreement_is_a_conflict(left, right, is_conflict):
    """Step 3. A false conflict costs the founder's attention and teaches them the card is
    noise — after which the real conflict is ignored too."""
    detection = detect(claim("a", left, Authority.EMAIL_PROSE, event_id="evt_a"),
                       claim("b", right, Authority.EMAIL_PROSE, event_id="evt_b"))
    assert bool(detection.conflicts) is is_conflict
    assert detection.total_detected == (1 if is_conflict else 0)


def test_two_claims_about_different_fields_never_compete():
    """Grouping is by (subject, field). A renewal date and a contract value disagreeing would
    be nonsense, and the group key is the only thing stopping it."""
    assert detect(claim("a", usd(8_400_000, "$84K"), Authority.EMAIL_PROSE),
                  claim("b", usd(7_400_000, "$74K"), Authority.EMAIL_PROSE,
                        field="deal.amount")).conflicts == ()


def test_the_same_amount_on_two_different_subjects_is_not_a_conflict():
    assert detect(claim("a", usd(8_400_000, "$84K"), Authority.EMAIL_PROSE),
                  claim("b", usd(7_400_000, "$74K"), Authority.EMAIL_PROSE,
                        subject="contract:other-vendor")).conflicts == ()


def test_one_claim_is_a_fact_not_a_disagreement():
    assert detect(SIGNED_74K).conflicts == ()


# ---------------------------------------------------------------------------------------------
# U1 · step 4, resolution
# ---------------------------------------------------------------------------------------------

RESOLUTION_ROWS = (
    # id, left authority, right authority, expected resolution, expected winning minor_units
    ("a signed document four ranks above an email",
     Authority.SIGNED_DOCUMENT, Authority.EMAIL_PROSE,
     ConflictResolution.RESOLVED_BY_AUTHORITY, 7_400_000),
    ("company canon two ranks above an email",
     Authority.COMPANY_CANON, Authority.EMAIL_PROSE,
     ConflictResolution.RESOLVED_BY_AUTHORITY, 7_400_000),
    ("an attachment exactly one rank above email prose",
     Authority.ATTACHMENT, Authority.EMAIL_PROSE,
     ConflictResolution.UNRESOLVED_SURFACE_BOTH, None),
    ("a system of record one rank above an attachment",
     Authority.STRUCTURED_SOURCE, Authority.ATTACHMENT,
     ConflictResolution.UNRESOLVED_SURFACE_BOTH, None),
    ("two emails of equal standing",
     Authority.EMAIL_PROSE, Authority.EMAIL_PROSE,
     ConflictResolution.UNRESOLVED_SURFACE_BOTH, None),
)


@pytest.mark.parametrize("left,right,resolution,winner",
                         [pytest.param(*row[1:], id=row[0]) for row in RESOLUTION_ROWS])
def test_authority_resolves_only_when_the_gap_is_at_least_two(left, right, resolution, winner):
    """Doc 05 step 4. One step of authority is not enough to silence the other side — the
    attachment/email pair is exactly where the email often carries the amendment."""
    conflict = only(detect(claim("hi", usd(7_400_000, "$74K"), left, at=EARLIER),
                           claim("lo", usd(8_400_000, "$84K"), right, at=LATER)))
    assert conflict.resolution is resolution
    if winner is None:
        assert conflict.resolved_value is None
    else:
        assert conflict.resolved_value.minor_units == winner


@pytest.mark.parametrize("resolution,claims", [
    pytest.param(ConflictResolution.RESOLVED_BY_AUTHORITY,
                 (SIGNED_74K, EMAIL_84K), id="resolved_by_authority"),
    pytest.param(ConflictResolution.UNRESOLVED_SURFACE_BOTH,
                 (claim("a", usd(7_400_000, "$74K"), Authority.EMAIL_PROSE),
                  claim("b", usd(8_400_000, "$84K"), Authority.EMAIL_PROSE)),
                 id="unresolved_surface_both"),
    pytest.param(ConflictResolution.RESOLVED_BY_RECENCY,
                 (claim("orig", usd(7_400_000, "$74K"), Authority.SIGNED_DOCUMENT, at=EARLIER),
                  claim("amend", usd(8_400_000, "$84K"), Authority.SIGNED_DOCUMENT, at=LATER,
                        supersedes="orig")),
                 id="resolved_by_recency"),
])
def test_every_resolution_mode_retains_both_claims(resolution, claims):
    """The rule the whole module exists for, asserted once per mode it can produce."""
    conflict = only(detect(*claims))
    assert conflict.resolution is resolution
    assert len(conflict.claims) >= 2


def test_an_amendment_supersedes_the_original_within_one_authority_rank():
    """Doc 05: recency is a tie-break ONLY within the same rank, and only on an explicit
    supersession — otherwise the rule reads "the newest thing wins", which is v1."""
    conflict = only(detect(
        claim("orig", usd(7_400_000, "$74K"), Authority.SIGNED_DOCUMENT, at=EARLIER),
        claim("amend", usd(8_400_000, "$84K"), Authority.SIGNED_DOCUMENT, at=LATER,
              supersedes="orig")))
    assert conflict.resolution is ConflictResolution.RESOLVED_BY_RECENCY
    assert conflict.resolved_value.minor_units == 8_400_000


def test_a_newer_claim_that_supersedes_nothing_does_not_win():
    """The same pair without the supersession link stays open. Recency is a tie-break, never
    an argument."""
    conflict = only(detect(
        claim("orig", usd(7_400_000, "$74K"), Authority.SIGNED_DOCUMENT, at=EARLIER),
        claim("newer", usd(8_400_000, "$84K"), Authority.SIGNED_DOCUMENT, at=LATER)))
    assert conflict.resolution is ConflictResolution.UNRESOLVED_SURFACE_BOTH
    assert conflict.resolved_value is None


def test_a_newer_email_never_beats_an_older_signed_document():
    """Rule 5, stated the way it fails in production: the email is both LATER and weaker, and
    it declares that it supersedes the contract. Authority still decides, and it decides
    against the newer thing."""
    conflict = only(detect(
        claim("pdf", usd(7_400_000, "$74K"), Authority.SIGNED_DOCUMENT, at=EARLIER),
        claim("mail", usd(8_400_000, "$84K"), Authority.EMAIL_PROSE, at=LATER,
              supersedes="pdf")))
    assert conflict.resolution is ConflictResolution.RESOLVED_BY_AUTHORITY
    assert conflict.resolved_value.minor_units == 7_400_000


def test_a_draft_and_a_signed_copy_stating_the_same_value_is_not_a_conflict():
    """Doc 05's failure table, row 2. The rank separates them; step 3 means they never get
    that far, because they agree."""
    assert detect(claim("draft", usd(7_400_000, "$74,000"), Authority.ATTACHMENT, at=EARLIER),
                  claim("signed", usd(7_400_000, "$74K"), Authority.SIGNED_DOCUMENT,
                        at=LATER)).conflicts == ()


def test_a_claim_carrying_no_evidence_is_refused_at_construction():
    """The cheapest way to win a conflict would be to assert a value with nothing behind it."""
    with pytest.raises(ValueError, match="no evidence"):
        C.NormalizedClaim(claim_id="x", subject_key=SUBJECT, field="contract.value",
                          value=usd(1, "1c"), authority=Authority.SIGNED_DOCUMENT,
                          evidence=(), asserted_at=NOW, event_id="e")


def test_a_rank_is_read_from_the_authority_table_not_from_the_caller():
    """ALG-14 owns the mapping; a claim cannot arrive carrying a rank nobody assigned."""
    assert claim("x", usd(1, "1c"), Authority.SIGNED_DOCUMENT).authority_rank == 6
    assert claim("x", usd(1, "1c"), Authority.CHAT_ASIDE).authority_rank == 1


def test_detected_at_must_be_supplied_and_timezone_aware():
    """No clock in this package: a replay of March's sync writes March's row."""
    with pytest.raises(ValueError):
        detect(SIGNED_74K, EMAIL_84K, detected_at=datetime(2026, 1, 21, 12, 0))


# ---------------------------------------------------------------------------------------------
# U1 · step 6, the storm cap
# ---------------------------------------------------------------------------------------------

#: Doc 05 files the cap under the failure mode *"Conflict storm on ONE ENTITY"*, and the rule it
#: writes is "cap 20 conflicts per signal". Both halves of that sentence are per subject: the
#: thing that storms is one entity, and the signal a conflict escalates to is about one subject.
#: A cap counted over the whole batch punishes a subject for the noise of its neighbours — which
#: is what these fixtures are shaped to catch. `_storm` therefore builds N conflicts on ONE
#: subject (N distinct fields of it); `_many_subjects` builds one conflict each on N subjects.

def _conflicting_pair(index: int, *, subject: str, field_name: str) -> list[C.NormalizedClaim]:
    return [
        claim(f"a{index}", usd(7_400_000, "$74K"), Authority.EMAIL_PROSE,
              subject=subject, field=field_name, event_id=f"evt_a{index}"),
        claim(f"b{index}", usd(8_400_000, "$84K"), Authority.EMAIL_PROSE,
              subject=subject, field=field_name, event_id=f"evt_b{index}"),
    ]


def _storm(conflicts: int, subject: str = "contract:vendor-noisy") -> C.ConflictDetection:
    """`conflicts` disagreements about ONE subject — a broken source, which is one fact."""
    claims: list[C.NormalizedClaim] = []
    for index in range(conflicts):
        claims.extend(_conflicting_pair(index, subject=subject,
                                        field_name=f"policy.term_{index:02d}"))
    return C.detect_conflicts(claims, detected_at=DETECTED)


def _many_subjects(subjects: int) -> C.ConflictDetection:
    """One honest disagreement each on `subjects` different subjects — N real cards."""
    claims: list[C.NormalizedClaim] = []
    for index in range(subjects):
        claims.extend(_conflicting_pair(index, subject=f"contract:vendor-{index:02d}",
                                        field_name="contract.value"))
    return C.detect_conflicts(claims, detected_at=DETECTED)


def test_twenty_five_conflicts_on_one_subject_are_capped_at_twenty_and_reported_as_a_storm():
    detection = _storm(25)
    assert len(detection.conflicts) == C.MAX_CONFLICTS_PER_SIGNAL == 20
    assert detection.total_detected == 25
    assert detection.truncated is True
    escalations = C.escalate_conflicts(detection)
    assert len(escalations) == 1, "a storm must not become twenty signals"
    assert escalations[0].storm is True
    assert escalations[0].signal_type is SignalType.INFORMATION_CONFLICT
    assert escalations[0].subject_key == "contract:vendor-noisy"


def test_exactly_twenty_conflicts_on_one_subject_is_not_a_storm():
    """The boundary, because an off-by-one here silently swallows nineteen real cards."""
    detection = _storm(20)
    assert len(detection.conflicts) == 20
    assert detection.truncated is False
    assert all(not e.storm for e in C.escalate_conflicts(detection))


def test_the_capped_twenty_are_the_same_twenty_every_run():
    kept = [item.conflict.field for item in _storm(25).conflicts]
    assert kept == sorted(kept), "which conflicts survive the cap must not be dict order"
    assert kept == [item.conflict.field for item in _storm(25).conflicts]


# --- D4 · the cap and the storm guard are PER SUBJECT ---------------------------------------

def test_twenty_five_quiet_subjects_are_twenty_five_cards_not_a_storm():
    """D4. Twenty-five vendors each disagreeing once is twenty-five pieces of intelligence.

    Counted globally the cap deletes five of them outright and relabels the surviving twenty as
    one storm about `vendor-00` — a headline that is false about twenty-four subjects and a
    silent loss of the other five. Nothing about vendor-07 got noisier because vendor-11 exists.
    """
    detection = _many_subjects(25)
    assert len(detection.conflicts) == 25, (
        "one subject's conflicts were dropped to pay for another subject's — the cap is global")
    assert detection.truncated is False
    escalations = C.escalate_conflicts(detection)
    assert len(escalations) == 25, "a quiet subject lost its own signal to a global storm guard"
    assert {e.subject_key for e in escalations} == {f"contract:vendor-{i:02d}"
                                                   for i in range(25)}
    assert not any(e.storm for e in escalations)


def test_one_storming_subject_does_not_silence_the_quiet_subject_beside_it():
    """D4, the mixed batch — the shape a real sweep produces.

    A vendor with a broken export storms; the deal that disagrees about its amount once does not.
    Globally capped, the storm eats all twenty slots, the honest conflict never lands, and the
    ONE escalation the founder receives is about the broken exporter.
    """
    claims: list[C.NormalizedClaim] = []
    for index in range(25):
        claims.extend(_conflicting_pair(index, subject="contract:vendor-noisy",
                                        field_name=f"policy.term_{index:02d}"))
    claims.extend(_conflicting_pair(99, subject="contract:acme-msa",
                                    field_name="contract.value"))
    detection = C.detect_conflicts(claims, detected_at=DETECTED)

    quiet = [item for item in detection.conflicts if item.subject_key == "contract:acme-msa"]
    assert len(quiet) == 1, (
        "the quiet subject's only conflict was crowded out by a neighbour's storm")
    assert len([item for item in detection.conflicts
                if item.subject_key == "contract:vendor-noisy"]) == 20

    escalations = C.escalate_conflicts(detection)
    storms = [e for e in escalations if e.storm]
    normal = [e for e in escalations if not e.storm]
    assert len(storms) == 1 and storms[0].subject_key == "contract:vendor-noisy"
    assert [e.subject_key for e in normal] == ["contract:acme-msa"], (
        "the quiet subject's INFORMATION_CONFLICT was dropped by a storm it had no part in")


def test_a_storm_headline_counts_only_its_own_subject():
    """The number on the card must be that subject's, not the batch's."""
    claims: list[C.NormalizedClaim] = []
    for index in range(22):
        claims.extend(_conflicting_pair(index, subject="contract:vendor-noisy",
                                        field_name=f"policy.term_{index:02d}"))
    for index in range(30, 35):
        claims.extend(_conflicting_pair(index, subject=f"contract:vendor-{index:02d}",
                                        field_name="contract.value"))
    storm, = [e for e in C.escalate_conflicts(
        C.detect_conflicts(claims, detected_at=DETECTED)) if e.storm]
    assert "22" in storm.headline and "27" not in storm.headline


def test_twenty_five_claims_about_ONE_field_are_one_conflict_holding_all_of_them():
    """A storm of claims is not a storm of conflicts — and none of the 25 is dropped."""
    claims = [claim(f"c{i}", usd(7_400_000 + i * 100_000, f"${74 + i}K"),
                    Authority.EMAIL_PROSE, event_id=f"evt_{i}") for i in range(25)]
    detection = C.detect_conflicts(claims, detected_at=DETECTED)
    conflict = only(detection)
    assert detection.truncated is False
    assert len(conflict.claims) == 25


# ---------------------------------------------------------------------------------------------
# D3 · a receipt ALG-08 could not verify is not a side of a disagreement
# ---------------------------------------------------------------------------------------------
#
# `spans.verify_span` grades every receipt and is the ONLY thing in the system allowed to stamp
# `EvidenceSpan.verified`. Four of its six verdicts are literal matches and stamp True; UNVERIFIED
# ("the model invented the sentence it claims to cite") and INVALID_BOUNDS ("the offsets could not
# describe a region of this text") force it back to False.
#
# A conflict card is the one surface that asks a human to ADJUDICATE between two sources, quoting
# each verbatim. Standing an unverified span up as one of those two sides means printing a
# sentence nothing in the source contains, over a real quote, and asking the founder to weigh
# them — the exact "confidently wrong with a receipt that looks legitimate" failure this whole
# module exists to end, committed by the module itself.

UNVERIFIABLE = C.NormalizedClaim(
    claim_id="c_hallucinated", subject_key=SUBJECT, field="contract.value",
    value=usd(9_400_000, "$94,000"), authority=Authority.EMAIL_PROSE,
    evidence=(span("the $94,000 renewal figure", "email:thread-8f2a", verified=False),),
    asserted_at=LATER, event_id="evt_hallucinated")


@pytest.mark.gate
def test_a_claim_whose_receipt_never_verified_is_not_a_side_of_a_disagreement():
    """D3. An unverified quote cannot contradict a verified one."""
    assert detect(SIGNED_74K, UNVERIFIABLE).conflicts == (), (
        "a sentence ALG-08 could not find in the source was stood up against a signed document")


def test_two_unverified_claims_do_not_manufacture_a_conflict_between_themselves():
    other = C.NormalizedClaim(
        claim_id="c_hallucinated_2", subject_key=SUBJECT, field="contract.value",
        value=usd(6_400_000, "$64,000"), authority=Authority.EMAIL_PROSE,
        evidence=(span("the $64,000 figure", "email:thread-8f2a", verified=False),),
        asserted_at=NOW, event_id="evt_hallucinated_2")
    assert detect(UNVERIFIABLE, other).conflicts == ()


def test_an_unverified_claim_does_not_silence_the_conflict_the_other_two_have():
    """Refusal is scoped to the bad claim. The disagreement between the two real receipts is
    still a disagreement, and the founder must still see it."""
    conflict = only(detect(SIGNED_74K, EMAIL_84K, UNVERIFIABLE))
    values = sorted(c.value.minor_units for c in conflict.claims)
    assert values == [7_400_000, 8_400_000]
    assert 9_400_000 not in {c.value.minor_units for c in conflict.claims}


def test_a_claim_keeps_its_verified_receipts_and_sheds_the_invented_one():
    """A real quote stapled beside a fabricated one is the cheapest way to launder a fabrication
    past the unit built to catch it — `spans._UNVERIFIED_FACTOR` prices exactly that move. The
    claim stands on its verified receipt; the invention does not travel onto the card."""
    mixed = C.NormalizedClaim(
        claim_id="c_mixed", subject_key=SUBJECT, field="contract.value",
        value=usd(8_400_000, "$84K"), authority=Authority.EMAIL_PROSE,
        evidence=(span("the $84K annual contract", "email:thread-8f2a"),
                  span("and the board already approved it", "email:thread-8f2a",
                       verified=False)),
        asserted_at=LATER, event_id="evt_mixed")
    conflict = only(detect(SIGNED_74K, mixed))
    survivor, = [c for c in conflict.claims if c.value.minor_units == 8_400_000]
    assert [e.quote for e in survivor.evidence] == ["the $84K annual contract"]

    quotes = {line.quote for line in C.render_conflict_card(conflict).lines}
    assert "and the board already approved it" not in quotes, (
        "the card quoted a sentence ALG-08 could not find in the source")


def test_the_pure_unit_refuses_unverified_evidence_without_reading_the_flag_off_the_claim():
    """The refusal is not a property a caller can set: `NormalizedClaim` still ACCEPTS the claim
    (L1 deletes nothing), and it is `detect_conflicts` that declines to weigh it."""
    assert UNVERIFIABLE.evidence[0].verified is False
    assert UNVERIFIABLE.authority_rank == C.rank_of(Authority.EMAIL_PROSE)


def _extraction(*evidence: EvidenceSpan, amount: Money) -> ExtractionResult:
    return ExtractionResult(intent="inform", stance="neutral", amounts=[amount],
                            all_evidence=list(evidence), model_snapshot="fake-model-1",
                            prompt_version="v1", schema_version="v1",
                            extraction_profile="test", input_tokens=1, output_tokens=1)


class _Prepared:
    def __init__(self, text: str) -> None:
        self.clean_text = text
        self.prepared_content_id = "pc_test"


def test_the_production_receipt_finder_refuses_a_span_alg08_cannot_find_in_the_text():
    """D3 at the seam that BUILDS the claims — `_receipts_for`, the one place a conflict's
    receipt comes from on the live path.

    The extraction offers a span that quotes the amount inside a sentence the source does not
    contain — a real number wrapped in invented words, which is what a fabricated citation
    actually looks like. Taking the extractor's word for it (its `verified` flag is False, and
    `semantic/evidence_binder.py:414` forces it False on EVERYTHING) would put that sentence on
    a card verbatim. Every candidate goes to `spans.verify_span` and only what comes back
    stamped is kept, so the fabricated wrapper is dropped and the receipt is the real position
    of the number in the prepared text.
    """
    text = "As discussed the annual figure with Acme Corp is $84,000 for year one."
    fabricated = EvidenceSpan(source_ref="prepared_content:pc_test",
                              quote="the $84,000 the board already approved",
                              start_offset=0, end_offset=38, verified=False)
    amount = usd(8_400_000, "$84,000")

    receipts = C._receipts_for(amount, _extraction(fabricated, amount=amount),
                               _Prepared(text))

    assert receipts, "the amount is in the text; a real receipt exists and must be found"
    assert all(span.verified for span in receipts), (
        "an unstamped span left the receipt finder — ALG-08 is the only thing entitled to "
        "stamp one, and D3 admits nothing else as a side of a disagreement")
    assert [span.quote for span in receipts] == ["$84,000"]
    assert text[receipts[0].start_offset:receipts[0].end_offset] == "$84,000"


def test_the_production_receipt_finder_keeps_a_span_alg08_can_relocate():
    """The other side of the same rule: real words measured in the wrong place are a real
    citation with a bad ruler, and ALG-08 grades them VERIFIED_RELOCATED. Refusing those would
    throw away most honest receipts an extractor produces."""
    text = "Header line. As discussed the annual figure is $84,000 for year one."
    misplaced = EvidenceSpan(source_ref="prepared_content:pc_test",
                             quote="the annual figure is $84,000",
                             start_offset=0, end_offset=28, verified=False)
    amount = usd(8_400_000, "$84,000")

    receipts = C._receipts_for(amount, _extraction(misplaced, amount=amount), _Prepared(text))

    assert [span.quote for span in receipts] == ["the annual figure is $84,000"]
    assert receipts[0].verified is True
    assert text[receipts[0].start_offset:receipts[0].end_offset] == \
        "the annual figure is $84,000", "the offsets were not corrected to where it really is"


# ---------------------------------------------------------------------------------------------
# U2 · escalation
# ---------------------------------------------------------------------------------------------

MATERIAL_ROWS = (
    ("contract.value", True),
    ("contract.renewal_date", True),
    ("contract.notice_period", True),
    ("deal.amount", True),
    ("policy.refund_window", True),
    ("policy.notice", True),
    ("meeting.location", False),
    ("contract.counterparty_nickname", False),
)


@pytest.mark.parametrize("field_name,material",
                         [pytest.param(*row, id=row[0]) for row in MATERIAL_ROWS])
def test_only_a_material_field_becomes_a_signal(field_name, material):
    """"Your systems disagree about the refund window" is intelligence. "They disagree about a
    nickname" is noise, and shipping both teaches the founder to ignore the first."""
    detection = detect(claim("a", usd(7_400_000, "$74K"), Authority.EMAIL_PROSE,
                             field=field_name),
                       claim("b", usd(8_400_000, "$84K"), Authority.EMAIL_PROSE,
                             field=field_name))
    assert C.is_material_field(field_name) is material
    escalations = C.escalate_conflicts(detection)
    assert bool(escalations) is material


def test_an_escalation_names_the_signal_type_the_subject_and_both_values():
    escalation, = C.escalate_conflicts(detect(EMAIL_84K, SIGNED_74K))
    assert escalation.signal_type is SignalType.INFORMATION_CONFLICT
    assert escalation.subject_key == SUBJECT
    assert escalation.field == "contract.value"
    assert "$74,000" in escalation.headline and "$84K" in escalation.headline
    assert len(escalation.conflicts) == 1
    assert len(escalation.conflicts[0].claims) == 2, "the escalation dropped a side"


def test_no_conflict_means_no_escalation():
    assert C.escalate_conflicts(detect(SIGNED_74K)) == ()


# ---------------------------------------------------------------------------------------------
# U3 · the card contract
# ---------------------------------------------------------------------------------------------

def test_the_card_shows_both_values_both_authorities_and_both_quotes():
    card = C.render_conflict_card(only(detect(EMAIL_84K, SIGNED_74K)))
    assert len(card.lines) == 2
    signed, email = card.lines
    assert (signed.authority_label, signed.value_text) == ("Signed document", "$74,000")
    assert signed.quote == "total annual commitment of $74,000"
    assert signed.source_ref == "chunk:aws_agreement.pdf:42"
    assert (email.authority_label, email.value_text) == ("An email", "$84K")
    assert email.quote == "the $84K annual contract"
    assert email.source_ref == "email:thread-8f2a"

    rendered = card.render()
    assert "$74,000" in rendered and "$84K" in rendered
    assert card.verdict is not None and "higher authority" in card.verdict
    assert rendered.endswith("Conflict detected. " + card.verdict)


def test_an_unresolved_card_makes_no_recommendation():
    """Doc 05: no recommendation about which is right unless `resolved_by_authority`."""
    card = C.render_conflict_card(only(detect(
        claim("a", usd(7_400_000, "$74K"), Authority.EMAIL_PROSE),
        claim("b", usd(8_400_000, "$84K"), Authority.EMAIL_PROSE))))
    assert card.resolution is ConflictResolution.UNRESOLVED_SURFACE_BOTH
    assert card.verdict is None
    assert card.render().endswith("Conflict detected.")
    assert len(card.lines) == 2


def test_a_recency_resolution_states_the_rule_but_recommends_nothing():
    """An amendment superseding an original is a fact about documents, not a ruling about who
    to believe — so the card carries the resolution and still no verdict line."""
    card = C.render_conflict_card(only(detect(
        claim("orig", usd(7_400_000, "$74K"), Authority.SIGNED_DOCUMENT, at=EARLIER),
        claim("amend", usd(8_400_000, "$84K"), Authority.SIGNED_DOCUMENT, at=LATER,
              supersedes="orig"))))
    assert card.resolution is ConflictResolution.RESOLVED_BY_RECENCY
    assert card.verdict is None


def test_a_date_card_quotes_the_source_words_rather_than_reformatting_them():
    """Re-rendering one side's words quietly edits the argument the founder is adjudicating."""
    card = C.render_conflict_card(only(detect(
        claim("a", day("Oct 15", datetime(2026, 10, 15, tzinfo=timezone.utc)),
              Authority.EMAIL_PROSE, field="contract.renewal_date"),
        claim("b", day("Nov 15", datetime(2026, 11, 15, tzinfo=timezone.utc)),
              Authority.EMAIL_PROSE, field="contract.renewal_date"))))
    assert {line.value_text for line in card.lines} == {"Oct 15", "Nov 15"}


# ---------------------------------------------------------------------------------------------
# the wiring · driven through capture_event, twice, as two real events
# ---------------------------------------------------------------------------------------------

class _AmountGrouper:
    """The L1.5.0 (ALG-23) seam, standing in until that unit lands.

    It does the one thing this module refuses to do for itself: decide that the PDF attached to
    a message and the message body are talking about the same contract. The subject key is the
    message the attachment hangs off — `parent_object_id`, exactly the link the Gmail connector
    writes (`connectors/composio.py:562`). Authority comes from the REAL ALG-14 cascade, and
    `executed` is established by the caller (a signature block, a DocuSign envelope), never
    guessed here.
    """

    def __init__(self, executed: frozenset[str] = frozenset()):
        self.executed = executed

    def claims_for(self, event, extraction) -> list[C.NormalizedClaim]:
        weight = weigh_authority(Provenance(
            source=event.source, object_type=event.object_type,
            executed=event.source_object_id in self.executed))
        subject = "contract:" + (event.parent_object_id or event.source_object_id)
        evidence = tuple(extraction.all_evidence) or (
            span("stated amount", f"event:{event.event_id}"),)
        return [C.NormalizedClaim(
            claim_id=f"{event.source_object_id}:{index}", subject_key=subject,
            field="contract.value", value=amount, authority=weight.authority,
            evidence=evidence, asserted_at=event.occurred_at, event_id=event.event_id)
            for index, amount in enumerate(extraction.amounts)]


def _answer(minor_units: int, as_written: str) -> dict:
    return {"intent": "inform", "stance": "neutral",
            "amounts": [{"minor_units": minor_units, "currency": "USD",
                         "as_written": as_written}]}


def _message() -> RawObject:
    return RawObject(source="gmail", object_type="email_message", source_object_id="m1",
                     occurred_at=LATER, actor_email="buyer@acme.com", recipients=(OWNER,),
                     raw={"subject": "Contract", "body": "Confirming the $84K annual contract."})


def _attachment() -> RawObject:
    """A separate event, linked to the message — connectors/composio.py:562."""
    return RawObject(source="gmail", object_type="email_attachment",
                     source_object_id="att1", parent_object_id="m1",
                     occurred_at=EARLIER, actor_email="buyer@acme.com", recipients=(OWNER,),
                     raw={"subject": "aws_agreement.pdf",
                          "body": "The total annual commitment of $74,000 is due on signature."})


@pytest.mark.gate
def test_the_pipeline_detects_the_conflict_across_two_separate_events(fake_llm):
    """The wiring, driven through the real entry point: two `capture_event` calls, an email and
    its signed attachment, and the conflict falls out of the second one."""
    llm = fake_llm(_answer(8_400_000, "$84K"), _answer(7_400_000, "$74,000"))
    repo = InMemorySourceEventRepository()
    lane = C.ConflictLane(grouper=_AmountGrouper(executed=frozenset({"att1"})),
                          detected_at=DETECTED)

    def capture(raw):
        return P.capture_event(raw, org_id="org_c", connection_id="con_c", repo=repo,
                               mailbox_owner=OWNER,
                               semantic=P.SemanticLane(llm=llm, eval_time=NOW),
                               conflict_lane=lane)

    first = capture(_message())
    assert first.outcome == "emitted" and first.extraction is not None
    assert first.conflicts is not None and first.conflicts.conflicts == (), (
        "one event cannot contradict itself here — there is nothing to compare it to yet")

    second = capture(_attachment())
    assert second.outcome == "emitted"
    assert second.conflicts is not None
    detected, = second.conflicts.conflicts
    assert detected.conflict.resolution is ConflictResolution.RESOLVED_BY_AUTHORITY
    assert detected.conflict.resolved_value.minor_units == 7_400_000
    assert len(detected.conflict.claims) == 2
    assert len(detected.event_ids) == 2, "the two claims must come from two events"
    assert detected.subject_key == "contract:m1"

    escalation, = second.conflicts.escalations
    assert escalation.signal_type is SignalType.INFORMATION_CONFLICT
    assert [r.stage for r in second.trace.records].count("conflict") == 1


def test_no_lane_means_no_conflict_detection_at_all(fake_llm):
    """Wiring a seam must not activate it: a caller with no lane gets the old behaviour."""
    res = P.capture_event(_message(), org_id="org_c", connection_id="con_c",
                          repo=InMemorySourceEventRepository(), mailbox_owner=OWNER,
                          semantic=P.SemanticLane(llm=fake_llm(_answer(8_400_000, "$84K")),
                                                  eval_time=NOW))
    assert res.outcome == "emitted"
    assert res.conflicts is None
    assert "conflict" not in [r.stage for r in res.trace.records]


def test_a_redelivered_event_does_not_fabricate_a_conflict_with_itself(fake_llm):
    """Landing dedups a redelivery inside one sweep, so this is the case landing cannot catch:
    the SAME source object re-extracted through the same lane in a second sweep (a recovered
    park, a backfill overlapping an incremental). The second reading even differs — a re-run at
    a different tier read "$74,000" where the first read "$84K" — and that is still ONE source,
    not two sources disagreeing. Without the lane's guard, a message contradicts itself and the
    founder gets a card about a dispute nobody had."""
    llm = fake_llm(_answer(8_400_000, "$84K"), _answer(7_400_000, "$74,000"))
    lane = C.ConflictLane(grouper=_AmountGrouper(), detected_at=DETECTED)
    for _ in range(2):
        result = P.capture_event(_message(), org_id="org_c", connection_id="con_c",
                                 repo=InMemorySourceEventRepository(),
                                 mailbox_owner=OWNER,
                                 semantic=P.SemanticLane(llm=llm, eval_time=NOW),
                                 conflict_lane=lane)
    assert result.conflicts is not None
    assert result.conflicts.conflicts == ()


# =============================================================================================
# WIRED · driven through run_sync — no test-supplied grouper anywhere below this line
# =============================================================================================
#
# Everything above proves the UNIT. `_AmountGrouper` is a fixture: it decides that the PDF and
# the mail are about the same contract, which is the hardest half of the problem, and a seam
# that only closes when a test supplies that half is not wired. This section drives `run_sync`
# — the function EVERY polling path in the product goes through — over a real connector page,
# the real gate, the real extractor, the real ALG-23 assembler and the real ALG-14 cascade, and
# asserts the conflict falls out the other end.

RUN_ORG = "org_wired"
RUN_CONN = "con_wired"
RUN_MESSAGE = "msg_wired_1"
RUN_ATTACHMENT = "att_wired_1"
RUN_THREAD = "thr_wired_1"

RUN_BODY = ("Attaching the signed MSA. As discussed the annual figure with Acme Corp "
            "is $84,000 for year one.")
RUN_PDF = ("MASTER SERVICES AGREEMENT between Acme Corp and GeniOS. "
           "Total annual fee: $74,000, payable quarterly.")


def _run_cite(text: str, quote: str) -> list[dict]:
    start = text.index(quote)
    return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]


class _ContentKeyedLLM:
    """Answers from the CONTENT it was shown, never from call order.

    `run_sync` captures a page through a thread pool, so the mail and its attachment race; an
    order-keyed fixture would be flaky in exactly the way this unit must not be.
    """

    model = "fake-model-1"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def call(self, prompt: str, *, max_tokens: int = 4096):
        import json as _json
        from dataclasses import dataclass

        @dataclass
        class _Result:
            parsed: dict
            raw: str
            input_tokens: int = 100
            output_tokens: int = 50
            model: str = "fake-model-1"
            cached: bool = False
            ok: bool = True
            error: str | None = None

        self.calls.append(prompt)
        if "74,000" in prompt:
            text, minor, written = RUN_PDF, 7_400_000, "$74,000"
        else:
            text, minor, written = RUN_BODY, 8_400_000, "$84,000"
        payload = {
            "intent": "inform", "stance": "neutral",
            "entity_mentions": [{"surface_form": "Acme Corp", "entity_type": "organization",
                                 "evidence": _run_cite(text, "Acme Corp"),
                                 "confidence_bp": 9000}],
            "amounts": [{"minor_units": minor, "currency": "USD", "as_written": written}],
        }
        return _Result(parsed=payload, raw=_json.dumps(payload, sort_keys=True))


class _MailboxWithASignedAttachment:
    """One Gmail message -> two RawObjects, exactly as composio.py:512/:559 emits them.

    `suffix` keeps each test's source object ids its own. Landing dedups on `(org, dedup_key)`
    and that key is derived from the source's ids, so two tests sharing them would depend on
    which ran first — the kind of coupling that makes a wired test flaky for a reason that has
    nothing to do with what it asserts.
    """

    source = "gmail"

    def __init__(self, suffix: str = "") -> None:
        self.suffix = suffix

    def validate_connection(self) -> bool:
        return True

    def _objects(self) -> list[RawObject]:
        message, attachment = RUN_MESSAGE + self.suffix, RUN_ATTACHMENT + self.suffix
        return [
            RawObject(source="gmail", object_type="email_message",
                      source_object_id=message, occurred_at=LATER,
                      actor_email="buyer@acme.com", recipients=(OWNER,),
                      parent_object_id=RUN_THREAD + self.suffix,
                      raw={"subject": "Signed MSA", "body": RUN_BODY}),
            RawObject(source="gmail", object_type="email_attachment",
                      source_object_id=attachment, occurred_at=EARLIER,
                      actor_email="buyer@acme.com", recipients=(OWNER,),
                      parent_object_id=message,
                      raw={"subject": "MSA_signed_v2.pdf", "body": RUN_PDF,
                           "has_attachment": True}),
        ]

    def initial_snapshot(self, cursor=None, limit=50) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)

    def incremental_changes(self, cursor=None, limit=50, since=None) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)


@pytest.mark.gate
def test_run_sync_detects_the_conflict_across_the_two_events_it_just_captured():
    """The production caller. Without this the detector is a library nothing on a request path
    reaches — and the $84,000 the founder is shown never mentions the $74,000 that contradicts
    it.

    NO grouper is supplied here. `run_sync` builds one out of ALG-23's assembled groups, which
    is the only thing that puts the attachment's amount and the mail's amount into one
    comparison: the PDF keys on its document identity and the mail keys on the organisation it
    names, so the per-claim subjects never match.
    """
    llm = _ContentKeyedLLM()
    summary = run_sync(_MailboxWithASignedAttachment(), org_id=RUN_ORG, connection_id=RUN_CONN,
                       repo=InMemorySourceEventRepository(), mode="backfill",
                       mailbox_owner=OWNER, source="gmail",
                       semantic=P.SemanticLane(llm=llm, eval_time=NOW))

    assert summary.scanned == 2 and llm.calls, "the page never reached the extractor"
    assert summary.conflicts is not None, (
        "run_sync captured two events that disagree and published no conflict detection at all "
        "— the ALG-12 seam is not on the live path")

    detected, = summary.conflicts.conflicts
    values = sorted(c.value.minor_units for c in detected.conflict.claims)
    assert values == [7_400_000, 8_400_000], (
        "the conflict does not hold BOTH amounts; the losing claim is never deleted")
    assert len(detected.event_ids) == 2, (
        "both sides came from one event — grouping by event misses the headline case entirely")
    assert detected.conflict.resolution is ConflictResolution.UNRESOLVED_SURFACE_BOTH, (
        "nothing in L1 establishes that a PDF is executed, so ATTACHMENT(3) vs EMAIL_PROSE(2) "
        "is a one-rank gap, which doc 05 refuses to auto-resolve")

    # D3, on the live path: the card's quotes are receipts ALG-08 graded, not offsets this
    # module asserted for itself. If the seam ever goes back to stamping its own spans, the
    # detector keeps working and the founder silently starts adjudicating unchecked citations.
    receipts = [e for c in detected.conflict.claims for e in c.evidence]
    assert receipts and all(e.verified for e in receipts), (
        "a conflict reached the card carrying a receipt ALG-08 never verified")
    assert {e.quote for e in receipts} == {"$84,000", "$74,000"}
    assert detected.conflict.claims[0].evidence[0].source_ref.startswith("prepared_content:")

    tally, = summary.conflicts.detection.subjects
    assert tally.detected == 1 and tally.kept == 1 and tally.truncated is False


@pytest.mark.gate
def test_run_sync_drops_a_claim_whose_amount_is_nowhere_in_the_source():
    """D3 through the real entry point.

    The model returns an amount whose `as_written` appears in NO source text — the shape a
    hallucinated figure takes. There is no span quoting it and no position to locate it at, so
    ALG-08 can grade nothing, and it must not become one side of a disagreement with the signed
    PDF's $74,000. What the founder must never see is a card weighing a real quote against a
    number the source does not contain.
    """
    class _Hallucinating(_ContentKeyedLLM):
        def call(self, prompt: str, *, max_tokens: int = 4096):
            result = super().call(prompt, max_tokens=max_tokens)
            if "74,000" not in prompt:
                result.parsed["amounts"] = [{"minor_units": 9_400_000, "currency": "USD",
                                             "as_written": "$94,000"}]
            return result

    summary = run_sync(_MailboxWithASignedAttachment("_d3"), org_id=RUN_ORG,
                       connection_id=RUN_CONN, repo=InMemorySourceEventRepository(),
                       mode="backfill", mailbox_owner=OWNER, source="gmail",
                       semantic=P.SemanticLane(llm=_Hallucinating(), eval_time=NOW))

    assert summary.scanned == 2
    assert summary.conflicts is not None
    assert summary.conflicts.conflicts == (), (
        "an amount that appears nowhere in the source was stood up against a signed document")


@pytest.mark.gate
def test_run_sync_with_no_extraction_publishes_no_conflicts():
    """No semantic lane wired -> nothing to compare -> None, never a crash at the seam."""
    summary = run_sync(_MailboxWithASignedAttachment("_noextract"), org_id=RUN_ORG,
                       connection_id=RUN_CONN, repo=InMemorySourceEventRepository(),
                       mode="backfill", mailbox_owner=OWNER, source="gmail")
    assert summary.conflicts is None
