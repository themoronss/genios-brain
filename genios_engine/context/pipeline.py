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
# P1 — node-type whitelist. An LLM entity_mention becomes a first-class graph NODE only if its type
# is a person WITH an email (a deterministic anchor). Anything else (product/system/organization/
# tool/event, or an anchorless person/company mention) is recorded as a `mention:<type>` observation
# on the sender — data kept + queryable, but no orphan node (the SAP/OpenClaw dead-dots go away).
# This whitelist governs ONLY the L2 mention loop below; the structured lane (deal/meeting/
# subscription/product_account, anchored by source-id) is NOT gated here.
_NODE_TYPES = {"person", "company", "deal", "meeting", "commitment", "thread", "document", "agent"}
_MAX_RECIPIENTS = 25          # cap fan-out from a mass To/Cc so one email can't explode the graph
_BULK_RECIPIENTS = 10         # P2 — above this many recipients an email is a bulk blast: skip
                              # per-recipient nodes/edges (not 1:1 relationships). HYP, tune in shadow.


def _company_domain(email: str | None) -> str | None:
    """Work domain from an email → a company canonical_key. None for personal providers
    (gmail/outlook/…) and malformed addresses, so we never create a 'gmail.com' company."""
    if not email or "@" not in email:
        return None
    dom = email.rsplit("@", 1)[1].strip().lower()
    return None if (not dom or dom in _PERSONAL_DOMAINS) else dom


def _norm_email(email: str | None) -> str | None:
    """P5 — canonical email key: lowercase + trim + strip a +tag suffix from the local part, so
    priya+vendors@x.com and priya@x.com resolve to ONE person node. None for malformed input.
    Merge stays deterministic (exact key only); no fuzzy-name merge is ever done."""
    if not email or "@" not in email:
        return None
    local, _, dom = str(email).strip().lower().partition("@")
    local = local.split("+", 1)[0]
    return f"{local}@{dom}" if local and dom else None


# F2 — obs-kind normalizer. The LLM emits free-form observation kinds; sales rules read exact
# canonical strings (has_obs "competitor"/"objection_price"/…). Mapping synonyms → canonical HERE
# (at commit) makes the deep sales corpus fire deterministically instead of by LLM lottery, and
# works on both new events and a cache-replay rebuild. Unknown kinds pass through unchanged
# (stored under their own name — never dropped). Canonical set mirrors signals_derived POS/NEG_OBS.
_OBS_CANON = {
    # buying
    "budget_approved": "budget_approved", "budget_confirmed": "budget_approved",
    "has_budget": "budget_approved", "budget_available": "budget_approved",
    "verbal_yes": "verbal_yes", "verbal_commitment": "verbal_yes", "agreed_to_proceed": "next_step_agreed",
    "next_step_agreed": "next_step_agreed", "next_steps_agreed": "next_step_agreed",
    "contract_requested": "contract_requested", "send_contract": "contract_requested",
    "msa_requested": "contract_requested", "order_form_requested": "contract_requested",
    "security_review_started": "security_review_started", "security_review": "security_review_started",
    "security_questionnaire": "security_review_started", "vendor_review": "security_review_started",
    "stakeholder_added": "stakeholder_added", "looping_in": "stakeholder_added", "new_stakeholder": "stakeholder_added",
    "demo_requested": "demo_requested", "demo_request": "demo_requested",
    # stage / pricing
    "pricing_discussed": "pricing_discussed", "pricing_shared": "pricing_discussed",
    "proposal_sent": "proposal_sent", "quote_sent": "proposal_sent", "proposal_shared": "proposal_sent",
    # risk
    "competitor": "competitor", "competitor_mention": "competitor", "competitor_mentioned": "competitor",
    "other_vendor": "competitor", "rival": "competitor", "alternative_vendor": "competitor",
    "discount_pressure": "discount_pressure", "discount": "discount_pressure", "price_reduction_request": "discount_pressure",
    "budget_freeze": "budget_freeze", "budget_frozen": "budget_freeze", "spending_freeze": "budget_freeze", "budget_on_hold": "budget_freeze",
    "champion_change": "champion_change", "champion_left": "champion_change",
    "champion_leaving": "champion_change", "stakeholder_left": "champion_change",
    "legal_review": "legal_review", "redlines": "legal_review", "legal_in_review": "legal_review", "contract_in_legal": "legal_review",
    "timeline_slip": "timeline_slip", "timeline_delay": "timeline_slip", "pushed_timeline": "timeline_slip",
    "going_dark": "going_dark", "closed_lost_mention": "closed_lost_mention", "closed_lost": "closed_lost_mention",
    # objection (typed)
    "objection": "objection", "concern": "objection",
    "objection_price": "objection_price", "price_objection": "objection_price", "too_expensive": "objection_price",
    "objection_timing": "objection_timing", "timing_objection": "objection_timing",
    "objection_security": "objection_security", "objection_authority": "objection_authority",
    "objection_integration": "objection_integration",
    # sentiment
    "positive_reply": "positive_reply", "negative_reply": "negative_reply", "price_pushback": "price_pushback",
    "buying_intent": "buying_intent", "churn_risk": "churn_risk",
}


def norm_obs_kind(kind) -> str:
    """Synonym → canonical obs kind. Lowercased, spaces/hyphens → underscores; unknown kinds kept."""
    k = str(kind or "note").strip().lower().replace(" ", "_").replace("-", "_")
    return _OBS_CANON.get(k, k)


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
                  recipient_emails: list[str] | None = None,
                  internal_emails: frozenset[str] | None = None) -> L2Result:
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
        obs_n = 0

        def _person(email: str) -> str:
            return store.find_or_create_node(
                conn, org_id=org_id, node_type="person",
                canonical_key=(_norm_email(email) or email.strip().lower()),
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

        sender_norm = _norm_email(sender_email) or (sender_email or "").strip().lower()
        internal_set = internal_emails or frozenset()
        sender_node = None
        # P2 — a NODE means a real relationship. A noise sender (newsletter/automated/spam) does
        # NOT become a person/company node; the email stays in the L1 ledger (recoverable), out of
        # the graph. A real sender (incl. a personal 1:1) still anchors its facts/observations.
        if sender_email and not is_noise:
            sender_node = _person(sender_email)
            nodes += 1

        # NETWORK edges (who↔whom, who works where) — built for real correspondence only, skipped
        # for noise so newsletters don't pollute the relationship graph. Content above is kept
        # either way; this gate is about the NETWORK, not about deleting data.
        if not is_noise:
            if sender_node:
                _works_at(sender_email, sender_node)
            # recipients (To + Cc) → person nodes + sender↔recipient correspondence + affiliation.
            # P2 — skip per-recipient nodes on a mass fan-out (a large To/Cc blast is not a set of
            # 1:1 relationships); small/direct threads still link everyone. Bulk lists stay in the
            # L1 ledger, out of the graph.
            recips = recipient_emails or []
            for rcpt in ([] if len(recips) > _BULK_RECIPIENTS else recips[:_MAX_RECIPIENTS]):
                rn_email = _norm_email(rcpt) or rcpt.strip().lower()
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
                # OUTBOUND RESET: we just replied to this person → the ball moves to THEIR court.
                # Without this, unanswered_email kept firing forever after we'd already answered,
                # because nothing ever flipped ball_in_court back — the "still shows as unanswered
                # after I replied" bug. Skipped for internal teammates (not a prospect thread) and
                # for noise (an outbound auto-reply doesn't count as answering).
                if (not is_inbound and not is_noise and occurred_at is not None
                        and rn_email not in internal_set):
                    store.write_fact(conn, org_id=org_id, subject_node_id=rnode,
                                     field="thread.last_outbound", value=occurred_at.isoformat(),
                                     value_type="timestamp", confidence=max(ex.relevance, 0.05),
                                     occurred_at=occurred_at, event_id=event_id,
                                     evidence={"derived": "outbound event"}, source=source,
                                     authority_rank=2)
                    store.write_fact(conn, org_id=org_id, subject_node_id=rnode,
                                     field="thread.ball_in_court", value="them", value_type="enum",
                                     confidence=max(ex.relevance, 0.05), occurred_at=occurred_at,
                                     event_id=event_id, evidence={"derived": "we replied"},
                                     source=source, authority_rank=2)

        # B5 resolve — P1 anchor rule. A mention becomes a NODE only when it is a person WITH an
        # email (deterministic anchor). Anchorless mentions (companies/products/tools/systems, or
        # people with no email) do NOT get their own node — they land as a `mention:<type>`
        # observation on the sender, and their name maps to the sender so any fact_candidate about
        # them attaches to an anchored node (fallback is already sender). Kills the orphan
        # SAP/OpenClaw/Product/System nodes without losing a single extracted fact.
        for e in ents:
            etype = str(e.get("type") or "person").strip().lower()
            email = _norm_email(e.get("email"))
            name = e.get("name")
            if etype == "person" and email:                  # anchored contact → real node
                nid = store.find_or_create_node(
                    conn, org_id=org_id, node_type="person", canonical_key=email,
                    display_name=name or email, event_id=event_id)
                nodes += 1
                name_to_node[_norm(email)] = nid
                if name:
                    name_to_node[_norm(str(name))] = nid
                if not is_noise:
                    _works_at(email, nid)                    # affiliation from a real anchor
            elif name and sender_node:                       # anchorless mention → context on sender
                store.write_observation(
                    conn, org_id=org_id, subject_node_id=sender_node,
                    kind="mention:" + (etype if etype in _NODE_TYPES else "entity"),
                    confidence=ex.relevance, occurred_at=occurred_at, event_id=event_id,
                    evidence={"name": name, "type": etype, "text": e.get("evidence_text")},
                    source=source)
                obs_n += 1
                name_to_node.setdefault(_norm(str(name)), sender_node)
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
        for o in obs:
            store.write_observation(conn, org_id=org_id, subject_node_id=sender_node,
                                    kind=norm_obs_kind(o.get("kind")), confidence=ex.relevance,
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
        # Skip for noise (a newsletter doesn't put the ball in our court) and for internal
        # teammates (an internal reply isn't a prospect thread we owe an external reply on).
        # Confidence = this email's actual relevance (was hardcoded 1.0) — so a low-relevance
        # inbound message (off-topic, low-signal) scores a low C in L3 and can miss the gate,
        # instead of nagging with the same urgency as a real stalled prospect thread.
        if (is_inbound and sender_node and occurred_at is not None and not is_noise
                and sender_norm not in internal_set):
            store.write_fact(conn, org_id=org_id, subject_node_id=sender_node,
                             field="thread.last_inbound", value=occurred_at.isoformat(),
                             value_type="timestamp", confidence=max(ex.relevance, 0.05),
                             occurred_at=occurred_at, event_id=event_id,
                             evidence={"derived": "inbound event"},
                             source=source, authority_rank=2)
            store.write_fact(conn, org_id=org_id, subject_node_id=sender_node,
                             field="thread.ball_in_court", value="us", value_type="enum",
                             confidence=max(ex.relevance, 0.05), occurred_at=occurred_at,
                             event_id=event_id, evidence={"derived": "last message inbound"},
                             source=source, authority_rank=2)

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
