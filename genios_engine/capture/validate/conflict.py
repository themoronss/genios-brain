"""ALG-12 · L1.5.5 — the conflict detector. The unit that makes GeniOS trustworthy rather
than merely confident.

The worked fault: a signed PDF states an annual commitment of \\$74,000; an email in the same
thread says "the \\$84K annual contract". v1 wrote whichever landed last and told the founder one
number with no indication the other existed — confidently wrong with a receipt that looks
legitimate, which is the failure mode that ends trust permanently.

So this module never picks a winner quietly. Three units live here:

* **U1 ``detect_conflicts``** — group claims across EVENTS by (subject, field), compare them
  AFTER normalization, and emit a ``Conflict`` that RETAINS EVERY COMPETING CLAIM, in every
  resolution mode. A resolution is a recommendation with its reasoning attached, never a
  deletion.
* **U2 ``escalate_conflicts``** — a conflict on a material field is itself intelligence, and
  becomes a ``SignalType.INFORMATION_CONFLICT``. "Your systems disagree about the refund
  window" is often worth more than either value.
* **U3 ``render_conflict_card``** — what a human sees: both values, both authorities, both
  verbatim quotes, and NO recommendation unless authority actually settled it.

``ConflictLane`` is the production seam: it accumulates claims across the events of one sync
run (an email and its attachment are two separate events — ``connectors/composio.py:562``
gives the attachment ``parent_object_id`` = the message id) and runs U1+U2 as each event lands.
``capture/pipeline.py`` calls it; a caller that passes no lane behaves exactly as before.

Three boundaries this module does NOT cross:

* **It does not decide which claims are about the same thing.** That is L1.5.0 (ALG-23, claim
  groups), which owns ``subject_key``. This module consumes a ``ClaimGrouper`` — see the
  protocol below and the GAP FLAG on it, because L1.5.0 does not exist yet.
* **It does not own the authority table.** ``authority.rank_of`` (ALG-14) is read for every
  claim, once, at detection time, and the integer is copied onto the ``ConflictClaim`` so a
  stored conflict keeps explaining the resolution it actually made after the table is re-tuned.
* **It does not write to the database.** ``capture/validate/`` is pure: no clock (``detected_at``
  is a parameter), no float (integer ranks only), no model, no I/O. The ``signal_conflicts``
  persistence named in doc 05 belongs at the storage seam, not here.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
from typing import Protocol, runtime_checkable

from genios_engine.contracts.conflict import (Authority, ClaimValue, Conflict, ConflictClaim,
                                              ConflictResolution, require_no_float)
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import ExtractionResult
from genios_engine.contracts.signal import SignalType
from genios_engine.contracts.units import UNKNOWN_CURRENCY, Money, ResolvedDate
from genios_engine.contracts.validators import require_aware
from genios_engine.capture.validate.authority import Provenance, rank_of, weigh_authority
from genios_engine.capture.validate.claim_group import (FieldFamily, SubjectTier,
                                                        claims_from_extraction)
from genios_engine.capture.validate.spans import verify_span

#: Doc 05's storm cap. Twenty disagreements about one subject is not twenty pieces of
#: intelligence — it is one piece of intelligence about a broken source, and rendering all of
#: them buries the twenty-first thing the founder actually needed to read.
MAX_CONFLICTS_PER_SIGNAL = 20

#: U2's material fields — a conflict here is worth a signal of its own. Exact names first,
#: then prefixes: doc 05 writes `policy.*`, meaning every field of a stated policy.
MATERIAL_FIELDS = frozenset({
    "contract.value",
    "contract.renewal_date",
    "contract.notice_period",
    "deal.amount",
})
MATERIAL_FIELD_PREFIXES = ("policy.",)

#: The field name the storm escalation is filed under. A real field path would be a lie — the
#: storm is about the subject, not about one of its fields.
STORM_FIELD = "information_conflict.storm"

#: How an ``Authority`` reads on a card. Card copy, not doctrine: the ranking stays in ALG-14
#: and this table can be reworded without touching a single resolution.
AUTHORITY_LABEL: dict[Authority, str] = {
    Authority.SIGNED_DOCUMENT: "Signed document",
    Authority.COMPANY_CANON: "Company policy",
    Authority.STRUCTURED_SOURCE: "System of record",
    Authority.ATTACHMENT: "An attached document",
    Authority.EMAIL_PROSE: "An email",
    Authority.CHAT_ASIDE: "A chat message",
    Authority.INFERRED: "An unattributed source",
}


# ---------------------------------------------------------------------------------------------
# the input seam
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class NormalizedClaim:
    """One source asserting one value for one field of one subject — ALG-12's input row.

    GAP FLAG — this type is the seam to **L1.5.0 (claim groups, ALG-23)**, which is being built
    alongside this file and does not exist yet. L1.5.0 owns ``subject_key``: deciding that the
    PDF attached to a message and the message body are talking about the same contract is
    grouping work, and grouping by event would miss the headline case entirely (the two amounts
    live in two different events). When L1.5.0 lands, its claim row either becomes this type or
    is adapted onto it at one call site — ``ClaimGrouper`` below.

    ``authority_rank`` is NOT a field. It is read from ALG-14 through ``rank_of`` at detection
    time, so a caller cannot hand a claim a rank the authority table never assigned — and 7,500
    basis points pasted into a rank field is a 7,498-rank gap that resolves every conflict it
    touches in favour of whichever side leaked a score.
    """

    #: Stable within a detection run. Referenced by ``supersedes`` and used as the last
    #: tie-break in every ordering here, so the same input always produces the same output.
    claim_id: str
    #: L1.5.0's grouping key — "contract:aws-enterprise-agreement". Opaque to this module.
    subject_key: str
    #: The dotted field path — "contract.value". Written into ``Conflict.field``.
    field: str
    #: Already normalized: a ``Money`` (integer minor units), a ``ResolvedDate`` (a window), or a
    #: string / int. Comparison happens after normalization — "$84K" and "USD 84,000" are one
    #: amount written twice, and comparing raw strings reports a disagreement between two
    #: sources that agree.
    value: ClaimValue
    #: The provenance class, from ALG-14's cascade (``weigh_authority``).
    authority: Authority
    #: The receipt. Non-empty is enforced: a claim with no evidence is a guess, and a guess must
    #: not be weighed against a document.
    evidence: tuple[EvidenceSpan, ...]
    #: When the SOURCE asserted it — the event's ``occurred_at``, never a clock read. Recency is
    #: a tie-break within one authority rank and nothing else, so this must be the source's own
    #: time: a re-sync that stamped "now" would let a replay reorder history.
    asserted_at: datetime
    #: Which event carried it. Kept so a conflict can be shown to span two events, which is the
    #: property the headline fixture exists to prove.
    event_id: str
    #: The ``claim_id`` this claim explicitly supersedes — an amendment naming the original.
    #: Required for a recency resolution, and deliberately so: without an explicit supersession
    #: a newer value is just a newer value, and "the last email wins" is exactly the v1 behaviour
    #: this module was written to end.
    supersedes: str | None = None

    def __post_init__(self) -> None:
        if not self.claim_id or not self.subject_key or not self.field:
            raise ValueError("a claim needs a claim_id, a subject_key and a field")
        if not self.evidence:
            raise ValueError(
                f"claim {self.claim_id!r} has no evidence — a claim with no receipt is a guess, "
                "and a guess must not be weighed against a document")
        require_no_float(self.value, f"NormalizedClaim({self.claim_id}).value")
        require_aware(self.asserted_at, "asserted_at")

    @property
    def authority_rank(self) -> int:
        """ALG-14's rank for this claim's provenance class. One table, read here."""
        return rank_of(self.authority)

    @property
    def verified_evidence(self) -> tuple[EvidenceSpan, ...]:
        """The receipts ALG-08 actually located in the source — D3's admissibility filter.

        ``EvidenceSpan.verified`` is stamped in exactly one place, ``spans.verify_span``, and
        forced back to False on its two failing verdicts: UNVERIFIED (the quote is not in the
        source at all) and INVALID_BOUNDS (the offsets never described a region of this text).
        So this is not "the extractor's opinion of its own output" — it is the validator's.
        """
        return tuple(span for span in self.evidence if span.verified)

    @property
    def is_admissible(self) -> bool:
        """D3 — may this claim stand as one SIDE of a disagreement?

        REFUSE, not demote, and the choice is forced by what a conflict card is. Everywhere else
        in L1 an unverified receipt DEMOTES: ALG-08 halves the claim's confidence and keeps it
        (``spans._UNVERIFIED_FACTOR``), because an unverified commitment is still an open loop
        somebody may be waiting on. A conflict is the one surface that does not consume
        confidence at all — U3 renders both quotes verbatim, side by side, and asks a human to
        adjudicate between them with no score anywhere on the card for a demotion to land on.
        Demoting here would therefore be indistinguishable from doing nothing, and the founder
        would be shown a sentence the source does not contain, in the same typeface as one it
        does, over a signed document. That is precisely the "confidently wrong with a receipt
        that looks legitimate" failure this module was written to end.

        Refusal is scoped to ALG-12 and to this claim alone. The claim is not deleted: the
        extraction keeps it, ALG-08's halved confidence still travels with it, and the OTHER
        claims in its group still conflict with each other normally.
        """
        return bool(self.verified_evidence)

    def to_conflict_claim(self) -> ConflictClaim:
        """The contract form, with the rank frozen at detection time.

        Only the verified receipts travel. A real quote stapled beside a fabricated one is the
        cheapest way to launder an invention past the unit built to catch it — the claim rides
        in on the good receipt and the card then prints the bad one.
        """
        receipts = self.verified_evidence
        if not receipts:
            raise ValueError(
                f"claim {self.claim_id!r} carries no receipt ALG-08 could verify — it must not "
                "stand as a side of a disagreement (D3). Filter with `is_admissible` first")
        return ConflictClaim(value=self.value, authority=self.authority,
                             authority_rank=self.authority_rank,
                             evidence=list(receipts))


@runtime_checkable
class ClaimGrouper(Protocol):
    """L1.5.0's half of the seam: turn one event's extraction into normalized, subject-keyed
    claims.

    Injected rather than imported so this module cannot grow its own opinion about which
    amounts belong to which contract. GAP FLAG: the concrete implementation is L1.5.0 (ALG-23)
    and is not built yet, so ``ConflictLane`` is only wired where a caller supplies one.
    """

    def claims_for(self, event: object,
                   extraction: ExtractionResult) -> Sequence[NormalizedClaim]:
        ...


# ---------------------------------------------------------------------------------------------
# outputs
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DetectedConflict:
    """A ``Conflict`` plus the subject it is about.

    GAP FLAG (cross-doc): doc 05's ``signal_conflicts`` DDL has a ``subject_key`` column, but
    C-10 ``Conflict`` has no such field and forbids extras — deliberately, since the contract
    owns what a conflict must be true of, not how it was grouped. Pairing them here keeps both
    facts without a second Conflict type or a smuggled attribute.
    """

    subject_key: str
    conflict: Conflict
    #: The events the competing claims came from, strongest claim first. Two distinct ids is
    #: what proves a cross-event conflict rather than one event contradicting itself.
    event_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SubjectTally:
    """How many disagreements one SUBJECT holds, and how many of them survived its own cap.

    D4's record. The cap and the storm guard used to be counted over the whole batch, which made
    them properties of a sweep rather than of a subject: twenty-five vendors disagreeing once
    each lost five of those cards outright and had the surviving twenty relabelled as one storm
    about whichever vendor happened to sort first. Doc 05 files the rule under the failure mode
    *"Conflict storm on ONE entity"* and writes it as "cap 20 conflicts per signal" — both
    halves of that are per subject, and a tally per subject is what makes them so.
    """

    subject_key: str
    #: Conflicts this subject holds, before its own cap.
    detected: int
    #: How many of them survived it.
    kept: int

    @property
    def truncated(self) -> bool:
        return self.kept < self.detected


@dataclass(frozen=True, slots=True)
class ConflictDetection:
    """U1's answer for one batch of claims.

    GAP FLAG: doc 05's reverse prompt types this ``-> list[Conflict]``. A bare list cannot say
    whether the 20-conflict cap TRUNCATED the result, and step 6 of the same prompt requires
    exactly that ("cap 20 ... beyond that emit one INFORMATION_CONFLICT and stop"). The
    conflicts are still the whole content of this object; ``truncated`` is the one fact a list
    could not carry.
    """

    conflicts: tuple[DetectedConflict, ...]
    #: How many conflicts the claims actually contain across every subject, before any cap.
    total_detected: int
    #: One row per subject that held at least one conflict, sorted by ``subject_key``. D4: the
    #: cap is spent PER SUBJECT, so the record of how it was spent has to be per subject too.
    subjects: tuple[SubjectTally, ...] = ()

    @property
    def truncated(self) -> bool:
        """True when ANY subject overflowed its own cap. A batch-level convenience — the thing
        that storms is a subject, and ``storming`` names which ones did."""
        return any(tally.truncated for tally in self.subjects)

    @property
    def storming(self) -> tuple[SubjectTally, ...]:
        """The subjects whose conflicts were capped. U2 raises exactly one signal for each."""
        return tuple(tally for tally in self.subjects if tally.truncated)


@dataclass(frozen=True, slots=True)
class ConflictEscalation:
    """U2 · a conflict that became a signal in its own right.

    Not a ``QualifiedEnterpriseSignal``: that type carries an extraction, a confidence vector
    and a triage lane, none of which this unit is entitled to invent. This is the qualifying
    half — the signal type, what it is about, and the conflicts behind it — which the QES
    assembler consumes. GAP FLAG: that assembler does not exist yet (nothing in the tree
    constructs a ``QualifiedEnterpriseSignal``).
    """

    signal_type: SignalType
    subject_key: str
    field: str
    headline: str
    conflicts: tuple[Conflict, ...]
    #: True for the single aggregate escalation emitted when the cap truncated detection.
    storm: bool = False
    #: U3's render of each conflict above, in the same order and always the same length — the
    #: card is what a human reads, and a signal that says "your sources disagree" without it
    #: leaves every consumer to invent its own rendering. That is not a hypothetical: before
    #: this field existed `render_conflict_card` had no caller in the engine at all, so an
    #: `INFORMATION_CONFLICT` could only ever be shown as its headline string, and the verdict
    #: rule doc 05 is strictest about (no recommendation unless authority settled it) lived in a
    #: function nothing ran.
    cards: tuple[ConflictCard, ...] = ()


@dataclass(frozen=True, slots=True)
class ConflictCardLine:
    """One side of the disagreement, as a human reads it."""

    authority_label: str
    authority_rank: int
    value_text: str
    quote: str
    source_ref: str

    def render(self) -> str:
        return (f"{self.authority_label} says {self.value_text} — "
                f'"{self.quote}" ({self.source_ref})')


@dataclass(frozen=True, slots=True)
class ConflictCard:
    """U3 · the exact shape delivery renders.

    Both values, both authorities, both verbatim quotes, and — per doc 05 — **no recommendation
    about which is right unless ``resolved_by_authority``**. ``verdict`` is therefore ``None``
    for every other resolution, including a recency tie-break: an amendment superseding an
    original is a fact about documents, not a ruling about who to believe, and ``resolution``
    is on the card for a consumer that wants to say so in its own words.
    """

    field: str
    resolution: ConflictResolution
    lines: tuple[ConflictCardLine, ...]
    headline: str
    verdict: str | None

    def render(self) -> str:
        parts = [line.render() for line in self.lines]
        parts.append(self.headline if self.verdict is None
                     else f"{self.headline} {self.verdict}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------------------------
# step 3 · the tolerance ladder
# ---------------------------------------------------------------------------------------------

def _normalized_text(value: str) -> str:
    """Whitespace-collapsed and case-folded — doc 05 step 3's text tolerance."""
    return " ".join(value.split()).casefold()


def _provably_different(left: ClaimValue, right: ClaimValue) -> bool:
    """Are these two normalized values PROVABLY in disagreement?

    Stated as proof of difference rather than a test of equality, because the third state is
    the one that matters: two values this module cannot compare are not a conflict. A false
    conflict costs a founder's attention and, worse, teaches them the conflict card is noise —
    after which the real one is ignored too.

    * **Money** — exact on ``(minor_units, currency)``; no percentage tolerance, money is exact.
      One exception, and it is a refusal to guess rather than a tolerance: equal minor units
      where one side's currency is UNKNOWN (ALG-10 could not establish it) is not proof of
      disagreement, it is one amount whose currency nobody wrote down.
    * **ResolvedDate** — window OVERLAP, not equality. "Oct 10-17" and "Oct 15" are one claim
      written twice. An UNRESOLVED date has no window and overlaps nothing, which is silence
      about a deadline, not a competing claim about it.
    * **text / int** — normalized equality.
    * **anything else, or two different types** — not comparable, so not proof of anything.
    """
    if isinstance(left, Money) and isinstance(right, Money):
        if left.minor_units != right.minor_units:
            return True
        if UNKNOWN_CURRENCY in (left.currency, right.currency):
            return False
        return left.currency != right.currency
    if isinstance(left, ResolvedDate) and isinstance(right, ResolvedDate):
        if left.window is None or right.window is None:
            return False
        return not left.overlaps(right)
    if isinstance(left, str) and isinstance(right, str):
        return _normalized_text(left) != _normalized_text(right)
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left is not right
    if isinstance(left, int) and isinstance(right, int):
        return left != right
    return False


def _ordered(claims: Sequence[NormalizedClaim]) -> list[NormalizedClaim]:
    """Strongest first, then most recent, then by id so ties never reorder between runs.

    Three stable passes rather than one composite key, because the only way to write "highest
    rank, then LATEST time" as a single key is to negate the time — and the obvious negation is
    `-asserted_at.timestamp()`, a float, in a package whose whole contract is that it contains
    none. Python's sort is stable and `reverse=True` does not reorder equal keys, so passes
    compose exactly as the tuple would have.
    """
    by_id = sorted(claims, key=lambda claim: claim.claim_id)
    by_recency = sorted(by_id, key=lambda claim: claim.asserted_at, reverse=True)
    return sorted(by_recency, key=lambda claim: -claim.authority_rank)


def _cluster(claims: Sequence[NormalizedClaim]) -> list[list[NormalizedClaim]]:
    """Partition a group into sides that agree. A claim joins the first cluster whose
    representative it is not provably different from; two clusters means a disagreement.

    Representative-based rather than transitive-closure, because overlap is not transitive:
    Oct 1-10 overlaps Oct 5-15 which overlaps Oct 12-20, while the first and last do not, and a
    transitive union would silently merge two sides that genuinely disagree.
    """
    clusters: list[list[NormalizedClaim]] = []
    for claim in sorted(claims, key=lambda c: (c.asserted_at, c.claim_id)):
        for cluster in clusters:
            if not _provably_different(cluster[0].value, claim.value):
                cluster.append(claim)
                break
        else:
            clusters.append([claim])
    return clusters


def _best(cluster: Sequence[NormalizedClaim]) -> NormalizedClaim:
    """The claim that speaks for a side: highest authority, then most recent."""
    return _ordered(cluster)[0]


def _recency_winner(clusters: Sequence[Sequence[NormalizedClaim]]
                    ) -> NormalizedClaim | None:
    """The amendment, if one exists — doc 05's "recency is a tie-break ONLY within one rank".

    A claim wins by recency only when it EXPLICITLY supersedes a claim on every other side and
    is strictly later than each of them. Without the explicit link the rule would read "the
    newest email wins", which is the v1 write-last-value behaviour under a new name.
    """
    by_id = {claim.claim_id: claim for cluster in clusters for claim in cluster}
    for index, cluster in enumerate(clusters):
        others = [c for i, c in enumerate(clusters) if i != index]
        for claim in _ordered(cluster):
            if claim.supersedes is None:
                continue
            superseded = by_id.get(claim.supersedes)
            if superseded is None or claim.asserted_at <= superseded.asserted_at:
                continue
            covered = all(any(c.claim_id == claim.supersedes for c in other)
                          for other in others)
            if covered:
                return claim
    return None


def _resolve(clusters: Sequence[Sequence[NormalizedClaim]]
             ) -> tuple[ConflictResolution, ClaimValue]:
    """Doc 05 step 4, in full.

    * gap >= 2 -> ``resolved_by_authority``, the higher-ranked claim's value.
    * gap == 1 -> ``unresolved_surface_both``. One step of authority is not enough to silence
      the other side, and this is the rule most likely to be "simplified" later: an attachment
      (3) outranking email prose (2) by one is precisely the pair where the email is often the
      one carrying the amendment.
    * gap == 0 -> recency, but ONLY on an explicit supersession; otherwise both sides surface.
    """
    strongest = {id(cluster): _best(cluster) for cluster in clusters}
    rank_of_best = _ordered(list(strongest.values()))
    order = {id(claim): position for position, claim in enumerate(rank_of_best)}
    ordered = sorted(clusters, key=lambda cluster: order[id(strongest[id(cluster)])])
    top, runner_up = strongest[id(ordered[0])], strongest[id(ordered[1])]
    gap = top.authority_rank - runner_up.authority_rank
    if gap >= 2:
        return ConflictResolution.RESOLVED_BY_AUTHORITY, top.value
    if gap == 0:
        winner = _recency_winner(ordered)
        if winner is not None:
            return ConflictResolution.RESOLVED_BY_RECENCY, winner.value
    return ConflictResolution.UNRESOLVED_SURFACE_BOTH, None


# ---------------------------------------------------------------------------------------------
# U1
# ---------------------------------------------------------------------------------------------

def detect_conflicts(claims: Iterable[NormalizedClaim], *, detected_at: datetime,
                     max_conflicts: int = MAX_CONFLICTS_PER_SIGNAL) -> ConflictDetection:
    """ALG-12 — find every disagreement in a batch of claims, and keep both sides of each.

    The batch SPANS EVENTS by design: the email body and the PDF attached to it are two source
    events, and grouping by event would miss the case this unit exists for. Grouping is by
    ``(subject_key, field)``, which L1.5.0 assigns.

    Deterministic end to end: no clock (``detected_at`` is passed in and stamped on every
    conflict, so a replay of March's sync writes March's row), no float in any comparison, and
    every ordering falls back to ``claim_id``. Groups are visited sorted by
    ``(subject_key, field)`` so which conflicts survive a cap is stable rather than dict-order.

    Two admissibility rules run before anything is compared:

    * **D3 — an unverified receipt is not a side of a disagreement.** ``is_admissible`` carries
      the reasoning; the effect here is that a claim ALG-08 could not locate in its source is
      skipped, and the claims around it still conflict with each other normally.
    * **D4 — the cap is spent PER SUBJECT.** Doc 05 caps "20 conflicts per signal" under the
      failure mode *"Conflict storm on one entity"*. Counted over the batch, one subject with a
      broken export spends every slot and every other subject in the same sweep goes silent —
      the founder loses twenty-four honest cards to one noisy vendor and is told, falsely, that
      the vendor is what all of them were about. Each subject now gets its own budget and its
      own tally, so a storm stays inside the subject that is storming.
    """
    require_aware(detected_at, "detected_at")
    if max_conflicts < 1:
        raise ValueError("max_conflicts must be at least 1 — a cap of zero detects nothing "
                         "and reports no storm either")

    groups: dict[tuple[str, str], list[NormalizedClaim]] = {}
    for claim in claims:
        if not claim.is_admissible:        # D3 — no verified receipt, no seat at the table
            continue
        groups.setdefault((claim.subject_key, claim.field), []).append(claim)

    by_subject: dict[str, list[DetectedConflict]] = {}
    for (subject_key, field_name) in sorted(groups):
        members = groups[(subject_key, field_name)]
        if len(members) < 2:
            continue                       # one claim is a fact, not a disagreement
        clusters = _cluster(members)
        if len(clusters) < 2:
            continue                       # step 3: they agree after normalization
        resolution, resolved_value = _resolve(clusters)
        ordered_claims = _ordered(members)
        by_subject.setdefault(subject_key, []).append(DetectedConflict(
            subject_key=subject_key,
            conflict=Conflict(
                field=field_name,
                # EVERY competing claim, in every resolution mode. The losing side is the
                # evidence that the winning side was contested.
                claims=[claim.to_conflict_claim() for claim in ordered_claims],
                resolution=resolution,
                resolved_value=resolved_value,
                detected_at=detected_at),
            event_ids=tuple(dict.fromkeys(claim.event_id for claim in ordered_claims))))

    kept: list[DetectedConflict] = []
    tallies: list[SubjectTally] = []
    total = 0
    for subject_key in sorted(by_subject):
        found = by_subject[subject_key]    # already in field order
        total += len(found)
        survivors = found[:max_conflicts]
        kept.extend(survivors)
        tallies.append(SubjectTally(subject_key=subject_key, detected=len(found),
                                    kept=len(survivors)))
    return ConflictDetection(conflicts=tuple(kept), total_detected=total,
                             subjects=tuple(tallies))


# ---------------------------------------------------------------------------------------------
# U2
# ---------------------------------------------------------------------------------------------

def is_material_field(field_name: str) -> bool:
    """Does a disagreement about this field deserve a signal of its own? Doc 05's list."""
    return (field_name in MATERIAL_FIELDS
            or any(field_name.startswith(prefix) for prefix in MATERIAL_FIELD_PREFIXES))


def _value_text(value: ClaimValue) -> str:
    """How a value reads on a card, using the source's own words where they exist.

    ``as_written`` rather than a re-formatted number on purpose: the founder is being asked to
    adjudicate between two sources, and re-rendering "$84K" as "$84,000.00" quietly edits one
    side of the argument into a shape neither source used.
    """
    if isinstance(value, (Money, ResolvedDate)):
        return value.as_written
    return str(value)


def escalate_conflicts(detection: ConflictDetection) -> tuple[ConflictEscalation, ...]:
    """U2 — a conflict on a material field becomes an ``INFORMATION_CONFLICT`` signal.

    "Your systems disagree about the refund window" is itself intelligence, and often more
    valuable than either value.

    A STORMING SUBJECT produces exactly ONE escalation, per doc 05's storm rule: twenty
    disagreements about one subject means that source is broken, and twenty signals about it
    would bury everything else in the founder's day. Its own per-conflict escalations are
    dropped deliberately — "and stop" is the instruction.

    D4 — that guard is per subject, and this is the half of D4 that costs the most when it is
    global. A batch-level guard let one vendor's broken export delete every OTHER subject's
    INFORMATION_CONFLICT in the same sweep: the deal that quietly disagreed about its amount
    raised nothing at all, and the single signal the founder received named the exporter. A
    subject that is not storming keeps its own signals whatever its neighbours are doing, and a
    storm headline counts only its own subject's conflicts.

    Order follows ``detection.conflicts`` — subject, then field — so a sweep's escalations come
    back in the same fixed order every run.
    """
    storming = {tally.subject_key: tally for tally in detection.storming}

    grouped: dict[str, list[DetectedConflict]] = {}
    for item in detection.conflicts:
        grouped.setdefault(item.subject_key, []).append(item)

    escalations: list[ConflictEscalation] = []
    for subject_key in sorted(grouped):
        items = grouped[subject_key]
        tally = storming.get(subject_key)
        if tally is not None:
            escalations.append(ConflictEscalation(
                signal_type=SignalType.INFORMATION_CONFLICT,
                subject_key=subject_key,
                field=STORM_FIELD,
                headline=(f"{tally.detected} conflicting values recorded for this subject — "
                          "the sources disagree systematically."),
                conflicts=tuple(item.conflict for item in items),
                storm=True,
                cards=tuple(render_conflict_card(item.conflict) for item in items)))
            continue
        for item in items:
            conflict = item.conflict
            if not is_material_field(conflict.field):
                continue
            values = " vs ".join(_value_text(claim.value) for claim in conflict.claims)
            escalations.append(ConflictEscalation(
                signal_type=SignalType.INFORMATION_CONFLICT,
                subject_key=subject_key,
                field=conflict.field,
                headline=f"Sources disagree about {conflict.field}: {values}.",
                conflicts=(conflict,),
                cards=(render_conflict_card(conflict),)))
    return tuple(escalations)


# ---------------------------------------------------------------------------------------------
# U3
# ---------------------------------------------------------------------------------------------

def render_conflict_card(conflict: Conflict) -> ConflictCard:
    """U3 — the card contract: both values, both authorities, both verbatim quotes.

    The verdict line appears for ``resolved_by_authority`` and for nothing else, because that is
    the only resolution that is a statement about which source to believe. Both claims are
    rendered in every mode — a card showing only the winner cannot explain itself, and the
    loser is the receipt that the winner was contested.
    """
    lines = tuple(
        ConflictCardLine(
            authority_label=AUTHORITY_LABEL[claim.authority],
            authority_rank=claim.authority_rank,
            value_text=_value_text(claim.value),
            quote=claim.evidence[0].quote,
            source_ref=claim.evidence[0].source_ref)
        for claim in conflict.claims)

    verdict: str | None = None
    if conflict.resolution is ConflictResolution.RESOLVED_BY_AUTHORITY:
        strongest = max(conflict.claims, key=lambda claim: claim.authority_rank)
        verdict = (f"{AUTHORITY_LABEL[strongest.authority]} has higher authority "
                   f"({_value_text(strongest.value)}).")
    return ConflictCard(field=conflict.field, resolution=conflict.resolution, lines=lines,
                        headline="Conflict detected.", verdict=verdict)


def render_stored_conflict(record: object) -> ConflictCard | None:
    """U3 for a conflict that came back OUT of `signal_conflicts` — the read path's card.

    A stored row keeps its claims as plain JSON, deliberately: `conflict_store.ConflictRow`
    refuses to rehydrate them itself because "today's contract still validates a row written
    under an older one" is an assertion a permanent evidence record must not make on the
    reader's behalf. So the decision is made HERE, where a reader is asking for a card, and it
    is made by RE-VALIDATING: a row that no longer satisfies the contract returns None and is
    reported as unrenderable rather than shown as a half-card with a dict where a number should
    be.

    Duck-typed over the row (`.field`, `.claims`, `.resolution`, `.resolved_value`,
    `.detected_at`) on `conflict_store.rows_for`'s own terms, so `capture/validate/` keeps its
    no-I/O rule and does not import the module that opens a database engine.
    """
    try:
        claims = [_stored_claim(raw) for raw in getattr(record, "claims", ()) or ()]
        if any(claim is None for claim in claims):
            return None
        conflict = Conflict(
            field=str(getattr(record, "field", "")),
            claims=claims,
            resolution=ConflictResolution(getattr(record, "resolution", "")),
            resolved_value=_stored_value(getattr(record, "resolved_value", None)),
            detected_at=require_aware(getattr(record, "detected_at", None), "detected_at"))
    except (TypeError, ValueError, KeyError):
        return None
    return render_conflict_card(conflict)


def _stored_claim(raw: object) -> ConflictClaim | None:
    """One stored claim back into the contract, or None when the row no longer satisfies it."""
    if not isinstance(raw, Mapping):
        return None
    value = _stored_value(raw.get("value"))
    if value is None:
        return None
    try:
        return ConflictClaim(
            value=value,
            authority=Authority(raw.get("authority")),
            authority_rank=raw.get("authority_rank"),
            evidence=[EvidenceSpan(**span) for span in raw.get("evidence") or ()])
    except (TypeError, ValueError):
        return None


def _stored_value(raw: object) -> ClaimValue | None:
    """A stored claim value back as the NORMALIZED type it was written as.

    The type matters to the card: `_value_text` renders a `Money`'s `as_written` — the source's
    own "$84K" — and would otherwise print the jsonb dict at a founder. Which type a row holds
    is read off the fields ALG-10 and ALG-09 write and nothing else: `minor_units` belongs to
    `Money` alone and `certainty` to `ResolvedDate` alone, so neither branch is a guess about
    shape. A scalar was stored as itself and comes back as itself.
    """
    if isinstance(raw, Mapping):
        try:
            if "minor_units" in raw:
                return Money(**raw)
            if "certainty" in raw:
                return ResolvedDate(**raw)
        except (TypeError, ValueError):
            return None
        return None
    return raw


# ---------------------------------------------------------------------------------------------
# the production seam
# ---------------------------------------------------------------------------------------------

#: The two claim families ALG-12 can actually compare. ``_provably_different`` returns False for
#: every other shape — two ``Commitment`` objects are never proof of disagreement — so feeding
#: them in would spend the storm cap and the lane's memory on pairs that can never be a conflict.
COMPARABLE_FAMILIES = frozenset({FieldFamily.AMOUNT, FieldFamily.DATE})

#: The field path a claim of each comparable family gets on a STRUCTURED subject, where the
#: event's own ``object_type`` is a typed noun the source assigned. ``deal.amount`` is doc 05's
#: material name and it is reached here by reading the record's type, not by guessing one.
_STRUCTURED_FIELD: dict[FieldFamily, str] = {
    FieldFamily.AMOUNT: "amount",
    FieldFamily.DATE: "date",
}


def _collapsed(text: str) -> str:
    """Whitespace-collapsed and case-folded — the same normalisation ``_normalized_text`` uses,
    applied to receipt matching so a span broken across a line still matches its claim."""
    return " ".join(text.split()).casefold()


def field_path_for(family: FieldFamily, tier: SubjectTier, object_type: str | None) -> str:
    """The dotted field a claim is filed under — the second half of ALG-12's grouping key.

    Two branches, and the split is between a fact and the absence of one:

    * a **STRUCTURED** subject is a typed record whose ``object_type`` the SOURCE assigned, so a
      HubSpot deal's amount is literally ``deal.amount`` — doc 05's material name, reached by
      reading the record's type rather than by inferring a business meaning for it;
    * every other tier is prose or a file, where nothing on the event says whether an amount is a
      contract value, an invoice total or a number in a forwarded quote. Those are filed under
      the family (``amount.value``), which groups them correctly and — deliberately — does NOT
      claim materiality it cannot establish.

    That second branch is a KNOWN LIMIT, not an oversight: ``is_material_field`` names four
    business fields, none of which an email body identifies itself as, so a conflict between two
    prose amounts is detected and retained but raises no ``INFORMATION_CONFLICT``. Inventing
    ``contract.value`` for every attachment amount would make the signal fire on invoices and
    forwarded quotes, which is the false-conflict cost ``_provably_different`` exists to avoid.
    """
    if tier is SubjectTier.STRUCTURED and (object_type or "").strip():
        return f"{_collapsed(object_type).replace(' ', '_')}.{_STRUCTURED_FIELD[family]}"
    return f"{family.value}.value"


@dataclass(frozen=True)
class ExtractionClaimGrouper:
    """L1.5.0's claim row adapted onto ALG-12's — **the one call site** the ``ClaimGrouper``
    GAP FLAG names, and the reason conflict detection now runs outside a test.

    ALG-23 (``claims_from_extraction``) already decides what a claim is ABOUT and what family it
    belongs to. What it does not carry is the three things ALG-12 needs: a provenance class, a
    receipt, and a dotted field. Each is derived from a fact rather than assumed:

    * **authority** — ``weigh_authority`` (ALG-14) over the event's own provenance. Read here so
      the rank a conflict is resolved by is the same table the rest of L1 reads.
    * **receipt** — the spans in ``all_evidence`` that literally quote the claim's ``as_written``
      text. ``Money`` and ``ResolvedDate`` carry no evidence list of their own, and a claim whose
      receipt cannot be located is DROPPED rather than handed the extraction's first span: the
      card renders ``evidence[0].quote`` verbatim, so a mismatched span would show the founder a
      sentence that does not contain the number being disputed.
    * **claim_id** — keyed on ``source_object_id``, never on ``event_id``. The same source object
      re-extracted in a later sweep (a recovered park, an overlapping backfill) lands a NEW
      ``event_id``, and keying on that would let one message contradict itself.

    ``executed`` is INJECTED as a set of source object ids rather than inferred, and today no
    production caller can populate it — nothing in L1 determines whether a PDF is signed. That
    is a stated gap, not a default: with it empty an attachment weighs ``ATTACHMENT`` (3) against
    email prose (2), a gap of one, which doc 05 resolves ``unresolved_surface_both``. Both claims
    are still retained and surfaced; only the automatic verdict is withheld.
    """

    #: ``source_object_id`` -> event, for ALG-23's parent walk. Without it a claim with no entity
    #: of its own keys on its event, which groups alone rather than wrongly.
    event_lookup: Callable[[str], object | None] | None = None
    #: The ``source_object_id``s known to be executed agreements. See the class docstring.
    executed: frozenset[str] = frozenset()
    #: ``event -> PreparedContent | None`` — the masked text a claim's offsets are measured
    #: against. Injected, because ``capture/validate/`` may not read a row to find it. Without it
    #: an amount is kept only when some OTHER claim's span happens to quote it, which is
    #: incidental; with it the receipt is located and carries true offsets.
    prepared_for: Callable[[object], object | None] | None = None
    #: ``(event_id, ordinal) -> group_key`` from ALG-23's assembler, or None when the caller has
    #: not assembled groups. This is the field that makes the headline fixture WORK, and the
    #: reason is ALG-22's cascade: an attachment keys on its document identity (rung 2) while the
    #: mail that carried it keys on the organisation it names (rung 3), so the signed PDF's
    #: \$74,000 and the covering mail's \$84K never share a per-claim subject and would never be
    #: compared. Deciding they are about the same contract is ALG-23's job — it unions the two
    #: subjects across the parent walk — and this seam reads that answer instead of this module
    #: growing a second opinion about it. Falls back to the per-claim subject, which groups a
    #: claim alone rather than wrongly.
    group_key_for: Callable[[tuple[str, int]], str | None] | None = None

    def claims_for(self, event: object,
                   extraction: ExtractionResult) -> tuple[NormalizedClaim, ...]:
        source_object_id = str(getattr(event, "source_object_id", "") or "")
        authority = weigh_authority(Provenance(
            source=getattr(event, "source", None),
            object_type=getattr(event, "object_type", None),
            internal_kind=getattr(event, "internal_kind", None),
            executed=source_object_id in self.executed)).authority
        object_type = getattr(event, "object_type", None)
        handle = source_object_id or str(getattr(event, "event_id", ""))
        prepared = self.prepared_for(event) if self.prepared_for is not None else None

        built: list[NormalizedClaim] = []
        for row in claims_from_extraction(event, extraction,
                                          event_lookup=self.event_lookup):
            if row.family not in COMPARABLE_FAMILIES:
                continue
            receipts = _receipts_for(row.claim, extraction, prepared)
            if not receipts:
                continue
            grouped_key = (self.group_key_for((row.event_id, row.ordinal))
                           if self.group_key_for is not None else None)
            built.append(NormalizedClaim(
                claim_id=f"{handle}:{row.ordinal}",
                subject_key=grouped_key or row.subject,
                field=field_path_for(row.family, row.tier, object_type),
                value=row.claim,
                authority=authority,
                evidence=receipts,
                asserted_at=row.occurred_at,
                event_id=str(getattr(event, "event_id", "")) or handle))
        return tuple(built)


def _receipts_for(value: ClaimValue, extraction: ExtractionResult,
                  prepared: object | None) -> tuple[EvidenceSpan, ...]:
    """The receipt for one claim, in two tries and never a third.

    ``Money`` and ``ResolvedDate`` have no ``evidence`` field — a ``Money``'s receipt is its
    ``as_written`` — while ``NormalizedClaim`` refuses a claim with no receipt, because a guess
    must not be weighed against a document. Both rules are right and they meet here, so this
    function's whole job is to find a REAL span rather than to relax either one:

    1. a span already in ``all_evidence`` that quotes the claim's own characters AND that
       ALG-08 has already stamped ``verified``;
    2. the same spans re-graded by ``verify_span`` against the prepared text, when the
       extraction's own spans have not been through ALG-08 yet — which on today's path is
       always, because ``semantic/evidence_binder.py:414`` deliberately forces ``verified``
       False on everything it emits ("a span leaving here wearing a checkmark would be the
       extractor grading its own homework");
    3. failing both, the literal position of ``as_written`` in the PREPARED text, handed to
       ``verify_span`` for the same grading as anything else.

    **D3.** Every branch ends at ``verify_span``, and only a span that comes back stamped is
    kept. That stamp is the ONLY thing ``detect_conflicts`` will admit as a side of a
    disagreement, and ``spans.verify_span`` is the only function in the system entitled to grant
    it. Constructing a span here with ``verified=True`` because we "know" we found it would be
    this module grading its own homework — the exact move the binder refuses one layer up — so
    the offsets are located here and the verdict is asked for there.

    There is deliberately no fourth branch. A span invented with offsets nobody measured would
    satisfy the constructor (``len(quote) == end - start`` is easy to fake) and would put a
    fabricated citation on a card a founder is being asked to adjudicate — the exact failure the
    evidence primitive exists to prevent. A claim with no verifiable receipt is dropped, and it
    is dropped from conflict DETECTION only: the extraction keeps it, at ALG-08's halved
    confidence.

    Match is on ``as_written`` because that is the only string the claim and the text are
    guaranteed to share — 8,400,000 minor units appears in the source as "$84K". The
    ``all_evidence`` comparison is whitespace-collapsed so a quote wrapped across a line still
    matches; the positional search is exact, because an offset is only a receipt if it is right.
    """
    as_written = str(getattr(value, "as_written", "") or "")
    if not as_written.strip():
        return ()

    needle = _collapsed(as_written)
    quoting = tuple(span for span in extraction.all_evidence
                    if needle in _collapsed(span.quote))
    already_graded = tuple(span for span in quoting if span.verified)
    if already_graded:
        return already_graded

    text = getattr(prepared, "clean_text", None)
    if not isinstance(text, str):
        return ()

    regraded = tuple(graded for graded in (_graded(span, text) for span in quoting)
                     if graded is not None)
    if regraded:
        return regraded

    start = text.find(as_written)
    if start < 0:
        return ()
    located = _graded(EvidenceSpan(
        source_ref=f"prepared_content:{getattr(prepared, 'prepared_content_id', '')}",
        quote=as_written, start_offset=start, end_offset=start + len(as_written)), text)
    return () if located is None else (located,)


def _graded(span: EvidenceSpan, source_text: str) -> EvidenceSpan | None:
    """ALG-08's verdict on one candidate receipt, or None when it did not resolve.

    The span that comes back is the one to keep: ``verify_span`` rewrites the offsets to where
    the words were actually found and stamps ``verified`` itself. UNVERIFIED and INVALID_BOUNDS
    come back unstamped and are dropped here — D3.
    """
    _, corrected = verify_span(span, source_text)
    return corrected if corrected.verified else None


@dataclass(frozen=True, slots=True)
class ConflictOutcome:
    """What the lane produced for one event — the detection over everything seen SO FAR."""

    detection: ConflictDetection
    escalations: tuple[ConflictEscalation, ...]

    @property
    def conflicts(self) -> tuple[DetectedConflict, ...]:
        return self.detection.conflicts


@dataclass
class ConflictLane:
    """The seam ``capture/pipeline.py`` calls: conflict detection across the events of one run.

    Stateful on purpose and scoped to ONE ORG and one sync run, exactly like ``SemanticLane``
    carries the run's ``eval_time``. The state is the point: a conflict lives BETWEEN two
    events, so something has to remember the email's claim when the attachment lands twenty
    events later. A caller that constructs no lane gets the pipeline's previous behaviour
    unchanged — wiring a seam must not activate it.

    ``detected_at`` is a constructor argument rather than a clock read, so a replayed sync
    writes the timestamps of the sync it is replaying.
    """

    grouper: ClaimGrouper
    detected_at: datetime
    max_conflicts: int = MAX_CONFLICTS_PER_SIGNAL
    _claims: list[NormalizedClaim] = dataclass_field(default_factory=list, repr=False)
    _seen: set[str] = dataclass_field(default_factory=set, repr=False)

    def observe(self, event: object, extraction: ExtractionResult) -> ConflictOutcome:
        """Add this event's claims to the run and re-detect. Idempotent per ``claim_id``, so a
        redelivered event does not turn one claim into two sides of a fabricated conflict."""
        for claim in self.grouper.claims_for(event, extraction):
            if claim.claim_id in self._seen:
                continue
            self._seen.add(claim.claim_id)
            self._claims.append(claim)
        detection = detect_conflicts(self._claims, detected_at=self.detected_at,
                                     max_conflicts=self.max_conflicts)
        return ConflictOutcome(detection=detection,
                               escalations=escalate_conflicts(detection))


__all__ = [
    "AUTHORITY_LABEL",
    "MATERIAL_FIELDS",
    "MATERIAL_FIELD_PREFIXES",
    "MAX_CONFLICTS_PER_SIGNAL",
    "STORM_FIELD",
    "COMPARABLE_FAMILIES",
    "ClaimGrouper",
    "ConflictCard",
    "ConflictCardLine",
    "ConflictDetection",
    "ConflictEscalation",
    "ConflictLane",
    "ConflictOutcome",
    "DetectedConflict",
    "ExtractionClaimGrouper",
    "SubjectTally",
    "NormalizedClaim",
    "detect_conflicts",
    "escalate_conflicts",
    "field_path_for",
    "is_material_field",
    "render_conflict_card",
    "render_stored_conflict",
]
