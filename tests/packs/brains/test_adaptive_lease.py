"""The ADAPTIVE LEASE — a founder's `bad_timing` verdict becomes short-term memory with a clock.

The claim under test is narrow and checkable: a lease exists only when the tenant's own Layer 6
floors are cleared, it always carries an expiry inside the tenant's ceiling, it is written by the
publisher and nothing else, and the clock actually retires it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.contracts.learning import LearningPolicy, LearningTarget
from genios_engine.feedback.governance import govern, preflight
from genios_engine.feedback.units import validate_learning
from genios_engine.packs.brains import adaptive_lease as al

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
CAPABILITY = "admin.executive_support.commitment_tracking"
POLICY = LearningPolicy(org_id="org_scratch_tests", revision=1)


def _cohort(*, verdicts=4, bad_timing=4, days=2, actors=2, cards=4,
            first=NOW - timedelta(days=6), last=NOW) -> al.TimingCohort:
    return al.TimingCohort(capability_id=CAPABILITY, verdicts=verdicts, bad_timing=bad_timing,
                           distinct_days=days, distinct_actors=actors, distinct_cards=cards,
                           first_at=first, last_at=last)


# ---- the gate ---------------------------------------------------------------------------------

def test_one_click_is_not_a_preference():
    qualified, refusals = al.qualify_leases([_cohort(verdicts=1, bad_timing=1, days=1,
                                                     actors=1, cards=1)], policy=POLICY)
    assert qualified == ()
    assert [r.reason for r in refusals] == ["insufficient_observations"]


def test_the_same_day_three_times_is_still_one_day():
    qualified, refusals = al.qualify_leases([_cohort(days=1)], policy=POLICY)
    assert qualified == ()
    assert [r.reason for r in refusals] == ["insufficient_distinct_days"]


def test_a_minority_complaint_does_not_lease():
    """Two of nine verdicts saying 'bad timing' is not the tenant saying 'not now'."""
    qualified, refusals = al.qualify_leases([_cohort(verdicts=9, bad_timing=3)], policy=POLICY)
    assert qualified == ()
    assert [r.reason for r in refusals] == ["below_confidence_floor"]


def test_repeated_bad_timing_across_days_earns_a_lease():
    qualified, refusals = al.qualify_leases([_cohort()], policy=POLICY)
    assert refusals == () and len(qualified) == 1
    assert qualified[0].share_bp == 10_000


def test_the_share_is_integer_basis_points_never_a_float():
    assert _cohort(verdicts=3, bad_timing=1).share_bp == 3333
    assert _cohort(verdicts=0, bad_timing=0).share_bp == 0
    assert isinstance(_cohort().share_bp, int)


# ---- the mandatory clock ----------------------------------------------------------------------

def _proposal(policy=POLICY, cohort=None, now=NOW):
    proposals = [al._proposal(cohort or _cohort(), org_id=policy.org_id, policy=policy, now=now)]
    return proposals[0]


def test_a_lease_always_carries_an_expiry_inside_the_tenants_ceiling():
    obj = _proposal()
    assert obj.target is LearningTarget.RUNTIME
    assert obj.expires_at == NOW + timedelta(seconds=al.LEASE_TTL_SECONDS)
    assert preflight(obj, POLICY, now=NOW).ok


def test_a_tenant_that_shortened_its_ceiling_gets_the_shorter_lease():
    strict = LearningPolicy(org_id="o", revision=1, max_runtime_ttl_seconds=3600)
    assert al.lease_ttl_seconds(strict) == 3600
    obj = _proposal(policy=strict)
    assert obj.expires_at == NOW + timedelta(seconds=3600)
    assert preflight(obj, strict, now=NOW).ok, "the clamp is what keeps preflight satisfied"


def test_an_unclamped_lease_would_be_refused_by_preflight():
    """Why the clamp exists: the ceiling is enforced BEFORE storage, not as advice."""
    strict = LearningPolicy(org_id="o", revision=1, max_runtime_ttl_seconds=3600)
    obj = _proposal(policy=strict)
    forged = type(obj)(
        org_id=obj.org_id, unit=obj.unit, target=obj.target, subject=obj.subject,
        proposed_value=dict(obj.proposed_value), evidence=obj.evidence,
        visibility=obj.visibility, first_seen_at=obj.first_seen_at,
        last_seen_at=obj.last_seen_at, policy_key=obj.policy_key,
        expires_at=NOW + timedelta(days=30))
    assert preflight(forged, strict, now=NOW).reason_code == "runtime_ttl_over_ceiling"


def test_a_lease_goes_to_the_temporary_state_not_to_a_human_and_not_to_a_brain():
    obj = _proposal()
    assert validate_learning(obj, POLICY)[0]
    from genios_engine.contracts.learning import LearningState

    assert govern(obj, POLICY).target_state is LearningState.TEMPORARY


def test_the_statement_is_templated_and_the_value_names_its_capability():
    cohort = _cohort()
    obj = _proposal(cohort=cohort)
    value = dict(obj.proposed_value)
    assert value["capability_id"] == CAPABILITY and value["source"] == "card_feedback"
    assert str(cohort.bad_timing) in value["statement"]
    assert CAPABILITY in value["statement"]
    assert obj.subject == al.lease_subject(CAPABILITY)
    assert CAPABILITY in obj.subject.split(":")[2:], "the capability must be a colon segment"


# ---- the real path ----------------------------------------------------------------------------

@pytest.fixture()
def conn(live_db_url):
    if not live_db_url:
        pytest.skip("no database configured")
    from genios_engine.platform.db import get_engine
    c = get_engine(live_db_url).connect()
    tx = c.begin()
    org = c.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        tx.rollback(); c.close(); pytest.skip("no org")
    try:
        yield c, org
    finally:
        tx.rollback(); c.close()


def _seed_verdict(c, org, *, n: int, at: datetime, cause="wrong", reason="bad_timing",
                  actor="founder", capability=CAPABILITY):
    card_id = f"card_lease_{n}"
    c.execute(text(
        "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, "
        "situation, score, expires_at) values (:c, :s, :o, 'prescriptive', 'standard', 'h', "
        "'s', 10, :exp) on conflict (card_id) do nothing"),
        {"c": card_id, "s": f"sig_lease_{n}", "o": org, "exp": at + timedelta(days=7)})
    c.execute(text(
        "insert into card_feedback_verdicts (feedback_id, org_id, card_id, pack_id, pack_version, "
        "authority_pack_revision, capability_id, capability_version, rule_id, cause, reason, "
        "detail, actor_id, verdict_version, occurred_at, created_at) "
        "values (:f, :o, :c, 'admin', '1.0.0', 1, :cap, '1.0.0', 'r', :cause, :reason, '{}', "
        ":actor, 1, :at, :at)"),
        {"f": f"fb_lease_{n}", "o": org, "c": card_id, "cap": capability, "cause": cause,
         "reason": reason, "actor": actor, "at": at})


def test_the_verdicts_are_counted_off_the_real_ledger(conn):
    c, org = conn
    for i in range(3):
        _seed_verdict(c, org, n=i, at=NOW - timedelta(days=i), actor=f"a{i % 2}")
    _seed_verdict(c, org, n=9, at=NOW, cause="run_play", reason=None)
    cohorts = al.read_timing_cohorts(c, org_id=org, since=NOW - timedelta(days=28), until=NOW)
    ours = [x for x in cohorts if x.capability_id == CAPABILITY][0]
    assert ours.verdicts == 4 and ours.bad_timing == 3
    assert ours.distinct_days == 3 and ours.distinct_actors == 2 and ours.distinct_cards == 3
    assert ours.share_bp == 7500


def test_a_quality_complaint_is_not_a_lease(conn):
    """`not_relevant` says the card should not exist. That is calibration's subject, not a lease."""
    c, org = conn
    for i in range(4):
        _seed_verdict(c, org, n=i, at=NOW - timedelta(days=i), reason="not_relevant")
    proposals, refusals = al.lease_proposals(c, org_id=org, policy=LearningPolicy(org_id=org,
                                                                                 revision=1),
                                             now=NOW)
    assert proposals == ()
    assert [r.reason for r in refusals] == ["insufficient_observations"]


def test_the_founders_verdicts_reach_temporary_memories_through_the_pipeline(conn):
    c, org = conn
    for i in range(4):
        _seed_verdict(c, org, n=i, at=NOW - timedelta(days=i), actor=f"a{i % 2}")
    from genios_engine.feedback.brain_pipeline import lease_from_card_feedback

    result = lease_from_card_feedback(c, org_id=org, now=NOW, capability_ids=(CAPABILITY,))
    assert result["published"] == 1, result

    row = c.execute(text(
        "select subject, value, expires_at, active, learning_id from temporary_memories "
        "where org_id=:o and subject=:s"), {"o": org, "s": al.lease_subject(CAPABILITY)}
    ).mappings().first()
    assert row is not None and row["active"] is True
    assert row["expires_at"] == NOW + timedelta(seconds=al.LEASE_TTL_SECONDS)
    assert row["value"]["source"] == "card_feedback"
    # The receipt: the lease names the proposal that produced it, and that proposal was persisted.
    assert c.execute(text("select unit from learning_objects where org_id=:o and learning_id=:l"),
                     {"o": org, "l": row["learning_id"]}).scalar() == al.LEASE_UNIT


def test_the_same_verdicts_twice_do_not_mint_a_second_lease(conn):
    c, org = conn
    for i in range(4):
        _seed_verdict(c, org, n=i, at=NOW - timedelta(days=i), actor=f"a{i % 2}")
    from genios_engine.feedback.brain_pipeline import lease_from_card_feedback

    lease_from_card_feedback(c, org_id=org, now=NOW, capability_ids=(CAPABILITY,))
    again = lease_from_card_feedback(c, org_id=org, now=NOW, capability_ids=(CAPABILITY,))
    assert again["unchanged"] == 1 and again["published"] == 0
    assert c.execute(text("select count(*) from temporary_memories where org_id=:o and subject=:s"),
                     {"o": org, "s": al.lease_subject(CAPABILITY)}).scalar() == 1


def test_the_clock_actually_retires_the_lease_and_says_so(conn):
    c, org = conn
    for i in range(4):
        _seed_verdict(c, org, n=i, at=NOW - timedelta(days=i), actor=f"a{i % 2}")
    from genios_engine.feedback.brain_pipeline import expire_leases, lease_from_card_feedback

    lease_from_card_feedback(c, org_id=org, now=NOW, capability_ids=(CAPABILITY,))
    assert expire_leases(c, org_id=org, now=NOW + timedelta(hours=1)) == 0, "not expired yet"

    after = NOW + timedelta(seconds=al.LEASE_TTL_SECONDS + 1)
    assert expire_leases(c, org_id=org, now=after) == 1
    assert c.execute(text("select active from temporary_memories where org_id=:o and subject=:s"),
                     {"o": org, "s": al.lease_subject(CAPABILITY)}).scalar() is False
    transition = c.execute(text(
        "select from_state, to_state, reason_code, actor from learning_transitions "
        "where org_id=:o and to_state='expired' order by occurred_at desc limit 1"),
        {"o": org}).mappings().first()
    assert transition is not None
    assert (transition["from_state"], transition["reason_code"]) == ("temporary", "lease_expired")
    assert transition["actor"] == "clock"


def test_an_expired_lease_is_invisible_to_a_reader_even_before_it_is_cleared(conn):
    """Expiry is correct at the READ, not only at the sweep. The sweep makes it observable."""
    c, org = conn
    for i in range(4):
        _seed_verdict(c, org, n=i, at=NOW - timedelta(days=i), actor=f"a{i % 2}")
    from genios_engine.contracts.learned_state import snapshot
    from genios_engine.feedback.brain_pipeline import lease_from_card_feedback

    lease_from_card_feedback(c, org_id=org, now=NOW, capability_ids=(CAPABILITY,))
    subject = al.lease_subject(CAPABILITY)
    live = snapshot(c, org_id=org, consumer="delivery", subject=subject, now=NOW)
    assert subject in live.runtime
    dead = snapshot(c, org_id=org, consumer="delivery", subject=subject,
                    now=NOW + timedelta(days=30))
    assert dead.runtime == {}


def test_consent_off_means_no_lease(conn):
    c, org = conn
    for i in range(4):
        _seed_verdict(c, org, n=i, at=NOW - timedelta(days=i), actor=f"a{i % 2}")
    c.execute(text(
        "insert into learning_policies (org_id, revision, snapshot, learning_enabled, created_at) "
        "values (:o, 99, '{}', false, :at)"), {"o": org, "at": NOW})
    from genios_engine.feedback.brain_pipeline import lease_from_card_feedback

    assert lease_from_card_feedback(c, org_id=org, now=NOW) == {"skipped": "consent_disabled"}
    assert c.execute(text("select count(*) from temporary_memories where org_id=:o"),
                     {"o": org}).scalar() == 0


def test_the_card_feedback_route_is_the_caller(conn):
    """REACHED FROM A REAL PATH: the endpoint that records a verdict evaluates the lease."""
    import inspect

    from genios_engine.api import intelligence_routes

    source = inspect.getsource(intelligence_routes.intelligence_feedback)
    assert "lease_from_card_feedback" in source
    assert "capability_ids=(card.capability_id,)" in source
    del conn


def test_the_share_never_rounds_up_into_a_floor_it_did_not_clear():
    """Integer basis points, floored. `round(2*10000/3)` is 6667 and would clear a 6667 floor."""
    assert _cohort(verdicts=3, bad_timing=2).share_bp == 6666
    assert _cohort(verdicts=7, bad_timing=5).share_bp == 7142


def test_a_proposal_the_evidence_does_not_support_is_held_not_published(conn):
    """`admit_proposals` runs Unit 11 first. Without it, a one-click lease would reach the store."""
    c, org = conn
    from genios_engine.feedback.brain_pipeline import admit_proposals

    thin = al._proposal(_cohort(verdicts=1, bad_timing=1, days=1, actors=1, cards=1),
                        org_id=org, policy=LearningPolicy(org_id=org, revision=1), now=NOW)
    counts = admit_proposals(c, [thin], policy=LearningPolicy(org_id=org, revision=1), now=NOW)
    assert counts.held == 1 and counts.published == 0
    assert c.execute(text("select count(*) from temporary_memories where org_id=:o"),
                     {"o": org}).scalar() == 0


def test_a_lease_whose_clock_has_already_run_out_is_refused_before_it_is_stored(conn):
    """Preflight, not validation, is what stops it — and it runs BEFORE anything is persisted."""
    c, org = conn
    from genios_engine.feedback.brain_pipeline import admit_proposals

    policy = LearningPolicy(org_id=org, revision=1)
    obj = al._proposal(_cohort(), org_id=org, policy=policy, now=NOW)
    stale = type(obj)(
        org_id=obj.org_id, unit=obj.unit, target=obj.target, subject=obj.subject,
        proposed_value=dict(obj.proposed_value), evidence=obj.evidence,
        visibility=obj.visibility, first_seen_at=obj.first_seen_at,
        last_seen_at=obj.last_seen_at, policy_key=obj.policy_key,
        expires_at=NOW - timedelta(days=1))
    assert validate_learning(stale, policy)[0], "the evidence is fine; the clock is not"
    counts = admit_proposals(c, [stale], policy=policy, now=NOW)
    assert counts.refused == 1 and counts.published == 0
    assert c.execute(text("select count(*) from learning_objects where org_id=:o and unit=:u"),
                     {"o": org, "u": al.LEASE_UNIT}).scalar() == 0, "refused means never stored"
