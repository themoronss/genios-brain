"""ALG-03 · L1.3.6 — the Thread Reconstructor: which way a message went, and where it sits.

*Without direction, an outbound offer reads as an inbound request.* That is not a hypothetical
— this codebase shipped it, and the repair was to put an envelope in front of the extraction
prompt. S1 computes the envelope so S2 can be TOLD, because a model asked to infer direction
from prose will be right most of the time, and the times it is wrong are the times somebody
acts on a card that has the two parties the wrong way round.

Everything here is a derivation, not a judgement:

    direction      outbound if the sender is one of us, inbound if not
    turn_index     0-based position in the reconstructed chain
    thread_depth   how many messages of the chain we hold at ingest time
    last_inbound_at / last_outbound_at   the newest message on each leg
    ball_in_court  the party who did NOT send the most recent message

`ball_in_court` says whose turn it is. Whether that means somebody is stalling is L2's
question and is answered with L2's clock; nothing in this module reads a clock, so a thread
replayed in a year reconstructs to exactly the same shape it had the day it landed.

**Two units, one threading notion.** The grouping key is the connector's own thread id — Gmail's
`threadId`, carried as `SourceEvent.parent_object_id` since the landing seam — and never a
second notion invented here. Ordering *within* the group uses `In-Reply-To`/`References` when a
connector supplies them and falls back to `occurred_at`; today no connector captures those
headers (see `capture/connectors/composio.py`, which keeps only the six noise headers), so the
fallback is the live path and the header path is ready for the connector change rather than
waiting on it.

**An empty identity set produces `unknown`, never `inbound`.** The org's own addresses arrive
from the caller (`context/runner._internal_emails` unions seats, the account owner and the
connected mailboxes). When that set is empty — as it was for the design partner, whose
`org_seats` had zero rows — treating every message as inbound is the failure that put
`ball_in_court='us'` on people nobody was corresponding with and modelled the product's own
onboarding mail as a prospect asking for a demo. An empty set is missing configuration, so the
answer is `unknown`: it is loud, it is filterable, and no rule fires on it by accident.

PURE — no clock, no model, no database, no network, no float.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterable, Sequence


class Direction(str, Enum):
    """Which way the message went. `unknown` is a real answer, not a failure to have one: a
    message from an unnamed sender, or one seen while we do not know who "we" are, has a
    direction nobody can derive, and the honest value keeps it out of every rule that means
    "they said" or "we said"."""

    inbound = "inbound"
    outbound = "outbound"
    unknown = "unknown"


class BallInCourt(str, Enum):
    """Whose turn it is. The strings match what `context/pipeline.py` already writes to
    `thread.ball_in_court`, so this module can replace that derivation without a migration and
    without inverting the meaning of a value the reasoner has been reading for months: WE
    replied, so the ball is with THEM."""

    us = "us"
    them = "them"
    unknown = "unknown"


#: A forward is a new conversation wearing an old subject. Only the FIRST prefix decides:
#: "Re: Fwd: pricing" is a reply to a forward, and counting it as a forward would restart the
#: turn index in the middle of a live exchange.
_FORWARD_SUBJECT = re.compile(r"^\s*(?:fwd|fw|tr|wg|rv)\s*:", re.IGNORECASE)


@dataclass(frozen=True)
class ThreadMessage:
    """One message of one thread, in the shape the landing seam already holds it.

    `message_id` is the connector's `source_object_id`, `thread_id` its `parent_object_id`.
    `in_reply_to`/`references` are the RFC 5322 headers, optional because the Gmail path does
    not carry them yet; when they are absent the chain is reconstructed from `occurred_at`,
    which is what a single-branch email thread looks like anyway.

    `is_forward` may be stated by a connector that knows; left `None` it is derived from the
    subject line."""

    message_id: str
    occurred_at: datetime
    thread_id: str | None = None
    actor_email: str | None = None
    subject: str | None = None
    in_reply_to: str | None = None
    references: tuple[str, ...] = ()
    is_forward: bool | None = None


@dataclass(frozen=True)
class ChainLink:
    """One message's place in the reconstructed chain.

    `is_reply` is a fact about the message's own headers — it declared a parent — while
    `parent_message_id` is a fact about what we hold: a reply whose parent has not been synced
    is still a reply, and pretending otherwise would make every partially backfilled thread
    look like a pile of unrelated first contacts."""

    message: ThreadMessage
    turn_index: int
    parent_message_id: str | None
    is_reply: bool
    is_forward: bool
    reply_depth: int


@dataclass(frozen=True)
class ThreadChain:
    """L1.3.6-U2's answer: the messages of one thread, in chain order."""

    thread_id: str | None
    links: tuple[ChainLink, ...]

    @property
    def thread_depth(self) -> int:
        """Messages of the chain we hold at ingest time — the number ALG-05 scores on."""
        return len(self.links)


@dataclass(frozen=True)
class MessageTurn:
    """Per-message envelope: the four facts S2 must be told rather than asked to infer."""

    message_id: str
    direction: Direction
    turn_index: int
    is_reply: bool
    reply_depth: int


@dataclass(frozen=True)
class ReconstructedThread:
    """L1.3.6-U1's answer: the whole thread's envelope."""

    thread_id: str | None
    turns: tuple[MessageTurn, ...]
    thread_depth: int
    last_inbound_at: datetime | None
    last_outbound_at: datetime | None
    ball_in_court: BallInCourt
    #: The identities that were treated as "us". Carried so a wrong direction can be explained
    #: by the configuration that produced it rather than re-derived from a table that has since
    #: changed — an audit trail, and the fastest way to see an empty identity set.
    org_identities: frozenset[str] = field(default_factory=frozenset)


def _is_forward(message: ThreadMessage) -> bool:
    if message.is_forward is not None:
        return message.is_forward
    return bool(message.subject) and _FORWARD_SUBJECT.match(message.subject or "") is not None


def assemble_chain(messages: Sequence[ThreadMessage]) -> ThreadChain:
    """L1.3.6-U2 — order one thread's messages into its reply chain.

    The order is a depth-first walk of the reply forest: roots oldest first, siblings oldest
    first. For a linear thread — every email thread that has never branched, which is nearly
    all of them — that is exactly chronological order, and for a branched one it keeps a branch
    together, which is what "position in the chain" means to a reader.

    Three things this refuses to do, each because the alternative is worse than an unordered
    thread:

    * **Follow a parent that arrived later.** A parent link pointing forward in time is clock
      skew or a duplicated message id, and honouring it can build a cycle. The link is dropped;
      the message becomes a root. The chain stays a forest by construction, so no traversal
      here can loop.
    * **Treat a forward as a reply.** `Fwd:` carries the same subject and often the same
      `References` header, and counting it as a reply inflates the turn count of a conversation
      that has not actually had another turn.
    * **Count a message twice.** A re-sync re-lands the same `source_object_id`; the second
      copy is dropped rather than deepening the thread, because `thread_depth` feeds the tier
      router and a re-sync must not make a document more expensive.

    Raises `ValueError` on an empty sequence, or on messages from more than one thread — the
    caller groups, and silently reconstructing two threads as one produces an envelope that is
    confidently wrong for both.
    """
    if not messages:
        raise ValueError("assemble_chain needs at least one message")
    thread_ids = {m.thread_id for m in messages if m.thread_id}
    if len(thread_ids) > 1:
        raise ValueError(f"messages span {len(thread_ids)} threads: {sorted(thread_ids)!r} — "
                         "group by thread_id before reconstructing")
    thread_id = next(iter(thread_ids), None)

    chronological: list[ThreadMessage] = []
    seen: set[str] = set()
    for message in sorted(messages, key=lambda m: (m.occurred_at, m.message_id)):
        if message.message_id in seen:
            continue
        seen.add(message.message_id)
        chronological.append(message)
    position = {m.message_id: i for i, m in enumerate(chronological)}

    parents: dict[str, str | None] = {}
    declared_reply: dict[str, bool] = {}
    forwards: dict[str, bool] = {}
    for message in chronological:
        forward = _is_forward(message)
        forwards[message.message_id] = forward
        declared = bool(message.in_reply_to or message.references)
        declared_reply[message.message_id] = declared and not forward
        parent: str | None = None
        if not forward:
            candidates = ((message.in_reply_to,) if message.in_reply_to else ()) + \
                tuple(reversed(message.references))
            for candidate in candidates:
                if (candidate in position and candidate != message.message_id
                        and position[candidate] < position[message.message_id]):
                    parent = candidate
                    break
        parents[message.message_id] = parent

    children: dict[str | None, list[ThreadMessage]] = defaultdict(list)
    for message in chronological:                    # already chronological → siblings are too
        children[parents[message.message_id]].append(message)

    links: list[ChainLink] = []
    stack: list[tuple[ThreadMessage, int]] = [
        (m, 0) for m in reversed(children[None])]
    while stack:
        message, depth = stack.pop()
        links.append(ChainLink(
            message=message,
            turn_index=len(links),
            parent_message_id=parents[message.message_id],
            is_reply=declared_reply[message.message_id],
            is_forward=forwards[message.message_id],
            reply_depth=depth,
        ))
        stack.extend((child, depth + 1)
                     for child in reversed(children[message.message_id]))
    return ThreadChain(thread_id=thread_id, links=tuple(links))


def reconstruct_thread(messages: Sequence[ThreadMessage],
                       *,
                       org_identities: Iterable[str]) -> ReconstructedThread:
    """L1.3.6-U1 — direction, turn index and whose turn it is, for one thread.

    `org_identities` is every address that is US: seats, the account owner, the connected
    mailboxes. Matching is on the lowercased address, because a mailbox that writes `Rohit@` on
    Tuesday and `rohit@` on Wednesday is one person and a case-sensitive comparison would make
    half their mail inbound.

    `ball_in_court` is derived from the most recent message BY TIME, not from the last link of
    the walk: on a branched thread the newest message is the one the other party is waiting on,
    whichever branch it sits in. A thread whose newest message has an underivable direction
    yields `unknown` rather than falling back to an older message — "whose turn it is" is a
    claim about the present, and answering it from a stale turn is how a closed conversation
    keeps showing up as owed.
    """
    identities = frozenset(
        address.strip().lower() for address in org_identities if address and address.strip())
    chain = assemble_chain(messages)

    def direction_of(message: ThreadMessage) -> Direction:
        if not identities or not message.actor_email or not message.actor_email.strip():
            return Direction.unknown
        return (Direction.outbound if message.actor_email.strip().lower() in identities
                else Direction.inbound)

    turns: list[MessageTurn] = []
    last_inbound_at: datetime | None = None
    last_outbound_at: datetime | None = None
    newest: tuple[datetime, str, Direction] | None = None
    for link in chain.links:
        direction = direction_of(link.message)
        turns.append(MessageTurn(
            message_id=link.message.message_id,
            direction=direction,
            turn_index=link.turn_index,
            is_reply=link.is_reply,
            reply_depth=link.reply_depth,
        ))
        at = link.message.occurred_at
        if direction is Direction.inbound and (last_inbound_at is None or at > last_inbound_at):
            last_inbound_at = at
        if direction is Direction.outbound and (last_outbound_at is None or at > last_outbound_at):
            last_outbound_at = at
        stamp = (at, link.message.message_id, direction)
        if newest is None or stamp[:2] > newest[:2]:
            newest = stamp

    ball = BallInCourt.unknown
    if newest is not None:
        if newest[2] is Direction.inbound:
            ball = BallInCourt.us                    # they spoke last → we owe the reply
        elif newest[2] is Direction.outbound:
            ball = BallInCourt.them

    return ReconstructedThread(
        thread_id=chain.thread_id,
        turns=tuple(turns),
        thread_depth=chain.thread_depth,
        last_inbound_at=last_inbound_at,
        last_outbound_at=last_outbound_at,
        ball_in_court=ball,
        org_identities=identities,
    )


__all__ = [
    "BallInCourt",
    "ChainLink",
    "Direction",
    "MessageTurn",
    "ReconstructedThread",
    "ThreadChain",
    "ThreadMessage",
    "assemble_chain",
    "reconstruct_thread",
]
