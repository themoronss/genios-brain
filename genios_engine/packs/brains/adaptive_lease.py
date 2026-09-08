"""The ADAPTIVE LEASE — a founder's card verdict becomes short-term memory with a real clock.

**WHAT A LEASE IS.** The Adaptive brain holds *current* priorities and stated preferences, and
doc 02 gives it the one property the other two brains do not have: `temporary_memories.expires_at`
is `NOT NULL`. A lease that never expires is a permanent memory wearing a temporary label, so the
expiry is not decoration — it is the entire difference between this brain and the Organization
brain, and it is enforced three times over: by the column, by `preflight` (a Runtime proposal with
no expiry, a past expiry, or an expiry beyond the tenant's `max_runtime_ttl_seconds` is refused
before it is ever stored), and by `feedback/brain_pipeline.expire_leases`, which actually retires
them. `scripts/brain_content_report.py` prints the leases that expired and were not cleared,
because "the sweep stopped running" and "nothing has expired yet" look identical from the table.

**WHICH VERDICT MAKES A LEASE, AND WHY ONLY THAT ONE.** `card_feedback_verdicts` (migration 0034)
carries three causes and, on `wrong`, three reasons. Two of those reasons are quality faults —
`not_relevant` and `wrong_facts` say the card should not have existed, which is calibration's
subject and already flows to METRICS through `feedback/units.unit_feedback_learning`. The third,
`bad_timing`, is a different claim entirely: *the card was right and the moment was wrong*. That
is a statement about NOW with an implicit clock on it, which is the definition of a lease. Reading
it as a quality signal would mute a correct rule; reading a quality complaint as a lease would
snooze a rule that is simply wrong. The ledger already separates them — `unit_feedback_learning`'s
own docstring says `bad_timing` "must not count against the rule's accuracy" — and this module is
the consumer that separation was waiting for.

**NO MODEL RUNS HERE.** Doc 02 puts an LLM on the Adaptive brain for *feedback parsing (free text
→ structured)*. A `bad_timing` verdict is ALREADY structured — a closed-vocabulary reason on a
typed ledger with a card id, a capability and an actor. Asking a model to restate it would add a
stochastic step to a deterministic path and buy nothing. The statement is templated from validated
integers, exactly as N-4's is.

**THE FLOORS ARE THE TENANT'S OWN.** One click is not a preference; it is a click. The lease needs
`min_observations` verdicts across `min_distinct_days` distinct days, and the share of verdicts on
that capability that say `bad_timing` must clear `min_confidence_bp` — the same three numbers
`learning_policies` already uses everywhere else. No new governance, and nothing here decides a
promotion: these proposals enter the existing Layer 6 pipeline and `govern()` routes a Runtime
target to `TEMPORARY`, which is the only path to `temporary_memories` there has ever been.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.brain_address import BrainAddress
from genios_engine.contracts.brain_address import token as address_token
from genios_engine.contracts.learning import (
    LearningEvidence,
    LearningObject,
    LearningPolicy,
    LearningTarget,
    Visibility,
    VisibilityScope,
)

#: `learning_objects.unit` for every proposal from here — how the content report attributes an
#: entry to "leased".
LEASE_UNIT = "adaptive_lease"

#: The subject namespace, and the capability is a colon segment of it so a reader that knows the
#: capability can find the lease without knowing this module's spelling.
LEASE_SUBJECT_PREFIX = "adaptive:card_timing"

#: The verdict vocabulary this module reads, from `card_feedback_verdicts`' own CHECK constraint.
#: Named rather than inlined so the one place they are interpreted is the one place to review.
LEASE_CAUSE = "wrong"
LEASE_REASON = "bad_timing"

#: How far back a lease looks. The same 28 days `feedback/store.COHORT_DAYS` bounds a learning run
#: to — spelled here because `packs` is Layer 3 and may not import Layer 7, and kept equal on
#: purpose: a lease and the weekly run that re-proposes it must agree about which verdicts exist.
LEASE_WINDOW_DAYS = 28

#: The lease's own life. Seven days is `learning_policies.max_runtime_ttl_seconds`' default, and
#: the value is CLAMPED to whatever the tenant actually set — a tenant that shortened its ceiling
#: gets the shorter lease, never this constant.
LEASE_TTL_SECONDS = 7 * 24 * 3600

#: Verdicts read per evaluation. A bound, not a policy: the cohort is one tenant's recent card
#: verdicts, and an unbounded read is how a hot path becomes a table scan.
MAX_VERDICTS_READ = 5_000

#: The statement. Descriptive, templated from validated integers, and it states the window it was
#: measured over — a preference with no window is a permanent claim.
LEASE_TEMPLATE = ("{bad_timing} of {verdicts} recent verdicts on {capability} said the timing was "
                  "wrong, from {actors} people over {days} days.")


@dataclass(frozen=True, slots=True)
class TimingCohort:
    """One capability's recent card verdicts, counted. Every field is a count of stored rows."""

    capability_id: str
    verdicts: int
    bad_timing: int
    distinct_days: int
    distinct_actors: int
    distinct_cards: int
    first_at: datetime
    last_at: datetime

    @property
    def share_bp(self) -> int:
        """The share of verdicts that named bad timing, in integer basis points. No float."""
        if self.verdicts <= 0:
            return 0
        return max(0, min(10_000, self.bad_timing * 10_000 // self.verdicts))

    @property
    def window_days(self) -> int:
        return max(0, int((self.last_at - self.first_at).total_seconds()) // 86_400)


@dataclass(frozen=True, slots=True)
class LeaseRefusal:
    """A capability whose verdicts did not earn a lease, and why. Counted, never silent."""

    reason: str
    capability_id: str
    detail: str = ""


_VERDICTS_SQL = text(
    "select capability_id, cause, reason, actor_id, card_id, occurred_at "
    "from card_feedback_verdicts "
    "where org_id = :o and occurred_at >= :since and occurred_at <= :until "
    "order by occurred_at desc limit :limit")


def read_timing_cohorts(conn, *, org_id: str, since: datetime, until: datetime,
                        capability_ids: Sequence[str] | None = None,
                        limit: int = MAX_VERDICTS_READ) -> tuple[TimingCohort, ...]:
    """Count this tenant's recent verdicts per capability. Reads rows; computes nothing else.

    `capability_ids` narrows the read to the capability a caller just received feedback on — the
    immediate path evaluates one lease, not the whole tenant, so a founder's click cannot turn
    into a full-tenant sweep inside a request.
    """
    rows = conn.execute(_VERDICTS_SQL, {"o": org_id, "since": since, "until": until,
                                        "limit": int(limit)}).mappings().all()
    wanted = set(capability_ids) if capability_ids is not None else None
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        capability = str(row["capability_id"] or "")
        if not capability or (wanted is not None and capability not in wanted):
            continue
        at = row["occurred_at"]
        bucket = buckets.setdefault(capability, {
            "verdicts": 0, "bad_timing": 0, "days": set(), "actors": set(), "cards": set(),
            "first": at, "last": at})
        bucket["verdicts"] += 1
        if str(row["cause"]) == LEASE_CAUSE and str(row["reason"] or "") == LEASE_REASON:
            bucket["bad_timing"] += 1
            # Days, actors and cards are counted on the BAD-TIMING rows only: they are the
            # evidence for the claim. Counting them over every verdict would let three unrelated
            # "run_play" verdicts supply the independence a timing complaint has not earned.
            if at is not None:
                bucket["days"].add(at.date())
            bucket["actors"].add(str(row["actor_id"] or ""))
            bucket["cards"].add(str(row["card_id"] or ""))
        if at is not None:
            bucket["first"] = min(bucket["first"], at) if bucket["first"] else at
            bucket["last"] = max(bucket["last"], at) if bucket["last"] else at
    return tuple(sorted(
        (TimingCohort(capability_id=capability, verdicts=b["verdicts"],
                      bad_timing=b["bad_timing"], distinct_days=len(b["days"]),
                      distinct_actors=len(b["actors"]), distinct_cards=len(b["cards"]),
                      first_at=b["first"], last_at=b["last"])
         for capability, b in buckets.items() if b["first"] is not None),
        key=lambda c: c.capability_id))


def qualify_leases(cohorts: Sequence[TimingCohort], *, policy: LearningPolicy
                   ) -> tuple[tuple[TimingCohort, ...], tuple[LeaseRefusal, ...]]:
    """The gate: which cohorts have earned a lease. The tenant's own Layer 6 floors, nothing new."""
    qualified: list[TimingCohort] = []
    refusals: list[LeaseRefusal] = []
    for cohort in cohorts:
        detail = (f"verdicts={cohort.verdicts} bad_timing={cohort.bad_timing} "
                  f"days={cohort.distinct_days} share_bp={cohort.share_bp}")
        if cohort.bad_timing < policy.min_observations:
            refusals.append(LeaseRefusal("insufficient_observations", cohort.capability_id, detail))
            continue
        if cohort.distinct_days < policy.min_distinct_days:
            refusals.append(LeaseRefusal("insufficient_distinct_days", cohort.capability_id,
                                         detail))
            continue
        if cohort.share_bp < policy.min_confidence_bp:
            refusals.append(LeaseRefusal("below_confidence_floor", cohort.capability_id, detail))
            continue
        qualified.append(cohort)
    return tuple(qualified), tuple(refusals)


def lease_subject(capability_id: str) -> str:
    """`adaptive:card_timing:<capability>` — the key a lease is stored and read under."""
    return f"{LEASE_SUBJECT_PREFIX}:{capability_id}"


def lease_ttl_seconds(policy: LearningPolicy) -> int:
    """The lease's life, clamped to the tenant's ceiling. Never longer than the tenant allows."""
    return min(LEASE_TTL_SECONDS, int(policy.max_runtime_ttl_seconds))


def lease_statement(cohort: TimingCohort) -> str:
    """The sentence, templated from counted rows. No model, and every number is a count."""
    return LEASE_TEMPLATE.format(
        bad_timing=cohort.bad_timing, verdicts=cohort.verdicts, capability=cohort.capability_id,
        actors=cohort.distinct_actors, days=max(cohort.window_days, 1))


def _proposal(cohort: TimingCohort, *, org_id: str, policy: LearningPolicy,
              now: datetime) -> LearningObject:
    """One Runtime lease proposal. The expiry is the point, so it is computed here and nowhere else."""
    return LearningObject(
        org_id=org_id, unit=LEASE_UNIT, target=LearningTarget.RUNTIME,
        subject=lease_subject(cohort.capability_id),
        proposed_value={
            "kind": "timing_lease",
            # `capability_id` is a first-class key, not decoration: it is what a reader matches on
            # when it holds a route plan rather than a subject string.
            "capability_id": cohort.capability_id,
            # THE ADDRESS. `capability_id` above was already matchable and is kept exactly as it
            # was; this says the same thing in the vocabulary the other two brains now speak, so
            # one selector serves all three rather than three special cases serving one each.
            #
            # The lease is the brain that was unreachable for a SECOND reason, and the address does
            # not fix that one: it is written to `temporary_memories` and the compiler read only
            # `learned_brain_entries`. See `PostgresRuntimeBrains.snapshot`, which now reads both.
            "address": BrainAddress(
                org_id=org_id, brain="adaptive",
                tokens=(address_token("capability", cohort.capability_id),),
                authority={"source": "card_feedback", "reason": LEASE_REASON,
                           "verdicts": cohort.verdicts,
                           "distinct_actors": cohort.distinct_actors}).as_value(),
            "statement": lease_statement(cohort),
            "source": "card_feedback",
            "reason": LEASE_REASON,
            "verdicts": cohort.verdicts, "bad_timing": cohort.bad_timing,
            "share_bp": cohort.share_bp, "distinct_days": cohort.distinct_days,
            "distinct_actors": cohort.distinct_actors, "distinct_cards": cohort.distinct_cards,
            "observed_from": cohort.first_at.isoformat(),
            "observed_through": cohort.last_at.isoformat()},
        evidence=LearningEvidence(
            observations=cohort.bad_timing,
            # Independent judges, not repeated clicks: three verdicts from one person is one
            # opinion said three times, and the ledger can tell the difference.
            independent_refs=cohort.distinct_actors,
            distinct_days=cohort.distinct_days, positive=cohort.bad_timing,
            negative=cohort.verdicts - cohort.bad_timing, confidence_bp=cohort.share_bp,
            distinct_entities=cohort.distinct_cards),
        # Org scope: the verdicts are judgments on org-visible cards, and a lease that changed
        # what one person sees while the rest of the tenant kept getting the same badly-timed card
        # would be a preference nobody could explain. A user-scoped preference is a different
        # object with a different contract (`subject_principal`), not this one.
        visibility=Visibility(scope=VisibilityScope.ORGANIZATION),
        first_seen_at=cohort.first_at, last_seen_at=cohort.last_at,
        policy_key=policy.policy_key,
        # THE MANDATORY CLOCK. `preflight` refuses this object if the expiry is absent, already
        # past, or beyond the tenant's ceiling — so an unexpiring lease cannot be stored even by
        # a caller that wanted one.
        expires_at=now + timedelta(seconds=lease_ttl_seconds(policy)))


def lease_proposals(conn, *, org_id: str, policy: LearningPolicy, now: datetime,
                    capability_ids: Sequence[str] | None = None,
                    window_days: int = LEASE_WINDOW_DAYS
                    ) -> tuple[tuple[LearningObject, ...], tuple[LeaseRefusal, ...]]:
    """Card feedback in, Runtime lease proposals out. Writes NOTHING; publishes NOTHING.

    Returns the refusals alongside the proposals for the same reason N-4 does: a tenant whose
    verdicts all fell short of the floors and a tenant with no verdicts at all are different
    states, and the counts are where an operator can tell them apart.
    """
    since = now - timedelta(days=window_days)
    cohorts = read_timing_cohorts(conn, org_id=org_id, since=since, until=now,
                                  capability_ids=capability_ids)
    qualified, refusals = qualify_leases(cohorts, policy=policy)
    return (tuple(_proposal(c, org_id=org_id, policy=policy, now=now) for c in qualified),
            refusals)


def lease_rows(conn, *, org_id: str) -> tuple[Mapping[str, Any], ...]:
    """Every lease row this tenant holds, live and expired. The report's read; it writes nothing.

    No instant is taken: what counts as expired is the CALLER's `at`, read once at its process
    boundary, and a helper that quietly compared against its own clock would give two callers in
    the same second two different answers.
    """
    rows = conn.execute(text(
        "select memory_id, learning_id, subject, expires_at, active, created_at "
        "from temporary_memories where org_id = :o order by created_at, memory_id"),
        {"o": org_id}).mappings().all()
    return tuple(dict(r) for r in rows)


__all__ = ["LEASE_CAUSE", "LEASE_REASON", "LEASE_SUBJECT_PREFIX", "LEASE_TEMPLATE",
           "LEASE_TTL_SECONDS", "LEASE_UNIT", "LEASE_WINDOW_DAYS", "MAX_VERDICTS_READ",
           "LeaseRefusal", "TimingCohort", "lease_proposals", "lease_rows", "lease_statement",
           "lease_subject", "lease_ttl_seconds", "qualify_leases", "read_timing_cohorts"]
