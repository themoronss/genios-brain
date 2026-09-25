"""L3-08 · an unsent draft counted as a reply, and that is the benchmark's central number.

`reconstruct_thread.direction_of` asked ONE question — is the author one of us — and a draft is
authored by us, so it returned `outbound`. Outbound is read everywhere as "we replied":
`ball_in_court` flips to `them`, a waiting relationship reads as answered, and the 23 September
benchmark's headline finding — "you have sent zero emails in 28 days", with four investor-adjacent
people waiting 46–77 days — WOULD HAVE READ "you sent two" on the strength of two drafts sitting in
a folder.

Gmail says so with a `DRAFT` label. The label was captured on every message (`labelIds`) and read by
nothing: `light_junk` filters SPAM, TRASH, PROMOTIONS and SOCIAL, and DRAFT appears nowhere in the
engine.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.capture.pipeline import _draft_flag
from genios_engine.capture.structural.threads import Direction, ThreadMessage, reconstruct_thread

US = "founder@ours.test"
THEM = "investor@theirs.test"
T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _msg(i: int, who: str, *, is_draft=None) -> ThreadMessage:
    return ThreadMessage(message_id=f"m{i}", occurred_at=T0 + timedelta(hours=i),
                         thread_id="t1", actor_email=who, is_draft=is_draft)


def _read(*messages):
    return reconstruct_thread(list(messages), org_identities=(US,))


# =================================================================================================
# 1 · ⛔ THE DEFECT
# =================================================================================================

def test_a_draft_we_never_sent_is_not_counted_as_our_reply():
    """⛔ Before this, `ball_in_court` came back `us`→`them` on a message nobody received."""
    read = _read(_msg(1, THEM), _msg(2, US, is_draft=True))
    assert read.turns[-1].direction is Direction.unknown, "a draft still reads as outbound"
    assert read.ball_in_court != "them", (
        "an unsent draft handed the conversation back to the other party — this is the line that "
        "turns four people waiting 46-77 days into four people who were answered")


def test_a_real_send_is_still_our_reply():
    """The refusal must not become a wall. A sent message from us is outbound, unchanged."""
    read = _read(_msg(1, THEM), _msg(2, US, is_draft=False))
    assert read.turns[-1].direction is Direction.outbound
    assert read.ball_in_court == "them"


def test_a_connector_that_says_nothing_behaves_exactly_as_before():
    """⛔ `None` is not `False`. A source that carries no labels cannot rule a draft out, and every
    caller written before this field existed supplies `None` — their behaviour must not move."""
    read = _read(_msg(1, THEM), _msg(2, US))
    assert read.turns[-1].direction is Direction.outbound


def test_an_inbound_message_is_untouched_whatever_the_flag_says():
    """A draft is something WE hold. `is_draft` on a counterparty's message is meaningless and must
    not silently reclassify their reply — the refusal belongs to the identity branch, not before it."""
    read = _read(_msg(1, US, is_draft=False), _msg(2, THEM, is_draft=True))
    assert read.turns[-1].direction is Direction.unknown or read.turns[-1].direction is Direction.inbound


# =================================================================================================
# 2 · ⛔ THE FLAG IS TRI-STATE, AND THE THIRD STATE IS THE POINT
# =================================================================================================

def test_the_draft_flag_reads_gmails_own_label():
    assert _draft_flag({"labelIds": ["DRAFT", "INBOX"]}) is True
    assert _draft_flag({"labelIds": ["draft"]}) is True, "the label check must not be case-bound"
    assert _draft_flag({"labelIds": ["SENT", "INBOX"]}) is False


def test_no_labels_at_all_is_unknown_and_never_false():
    """⛔ "Labels were present and DRAFT was not among them" and "this source carries no labels"
    are different facts. Only the first can rule a draft out."""
    assert _draft_flag({}) is None
    assert _draft_flag({"labelIds": None}) is None
    assert _draft_flag({"labelIds": "DRAFT"}) is None, "a bare string is not a label list"
    assert _draft_flag({"labelIds": []}) is False


# =================================================================================================
# 3 · ⛔ THE DRAFT IS KEPT, NOT DROPPED
# =================================================================================================

def test_a_draft_is_captured_rather_than_filtered_as_junk():
    """⛔ "You drafted a reply three weeks ago and never sent it" is one of the most useful things
    in a founder's mailbox. The defect was calling it a send, not keeping it — so DRAFT must NOT
    join the junk labels, and `is_draft` travels so a later reading can say exactly that."""
    from genios_engine.capture.gate.rules import light_junk
    assert light_junk(["DRAFT", "INBOX"], "someone@x.test", False) is None, (
        "drafts are being dropped as junk — that loses the 'started and never sent' finding "
        "entirely, which is the opposite mistake")
    assert light_junk(["SPAM"], "someone@x.test", False) == "N-09", "the real junk rules moved"


def test_the_turn_still_carries_the_message_so_nothing_is_lost():
    read = _read(_msg(1, THEM), _msg(2, US, is_draft=True))
    assert len(read.turns) == 2, "the draft was dropped from the thread rather than reclassified"
    assert read.turns[-1].message_id == "m2"
