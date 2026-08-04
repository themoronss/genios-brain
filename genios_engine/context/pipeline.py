from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from genios_engine.capture.structured.apply import _PERSONAL_DOMAINS
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

# B0→B7 orchestrator for ONE emitted event. STORE-DON'T-DELETE: the LLM extracts AND scores
# relevance, but relevance is a SCORE, not a delete gate — every grounded fact/observation is
# committed, tagged with that relevance as its confidence, so L3/queries can RANK (not lose) it.
# ("Partial data se intelligence nahi aati.") Junk is rejected upstream at L1 (Gmail SPAM/TRASH),
# never silently here. Every committed fact is evidence-grounded (B4) and versioned+provenanced (B7).

# Downstream RANKING reference only (NOT a commit gate): facts below this relevance are low-priority
# for surfacing, but are still stored and queryable.
RELEVANCE_FLOOR = 0.35
PROMPT_VERSION = "b3-1"
# email classes that carry no real relationship → no structural graph (newsletters, bots, spam).
# NOTE: "personal" is NOT here — a personal 1:1 email is still a real correspondence edge.
_NOISE_TYPES = {"newsletter", "automated", "spam"}
_MAX_RECIPIENTS = 25          # cap fan-out from a mass To/Cc so one email can't explode the graph


def _company_domain(email: str | None) -> str | None:
    """Work domain from an email → a company canonical_key. None for personal providers
    (gmail/outlook/…) and malformed addresses, so we never create a 'gmail.com' company."""
    if not email or "@" not in email:
        return None
    dom = email.rsplit("@", 1)[1].strip().lower()
    return None if (not dom or dom in _PERSONAL_DOMAINS) else dom


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
                  llm: LLMClient, store: GraphStore, is_inbound: bool = False,
                  recipient_emails: list[str] | None = None) -> L2Result:
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

    # RELEVANCE IS A SCORE, NOT A DELETE GATE. The Haiku call already extracted AND scored this
    # email — so we PERSIST all of it, tagged with that relevance (→ each fact's confidence), and
    # let L3/queries RANK by it. Nothing readable is thrown away at L2. "Partial data se intelligence
    # nahi aati." True junk is rejected upstream at L1 (Gmail SPAM/TRASH label), not silently here.
    #   • noise_type (newsletter/automated/spam) → a STORED flag; we skip only the network EDGES
    #     for it (you don't "correspond with" a newsletter) but still keep its facts/entities.
    #   • relevance is NOT a floor anymore — low-relevance facts land with low confidence, present
    #     and queryable, never deleted.
    is_noise = ex.noise_type in _NOISE_TYPES

    # B4 guard — keep candidates that quote the source (anti-hallucination — so garbage doesn't
    # enter, but nothing relevant is dropped by a relevance score).
    ents = keep_grounded(content, ex.entity_mentions)
    facts = keep_grounded(content, ex.fact_candidates)
    obs = keep_grounded(content, ex.observations)

    with store.engine.begin() as conn:          # one transaction (B7)
        version = store.bump_version(conn, org_id)
        name_to_node: dict[str, str] = {}
        nodes = 0
        edge_n = 0

        def _person(email: str) -> str:
            return store.find_or_create_node(
                conn, org_id=org_id, node_type="person", canonical_key=email.lower(),
                display_name=email, event_id=event_id)

        def _works_at(email: str, person_node: str) -> None:
            """person → works_at → company(domain). Groups everyone at 3one4/kurral/… together."""
            nonlocal edge_n
            dom = _company_domain(email)
            if not dom:
                return
            company = store.find_or_create_node(
                conn, org_id=org_id, node_type="company", canonical_key=dom,
                display_name=dom, event_id=event_id)
            if store.write_edge(conn, org_id=org_id, edge_type="works_at",
                                from_node_id=person_node, to_node_id=company, confidence=0.9,
                                occurred_at=occurred_at, event_id=event_id,
                                evidence={"derived": "email domain", "domain": dom},
                                source=source, authority_rank=2):
                edge_n += 1

        sender_norm = (sender_email or "").lower()
        sender_node = None
        if sender_email:                        # always — facts/observations attach to this node
            sender_node = _person(sender_email)
            nodes += 1

        # NETWORK edges (who↔whom, who works where) — built for real correspondence only, skipped
        # for noise so newsletters don't pollute the relationship graph. Content above is kept
        # either way; this gate is about the NETWORK, not about deleting data.
        if not is_noise:
            if sender_node:
                _works_at(sender_email, sender_node)
            # recipients (To + Cc) → person nodes + sender↔recipient correspondence + affiliation.
            # This is exactly what was missing — a thread with Piyush left him with only a calendar
            # edge; now every message links the people.
            for rcpt in (recipient_emails or [])[:_MAX_RECIPIENTS]:
                rn_email = rcpt.lower()
                if not rn_email or rn_email == sender_norm:
                    continue
                rnode = _person(rn_email)
                nodes += 1
                _works_at(rn_email, rnode)
                if sender_node:
                    # canonicalise pair direction (lexically smaller email = from) → ONE edge per
                    # pair, so A→B and B→A on later emails stay idempotent (no duplicate edges)
                    frm, to = ((sender_node, rnode) if sender_norm < rn_email
                               else (rnode, sender_node))
                    if store.write_edge(conn, org_id=org_id, edge_type="corresponded_with",
                                        from_node_id=frm, to_node_id=to, confidence=1.0,
                                        occurred_at=occurred_at, event_id=event_id,
                                        evidence={"derived": "email to/cc"}, source=source,
                                        authority_rank=2):
                        edge_n += 1

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

        # per-email relevance recorded as an append-only signal so L3/queries can RANK — the
        # "score, don't delete" record: even a low-relevance email leaves its score, never a gap.
        if sender_node:
            store.write_observation(
                conn, org_id=org_id, subject_node_id=sender_node,
                kind=("email_noise:" + ex.noise_type) if is_noise else "email_relevance",
                confidence=ex.relevance, occurred_at=occurred_at, event_id=event_id,
                evidence={"relevance": ex.relevance, "noise_type": ex.noise_type}, source=source)
            obs_n += 1

        # thread state (direction-derived, deterministic) → feeds L3's unanswered_email.
        # Skip for noise (a newsletter doesn't put the ball in our court).
        if is_inbound and sender_node and occurred_at is not None and not is_noise:
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

        # commitments → commitment.due_at (best-effort due) → feeds L3's commitment rules.
        # Stored for every email (confidence = relevance), never gated away.
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
                           payload={"nodes": nodes, "edges": edge_n, "facts": fact_n,
                                    "observations": obs_n})

    # Everything readable is stored (facts tagged with relevance as confidence); nothing is
    # deleted by a relevance score. Ranking happens downstream (L3/queries), not by dropping here.
    return L2Result(event_id, "committed", ex.relevance, nodes=nodes, facts=fact_n,
                    observations=obs_n, input_tokens=ex.input_tokens,
                    output_tokens=ex.output_tokens, graph_version=version, cached=is_cached,
                    primary_node=sender_node)
