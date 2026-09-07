"""L2.3.8 · BLG-05 — dependency correlation, the thing that makes a deadline more than a calendar.

Doc 03 states the failure this closes in Globe's own words: *"'Deadline tomorrow' is the calendar's
job and adds nothing."* A due date fires at whoever holds the deliverable, who is routinely not the
person who can move it. The blocking chain is what turns that date into a structure: an escalation
can be aimed at the node that is actually stuck.

L1 v2 has published the input on every message it extracts since the layer landed —
`ExtractionResult.dependencies[]`, carrying `blocker · blocked · dependency_type · evidence` — and
until this module nothing read it. Two consumers have been reasoning over nothing as a result:
L2.7.4's importance modifier 3d (*N items blocked on this*, because the cost of an unresolved
decision is the blocked work rather than the decision) and Layer 4's Dependency unit.

THE SIX ORDERED STEPS (doc 03, L2.3.8-U1), and where each one lives here:

    1. EDGES     `materialize_edges` — every claim becomes a typed edge, or is dropped with a
                 stated reason. Nothing is guessed into existence.
    2. RESOLVE   the same call's injected `resolve`, backed by `graph_endpoint_resolver` — both
                 endpoints through the identity cascade, so "Finance" and "finance@acme.ai" are
                 one node and an unresolved endpoint is NO edge.
    3. CHAINS    `build_chains` — depth-first from each unblocked root, `MAX_DEPENDENCY_DEPTH`
                 EDGES deep (the contract's unit; see the GAP FLAG note below).
    4. CYCLES    the same call — circular waits are OUTPUT, not errors, and they are found by a
                 separate scan because a pure cycle has no unblocked root to start from.
    5. MISSING   `materialize_edges` again — a dependency whose blocker resolves to nothing is a
                 typed absence (`contracts/quality.MissingFact`), not an invented node.
    6. COUNT     `blocked_counts` — written as a derived fact by `refresh_dependency_chains`.

**A FALSE CHAIN IS WORSE THAN A MISSING ONE.** A phantom blocker nags a real person about work
that does not exist, with the full authority of a system that says it checked. Every refusal below
follows from that one sentence, and the refusals are the feature:

  * an endpoint the identity cascade cannot resolve produces no edge, ever;
  * a claim group whose every member carries `resolved_at` produces no edge — doc 03's mitigation
    for "resolved dependency stays in the chain" is that chains read only unresolved edges;
  * a cycle longer than the depth cap is REFUSED rather than truncated into a sequence, because a
    truncated cycle rendered as a chain is a card telling somebody to go unblock the person who
    is waiting on them;
  * a `missing_prerequisite` whose caller declared no coverage basis is `UNKNOWABLE`, never
    `GENUINELY_ABSENT` — "we could not find the blocker" is not the same claim as "the blocker
    does not exist", and only the second one licenses telling a human there is nobody there.

GAP FLAG (inherited, resolved the same way) — doc 03 says "max depth 6" and never says whether
depth counts NODES or EDGES. `contracts/dependency.MAX_DEPENDENCY_DEPTH` reads it as EDGES, the
stricter reading, and this module imports that constant rather than restating the number. A
mismatch here would mean the builder and the contract disagree about what a legal chain is, and
the disagreement would surface as a `ValidationError` on a real tenant's data.

GAP FLAG — nothing in this build WRITES `resolved_at` on a dependency yet. L1 publishes the claim
and no lane retires it. The rule is enforced anyway, at the seam and in the contract, because the
retiring lane is the next thing anybody adds and the mitigation must already be in place when it
arrives; `refresh_dependency_chains` takes a `resolutions` mapping so a future retirement lane
hands its verdict in rather than editing this traversal.

DETERMINISM — no clock, no float, no model. `eval_time` is a parameter, every count is an integer,
every collection is sorted before it is traversed, and `chain_id` is a content hash of the path. A
sweep that runs twice at one instant writes byte-identical rows. Doc 03's group gate greps every
`context/correlation*.py` for a model client by name and must find nothing — not even in a comment,
which is why this paragraph does not spell either name. Correlation's two model sites are M-3
(ambiguous conversation matching) and M-5 (condition parsing) and neither is here: "does A block B"
was already decided by the sentence L1 quoted.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from genios_engine.context.analytic.publish import close_derived_facts, publish_derived_fact
from genios_engine.contracts.dependency import (MAX_DEPENDENCY_DEPTH, DependencyChain,
                                                DependencyLink)
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import Dependency
from genios_engine.contracts.quality import AbsenceType, MissingFact
from genios_engine.contracts.validators import require_aware
from genios_engine.contracts.visibility import ORG, PARTICIPANTS
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.context.dependency")

# =================================================================================================
# NAMES THE STORE AND THE READERS SHARE
# =================================================================================================

#: L1's extraction store (migration 0080) and the landing table its rows are dated by. Same pair
#: `capture/esqe/baseline_reader.py` reads: the extraction is filed under a processing key that
#: says nothing about when the message arrived, and when we READ a message is not when the
#: blocking was stated.
EXTRACTION_TABLE = "l1_extraction_results"
EVENT_TABLE = "source_events"

#: The derived fields this module owns in `graph_facts`. Namespaced under `derived.dependency`
#: so the sweep can retire its own rows by prefix without touching a fact anybody else wrote —
#: which is what stops a chain that no longer exists from sitting on a node for ever.
FACT_PREFIX = "derived.dependency"
FIELD_BLOCKED_COUNT = f"{FACT_PREFIX}.blocked_count"
FIELD_CHAINS = f"{FACT_PREFIX}.chains"
FIELD_CIRCULAR_WAIT = f"{FACT_PREFIX}.circular_wait"
FIELD_MISSING_PREREQUISITE = f"{FACT_PREFIX}.missing_prerequisite"
#: The `fact_version_id` prefix. `publish_derived_fact` keys the rest of the id on (node, field,
#: PERIOD) and scopes both its open-row lookup and its close by this prefix, so the sweep can only
#: ever supersede or retire a row THIS module wrote. Rows written under the old period-less shape
#: (`fv_dep:<field>:<node>`) still begin with it and are absorbed rather than orphaned.
VERSION_PREFIX = "fv_dep"
VALUE_TYPE = "dependency"

#: WHO EACH OF THESE FOUR FACTS MAY REACH — stated per field, because `publish_derived_fact`
#: refuses to default it and because `'org'` spelled inline in four modules was a scope nobody
#: could grep for. `contracts/visibility` states the law: *the audience of a derived insight can
#: never be wider than the audience of the evidence it came from.*
#:
#: THE LINE: a derived row's audience is set by WHAT THE ROW CARRIES, not by the ultimate
#: provenance of the numbers in it. Trace every input back to the mail it came from and every fact
#: in the graph is `private`, which turns the column into a constant that says nothing. Carry
#: somebody's sentence or somebody else's identity forward, and you have republished it.
#:
#: By that line these fields split, and the split is the reason this is a table rather than one
#: literal:
#:
#: * `chains`, `circular_wait` and `missing_prerequisite` are `PARTICIPANTS`. Each row embeds
#:   `EvidenceSpan`s — the VERBATIM sentence, with its offsets, out of one email thread — and each
#:   names THIRD-PARTY nodes ("legal is waiting on finance") on a subject that is not them. That
#:   is thread content and thread identities republished onto a node, and L1 stamps a mail event
#:   `participants` precisely so it cannot be read by anyone who was not on it. Writing it `org`
#:   was the widening, and it was invisible because nothing enforces this column yet — which makes
#:   it exactly the kind of claim that has to be right BEFORE somebody builds the enforcement.
#: * `blocked_count` is `ORG`. It carries ONE INTEGER about its own subject: no quote, no offsets,
#:   no other node's name, nothing a reader could turn back into a sentence. It is
#:   `context/derived.py`'s defensible case — a fact that describes the subject alone is as
#:   visible as the subject — and it is the field L2.7.4's importance modifier 3d reads, so
#:   narrowing it on provenance grounds would cost a real reader for no disclosure it prevents.
#:
#: `graph_facts` has no principals column (only `source_events` does), so `participants` here
#: records the CEILING — "narrower than the tenant; the named people are on the source events" —
#: which is the most this table can honestly say and strictly more than `'org'` said.
_FIELD_SCOPE: dict[str, str] = {
    FIELD_CHAINS: PARTICIPANTS,
    FIELD_CIRCULAR_WAIT: PARTICIPANTS,
    FIELD_MISSING_PREREQUISITE: PARTICIPANTS,
    FIELD_BLOCKED_COUNT: ORG,
}

#: The expectation a `missing_prerequisite` is stated against. A field PATH, not a sentence:
#: `MissingFact.expected_fact` is consulted by predicate evaluation, and a human label with
#: spaces in it answers FALSE where it should answer UNKNOWN.
MISSING_PREREQUISITE_FACT = "dependency.blocker"

#: How far back a sweep reads dependency claims. A blocking stated two years ago and never
#: restated is not a live chain; it is history, and traversing it would nag about the archive.
DEPENDENCY_WINDOW_DAYS = 180

#: Ceilings on one sweep, in the shape `baseline_reader.MAX_OBSERVATIONS` already uses: a cost
#: ceiling, not a sample. A tenant with a decade of mail must not turn a once-per-sweep read into
#: an unbounded scan, and a graph big enough to exceed these is a graph whose chains are an
#: identity-resolution defect rather than a finding.
MAX_CLAIMS_PER_SWEEP = 5000
MAX_CHAINS_PER_ROOT = 8
MAX_FACT_WRITES_PER_SWEEP = 2000


class DropReason(str, Enum):
    """Why a claim produced no edge. Every dropped claim carries one — a silent drop is how a
    tenant ends up with an empty Ownership surface and nobody able to say whether that means
    "nothing is blocked" or "the resolver never matched anything"."""

    #: The blocker end resolved to nobody. Doc 03 hard rule 1: NO edge, never a guessed one.
    UNRESOLVED_BLOCKER = "unresolved_blocker"
    #: The waiting end resolved to nobody. Not a `missing_prerequisite`: we do not know WHO is
    #: waiting, so there is no subject to state the absence on.
    UNRESOLVED_BLOCKED = "unresolved_blocked"
    #: Both ends resolved to the same node. The contract refuses a self-blocking link, and it is
    #: right to: a one-node cycle makes every traversal non-terminating while looking ordinary.
    SELF_LOOP = "self_loop"
    #: Every claim for this pair carries `resolved_at`. Chains read only unresolved edges.
    RESOLVED = "resolved"
    #: The claim carried no usable span. A claim about two named parties with no receipt is a
    #: guess, and `DependencyLink` refuses it at construction.
    NO_EVIDENCE = "no_evidence"


# =================================================================================================
# THE INPUT — a claim, with the provenance the contract type does not carry
# =================================================================================================

@dataclass(frozen=True, slots=True)
class DependencyClaim:
    """One `Dependency` L1 published, plus WHEN and FROM WHAT it was read.

    `contracts/extraction.Dependency` is the claim; it deliberately carries no event id and no
    resolution, because those are facts about the claim's life in the graph rather than about the
    sentence. Wrapping rather than widening keeps L1's contract the shape L1 publishes.
    """

    blocker: str
    blocked: str
    dependency_type: str
    evidence: tuple[EvidenceSpan, ...]
    event_id: str
    #: World time of the message the claim was read from — never capture time.
    occurred_at: datetime | None = None
    #: When the blocking stopped being true. See the module GAP FLAG: nothing writes this yet,
    #: and the rule that reads it is enforced regardless.
    resolved_at: datetime | None = None

    @property
    def resolved(self) -> bool:
        return self.resolved_at is not None

    @classmethod
    def from_extraction(cls, claim: Dependency, *, event_id: str,
                        occurred_at: datetime | None = None,
                        resolved_at: datetime | None = None) -> DependencyClaim:
        """Built FROM the contract, so a claim that L1 could not have published cannot enter."""
        return cls(blocker=claim.blocker, blocked=claim.blocked,
                   dependency_type=claim.dependency_type, evidence=tuple(claim.evidence),
                   event_id=event_id, occurred_at=occurred_at, resolved_at=resolved_at)


@dataclass(frozen=True, slots=True)
class DroppedClaim:
    """A claim that produced no edge, and the stated reason."""

    claim: DependencyClaim
    reason: DropReason


@dataclass(frozen=True, slots=True)
class MissingPrerequisite:
    """Step 5's finding — a real party waiting on something the graph cannot name.

    GAP FLAG — doc 03 calls this a `missing_prerequisite` OBSERVATION that names the blocker, and
    `contracts/quality.MissingFact` (correctly) has no slot for the name: `expected_fact` is a
    field PATH validated by `require_identifier`, so "Legal team" cannot go in it, and the
    contract forbids extra fields on purpose. Widening the contract for one caller would fork the
    vocabulary that decides whether a negative inference is licensed. So the typed absence stays
    exactly what X0 built, and the two things a card additionally needs — WHO was named and the
    sentence that named them — travel beside it here.
    """

    #: The typed absence. `GENUINELY_ABSENT` only when the caller declared what it searched.
    absence: MissingFact
    #: The blocker exactly as the source wrote it: "Finance", "legal", "the security review".
    #: Never resolved, by definition — that is what makes this a finding.
    blocker_named: str
    #: The receipt. An absence has no span of its own, but the CLAIM that ran into it does, and
    #: that sentence is what makes "you are waiting on Finance and we have no Finance" checkable.
    evidence: tuple[EvidenceSpan, ...]

    @property
    def subject_node_id(self) -> str:
        return self.absence.subject_node_id


@dataclass(frozen=True, slots=True)
class Materialization:
    """Step 1+2+5's whole answer: the edges, the typed absences, and what was refused."""

    edges: tuple[DependencyLink, ...] = ()
    missing: tuple[MissingPrerequisite, ...] = ()
    dropped: tuple[DroppedClaim, ...] = ()

    @property
    def dropped_by_reason(self) -> Mapping[str, int]:
        counts: dict[str, int] = {}
        for entry in self.dropped:
            counts[entry.reason.value] = counts.get(entry.reason.value, 0) + 1
        return counts


#: What resolves a claim's raw endpoint text to a graph node id. A callable rather than a class
#: because doc 03 hard rule 6 is that the graph read is INJECTED: the traversal takes nodes and
#: edges, and every test in this suite drives it with a dict.
EndpointResolver = Callable[[str], "str | None"]


def materialize_edges(claims: Sequence[DependencyClaim], resolve: EndpointResolver, *,
                      coverage_basis: Sequence[str] = ()) -> Materialization:
    """Steps 1, 2 and 5 — claims become edges, or become nothing with a reason.

    **Claims are grouped by the RESOLVED pair, not by the sentence.** Two messages a month apart
    both saying "legal is waiting on finance" are one edge observed twice, and treating them as
    two would make a two-node graph look like a cycle the moment one of them was restated in the
    other direction. The group's evidence is the union of its live claims' spans, so the card can
    cite every sentence that established the blocking rather than whichever one was read first.

    **A group is live if ANY of its claims is unresolved.** The alternative — earliest wins, or
    latest wins — gets the common case wrong in both directions: an old satisfied blocking plus a
    fresh restatement is a live edge, and a resolved restatement of a stale claim is a dead one.

    `coverage_basis` is what was consulted when the blocker did not resolve. Supplied, the absence
    is `GENUINELY_ABSENT` and licenses saying "there is no such thing"; empty, it is `UNKNOWABLE`
    and licenses nothing. The caller has to say which, because only the caller knows what it read.
    """
    basis = tuple(sorted({str(entry).strip() for entry in coverage_basis if str(entry).strip()}))
    groups: dict[tuple[str, str, str], list[DependencyClaim]] = {}
    dropped: list[DroppedClaim] = []
    missing: dict[tuple[str, str], MissingFact] = {}
    missing_spans: dict[tuple[str, str], list[EvidenceSpan]] = {}
    memo: dict[str, str | None] = {}

    def _resolve(raw: str) -> str | None:
        if raw not in memo:
            memo[raw] = resolve(raw)
        return memo[raw]

    for claim in claims:
        if not claim.evidence:
            dropped.append(DroppedClaim(claim, DropReason.NO_EVIDENCE))
            continue
        blocker_node = _resolve(claim.blocker)
        blocked_node = _resolve(claim.blocked)
        if not blocked_node:
            dropped.append(DroppedClaim(claim, DropReason.UNRESOLVED_BLOCKED))
            continue
        if not blocker_node:
            # Step 5. We know who is waiting and not what for — that is the finding, and it is
            # typed absence rather than a second spelling of "we expected a node and there was
            # none". A blocker we cannot name is never invented into one.
            dropped.append(DroppedClaim(claim, DropReason.UNRESOLVED_BLOCKER))
            key = (blocked_node, claim.blocker)
            spans = missing_spans.setdefault(key, [])
            spans.extend(span for span in claim.evidence if span not in spans)
            if key not in missing:
                missing[key] = MissingFact(
                    subject_node_id=blocked_node, expected_fact=MISSING_PREREQUISITE_FACT,
                    absence_type=AbsenceType.GENUINELY_ABSENT if basis else AbsenceType.UNKNOWABLE,
                    coverage_ready=True if basis else None, coverage_basis=basis)
            continue
        if blocker_node == blocked_node:
            dropped.append(DroppedClaim(claim, DropReason.SELF_LOOP))
            continue
        groups.setdefault((blocker_node, blocked_node, claim.dependency_type), []).append(claim)

    edges: list[DependencyLink] = []
    for key in sorted(groups):
        members = groups[key]
        live = [member for member in members if not member.resolved]
        if not live:
            dropped.extend(DroppedClaim(member, DropReason.RESOLVED) for member in members)
            continue
        blocker_node, blocked_node, kind = key
        edges.append(DependencyLink(blocker=blocker_node, blocked=blocked_node,
                                    dependency_type=kind, evidence=_union_spans(live),
                                    resolved=False))
    return Materialization(
        edges=tuple(edges),
        missing=tuple(MissingPrerequisite(absence=missing[key], blocker_named=key[1],
                                          evidence=tuple(missing_spans.get(key, ())))
                      for key in sorted(missing)),
        dropped=tuple(dropped))


def _union_spans(claims: Iterable[DependencyClaim]) -> tuple[EvidenceSpan, ...]:
    """Every distinct span the live claims carry, in a stable order.

    `EvidenceSpan` is frozen and therefore hashable, which is what lets the many claims read from
    one sentence share a receipt instead of each carrying a near-identical copy. Sorted by the
    span's own coordinates so two sweeps that read the claims in a different order still produce
    a byte-identical link.
    """
    seen: set[EvidenceSpan] = set()
    for claim in claims:
        seen.update(claim.evidence)
    return tuple(sorted(seen, key=lambda span: (span.source_ref, span.start_offset,
                                                span.end_offset, span.quote)))


# =================================================================================================
# THE TRAVERSAL — steps 3 and 4, pure over nodes and edges
# =================================================================================================

@dataclass(frozen=True, slots=True)
class RefusedCycle:
    """A circular wait that exists and could not be stated legally.

    Doc 03: deeper than the cap is almost always an identity-resolution error, so it is FLAGGED
    rather than traversed further. A cycle longer than `MAX_DEPENDENCY_DEPTH` edges cannot become
    a `DependencyChain` at all — the contract refuses it — and truncating it into a sequence would
    render a cycle as a line with a start and an end, which is the one thing that must never be
    shown. So it comes back as this: the members, named, with nothing implied about direction.
    """

    #: The strongly-connected members, sorted. Not a path: any path through them would be a claim
    #: about order that the refusal is precisely unable to make.
    members: tuple[str, ...]
    #: How deep the traversal was allowed to look before giving up.
    depth_cap: int = MAX_DEPENDENCY_DEPTH


@dataclass(frozen=True, slots=True)
class ChainSet:
    """Everything one traversal found: the chains, the cycles it could state, the ones it could
    not, and the blocked counts step 6 writes out."""

    chains: tuple[DependencyChain, ...] = ()
    refused_cycles: tuple[RefusedCycle, ...] = ()
    blocked_counts: Mapping[str, int] = field(default_factory=dict)

    @property
    def circular(self) -> tuple[DependencyChain, ...]:
        """The chains that close on themselves — Globe's Ownership surface, in one property."""
        return tuple(chain for chain in self.chains if chain.circular_wait)

    @property
    def truncated(self) -> tuple[DependencyChain, ...]:
        """The chains that hit the depth cap and said so."""
        return tuple(chain for chain in self.chains if chain.truncated)

    def chains_from(self, root: str) -> tuple[DependencyChain, ...]:
        return tuple(chain for chain in self.chains if chain.root == root)


def chain_id_for(links: Sequence[DependencyLink]) -> str:
    """A content address for the path — deterministic, and the same on every replay.

    Not a uuid: one traversal produces many chains, they are stored and compared and superseded
    independently, and a chain whose id changed every sweep would supersede itself for ever. The
    dependency TYPE is in the digest because "A waits on B for approval" and "A waits on B for
    information" are two blockings with two remedies, not one chain seen twice.
    """
    payload = "\x1f".join(f"{link.blocker}\x1e{link.dependency_type}\x1e{link.blocked}"
                          for link in links)
    return f"dep_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"


def _adjacency(edges: Sequence[DependencyLink]) -> dict[str, tuple[DependencyLink, ...]]:
    """blocker → its outgoing links, every list sorted. Sorting here is what makes the whole
    traversal replayable: DFS order is the only thing that decides which maximal path is found
    first, and an unsorted adjacency makes that a property of dict insertion order."""
    out: dict[str, list[DependencyLink]] = {}
    for edge in edges:
        out.setdefault(edge.blocker, []).append(edge)
    return {node: tuple(sorted(links, key=lambda link: (link.blocked, link.dependency_type)))
            for node, links in sorted(out.items())}


def unblocked_roots(edges: Sequence[DependencyLink]) -> tuple[str, ...]:
    """Nodes that block something and are blocked by nothing — step 3's starting set.

    A node inside a cycle is never here, by construction: everything in a cycle is blocked by
    something. That is why step 4 is a separate scan and not a special case of step 3.
    """
    blocking = {edge.blocker for edge in edges}
    waiting = {edge.blocked for edge in edges}
    return tuple(sorted(blocking - waiting))


def _strongly_connected(adjacency: Mapping[str, Sequence[DependencyLink]],
                        nodes: Sequence[str]) -> list[tuple[str, ...]]:
    """Tarjan, iterative — the components that contain a cycle.

    Iterative rather than recursive because the depth here is the graph's, not the chain's: the
    cap bounds a CHAIN, and a tenant whose identity resolution has fractured can present a
    thousand-node path that a recursive walk would meet as a `RecursionError` inside a sweep.

    A component of one node is not a cycle: `DependencyLink` refuses a self-blocking link, so a
    singleton component has no edge back to itself.
    """
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components: list[tuple[str, ...]] = []
    counter = 0

    for start in nodes:
        if start in index:
            continue
        work: list[tuple[str, int]] = [(start, 0)]
        while work:
            node, child = work[-1]
            if child == 0:
                index[node] = low[node] = counter
                counter += 1
                stack.append(node)
                on_stack.add(node)
            links = adjacency.get(node, ())
            if child < len(links):
                work[-1] = (node, child + 1)
                nxt = links[child].blocked
                if nxt not in index:
                    work.append((nxt, 0))
                elif nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                member: list[str] = []
                while True:
                    popped = stack.pop()
                    on_stack.discard(popped)
                    member.append(popped)
                    if popped == node:
                        break
                if len(member) > 1:
                    components.append(tuple(sorted(member)))
    return sorted(components)


def _maximal_paths(adjacency: Mapping[str, Sequence[DependencyLink]], root: str,
                   max_depth: int) -> list[tuple[tuple[DependencyLink, ...], bool]]:
    """Every maximal simple path out of `root`, each with "did it stop at the cap".

    MAXIMAL, not every prefix: a chain of three is one finding, and emitting A→B and A→B→C as two
    would make the same blocking appear twice on the same card with two different terminal nodes.

    A path stops for exactly three reasons, and they are not the same reason:
      * the far node blocks nothing further — the chain ended, `truncated=False`;
      * the cap was reached and the far node blocks something more — `truncated=True`, which is
        how the traversal says "there is more of this" instead of implying there is not;
      * the next hop is already ON this path — a cycle downstream of the root. The path ends
        there and `truncated` stays False, because the cycle is not this chain's story: step 4
        emits it as its own `circular_wait`, and marking the approach path truncated would claim
        the cap stopped it when the graph did.
    """
    found: list[tuple[tuple[DependencyLink, ...], bool]] = []
    stack: list[tuple[str, tuple[DependencyLink, ...], frozenset[str]]] = [
        (root, (), frozenset({root}))]
    while stack:
        node, path, seen = stack.pop()
        links = adjacency.get(node, ())
        extendable = [link for link in links if link.blocked not in seen]
        if not links or not extendable:
            if path:
                found.append((path, False))
            continue
        if len(path) >= max_depth:
            found.append((path, True))
            continue
        # Reversed, so the popped order matches the sorted adjacency and two runs enumerate the
        # paths in the same order — the property `chain_id` alone cannot give us.
        for link in reversed(extendable):
            stack.append((link.blocked, (*path, link), seen | {link.blocked}))
    return found


def _elementary_cycles(adjacency: Mapping[str, Sequence[DependencyLink]],
                       component: Sequence[str],
                       max_depth: int) -> list[tuple[DependencyLink, ...]]:
    """Every cycle inside one component, each found exactly once, bounded by the cap.

    Canonicalised by starting node: a cycle is enumerated only from its SMALLEST member and only
    through members that sort after it, so A→B→C→A is found once as (A,B,C) rather than three
    times rotated. Without that rule the same circular wait would be written onto three nodes as
    three different findings, and a founder would be told about one stuck triangle three times.
    """
    members = sorted(component)
    rank = {node: position for position, node in enumerate(members)}
    inside = set(members)
    cycles: list[tuple[DependencyLink, ...]] = []
    for start in members:
        floor = rank[start]
        stack: list[tuple[str, tuple[DependencyLink, ...], frozenset[str]]] = [
            (start, (), frozenset({start}))]
        while stack:
            node, path, seen = stack.pop()
            for link in reversed(adjacency.get(node, ())):
                nxt = link.blocked
                if nxt not in inside:
                    continue
                if nxt == start:
                    if path or link.blocker != link.blocked:
                        cycles.append((*path, link))
                    continue
                if nxt in seen or rank[nxt] < floor or len(path) + 1 >= max_depth:
                    continue
                stack.append((nxt, (*path, link), seen | {nxt}))
    return sorted(cycles, key=lambda links: tuple(link.blocker for link in links))


def blocked_counts(edges: Sequence[DependencyLink], *,
                   max_depth: int = MAX_DEPENDENCY_DEPTH) -> dict[str, int]:
    """Step 6 — how many distinct things are waiting on each node, directly or through others.

    TRANSITIVE, and that is the whole value of the number. L2.7.4's modifier 3d reads it as *"the
    cost of an unresolved decision is the blocked work"*, and the blocked work behind a stuck
    approval is everything downstream of it, not just the one team that wrote in. Direct-degree
    would rank a node blocking one team that blocks nine others below a node blocking two.

    Bounded by the same depth cap for the same reason the chains are: past it, the reachable set
    is describing an identity defect rather than the business. A node inside a cycle does not
    count itself — it is stuck, not waiting on its own output.
    """
    adjacency = _adjacency(edges)
    counts: dict[str, int] = {}
    for node in sorted(adjacency):
        reached: set[str] = set()
        frontier = {node}
        for _ in range(max_depth):
            nxt: set[str] = set()
            for current in sorted(frontier):
                for link in adjacency.get(current, ()):
                    if link.blocked not in reached and link.blocked != node:
                        reached.add(link.blocked)
                        nxt.add(link.blocked)
            if not nxt:
                break
            frontier = nxt
        if reached:
            counts[node] = len(reached)
    return counts


def build_chains(edges: Sequence[DependencyLink], *,
                 max_depth: int = MAX_DEPENDENCY_DEPTH) -> ChainSet:
    """Steps 3, 4 and 6 — the traversal, pure over the edges it is handed.

    Chains come back in a stable order (deepest first, then by content address) because the write
    budget downstream is a HEAD of this list: if the order moved between sweeps, which chains got
    written would move with it, and a tenant would watch findings appear and vanish with nothing
    having changed in their business.
    """
    if max_depth < 1 or max_depth > MAX_DEPENDENCY_DEPTH:
        raise ValueError(
            f"max_depth must be between 1 and {MAX_DEPENDENCY_DEPTH} edges (got {max_depth}) — "
            "the contract refuses a longer chain, so building one only moves the failure")
    adjacency = _adjacency(edges)
    nodes = sorted({edge.blocker for edge in edges} | {edge.blocked for edge in edges})

    chains: list[DependencyChain] = []
    for root in unblocked_roots(edges):
        for path, truncated in _maximal_paths(adjacency, root, max_depth):
            chains.append(DependencyChain(chain_id=chain_id_for(path), links=path,
                                          circular_wait=False, truncated=truncated))

    refused: list[RefusedCycle] = []
    for component in _strongly_connected(adjacency, nodes):
        found = _elementary_cycles(adjacency, component, max_depth)
        if not found:
            # A cycle exists — Tarjan proved it — and no legal statement of it fits inside the
            # cap. Doc 03's own reading: almost always an identity-resolution error.
            refused.append(RefusedCycle(members=tuple(component), depth_cap=max_depth))
            continue
        for path in found:
            chains.append(DependencyChain(chain_id=chain_id_for(path), links=path,
                                          circular_wait=True, truncated=False))

    chains.sort(key=lambda chain: (-chain.depth, chain.chain_id))
    counts = blocked_counts(edges, max_depth=max_depth)
    return ChainSet(chains=tuple(chains), refused_cycles=tuple(refused), blocked_counts=counts)


def correlate_dependencies(claims: Sequence[DependencyClaim], resolve: EndpointResolver, *,
                           coverage_basis: Sequence[str] = (),
                           max_depth: int = MAX_DEPENDENCY_DEPTH) -> "DependencyCorrelation":
    """All six steps, in order, over claims a caller already has. The pure entry point.

    `refresh_dependency_chains` is this function with a database on either side of it; every
    behaviour worth asserting is asserted here, against dicts.
    """
    material = materialize_edges(claims, resolve, coverage_basis=coverage_basis)
    return DependencyCorrelation(material=material,
                                 chains=build_chains(material.edges, max_depth=max_depth))


@dataclass(frozen=True, slots=True)
class DependencyCorrelation:
    """What one correlation produced: the edges and absences, and the traversal over them."""

    material: Materialization
    chains: ChainSet

    @property
    def edges(self) -> tuple[DependencyLink, ...]:
        return self.material.edges

    @property
    def missing(self) -> tuple[MissingPrerequisite, ...]:
        return self.material.missing

    @property
    def circular(self) -> tuple[DependencyChain, ...]:
        return self.chains.circular


# =================================================================================================
# THE READ — L1's claims, out of the store, once per sweep
# =================================================================================================

_CLAIMS_SQL = (
    "select e.event_id as event_id, e.occurred_at as occurred_at, "
    "       x.output -> 'dependencies' as dependencies "
    f"from {EXTRACTION_TABLE} x "
    f"join {EVENT_TABLE} e on e.event_id = x.event_id and e.org_id = x.org_id "
    "where x.org_id = :org and e.occurred_at >= :since and e.occurred_at <= :until "
    "  and jsonb_array_length(coalesce(x.output -> 'dependencies', '[]'::jsonb)) > 0 "
    "order by e.occurred_at desc, e.event_id limit :cap")


def _span_of(entry: Any) -> EvidenceSpan | None:
    """One stored evidence entry back into `EvidenceSpan`, or None when it is not that shape.

    Rebuilt THROUGH the contract, exactly as `baseline_reader._money_of` rebuilds `Money`: the
    span's own validators are what refuse an inverted range and a quote whose length disagrees
    with its offsets, and an edge evidenced by a row that skipped them is an edge citing text
    nobody can check.
    """
    if not isinstance(entry, dict):
        return None
    try:
        return EvidenceSpan(source_ref=entry["source_ref"], quote=entry["quote"],
                            start_offset=entry["start_offset"], end_offset=entry["end_offset"],
                            verified=bool(entry.get("verified", False)))
    except (KeyError, TypeError, ValueError):
        return None


def _claim_of(entry: Any, *, event_id: str, occurred_at: datetime | None,
              resolutions: Mapping[tuple[str, str], datetime]) -> DependencyClaim | None:
    """One stored `dependencies` entry back into a claim, or None.

    The `Dependency` contract is constructed first and its fields are read off the object, so a
    stored row missing `dependency_type`, carrying no receipt, or holding a confidence outside
    the band cannot enter the traversal — the same refusal L1's own publishing seam applies,
    applied again on the way back out, because a cache row can outlive the validator that wrote
    it.
    """
    if not isinstance(entry, dict):
        return None
    spans = [span for span in (_span_of(item) for item in entry.get("evidence") or []) if span]
    try:
        claim = Dependency(blocker=entry["blocker"], blocked=entry["blocked"],
                           dependency_type=entry["dependency_type"], evidence=spans,
                           confidence_bp=entry.get("confidence_bp", 5000))
    except (KeyError, TypeError, ValueError):
        return None
    key = (claim.blocker, claim.blocked)
    resolved_at = entry.get("resolved_at")
    if isinstance(resolved_at, str):
        try:
            resolved_at = datetime.fromisoformat(resolved_at.replace("Z", "+00:00"))
        except ValueError:
            resolved_at = None
    if not isinstance(resolved_at, datetime):
        resolved_at = None
    return DependencyClaim.from_extraction(
        claim, event_id=event_id, occurred_at=occurred_at,
        resolved_at=resolutions.get(key, resolved_at))


def read_dependency_claims(engine, org_id: str, *, eval_time: datetime,
                           window_days: int = DEPENDENCY_WINDOW_DAYS,
                           cap: int = MAX_CLAIMS_PER_SWEEP,
                           resolutions: Mapping[tuple[str, str], datetime] | None = None,
                           ) -> tuple[DependencyClaim, ...]:
    """Every dependency claim L1 filed for this org inside the window. Never raises into a sweep.

    ONCE PER SWEEP, NEVER PER EVENT — `baseline_reader`'s shape and its reason: a chain is a
    property of the whole graph, and paying a scan per message would put a table read on the
    ingestion path of every email for an answer that is the same all sweep.

    A database that is unreachable, a table a migration has not reached, a row whose json is not
    the shape this build knows: all of them yield fewer claims and no chains, which is the state
    every tenant was already in. An exception raised here would stop the drain for the whole
    tenant over a derived view.
    """
    at = require_aware(eval_time, "eval_time")
    if engine is None:
        return ()
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            rows = list(conn.execute(text(_CLAIMS_SQL), {
                "org": org_id, "since": at - timedelta(days=window_days), "until": at,
                "cap": cap}))
    except Exception:      # noqa: BLE001 — an unreadable claim store is no chains, never a 500
        _log.warning("could not read dependency claims for org=%s", org_id, exc_info=True)
        return ()

    fixed = dict(resolutions or {})
    claims: list[DependencyClaim] = []
    for row in rows:
        entries = row.dependencies if isinstance(row.dependencies, list) else []
        for entry in entries:
            claim = _claim_of(entry, event_id=row.event_id, occurred_at=row.occurred_at,
                              resolutions=fixed)
            if claim is not None:
                claims.append(claim)
    return tuple(claims)


def graph_endpoint_resolver(conn, *, org_id: str) -> EndpointResolver:
    """Step 2 — the identity cascade, as one callable the traversal can be handed.

    THE SAME CASCADE AS EVERYTHING ELSE, in the order `context/identity.py` states its alias
    kinds: an email identifies one human; a person's name identifies a person only as well as the
    name is unique; a company name identifies a company only as well as ITS name is; a canon
    title identifies declared company knowledge. Nothing is created and nothing is guessed —
    `resolve_alias` already answers None where two nodes contend for a key, and None here means
    no edge, which is the whole of doc 03's hard rule 1.

    A single memo per resolver instance, because one sweep resolves the same handful of names
    hundreds of times and each miss is a round trip.
    """
    from genios_engine.context.canon import resolve_canon_mention
    from genios_engine.context.identity import (ALIAS_EMAIL, resolve_alias,
                                                resolve_company_mention, resolve_person_name)
    from genios_engine.platform.identity import norm_email

    memo: dict[str, str | None] = {}

    def _resolve(raw: str) -> str | None:
        name = str(raw or "").strip()
        if not name:
            return None
        if name in memo:
            return memo[name]
        found: str | None = None
        email = norm_email(name) if "@" in name else None
        if email:
            found = resolve_alias(conn, org_id=org_id, alias_type=ALIAS_EMAIL, alias_key=email)
        if not found:
            found = resolve_person_name(conn, org_id=org_id, name=name)
        if not found:
            found = resolve_company_mention(conn, org_id=org_id, name=name)
        if not found:
            canon = resolve_canon_mention(conn, org_id=org_id, name=name)
            found = canon[0] if canon else None
        memo[name] = found
        return found

    return _resolve


# =================================================================================================
# THE SWEEP — the wired entry point `context/runner.process_pending` calls
# =================================================================================================

@dataclass(frozen=True, slots=True)
class DependencySweep:
    """What one sweep did, in numbers the drain's return value carries."""

    claims_read: int = 0
    edges: int = 0
    chains: int = 0
    circular_waits: int = 0
    missing_prerequisites: int = 0
    refused_cycles: int = 0
    facts_written: int = 0
    #: Rows whose open version already held exactly this value, so NOTHING was written for them.
    #: Carried beside `facts_written` because the two together are the honest total: a sweep that
    #: re-confirms four hundred unchanged chains has produced no new fact, and a writer that
    #: reported those as writes is how the old amplification hid.
    facts_unchanged: int = 0
    #: Rows this sweep retired because they stopped being true. Soft-closed, never deleted.
    facts_closed: int = 0
    #: This sweep hit `MAX_FACT_WRITES_PER_SWEEP` and left rows unpublished. Surfaced through the
    #: drain's return value: a per-sweep ceiling that is computed and then discarded makes an org
    #: above budget look exactly like an org with nothing to do.
    budget_exhausted: bool = False
    dropped: Mapping[str, int] = field(default_factory=dict)


def _fact_rows(correlation: DependencyCorrelation, *,
               limit: int = MAX_FACT_WRITES_PER_SWEEP
               ) -> tuple[list[tuple[str, str, dict[str, Any]]], bool]:
    """The derived facts one correlation produces: `(node_id, field, value)`, ordered and capped,
    and WHETHER THE CAP CUT ANY OF THEM.

    ONE ROW PER (node, field), never one per chain. A chain-keyed row would be unbounded over
    time — every path a graph has ever held would keep its row while the paths themselves changed
    — and the node-keyed shape is the same version-keyed publish `analytic/anomaly.py` uses, for
    the same stated reason: the append shape is what put this database into read-only once already.

    THE TRUNCATION IS STABLE (sorted by node), AND HERE THAT IS DELIBERATE rather than the defect
    it was in `anomaly._measured_pairs`. The anomaly pass only READS its budget, so rotating its
    queue by staleness costs nothing and buys the tail a verdict. This pass also CLOSES: every
    open row it did not publish is retired, because that is how a resolved blocking disappears. So
    a rotating order here would retire the tail it cut on one sweep and re-open it on the next,
    and a chain would FLAP between "true" and "resolved" every period — worse for a reader than a
    tail that is merely absent, and a fabricated resolution on top. Making the truncation visible
    is what this returns instead; making it fair needs the close to learn which nodes a sweep
    actually CONSIDERED, which is a change to what `correlate_dependencies` reports and is flagged
    rather than smuggled in here.
    """
    rows: list[tuple[str, str, dict[str, Any]]] = []

    by_root: dict[str, list[DependencyChain]] = {}
    circular_by_node: dict[str, list[DependencyChain]] = {}
    for chain in correlation.chains.chains:
        if chain.circular_wait:
            for node in chain.nodes[:-1]:          # the closing node repeats the root
                circular_by_node.setdefault(node, []).append(chain)
        else:
            by_root.setdefault(chain.root, []).append(chain)

    for node in sorted(by_root):
        kept = by_root[node][:MAX_CHAINS_PER_ROOT]
        rows.append((node, FIELD_CHAINS, {
            "chains": [_chain_json(chain) for chain in kept],
            "total": len(by_root[node]), "truncated_by_budget": len(by_root[node]) > len(kept)}))

    for node in sorted(circular_by_node):
        kept = circular_by_node[node][:MAX_CHAINS_PER_ROOT]
        rows.append((node, FIELD_CIRCULAR_WAIT, {
            "cycles": [_chain_json(chain) for chain in kept],
            "total": len(circular_by_node[node])}))

    for node, count in sorted(correlation.chains.blocked_counts.items()):
        rows.append((node, FIELD_BLOCKED_COUNT, {"count": count}))

    absences: dict[str, list[MissingPrerequisite]] = {}
    for found in correlation.missing:
        absences.setdefault(found.subject_node_id, []).append(found)
    for node in sorted(absences):
        rows.append((node, FIELD_MISSING_PREREQUISITE, {"absences": [
            {"blocker_named": found.blocker_named,
             "absence": found.absence.model_dump(mode="json"),
             "evidence": [span.model_dump(mode="json") for span in found.evidence]}
            for found in absences[node]]}))

    return rows[:limit], len(rows) > limit


def _chain_json(chain: DependencyChain) -> dict[str, Any]:
    """A chain in the shape a reader downstream consumes — every hop named, with its receipt.

    The evidence travels WITH the hop rather than with the chain, because the chain has no
    receipt and each hop does; a card that says "legal is waiting on finance" has to be able to
    quote the sentence that established that one blocking, not the sentence that established some
    other blocking in the same path.
    """
    return {
        "chain_id": chain.chain_id, "nodes": list(chain.nodes), "depth": chain.depth,
        "circular_wait": chain.circular_wait, "truncated": chain.truncated,
        "root": chain.root, "terminal": chain.terminal,
        "links": [{"blocker": link.blocker, "blocked": link.blocked,
                   "dependency_type": link.dependency_type,
                   "evidence": [span.model_dump(mode="json") for span in link.evidence]}
                  for link in chain.links],
    }


def _write_facts(conn, *, org_id: str, rows: Sequence[tuple[str, str, dict[str, Any]]],
                 now: datetime) -> tuple[int, int, int]:
    """Publish this sweep's answer and CLOSE everything this module wrote that is no longer true.

    Two halves, and the second one is a correctness rule rather than a tidy-up. A blocking that
    gets RESOLVED has to disappear, or last week's chain sits on the node for ever nagging about
    work that is done — so the rows this sweep did not publish are closed. Closed, never deleted:
    `valid_to` is what the whole graph means by "stopped being true" (`[valid_from, valid_to)`,
    half-open, exactly as every other versioned row here), and a hard delete would make every
    as-of read of last week silently change its answer with no way to recover it.

    **AND THE REOPEN USED TO DO PRECISELY THAT, to this module's own history.** The old upsert's
    conflict clause set `valid_to = null` AND `valid_from = excluded.valid_from`, so a blocking
    stated in March, resolved in April and re-stated in August collapsed into ONE row reading
    `[August, inf)`: the March stint was not superseded, it was ERASED from every as-of read, and
    the paragraph above — this function's own argument against a hard delete — was being defeated
    six lines below where it was written. A reopen is a NEW STINT. `publish_derived_fact` keys the
    id on the PERIOD, so August is a different row from March, the earlier stint keeps its own
    window, and the timeline reads `[March, April) ... [August, inf)` — two true statements rather
    than one lie spanning both.

    `keep` is the ids the publisher RETURNED, never ids rebuilt here. Under period keying an
    unchanged fact keeps the id of the period it was FIRST published in, so a reconstructed id
    would close exactly the rows that are still true.

    Returns `(written, unchanged, closed)`. The middle number is the one the old writer could not
    report: a sweep that re-confirms four hundred unchanged chains now writes nothing at all, and
    counting those as writes is how the amplification stayed invisible in the numbers.
    """
    prefix = f"{VERSION_PREFIX}:"
    written = unchanged = 0
    keep: list[str] = []
    for node_id, field_name, value in rows:
        published = publish_derived_fact(
            conn, org_id=org_id, subject_node_id=node_id, field=field_name, value=value,
            eval_time=now, value_type=VALUE_TYPE,
            # Per FIELD, never per module — see `_FIELD_SCOPE`. A chain republishes somebody's
            # sentence; a count of blocked items does not.
            visibility_scope=_FIELD_SCOPE[field_name],
            version_prefix=prefix, fact_id=f"f_dep:{field_name}:{node_id}")
        keep.append(published.version_id)
        if published.wrote:
            written += 1
        else:
            unchanged += 1

    closed = close_derived_facts(conn, org_id=org_id, version_prefix=prefix, keep=keep,
                                 eval_time=now)
    return written, unchanged, closed


def refresh_dependency_chains(store, org_id: str, *, eval_time: datetime,
                              window_days: int = DEPENDENCY_WINDOW_DAYS,
                              cap: int = MAX_CLAIMS_PER_SWEEP,
                              max_depth: int = MAX_DEPENDENCY_DEPTH,
                              resolutions: Mapping[tuple[str, str], datetime] | None = None,
                              ) -> DependencySweep:
    """BLG-05, end to end, for one org. Called from `context/runner.process_pending`.

    ON THE DRAIN rather than on a schedule, for the reason the whole layer prefers: the Celery
    broker is a quota-limited Upstash instance, and the drain is the only thing that knows an org
    is active. Unconditional within it, like the sampler and the trend above it — a chain changes
    because a blocking was RESOLVED as often as because one was stated, and gating this on "did
    new mail arrive" would freeze a resolved chain in place on exactly the quiet org whose stuck
    work is worth surfacing.

    `eval_time` is a parameter with no fallback clock: it is the end of the read window, the
    `valid_from` of every row this sweep OPENS and the `valid_to` of every row it closes, so a
    sweep replayed at one instant produces byte-identical facts. It never moves the `valid_from`
    of a row that already exists — see `_write_facts`, which is where that used to happen.
    """
    at = require_aware(eval_time, "eval_time")
    claims = read_dependency_claims(store.engine, org_id, eval_time=at, window_days=window_days,
                                    cap=cap, resolutions=resolutions)
    if not claims:
        # Still CLOSE our own rows: "no claims in the window" is a real answer, and leaving last
        # sweep's chains open would make a tenant who resolved everything look permanently stuck.
        with store.engine.begin() as conn:
            _, _, closed = _write_facts(conn, org_id=org_id, rows=(), now=at)
        return DependencySweep(facts_closed=closed)

    with store.engine.connect() as conn:
        correlation = correlate_dependencies(
            claims, graph_endpoint_resolver(conn, org_id=org_id),
            coverage_basis=(f"{EXTRACTION_TABLE}:{org_id}",), max_depth=max_depth)

    rows, exhausted = _fact_rows(correlation)
    with store.engine.begin() as conn:
        written, unchanged, closed = _write_facts(conn, org_id=org_id, rows=rows, now=at)

    return DependencySweep(
        claims_read=len(claims), edges=len(correlation.edges),
        chains=len(correlation.chains.chains), circular_waits=len(correlation.circular),
        missing_prerequisites=len(correlation.missing),
        refused_cycles=len(correlation.chains.refused_cycles), facts_written=written,
        facts_unchanged=unchanged, facts_closed=closed, budget_exhausted=exhausted,
        dropped=dict(correlation.material.dropped_by_reason))


__all__ = ["DEPENDENCY_WINDOW_DAYS", "EXTRACTION_TABLE", "FACT_PREFIX", "FIELD_BLOCKED_COUNT",
           "FIELD_CHAINS", "FIELD_CIRCULAR_WAIT", "FIELD_MISSING_PREREQUISITE",
           "MAX_CHAINS_PER_ROOT", "MAX_CLAIMS_PER_SWEEP", "MAX_FACT_WRITES_PER_SWEEP",
           "MISSING_PREREQUISITE_FACT", "VALUE_TYPE", "VERSION_PREFIX", "ChainSet",
           "DependencyClaim", "DependencyCorrelation", "DependencySweep", "DroppedClaim",
           "DropReason", "EndpointResolver", "Materialization", "MissingPrerequisite",
           "RefusedCycle", "blocked_counts",
           "build_chains", "chain_id_for", "correlate_dependencies", "graph_endpoint_resolver",
           "materialize_edges", "read_dependency_claims", "refresh_dependency_chains",
           "unblocked_roots"]
