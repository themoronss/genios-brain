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

from genios_engine.contracts.learning import (
    PROHIBITIONS_ABSENT,
    PROHIBITIONS_LOADED,
    PROHIBITIONS_MALFORMED,
    LearningPolicy,
    LearningState,
)
from genios_engine.feedback.brain_pipeline import brain_pipeline_proposals, expire_leases
from genios_engine.feedback.governance import govern, preflight
from genios_engine.feedback.publisher import persist, publish
from genios_engine.feedback.store import HEALTH_SEAMS, load_batch
from genios_engine.feedback.units import run_all_units, validate_learning
from genios_engine.platform.ids import new_id


def week_key(now: datetime) -> str:
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _prohibition_list(value) -> tuple[tuple[str, ...], str]:
    """One jsonb prohibition column as `(list, state)`.

    ⛔ THIS REPLACES `_as_tuple`, WHICH COULD NOT KEEP THE PROMISE IN ITS OWN DOCSTRING. It said it
    was *"refusing to silently invent an empty one"* and that treating a NULL as "nothing is
    blocked" is *"the failure mode this whole field guards against"* — and it returned `()` for
    `None` and for every malformed value alike. **It received only the value, so it could not tell
    an absence from a decision; nothing in its signature made the promise keepable.**

    ⛔ THE DISTINCTION IS PRESERVED EVERYWHERE ELSE AND WAS DESTROYED HERE. `migrations/0045` makes
    both columns nullable and the seed below writes `cast('[]' as jsonb)` with the comment *"an
    empty prohibition list is a decision ('nothing is blocked'), NULL is an absence. Keeping them
    distinct is what lets the guard below tell a deliberate empty policy from one that failed to
    load."* ⛔ **There was no such guard.** The database kept the two apart and the load collapsed
    them one line later.

    The three outcomes, and why each is what it is:

      a JSON array of non-empty strings  → `loaded`     the only trustworthy shape
      `None`                             → `absent`     a stored revision with NULL where a list
                                                        belongs did not load
      anything else                      → `malformed`  ⛔ including a list with a non-string in
                                                        it, which can never equal a target value,
                                                        and a list with an EMPTY string in it,
                                                        which `str.startswith("")` would match
                                                        against EVERY subject

    ⛔ The two bad shapes fail in OPPOSITE directions — a non-string blocks nothing, an empty
    prefix blocks everything — so neither may be silently repaired. The old code coerced with
    `str(v) for v in value if v`, which turned the first into a harmless-looking fail-open and the
    second into an invisible drop.
    """
    if value is None:
        return (), PROHIBITIONS_ABSENT
    if not isinstance(value, (list, tuple)):
        return (), PROHIBITIONS_MALFORMED
    if any(not isinstance(v, str) or not v for v in value):
        return (), PROHIBITIONS_MALFORMED
    return tuple(value), PROHIBITIONS_LOADED


def _prohibitions(targets, prefixes) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    """Both prohibition columns, and the WORST of their two states.

    ⛔ Returns empty lists for BOTH whenever either is untrustworthy, rather than handing back the
    half that loaded. The pass is blocked either way, and a half-populated policy is the shape
    somebody later reads as complete. *An untrusted list is not partially usable.*
    """
    blocked, blocked_state = _prohibition_list(targets)
    prefix, prefix_state = _prohibition_list(prefixes)
    for state in (PROHIBITIONS_MALFORMED, PROHIBITIONS_ABSENT):      # malformed is the worse one
        if state in (blocked_state, prefix_state):
            return (), (), state
    return blocked, prefix, PROHIBITIONS_LOADED


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
        # ⛔ A STORED REVISION IS THE ONLY POLICY THAT CAN FAIL TO LOAD, which is why the state is
        # resolved here and not in the contract: the seeded default below is authored in code and
        # is trusted by construction.
        blocked, prefixes, prohibitions_state = _prohibitions(
            row["blocked_targets"], row["blocked_subject_prefixes"])
        return LearningPolicy(
            org_id=org_id, revision=row["revision"], min_observations=row["min_observations"],
            min_distinct_days=row["min_distinct_days"],
            min_distinct_entities=row["min_distinct_entities"],
            min_confidence_bp=row["min_confidence_bp"],
            max_noise_bp=row["max_noise_bp"], max_conflict_bp=row["max_conflict_bp"],
            max_runtime_ttl_seconds=row["max_runtime_ttl_seconds"],
            organization_requires_review=row["organization_requires_review"],
            blocked_targets=blocked,
            blocked_subject_prefixes=prefixes,
            prohibitions_state=prohibitions_state,
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

    # ⛔ BEFORE `_claim_week`, AND THE ORDER IS THE WHOLE POINT. A policy whose prohibition lists
    # did not load must not learn — an empty list would be read as "this tenant blocks nothing" and
    # admit the exact targets they meant to forbid.
    #
    # ⛔ AFTER the claim this would be far worse than the fail-open it replaces. `_claim_week`
    # inserts `on conflict (org_id, week_key) do nothing`, so a claimed week is claimed: the next
    # heartbeat would answer "already_ran_this_week" for the rest of the week, and a policy row
    # somebody fixed on Tuesday would not be learned from until the following Monday. **A
    # fail-closed placed after the claim converts a policy problem into a lost week.**
    #
    # `governance.preflight` refuses the same policy independently, because `brain_pipeline` and
    # `org_rule_ingest` reach the pipeline without passing through here.
    if not policy.prohibitions_loaded:
        return {"org_id": org_id, "skipped": f"policy_prohibitions_{policy.prohibitions_state}",
                "policy_revision": policy.revision}

    run_id = _claim_week(conn, org_id, policy, now)
    if run_id is None:
        return {"org_id": org_id, "skipped": "already_ran_this_week"}

    batch = load_batch(conn, org_id=org_id, now=now)
    # Which inputs arrived empty. A learning run whose seams are all empty proposed nothing
    # because it had nothing to read — that is a DEGRADED run, not a healthy one that found
    # nothing to learn, and from the counts alone the two looked identical.
    # ⛔⛔ FIELD NAMES FROM `store.HEALTH_SEAMS`, NOT GUESSED STRINGS. This set was built inline
    # and one of its three entries read `getattr(batch, "deliveries", ())` — the field is
    # `delivery`. **The default fired on every single run**, so the delivery seam was reported
    # DEGRADED forever regardless of how much delivery data arrived, and `degraded` below was
    # therefore ALWAYS True. ⛔ *A flag that is always set is a flag nobody reads* — the same shape
    # as `receipts.py`'s *a gate that is always red is a gate nobody reads.*
    #
    # ⛔ A `getattr` with a default converts a wrong attribute name into a plausible value. On a
    # dataclass, `batch.delivery` would have raised the first time it ran. The names now live
    # beside `LearningBatch` and a test asserts each one is a real field.
    degraded_seams = {name for name in HEALTH_SEAMS if not getattr(batch, name)}
    # `learning_event_inbox` is loaded into every batch and no unit references it. Empty at both
    # ends today, so it costs nothing — but the day something starts writing to that table, rows
    # would be read and dropped on the floor with no counter moving anywhere. Naming the count
    # makes that arrival visible instead of making it a mystery about why learning ignores a
    # ledger somebody just wired up.
    #
    # ⛔ CORRECTED 2026-10-02 — *"EMPTY AT BOTH ENDS TODAY"* IS NO LONGER TRUE, AND THIS COMMENT'S
    # OWN PREDICTION IS WHAT HAPPENED. `reason/moments/store.record_feedback` inserts a row into
    # `learning_event_inbox` for every moment-feedback action, and it is reached in production from
    # `api/moment_routes.py:746`. So rows ARE read and dropped on the floor — the write end is
    # live, the read end is `unit_preference_learning` and `unit_temporary_memory`, and both still
    # `return []`.
    #
    # ⛔ The counter was built for exactly this day and it did its job: `inbox_unconsumed` is
    # persisted into `learning_runs.counts` below. ⛔ **And nothing read it until 2026-10-02**,
    # when it got the receipt *"no completed learning run hides whether it dropped inbox rows"* —
    # `feedback/`'s first CORRECTNESS receipt, after four that only asked whether the loop had run.
    #
    # ⛔ A non-zero count is the DECLARED gap (Atlas Layer 7 #1: the preference and
    # temporary-memory inboxes need a KIND of event nobody can send yet — every row written today
    # is `payload.kind == "moment_feedback"`). It is not a defect in this function.
    inbox_unconsumed = len(getattr(batch, "inbox", ()) or ())
    # A Runtime lease carries a mandatory expiry, and an expiry nothing acts on is a label. The
    # weekly pass retires the ones whose clock ran out BEFORE it proposes, so a lease re-proposed
    # this week supersedes a dead one rather than sitting beside it.
    expired_leases = expire_leases(conn, org_id=org_id, now=now)
    # Layer 3's brain-content pipelines are proposal PRODUCERS and nothing else: N-4 turns L2.4's
    # measured findings into behaviour patterns and the Adaptive path turns card verdicts into
    # leases. They are appended to this run's proposals so the SAME loop below validates, governs,
    # persists and publishes them — one claimed run, one pinned policy revision, one set of
    # counts. A producer that published on its own would be the "write outside the L6 pipeline"
    # the J4 gate counts, and there would be no way to see it from here.
    proposals = list(run_all_units(batch, policy, now))
    proposals.extend(brain_pipeline_proposals(conn, org_id=org_id, policy=policy, now=now))

    inserted = published = held = refused = unchanged = queued_for_review = 0
    # ⛔⛔ THE NO-SILENT-DROP CONTRACT. Until 2026-10-02 all three refusal paths below discarded a
    # reason the callee had already computed — `ok, _ = validate_learning(...)` threw away the
    # string, and only `.ok` / `.rejected` were read off `PreflightResult` and
    # `GovernanceDecision`. A refused proposal was COUNTED and never NAMED.
    #
    # ⛔ The Atlas states the contract this breaks: *"Every rejected or deferred candidate must
    # retain run_id, tenant, unit, evidence IDs, REASON CODE, failed gate, policy version,
    # timestamp, and recovery status. 'No proposal' is valid only when accompanied by a
    # machine-readable reason … A weekly sweep that returns zero objects without this accounting is
    # operationally indistinguishable from broken wiring."*
    #
    # ⛔ AND THE LEDGER WAS BUILT FOR IT. `migrations/0046` describes
    # `learning_object_evaluations` as *"append-only: every actual per-run decision (NEW OR HELD
    # object)"* — the held case is named in the schema's own comment and was never written. No
    # migration was needed: `run_id`, `policy_revision`, `evaluated_at`, `prior_state`,
    # `result_state` and `sink_reason` are exactly the fields the Atlas asks for, and
    # `learning_id` carries no foreign key, so a proposal that never reached `persist` can still
    # be recorded.
    #
    # `evaluations` counts the rows written. It is the MARKER the reconciliation receipt gates on:
    # a run completed before this change has no such key, so the receipt cannot be red for history
    # it could not have recorded.
    evaluations = 0
    for obj in proposals:
        ok, reason = validate_learning(obj, policy)
        if not ok:
            held += 1
            _record_evaluation(conn, org_id, run_id, obj, policy, now,
                               prior=None, result="held", inserted=False, sink=reason)
            evaluations += 1
            continue
        gate = preflight(obj, policy, now=now)
        if not gate.ok:
            refused += 1
            _record_evaluation(conn, org_id, run_id, obj, policy, now,
                               prior=None, result="refused", inserted=False,
                               sink=gate.reason_code)
            evaluations += 1
            continue
        decision = govern(obj, policy)
        if decision.rejected:
            refused += 1
            _record_evaluation(conn, org_id, run_id, obj, policy, now,
                               prior=None, result="refused", inserted=False,
                               sink=decision.reason_code)
            evaluations += 1
            continue
        outcome = persist(conn, obj, state=LearningState.GOVERNED, at=now,
                          policy_revision=policy.revision)
        if outcome == "unchanged":
            unchanged += 1
            _record_evaluation(conn, org_id, run_id, obj, policy, now,
                               prior=None, result="unchanged", inserted=False,
                               sink="no_material_change")
            evaluations += 1
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
        evaluations += 1

    counts = {"proposals": len(proposals), "inserted": inserted, "published": published,
              "queued_for_review": queued_for_review,
              "held": held, "refused": refused, "unchanged": unchanged,
              # ⛔ ONE EVALUATION ROW PER PROPOSAL — the contract `migrations/0046` states and the
              # code broke for every refusal. This number exists for two readers: an operator, and
              # the receipt *"every proposal a completed learning run made is recorded as a
              # decision"*, which uses the KEY's presence to exclude runs that completed before
              # refusals were recorded at all. A run from last week cannot be judged against a
              # contract it predates.
              "evaluations": evaluations,
              # A run that proposed nothing because its inputs were empty is NOT a healthy run
              # that found nothing to learn, and the two were indistinguishable from the counts.
              "degraded": bool(degraded_seams), "degraded_seams": sorted(degraded_seams),
              # ⛔ WHICH SEAM WAS LOST, not merely which was empty. `_read_optional_seam`
              # quarantines a read that raised, records it in `learning_input_rejections` and
              # returns `()` — so an isolated seam used to arrive here identical to an empty one
              # and appeared in `degraded_seams` with no way to tell the two apart. The Atlas's
              # `L7-29` asks for the **empty reason**, and L5 learned the same shape one layer
              # down: *a dead row cannot tell "we chose not to send" from "we lost it".*
              "quarantined_seams": sorted(batch.quarantined),
              "inbox_unconsumed": inbox_unconsumed, "expired_leases": expired_leases}
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
    """The heartbeat entry point — one guarded per-org transaction each. Weekly via the DB claim.

    ⛔ `skipped_by_reason` EXISTS BECAUSE THE COUNT ALONE COULD NOT BE ACTED ON. This function
    returned `{orgs, passes, skipped}`, and **a tenant who turned learning off, a tenant whose week
    was already claimed, and a tenant whose transaction raised were the same number.** The
    `except` below still counts a crash as a skip — that is deliberate, one tenant's failure is not
    the rest's — but it no longer makes a crash look like consent.

    ⛔ It is also what makes `S3`'s fail-closed usable. `run_learning` now refuses a pass whose
    prohibition lists did not load, and **a refusal nobody can see is a silent stop** — strictly
    worse than the fail-open it replaces, because at least a fail-open is loud in its consequences.
    *The reader is half the unit.*
    """
    orgs = learning_orgs(engine)
    passes = skipped = 0
    by_reason: dict[str, int] = {}
    for org in orgs:
        try:
            with engine.begin() as c:
                result = run_learning(c, org_id=org, now=now)
            if "skipped" in result:
                skipped += 1
                reason = str(result["skipped"])
            else:
                passes += 1
                continue
        except Exception as exc:  # noqa: BLE001 — one tenant's failure is not the rest's
            skipped += 1
            # ⛔ The TYPE, not a bare flag. `{"error": True}` hid a NameError in the executive
            # sweep for 15 days: the pass reported a generic failure every tick and nobody could
            # tell enumeration from execution.
            reason = f"error:{type(exc).__name__}"
        by_reason[reason] = by_reason.get(reason, 0) + 1
    return {"orgs": len(orgs), "passes": passes, "skipped": skipped,
            "skipped_by_reason": by_reason}


__all__ = ["learning_orgs", "load_or_seed_policy", "run_learning", "run_learning_sweep", "week_key"]
