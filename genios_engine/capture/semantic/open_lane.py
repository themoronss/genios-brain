"""L1.4.5 · THE OPEN LANE — the release valve that makes a closed vocabulary honest.

`ExtractionResult` names a fixed set of things a message can contain. That closure is what makes
a rule writable: a pack can match `commitment` because `commitment` means one thing this quarter
and the same thing next quarter. The price of closure is everything else — every detail the model
described accurately and the sink had no field for. Today that price is paid silently: the loss
happens at the boundary, not at the model, and nothing anywhere records that a thing was seen.

This module is the other half of the bargain. The extractor is allowed one free-form list,
`unclassified_observations`, and every entry in it lands HERE: span-validated like any other
claim, persisted with its receipt, counted, and reviewed. The vocabulary then grows from evidence
— "this kind of thing has been noticed 40 times across 6 orgs, here are the sentences" — instead
of from somebody's guess about what customers will say next.

THREE UNITS, THREE LAWS
-----------------------
**U1 `capture_unclassified`** — accept and persist. Two behaviours carry the weight:

* *span validation runs on them.* Each observation's receipts go through L1.5.1's `verify_span`,
  the same grader every other claim gets, and the row stores the CORRECTED offsets with the
  verdict the grader gave — never the flag the extractor set on itself. An observation whose
  receipts all resolved to nothing is still stored, flagged `verified=false`: that matches the
  ALG-08 policy row for `UnclassifiedObservation` (keep-and-flag, never drop) and it is the only
  record that the extractor invented a sentence. It is evidence about the extractor even when it
  is not evidence about the world. What it is NOT is a promotion candidate — see U3.
* *the cap is applied at the sink, not raised as an error.* `MAX_UNCLASSIFIED_PER_EXTRACTION` is
  5 and the contract deliberately refuses to enforce it, because an over-eager extractor must not
  be able to destroy an entire message's extraction. So the sink keeps the five most confident
  and COUNTS the rest (`over_cap`). A number that climbs is a prompt regression with a date on it.

**U2 `promote_kind`** — the human gate. A recurring kind becomes a vocabulary member when a
person decides it should, and this callable is the part of that act which touches data: it
verifies the decision is admissible and stamps the historical rows. It cannot and must not edit
`vocabulary.py`; it returns the edit that a human then makes, with the schema-version bump that
invalidates the extraction cache. A vocabulary that grows itself is a vocabulary nobody can write
a rule against — so every refusal below is a refusal to grow it automatically.

**U3 `discovery_report`** — the weekly artifact: what does the model keep noticing that has no
name? Frequency, org spread, first/last seen, and example quotes for the ones a reviewer asks to
read. It is ON DEMAND (an admin call, a script), not a periodic task: the Celery broker here is a
quota-limited Upstash Redis instance, and a report nobody is reading does not need to run itself.

NO RULE MAY READ ANY OF THIS
----------------------------
The rows are unreviewed labels the model chose its own words for. A rule that fired on one would
change behaviour whenever the model's phrasing drifted — which is not a rule, it is a mood.
`context/extract/vocab.py` is the fault already paid for: free-form field names reached 268
distinct values in one org, 192 used exactly once. So the fence is structural and asserted twice
in `tests/capture/semantic/test_open_lane.py`: nothing under `genios_engine/packs/` or
`genios_engine/reason/` imports this module, and neither tree names the table in SQL either —
because an import fence a raw query walks around is not a fence.

INTEGER BASIS POINTS, AND A CLOCK THAT IS A PARAMETER. `capture/semantic/` may call a model and
may touch the database; it still may not invent a score or read a wall clock. No confidence is
computed here at all — `apply_verdicts` already priced these claims — and `eval_time` is passed
in so that a capture, a report and a promotion in one test all agree about when "now" was.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from sqlalchemy import text

from genios_engine.capture.validate.spans import SpanVerdict, verify_span
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import (MAX_UNCLASSIFIED_PER_EXTRACTION, ExtractionResult,
                                                UnclassifiedObservation)
from genios_engine.platform.db import get_engine

#: Rolling retention for an UNPROMOTED observation, from doc 04's storage note. A promoted row is
#: the provenance of a vocabulary member — the answer to "why does this kind exist?" — so it is
#: exempt and outlives the window.
OPEN_LANE_RETENTION_DAYS = 180

#: The discovery window doc 04's U3 query states (`created_at > now() - interval '30 days'`).
#: Long enough that a monthly pattern shows up twice, short enough that a kind which stopped
#: appearing stops being proposed.
DISCOVERY_WINDOW_DAYS = 30

#: `having count(*) >= 5`, verbatim from the U3 query. Below this a "pattern" is a coincidence,
#: and promoting a coincidence adds a vocabulary member no rule will ever match.
PROMOTION_MIN_OCCURRENCES = 5

#: How many example quotes a report may carry per kind. Small on purpose: the quotes are message
#: CONTENT crossing the cross-org admin boundary, and three sentences are enough to name a thing.
MAX_EXAMPLE_QUOTES = 3

#: Canonical kinds are truncated here. The column is indexed and a model that emits a paragraph
#: as a label would otherwise write an index entry PostgreSQL can refuse. Truncation can collide;
#: `proposed_kind_raw` keeps the model's own words so nothing is actually lost.
MAX_KIND_CHARS = 64

#: The bucket a label that canonicalizes to nothing lands in — "???", an emoji, punctuation. It is
#: deliberately not a plausible vocabulary member: a reviewer seeing `unnamed` forty times is
#: reading a prompt defect, not a discovery, and `proposed_kind_raw` shows them what was said.
UNNAMEABLE_KIND = "unnamed"

#: A vocabulary member is lowercase snake_case (L1.4.4's own acceptance asserts it of every set).
#: U2 refuses to promote to anything else, because the promoted name is what a rule will be
#: written against and `Renewal Risk` is not a name a rule can match.
_VOCABULARY_MEMBER = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")

_NON_SLUG = re.compile(r"[^a-z0-9]+")

#: Strongest verdict first — `SpanVerdict` declares its members in strength order and says so.
#: Derived rather than restated so that reordering the enum cannot silently invert "best" here;
#: `tests/capture/semantic/test_open_lane.py` pins the order it depends on.
_STRENGTH_ORDER: tuple[SpanVerdict, ...] = tuple(SpanVerdict)


def canonical_kind(label: str) -> str:
    """A model's free-text label -> the key the discovery report groups on.

    "Renewal Risk", "renewal risk", "Renewal-Risk!" and "  RENEWAL   RISK " are one candidate.
    Without this they are four, each sitting under the promotion threshold forever while the
    pattern is right there four times over — the report would then propose nothing and the lane
    would look empty while it was in fact full.

    Lossy by construction, which is why the raw label is stored beside it and why nothing but
    GROUPING is ever done with the result. Not a vocabulary member either: it becomes one only
    when a human promotes it through `promote_kind`.
    """
    slug = _NON_SLUG.sub("_", label.strip().lower()).strip("_")
    if not slug:
        return UNNAMEABLE_KIND
    return slug[:MAX_KIND_CHARS].strip("_") or UNNAMEABLE_KIND


# ─────────────────────────────────────────────────────────────────────────────────────────────
# The row, and what one capture did
# ─────────────────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ObservationRow:
    """One persisted open-lane row: an observation, its single strongest receipt, and its grade.

    Frozen for the reason `EvidenceSpan` is: this is a record of what was seen and graded, and a
    tally that can be edited after the fact is not a tally.

    ONE receipt, not a list, and that is a real narrowing: an observation may cite several spans,
    the table stores the best-resolving one. The alternative — a child table of receipts for a
    lane whose whole purpose is to be reviewed by eye and mostly deleted after 180 days — buys a
    completeness nobody reads at the cost of a join on every report. `span_verdict` records which
    grade that receipt reached, so "verified" never has to stand in for "byte-exact".
    """

    observation_id: str
    org_id: str
    event_id: str
    #: Canonical, lowercase snake_case. The grouping key.
    proposed_kind: str
    #: What the model actually called it, verbatim.
    proposed_kind_raw: str
    description: str
    quote: str
    source_ref: str
    start_offset: int
    end_offset: int
    confidence_bp: int
    verified: bool
    span_verdict: str
    created_at: datetime
    promoted_to: str | None = None
    promoted_by: str | None = None
    promoted_schema_version: str | None = None
    reviewed_at: datetime | None = None


@dataclass(frozen=True)
class OpenLaneCapture:
    """What one extraction contributed to the lane — the whole outcome, counted.

    `stored` is smaller than `len(rows)` on a replay: observation ids are content-addressed, so
    re-extracting the same event writes nothing new. That matters more than it looks. If ids were
    random, a re-sync would double every kind's frequency and the promotion threshold — the one
    number that decides whether a word enters the vocabulary — would be measuring how often we
    re-ran the pipeline.
    """

    rows: tuple[ObservationRow, ...] = ()
    #: Rows that were new to the table. `len(rows) - stored` is the replay overlap.
    stored: int = 0
    #: Observations beyond `MAX_UNCLASSIFIED_PER_EXTRACTION`, dropped by confidence order. A
    #: rising count is a prompt that stopped honouring the cap it is instructed with.
    over_cap: int = 0
    #: Rows kept but flagged: not one of the observation's receipts resolved against the source.
    #: These never become promotion candidates; they are the record that the extractor invented.
    unverified: int = 0


# ─────────────────────────────────────────────────────────────────────────────────────────────
# L1.4.5-U1 · capture
# ─────────────────────────────────────────────────────────────────────────────────────────────


def _best_receipt(observation: UnclassifiedObservation,
                  source_text: str) -> tuple[SpanVerdict, EvidenceSpan]:
    """Grade every receipt this observation carries and return the strongest one, corrected.

    Strength, not first-listed: an observation citing one relocated quote and one invention must
    be stored against the quote that exists. `verify_span` is L1.5.1's per-span entry point — the
    same grader every other claim gets — and the span it returns carries the source's own bytes at
    the offsets actually found, with a `verified` flag this process did not take on trust.

    The contract guarantees at least one receipt (`_require_receipt`), so there is always
    something to grade and no empty-list branch to get wrong.
    """
    graded = [verify_span(span, source_text) for span in observation.evidence]
    return min(graded, key=lambda pair: _STRENGTH_ORDER.index(pair[0]))


def _observation_id(org_id: str, kind: str, span: EvidenceSpan) -> str:
    """A content address: same org, same kind, same region of the same source -> same id.

    Deterministic so that a re-extract is idempotent (see `OpenLaneCapture.stored`), and derived
    from the CORRECTED span so that a replay whose offsets were fixed by the validator still lands
    on the row the first run wrote rather than beside it.
    """
    digest = hashlib.sha256("\x1f".join([
        org_id, kind, span.source_ref, str(span.start_offset), str(span.end_offset),
    ]).encode("utf-8")).hexdigest()
    return f"obs_{digest[:24]}"


def _most_significant(observations: Sequence[UnclassifiedObservation],
                      ) -> list[UnclassifiedObservation]:
    """The cap, applied at the sink: keep the `MAX_UNCLASSIFIED_PER_EXTRACTION` most confident.

    Doc 04 puts the cap in the PROMPT ("the model is told to pick the 5 most significant") and
    `MAX_UNCLASSIFIED_PER_EXTRACTION` is deliberately not enforced by the contract, because an
    extraction that raises on its sixth observation loses the other five and the whole message
    with them. So this is a trim, not a rejection: highest confidence first, ties broken by the
    model's own ordering, and the remainder is counted rather than mourned.
    """
    ranked = sorted(enumerate(observations), key=lambda pair: (-pair[1].confidence_bp, pair[0]))
    return [observation for _, observation in ranked[:MAX_UNCLASSIFIED_PER_EXTRACTION]]


def capture_unclassified(result: ExtractionResult, *, org_id: str, event_id: str,
                         source_text: str, eval_time: datetime,
                         store: OpenLaneStore) -> OpenLaneCapture:
    """L1.4.5-U1 · persist what the vocabulary had no field for. The sink, and the whole of it.

    `source_text` is the PREPARED clean text the extractor was shown — the only coordinate system
    in which its offsets can be right — and every observation's receipts are re-graded against it
    here rather than trusted. `eval_time` is the row clock: a parameter, so a test can write a
    row into last month and read the report that would have proposed it.

    Returns an `OpenLaneCapture` describing everything that happened, including what did not get
    stored. An extraction with no unclassified observations returns an empty capture and touches
    no storage, which is the overwhelmingly common case and must cost nothing.
    """
    observations = result.unclassified_observations
    if not observations:
        return OpenLaneCapture()

    kept = _most_significant(observations)
    rows: list[ObservationRow] = []
    unverified = 0
    for observation in kept:
        verdict, span = _best_receipt(observation, source_text)
        if not span.verified:
            unverified += 1
        kind = canonical_kind(observation.proposed_kind)
        rows.append(ObservationRow(
            observation_id=_observation_id(org_id, kind, span),
            org_id=org_id, event_id=event_id,
            proposed_kind=kind, proposed_kind_raw=observation.proposed_kind,
            description=observation.description, quote=span.quote,
            source_ref=span.source_ref, start_offset=span.start_offset,
            end_offset=span.end_offset, confidence_bp=observation.confidence_bp,
            verified=span.verified, span_verdict=verdict.value, created_at=eval_time))
    stored = store.add(rows)
    return OpenLaneCapture(rows=tuple(rows), stored=stored,
                           over_cap=len(observations) - len(kept), unverified=unverified)


# ─────────────────────────────────────────────────────────────────────────────────────────────
# L1.4.5-U3 · the discovery report
# ─────────────────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DiscoveryCandidate:
    """One thing the model keeps noticing that has no name.

    `occurrences` counts every row in the window; `verified_occurrences` counts only the ones
    whose receipt resolved against real source text, and that is the number `promotable` is
    computed from. The split is the point: a kind seen 40 times of which 38 cite sentences nobody
    wrote is not a discovery, it is a prompt that has started hallucinating in a new direction,
    and a report showing only the 40 would have a human name it.
    """

    proposed_kind: str
    occurrences: int
    verified_occurrences: int
    orgs: int
    first_seen: datetime
    last_seen: datetime
    #: Verified quotes only, newest first, at most `MAX_EXAMPLE_QUOTES` and only when asked for.
    #: A fabricated quote must never be shown to a reviewer as something somebody wrote.
    example_quotes: tuple[str, ...] = ()
    #: Whether U2 would accept this kind for promotion right now.
    promotable: bool = False


@dataclass(frozen=True)
class DiscoveryReport:
    """The weekly artifact. Carries its own parameters because a bare list of counts is unreadable
    six months later — "seen 7 times" means nothing without the window it was counted over."""

    generated_at: datetime
    window_days: int
    min_occurrences: int
    rows: tuple[DiscoveryCandidate, ...] = ()

    @property
    def promotable(self) -> tuple[DiscoveryCandidate, ...]:
        """The subset a human could act on today — what the review meeting is actually about."""
        return tuple(row for row in self.rows if row.promotable)


def discovery_report(store: OpenLaneStore, *, eval_time: datetime,
                     window_days: int = DISCOVERY_WINDOW_DAYS,
                     min_occurrences: int = PROMOTION_MIN_OCCURRENCES,
                     examples: int = 0, limit: int = 200) -> DiscoveryReport:
    """L1.4.5-U3 · what should the 35th observation kind be?

    Doc 04's query, plus the two columns that query cannot answer: how many of those occurrences
    are actually substantiated, and — when the caller asks for them — what the model was looking
    at. `examples` defaults to ZERO because the quotes are customer message content and this
    report is the one cross-org read surface in Layer 1; the admin route asks for them explicitly
    and audits the ask.

    On demand, not on a schedule. The repo's Celery broker is a quota-limited Upstash Redis and a
    weekly beat that nobody reads the output of is exactly the kind of periodic task this codebase
    has decided not to add. An admin endpoint (`GET /admin/discovery`) and a script call this.

    Kinds already promoted are excluded — by the store, in the query — so a straggling extraction
    from before the schema-version bump cannot re-propose a word that is already in the
    vocabulary.
    """
    rows = store.candidates(eval_time=eval_time, window_days=window_days,
                            min_occurrences=min_occurrences,
                            examples=max(0, min(examples, MAX_EXAMPLE_QUOTES)), limit=limit)
    return DiscoveryReport(generated_at=eval_time, window_days=window_days,
                           min_occurrences=min_occurrences, rows=rows)


# ─────────────────────────────────────────────────────────────────────────────────────────────
# L1.4.5-U2 · the promotion path
# ─────────────────────────────────────────────────────────────────────────────────────────────


class PromotionRefused(ValueError):
    """A promotion that must not proceed, with the reason a human needs in order to fix it.

    An exception rather than a falsy return: `promote_kind` writes to shared history, and a
    refusal a caller can ignore by not reading the result is not a gate. Every message names the
    specific condition and the number behind it, because "refused" alone sends the reviewer back
    to the report to guess which of five rules they tripped.
    """


@dataclass(frozen=True)
class PromotionDecision:
    """A HUMAN's decision, stated in full. Every field is something only a person can supply.

    There is deliberately no `auto` flag, no threshold override and no "promote everything above
    N" constructor: the type cannot express an automatic promotion, so no call site can perform
    one. That is the same trick `CanonicalProposal` uses one unit over — the shape refuses what
    the prose forbids.
    """

    #: The canonical kind from the report. Canonicalized again on the way in, so a reviewer can
    #: paste the raw label from a quote list and still hit the right bucket.
    proposed_kind: str
    #: The vocabulary member it becomes — lowercase snake_case, because a rule will be written
    #: against this name.
    vocabulary_member: str
    #: Who decided. Free text (an email, a name); required, and stored on every row it stamps.
    decided_by: str
    #: `EXTRACTION_SCHEMA_VERSION` as it stands, and as it will stand after the vocabulary edit.
    #: They must differ: the version is part of the extraction cache key, so without the bump the
    #: cache keeps answering with the old vocabulary and the new kind never appears in an
    #: extraction — the promotion would be real in the vocabulary file and invisible everywhere
    #: else.
    schema_version_before: str
    schema_version_after: str


@dataclass(frozen=True)
class Promotion:
    """The outcome: what was stamped, and the CODE EDIT the human still has to make.

    This unit does not touch `vocabulary.py`, and `vocabulary_edit` is how it says so out loud —
    it hands back the two changes (add the member, bump the version) rather than performing them.
    A module that could write the closed vocabulary is a module through which the vocabulary can
    grow itself, and one refactor later "human-in-the-loop" would be a comment.
    """

    decision: PromotionDecision
    #: Historical rows stamped `promoted_to` across every org — the provenance of the new member.
    rows_marked: int
    promoted_at: datetime
    candidate: DiscoveryCandidate

    @property
    def vocabulary_edit(self) -> str:
        """The instruction a human carries out, in one line, with both halves of it."""
        return (f"add '{self.decision.vocabulary_member}' to the closed vocabulary in "
                f"capture/semantic/vocabulary.py and set EXTRACTION_SCHEMA_VERSION = "
                f"'{self.decision.schema_version_after}' (was "
                f"'{self.decision.schema_version_before}') — the bump invalidates the extraction "
                f"cache key so new events extract with the new kind")


def promote_kind(store: OpenLaneStore, decision: PromotionDecision, *, eval_time: datetime,
                 window_days: int = DISCOVERY_WINDOW_DAYS,
                 min_occurrences: int = PROMOTION_MIN_OCCURRENCES) -> Promotion:
    """L1.4.5-U2 · stamp the historical rows for a kind a HUMAN has decided to promote.

    Step 3 of doc 04's procedure, and only the half that is data. The other half — adding the
    member to the closed vocabulary and bumping `EXTRACTION_SCHEMA_VERSION` — is a code change,
    is returned as `Promotion.vocabulary_edit`, and is never performed here.

    Refuses, loudly, when:

    * nobody is recorded as having decided (`decided_by` blank) — the gate itself;
    * the target name is not a lowercase snake_case vocabulary member, because that name is what
      a rule will match on;
    * the schema version is not bumped — without it the extraction cache keeps serving the old
      vocabulary and the promotion changes nothing about what gets extracted;
    * the kind has already been promoted — a second stamp would rewrite the provenance of an
      existing vocabulary member with a new author and a new date;
    * the evidence is thin: fewer than `min_occurrences` SUBSTANTIATED occurrences in the window.
      Unverified rows do not count toward the bar, which is what stops a hallucinating prompt from
      voting a word into the vocabulary.
    """
    kind = canonical_kind(decision.proposed_kind)
    if not decision.decided_by.strip():
        raise PromotionRefused(
            "promotion requires a named human decider: the open lane grows the closed vocabulary "
            "only by an act somebody signed")
    if not _VOCABULARY_MEMBER.fullmatch(decision.vocabulary_member):
        raise PromotionRefused(
            f"'{decision.vocabulary_member}' is not a vocabulary member: members are lowercase "
            "snake_case because rules are written against the name")
    if decision.schema_version_after == decision.schema_version_before:
        raise PromotionRefused(
            "promotion must bump EXTRACTION_SCHEMA_VERSION: the version is part of the extraction "
            "cache key, and without the bump every new event is answered from a cache that "
            f"predates '{decision.vocabulary_member}'")
    already = store.promotion_of(kind)
    if already is not None:
        raise PromotionRefused(
            f"'{kind}' was already promoted to '{already}': re-stamping would overwrite the "
            "provenance of a vocabulary member that already exists")

    found = store.candidates(eval_time=eval_time, window_days=window_days, min_occurrences=0,
                             examples=MAX_EXAMPLE_QUOTES, kinds=(kind,), limit=1)
    candidate = found[0] if found else DiscoveryCandidate(
        proposed_kind=kind, occurrences=0, verified_occurrences=0, orgs=0,
        first_seen=eval_time, last_seen=eval_time)
    if candidate.verified_occurrences < min_occurrences:
        raise PromotionRefused(
            f"'{kind}' has {candidate.verified_occurrences} substantiated occurrence(s) in the "
            f"last {window_days} days and the bar is {min_occurrences}: below it a pattern is a "
            "coincidence, and a vocabulary member no rule ever matches is worse than none")

    marked = store.mark_promoted(proposed_kind=kind, promoted_to=decision.vocabulary_member,
                                 promoted_by=decision.decided_by.strip(),
                                 schema_version=decision.schema_version_after,
                                 eval_time=eval_time)
    return Promotion(decision=decision, rows_marked=marked, promoted_at=eval_time,
                     candidate=candidate)


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Storage
# ─────────────────────────────────────────────────────────────────────────────────────────────


class OpenLaneStore(Protocol):
    """The lane's persistence seam. Two implementations, one contract, asserted equal by test.

    `candidates` is the shape everything else is expressed in, including U2's gate: one query
    answers "what recurs, how widely, how well substantiated" and both the report and the
    promotion check read it, so the threshold a human sees is computed by the same code as the
    threshold the gate enforces.
    """

    def add(self, rows: Sequence[ObservationRow]) -> int: ...

    def observations_for(self, *, org_id: str,
                         event_id: str) -> tuple[ObservationRow, ...]: ...

    def candidates(self, *, eval_time: datetime, window_days: int, min_occurrences: int,
                   examples: int = 0, kinds: Sequence[str] | None = None,
                   limit: int = 200) -> tuple[DiscoveryCandidate, ...]: ...

    def promotion_of(self, proposed_kind: str) -> str | None: ...

    def mark_promoted(self, *, proposed_kind: str, promoted_to: str, promoted_by: str,
                      schema_version: str, eval_time: datetime) -> int: ...

    def purge_expired(self, *, eval_time: datetime | None = None) -> int: ...


def _aggregate(rows: Iterable[ObservationRow], *, since: datetime, min_occurrences: int,
               examples: int, kinds: Sequence[str] | None, limit: int,
               promoted: set[str]) -> tuple[DiscoveryCandidate, ...]:
    """The report, computed in Python — the in-memory store's half of the two-implementation seam.

    Kept beside the SQL rather than hidden inside the class so the two can be read against each
    other line by line; `test_open_lane.py` runs both over identical rows and asserts they agree,
    which is the only way a second implementation stays honest.

    `examples` is clamped to `MAX_EXAMPLE_QUOTES` HERE and not left to the caller, because that
    is where the SQL clamps it — inside the `array_agg` slice, "never a caller's number". A
    Python aggregation that obeyed the caller was not merely a different answer, it was the
    looser of the two: asked for ten, the hermetic store handed back every verified quote it had
    while the server handed back three, and the quotes are customer message content crossing the
    one cross-org read surface in Layer 1. `discovery_report` clamps too; this is the clamp that
    also covers a caller holding the store directly, which is every caller the Protocol has.
    """
    examples = max(0, min(examples, MAX_EXAMPLE_QUOTES))
    buckets: dict[str, list[ObservationRow]] = {}
    for row in rows:
        if row.promoted_to is not None or row.proposed_kind in promoted:
            continue
        if row.created_at <= since:
            continue
        if kinds is not None and row.proposed_kind not in kinds:
            continue
        buckets.setdefault(row.proposed_kind, []).append(row)

    candidates: list[DiscoveryCandidate] = []
    for kind, bucket in buckets.items():
        if len(bucket) < min_occurrences:
            continue
        verified = [row for row in bucket if row.verified]
        newest_first = sorted(verified, key=lambda row: row.created_at, reverse=True)
        candidates.append(DiscoveryCandidate(
            proposed_kind=kind, occurrences=len(bucket), verified_occurrences=len(verified),
            orgs=len({row.org_id for row in bucket}),
            first_seen=min(row.created_at for row in bucket),
            last_seen=max(row.created_at for row in bucket),
            example_quotes=tuple(row.quote for row in newest_first[:examples]),
            promotable=len(verified) >= max(min_occurrences, PROMOTION_MIN_OCCURRENCES)))
    candidates.sort(key=lambda c: (-c.occurrences, c.proposed_kind))
    return tuple(candidates[:limit])


@dataclass
class InMemoryOpenLaneStore:
    """The dev/hermetic store. Same contract, same aggregation, no server.

    A dict keyed by `observation_id` rather than a list, because the content-addressed id is what
    makes a re-capture idempotent and a list would let the in-memory lane double-count where the
    real one does not — a divergence that would show up as a test passing for the wrong reason.
    """

    rows: dict[str, ObservationRow] = field(default_factory=dict)

    def add(self, rows: Sequence[ObservationRow]) -> int:
        stored = 0
        for row in rows:
            if row.observation_id in self.rows:
                continue
            self.rows[row.observation_id] = row
            stored += 1
        return stored

    def observations_for(self, *, org_id: str, event_id: str) -> tuple[ObservationRow, ...]:
        return tuple(sorted((row for row in self.rows.values()
                             if row.org_id == org_id and row.event_id == event_id),
                            key=lambda row: (row.created_at, row.observation_id)))

    def candidates(self, *, eval_time: datetime, window_days: int, min_occurrences: int,
                   examples: int = 0, kinds: Sequence[str] | None = None,
                   limit: int = 200) -> tuple[DiscoveryCandidate, ...]:
        promoted = {row.proposed_kind for row in self.rows.values() if row.promoted_to is not None}
        return _aggregate(self.rows.values(), since=eval_time - timedelta(days=window_days),
                          min_occurrences=min_occurrences, examples=examples,
                          kinds=None if kinds is None else tuple(kinds), limit=limit,
                          promoted=promoted)

    def promotion_of(self, proposed_kind: str) -> str | None:
        for row in self.rows.values():
            if row.proposed_kind == proposed_kind and row.promoted_to is not None:
                return row.promoted_to
        return None

    def mark_promoted(self, *, proposed_kind: str, promoted_to: str, promoted_by: str,
                      schema_version: str, eval_time: datetime) -> int:
        marked = 0
        for key, row in list(self.rows.items()):
            if row.proposed_kind != proposed_kind or row.promoted_to is not None:
                continue
            self.rows[key] = ObservationRow(
                **{**row.__dict__, "promoted_to": promoted_to, "promoted_by": promoted_by,
                   "promoted_schema_version": schema_version, "reviewed_at": eval_time})
            marked += 1
        return marked

    def purge_expired(self, *, eval_time: datetime | None = None) -> int:
        now = eval_time or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=OPEN_LANE_RETENTION_DAYS)
        expired = [key for key, row in self.rows.items()
                   if row.promoted_to is None and row.created_at < cutoff]
        for key in expired:
            del self.rows[key]
        return len(expired)


_COLUMNS = ("observation_id, org_id, event_id, proposed_kind, proposed_kind_raw, description, "
            "quote, source_ref, start_offset, end_offset, confidence_bp, verified, span_verdict, "
            "created_at, promoted_to, promoted_by, promoted_schema_version, reviewed_at")

#: Doc 04's U3 query with the three additions this module's docstrings argue for: the
#: verified/unverified split, the example quotes, and the exclusion of kinds already promoted.
#: `array_agg` is sliced with the module CONSTANT (never a caller's number) so the row that
#: crosses the wire is bounded no matter how hot a kind is; the caller's `examples` then trims it.
_CANDIDATES_SQL = f"""
with promoted as (
    select distinct proposed_kind from unclassified_observations where promoted_to is not null
)
select o.proposed_kind,
       count(*)                                            as occurrences,
       count(*) filter (where o.verified)                  as verified_occurrences,
       count(distinct o.org_id)                            as orgs,
       min(o.created_at)                                   as first_seen,
       max(o.created_at)                                   as last_seen,
       (array_agg(o.quote order by o.created_at desc)
            filter (where o.verified))[1:{MAX_EXAMPLE_QUOTES}] as example_quotes
  from unclassified_observations o
 where o.created_at > :since
   and o.promoted_to is null
   and o.proposed_kind not in (select proposed_kind from promoted)
   -- `cast(... as text)` on BOTH uses, not decoration: psycopg refuses a bare parameter it
   -- cannot type (`could not determine data type of parameter $2`), and the null branch of
   -- this filter is exactly where the driver has nothing to infer from.
   and (cast(:kinds as text) is null
        or o.proposed_kind = any(string_to_array(cast(:kinds as text), ',')))
 group by o.proposed_kind
having count(*) >= :min_occurrences
 order by occurrences desc, o.proposed_kind asc
 limit :lim
"""


class PostgresOpenLaneStore:
    """The real lane. Every write is `on conflict do nothing` against a content-addressed id, so
    a replay is a no-op rather than a second vote for the same kind."""

    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    def add(self, rows: Sequence[ObservationRow]) -> int:
        if not rows:
            return 0
        with self._engine.begin() as conn:
            stored = 0
            for row in rows:
                stored += conn.execute(text(
                    f"insert into unclassified_observations ({_COLUMNS}) values "
                    "(:observation_id, :org_id, :event_id, :proposed_kind, :proposed_kind_raw, "
                    ":description, :quote, :source_ref, :start_offset, :end_offset, "
                    ":confidence_bp, :verified, :span_verdict, :created_at, :promoted_to, "
                    ":promoted_by, :promoted_schema_version, :reviewed_at) "
                    "on conflict (observation_id) do nothing"), row.__dict__).rowcount
        return stored

    def observations_for(self, *, org_id: str, event_id: str) -> tuple[ObservationRow, ...]:
        with self._engine.connect() as conn:
            rows = conn.execute(text(
                f"select {_COLUMNS} from unclassified_observations "
                "where org_id=:o and event_id=:e order by created_at, observation_id"),
                {"o": org_id, "e": event_id}).all()
        return tuple(ObservationRow(**dict(row._mapping)) for row in rows)

    def candidates(self, *, eval_time: datetime, window_days: int, min_occurrences: int,
                   examples: int = 0, kinds: Sequence[str] | None = None,
                   limit: int = 200) -> tuple[DiscoveryCandidate, ...]:
        params: dict[str, Any] = {
            "since": eval_time - timedelta(days=window_days),
            "min_occurrences": min_occurrences, "lim": limit,
            # Comma-joined and split server-side (`string_to_array`). A canonical kind is
            # `[a-z0-9_]+` by construction, so a comma cannot occur inside one — and a plain
            # bound string is adapted identically by every driver, where a Python list handed to
            # a raw `= any(...)` is adapted by some and silently ignored by others.
            "kinds": None if kinds is None else ",".join(kinds),
        }
        # The SQL already slices with the module constant; this is the same clamp on the trim, so
        # the two implementations bound the caller's number identically and a negative one
        # cannot become a from-the-end slice that silently drops the newest quote.
        keep = max(0, min(examples, MAX_EXAMPLE_QUOTES))
        with self._engine.connect() as conn:
            rows = conn.execute(text(_CANDIDATES_SQL), params).all()
        return tuple(DiscoveryCandidate(
            proposed_kind=row.proposed_kind, occurrences=int(row.occurrences),
            verified_occurrences=int(row.verified_occurrences), orgs=int(row.orgs),
            first_seen=row.first_seen, last_seen=row.last_seen,
            example_quotes=tuple((row.example_quotes or [])[:keep]),
            promotable=int(row.verified_occurrences) >= max(min_occurrences,
                                                            PROMOTION_MIN_OCCURRENCES))
            for row in rows)

    def promotion_of(self, proposed_kind: str) -> str | None:
        with self._engine.connect() as conn:
            row = conn.execute(text(
                "select promoted_to from unclassified_observations "
                "where proposed_kind=:k and promoted_to is not null limit 1"),
                {"k": proposed_kind}).first()
        return row.promoted_to if row else None

    def mark_promoted(self, *, proposed_kind: str, promoted_to: str, promoted_by: str,
                      schema_version: str, eval_time: datetime) -> int:
        with self._engine.begin() as conn:
            return conn.execute(text(
                "update unclassified_observations set promoted_to=:to, promoted_by=:by, "
                "promoted_schema_version=:ver, reviewed_at=:at "
                "where proposed_kind=:k and promoted_to is null"),
                {"to": promoted_to, "by": promoted_by, "ver": schema_version,
                 "at": eval_time, "k": proposed_kind}).rowcount

    def purge_expired(self, *, eval_time: datetime | None = None) -> int:
        """The 180-day clock. A promoted row is exempt: it is the provenance of a vocabulary
        member, and deleting it would leave a word in the vocabulary with no record of why."""
        now = eval_time or datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            return conn.execute(text(
                "delete from unclassified_observations where promoted_to is null "
                "and created_at < :cutoff"),
                {"cutoff": now - timedelta(days=OPEN_LANE_RETENTION_DAYS)}).rowcount


__all__ = ["DISCOVERY_WINDOW_DAYS", "MAX_EXAMPLE_QUOTES", "MAX_KIND_CHARS",
           "OPEN_LANE_RETENTION_DAYS", "PROMOTION_MIN_OCCURRENCES", "UNNAMEABLE_KIND",
           "DiscoveryCandidate", "DiscoveryReport", "InMemoryOpenLaneStore", "ObservationRow",
           "OpenLaneCapture", "OpenLaneStore", "PostgresOpenLaneStore", "Promotion",
           "PromotionDecision", "PromotionRefused", "canonical_kind", "capture_unclassified",
           "discovery_report", "promote_kind"]
