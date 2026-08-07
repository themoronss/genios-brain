"""Company knowledge — the WRITING door into Layer 1's Internal Sources family.

The upload door (upload_routes) takes a file the company already has. This one takes
what is only in someone's head: the refund policy, how onboarding actually runs, what
the Q3 goal is. Both land through `capture_event` like a connector sync, and both enter
at authority rank 4 — above a system of record. See capture.internal_knowledge for why.

An assertion has an identity (`key`, defaulted from the title), so editing a policy
SUPERSEDES it rather than leaving two contradictory versions in the graph. Re-submitting
unchanged content is a no-op duplicate, not a re-land.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from genios_engine.capture.internal_knowledge import INTERNAL_KINDS, normalize_kind
from genios_engine.platform.auth import get_current_org
from genios_engine.platform.logging import get_logger
from genios_engine.platform.wiring import (make_graph_store, make_payload_store,
                                           make_prepared_store, make_repo,
                                           make_trace_repo)

router = APIRouter()
_log = get_logger("genios.knowledge")
_graph = make_graph_store()
_payloads = make_payload_store()
_repo = make_repo()
_prepared = make_prepared_store()
_trace_repo = make_trace_repo()


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    """Resolve the tenant from the credential; refuse a path that names a different org."""
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


class KnowledgeIn(BaseModel):
    kind: str = Field(description="one of capture.internal_knowledge.INTERNAL_KINDS")
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=200_000)
    key: str | None = Field(
        default=None, max_length=80,
        description="stable identity of the assertion; defaults to a slug of the title. "
                    "Pass it when the title changes but the subject does not.")


@router.get("/api/org/{org_id}/knowledge/kinds")
def list_kinds(org_id: str, org: str = Depends(_org)) -> dict:
    """The vocabulary the compose form offers. Served from the same constant capture
    validates against, so the UI cannot drift into offering a kind the door refuses."""
    return {"kinds": sorted(INTERNAL_KINDS)}


@router.post("/api/org/{org_id}/knowledge")
def write_knowledge(org_id: str, body: KnowledgeIn, org: str = Depends(_org)) -> dict:
    """Write one piece of company canon into the graph's world."""
    kind = normalize_kind(body.kind)
    if kind is None:
        raise HTTPException(422, {"error": "unknown_kind", "kind": body.kind,
                                  "expected": sorted(INTERNAL_KINDS)})

    author = None
    if _graph is not None:
        with _graph.engine.connect() as c:
            author = c.execute(text("select email from orgs where id=:o"), {"o": org}).scalar()

    from genios_engine.capture.intake import ingest_internal_knowledge
    result = ingest_internal_knowledge(
        org_id=org, kind=kind, title=body.title, body=body.body, key=body.key,
        author_email=author, repo=_repo, payload_store=_payloads,
        prepared_store=_prepared, trace_repo=_trace_repo)

    from genios_engine.platform.audit import record
    record(org, "data_written", actor_type="user", actor_id=author or org,
           target_type="knowledge", target_id=result.event.dedup_key,
           metadata={"kind": kind, "title": body.title, "outcome": result.outcome})

    # `duplicate` is a SUCCESS: the org re-submitted content it had already asserted, so
    # the graph already holds it. Reporting it as an error would push users to edit text
    # meaninglessly just to make the button work.
    return {"kind": kind, "outcome": result.outcome, "event_id": result.event.event_id,
            "unchanged": result.outcome == "duplicate"}


@router.get("/api/org/{org_id}/knowledge")
def list_knowledge(org_id: str, org: str = Depends(_org)) -> dict:
    """Every piece of company canon this org has written — latest version per entry (an edit
    SUPERSEDES, it doesn't stack, so we show one row per assertion). The compose UI needs this to
    see + manage what's stored; before, knowledge could be written but never viewed or removed
    while uploads had both. `key` ({kind}:{slug}) is stable across edits — pass it to DELETE."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            "select distinct on (source_object_id) source_object_id, object_type, occurred_at "
            "from source_events where org_id=:o and source='internal' "
            "order by source_object_id, occurred_at desc"), {"o": org}).fetchall()
    items = []
    for r in rows:
        slug = r.source_object_id.split(":", 1)[1] if ":" in r.source_object_id else r.source_object_id
        items.append({
            "key": r.source_object_id,
            "kind": r.object_type,
            "title": slug.replace("-", " ").strip().title() or slug,
            "updated_at": r.occurred_at.isoformat() if r.occurred_at else None,
        })
    items.sort(key=lambda x: x["updated_at"] or "", reverse=True)
    return {"knowledge": items}


@router.delete("/api/org/{org_id}/knowledge/{key}")
def delete_knowledge(org_id: str, key: str, org: str = Depends(_org)) -> dict:
    """Remove a written assertion + everything learned from it (facts, observations, capture
    artifacts), bumping the tenant graph version in the SAME txn (L4 holds a shared lock while
    publishing, so an erasure never commits mid-reasoning). `key` is the value list returns
    ({kind}:{slug}). Mirrors upload deletion; shared graph_nodes are left in place."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    with _graph.engine.begin() as c:
        evids = [row.event_id for row in c.execute(text(
            "select event_id from source_events where org_id=:o and source='internal' "
            "and source_object_id=:k"), {"o": org, "k": key})]
        if not evids:
            raise HTTPException(404, {"error": "not_found", "message": "knowledge entry not found"})
        _graph.bump_version(c, org)
        c.execute(text("delete from graph_facts where org_id=:o and created_by_event_id = any(:e)"),
                  {"o": org, "e": evids})
        c.execute(text("delete from graph_observations where org_id=:o and created_by_event_id = any(:e)"),
                  {"o": org, "e": evids})
        c.execute(text("delete from raw_payloads where org_id=:o and event_id = any(:e)"),
                  {"o": org, "e": evids})
        c.execute(text("delete from prepared_content where org_id=:o and event_id = any(:e)"),
                  {"o": org, "e": evids})
        c.execute(text("delete from source_events where org_id=:o and event_id = any(:e)"),
                  {"o": org, "e": evids})
    from genios_engine.platform.audit import record
    record(org, "data_subject_erasure", actor_type="user", target_type="knowledge", target_id=key,
           metadata={"events_removed": len(evids)})
    return {"deleted": True, "events_removed": len(evids)}
