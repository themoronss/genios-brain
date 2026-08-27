"""The deal node, end to end, against a REAL Postgres (skipped without GENIOS_TEST_DATABASE_URL).

WHAT WAS BROKEN
`context/pipeline.py` created exactly four node types — commitment, company, person, thread — and
`deal` was not among them. Every other link in the chain was already built and waiting:

    correlation.ANCHOR_PRIORITY  →  ("deal", …)   — deal ranks ABOVE company and person
    domain_spec.situation_types  →  {"deal": "deal", …}
    the Sales corpus             →  4 situations bound to the `deal` type, ~20 capabilities behind them

So a `deal.status` fact was extracted correctly, written onto whichever PERSON happened to be its
subject, and the whole deal lane stayed empty. On the design partner's org that was 45 `deal.status`
rows across 38 nodes, zero deal nodes, zero deal situations, and roughly twenty authored
capabilities that could never compile.

These tests are deliberately behavioural rather than unit-shaped: the bug was invisible to unit
tests precisely because every unit worked. Only running the real SQL — extraction through node
creation through correlation to a typed situation — shows the gap.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.context import situations
from genios_engine.context.backfill import (
    backfill_correlations,
    backfill_deal_nodes,
    backfill_layer2,
)
from genios_engine.context.pipeline import process_event

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _seed_org(store, org: str) -> None:
    """The FK-parent org row, filling any NOT-NULL-no-default column so graph_nodes.org_id resolves."""
    with store.engine.begin() as conn:
        reqd = conn.execute(text(
            "select column_name, data_type from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
        parts, ph, vals = ["id"], [":id"], {"id": org}
        for r in reqd:
            parts.append(r.column_name)
            ph.append(f":{r.column_name}")
            dt = r.data_type
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                                   else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                                   else "o@x.test" if "email" in r.column_name else org)
        conn.execute(text(f"insert into orgs ({','.join(parts)}) values ({','.join(ph)}) "
                          "on conflict do nothing"), vals)


def _seed_event(conn, org: str, event_id: str) -> None:
    """A minimal emitted `source_events` row. Columns are discovered rather than listed, because
    the table has grown several NOT-NULL columns since it was written and a hard-coded insert
    breaks on the next migration for reasons that have nothing to do with what is under test."""
    reqd = conn.execute(text(
        "select column_name, data_type from information_schema.columns "
        "where table_name='source_events' and is_nullable='NO' and column_default is null")).all()
    # `domain_hints` is nullable, and leaving it null routes the replay to the `general` domain —
    # the situation then types as `general_deal`, which no Sales situation file claims.
    vals = {"event_id": event_id, "org_id": org, "source": "gmail", "object_type": "email",
            "outcome": "emitted", "occurred_at": NOW,
            "domain_hints": json.dumps([{"domain": "sales"}])}
    for r in reqd:
        if r.column_name in vals:
            continue
        vals[r.column_name] = (NOW if ("time" in r.data_type or "date" in r.data_type)
                               else 0 if ("int" in r.data_type or "numeric" in r.data_type)
                               else "{}" if "json" in r.data_type
                               else f"{r.column_name}_{event_id}")
    cols = ",".join(vals)
    conn.execute(text(f"insert into source_events ({cols}) "
                      f"values ({','.join(':' + c for c in vals)}) on conflict do nothing"), vals)


class _FakeResult:
    ok, raw, input_tokens, output_tokens, error = True, "{}", 10, 20, None

    def __init__(self, parsed):
        self.parsed = parsed


class _FakeLLM:
    """Deterministic stand-in for the Haiku extractor, so the real resolution/write/correlate SQL
    runs without an API key and without the test depending on model behaviour."""
    model = "fake-haiku"

    def __init__(self, parsed):
        self._parsed = parsed

    def call(self, prompt, *, max_tokens=4096):
        return _FakeResult(self._parsed)


# Every fact and observation is substring-backed, because the grounding guard silently discards
# anything it cannot find in the content — a canned payload that ignores that tests nothing.
_CONTENT = ("Priya from Acme confirmed the proposal is at final review and the deal is in "
            "negotiation. Legal is reviewing the contract this week.")

_CANNED = {
    "relevance": 0.9, "noise_type": "none", "domains": ["sales"],
    "entity_mentions": [
        {"type": "person", "name": "Priya", "email": "priya@acme.io",
         "evidence_text": "Priya from Acme"},
        {"type": "company", "name": "Acme", "email": None, "evidence_text": "from Acme"}],
    "fact_candidates": [
        {"subject": "Priya", "field": "deal.status", "value": "negotiation",
         "evidence_text": "the deal is in negotiation"},
        {"subject": "Priya", "field": "deal.stage", "value": "final review",
         "evidence_text": "the proposal is at final review"}],
    "commitments": [],
    "questions": [],
    "observations": [{"kind": "legal_review", "evidence_text": "Legal is reviewing the contract"}],
}


def _run(store, org: str, event_id: str = "d_evt") -> None:
    res = process_event(org_id=org, event_id=event_id, source="gmail", content=_CONTENT,
                        sender_email="priya@acme.io", occurred_at=NOW, llm=_FakeLLM(_CANNED),
                        store=store, is_inbound=True, internal_emails=frozenset(),
                        domain_hints=[{"domain": "sales"}])
    assert res.outcome == "committed"


def test_a_deal_fact_from_correspondence_mints_a_deal_node(pg_store):
    org = "deal_mint"
    _seed_org(pg_store, org)
    _run(pg_store, org)
    with pg_store.engine.begin() as conn:
        deals = conn.execute(text(
            "select node_id, canonical_key, display_name from graph_nodes "
            "where org_id=:o and node_type='deal' and valid_to is null"), {"o": org}).all()
    assert len(deals) == 1, "correspondence carrying deal.* must produce exactly one deal node"
    # Named after the ACCOUNT. A card says this out loud, and "deal:node_abc123" in front of a
    # founder is worse than no card at all.
    assert "acme.io" in (deals[0].display_name or "")


def test_deal_facts_land_on_the_deal_not_on_the_person(pg_store):
    org = "deal_subject"
    _seed_org(pg_store, org)
    _run(pg_store, org)
    with pg_store.engine.begin() as conn:
        rows = conn.execute(text(
            "select f.field, n.node_type from graph_facts f "
            "join graph_nodes n on n.org_id=f.org_id and n.node_id=f.subject_node_id "
            "where f.org_id=:o and f.field like 'deal.%' and f.valid_to is null"), {"o": org}).all()
    assert rows, "the deal facts were dropped entirely"
    # `_load_context` reads facts by subject_node_id, so a deal fact filed on a person is a fact
    # the deal-anchored situation cannot see. This is the whole point of the node.
    assert {r.node_type for r in rows} == {"deal"}


def test_the_deal_is_edged_to_both_the_account_and_the_contact(pg_store):
    org = "deal_edges"
    _seed_org(pg_store, org)
    _run(pg_store, org)
    with pg_store.engine.begin() as conn:
        edges = conn.execute(text(
            "select e.edge_type, f.node_type as from_type, t.node_type as to_type "
            "from graph_edges e "
            "join graph_nodes f on f.org_id=e.org_id and f.node_id=e.from_node_id "
            "join graph_nodes t on t.org_id=e.org_id and t.node_id=e.to_node_id "
            "where e.org_id=:o and e.valid_to is null "
            "  and (f.node_type='deal' or t.node_type='deal')"), {"o": org}).all()
    pairs = {(e.from_type, e.edge_type, e.to_type) for e in edges}
    assert ("company", "owns", "deal") in pairs
    # The person edge is not decoration. `_neighborhood` is ONE hop and a company node holds
    # almost no facts of its own — thread.ball_in_court, commitment.due_at and derived.engagement
    # all sit on the PEOPLE. Without a direct deal→person edge the contacts are two hops away and
    # a deal-anchored situation reads an empty neighbourhood, which returns INSUFFICIENT_CONTEXT.
    assert ("deal", "involves", "person") in pairs


def test_the_situation_types_as_a_deal_not_as_an_opportunity(pg_store):
    org = "deal_situation"
    _seed_org(pg_store, org)
    _run(pg_store, org)
    situations.refresh_situations(pg_store, org, eval_time=NOW)
    with pg_store.engine.begin() as conn:
        types = {s["situation_type"] for s in situations.active_situations(conn, org_id=org)}
    # This is the assertion the whole change exists for: `deal` outranks `company` in
    # ANCHOR_PRIORITY, so the situation the corpus sees is the deal one, and the ~20 deal-bound
    # capabilities become reachable without a line of new corpus.
    assert "deal" in types, f"expected a deal-typed situation, got {types}"


def test_re_running_the_same_event_does_not_mint_a_second_deal(pg_store):
    org = "deal_idem"
    _seed_org(pg_store, org)
    _run(pg_store, org, event_id="idem_1")
    _run(pg_store, org, event_id="idem_2")
    with pg_store.engine.begin() as conn:
        n = conn.execute(text("select count(*) from graph_nodes where org_id=:o "
                              "and node_type='deal' and valid_to is null"), {"o": org}).scalar()
    # Keyed on the account, not on the message: the same opportunity reaches us through several
    # contacts and several threads, and one deal per email would shatter one negotiation into
    # dozens of situations.
    assert n == 1


def test_the_backfill_gives_history_the_deal_node_it_never_had(pg_store):
    """A tenant with months of history has the facts already written onto people. Without this
    pass the deal lane stays empty until fresh mail arrives, and every deal capability looks
    broken while being correctly authored."""
    org = "deal_backfill"
    _seed_org(pg_store, org)
    with pg_store.engine.begin() as conn:
        _seed_event(conn, org, "bf_e1")
        person = pg_store.find_or_create_node(conn, org_id=org, node_type="person",
                                              canonical_key="buyer@zeta.io",
                                              display_name="Buyer", event_id="bf_e1")
        company = pg_store.find_or_create_node(conn, org_id=org, node_type="company",
                                               canonical_key="zeta.io", display_name="zeta.io",
                                               event_id="bf_e1")
        pg_store.write_edge(conn, org_id=org, edge_type="works_at", from_node_id=person,
                            to_node_id=company, confidence=0.9, occurred_at=NOW,
                            event_id="bf_e1", evidence={}, source="gmail")
        # The misfiling this pass exists to correct: a deal fact sitting on a person.
        pg_store.write_fact(conn, org_id=org, subject_node_id=person, field="deal.status",
                            value="negotiation", value_type="string", confidence=0.8,
                            relevance=0.9, occurred_at=NOW, event_id="bf_e1",
                            evidence={}, source="gmail")

    out = backfill_deal_nodes(pg_store, org)
    assert out["deal_nodes_created"] == 1 and out["deal_facts_moved"] == 1

    with pg_store.engine.begin() as conn:
        holder = conn.execute(text(
            "select n.node_type from graph_facts f "
            "join graph_nodes n on n.org_id=f.org_id and n.node_id=f.subject_node_id "
            "where f.org_id=:o and f.field='deal.status' and f.valid_to is null"),
            {"o": org}).scalar()
    assert holder == "deal"

    # Re-runnable. A backfill that double-mints on a second pass is a backfill nobody dares run
    # twice, and on a live tenant it will be run twice.
    again = backfill_deal_nodes(pg_store, org)
    assert again["deal_nodes_created"] == 0 and again["deal_facts_moved"] == 0


def test_a_later_message_about_the_account_reaches_the_deal(pg_store):
    """`plan_correlation` is thread-first: a reply carries the conversation's identity. So a
    thread that anchored on the company before the deal node existed keeps pulling every later
    message back to the company anchor, and the deal situation stays a group of one — a failure
    that shows up in no count anywhere. Lifting the company to its deal removes the ordering
    problem instead of trying to sequence around it."""
    from genios_engine.context.correlation import lift_companies_to_their_deals

    org = "deal_lift"
    _seed_org(pg_store, org)
    _run(pg_store, org, event_id="lift_1")
    with pg_store.engine.begin() as conn:
        company = conn.execute(text(
            "select node_id from graph_nodes where org_id=:o and node_type='company' "
            "and valid_to is null limit 1"), {"o": org}).scalar()
        lifted = lift_companies_to_their_deals(
            conn, org_id=org, domain="sales", node_types={company: "company"})
        assert set(lifted.values()) == {"company", "deal"}, lifted

        # Scoped to domains where a deal is a thing. `deal.status` is extracted from investor and
        # recruiting mail too, so an unconditional lift would retype every `investor_relationship`
        # as `fundraising_deal` — which no capability claims. One empty lane traded for another.
        assert lift_companies_to_their_deals(
            conn, org_id=org, domain="fundraising",
            node_types={company: "company"}) == {company: "company"}


def test_the_backfill_reanchors_a_situation_that_was_already_correlated(pg_store):
    """The half of the fix that is easy to leave out and impossible to notice.

    `backfill_correlations` skips events already in `context_correlation_members` — that guard is
    what makes it safe to re-run. On a tenant whose whole history is already correlated it also
    means the deal nodes appear, the corpus waits, and every situation still says `opportunity`.
    Without the release step the backfill reports success and changes nothing a user can see.
    """
    org = "deal_reanchor"
    _seed_org(pg_store, org)
    with pg_store.engine.begin() as conn:
        _seed_event(conn, org, "ra_1")     # backfill_correlations replays from source_events
    _run(pg_store, org, event_id="ra_1")
    situations.refresh_situations(pg_store, org, eval_time=NOW)

    # Simulate the live tenant's starting point: a graph whose deal facts sit on people and whose
    # events are already correlated against the resulting company anchor.
    with pg_store.engine.begin() as conn:
        person = conn.execute(text(
            "select node_id from graph_nodes where org_id=:o and node_type='person' "
            "and valid_to is null limit 1"), {"o": org}).scalar()
        conn.execute(text("update graph_facts set subject_node_id=:p where org_id=:o "
                          "and field like 'deal.%'"), {"o": org, "p": person})
        conn.execute(text("delete from graph_edges where org_id=:o and (from_node_id in "
                          "(select node_id from graph_nodes where org_id=:o and node_type='deal') "
                          "or to_node_id in (select node_id from graph_nodes where org_id=:o "
                          "and node_type='deal'))"), {"o": org})
        conn.execute(text("update graph_nodes set valid_to=now() where org_id=:o "
                          "and node_type='deal'"), {"o": org})
        conn.execute(text("update context_correlations set anchor_type='company' where org_id=:o"),
                     {"o": org})
        conn.execute(text("update context_situations set situation_type='opportunity' "
                          "where org_id=:o"), {"o": org})

    out = backfill_layer2(pg_store, org)
    assert out["deal_facts_moved"] >= 1
    with pg_store.engine.begin() as conn:
        types = {s["situation_type"] for s in situations.active_situations(conn, org_id=org)}
    assert "deal" in types, f"re-anchoring did not reach the situation: {types}"


def test_the_incremental_path_alone_cannot_correct_an_anchor(pg_store):
    """States the limitation the `rebuild` flag exists for, so nobody removes it as redundant.

    Releasing the affected events is not enough. Their THREAD still carries the old
    company-anchored correlation, and `plan_correlation` checks the thread before the anchor —
    so a released event rejoins exactly the group the correction was meant to move it out of.
    """
    org = "deal_incremental"
    _seed_org(pg_store, org)
    with pg_store.engine.begin() as conn:
        _seed_event(conn, org, "inc_1")
        conn.execute(text("update source_events set parent_object_id='thr_inc' "
                          "where org_id=:o and event_id='inc_1'"), {"o": org})
    _run(pg_store, org, event_id="inc_1")
    with pg_store.engine.begin() as conn:            # back to the pre-deal world
        person = conn.execute(text(
            "select node_id from graph_nodes where org_id=:o and node_type='person' "
            "and valid_to is null limit 1"), {"o": org}).scalar()
        conn.execute(text("update graph_facts set subject_node_id=:p where org_id=:o "
                          "and field like 'deal.%'"), {"o": org, "p": person})
        conn.execute(text("update graph_nodes set valid_to=now() where org_id=:o "
                          "and node_type='deal'"), {"o": org})
        conn.execute(text("delete from graph_edges where org_id=:o and edge_type in "
                          "('owns','involves')"), {"o": org})

    backfill_deal_nodes(pg_store, org)               # release only — no rebuild
    backfill_correlations(pg_store, org)
    situations.refresh_situations(pg_store, org, eval_time=NOW)
    with pg_store.engine.begin() as conn:
        stuck = {s["situation_type"] for s in situations.active_situations(conn, org_id=org)}

    backfill_correlations(pg_store, org, rebuild=True)
    situations.refresh_situations(pg_store, org, eval_time=NOW)
    with pg_store.engine.begin() as conn:
        fixed = {s["situation_type"] for s in situations.active_situations(conn, org_id=org)}
    assert "deal" in fixed, f"rebuild did not re-anchor: {fixed}"
    assert "deal" not in stuck or stuck == fixed     # documents, never dictates, the old value
