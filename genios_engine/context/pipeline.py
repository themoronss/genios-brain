from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from genios_engine.context.extract.extractor import Extraction, extract
from genios_engine.context.graph_store import GraphStore
from genios_engine.context.guard import _norm, keep_grounded
from genios_engine.context.llm.client import LLMClient

_WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
             "friday": 4, "saturday": 5, "sunday": 6}


def parse_due(text: str | None, base: datetime) -> datetime | None:
    """Best-effort due-date from a commitment's due_text (ISO or common relatives), so
    L3's commitment rules have a real `commitment.due_at`. Deterministic; None if unclear."""
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        pass
    t = text.strip().lower()
    if "today" in t or "eod" in t or "aaj" in t:
        return base.replace(hour=18, minute=0, second=0, microsecond=0)
    if "tomorrow" in t or "kal" in t:
        return base + timedelta(days=1)
    if "next week" in t or "agle hafte" in t:
        return base + timedelta(days=7)
    m = re.search(r"in (\d+) day", t)
    if m:
        return base + timedelta(days=int(m.group(1)))
    for name, wd in _WEEKDAYS.items():
        if name in t:
            return base + timedelta(days=((wd - base.weekday()) % 7) or 7)
    return None

# B0→B7 orchestrator for ONE emitted event. Relevance-gated commit: the LLM's relevance
# judgment decides whether facts enter the graph (below the floor = parked, not committed
# — this is where the "20% memory" cut actually happens). Every committed fact/observation
# is evidence-grounded (B4) and versioned + provenanced (B7).

RELEVANCE_FLOOR = 0.35
PROMPT_VERSION = "b3-1"


@dataclass
class L2Result:
    event_id: str
    outcome: str                 # committed | parked_low_relevance | extract_failed
    relevance: float = 0.0
    nodes: int = 0
    facts: int = 0
    observations: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    graph_version: int | None = None
    cached: bool = False
    primary_node: str | None = None


def _from_cache(d: dict) -> Extraction:
    return Extraction(
        relevance=float(d.get("relevance", 0.0) or 0.0),
        noise_type=d.get("noise_type", "none"), domains=d.get("domains", []),
        entity_mentions=d.get("entity_mentions", []), fact_candidates=d.get("fact_candidates", []),
        commitments=d.get("commitments", []), questions=d.get("questions", []),
        observations=d.get("observations", []), ok=True)


def _to_cache(ex: Extraction) -> dict:
    return {"relevance": ex.relevance, "noise_type": ex.noise_type, "domains": ex.domains,
            "entity_mentions": ex.entity_mentions, "fact_candidates": ex.fact_candidates,
            "commitments": ex.commitments, "questions": ex.questions,
            "observations": ex.observations}


def _resolve_subject(name, name_to_node: dict, fallback: str | None) -> str | None:
    if name and _norm(str(name)) in name_to_node:
        return name_to_node[_norm(str(name))]
    return fallback


def process_event(*, org_id: str, event_id: str, source: str, content: str,
                  sender_email: str | None, occurred_at: datetime | None,
                  llm: LLMClient, store: GraphStore, is_inbound: bool = False) -> L2Result:
    # replay cache — identical content+prompt → reuse, no re-call, deterministic. The key is
    # ORG-SCOPED (org_id in the hash) so tenant A's cached extraction can never be served to
    # tenant B on byte-identical content (e.g. the same newsletter) — the cross-tenant leak fix.
    key = LLMClient.content_hash(f"{org_id}:{PROMPT_VERSION}:{content}")
    cached = store.cache_get(key, org_id=org_id)
    if cached is not None:
        ex, is_cached = _from_cache(cached), True
    else:
        ex, is_cached = extract(llm, source=source, content=content), False
        store.record_cost(org_id=org_id, model=llm.model, purpose="extract",
                          input_tokens=ex.input_tokens, output_tokens=ex.output_tokens,
                          success=ex.ok, error=ex.error, event_id=event_id)
        if not ex.ok:
            return L2Result(event_id, "extract_failed", input_tokens=ex.input_tokens,
                            output_tokens=ex.output_tokens)
        store.cache_set(processing_key=key, org_id=org_id, event_id=event_id,
                        output=_to_cache(ex), input_tokens=ex.input_tokens,
                        output_tokens=ex.output_tokens, model=llm.model)

    if ex.relevance < RELEVANCE_FLOOR:      # relevance-gated commit — the memory cut
        return L2Result(event_id, "parked_low_relevance", ex.relevance,
                        input_tokens=ex.input_tokens, output_tokens=ex.output_tokens,
                        cached=is_cached)

    # B4 guard — keep only candidates that quote the source exactly
    ents = keep_grounded(content, ex.entity_mentions)
    facts = keep_grounded(content, ex.fact_candidates)
    obs = keep_grounded(content, ex.observations)

    with store.engine.begin() as conn:          # one transaction (B7)
        version = store.bump_version(conn, org_id)
        name_to_node: dict[str, str] = {}
        nodes = 0
        sender_node = None
        if sender_email:
            sender_node = store.find_or_create_node(
                conn, org_id=org_id, node_type="person", canonical_key=sender_email.lower(),
                display_name=sender_email, event_id=event_id)
            nodes += 1
        for e in ents:                          # B5 resolve — deterministic anchors only
            email = (str(e.get("email") or "").lower() or None)
            name = e.get("name")
            nid = store.find_or_create_node(
                conn, org_id=org_id, node_type=str(e.get("type") or "person"),
                canonical_key=email, display_name=name or email, event_id=event_id)
            nodes += 1
            if name:
                name_to_node[_norm(str(name))] = nid
            if email:
                name_to_node[_norm(email)] = nid
        fact_n = 0
        for f in facts:
            subj = _resolve_subject(f.get("subject"), name_to_node, sender_node)
            if subj is None:
                continue
            wrote = store.write_fact(conn, org_id=org_id, subject_node_id=subj,
                                     field=str(f.get("field") or "note"), value=f.get("value"),
                                     value_type="string", confidence=ex.relevance,
                                     occurred_at=occurred_at, event_id=event_id,
                                     evidence={"text": f.get("evidence_text")}, source=source,
                                     authority_rank=2)   # R2: direct evidence-backed
            if wrote:
                fact_n += 1
        obs_n = 0
        for o in obs:
            store.write_observation(conn, org_id=org_id, subject_node_id=sender_node,
                                    kind=str(o.get("kind") or "note"), confidence=ex.relevance,
                                    occurred_at=occurred_at, event_id=event_id,
                                    evidence={"text": o.get("evidence_text")}, source=source)
            obs_n += 1

        # thread state (direction-derived, deterministic) → feeds L3's unanswered_email
        if is_inbound and sender_node and occurred_at is not None:
            store.write_fact(conn, org_id=org_id, subject_node_id=sender_node,
                             field="thread.last_inbound", value=occurred_at.isoformat(),
                             value_type="timestamp", confidence=1.0, occurred_at=occurred_at,
                             event_id=event_id, evidence={"derived": "inbound event"},
                             source=source, authority_rank=2)
            store.write_fact(conn, org_id=org_id, subject_node_id=sender_node,
                             field="thread.ball_in_court", value="us", value_type="enum",
                             confidence=1.0, occurred_at=occurred_at, event_id=event_id,
                             evidence={"derived": "last message inbound"}, source=source,
                             authority_rank=2)

        # commitments → commitment.due_at (best-effort due) → feeds L3's commitment rules
        for cm in keep_grounded(content, ex.commitments):
            subj = _resolve_subject(cm.get("actor"), name_to_node, sender_node)
            due = parse_due(cm.get("due_text"), occurred_at) if occurred_at else None
            if subj and due:
                store.write_fact(conn, org_id=org_id, subject_node_id=subj,
                                 field="commitment.due_at", value=due.isoformat(),
                                 value_type="timestamp", confidence=ex.relevance, occurred_at=due,
                                 event_id=event_id, evidence={"text": cm.get("evidence_text")},
                                 source=source, authority_rank=2)

        store.write_change(conn, org_id=org_id, graph_version=version, cause_event_id=event_id,
                           payload={"nodes": nodes, "facts": fact_n, "observations": obs_n})

    return L2Result(event_id, "committed", ex.relevance, nodes=nodes, facts=fact_n,
                    observations=obs_n, input_tokens=ex.input_tokens,
                    output_tokens=ex.output_tokens, graph_version=version, cached=is_cached,
                    primary_node=sender_node)
