"""P-11 · who can cover a commitment whose owner is away. Deterministic; abstains without evidence.

Order (tightest claim first), each candidate an ACTIVE seat:
    1. `covers` — a declared responsibility over the commitment's scope (incl. its owner:
       `scope_kind='seat'|'person'`, i.e. "Shalini covers Anisha")
    2. `owns`   — a declared responsibility over the same scope
    3. past done work — the seat delivered an earlier commitment to the same beneficiary
Excluded: the absent owner, the recipient of the card, and anyone themselves away before the due
date (named in `blocked`, so the card can say "Shalini is also away"). No candidate → no proposal;
nothing is ever guessed from load, seniority or round-robin.
"""
from __future__ import annotations

from dataclasses import dataclass

from genios_engine.context.correlation_people import (CommitmentLink, answering_for,
                                                      same_beneficiary, scope_pairs_for)
from genios_engine.reason.team.common import TeamContext
from genios_engine.reason.team.emit import clip

_RANK = {"covers": 0, "owns": 1}
PAST_WORK_RANK = 2


@dataclass(frozen=True)
class Cover:
    seat_id: str | None = None
    name: str | None = None
    basis: str | None = None           # covers | owns | past_work
    phrase: str | None = None          # why, in words
    evidence: tuple[dict, ...] = ()
    blocked: tuple[str, ...] = ()      # names of candidates who are themselves away

    @property
    def proposed(self) -> bool:
        return self.seat_id is not None

    def sentence(self) -> str:
        if self.proposed:
            return f"Proposed cover: {self.name} ({self.phrase})."
        if self.blocked:
            names = ", ".join(self.blocked)
            verb = "is" if len(self.blocked) == 1 else "are"
            return f"No cover available: {names} {verb} also away."
        return "No cover on record."


def propose_cover(conn, ctx: TeamContext, link: CommitmentLink, *, away_seats: set[str],
                  exclude: set[str]) -> Cover:
    owner_label = link.owner.label if link.owner else "the owner"
    cands: dict[str, list] = {}          # seat → [rank, basis, phrase, evidence list]

    def add(seat: str, rank: int, basis: str, phrase: str, ev: dict) -> None:
        held = cands.get(seat)
        if held is None:
            cands[seat] = [rank, basis, phrase, [ev]]
            return
        held[3].append(ev)
        if rank < held[0]:
            held[0], held[1], held[2] = rank, basis, phrase

    for r in answering_for(conn, ctx.org_id, scope_pairs_for(link), ctx.now):
        rank = _RANK.get(r.accountability)
        if rank is None:
            continue
        what = (f"for {owner_label}" if r.scope_kind.lower() in ("seat", "person")
                else f"{r.scope_kind} {r.scope_key}")
        add(r.seat_id, rank, r.accountability, f"{r.accountability} {what}",
            {"kind": "responsibility", "seat_id": r.seat_id, "accountability": r.accountability,
             "scope_kind": r.scope_kind, "scope_key": r.scope_key, "source": r.source})
    for past in ctx.links:
        seat = past.owner.seat_id if past.owner else None
        if not seat or past.node_id == link.node_id or not past.done \
                or not same_beneficiary(past, link):
            continue
        whom = past.beneficiary.label if past.beneficiary else (past.owed_to or "them")
        add(seat, PAST_WORK_RANK, "past_work", f"delivered “{clip(past.text, 40)}” for {whom}",
            {"kind": "past_work", "seat_id": seat, "commitment_node_id": past.node_id,
             "text": past.text, "due": past.due.isoformat() if past.due else None})

    blocked: list[str] = []
    for seat, (rank, basis, phrase, evs) in sorted(cands.items(), key=lambda kv: (kv[1][0], kv[0])):
        if seat in exclude:
            continue
        person = ctx.directory.for_seat(seat)
        if person is None:
            continue
        if seat in away_seats:
            blocked.append(person.label)
            continue
        return Cover(seat, person.label, basis, phrase, tuple(evs), tuple(blocked))
    return Cover(blocked=tuple(blocked))


__all__ = ["Cover", "propose_cover"]
