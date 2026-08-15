from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from genios_engine.capture.internal_knowledge import authority_rank_for
from genios_engine.capture.structured.apply import _PERSONAL_DOMAINS
from genios_engine.context.extract.extractor import Extraction, extract
from genios_engine.context.graph_store import GraphStore
from genios_engine.context.guard import _norm, annotate_grounding, keep_grounded
from genios_engine.context.correlation import correlate_event
from genios_engine.context.canon import register_canon_node, resolve_canon_mention
from genios_engine.context.identity import (observe_person_name, resolve_company_mention,
                                            resolve_person_name)
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

# Deterministic fact confidence by authority rank — the ONLY confidence the L3 gate reads.
# The constitution's line ("the model extracts, it never decides") was broken here for
# months: fact confidence was ex.relevance (an LLM float), which flowed into engine
# ext_conf → C → the c_min gate — a language model's mood decided whether signals fired.
# Now: confidence = what KIND of source asserted it. The LLM's relevance is stored
# SEPARATELY on the fact (relevance column) and may rank; it may never gate.
#
# Calibration of rank 2 (the common case — an email-derived extraction): a rank-2 fact
# has PASSED the B4 evidence guard, i.e. the extraction quoted a verbatim substring of
# the source. We therefore know the source said it; only the interpretation carries
# risk. 0.85 encodes that: materially below a human correction (1.0) or a system of
# record (0.9), far above weak inference (0.4). The first draft used 0.70, which was
# picked by feel and — with the pack's impact floor — put the ENTIRE email-derived
# corpus permanently below the gate. tests/test_corpus_can_fire.py locks the property
# so a future change to this table cannot silently kill the rules again.
FACT_CONF_BY_RANK = {4: 1.00, 3: 0.90, 2: 0.85, 1: 0.40}
PROMPT_VERSION = "b3-2"          # b3-2: enriched observations with the canonical SIGNAL KINDS vocab
                                # (deep sales+general detection). Bump invalidates the extraction
                                # cache → new events extract rich for free; existing backlog gets
                                # rich signals only on a deliberate (cheap Haiku) re-extract/rebuild.
# email classes that carry no real relationship → no structural graph (newsletters, bots, spam).
# NOTE: "personal" is NOT here — a personal 1:1 email is still a real correspondence edge.
_NOISE_TYPES = {"newsletter", "automated", "spam"}

# Deterministic non-human sender detector. Addresses like noreply@/notify./mailer-daemon are
# MACHINES, not people — they must never become `person` nodes (that is how cloudflare/mongodb/
# algolia polluted the relationship graph). They still get a `service` node so their content can
# attach, but they stay out of the person graph, network edges and correlation. Conservative:
# matches only clearly-automated local-parts/subdomains, so a real person is never mislabelled.
_AUTOMATED_SENDER = re.compile(
    r"(^|[._-])(no[._-]?reply|do[._-]?not[._-]?reply|donotreply|mailer[._-]?daemon|postmaster|"
    r"bounce[sd]?|notification[s]?|notify|alert[s]?|jobalert[s]?|naukrialert[s]?|newsletter[s]?|"
    r"digest|mailer|mailing|automated|auto[._-]?reply|updates?|support|community|feedback|help)@|"
    r"^usr[._-]|@(notify|notifications|mailer|mail|em|e|bounces?|alerts?|news|digest|updates?|"
    r"user[s]?)\.",
    re.I,
)


def _is_automated_sender(email: str | None) -> bool:
    """True for machine senders (noreply@, notify.<domain>, mailer-daemon, jobalerts…). Deterministic
    — no LLM — so it is cheap and predictable, exactly what MD #5 asks for the graph gatekeeper."""
    return bool(email) and bool(_AUTOMATED_SENDER.search(email.strip().lower()))
_GROUNDING_PENALTY = 0.4      # ungrounded (paraphrased) claim → kept but scored down, not dropped
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


# P5 — canonical email key. ONE definition for the whole system (platform.identity):
# the structured lane (calendar attendees, CRM contacts) and this pipeline must mint
# byte-identical person keys or the same human splits into strangers per tool.
from genios_engine.platform.identity import norm_email as _norm_email  # noqa: E402


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
    # general
    "introduction": "introduction", "intro": "introduction", "introduced": "introduction",
    "connecting_you": "introduction", "warm_intro": "introduction",
    "followup_sent": "followup_sent", "follow_up_sent": "followup_sent", "recap_sent": "followup_sent",
    "meeting_request": "meeting_request", "meeting_requested": "meeting_request",
    "book_a_meeting": "meeting_request", "schedule_call": "meeting_request",
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
    correlations: int = 0


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


def _claim_evidence(fact: dict, internal_kind: str | None) -> dict:
    """Evidence for one extracted claim. A canon fact records WHICH kind of company
    statement it came from, so a rank-4 value can be traced back to the policy that
    asserted it rather than just appearing authoritative."""
    evidence = {"text": fact.get("evidence_text")}
    if internal_kind:
        evidence["internal_kind"] = internal_kind
    return evidence


def _resolve_subject(name, name_to_node: dict, fallback: str | None) -> str | None:
    if name and _norm(str(name)) in name_to_node:
        return name_to_node[_norm(str(name))]
    return fallback


def process_event(*, org_id: str, event_id: str, source: str, content: str,
                  sender_email: str | None, occurred_at: datetime | None,
                  llm: LLMClient, store: GraphStore, is_inbound: bool = False,
                  recipient_emails: list[str] | None = None,
                  internal_emails: frozenset[str] | None = None,
                  internal_kind: str | None = None,
                  thread_id: str | None = None,
                  domain_hints: list | None = None,
                  canon_meta: dict | None = None) -> L2Result:
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

    # AUTHORITY comes from L1, which is the layer that knows PROVENANCE. Company canon
    # (a written policy, an upload tagged `pricing`) enters at rank 4 — above a system of
    # record — while observed traffic stays at rank 2. Before this, both landed at 2, so
    # a Stripe row outranked the company's own pricing sheet.
    # Only the EXTRACTED CLAIMS take this rank. Facts derived from email mechanics
    # (thread.ball_in_court, correspondence edges) stay at 2: those describe the mailbox,
    # not something the org asserted, and they never occur on a canon event anyway.
    claim_rank = authority_rank_for(internal_kind)

    # B4 guard. Grounding is a HARD gate only for identity NODES (a fabricated entity must never
    # become a graph node → keep_grounded). For SCORED claims (facts/observations) it is a
    # PENALTY, not a drop: an ungrounded/paraphrased-but-real fact is kept and scored down
    # (_grounded flag → _GROUNDING_PENALTY), never silently deleted. Store-and-score, not delete.
    ents = keep_grounded(content, ex.entity_mentions)
    facts = annotate_grounding(content, ex.fact_candidates)
    obs = annotate_grounding(content, ex.observations)

    with store.engine.begin() as conn:          # one transaction (B7)
        version = store.bump_version(conn, org_id)
        name_to_node: dict[str, str] = {}
        nodes = 0
        edge_n = 0
        obs_n = 0

        # Which nodes this event was ABOUT, and which of them are US. Correlation anchors
        # a situation on the COUNTERPARTY: anchoring on our own company would file every
        # outbound email under one enormous "us" group and correlate nothing.
        touched: dict[str, str] = {}
        internal_nodes: set[str] = set()

        def _person(email: str) -> str:
            key = _norm_email(email) or email.strip().lower()
            # A machine sender (noreply@/notify./mailer-daemon) is NOT a person — file it as a
            # `service` node so its content still attaches, but it never enters the person graph.
            ntype = "service" if _is_automated_sender(email) else "person"
            node = store.find_or_create_node(
                conn, org_id=org_id, node_type=ntype,
                canonical_key=key, display_name=email, event_id=event_id)
            touched[node] = ntype
            if key in internal_set:
                internal_nodes.add(node)
            return node

        def _works_at(email: str, person_node: str) -> None:
            """person → works_at → company(domain). Groups everyone at 3one4/kurral/… together."""
            nonlocal edge_n
            dom = _company_domain(email)
            if not dom:
                return
            company = store.find_or_create_node(
                conn, org_id=org_id, node_type="company", canonical_key=dom,
                display_name=dom, event_id=event_id)
            touched[company] = "company"
            # A company reached through one of OUR OWN seats is us, not a counterparty.
            # Without this, every outbound email anchors on our own domain and the whole
            # org collapses into one situation containing everything.
            if (_norm_email(email) or "") in internal_set:
                internal_nodes.add(company)
            if store.write_edge(conn, org_id=org_id, edge_type="works_at",
                                from_node_id=person_node, to_node_id=company, confidence=0.9,
                                occurred_at=occurred_at, event_id=event_id,
                                evidence={"derived": "email domain", "domain": dom},
                                source=source, authority_rank=2):
                edge_n += 1

        sender_norm = _norm_email(sender_email) or (sender_email or "").strip().lower()
        internal_set = internal_emails or frozenset()
        sender_node = None
        # A machine sender is noise for the NETWORK too: it gets a `service` node (facts attach) but
        # never anchors a relationship edge or a situation — same treatment as a newsletter.
        is_noise = is_noise or _is_automated_sender(sender_email)

        # CANON — company knowledge becomes a node of its own, so the facts in a refund
        # policy are facts about the Refund Policy rather than about the colleague who
        # typed it. Without this the most authoritative material in the system was also
        # the least connected: filed under an internal seat, which correlation excludes,
        # so it reached no situation at all.
        canon_node = None
        if internal_kind:
            raw_extra = canon_meta or {}
            canon_node = register_canon_node(
                conn, store, org_id=org_id, kind=internal_kind,
                title=raw_extra.get("title") or "",
                knowledge_key=raw_extra.get("knowledge_key") or event_id,
                event_id=event_id)
            touched[canon_node] = internal_kind
        # A sender always gets a node so its extracted facts/observations have something to attach
        # to — store-and-score, not delete. Noise (newsletter/automated) is NOT dropped here: its
        # facts land with a LOW relevance score and it is kept OUT of the network graph and
        # correlation below (guarded by `not is_noise`), so a newsletter never becomes a
        # relationship or a live situation — but its content is not silently thrown away. True junk
        # was already stopped upstream at the L1 LLM junk-gate, before it ever reached L2.
        if sender_email:
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
                # Confidence is deterministic (rank 2 = grounded event): whether WE replied is a
                # fact of the mailbox, not a function of how interesting the LLM found the email.
                if (not is_inbound and not is_noise and occurred_at is not None
                        and rn_email not in internal_set):
                    store.write_fact(conn, org_id=org_id, subject_node_id=rnode,
                                     field="thread.last_outbound", value=occurred_at.isoformat(),
                                     value_type="timestamp", confidence=FACT_CONF_BY_RANK[2],
                                     relevance=ex.relevance,
                                     occurred_at=occurred_at, event_id=event_id,
                                     evidence={"derived": "outbound event"}, source=source,
                                     authority_rank=2)
                    store.write_fact(conn, org_id=org_id, subject_node_id=rnode,
                                     field="thread.ball_in_court", value="them", value_type="enum",
                                     confidence=FACT_CONF_BY_RANK[2], relevance=ex.relevance,
                                     occurred_at=occurred_at,
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
                    observe_person_name(conn, org_id=org_id, node_id=nid, name=str(name),
                                        event_id=event_id)
                if not is_noise:
                    _works_at(email, nid)                    # affiliation from a real anchor
            elif etype == "company" and name and (
                    known := resolve_company_mention(conn, org_id=org_id, name=str(name))):
                # ALREADY ANCHORED. "Acme" in prose reaching the company node built from
                # acme.io — the mention is the same company we already know, so facts
                # about it attach THERE instead of piling onto whoever sent the email.
                # This is the anchor rule holding, not bending: no node is created, and
                # a name nothing is anchored under still falls through to an observation.
                name_to_node[_norm(str(name))] = known
                touched[known] = "company"
                nodes += 1
            elif etype == "person" and name and (person_hit := resolve_person_name(
                    conn, org_id=org_id, name=str(name))):
                # A person named in prose without an email — "Rohit said yes" — reaching the person we
                # already know by that name. Completes observe_person_name's intent: the write side
                # recorded the name-alias, this is the read side that was MISSING (so a name-only mention
                # linked to nobody and piled onto the sender). Same-name people share one key → resolves
                # to the first-anchored holder; never creates a node, never merges.
                name_to_node[_norm(str(name))] = person_hit
                touched.setdefault(person_hit, "person")
                nodes += 1
            elif name and (canon_hit := resolve_canon_mention(conn, org_id=org_id,
                                                              name=str(name))):
                # A named piece of company knowledge — "Project Phoenix" in a Slack
                # message reaching the project brief someone uploaded.
                #
                # Matched by NAME, not by entity type, and that is forced rather than
                # chosen: the extraction prompt never asks for a "project" type and
                # _NODE_TYPES has no entry for one, so a type-based lookup would silently
                # never fire.
                #
                # Checked AFTER the company branch on purpose. Canon titles live in their
                # own alias namespace, so a project called "Acme" and the customer called
                # "Acme" cannot contend for one key — but when a name could mean either,
                # the customer wins: its alias is derived from a real email domain, which
                # is harder evidence than a title someone typed.
                #
                # The node TYPE is carried through, not invented. Correlation anchors on
                # type, so a placeholder here would resolve the mention correctly and then
                # anchor nothing — built, and silently inert.
                canon_id, canon_type = canon_hit
                name_to_node[_norm(str(name))] = canon_id
                touched.setdefault(canon_id, canon_type)
                nodes += 1
            elif name and sender_node:                       # anchorless mention → context on sender
                store.write_observation(
                    conn, org_id=org_id, subject_node_id=sender_node,
                    kind="mention:" + (etype if etype in _NODE_TYPES else "entity"),
                    confidence=ex.relevance, occurred_at=occurred_at, event_id=event_id,
                    evidence={"name": name, "type": etype, "text": e.get("evidence_text")},
                    source=source)
                obs_n += 1
                name_to_node.setdefault(_norm(str(name)), sender_node)
        # The subject extracted CONTENT attaches to. Canon documents own their own
        # content; ordinary mail still attaches to its sender. Network edges below are
        # deliberately NOT rerouted — who corresponded with whom is a fact about people,
        # not about a document.
        content_subject = canon_node or sender_node
        fact_n = 0
        for f in facts:
            subj = _resolve_subject(f.get("subject"), name_to_node, content_subject)
            if subj is None:
                continue
            # ungrounded (paraphrased) fact → kept, but scored down instead of dropped.
            fact_rel = ex.relevance if f.get("_grounded", True) else ex.relevance * _GROUNDING_PENALTY
            wrote = store.write_fact(conn, org_id=org_id, subject_node_id=subj,
                                     field=str(f.get("field") or "note"), value=f.get("value"),
                                     value_type="string",
                                     confidence=FACT_CONF_BY_RANK[claim_rank],
                                     relevance=fact_rel,
                                     occurred_at=occurred_at, event_id=event_id,
                                     evidence=_claim_evidence(f, internal_kind),
                                     source=source,
                                     # R2 evidence-backed · R4 company canon
                                     authority_rank=claim_rank)
            if wrote:
                fact_n += 1
        # observation hygiene: one email quoting the same moment twice must not commit the
        # same (kind, evidence) twice — duplicates double-count in derived sentiment.
        seen_obs: set[tuple[str, str]] = set()
        for o in obs:
            kind = norm_obs_kind(o.get("kind"))
            key = (kind, str(o.get("evidence_text") or ""))
            if key in seen_obs:
                continue
            seen_obs.add(key)
            obs_conf = ex.relevance if o.get("_grounded", True) else ex.relevance * _GROUNDING_PENALTY
            store.write_observation(conn, org_id=org_id, subject_node_id=content_subject,
                                    kind=kind, confidence=obs_conf,
                                    occurred_at=occurred_at, event_id=event_id,
                                    evidence={"text": o.get("evidence_text")}, source=source)
            obs_n += 1
        # INTENT, finally committed: the LLM already extracts open questions — the pipeline
        # parsed and DROPPED them for months. A question directed at us is the strongest
        # "they expect an answer" signal the twin can hold.
        for q in keep_grounded(content, ex.questions):
            key = ("question", str(q.get("evidence_text") or ""))
            if key in seen_obs or content_subject is None:
                continue
            seen_obs.add(key)
            store.write_observation(conn, org_id=org_id, subject_node_id=sender_node,
                                    kind="question", confidence=ex.relevance,
                                    occurred_at=occurred_at, event_id=event_id,
                                    evidence={"text": q.get("evidence_text"),
                                              "directed_at": q.get("directed_at")},
                                    source=source)
            obs_n += 1

        # per-email relevance recorded as an append-only signal so L3/queries can RANK — the
        # "score, don't delete" record: even a low-relevance email leaves its score, never a gap.
        # domains (which business areas the email touches) ride along — extracted since day
        # one, dropped until now.
        if sender_node:
            store.write_observation(
                conn, org_id=org_id, subject_node_id=sender_node,
                kind=("email_noise:" + ex.noise_type) if is_noise else "email_relevance",
                confidence=ex.relevance, occurred_at=occurred_at, event_id=event_id,
                evidence={"relevance": ex.relevance, "noise_type": ex.noise_type,
                          "domains": ex.domains}, source=source)
            obs_n += 1

        # thread state (direction-derived, deterministic) → feeds L3's unanswered_email.
        # Skip for noise (a newsletter doesn't put the ball in our court) and for internal
        # teammates (an internal reply isn't a prospect thread we owe an external reply on).
        # Confidence is deterministic rank-2 (the mailbox is certain the message arrived);
        # the email's LLM relevance is stored on the fact's relevance column for RANKING —
        # it no longer decides whether the signal clears the c_min gate (D3).
        if (is_inbound and sender_node and occurred_at is not None and not is_noise
                and sender_norm not in internal_set):
            store.write_fact(conn, org_id=org_id, subject_node_id=sender_node,
                             field="thread.last_inbound", value=occurred_at.isoformat(),
                             value_type="timestamp", confidence=FACT_CONF_BY_RANK[2],
                             relevance=ex.relevance,
                             occurred_at=occurred_at, event_id=event_id,
                             evidence={"derived": "inbound event"},
                             source=source, authority_rank=2)
            store.write_fact(conn, org_id=org_id, subject_node_id=sender_node,
                             field="thread.ball_in_court", value="us", value_type="enum",
                             confidence=FACT_CONF_BY_RANK[2], relevance=ex.relevance,
                             occurred_at=occurred_at,
                             event_id=event_id, evidence={"derived": "last message inbound"},
                             source=source, authority_rank=2)

        # commitments → FIRST-CLASS nodes. A commitment is the highest-value extracted
        # object in the system, and it used to be one colliding fact field on the person:
        # facts key on (subject, field), so the SECOND promise silently superseded the
        # first — a person could hold exactly one commitment. Data loss, fixed.
        # Each commitment now gets its own node (deterministic canonical key: who +
        # normalized text + due date), an owns-edge from the actor, and its own facts.
        # DUAL-WRITE strangler: the legacy person-level commitment.due_at keeps being
        # written (latest wins, as before) so general_v1's commitment_overdue rule keeps
        # firing unchanged; commitment-scoped rules migrate to the nodes later.
        for cm in keep_grounded(content, ex.commitments):
            subj = _resolve_subject(cm.get("actor"), name_to_node, sender_node)
            due = parse_due(cm.get("due_text"), occurred_at) if occurred_at else None
            if subj and due:
                cm_text = str(cm.get("evidence_text") or "").strip()
                ck = "commitment:" + hashlib.sha1(
                    f"{subj}:{_norm(cm_text)}:{due.date().isoformat()}".encode()).hexdigest()[:20]
                cnode = store.find_or_create_node(
                    conn, org_id=org_id, node_type="commitment", canonical_key=ck,
                    display_name=(cm_text[:80] or "commitment"), event_id=event_id)
                if store.write_edge(conn, org_id=org_id, edge_type="owns",
                                    from_node_id=subj, to_node_id=cnode, confidence=0.9,
                                    occurred_at=occurred_at, event_id=event_id,
                                    evidence={"derived": "commitment actor"}, source=source,
                                    authority_rank=2):
                    edge_n += 1
                for fld, val, vt in (("commitment.due_at", due.isoformat(), "timestamp"),
                                     ("commitment.text", cm_text, "string"),
                                     ("commitment.status", "open", "enum")):
                    store.write_fact(conn, org_id=org_id, subject_node_id=cnode,
                                     field=fld, value=val, value_type=vt,
                                     confidence=FACT_CONF_BY_RANK[2], relevance=ex.relevance,
                                     occurred_at=due if fld == "commitment.due_at" else occurred_at,
                                     event_id=event_id,
                                     evidence={"text": cm.get("evidence_text")},
                                     source=source, authority_rank=2)
                # legacy dual-write (person-level; latest wins — pre-existing shape).
                # commitment.action rides alongside due_at (same latest-wins key space) so the
                # person-scoped commitment_overdue card can render WHAT was promised instead of a
                # hollow "you promised this" — the rule's evidence_fields already cite it; the
                # pipeline just never wrote it. Firing is unchanged (trigger stays commitment.due_at).
                for fld, val, oc in (("commitment.due_at", due.isoformat(), due),
                                     ("commitment.action", cm_text, occurred_at)):
                    if fld == "commitment.action" and not cm_text:
                        continue  # no promise text extracted → leave unset rather than write ""
                    store.write_fact(conn, org_id=org_id, subject_node_id=subj,
                                     field=fld, value=val,
                                     value_type="timestamp" if fld == "commitment.due_at" else "string",
                                     confidence=FACT_CONF_BY_RANK[2],
                                     relevance=ex.relevance, occurred_at=oc,
                                     event_id=event_id, evidence={"text": cm.get("evidence_text")},
                                     source=source, authority_rank=2)

        # CORRELATION — the last thing in the same transaction, because a situation must
        # never reference nodes that rolled back. Anchors are the COUNTERPARTY only: our
        # own seats and our own company are removed, or every outbound email would file
        # under one enormous "us" situation containing the whole company.
        # Noise is excluded for the same reason it gets no network edges: a newsletter
        # naming one of your contacts is not part of that customer's situation. The
        # mention loop still creates the node and keeps every fact — this skips only the
        # grouping, so nothing is lost, it just stops a marketing blast from becoming
        # evidence in a live deal.
        correlations = [] if is_noise else correlate_event(
            conn, org_id=org_id, event_id=event_id, occurred_at=occurred_at,
            thread_id=thread_id,
            node_types={n: t for n, t in touched.items() if n not in internal_nodes},
            domain_hints=domain_hints)

        store.write_change(conn, org_id=org_id, graph_version=version, cause_event_id=event_id,
                           payload={"nodes": nodes, "edges": edge_n, "facts": fact_n,
                                    "observations": obs_n,
                                    "correlations": len(correlations)})

    # Everything readable is stored (facts tagged with relevance as confidence); nothing is
    # deleted by a relevance score. Ranking happens downstream (L3/queries), not by dropping here.
    return L2Result(event_id, "committed", ex.relevance, nodes=nodes, facts=fact_n,
                    observations=obs_n, input_tokens=ex.input_tokens,
                    output_tokens=ex.output_tokens, graph_version=version, cached=is_cached,
                    primary_node=sender_node, correlations=len(correlations))
