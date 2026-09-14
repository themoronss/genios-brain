"""They answered. Nothing went back. Nothing in the layer said so.

`read_awaiting_response` fires while WE are waiting. `support_situations.read_first_response`
fires when THEY opened a thread we never answered — its predicate returns at `msgs[0].internal`,
so a conversation we started is not its case. Between them sits the exchange that actually fills a
founder's mailbox: we wrote, they REPLIED, and the reply is still sitting there. An intro
network's entire output has this shape, and no reading in this layer named it.

THE GATE IS THREE POSITIVE FACTS, and the shorter version was available and rejected. Firing on
`thread.days_waiting` being GONE would be one line — `waiting.py` retires it the moment a reply
lands — but a reading built on a missing field fires just as happily when the waiting pass failed,
when the field was renamed, or when the node was never swept. These tests pin the positive form,
including the case that separates it from a cold inbound.
"""
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.context.outreach_situations import (ANCHOR_UNANSWERED, READINGS,
                                                       read_awaiting_response,
                                                       read_unanswered_replies)

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def _ago(days: float) -> str:
    return (NOW - timedelta(days=days)).isoformat()


def _rows(**over):
    held = {"_name": "Sehan Sanjula", "_node_type": "person",
            "thread.last_inbound": _ago(17), "thread.last_outbound": _ago(19)}
    held.update(over)
    return {"n1": held}


def _one(rows):
    found = read_unanswered_replies(rows, NOW, {})
    assert len(found) == 1, found
    return found[0]


def _facts(finding):
    return {f[0]: f[1] for f in finding.facts}


# ── the case ─────────────────────────────────────────────────────────────────────────────────

def test_a_reply_nobody_answered_is_a_finding() -> None:
    finding = _one(_rows())
    assert finding.anchor == ANCHOR_UNANSWERED
    assert finding.concerns_node == "n1"
    assert _facts(finding)["outreach.days_owed"] == 17
    assert _facts(finding)["outreach.counterparty"] == "Sehan Sanjula"


def test_the_headline_states_the_finding_not_a_verdict() -> None:
    """"No answer sent" is a fact about a mailbox. "Ignored" would be a verdict on a person."""
    assert _one(_rows()).display_name == "Sehan Sanjula — replied 17d ago, no answer sent"


def test_what_it_cannot_see_is_declared_rather_than_assumed() -> None:
    """A reply drafted and not sent, an answer from an unconnected address, or a colleague who
    replied from their own mailbox are all invisible here. The card says so rather than asserting
    a silence it cannot prove."""
    assert set(_one(_rows()).missing) == {"outreach.reply_drafted", "outreach.answered_elsewhere"}


# ── the direction, which is the whole question ───────────────────────────────────────────────

def test_when_we_spoke_last_it_is_not_our_turn(_=None) -> None:
    """That is `read_awaiting_response`'s case, and this reading must not also claim it."""
    assert read_unanswered_replies(
        _rows(**{"thread.last_inbound": _ago(19), "thread.last_outbound": _ago(17)}),
        NOW, {}) == []


def test_the_two_readings_cannot_both_fire_on_one_conversation() -> None:
    """Not by agreement between them — by construction. `waiting.WAITING_ONLY_FIELDS` retires
    `thread.days_waiting` the instant a reply lands, so the fact its mirror needs is gone exactly
    when these arrive. Neither reading has to know the other exists."""
    theirs_last = _rows()
    assert len(read_unanswered_replies(theirs_last, NOW, {})) == 1
    assert read_awaiting_response(theirs_last, NOW, {}) == [], "no days_waiting once they reply"

    ours_last = _rows(**{"thread.last_inbound": _ago(19), "thread.last_outbound": _ago(17),
                         "thread.days_waiting": 17})
    assert read_unanswered_replies(ours_last, NOW, {}) == []
    assert len(read_awaiting_response(ours_last, NOW, {})) == 1


# ── the clause that keeps a cold inbound out ─────────────────────────────────────────────────

def test_a_stranger_who_wrote_in_is_not_this_readings_case() -> None:
    """They wrote, we never wrote at all. That is `first_response_overdue`, which owns the
    first-response clock and a policy window this reading has no business re-deriving. Requiring
    `thread.last_outbound` is what keeps the two apart."""
    assert read_unanswered_replies(
        _rows(**{"thread.last_outbound": None}), NOW, {}) == []


def test_a_conversation_where_they_never_replied_is_not_our_turn() -> None:
    assert read_unanswered_replies(_rows(**{"thread.last_inbound": None}), NOW, {}) == []


# ── the grace period ─────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("days, fires", [(0, False), (1, False), (2, True), (30, True)])
def test_a_reply_gets_the_same_grace_we_give_ourselves(days: float, fires: bool) -> None:
    """Mirrors `_WAITING_AFTER_DAYS`: the same clock pointed the other way. A founder who waits
    two days before chasing somebody should get two before being chased."""
    rows = _rows(**{"thread.last_inbound": _ago(days), "thread.last_outbound": _ago(days + 2)})
    assert bool(read_unanswered_replies(rows, NOW, {})) is fires


# ── one card per conversation ────────────────────────────────────────────────────────────────

def test_the_thread_yields_to_the_person() -> None:
    """`waiting.py` writes thread facts onto BOTH the thread node and the party, so without a
    guard one conversation mints two anchors — and one of them is addressed to "Thread with
    sehan@sanjula.io". The existing `_covered_by_party` stamp cannot serve here: it joins on
    `thread.days_waiting`, which is retired exactly when this reading becomes relevant."""
    rows = _rows(_covered_by_replier="n_person")
    assert read_unanswered_replies(rows, NOW, {}) == []


# ── context that travels, and context that does not become a gate ────────────────────────────

def test_their_habit_travels_as_context():
    """`party.reply_cadence_days` is how fast THEY answer — not how fast we do — so it rides on
    the card and stays out of the gate. Turning "we are four times slower than they are" into a
    threshold needs our own cadence, which nothing derives yet."""
    facts = _facts(_one(_rows(**{"party.reply_cadence_days": 2})))
    assert facts["outreach.their_normal_reply_days"] == 2


def test_a_missing_cadence_changes_nothing() -> None:
    facts = _facts(_one(_rows()))
    assert "outreach.their_normal_reply_days" not in facts
    assert facts["outreach.days_owed"] == 17


def test_what_they_are_to_us_travels_because_it_changes_the_advice() -> None:
    facts = _facts(_one(_rows(**{"relationship.nature": "investor"})))
    assert facts["outreach.counterparty_role"] == "investor"


# ── it is dispatched, and its anchor resolves ────────────────────────────────────────────────

def test_the_reading_is_actually_dispatched() -> None:
    """A reading absent from READINGS is a function nothing calls."""
    assert (ANCHOR_UNANSWERED, read_unanswered_replies) in READINGS


def test_a_domain_declares_the_anchor_or_the_reading_produces_nothing() -> None:
    """`refresh_state_situations` skips any anchor no domain claims — the silent failure that
    kept `admin_person` and `fundraising_deal` dark."""
    from genios_engine.context.domain_spec import domains_declaring, spec_for

    assert domains_declaring(ANCHOR_UNANSWERED) == ("admin",)
    assert spec_for("admin").type_for(ANCHOR_UNANSWERED) == "reply_owed"


def test_the_corpus_binds_the_type_it_emits() -> None:
    """The other half of the same failure: a type L2 emits that no situation file claims compiles
    to nothing, silently."""
    import yaml

    registry = yaml.safe_load(open(
        "Domain Expertise/Admin Expertise/registry/situation-capability-map.yaml",
        encoding="utf-8"))
    assert "reply_owed" in registry["map"]
    assert "admin.sit.reply_owed" in registry["map"]["reply_owed"]["situations"]
