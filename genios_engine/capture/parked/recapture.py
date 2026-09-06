"""L1.3.8-U3 · the THIRD drain — parks that only a re-derivation or a later capture can settle.

`drain.py` split the parked queue into two classes and stated the law that binds them:

    A code in neither set is worse than an unhandled one: `drain_parked` counts it into
    `by_reason` and then walks past it, `parked_aging` labels it ``"terminal"`` — a claim nobody
    made — … and `read_aging`, which IS the G2 metric in `scripts/l1_s1_report.py`, filters on
    this same set. So the documents sit at ``status='pending'`` forever while every surface that
    could show them reads clean.

That law was enforced for ``DOC-*`` only. The gate parks under two more codes that neither class
claims, and both were doing exactly what the paragraph describes:

  ``visibility_unknown``  (`gate/gate.py` S0.6) — no rule in `capture/visibility_rules.py` could
        name who could see the original, so the event was held rather than published under a
        guessed audience. The retained ROW answers it (source, actor, recipients, internal_kind
        are all columns), but only if something RE-DERIVES it. `drain_parked` does not derive
        anything: it flips ``source_events.outcome`` to ``emitted`` and hands the stored row to
        L2. Doing that here would publish an event whose audience is still unnamed — the precise
        thing the park exists to prevent — so `RE_ADJUDICABLE` is not merely unhelpful for this
        code, it is wrong.

  ``MUT-01``  (`gate/rules.py::content_integrity_rule`) — a MUTABLE object arrived with no
        version stamp, so versions of it cannot be told apart. Re-emitting it is wrong for the
        same reason and worse: the whole failure MUT-01 names is that the object freezes at its
        first-seen state, and re-emitting the frozen copy is publishing that stale state on
        purpose. Nor is it a refetch: the payload is complete, it is the IDENTITY that is
        missing.

**So the class is defined by what settles it, not by what is wrong with it.** Neither code is
answered by re-reading a payload (`RE_ADJUDICABLE`) or by asking the provider for bytes
(`NEEDS_REFETCH`). Both are answered by a LATER ACT — our code learning to derive the audience,
or the connector landing a properly versioned capture of the same object — and until that act
happens the honest report is "still blocked, and this old", not "terminal".

PURE DECISION, IMPURE DRAIN. `plan_recapture` takes a candidate and a clock reading and returns
the action; `drain_recapture` does the SQL. Every interesting property — that a still-unnamable
audience is not published, that a superseded park settles once and stays settled, that a re-derived
audience is never WIDER than the evidence — is a property of the decision, so it is a table with a
row per condition rather than an integration test that needs a server.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Sequence

from genios_engine.capture.visibility_rules import derive_visibility
from genios_engine.contracts.visibility import Visibility
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.capture.parked.recapture")

#: The park code held because no visibility rule covered the source.
VISIBILITY_UNKNOWN = "visibility_unknown"
#: The park code held because a mutable object carried no version stamp.
VERSIONLESS_MUTABLE = "MUT-01"

#: The third drain class. Kept here rather than in `drain.py` so that the module that OWNS the
#: settlement owns the set — the two `drain.py` sets are imported by `refetch_policy.py` for
#: exactly that reason, and a set whose members are decided in one file and acted on in another
#: is how ``DOC-07`` spent six months in neither.
NEEDS_RECAPTURE: frozenset[str] = frozenset({VISIBILITY_UNKNOWN, VERSIONLESS_MUTABLE})

#: How old a still-blocked recapture park has to be before it is an operator's problem. The same
#: three days `drain.STALE_AFTER` uses, imported rather than restated so the two surfaces cannot
#: report different backlogs from the same rows.
from genios_engine.capture.parked.drain import STALE_AFTER  # noqa: E402  (cycle-free, see above)

#: `parked_events.status` this unit writes. `superseded` is a NEW terminal state and it is not a
#: synonym for `dropped`: dropped means "we looked and there was nothing to recover", superseded
#: means "a later, better capture of this same object exists and is live". An operator counting
#: losses must be able to tell those apart.
STATUS_PENDING = "pending"
STATUS_RECOVERED = "recovered"
STATUS_SUPERSEDED = "superseded"


class RecaptureAction(str, Enum):
    """What one recapture park's state says should happen to it now."""

    REDERIVED = "rederived"          # the derivation now succeeds → stamp it and release
    SUPERSEDED = "superseded"        # a later capture of the same object is live → settle
    STILL_BLOCKED = "still_blocked"  # nothing has changed → stay pending, and be COUNTED
    SKIP = "skip"                    # not this unit's row


@dataclass(frozen=True)
class RecaptureCandidate:
    """One parked event, reduced to the columns the decision reads.

    Everything here is a `source_events` / `parked_events` column, so a candidate can be
    reconstructed from a report and the decision replayed without a database.
    """

    event_id: str
    org_id: str
    reason_code: str
    status: str
    source: str
    source_object_id: str
    object_type: str
    parked_at: datetime
    actor_email: str | None = None
    recipients: tuple[str, ...] = ()
    internal_kind: str | None = None
    #: True when a DIFFERENT, later event for the same (source, source_object_id) has been
    #: emitted. The only fact MUT-01's settlement depends on, computed by the drain's SQL.
    has_later_capture: bool = False


@dataclass(frozen=True)
class RecapturePlan:
    """The decision for one candidate, and — for a re-derivation — the audience it produced."""

    candidate: RecaptureCandidate
    action: RecaptureAction
    reason: str
    visibility: Visibility | None = None
    #: Whole days the park has been waiting, for the still-blocked report. Integer: a backlog
    #: age compared against a threshold in an alert must not flap on a float's last place.
    age_days: int = 0


@dataclass(frozen=True)
class RecaptureReport:
    """What one drain cycle did. Typed, not a dict, because it crosses a module boundary and is
    rendered by both the heartbeat response and the G2 report."""

    examined: int = 0
    rederived: int = 0
    superseded: int = 0
    still_blocked: int = 0
    stale: int = 0
    #: `(reason_code, still-blocked count)`, sorted — the per-code backlog the gate counts.
    blocked_by_reason: tuple[tuple[str, int], ...] = ()

    @property
    def settled(self) -> int:
        """Parks this cycle took OUT of `pending`. The number that must be non-zero for the
        queue to be moving at all."""
        return self.rederived + self.superseded


def plan_recapture(candidate: RecaptureCandidate, *, eval_time: datetime,
                   mailbox_owner: str | None = None) -> RecapturePlan:
    """Decide what to do with one recapture park at `eval_time`. Pure.

    `mailbox_owner` is optional and its absence is SAFE by construction: it only ever ADDS the
    connected account to a participants set, so omitting it yields a narrower audience. The one
    direction that must never happen — an audience wider than the evidence — cannot be reached
    by leaving it out.
    """
    def _plan(action: RecaptureAction, reason: str,
              visibility: Visibility | None = None) -> RecapturePlan:
        age = eval_time - candidate.parked_at
        return RecapturePlan(candidate=candidate, action=action, reason=reason,
                             visibility=visibility,
                             age_days=max(age // timedelta(days=1), 0))

    if candidate.status != STATUS_PENDING:
        return _plan(RecaptureAction.SKIP, f"already settled as {candidate.status!r}")
    if candidate.reason_code not in NEEDS_RECAPTURE:
        return _plan(RecaptureAction.SKIP,
                     f"{candidate.reason_code} is not a recapture reason")

    if candidate.reason_code == VISIBILITY_UNKNOWN:
        visibility = derive_visibility(
            source=candidate.source, actor_email=candidate.actor_email,
            recipients=candidate.recipients, internal_kind=candidate.internal_kind,
            mailbox_owner=mailbox_owner)
        if visibility is None:
            # STILL no rule covers this source. Publishing now would be publishing under a
            # guessed audience, which is the one thing the park forbids.
            return _plan(RecaptureAction.STILL_BLOCKED,
                         f"no visibility rule covers source {candidate.source!r} yet")
        return _plan(RecaptureAction.REDERIVED,
                     f"audience now derivable: {visibility.derived_from}", visibility)

    # MUT-01. The park is settled by a LATER capture, never by re-emitting the frozen copy.
    if candidate.has_later_capture:
        return _plan(RecaptureAction.SUPERSEDED,
                     "a later capture of this source object is live; the parked copy is stale "
                     "state about an object we now version correctly")
    return _plan(RecaptureAction.STILL_BLOCKED,
                 f"{candidate.source} still emits no version stamp for this object")


def summarise(plans: Sequence[RecapturePlan], *, stale_after: timedelta = STALE_AFTER
              ) -> RecaptureReport:
    """Fold a cycle's plans into the report. Separate from the drain so the counting can be
    tested without a database — a miscounted backlog reads exactly like a drained one."""
    blocked: dict[str, int] = {}
    rederived = superseded = still = stale = 0
    for plan in plans:
        if plan.action is RecaptureAction.REDERIVED:
            rederived += 1
        elif plan.action is RecaptureAction.SUPERSEDED:
            superseded += 1
        elif plan.action is RecaptureAction.STILL_BLOCKED:
            still += 1
            blocked[plan.candidate.reason_code] = blocked.get(plan.candidate.reason_code, 0) + 1
            if plan.age_days >= stale_after // timedelta(days=1):
                stale += 1
    return RecaptureReport(
        examined=len(plans), rederived=rederived, superseded=superseded, still_blocked=still,
        stale=stale, blocked_by_reason=tuple(sorted(blocked.items())))


#: One statement, because the fact MUT-01 needs (is there a later capture of this object) is a
#: property of `source_events` and asking for it per row would put a query on every park.
_SELECT = """
select pe.event_id, pe.org_id, pe.reason_code, pe.status, pe.created_at,
       se.source, se.source_object_id, se.object_type, se.actor, se.recipients,
       se.internal_kind,
       exists (select 1 from source_events later
               where later.org_id = se.org_id
                 and later.source = se.source
                 and later.source_object_id = se.source_object_id
                 and later.event_id <> se.event_id
                 and later.captured_at > se.captured_at
                 and later.outcome = 'emitted') as has_later_capture
from parked_events pe
join source_events se on se.event_id = pe.event_id
where pe.status = 'pending' and pe.reason_code = any(:codes){org}
order by pe.created_at asc
limit :lim
"""


def drain_recapture(engine, *, eval_time: datetime, org_id: str | None = None,
                    limit: int = 200,
                    mailbox_owner_for: Callable[[str], str | None] | None = None
                    ) -> RecaptureReport:
    """One recapture cycle: re-derive what is derivable, settle what is superseded, COUNT the
    rest by reason and age.

    The third thing is not a consolation prize. `still_blocked` with a per-code breakdown is the
    number that makes the class honest: a park nobody can settle yet is a real state, and saying
    so is the difference between an operable backlog and the silence this whole component exists
    to remove.
    """
    from sqlalchemy import text

    params: dict = {"codes": sorted(NEEDS_RECAPTURE), "lim": limit}
    org_clause = ""
    if org_id:
        org_clause = " and pe.org_id = :org"
        params["org"] = org_id

    plans: list[RecapturePlan] = []
    with engine.begin() as conn:
        rows = conn.execute(text(_SELECT.format(org=org_clause)), params).fetchall()
        for row in rows:
            candidate = _to_candidate(row)
            owner = mailbox_owner_for(candidate.org_id) if mailbox_owner_for else None
            plan = plan_recapture(candidate, eval_time=eval_time, mailbox_owner=owner)
            plans.append(plan)

            if plan.action is RecaptureAction.REDERIVED and plan.visibility is not None:
                conn.execute(text(
                    "update source_events set visibility_scope = :scope, "
                    "visibility_principals = :principals, visibility_derived_from = :derived, "
                    "outcome = 'emitted' "
                    "where org_id = :org and event_id = :event"),
                    {"scope": plan.visibility.scope,
                     "principals": list(plan.visibility.principals or ()),
                     "derived": plan.visibility.derived_from,
                     "org": candidate.org_id, "event": candidate.event_id})
                conn.execute(text(
                    "update parked_events set status = :status where event_id = :event"),
                    {"status": STATUS_RECOVERED, "event": candidate.event_id})
            elif plan.action is RecaptureAction.SUPERSEDED:
                # The park settles; the stale row is NOT re-emitted. Superseding is a statement
                # about the queue, never a licence to publish the frozen copy.
                conn.execute(text(
                    "update parked_events set status = :status where event_id = :event"),
                    {"status": STATUS_SUPERSEDED, "event": candidate.event_id})

    report = summarise(plans)
    if report.examined:
        _log.info("recapture drain: examined=%d rederived=%d superseded=%d still_blocked=%d "
                  "stale=%d", report.examined, report.rederived, report.superseded,
                  report.still_blocked, report.stale)
    return report


def _to_candidate(row) -> RecaptureCandidate:
    actor = row.actor if isinstance(row.actor, dict) else {}
    if isinstance(row.actor, str):
        import json
        try:
            actor = json.loads(row.actor) or {}
        except ValueError:
            actor = {}
    return RecaptureCandidate(
        event_id=row.event_id, org_id=row.org_id, reason_code=row.reason_code,
        status=row.status, source=row.source or "", source_object_id=row.source_object_id or "",
        object_type=row.object_type or "", parked_at=row.created_at,
        actor_email=actor.get("email"), recipients=tuple(row.recipients or ()),
        internal_kind=row.internal_kind, has_later_capture=bool(row.has_later_capture))


__all__ = ["NEEDS_RECAPTURE", "STATUS_PENDING", "STATUS_RECOVERED", "STATUS_SUPERSEDED",
           "VERSIONLESS_MUTABLE", "VISIBILITY_UNKNOWN", "RecaptureAction", "RecaptureCandidate",
           "RecapturePlan", "RecaptureReport", "drain_recapture", "plan_recapture", "summarise"]
