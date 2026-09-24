"""L1.2.x-U4 · SENT/RECEIVED SYMMETRY — the blind spot a completeness ratio cannot see.

`sync_runner`'s `cursor_exhausted` answers *"did we read every page the provider offered?"* This
module answers a different question the same sweep cannot: **were we offered both sides?**

THE FAILURE IT CATCHES, and it is not hypothetical. A Gmail connection scoped to `in:inbox`, a
label filter that excludes `SENT`, an OAuth grant narrowed after the fact, a provider that pages
received and sent mail under different cursors — every one of them produces a sweep that exhausts
its cursor honestly and lands **half a conversation**. `cursor_exhausted=true` is then perfectly
true and perfectly misleading: we read everything we were shown, and we were shown one side.

What it costs downstream is specific. Layer 1 derives `direction`, `turn_index` and
`ball_in_court` from a thread's messages (`structural/threads.reconstruct_thread`), and Layer 2
builds `awaiting_response` and `first_response_overdue` situations on top. A thread whose outbound
half never landed reads as **"they wrote, we never answered"** — so the product tells a founder
they owe a reply they already sent. That is the second false chase, and the doc's own note on
`Commitment` says what the second false chase costs: *"the last time that founder reads a nudge
from us."*

WHY `parent_object_id` AND NOT THE REPLY CHAIN. ALG-03's `assemble_chain` walks `In-Reply-To` /
`References`, and the step-16 audit found **Gmail never captures either** — so a check built on it
would report perfect symmetry on a corpus it could not actually read. `parent_object_id` is the
provider's own thread id (Gmail's `threadId`), it is populated on every landed message, and it is
the one grouping that is true today. A check that works on real data beats a check that is
theoretically better on data we do not have.

PURE: no clock, no I/O, no model. It takes the pairs and returns the finding.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

#: The three values `structural/threads.Direction` produces, as plain strings — this module is
#: handed rows out of storage and must not require the enum to read them.
INBOUND = "inbound"
OUTBOUND = "outbound"
UNKNOWN = "unknown"

#: Why a thread is one-sided. Reported per thread, because the three are not equally alarming and
#: an operator who cannot tell them apart treats all three as the worst one.
ONLY_INBOUND = "only_inbound"
ONLY_OUTBOUND = "only_outbound"
UNDERIVABLE = "underivable"


@dataclass(frozen=True, slots=True)
class OneSidedThread:
    """A thread that landed with one side of the conversation missing."""

    thread_key: str
    reason: str
    inbound: int
    outbound: int
    unknown: int

    @property
    def messages(self) -> int:
        return self.inbound + self.outbound + self.unknown

    @property
    def is_singleton(self) -> bool:
        """One message, so it never had a chance to be two-sided. Still reported — it may be the
        unanswered thread somebody is looking for — but never counted in the rate."""
        return self.messages == 1


@dataclass(frozen=True, slots=True)
class SymmetryReport:
    """What a sweep's threads look like, and the one number worth putting on a dashboard.

    `asymmetry_bp` is INTEGER BASIS POINTS like every other ratio in this layer — never a float,
    never a percentage rounded on the way out. Doctrine V-7 is not a formatting preference: a
    float here reaches storage as jsonb and comes back as a number nobody can trace to a count.
    """

    threads: int = 0
    two_sided: int = 0
    one_sided: tuple[OneSidedThread, ...] = ()
    #: Threads with no derivable direction AT ALL. Counted apart from `one_sided` because they are
    #: a different defect: not "we are missing a side" but "we cannot tell which side anything is",
    #: which points at `org_identities` being empty rather than at the mailbox scope.
    undirected: int = 0
    singleton: int = 0

    @property
    def asymmetry_bp(self) -> int:
        """One-sided threads per 10,000, over threads that had a chance to be two-sided.

        SINGLETONS ARE EXCLUDED FROM BOTH SIDES OF THE RATIO, and getting that wrong is how this
        number becomes nonsense. A thread with exactly one message is not evidence of a missing
        side — a newsletter, a notification and a cold email that got no reply are all
        legitimately one message long — so counting them would put a permanent alarm on a healthy
        mailbox and train every operator to ignore the number.

        The first version of this property removed them from the denominator ONLY, which made
        three newsletters beside one healthy thread report **30000 bp**: a rate above 100%, from
        a mailbox with nothing wrong with it. Caught by
        `test_a_single_message_thread_is_not_evidence_of_a_missing_side`, which is the row that
        exists to pin exactly this.

        The singleton ROWS stay in `one_sided` regardless. A thread that should have had a reply
        and did not is precisely what `awaiting_response` is about, so the judgement is about the
        RATE and never about hiding the finding.

        Integer division, so the rate is truncated and never overstated. Zero eligible threads
        reports 0, which is why a caller must read it beside `threads`: a sweep with no
        multi-message threads is not a symmetrical sweep, and only the two together say which.
        """
        eligible = self.threads - self.singleton
        if eligible <= 0:
            return 0
        counted = sum(1 for finding in self.one_sided if not finding.is_singleton)
        return counted * 10_000 // eligible


def _direction_of(value: object) -> str:
    """One stored direction into this module's vocabulary. Anything unrecognised is UNKNOWN —
    never guessed into a side, because a guessed direction is exactly the thing whose absence
    this check exists to report."""
    text = getattr(value, "value", value)
    if not isinstance(text, str):
        return UNKNOWN
    text = text.strip().lower()
    return text if text in (INBOUND, OUTBOUND) else UNKNOWN


def check_symmetry(messages: Iterable[Mapping[str, object]]) -> SymmetryReport:
    """Group landed messages by thread and report the ones that arrived one-sided.

    Each item needs two keys and nothing else: `thread_key` (the provider's thread id, from
    `parent_object_id`) and `direction`. Items with no thread key are SKIPPED rather than pooled
    under a placeholder — a single bucket of every threadless message would report itself as one
    enormous one-sided thread and drown the real findings.

    Deterministic: threads are reported in sorted key order, so two runs over one corpus produce
    byte-identical output and a diff between two sweeps means something changed rather than that
    a dict iterated differently.
    """
    buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {INBOUND: 0, OUTBOUND: 0, UNKNOWN: 0})
    for message in messages:
        key = message.get("thread_key")
        if not isinstance(key, str) or not key.strip():
            continue
        buckets[key.strip()][_direction_of(message.get("direction"))] += 1

    one_sided: list[OneSidedThread] = []
    two_sided = undirected = singleton = 0
    for key in sorted(buckets):
        counts = buckets[key]
        inbound, outbound, unknown = counts[INBOUND], counts[OUTBOUND], counts[UNKNOWN]
        if inbound + outbound + unknown == 1:
            singleton += 1
        if inbound and outbound:
            two_sided += 1
            continue
        if not inbound and not outbound:
            # Every message present, no direction on any of them. `org_identities` is the usual
            # cause and the fix is a configuration one, so it is not filed as a missing side.
            undirected += 1
            continue
        reason = ONLY_INBOUND if inbound else ONLY_OUTBOUND
        one_sided.append(OneSidedThread(thread_key=key, reason=reason, inbound=inbound,
                                        outbound=outbound, unknown=unknown))

    return SymmetryReport(threads=len(buckets), two_sided=two_sided,
                          one_sided=tuple(one_sided), undirected=undirected,
                          singleton=singleton)


__all__ = ["INBOUND", "ONLY_INBOUND", "ONLY_OUTBOUND", "OUTBOUND", "UNDERIVABLE", "UNKNOWN",
           "OneSidedThread", "SymmetryReport", "check_symmetry"]
