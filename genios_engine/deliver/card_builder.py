from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.contracts.abstention import Level as _ABSTENTION
from genios_engine.contracts.abstention import VALID_LEVELS as _ABSTENTION_LEVELS
from .bands import band
from .router import resolve_assignee
from .slots import _fval, compute_slots

# E0 · Card Builder (§5.10). Compose the card.v1 draft deterministically from a signal + play +
# template — NO LLM here (that is E1). Attaches band (E2), owner (E3), the evidence chain (≥2,
# Law 2), on-device context_tags, the four actions, and +7d expiry. Returns a draft the renderer
# fills and the store persists.

EXPIRY_DAYS = 3650      # effectively "never" — a card only leaves the queue via user action
                        # (do_it_myself/snooze/dismiss) or a genuine decision_expires_at deadline,
                        # never a fixed housekeeping timer

# field prefix → the surface that produced it (for the evidence chain's `source`)
_SOURCE = {"deal": "crm", "thread": "gmail", "commitment": "gmail", "meeting": "calendar"}
# real connector source (graph_source_refs.source) → app tag. NOT field-name-based: there is no
# "deal" entry here on purpose. A "deal.*" field is just a field name — the L2 extractor writes it
# from whatever it was reading (usually a Gmail email), and only source_refs.source knows the truth.
_SOURCE_APP = {"gmail": "app:gmail", "gcal": "app:googlecalendar", "calendar": "app:googlecalendar",
               "notion": "app:notion", "drive": "app:googledrive", "hubspot": "app:hubspot"}


#: A card's level is what it CLAIMS: an instruction, a warning, or an explicit refusal to advise.
#: Sourced from `contracts/abstention.py` so the vocabulary cannot fork — the reasoner, the card
#: and the delivery gate must agree on what "the system is not telling you what to do" looks like.
VALID_LEVELS = _ABSTENTION_LEVELS


#: Observation kinds that mean the counterparty asked for SOMETHING. Without one of these we know
#: they wrote and that the ball is on us — but not what response they need, which is the whole
#: content of the instruction "reply now".
_ASK_SIGNALS: frozenset[str] = frozenset({
    "question", "meeting_request", "proposal_sent", "demo_requested",
    "contract_requested", "objection", "next_step_agreed",
})

#: reason_code -> (the fact or observation that makes its imperative meaningful, what is missing,
#: what a human should do instead). A card may carry a confident imperative ONLY when the
#: decisive context for its own type is grounded.
_CLARITY_REQUIREMENT: dict[str, tuple[str, str, str]] = {
    "unanswered_email": (
        "obs:ask",
        "what response they need",
        "Open the email to see what they are actually asking before replying."),
    "commitment_overdue": (
        "fact:commitment.action",
        "the promised outcome",
        "Open the source thread to verify what you committed to before acting."),
    "meeting_no_followup": (
        "fact:meeting.description",
        "what to recap",
        "Open the calendar event to see what was discussed before sending a recap."),
}


def clarity_verdict(reason_code: str | None, obs_kinds: set[str],
                    fact_fields: set[str]) -> tuple[bool, str, str]:
    """Is this card's imperative grounded? Returns (ok, what_is_missing, what_to_do_instead).

    This logic already existed and was correct — and it ran in a read projection on a single
    endpoint, `GET /cards/{card_id}`, where it ADDED a sibling field rather than changing
    anything. The list view, which is the surface a user actually scans, applied no gate at all,
    so "Reply to boardy@boardy.ai now" was shown as a confident instruction while the detail view
    of the same card knew the ask was unknown.

    Deciding at BUILD time is what makes the verdict real: the card is written as an observation,
    with a non-imperative headline and no action button, so every reader sees the same thing.
    """
    requirement = _CLARITY_REQUIREMENT.get(str(reason_code or ""))
    if requirement is None:
        return True, "", ""
    needed, missing, recommended = requirement
    kind, _, name = needed.partition(":")
    grounded = bool(obs_kinds & _ASK_SIGNALS) if kind == "obs" else name in fact_fields
    return grounded, ("" if grounded else missing), ("" if grounded else recommended)


def _why_now(reason_code: str | None, facts: dict, slots: dict, eval_time) -> str | None:
    """What CHANGED to make this actionable — never elapsed time on its own.

    "It has been 9 days" is not a reason; it is a measurement, and presenting it as a reason is
    what manufactured urgency on threads where nothing had happened. A real why-now names the
    event: they asked something, a promise came due, a meeting ended.
    """
    days = slots.get("days")
    if reason_code == "commitment_overdue":
        action = _fval(facts, "commitment.action")
        return f"A promise came due{f': {action}' if action else ''}"
    if reason_code == "meeting_no_followup":
        title = _fval(facts, "meeting.title")
        return f"A meeting ended with no follow-up{f': {title}' if title else ''}"
    if reason_code == "unanswered_email":
        # Only a real ask makes this a why-now. Without one the clarity gate has already
        # downgraded the card, and inventing a reason here would undo that.
        return ("They are waiting on a reply"
                if isinstance(days, int) else None)
    return None


def _play_window(effective: dict, play_id: str | None) -> int | None:
    play = (effective.get("plays") or {}).get(str(play_id or ""), {})
    window = play.get("window_days")
    return int(window) if isinstance(window, int) else None


def _play_success(effective: dict, play_id: str | None) -> str | None:
    play = (effective.get("plays") or {}).get(str(play_id or ""), {})
    return play.get("success_signal") or None


def _require_level(signal: dict) -> str:
    """The signal's own level, or refuse to build the card.

    Silently defaulting is how the level literal in ``deliver/pipeline.py`` survived: every card
    carried `prescriptive`, so `select count(distinct level) from cards` returned 1 and the
    hardcoding was invisible from the data. A missing level is a broken producer, not a card
    that should ship as a command — the default that "feels safe" is the one that instructs.
    """
    level = (signal.get("level") or "").strip()
    if level not in VALID_LEVELS:
        raise ValueError(
            f"signal {signal.get('signal_id')!r} carries level {level!r}; expected one of "
            f"{sorted(VALID_LEVELS)}. A card must not infer its own authority.")
    return level


def load_node(store, org_id: str, node_id: str) -> tuple[str, str, dict, dict]:
    """(display_name, node_type, attributes, facts{field:{value,confidence,authority_rank}})."""
    with store.engine.connect() as c:
        nd = c.execute(text("select node_type, display_name, attributes from graph_nodes "
                            "where org_id=:o and node_id=:n and valid_to is null limit 1"),
                       {"o": org_id, "n": node_id}).first()
        facts: dict = {}
        for r in c.execute(text(
                "select field, value, confidence, authority_rank from graph_facts "
                "where org_id=:o and subject_node_id=:n and valid_to is null and status='active'"),
                {"o": org_id, "n": node_id}):
            v = r.value
            if isinstance(v, str):
                try:
                    v = json.loads(v)
                except (ValueError, TypeError):
                    pass
            facts[r.field] = {"value": v, "confidence": float(r.confidence),
                              "authority_rank": r.authority_rank}
    if nd is None:
        return "this account", "unknown", {}, facts
    attrs = nd.attributes if isinstance(nd.attributes, dict) else json.loads(nd.attributes or "{}")
    return (nd.display_name or "this account"), nd.node_type, attrs, facts


def load_evidence_quotes(store, org_id: str, node_id: str, limit: int = 8) -> list[dict]:
    """The counterparty's OWN WORDS, and the human name behind the address.

    The renderer's entire world was `graph_nodes` + `graph_facts` — two queries, about five typed
    key/value pairs — and it was then asked to write a thread-specific reply. The substance a
    person would use sits one join away and was never fetched: `graph_source_refs.evidence` holds
    the exact quoted sentence each observation was extracted from, and a `mention:person`
    observation holds the real name for an address the node is keyed on.

    That is why the copy has no content: there was no content in the prompt. Newest first, and
    bounded — the point is a handful of load-bearing quotes, not the whole thread.
    """
    try:
        with store.engine.connect() as c:
            rows = c.execute(text(
                "select o.kind, o.occurred_at, sr.evidence "
                "from graph_observations o "
                "join graph_source_refs sr on sr.observation_id = o.observation_id "
                "where o.org_id=:o and o.subject_node_id=:n and o.status='active' "
                "and o.kind not like 'email_noise%' "
                "order by o.occurred_at desc nulls last limit :lim"),
                {"o": org_id, "n": node_id, "lim": limit}).fetchall()
    except Exception:      # noqa: BLE001 — richer context is an enrichment, never a hard failure
        return []
    out: list[dict] = []
    for r in rows:
        ev = r.evidence if isinstance(r.evidence, dict) else {}
        quote = str(ev.get("text") or "").strip()
        if not quote:
            continue
        out.append({"kind": r.kind, "quote": quote[:300],
                    "name": str(ev.get("name") or "").strip() or None,
                    "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None})
    return out


def resolved_person_name(quotes: list[dict], fallback: str) -> str:
    """The human name for a node keyed on an email address.

    35 of 38 person cards named an address in the headline. The real name was already extracted —
    a `mention:person` observation carries `{"name": "Maria Exconde"}` — but the node's
    display_name stayed the address, so the headline spent its 60-character budget on
    "maria@alystventures.com" and the invention guard rejected any draft that wrote "Maria".
    """
    for q in quotes:
        if q.get("kind") == "mention:person" and q.get("name"):
            return q["name"]
    return fallback


def _real_sources(store, org_id: str, node_id: str) -> set[str]:
    """The TRUE app(s) behind this node's current facts, via graph_source_refs — never guessed from
    a field-name prefix. Fixes the bug where an LLM-extracted "deal.*" field from a Gmail email got
    tagged app:hubspot purely because its field name started with "deal.", regardless of the fact's
    actual (correctly-recorded) source."""
    with store.engine.connect() as c:
        rows = c.execute(text(
            "select distinct sr.source from graph_facts f "
            "join graph_source_refs sr on sr.fact_version_id = f.fact_version_id "
            "where f.org_id=:o and f.subject_node_id=:n and f.valid_to is null and f.status='active'"),
            {"o": org_id, "n": node_id}).fetchall()
    return {r.source for r in rows if r.source}


def _why(evidence: list, _facts: dict) -> list[dict]:
    """Project only evidence that the immutable reasoning context actually bound.

    A short evidence chain must stay short and honest. Unrelated current graph facts cannot be
    promoted into post-hoc reasons merely to satisfy a presentation count.
    """
    out = []
    for e in (evidence or []):
        if isinstance(e, str):
            out.append({"evidence_id": e, "source": "reasoning_trace"})
            continue
        if not isinstance(e, dict):
            continue
        field = e.get("field", "")
        out.append({"field": field, "value": e.get("value"),
                    "source": _SOURCE.get(field.split(".")[0], "graph")})
    return out


def _context_tags(node_type: str, attrs: dict, facts: dict, sources: set[str]) -> list[str]:
    """On-device matcher whitelist (§5.14). App tags come from each fact's REAL source_ref.source
    (graph_source_refs) — never guessed from a field-name prefix — plus a work-tool url_domain/tool
    path when the fact set carries one."""
    tags: set[str] = {_SOURCE_APP[s] for s in sources if s in _SOURCE_APP}
    domain = (attrs or {}).get("company_domain") or \
        (facts.get("deal.company_domain") or {}).get("value") or \
        (facts.get("company.domain") or {}).get("value")
    if domain:
        tags.add(f"url_domain:{domain}")
    deal_key = (attrs or {}).get("crm_deal_id") or (facts.get("deal.id") or {}).get("value")
    if deal_key:
        tags.add(f"hs:deal:{deal_key}")
    return sorted(tags)


def build_draft(store, org_id: str, signal: dict, effective: dict, eval_time) -> dict:
    """E0 output — a complete card.v1 minus the rendered copy (E1) and persisted state."""
    node_id = signal["subject_node_id"]
    name, node_type, attrs, facts = load_node(store, org_id, node_id)
    sources = _real_sources(store, org_id, node_id)
    reason_code = signal["reason_code"]

    scoring = effective.get("scoring", {})
    urgency_band = band(int(signal["score"]), scoring.get("bands"))
    assignee, rule = resolve_assignee(store, org_id, facts, attrs)
    # The rule's own declared clock, not a hand-written lookup. Each pack rule states the field
    # its urgency is timed from; the renderer used a 6-entry map and printed "severald" for the
    # other 19.
    clock_path = None
    for r in (effective.get("rules") or ()):
        if isinstance(r, dict) and r.get("reason_code") == reason_code:
            clock_path = (r.get("urgency") or {}).get("path")
            break
    slots = compute_slots(reason_code, name, facts, eval_time, clock_path)

    # Composite deal-health (C3): member concerns come from the immutable context payload bound to
    # the selected run, never from the mutable signal projection. Surface them as a `concerns` slot
    # and grounded fact so the renderer can compose the audited verdict.
    if reason_code == "deal_health":
        codes = [member.get("reason_code") for member in
                 (signal.get("composite_members") or ()) if isinstance(member, dict)]
        codes = list(dict.fromkeys(code for code in codes if code))
        if codes:
            concerns = ", ".join(str(c).replace("_", " ") for c in codes)
            slots["concerns"] = concerns
            facts = {**facts, "deal.concerns": {"value": concerns, "confidence": 1.0,
                                                "authority_rank": 3}}
    # THE COMPILED BRAIN'S OWN COPY FIRST. `effective["templates"]` is the TENANT PACK's, keyed
    # by the pack's own reason codes; a compiled signal's reason_code is its situation type
    # (`opportunity`, `relationship`, `investor_relationship`) and no pack authors those. The
    # lookup therefore returned `{}` for every compiled card — an empty render_hint, so the
    # prompt carried no guidance and eighteen cards came back reading alike, and an empty
    # fallback, so a rejected line shipped as the default `{stage}` slot: the word "open".
    #
    # A legacy signal carries no `capability_render` and falls through to the pack exactly as
    # before. Neither lane can take the other's copy: the compiled block travels on the audited
    # capability snapshot, the pack block on the tenant's effective config.
    capability_render = signal.get("capability_render")
    template = (dict(capability_render) if isinstance(capability_render, dict)
                and capability_render else
                (effective.get("templates", {}) or {}).get(reason_code, {}))
    play_id = (effective.get("plays", {}).get(signal.get("play") or "", {}) and signal.get("play"))

    actions = [
        {"type": "run_play", "play_id": signal.get("play"),
         "label": f"Draft {template.get('artifact_kind', 'response').replace('draft_', '')}",
         "artifact_ready": True},
        {"type": "do_it_myself"},
        {"type": "snooze", "options": ["4h", "tomorrow_09", "3d", "custom"]},
        {"type": "wrong", "reasons": ["not_relevant", "bad_timing", "wrong_facts"]},
    ]
    # CLARITY GATE, at build time. When the fact that gives this card's imperative its meaning is
    # absent, the card is WRITTEN as an observation: no run_play button, and a stated reason. The
    # same verdict used to be computed in a read projection on one endpoint and merely annotated
    # there, so the list view — the surface anyone actually scans — showed the imperative anyway.
    level = _require_level(signal)
    abstained = signal.get("abstained_because")
    grounded, missing, recommended = clarity_verdict(
        reason_code, {str(o.get("kind")) for o in (signal.get("observations") or ())},
        set(facts))
    if not grounded:
        level = str(_ABSTENTION.OBSERVATION)
        abstained = abstained or f"missing {missing} — {recommended}"
        # A card that cannot say what to do must not offer a button that claims to do it. `wrong`
        # and `snooze` remain: the user must still be able to dismiss or defer it.
        actions = [a for a in actions if a.get("type") in ("wrong", "snooze")]

    score_inputs = signal.get("score_inputs") or {}
    card_expires_at = eval_time + timedelta(days=EXPIRY_DAYS)
    decision_expires_at = signal.get("decision_expires_at")
    if isinstance(decision_expires_at, str):
        try:
            decision_expires_at = datetime.fromisoformat(
                decision_expires_at.replace("Z", "+00:00"))
        except ValueError:
            decision_expires_at = None
    if isinstance(decision_expires_at, datetime):
        if decision_expires_at.tzinfo is None or decision_expires_at.utcoffset() is None:
            raise ValueError("decision_expires_at must be timezone-aware")
        card_expires_at = min(card_expires_at,
                              decision_expires_at.astimezone(timezone.utc))

    return {
        "signal_id": signal["signal_id"], "org_id": org_id, "subject_node_id": node_id,
        # Fail closed on level: defaulting to "prescriptive" is what let the pipeline's hardcoded
        # literal go unnoticed, turning every predictive risk warning into a direct order.
        "domain": effective.get("pack_id", "sales"), "level": level,
        # A card that declines to instruct without saying why is indistinguishable from one that
        # broke — the user cannot tell "we do not know enough" from "something failed".
        "abstained_because": abstained,
        "urgency_band": urgency_band, "assignee": assignee, "resolved_rule": rule,
        "score": int(signal["score"]),
        "score_block": {"S": int(signal["score"]), **{k: score_inputs.get(k) for k in
                        ("U", "I", "R", "C")}, "inputs": score_inputs},
        # ── The Customer Intelligence Contract ────────────────────────────────────────────
        # Six of the twelve answers a promoted item must give had no column at all, and two of
        # them (`stakes`, `completion`) were the literal string "missing", written into the read
        # projection at request time. Producing them HERE makes card_builder the single producer
        # of the contract instead of a request-time projection inventing what it can.
        #
        # Every one of these is populated from something the engine already computed. None is
        # inferred: a NULL means this card genuinely never carried that answer, which is the
        # measurement the scorecard needs.
        "business_subject": name,                      # the counterparty, not the GeniOS seat
        "relationship_role": _fval(facts, "party.role"),
        "unresolved_item": _fval(facts, "commitment.action") or slots.get("action") or None,
        "why_now": _why_now(reason_code, facts, slots, eval_time),
        "capability_key": signal.get("capability_id"),
        "capability_version": signal.get("capability_version"),
        # Unreviewed expertise must not instruct — the same state the abstention gate reads.
        # The SIGNAL's own value first: it records the review state of the exact package that
        # authored this decision, while `effective` describes the tenant's config as a whole. A
        # legacy signal carries none and falls through to the config, exactly as before.
        "capability_review_state": str(
            signal.get("capability_review_state")
            or (effective.get("expertise") or {}).get("review_state") or "unreviewed"),
        # The DECISION's own values first; the pack template only fills a pre-0070 signal.
        # These came from ReasoningDecision at emit time — the pack fallback is a config author's
        # generic estimate, not this decision's judgment.
        "outcome_window_days": (signal.get("decision_window")
                                or _play_window(effective, signal.get("play"))),
        "success_signal": _play_success(effective, signal.get("play")),
        "do_nothing_consequence": signal.get("do_nothing_consequence"),
        "candidate_steps": signal.get("candidate_steps") or [],
        "rejected_candidates": signal.get("rejected_candidates") or [],
        "uncertainty": signal.get("uncertainty") or [],
        # Decomposed, not a scalar: "unsure about the evidence" and "unsure about the timing"
        # call for different user actions and a single number cannot tell them apart.
        "confidence_vector": {k: score_inputs.get(k) for k in ("C", "U", "I", "R")},
        "actions": actions, "why": _why(signal.get("evidence"), facts),
        "context_tags": _context_tags(node_type, attrs, facts, sources),
        "config_snapshot_id": signal.get("config_snapshot_id"),
        "template_version": (effective.get("templates", {}) or {}).get("_version"),
        "expires_at": card_expires_at,
        # carried forward to E1 (not persisted as-is)
        "_reason_code": reason_code, "_template": template, "_facts": facts, "_slots": slots,
    }
