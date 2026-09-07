"""D-09 · `DependencyChain` — what makes a deadline more than a calendar entry.

Without the blocking edge a due date is a reminder that fires at the person holding the
deliverable, who is frequently not the person who can unblock it. Globe names the failure in its
own words: *"'Deadline tomorrow' is the calendar's job and adds nothing."* With the chain, the
same date is a structure — an escalation can be aimed at the node that is actually stuck, which is
the difference between telling somebody they are late and telling them why.

The input already exists and nothing consumes it: L1 v2 publishes `ExtractionResult.dependencies`
with `blocker · blocked · dependency_type · evidence` on every message it extracts. This module is
the shape BLG-05 assembles those claims into, and it is read by two places that have nothing to
reason over today — L2.7.4's importance modifier 3d (*N items blocked on this*, because the cost
of an unresolved decision is the blocked work rather than the decision) and Layer 4's Dependency
unit.

**A false chain is worse than a missing one**, and every rule below follows from that one
sentence: a phantom blocker nags a real person about work that does not exist, and it does so with
the full authority of a system that says it checked. So:

* **Contiguity is enforced.** `links[i].blocked` must be `links[i+1].blocker`. A "chain" whose
  hops do not join is a list of unrelated pairs rendered as a causal sequence, and it typechecks
  perfectly.
* **Resolved links cannot appear.** Doc 03's mitigation for "resolved dependency stays in the
  chain" is that chains read only unresolved edges. Enforced at the seam rather than only in the
  traversal, because the traversal is not the only thing that will ever build one of these.
* **`circular_wait` is not a caller's opinion.** It is checked against the links: True iff the
  last hop returns to the first blocker. A circular wait is OUTPUT, not an error — "A waits on B,
  B waits on A" is precisely the Ownership intelligence — so it must be trustworthy enough to
  render, which means it cannot be settable independently of the structure it describes.
* **Depth is capped.** Beyond `MAX_DEPENDENCY_DEPTH` a chain is almost always an
  identity-resolution defect (two spellings of one team resolved to two nodes), and `truncated`
  is how the traversal says "I stopped, this is not the whole story" instead of implying it was.

GAP FLAG — doc 03 says "max depth 6" and never says whether depth counts NODES or EDGES. It is
edges here, which is the ordinary meaning in a depth-first traversal and the stricter of the two
readings; a six-edge chain carries seven nodes. Whoever builds `context/correlation_dependency.py`
must use the same unit, and `MAX_DEPENDENCY_DEPTH` is the one place it is written down.

GAP FLAG — doc 03's `missing_prerequisite` (a dependency whose blocker node does not exist) is an
OBSERVATION the traversal emits, not a property of a chain: by construction such a dependency
produces no edge and therefore appears in no chain. It has no type here, deliberately —
`contracts/quality.MissingFact` already carries typed absence, and inventing a second spelling of
"we expected a node and there was none" would fork the vocabulary that decides whether a negative
inference is licensed.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.validators import (require_bool, require_identifier,
                                                require_non_negative, require_text)

#: Max EDGES in one chain (see the module GAP FLAG on the unit). Doc 03: deeper than this is
#: almost always an identity-resolution error, so the traversal stops and flags rather than
#: spending the traversal budget confirming a defect.
MAX_DEPENDENCY_DEPTH = 6


class DependencyLink(BaseModel):
    """One hop: this blocks that, for this reason, with the receipt it was read from.

    A supporting type of D-09 rather than a tenth contract, the way `AbsenceType` supports D-07.
    It exists because the alternative — parallel `nodes` and `edge_types` tuples on the chain — is
    a shape whose invariant (`len(types) == len(nodes) - 1`) has to be re-checked by every reader,
    and because a hop is the thing that carries evidence. The chain does not have a receipt; each
    hop does, and that is what lets a card cite the sentence that established the blocking.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: The thing in the way. A RESOLVED node id — doc 03's hard rule 1 is that both endpoints go
    #: through the identity cascade and an unresolved endpoint produces NO edge, never a guessed
    #: one. `require_text`, not `require_identifier`: a resolved node id is frequently an email
    #: address and a `+` tag in one is legal.
    blocker: str
    #: The thing waiting.
    blocked: str
    #: approval | information | delivery | decision. Typed `str`, mirroring
    #: `contracts/extraction.Dependency.dependency_type` exactly rather than narrowing it: the
    #: kind decides who is escalated to and how long a wait may run, and a value L1 can publish
    #: must be a value L2 can carry.
    dependency_type: str
    #: The spans the blocking was read from. Non-empty: this is a claim about two named parties,
    #: and a claim with no receipt is a guess.
    evidence: tuple[EvidenceSpan, ...]
    #: Has the dependency been satisfied? Carried so a resolved edge is a fact the graph keeps,
    #: and refused inside a chain so a resolved edge is never nagged about. See the chain's rule.
    resolved: bool = False

    @field_validator("blocker", "blocked", mode="before")
    @classmethod
    def _endpoint(cls, value: Any) -> str:
        return require_text(value, "dependency endpoint")

    @field_validator("dependency_type", mode="before")
    @classmethod
    def _kind(cls, value: Any) -> str:
        return require_text(value, "dependency_type")

    @field_validator("resolved", mode="before")
    @classmethod
    def _resolved(cls, value: Any) -> bool:
        return require_bool(value, "resolved")

    @model_validator(mode="after")
    def _real_hop(self) -> DependencyLink:
        """A receipt, and two distinct ends.

        A self-blocking link is a one-node cycle that makes every traversal non-terminating while
        looking perfectly ordinary in a single row — the same failure `QualifiedEnterpriseSignal`
        refuses when a signal supersedes itself.
        """
        if not self.evidence:
            raise ValueError(
                "a dependency link requires evidence — 'A is blocked by B' names two real "
                "parties, and a claim with no receipt is a guess")
        if self.blocker == self.blocked:
            raise ValueError(
                f"a dependency link cannot block itself ({self.blocker!r}) — a one-node cycle "
                "makes every traversal non-terminating and looks ordinary in a single row")
        return self


class DependencyChain(BaseModel):
    """D-09 · `A blocks B blocks C`, assembled by BLG-05 from L1's dependency claims."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: The chain's own id. One traversal produces many chains and they are stored, compared and
    #: superseded independently.
    chain_id: str
    #: The hops, in order. Contiguous, unresolved, at most `MAX_DEPENDENCY_DEPTH` of them.
    links: tuple[DependencyLink, ...]
    #: True iff the last hop returns to the first blocker. Checked against `links`, never taken
    #: on trust — see the module docstring.
    circular_wait: bool = False
    #: The traversal hit the depth cap and stopped. `False` on a chain that ended naturally. This
    #: is how "there may be more" is said out loud instead of being implied by a chain that just
    #: happens to be six long.
    truncated: bool = False
    #: How many items are blocked on this chain's ROOT — the derived fact L2.7.4 modifier 3d
    #: consumes. Carried rather than recomputed by each reader, because the count is over the
    #: whole graph and a chain is one path through it.
    blocked_count: int = 0

    @field_validator("chain_id", mode="before")
    @classmethod
    def _chain_id(cls, value: Any) -> str:
        return require_identifier(value, "chain_id")

    @field_validator("circular_wait", "truncated", mode="before")
    @classmethod
    def _flags(cls, value: Any) -> bool:
        return require_bool(value, "chain flag")

    @field_validator("blocked_count", mode="before")
    @classmethod
    def _blocked_count(cls, value: Any) -> int:
        return require_non_negative(value, "blocked_count")

    @model_validator(mode="after")
    def _well_formed_chain(self) -> DependencyChain:
        """Contiguity, the depth cap, the resolved rule, and `circular_wait` in both directions.

        Every one of them exists because a false chain nags a real person about work that does
        not exist, with the authority of a system that says it checked. The `circular_wait`
        check is enforced in BOTH directions on purpose: a chain that closes and does not say so
        is a cycle rendered as a sequence with a start and an end, which is a card telling
        somebody to go unblock the person who is waiting on them.
        """
        if not self.links:
            raise ValueError("a dependency chain requires at least one link")
        if len(self.links) > MAX_DEPENDENCY_DEPTH:
            raise ValueError(
                f"a dependency chain may traverse at most {MAX_DEPENDENCY_DEPTH} edges (got "
                f"{len(self.links)}) — deeper is almost always an identity-resolution defect, "
                "and `truncated` is how the traversal says it stopped")
        broken = [index for index in range(len(self.links) - 1)
                  if self.links[index].blocked != self.links[index + 1].blocker]
        if broken:
            raise ValueError(
                f"dependency chain links must join: link {broken[0]} blocks "
                f"{self.links[broken[0]].blocked!r} but link {broken[0] + 1} starts at "
                f"{self.links[broken[0] + 1].blocker!r} — unjoined hops rendered as a sequence "
                "are a causal claim nobody made")
        resolved = [link.blocked for link in self.links if link.resolved]
        if resolved:
            raise ValueError(
                f"a chain may contain no resolved link (found {resolved}) — chains read only "
                "unresolved edges, or the system nags about work that is done")
        closes = self.links[-1].blocked == self.links[0].blocker
        if closes and not self.circular_wait:
            raise ValueError(
                f"this chain closes back on {self.links[0].blocker!r} and must set "
                "circular_wait — a cycle rendered as a sequence tells somebody to go unblock the "
                "person who is waiting on them")
        if self.circular_wait and not closes:
            raise ValueError(
                "circular_wait is set on a chain that does not close — the flag is checked "
                "against the links and is not a caller's opinion")
        return self

    @property
    def nodes(self) -> tuple[str, ...]:
        """The chain's nodes in order, blocker first. Derived from `links` rather than stored
        beside them, so the two can never disagree about the same path."""
        return (self.links[0].blocker, *(link.blocked for link in self.links))

    @property
    def depth(self) -> int:
        """Edges traversed. See the module GAP FLAG on the unit."""
        return len(self.links)

    @property
    def root(self) -> str:
        """The node everything downstream is waiting on — the one an escalation is aimed at.

        On a circular chain this is one of several equally stuck nodes and is NOT "the cause";
        `circular_wait` is what tells a reader to treat it that way.
        """
        return self.links[0].blocker

    @property
    def terminal(self) -> str:
        """The node at the far end — the one whose deadline is at risk."""
        return self.links[-1].blocked


__all__ = ["MAX_DEPENDENCY_DEPTH", "DependencyChain", "DependencyLink"]
