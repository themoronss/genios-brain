from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text

# Load-bearing at RUNTIME only (the ask/reply branches) — exactly how their absence shipped:
# module imported cleanly, suite green, and the first real extraction with an ask observation
# would have raised NameError and zeroed the whole L2 processing phase.
from genios_engine.context.open_loops import close_loops_for_reply, record_ask
from genios_engine.contracts.open_loop import is_ask, open_loop_id
from genios_engine.capture.internal_knowledge import authority_rank_for
from genios_engine.capture.structured.apply import _PERSONAL_DOMAINS
from genios_engine.context.extract.envelope import Envelope
from genios_engine.context.extract.extractor import Extraction, extract
from genios_engine.context.graph_store import GraphStore
from genios_engine.platform.config import get_settings
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
# b3-2: enriched observations with the canonical SIGNAL KINDS vocab
# b3-3: envelope (direction/from/to/we_are) + typed roles + scheduling_proposals split out of
#       commitments + pack-supplied field and observation vocabulary
PROMPT_VERSION = "b3-4"

#: Bumped whenever the SHAPE the pipeline reads out of an extraction changes, even if the prompt
#: text does not. Both belong in the cache key: the cache stores a parsed result, so a reader
#: that now looks for `roles` would otherwise be served a cached payload that never had them —
#: silently, and for exactly the messages that already matter most.
EXTRACTION_SCHEMA_VERSION = "3"


def _vocab_fingerprint(effective: dict | None) -> str:
    """A short, stable hash of the pack vocabulary that shaped the prompt.

    Promoting a tenant to a pack version that adds an observation kind changes what the model is
    asked to look for, so it must change the cache key too — otherwise the new kind is never
    extracted for any message the tenant has already seen, which is most of them.
    """
    from genios_engine.context.extract.vocab import field_vocabulary, observation_vocabulary
    if not effective:
        return "novocab"
    material = "|".join(observation_vocabulary(effective)) + "#" + "|".join(field_vocabulary(effective))
    return LLMClient.content_hash(material)[:12]
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


def is_platform_sender(email: str | None) -> bool:
    """True when this address is OURS — the product's own transactional mail.

    Distinct from the tenant's self-filter, which asks "is this the customer?". We are not the
    customer, so that filter correctly says no and the vendor's onboarding mail becomes a
    business relationship inside the customer's own graph. The design partner's feed carried
    three cards on `invite@thegenios.com`, one of them telling him to book a demo with his own
    product, from a message whose entire body was a congratulations note.

    Domains come from settings, never a literal here: a self-hosted or white-labelled deployment
    sends from a different domain, and a hardcoded string would quietly stop protecting it.
    """
    addr = (email or "").strip().lower()
    if "@" not in addr:
        return False
    domain = addr.rsplit("@", 1)[1]
    raw = getattr(get_settings(), "platform_domains", "") or ""
    owned = {d.strip().lower() for d in raw.split(",") if d.strip()}
    return any(domain == d or domain.endswith("." + d) for d in owned)
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


#: Words that make a clause an obligation rather than an offer. A promise has a verb of owing.
_OBLIGATION = re.compile(
    r"\b(will|i'?ll|we'?ll|shall|going to|gonna|send|share|introduce|intro|get you|"
    r"revert|follow up|circle back|deliver|prepare|draft|schedule|set up|confirm|"
    r"provide|update you|come back|forward|arrange|book)\b", re.I)


#: The role vocabulary the extractor may assign. Closed on purpose — an open set would let the
#: model invent a role no rule can ever match, which is the fact-field failure in a new costume.
#: What the two sides ARE to each other. Closed on purpose: an open vocabulary would let the
#: model invent a lens nothing downstream knows how to apply.
_RELATIONSHIP_NATURES = frozenset({
    "investor", "customer", "prospect", "vendor", "candidate", "partner", "community", "unknown"})
#: Which way money and evaluation flow — what separates raising from selling.
_RELATIONSHIP_DIRECTIONS = frozenset({"they_evaluate_us", "we_evaluate_them", "peer"})

_COUNTERPARTY_ROLES = frozenset({
    "counterparty",   # the business subject: the person the loop is actually with
    "introducer",     # made the introduction; never the target of the resulting action
    "introduced",     # the person being introduced
    "owner",          # owns the work on our side
    "approver",       # must approve before anything is sent
    "observer",       # cc'd, not party to the loop
    "machine",        # a bot or automated sender
})


def _merge_domain_hints(l1_hints: list | None, model_domains: list | None) -> list:
    """L1's keyword hints, then the model's own reading of the message.

    Kept as separate hints rather than merged into one verdict so `selected_by` provenance stays
    recoverable: when a situation is typed oddly, the question "did a keyword do that or did the
    model?" has an answer.
    """
    out = list(l1_hints or [])
    seen = {(h.get("domain") if isinstance(h, dict) else getattr(h, "domain", None))
            for h in out}
    for d in (model_domains or ()):
        name = str(d).strip().lower()
        if name and name not in seen:
            out.append({"domain": name, "source": "model"})
            seen.add(name)
    return out


def _thread_node(store, conn, *, org_id: str, thread_id: str | None, event_id: str,
                 counterparty: str | None) -> str | None:
    """The conversation itself, as a node — so its state stops colliding with every other one.

    `graph_facts` keys on (org, subject, field), and thread state was written on the PERSON. One
    person therefore held exactly one `thread.ball_in_court`, last write wins, across every
    conversation they were part of: `boardy@boardy.ai` spans 254 distinct threads in the design
    partner's graph and `theresa.hoffmann@antler.co` spans 3. Whichever message landed last
    decided whose turn it was in all of them — and that single fact drives 22 of 41 live signals.

    A thread node gives each conversation its own key space. It is written ALONGSIDE the
    person-level fact, not instead of it: the rules read the person fact today, and changing what
    they read is a separate, testable step. This lands the substrate the Antler arc needs
    (rejected -> re-pitched -> reconsideration open is a property of one thread, not of a person)
    without moving any rule.
    """
    if not thread_id:
        return None
    key = f"thread:{thread_id}"
    label = f"Thread with {counterparty}" if counterparty else f"Thread {thread_id[:12]}"
    return store.find_or_create_node(
        conn, org_id=org_id, node_type="thread", canonical_key=key,
        display_name=label[:120], event_id=event_id)


def _is_a_promise(cm: dict) -> bool:
    """Deterministic post-gate on a commitment candidate.

    The prompt now defines a commitment and gives negative examples, but a prompt is guidance and
    this is a data-integrity boundary: a commitment node mints a due date, goes overdue, and
    becomes an imperative card. The live graph held 24 of them and most were scheduling talk —
    "Can we do next week?", "Any time next week works", "Thursday 20 Aug ⋅ 11:15am" — each with
    a fabricated deadline derived from the email's own timestamp.

    Two rules, both about the evidence rather than the model's confidence:
      * a clause ending in "?" is a request, and a request creates no obligation;
      * an obligation needs a verb of owing. "Any time next week works" states availability.
    """
    quote = str(cm.get("evidence_text") or "").strip()
    action = str(cm.get("action") or "").strip()
    if not (quote or action):
        return False
    if quote.endswith("?"):
        return False
    return bool(_OBLIGATION.search(action) or _OBLIGATION.search(quote))


def _from_cache(d: dict) -> Extraction:
    return Extraction(
        relevance=float(d.get("relevance", 0.0) or 0.0),
        noise_type=d.get("noise_type", "none"), domains=d.get("domains", []),
        entity_mentions=d.get("entity_mentions", []), fact_candidates=d.get("fact_candidates", []),
        commitments=d.get("commitments", []), questions=d.get("questions", []),
        observations=d.get("observations", []),
        # Missing on rows cached before the shape changed. The key now carries
        # EXTRACTION_SCHEMA_VERSION so those rows are no longer reachable, but defaulting here
        # keeps a stale row readable instead of raising — a cache is not a place to fail.
        roles=d.get("roles", []),
        relationships=d.get("relationships", []),
        scheduling_proposals=d.get("scheduling_proposals", []),
        ok=True)


def _to_cache(ex: Extraction) -> dict:
    return {"relevance": ex.relevance, "noise_type": ex.noise_type, "domains": ex.domains,
            "entity_mentions": ex.entity_mentions, "fact_candidates": ex.fact_candidates,
            "commitments": ex.commitments, "questions": ex.questions,
            "roles": ex.roles, "relationships": ex.relationships,
            "scheduling_proposals": ex.scheduling_proposals,
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


#: Words that mean a deal is FINISHED, and which way it went. Everything else is live.
#:
#: `deal.status` is declared as an extraction field and its VALUES were never constrained
#: anywhere — not in the prompt, not in the pack schema, not in the corpus vocabulary. So the
#: model wrote whatever the message said. One live tenant holds `lost`, `rejected` and `engaged`
#: and not one `open`, while `sales_v1.py` gates six rules on `deal.status = open` and three
#: Sales situations gate on the same literal. Every one of them is dead, in both the pack lane
#: and the compiled lane, for a reason that appears in no error and no count: the rule is
#: correct, the fact is present, and the two never meet.
#:
#: Normalising at the WRITE, not in the prompt, is deliberate. The prompt is hashed into the
#: extraction cache key, so constraining it there re-runs the model over a tenant's whole history
#: at real cost to fix a mapping that is deterministic. And a controlled value is what every
#: reader already assumes it is reading.
_DEAL_TERMINAL = {
    "lost": "lost", "closed lost": "lost", "closed_lost": "lost", "closed-lost": "lost",
    "rejected": "lost", "declined": "lost", "passed": "lost", "no": "lost",
    "dead": "lost", "cancelled": "lost", "canceled": "lost", "churned": "lost",
    "won": "won", "closed won": "won", "closed_won": "won", "closed-won": "won",
    "signed": "won", "closed": "won",
}


def _normalise_deal_status(value):
    """Free-text deal status → the controlled value every reader assumes: open | won | lost.

    Returns a (status, raw) pair. The model's own word is never discarded — it is the stage, and
    "negotiation" or "final review" is more informative than "open" once something is reading
    for it. Only the STATUS is collapsed, because that is the one every rule compares against.
    """
    raw = str(value or "").strip()
    if not raw:
        return None, None
    return _DEAL_TERMINAL.get(raw.lower(), "open"), raw


def _normalise_meeting_status(value):
    """Free-text meeting status → the one spelling every reader was written against.

    `context/meeting_lifecycle.py` already owns the set of words that mean "the event is off"
    (`cancelled`, `canceled`, `declined`) because a calendar provider may send any of them. Every
    AUTHORED predicate, however, compares a literal: `admin.obj.core.meeting`,
    `admin.obj.core.action_item`, `admin.obj.core.deadline`, `admin.obj.core.escalation`,
    `admin.obj.core.expense` and `admin.obj.calendar_management.time_block` all test
    `meeting.status = cancelled`. A fact written `canceled` matches none of them and is not
    reported missing either — it is present, it is simply a word nobody asked about.

    On the design partner's graph both spellings are live on person nodes. Collapsing them here
    means the tolerant set stays where it belongs (reading a provider's payload) and the stored
    fact says one thing, which is the same division of labour `_normalise_deal_status` uses.

    Imported from `meeting_lifecycle` rather than restated: two lists of the same synonyms drift,
    and the drift is silent for exactly as long as nobody adds a sixth word.
    """
    from genios_engine.context.meeting_lifecycle import CANCELLED

    raw = str(value or "").strip()
    if not raw:
        return None
    return "cancelled" if raw.lower() in CANCELLED else raw


def process_event(*, org_id: str, event_id: str, source: str, content: str,
                  sender_email: str | None, occurred_at: datetime | None,
                  sender_name: str | None = None,
                  llm: LLMClient, store: GraphStore, is_inbound: bool = False,
                  recipient_emails: list[str] | None = None,
                  internal_emails: frozenset[str] | None = None,
                  internal_kind: str | None = None,
                  thread_id: str | None = None,
                  domain_hints: list | None = None,
                  canon_meta: dict | None = None,
                  effective: dict | None = None) -> L2Result:
    # replay cache — identical content+prompt → reuse, no re-call, deterministic. The key is
    # ORG-SCOPED (org_id in the hash) so tenant A's cached extraction can never be served to
    # tenant B on byte-identical content (e.g. the same newsletter) — the cross-tenant leak fix.
    # The key must cover everything that can change the ANSWER: the tenant, the prompt, the
    # parsed shape, the model, and the pack vocabulary now baked into the prompt. It used to
    # cover only tenant + prompt version + content, so this org held 260 cached extractions that
    # would have survived a prompt fix and hidden it completely — the fix would ship, the
    # numbers would not move, and the conclusion would be that the fix did not work.
    pack_fingerprint = _vocab_fingerprint(effective)
    key = LLMClient.content_hash(
        f"{org_id}:{PROMPT_VERSION}:{EXTRACTION_SCHEMA_VERSION}:"
        f"{getattr(llm, 'model', '?')}:{pack_fingerprint}:{content}")
    cached = store.cache_get(key, org_id=org_id)
    if cached is not None:
        ex, is_cached = _from_cache(cached), True
    else:
        # The envelope is built from data the pipeline already holds — it was simply never
        # passed to the model, which is why direction and party roles had to be guessed from
        # prose and were routinely guessed wrong.
        envelope = Envelope(
            sender=(sender_email or "").strip().lower(),
            recipients=tuple((r or "").strip().lower() for r in (recipient_emails or []) if r),
            self_identities=frozenset(internal_emails or ()))
        ex, is_cached = extract(llm, source=source, content=content,
                                envelope=envelope, effective=effective), False
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
            # Our own product mail is a `service`, never a person: it can still carry content
            # (a billing notice is real), but it must never enter the person graph where the
            # relationship rules live. `service` has no rule scope, which is exactly right —
            # nobody is in a business relationship with their own tooling.
            ntype = ("service" if (_is_automated_sender(email) or is_platform_sender(email))
                     else "person")
            # NAME THE PERSON IF THE SOURCE NAMED THEM. Only the SENDER's name is known here —
            # recipients arrive as bare addresses in To/Cc — so this applies to the one address
            # the From header described, and everyone else keeps the address until they write to
            # us. That asymmetry is the honest one: we name people who have spoken.
            label = (sender_name if (sender_name and key == (sender_email or "").strip().lower())
                     else email)
            node = store.find_or_create_node(
                conn, org_id=org_id, node_type=ntype,
                canonical_key=key, display_name=label, event_id=event_id)
            touched[node] = ntype
            if key in internal_set:
                internal_nodes.add(node)
            return node

        employer: dict[str, str] = {}

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
            employer[person_node] = company     # read by _deal_for, so a deal lands on the
            #                                     subject's OWN account and not an arbitrary one
            # A company reached through one of OUR OWN seats is us, not a counterparty.
            # Without this, every outbound email anchors on our own domain and the whole
            # org collapses into one situation containing everything.
            #
            # And a company reached through the PLATFORM's own address is nobody's counterparty
            # either. `is_platform_sender` already keeps `invite@thegenios.com` out of the person
            # graph — but only the PERSON was protected. `_works_at` still minted a `thegenios.com`
            # company node and left it eligible to anchor, so the product's own domain became a
            # situation inside the customer's graph: the design partner carries a
            # `recruiting_company` situation on `thegenios.com`, which is a card advising a founder
            # about his relationship with his own vendor's website. Two different questions —
            # "is this the customer?" (internal_set) and "is this us, the product?"
            # (is_platform_sender) — and the answer to either one means this is not a counterparty.
            if (_norm_email(email) or "") in internal_set or is_platform_sender(email):
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
                    # …and the reply CLOSES this thread's open loops for this person. The
                    # ball_in_court flip below says whose turn it is; the ledger says WHICH
                    # requests this reply answered — one row each, never the whole person.
                    close_loops_for_reply(conn, org_id=org_id, subject_node_id=rnode,
                                          thread_id=thread_id, event_id=event_id,
                                          at=occurred_at)
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
                    # …and on the thread, per the inbound side. Answering ONE conversation must
                    # not mark every other conversation with the same person as answered.
                    tnode = _thread_node(store, conn, org_id=org_id, thread_id=thread_id,
                                         event_id=event_id, counterparty=rn_email)
                    if tnode:
                        if store.write_edge(conn, org_id=org_id,
                                            edge_type="corresponded_with",
                                            from_node_id=rnode, to_node_id=tnode,
                                            confidence=0.95, occurred_at=occurred_at,
                                            event_id=event_id,
                                            evidence={"derived": "thread participant"},
                                            source=source, authority_rank=2):
                            edge_n += 1
                        for fld, val, vt in (
                                ("thread.last_outbound", occurred_at.isoformat(), "timestamp"),
                                ("thread.ball_in_court", "them", "enum")):
                            store.write_fact(conn, org_id=org_id, subject_node_id=tnode,
                                             field=fld, value=val, value_type=vt,
                                             confidence=FACT_CONF_BY_RANK[2],
                                             relevance=ex.relevance, occurred_at=occurred_at,
                                             event_id=event_id,
                                             evidence={"derived": "we replied",
                                                       "thread": thread_id},
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

        # DEAL NODES. `deal.*` facts used to land on whichever person happened to be the subject,
        # because this loop writes every extracted fact to its subject and nothing minted a deal.
        # The cost was invisible and total: `correlation.ANCHOR_PRIORITY` puts "deal" FIRST, above
        # company and person, and `domain_spec` types a deal-anchored sales situation as `deal` —
        # so the whole chain from correlation through situation typing to the corpus was built and
        # waiting on a node that was never created. Measured on the design partner's org: 45
        # `deal.status` rows across 38 nodes, zero deal nodes, zero `deal` situations, and roughly
        # twenty authored capabilities (closing, negotiation, pricing, discovery, demo, forecasting,
        # the qualification cluster) unreachable for want of this.
        #
        # Keyed on the COMPANY, not the person: a deal is an account-level thing and the same
        # opportunity reaches us through several contacts. Keying it per person would mint one deal
        # per correspondent and split one negotiation into five situations.
        deal_nodes: dict[str, str] = {}

        def _deal_for(subject_node: str) -> str | None:
            """The deal node for whichever account this subject belongs to, minted on first need."""
            nonlocal edge_n
            if touched.get(subject_node) == "company":
                company = subject_node
            else:
                # The subject's OWN employer first. Falling straight to "any company in the
                # event" would put a deal on whichever counterparty happened to be cc'd, and on
                # an introduction thread naming three firms that is a coin toss recorded as fact.
                company = employer.get(subject_node)
            if company is None or company in internal_nodes:
                external = sorted(c for c, t in touched.items()
                                  if t == "company" and c not in internal_nodes)
                company = external[0] if len(external) == 1 else None
            if not company or company in internal_nodes:
                return None            # our own domain is not a counterparty, so it has no deal
            node = deal_nodes.get(company)
            if node is None:
                # Named after the account, because the card says this out loud and
                # "deal:node_abc123" in front of a founder is worse than no card.
                row = conn.execute(text(
                    "select display_name from graph_nodes where org_id=:o and node_id=:n"),
                    {"o": org_id, "n": company}).first()
                label = (row[0] if row and row[0] else company)
                node = store.find_or_create_node(
                    conn, org_id=org_id, node_type="deal", canonical_key="deal:" + company,
                    display_name=f"{label} — deal"[:80], event_id=event_id)
                touched[node] = "deal"
                deal_nodes[company] = node
            # BOTH edges are load-bearing, and the person one especially so. `_neighborhood` is
            # ONE hop and verb-agnostic, and a company node holds almost no facts of its own —
            # everything a deal capability asks for (`thread.ball_in_court`, `commitment.due_at`,
            # `derived.engagement`) sits on the PEOPLE. With only `company owns deal` the contacts
            # are two hops away, so a deal-anchored situation would read an empty neighbourhood
            # and come back INSUFFICIENT_CONTEXT — the exact failure the company anchor already
            # had to be rescued from.
            for frm, to, verb in ((company, node, "owns"), (node, subject_node, "involves")):
                if frm != to and store.write_edge(
                        conn, org_id=org_id, edge_type=verb, from_node_id=frm, to_node_id=to,
                        confidence=0.9, occurred_at=occurred_at, event_id=event_id,
                        evidence={"derived": "deal from deal.* facts"}, source=source,
                        authority_rank=2):
                    edge_n += 1
            return node

        for f in facts:
            subj = _resolve_subject(f.get("subject"), name_to_node, content_subject)
            if subj is None:
                continue
            field = str(f.get("field") or "note")
            value = f.get("value")
            # A `deal.*` fact belongs to the deal, not to whoever happened to mention it.
            if field.startswith("deal."):
                subj = _deal_for(subj) or subj
            # ungrounded (paraphrased) fact → kept, but scored down instead of dropped.
            fact_rel = ex.relevance if f.get("_grounded", True) else ex.relevance * _GROUNDING_PENALTY
            if field == "meeting.status":
                normalised = _normalise_meeting_status(value)
                if normalised is None:
                    continue
                value = normalised
            if field == "deal.status":
                status, raw = _normalise_deal_status(value)
                if status is None:
                    continue
                value = status
                # The model's own word survives as the STAGE. "negotiation" and "final review"
                # are what a reader actually wants back; collapsing them into "open" and
                # throwing the original away would trade one dead field for a duller one.
                if raw.lower() != status and store.write_fact(
                        conn, org_id=org_id, subject_node_id=subj, field="deal.stage",
                        value=raw, value_type="string",
                        confidence=FACT_CONF_BY_RANK[claim_rank], relevance=fact_rel,
                        occurred_at=occurred_at, event_id=event_id,
                        evidence=_claim_evidence(f, internal_kind), source=source,
                        authority_rank=claim_rank):
                    fact_n += 1
            wrote = store.write_fact(conn, org_id=org_id, subject_node_id=subj,
                                     field=field, value=value,
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
            obs_evidence = {"text": o.get("evidence_text")}
            # An ask-class observation IS an open loop, and it carries its loop's stable
            # identity from birth. Nothing in the system named a REQUEST before this: completion
            # authority was one ball_in_court bit per person, so answering any of somebody's
            # three questions read as answering all of them. The id is content-addressed
            # (subject + kind + thread) — a follow-up repeating the ask lands on the SAME loop,
            # a different thread's same-kind ask is a different one.
            if is_ask(kind) and content_subject:
                obs_evidence["open_loop_id"] = record_ask(
                    conn, org_id=org_id, subject_node_id=content_subject, kind=kind,
                    thread_id=thread_id, event_id=event_id,
                    at=occurred_at) if occurred_at else open_loop_id(
                    org_id=org_id, subject_node_id=content_subject, kind=kind,
                    thread_id=thread_id)
            store.write_observation(conn, org_id=org_id, subject_node_id=content_subject,
                                    kind=kind, confidence=obs_conf,
                                    occurred_at=occurred_at, event_id=event_id,
                                    evidence=obs_evidence, source=source)
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
                                              "directed_at": q.get("directed_at"),
                                              "open_loop_id": (record_ask(
                                                  conn, org_id=org_id,
                                                  subject_node_id=sender_node,
                                                  kind="question", thread_id=thread_id,
                                                  event_id=event_id, at=occurred_at)
                                                  if occurred_at else open_loop_id(
                                                      org_id=org_id,
                                                      subject_node_id=sender_node,
                                                      kind="question", thread_id=thread_id))},
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
            # …and the same state on the THREAD, where it does not collide. The person-level
            # write above stays for the rules that read it today; this is the substrate that
            # makes "whose turn is it in THIS conversation" answerable at all.
            tnode = _thread_node(store, conn, org_id=org_id, thread_id=thread_id,
                                 event_id=event_id, counterparty=sender_norm)
            if tnode:
                if store.write_edge(conn, org_id=org_id, edge_type="corresponded_with",
                                    from_node_id=sender_node, to_node_id=tnode, confidence=0.95,
                                    occurred_at=occurred_at, event_id=event_id,
                                    evidence={"derived": "thread participant"},
                                    source=source, authority_rank=2):
                    edge_n += 1
                for fld, val, vt in (("thread.last_inbound", occurred_at.isoformat(), "timestamp"),
                                     ("thread.ball_in_court", "us", "enum")):
                    store.write_fact(conn, org_id=org_id, subject_node_id=tnode,
                                     field=fld, value=val, value_type=vt,
                                     confidence=FACT_CONF_BY_RANK[2], relevance=ex.relevance,
                                     occurred_at=occurred_at, event_id=event_id,
                                     evidence={"derived": "inbound event", "thread": thread_id},
                                     source=source, authority_rank=2)

        node_roles: dict[str, str] = {}
        # A machine sender is plumbing whatever the model says, so seed it deterministically —
        # role extraction is per-message and a bot will not always be described in the text.
        for _n, _t in touched.items():
            if _t == "service":
                node_roles[_n] = "machine"
        # roles → a fact on the counterparty node. WHO someone is in this exchange is the single
        # thing no rule could previously ask: all 25 rules condition on channel mechanics (when
        # did they write, whose turn is it) and not one cites a role, so a connector, an
        # introducer and the actual business subject were indistinguishable. That is why a card
        # could target Boardy — an introduction bot — as though it were the investor.
        #
        # Written as a fact rather than an edge on purpose: a role is a property of a party
        # WITHIN a relationship and changes as the relationship does, which is exactly the
        # versioned-fact shape (supersede, keep history) and not the shape of a graph edge.
        for r in ex.roles or ():
            party = str((r or {}).get("party") or "").strip()
            role = str((r or {}).get("role") or "").strip().lower()
            if not party or role not in _COUNTERPARTY_ROLES:
                continue
            rnode = name_to_node.get(_norm(party)) or (
                _person(party) if "@" in party else None)
            if not rnode:
                continue
            node_roles[rnode] = role
            store.write_fact(
                conn, org_id=org_id, subject_node_id=rnode,
                field="party.role", value=role, value_type="enum",
                confidence=FACT_CONF_BY_RANK[2], relevance=ex.relevance,
                occurred_at=occurred_at, event_id=event_id,
                evidence={"text": (r or {}).get("evidence_text")},
                source=source, authority_rank=2)

        # relationships → the LENS. `party.role` says who acted in this exchange; this says what
        # the two sides ARE to each other, and it is the fact that decides which expertise may
        # speak at all. Without it every counterparty is a potential deal: the engine extracted
        # `company_type = "founder-only pre-seed VC"` for an investor, carried investment
        # timelines and closure rates — and still told the founder to "Save the deal now",
        # because no rule could read any of it. A pass from a fund is a fundraising outcome; a
        # sales rule has no business narrating it.
        #
        # Typed from the message content, never from the address. A domain list would work for
        # one inbox and fail for the next tenant, which is the opposite of what this layer is.
        for rel in ex.relationships or ():
            party = str((rel or {}).get("party") or "").strip()
            nature = str((rel or {}).get("nature") or "").strip().lower()
            if not party or nature not in _RELATIONSHIP_NATURES:
                continue
            rnode = name_to_node.get(_norm(party)) or (
                _person(party) if "@" in party else None)
            if not rnode:
                continue
            store.write_fact(
                conn, org_id=org_id, subject_node_id=rnode,
                field="relationship.nature", value=nature, value_type="enum",
                confidence=FACT_CONF_BY_RANK[2], relevance=ex.relevance,
                occurred_at=occurred_at, event_id=event_id,
                evidence={"text": (rel or {}).get("evidence_text")},
                source=source, authority_rank=2)
            direction = str((rel or {}).get("direction") or "").strip().lower()
            if direction in _RELATIONSHIP_DIRECTIONS:
                store.write_fact(
                    conn, org_id=org_id, subject_node_id=rnode,
                    field="relationship.direction", value=direction, value_type="enum",
                    confidence=FACT_CONF_BY_RANK[2], relevance=ex.relevance,
                    occurred_at=occurred_at, event_id=event_id,
                    evidence={"text": (rel or {}).get("evidence_text")},
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
            if not _is_a_promise(cm):
                continue          # a question or an availability window, not an obligation
            subj = _resolve_subject(cm.get("actor"), name_to_node, sender_node)
            due = parse_due(cm.get("due_text"), occurred_at) if occurred_at else None
            if subj and due:
                cm_text = str(cm.get("evidence_text") or "").strip()
                # The NORMALISED obligation ("share the updated deck"), with the verbatim quote
                # kept as evidence. The extractor has always returned both and the pipeline read
                # only the quote, so a commitment's title was the counterparty's raw sentence —
                # in their voice, framed as the founder's overdue promise, then sliced at 60
                # characters: "Deliver I'll be in PST starting this weekend, let's find som".
                cm_action = str(cm.get("action") or "").strip() or cm_text
                ck = "commitment:" + hashlib.sha1(
                    f"{subj}:{_norm(cm_text)}:{due.date().isoformat()}".encode()).hexdigest()[:20]
                cnode = store.find_or_create_node(
                    conn, org_id=org_id, node_type="commitment", canonical_key=ck,
                    display_name=(cm_action[:80] or "commitment"), event_id=event_id)
                if store.write_edge(conn, org_id=org_id, edge_type="owns",
                                    from_node_id=subj, to_node_id=cnode, confidence=0.9,
                                    occurred_at=occurred_at, event_id=event_id,
                                    evidence={"derived": "commitment actor"}, source=source,
                                    authority_rank=2):
                    edge_n += 1
                for fld, val, vt in (("commitment.due_at", due.isoformat(), "timestamp"),
                                     ("commitment.text", cm_action, "string"),
                                     ("commitment.status", "open", "enum")):
                    store.write_fact(conn, org_id=org_id, subject_node_id=cnode,
                                     field=fld, value=val, value_type=vt,
                                     confidence=FACT_CONF_BY_RANK[2], relevance=ex.relevance,
                                     occurred_at=due if fld == "commitment.due_at" else occurred_at,
                                     event_id=event_id,
                                     evidence={"text": cm.get("evidence_text")},
                                     source=source, authority_rank=2)
                # LEGACY DUAL-WRITE — retired. `commitment_overdue` now reads the commitment
                # node (general_v1 1.2.0), so mirroring onto the person is no longer feeding any
                # rule; it only recreated the collision this change exists to remove. Kept as a
                # comment rather than deleted silently so the next reader knows the mirror was
                # deliberate once and is deliberately gone now.
                #
                # The person keeps a POINTER, not the promise. `commitment.last_due_at` says
                # "this person owes something, soonest due here" — useful for ranking a
                # relationship — while the promise itself lives on its own node where a second
                # one cannot overwrite the first. The old mirror wrote the full promise here and
                # collided; this writes a single derived timestamp that is meant to be latest-wins.
                store.write_fact(conn, org_id=org_id, subject_node_id=subj,
                                 field="commitment.last_due_at", value=due.isoformat(),
                                 value_type="timestamp",
                                 confidence=FACT_CONF_BY_RANK[2],
                                 relevance=ex.relevance, occurred_at=due,
                                 event_id=event_id,
                                 evidence={"derived": "soonest open commitment"},
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
            # Who is a party and who is plumbing. An introduction bot is named in every
            # introduction it brokers, so anchoring on it fuses them all into one situation.
            node_roles=node_roles,
            # L1's keyword hints AND the model's own domain judgment. The model already read the
            # whole message and answered — it labelled the Antler thread
            # ["venture_capital","startup_funding"] — and that answer was written into an
            # observation's evidence and then never consulted, while an 8-keyword regex over the
            # raw body decided the domain. That regex matched "error" four times inside a legal
            # footer and typed the org's most important fundraising thread as `support`.
            #
            # L1 first: a source prior is cheap and deterministic, and `resolve_domain` takes the
            # first hint. The model's judgment ranks behind it and ahead of nothing — which is
            # still infinitely better than being discarded.
            domain_hints=_merge_domain_hints(domain_hints, ex.domains))

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
