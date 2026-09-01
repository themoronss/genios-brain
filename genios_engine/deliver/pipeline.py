from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.packs.wiring import ensure_default, make_registry
from genios_engine.reason.authority import (
    AUTHORITATIVE_REASON_CODE_SQL,
    AUTHORITATIVE_SCORE_SQL,
    AUTHORITATIVE_SCORE_INPUTS_SQL,
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
    authority_time,
)

from genios_engine.contracts.abstention import downgrade_to_observation, is_actionable
from .card_builder import BUILDER_VERSION, build_draft, load_evidence_quotes
from .render import render_copy
from .router import budget_full
from genios_engine.contracts.abstention import is_actionable

from .store import CardStore

# L5 pipeline — turn gated signals into delivered cards. Runs after L3 (in-process background, no
# Celery). One card per open signal: E0 compose → E1 render (one temp-0 call, validated) → E3
# budget → persist at 'queued'. Cards only build from signals that already passed L3's gate, so
# the model runs at most budget_per_day times per org — cheap by construction.


def _open_signals_without_cards(graph, org_id: str,
                                evaluation_time: datetime | None = None) -> list[dict]:
    as_of = authority_time(evaluation_time)
    with graph.engine.connect() as c:
        rows = c.execute(text(
            "select s.signal_id, " + AUTHORITATIVE_REASON_CODE_SQL +
            # s.level, never a literal: the pack authors 11 of 25 rules as `predictive`, and
            # hardcoding `prescriptive` here rendered every risk warning as a direct command.
            " as reason_code, s.level as level, s.subject_node_id, "
            + AUTHORITATIVE_SCORE_SQL + " as score, " +
            AUTHORITATIVE_SCORE_INPUTS_SQL + " as score_inputs, "
            "coalesce(authority_payload.payload->'evidence', selected_rc.evidence_refs) "
            "as evidence, authority_payload.payload->'facts'->'signals.open' "
            "as composite_members, "
            "selected_rc.play_id as play, s.config_snapshot_id, "
            "authority_cfg.effective as effective_config, "
            "authority_cfg.pack_id, s.authority_expires_at as decision_expires_at, "
            "s.reasoning_run_id, s.reasoning_candidate_id, s.reasoning_decision_hash, "
            # WHICH BRAIN authored this. card_builder has always read `capability_id` for a card's
            # capability_key (0074 added the columns), but this SELECT never carried them, so the
            # read returned None and every card — compiled or legacy — looked identically like
            # legacy output. Without these three the cutover cannot be measured from `cards` at
            # all: NULL would mean "legacy" and "compiled" at the same time.
            "s.capability_id, s.capability_version, s.capability_review_state, "
            # The compiled brain's OWN card copy, off the audited capability snapshot `rcap`
            # (already joined for the authority predicate). card_builder used to look a template
            # up in the tenant pack by reason_code, and a compiled signal's reason_code is its
            # situation type — which no pack authors. So every compiled card rendered against an
            # empty template: no guidance reached the prompt, and the fallback shipped the bare
            # `{stage}` slot, the literal word "open", as the situation line on ten of the design
            # partner's eighteen live cards.
            "rcap.manifest->'metadata'->'render' as capability_render, "
            # The DecisionObject's own content (0070). Reading it here is what retires the API
            # layer's reason_code if/elif chain as the source of a card's recommendation.
            "s.do_nothing_consequence, s.uncertainty, s.outcome_window_days as decision_window, "
            "s.rejected_candidates, s.candidate_steps "
            "from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
            " left join reasoning_context_payloads authority_payload "
            "on authority_payload.org_id=authority_ctx.org_id and "
            "authority_payload.context_snapshot_id=authority_ctx.context_snapshot_id "
            # Excludes an EXPIRED card from the join on purpose: an expired card used to permanently
            # block a still-open signal from ever getting a fresh one (k.card_id was never null
            # again), which is why signals that predate the no-auto-expiry fix (card_builder.py)
            # were stuck invisible forever even though the underlying signal was still open and
            # valid. A non-expired card (queued/surfaced/snoozed/claimed/resolved) still counts as
            # "already has a card" — only 'expired' reopens the door for a rebuild.
            # A STALE card no longer blocks either. The join already excluded expired cards for
            # the same reason this excludes out-of-date ones: a card that is not going to be
            # looked at, or that was composed by a builder we have since improved, is not a
            # reason to withhold a better one. Untouched states only — a card the user snoozed,
            # claimed, acted on or resolved is their answer, and re-deriving it is not a fix.
            # `CardStore.claim_build` re-checks the same condition transactionally; this join is
            # what stops the signal being filtered out before the claim is ever attempted.
            " left join cards k on k.signal_id=s.signal_id and k.org_id=s.org_id "
            "and k.state != 'expired' "
            "and not (k.builder_version is distinct from :builder "
            "         and k.state = any(:refreshable) and k.resolved_at is null) "
            "where s.org_id=:o and s.status='open' and k.card_id is null and " +
            AUTHORITATIVE_SIGNAL_PREDICATE +
            " order by selected_rc.final_utility_bp desc, s.signal_id asc"),
            {"o": org_id, "authority_time": as_of,
             "builder": BUILDER_VERSION,
             "refreshable": list(CardStore.REFRESHABLE_STATES)}).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        for jf in ("score_inputs", "evidence", "composite_members", "capability_render"):
            if isinstance(d.get(jf), str):
                try:
                    d[jf] = json.loads(d[jf])
                except (ValueError, TypeError):
                    d[jf] = {} if jf in ("score_inputs", "capability_render") else []
        out.append(d)
    return out


def _apply_abstention(signal: dict, effective: dict) -> dict:
    """Downgrade an instruction to an observation when nothing authorises instructing.

    Authority, not confidence — a low-confidence prescription is still read and acted on as an
    instruction, so the question is only ever "did reviewed expertise back this decision?".

    TWO authority sources, and reading only the second is what downgraded 15 of 15 live cards:

      * a COMPILED expertise package, whose `review_state` says whether a named human accepted
        the corpus behind it (`effective["expertise"]`), or
      * the TENANT'S ACTIVE PACK — which is itself authored, content-addressed, versioned and
        explicitly promoted per tenant (`tenant_packs.state='active'`). A promoted pack is a
        human saying "these rules may instruct my org"; treating it as unreviewed made every
        card carry a "reply now" headline over an `observation` level, so the two halves of the
        same card contradicted each other on every single row.

    The reason travels with the card. An abstention with no stated cause is indistinguishable
    from a bug: the user cannot tell "outside my coverage" from "something broke".
    """
    if not is_actionable(signal.get("level")):
        return signal
    review_state = str((effective.get("expertise") or {}).get("review_state") or "").lower()
    if review_state in ("accepted", "reviewed"):
        return signal
    # The pack path. `state` comes from tenant_packs via registry.effective(); only an ACTIVE
    # promotion carries instructing authority — a paused or draft pack falls through to the
    # downgrade below exactly as an unaccepted corpus does.
    if str(effective.get("state") or "").lower() == "active":
        return signal
    level, reason = downgrade_to_observation(
        signal.get("level"),
        reason=("no accepted expertise for this situation — showing what was observed, "
                "not what to do"))
    return {**signal, "level": level, "abstained_because": reason}


def _tenant_identities(graph, org_id: str) -> tuple[str, ...]:
    """The account holder's own names and addresses, for the render grounding corpus.

    Signing a draft "Best, Rohit" is not a claim the facts have to support — it is the sender
    naming himself. The corpus was built from the card SUBJECT's facts only, so the founder's own
    name read as an invented person and the entire card fell back to an empty template stub.
    """
    try:
        with graph.engine.connect() as c:
            row = c.execute(text(
                "select name, first_name, last_name, email, company from orgs where id=:o"),
                {"o": org_id}).first()
            seats = [r[0] for r in c.execute(text(
                "select email from org_seats where org_id=:o and active and email is not null"),
                {"o": org_id})]
    except Exception:      # noqa: BLE001 — grounding is an enrichment, never a reason to fail
        return ()
    if row is None:
        return tuple(seats)
    parts = [row.name, row.first_name, row.last_name, row.email, row.company, *seats]
    return tuple(str(p).strip() for p in parts if p and str(p).strip())


#: The cohort card already carries a line for these people, so a card each says nothing new.
#:
#: A campaign of five silent contacts produced five per-person cards AND one cohort card, and six
#: cards about one campaign is not six pieces of intelligence. But suppressing all five would be
#: wrong in the other direction: the per-person judgment DIFFERS once somebody has been chased —
#: "chased twice with no reply, another reminder is unlikely to be what changes this" is an
#: instruction about that relationship, and the cohort's aggregate cannot make it.
#:
#: So only the never-chased are absorbed. The cohort states them as a group ("never chased: 3")
#: and names them in its own artifact, which is exactly as much as an individual card for one of
#: them would have said. Everyone the cohort can only count keeps their own card.
#:
#: THIS IS A DELIVERY POLICY AND IT LIVES HERE DELIBERATELY. Layer 2 mints both situations because
#: both are true; deciding that one presentation makes the other redundant is a judgment about
#: what a person should be shown, which is this layer's job and not the context graph's.
_COHORT_REASON = "cohort_outreach_gap"
_MEMBER_REASON = "awaiting_response"


#: How many cards of ONE reason code may be surfaced in a single build pass.
#: Three is enough to show a pattern is real and few enough that it cannot own the queue.
_MAX_SURFACED_PER_REASON = 3


def _cohort_absorbed(graph, org_id: str, signals: list[dict]) -> set[str]:
    """Signal ids whose per-person card the cohort card in this same pass already covers.

    Computed over the WHOLE signal list before any card is built, so the outcome does not depend
    on which card happened to be built first — the same pass must produce the same queue however
    the rows were ordered.
    """
    objectives = {str(s.get("reason_code") or ""): None for s in signals}
    if _COHORT_REASON not in objectives or _MEMBER_REASON not in objectives:
        return set()
    subjects = [str(s["subject_node_id"]) for s in signals if s.get("subject_node_id")]
    if not subjects:
        return set()
    with graph.engine.connect() as c:
        rows = c.execute(text(
            "select subject_node_id, field, value from graph_facts "
            "where org_id=:o and subject_node_id = any(:n) and valid_to is null "
            "and status='active' and field in "
            "('cohort.objective','outreach.objective','outreach.follow_up_count')"),
            {"o": org_id, "n": subjects}).fetchall()
    held: dict[str, dict] = {}
    for row in rows:
        value = row.value
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (TypeError, ValueError):
                pass
        held.setdefault(str(row.subject_node_id), {})[str(row.field)] = value

    covered = {str(held.get(str(s["subject_node_id"]), {}).get("cohort.objective") or "")
               for s in signals if s.get("reason_code") == _COHORT_REASON}
    covered.discard("")
    if not covered:
        return set()

    absorbed: set[str] = set()
    for sig in signals:
        if sig.get("reason_code") != _MEMBER_REASON:
            continue
        facts = held.get(str(sig.get("subject_node_id") or ""), {})
        if str(facts.get("outreach.objective") or "") not in covered:
            continue
        chased = facts.get("outreach.follow_up_count")
        # Absent is NOT zero. A member whose chase count could not be computed keeps its card:
        # the cohort's "never chased: N" line does not include them, so absorbing them would
        # remove the only place they appear.
        if isinstance(chased, bool) or not isinstance(chased, (int, float)):
            continue
        if int(chased) == 0:
            absorbed.add(str(sig["signal_id"]))
    return absorbed


def build_cards_for_org(*, graph, card_store: CardStore, org_id: str, llm=None,
                        registry=None, eval_time: datetime | None = None) -> dict:
    """E0→E1→E3→persist for every open, un-carded signal. Returns delivery counts."""
    eval_time = eval_time or datetime.now(timezone.utc)
    registry = registry or make_registry()
    ensure_default(registry, org_id)
    out = {"built": 0, "refreshed": 0, "already_built": 0, "build_in_progress": 0,
           "llm": 0, "raw_slot": 0, "unrouted": 0,
           "absorbed_by_cohort": 0,
           "over_budget_no_push": 0,
           "not_pushed_abstained": 0, "not_pushed_reason_saturated": 0,
           "pushed": 0, "agent_pushed": 0}
    from .bands import band
    # How many of one situation type may interrupt in a single pass. Counted per pass rather than
    # per day: the point is that a finding which fires across ten accounts is one thing to tell
    # somebody, and the tenth copy carries no information the first did not.
    surfaced_by_reason: dict[str, int] = {}
    identities = _tenant_identities(graph, org_id)   # once per org, not per card
    signals = _open_signals_without_cards(graph, org_id, eval_time)
    absorbed = _cohort_absorbed(graph, org_id, signals)
    for sig in signals:
        if sig["signal_id"] in absorbed:
            # Counted, never silent. A suppressed card is a decision this layer made about what
            # the user sees, and a suppression nobody can see the size of is indistinguishable
            # from a bug that lost cards.
            out["absorbed_by_cohort"] += 1
            continue
        claim_token = card_store.claim_build(
            org_id, sig["signal_id"], eval_time=eval_time,
            builder_version=BUILDER_VERSION)
        if claim_token is None:
            out["build_in_progress"] += 1
            continue
        try:
            effective = sig.pop("effective_config", {})
            if isinstance(effective, str):
                effective = json.loads(effective or "{}")
            if not isinstance(effective, dict):
                continue
            bands_cfg = effective.get("scoring", {}).get("bands")
            budget = int(effective.get("scoring", {}).get("budget_per_user_day", 7))
            # ABSTENTION GATE. A card may only instruct when the expertise behind it has been
            # reviewed and accepted. The corpus currently holds 152 capabilities, 0 of them
            # accepted, so every prescription shipped on unreviewed authority — the system was
            # structurally unable to say "this is outside what I have been taught". Downgrading
            # keeps the observation (which is real and useful) and drops only the instruction.
            sig = _apply_abstention(sig, effective)
            # LOADED BEFORE THE BUILD, and that ordering is the fix to a gate that could never
            # have fired. `build_draft` runs `clarity_verdict` over `signal["observations"]` — and
            # this line used to come AFTER the build, so the gate read an empty list on every card
            # ever built and could only ever return "grounded". It survived unnoticed because the
            # compiled lane's reason codes are not in its map either.
            #
            # What the counterparty actually said, their real name, and who said it. All three
            # were already in the graph and none reached the renderer, which is why 37 of 41 cards
            # shipped as template stubs with an empty draft body. `identities` is passed so the
            # loader can tell the founder's own outgoing sentences from the counterparty's.
            quotes = load_evidence_quotes(
                graph, org_id, sig["subject_node_id"], identities=identities)
            # The clarity gate needs to know WHAT they asked for, not only that they wrote. The
            # kinds come from the same evidence the renderer now receives, so the gate and the
            # copy are reasoning about one set of facts rather than two.
            sig = {**sig, "observations": [{"kind": q.get("kind")} for q in quotes]}
            draft = build_draft(graph, org_id, sig, effective, eval_time,   # E0
                                quotes=quotes)
            copy = render_copy(                                                    # E1
                reason_code=draft["_reason_code"], template=draft["_template"],
                facts=draft["_facts"], slots=draft["_slots"], llm=llm,
                cost_sink=graph.record_cost, org_id=org_id,
                # The tenant's own names and addresses. A draft signed by the account holder is
                # not inventing them, but the grounding corpus was built from the SUBJECT's facts
                # alone, so "Best, Rohit" was rejected as a hallucinated person on the founder's
                # own outgoing mail — and the whole card shipped as an empty stub because of it.
                identities=identities, quotes=quotes,
                subject_ref=f"signal:{sig['signal_id']}")
            # artifact_ready must reflect the REAL render — a raw-slot fallback has an empty body,
            # so Run Play must not advertise a ready draft.
            ready = bool((copy.get("artifact") or {}).get("body"))
            for action in draft["actions"]:
                if action.get("type") == "run_play":
                    action["artifact_ready"] = ready
            draft["_authority"] = {
                "reasoning_run_id": sig["reasoning_run_id"],
                "reasoning_candidate_id": sig["reasoning_candidate_id"],
                "reasoning_decision_hash": sig["reasoning_decision_hash"],
                "config_snapshot_id": sig["config_snapshot_id"],
            }
            draft["_authority_time"] = eval_time
            over_budget = budget_full(card_store, org_id, draft["assignee"], eval_time, budget)
            if over_budget:
                out["over_budget_no_push"] += 1
            card_id, created, refreshed = card_store.insert_card(
                draft, copy, build_claim_token=claim_token)
            if card_id is None or not created:
                if refreshed:
                    # The words on an existing card improved. Counted apart from `already_built`
                    # because they mean opposite things — one is work done, the other is work
                    # correctly skipped — and deliberately NOT pushed: the user has already been
                    # shown this card, and a rewrite is not a new event to interrupt them with.
                    out["refreshed"] += 1
                    out["llm" if copy["render_mode"] == "llm" else "raw_slot"] += 1
                elif card_id is not None:
                    out["already_built"] += 1
                continue
            out["built"] += 1
            out["llm" if copy["render_mode"] == "llm" else "raw_slot"] += 1
            try:
                # ENQUEUED, not POSTed. The inline send from inside this build loop was the
                # exact anti-pattern the outbox exists for: one slow client webhook degraded
                # the whole org's card build, and the delivery appeared in no outbox, retry
                # schedule, dead letter or analytics. The drain sends it with the same
                # authority recheck and backoff ladder every human delivery gets.
                from .outbox import enqueue_agent_push
                out["agent_pushed"] += enqueue_agent_push(graph.engine, org_id, card_id)
            except Exception:                                  # noqa: BLE001
                pass
            if draft["assignee"] is None:
                out["unrouted"] += 1
            # WHAT MAY INTERRUPT SOMEBODY. Three conditions, and only the first was ever checked.
            #
            # 1. A CARD THAT DECLINED TO ADVISE MUST NOT PUSH. `contracts/abstention.is_actionable`
            #    has existed all along and this decision never consulted it, so a `review` card —
            #    one whose own body says "there is no instruction to give, a human must look" —
            #    was pushed on exactly the same terms as a recommendation. On the design partner's
            #    org that was 18 of the 24 surfaced cards, while 28 PRESCRIPTIVE ones sat queued
            #    behind them. The queue was full of the system saying it could not help.
            #
            #    Abstaining cards are not suppressed; they stay queued and are read when the user
            #    opens the app. The distinction is interruption, not visibility.
            #
            # 2. ONE SITUATION MAY NOT FLOOD THE SURFACE. `deal_without_a_stated_problem` fired on
            #    ten accounts, scored every one 75/critical, and took ten of the surfaced slots.
            #    Ten identical scores are one finding about a pattern, not ten urgencies, and the
            #    eleventh through twentieth tell the reader nothing the first did not. The rest
            #    stay queued and are still there when the user looks.
            #
            # 3. The band and budget checks, unchanged.
            reason_code = str(sig.get("reason_code") or "")
            floods = surfaced_by_reason.get(reason_code, 0) >= _MAX_SURFACED_PER_REASON
            if not is_actionable(draft.get("level")):
                out["not_pushed_abstained"] += 1
            elif floods:
                out["not_pushed_reason_saturated"] += 1
            elif (band(int(sig["score"]), bands_cfg) in ("high", "critical")
                    and draft["assignee"] and not over_budget
                    and card_store.transition(
                        card_id, org_id, "surfaced", "card.surfaced", cause="push",
                        allowed_from=("queued",))):
                out["pushed"] += 1
                surfaced_by_reason[reason_code] = surfaced_by_reason.get(reason_code, 0) + 1
        finally:
            card_store.release_build(org_id, sig["signal_id"], claim_token)
    return out
