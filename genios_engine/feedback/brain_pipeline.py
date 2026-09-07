"""The DRIVER for the Layer 3 brain-content pipelines — and it builds no governance of its own.

`packs/brains/` produces proposals and is Layer 3; the promotion pipeline that decides what
becomes authoritative is Layer 6, and the import ratchet
(`tests/test_layer_topology.py::test_import_direction`) makes that direction one-way: a producer
CANNOT call the governance that judges it. That is the property this module exists to preserve.
It sits on the Layer 6 side, calls into `packs/brains` for proposals, and then runs them through
exactly the four steps `feedback/orchestrator.run_learning` already runs — `validate_learning`,
`preflight`, `govern`, `persist` + `publish` — reusing those functions rather than re-deciding
anything. There is no new floor, no new state machine and no second opinion here.

**THREE ENTRY POINTS, ONE PIPELINE.**

* `brain_pipeline_proposals` — what the WEEKLY run collects. `run_learning` appends it to the
  proposals its own ten units produced, so N-4's output is counted, evaluated and published by
  the same loop, under the same claimed run and the same pinned policy revision.
* `lease_from_card_feedback` — the IMMEDIATE path. Doc 02's Adaptive row says a lease is created
  *immediate*, not next Tuesday, and a preference that arrives a week after the founder stated it
  is not a current preference. Immediacy is the only thing this path adds: the same validation,
  the same preflight, the same `govern()`, the same publisher.
* `expire_leases` — the other half of a mandatory TTL. A lease is already invisible to readers
  once `expires_at` passes (`contracts/learned_state.snapshot` filters on it), so this sweep is
  not what makes expiry correct — it is what makes it OBSERVABLE, retiring the row and appending
  the `temporary → expired` transition that says the clock, not a human, closed it.

**WHAT THIS MODULE MAY NOT DO.** It may not write `learned_brain_entries` or `temporary_memories`
itself; only `feedback/publisher.py` does that, and only for a governed object. It may not touch
the Expert brain — no code path here can, because `LearningTarget` has no such member and the
database has a CHECK constraint underneath it. Both are asserted in `tests/packs/brains/`.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text

from genios_engine.contracts.learning import (
    LearningObject,
    LearningPolicy,
    LearningState,
    learning_can_transition,
)
from genios_engine.feedback.governance import govern, preflight
from genios_engine.feedback.publisher import log_transition, persist, publish
from genios_engine.feedback.units import validate_learning
from genios_engine.packs.brains import adaptive_lease, behavior_distill


@dataclass(frozen=True, slots=True)
class AdmissionCounts:
    """What one admission pass actually did. Every proposal lands in exactly one of these."""

    proposals: int = 0
    held: int = 0                 # failed Unit 11 validation — the evidence did not support it
    refused: int = 0              # preflight or governance said no
    unchanged: int = 0            # already known at a later state; not reopened
    published: int = 0            # reached a sink
    queued_for_review: int = 0    # governance routed it to a human
    sinks: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {"proposals": self.proposals, "held": self.held, "refused": self.refused,
                "unchanged": self.unchanged, "published": self.published,
                "queued_for_review": self.queued_for_review, "sinks": list(self.sinks)}


def admit_proposals(conn, proposals: Sequence[LearningObject], *, policy: LearningPolicy,
                    now: datetime) -> AdmissionCounts:
    """Run proposals through the EXISTING Layer 6 gates, in the existing order. Nothing new.

    Deliberately the same four steps, called in the same sequence, as
    `orchestrator.run_learning`'s loop: validate, preflight, govern, persist-then-publish. It does
    not write `learning_object_evaluations` — that ledger is keyed on a claimed weekly `run_id`,
    and an immediate lease has no run. The transition ledger, which is keyed on the object, is
    written by the publisher exactly as it is for a weekly proposal.
    """
    held = refused = unchanged = published = queued = 0
    sinks: list[str] = []
    for obj in proposals:
        ok, _reason = validate_learning(obj, policy)
        if not ok:
            held += 1
            continue
        if not preflight(obj, policy, now=now).ok:
            refused += 1
            continue
        decision = govern(obj, policy)
        if decision.rejected:
            refused += 1
            continue
        outcome = persist(conn, obj, state=LearningState.GOVERNED, at=now,
                          policy_revision=policy.revision)
        if outcome == "unchanged":
            # A byte-identical proposal already sits at a later state. Re-publishing it would be
            # the version noise the publisher's `no_material_change` branch exists to prevent.
            unchanged += 1
            continue
        sink = publish(conn, obj, target_state=decision.target_state, at=now)
        sinks.append(str(sink))
        if str(sink) == "queued_for_review":
            queued += 1
        else:
            published += 1
    return AdmissionCounts(proposals=len(proposals), held=held, refused=refused,
                           unchanged=unchanged, published=published, queued_for_review=queued,
                           sinks=tuple(sinks))


def brain_pipeline_proposals(conn, *, org_id: str, policy: LearningPolicy, now: datetime,
                             labeler: behavior_distill.Labeler | None = None
                             ) -> list[LearningObject]:
    """The weekly batch's contribution: N-4's behaviour patterns and any lease the week earned.

    Returned rather than admitted, so `run_learning`'s own loop counts and evaluates them under
    the run it already claimed — one pass, one policy revision, one set of counts.

    A failure inside one pipeline isolates that pipeline, INSIDE A SAVEPOINT. Layer 6's sweep
    already treats one tenant's failure as not the rest's, and the same reasoning applies one
    level down — but a bare try/except is not isolation in PostgreSQL: a statement that raises
    poisons the surrounding transaction, so every later statement in the caller's learning run
    would fail too and the "isolated" pipeline would take the whole run with it. `begin_nested`
    is what makes the sentence true. The isolation is RECORDED, never silent.
    """
    proposals: list[LearningObject] = []
    distilled = _isolated(conn, org_id, "brains.behavior_distill", at=now, call=lambda: (
        behavior_distill.distill(conn, org_id=org_id, policy=policy, labeler=labeler)[0]))
    proposals.extend(distilled or ())
    leases = _isolated(conn, org_id, "brains.adaptive_lease", at=now, call=lambda: (
        adaptive_lease.lease_proposals(conn, org_id=org_id, policy=policy, now=now)[0]))
    proposals.extend(leases or ())
    return proposals


def _isolated(conn, org_id: str, seam: str, *, at: datetime, call):
    """Run one producer inside a SAVEPOINT. On failure: roll back to it, record, return None.

    The savepoint is the whole mechanism. Without it, a producer whose SQL raises leaves the
    caller's transaction in an aborted state, and the next statement — the run's own counts write
    — fails with `current transaction is aborted`. Rolling back to the savepoint returns the
    connection to exactly the state the caller had before this producer ran, which is what
    "isolate the seam, never fail the run" has to mean when the seam is a database read.

    A connection object that cannot open one is not a transaction this function can protect — a
    test double, or a driver-level handle — so it is run WITHOUT a savepoint rather than refused.
    The isolation is then only as good as the caller's own transaction, which is exactly what it
    was before this function existed; refusing instead would make a stand-in connection fail at
    the one seam that is supposed to never cost its caller anything.
    """
    savepoint = conn.begin_nested() if hasattr(conn, "begin_nested") else None
    try:
        result = call()
    except Exception as exc:                                  # noqa: BLE001 — isolate and record
        if savepoint is not None:
            savepoint.rollback()
        _record_rejection(conn, org_id, seam, exc, at=at)
        return None
    if savepoint is not None:
        savepoint.commit()
    return result


def lease_from_card_feedback(conn, *, org_id: str, now: datetime,
                             capability_ids: Sequence[str] | None = None) -> dict[str, object]:
    """THE IMMEDIATE PATH: a founder's verdict lands, and the lease it earns exists now.

    Called from the card-feedback route inside the transaction that wrote the verdict, so the
    cohort this reads INCLUDES the verdict that triggered it and the two either commit together
    or neither does. `capability_ids` narrows the read to the capability just judged: a click must
    not turn into a tenant-wide sweep inside a request.

    Expired leases are retired first. The order matters: the founder who says "not now" for the
    fourth time should not be told about a lease that ran out on Tuesday.

    ISOLATED IN A SAVEPOINT, and that is a product decision rather than defensive habit. This runs
    inside the request that records a human's verdict on a card. A learning proposal that cannot
    be built must never cost that human their feedback — so a failure here rolls back to the
    savepoint, leaves a `learning_input_rejections` row behind naming the seam, and leaves the
    verdict write intact and committable.
    """
    result = _isolated(conn, org_id, "brains.adaptive_lease.immediate", at=now,
                       call=lambda: _lease_now(conn, org_id=org_id, now=now,
                                               capability_ids=capability_ids))
    return result if result is not None else {"skipped": "isolated"}


def _lease_now(conn, *, org_id: str, now: datetime,
               capability_ids: Sequence[str] | None) -> dict[str, object]:
    """The immediate lease evaluation itself, so the isolation above wraps ALL of it."""
    from genios_engine.feedback.orchestrator import load_or_seed_policy

    policy = load_or_seed_policy(conn, org_id, now=now)
    if not policy.learning_enabled:
        return {"skipped": "consent_disabled"}
    expired = expire_leases(conn, org_id=org_id, now=now)
    proposals, refusals = adaptive_lease.lease_proposals(
        conn, org_id=org_id, policy=policy, now=now, capability_ids=capability_ids)
    counts = admit_proposals(conn, proposals, policy=policy, now=now)
    return {**counts.as_dict(), "expired": expired,
            "refusals": [r.reason for r in refusals]}


_EXPIRE_SQL = text(
    "update temporary_memories set active = false "
    "where org_id = :o and active and expires_at <= :now "
    "returning memory_id, learning_id, subject")


def expire_leases(conn, *, org_id: str, now: datetime) -> int:
    """Retire every lease whose clock has run out, and SAY SO in the transition ledger.

    Deactivation rather than deletion, for the reason the whole learning spine is append-only: the
    row is the evidence that the lease existed and that it ended, and a lease that vanished is
    indistinguishable from one that was never granted.

    `learning_objects.state` is deliberately not rewritten. Layer 6 stores lifecycle in
    `learning_transitions` — the publisher itself only ever appends there after `persist` — and a
    second opinion about state written from a sweep is how the two ledgers start disagreeing. The
    transition is checked against the contract's own state machine before it is written, so this
    sweep cannot invent an edge the lifecycle does not have.
    """
    if not learning_can_transition(LearningState.TEMPORARY, LearningState.EXPIRED):
        raise AssertionError("the lifecycle no longer allows temporary → expired; a lease that "
                             "cannot expire is a permanent memory wearing a temporary label")
    rows = conn.execute(_EXPIRE_SQL, {"o": org_id, "now": now}).mappings().all()
    for row in rows:
        learning_id = row["learning_id"]
        if not learning_id:
            continue                     # a lease with no proposal behind it: nothing to transition
        log_transition(conn, org_id=org_id, learning_id=str(learning_id),
                       from_state=LearningState.TEMPORARY.value,
                       to_state=LearningState.EXPIRED.value, reason_code="lease_expired",
                       at=now, actor="clock",
                       detail={"memory_id": str(row["memory_id"]), "subject": str(row["subject"])})
    return len(rows)


def _record_rejection(conn, org_id: str, seam: str, exc: BaseException, *,
                      at: datetime) -> None:
    """Note an isolated pipeline in `learning_input_rejections`, without failing the run over it.

    Same ledger and same best-effort contract as `feedback/store._record_rejection`: an audit row
    is never worth losing a learning run, but an input the system deliberately quarantined must
    not be indistinguishable from one that never arrived.
    """
    try:
        from genios_engine.platform.ids import new_id
        conn.execute(text(
            "insert into learning_input_rejections "
            "(id, org_id, seam, source_ref, reason_code, created_at) "
            "values (:id, :o, :seam, :ref, :code, :at)"),
            {"id": new_id("lrej"), "o": org_id, "seam": seam, "ref": seam,
             "code": f"{type(exc).__name__}: {exc}"[:200], "at": at})
    except Exception:                     # noqa: BLE001 — an audit row never costs a run
        pass


__all__ = ["AdmissionCounts", "admit_proposals", "brain_pipeline_proposals", "expire_leases",
           "lease_from_card_feedback"]
