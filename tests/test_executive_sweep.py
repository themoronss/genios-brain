"""Layer 5 · the orchestrator, actually executed.

``sweep.py`` and ``execution_store.py`` are the two modules that turn eleven correct units into a
running layer, and until this file existed neither had ever had a line executed — they were
proven only by static SQL analysis. Static analysis cannot tell you that a COMPLETE verdict
closes the row *and* writes the outcome *and* logs the event. That is what is tested here.

The database is a double (``tests/executive_fakes.py``) that keeps real rows and implements what
each statement means. It cannot catch a SQL error; ``test_executive_store_schema.py`` covers
that, and a run against real Postgres is still outstanding. What it does catch is every way the
control flow can be wrong, which is the part that no amount of schema checking would reveal.

The scenarios are the lifecycle a commitment actually lives: planned, delivered, nudged,
escalated, and then ended one of the five ways it can end.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

from genios_engine.contracts.execution import ExecutionState
from genios_engine.executive import execution_store as store
from genios_engine.executive import sweep
from genios_engine.executive.assignment import (
    PgSeatDirectory,
    StaticSeatDirectory,
    resolve_owner,
)
from genios_engine.executive.execution import build_from_decision
from genios_engine.platform.canonical import canonical_dumps, semantic_hash

from tests.executive_fakes import FakeDB, FakeEngine, UnhandledStatement
from tests.test_executive_execution import NOW, build, make_decision

PACK = {"scoring": {"execution": {}}}


def world(*, channels=("slack",), owner="rep@acme.io", subject="deal_9") -> FakeDB:
    db = FakeDB()
    db.add_seat("seat_rep", email="rep@acme.io", manager="seat_mgr")
    db.add_seat("seat_mgr", email="mgr@acme.io", role="admin")
    db.channels = list(channels)
    db.set_facts(subject, {"deal.owner": owner, "deal.status": "open"}, attrs={})
    return db


def planted(db: FakeDB, *, decision=None, subject="deal_9") -> None:
    """Put one authoritative, uncommitted decision in front of the planning pass."""
    decision = decision or make_decision()
    candidate = decision.candidates[0]
    db.plannable.append({
        "signal_id": "sig_1", "subject_node_id": subject, "node_type": "deal",
        "run_id": "run_1", "capability_id": decision.capability_id,
        "capability_version": decision.capability_version, "config_snapshot_id": "cfg_1",
        "context_snapshot_id": "ctx_1", "decision_hash": decision.semantic_hash,
        "decision_core": json.loads(canonical_dumps({
            "expires_at": decision.expires_at,
            "do_nothing_consequence": decision.do_nothing_consequence,
            "outcome_window_days": decision.outcome_window_days})),
        "decision_confidence_bp": decision.confidence_bp,
        "missing_data": list(decision.uncertainty),
        "candidate_id": candidate.candidate_id, "play_id": candidate.play_id,
        "play_version": candidate.play_version,
        "parameters": json.loads(canonical_dumps(dict(candidate.parameters))),
        "score_components": dict(candidate.score_components),
        "final_utility_bp": candidate.utility_bp,
        "evidence_refs": [{"evidence_id": item} for item in candidate.evidence_ids]})


def persisted(db: FakeDB, *, execution=None, at=NOW, state=ExecutionState.CREATED):
    """Write a commitment straight through the real store, bypassing the planning query."""
    execution = execution or build().require()
    engine = FakeEngine(db)
    with engine.begin() as conn:
        store.persist(conn, execution, next_check_at=at, signal_id="sig_1", state=state)
    return execution, engine


# --- pass 1: planning ------------------------------------------------------------------------

def test_planning_writes_the_commitment_its_steps_and_its_ladder():
    db = world()
    planted(db)
    report = sweep.plan_commitments(FakeEngine(db), "org_1", eval_time=NOW, effective=PACK)

    assert report.created == 1 and report.reasons["built"] == 1
    row = db.open_execution()
    assert row["state"] == "created" and row["assignee"] == "seat_rep"
    assert row["routing_rule"] == "rule1_owner" and row["signal_id"] == "sig_1"
    assert len(db.execution_actions) == 3
    assert [r["day_offset"] for r in db.execution_escalations] == [1, 2, 4, 7]
    assert db.events_of("execution.created")


def test_planning_twice_produces_one_commitment():
    """The pass is meant to run on a timer. Idempotence has to be a property of the write, not of
    a caller remembering to check first."""
    db = world()
    planted(db)
    engine = FakeEngine(db)
    first = sweep.plan_commitments(engine, "org_1", eval_time=NOW, effective=PACK)
    second = sweep.plan_commitments(engine, "org_1", eval_time=NOW, effective=PACK)
    assert first.created == 1 and second.created == 0
    assert len(db.executions) == 1


def test_planning_refuses_an_unreadable_expiry_rather_than_guessing():
    db = world()
    planted(db)
    db.plannable[0]["decision_core"] = {"do_nothing_consequence": "x"}
    report = sweep.plan_commitments(FakeEngine(db), "org_1", eval_time=NOW, effective=PACK)
    assert report.created == 0 and report.reasons["unreadable_expiry"] == 1
    assert not db.executions


def test_planning_counts_refusals_by_reason_not_as_one_skipped_bucket():
    db = world()
    planted(db)
    db.plannable[0]["parameters"] = {**db.plannable[0]["parameters"], "steps": []}
    report = sweep.plan_commitments(FakeEngine(db), "org_1", eval_time=NOW, effective=PACK)
    assert report.reasons == {"no_steps": 1} and report.examined == 1


def test_an_unowned_deal_is_committed_unowned_but_still_reachable():
    """Dropping it is how a system quietly stops mentioning the accounts nobody owns.

    Ownership and recipiency are answered separately and both answers are recorded. The
    commitment stays UNOWNED — audience `admin_queue`, `payload.communication.assignee` null,
    routing rule `rule3_admin_queue` — so nothing claims a person promised this. But the
    `assignee` COLUMN carries the seat that will actually receive it, exactly as `cards.assignee`
    already does, and that is what the executive bridge's `x.assignee is not null` predicate,
    the outbox recipient and the escalation ladder all read.
    """
    db = world(owner="")
    db.set_facts("deal_9", {"deal.status": "open"}, attrs={})
    planted(db)
    sweep.plan_commitments(FakeEngine(db), "org_1", eval_time=NOW, effective=PACK)
    row = db.open_execution()
    assert row is not None
    assert row["routing_rule"] == "rule3_admin_queue" and row["audience"] == "admin_queue"
    assert row["assignee"] == "seat_mgr", "the admin mans the queue; the row must say so"
    payload = json.loads(row["payload"])
    assert payload["communication"]["assignee"] is None, "still nobody's to OWN"
    assert payload["remindable"] is True
    assert db.execution_escalations, "a reachable commitment gets the ladder it was promised"


def test_a_commitment_with_no_admin_to_receive_it_gets_no_ladder():
    """The counterweight: reachability is measured, never assumed.

    An org with no active admin has nobody on the other end at all. The commitment is still
    planned and still tracked — never dropped — but its ladder is empty and it is not
    remindable, because escalating into an empty room is noise rather than diligence.
    """
    db = world(owner="")
    db.seats["seat_mgr"]["role"] = "member"          # the org's only admin is gone
    db.set_facts("deal_9", {"deal.status": "open"}, attrs={})
    planted(db)
    sweep.plan_commitments(FakeEngine(db), "org_1", eval_time=NOW, effective=PACK)
    row = db.open_execution()
    assert row is not None and row["routing_rule"] == "rule3_unrouted"
    assert row["assignee"] is None
    assert json.loads(row["payload"])["remindable"] is False
    assert not db.execution_escalations, "an unreachable commitment escalates into an empty room"


def unreachable_commitment():
    """A commitment built the way all 203 production rows were: with nobody resolvable.

    Not a contrived fixture. Until this fix the ONLY resolvable owner rules read facts no
    producer writes, so every commitment ever built came out of the builder in exactly this
    shape — `remindable=false`, empty ladder, `communication.assignee=null`.
    """
    return build_from_decision(
        make_decision(), org_id="org_1", reasoning_run_id="run_1", config_snapshot_id="cfg_1",
        decision_hash=semantic_hash({"fixture": "legacy"}), eval_time=NOW,
        directory=StaticSeatDirectory({}), facts={}, available_channels={"slack", "in_app"},
        subject_ref="deal_9", subject_type="deal").require()


def test_a_commitment_stored_unreachable_is_healed_when_the_directory_can_name_somebody():
    """The 170 rows that were already sitting silent when the defect was found.

    ``plan_commitments`` never re-examines a decision that already has a live commitment, so a
    row built unreachable stays unreachable for the whole of its life — no replan, no second
    chance. Reachability is the one thing on a commitment that is a fact about the ORG rather
    than a promise to its owner, so the lifecycle pass re-asks it and heals the row in place.
    """
    db = world(owner="")                     # nobody owns it, exactly as production has it
    db.set_facts("deal_9", {"deal.status": "open"}, attrs={})
    execution, engine = persisted(db, execution=unreachable_commitment(),
                                  state=ExecutionState.PENDING)
    assert execution.remindable is False and db.open_execution()["assignee"] is None

    report = sweep.run_lifecycle(engine, eval_time=NOW + timedelta(days=2), effective=PACK)

    row = db.open_execution()
    assert row["assignee"] == "seat_mgr"
    # The channel is re-asked too, not only the recipient: `in_app` was chosen BECAUSE nobody
    # could be reached, and leaving it would make the commitment remindable but still uncarried
    # — Layer 6's bridge matches on the channel Layer 5 recorded.
    assert row["routing_rule"] == "reachability_restored_band_critical_interrupt"
    assert row["channel_id"] == "slack" and row["interrupt"] is True
    assert json.loads(row["payload"])["remindable"] is True
    assert report.reminded == 1 and db.events_of("execution.reminded")
    # The frozen half stays frozen. The heal never invents ladder rungs the commitment never
    # promised — it was woken by the untouched trigger, which needs no ladder at all.
    assert not db.execution_escalations
    assert db.events_of("execution.reminded")[0]["reason_code"] == "untouched"


def test_healing_is_idempotent_and_never_fires_when_there_is_nobody():
    """Two guarantees in one place, because they are the two ways a heal goes wrong.

    A heal that ran every pass would rewrite the routing row forever; a heal that invented a
    recipient would nudge an empty room. The first is proved by running the sweep twice, the
    second by an org whose only admin is gone.
    """
    db = world(owner="")
    db.set_facts("deal_9", {"deal.status": "open"}, attrs={})
    _, engine = persisted(db, execution=unreachable_commitment(), state=ExecutionState.PENDING)
    sweep.run_lifecycle(engine, eval_time=NOW + timedelta(days=2), effective=PACK)
    reassignments = len(db.events_of("execution.reassigned"))
    sweep.run_lifecycle(engine, eval_time=NOW + timedelta(days=3), effective=PACK)
    assert len(db.events_of("execution.reassigned")) == reassignments, "healed once, not on every pass"

    orphan = FakeDB()
    orphan.add_seat("seat_rep", email="rep@acme.io")          # a member, no admin anywhere
    orphan.channels = ["slack"]
    orphan.set_facts("deal_9", {"deal.status": "open"}, attrs={})
    _, orphan_engine = persisted(orphan, execution=unreachable_commitment(),
                                 state=ExecutionState.PENDING)
    sweep.run_lifecycle(orphan_engine, eval_time=NOW + timedelta(days=2), effective=PACK)
    assert orphan.open_execution()["assignee"] is None
    assert not orphan.events_of("execution.reminded"), "nobody to nudge, so nothing is said"


# --- pass 2: first delivery ---------------------------------------------------------------

def test_the_first_pass_validates_then_delivers():
    db = world()
    execution, engine = persisted(db)
    report = sweep.run_lifecycle(engine, eval_time=NOW + timedelta(minutes=1), effective=PACK)

    row = db.open_execution()
    assert row["state"] == "pending" and row["delivered_at"] is not None
    assert report.transitioned == 1
    assert db.events_of("execution.delivered")
    # Order is the invariant: nothing may be delivered before the guard has spoken.
    statements = db.statements()
    guard = next(i for i, s in enumerate(statements) if "select 1 from signals s" in s)
    move = next(i for i, s in enumerate(statements) if "update executions set state=" in s)
    assert guard < move


def test_a_commitment_whose_owner_left_before_delivery_is_suppressed_not_delivered():
    db = world()
    persisted(db)
    db.seats["seat_rep"]["active"] = False
    engine = FakeEngine(db)
    sweep.run_lifecycle(engine, eval_time=NOW + timedelta(minutes=1), effective=PACK)

    row = db.open_execution()
    assert row["state"] == "created"
    suppressed = db.events_of("execution.suppressed")
    assert suppressed and suppressed[0]["reason_code"] == "owner_inactive_at_build"
    assert row["next_check_at"] is not None, "a suppressed moment must still be re-examined"


# --- pass 2: the endings ----------------------------------------------------------------------

def test_the_world_finishing_the_job_closes_the_commitment_and_writes_the_outcome():
    """The single most important path in the layer: it noticed, so it stopped asking."""
    db = world()
    execution, engine = persisted(db, state=ExecutionState.PENDING)
    db.observe("deal_9", "prospect_reply", NOW + timedelta(hours=6))

    report = sweep.run_lifecycle(engine, eval_time=NOW + timedelta(days=1), effective=PACK)

    row = db.executions[0]
    assert row["state"] == "completed" and row["closed_at"] is not None
    assert row["close_reason"] == "outcome_observed" and report.closed == 1
    outcome = db.execution_outcomes[0]
    assert outcome["label"] == "succeeded" and outcome["outcome_kind"] == "prospect_reply"
    assert outcome["execution_id"] == execution.execution_id


def test_a_closed_lost_deal_cancels_rather_than_being_chased():
    db = world()
    db.set_facts("deal_9", {"deal.owner": "rep@acme.io", "deal.status": "closed_lost"})
    _, engine = persisted(db, state=ExecutionState.PENDING)
    sweep.run_lifecycle(engine, eval_time=NOW + timedelta(days=1), effective=PACK)

    assert db.executions[0]["close_reason"] == "subject_closed"
    assert db.execution_outcomes[0]["label"] == "cancelled_by_world"


def test_revoked_authority_stops_everything_mid_flight():
    db = world()
    db.authority_ok = False
    _, engine = persisted(db, state=ExecutionState.PENDING)
    sweep.run_lifecycle(engine, eval_time=NOW + timedelta(days=1), effective=PACK)

    assert db.executions[0]["close_reason"] == "authority_revoked"
    assert db.execution_outcomes[0]["label"] == "cancelled_by_system"


def test_the_deadline_passing_expires_it_and_records_how_far_it_got():
    db = world()
    execution, engine = persisted(db, state=ExecutionState.PENDING)
    with engine.begin() as conn:
        store.complete_action(conn, org_id="org_1", execution_id=execution.execution_id,
                              action_id="a1", at=NOW + timedelta(hours=2), actor="seat_rep")

    sweep.run_lifecycle(engine, eval_time=execution.deadline_at + timedelta(hours=1),
                        effective=PACK)

    outcome = db.execution_outcomes[0]
    assert outcome["terminal_state"] == "expired"
    assert outcome["label"] == "expired_in_progress"
    assert outcome["actions_completed"] == 1 and outcome["progress_bp"] == 3_333


def test_a_human_dismissal_cancels_on_the_next_pass():
    db = world()
    execution, engine = persisted(db, state=ExecutionState.PENDING)
    with engine.begin() as conn:
        store.log_event(conn, org_id="org_1", execution_id=execution.execution_id,
                        kind="execution.cancelled", reason_code="human_dismissed",
                        actor="seat_rep", occurred_at=NOW + timedelta(hours=1))

    sweep.run_lifecycle(engine, eval_time=NOW + timedelta(hours=2), effective=PACK)
    assert db.executions[0]["close_reason"] == "human_dismissed"
    assert db.execution_outcomes[0]["label"] == "cancelled_by_human"


def test_an_outcome_is_written_exactly_once():
    db = world()
    _, engine = persisted(db, state=ExecutionState.PENDING)
    db.observe("deal_9", "prospect_reply", NOW + timedelta(hours=6))
    for _ in range(3):
        sweep.run_lifecycle(engine, eval_time=NOW + timedelta(days=1), effective=PACK)
    assert len(db.execution_outcomes) == 1


# --- pass 2: nudging and escalating -------------------------------------------------------

def test_a_due_rung_reminds_fires_the_rung_and_resolves_the_target_at_fire_time():
    db = world()
    execution, engine = persisted(db, state=ExecutionState.PENDING)
    rung = next(step for step in execution.escalation if step.audience.value == "manager")

    sweep.run_lifecycle(engine, eval_time=rung.fires_at + timedelta(minutes=1), effective=PACK)

    fired = [r for r in db.execution_escalations if r["fired_at"] is not None]
    assert [r["day_offset"] for r in fired] == [rung.day_offset]
    assert fired[0]["target_seat"] == "seat_mgr", "the manager is resolved now, not at plan time"
    row = db.executions[0]
    assert row["reminder_count"] == 1 and row["escalation_count"] == 1
    assert db.events_of("execution.reminded") and db.events_of("execution.escalated")


def test_a_rung_never_fires_twice_however_often_the_sweep_runs():
    db = world()
    execution, engine = persisted(db, state=ExecutionState.PENDING)
    rung = execution.escalation[0]
    at = rung.fires_at + timedelta(minutes=1)
    for _ in range(4):
        sweep.run_lifecycle(engine, eval_time=at, effective=PACK)
    fired = [r for r in db.execution_escalations if r["fired_at"] is not None]
    assert len(fired) == 1 and db.executions[0]["reminder_count"] == 1


def test_a_quiet_commitment_is_rescheduled_rather_than_nudged():
    db = world()
    _, engine = persisted(db, state=ExecutionState.PENDING)
    at = NOW + timedelta(hours=2)
    report = sweep.run_lifecycle(engine, eval_time=at, effective=PACK)

    row = db.executions[0]
    assert report.reminded == 0 and row["reminder_count"] == 0
    assert row["next_check_at"] > at, "every pass must leave a next meaningful moment"
    assert not db.events_of("execution.reminded")


def test_nothing_is_ever_nudged_about_work_the_world_already_did():
    """The guard runs before the reminder unit, and this proves the ordering holds in the sweep
    rather than only in the unit tests."""
    db = world()
    execution, engine = persisted(db, state=ExecutionState.PENDING)
    rung = execution.escalation[-1]
    db.observe("deal_9", "meeting_booked", NOW + timedelta(hours=3))

    sweep.run_lifecycle(engine, eval_time=rung.fires_at + timedelta(hours=1), effective=PACK)

    assert db.executions[0]["state"] == "completed"
    assert not db.events_of("execution.reminded")
    assert not [r for r in db.execution_escalations if r["fired_at"] is not None]


# --- pass 2: progress and rerouting ---------------------------------------------------------

def test_ticking_a_step_moves_a_pending_commitment_to_running():
    db = world()
    execution, engine = persisted(db, state=ExecutionState.PENDING)
    with engine.begin() as conn:
        store.complete_action(conn, org_id="org_1", execution_id=execution.execution_id,
                              action_id="a1", at=NOW + timedelta(hours=1), actor="seat_rep")

    sweep.run_lifecycle(engine, eval_time=NOW + timedelta(hours=2), effective=PACK)
    row = db.executions[0]
    assert row["state"] == "running" and row["first_touch_at"] is not None


def test_every_step_ticked_with_no_evidence_becomes_waiting_not_completed():
    """A sweep may recognise work in flight; it may never decide on somebody's behalf that they
    succeeded."""
    db = world()
    execution, engine = persisted(db, state=ExecutionState.PENDING)
    with engine.begin() as conn:
        for action in execution.actions:
            store.complete_action(conn, org_id="org_1", execution_id=execution.execution_id,
                                  action_id=action.action_id, at=NOW + timedelta(hours=1),
                                  actor="seat_rep")

    at = NOW + timedelta(hours=2)
    sweep.run_lifecycle(engine, eval_time=at, effective=PACK)          # pending → running
    # The first pass scheduled its own next look. Running again before that horizon is correctly
    # a no-op — the sweep is a due-time query, not a full walk of every open row every time.
    assert db.executions[0]["next_check_at"] > at
    assert sweep.run_lifecycle(engine, eval_time=at + timedelta(hours=1),
                               effective=PACK).examined == 0

    sweep.run_lifecycle(engine, eval_time=db.executions[0]["next_check_at"], effective=PACK)
    assert db.executions[0]["state"] == "waiting"
    assert not db.execution_outcomes


def test_a_departed_owner_hands_the_commitment_on_instead_of_losing_it():
    db = world()
    persisted(db, state=ExecutionState.PENDING)
    engine = FakeEngine(db)
    db.seats["seat_rep"]["active"] = False
    db.set_facts("deal_9", {"deal.owner": "mgr@acme.io", "deal.status": "open"})

    report = sweep.run_lifecycle(engine, eval_time=NOW + timedelta(days=1), effective=PACK)

    row = db.executions[0]
    assert report.reassigned == 1 and row["assignee"] == "seat_mgr"
    assert row["closed_at"] is None, "reassignment must never close the commitment"
    assert db.events_of("execution.reassigned")


def test_reassignment_keeps_one_commitment_and_one_ladder():
    db = world()
    execution, engine = persisted(db, state=ExecutionState.PENDING)
    rungs_before = len(db.execution_escalations)
    with engine.begin() as conn:
        store.reassign(conn, org_id="org_1", execution_id=execution.execution_id,
                       assignee="seat_mgr", audience="owner", routing_rule="manual_reassign",
                       at=NOW + timedelta(hours=1))
    assert len(db.executions) == 1
    assert len(db.execution_escalations) == rungs_before


# --- resilience ------------------------------------------------------------------------------

def test_one_broken_commitment_does_not_stop_the_sweep():
    """This sweep is the only thing keeping commitments moving; an all-or-nothing pass would let
    a single bad row stall the layer."""
    db = world()
    good, engine = persisted(db, state=ExecutionState.PENDING)
    # A genuinely different decision, not just a different plan — otherwise the partial unique
    # index correctly rejects it and there is no second row to break.
    other = build(decision=make_decision(utility_bp=5_000),
                  decision_hash=semantic_hash({"fixture": "second"})).require()
    with engine.begin() as conn:
        store.persist(conn, other, next_check_at=NOW, signal_id="sig_2",
                      state=ExecutionState.PENDING)
    broken = next(r for r in db.executions if r["execution_id"] == other.execution_id)
    broken["payload"] = json.loads(broken["payload"])
    broken["payload"].pop("actions")                     # a plan storage can no longer explain

    db.observe("deal_9", "prospect_reply", NOW + timedelta(hours=6))
    report = sweep.run_lifecycle(engine, eval_time=NOW + timedelta(days=1), effective=PACK)

    assert report.examined == 2
    assert report.reasons.get("processing_error") == 1
    healthy = next(r for r in db.executions if r["execution_id"] == good.execution_id)
    assert healthy["state"] == "completed", "the healthy commitment still completed"


def test_the_double_refuses_statements_it_does_not_model():
    """A guard against the guard. If an unmodelled query returned empty, every test that depended
    on it would pass while proving nothing."""
    db = FakeDB()
    with pytest.raises(UnhandledStatement):
        db.execute("select * from something_nobody_wrote", {})


# --- the store's own guarantees ---------------------------------------------------------------

def test_persist_is_idempotent_and_reports_it():
    db = world()
    execution = build().require()
    engine = FakeEngine(db)
    with engine.begin() as conn:
        first = store.persist(conn, execution, next_check_at=NOW)
        second = store.persist(conn, execution, next_check_at=NOW)
    assert first["created"] is True and second["created"] is False
    assert len(db.executions) == 1 and len(db.execution_actions) == 3


def test_a_stored_commitment_rehydrates_to_the_object_that_was_written():
    db = world()
    execution, engine = persisted(db)
    with engine.begin() as conn:
        restored, row = store.load(conn, "org_1", execution.execution_id)
    assert restored.semantic_hash == execution.semantic_hash
    assert restored.execution_id == row["execution_id"]


def test_a_lost_transition_race_is_reported_not_forced():
    from genios_engine.executive.lifecycle import transition
    db = world()
    execution, engine = persisted(db, state=ExecutionState.PENDING)
    move = transition(ExecutionState.CREATED, ExecutionState.PENDING, reason_code="x",
                      actor="system", at=NOW)                      # stale view of the state
    with engine.begin() as conn:
        assert store.apply_transition(conn, org_id="org_1",
                                      execution_id=execution.execution_id, move=move) is False
    assert db.executions[0]["state"] == "pending"


def test_completing_the_same_action_twice_is_a_no_op():
    db = world()
    execution, engine = persisted(db, state=ExecutionState.PENDING)
    with engine.begin() as conn:
        first = store.complete_action(conn, org_id="org_1",
                                      execution_id=execution.execution_id, action_id="a1",
                                      at=NOW + timedelta(hours=1), actor="seat_rep")
        second = store.complete_action(conn, org_id="org_1",
                                       execution_id=execution.execution_id, action_id="a1",
                                       at=NOW + timedelta(hours=2), actor="seat_rep")
    assert first is True and second is False
    assert len(db.events_of("execution.action_completed")) == 1


def test_supersede_frees_the_key_so_a_new_plan_can_land():
    db = world()
    execution, engine = persisted(db)
    replacement = build(decision=make_decision(steps=("Draft the note.",))).require()
    with engine.begin() as conn:
        assert store.supersede(conn, org_id="org_1", execution_id=execution.execution_id,
                               by_execution_id=replacement.execution_id,
                               at=NOW + timedelta(hours=1)) is True
        again = store.persist(conn, replacement, next_check_at=NOW + timedelta(hours=1))
    assert again["created"] is True and len(db.executions) == 2
    assert db.executions[0]["superseded_by"] == replacement.execution_id


def test_the_seat_directory_resolves_by_id_and_by_email():
    db = world()
    engine = FakeEngine(db)
    with engine.begin() as conn:
        directory = PgSeatDirectory(conn=conn, org_id="org_1")
        assert directory.active_seat("rep@acme.io") == "seat_rep"
        assert directory.active_seat("seat_rep") == "seat_rep"
        assert directory.active_seat("nobody@acme.io") is None
        assert directory.manager_of("seat_rep") == "seat_mgr"
        assert directory.admins() == ("seat_mgr",)
        assert resolve_owner(facts={"deal.owner": {"value": "rep@acme.io"}}, attrs={},
                             directory=directory).seat_id == "seat_rep"


def test_active_channels_always_include_the_card_surface():
    db = world(channels=())
    engine = FakeEngine(db)
    with engine.begin() as conn:
        assert store.active_channels(conn, "org_1") == frozenset({"in_app"})


def test_run_executive_plans_then_runs_the_lifecycle_in_one_pass():
    """Planning first so a commitment created this minute is validated in the same pass rather
    than waiting for the next one."""
    db = world()
    planted(db)
    result = sweep.run_executive(FakeEngine(db), "org_1", eval_time=NOW, effective=PACK)
    assert result["planned"].created == 1
    assert result["lifecycle"].examined == 1
    assert db.open_execution()["state"] == "pending"


# --- the scheduler heartbeat -------------------------------------------------------------

def test_the_maintenance_heartbeat_actually_drives_layer_five():
    """Wiring is a claim until something proves it.

    Layer 5 is worthless on a timer nobody set: commitments would never be planned, never
    advance, and never escalate. This asserts the scheduled heartbeat calls the executive sweep,
    that it runs *before* distribution (so a reminder decided this tick leaves this tick), and
    that it only sweeps tenants with an active pack.
    """
    import inspect

    from genios_engine.api import routes

    source = inspect.getsource(routes.run_maintenance_sweep)
    assert "run_executive" in source, "the heartbeat never calls the executive sweep"
    assert source.index("run_executive") < source.index("run_distribution"), (
        "the executive pass must run before distribution, or a reminder decided this tick "
        "waits a whole interval to leave")
    assert '"executive"' in source, "the sweep result must report what Layer 5 did"

    scope = inspect.getsource(routes._executive_orgs)
    assert "tenant_packs" in scope and "state='active'" in scope, (
        "sweeping tenants with no applied pack is pure cost — Layer 4 produces nothing to commit to")


def test_executive_orgs_actually_executes_and_returns_active_pack_tenants(monkeypatch):
    """Enumeration must RUN, not merely contain the right SQL text.

    The sibling assertion above reads source text, and for 15 days that was the only guard:
    ``_executive_orgs`` called ``text(...)`` with no ``sqlalchemy`` import in scope, so every
    heartbeat tick raised ``NameError`` into a bare ``{"error": True}`` and Layer 5 never planned
    a single commitment. Source text cannot see a NameError inside the function it inspects — only
    calling it can.
    """
    from types import SimpleNamespace

    from genios_engine.api import routes

    captured: dict[str, str] = {}

    class _Conn:
        def execute(self, stmt, *_a, **_kw):
            captured["sql"] = str(stmt)
            return [("org_a",), ("org_b",)]

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    monkeypatch.setattr(routes, "_graph",
                        SimpleNamespace(engine=SimpleNamespace(connect=lambda: _Conn())))

    assert routes._executive_orgs() == ["org_a", "org_b"]
    assert "tenant_packs" in captured["sql"] and "state='active'" in captured["sql"]


def test_a_broken_executive_pass_cannot_kill_the_heartbeat():
    """The heartbeat also drives card expiry, retention and delivery. It must degrade, never die."""
    import inspect

    from genios_engine.api import routes

    source = inspect.getsource(routes.run_maintenance_sweep)
    block = source[source.index("executive = None"):source.index("# L6 distribution")]
    assert block.count("except Exception") >= 2, (
        "the executive pass needs both a per-org guard and an outer guard — org enumeration is "
        "a database round trip like any other")
    assert '"error": True' in block
