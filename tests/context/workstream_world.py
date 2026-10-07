"""STEP-09 · the small world the workstream tests share — a tenant, its company brief, and one mail
handed to `context/pipeline.process_event` the way the drain hands it.

Not a test module. Each test file names its own tenant, so files running side by side never meet.
The founder writes from his company address; Introly is the connector the brief names; StartupSetu
is a portal it watches.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.context import pipeline
from genios_engine.context.extract.extractor import Extraction
from genios_engine.contracts.company_brief import CompanyBrief, CompanyBriefLine, compose
from genios_engine.platform.self_identity import identity_for

FOUNDER = "arjun@nimbuslabs.test"
CONNECTOR = "hello@introly.test"
WATCHED = "startupsetu.gov.test"
T0 = datetime(2026, 9, 3, 18, 0, tzinfo=timezone.utc)
UNSUBSCRIBE = {"List-Unsubscribe": "<https://introly.test/u/abc>"}


def brief(org: str, *, connectors=(CONNECTOR,), watchlist=(WATCHED,)) -> CompanyBrief:
    """The brief the founder accepted: each connector by its address, each portal by its domain."""
    lines = [CompanyBriefLine(line_id=f"cbl_c{i}", section="connectors", address=a,
                              text=f"{a.split('@')[1].split('.')[0].title()} — introduces the "
                                   "founder to people")
             for i, a in enumerate(connectors)]
    lines += [CompanyBriefLine(line_id=f"cbl_w{i}", section="watchlist", domain=d,
                               text=f"{d.split('.')[0].title()} — a portal the founder watches")
              for i, d in enumerate(watchlist)]
    return compose(org_id=org, company="Nimbus Labs", founder="Arjun Rao", lines=lines)


def reset(store, org: str) -> None:
    from genios_engine.api.account_routes import _wipe
    with store.engine.begin() as c:
        _wipe(c, org)
        for table in ("context_correlation_members", "context_situations",
                      "context_correlations"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
        c.execute(text("delete from orgs where id = :o"), {"o": org})


def tenant(store, org: str) -> None:
    """A tenant whose founder is us by declaration. `orgs.email` is unique across tenants, so it
    carries a per-tenant address and the founder's own is declared (`org_self_identities`)."""
    reset(store, org)
    with store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"),
                  {"o": org, "e": f"{org}@tenant.test"})
        for kind, value in (("address", FOUNDER), ("domain", FOUNDER.split("@")[1])):
            c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) "
                           "values (:o, :k, :v, 'test')"), {"o": org, "k": kind, "v": value})


def mention(name: str, kind: str = "person") -> dict:
    """An entity mention as `context/qes_adapter` hands it over — quoted from the text."""
    return {"type": kind, "name": name, "email": None, "evidence_text": name}


def extraction(mentions=()) -> Extraction:
    return Extraction(ok=True, relevance=0.9, noise_type="none", domains=[],
                      entity_mentions=list(mentions), fact_candidates=[], commitments=[],
                      questions=[], observations=[])


def ledger(store, org: str, *, event_id: str, sender: str, thread: str | None,
           at: datetime = T0) -> None:
    """The ledger row Layer 1 would have written: a thread is found through it
    (`correlation.thread_correlations` reads `source_events.parent_object_id`), and a rebuild replays
    from it (`context/backfill`)."""
    with store.engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, parent_object_id, dedup_key, actor, occurred_at, captured_at, "
            " outcome) values (:e, :o, 'con_x', 'gmail', 'email_message', :e, :t, :k, "
            " cast(:a as jsonb), :at, :at, 'emitted') on conflict do nothing"),
            {"e": event_id, "o": org, "t": thread, "k": f"gmail:email_message:{event_id}",
             "a": json.dumps({"type": "external_contact", "email": sender}), "at": at})


def process(store, org: str, *, event_id: str, sender: str, recipients=(FOUNDER,),
            sender_name: str | None = None, thread: str | None = None, headers=None,
            mentions=(), company_brief: CompanyBrief | None = None,
            at: datetime = T0, content: str | None = None, availability_marker: str | None = None):
    """One mail through the pipeline, as `context/runner` hands it: who is us read once, the
    company brief beside it, the stored payload as `canon_meta`. The text names every mention —
    a mention the text does not carry is ungrounded and never reaches the graph."""
    us = identity_for(store, org)
    content = content or ("A note. " + " ".join(m["name"] for m in mentions)).strip()
    ledger(store, org, event_id=event_id, sender=sender, thread=thread, at=at)
    return pipeline.process_event(
        org_id=org, event_id=event_id, source="gmail", content=content, sender_email=sender,
        sender_name=sender_name, recipient_emails=list(recipients), occurred_at=at,
        llm=None, store=store, is_inbound=sender != FOUNDER,
        internal_emails=us.addresses, self_identity=us, thread_id=thread,
        canon_meta={"headers": dict(headers or {})}, qualified_extraction=extraction(mentions),
        company_brief=company_brief, availability_marker=availability_marker)


def anchors(store, org: str, event_id: str) -> set[str]:
    """The canonical keys of the nodes this event's files are anchored on."""
    with store.engine.connect() as c:
        return {r.canonical_key for r in c.execute(text(
            "select n.canonical_key from context_correlation_members m "
            "  join context_correlations k on k.org_id = m.org_id "
            "       and k.correlation_id = m.correlation_id "
            "  join graph_nodes n on n.org_id = k.org_id and n.node_id = k.anchor_node_id "
            "       and n.valid_to is null "
            " where m.org_id = :o and m.event_id = :e"), {"o": org, "e": event_id})}


def node(store, org: str, key: str):
    with store.engine.connect() as c:
        return c.execute(text(
            "select node_id, node_type, display_name from graph_nodes "
            " where org_id = :o and canonical_key = :k and valid_to is null"),
            {"o": org, "k": key}).first()


def _loaded(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def facts(store, org: str, key: str, field: str) -> list:
    """Every current fact of `field` on the node keyed `key`, each with the evidence it was
    written with (`graph_source_refs`)."""
    with store.engine.connect() as c:
        rows = c.execute(text(
            "select f.value, r.evidence from graph_facts f "
            "  join graph_nodes n on n.org_id = f.org_id and n.node_id = f.subject_node_id "
            "       and n.valid_to is null "
            "  left join graph_source_refs r on r.org_id = f.org_id "
            "       and r.fact_version_id = f.fact_version_id "
            " where f.org_id = :o and n.canonical_key = :k and f.field = :f "
            "   and f.valid_to is null"), {"o": org, "k": key, "f": field}).fetchall()
    return [(_loaded(r.value), _loaded(r.evidence) or {}) for r in rows]


def noise(store, org: str, event_id: str) -> list[str]:
    """The kinds of the noise or relevance record an event left on its sender."""
    with store.engine.connect() as c:
        return sorted(r.kind for r in c.execute(text(
            "select kind from graph_observations where org_id = :o and created_by_event_id = :e "
            "   and (kind like 'email_noise:%' or kind = 'email_relevance')"),
            {"o": org, "e": event_id}))


def edges(store, org: str, edge_type: str) -> set[tuple[str, str]]:
    """Every live edge of `edge_type`, as (from key, to key)."""
    with store.engine.connect() as c:
        return {(r.a, r.b) for r in c.execute(text(
            "select fa.canonical_key as a, fb.canonical_key as b from graph_edges e "
            "  join graph_nodes fa on fa.org_id = e.org_id and fa.node_id = e.from_node_id "
            "       and fa.valid_to is null "
            "  join graph_nodes fb on fb.org_id = e.org_id and fb.node_id = e.to_node_id "
            "       and fb.valid_to is null "
            " where e.org_id = :o and e.edge_type = :t and e.valid_to is null"),
            {"o": org, "t": edge_type})}


def later(days: float) -> datetime:
    return T0 + timedelta(days=days)
