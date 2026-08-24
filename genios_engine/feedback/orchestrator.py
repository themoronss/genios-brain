"""Layer 6 · Phase 6 — the Learning Orchestrator (`run_learning`, Part 3).

Coordinates one tenant's weekly pass: freeze the policy, gate on consent, claim the tenant/week in
PostgreSQL (the DB claim — not process memory — is the multi-replica authority), load the bounded
cohort, run the ten units in canonical order, then for each proposal validate → preflight → govern
→ persist → publish, and complete the run with counts. The orchestrator coordinates; it never
invents a learning. A completed week is idempotent; the claim makes it safe to call every heartbeat.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from genios_engine.contracts.learning import LearningPolicy, LearningState
from genios_engine.feedback.governance import govern, preflight
from genios_engine.feedback.publisher import persist, publish
from genios_engine.feedback.store import load_batch
from genios_engine.feedback.units import run_all_units, validate_learning
from genios_engine.platform.ids import new_id


def week_key(now: datetime) -> str:
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _as_tuple(value) -> tuple[str, ...]:
    """A jsonb prohibition list as a tuple, refusing to silently invent an empty one.

    A NULL here on a revision the tenant actually authored means the policy did not load, and
    treating that as "nothing is blocked" is the failure mode this whole field guards against.
    """
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value if v)
    return ()


def load_or_seed_policy(conn, org_id: str, *, now: datetime) -> LearningPolicy:
    """The active policy revision, or a seeded protective default (revision 1)."""
    row = conn.execute(text(
        "select revision, min_observations, min_distinct_days, min_distinct_entities, "
        "min_confidence_bp, max_noise_bp, "
        "max_conflict_bp, max_runtime_ttl_seconds, organization_requires_review, "
        # Both prohibition columns. They exist (migration 0045), `governance.py` enforces them,
        # and this SELECT omitted them — so a tenant's "never learn about these targets" list was
        # loaded as empty on every run. Latent rather than live only because nothing can write
        # them yet; the moment a policy-write surface exists it becomes a silent authority hole.
        "blocked_targets, blocked_subject_prefixes, "
        "knowledge_requires_review, learning_enabled from learning_policies "
        "where org_id = :o order by revision desc limit 1"), {"o": org_id}).mappings().first()
    if row is not None:
        return LearningPolicy(
            org_id=org_id, revision=row["revision"], min_observations=row["min_observations"],
            min_distinct_days=row["min_distinct_days"],
            min_distinct_entities=row["min_distinct_entities"],
            min_confidence_bp=row["min_confidence_bp"],
            max_noise_bp=row["max_noise_bp"], max_conflict_bp=row["max_conflict_bp"],
            max_runtime_ttl_seconds=row["max_runtime_ttl_seconds"],
            organization_requires_review=row["organization_requires_review"],
            blocked_targets=_as_tuple(row["blocked_targets"]),
            blocked_subject_prefixes=_as_tuple(row["blocked_subject_prefixes"]),
            knowledge_requires_review=True, learning_enabled=row["learning_enabled"])
    default = LearningPolicy(org_id=org_id, revision=1)
    conn.execute(text(
        "insert into learning_policies (org_id, revision, snapshot, min_observations, "
        "min_distinct_days, min_distinct_entities, min_confidence_bp, max_noise_bp, max_conflict_bp, "
        "max_runtime_ttl_seconds, organization_requires_review, knowledge_requires_review, "
        # Seeded EMPTY rather than NULL: an empty prohibition list is a decision ("nothing is
        # blocked"), NULL is an absence. Keeping them distinct is what lets the guard below tell
        # a deliberate empty policy from one that failed to load.
        "blocked_targets, blocked_subject_prefixes, "
        "learning_enabled, created_at) values (:o, 1, '{}', :mo, :md, :me, :mc, :mn, :mcf, :ttl, "
        "true, true, cast('[]' as jsonb), cast('[]' as jsonb), true, :at) "
        "on conflict (org_id, revision) do nothing"),
        {"o": org_id, "mo": default.min_observations, "md": default.min_distinct_days,
         "me": default.min_distinct_entities, "mc": default.min_confidence_bp,
         "mn": default.max_noise_bp,
         "mcf": default.max_conflict_bp, "ttl": default.max_runtime_ttl_seconds, "at": now})
    return default


def _claim_week(conn, org_id: str, policy: LearningPolicy, now: datetime) -> str | None:
    """Claim this tenant/week. Returns a run_id, or None if the week is already claimed (idempotent)."""
    run_id = new_id("lrun")
    claimed = conn.execute(text(
        "insert into learning_runs (org_id, run_id, week_key, policy_revision, evaluated_at, "
        "status, created_at) values (:o, :r, :wk, :pr, :at, 'claimed', :at) "
        "on conflict (org_id, week_key) do nothing returning run_id"),
        {"o": org_id, "r": run_id, "wk": week_key(now), "pr": policy.revision, "at": now}
    ).first()
    return run_id if claimed is not None else None


def run_learning(conn, *, org_id: str, now: datetime) -> dict:
    """One tenant's weekly learning pass, inside the caller's transaction."""
    policy = load_or_seed_policy(conn, org_id, now=now)
    if not policy.learning_enabled:
        return {"org_id": org_id, "skipped": "consent_disabled"}

    run_id = _claim_week(conn, org_id, policy, now)
    if run_id is None:
        return {"org_id": org_id, "skipped": "already_ran_this_week"}

    batch = load_batch(conn, org_id=org_id, now=now)
    # Which inputs arrived empty. A learning run whose seams are all empty proposed nothing
    # because it had nothing to read — that is a DEGRADED run, not a healthy one that found
    # nothing to learn, and from the counts alone the two looked identical.
    degraded_seams = {name for name, rows in (
        ("outcomes", getattr(batch, "outcomes", ())),
        ("feedback", getattr(batch, "feedback", ())),
        ("deliveries", getattr(batch, "deliveries", ())),
    ) if not rows}
    # `learning_event_inbox` is loaded into every batch and no unit references it. Empty at both
    # ends today, so it costs nothing — but the day something starts writing to that table, rows
    # would be read and dropped on the floor with no counter moving anywhere. Naming the count
    # makes that arrival visible instead of making it a mystery about why learning ignores a
    # ledger somebody just wired up.
    inbox_unconsumed = len(getattr(batch, "inbox", ()) or ())
    proposals = run_all_units(batch, policy, now)

    inserted = published = held = refused = unchanged = queued_for_review = 0
    for obj in proposals:
        ok, _ = validate_learning(obj, policy)
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
            unchanged += 1
            _record_evaluation(conn, org_id, run_id, obj, policy, now,
                               prior=None, result="unchanged", inserted=False,
                               sink="no_material_change")
            continue
        sink = publish(conn, obj, target_state=decision.target_state, at=now)
        inserted += 1 if outcome == "inserted" else 0
        # The SINK decides what happened, not the fact that publish() returned. Counting every
        # call as `published` made the run ledger disagree with the evaluation ledger inside one
        # transaction: `counts.published = 1` beside `result_state='human_review',
        # sink_reason='queued_for_review'` for the same object. `published` is the number an
        # operator reads, and it was wrong for every review-routed object — which today is 100%
        # of brain-target objects, so the one number that says "learning is working" has never
        # been true.
        if str(sink) == "queued_for_review":
            queued_for_review += 1
        else:
            published += 1
        _record_evaluation(conn, org_id, run_id, obj, policy, now, prior="governed",
                           result=decision.target_state.value,
                           inserted=(outcome == "inserted"), sink=sink)

    counts = {"proposals": len(proposals), "inserted": inserted, "published": published,
              "queued_for_review": queued_for_review,
              "held": held, "refused": refused, "unchanged": unchanged,
              # A run that proposed nothing because its inputs were empty is NOT a healthy run
              # that found nothing to learn, and the two were indistinguishable from the counts.
              "degraded": bool(degraded_seams), "degraded_seams": sorted(degraded_seams),
              "inbox_unconsumed": inbox_unconsumed}
    conn.execute(text(
        "update learning_runs set status = 'completed', completed_at = :at, "
        "objects_inserted = :ins, objects_unchanged = :unc, counts = cast(:c as jsonb) "
        "where org_id = :o and run_id = :r"),
        {"at": now, "ins": inserted, "unc": unchanged, "c": _json(counts), "o": org_id, "r": run_id})
    return {"org_id": org_id, "run_id": run_id, **counts, **batch.counts()}


def _record_evaluation(conn, org_id, run_id, obj, policy, now, *, prior, result, inserted, sink):
    """Append-only: the final sink-level outcome of one actual decision, pinned to run+policy+time.

    Storing the final publisher/lifecycle result (not merely the last planned policy edge) keeps
    published / no_material_change / metric_identity_conflict distinguishable, and object replay
    never needs to mutate the proposal.
    """
    conn.execute(text(
        "insert into learning_object_evaluations (id, org_id, run_id, learning_id, policy_revision, "
        "evaluated_at, prior_state, result_state, object_inserted, sink_reason) "
        "values (:id, :o, :r, :l, :pr, :at, :prior, :res, :ins, :sink)"),
        {"id": new_id("leval"), "o": org_id, "r": run_id, "l": obj.learning_id,
         "pr": policy.revision, "at": now, "prior": prior, "res": result, "ins": inserted,
         "sink": sink})


def _json(d: dict) -> str:
    from genios_engine.platform.canonical import canonical_dumps
    return canonical_dumps(d)


def learning_orgs(engine) -> list[str]:
    """Tenants eligible for a learning pass: those with an active pack (a source of decisions)."""
    with engine.connect() as c:
        return [r[0] for r in c.execute(text(
            "select distinct org_id from tenant_packs where state = 'active'"))]


def run_learning_sweep(engine, *, now: datetime) -> dict:
    """The heartbeat entry point — one guarded per-org transaction each. Weekly via the DB claim."""
    orgs = learning_orgs(engine)
    passes = skipped = 0
    for org in orgs:
        try:
            with engine.begin() as c:
                result = run_learning(c, org_id=org, now=now)
            if "skipped" in result:
                skipped += 1
            else:
                passes += 1
        except Exception:  # noqa: BLE001 — one tenant's failure is not the rest's
            skipped += 1
    return {"orgs": len(orgs), "passes": passes, "skipped": skipped}


__all__ = ["learning_orgs", "load_or_seed_policy", "run_learning", "run_learning_sweep", "week_key"]
