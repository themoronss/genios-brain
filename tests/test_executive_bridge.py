"""Layer 5 → Layer 6 · the wire, executed.

Before the bridge existed, Layer 5 could decide somebody needed nudging, record the decision,
fire the escalation rung — and nothing left the building. The reminder was a row. This file
proves the row becomes a message, and proves the three guarantees that make it safe to send:

  * **Layer 5's channel choice is obeyed.** A commitment planned for the digest is not pushed.
  * **Nothing new is ever said.** The message contains only values Layer 5 attached to the event.
  * **Exactly once, and never stale.** The unique key absorbs a re-run, and a commitment that
    closed while the message sat in the retry backoff is cancelled rather than delivered.

The layer direction is the point of the design and is asserted here too: Layer 5 writes the
decision, Layer 6 reads it. Nothing in ``executive/`` knows this module exists.
"""

from __future__ import annotations

import json
from datetime import timedelta

from genios_engine.contracts.execution import ExecutionState
from genios_engine.deliver import executive_bridge as bridge
from genios_engine.deliver.channels.slack import format_reminder_message
from genios_engine.executive import execution_store as store
from genios_engine.executive import sweep

from tests.executive_fakes import FakeEngine
from tests.test_executive_sweep import PACK, persisted, world
from tests.test_executive_execution import NOW


def nudged(db, *, channel="slack"):
    """Drive a real commitment to the point where Layer 5 has decided to speak."""
    execution, engine = persisted(db, state=ExecutionState.PENDING)
    if channel != "slack":
        db.executions[0]["channel_id"] = channel
    rung = execution.escalation[0]
    sweep.run_lifecycle(engine, eval_time=rung.fires_at + timedelta(minutes=1), effective=PACK)
    return execution, engine


# --- the wire ---------------------------------------------------------------------------------

def test_a_layer_five_reminder_becomes_a_queued_message():
    db = world()
    db.cards.append({"card_id": "card_1", "signal_id": "sig_1"})
    execution, engine = nudged(db)
    assert db.events_of("execution.reminded"), "precondition: Layer 5 decided to speak"
    assert not db.delivery_outbox

    bridge.link_commitment_cards(engine, "org_1")
    queued = bridge.enqueue_executive_messages(engine, "org_1", base_url="https://app.test")

    assert queued == 1 and len(db.delivery_outbox) == 1
    row = db.delivery_outbox[0]
    assert row["channel"] == "slack" and row["status"] == "queued"
    assert row["card_id"].startswith(bridge.EXECUTIVE_PREFIX)
    assert bridge.parse_executive_card_id(row["card_id"])[0] == execution.execution_id


def test_the_message_says_only_what_layer_five_grounded():
    """The bridge has no access to the graph and cannot look anything up. That is what makes the
    invention guarantee structural rather than a matter of discipline."""
    db = world()
    _, engine = nudged(db)
    bridge.enqueue_executive_messages(engine, "org_1")

    payload = json.loads(db.delivery_outbox[0]["payload"])
    text = payload["blocks"][0]["text"]["text"]
    facts = db.events_of("execution.reminded")[0]["detail"]["facts"]

    assert facts["goal"] in text
    assert facts["consequence"] in text
    assert facts["next_action"] in text
    # Every number in the message must be one Layer 5 put in the corpus.
    import re
    grounded = {str(value) for value in facts.values() if isinstance(value, int)}
    for number in re.findall(r"\b\d+\b", text):
        assert number in grounded, f"{number} appears in the message but not in the corpus"


def test_a_commitment_planned_for_the_digest_is_not_pushed():
    """Respecting this is the whole reason Layer 5 was given the channel decision."""
    db = world()
    nudged(db, channel="digest")
    assert bridge.enqueue_executive_messages(FakeEngine(db), "org_1") == 0
    assert not db.delivery_outbox


def test_an_unrouted_commitment_is_never_pushed():
    db = world()
    _, engine = nudged(db)
    db.executions[0]["assignee"] = None
    db.delivery_outbox.clear()
    assert bridge.enqueue_executive_messages(engine, "org_1") == 0


def test_enqueueing_twice_queues_one_message():
    db = world()
    _, engine = nudged(db)
    first = bridge.enqueue_executive_messages(engine, "org_1")
    second = bridge.enqueue_executive_messages(engine, "org_1")
    assert first == 1 and second == 0 and len(db.delivery_outbox) == 1


def test_a_second_reminder_is_a_second_message():
    """Deduplication is per reminder, not per commitment — otherwise day 7 would be silent
    because day 1 already sent."""
    db = world()
    execution, engine = nudged(db)
    bridge.enqueue_executive_messages(engine, "org_1")

    later = execution.escalation[1]
    sweep.run_lifecycle(engine, eval_time=later.fires_at + timedelta(minutes=1), effective=PACK)
    assert bridge.enqueue_executive_messages(engine, "org_1") == 1
    assert len(db.delivery_outbox) == 2


def test_an_escalation_is_delivered_to_the_resolved_rung_target():
    """Resolving a manager into the audit row is not enough: the actual outbox recipient must
    be that manager, and the rung's own interrupt policy must replace the owner's base plan."""
    db = world()
    execution, engine = persisted(db, state=ExecutionState.BLOCKED)
    rung = execution.escalation[2]
    sweep.run_lifecycle(engine, eval_time=rung.fires_at + timedelta(minutes=1), effective=PACK)

    event = db.events_of("execution.reminded")[-1]
    assert event["detail"]["target_seat"] == "seat_mgr"
    assert event["detail"]["target_audience"] == "manager"
    assert bridge.enqueue_executive_messages(engine, "org_1") == 1
    outbox = db.delivery_outbox[-1]
    assert outbox["recipient"] == "seat_mgr"
    assert outbox["interrupt"] is rung.interrupt


def test_a_closed_commitment_is_cancelled_at_send_not_delivered():
    """A reminder can sit through a retry backoff, and the customer can reply inside that
    window. Sending it then is the exact nudge this layer exists to never send."""
    db = world()
    _, engine = nudged(db)
    bridge.enqueue_executive_messages(engine, "org_1")
    card_id = db.delivery_outbox[0]["card_id"]

    with engine.begin() as conn:
        assert bridge.executive_delivery_is_live(conn, "org_1", card_id,
                                                 now=NOW + timedelta(days=1)) is True

    db.executions[0]["closed_at"] = NOW + timedelta(days=1)
    with engine.begin() as conn:
        assert bridge.executive_delivery_is_live(conn, "org_1", card_id,
                                                 now=NOW + timedelta(days=2)) is False


def test_an_expired_commitment_is_not_delivered_either():
    db = world()
    _, engine = nudged(db)
    bridge.enqueue_executive_messages(engine, "org_1")
    card_id = db.delivery_outbox[0]["card_id"]
    with engine.begin() as conn:
        beyond = db.executions[0]["expires_at"] + timedelta(hours=1)
        assert bridge.executive_delivery_is_live(conn, "org_1", card_id, now=beyond) is False


def test_transport_success_is_what_marks_a_commitment_delivered():
    db = world()
    execution, engine = nudged(db)
    bridge.enqueue_executive_messages(engine, "org_1")
    outbox = db.delivery_outbox[0]
    assert db.executions[0]["delivered_at"] is None

    delivered_at = NOW + timedelta(days=2)
    with engine.begin() as conn:
        assert bridge.mark_executive_delivered(
            conn, "org_1", outbox["card_id"], at=delivered_at, channel="slack") is True
    assert db.executions[0]["delivered_at"] == delivered_at
    event = db.events_of("execution.delivery_confirmed")[-1]
    assert event["detail"]["channel"] == "slack"
    assert event["execution_id"] == execution.execution_id


def test_a_foreign_card_id_is_never_treated_as_a_commitment():
    db = world()
    engine = FakeEngine(db)
    with engine.begin() as conn:
        assert bridge.executive_delivery_is_live(conn, "org_1", "card_1") is False
        assert bridge.executive_delivery_is_live(conn, "org_1", "digest:2026-08-06") is False
    assert bridge.is_executive_delivery("digest:2026-08-06") is False
    assert bridge.parse_executive_card_id("card_1") is None


# --- the card link ---------------------------------------------------------------------------

def test_a_commitment_is_linked_to_the_card_that_surfaces_it():
    db = world()
    db.cards.append({"card_id": "card_1", "signal_id": "sig_1"})
    execution, engine = persisted(db)
    assert db.executions[0]["card_id"] is None

    assert bridge.link_commitment_cards(engine, "org_1") == 1
    assert db.executions[0]["card_id"] == "card_1"
    # Self-healing and write-once: a second pass links nothing and repoints nothing.
    assert bridge.link_commitment_cards(engine, "org_1") == 0
    assert execution.execution_id == db.executions[0]["execution_id"]


def test_a_link_is_never_repointed():
    """The audit trail would otherwise describe a surface that no longer shows this work."""
    db = world()
    execution, engine = persisted(db)
    with engine.begin() as conn:
        assert store.link_card(conn, org_id="org_1", execution_id=execution.execution_id,
                               card_id="card_1") is True
        assert store.link_card(conn, org_id="org_1", execution_id=execution.execution_id,
                               card_id="card_2") is False
    assert db.executions[0]["card_id"] == "card_1"


# --- rendering ---------------------------------------------------------------------------------

def test_the_reminder_carries_a_reason_to_act_not_an_accusation():
    message = bridge.format_reminder({
        "execution_id": "exec_a", "goal": "Restore momentum on the Acme deal",
        "card_id": "card_1", "reason_code": "escalation_remind", "urgency": "urgent",
        "escalation_day": 3,
        "facts": {"goal": "Restore momentum on the Acme deal", "days_open": 3,
                  "days_remaining": 11, "consequence": "The Acme deal slips past quarter end.",
                  "next_action": "Review the cooling evidence."}})
    assert message["consequence"] == "The Acme deal slips past quarter end."
    assert "open 3d" in message["situation"] and "11d left" in message["situation"]
    assert "day 3 of the escalation ladder" in message["situation"]

    slack = format_reminder_message(message, base_url="https://app.test")
    body = slack["blocks"][0]["text"]["text"]
    assert "🔴" in slack["text"], "urgent framing survives to the notification line"
    assert "https://app.test/cards/card_1" in body


def test_a_missing_fact_is_omitted_rather_than_rendered_as_zero():
    """"0 days remaining" because a value was absent reads as a crisis that is not happening."""
    message = bridge.format_reminder({"goal": "Something", "facts": {}})
    assert message["situation"] == ""
    assert "0" not in format_reminder_message(message)["blocks"][0]["text"]["text"]


def test_due_today_is_said_in_words_not_as_a_bare_zero():
    message = bridge.format_reminder({"goal": "x", "facts": {"days_open": 5,
                                                             "days_remaining": 0}})
    assert "due today" in message["situation"]


def test_a_corrupt_event_detail_degrades_instead_of_raising():
    db = world()
    _, engine = nudged(db)
    db.execution_events[-1]["detail"] = "not json at all"
    assert bridge.enqueue_executive_messages(engine, "org_1") == 1
    payload = json.loads(db.delivery_outbox[0]["payload"])
    assert payload["text"], "a message still ships, worded from the commitment alone"


# --- the layer boundary --------------------------------------------------------------------

def test_layer_five_never_imports_the_bridge():
    """The whole design rests on this direction: Layer 5 writes the decision, Layer 6 reads it.

    Checked against the import graph rather than the file text — "delivery" is a word this layer
    uses constantly in prose, and a grep would either miss real violations or fire on every
    docstring that mentions the concept."""
    import ast
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1] / "genios_engine" / "executive"
    for path in sorted(root.glob("*.py")):
        tree = ast.parse(path.read_text())
        targets = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                targets.add(node.module)
            elif isinstance(node, ast.Import):
                targets.update(alias.name for alias in node.names)
        offending = {name for name in targets if name.startswith("genios_engine.deliver")}
        assert not offending, f"{path.name} imports Layer 6: {offending}"
