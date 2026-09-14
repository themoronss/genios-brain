"""A partner said they would revisit once you had two enterprise references. You closed the
second eleven days ago.

`correlation_timeline` was built for exactly that sentence and has published the answer every
sweep since it shipped. `_satisfied_json` writes BOTH evidence spans side by side, and
`SatisfiedCondition.__post_init__` refuses to construct with only one of them — "the card has to
show the sentence from May, and a claim with no receipt is a guess".

Nothing read it. `condition_situations` surfaced only the review queue — the conditions
`parse_condition` REFUSED to parse — and the parsed ones that had since come true had no reading,
no anchor and no type. `condition-now-satisfied.yaml` was authored, reviewed and approved, and
bound to `admin_contact` as "the nearest live type", with its own header explaining that binding
it properly "would produce a card asserting that something became true — the one claim this
capability is forbidden to make on evidence it does not have".

The evidence was there the whole time. The door was not.
"""
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.context.condition_situations import (ANCHOR_CONDITION_MET, MAX_PER_NODE,
                                                        SATISFIED_FIELD,
                                                        read_conditions_satisfied)

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
STATED = NOW - timedelta(days=44)
MET = NOW - timedelta(days=11)


def _entry(**over):
    entry = {
        "condition_id": "cond_1",
        "actor": "Theresa",
        "action": "take another look",
        "condition_text": "once you have two enterprise references",
        "stated_at": STATED.isoformat(),
        "satisfied_at": MET.isoformat(),
        "strength_bp": 8200,
        "stale": False,
        "world_key": "enterprise_references",
        "world_value": 2,
        "statement": [{"quote": "Always happy to take a look and reconsider once you have two "
                                "enterprise references.", "start_offset": 0, "end_offset": 70}],
        "satisfied_by": [{"quote": "Signed — that's our second enterprise logo.",
                          "start_offset": 0, "end_offset": 42}],
    }
    entry.update(over)
    return entry


def _rows(*entries):
    return {"n1": {"satisfied": list(entries or (_entry(),))}}


def _one(rows=None, owner=None):
    found = read_conditions_satisfied(rows or _rows(), NOW, owner)
    assert len(found) == 1, found
    return found[0]


def _facts(finding):
    return {f[0]: f[1] for f in finding.facts}


# ── the card ─────────────────────────────────────────────────────────────────────────────────

def test_a_satisfied_condition_becomes_a_finding() -> None:
    finding = _one()
    assert finding.anchor == ANCHOR_CONDITION_MET
    assert finding.display_name == "Theresa — the condition they set is now met"
    assert finding.concerns_node == "n1"


def test_the_card_carries_the_three_things_the_authored_situation_demanded() -> None:
    """`condition-now-satisfied.yaml` named its contract before an emitter existed: "the emitted
    situation must carry the original condition text, the satisfying evidence span, and a
    certainty tier"."""
    facts = _facts(_one())
    assert facts["condition.text"] == "once you have two enterprise references"
    assert facts["condition.satisfied_by"] == "enterprise_references"
    assert facts["condition.strength_bp"] == 8200


def test_the_counterpartys_own_sentence_travels() -> None:
    """The half that makes the claim checkable rather than asserted. Nobody remembers a sentence
    from four months ago, which is exactly why the condition is still unacted on."""
    assert _facts(_one())["condition.quote"].startswith("Always happy to take a look")


def test_how_long_it_waited_is_on_the_card() -> None:
    """The distance between the sentence and the world turning is the reason this is worth
    saying at all."""
    facts = _facts(_one())
    assert facts["condition.waited_days"] == 33
    assert facts["condition.days_since_satisfied"] == 11


def test_whether_we_have_told_them_is_declared_unknown() -> None:
    """Nothing in this system observes that we went back to somebody about a condition coming
    true — so the question a reader most wants answered is not on the record, and the situation
    says so rather than scoring itself complete."""
    assert _one().missing == ["condition.counterparty_informed"]


# ── both spans or nothing ────────────────────────────────────────────────────────────────────

def test_a_satisfaction_it_cannot_quote_is_not_a_card() -> None:
    """`SatisfiedCondition` already refuses to exist without the statement's evidence, so a row
    without one is a row this reading does not understand. Requiring the quote is a second lock
    on the same door, not a new judgement."""
    assert read_conditions_satisfied(_rows(_entry(statement=[])), NOW) == []


def test_a_row_with_no_condition_id_yields_nothing() -> None:
    assert read_conditions_satisfied(_rows(_entry(condition_id="")), NOW) == []


@pytest.mark.parametrize("value", [None, {}, "not json", {"satisfied": "not a list"}, 7])
def test_a_malformed_row_is_one_silent_condition_not_an_exception(value) -> None:
    """A malformed row must cost one condition, never every condition on the tenant."""
    assert read_conditions_satisfied({"n1": value}, NOW) == []


# ── staleness is reported, never a gate ──────────────────────────────────────────────────────

def test_a_stale_satisfaction_still_reaches_a_card() -> None:
    """`strength_bp` decays from the moment the world became true and the correlator marks the
    row stale below its floor, because the instruction is to act while the evidence is fresh. A
    condition satisfied eight months ago is still satisfied — it is worth less, which is a
    ranking question for `importance.py`, not a reason for this layer to decide nobody is told."""
    finding = _one(_rows(_entry(stale=True, strength_bp=1200)))
    assert _facts(finding)["condition.stale"] is True
    assert _facts(finding)["condition.strength_bp"] == 1200


def test_staleness_is_always_stated_even_when_false() -> None:
    """Absent would read as "not stale" to one consumer and "unknown" to another."""
    assert _facts(_one())["condition.stale"] is False


# ── a condition WE set is kept, for the reason its twin keeps them ───────────────────────────

def test_a_condition_we_set_that_came_true_is_also_a_finding() -> None:
    """Its sibling's rule: "you told them you would reply once it was booked" is as much an open
    loop as anything they said — and one WE set that has now come true is something we said we
    would do and now can."""
    finding = _one(_rows(_entry(actor="Rohit Swerashi")), owner="rohit swerashi")
    assert _facts(finding)["condition.actor_is_us"] is True


def test_an_ambiguous_first_name_makes_no_ownership_claim() -> None:
    """This tenant carries two Rohits. `_is_owner` returns None for anything that ambiguous, and
    an absent flag is the honest answer — the condition still surfaces."""
    facts = _facts(_one(_rows(_entry(actor="Rohit")), owner="rohit swerashi"))
    assert "condition.actor_is_us" not in facts


# ── bounded ──────────────────────────────────────────────────────────────────────────────────

def test_one_node_cannot_flood_the_sweep() -> None:
    entries = [_entry(condition_id=f"cond_{i}") for i in range(MAX_PER_NODE + 4)]
    assert len(read_conditions_satisfied(_rows(*entries), NOW)) == MAX_PER_NODE


# ── the route exists end to end ──────────────────────────────────────────────────────────────

def test_the_field_read_is_the_field_the_correlator_writes() -> None:
    from genios_engine.context.correlation_timeline import FIELD_SATISFIED

    assert SATISFIED_FIELD == FIELD_SATISFIED, (
        "the reading and the publisher must name one fact, or the door opens onto nothing")


def test_the_reading_is_dispatched_and_its_anchor_is_declared() -> None:
    from genios_engine.context.domain_spec import domains_declaring, spec_for
    from genios_engine.context.outreach_situations import READINGS

    assert ANCHOR_CONDITION_MET in {anchor for anchor, _ in READINGS}
    assert domains_declaring(ANCHOR_CONDITION_MET) == ("admin",)
    assert spec_for("admin").type_for(ANCHOR_CONDITION_MET) == "condition_satisfied"


def test_the_authored_situation_is_no_longer_waiting_on_a_type_that_does_not_exist() -> None:
    """It was bound to `admin_contact` as "the nearest live type" and its header said binding it
    properly would assert something the evidence could not support. The evidence now arrives."""
    import yaml

    registry = yaml.safe_load(open(
        "Domain Expertise/Admin Expertise/registry/situation-capability-map.yaml",
        encoding="utf-8"))
    assert "condition_satisfied" in registry["map"]
    assert "admin.sit.condition_now_satisfied" in registry["map"]["condition_satisfied"]["situations"]
