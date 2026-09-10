"""DEL-03 — an escalation must say it is one.

    pytest tests/contracts/test_escalation_says_so.py -q

`contracts/outcomes` records `ESCALATE` as reachable from `execution.EscalationAction` and from no
card or delivery vocabulary at all. This is the seam where that stopped being true for the surface
a person actually reads.

`executive/reminder.py:170` writes the rung it fired into the reason code —
`escalation_notify`, `escalation_remind`, `escalation_escalate`, `escalation_critical` — and
`deliver/executive_bridge.py` already carried that code into the message dict. Nothing read it.
The headline was the bare goal, so the fourth rung of a ladder, the one that widens the audience
and interrupts, reached a human looking exactly like the first gentle nudge. `escalation_day`
appeared as a fragment in the sub-line — "day 3 of the escalation ladder" — and that was the whole
difference.

Same defect shape as the card headline, one surface over: the information existed and the sentence
did not use it.
"""

from __future__ import annotations

import pytest

from genios_engine.contracts.execution import EscalationAction
from genios_engine.contracts.outcomes import Outcome, project
from genios_engine.deliver.executive_bridge import (
    escalation_action,
    format_reminder,
    is_escalation,
)

pytestmark = pytest.mark.unit

GOAL = "Send the signed order form"


def reminder(reason_code: str, **over) -> dict:
    row = {"goal": GOAL, "reason_code": reason_code, "urgency": "urgent",
           "escalation_day": 3, "facts": {"days_open": 12, "days_remaining": 2}}
    row.update(over)
    return format_reminder(row)


# =============================================================================================
# The rung is parsed from what Layer 5 already wrote.
# =============================================================================================
@pytest.mark.parametrize("action", [a.value for a in EscalationAction])
def test_every_rung_the_ladder_can_fire_is_parsed(action):
    """A rung this bridge cannot parse would silently render as an ordinary nudge."""
    assert escalation_action(f"escalation_{action}") == action


def test_a_non_escalation_reason_code_parses_to_nothing():
    assert escalation_action("deadline_warning") == ""
    assert escalation_action(None) == ""
    assert escalation_action("") == ""


# =============================================================================================
# The two rungs that must announce themselves — and the two that must not.
# =============================================================================================
@pytest.mark.parametrize("action", ["escalate", "critical"])
def test_a_widening_rung_says_it_is_an_escalation(action):
    message = reminder(f"escalation_{action}")

    assert is_escalation(f"escalation_{action}")
    assert message["kind"] == "execution_escalation"
    assert message["headline"].startswith("Escalated")
    assert GOAL in message["headline"]


@pytest.mark.parametrize("action", ["notify", "remind"])
def test_an_ordinary_rung_is_left_alone(action):
    """These are rungs too, and they are ordinary nudges. Framing them as escalations would make
    the word mean nothing by the time it is needed."""
    message = reminder(f"escalation_{action}")

    assert not is_escalation(f"escalation_{action}")
    assert message["kind"] == "execution_reminder"
    assert message["headline"] == GOAL


def test_a_plain_deadline_warning_is_not_an_escalation():
    message = reminder("deadline_warning")

    assert message["kind"] == "execution_reminder"
    assert message["headline"] == GOAL


def test_critical_reads_louder_than_escalate():
    """Two rungs, two different sentences. Collapsing them would lose the one distinction the
    ladder's top exists to draw."""
    assert reminder("escalation_critical")["headline"] != \
        reminder("escalation_escalate")["headline"]


# =============================================================================================
# What the message carries.
# =============================================================================================
def test_the_action_travels_explicitly():
    """Carried as a field so a channel adapter can style it without re-parsing a string, and so
    the outcome is legible in the stored payload rather than inferable from a reason code."""
    assert reminder("escalation_critical")["escalation_action"] == "critical"
    assert reminder("deadline_warning")["escalation_action"] == ""


def test_the_goal_is_never_lost_to_the_frame():
    """The reader still has to know what is being escalated."""
    for action in ("escalate", "critical"):
        assert GOAL in reminder(f"escalation_{action}")["headline"]


def test_the_existing_sub_line_is_unchanged():
    """The escalation day and the elapsed clauses were the only signal before this change, and
    they stay — this adds a statement, it does not replace the detail."""
    message = reminder("escalation_escalate")

    assert "day 3 of the escalation ladder" in message["situation"]
    assert "open 12d" in message["situation"]


def test_a_reminder_with_no_facts_still_renders():
    """Every clause in the sub-line is guarded on its fact existing; the headline must be too."""
    message = format_reminder({"goal": GOAL, "reason_code": "escalation_critical"})

    assert message["headline"].startswith("Escalated")
    assert message["situation"] == ""


# =============================================================================================
# The vocabulary this closes.
# =============================================================================================
def test_the_canonical_outcome_agrees_with_the_rungs_that_announce_themselves():
    """`contracts/outcomes` projects `escalate` and `critical` onto `ESCALATE` and the other two
    onto `EMIT_ACTION`. The bridge must frame exactly the pair the projection escalates, or the
    stored outcome and the sentence a human reads disagree."""
    for action in (a.value for a in EscalationAction):
        projected = project("execution.EscalationAction", action)
        framed = is_escalation(f"escalation_{action}")

        assert framed == (projected is Outcome.ESCALATE), action


# =============================================================================================
# The surface a founder is actually pinged on.
# =============================================================================================
def test_the_escalation_frame_survives_the_slack_adapter():
    """THE SECOND HALF, and it was missing. `executive_bridge` sets `kind` and
    `escalation_action` for exactly this, and both had ZERO consumers — `channels/slack.py`
    prefixed all four rungs of the ladder with "Still open — ", so the rung that widens the
    audience and interrupts arrived looking like the first gentle nudge."""
    from genios_engine.deliver.channels.slack import format_card_message, format_reminder_message

    escalated = format_reminder_message(reminder("escalation_critical"))
    ordinary = format_reminder_message(reminder("escalation_remind"))

    assert "Escalated" in escalated["text"]
    assert "Still open" not in escalated["text"]
    assert "Still open" in ordinary["text"]
    assert format_card_message is not None


def test_an_ordinary_reminder_still_reads_as_one():
    from genios_engine.deliver.channels.slack import format_reminder_message

    payload = format_reminder_message(reminder("deadline_warning"))

    assert payload["text"].endswith(GOAL)
    assert "Still open" in payload["text"]


def test_the_blocks_and_the_fallback_text_agree():
    """Slack shows `text` in the notification and `blocks` in the channel. Two different frames
    would mean the ping said one thing and the message another."""
    from genios_engine.deliver.channels.slack import format_reminder_message

    payload = format_reminder_message(reminder("escalation_escalate"))
    rendered = payload["blocks"][0]["text"]["text"]

    assert payload["text"].startswith("🔴 Escalated")
    assert rendered.startswith("🔴 *Escalated")


# =============================================================================================
# An abstention with no stated cause is indistinguishable from an opinion.
# =============================================================================================
def test_the_reason_a_card_declined_to_advise_reaches_chat():
    """`cards.abstained_because` exists to carry it and `format_card_message` rendered headline
    and situation only — so on the one surface a founder is pinged on, the cause was absent.
    That matters more now that ASK_DECISION interrupts: a card whose whole content is a question
    would have arrived looking like an instruction."""
    from genios_engine.deliver.channels.slack import format_card_message

    payload = format_card_message({
        "card_id": "c1", "headline": "Needs a decision — who owns Document C",
        "situation": "Nobody is recorded as accountable.",
        "level": "review", "abstained_because": "no owner is recorded for this requirement"})

    assert "no owner is recorded for this requirement" in payload["blocks"][0]["text"]["text"]


def test_a_prescriptive_card_is_not_given_an_abstention_line():
    """The field can be set on a card that later became actionable. Printing it there would tell
    a reader the system declined to advise on a card that is advising."""
    from genios_engine.deliver.channels.slack import format_card_message

    payload = format_card_message({
        "card_id": "c1", "headline": "Send the signed order form",
        "situation": "They asked on Tuesday.",
        "level": "prescriptive", "abstained_because": "stale"})

    assert "stale" not in payload["blocks"][0]["text"]["text"]


def test_a_card_with_no_stated_cause_renders_exactly_as_before():
    """Most cards carry nothing here, and an empty italic line is worse than none."""
    from genios_engine.deliver.channels.slack import format_card_message

    with_field = format_card_message({"card_id": "c1", "headline": "H", "situation": "S",
                                      "level": "observation", "abstained_because": ""})
    without = format_card_message({"card_id": "c1", "headline": "H", "situation": "S"})

    assert with_field["blocks"] == without["blocks"]


def test_the_outbox_selects_the_two_columns_the_renderer_needs():
    """A renderer reading a column the query never selected gets `None` on every row — the same
    silent shape as a missing writer, one join away."""
    import inspect

    from genios_engine.deliver import outbox

    source = inspect.getsource(outbox)

    assert "k.level,k.abstained_because," in source
