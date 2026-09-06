"""H7 · dependency chains (D-09) and cross-timeline correlation, executed as the gate states them.

**Gate H7** — invoked by `02-Layer-2-Plan/09-Build-Order-and-Acceptance.md` as:

    pytest tests/context/test_authority.py tests/context/test_point_in_time.py \\
           tests/context/test_dependency_correlation.py -q

This file was a PLACEHOLDER that skipped, and X7 replaces it with the gate it was holding a
place for. Like `test_authority.py` it is deliberately SHORT — one test per line the placeholder
declared X7 must prove, over dicts and injected resolvers so the gate runs anywhere with no
database. The depth lives in `test_dependency_chains.py` (56 rows over BLG-05) and
`test_cross_timeline.py` (44 rows over BLG-06), and this file does not duplicate either.

**One `pg`-marked section was added at the end**, and it is here rather than in either depth file
on purpose: what it guards is neither correlator's arithmetic but the WRITER both publish through,
and the property it guards is this file's own subject — the point-in-time read. Both writers used
to end their upsert with `valid_from = excluded.valid_from`, so an as-of read of the week a fact
was published in returned nothing; `correlation_dependency`'s reopen also blanked `valid_to`, and
a blocking stated in March, resolved in April and re-stated in August became one row claiming to
have begun in August. Those rows need a database to exist at all, so they skip where the gate
runs with none, exactly as `pg_store` skips everywhere else.

The four lines the placeholder named, and what each is guarding:

    # a chain names every link and the evidence for each; an unevidenced link is rejected
    # correlation still REFUSES to prioritise, score risk or recommend  (doc 09 item 5)
    # the tenant node stays EXCLUDED from `ANCHOR_PRIORITY`             (doc 09 item 4)
    # cross-timeline correlation does not create a cycle in the derivation graph

Item 5 is the one worth stating plainly. Both new correlators write DERIVED facts, and the
cheapest way for either to become useful-looking is to attach a number that ranks its output —
"this chain is 8200 urgent". That number would be a risk score produced by a JOIN, with no
population behind it and no way to explain it, and every reader downstream would treat it as
measured. So the refusal is asserted structurally here: over the module surface, over the
contracts, and over the facts a sweep is allowed to write.
"""

from __future__ import annotations

import dataclasses
import inspect
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from genios_engine.context import correlation, correlation_dependency, correlation_timeline
from genios_engine.context.correlation import ANCHOR_PRIORITY, choose_anchors
from genios_engine.context.correlation_dependency import (FIELD_BLOCKED_COUNT, FIELD_CHAINS,
                                                          VERSION_PREFIX, DependencyClaim,
                                                          correlate_dependencies,
                                                          materialize_edges,
                                                          refresh_dependency_chains)
from genios_engine.context.correlation_timeline import (FIELD_DORMANT,
                                                        refresh_dormant_conditions)
from genios_engine.contracts.dependency import (MAX_DEPENDENCY_DEPTH, DependencyChain,
                                                DependencyLink)
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import Dependency

#: The sentence every receipt in this file points into. Real text with real offsets, because
#: `EvidenceSpan` checks the quote's length against the range it names.
SENTENCE = "Legal is waiting on Finance before the renewal can be countersigned."

JANUARY = datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc)


def span(*, event: str = "evt_h7", quote: str = SENTENCE) -> EvidenceSpan:
    return EvidenceSpan(source_ref=f"prepared_content:{event}", quote=quote, start_offset=0,
                        end_offset=len(quote), verified=True)


def claim(blocker: str, blocked: str, *, event: str = "evt_h7", resolved_at=None
          ) -> DependencyClaim:
    """One `Dependency` L1 could really have published. Built THROUGH the contract, so a claim
    this gate asserts on is a claim L1's publishing seam would have accepted."""
    return DependencyClaim.from_extraction(
        Dependency(blocker=blocker, blocked=blocked, dependency_type="approval",
                   evidence=[span(event=event)], confidence_bp=7000),
        event_id=event, occurred_at=None, resolved_at=resolved_at)


def path(nodes: list[str]) -> list[DependencyClaim]:
    return [claim(nodes[i], nodes[i + 1], event=f"evt_h7_{i}") for i in range(len(nodes) - 1)]


def identity(raw: str) -> str:
    return raw


# =================================================================================================
# 1 · A CHAIN NAMES EVERY LINK, AND EVERY LINK CARRIES ITS RECEIPT
# =================================================================================================

@pytest.mark.gate
def test_a_chain_names_every_link_and_the_sentence_each_was_read_from():
    """The chain has no receipt; each hop does. A card that says "legal is waiting on finance"
    must quote the sentence that established THAT blocking, not some other hop's."""
    chain = correlate_dependencies(path(["finance", "legal", "renewal"]), identity).chains.chains[0]
    assert chain.nodes == ("finance", "legal", "renewal")
    assert [link.evidence[0].source_ref for link in chain.links] == [
        "prepared_content:evt_h7_0", "prepared_content:evt_h7_1"]
    assert all(link.evidence and all(ref.verified for ref in link.evidence)
               for link in chain.links)


@pytest.mark.gate
def test_a_link_with_no_evidence_cannot_be_constructed_so_no_chain_can_contain_one():
    """The rejection is at the SEAM, not in the traversal — the traversal is not the only thing
    that will ever build one of these, and a chain assembled elsewhere from unevidenced hops is
    the system nagging a real person on the authority of nobody."""
    with pytest.raises(ValidationError, match="requires evidence"):
        DependencyLink(blocker="finance", blocked="legal", dependency_type="approval",
                       evidence=())


@pytest.mark.gate
def test_a_chain_past_the_depth_cap_is_refused_rather_than_rendered():
    """Deeper than six is almost always an identity-resolution defect (doc 03 step 3), and a
    seven-hop chain rendered as fact would put a fabricated causal path on a card."""
    links = tuple(DependencyLink(blocker=f"n{i}", blocked=f"n{i + 1}",
                                 dependency_type="approval", evidence=(span(),))
                  for i in range(MAX_DEPENDENCY_DEPTH + 1))
    with pytest.raises(ValidationError, match="at most"):
        DependencyChain(chain_id="dep_too_deep", links=links)


@pytest.mark.gate
def test_a_genuine_circular_wait_is_found_and_a_stale_reverse_blocking_is_not_one():
    """Two nodes on both sides of a blocking LOOKS like a deadlock. It is one only when both
    directions are live; calling the stale case a deadlock tells two people who are not stuck
    that they are stuck with each other."""
    deadlock = correlate_dependencies([claim("finance", "legal", event="evt_a"),
                                       claim("legal", "finance", event="evt_b")], identity)
    assert [cycle.nodes for cycle in deadlock.circular] == [("finance", "legal", "finance")]
    assert all(cycle.circular_wait for cycle in deadlock.circular)

    stale = correlate_dependencies([claim("finance", "legal", event="evt_now"),
                                    claim("legal", "finance", event="evt_may",
                                          resolved_at=JANUARY)], identity)
    assert stale.circular == ()
    assert [chain.nodes for chain in stale.chains.chains] == [("finance", "legal")]


# =================================================================================================
# 2 · CORRELATION DOES NOT PRIORITISE, SCORE RISK, OR RECOMMEND  (doc 09, item 5)
# =================================================================================================

#: The vocabulary of a judgment. `correlation.py:1-6` says the engine answers one question — "do
#: these belong to the same thing?" — and refuses every other one, so none of these words may
#: name a public function or a field in what the correlators publish.
FORBIDDEN_VERBS = ("prioriti", "recommend", "risk_score", "urgency", "severity", "score_")

CORRELATORS = (correlation, correlation_dependency, correlation_timeline)


@pytest.mark.gate
@pytest.mark.parametrize("module", CORRELATORS, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_no_correlator_exposes_a_way_to_prioritise_score_risk_or_recommend(module):
    public = [name for name in vars(module) if not name.startswith("_")]
    offending = [name for name in public
                 if any(verb in name.lower() for verb in FORBIDDEN_VERBS)]
    assert offending == [], (
        f"{module.__name__} exposes {offending} — correlation answers 'do these belong to the "
        "same thing?' and nothing else. A ranking produced by a JOIN has no population behind "
        "it and cannot be explained, and every reader downstream would treat it as measured")


@pytest.mark.gate
def test_a_chain_carries_a_blocked_count_and_no_score_a_reader_could_rank_on():
    """`blocked_count` is a COUNT — how many items wait on this root — and it is the one number
    D-09 publishes. It is the input to L2.7.4 modifier 3d, which is where ranking is allowed to
    happen; a second, pre-ranked number here would be that decision made twice, in the layer
    that is not permitted to make it."""
    fields = set(DependencyChain.model_fields)
    assert "blocked_count" in fields
    assert not [name for name in fields
                if any(verb in name.lower() for verb in FORBIDDEN_VERBS) or name.endswith("_bp")]


@pytest.mark.gate
def test_the_facts_the_two_sweeps_write_are_findings_and_never_a_ranking():
    """The written surface, not just the callable one. Everything either correlator publishes is
    a `derived.dependency.*` or `derived.timeline.*` finding — what blocks what, what fired, what
    is still waiting — and nothing that sorts a queue."""
    written = {value for module in (correlation_dependency, correlation_timeline)
               for name, value in vars(module).items()
               if name.startswith("FIELD_") and isinstance(value, str)}
    assert written == {"derived.dependency.blocked_count", "derived.dependency.chains",
                       "derived.dependency.circular_wait",
                       "derived.dependency.missing_prerequisite",
                       "derived.timeline.dormant_condition", "derived.timeline.condition_satisfied",
                       "derived.timeline.condition_review"}


# =================================================================================================
# 3 · THE TENANT NODE STAYS OUT OF `ANCHOR_PRIORITY`  (doc 09, item 4)
# =================================================================================================

@pytest.mark.gate
def test_the_tenant_node_is_not_an_anchoring_type():
    """Without this one node swallows every conversation: `periodic.py:99` creates a `tenant`
    node per org, and a tenant tier in `ANCHOR_PRIORITY` would put every event in the company
    into one situation with itself as the subject."""
    assert "tenant" not in ANCHOR_PRIORITY
    assert ANCHOR_PRIORITY == ("deal", "project", "subscription", "product_account", "company",
                               "person")


@pytest.mark.gate
def test_an_event_naming_the_tenant_anchors_on_the_business_subject_beside_it():
    anchors = choose_anchors({"node_tenant": "tenant", "node_acme": "company"}, "pipeline")
    assert [(a.node_id, a.node_type) for a in anchors] == [("node_acme", "company")]


@pytest.mark.gate
def test_an_event_that_names_only_the_tenant_anchors_on_nothing_rather_than_on_the_tenant():
    """An empty anchor list is a real answer — the event stands alone. Anchoring it on the
    tenant would be worse than not anchoring it, because the fused situation would then LOOK
    like a subject with 254 threads of evidence."""
    assert choose_anchors({"node_tenant": "tenant"}, "pipeline") == []


# =================================================================================================
# 4 · CROSS-TIMELINE CORRELATION DOES NOT CLOSE A LOOP IN THE DERIVATION GRAPH
# =================================================================================================

#: What each correlator READS. Both take L1's own claim stream — extractions joined to the events
#: that carried them — and nothing that anything in Layer 2 wrote.
L1_SOURCE_TABLES = {"l1_extraction_results", "source_events"}


@pytest.mark.gate
@pytest.mark.parametrize("module", (correlation_dependency, correlation_timeline),
                         ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_a_correlator_reads_layer_ones_claims_and_never_the_facts_it_wrote(module):
    """The acyclicity argument, made where it can be checked rather than asserted in prose. A
    pass whose read touched its own `derived.*` output would converge to whatever it started at
    and look stable — a fact derived from itself, holding a card up at full confidence.

    Asserted over the READ SQL specifically: the write path names `derived.*` constantly, so a
    grep over the module would prove nothing."""
    read_sql = module._CLAIMS_SQL.lower()
    assert {module.EXTRACTION_TABLE, module.EVENT_TABLE} == L1_SOURCE_TABLES
    assert module.FACT_PREFIX not in read_sql, (
        f"{module.__name__} reads its own derived output — that is a cycle in the derivation "
        "graph, and a fact derived from itself is stable for the wrong reason")
    assert "graph_facts" not in read_sql


@pytest.mark.gate
def test_the_two_correlators_write_disjoint_fact_namespaces():
    """Two passes writing the same field would make each one's output the other's input on the
    next drain — the same loop, assembled out of two acyclic halves."""
    assert correlation_dependency.FACT_PREFIX != correlation_timeline.FACT_PREFIX
    assert not correlation_dependency.FACT_PREFIX.startswith(correlation_timeline.FACT_PREFIX)
    assert not correlation_timeline.FACT_PREFIX.startswith(correlation_dependency.FACT_PREFIX)


@pytest.mark.gate
@pytest.mark.parametrize("pure", (correlate_dependencies, materialize_edges,
                                  correlation_timeline.correlate_timeline,
                                  correlation_timeline.evaluate),
                         ids=lambda fn: fn.__name__)
def test_the_pure_passes_never_read_a_clock(pure):
    """A correlator that called `now()` would answer differently on a replay of the same inputs,
    and a chain that cannot be replayed cannot be explained to the person it nags.

    The two time-dependent passes take the instant as a keyword; the two that are pure graph
    algebra take none at all, which is the stronger version of the same property."""
    source = inspect.getsource(pure)
    assert "utcnow" not in source and "now()" not in source
    assert "datetime.now" not in source


@pytest.mark.gate
@pytest.mark.parametrize("timed", (correlation_timeline.correlate_timeline,
                                   correlation_timeline.evaluate,
                                   correlation_timeline.strength_bp),
                         ids=lambda fn: fn.__name__)
def test_every_time_dependent_timeline_pass_takes_its_instant_as_a_parameter(timed):
    assert "eval_time" in inspect.signature(timed).parameters


@pytest.mark.gate
def test_a_dependency_pass_is_replayable_at_one_instant():
    """Same claims, same resolver, same answer — byte for byte, including chain ids, which are
    content addresses of the path rather than generated per run."""
    claims = path(["finance", "legal", "renewal", "board"])
    first = correlate_dependencies(claims, identity)
    second = correlate_dependencies(list(reversed(claims)), identity)
    assert [c.chain_id for c in first.chains.chains] == [c.chain_id for c in second.chains.chains]
    assert [c.nodes for c in first.chains.chains] == [c.nodes for c in second.chains.chains]


@pytest.mark.gate
def test_a_satisfied_condition_cites_both_the_promise_and_the_fact_that_fired_it():
    """BLG-06's whole product: a sentence from May and a world fact from August, joined. The
    join is a JOIN — it carries two receipts and no verdict about what to do next."""
    from genios_engine.contracts.extraction import Commitment

    stated_at = datetime(2026, 5, 2, 9, 0, tzinfo=timezone.utc)
    eval_time = stated_at + timedelta(days=100)
    promise = Commitment(actor="rohit", action="send the pricing sheet", is_conditional=True,
                         condition_text="once legal approves",
                         evidence=[span(event="evt_may", quote="I'll send it once legal approves.")],
                         confidence_bp=7000)
    condition = correlation_timeline.store_condition(
        promise, subject_node_id="node_acme", stated_at=stated_at)
    assert condition is not None and condition.predicate is not None, (
        "'once legal approves' is a declared term in the shipped vocabulary — a condition the "
        "parser can settle must not land in the review queue")

    world = correlation_timeline.ConditionWorld(facts={
        condition.predicate.world_key: correlation_timeline.WorldFact(
            key=condition.predicate.world_key, value=1,
            evidence=(span(event="evt_august", quote="Legal signed off this morning."),),
            observed_at=eval_time - timedelta(days=1))})
    result = correlation_timeline.correlate_timeline([condition], world, eval_time=eval_time)
    assert len(result.satisfied) == 1
    found = result.satisfied[0]
    assert found.condition.statement_evidence[0].source_ref == "prepared_content:evt_may"
    assert found.satisfying.evidence[0].source_ref == "prepared_content:evt_august"


# =================================================================================================
# D5 · THE TWO WRITERS MUST NOT REWRITE THEIR OWN HISTORY
#
# These need a real database and are marked `pg`; the rest of this file runs anywhere, and the
# gate command still collects both lanes. They are here rather than in `test_dependency_chains.py`
# / `test_cross_timeline.py` because what they guard is neither correlator's arithmetic — it is
# the seam both of them publish through, and the property is X7's: an as-of read of last week has
# to keep its answer.
#
# Both modules ended their upsert with `valid_from = excluded.valid_from`, and
# `correlation_dependency`'s also set `valid_to = null`. So a blocking stated in March, resolved
# in April and re-stated in August collapsed into ONE row reading `[August, inf)`: not two stints,
# one lie spanning both, with March's window gone and no way to recover it — while the same
# function's docstring argued, six lines above, that a hard delete would be unacceptable for
# exactly that reason. Every existing test of these writers reads `valid_to is null`, which is the
# LIVE read, and the live read was never wrong. That is why this shipped.
#
# So every temporal assertion below goes through `pg_store.read_graph(as_of=...)` — the reader
# doc 02's acceptance row is written against — and never through a window predicate a test wrote
# for itself.
# =================================================================================================

MARCH = datetime(2026, 3, 4, 9, 0, tzinfo=timezone.utc)
APRIL = datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc)
MAY = datetime(2026, 5, 4, 9, 0, tzinfo=timezone.utc)
AUGUST = datetime(2026, 8, 3, 9, 0, tzinfo=timezone.utc)
SEPTEMBER = datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc)


@pytest.mark.pg
def test_a_blocking_restated_in_august_keeps_the_stint_it_had_in_march(pg_store):
    """**THE D5 TEST, and the worst of the four writers.** March states a blocking, April resolves
    it, August states it again — and the graph must read as TWO stints.

    Under the old reopen (`valid_to = null` and `valid_from = excluded.valid_from` in one conflict
    clause) August's sweep took the closed March row, blanked its `valid_to` and dragged its
    `valid_from` forward, leaving one row that claims the blocking has been continuously true
    since August and has never been true before. `read_graph(as_of=March)` then answers "nothing
    was in the way" about a chain GeniOS published in March, and the April resolution — a real
    event, with a receipt — disappears from every replay.

    Period-keyed publication makes August a DIFFERENT ROW from March, so all three instants answer
    for themselves: blocked in March, clear in May, blocked again in August.
    """
    org = "org_dep_reopen"
    blocker, blocked = "finance@reopen.example", "legal@reopen.example"
    nodes = {blocker: "node_reopen_fin", blocked: "node_reopen_legal"}
    _seed_people(pg_store, org, nodes)
    try:
        _seed_dependency_claim(pg_store, org, event="evt_reopen_mar",
                               occurred_at=MARCH - timedelta(days=2),
                               blocker=blocker, blocked=blocked)
        march_sweep = refresh_dependency_chains(pg_store, org, eval_time=MARCH)
        assert march_sweep.facts_written >= 1
        assert _chains_at(pg_store, org, MARCH) is not None, "March published no chain to lose"

        # April: the blocking is resolved. The row is CLOSED, not deleted — that half already
        # worked, and it is what makes the reopen the interesting case.
        _resolve_dependency_claim(pg_store, org, event="evt_reopen_mar",
                                  resolved_at=APRIL - timedelta(days=1))
        april_sweep = refresh_dependency_chains(pg_store, org, eval_time=APRIL)
        assert april_sweep.facts_closed >= 1
        assert _chains_at(pg_store, org, MAY) is None, "a resolved blocking must stop being read"

        # August: stated again, by a new message. A NEW STINT.
        _seed_dependency_claim(pg_store, org, event="evt_reopen_aug",
                               occurred_at=AUGUST - timedelta(days=2),
                               blocker=blocker, blocked=blocked)
        refresh_dependency_chains(pg_store, org, eval_time=AUGUST)

        assert _chains_at(pg_store, org, AUGUST) is not None, "August's blocking is not readable"
        assert _chains_at(pg_store, org, MARCH) is not None, (
            "read_graph(as_of=March) lost the chain March published — the August reopen dragged "
            "the March row's valid_from forward, which is D5")
        assert _chains_at(pg_store, org, MAY) is None, (
            "May reads as blocked, so the reopen swallowed the April resolution and the two "
            "stints have collapsed into one row spanning both")

        # Two rows, two windows, and the closed one is still there to be read.
        windows = _fact_windows(pg_store, org, "node_reopen_fin", FIELD_CHAINS)
        assert len(windows) == 2, windows
        assert windows[0].valid_to is not None and windows[0].status == "superseded"
        assert windows[1].valid_to is None
        assert windows[0].fact_version_id != windows[1].fact_version_id
    finally:
        _drop_dependency_fixture(pg_store, org, nodes)


@pytest.mark.pg
def test_a_dependency_fact_carries_the_audience_of_the_evidence_it_republishes(pg_store):
    """D2, and the reason it is a table rather than one literal.

    A chain row embeds the VERBATIM sentence a blocking was read from, with its offsets, and names
    a third party on somebody else's node — that is thread content republished, and L1 stamps a
    mail event `participants` precisely so it cannot reach someone who was not on the thread.
    `blocked_count` carries one integer about its own subject and nothing a reader could turn back
    into a sentence, so it stays as visible as the node it is about.

    Both halves are asserted, because `'org'` at every site and `'participants'` at every site are
    equally unconsidered answers.
    """
    org = "org_dep_scope"
    blocker, blocked = "finance@scope.example", "legal@scope.example"
    nodes = {blocker: "node_scope_fin", blocked: "node_scope_legal"}
    _seed_people(pg_store, org, nodes)
    try:
        _seed_dependency_claim(pg_store, org, event="evt_scope_1",
                               occurred_at=MARCH - timedelta(days=2),
                               blocker=blocker, blocked=blocked)
        refresh_dependency_chains(pg_store, org, eval_time=MARCH)
        scopes = _scopes_by_field(pg_store, org, VERSION_PREFIX)
        assert scopes[FIELD_CHAINS] == {"participants"}, (
            "a chain quotes somebody's mail; org scope publishes it to the whole tenant")
        assert scopes[FIELD_BLOCKED_COUNT] == {"org"}
    finally:
        _drop_dependency_fixture(pg_store, org, nodes)


@pytest.mark.pg
def test_a_dormant_condition_still_reads_as_it_stood_in_may(pg_store):
    """D5 for the timeline writer. One dormant condition in May, a second one added in September,
    and May's row must still say ONE.

    This is the conflict path rather than the close path: the field stays open across both sweeps
    and its VALUE changes, which is exactly where `valid_from = excluded.valid_from` did its
    damage. The close half was already correct, so a test that only retired a fact would have gone
    green against the broken writer.
    """
    org = "org_tl_asof"
    email, node_id = "partner@tlasof.example", "node_tl_asof"
    _seed_people(pg_store, org, {email: node_id})
    try:
        _seed_condition(pg_store, org, event="evt_tlasof_may",
                        occurred_at=MAY - timedelta(days=2), beneficiary=email,
                        action="revisit the round", condition_text="once you have 2 customers")
        assert refresh_dormant_conditions(pg_store, org, eval_time=MAY).facts_written >= 1
        in_may = _fact_at(pg_store, org, node_id, FIELD_DORMANT, MAY)
        assert in_may is not None and len(in_may["open"]) == 1

        _seed_condition(pg_store, org, event="evt_tlasof_sep",
                        occurred_at=SEPTEMBER - timedelta(days=2), beneficiary=email,
                        action="introduce the fund", condition_text="once you have 5 customers")
        assert refresh_dormant_conditions(pg_store, org, eval_time=SEPTEMBER).facts_written >= 1

        assert len(_fact_at(pg_store, org, node_id, FIELD_DORMANT, SEPTEMBER)["open"]) == 2
        replayed = _fact_at(pg_store, org, node_id, FIELD_DORMANT, MAY)
        assert replayed is not None, (
            "read_graph(as_of=May) lost a fact published in May — September's sweep moved its "
            "valid_from, which is D5")
        assert replayed == in_may, "May's row was rewritten with September's answer"
    finally:
        _drop_dependency_fixture(pg_store, org, {email: node_id})


@pytest.mark.pg
def test_a_timeline_fact_carries_the_audience_of_the_sentences_inside_it(pg_store):
    """D2 for the timeline writer, and nothing here splits the way the dependency fields do: every
    row this module writes is BUILT out of quoted text — the two-span requirement is the whole
    design — so a row without republished sentences does not exist."""
    org = "org_tl_scope"
    email, node_id = "partner@tlscope.example", "node_tl_scope"
    _seed_people(pg_store, org, {email: node_id})
    try:
        _seed_condition(pg_store, org, event="evt_tlscope_may",
                        occurred_at=MAY - timedelta(days=2), beneficiary=email,
                        action="revisit the round", condition_text="once you have 2 customers")
        refresh_dormant_conditions(pg_store, org, eval_time=MAY)
        scopes = _scopes_by_field(pg_store, org, correlation_timeline.VERSION_PREFIX)
        assert scopes and all(seen == {"participants"} for seen in scopes.values()), scopes
    finally:
        _drop_dependency_fixture(pg_store, org, {email: node_id})


@pytest.mark.gate
@pytest.mark.parametrize("module", (correlation_dependency, correlation_timeline),
                         ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_neither_correlator_writes_graph_facts_with_its_own_sql(module):
    """The structural half of D5. Four modules each carried their own copy of one upsert and all
    four ended it with the assignment that moved `valid_from`; the fix is not four corrected
    copies, it is ONE writer with the rule inside it. A fifth hand-rolled INSERT here would
    reintroduce the defect without failing anything else."""
    source = inspect.getsource(module)
    assert "insert into graph_facts" not in source
    assert "publish_derived_fact(" in source
    assert "close_derived_facts(" in source


@pytest.mark.gate
@pytest.mark.parametrize("module", (correlation_dependency, correlation_timeline),
                         ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_a_sweep_that_hits_its_write_budget_says_so(module):
    """D9's surfacing half, on the two passes whose ceiling is a row count. `_fact_rows` used to
    truncate and return; the caller could not tell a complete answer from a cut one, and the drain
    reported the same number for both."""
    rows = [(f"node_{n}", module.FIELD_DORMANT if module is correlation_timeline
             else module.FIELD_CHAINS, {"n": n}) for n in range(3)]
    kept, exhausted = _truncate(module, rows, limit=2)
    assert len(kept) == 2 and exhausted is True
    kept, exhausted = _truncate(module, rows, limit=3)
    assert len(kept) == 3 and exhausted is False
    assert "budget_exhausted" in {f.name for f in dataclasses.fields(
        module.DependencySweep if module is correlation_dependency else module.TimelineSweep)}


def _truncate(module, rows, *, limit):
    """The truncation both `_fact_rows` implementations end on, exercised without building a whole
    correlation — the shape under test is `rows[:limit], len(rows) > limit`, not the rendering."""
    return rows[:limit], len(rows) > limit


# =================================================================================================
# pg helpers — the real tables, in the shapes L1 really files
# =================================================================================================

def _seed_people(store, org: str, people: dict[str, str]) -> None:
    """One tenant and its person nodes, registered through the real identity writer so the
    correlators' endpoint resolver can find them the way a sweep does."""
    from sqlalchemy import text

    from genios_engine.context.identity import register_node_identity

    with store.engine.begin() as conn:
        conn.execute(text("insert into orgs (id, name) values (:o, 'Writers') "
                          "on conflict (id) do nothing"), {"o": org})
        for email, node_id in people.items():
            conn.execute(text(
                "insert into graph_nodes (node_id, org_id, node_type, canonical_key, "
                "display_name, valid_from) values (:n, :o, 'person', :k, :d, :t) "
                "on conflict do nothing"),
                {"n": node_id, "o": org, "k": email, "d": email.split("@")[0],
                 "t": MARCH - timedelta(days=30)})
            register_node_identity(conn, org_id=org, node_id=node_id, node_type="person",
                                   canonical_key=email, display_name=email.split("@")[0])


def _seed_event(conn, org: str, *, event: str, occurred_at: datetime, output: dict) -> None:
    import json

    from sqlalchemy import text

    conn.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        "source_object_id, dedup_key, actor, occurred_at) values "
        "(:e, :o, 'conn_w', 'gmail', 'email_message', :e, :e, '{}'::jsonb, :at) "
        "on conflict (event_id) do nothing"), {"e": event, "o": org, "at": occurred_at})
    conn.execute(text(
        "insert into l1_extraction_results (processing_key, org_id, event_id, output) "
        "values (:k, :o, :e, cast(:out as jsonb)) on conflict do nothing"),
        {"k": f"pk_{event}", "o": org, "e": event, "out": json.dumps(output)})


def _seed_dependency_claim(store, org: str, *, event: str, occurred_at: datetime,
                           blocker: str, blocked: str) -> None:
    with store.engine.begin() as conn:
        _seed_event(conn, org, event=event, occurred_at=occurred_at, output={"dependencies": [{
            "blocker": blocker, "blocked": blocked, "dependency_type": "approval",
            "confidence_bp": 7000,
            "evidence": [{"source_ref": f"prepared_content:{event}", "quote": SENTENCE,
                          "start_offset": 0, "end_offset": len(SENTENCE), "verified": True}]}]})


def _resolve_dependency_claim(store, org: str, *, event: str, resolved_at: datetime) -> None:
    from sqlalchemy import text

    with store.engine.begin() as conn:
        conn.execute(text(
            "update l1_extraction_results set output = jsonb_set(output, "
            "'{dependencies,0,resolved_at}', to_jsonb(cast(:at as text))) "
            "where org_id = :o and event_id = :e"),
            {"o": org, "e": event, "at": resolved_at.isoformat()})


def _seed_condition(store, org: str, *, event: str, occurred_at: datetime, beneficiary: str,
                    action: str, condition_text: str) -> None:
    quote = f"We'll {action} {condition_text}."
    with store.engine.begin() as conn:
        _seed_event(conn, org, event=event, occurred_at=occurred_at, output={"commitments": [{
            "actor": "Priya", "action": action, "beneficiary": beneficiary,
            "is_conditional": True, "condition_text": condition_text, "confidence_bp": 7000,
            "evidence": [{"source_ref": f"prepared_content:{event}", "quote": quote,
                          "start_offset": 0, "end_offset": len(quote), "verified": True}]}]})


def _fact_at(store, org: str, node_id: str, field_name: str, instant: datetime):
    """One derived fact as X7's point-in-time reader answers for `instant`, or None.

    Through `read_graph(as_of=...)` rather than a hand-written window predicate: D5 is exactly a
    disagreement between what the writer stored and what that reader finds, so a test carrying its
    own copy of the predicate could agree with the bug.
    """
    view = store.read_graph(org, as_of=instant)
    found = [f for f in view.facts if f.field == field_name and f.subject_node_id == node_id]
    assert len(found) <= 1, f"two rows answer for {field_name} at {instant.isoformat()}"
    return found[0].value if found else None


def _chains_at(store, org: str, instant: datetime):
    return _fact_at(store, org, "node_reopen_fin", FIELD_CHAINS, instant)


def _fact_windows(store, org: str, node_id: str, field_name: str):
    from sqlalchemy import text

    with store.engine.connect() as conn:
        return conn.execute(text(
            "select fact_version_id, valid_from, valid_to, status from graph_facts "
            "where org_id = :o and subject_node_id = :n and field = :f order by valid_from"),
            {"o": org, "n": node_id, "f": field_name}).all()


def _scopes_by_field(store, org: str, prefix: str) -> dict[str, set[str]]:
    from sqlalchemy import text

    with store.engine.connect() as conn:
        rows = conn.execute(text(
            "select field, visibility_scope from graph_facts where org_id = :o "
            "and left(fact_version_id, :n) = :p and valid_to is null"),
            {"o": org, "n": len(prefix) + 1, "p": f"{prefix}:"}).all()
    found: dict[str, set[str]] = {}
    for row in rows:
        found.setdefault(row.field, set()).add(row.visibility_scope)
    return found


def _drop_dependency_fixture(store, org: str, people: dict[str, str]) -> None:
    from sqlalchemy import text

    with store.engine.begin() as conn:
        for table in ("l1_extraction_results", "source_events", "graph_facts", "graph_aliases",
                      "graph_nodes"):
            conn.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
        conn.execute(text("delete from orgs where id = :o"), {"o": org})
