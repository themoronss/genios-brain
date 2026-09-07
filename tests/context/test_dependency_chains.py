"""L2.3.8 · BLG-05 — the dependency chain suite.

Doc 03's premise, and the reason every row below is written the way it is: **a false chain is
worse than a missing one.** A phantom blocker nags a real person about work that does not exist,
with the authority of a system that says it checked. So the assertions here are mostly refusals —
what the traversal declines to say, and whether it says WHY instead of saying nothing.

Everything is driven through the injected resolver (doc 03 hard rule 6: the graph read is
injected, the algorithm takes nodes and edges), which is what lets the whole traversal be tested
against dicts. The two `pg`-marked tests at the bottom are the other half of that seam: a unit
proven against a dict and reached by nothing is the failure Layer 1 already paid for, so the last
tests drive `context/runner.process_pending` — the real drain — and assert the rows land.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import ValidationError

from genios_engine.contracts.dependency import (MAX_DEPENDENCY_DEPTH, DependencyChain,
                                                DependencyLink)
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import Dependency
from genios_engine.contracts.quality import AbsenceType
from genios_engine.context.correlation_dependency import (FIELD_BLOCKED_COUNT, FIELD_CHAINS,
                                                          MISSING_PREREQUISITE_FACT,
                                                          VERSION_PREFIX, DependencyClaim,
                                                          DropReason, blocked_counts,
                                                          build_chains, chain_id_for,
                                                          correlate_dependencies,
                                                          materialize_edges, unblocked_roots)

# =================================================================================================
# BUILDERS — one sentence, one claim, no clock
# =================================================================================================

#: The sentence every default receipt points into. Real text with real offsets, because
#: `EvidenceSpan` checks that the quote's length matches the range it names, and a builder that
#: faked that would make every link in this file cite a region that does not exist.
_SENTENCE = "Legal is waiting on Finance before the renewal can be countersigned."


def span(*, ref: str = "prepared_content:evt_dep_1", quote: str = _SENTENCE) -> EvidenceSpan:
    return EvidenceSpan(source_ref=ref, quote=quote, start_offset=0, end_offset=len(quote),
                        verified=True)


def claim(blocker: str, blocked: str, *, kind: str = "approval", event: str = "evt_dep_1",
          quote: str = _SENTENCE, occurred_at=None, resolved_at=None) -> DependencyClaim:
    """One `Dependency` L1 could really have published, wrapped with its provenance.

    Built through the CONTRACT — `Dependency` first, `from_extraction` second — so a claim this
    suite asserts on is a claim L1's own publishing seam would have accepted. A local dataclass
    that skipped those validators would let the suite go green against a shape L1 cannot emit.
    """
    return DependencyClaim.from_extraction(
        Dependency(blocker=blocker, blocked=blocked, dependency_type=kind,
                   evidence=[span(ref=f"prepared_content:{event}", quote=quote)],
                   confidence_bp=7000),
        event_id=event, occurred_at=occurred_at, resolved_at=resolved_at)


def resolver(known: dict[str, str] | None = None, *, identity: bool = True):
    """The injected identity cascade, as a dict.

    `identity=True` maps any name to itself so a test about traversal does not have to declare a
    resolution table; a test about RESOLUTION passes `identity=False` and states exactly which
    names the graph knows, so an unresolved endpoint is a thing somebody deliberately typed.
    """
    table = dict(known or {})

    def _resolve(raw: str) -> str | None:
        if raw in table:
            return table[raw]
        return raw if identity else None

    return _resolve


def path_claims(nodes: list[str], **kwargs) -> list[DependencyClaim]:
    """A→B→C… as claims, one per hop, each with its own event so the receipts differ."""
    return [claim(nodes[i], nodes[i + 1], event=f"evt_hop_{i}", **kwargs)
            for i in range(len(nodes) - 1)]


def only_chain(claims, **kwargs) -> DependencyChain:
    result = correlate_dependencies(claims, resolver(), **kwargs)
    assert len(result.chains.chains) == 1, [c.nodes for c in result.chains.chains]
    return result.chains.chains[0]


# =================================================================================================
# A SIMPLE CHAIN — A blocks B blocks C
# =================================================================================================

def test_a_simple_chain_is_one_chain_of_three_nodes() -> None:
    """Doc 03's first acceptance row. Three nodes, two hops, one finding — not two findings for
    the two claims, and not three for the prefixes."""
    chain = only_chain(path_claims(["finance", "legal", "renewal"]))
    assert chain.nodes == ("finance", "legal", "renewal")
    assert chain.depth == 2
    assert chain.root == "finance"
    assert chain.terminal == "renewal"
    assert chain.circular_wait is False
    assert chain.truncated is False


def test_every_hop_carries_the_sentence_it_was_read_from() -> None:
    """The chain has no receipt; each hop does. A card saying "legal is waiting on finance" has
    to quote the sentence that established THAT blocking, not some other hop's."""
    chain = only_chain(path_claims(["finance", "legal", "renewal"]))
    assert [link.evidence[0].source_ref for link in chain.links] == [
        "prepared_content:evt_hop_0", "prepared_content:evt_hop_1"]
    assert all(link.evidence for link in chain.links)


def test_a_prefix_of_a_chain_is_not_emitted_as_its_own_finding() -> None:
    """Maximal paths only. A→B and A→B→C as two chains puts the same blocking on a card twice
    with two different terminal nodes, and a reader cannot tell which one to act on."""
    result = correlate_dependencies(path_claims(["a", "b", "c", "d"]), resolver())
    assert [chain.nodes for chain in result.chains.chains] == [("a", "b", "c", "d")]


def test_a_fork_produces_one_chain_per_branch() -> None:
    """One blocker holding up two independent things is two findings, not one — they are escalated
    to two different people and resolved by two different acts."""
    result = correlate_dependencies(
        [claim("finance", "legal", event="e1"), claim("finance", "ops", event="e2"),
         claim("legal", "renewal", event="e3")], resolver())
    assert {chain.nodes for chain in result.chains.chains} == {
        ("finance", "legal", "renewal"), ("finance", "ops")}


def test_the_unblocked_root_is_the_only_starting_point() -> None:
    """Step 3 starts at nodes that block something and wait on nothing. Anything else as a start
    would emit the same path once per node in it."""
    edges = materialize_edges(path_claims(["a", "b", "c"]), resolver()).edges
    assert unblocked_roots(edges) == ("a",)


# =================================================================================================
# THE DEPTH CAP — exactly at it, and past it
# =================================================================================================

def test_a_chain_at_exactly_the_cap_is_whole_and_says_so() -> None:
    """`MAX_DEPENDENCY_DEPTH` EDGES — the contract's unit, and a six-edge chain carries seven
    nodes. A chain that merely happens to be as long as the cap is not truncated, and saying it
    was would tell a reader there is more when the chain has ended."""
    nodes = [f"n{i}" for i in range(MAX_DEPENDENCY_DEPTH + 1)]
    chain = only_chain(path_claims(nodes))
    assert chain.depth == MAX_DEPENDENCY_DEPTH
    assert len(chain.nodes) == MAX_DEPENDENCY_DEPTH + 1
    assert chain.truncated is False


def test_a_chain_past_the_cap_stops_at_the_cap_and_is_flagged() -> None:
    """Doc 03's reverse prompt asks for exactly this: a 10-deep chain that stops at 6 and flags.
    `truncated` is how the traversal says "I stopped, this is not the whole story" — the
    alternative is a six-long chain that silently claims to be the end of the line."""
    nodes = [f"n{i}" for i in range(11)]
    chain = only_chain(path_claims(nodes))
    assert chain.depth == MAX_DEPENDENCY_DEPTH
    assert chain.truncated is True
    assert chain.nodes == tuple(nodes[:MAX_DEPENDENCY_DEPTH + 1])


def test_the_contract_refuses_a_chain_longer_than_the_cap() -> None:
    """The builder and the contract must agree on the UNIT. If the traversal counted nodes and
    the contract counted edges, a seven-node chain would be legal on one side and a
    `ValidationError` on the other — on a real tenant, in a sweep, months later."""
    links = [DependencyLink(blocker=f"n{i}", blocked=f"n{i + 1}", dependency_type="approval",
                            evidence=(span(),))
             for i in range(MAX_DEPENDENCY_DEPTH + 1)]
    with pytest.raises(ValidationError, match="at most 6 edges"):
        DependencyChain(chain_id="dep_toolong", links=tuple(links))


@pytest.mark.parametrize("cap", [0, MAX_DEPENDENCY_DEPTH + 1])
def test_an_illegal_depth_cap_is_refused_at_the_call(cap: int) -> None:
    """Asking for a chain the contract cannot hold only moves the failure to the write."""
    with pytest.raises(ValueError, match="max_depth"):
        build_chains((), max_depth=cap)


# =================================================================================================
# A GENUINE CIRCULAR WAIT — the single most actionable thing this layer finds
# =================================================================================================

def test_a_two_node_circular_wait_is_emitted_not_dropped() -> None:
    """"A is waiting on B and B on A" is intelligence, not an error: nobody is blocked by work,
    everybody is blocked by each other, and nothing moves until someone is told."""
    result = correlate_dependencies(
        [claim("legal", "finance", event="e1"), claim("finance", "legal", event="e2")],
        resolver())
    assert len(result.circular) == 1
    cycle = result.circular[0]
    assert cycle.circular_wait is True
    assert cycle.nodes[0] == cycle.nodes[-1]
    assert set(cycle.nodes) == {"finance", "legal"}


def test_a_three_node_circular_wait_closes_on_its_own_root() -> None:
    result = correlate_dependencies(path_claims(["a", "b", "c"]) + [claim("c", "a", event="e4")],
                                    resolver())
    assert [chain.nodes for chain in result.circular] == [("a", "b", "c", "a")]
    assert result.chains.chains == result.circular       # a pure cycle has no acyclic chain


def test_a_circular_wait_is_reported_once_not_once_per_member() -> None:
    """Canonicalised by its smallest member. Three rotations of one stuck triangle would tell a
    founder about the same deadlock three times, and each telling would look like a new finding."""
    result = correlate_dependencies(path_claims(["a", "b", "c"]) + [claim("c", "a", event="e4")],
                                    resolver())
    assert len(result.circular) == 1


def test_a_chain_that_closes_and_does_not_say_so_is_refused_by_the_contract() -> None:
    """The flag is checked against the links in BOTH directions. A cycle rendered as a sequence
    tells somebody to go unblock the person who is waiting on them."""
    links = (DependencyLink(blocker="a", blocked="b", dependency_type="approval",
                            evidence=(span(),)),
             DependencyLink(blocker="b", blocked="a", dependency_type="approval",
                            evidence=(span(),)))
    with pytest.raises(ValidationError, match="circular_wait"):
        DependencyChain(chain_id="dep_unflagged", links=links)
    with pytest.raises(ValidationError, match="does not close"):
        DependencyChain(chain_id="dep_overclaimed", links=links[:1], circular_wait=True)


def test_a_cycle_deeper_than_the_cap_is_refused_rather_than_truncated() -> None:
    """A truncated cycle rendered as a chain is the one output that must never be produced, so a
    cycle that will not fit inside the cap comes back as a REFUSAL that names its members and
    implies no order — doc 03's own reading: deeper than the cap is almost always an
    identity-resolution error, so flag it rather than traverse further."""
    nodes = [f"n{i}" for i in range(MAX_DEPENDENCY_DEPTH + 2)]
    claims = path_claims(nodes) + [claim(nodes[-1], nodes[0], event="close")]
    result = correlate_dependencies(claims, resolver())
    assert result.circular == ()
    assert len(result.chains.refused_cycles) == 1
    assert set(result.chains.refused_cycles[0].members) == set(nodes)
    assert result.chains.chains == ()                   # nothing is rendered as a sequence


def test_an_approach_path_into_a_downstream_cycle_ends_without_claiming_the_cap() -> None:
    """X→A, A→B, B→A. The approach path ends because the graph loops, not because the cap was
    hit, and `truncated` means the cap — conflating them would make an ordinary two-hop finding
    read as "there is more of this"."""
    result = correlate_dependencies(
        [claim("x", "a", event="e0"), claim("a", "b", event="e1"), claim("b", "a", event="e2")],
        resolver())
    acyclic = [chain for chain in result.chains.chains if not chain.circular_wait]
    assert [chain.nodes for chain in acyclic] == [("x", "a", "b")]
    assert acyclic[0].truncated is False
    assert [chain.nodes for chain in result.circular] == [("a", "b", "a")]


# =================================================================================================
# LOOKS CIRCULAR, IS NOT — the same node twice at different times
# =================================================================================================

def test_the_same_blocking_stated_twice_is_one_edge_not_a_cycle() -> None:
    """Two messages a month apart both saying "legal is waiting on finance" are one edge observed
    twice. Treated as two claims about two moments they are still one direction — and the chain
    carries both receipts, because both sentences are worth showing."""
    early = claim("finance", "legal", event="evt_may")
    late = claim("finance", "legal", event="evt_august", quote="Still waiting on Finance here.")
    result = correlate_dependencies([early, late], resolver())
    assert len(result.edges) == 1
    assert len(result.edges[0].evidence) == 2
    assert result.circular == ()


def test_an_old_resolved_blocking_in_the_other_direction_is_not_a_circular_wait() -> None:
    """The trap this row exists for: A→B is live and B→A was satisfied months ago. The two nodes
    appear on both sides of a blocking, which LOOKS like a deadlock and is not one — and calling
    it one would tell two people who are not stuck that they are stuck with each other."""
    from datetime import datetime, timezone

    live = claim("finance", "legal", event="evt_now")
    old = claim("legal", "finance", event="evt_may",
                resolved_at=datetime(2026, 1, 5, tzinfo=timezone.utc))
    result = correlate_dependencies([live, old], resolver())
    assert result.circular == ()
    assert [chain.nodes for chain in result.chains.chains] == [("finance", "legal")]
    assert result.material.dropped_by_reason == {DropReason.RESOLVED.value: 1}


def test_a_resolved_blocking_restated_as_live_is_live_again() -> None:
    """Earliest-wins and latest-wins are both wrong. A group is live if ANY of its claims is
    unresolved: a satisfied blocking that somebody restates has come back, and a resolved
    restatement of a stale claim is still done."""
    from datetime import datetime, timezone

    old = claim("finance", "legal", event="evt_may",
                resolved_at=datetime(2026, 1, 5, tzinfo=timezone.utc))
    again = claim("finance", "legal", event="evt_august")
    result = correlate_dependencies([old, again], resolver())
    assert len(result.edges) == 1
    assert result.edges[0].resolved is False


def test_a_fully_resolved_dependency_drops_out_of_the_chain() -> None:
    """Doc 03's acceptance row, and its mitigation for "nagging about done work": chains read
    only unresolved edges."""
    from datetime import datetime, timezone

    claims = path_claims(["a", "b", "c"])
    claims[1] = claim("b", "c", event="evt_done",
                      resolved_at=datetime(2026, 2, 1, tzinfo=timezone.utc))
    result = correlate_dependencies(claims, resolver())
    assert [chain.nodes for chain in result.chains.chains] == [("a", "b")]


def test_the_contract_refuses_a_resolved_link_inside_a_chain() -> None:
    """Enforced at the seam as well as in the traversal, because the traversal is not the only
    thing that will ever build one of these."""
    with pytest.raises(ValidationError, match="no resolved link"):
        DependencyChain(chain_id="dep_stale", links=(
            DependencyLink(blocker="a", blocked="b", dependency_type="approval",
                           evidence=(span(),), resolved=True),))


def test_a_node_revisited_on_two_different_branches_is_not_a_cycle() -> None:
    """A→B→D and A→C→D. D appears twice across the findings and nothing loops; a visited-set that
    was global rather than per-path would silently drop the second branch."""
    result = correlate_dependencies(
        [claim("a", "b", event="e1"), claim("a", "c", event="e2"),
         claim("b", "d", event="e3"), claim("c", "d", event="e4")], resolver())
    assert {chain.nodes for chain in result.chains.chains} == {("a", "b", "d"), ("a", "c", "d")}
    assert result.circular == ()


# =================================================================================================
# A BROKEN CHAIN IS REFUSED, NEVER SILENTLY TRUNCATED
# =================================================================================================

def test_an_unresolved_blocker_produces_no_edge_and_no_joined_chain() -> None:
    """Doc 03 hard rule 1. A→B is real, "Procurement"→C cannot be resolved: the answer is the
    A→B chain and a stated absence — NEVER A→B→C bridged across the gap, which is a causal claim
    nobody made."""
    claims = [claim("alice@acme.io", "bob@acme.io", event="e1"),
              claim("Procurement", "bob@acme.io", event="e2")]
    result = correlate_dependencies(
        claims, resolver({"alice@acme.io": "node_alice", "bob@acme.io": "node_bob"},
                         identity=False), coverage_basis=("l1_extraction_results:org_x",))
    assert [chain.nodes for chain in result.chains.chains] == [("node_alice", "node_bob")]
    assert result.material.dropped_by_reason == {DropReason.UNRESOLVED_BLOCKER.value: 1}


def test_an_unjoined_pair_rendered_as_a_sequence_is_refused_by_the_contract() -> None:
    """Contiguity, checked. Two unrelated pairs typecheck perfectly as a "chain" and read as a
    causal sequence, which is the exact shape a silent truncation would produce."""
    with pytest.raises(ValidationError, match="links must join"):
        DependencyChain(chain_id="dep_broken", links=(
            DependencyLink(blocker="a", blocked="b", dependency_type="approval",
                           evidence=(span(),)),
            DependencyLink(blocker="c", blocked="d", dependency_type="approval",
                           evidence=(span(),))))


def test_a_missing_prerequisite_names_who_is_waiting_and_on_what() -> None:
    """Step 5. The finding is about the party we CAN name — a blocker we cannot resolve is never
    invented into a node, and the raw name plus the sentence travel beside the typed absence so a
    card can say what was asked for."""
    result = correlate_dependencies(
        [claim("Procurement", "bob@acme.io", event="e2")],
        resolver({"bob@acme.io": "node_bob"}, identity=False),
        coverage_basis=("l1_extraction_results:org_x",))
    assert len(result.missing) == 1
    found = result.missing[0]
    assert found.subject_node_id == "node_bob"
    assert found.blocker_named == "Procurement"
    assert found.absence.expected_fact == MISSING_PREREQUISITE_FACT
    assert found.absence.absence_type is AbsenceType.GENUINELY_ABSENT
    assert found.absence.licenses_negative_inference is True
    assert found.evidence and found.evidence[0].quote


def test_without_a_declared_coverage_basis_the_absence_licenses_nothing() -> None:
    """"We could not find the blocker" is not "the blocker does not exist". Only a caller that
    states what it searched may make the second claim; a caller that states nothing gets
    `UNKNOWABLE`, which licenses no negative inference at all."""
    result = correlate_dependencies(
        [claim("Procurement", "bob@acme.io", event="e2")],
        resolver({"bob@acme.io": "node_bob"}, identity=False))
    assert result.missing[0].absence.absence_type is AbsenceType.UNKNOWABLE
    assert result.missing[0].absence.licenses_negative_inference is False


def test_an_unresolved_waiting_end_is_dropped_without_a_finding() -> None:
    """No subject, no statement. We would be asserting an absence ON a node we cannot name."""
    result = correlate_dependencies(
        [claim("alice@acme.io", "whoever", event="e1")],
        resolver({"alice@acme.io": "node_alice"}, identity=False),
        coverage_basis=("l1_extraction_results:org_x",))
    assert result.edges == ()
    assert result.missing == ()
    assert result.material.dropped_by_reason == {DropReason.UNRESOLVED_BLOCKED.value: 1}


def test_two_spellings_of_one_party_become_one_node_and_one_chain() -> None:
    """Step 2's whole point: "Finance" and "finance@acme.ai" are one node, so a chain stated
    across two messages in two vocabularies is one chain rather than two fragments."""
    resolve = resolver({"Finance": "node_finance", "finance@acme.ai": "node_finance",
                        "Legal": "node_legal", "renewal": "node_renewal"}, identity=False)
    result = correlate_dependencies(
        [claim("Finance", "Legal", event="e1"), claim("finance@acme.ai", "renewal", event="e2")],
        resolve)
    assert {chain.nodes for chain in result.chains.chains} == {
        ("node_finance", "node_legal"), ("node_finance", "node_renewal")}


def test_a_self_blocking_claim_is_dropped_not_traversed() -> None:
    """Both ends resolving to one node is a one-node cycle: it makes every traversal
    non-terminating and looks perfectly ordinary in a single row."""
    result = correlate_dependencies(
        [claim("Finance", "finance@acme.ai", event="e1")],
        resolver({"Finance": "node_finance", "finance@acme.ai": "node_finance"}, identity=False))
    assert result.edges == ()
    assert result.material.dropped_by_reason == {DropReason.SELF_LOOP.value: 1}


def test_two_blocking_kinds_between_the_same_pair_stay_two_edges() -> None:
    """"waiting for approval" and "waiting for information" have two remedies and two people to
    escalate to. Collapsing them on the pair alone would lose which one to act on."""
    result = correlate_dependencies(
        [claim("finance", "legal", kind="approval", event="e1"),
         claim("finance", "legal", kind="information", event="e2")], resolver())
    assert {edge.dependency_type for edge in result.edges} == {"approval", "information"}


# =================================================================================================
# STEP 6 — blocked_count, the derived fact L2.7.4 modifier 3d consumes
# =================================================================================================

def test_blocked_count_is_transitive_because_the_cost_is_the_blocked_work() -> None:
    """A blocks B, B blocks C and D. The cost of A being stuck is three pieces of work, not one —
    direct degree would rank a node holding up a whole tree below one holding up two leaves."""
    counts = blocked_counts(materialize_edges(
        [claim("a", "b", event="e1"), claim("b", "c", event="e2"), claim("b", "d", event="e3")],
        resolver()).edges)
    assert counts == {"a": 3, "b": 2}


def test_a_node_in_a_cycle_does_not_count_itself() -> None:
    """It is stuck, not waiting on its own output."""
    counts = blocked_counts(materialize_edges(
        path_claims(["a", "b", "c"]) + [claim("c", "a", event="e4")], resolver()).edges)
    assert counts == {"a": 2, "b": 2, "c": 2}


def test_blocked_count_stops_at_the_same_depth_cap_as_the_chains() -> None:
    """Past the cap the reachable set is describing an identity defect rather than the business,
    and the two numbers on one card must not disagree about how far the system looked."""
    counts = blocked_counts(materialize_edges(
        path_claims([f"n{i}" for i in range(11)]), resolver()).edges)
    assert counts["n0"] == MAX_DEPENDENCY_DEPTH


def test_a_node_that_blocks_nothing_carries_no_count() -> None:
    """A zero written as a row is a claim; an absent row is the absence of one."""
    counts = blocked_counts(materialize_edges([claim("a", "b", event="e1")], resolver()).edges)
    assert "b" not in counts


# =================================================================================================
# DETERMINISM — the property that makes a replay an overwrite rather than a second answer
# =================================================================================================

def test_the_same_claims_in_a_different_order_produce_identical_chains() -> None:
    claims = path_claims(["a", "b", "c"]) + [claim("a", "x", event="e9")]
    forward = correlate_dependencies(claims, resolver())
    backward = correlate_dependencies(list(reversed(claims)), resolver())
    assert ([c.chain_id for c in forward.chains.chains]
            == [c.chain_id for c in backward.chains.chains])
    assert [c.nodes for c in forward.chains.chains] == [c.nodes for c in backward.chains.chains]


def test_a_chain_id_is_a_content_address_of_its_path() -> None:
    """Not a uuid: chains are stored, compared and superseded independently, and an id that moved
    every sweep would make a chain supersede itself for ever. The blocking KIND is in the digest
    because two kinds between one pair are two findings."""
    links = materialize_edges(path_claims(["a", "b"]), resolver()).edges
    other = materialize_edges([claim("a", "b", kind="information", event="e1")], resolver()).edges
    assert chain_id_for(links) == chain_id_for(links)
    assert chain_id_for(links) != chain_id_for(other)
    assert chain_id_for(links).startswith("dep_")


def test_no_clock_and_no_model_are_reachable_from_this_module() -> None:
    """Doc 03's group gate greps `context/correlation*.py` for a model client. The clock check is
    the same rule stated for time: `eval_time` is a parameter, so a sweep replayed at one instant
    writes byte-identical rows."""
    from pathlib import Path

    from genios_engine.context import correlation_dependency

    source = Path(correlation_dependency.__file__).read_text()
    for forbidden in ("LLMClient", "anthropic", "datetime.now(", "utcnow("):
        assert forbidden not in source, forbidden
    assert "float(" not in source


# =================================================================================================
# THE WIRING — a unit a real request path reaches, driven through that path
# =================================================================================================

def test_the_drain_calls_the_dependency_pass() -> None:
    """A unit tested against dicts and called by nothing is the failure Layer 1 already paid for
    once. This is the cheap half of the guard; the `pg` test below is the real one."""
    import inspect

    from genios_engine.context.runner import process_pending

    source = inspect.getsource(process_pending)
    assert "refresh_dependency_chains(" in source
    assert "eval_time=sweep_at" in source


@pytest.mark.pg
def test_the_drain_writes_dependency_facts_for_a_real_orgs_claims(pg_store, org_id, eval_time):
    """THE WIRING TEST. Seed what L1 really files — a `source_events` row and its
    `l1_extraction_results` output carrying `dependencies[]` — plus the person nodes and aliases
    the identity cascade resolves through, then run the REAL drain and read the graph back.

    Nothing here constructs the correlator. `process_pending` is the entry point the sync calls,
    and if the pass were removed from it this test would go red while every unit test above
    stayed green — which is the only arrangement that proves a chain reaches a tenant.
    """
    from sqlalchemy import text

    from genios_engine.context.identity import register_node_identity
    from genios_engine.context.runner import process_pending

    people = {"finance@acme.io": "node_dep_finance", "legal@acme.io": "node_dep_legal",
              "ops@acme.io": "node_dep_ops"}
    with pg_store.engine.begin() as conn:
        _reset_dependency_fixture(conn, org_id, people)
        for email, node_id in people.items():
            conn.execute(text(
                "insert into graph_nodes (node_id, org_id, node_type, canonical_key, "
                "display_name, valid_from) values (:n, :o, 'person', :k, :d, now())"),
                {"n": node_id, "o": org_id, "k": email, "d": email.split("@")[0]})
            register_node_identity(conn, org_id=org_id, node_id=node_id, node_type="person",
                                   canonical_key=email, display_name=email.split("@")[0])
        _seed_claim(conn, org_id, event="evt_dep_chain_1",
                    occurred_at=eval_time - timedelta(days=3),
                    pairs=[("finance@acme.io", "legal@acme.io"),
                           ("legal@acme.io", "ops@acme.io")])

    result = process_pending(org_id=org_id, store=pg_store, llm=None, crypto_key="k" * 32,
                             eval_time=eval_time)
    assert result["dependency_facts"] >= 1

    with pg_store.engine.connect() as conn:
        rows = dict(conn.execute(text(
            "select subject_node_id || '|' || field, value from graph_facts "
            "where org_id = :o and left(fact_version_id, :n) = :p and valid_to is null"),
            {"o": org_id, "n": len(VERSION_PREFIX) + 1, "p": f"{VERSION_PREFIX}:"}).all())

    chain_fact = rows[f"node_dep_finance|{FIELD_CHAINS}"]
    assert chain_fact["chains"][0]["nodes"] == ["node_dep_finance", "node_dep_legal",
                                                "node_dep_ops"]
    assert chain_fact["chains"][0]["links"][0]["evidence"], "a hop with no receipt is a guess"
    assert rows[f"node_dep_finance|{FIELD_BLOCKED_COUNT}"]["count"] == 2
    assert f"node_dep_ops|{FIELD_BLOCKED_COUNT}" not in rows


@pytest.mark.pg
def test_a_resolved_blocking_disappears_from_the_graph_on_the_next_drain(pg_store, org_id,
                                                                        eval_time):
    """The stale-fact half. A chain that stops being true must STOP BEING READ — a version-keyed
    upsert alone leaves last sweep's chain open on the node, nagging about work that is done —
    and it must be CLOSED rather than deleted, because an as-of read of last week has to keep its
    answer. Both halves are asserted: no live row, and the closed row still there.
    """
    from sqlalchemy import text

    from genios_engine.context.identity import register_node_identity
    from genios_engine.context.runner import process_pending

    people = {"a@acme.io": "node_dep_a", "b@acme.io": "node_dep_b"}
    with pg_store.engine.begin() as conn:
        _reset_dependency_fixture(conn, org_id, people)
        for email, node_id in people.items():
            conn.execute(text(
                "insert into graph_nodes (node_id, org_id, node_type, canonical_key, "
                "display_name, valid_from) values (:n, :o, 'person', :k, :d, now())"),
                {"n": node_id, "o": org_id, "k": email, "d": email.split("@")[0]})
            register_node_identity(conn, org_id=org_id, node_id=node_id, node_type="person",
                                   canonical_key=email, display_name=email.split("@")[0])
        _seed_claim(conn, org_id, event="evt_dep_live", occurred_at=eval_time - timedelta(days=2),
                    pairs=[("a@acme.io", "b@acme.io")])

    process_pending(org_id=org_id, store=pg_store, llm=None, crypto_key="k" * 32,
                    eval_time=eval_time)
    assert _live_dependency_fields(pg_store, org_id)

    with pg_store.engine.begin() as conn:
        conn.execute(text(
            "update l1_extraction_results set output = jsonb_set(output, '{dependencies,0,"
            "resolved_at}', to_jsonb(cast(:at as text))) where org_id = :o "
            "and event_id = 'evt_dep_live'"),
            {"o": org_id, "at": (eval_time - timedelta(days=1)).isoformat()})

    process_pending(org_id=org_id, store=pg_store, llm=None, crypto_key="k" * 32,
                    eval_time=eval_time)
    assert not _live_dependency_fields(pg_store, org_id)

    with pg_store.engine.connect() as conn:
        closed = conn.execute(text(
            "select count(*) from graph_facts where org_id = :o "
            "and left(fact_version_id, :n) = :p and valid_to is not null"),
            {"o": org_id, "n": len(VERSION_PREFIX) + 1, "p": f"{VERSION_PREFIX}:"}).scalar()
    assert closed >= 1, "a fact that stopped being true is closed, never erased"


# =================================================================================================
# pg helpers — seeding what L1 really files, not a convenient approximation
# =================================================================================================

def _reset_dependency_fixture(conn, org_id: str, people: dict[str, str]) -> None:
    """Clear only what these two tests seed. Scoped by the ids they own so a shared scratch
    database is not a shared fixture."""
    from sqlalchemy import text

    conn.execute(text("delete from l1_extraction_results where org_id = :o and event_id like "
                      "'evt_dep_%'"), {"o": org_id})
    conn.execute(text("delete from source_events where org_id = :o and event_id like 'evt_dep_%'"),
                 {"o": org_id})
    conn.execute(text("delete from graph_facts where org_id = :o and subject_node_id = any("
                      "cast(:n as text[]))"), {"o": org_id, "n": list(people.values())})
    conn.execute(text("delete from graph_aliases where org_id = :o and node_id = any("
                      "cast(:n as text[]))"), {"o": org_id, "n": list(people.values())})
    conn.execute(text("delete from graph_nodes where org_id = :o and node_id = any("
                      "cast(:n as text[]))"), {"o": org_id, "n": list(people.values())})


def _seed_claim(conn, org_id: str, *, event: str, occurred_at, pairs) -> None:
    """One landed event and the extraction L1 filed for it, in the real tables and real shapes."""
    import json

    from sqlalchemy import text

    conn.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        "source_object_id, dedup_key, actor, occurred_at) values "
        "(:e, :o, 'conn_dep', 'gmail', 'email_message', :e, :e, '{}'::jsonb, :at)"),
        {"e": event, "o": org_id, "at": occurred_at})
    quote = _SENTENCE
    dependencies = [{"blocker": blocker, "blocked": blocked, "dependency_type": "approval",
                     "confidence_bp": 7000,
                     "evidence": [{"source_ref": f"prepared_content:{event}", "quote": quote,
                                   "start_offset": 0, "end_offset": len(quote),
                                   "verified": True}]}
                    for blocker, blocked in pairs]
    conn.execute(text(
        "insert into l1_extraction_results (processing_key, org_id, event_id, output) "
        "values (:k, :o, :e, cast(:out as jsonb))"),
        {"k": f"pk_{event}", "o": org_id, "e": event,
         "out": json.dumps({"dependencies": dependencies})})


def _live_dependency_fields(store, org_id: str) -> set[str]:
    from sqlalchemy import text

    with store.engine.connect() as conn:
        return {row[0] for row in conn.execute(text(
            "select field from graph_facts where org_id = :o and left(fact_version_id, :n) = :p "
            "and valid_to is null"),
            {"o": org_id, "n": len(VERSION_PREFIX) + 1, "p": f"{VERSION_PREFIX}:"}).all()}
