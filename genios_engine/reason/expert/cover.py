"""What a covered file's review explains — the decisions that stand down for it, in either lane (STEP-12).

Tree `yc2_w27_s12` M33.C1.L-logic.V0.U10. Under `06` D1 a file a VALID review covers is decided ONCE, from
that review (`reason/domain_shadow`, M33.C1.L-integration.V1.U02), and what the review EXPLAINS stands
down: no second decision about the same matter, no decider and no R-1 asked about it. The first decided
re-record of the golden set (12 Oct, `03` F173) measured what "explains" had been: only the situations
anchored on the file itself. Beside the file's card stood the pack rule `unanswered_email` on the person
who wrote, the compiled lane's `meeting_follow_through` on the meeting's reading, `dependency_stated` on
the dependency the mail stated, `first_response_overdue` on the thread — each about the matter the review
had just decided, and the decider asked for each. One rule, for both lanes:

  * A NODE OF THE FILE — its anchor, or one of its people (`context/workstreams.WorkFile.people`: the
    anchor when it is a person, everyone who works at it when it is a company) — is explained by its own
    file's review, and only by it;
  * A NODE THAT IS NO ONE'S COUNTERPARTY — a thread, a meeting, its reading, a stated dependency, a
    condition — is explained by any covered file whose review saw it: such a node has no file of its
    own, and the review that saw every event behind it judged it. A person, a company or the tenant
    (`MEMBERS_ONLY`) is never matched this way: an introduction of two people is one thread and two files
    (`context/workstreams`), and one file's review must not stand the other's down;
  * and in both, only when EVERY event behind the decision was in what the review judged — the events and
    the booked meetings its stored fingerprint inputs name (`expert_reviews.inputs`, 0198). A decision
    resting on an event the review never saw — a private one, one the file does not hold, one from after
    a review that still stands — keeps its own path (STEP-12 §8.7). Nothing behind it, nothing explained.

Pure but for `covers_for`, which reads each file's stored review once.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from . import store as reviews

#: The node types matched by membership only, never by the events behind them: a file's counterparty —
#: a person or a company — and the tenant itself, whose situations are about the whole period.
MEMBERS_ONLY: frozenset[str] = frozenset({"person", "company", "tenant"})


def seen(inputs: Mapping[str, Any] | None) -> frozenset[str]:
    """What a review judged: the events and the booked meetings its fingerprint inputs name."""
    inputs = inputs or {}
    return frozenset(str(e) for e in (*(inputs.get("events") or ()), *(inputs.get("booked") or ())))


@dataclass(frozen=True, slots=True)
class FileCover:
    """One covered file: the fingerprint of its review, what that review judged, and who is in it."""

    file_id: str
    fingerprint: str
    seen: frozenset[str]
    members: frozenset[str]

    def explains(self, events: Iterable[str]) -> bool:
        """Every event behind a decision was in what this review judged — and there was one."""
        behind = {str(e) for e in events}
        return bool(behind) and behind <= self.seen


class Covers:
    """The covered files of one pass — and which of them, if any, explains a decision about a node."""

    def __init__(self, covers: Iterable[FileCover] = ()) -> None:
        self._covers = tuple(sorted(covers, key=lambda c: c.file_id))
        self._by_member: dict[str, list[FileCover]] = {}
        for cover in self._covers:
            for node in sorted(cover.members):
                self._by_member.setdefault(node, []).append(cover)

    def __len__(self) -> int:
        return len(self._covers)

    def __iter__(self) -> Iterator[FileCover]:
        return iter(self._covers)

    def explaining(self, node_id: str, node_type: str | None,
                   events: Iterable[str]) -> FileCover | None:
        """The covered file whose review explains a decision about `node_id` resting on `events`: the
        node's own file's (its anchor or one of its people) — or, for a node that is no one's
        counterparty, any covered file's. None when none does (see the module docstring)."""
        events = tuple(events)
        candidates = self._by_member.get(str(node_id))
        if candidates is None:
            if node_type is None or str(node_type) in MEMBERS_ONLY:
                return None
            candidates = list(self._covers)
        return next((cover for cover in candidates if cover.explains(events)), None)


def cover_of(row: reviews.StoredReview, *, people: Iterable[str] = ()) -> FileCover:
    """A stored review as a cover — what it judged; its file's anchor and people its members."""
    return FileCover(file_id=str(row.file_id), fingerprint=str(row.fingerprint), seen=seen(row.inputs),
                     members=frozenset({str(row.file_id), *(str(p) for p in people)}))


def covers_for(conn, org_id: str, files: Mapping[str, str],
               people: Mapping[str, Iterable[str]] | None = None) -> Covers:
    """Each file's review — `files[file_id]` is its fingerprint — read once. A row gone, or not VALID,
    covers nothing: only a valid review may decide (`migrations/0197`)."""
    out = []
    for file_id, fingerprint in sorted((files or {}).items()):
        row = reviews.read_review(conn, org_id, str(file_id), str(fingerprint))
        if row is not None and row.status == reviews.VALID and row.review is not None:
            out.append(cover_of(row, people=(people or {}).get(str(file_id), ())))
    return Covers(out)


__all__ = ["MEMBERS_ONLY", "Covers", "FileCover", "cover_of", "covers_for", "seen"]
