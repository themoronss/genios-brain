"""L1.6.8 · ALG-18 — **the qualification floor**, and the ledger that makes a drop explainable.

Doc 06 gives this unit four lines of arithmetic and one sentence that is worth more than the
arithmetic:

    below floor -> dropped, ledger row written WITH components and payload ref

The floor itself is trivial — one comparison against a tenant number. The LEDGER is the unit.
ESQE exists to discard the ~92% of traffic that is not business-relevant *before it costs
anything downstream*, and a system that discards 92% of what a founder was sent has to be able
to answer **"why did I never see X?"** in one query. A drop with no row is indistinguishable
from a bug: nobody can tell a correct refusal from a predicate that failed to fire, from an
extraction that never ran, from an event that was lost in transport. All four look identical —
an absence — and the first three are incidents.

So every refusal here writes `qualification_drops`: the computed importance, EVERY component
that produced it, the floor it failed, and a `prefix:id` reference to the payload it was read
from. That is the difference between "we dropped it" and "we dropped it *because*".

**THE FLOOR IS PER TENANT, AND IT IS A ROW.** Doc 06's failure-mode list ends on the point and
this module obeys it literally: `DEFAULT_FLOOR_BP` is the value a tenant with no row gets, never
the value every tenant gets. A startup's $8K renewal is its quarter; a bank's is noise. A module
constant is how every tenant ends up sharing one cut-off, and how a threshold gets changed by a
deploy with no owner and no date attached — which is why `org_qualification_floors` carries an
`owner` and `qualification_floor_changes` is append-only.

**The three overrides, and why they are not exceptions to the rule.**

* `carries_conflict` — a disagreement between two sources is *by construction* something no
  score can rank, because the two claims disagree about the number the score would be computed
  from. ALG-12 retained both sides precisely so a human could look; dropping the signal on an
  importance derived from one of them would decide the conflict by accident.
* `internal_kind` — company canon (a policy, a written decision, a founder's own note) is not
  observed traffic to be triaged. It is the tenant telling us something. Scoring it against a
  contract-value baseline and refusing it is a category error.
* an UNSCORED signal — L1.6.7 could not produce a number. It travels. *Never block on a missing
  score*: the failure mode of a floor that drops what it could not measure is silent and total.

DETERMINISM. Integer basis points only — there is no float in this file and no arithmetic that
could produce one. No clock: `eval_time` is a parameter of every function that needs an instant,
and `sweep_eval_time` derives the sweep's instant from what the sweep already stored. No model:
a model may DESCRIBE a drop, it may never decide one, because the same message reaching a
founder on Tuesday and not on Wednesday is the failure that ends trust in the whole product.

Related: `capture/parked/` is the OTHER not-delivered vocabulary and this module deliberately
does not become a second one. A `ParkedEvent` is an event we could not *process* — uncertain,
unsupported, recoverable, with a `status` a human moves. A qualification drop is an event we
processed perfectly and *decided against*. Parking a floor drop would put 92% of a tenant's mail
into the human-review queue, which is the queue's death. They stay separate on purpose, and the
ledger row is the record a drop gets instead.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence

from genios_engine.capture.esqe.importance import (ImportanceComponents, ImportanceScore,
                                                    OrgBaseline, compute_org_baseline,
                                                    explain_importance, require_aware_instant,
                                                    score_importance)
from genios_engine.capture.esqe.normalize import NormalizedSignal
from genios_engine.contracts.signal import SignalType
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.capture.qualification")

FLOOR_TABLE = "org_qualification_floors"
FLOOR_CHANGE_TABLE = "qualification_floor_changes"
DROP_TABLE = "qualification_drops"

#: Doc 06's `tenant.qualification_floor_bp` default. The value a tenant with NO row gets — read
#: the module docstring on why it is not the value every tenant gets.
DEFAULT_FLOOR_BP = 2500

#: Doc 06: "DROP, LOGGED, PAYLOAD RETAINED 90d". The same 90 days `pipeline._JUDGED_DROP_PAYLOAD_TTL_DAYS`
#: already gives a judged gate drop, and for the same reason: the floor that refused this signal
#: is not the floor we will be running next quarter, and re-adjudicating a refusal is only
#: possible while the body it was made from still exists.
DROP_PAYLOAD_RETENTION_DAYS = 90

#: The version stamped on a verdict whose importance could not be computed. Not "0" and not the
#: scorer's version: a reader must be able to tell "L1.6.7 scored this at zero" from "L1.6.7
#: never ran", and a shared value would make those two rows identical.
UNSCORED_VERSION = "unscored"


class QualificationReason(str, Enum):
    """Why this signal was kept or refused — a CLOSED vocabulary, on the same terms as
    `ConflictResolution`. Free text here would be re-parsed by whoever builds the drop-rate
    dashboard, and "conflict" / "had a conflict" / "conflict_override" would become three
    distinct causes of the same decision."""

    AT_OR_ABOVE_FLOOR = "at_or_above_floor"
    CONFLICT_OVERRIDE = "conflict_override"
    INTERNAL_KIND_OVERRIDE = "internal_kind_override"
    UNSCORED = "unscored"
    BELOW_FLOOR = "below_floor"


@dataclass(frozen=True)
class QualificationFloor:
    """One tenant's cut-off, with the person who answers for it.

    `origin` is not decoration. A support engineer looking at a tenant with a 92% drop rate has
    to know whether somebody set 6000 or whether nobody ever set anything and the default is
    simply wrong for this customer — those are opposite remedies, and a bare integer cannot tell
    them apart.
    """

    org_id: str
    floor_bp: int
    #: Who answers for the number. `"genios-default"` for the unset case, a real identity for a
    #: tenant row — the DDL makes the column NOT NULL for the same reason.
    owner: str
    note: str = ""
    #: `tenant` — read from `org_qualification_floors`; `default` — no row existed.
    origin: str = "tenant"
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.floor_bp <= 10000:
            raise ValueError(f"floor_bp out of range: {self.floor_bp}")
        if not self.owner:
            raise ValueError("a floor with no owner is a global constant wearing a row")

    @classmethod
    def unset(cls, org_id: str) -> "QualificationFloor":
        """The floor a tenant that has never been tuned gets. A REAL floor object rather than
        `None` handled at four call sites, so the arithmetic below never branches on absence."""
        return cls(org_id=org_id, floor_bp=DEFAULT_FLOOR_BP, owner="genios-default",
                   note="no tenant floor configured", origin="default")


@dataclass(frozen=True)
class FloorChange:
    """One entry in the changelog. `from_bp` is None for the first setting of a floor."""

    change_id: str
    org_id: str
    from_bp: int | None
    to_bp: int
    changed_by: str
    reason: str
    changed_at: datetime


@dataclass(frozen=True)
class ScoredSignal:
    """One normalized signal WITH L1.6.7's answer about it — the floor's input.

    The importance is passed IN rather than computed here, and that separation is the design:
    this unit must not be able to change a score, only to compare one. `importance_bp` is
    `None` when L1.6.7 could not score the signal at all, which is a third state distinct from
    both a low score and a high one — see `QualificationReason.UNSCORED`.
    """

    signal: NormalizedSignal
    #: 0..10000, or None when the scorer produced nothing.
    importance_bp: int | None
    #: L1.6.7's `importance_components`, VERBATIM. Stored on the drop row rather than recomputed:
    #: a weight change next month must not silently re-explain a refusal made under the old ones.
    components: Mapping[str, Any] = field(default_factory=dict)
    importance_version: str = UNSCORED_VERSION
    #: `prepared_content:<id>` or `raw_payload:<event_id>` — ALG-14's `prefix:id` provenance
    #: form. Without it a drop row is a regret rather than a receipt.
    payload_ref: str | None = None
    #: Does this event carry an ALG-12 disagreement. A boolean rather than the `Conflict` objects
    #: because that is the entire input to the rule, and importing the conflict contract to read
    #: `len()` of it would tie the floor to a shape it never looks inside.
    carries_conflict: bool = False
    #: THE INSTANT THIS SIGNAL'S SCORE WAS COMPUTED AGAINST — `importance_components.eval_time`,
    #: carried here so the verdict is stamped with it rather than with a second one.
    #:
    #: The defect this closes: the score used to be computed twice, in two places, against two
    #: different instants. `capture/pipeline.run_esqe_stage` scores every signal at capture
    #: against the event's own frozen moment; `scored_signals_for` then scored it AGAIN against
    #: the sweep's instant, and the drop ledger filed THAT number with THAT timestamp. A founder
    #: asking "why was this refused" read an importance that contradicted the one stored on the
    #: event, and a deadline that had moved a rung between the two moments made the two numbers
    #: genuinely different rather than merely re-derived. `None` only when nothing scored this
    #: signal, in which case `qualify_signals` falls back to the batch instant.
    evaluated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.importance_bp is not None and not 0 <= self.importance_bp <= 10000:
            raise ValueError(f"importance_bp out of range: {self.importance_bp}")


@dataclass(frozen=True)
class QualificationVerdict:
    """The decision about ONE signal, carrying everything the ledger row needs.

    A qualified verdict and a dropped verdict are the SAME type. Two types would let a caller
    handle one and forget the other, which is how the drop half stops being written the first
    time somebody adds a branch.
    """

    org_id: str
    signal_id: str
    event_id: str
    signal_type: SignalType
    predicate: str
    subject_key: str
    qualified: bool
    reason: QualificationReason
    importance_bp: int | None
    floor_bp: int
    components: Mapping[str, Any]
    importance_version: str
    payload_ref: str | None
    evaluated_at: datetime
    #: How long the payload behind this decision must remain fetchable. Set for a DROP; `None`
    #: for a qualified signal, whose body L2 is about to read anyway.
    retain_until: datetime | None


@dataclass(frozen=True)
class QualificationOutcome:
    """Every verdict from one qualification pass, plus the floor they were judged against.

    The floor travels with the verdicts because doc 06 monitors `drop_rate` per org and alerts
    above 95%, and a drop rate quoted without the threshold that produced it is unactionable —
    the first question about a 96% is always "against what floor".
    """

    floor: QualificationFloor
    verdicts: tuple[QualificationVerdict, ...] = ()

    @property
    def qualified(self) -> tuple[QualificationVerdict, ...]:
        return tuple(v for v in self.verdicts if v.qualified)

    @property
    def dropped(self) -> tuple[QualificationVerdict, ...]:
        return tuple(v for v in self.verdicts if not v.qualified)

    @property
    def drop_rate_bp(self) -> int:
        """Doc 06's monitored ratio, in basis points. Integer division — a drop rate is a count
        over a count and a float here would be the only float in the module."""
        return 0 if not self.verdicts else len(self.dropped) * 10000 // len(self.verdicts)

    @property
    def qualify_rate_bp(self) -> int:
        return 0 if not self.verdicts else 10000 - self.drop_rate_bp


def signal_ref(signal: NormalizedSignal) -> str:
    """The content address of one normalized signal — its id until L1.7.4 mints one.

    Content-addressed over the identity tuple (org, event, type, predicate, subject) rather than
    minted from a counter, so that a REPLAYED sweep files its refusal against the same id
    instead of appending a second row about one decision. `qualification_drops.signal_id`
    therefore stays joinable when the qualified-signal store lands and starts stamping
    `QualifiedEnterpriseSignal.signal_id` — it is the same identity, computed the same way.
    """
    payload = json.dumps({
        "org": signal.org_id, "event": signal.event_id,
        # `getattr`, not `.value`. A normalized signal built by L1.6.2 always carries a
        # `SignalType`, but this function is called on EVERY signal of every sweep from three
        # different seams (`scored_signals_for`, `publish_one`, the drop-row join), and an
        # AttributeError here does not cost one signal its id — it unwinds through the sweep
        # guard and costs the whole page its publication. A kind outside the closed 14 is V-2's
        # to refuse, with a ledger row that quotes it; it is not this function's to crash on.
        "type": getattr(signal.signal_type, "value", str(signal.signal_type)),
        "predicate": signal.predicate,
        "subject": signal.subject_key,
    }, sort_keys=True, separators=(",", ":"))
    return "sig_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def drop_id(org_id: str, signal_id: str, floor_bp: int, importance_bp: int) -> str:
    """The content address of one REFUSAL. The floor and the score are both in the digest: the
    same signal refused again after the floor moved is a different decision and deserves its own
    row, while the same signal refused twice by the same floor is one fact re-observed.
    `evaluated_at` is deliberately excluded — it is the only field a replay changes."""
    return "qdr_" + hashlib.sha256(
        f"{org_id}:{signal_id}:{floor_bp}:{importance_bp}".encode("utf-8")).hexdigest()[:32]


# ────────────────────────────────────────────────────────────────────────────────────────────
# THE UNIT (ALG-18). Pure, integer, no clock, no I/O.
# ────────────────────────────────────────────────────────────────────────────────────────────
def qualify_signals(candidates: Sequence[ScoredSignal], *, floor: QualificationFloor,
                    eval_time: datetime) -> QualificationOutcome:
    """ALG-18 over a batch of scored signals — the pass/fail gate, and nothing else.

    Doc 06's ladder, in its order, because the order IS the rule:

        importance_bp >= floor_bp          -> QUALIFY   (at the floor passes: the floor is the
                                                         lowest score worth surfacing, not the
                                                         first score too low to surface)
        below floor + conflict             -> QUALIFY
        below floor + internal_kind        -> QUALIFY
        otherwise                          -> DROP, and the verdict carries the components

    Nothing is written here. The verdicts are values; `drop_rows` turns the refusals into rows
    and a `DropLedger` files them — separated so that the DECISION is testable without a
    database and so an I/O failure can never change what was decided.
    """
    require_aware_instant(eval_time)
    verdicts: list[QualificationVerdict] = []
    for candidate in candidates:
        qualified, reason = _decide(candidate, floor.floor_bp)
        signal = candidate.signal
        # ONE event, ONE instant. The candidate's own `evaluated_at` is the moment its score was
        # computed against, so the ledger row, the components it stores and the retention promise
        # all name the same moment. `eval_time` is the fallback for a candidate nothing scored —
        # a batch instant is the honest answer when there is no per-signal one.
        judged_at = candidate.evaluated_at or eval_time
        retain_until = judged_at + timedelta(days=DROP_PAYLOAD_RETENTION_DAYS)
        verdicts.append(QualificationVerdict(
            org_id=signal.org_id,
            signal_id=signal_ref(signal),
            event_id=signal.event_id,
            signal_type=signal.signal_type,
            predicate=signal.predicate,
            subject_key=signal.subject_key,
            qualified=qualified,
            reason=reason,
            importance_bp=candidate.importance_bp,
            floor_bp=floor.floor_bp,
            # A plain dict copy in a fixed key order: the map is written to jsonb and read back
            # by a human, and two replays whose components serialise in different orders would
            # produce two different `components` strings for one decision.
            components=dict(sorted(candidate.components.items())),
            importance_version=candidate.importance_version,
            payload_ref=candidate.payload_ref,
            evaluated_at=judged_at,
            retain_until=None if qualified else retain_until))
    return QualificationOutcome(floor=floor, verdicts=tuple(verdicts))


def _decide(candidate: ScoredSignal, floor_bp: int) -> tuple[bool, QualificationReason]:
    """The ladder itself. Split out so the ORDER of the four rules is one readable block rather
    than four branches interleaved with object construction."""
    if candidate.importance_bp is None:
        # Fail open, loudly in the reason. A floor that refuses what it could not measure turns
        # a scorer outage into total, silent signal loss for the tenant.
        return True, QualificationReason.UNSCORED
    if candidate.importance_bp >= floor_bp:
        return True, QualificationReason.AT_OR_ABOVE_FLOOR
    if candidate.carries_conflict:
        return True, QualificationReason.CONFLICT_OVERRIDE
    if candidate.signal.internal_kind:
        return True, QualificationReason.INTERNAL_KIND_OVERRIDE
    return False, QualificationReason.BELOW_FLOOR


# ────────────────────────────────────────────────────────────────────────────────────────────
# The floor STORE — the per-tenant setting, its owner and its changelog.
# ────────────────────────────────────────────────────────────────────────────────────────────
class FloorStore(Protocol):
    """Three operations: read the tenant's floor, move it (with attribution), read why it moved."""

    def get(self, org_id: str) -> QualificationFloor | None: ...

    def set(self, org_id: str, floor_bp: int, *, owner: str, changed_by: str,
            at: datetime, reason: str = "", note: str = "") -> QualificationFloor: ...

    def history(self, org_id: str) -> list[FloorChange]: ...


def resolve_floor(org_id: str, store: FloorStore | None = None) -> QualificationFloor:
    """This tenant's floor, or the default — NEVER a failure and never a `None` for the caller
    to interpret. A store that raises costs the sweep its tuning, not its qualification: falling
    back to the default keeps every signal judged, where an exception would leave a whole sweep
    unqualified because a settings read timed out."""
    if store is None:
        return QualificationFloor.unset(org_id)
    try:
        return store.get(org_id) or QualificationFloor.unset(org_id)
    except Exception:      # noqa: BLE001 — a settings read never fails a sweep
        _log.warning("floor lookup failed for org=%s; using the default floor", org_id,
                     exc_info=True)
        return QualificationFloor.unset(org_id)


class InMemoryFloorStore:
    """A dict, for dev and hermetic tests — with the same changelog discipline as the real one,
    so a test cannot pass against a store that silently forgot to record who moved the number."""

    def __init__(self, floors: Mapping[str, int] | None = None, *, owner: str = "test") -> None:
        self._floors: dict[str, QualificationFloor] = {}
        self._history: dict[str, list[FloorChange]] = {}
        for org_id, bp in (floors or {}).items():
            self._floors[org_id] = QualificationFloor(org_id=org_id, floor_bp=bp, owner=owner)

    def get(self, org_id: str) -> QualificationFloor | None:
        return self._floors.get(org_id)

    def set(self, org_id: str, floor_bp: int, *, owner: str, changed_by: str,
            at: datetime, reason: str = "", note: str = "") -> QualificationFloor:
        previous = self._floors.get(org_id)
        floor = QualificationFloor(org_id=org_id, floor_bp=floor_bp, owner=owner, note=note,
                                   updated_at=at)
        self._floors[org_id] = floor
        self._history.setdefault(org_id, []).append(FloorChange(
            change_id=_change_id(org_id, previous.floor_bp if previous else None, floor_bp, at),
            org_id=org_id, from_bp=previous.floor_bp if previous else None, to_bp=floor_bp,
            changed_by=changed_by, reason=reason, changed_at=at))
        return floor

    def history(self, org_id: str) -> list[FloorChange]:
        return list(reversed(self._history.get(org_id, [])))


def _change_id(org_id: str, from_bp: int | None, to_bp: int, at: datetime) -> str:
    return "qfc_" + hashlib.sha256(
        f"{org_id}:{from_bp}:{to_bp}:{at.isoformat()}".encode("utf-8")).hexdigest()[:32]


class PostgresFloorStore:
    """`org_qualification_floors` + `qualification_floor_changes` (migration 0088).

    `set` writes BOTH in one transaction. A floor that moved without a changelog entry is the
    unattributed constant edit doc 06 forbids, and two statements outside a transaction is
    exactly how one of them ends up missing.
    """

    def __init__(self, database_url: str) -> None:
        from genios_engine.platform.db import get_engine
        self._engine = get_engine(database_url)

    def get(self, org_id: str) -> QualificationFloor | None:
        from sqlalchemy import text
        with self._engine.connect() as conn:
            row = conn.execute(text(
                f"select org_id, floor_bp, owner, note, updated_at from {FLOOR_TABLE} "
                "where org_id=:o"), {"o": org_id}).first()
        if row is None:
            return None
        return QualificationFloor(org_id=row.org_id, floor_bp=row.floor_bp, owner=row.owner,
                                  note=row.note or "", origin="tenant",
                                  updated_at=row.updated_at)

    def set(self, org_id: str, floor_bp: int, *, owner: str, changed_by: str,
            at: datetime, reason: str = "", note: str = "") -> QualificationFloor:
        from sqlalchemy import text
        # Validated here rather than only by the CHECK constraint, so a bad value is a Python
        # error at the call site instead of a database error three frames away.
        floor = QualificationFloor(org_id=org_id, floor_bp=floor_bp, owner=owner, note=note,
                                   updated_at=at)
        with self._engine.begin() as conn:
            previous = conn.execute(text(
                f"select floor_bp from {FLOOR_TABLE} where org_id=:o for update"),
                {"o": org_id}).scalar()
            conn.execute(text(
                f"insert into {FLOOR_TABLE} (org_id, floor_bp, owner, note, updated_at) "
                "values (:o, :bp, :owner, :note, :at) "
                "on conflict (org_id) do update set floor_bp=excluded.floor_bp, "
                "owner=excluded.owner, note=excluded.note, updated_at=excluded.updated_at"),
                {"o": org_id, "bp": floor_bp, "owner": owner, "note": note, "at": at})
            conn.execute(text(
                f"insert into {FLOOR_CHANGE_TABLE} "
                "(change_id, org_id, from_bp, to_bp, changed_by, reason, changed_at) "
                "values (:id, :o, :from_bp, :to_bp, :by, :reason, :at) "
                "on conflict (change_id) do nothing"),
                {"id": _change_id(org_id, previous, floor_bp, at), "o": org_id,
                 "from_bp": previous, "to_bp": floor_bp, "by": changed_by,
                 "reason": reason, "at": at})
        return floor

    def history(self, org_id: str) -> list[FloorChange]:
        from sqlalchemy import text
        with self._engine.connect() as conn:
            rows = conn.execute(text(
                "select change_id, org_id, from_bp, to_bp, changed_by, reason, changed_at "
                f"from {FLOOR_CHANGE_TABLE} where org_id=:o "
                "order by changed_at desc, change_id"), {"o": org_id}).all()
        return [FloorChange(change_id=r.change_id, org_id=r.org_id, from_bp=r.from_bp,
                            to_bp=r.to_bp, changed_by=r.changed_by, reason=r.reason,
                            changed_at=r.changed_at) for r in rows]


# ────────────────────────────────────────────────────────────────────────────────────────────
# The DROP LEDGER — "why did I never see X?"
# ────────────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class DropRow:
    """One refused signal, in the shape the table holds it.

    `components` is a plain mapping rather than a typed score object for the reason
    `ConflictRow.claims` is plain JSON: this type crosses the database boundary in BOTH
    directions, and a row written under one weight version must not have to re-validate against
    the next one to be readable. Re-interpretation is a reader's decision, never the store's.
    """

    org_id: str
    drop_id: str
    signal_id: str
    event_id: str
    signal_type: str
    predicate: str
    subject_key: str
    importance_bp: int
    importance_version: str
    floor_bp: int
    components: Mapping[str, Any]
    payload_ref: str | None
    evaluated_at: datetime
    retain_until: datetime


def drop_rows(outcome: QualificationOutcome) -> tuple[DropRow, ...]:
    """The outcome's refusals as rows. A free function, on `conflict_store.rows_for`'s terms:
    the SHAPE of a stored drop is decided once, so the in-memory ledger and the Postgres ledger
    agree by construction rather than by two implementations that happen to match today."""
    rows: list[DropRow] = []
    for verdict in outcome.dropped:
        # `dropped` only ever yields verdicts that failed the comparison, so both of these are
        # non-None by construction; the asserts are the type narrowing, not a runtime check.
        assert verdict.importance_bp is not None and verdict.retain_until is not None
        rows.append(DropRow(
            org_id=verdict.org_id,
            drop_id=drop_id(verdict.org_id, verdict.signal_id, verdict.floor_bp,
                            verdict.importance_bp),
            signal_id=verdict.signal_id, event_id=verdict.event_id,
            signal_type=verdict.signal_type.value, predicate=verdict.predicate,
            subject_key=verdict.subject_key, importance_bp=verdict.importance_bp,
            importance_version=verdict.importance_version, floor_bp=verdict.floor_bp,
            components=dict(verdict.components), payload_ref=verdict.payload_ref,
            evaluated_at=verdict.evaluated_at, retain_until=verdict.retain_until))
    return tuple(rows)


def extend_payload_retention(conn, rows: Sequence[Any]) -> None:
    """Doc 06's "PAYLOAD RETAINED 90d", enforced — for ANY ledger row that promises it.

    A free function rather than a method on `PostgresDropLedger`, because the drop ledger is not
    the only table that makes this promise: `publication_rejections` (migration 0092) stores the
    same `payload_ref` under the same retention, and a second copy of this UPDATE over there
    would be two writers that agree today and diverge the first time either is edited. A row
    needs three attributes to be extendable — `org_id`, `event_id` and `retain_until` — and both
    row types have them, which is why the parameter is typed structurally.

    `greatest` so an already-longer TTL (a parked event keeps its body a year) is never
    SHORTENED by a refusal being filed. Grouped by `(org, retain_until)` so one page of rows is
    one UPDATE per distinct promise rather than one per row.

    Takes an open CONNECTION rather than a URL: the extension has to land in the SAME
    transaction as the rows it is a promise about, or a crash between the two commits leaves a
    receipt for a body that is already deleted.
    """
    from sqlalchemy import text
    by_org: dict[tuple[str, datetime], set[str]] = {}
    for row in rows:
        by_org.setdefault((row.org_id, row.retain_until), set()).add(row.event_id)
    for (org_id, until), event_ids in by_org.items():
        conn.execute(text(
            "update raw_payloads set expires_at = greatest(expires_at, :until) "
            "where org_id=:o and event_id = any(:events)"),
            {"until": until, "o": org_id, "events": list(event_ids)})


class DropLedger(Protocol):
    """A sweep files what it refused; a support engineer asks what a tenant never saw."""

    def put(self, rows: Sequence[DropRow]) -> int: ...

    def list(self, org_id: str, event_id: str | None = None) -> list[DropRow]: ...

    def get(self, org_id: str, drop_id: str) -> DropRow | None: ...


class InMemoryDropLedger:
    """A dict, for dev and hermetic tests. Keyed on (org, drop_id) rather than the id alone —
    the same tenant boundary the real table enforces, so a hermetic test cannot pass while the
    real ledger would hand one tenant's subject lines to another."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], DropRow] = {}

    def put(self, rows: Sequence[DropRow]) -> int:
        for row in rows:
            self._rows[(row.org_id, row.drop_id)] = row
        return len(rows)

    def list(self, org_id: str, event_id: str | None = None) -> list[DropRow]:
        return [r for (o, _), r in sorted(self._rows.items())
                if o == org_id and (event_id is None or r.event_id == event_id)]

    def get(self, org_id: str, drop_id: str) -> DropRow | None:
        return self._rows.get((org_id, drop_id))


_DROP_COLUMNS = ("drop_id, org_id, signal_id, event_id, signal_type, predicate, subject_key, "
                 "importance_bp, importance_version, floor_bp, components, payload_ref, "
                 "evaluated_at, retain_until")


class PostgresDropLedger:
    """The real ledger — and the thing that makes `payload_ref` a promise rather than a string.

    `put` extends `raw_payloads.expires_at` for every referenced event to at least `retain_until`
    IN THE SAME TRANSACTION as the rows. An emitted event's body is kept 30 days
    (`pipeline._EMITTED_PAYLOAD_TTL_DAYS`); doc 06 requires 90 for a drop. A ledger row that
    outlived the payload it points at would be a receipt for something nobody can fetch, which
    is a worse answer to "why did I never see X?" than no row at all — it looks like an answer.

    `put` logs and returns 0 on a database error rather than raising into the ingestion path, on
    `PostgresConflictStore.put`'s terms: losing a drop row costs an explanation, losing a sweep
    costs the tenant their mail.
    """

    def __init__(self, database_url: str) -> None:
        from genios_engine.platform.db import get_engine
        self._engine = get_engine(database_url)

    def put(self, rows: Sequence[DropRow]) -> int:
        from sqlalchemy import text
        if not rows:
            return 0
        try:
            with self._engine.begin() as conn:
                for row in rows:
                    conn.execute(text(
                        f"insert into {DROP_TABLE} ({_DROP_COLUMNS}) values "
                        "(:id, :o, :sig, :ev, :st, :pred, :sub, :imp, :ver, :floor, "
                        " cast(:comp as jsonb), :ref, :at, :until) "
                        "on conflict (drop_id) do update set "
                        "components=excluded.components, payload_ref=excluded.payload_ref, "
                        "evaluated_at=excluded.evaluated_at, retain_until=excluded.retain_until"),
                        {"id": row.drop_id, "o": row.org_id, "sig": row.signal_id,
                         "ev": row.event_id, "st": row.signal_type, "pred": row.predicate,
                         "sub": row.subject_key, "imp": row.importance_bp,
                         "ver": row.importance_version, "floor": row.floor_bp,
                         "comp": json.dumps(dict(row.components), sort_keys=True),
                         "ref": row.payload_ref, "at": row.evaluated_at,
                         "until": row.retain_until})
                extend_payload_retention(conn, rows)
        except Exception as exc:      # noqa: BLE001 — a drop ledger never kills a sweep
            _log.warning("could not file %d qualification drop(s) for org=%s: %s",
                         len(rows), rows[0].org_id, exc)
            return 0
        return len(rows)

    def list(self, org_id: str, event_id: str | None = None) -> list[DropRow]:
        from sqlalchemy import text
        clause = " and event_id=:ev" if event_id else ""
        params: dict[str, Any] = {"o": org_id}
        if event_id:
            params["ev"] = event_id
        with self._engine.connect() as conn:
            rows = conn.execute(text(
                f"select {_DROP_COLUMNS} from {DROP_TABLE} where org_id=:o{clause} "
                "order by evaluated_at desc, drop_id"), params).all()
        return [_to_drop_row(r) for r in rows]

    def get(self, org_id: str, drop_id_: str) -> DropRow | None:
        from sqlalchemy import text
        with self._engine.connect() as conn:
            row = conn.execute(text(
                f"select {_DROP_COLUMNS} from {DROP_TABLE} "
                "where org_id=:o and drop_id=:id"), {"o": org_id, "id": drop_id_}).first()
        return _to_drop_row(row) if row is not None else None


def _to_drop_row(row: Any) -> DropRow:
    components = (row.components if isinstance(row.components, dict)
                  else json.loads(row.components or "{}"))
    return DropRow(
        org_id=row.org_id, drop_id=row.drop_id, signal_id=row.signal_id, event_id=row.event_id,
        signal_type=row.signal_type, predicate=row.predicate, subject_key=row.subject_key,
        importance_bp=row.importance_bp, importance_version=row.importance_version,
        floor_bp=row.floor_bp, components=components, payload_ref=row.payload_ref,
        evaluated_at=row.evaluated_at, retain_until=row.retain_until)


def explain_drop(row: DropRow) -> str | None:
    """L1.6.7-U3 rendered from a FILED REFUSAL — "why did I never see this?", in one sentence.

    The renderer existed and nothing on a request path called it, so the drop ledger stored the
    components that answer the tenant's question and answered it to nobody. This is the seam:
    `api/routes.get_qualification_drop` hands one stored row here and shows the sentence beside
    the number it explains.

    Rendered from `row.components` — never re-scored. Re-running ALG-17 to produce the sentence
    would explain today's weights over yesterday's decision, which is the one thing storing the
    components was meant to prevent.

    `None`, not a placeholder sentence, when the stored map is not a shape this build can
    re-type: a row written under an older components shape has an honest answer ("we cannot
    reconstruct this") and a dishonest one (a sentence assembled from defaults), and only the
    first is safe to put in front of a founder asking why they were not told something.
    """
    try:
        components = ImportanceComponents.from_record(row.components)
    except ValueError:
        _log.warning("drop %s carries components this build cannot re-type", row.drop_id)
        return None
    return explain_importance(ImportanceScore(importance_bp=row.importance_bp,
                                              components=components,
                                              importance_version=row.importance_version))


# ────────────────────────────────────────────────────────────────────────────────────────────
# THE SEAM — one sweep, qualified and filed. The production entry point.
# ────────────────────────────────────────────────────────────────────────────────────────────
class ImportanceScorer(Protocol):
    """L1.6.7's `score_importance`, as the module actually landed it.

    A Protocol beside the concrete default rather than instead of it: `qualify_sweep` defaults
    to the real ALG-17 scorer, and the seam stays injectable so a test can pin a number without
    the floor having to know it did. Doc 06's reverse prompt writes this signature with an
    `extraction` argument and a `(bp, components)` tuple; `importance.py` takes the whole
    `NormalizedSignal` instead — L1.6.2 has already read the extraction into `primary_amount`,
    `primary_date` and `attribution` — and returns a typed `ImportanceScore`. The landed API is
    what this depends on; the doc's prompt is noted in `docs/plans/L2_MISSING_UNIT_SPECS.md`
    §3 **A-12** rather than shimmed.
    """

    def __call__(self, signal: NormalizedSignal, baseline: OrgBaseline, *,
                 eval_time: datetime) -> ImportanceScore: ...


def payload_ref_for(result: Any) -> str | None:
    """The `prefix:id` reference to the body a signal was read from.

    `prepared_content:<id>` when the event produced prepared text — the same form
    `run_esqe_stage` already puts on `SourceAttribution.source_ref`, so a drop row and an
    attribution row point at one another rather than at two different notions of "the source".
    `raw_payload:<event_id>` otherwise, which is what a structured object has.
    """
    prepared = getattr(result, "prepared", None)
    if prepared is not None and getattr(prepared, "prepared_content_id", None):
        return f"prepared_content:{prepared.prepared_content_id}"
    event = getattr(result, "event", None)
    event_id = getattr(event, "event_id", None)
    return f"raw_payload:{event_id}" if event_id else None


def sweep_eval_time(summary: Any) -> datetime | None:
    """The instant this sweep's qualification is judged against, taken from what the sweep
    already stored — never from a clock in this module.

    ALG-12's `detected_at` first: it IS the sweep's frozen instant (the semantic lane's
    `eval_time` when a tenant is activated), so the conflict record and the drop ledger agree
    about when the sweep happened. Otherwise the latest `occurred_at` among the captured events,
    which is a stored world time and therefore replays identically. `None` for a sweep with
    nothing in it, which needs no instant because it has nothing to judge.
    """
    detection = getattr(getattr(summary, "conflicts", None), "detection", None)
    detected_at = getattr(detection, "detected_at", None)
    if isinstance(detected_at, datetime):
        return detected_at
    occurred = [result.event.occurred_at for result in getattr(summary, "results", ()) or ()
                if getattr(getattr(result, "event", None), "occurred_at", None) is not None]
    return max(occurred) if occurred else None


def scored_signals_for(summary: Any, *, scorer: ImportanceScorer | None,
                       eval_time: datetime,
                       org_baseline: OrgBaseline | None = None) -> tuple[ScoredSignal, ...]:
    """Every normalized signal this sweep produced, with L1.6.7's score attached.

    One try/except around the SCORER per signal rather than one around the loop: a scorer that
    raises on one malformed extraction must cost that signal its number, not cost the other
    forty-nine their qualification.
    """
    # L1.6.7-U2's own cold-start answer when the caller has no nightly baseline: `basis=ESTIMATED`,
    # a zero p50, and `score_importance` reading the BASIS to switch to the absolute ladder. Never
    # a fabricated p50 — an invented "typical contract" would rescale every money term this tenant
    # ever gets, invisibly.
    baseline = org_baseline or compute_org_baseline((), org_id=_org_of(summary),
                                                    eval_time=eval_time)
    candidates: list[ScoredSignal] = []
    for result in getattr(summary, "results", ()) or ():
        esqe = getattr(result, "esqe", None)
        signals = getattr(esqe, "normalized", ()) if esqe is not None else ()
        if not signals:
            continue
        # THE SCORE THE PIPELINE ALREADY COMPUTED, index-aligned with `normalized` by
        # `run_esqe_stage` itself. Reading it is the whole point: ALG-17 ran ONCE, at capture,
        # against that event's own frozen instant, and re-running it here against the sweep's
        # instant produced a second number for one signal — the one the ledger filed, and the one
        # that contradicted the score stored on the event.
        scores = getattr(esqe, "importance", ()) if esqe is not None else ()
        ref = payload_ref_for(result)
        carries_conflict = _event_carries_conflict(summary, getattr(result.event, "event_id", ""))
        for index, signal in enumerate(signals):
            # A caller whose summary carries no scores at all — an older shape, or a test pinning
            # a number — still gets one, from the injected scorer. That branch is the fallback,
            # never the path a sweep takes.
            score = scores[index] if index < len(scores) else None
            if score is None:
                score = _score_one(scorer, signal, baseline, eval_time)
            candidates.append(_candidate(signal, score, payload_ref=ref,
                                         carries_conflict=carries_conflict,
                                         eval_time=eval_time))
    return tuple(candidates)


def _candidate(signal: NormalizedSignal, score: ImportanceScore | None, *,
               payload_ref: str | None, carries_conflict: bool,
               eval_time: datetime) -> ScoredSignal:
    """One scored signal as the floor's input — the ONE place a score becomes a candidate.

    Written once rather than at the two branches above, because the two branches differ only in
    where the `ImportanceScore` came from and must not differ in how it is read. `as_record()` is
    L1.6.7's own storage shape — the doc's `importance_components` dict, produced once, there.
    Re-flattening the typed object here would be a second spelling of the same contract, which is
    how two spellings silently disagree.
    """
    if score is None:
        return ScoredSignal(signal=signal, importance_bp=None, components={},
                            importance_version=UNSCORED_VERSION, payload_ref=payload_ref,
                            carries_conflict=carries_conflict, evaluated_at=eval_time)
    return ScoredSignal(signal=signal, importance_bp=score.importance_bp,
                        components=score.components.as_record(),
                        importance_version=score.importance_version, payload_ref=payload_ref,
                        carries_conflict=carries_conflict,
                        evaluated_at=score.components.eval_time)


def _score_one(scorer: ImportanceScorer | None, signal: NormalizedSignal,
               baseline: OrgBaseline,
               eval_time: datetime) -> ImportanceScore | None:
    """One signal's score, or the honest absence of one. The FALLBACK, not the sweep's path.

    `score_importance` is TOTAL over its data — it documents that no signal makes it raise — so
    this except branch is not expected to fire. It is here because the alternative when it does
    is a whole sweep lost to one malformed claim, and because an injected scorer in a future
    caller carries no such guarantee. Either way the signal TRAVELS: a floor that refuses what it
    could not measure turns a scorer outage into total, silent signal loss for the tenant.
    """
    if scorer is None:
        return None
    try:
        return scorer(signal, baseline, eval_time=eval_time)
    except Exception:      # noqa: BLE001 — an unscorable signal travels; it is never dropped
        _log.warning("importance scoring failed for signal on event=%s", signal.event_id,
                     exc_info=True)
        return None


def _org_of(summary: Any) -> str:
    """The org a sweep's results belong to, for the cold-start baseline's own `org_id` field.
    Read off the first captured signal rather than taken as a parameter twice: the caller
    already names the org, and two sources for one identity is how they disagree."""
    for result in getattr(summary, "results", ()) or ():
        for signal in getattr(getattr(result, "esqe", None), "normalized", ()) or ():
            return signal.org_id
    return ""


def _event_carries_conflict(summary: Any, event_id: str) -> bool:
    """Does THIS event carry one of the sweep's disagreements.

    Read off the sweep's own `ConflictOutcome` rather than imported from `capture/pipeline` —
    the pipeline imports this package, so the dependency cannot point back the other way — and
    filtered by event id for the reason `pipeline._conflicts_for` states: the detection covers
    the whole sweep, so an unfiltered read would grant the conflict override to every message in
    a page because two OTHER messages disagreed.
    """
    detection = getattr(getattr(summary, "conflicts", None), "detection", None)
    for detected in getattr(detection, "conflicts", ()) or ():
        if event_id in (getattr(detected, "event_ids", ()) or ()):
            return True
    return False


def qualify_sweep(summary: Any, *, org_id: str, floor_store: FloorStore | None = None,
                  ledger: DropLedger | None = None,
                  scorer: ImportanceScorer | None = score_importance,
                  org_baseline: OrgBaseline | None = None) -> QualificationOutcome:
    """THE SEAM. One sweep's signals, judged against the tenant's floor and its refusals filed.

    A function over the SUMMARY rather than over a list of signals, on `persist_sweep_conflicts`'s
    terms: a caller that has a sweep result has everything this needs and cannot file half of it.
    Called from `api/routes._run_ledger` — the one hook every `run_sync` caller in the HTTP layer
    already passes — so the floor does not depend on which of the six sync call sites remembered.

    Never raises. A sweep that could not be qualified reports an empty outcome and keeps its
    mail; qualification is downstream of capture, exactly like grouping and conflict detection.
    """
    floor = resolve_floor(org_id, floor_store)
    try:
        eval_time = sweep_eval_time(summary)
        if eval_time is None:
            return QualificationOutcome(floor=floor)
        candidates = scored_signals_for(summary, scorer=scorer, eval_time=eval_time,
                                        org_baseline=org_baseline)
        outcome = qualify_signals(candidates, floor=floor, eval_time=eval_time)
    except Exception:      # noqa: BLE001 — downstream of capture, never above it
        _log.warning("qualification failed for org=%s", org_id, exc_info=True)
        return QualificationOutcome(floor=floor)
    if ledger is not None:
        rows = drop_rows(outcome)
        if rows:
            ledger.put(rows)
    return outcome


__all__ = [
    "DEFAULT_FLOOR_BP", "DROP_PAYLOAD_RETENTION_DAYS", "DROP_TABLE", "FLOOR_CHANGE_TABLE",
    "FLOOR_TABLE", "UNSCORED_VERSION",
    "DropLedger", "DropRow", "FloorChange", "FloorStore", "ImportanceScorer",
    "InMemoryDropLedger", "InMemoryFloorStore", "PostgresDropLedger", "PostgresFloorStore",
    "extend_payload_retention",
    "QualificationFloor", "QualificationOutcome", "QualificationReason", "QualificationVerdict",
    "ScoredSignal",
    "drop_id", "drop_rows", "explain_drop", "payload_ref_for", "qualify_signals",
    "qualify_sweep", "resolve_floor", "scored_signals_for", "signal_ref", "sweep_eval_time",
]
