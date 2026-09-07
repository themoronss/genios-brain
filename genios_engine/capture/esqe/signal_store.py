"""L1.7.4 · the SIGNAL STORE — `qualified_signals`, the durable set L2 never had.

`source_events` records that an object was ingested. `qualification_drops` records what the
floor refused. Neither records what Layer 1 CONCLUDED, so every question of the form "what does
the engine believe about this tenant right now" had to be answered by re-running capture over
mail we had already paid to read — and a signal's own explanation (its importance components,
its confidence vector, the spans it rests on) existed only for as long as one sweep's objects
were alive in memory.

This module is `conflict_store.py`'s sibling and follows its shape deliberately: a `Protocol`, an
in-memory implementation for a dev run with no database, and a Postgres one; content-addressed
ids so a replayed sweep UPSERTS its own row instead of appending a second copy of one conclusion;
and a writer that logs and returns 0 on a database error rather than raising into the ingestion
path. Losing a stored signal costs a card. Raising costs the tenant their mail.

WHAT IS STORED AND WHAT IS POINTED AT
-------------------------------------
`extraction_ref` is a POINTER into `l1_extraction_results.processing_key`. The extraction is the
expensive artifact, it is already content-addressed, and it already lives exactly once; copying
it per signal would multiply the largest rows in the database by the number of signals each
email produced. Everything else on the row is stored WHOLE, and for the reason doc 07 gives:
`importance_components` and `confidence_vector` are judgements made at a moment, under weights
that will be re-tuned, and a row that pointed at today's weights would silently re-explain a
score made under last month's.

`envelope` is the round-trip half — `source`, `object_type`, `triage_lane`, `recipients`,
`versions`, `schema_version` — see migration 0089 for why it is an addition to the DDL doc 06
prints, and `docs/plans/L2_MISSING_UNIT_SPECS.md` §3 **A-13** for the fact that it is one.

PURITY. No clock: `occurred_at` is world time off the signal and `created_at` is the database's
own default, which is a write timestamp rather than a judgement. No float: every number here is
basis points or a `Money.minor_units` int, and both reach jsonb through pydantic's JSON mode
rather than through `float()`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Protocol

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.capture.signal_store")

#: The table migration 0089 creates. Named once so the erasure list, the store and the tests all
#: spell it the same way.
SIGNAL_TABLE = "qualified_signals"

#: The six envelope keys that make a stored row rebuildable into a `QualifiedEnterpriseSignal`.
#: A frozen tuple rather than an ad-hoc dict literal at the one call site, so a reader can see
#: what round-tripping actually requires and a missing key is a visible omission.
ENVELOPE_KEYS: tuple[str, ...] = ("source", "object_type", "triage_lane", "recipients",
                                  "versions", "schema_version")

_COLUMNS = ("signal_id, org_id, event_id, trace_id, signal_type, secondary_types, "
            "importance_bp, importance_components, importance_version, confidence_bp, "
            "confidence_vector, domain_hints, visibility, coverage_ready, extraction_ref, "
            "evidence_refs, conflict_ids, state, supersedes, expires_at, internal_kind, "
            "occurred_at, envelope, authority_rank, ingested_at, content_hash, "
            "qualification_reason, superseded_by")


def _jsonable(value: Any) -> Any:
    """Whatever this is, as something `json.dumps` accepts — and never via `float()`.

    Pydantic models go out through their own JSON mode, which is what keeps `Money.minor_units`
    an int and a `datetime` an ISO-8601 string rather than a POSIX float. Mappings and sequences
    recurse. Anything else is returned unchanged and left for `json.dumps` to refuse loudly,
    because a silent `str()` here is how a typed value becomes a sentence nobody can read back.
    """
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _dumps(value: Any) -> str:
    """One canonical spelling for every jsonb column: sorted keys, no incidental whitespace.

    Canonical because these rows are compared — by a test, by an operator diffing two replays,
    and by `on conflict do update`, which rewrites a column whose bytes differ even when its
    meaning does not. Key order is not meaning.
    """
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"))


def _loads(value: Any, fallback: Any) -> Any:
    """A jsonb column on the way back. Already-decoded (psycopg2 returns dicts and lists) is the
    common case; a text column from a driver that does not decode is the other."""
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):      # pragma: no cover - a column that is not JSON at all
        return fallback


@dataclass(frozen=True)
class QualifiedSignalRow:
    """One stored signal, in the shape the table holds it.

    Plain JSON structures rather than contract objects for `visibility`, `evidence_refs`,
    `domain_hints` and the two component maps — this type crosses the database boundary in BOTH
    directions, and a row read back out of jsonb must not have to assert that TODAY's contract
    still validates a row written under an older one. Re-validation is a reader's decision (see
    `rehydrate`), not the store's; a store that validated on read would make an old row
    unreadable on the day a contract gained a required field, which is the one thing a permanent
    record must survive.
    """

    signal_id: str
    org_id: str
    event_id: str
    trace_id: str
    signal_type: str
    importance_bp: int
    importance_version: str
    confidence_bp: int
    extraction_ref: str
    state: str
    occurred_at: datetime
    secondary_types: tuple[str, ...] = ()
    importance_components: Mapping[str, Any] = field(default_factory=dict)
    confidence_vector: Mapping[str, int] = field(default_factory=dict)
    domain_hints: tuple[Mapping[str, Any], ...] = ()
    visibility: Mapping[str, Any] = field(default_factory=dict)
    coverage_ready: bool | None = None
    evidence_refs: tuple[Mapping[str, Any], ...] = ()
    conflict_ids: tuple[str, ...] = ()
    supersedes: str | None = None
    expires_at: datetime | None = None
    internal_kind: str | None = None
    envelope: Mapping[str, Any] = field(default_factory=dict)
    #: ALG-14's authority, translated to the 0..4 scale `context.pipeline.FACT_CONF_BY_RANK` is
    #: keyed by, through `capture/validate/authority.to_legacy_rank` — the module's own stated
    #: "one sanctioned crossing" between the two scales. Stored rather than left to the reader
    #: because the two scales share the digits 0..4 and mean different things by them, so a
    #: consumer that re-derives it gets it wrong for four of the seven classes (usually as
    #: `rank - 1`) and silently demotes a signed contract to a CRM row. `None` on a row written
    #: before migration 0092, which is an honest absence rather than an invented 2.
    authority_rank: int | None = None
    #: The database's own write time. `None` on a row that has not been stored yet — the column
    #: defaults in SQL, so the publisher never has to read a clock to fill it.
    created_at: datetime | None = None
    #: Migration 0115 — the four provenance answers the seam used to drop. `None` on any row
    #: written before it, which is an honest absence: none of the four can be reconstructed
    #: afterwards, so backfilling them with a default would be inventing history.
    ingested_at: datetime | None = None
    content_hash: str | None = None
    qualification_reason: str | None = None
    #: The FORWARD half of the supersession link, written by `put` when the REPLACEMENT lands —
    #: never by the publisher, which is holding the new signal and not the old row.
    superseded_by: str | None = None

    def __post_init__(self) -> None:
        # The two range checks the table also carries. Here as well, because the in-memory store
        # has no CHECK constraints and a dev run must not be the place where a bad row first
        # becomes possible.
        for name in ("importance_bp", "confidence_bp"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10000:
                raise ValueError(f"{name} must be basis points 0..10000, got {value!r}")
        if not self.evidence_refs:
            raise ValueError(
                "evidence_refs is empty — V-4 refuses a claim with no receipt, so a row without "
                "one could only have come from a writer that skipped the publication gate")
        rank = self.authority_rank
        if rank is not None and (isinstance(rank, bool) or not isinstance(rank, int)
                                 or not 1 <= rank <= 4):
            raise ValueError(
                f"authority_rank must be a live key of FACT_CONF_BY_RANK (1..4) or None, got "
                f"{rank!r} — an ALG-14 ladder position stored here would raise a KeyError at the "
                "Layer 2 fact write, or silently mean a different tier")
        if self.supersedes is not None and self.supersedes == self.signal_id:
            raise ValueError(f"signal {self.signal_id} cannot supersede itself")
        if self.superseded_by is not None and self.superseded_by == self.signal_id:
            raise ValueError(f"signal {self.signal_id} cannot be superseded by itself")
        digest = self.content_hash
        if digest is not None and (len(digest) != 64
                                   or any(c not in "0123456789abcdef" for c in digest)):
            raise ValueError(
                f"content_hash must be 64 lowercase hex or None, got {digest!r} — an upper-cased "
                "or truncated digest compares unequal to the same content hashed by the "
                "extraction cache, which is the only comparison the column exists for")

    def as_params(self) -> dict[str, Any]:
        """The bind parameters for one insert. Built here rather than at the SQL so the column
        list and the values cannot drift out of step at a call site."""
        return {
            "sig": self.signal_id, "o": self.org_id, "ev": self.event_id,
            "tr": self.trace_id, "st": self.signal_type,
            "sec": _dumps(list(self.secondary_types)),
            "imp": self.importance_bp, "comp": _dumps(dict(self.importance_components)),
            "iver": self.importance_version, "conf": self.confidence_bp,
            "cvec": _dumps(dict(self.confidence_vector)),
            "dom": _dumps(list(self.domain_hints)), "vis": _dumps(dict(self.visibility)),
            "cov": self.coverage_ready, "xref": self.extraction_ref,
            "ev_refs": _dumps(list(self.evidence_refs)),
            "cids": _dumps(list(self.conflict_ids)), "state": self.state,
            "sup": self.supersedes, "exp": self.expires_at, "kind": self.internal_kind,
            "occ": self.occurred_at, "env": _dumps(dict(self.envelope)),
            "arank": self.authority_rank, "ing": self.ingested_at, "chash": self.content_hash,
            "qreason": self.qualification_reason, "supby": self.superseded_by,
        }


def _to_row(row: Any) -> QualifiedSignalRow:
    """One database row as the dataclass. Every jsonb column decoded, nothing revalidated."""
    return QualifiedSignalRow(
        signal_id=row.signal_id, org_id=row.org_id, event_id=row.event_id,
        trace_id=row.trace_id, signal_type=row.signal_type,
        secondary_types=tuple(_loads(row.secondary_types, [])),
        importance_bp=row.importance_bp,
        importance_components=_loads(row.importance_components, {}),
        importance_version=row.importance_version, confidence_bp=row.confidence_bp,
        confidence_vector=_loads(row.confidence_vector, {}),
        domain_hints=tuple(_loads(row.domain_hints, [])),
        visibility=_loads(row.visibility, {}), coverage_ready=row.coverage_ready,
        extraction_ref=row.extraction_ref,
        evidence_refs=tuple(_loads(row.evidence_refs, [])),
        conflict_ids=tuple(_loads(row.conflict_ids, [])), state=row.state,
        supersedes=row.supersedes, expires_at=row.expires_at,
        internal_kind=row.internal_kind, occurred_at=row.occurred_at,
        envelope=_loads(getattr(row, "envelope", None), {}),
        authority_rank=getattr(row, "authority_rank", None),
        ingested_at=getattr(row, "ingested_at", None),
        content_hash=getattr(row, "content_hash", None),
        qualification_reason=getattr(row, "qualification_reason", None),
        superseded_by=getattr(row, "superseded_by", None))


def _link_supersessions(rows: Sequence[QualifiedSignalRow], *, get, set_link) -> int:
    """Write the FORWARD half of every supersession this batch declares. Returns links written.

    ALG-19 decides that a new signal replaces an old one and stamps `supersedes` on the NEW row —
    which is the only direction the publisher can know, because it is holding the replacement and
    not the thing replaced. From the old id there was then no way to reach the new one without
    scanning the table for a row pointing at you, and "what replaced this?" is the ordinary
    question a founder asks about a renewal that moved.

    Written HERE, at the store's own write seam, for the reason `finalize_l1` exists: both capture
    doors and every replay go through `put`, so a link written at a call site would be a link some
    door forgets. Only ever set on a row that EXISTS — a signal superseding something this tenant
    no longer holds (erased, or published before the column did) leaves no orphan pointer.
    """
    written = 0
    for row in rows:
        old = row.supersedes
        if not old or old == row.signal_id:
            continue
        held = get((row.org_id, old))
        # Absent, or already linked. A signal replaced twice was replaced by the EARLIER one and
        # THAT one was then replaced; overwriting reports the chain's last link as its first and
        # loses the middle. The Postgres side spells the same rule as `where superseded_by is
        # null`, which is also what makes a replay idempotent.
        if held is None or getattr(held, "superseded_by", None) is not None:
            continue
        set_link((row.org_id, old), row.signal_id)
        written += 1
    return written


class SignalStore(Protocol):
    """What the publisher needs from a signal store, and nothing more.

    `put` takes a SEQUENCE because a sweep publishes a page at a time and one transaction per
    signal would make a 200-message sync 200 round trips.
    """

    def put(self, rows: Sequence[QualifiedSignalRow]) -> int: ...

    def apply_lifecycle(self, records: Sequence[Any]) -> int: ...

    def get(self, org_id: str, signal_id: str) -> QualifiedSignalRow | None: ...

    def list(self, org_id: str, *, state: str | None = "active",
             event_id: str | None = None, limit: int = 100) -> list[QualifiedSignalRow]: ...


class InMemorySignalStore:
    """A dict that lives for the process — a dev run with no database, and the hermetic tests.

    Keyed by `(org_id, signal_id)` rather than by `signal_id` alone even though the real table's
    primary key is the id by itself: the id is a digest over the org among other things, so the
    two agree, and keying by the pair here means a test that reuses an id across two orgs finds
    the tenant boundary broken in the store rather than three layers downstream.
    """

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], QualifiedSignalRow] = {}

    def put(self, rows: Sequence[QualifiedSignalRow]) -> int:
        for row in rows:
            self._rows[(row.org_id, row.signal_id)] = row
        _link_supersessions(rows, get=self._rows.get, set_link=self._set_link)
        return len(rows)

    def _set_link(self, key: tuple[str, str], replacement: str) -> None:
        held = self._rows.get(key)
        if held is not None:
            self._rows[key] = replace(held, superseded_by=replacement)

    def apply_lifecycle(self, records: Sequence[Any]) -> int:
        """ALG-19's verdict about signals ALREADY stored — see the Postgres store's version."""
        from genios_engine.capture.esqe.lifecycle import ACTIVE
        moved = 0
        for record in records or ():
            key = (getattr(record, "org_id", None), getattr(record, "signal_id", None))
            state = getattr(record, "state", None)
            held = self._rows.get(key)
            if held is None or state is None or state == ACTIVE or held.state == state:
                continue
            self._rows[key] = replace(
                held, state=state, supersedes=getattr(record, "supersedes", held.supersedes),
                expires_at=getattr(record, "expires_at", held.expires_at))
            moved += 1
        return moved

    def get(self, org_id: str, signal_id: str) -> QualifiedSignalRow | None:
        return self._rows.get((org_id, signal_id))

    def list(self, org_id: str, *, state: str | None = "active",
             event_id: str | None = None, limit: int = 100) -> list[QualifiedSignalRow]:
        rows = [r for r in self._rows.values()
                if r.org_id == org_id
                and (state is None or r.state == state)
                and (event_id is None or r.event_id == event_id)]
        # The same order `qs_by_org_state` gives: biggest first, then by id so two equal scores
        # do not swap places between two reads of an unchanged store.
        rows.sort(key=lambda r: (-r.importance_bp, r.signal_id))
        return rows[:limit]

    def erase(self, org_id: str) -> int:
        """What `/reset` does to the real table, for a dev run. Present so the in-memory path
        cannot be the one where a tenant's signals outlive their deletion."""
        keys = [k for k in self._rows if k[0] == org_id]
        for key in keys:
            del self._rows[key]
        return len(keys)


class PostgresSignalStore:
    """The real store. UPSERT by `signal_id`, and never raises into a sweep.

    The conflict clause rewrites the JUDGEMENT columns and leaves `created_at` alone: a replayed
    sweep re-states what it concluded, and the row keeps the moment it first crossed the
    boundary. Rewriting `created_at` would make every replay look like a fresh signal to any
    consumer ordering by it — which is the whole of L2's "what is new since I last read".
    """

    def __init__(self, database_url: str) -> None:
        from genios_engine.platform.db import get_engine
        self._engine = get_engine(database_url)

    def put(self, rows: Sequence[QualifiedSignalRow]) -> int:
        from sqlalchemy import text
        if not rows:
            return 0
        try:
            with self._engine.begin() as conn:
                for row in rows:
                    conn.execute(text(
                        f"insert into {SIGNAL_TABLE} ({_COLUMNS}) values ("
                        " :sig, :o, :ev, :tr, :st, cast(:sec as jsonb), :imp,"
                        " cast(:comp as jsonb), :iver, :conf, cast(:cvec as jsonb),"
                        " cast(:dom as jsonb), cast(:vis as jsonb), :cov, :xref,"
                        " cast(:ev_refs as jsonb), cast(:cids as jsonb), :state, :sup, :exp,"
                        " :kind, :occ, cast(:env as jsonb), :arank, :ing, :chash, :qreason,"
                        " :supby) "
                        "on conflict (signal_id) do update set "
                        "secondary_types=excluded.secondary_types, "
                        "importance_bp=excluded.importance_bp, "
                        "importance_components=excluded.importance_components, "
                        "importance_version=excluded.importance_version, "
                        "confidence_bp=excluded.confidence_bp, "
                        "confidence_vector=excluded.confidence_vector, "
                        "domain_hints=excluded.domain_hints, "
                        "visibility=excluded.visibility, "
                        "coverage_ready=excluded.coverage_ready, "
                        "extraction_ref=excluded.extraction_ref, "
                        "evidence_refs=excluded.evidence_refs, "
                        "conflict_ids=excluded.conflict_ids, "
                        "state=excluded.state, supersedes=excluded.supersedes, "
                        "expires_at=excluded.expires_at, "
                        "internal_kind=excluded.internal_kind, "
                        "occurred_at=excluded.occurred_at, envelope=excluded.envelope, "
                        "authority_rank=excluded.authority_rank, "
                        "ingested_at=excluded.ingested_at, "
                        "content_hash=excluded.content_hash, "
                        "qualification_reason=excluded.qualification_reason, "
                        # NOT `excluded.superseded_by`. The replayed publish is holding the
                        # signal, which never knows what replaced it; the link is written by the
                        # UPDATE below when the replacement lands. Taking it from `excluded`
                        # would erase that link on every re-publish of the same sweep.
                        "superseded_by=coalesce(qualified_signals.superseded_by, "
                        "excluded.superseded_by)"),
                        row.as_params())
                # The forward half of the link, in the SAME transaction as the rows that declare
                # it: a commit that stored the replacement and not the pointer to it would leave
                # the table permanently half-linked, and nothing downstream would ever notice.
                # `where superseded_by is null` makes it idempotent under replay and keeps the
                # FIRST replacement — a signal replaced twice was replaced by the earlier one and
                # then that one was replaced, which is what the chain has to say.
                for row in rows:
                    if not row.supersedes or row.supersedes == row.signal_id:
                        continue
                    conn.execute(text(
                        f"update {SIGNAL_TABLE} set superseded_by = :new "
                        "where org_id = :o and signal_id = :old and superseded_by is null"),
                        {"new": row.signal_id, "o": row.org_id, "old": row.supersedes})
        except Exception as exc:      # noqa: BLE001 — a signal store never kills a sweep
            _log.warning("could not store %d qualified signal(s) for org=%s: %s",
                         len(rows), rows[0].org_id, exc)
            return 0
        return len(rows)

    def apply_lifecycle(self, records: Sequence[Any]) -> int:
        """ALG-19's verdict, carried onto the rows this table ALREADY holds. Returns rows moved.

        WHY THIS EXISTS. `sweep_lifecycle` ages a tenant's signals and `PostgresLifecycleStore`
        writes what it decided to `signal_lifecycle`. `publish_sweep` writes THIS sweep's signals
        here. Nothing joined the two — and the signals ALG-19 supersedes or expires are, by
        definition, the ones an EARLIER sweep published. So `signal_lifecycle` said `superseded`
        while `qualified_signals` still said `active`, and `context/situation_bso.
        gather_l1_signals` — which filters the live set on THIS table's `state` — kept letting a
        replaced signal set a live situation's importance. Migration 0093 names the cost in its
        own first paragraph: *"a renewal signal about a contract that was cancelled is dead, and
        must be marked so"*.

        UPDATE ONLY, never insert. A lifecycle row exists for every signal the sweep normalized;
        a row exists HERE only for the ones the publication gate emitted. Inserting would let a
        signal V-1 refused reappear as published because it aged.

        `active` records are skipped rather than written. This function carries a RETIREMENT; it
        is not a second opinion about liveness, and re-asserting `active` would reopen a row some
        other pass had closed. Terminal states only, and only downwards.

        Never raises, on `put`'s terms: losing this write costs a stale signal one more sweep of
        life, and raising costs the tenant their mail.
        """
        from sqlalchemy import text

        from genios_engine.capture.esqe.lifecycle import ACTIVE
        moved = 0
        pending = [r for r in (records or ())
                   if getattr(r, "state", None) and getattr(r, "state") != ACTIVE
                   and getattr(r, "org_id", None) and getattr(r, "signal_id", None)]
        if not pending:
            return 0
        try:
            with self._engine.begin() as conn:
                for record in pending:
                    result = conn.execute(text(
                        f"update {SIGNAL_TABLE} set state=:state, supersedes=:sup, "
                        "expires_at=coalesce(:exp, expires_at) "
                        "where org_id=:o and signal_id=:sig and state=:live"),
                        {"state": record.state, "sup": getattr(record, "supersedes", None),
                         "exp": getattr(record, "expires_at", None),
                         "o": record.org_id, "sig": record.signal_id, "live": ACTIVE})
                    moved += int(result.rowcount or 0)
        except Exception as exc:      # noqa: BLE001 — a lifecycle write never kills a sweep
            _log.warning("could not carry %d lifecycle verdict(s) onto %s for org=%s: %s",
                         len(pending), SIGNAL_TABLE, pending[0].org_id, exc)
            return 0
        return moved

    def get(self, org_id: str, signal_id: str) -> QualifiedSignalRow | None:
        from sqlalchemy import text
        with self._engine.connect() as conn:
            row = conn.execute(text(
                f"select {_COLUMNS} from {SIGNAL_TABLE} where org_id=:o and signal_id=:sig"),
                {"o": org_id, "sig": signal_id}).first()
        return _to_row(row) if row is not None else None

    def list(self, org_id: str, *, state: str | None = "active",
             event_id: str | None = None, limit: int = 100) -> list[QualifiedSignalRow]:
        from sqlalchemy import text
        params: dict[str, Any] = {"o": org_id, "n": max(1, int(limit))}
        clause = ""
        if state is not None:
            clause += " and state=:st"
            params["st"] = state
        if event_id is not None:
            clause += " and event_id=:ev"
            params["ev"] = event_id
        with self._engine.connect() as conn:
            rows = conn.execute(text(
                f"select {_COLUMNS} from {SIGNAL_TABLE} where org_id=:o{clause} "
                "order by importance_bp desc, signal_id limit :n"), params).all()
        return [_to_row(r) for r in rows]


# =============================================================================================
# AGE — what a stored signal is still worth when somebody reads it back
# =============================================================================================
@dataclass(frozen=True)
class AgedSignal:
    """One stored row, read at an instant, with its confidence aged to that instant.

    A WRAPPER rather than a mutated row, and that is the whole design. `confidence_bp` on the
    table is a JUDGEMENT MADE AT A MOMENT — ALG-13 composed it from sources whose own
    confidences were themselves aged against the sweep's frozen instant — and a store that
    rewrote the column on every read would destroy the composition it is a record of, would make
    two reads of one unchanged row disagree, and would age the same signal twice on a replay.

    So the row keeps what was composed and the reader is told what it is worth NOW. Which of the
    two a surface should show is not the store's decision: a card ranks on the aged number, and
    a provenance panel explaining "we were 82% sure in April" needs the stored one.
    """

    row: QualifiedSignalRow
    #: Whole days between the signal's world time and the read instant. Never negative — see
    #: `age_in_days`, which floors a future-dated signal at 0 rather than letting a clock skew
    #: manufacture confidence.
    days_old: int
    #: What the confidence is worth at `days_old`, in basis points.
    confidence_bp: int

    @property
    def stored_confidence_bp(self) -> int:
        """What ALG-13 actually composed, before age. The number a "why" panel quotes."""
        return self.row.confidence_bp

    @property
    def decayed_bp(self) -> int:
        """How many basis points age has removed. The delta rather than the ratio, because the
        ratio is the float this whole layer is written in integers to avoid."""
        return self.row.confidence_bp - self.confidence_bp


def age_signals(rows: Sequence[QualifiedSignalRow], *, eval_time: datetime,
                decay_bp_per_day: int | None = None) -> tuple[AgedSignal, ...]:
    """Every row, aged to `eval_time` — the read that stops a stored signal being served at the
    confidence it had the day it was composed.

    THE DEFECT THIS CLOSES. `capture/validate/confidence.decay` is ALG-13's age term and it ran
    in exactly one place: INSIDE a composition, over the sources a signal was being built from.
    Once composed, the number was frozen in `qualified_signals` and every read of it — every
    card, every ranking, every "what does the engine believe about this tenant" — got April's
    certainty in June. Freshness is the one axis of the confidence vector that keeps moving
    after the write, so it is the one that has to be applied on the read.

    `decay` is CALLED, not re-derived: the rate, the floor and the integer arithmetic live in
    L1.5.7 and a second copy of that curve here would be two answers to how fast evidence goes
    stale — one used while composing and one used while reading, disagreeing about the same day.

    `eval_time` is a PARAMETER. No clock in this module: the same rows read against the same
    instant give the same numbers, so a replay, a test and a support engineer looking at
    yesterday all see one answer. The route above is where the clock lives.
    """
    from genios_engine.capture.validate.confidence import DEFAULT_AGE_DECAY_BP_PER_DAY
    from genios_engine.capture.validate.confidence import age_in_days, decay
    rate = DEFAULT_AGE_DECAY_BP_PER_DAY if decay_bp_per_day is None else decay_bp_per_day
    aged: list[AgedSignal] = []
    for row in rows:
        days = age_in_days(row.occurred_at, eval_time=eval_time)
        aged.append(AgedSignal(
            row=row, days_old=days,
            confidence_bp=decay(row.confidence_bp, days_old=days, decay_bp_per_day=rate)))
    return tuple(aged)


__all__ = ["ENVELOPE_KEYS", "SIGNAL_TABLE", "AgedSignal", "InMemorySignalStore",
           "PostgresSignalStore", "QualifiedSignalRow", "SignalStore", "age_signals"]
