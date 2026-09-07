"""L2.4 · the ONE writer every derived-fact producer publishes through. Point-in-time safe.

**The defect this module exists to delete.** Four modules — `comparator`, `anomaly`,
`correlation_dependency`, `correlation_timeline` — each wrote their own copy of one upsert whose
conflict clause ended `valid_from = excluded.valid_from`. That single assignment MOVES the
window of a row that already exists, so a cohort position published in March and swept again in
September reads back as `[September, inf)` and `read_graph(as_of=March)` returns **nothing** —
about a fact GeniOS itself published in March. Doc 02's acceptance row, *"replaying a March
decision against as_of=March reproduces its inputs"*, therefore failed for exactly the class of
facts L2.4 exists to produce, and it failed silently: X7 shipped the as-of reader in the same
wave, which is what turns a harmless-looking recompute into a correctness bug.

`correlation_dependency`'s copy was worse. Its conflict clause also set `valid_to = null`, so a
blocking stated in March, resolved in April and re-stated in August collapsed into ONE row
reading `[August, inf)` — while the docstring six lines above it argued that a hard delete
"would make every as-of read of last week silently change its answer with no way to recover it".
The reopen did precisely that, to its own history.

**The rule this module encodes instead — `valid_from` NEVER moves.**

* Same value as the open row: **nothing is written at all.** Not a touch, not an `occurred_at`
  bump. A sweep is not evidence; a sweep that agrees with what is stored has produced no new
  fact, and a no-op leaves no dead tuple behind either.
* Value changed, still inside the same PERIOD: the period's row is revised in place, `valid_from`
  untouched. The period is the grain (below), so within it the latest reading IS the period's
  answer, and opening a row per intra-period change is the unbounded growth the bound forbids.
* Value changed in a LATER period: the open row is CLOSED (`valid_to = :eval_time`,
  `status = 'superseded'`) and a new, period-keyed row opens at `:eval_time`. March keeps its
  window, so `read_graph(as_of=March)` keeps its answer, and `as_of=now` sees the new one.
* A fact that is true again after being closed does NOT reopen the old row — a later period is a
  different key, so the earlier stint survives as its own row and the timeline reads
  `[March, April) ... [August, inf)` rather than one lie spanning both.

**The bound, stated as arithmetic, because this is the property the four modules' docstrings
defend** (`expertise_packages` reached 181 MB by appending a row per run and put this database
into read-only). The version id is `{prefix}{node}:{field}:{period_start}` at ISO-WEEK grain —
the grain `metric_history` and `peer_baselines` already use — so:

    rows per (node, field) per year  <=  52, and equals the number of ISO WEEKS IN WHICH THE
    VALUE ACTUALLY CHANGED — not the number of sweeps.

A value that never changes is ONE row for the life of the tenant no matter how often the drain
runs; a value that changes every single week is 52. Compare the shape this replaces: one row per
(node, field) — correct in size, and wrong about every instant except the last one.

GAP FLAG — there is NO retention pass here, and that is deliberate rather than forgotten. The
reviewer's correction proposed pruning closed rows on `metric_history`'s 24-month horizon, but
`metric_history` and `peer_baselines` are tables of their own, and `graph_facts` is governed by
doc 02's HARD RULE 1: *soft delete only — a hard delete makes history unreadable and there is no
way to recover it later* — asserted by the scan in `test_point_in_time.py`, which reads this whole
package looking for a hard DELETE that names a graph table, this docstring included (which is why
the phrase is not spelled out here). So the bound
this module offers is the one it can honour without breaking that rule: growth proportional to
CHANGES rather than to sweeps, capped at one row per (node, field) per ISO week. A retention
policy for `graph_facts` as a whole — which is what the 24-month horizon would actually be — is
that table's question, not this writer's, and inventing one here would be a hard delete against
the graph smuggled in as a helper.

**`visibility_scope` is a REQUIRED argument and has no default.** All four call sites hardcoded
`'org'` on facts derived from OTHER nodes' evidence, and `contracts/visibility.py` states the law
they were quietly widening: *"the audience of a derived insight can never be wider than the
audience of the evidence it came from."* A cohort position carries peers' readings and a
lookalike carries peers' matched traits onto the subject, so `'org'` there is a claim, not a
default — and a claim repeated as a literal in four files is a scope nobody can grep for. Making
it a required keyword does not make the answer right; it makes the answer STATED, at the one seam
where a reviewer can find every caller by looking at this function's callers.

**No clocks.** `eval_time` is a parameter, every timestamp written comes from it, and this module
never calls `now()` in Python or in SQL — the same discipline the rest of L2.4 holds to.

**No new table**, so nothing is added to `api/account_routes._ORG_SCOPED_TABLES`: `graph_facts`
is already on it and these rows are erased with the tenant by the entry already there.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Iterable, Sequence

from sqlalchemy import text

from genios_engine.contracts.validators import require_aware, require_text
from genios_engine.contracts.visibility import SCOPES
from genios_engine.context.analytic.history import MetricGrain, period_start

#: The table every derived fact lands in. Named once so the writer, the prune and the tests spell
#: it the same way.
FACT_TABLE = "graph_facts"

#: The versioning grain. ISO week, because that is what `metric_history` (`MetricGrain.WEEK`) and
#: `peer_baselines` (`BASELINE_GRAIN`) already key on: a derived fact whose grain was finer than
#: its own inputs' would carry a precision the inputs cannot support, and one whose grain was
#: coarser would hide a real month-over-month change inside a single row.
DERIVED_FACT_GRAIN = MetricGrain.WEEK

#: What the four writers already stamp. Kept as defaults rather than as literals in the SQL so a
#: caller with a genuinely different confidence can say so, in basis points like everything else.
DEFAULT_AUTHORITY_RANK = 100
DEFAULT_CONFIDENCE_BP = 9_000


class PublishAction(str, Enum):
    """What one call actually did — the accounting a sweep needs to report honest counts.

    The distinction between `UNCHANGED` and the other three is the whole point of the module: a
    sweep that reports "wrote 4,000 facts" when 3,990 of them were re-confirmations of rows it
    had already written is the metric that made the old writer's amplification invisible.
    """

    #: No row existed under this prefix for this (node, field): a first stint opened.
    INSERTED = "inserted"
    #: The open row already holds this exact value. NOTHING was written.
    UNCHANGED = "unchanged"
    #: The value changed within the open row's own period: that row was revised in place and its
    #: `valid_from` was left where it was.
    REVISED = "revised"
    #: The value changed in a later period: the open row was closed and a new one opened.
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class PublishedFact:
    """What the caller needs back: the id that is now current, and what happened to get there.

    `version_id` is returned on EVERY branch, `UNCHANGED` included, because the two callers that
    close their stale rows (`correlation_dependency`, `correlation_timeline`) build a `keep` list
    of the ids that are still true. Under period keying that id is not derivable from the node and
    field alone — an unchanged fact keeps the id of the period it was FIRST published in — so a
    caller that reconstructed it would close the row it meant to keep.
    """

    version_id: str
    action: PublishAction
    valid_from: datetime
    #: The row that was closed to make room, on the `SUPERSEDED` branch only.
    closed_version_id: str | None = None

    @property
    def wrote(self) -> bool:
        """Did this call change the database at all? `UNCHANGED` is the no-op."""
        return self.action is not PublishAction.UNCHANGED


def derived_fact_version_id(version_prefix: str, subject_node_id: str, field: str,
                            period: datetime) -> str:
    """The deterministic id of one (node, field) stint. Period-keyed — see the module docstring.

    `:` as the separator, and the period rendered as a date, so the id is greppable and a human
    reading `graph_facts` can see which week a row belongs to without joining anything. The
    prefix is passed whole (`"fv_cmp_"`, `"fv_dep:"`) and stays a true PREFIX of the id, which is
    what keeps the modules' existing `left(fact_version_id, n) = :prefix` closes working.
    """
    return f"{version_prefix}{subject_node_id}:{field}:{period.date().isoformat()}"


def _payload(value: Any) -> str:
    """Canonical JSON. `sort_keys` so the same value serialises identically on every sweep — the
    comparison below is `jsonb =`, but a stable body also means a REVISE writes the bytes the
    previous sweep would have written, and a diff of two rows is a diff of the fact."""
    return json.dumps(value, default=str, sort_keys=True)


def _utc(instant: datetime) -> datetime:
    """Postgres hands a `timestamptz` back in the session's timezone. `period_start` floors to a
    calendar day, so flooring a `+05:30` reading of the same instant lands on a different ISO
    week — the one way this module could disagree with itself about which period a row is in."""
    return require_aware(instant, "instant").astimezone(timezone.utc)


def _period_of(instant: datetime, grain: MetricGrain) -> datetime:
    return period_start(_utc(instant), grain)


def _scope(value: Any) -> str:
    """The required argument, checked against the four scopes `contracts/visibility` defines.

    A typo'd scope is not a widening in itself, but nothing downstream reads this column through
    `Visibility`, so `'orgs'` would sit in the table forever describing an audience no reader
    recognises. Checked here, at the seam that writes it.
    """
    scope = require_text(value, "visibility_scope")
    if scope not in SCOPES:
        raise ValueError(f"unknown visibility_scope {scope!r}; expected one of {SCOPES} — the "
                         "audience of a derived insight can never be wider than the audience of "
                         "the evidence it came from, so it is stated, never defaulted")
    return scope


def _confidence(confidence_bp: int) -> Decimal:
    """Basis points in, `numeric(4,3)` out, with no float anywhere on the path. `scaleb` shifts
    the decimal exponent — it is not a division, so 9000 bp is exactly `0.9000`."""
    if isinstance(confidence_bp, bool) or not isinstance(confidence_bp, int):
        raise TypeError("confidence_bp must be integer basis points")
    if not 0 <= confidence_bp <= 10_000:
        raise ValueError("confidence_bp must be between 0 and 10000")
    return Decimal(confidence_bp).scaleb(-4)


_OPEN_ROW_SQL = text(
    f"select fact_version_id, valid_from, (value = cast(:v as jsonb)) as same "
    f"from {FACT_TABLE} "
    "where org_id = :o and subject_node_id = :n and field = :f and valid_to is null "
    "  and left(fact_version_id, :pl) = :p "
    "order by valid_from desc, fact_version_id desc limit 1 for update")

#: `valid_from` is deliberately ABSENT from the update list. That one omission is the whole fix:
#: the conflict path may correct the body of a row, and may reopen one inside its own period, but
#: it may never move the instant the row began to be true.
_UPSERT_SQL = text(
    f"insert into {FACT_TABLE} (fact_version_id, fact_id, org_id, subject_node_id, field, "
    "value, value_type, status, authority_rank, confidence, occurred_at, valid_from, valid_to, "
    "visibility_scope) values "
    "(:vid, :fid, :o, :n, :f, cast(:v as jsonb), :vt, 'active', :rank, :conf, :occ, :now, null, "
    ":scope) "
    "on conflict (fact_version_id) do update set value = excluded.value, "
    "occurred_at = excluded.occurred_at, value_type = excluded.value_type, "
    "visibility_scope = excluded.visibility_scope, valid_to = null, status = 'active' "
    "returning valid_from")

_REVISE_SQL = text(
    f"update {FACT_TABLE} set value = cast(:v as jsonb), occurred_at = :occ, "
    "value_type = :vt, visibility_scope = :scope, confidence = :conf "
    "where fact_version_id = :vid and org_id = :o returning valid_from")

_CLOSE_SQL = text(
    f"update {FACT_TABLE} set valid_to = :now, status = 'superseded' "
    "where fact_version_id = :vid and org_id = :o and valid_to is null")


def publish_derived_fact(target, *, org_id: str, subject_node_id: str, field: str, value: Any,
                         eval_time: datetime, value_type: str, visibility_scope: str,
                         version_prefix: str, occurred_at: datetime | None = None,
                         fact_id: str | None = None,
                         authority_rank: int = DEFAULT_AUTHORITY_RANK,
                         confidence_bp: int = DEFAULT_CONFIDENCE_BP,
                         grain: MetricGrain = DERIVED_FACT_GRAIN) -> PublishedFact:
    """Publish one derived fact so that history survives it. THE function the four writers call.

    `target` is a connection or an engine: inside a sweep it is the transaction the caller already
    owns, so the close and the insert commit together and a sweep cannot close the old answer and
    then fail to write the new one. Given an engine, one transaction is opened here.

    The open row is selected `for update`, which is what serialises two sweeps racing on the same
    (node, field): without it both could read "changed", both close, and the loser's insert would
    open a second row on a field that already had one. Two concurrent FIRST writes cannot race —
    the id is deterministic, so one of them takes the conflict path.

    The lookup is scoped by `version_prefix` as well as by (org, node, field). A module may only
    ever close its own rows; an open row on the same field written by something else is another
    writer's business and is left exactly alone.

    LEGACY ROWS ARE ABSORBED, not orphaned. A row written by the old id shape
    (`fv_cmp_{node}_{field}`, no period) still matches the prefix and the (org, node, field)
    lookup, so it is found as the open stint and is either left alone (same value) or closed
    properly the first time the value moves. No migration, and no second open row on the field.

    Refuses a `eval_time` that falls in an EARLIER period than the open row's. A derived writer
    replaying backwards would have to insert a row whose window precedes one that is already open,
    which is not a history this table can express — and silently accepting it is how a backfill
    turns into the same rewrite this module was built to stop.
    """
    at = require_aware(eval_time, "eval_time")
    occurred = require_aware(occurred_at, "occurred_at") if occurred_at is not None else at
    scope = _scope(visibility_scope)
    prefix = require_text(version_prefix, "version_prefix")
    node = require_text(subject_node_id, "subject_node_id")
    name = require_text(field, "field")
    body = _payload(value)
    period = _period_of(at, grain)
    version_id = derived_fact_version_id(prefix, node, name, period)
    params = {"vid": version_id, "fid": fact_id or f"{prefix}{node}:{name}", "o": org_id,
              "n": node, "f": name, "v": body, "vt": require_text(value_type, "value_type"),
              "rank": int(authority_rank), "conf": _confidence(confidence_bp), "occ": occurred,
              "now": at, "scope": scope}

    if hasattr(target, "begin") and not hasattr(target, "execute"):
        with target.begin() as conn:                       # an engine: one transaction, here
            return _publish(conn, params, period=period, grain=grain, at=at, prefix=prefix)
    return _publish(target, params, period=period, grain=grain, at=at, prefix=prefix)


def _publish(conn, params: dict, *, period: datetime, grain: MetricGrain, at: datetime,
             prefix: str) -> PublishedFact:
    """The four branches. Split out so the engine and the connection forms cannot diverge."""
    open_row = conn.execute(_OPEN_ROW_SQL, {"o": params["o"], "n": params["n"], "f": params["f"],
                                            "v": params["v"], "pl": len(prefix),
                                            "p": prefix}).first()
    if open_row is None:
        valid_from = conn.execute(_UPSERT_SQL, params).scalar()
        return PublishedFact(params["vid"], PublishAction.INSERTED, _utc(valid_from))

    if open_row.same:
        # THE IDEMPOTENCY BRANCH, and it writes NOTHING. The row already says this; a sweep that
        # agrees with what is stored has produced no fact, and touching the row would move nothing
        # a reader can see while leaving a dead tuple for every sweep of the tenant's life.
        return PublishedFact(str(open_row.fact_version_id), PublishAction.UNCHANGED,
                             _utc(open_row.valid_from))

    open_period = _period_of(open_row.valid_from, grain)
    if open_period > period:
        raise ValueError(
            f"{params['f']} on {params['n']} already has an open row from "
            f"{open_period.date().isoformat()}, which is AFTER this call's period "
            f"{period.date().isoformat()} — a derived writer replayed backwards would have to "
            "open a window before one that is already open, which is the rewrite this writer "
            "exists to prevent")
    if open_period == period:
        # Same period, different value: the period is the grain, so the latest reading IS this
        # period's answer. Revised in place, `valid_from` untouched — a second row per
        # intra-period change is the per-sweep growth the bound forbids, and no as-of read is
        # promised at a finer resolution than the grain the inputs are sampled at.
        params_revise = dict(params, vid=str(open_row.fact_version_id))
        valid_from = conn.execute(_REVISE_SQL, params_revise).scalar()
        return PublishedFact(str(open_row.fact_version_id), PublishAction.REVISED,
                             _utc(valid_from))

    conn.execute(_CLOSE_SQL, {"vid": str(open_row.fact_version_id), "o": params["o"], "now": at})
    valid_from = conn.execute(_UPSERT_SQL, params).scalar()
    return PublishedFact(params["vid"], PublishAction.SUPERSEDED, _utc(valid_from),
                         closed_version_id=str(open_row.fact_version_id))


_CLOSE_STALE_SQL = text(
    f"update {FACT_TABLE} set valid_to = :now, status = 'superseded' "
    "where org_id = :o and left(fact_version_id, :pl) = :p and valid_to is null "
    "  and not (fact_version_id = any(cast(:keep as text[])))")


def close_derived_facts(conn, *, org_id: str, version_prefix: str, keep: Iterable[str],
                        eval_time: datetime) -> int:
    """Close this module's open rows that this sweep did NOT publish. The other half of the shape.

    `correlation_dependency` and `correlation_timeline` publish "what is true now" and must retire
    what stopped being true. Closed, never deleted: `valid_to` is what the whole graph means by
    "stopped being true", and a hard delete would make every as-of read of last week silently
    change its answer.

    `keep` is the ids `publish_derived_fact` RETURNED, not ids the caller rebuilt — under period
    keying an unchanged fact keeps the id of the period it was first published in, so a
    reconstructed id would close exactly the rows that are still true.
    """
    at = require_aware(eval_time, "eval_time")
    prefix = require_text(version_prefix, "version_prefix")
    kept: Sequence[str] = list(keep)
    return conn.execute(_CLOSE_STALE_SQL, {"now": at, "o": org_id, "pl": len(prefix),
                                           "p": prefix, "keep": kept}).rowcount


__all__ = ["DEFAULT_AUTHORITY_RANK", "DEFAULT_CONFIDENCE_BP", "DERIVED_FACT_GRAIN", "FACT_TABLE",
           "PublishAction", "PublishedFact", "close_derived_facts", "derived_fact_version_id",
           "publish_derived_fact"]
