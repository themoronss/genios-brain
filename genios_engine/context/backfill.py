"""L2 · Backfill — applying entity resolution and correlation to data already in the graph.

WHY THIS HAS TO EXIST
Aliases are claimed inside `find_or_create_node`, and correlation runs inside the L2
drain. Both only fire when an event arrives. So on a tenant that already has months of
history, everything built in Steps 1–3 would appear to do nothing:

  * no aliases      → "Acme" in an email never reaches the acme.io node, and no duplicate
                      is ever proposed for entities that already exist
  * no correlations → historical events belong to no situation
  * no situations   → because they are derived from correlations

The features would look broken while being perfectly implemented, which is worse than
missing: nobody would know where to look.

ORDER MATTERS AND IS NOT NEGOTIABLE
Aliases first, then correlations, then situations. Correlating before entities are
resolved groups the same company under several nodes and produces situations that must
later be folded. Situations before correlations produces nothing at all.

TIME ORDER MATTERS TOO
Events are replayed oldest-first. Correlation generations depend on the gap between an
event and a group's existing span, so processing newest-first would open a fresh
generation for every old event and shatter one history into dozens of situations.

This is safe to re-run. Aliases are insert-or-ignore, membership is idempotent, and
situations are rebuilt from scratch every time.
"""
from __future__ import annotations

import json

from sqlalchemy import bindparam, text

from genios_engine.context.correlation import correlate_event
from genios_engine.context.identity import register_node_identity
from genios_engine.context.pipeline import _normalise_deal_status, is_platform_sender
from genios_engine.context.situations import refresh_situations

# Events per transaction. Small enough that a failure costs little and a long backfill
# does not hold one transaction open across a tenant's entire history.
_BATCH = 200


def backfill_aliases(store, org_id: str) -> dict:
    """Claim lookup keys for every entity already in the graph.

    Nodes are processed oldest-first so the ORIGINAL entity keeps a contested key and the
    later duplicate is the one raised as a proposal. Reversing that would make the newest
    row the canonical one purely by accident of iteration order.
    """
    with store.engine.connect() as conn:
        nodes = conn.execute(text(
            "select node_id, node_type, canonical_key, display_name, created_by_event_id "
            "from graph_nodes where org_id = :o and valid_to is null "
            "  and canonical_key is not null "
            "order by valid_from asc"), {"o": org_id}).all()

    registered = 0
    proposals = 0
    for start in range(0, len(nodes), _BATCH):
        with store.engine.begin() as conn:
            for node in nodes[start:start + _BATCH]:
                raised = register_node_identity(
                    conn, org_id=org_id, node_id=node.node_id,
                    node_type=node.node_type, canonical_key=node.canonical_key,
                    display_name=node.display_name,
                    event_id=node.created_by_event_id)
                registered += 1
                proposals += len(raised)
    return {"nodes_registered": registered, "merge_proposals_raised": proposals}


def backfill_correlations(store, org_id: str, *, limit: int | None = None,
                          rebuild: bool = False) -> dict:
    """Group historical events into situations.

    The node set for an old event is recovered from the evidence it left behind: every
    fact, observation and node it created. That is the same material the live path uses
    — it just reads it back out of the graph instead of holding it in memory.

    Our own seats are excluded here exactly as in the live path. Without it, every
    outbound email in the tenant's history would anchor on our own company and the
    backfill would build one situation containing the entire business.

    `rebuild` re-derives the WHOLE set instead of only correlating what is not yet grouped.

    It exists because the incremental path cannot correct an anchor. Correlation is
    thread-first — a reply carries its conversation's identity — so once a thread anchored on a
    company, every later message rejoins that company however much the graph has since learned.
    A tenant whose deal nodes were minted after the fact therefore keeps company-anchored
    situations forever, and the deal lane looks empty for a reason no count reveals. Releasing
    the affected events is not enough: their threads pull them straight back.

    Safe because a correlation is a pure derivation of graph state, and because a situation's id
    is a content hash of (anchor node, domain, generation) — the ids of everything that did not
    genuinely change come back identical. The only outside reference is
    `expertise_packages.situation_id`, which the Layer 3 shadow compile rewrites on every pass.
    """
    if rebuild:
        with store.engine.begin() as conn:
            for table in ("context_situations", "context_correlation_members",
                          "context_correlations"):
                conn.execute(text(f"delete from {table} where org_id = :o"), {"o": org_id})
    with store.engine.connect() as conn:
        internal = frozenset(r.e for r in conn.execute(text(
            "select lower(email) as e from org_seats "
            "where org_id = :o and active and email is not null"), {"o": org_id}) if r.e)

        events = conn.execute(text(
            "select se.event_id, se.occurred_at, se.parent_object_id, se.domain_hints "
            "from source_events se "
            "where se.org_id = :o and se.outcome = 'emitted' "
            "  and se.event_id not in ("
            "    select event_id from context_correlation_members where org_id = :o) "
            "order by se.occurred_at asc nulls last" +
            (" limit :lim" if limit else "")),
            {"o": org_id, **({"lim": limit} if limit else {})}).all()
        if not events:
            return {"events_seen": 0, "events_correlated": 0}

        # Nodes an event touched, recovered from what it created. One query for the whole
        # tenant beats one per event by orders of magnitude on a real history.
        touched: dict[str, dict[str, str]] = {}
        for row in conn.execute(text(
                "select ev, node_id, node_type, canonical_key from ("
                "  select f.created_by_event_id as ev, n.node_id, n.node_type, n.canonical_key "
                "  from graph_facts f join graph_nodes n on n.org_id = f.org_id "
                "    and n.node_id = f.subject_node_id and n.valid_to is null "
                "  where f.org_id = :o and f.created_by_event_id is not null "
                "  union "
                "  select o2.created_by_event_id as ev, n.node_id, n.node_type, n.canonical_key "
                "  from graph_observations o2 join graph_nodes n on n.org_id = o2.org_id "
                "    and n.node_id = o2.subject_node_id and n.valid_to is null "
                "  where o2.org_id = :o and o2.created_by_event_id is not null "
                "  union "
                "  select n.created_by_event_id as ev, n.node_id, n.node_type, n.canonical_key "
                "  from graph_nodes n "
                "  where n.org_id = :o and n.valid_to is null "
                "    and n.created_by_event_id is not null"
                ") reached"), {"o": org_id}):
            if (row.canonical_key or "").lower() in internal:
                continue                       # our own people never anchor a situation
            touched.setdefault(row.ev, {})[row.node_id] = row.node_type

    correlated = 0
    for start in range(0, len(events), _BATCH):
        with store.engine.begin() as conn:
            for event in events[start:start + _BATCH]:
                nodes = touched.get(event.event_id)
                if not nodes:
                    continue                   # anchored nothing — correctly uncorrelated
                if correlate_event(conn, org_id=org_id, event_id=event.event_id,
                                   occurred_at=event.occurred_at,
                                   thread_id=event.parent_object_id,
                                   node_types=nodes,
                                   domain_hints=event.domain_hints):
                    correlated += 1
    return {"events_seen": len(events), "events_correlated": correlated}


def backfill_deal_nodes(store, org_id: str) -> dict:
    """Give every `deal.*` fact already in the graph the deal node it should always have had.

    `pipeline.py` now mints a deal node when it extracts a `deal.*` fact, but that only fires on
    a NEW event. On a tenant with months of history the facts are already written — onto the
    PERSON who happened to be the subject, because until now nothing else existed to hold them.
    The design partner's org carries 45 `deal.status` rows across 38 nodes and not one deal node,
    so without this pass the deal lane stays empty until fresh mail arrives, and the ~20
    deal-anchored capabilities keep looking broken while being correctly authored.

    Facts are MOVED, not copied. `_load_context` reads facts by `subject_node_id`, so a copy would
    make `deal.status` true of both the person and the deal, and a later contradiction would have
    two homes and no way to reconcile them. A person is not a deal; the fact was misfiled.

    Idempotent: a node already keyed `deal:<company>` is reused, edges are no-ops on repeat, and
    facts already sitting on a deal node are not re-selected.
    """
    with store.engine.connect() as conn:
        # Facts to move, with the company to hang them on, resolved down TWO routes because one
        # is not enough on real history:
        #
        #   `works_at`  — the edge the live pipeline itself uses, so backfill and live agree about
        #                 which account a deal belongs to instead of each inventing a rule; but it
        #                 only exists for people who were a sender or a recipient, and a person
        #                 first met as a NAME inside someone else's mail never got one.
        #   the domain  — the same derivation `_works_at` performs, applied after the fact. On the
        #                 design partner's org this is the difference between 8 facts rescued and
        #                 most of them: 23 deal facts sat on people with no `works_at` edge, and a
        #                 third of those carry a perfectly ordinary company domain.
        #
        # `created_by_event_id` is NULL on 67 of 75 of these facts and they have no source ref
        # either, so their own provenance is unrecoverable. The COMPANY node always has an event,
        # and attributing the deal to the correspondence that first established the account is the
        # truthful fallback — it points a reader at real mail about the right counterparty.
        rows = conn.execute(text(
            "select f.fact_version_id, f.subject_node_id, n.node_type, "
            "       coalesce(f.created_by_event_id, "
            "                (select min(sr.event_id) from graph_source_refs sr "
            "                 where sr.org_id = f.org_id "
            "                   and sr.fact_version_id = f.fact_version_id)) as fact_event, "
            "       coalesce(e.to_node_id, "
            "                case when n.node_type = 'company' then n.node_id end, "
            "                dom.node_id) as company_id, "
            "       coalesce(direct.created_by_event_id, dom.created_by_event_id) as company_event "
            "from graph_facts f "
            "join graph_nodes n on n.org_id = f.org_id and n.node_id = f.subject_node_id "
            "     and n.valid_to is null "
            "left join graph_edges e on e.org_id = f.org_id and e.from_node_id = f.subject_node_id "
            "     and e.edge_type = 'works_at' and e.valid_to is null "
            "left join graph_nodes direct on direct.org_id = f.org_id "
            "     and direct.node_id = coalesce(e.to_node_id, "
            "         case when n.node_type = 'company' then n.node_id end) "
            "     and direct.valid_to is null "
            # The domain half of the person's email, matched against a company we already know.
            # Deliberately never CREATES a company — inventing an account here would put a deal
            # on a counterparty nothing else in the graph has ever heard of.
            "left join graph_nodes dom on dom.org_id = f.org_id and dom.node_type = 'company' "
            "     and dom.valid_to is null and n.node_type = 'person' "
            "     and position('@' in coalesce(n.canonical_key, '')) > 0 "
            "     and dom.canonical_key = split_part(n.canonical_key, '@', 2) "
            "where f.org_id = :o and f.field like 'deal.%' and f.valid_to is null "
            "  and n.node_type <> 'deal' "
            "order by f.fact_version_id"), {"o": org_id}).all()

        # OUR OWN domains are not counterparties and cannot be in a deal with us. The live path
        # applies both halves of this in `_works_at` — the tenant's seats (is this the customer?)
        # and the platform's own address (is this us, the product?) — and a backfill that skips
        # them produces `thegenios.com — deal`: a card advising a founder about a negotiation with
        # his own vendor's website. It appeared on the first live run of this pass.
        seat_domains = {e.rsplit("@", 1)[1] for e in (
            (r.e or "") for r in conn.execute(text(
                "select lower(email) as e from org_seats where org_id=:o and active "
                "and email is not null"), {"o": org_id})) if "@" in e}
        internal = {r.node_id for r in conn.execute(text(
            "select node_id, canonical_key from graph_nodes where org_id=:o "
            "and node_type='company' and valid_to is null"), {"o": org_id})
            if (r.canonical_key or "").lower() in seat_domains
            or is_platform_sender("x@" + (r.canonical_key or ""))}

    orphaned = sum(1 for r in rows if not r.company_id or r.company_id in internal)
    by_company: dict[str, set[str]] = {}
    facts_for: dict[str, list[str]] = {}
    # `graph_source_refs.event_id` is NOT NULL, so the node and its edges must name a real event.
    cause: dict[str, str] = {}
    for r in rows:
        if not r.company_id or r.company_id in internal:
            continue                # no account to hang it on; leaving it put loses nothing
        by_company.setdefault(r.company_id, set()).add(r.subject_node_id)
        facts_for.setdefault(r.company_id, []).append(r.fact_version_id)
        if r.company_id not in cause and (r.fact_event or r.company_event):
            cause[r.company_id] = r.fact_event or r.company_event

    # Events whose node set has just CHANGED — they now touch a deal, and `choose_anchors` ranks
    # deal above company, so their correlation is stale and has to be released to take effect.
    touched_events = {r.fact_event for r in rows if r.company_id and r.fact_event}

    created = moved = edges = 0
    for company, subjects in sorted(by_company.items()):
        event_id = cause.get(company)
        if not event_id:
            continue                # no receipt is possible, and an unattributed node is worse
        with store.engine.begin() as conn:
            label = conn.execute(text(
                "select display_name from graph_nodes where org_id=:o and node_id=:n"),
                {"o": org_id, "n": company}).scalar()
            key = "deal:" + company
            existed = conn.execute(text(
                "select node_id from graph_nodes where org_id=:o and canonical_key=:k "
                "and valid_to is null"), {"o": org_id, "k": key}).first()
            deal = store.find_or_create_node(
                conn, org_id=org_id, node_type="deal", canonical_key=key,
                display_name=f"{label or company} — deal"[:80], event_id=event_id)
            created += 0 if existed else 1
            # The deal node carries `created_by_event_id = event_id`, and that is the third arm
            # of the union `backfill_correlations` uses to recover which nodes an event touched.
            # So this event now reaches a deal whether or not the FACT it came from ever recorded
            # its own provenance — which matters, because on real history most of them did not.
            touched_events.add(event_id)
            res = conn.execute(text(
                "update graph_facts set subject_node_id = :d "
                "where org_id = :o and fact_version_id in :ids").bindparams(
                    bindparam("ids", expanding=True)),
                {"d": deal, "o": org_id, "ids": facts_for[company]})
            moved += res.rowcount or 0
            for frm, to, verb in [(company, deal, "owns")] + [
                    (deal, s, "involves") for s in sorted(subjects) if s != company]:
                if store.write_edge(
                        conn, org_id=org_id, edge_type=verb, from_node_id=frm, to_node_id=to,
                        confidence=0.9, occurred_at=None, event_id=event_id,
                        evidence={"derived": "deal backfill"}, source=None, authority_rank=2):
                    edges += 1
    released = _release_stale_correlations(store, org_id, touched_events) if moved else 0
    return {"deal_nodes_created": created, "deal_facts_moved": moved,
            "deal_edges": edges, "deal_facts_orphaned": orphaned,
            "events_released": released, **normalise_deal_status(store, org_id)}


def normalise_deal_status(store, org_id: str) -> dict:
    """Collapse historical `deal.status` onto the controlled open|won|lost every reader assumes.

    `pipeline.py` now normalises at the write, but that only touches new events. History keeps
    whatever the model happened to say — one live tenant holds `lost`, `rejected` and `engaged`
    and not a single `open`, while six `sales_v1` rules and three Sales situations all gate on
    the literal `open`. Nothing errors and nothing fires.

    The model's word is preserved as `deal.stage` rather than discarded: "negotiation" is the
    part a reader actually wants back, and only the STATUS needs collapsing.
    """
    with store.engine.connect() as conn:
        rows = conn.execute(text(
            "select fact_version_id, subject_node_id, value, confidence, relevance, "
            "       occurred_at, created_by_event_id, authority_rank "
            "from graph_facts where org_id = :o and field = 'deal.status' "
            "and valid_to is null and status = 'active'"), {"o": org_id}).all()

    changed = staged = 0
    for r in rows:
        canonical, raw = _normalise_deal_status(r.value)
        if canonical is None or canonical == str(r.value):
            continue
        with store.engine.begin() as conn:
            # `value` is jsonb and `write_fact` stores `json.dumps(value)`, so a bare string
            # here would be invalid JSON and the whole pass would abort on the first row.
            conn.execute(text("update graph_facts set value = cast(:v as jsonb) "
                              "where org_id = :o and fact_version_id = :f"),
                         {"v": json.dumps(canonical), "o": org_id, "f": r.fact_version_id})
            changed += 1
            if raw.lower() != canonical and r.created_by_event_id and store.write_fact(
                    conn, org_id=org_id, subject_node_id=r.subject_node_id, field="deal.stage",
                    value=raw, value_type="string", confidence=float(r.confidence or 0.7),
                    relevance=float(r.relevance or 0.7), occurred_at=r.occurred_at,
                    event_id=r.created_by_event_id, evidence={"derived": "deal.status backfill"},
                    source=None, authority_rank=int(r.authority_rank or 2)):
                staged += 1
    return {"deal_status_normalised": changed, "deal_stage_written": staged}


def _release_stale_correlations(store, org_id: str, event_ids: set[str]) -> int:
    """Un-correlate the events whose node set just changed, so the next pass re-anchors them.

    `backfill_correlations` deliberately skips anything already in `context_correlation_members`,
    which is what makes it safe to re-run. That same guard means a graph correction — a fact
    moving to a node type that outranks the old anchor — would never take effect: the deal nodes
    would exist, the corpus would be waiting, and every situation would still say `opportunity`.

    Scoped to the affected events ONLY. Dropping the tenant's whole correlation set and rebuilding
    would re-anchor history that has nothing to do with deals, change situation ids that signals
    and decisions already reference, and turn a targeted correction into a migration.

    A correlation left with no members is deleted too — `refresh_situations` reads correlations,
    not memberships, so an empty one becomes a situation about nothing that no evidence supports.
    """
    if not event_ids:
        return 0
    with store.engine.begin() as conn:
        res = conn.execute(text(
            "delete from context_correlation_members where org_id = :o and event_id in :ids"
        ).bindparams(bindparam("ids", expanding=True)),
            {"o": org_id, "ids": sorted(event_ids)})
        conn.execute(text(
            "delete from context_situations where org_id = :o and correlation_id in ("
            "  select c.correlation_id from context_correlations c where c.org_id = :o "
            "  and not exists (select 1 from context_correlation_members m "
            "                  where m.org_id = c.org_id and m.correlation_id = c.correlation_id))"),
            {"o": org_id})
        conn.execute(text(
            "delete from context_correlations c where c.org_id = :o "
            "and not exists (select 1 from context_correlation_members m "
            "                where m.org_id = c.org_id and m.correlation_id = c.correlation_id)"),
            {"o": org_id})
    return res.rowcount or 0


def backfill_layer2(store, org_id: str, *, limit: int | None = None,
                    rebuild: bool = False) -> dict:
    """The whole of Layer 2 applied to existing history, in the only order that works."""
    aliases = backfill_aliases(store, org_id)
    # BEFORE correlations, and that ordering is as non-negotiable as the alias one above it.
    # `correlate_event` chooses an anchor from the node types an event touched, and `deal` is
    # first in ANCHOR_PRIORITY — so correlating before the deal nodes exist anchors the same
    # history on `company`, and the pass would have to be redone to change anything.
    deals = backfill_deal_nodes(store, org_id)
    # Deals that were minted just now are new node types on OLD events, and the incremental path
    # cannot re-anchor a thread. On a tenant that already has history this is the difference
    # between the pass reporting success and the pass changing anything.
    correlations = backfill_correlations(
        store, org_id, limit=limit, rebuild=rebuild or bool(deals["deal_nodes_created"]))
    situations = refresh_situations(store, org_id)
    return {**aliases, **deals, **correlations, "situations_written": situations}


# =================================================================================================
# THE NINE BUSINESS NOUNS, ON A GRAPH BUILT BEFORE THEY COULD BE WRITTEN
# =================================================================================================

#: Extractions re-graded per transaction. Same argument as `_BATCH` above; smaller because each
#: one carries a whole message's clean text.
_FACT_BATCH = 100


def _event_parties(conn, *, org_id: str, row) -> tuple[str, ...]:
    """The people this event was between, as graph nodes — by EMAIL and nothing else.

    The only alias that identifies one human on its own. A name is deliberately not tried here:
    `resolve_person_name` answers None where two live people share a name, and a backfill is
    exactly the place where quietly awarding a shared name to the first claimant would write a
    whole tenant's history onto the wrong person at once.
    """
    from genios_engine.context.identity import ALIAS_EMAIL, resolve_alias
    from genios_engine.platform.identity import norm_email

    raw = row["recipients"]
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = [raw]
    addresses = list(raw) if isinstance(raw, list) else []
    if row["actor"]:
        addresses.append(row["actor"])

    found: list[str] = []
    for address in addresses:
        email = norm_email(str(address)) if address and "@" in str(address) else None
        if not email:
            continue
        node = resolve_alias(conn, org_id=org_id, alias_type=ALIAS_EMAIL, alias_key=email)
        if node and node not in found:
            found.append(node)
    return tuple(found)


def backfill_business_facts(store, org_id: str, *, limit: int | None = None) -> dict:
    """Re-grade stored L1 extractions and write the business facts today's code would produce.

    WHY THIS HAS TO EXIST, and it is the module's own argument applied to a later fix. L1 files
    the extractor's UNVERIFIED output in the permanent cache on purpose — an audit and a replay
    need the original — and grades spans on the way OUT of the lane. Layer 2 is a reader too and
    read `l1_extraction_results.output` raw, so every span arrived `verified: false` and
    `_business_claim`, which keeps a fact only with a verified receipt, dropped EVERY business
    fact from every source. `runner.graded_extraction` closed that, and it closed it only for
    events that arrive AFTERWARDS. An event already processed is never processed again, so a
    tenant onboarded before the fix keeps a graph with none of these nouns in it, for ever.

    MEASURED ON THE PILOT, 2026-09-15. The extractor had emitted 1,211 business facts across all
    nine fields; the graph held five. Re-grading the stored extractions against their own
    prepared text verifies 811 of them — 256 of 267 `thread.objective`, 251 of 264 `party.role` —
    with no model call, because the grader is integer work over a string. `thread.objective` in
    particular is what `cohort_outreach_gap` groups on, and the approved corpus card bound to it
    could not fire on a tenant whose graph had zero of them.

    NOTHING IS RE-EXTRACTED AND NOTHING IS GUESSED. The claim, its value and its receipt are the
    ones L1 already published; this re-runs the grading and the resolution, both of which are
    deterministic. A claim whose span still does not resolve is dropped exactly as the live path
    drops it, and a subject that does not resolve to a node of the right type is dropped exactly
    as `_business_subject` drops it — this is the live path, replayed, not a looser one.

    SAFE TO RE-RUN. `write_fact` supersedes on change and no-ops on an unchanged value, so a
    second pass over a backfilled org writes nothing. Returns a census: what was read, what was
    written, and why each of the rest was not.
    """
    from genios_engine.context.pipeline import (FACT_CONF_BY_RANK, _business_claim,
                                                _business_subject, _thread_node)
    from genios_engine.context.runner import graded_extraction

    read = written = 0
    dropped: dict[str, int] = {}
    by_field: dict[str, int] = {}

    def refuse(reason: str) -> None:
        dropped[reason] = dropped.get(reason, 0) + 1

    with store.engine.connect() as conn:
        rows = conn.execute(text(
            # `source_events.parent_object_id` IS the thread, spelled as `runner._process_one`
            # spells it — it hands exactly this column to `process_event(thread_id=...)`, and a
            # backfill that resolved the conversation differently from the live path would write
            # a fact on a subject the live path would never have chosen.
            "select x.event_id as event_id, x.output as output, x.created_at as created_at, "
            "       p.clean_text as clean_text, se.parent_object_id as thread_id, "
            "       se.occurred_at as occurred_at, se.source as source, "
            "       se.recipients as recipients, se.actor as actor "
            "  from l1_extraction_results x "
            "  join prepared_content p on p.event_id = x.event_id and p.org_id = x.org_id "
            "  left join source_events se on se.event_id = x.event_id and se.org_id = x.org_id "
            " where x.org_id = :o order by x.created_at"
            + (" limit :limit" if limit else "")),
            {"o": org_id, **({"limit": int(limit)} if limit else {})}).mappings().all()

    for start in range(0, len(rows), _FACT_BATCH):
        with store.engine.begin() as conn:
            for row in rows[start:start + _FACT_BATCH]:
                raw = row["output"]
                payload = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                if not isinstance(payload, dict) or not payload.get("business_facts"):
                    continue
                graded = graded_extraction(payload, row["clean_text"], row["event_id"])
                claims = getattr(graded, "business_facts", None)
                if not claims:
                    # The whole extraction failed to re-validate. One event's nouns, never the
                    # tenant's — the same asymmetry every reading in this layer holds to.
                    refuse("extraction_unreadable")
                    continue
                occurred = row["occurred_at"] or row["created_at"]
                for claim_in in claims:
                    read += 1
                    candidate = {
                        "field": str(getattr(claim_in, "field", "")),
                        "subject": getattr(claim_in, "subject", None),
                        "value": getattr(claim_in, "value", None),
                        "standing": getattr(claim_in, "standing", None),
                        "evidence_spans": [s.model_dump()
                                           for s in (getattr(claim_in, "evidence", None) or ())],
                    }
                    claim = _business_claim(candidate, row["clean_text"] or "")
                    if claim is None:
                        # No receipt that resolves against the message's own text. The live path
                        # refuses here and so does this: an unverifiable business noun is the one
                        # thing the seam exists to keep out of the graph.
                        refuse("no_verified_span")
                        continue
                    if claim.field == "thread.objective":
                        if claim.subject not in {"thread", row["thread_id"],
                                                 f"thread:{row['thread_id']}"}:
                            refuse("objective_not_about_the_thread")
                            continue
                        subject = _thread_node(store, conn, org_id=org_id,
                                               thread_id=row["thread_id"],
                                               event_id=row["event_id"], counterparty=None)
                        if subject is None:
                            # No thread id on the event: nothing to hang a conversation's
                            # objective on, and the person is the wrong subject for it — that is
                            # the collision `_thread_node` was built to end.
                            refuse("no_thread_node")
                            continue
                        value_text = claim.value if isinstance(claim.value, str) else ""
                    else:
                        subject = _business_subject(conn, org_id=org_id, name=claim.subject,
                                                    field=claim.field)
                        if subject is None:
                            refuse("subject_unresolved")
                            continue
                        # AND ON THE COUNTERPARTY, for `thread.objective` only. The thread node
                        # is the right subject for a conversation's objective — one person spans
                        # 254 threads in the pilot's graph, so writing it on them means whichever
                        # message landed last decides what every conversation was for. But
                        # `read_outreach_cohorts` groups people by objective and compares each
                        # against `thread.days_waiting`, which is a PERSON fact, so an objective
                        # that exists only on threads gives it groups with no waiting state and
                        # it reports nothing. The live path writes both — `pipeline` writes the
                        # objective on the recipient node beside `thread.last_outbound` — and a
                        # backfill that wrote only one of the two would leave the cohort lane
                        # exactly as dead as it found it.
                        for party in _event_parties(conn, org_id=org_id, row=row):
                            store.write_fact(
                                conn, org_id=org_id, subject_node_id=party,
                                field="thread.objective", value=value_text,
                                value_type="string", confidence=FACT_CONF_BY_RANK[1],
                                relevance=1.0, occurred_at=occurred,
                                event_id=row["event_id"], source=row["source"] or "backfill",
                                authority_rank=1,
                                evidence={"text": claim.evidence[0].quote,
                                          "standing": claim.standing,
                                          "spans": [s.model_dump(mode="json")
                                                    for s in claim.evidence]})
                    rank = 2 if claim.standing == "observed" else 1
                    value = (claim.value if isinstance(claim.value, str)
                             else claim.value.model_dump())
                    if store.write_fact(
                            conn, org_id=org_id, subject_node_id=subject, field=claim.field,
                            value=value,
                            value_type="money" if claim.field == "deal.value" else "string",
                            confidence=FACT_CONF_BY_RANK[rank], relevance=1.0,
                            occurred_at=occurred, event_id=row["event_id"],
                            source=row["source"] or "backfill", authority_rank=rank,
                            evidence={"text": claim.evidence[0].quote,
                                      "standing": claim.standing,
                                      "spans": [s.model_dump(mode="json")
                                                for s in claim.evidence]}):
                        written += 1
                        by_field[claim.field] = by_field.get(claim.field, 0) + 1
                    else:
                        # The open version already held exactly this value. Not a loss, and
                        # counted apart from the refusals so it does not read as one.
                        refuse("already_current")

    return {"extractions": len(rows), "claims_read": read, "facts_written": written,
            "by_field": dict(sorted(by_field.items(), key=lambda kv: -kv[1])),
            "dropped": dict(sorted(dropped.items(), key=lambda kv: -kv[1]))}


# =================================================================================================
# CONVERSATIONS NOBODY COULD TELL APART
# =================================================================================================

#: Threads renamed per pass. Bounded for the reason every sweep in this file is.
_NAME_BATCH = 500


def name_thread_nodes(store, org_id: str | None = None, *, limit: int = _NAME_BATCH) -> int:
    """Give every conversation a name a reader can recognise, from what the graph already holds.

    WHY A SWEEP AND NOT ONLY THE WRITE PATH. `name_thread_node` runs where `thread.objective` is
    written, which repairs a conversation the next time anything is extracted from it. The threads
    that most need a name are the ones nobody has written in for months — a card that says "nobody
    answered this in 185 hours" is about a conversation that by definition went quiet — so the lazy
    path reaches precisely the wrong set.

    MEASURED ON THE PILOT, 2026-09-15: 236 threads, 151 named after a hex fragment
    (`Thread 1a07a6e0ca77`) and the remaining 85 sharing labels — all fifteen of one counterparty's
    conversations read `Thread with boardy@boardy.ai`. 31 live cards are anchored on a thread, so
    this is what a third of the deck's headlines say.

    THE COUNTERPARTY IS RESOLVED, NOT GUESSED. It comes from the `corresponded_with` edge the
    pipeline already writes from a person to the thread they were in, and it uses that person's
    DISPLAY NAME — which is a human name rather than an address for the first time, because
    `index_person_names` now registers it. A thread with several correspondents takes the one whose
    edge is oldest: the conversation is named after who it started with, which is stable, rather
    than after whoever wrote most recently, which would rename the card every sweep.

    Safe to re-run: `name_thread_node` promotes only over a label this module generated, so a
    thread named by anything better is left alone and a second pass writes nothing.
    """
    scope = "" if org_id is None else " and t.org_id = :org"
    rows = store.engine.connect().execute(text(
        "select t.org_id as org_id, t.node_id as node_id, t.canonical_key as canonical_key, "
        "       t.display_name as display_name, "
        "       (select f.value from graph_facts f "
        "         where f.org_id = t.org_id and f.subject_node_id = t.node_id "
        "           and f.field = 'thread.objective' and f.status = 'active' "
        "           and f.valid_to is null limit 1) as objective, "
        # OLDEST EDGE WINS — see the docstring. `min(created_at)` rather than any row, so the
        # answer does not depend on which correspondent the planner happened to return first.
        "       (select p.display_name from graph_edges e "
        "          join graph_nodes p on p.org_id = e.org_id and p.node_id = e.from_node_id "
        "                            and p.node_type = 'person' and p.valid_to is null "
        "         where e.org_id = t.org_id and e.to_node_id = t.node_id "
        "           and e.edge_type = 'corresponded_with' and e.valid_to is null "
        "         order by e.created_at, p.node_id limit 1) as party "
        "  from graph_nodes t "
        " where t.node_type = 'thread' and t.valid_to is null"
        f"{scope} order by t.node_id limit :limit"),
        {"limit": int(limit), **({} if org_id is None else {"org": org_id})}).mappings().all()

    renamed = 0
    with store.engine.begin() as conn:
        for row in rows:
            objective = str(row["objective"] or "").strip().strip('"')
            party = str(row["party"] or "").strip()
            # An address is not a name. It is still better than a hex fragment, so it is kept as
            # the counterparty rather than dropped — `index_person_names` will improve it the day
            # the graph learns what this person is called.
            if store.name_thread_node(conn, org_id=row["org_id"], node_id=row["node_id"],
                                      objective=objective or None, counterparty=party or None):
                renamed += 1
    return renamed


def name_company_nodes(store, org_id: str, *, limit: int | None = None) -> dict:
    """Give companies the human name L1 already extracted for them.

    THE DEFECT WAS ONE WORD. L1's entity vocabulary calls a company an `organization`; every branch
    in `pipeline` was written against `company`, and `qes_adapter` copies the type through verbatim
    because it is "intentionally not a semantic translation". So the company branch — the only
    caller of `name_company_node`, which is the only thing that gives a company a human name —
    never fired once. Measured on the pilot 2026-09-15: 337 organization mentions across 147
    distinct names, **48 of 48 company nodes displaying a hostname**, and 19 cards in the deck
    opening on "peakxv.com" rather than "PeakXV".

    `_company_type` closes it for events that arrive afterwards. This is the same argument
    `backfill_business_facts` makes for the nouns: an event already processed is never processed
    again, so a graph built before the fix keeps hostnames for ever while the code that would
    name them is correct.

    NOTHING IS INVENTED AND NO NODE IS CREATED. Each surface form is resolved through
    `resolve_company_mention` — exact key equality against the company's own anchor, refusing where
    two companies contend — and `name_company_node` promotes only while the display name still
    restates that anchor. A company already carrying a human name is left alone.
    """
    from genios_engine.context.identity import observe_company_name, resolve_company_mention

    read = named = 0
    dropped: dict[str, int] = {}

    def refuse(reason: str) -> None:
        dropped[reason] = dropped.get(reason, 0) + 1

    with store.engine.connect() as conn:
        rows = conn.execute(text(
            "select event_id, output from l1_extraction_results where org_id = :o "
            "order by created_at" + (" limit :limit" if limit else "")),
            {"o": org_id, **({"limit": int(limit)} if limit else {})}).mappings().all()

    # ONE NAME PER NODE, DECIDED BEFORE ANYTHING IS WRITTEN. The same company is named in many
    # messages and the spellings differ; taking them in order would let the last message seen
    # decide, and re-running the pass on a different slice would produce a different name. The
    # LONGEST surface form wins — "Titan Capital" over "Titan" — because it is the one that
    # survives `company_slug` with the most of the company's actual name intact.
    best: dict[str, str] = {}
    with store.engine.connect() as conn:
        for row in rows:
            payload = row["output"]
            payload = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
            if not isinstance(payload, dict):
                continue
            for mention in (payload.get("entity_mentions") or ()):
                if not isinstance(mention, dict):
                    continue
                if str(mention.get("entity_type") or "").strip().lower() not in {
                        "organization", "organisation", "company"}:
                    continue
                surface = " ".join(str(mention.get("surface_form") or "").split())
                if not surface:
                    continue
                read += 1
                node = resolve_company_mention(conn, org_id=org_id, name=surface)
                if not node:
                    # No company anchored under that name. The commonest answer by far, and the
                    # correct one: a name nothing is anchored under must not mint a company.
                    refuse("no_company_anchored_under_that_name")
                    continue
                if len(surface) > len(best.get(node, "")):
                    best[node] = surface

    with store.engine.begin() as conn:
        for node, surface in sorted(best.items()):
            observe_company_name(conn, org_id=org_id, node_id=node, name=surface)
            if store.name_company_node(conn, org_id=org_id, node_id=node, name=surface):
                named += 1
            else:
                refuse("already_carries_a_better_name")

    return {"mentions_read": read, "companies_named": named,
            "dropped": dict(sorted(dropped.items(), key=lambda kv: -kv[1]))}
