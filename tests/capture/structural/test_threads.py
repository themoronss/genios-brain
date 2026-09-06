"""G2 · ALG-03 thread reconstruction (L1.3.6, units U1/U2) — the envelope S2 must be told.

    pytest tests/capture/structural/test_threads.py -q

Doc 03's acceptance, one row per clause: *a 5-message thread produces correct direction and
turn index for each; a forwarded message is not counted as a reply; `ball_in_court` flips
correctly on each turn.* Around those sit the rows for the failures this derivation has
actually produced in this codebase:

* **An outbound offer read as an inbound request.** Every direction row states which mailbox
  the message came from and which addresses were "us" when it was read.
* **An empty identity set passing silently.** The design partner's `org_seats` had zero rows,
  and every guard written against that set passed — `ball_in_court='us'` landed on people
  nobody was corresponding with. Here an empty set must produce `unknown`, and the row fails if
  it ever produces `inbound` again.
* **A thread that will not terminate.** Reply headers are attacker- and bug-supplied; the cycle
  row builds a mutual reply pair and asserts the reconstruction is a forest.

No test here reads a clock: every timestamp is stated, so a thread replayed next year
reconstructs to the shape it had the day it landed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.structural.threads import (
    BallInCourt,
    Direction,
    ThreadMessage,
    assemble_chain,
    reconstruct_thread,
)

WAVE = "W2"
GATE = "G2"

pytestmark = pytest.mark.unit

US = frozenset({"founder@genios.ai", "sales@genios.ai"})
THEM = "rohit@acme.example.com"
START = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)


def at(minutes: int) -> datetime:
    return START + timedelta(minutes=minutes)


def message(mid: str, minutes: int, sender: str | None, *, subject: str = "Pricing",
            in_reply_to: str | None = None, references: tuple[str, ...] = (),
            thread_id: str | None = "t-1", is_forward: bool | None = None) -> ThreadMessage:
    return ThreadMessage(message_id=mid, occurred_at=at(minutes), thread_id=thread_id,
                         actor_email=sender, subject=subject, in_reply_to=in_reply_to,
                         references=references, is_forward=is_forward)


#: The acceptance's five-message thread: they open, we answer, they push back, we quote, they
#: forward it internally. Written once and reused, because every row below is a question about
#: this same conversation.
FIVE = (
    message("m1", 0, THEM, subject="Pricing"),
    message("m2", 5, "founder@genios.ai", subject="Re: Pricing", in_reply_to="m1"),
    message("m3", 20, THEM, subject="Re: Pricing", in_reply_to="m2"),
    message("m4", 35, "sales@genios.ai", subject="Re: Pricing", in_reply_to="m3"),
    message("m5", 50, THEM, subject="Fwd: Pricing", in_reply_to="m4"),
)


# --------------------------------------------------------------------------------------------
# L1.3.6-U1 · direction and turn index
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class TurnRow:
    message_id: str
    direction: Direction
    turn_index: int
    is_reply: bool
    reply_depth: int
    why: str


FIVE_ROWS: tuple[TurnRow, ...] = (
    TurnRow("m1", Direction.inbound, 0, False, 0, "a stranger opens the thread"),
    TurnRow("m2", Direction.outbound, 1, True, 1, "our founder answers — outbound, or the "
                                                  "offer reads as a request"),
    TurnRow("m3", Direction.inbound, 2, True, 2, "they push back"),
    TurnRow("m4", Direction.outbound, 3, True, 3, "a DIFFERENT seat of ours replies: any of "
                                                  "our identities makes a message outbound"),
    TurnRow("m5", Direction.inbound, 4, False, 0, "a forward is a new root: it holds its "
                                                  "position in the thread but is not a reply"),
)


@pytest.mark.parametrize("row", FIVE_ROWS, ids=lambda r: r.message_id)
def test_a_five_message_thread_gets_direction_and_turn_index_for_each(row: TurnRow) -> None:
    thread = reconstruct_thread(FIVE, org_identities=US)
    turn = next(t for t in thread.turns if t.message_id == row.message_id)
    assert turn.direction is row.direction, row.why
    assert turn.turn_index == row.turn_index, row.why
    assert turn.is_reply is row.is_reply, row.why
    assert turn.reply_depth == row.reply_depth, row.why


def test_the_thread_carries_its_depth_and_the_newest_message_on_each_leg() -> None:
    thread = reconstruct_thread(FIVE, org_identities=US)
    assert thread.thread_id == "t-1"
    assert thread.thread_depth == 5
    assert thread.last_inbound_at == at(50)
    assert thread.last_outbound_at == at(35)
    assert thread.org_identities == US


def test_last_leg_timestamps_are_the_newest_not_the_last_one_seen() -> None:
    """Out-of-order delivery must not make an older message the "last" one on its leg."""
    thread = reconstruct_thread((message("a", 30, THEM), message("b", 10, THEM)),
                                org_identities=US)
    assert thread.last_inbound_at == at(30)
    assert thread.last_outbound_at is None


# --------------------------------------------------------------------------------------------
# ball_in_court — a derivation, never a judgement
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class BallRow:
    upto: int
    ball: BallInCourt
    why: str


BALL_ROWS: tuple[BallRow, ...] = (
    BallRow(1, BallInCourt.us, "they spoke last, so the reply is owed by us"),
    BallRow(2, BallInCourt.them, "we replied, so it is their turn — the value this codebase "
                                 "already writes to thread.ball_in_court on an outbound leg"),
    BallRow(3, BallInCourt.us, "they came back"),
    BallRow(4, BallInCourt.them, "we quoted"),
    BallRow(5, BallInCourt.us, "their forward is still the most recent message"),
)


@pytest.mark.parametrize("row", BALL_ROWS, ids=lambda r: f"after-{r.upto}")
def test_ball_in_court_flips_on_every_turn(row: BallRow) -> None:
    thread = reconstruct_thread(FIVE[:row.upto], org_identities=US)
    assert thread.ball_in_court is row.ball, row.why


def test_ball_in_court_follows_the_newest_message_not_the_last_link_of_the_walk() -> None:
    """On a branched thread the walk ends wherever the last root sits; the party who is waiting
    is decided by the newest message, whichever branch it is in."""
    messages = (
        message("root", 0, THEM),
        message("reply", 30, "founder@genios.ai", in_reply_to="root"),
        message("separate", 20, THEM, subject="Fwd: Pricing"),
    )
    thread = reconstruct_thread(messages, org_identities=US)
    assert thread.turns[-1].message_id == "separate", "the walk does end on the later root"
    assert thread.ball_in_court is BallInCourt.them, "but the newest message is ours"


# --------------------------------------------------------------------------------------------
# "Who are we" — the empty-identity-set failure, written as a row
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class IdentityRow:
    identities: frozenset[str]
    sender: str | None
    direction: Direction
    ball: BallInCourt
    why: str


IDENTITY_ROWS: tuple[IdentityRow, ...] = (
    IdentityRow(US, "founder@genios.ai", Direction.outbound, BallInCourt.them, "a seat of ours"),
    IdentityRow(US, "FOUNDER@Genios.AI", Direction.outbound, BallInCourt.them,
                "the same mailbox shouting: matching is on the lowercased address"),
    IdentityRow(frozenset({"  founder@genios.ai  "}), "founder@genios.ai", Direction.outbound,
                BallInCourt.them, "a configured address with stray whitespace is still us"),
    IdentityRow(US, THEM, Direction.inbound, BallInCourt.us, "a counterparty"),
    IdentityRow(frozenset(), "founder@genios.ai", Direction.unknown, BallInCourt.unknown,
                "NOBODY configured: an empty identity set must not make our own mail inbound "
                "— that silence is what put ball_in_court='us' on strangers"),
    IdentityRow(frozenset({""}), THEM, Direction.unknown, BallInCourt.unknown,
                "a set of blanks is an empty set"),
    IdentityRow(US, None, Direction.unknown, BallInCourt.unknown,
                "a sender the connector could not name has no derivable direction"),
    IdentityRow(US, "   ", Direction.unknown, BallInCourt.unknown, "nor does a blank one"),
)


@pytest.mark.parametrize("row", IDENTITY_ROWS, ids=lambda r: r.why[:34])
def test_direction_is_derived_from_the_org_identities_or_is_unknown(row: IdentityRow) -> None:
    thread = reconstruct_thread((message("only", 0, row.sender),),
                                org_identities=row.identities)
    assert thread.turns[0].direction is row.direction, row.why
    assert thread.ball_in_court is row.ball, row.why


def test_an_unknown_newest_message_does_not_fall_back_to_an_older_turn() -> None:
    """"Whose turn it is" is a claim about the present; answering it from a stale turn is how a
    closed conversation keeps showing up as owed."""
    messages = (message("m1", 0, THEM), message("m2", 10, None))
    thread = reconstruct_thread(messages, org_identities=US)
    assert thread.turns[0].direction is Direction.inbound
    assert thread.ball_in_court is BallInCourt.unknown


# --------------------------------------------------------------------------------------------
# L1.3.6-U2 · chain assembly
# --------------------------------------------------------------------------------------------

def test_a_thread_with_no_reply_headers_is_ordered_by_time() -> None:
    """Today's live path: the Gmail connector carries `threadId` but not `In-Reply-To`, so the
    chain is chronological and nothing pretends to know more than that."""
    messages = (message("c", 20, THEM, in_reply_to=None),
                message("a", 0, THEM),
                message("b", 10, "sales@genios.ai"))
    chain = assemble_chain(messages)
    assert [link.message.message_id for link in chain.links] == ["a", "b", "c"]
    assert [link.turn_index for link in chain.links] == [0, 1, 2]
    assert all(link.parent_message_id is None for link in chain.links)
    assert not any(link.is_reply for link in chain.links)


def test_shuffled_input_reconstructs_to_the_same_chain() -> None:
    forwards = assemble_chain(FIVE)
    backwards = assemble_chain(tuple(reversed(FIVE)))
    assert [link.message.message_id for link in forwards.links] == \
        [link.message.message_id for link in backwards.links]
    assert [link.reply_depth for link in forwards.links] == \
        [link.reply_depth for link in backwards.links]


def test_the_references_header_is_used_when_in_reply_to_names_a_message_we_do_not_hold() -> None:
    """A partial backfill holds the middle of a chain; `References` still links it up."""
    messages = (message("m1", 0, THEM),
                message("m3", 20, "sales@genios.ai", subject="Re: Pricing",
                        in_reply_to="m2-never-synced", references=("m0-gone", "m1", "m2")))
    chain = assemble_chain(messages)
    linked = chain.links[1]
    assert linked.parent_message_id == "m1", "the newest reference we actually hold"
    assert linked.is_reply is True
    assert linked.reply_depth == 1


def test_a_reply_whose_parent_was_never_synced_is_still_a_reply() -> None:
    chain = assemble_chain((message("only", 0, THEM, subject="Re: Pricing",
                                    in_reply_to="not-here"),))
    (link,) = chain.links
    assert link.is_reply is True, "the header declared a parent — that is a fact about the "
    assert link.parent_message_id is None, "message, not about what we managed to sync"
    assert link.reply_depth == 0


@dataclass(frozen=True)
class ForwardRow:
    subject: str
    is_forward_flag: bool | None
    is_forward: bool
    is_reply: bool
    why: str


FORWARD_ROWS: tuple[ForwardRow, ...] = (
    ForwardRow("Fwd: Pricing", None, True, False, "the acceptance clause: a forward is not "
                                                  "counted as a reply"),
    ForwardRow("FW: Pricing", None, True, False, "the other spelling"),
    ForwardRow("fwd:Pricing", None, True, False, "no space, lower case"),
    ForwardRow("TR: Pricing", None, True, False, "the French client's prefix"),
    ForwardRow("Re: Fwd: Pricing", None, False, True, "a REPLY to a forward is a reply — only "
                                                      "the first prefix decides"),
    ForwardRow("Re: Pricing", None, False, True, "an ordinary reply"),
    ForwardRow("Forwarding you the deck", None, False, True,
               "a subject that merely talks about forwarding is not a Fwd: prefix"),
    ForwardRow("Re: Pricing", True, True, False, "a connector that KNOWS it is a forward wins "
                                                 "over the subject line"),
    ForwardRow("Fwd: Pricing", False, False, True, "and knows when it is not"),
)


@pytest.mark.parametrize("row", FORWARD_ROWS, ids=lambda r: r.why[:34])
def test_a_forward_is_never_counted_as_a_reply(row: ForwardRow) -> None:
    messages = (message("parent", 0, THEM),
                message("child", 10, "sales@genios.ai", subject=row.subject,
                        in_reply_to="parent", is_forward=row.is_forward_flag))
    child = assemble_chain(messages).links[1]
    assert child.is_forward is row.is_forward, row.why
    assert child.is_reply is row.is_reply, row.why
    assert (child.parent_message_id is None) is row.is_forward, row.why
    assert child.reply_depth == (0 if row.is_forward else 1), row.why


def test_a_branch_keeps_its_replies_together_oldest_branch_first() -> None:
    messages = (message("root", 0, THEM),
                message("branch-b", 30, "sales@genios.ai", in_reply_to="root"),
                message("branch-a", 10, "founder@genios.ai", in_reply_to="root"),
                message("branch-a-reply", 40, THEM, in_reply_to="branch-a"))
    chain = assemble_chain(messages)
    assert [link.message.message_id for link in chain.links] == [
        "root", "branch-a", "branch-a-reply", "branch-b"]
    assert [link.reply_depth for link in chain.links] == [0, 1, 2, 1]
    assert [link.turn_index for link in chain.links] == [0, 1, 2, 3]


def test_a_parent_link_pointing_forward_in_time_is_dropped() -> None:
    """Mutually-referencing ids are clock skew or a duplicated message id. Honouring both links
    builds a cycle, and a cycle in a thread walk is an ingest that never returns."""
    messages = (message("m1", 0, THEM, in_reply_to="m2"),
                message("m2", 10, "sales@genios.ai", in_reply_to="m1"))
    chain = assemble_chain(messages)
    assert [link.message.message_id for link in chain.links] == ["m1", "m2"]
    assert chain.links[0].parent_message_id is None, "the older message keeps no parent"
    assert chain.links[1].parent_message_id == "m1"
    assert chain.thread_depth == 2


def test_a_message_that_replies_to_itself_is_a_root() -> None:
    chain = assemble_chain((message("m1", 0, THEM, in_reply_to="m1"),))
    assert chain.links[0].parent_message_id is None
    assert chain.thread_depth == 1


def test_a_resynced_duplicate_does_not_deepen_the_thread() -> None:
    """`thread_depth` feeds the tier router: a re-sync must not make a document more
    expensive to extract than it was yesterday."""
    duplicate = message("m1", 0, THEM)
    chain = assemble_chain((FIVE[0], duplicate, FIVE[1]))
    assert chain.thread_depth == 2
    assert [link.message.message_id for link in chain.links] == ["m1", "m2"]


def test_a_thread_without_a_provider_thread_id_still_reconstructs() -> None:
    messages = (message("m1", 0, THEM, thread_id=None),
                message("m2", 10, "sales@genios.ai", thread_id=None, in_reply_to="m1"))
    thread = reconstruct_thread(messages, org_identities=US)
    assert thread.thread_id is None
    assert [t.turn_index for t in thread.turns] == [0, 1]
    assert thread.ball_in_court is BallInCourt.them


@dataclass(frozen=True)
class RefusalRow:
    messages: tuple[ThreadMessage, ...]
    fragment: str
    why: str


REFUSAL_ROWS: tuple[RefusalRow, ...] = (
    RefusalRow((), "at least one message", "there is no envelope for no messages"),
    RefusalRow((message("m1", 0, THEM, thread_id="t-1"),
                message("m2", 5, THEM, thread_id="t-2")),
               "group by thread_id",
               "reconstructing two conversations as one produces an envelope that is "
               "confidently wrong for both — the caller groups"),
)


@pytest.mark.parametrize("row", REFUSAL_ROWS, ids=lambda r: r.why[:34])
def test_the_reconstructor_refuses_input_it_cannot_answer_honestly(row: RefusalRow) -> None:
    with pytest.raises(ValueError, match=row.fragment):
        assemble_chain(row.messages)
    with pytest.raises(ValueError, match=row.fragment):
        reconstruct_thread(row.messages, org_identities=US)


def test_reconstruction_is_replayable() -> None:
    """Same messages, same identities, same answer — no clock, no ordering luck."""
    first = reconstruct_thread(FIVE, org_identities=US)
    second = reconstruct_thread(tuple(reversed(FIVE)), org_identities=set(US))
    assert first == second
