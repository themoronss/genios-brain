from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.packs.wiring import ensure_default, make_registry
from genios_engine.contracts import card_contract
from genios_engine.platform.self_identity import SelfIdentity, identity_for
from .lane_display import TALLY_KEYS, tally_lane
from .lane_recall import recall_verdict
from genios_engine.reason.authority import (
    AUTHORITATIVE_REASON_CODE_SQL,
    AUTHORITATIVE_SCORE_SQL,
    AUTHORITATIVE_SCORE_INPUTS_SQL,
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
    QUESTION_SIGNAL_JOINS,
    QUESTION_SIGNAL_PREDICATE,
    authority_time,
)

from genios_engine.contracts.abstention import downgrade_to_observation, is_actionable
from genios_engine.contracts.outcomes import interrupts, project
from genios_engine.deliver.render import state_not_command
from .card_builder import BUILDER_VERSION, SubjectIsUs, build_draft, load_evidence_quotes
from .render import _corpus, render_copy, review_copy
from genios_engine.reason.expert.decide import is_expert
from .router import budget_full

from .store import QUESTION_CARD_BUILDER, CardStore

# L5 pipeline — turn gated signals into delivered cards. Runs after L3 (in-process background, no
# Celery). One card per open signal: E0 compose → E1 render (one temp-0 call, validated) → E3
# budget → persist at 'queued'. Cards only build from signals that already passed L3's gate, so
# the model runs at most budget_per_day times per org — cheap by construction.


def _activated_features(graph, org_id: str) -> frozenset[str]:
    """The tenant's activation rows. Never raises: a delivery pass that dies because it could not
    read a feature flag is a pass that lost every card to an accounting question."""
    try:
        from genios_engine.platform.l4_activation import activated_features

        return frozenset(activated_features(graph.engine, org_id))
    except Exception:      # noqa: BLE001 — an unreadable flag means the OLD path, which is safe
        return frozenset()


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
            # STEP-11 · WHAT THE PLAY SAID SUCCESS IS, AND WHETHER A HUMAN REVIEWED ITS PLAYBOOK, off
            # `authority_play` — the very manifest entry the authority join already proved is the
            # selected candidate's play — and the corpus the capability was compiled from. A card's
            # success line read only the tenant pack's `plays`, which are `{}` for every corpus pack,
            # so no compiled card could ever name one (M30.C3.L-data.V1.U03); the review state is
            # what D3's "playbook not yet reviewed" is decided on.
            "authority_play.declared_play->'success_events' as play_success_events, "
            # STEP-14 · THE MOVE WHOLE, off the same audited play (`reason/expert/decide._play`): who, what, for
            # whom, by when, to whom — what a file card's version names as its ask, recipient and date (s14-D1).
            "authority_play.declared_play->'metadata' as play_metadata, "
            "authority_play.declared_play->'metadata'->>'review_state' as play_review_state, "
            "rcap.manifest->>'domain' as capability_domain, "
            # The DecisionObject's own content (0070). Reading it here is what retires the API
            # layer's reason_code if/elif chain as the source of a card's recommendation.
            "s.do_nothing_consequence, s.uncertainty, s.outcome_window_days as decision_window, "
            "s.rejected_candidates, s.candidate_steps, "
            # CLG-08's citations (0114). Selected here because a quote that reaches the signal row
            # and not the card is a quote that reached nobody: `scripts/l3_pilot_report.py`
            # measured `cards_quoting_the_claim_in_their_own_copy` at 0 on every card ever built,
            # and the cause was this column having no reader between the emitter and the surface.
            "s.citations, "
            # ⛔ WHICH LANE. `0189` added these and `domain_shadow` writes them on every
            # routed decision; until this line nothing in `deliver/` read either, so the
            # vocabulary was built, tested, green and called by nothing. NULL is carried as
            # NULL — `lane_display.describe` labels it `unrouted` rather than guessing
            # `decision`, because a default here would have the card assert an authority no
            # router granted it.
            "s.output_lane, s.lane_reason "
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
        for jf in ("score_inputs", "evidence", "composite_members", "capability_render",
                   "play_success_events", "play_metadata"):
            if isinstance(d.get(jf), str):
                try:
                    d[jf] = json.loads(d[jf])
                except (ValueError, TypeError):
                    d[jf] = {} if jf in ("score_inputs", "capability_render", "play_metadata") else []
        out.append(d)
    return out


def _open_situations_without_cards(graph, org_id: str,
                                   evaluation_time: datetime | None = None) -> list[dict]:
    """L2-7 · the sibling of the selector above. **One row per SITUATION, not per signal.**

    ⛔ **THE FAN-OUT IS AT THE RULE, NOT THE SIGNAL.** `domain_shadow._emit_capability_signal`
    writes one open signal per `(pack, rule, node)`, so one situation that fires three rules
    becomes three cards — *"Nitesh's inbound messages dropping"*, *"Nitesh Pant's touch frequency
    declining"*, *"Check in with Nitesh Pant"*. They can never merge while the builder loops over
    signals.

    ⛔ **AND `subject_node_id` IS NOT A SUBSTITUTE FOR `situation_id`.** `context_situations` is
    unique on `(org_id, correlation_id)`, so one node carries several genuinely different
    situations — a support case and an admin follow-up about the same person. Grouping cards by
    node would merge things that are not the same thing, which is worse than the fan-out it fixes.

    ⛔ **AND A NULL `situation_id` IS NOT EXCLUDED HERE.** It is grouped as its own bucket, so the
    caller can surface it labelled rather than never seeing it — see `deliver/card_source`. *"If
    every signal must belong to a situation to be seen, a correlator gap becomes a silent
    disappearance."*

    BUILT BESIDE THE OLD ONE, NOT OVER IT. `_open_signals_without_cards` is untouched and stays
    runnable for one release, because §4 of the step says the two paths are compared on one sweep
    before either is retired.
    """
    as_of = authority_time(evaluation_time)
    with graph.engine.connect() as c:
        rows = c.execute(text(
            "select s.situation_id, "
            # The signals this situation produced, oldest first — the card builder needs every
            # one of them, and their ORDER is what makes two sweeps render the same card.
            "array_agg(s.signal_id order by s.eval_time, s.signal_id) as signal_ids, "
            "count(*) as signal_count, "
            "min(s.subject_node_id) as subject_node_id, "
            "max(s.eval_time) as eval_time "
            "from signals s "
            "left join cards k on k.org_id=s.org_id and k.signal_id=s.signal_id "
            "  and k.state not in ('expired','dismissed') "
            "where s.org_id=:o and s.status='open' and k.card_id is null "
            "  and (s.authority_expires_at is null or s.authority_expires_at > :as_of) "
            # NULL groups as its own row. `group by` treats every NULL as equal in Postgres, so
            # the uninterpreted signals arrive as ONE bucket the caller can count and label —
            # never as rows that quietly fail the join.
            "group by s.situation_id "
            "order by max(s.eval_time) desc"),
            {"o": org_id, "as_of": as_of}).mappings().all()
    return [dict(r) for r in rows]


# ── STEP-13 · THE QUESTION CARD (`yc2_w27_s13` M36.C2.L-interface.V3.U05; `06` D60) ─────────────────────────────
#
# A held file asks the founder ONE question (`reason/expert/asks`), and the question signal is authorised as
# a question (`reason/authority.QUESTION_SIGNAL_PREDICATE`) — never as a decision, so the selector above never
# returns it. Each open question signal with no live card gets its card, by its own builder
# (`store.QUESTION_CARD_BUILDER`) and through its own door (`store.QUESTION_CARD_SQL`): the question as its
# headline, the file as the expert read it as its situation, the Investigation lane, an Answer action. It is
# the file's one card — a new question or a decision retires it (`asks`), and a re-asked question keeps it.
_QUESTIONS_WITHOUT_CARDS = (
    "select s.signal_id, s.subject_node_id, s.pack_id, s.score, s.config_snapshot_id, "
    "s.reasoning_run_id, s.reasoning_decision_hash, s.authority_expires_at, s.output_lane, s.lane_reason, "
    "s.capability_id, s.capability_version, s.capability_review_state, "
    "question_asked.question_id, question_asked.question, question_asked.why, "
    "question_asked.fingerprint, question_rr.trigger_ref as asking_review "
    "from signals s " + QUESTION_SIGNAL_JOINS +
    # The same rule as the decision selector's join: an expired card reopens the door, and so does a
    # stale one nobody has touched; any other card is the file's answer already.
    "left join cards k on k.signal_id=s.signal_id and k.org_id=s.org_id and k.state != 'expired' "
    "and not (k.builder_version is distinct from :builder "
    "         and k.state = any(:refreshable) and k.resolved_at is null) "
    "where s.org_id=:o and s.status='open' and k.card_id is null and " + QUESTION_SIGNAL_PREDICATE +
    " order by s.eval_time, s.signal_id")

#: What a question card offers: your answer, or later. A question is not an instruction, so there is
#: nothing to run and nothing to do yourself; `wrong` waits for STEP-16, which learns from it.
QUESTION_ACTIONS = ("answer", "snooze")
#: What answering does, and what waiting on the question costs (STEP-11's founder-card clause: every founder
#: card says both). OURS, CLOSED (STEP-13 M36.C2.L-logic.V2.U10): a question carries no playbook outcome and
#: no model prose may stand in for one — and no play window either, so its `outcome_window_days` stays None.
QUESTION_SUCCESS_SIGNAL = "you answered: your words are kept on the file and its next review reads them"
QUESTION_DO_NOTHING = "nothing on this file moves until you answer"


def _open_questions_without_cards(graph, org_id: str, evaluation_time: datetime | None = None) -> list[dict]:
    with graph.engine.connect() as c:
        return [dict(r) for r in c.execute(text(_QUESTIONS_WITHOUT_CARDS), {
            "o": org_id, "authority_time": authority_time(evaluation_time),
            "builder": QUESTION_CARD_BUILDER,
            "refreshable": list(CardStore.REFRESHABLE_STATES)}).mappings()]


def question_card(graph, org_id: str, row: dict, eval_time: datetime) -> tuple[dict, dict]:
    """The card a held file asks its question on, and its copy — every word the question's or the file's
    checked review's own; nothing written for it. Its situation is the expert's reading of the file as the
    check let it stand, labelled an inference; with none, why the file asks.

    ⛔ IN CHECKED WORDS, OR OURS (STEP-13 M36.C2.L-logic.V2.U10, `03` X06, X10). Why the file asks is one of
    `reason/expert/asks.WHYS` — closed, founder-facing — and so is the situation when the check withheld the
    reading: never the raw reading, never the check's internal reason. A question filed before its words
    were checked carries some other `why`; it is carded with the closed phrase, never with that prose."""
    from datetime import timedelta

    from genios_engine.reason.expert import store as reviews
    from genios_engine.reason.expert.asks import WHY_FIND_OUT, WHYS
    from genios_engine.contracts.card_version import QUESTION_MODE
    from genios_engine.reason.expert.decide import SITUATION_IS, fingerprint_of

    from .bands import band
    from .card_builder import EXPIRY_DAYS, _group_memberships, load_node
    from .lane_display import describe
    from .router import resolve_assignee

    node = row["subject_node_id"]
    name, _node_type, attrs, facts = load_node(graph, org_id, node)
    # WHOEVER THE FILE'S DECISION WOULD REACH: the same routing, so a question goes where its answer is.
    assignee, rule = resolve_assignee(graph, org_id, facts, {**(attrs or {}), **_group_memberships(
        graph, org_id, node)})
    # THE REVIEW ASKING IT NOW (STEP-13 M36.C2.L-integration.V2.U11, `03` X41): the same words asked by a later
    # review re-bind the question to the run asking now, whose trigger is that review (`reason/expert/decide`);
    # the question's own fingerprint is the review that asked it FIRST.
    with graph.engine.connect() as c:
        # The asking run's key names the review and its check (`decide.decision_ref`, STEP-13 X12); the review is
        # read by its fingerprint.
        asking = fingerprint_of(row.get("asking_review"))
        review = reviews.read_review(c, org_id, node, str(asking or row["fingerprint"]))
    checked = review.checked if review is not None else None
    # STEP-14 (`yc2_w27_s14` M43.C3.L-interface.V3.U03): the gold shape too — the file's person, role, why now and what
    # remains, from the lines its review kept (0221); none on a review stored before, and the card is as built.
    lines = getattr(review, "card_lines", None) if review is not None else None
    reading = checked.words.situation if checked is not None and checked.words.situation else None
    because = row["why"] if row["why"] in WHYS else WHY_FIND_OUT
    why = [{"sentence": "headline", "question": row["question"], "because": because,
            "source": "expert_check"}]
    if reading:
        why.append({"sentence": "situation", "inference": SITUATION_IS, "source": "expert_check"})
    lane = describe(row.get("output_lane"), row.get("lane_reason"))
    score = int(row.get("score") or 0)
    expires = eval_time + timedelta(days=EXPIRY_DAYS)
    if row.get("authority_expires_at") is not None:
        expires = min(expires, row["authority_expires_at"])
    card = {
        "signal_id": row["signal_id"], "org_id": org_id, "subject_node_id": node,
        "domain": row.get("pack_id") or "founder_office",
        # A QUESTION IS A REQUEST FOR ONE PRECISE ANSWER — `review`, the level that asks and never instructs
        # (`contracts/outcomes`: ASK_DECISION), and says why it does not instruct.
        "level": "review", "abstained_because": because,
        "urgency_band": band(score, None), "assignee": assignee, "resolved_rule": rule, "co_recipients": [],
        "score": score, "score_block": {"S": score},
        "business_subject": (lines.subject if lines else None) or name,
        "relationship_role": lines.role if lines else None,
        "why_now": lines.why_now if lines else None,
        "unresolved_item": ("; ".join(lines.what_remains) if lines else "") or row["question"],
        "capability_key": row.get("capability_id"), "capability_version": row.get("capability_version"),
        "capability_review_state": str(row.get("capability_review_state") or "unreviewed"),
        "output_lane": lane.lane, "lane_reason": lane.reason,
        "success_signal": QUESTION_SUCCESS_SIGNAL, "do_nothing_consequence": QUESTION_DO_NOTHING,
        "outcome_window_days": None,
        "actions": [{"type": "answer", "label": "Answer", "question_id": row["question_id"]},
                    {"type": "snooze", "options": ["4h", "tomorrow_09", "3d", "custom"]}],
        "why": why,
        # The app and the API; never an agent's to answer for you.
        "surfaces": ["app", "api"], "context_tags": [],
        "config_snapshot_id": row.get("config_snapshot_id"), "builder_version": QUESTION_CARD_BUILDER,
        # STEP-14: the file's card, asking — a version of the file's one card, its ask the question (s14-D1).
        "file_id": node,
        "_words": {"headline": row["question"], "situation": reading or because, "lane": lane.lane,
                   "mode": QUESTION_MODE, "ask": row["question_id"]},
        "expires_at": expires, "_authority_time": eval_time,
        "_question_authority": {"reasoning_run_id": row["reasoning_run_id"],
                                "reasoning_decision_hash": row["reasoning_decision_hash"],
                                "config_snapshot_id": row.get("config_snapshot_id"),
                                "question_id": row["question_id"]}}
    copy = {"headline": row["question"], "situation": reading or because, "artifact": {},
            "render_mode": "question"}
    return card, copy


def _build_question_cards(graph, card_store: CardStore, org_id: str, eval_time: datetime, out: dict, *,
                          us=None, our_names: tuple[str, ...] = (), identities: tuple[str, ...] = (),
                          refused_files: set[str] | None = None) -> None:
    """Each open question with no live card gets one — counted where it is written, its lane tallied as
    every card's is. ⛔ A pass that could not read its questions says so (`questions_unread`) and keeps
    the decisions' cards: a read refused here must never cost a card the founder was owed elsewhere."""
    try:
        questions = _open_questions_without_cards(graph, org_id, eval_time)
    except Exception as exc:      # noqa: BLE001 — see the docstring
        import logging

        logging.getLogger(__name__).warning("could not read the open questions for org=%s: %s", org_id, exc)
        out["questions_unread"] = 1
        return
    for row in questions:
        token = card_store.claim_build(org_id, row["signal_id"], eval_time=eval_time,
                                       builder_version=QUESTION_CARD_BUILDER)
        if token is None:
            out["build_in_progress"] += 1
            continue
        try:
            card, copy = question_card(graph, org_id, row, eval_time)
            # STEP-14 · the card contract first (M43.C4.L-integration.V1.U02): a question is the expert's checked words.
            if _refused(out, org_id, card, _contract_refusals(card, copy, us=us, our_names=our_names,
                                                              identities=identities, expert=True, question=True),
                        engine=getattr(graph, "engine", None)):
                if refused_files is not None and card.get("file_id"):
                    refused_files.add(str(card["file_id"]))      # its card stays as it was (`_close_the_files_pass`)
                continue
            # STEP-14: the file's card, asking — a VERSION of the file's one card when it has one.
            versioned = _version_file_card(card_store, card, copy, token, out)
            if versioned is not None:
                if versioned:
                    tally_lane(out, lane=card["output_lane"])
                continue
            card_id, created, refreshed = card_store.insert_card(card, copy, build_claim_token=token)
            if created:
                out["built"] += 1
                out["question_cards"] += 1
                tally_lane(out, lane=card["output_lane"])
            elif refreshed:
                out["refreshed"] += 1
                tally_lane(out, lane=card["output_lane"])
            elif card_id is not None:
                out["already_built"] += 1
        finally:
            card_store.release_build(org_id, row["signal_id"], token)


# ── STEP-14 · ONE FILE, ONE CARD (`yc2_w27_s14` M42.C3.L-integration.V2.U03; STEP-14 §8.4 items 1-3, s14-D1) ──────────
#
# Both builders — the decision loop and the question cards — VERSION the file's card onto the file's new signal
# (`CardStore.version_card`) where they used to insert a second card. A version that is MATERIAL (another ask,
# recipient, date, lane or mode) goes through the decision's push gate; a reworded or renewed one is never pushed. A
# card an agent holds makes the file's next version wait. At the end of the pass a file card whose signal closed and
# that no version reached is expired REPLACED, counted — a card from before 0220 among them, once — and
# `files_with_two_open_cards` is measured.

#: The decision's mode, as its run recorded it on the signal (`reason/expert/decide.MODE_MARKER`).
_MODE_MARK = "expert_mode:"


def _decision_words(sig: dict, draft: dict) -> dict:
    """What an expert decision's card shows, as a version names it: its move whole (the audited play's metadata),
    the ask it answers — the open ask it names (`answers`), else the move itself, so a move to another end is
    another ask — whom its draft goes to, by when, its lane, and the mode its run decided. The same move in other
    words is told from another ask only where the review names the ask it answers."""
    move = sig.get("play_metadata") if isinstance(sig.get("play_metadata"), dict) else {}
    mode = next((str(u)[len(_MODE_MARK):] for u in (sig.get("uncertainty") or ())
                 if str(u).startswith(_MODE_MARK)), None)
    what = " ".join(str(move.get("what") or "").lower().split())
    ask = move.get("answers") or (f"move:{what}" if what else None)
    return {"headline": ".", "situation": ".", "move": move.get("what"), "lane": draft.get("output_lane"),
            "mode": mode, "ask": ask, "recipient": move.get("to"), "by_when": move.get("by_when")}


def _version_file_card(card_store, card: dict, copy: dict, token: str, out: dict):
    """Version the file's card onto this card's signal. None: the card names no file, or its file has no card to
    version (insert it); False: the file's card waits on an agent, or refused this version; True: versioned."""
    file_id = card.get("file_id")
    if not file_id:
        return None
    current = card_store.file_card(card["org_id"], file_id)
    if current is None or current.signal_id == card["signal_id"]:
        return None                                   # no card yet — or this signal's own: a refresh
    if current.held:
        out["version_waits"] += 1
        return False
    done = card_store.version_card(card, copy, build_claim_token=token, file_card=current)
    if done is None:
        out["version_refused"] += 1
        return False
    _card_id, _version, material, change = done
    out["versioned"] += 1
    if not material:
        out["renewed" if change == "renewed" else "reworded"] += 1
    card["_versioned"] = {"card_id": _card_id, "material": material, "change": change}
    return True


#: The file cards whose signal closed and that no version reached: open, not held by an agent — a file's card, or
#: an expert or question card from before 0220 that names no file.
_ORPHANED_FILE_CARDS = (
    "select k.card_id, k.file_id from cards k join signals s on s.org_id = k.org_id and s.signal_id = k.signal_id "
    " where k.org_id = :o and k.state = any(:open) and k.state <> 'claimed' and s.status <> 'open' "
    "   and (k.file_id is not null or k.capability_key = :expert or k.builder_version = :question_builder) "
    "   and not exists (select 1 from agent_claims ac where ac.org_id = k.org_id and ac.card_id = k.card_id "
    "                   and ac.released_at is null and ac.result is null)")

#: Files with more than one open card: by the file a card names — or, an expert or question card from before 0220,
#: by its signal's subject.
_FILES_WITH_TWO_OPEN_CARDS = (
    "select count(*) from (select coalesce(k.file_id, s.subject_node_id) as file from cards k "
    "  join signals s on s.org_id = k.org_id and s.signal_id = k.signal_id "
    " where k.org_id = :o and k.state = any(:open) "
    "   and (k.file_id is not null or k.capability_key = :expert or k.builder_version = :question_builder) "
    " group by 1 having count(*) > 1) twice")


def _close_the_files_pass(graph, org_id: str, out: dict, refused_files=frozenset()) -> None:
    """End of pass: the orphaned file cards expired REPLACED, counted, and the files with two open cards measured.
    ⛔ A measurement may never kill what it measures: unreadable, it says so (`file_cards_unmeasured`).

    ⛔ NEVER A FILE WHOSE NEXT VERSION THE CONTRACT REFUSED THIS PASS (STEP-14 fix, the crosscheck's finding 3,
    `yc2_w27_s14` M43.C4.L-integration.V1.U06). The reason side retired the file's old signal and handed the file on;
    the refused version wrote nothing — and this sweep then expired the card REPLACED, with nothing in its place and
    History saying "replaced". Its card is left as it was — its words, state and history — counted
    `file_cards_kept_on_refusal`, said by the health check that names the contract, and lapsing by its own window as
    any card does; the file's next version that passes the contract versions it."""
    from genios_engine.platform import card_lifecycle
    from genios_engine.reason.expert.decide import CAPABILITY_ID

    params = {"o": org_id, "open": list(card_lifecycle.OPEN_STATES), "expert": CAPABILITY_ID,
              "question_builder": QUESTION_CARD_BUILDER}
    try:
        with graph.engine.begin() as c:
            orphans, kept = [], 0
            for r in c.execute(text(_ORPHANED_FILE_CARDS), params):
                if r.file_id is not None and str(r.file_id) in refused_files:
                    kept += 1
                else:
                    orphans.append(r.card_id)
            out["file_cards_kept_on_refusal"] += kept
            if orphans:
                out["file_cards_replaced"] += len(card_lifecycle.expire_cards(
                    c, org_id=org_id, cause=card_lifecycle.REPLACED, card_ids=orphans))
            out["files_with_two_open_cards"] = int(c.execute(text(_FILES_WITH_TWO_OPEN_CARDS), params).scalar() or 0)
    except Exception as exc:      # noqa: BLE001 — see the docstring
        import logging

        logging.getLogger(__name__).warning("could not close the files' pass for org=%s: %s", org_id, exc)
        out["file_cards_unmeasured"] = 1


# ── STEP-14 · THE CARD CONTRACT, BEFORE EVERY CARD THIS PIPELINE WRITES (`yc2_w27_s14` M43.C4.L-integration.V1.U02) ──
#
# A decision's card or a question's, new or a version: its words pass `contracts/card_contract` against what they were
# made from — refused, it is not written (a refused version leaves the file's card as it was), counted
# `refused_contract:<rule>` and logged. Production's *"nsrcel — a dated payment obligation is open"* (a template's
# money claim, no money in the evidence) and *"Which is right? Maria Exconde: party.role"* are its cases.

#: A fact or quote that holds money: a key naming an amount, or a currency in its value.
_MONEY_KEYS = ("amount", "price", "invoice", "payment", "fee", "revenue", "budget", "cost", "valuation")
_CURRENCY = ("₹", "$", "€", "£", " inr", " usd", "lakh", "crore")


def _holds_money(facts: dict, quotes) -> bool:
    if any(any(k in str(name).lower() for k in _MONEY_KEYS) for name in (facts or {})):
        return True
    said = " ".join(str(q.get("quote") or "") for q in quotes or () if isinstance(q, dict)).lower()
    values = json.dumps({k: (v.get("value") if isinstance(v, dict) else v) for k, v in (facts or {}).items()},
                        default=str, ensure_ascii=False).lower()
    return any(c in said or c in values for c in _CURRENCY)


def _cited_texts(graph, org_id: str, sources) -> list[str]:
    """The words of the mails and meetings an expert card's move rests on (`decide.sources_of`: the headline's and
    the draft's evidence ids) — the retained text of each (`prepared_content`), as the quote loader verifies a quote.
    ⛔ An enrichment of the contract's evidence, never a hard failure: unreadable, nothing is added."""
    ids = sorted({str(e) for part in (sources or {}).values() if isinstance(part, dict)
                  for e in (part.get("evidence") or ())})          # a reading's id (`loop:`, `num:`) holds no mail
    engine = getattr(graph, "engine", None)
    if not ids or engine is None:
        return []
    from .card_builder import _quote_source_texts
    try:
        with engine.connect() as c:
            return [t for _id, t in sorted(_quote_source_texts(c, org_id, ids).items()) if t]
    except Exception:      # noqa: BLE001 — see the docstring
        return []


def _contract_refusals(card: dict, copy: dict, *, us, our_names, identities, expert: bool,
                       question: bool = False):
    """What the card contract refuses in this card (see above). Every card's corpus is what it was made from: the
    facts, slots, quotes and our names (`render._corpus`); a narrated card's outcome lines are its template's.

    ⛔ AN EXPERT DECISION'S CARD IS HELD TO THE EVIDENCE ITS MOVE RESTS ON (STEP-14 fix, the crosscheck's finding 4,
    `yc2_w27_s14` M43.C4.L-integration.V1.U07). Its own words — the headline, the reading, the draft, the move whole,
    the alternative, the stop rule, what done looks like and what doing nothing costs — were its corpus, so money, a
    quote and a number were held by themselves and only `us` and `internal` could ever fire on it; the check holds
    figures and names, never a money word nor a quoted span. Its evidence is the quotes its check matched
    (`_checked_quotes`), the mails and meetings those are from (`_cited_texts`), the file's facts and quotes — and the
    lines CODE wrote from the dossier at review time (why now, what remains: `reason/expert/card_lines`, no model
    writes them; without them 19 golden cards were refused for a day or a title the dossier printed, s14-F21). Money is
    allowed only where that evidence holds money. A QUESTION card's words are ours — the check's own question, or our
    closed phrases — and stay its corpus, as before."""
    quotes = card.get("_quotes") or []
    draft = (copy.get("artifact") or {}).get("body") or None
    recommended = card.get("recommended") if isinstance(card.get("recommended"), dict) else {}
    text_ = card_contract.CardText(
        headline=str(copy.get("headline") or ""), situation=str(copy.get("situation") or ""),
        subject=card.get("business_subject"), recipient=card.get("_recipient"), draft=draft,
        why_now=card.get("why_now"),
        what_remains=tuple(x for x in (card.get("unresolved_item"),) if x),
        # STEP-14 (0221): the gold card's lines are shown, so the contract reads them too — and what done looks like
        # and what doing nothing costs, which GET /cards/{id} serves (the crosscheck's finding 4).
        recommended=recommended.get("what") or None, alternative=card.get("alternative"),
        wait_or_stop=card.get("wait_or_stop"), success=card.get("success_signal"),
        do_nothing=card.get("do_nothing_consequence"))
    corpus = [_corpus(card.get("_facts") or {}, card.get("_slots") or {}, identities, quotes)[0]]
    evidence = [*(card.get("_checked_quotes") or ()), *(card.get("_cited_texts") or ())]
    if not expert:
        corpus += [card.get("success_signal") or "", card.get("do_nothing_consequence") or ""]
        money = _holds_money(card.get("_facts") or {}, quotes)
    elif question:
        corpus += [text_.headline, text_.situation, draft or "", text_.success or "", text_.do_nothing or "",
                   *evidence, *(x for x in (text_.why_now, *text_.what_remains) if x)]
        money = True
    else:
        corpus += [*evidence, *(x for x in (text_.why_now, *text_.what_remains) if x)]
        money = _holds_money(card.get("_facts") or {}, quotes) or card_contract.holds_money(evidence)
    return card_contract.check(text_, us=us or SelfIdentity(), our_names=our_names,
                               quotes=[*(str(q.get("quote") or "") for q in quotes if isinstance(q, dict)),
                                       *evidence],
                               corpus=corpus, money_evidence=money)


def _refused(out: dict, org_id: str, card: dict, refusals, *, engine=None) -> bool:
    """Count, log and keep what the contract refused (`platform/card_refusals`, 0222 — a refused card is never
    written, so it is kept where `scripts/pipeline_health` reads it); True when the card must not be written.
    ⛔ Keeping it may never cost the pass: unkept, it is counted `refusals_unkept` and logged."""
    if not refusals:
        return False
    import logging

    for r in refusals:
        out[f"refused_contract:{r.rule}"] = out.get(f"refused_contract:{r.rule}", 0) + 1
    log = logging.getLogger(__name__)
    log.warning("card refused by the card contract org=%s signal=%s: %s", org_id, card.get("signal_id"),
                "; ".join(f"{r.rule}: {r.found}" for r in refusals))
    if engine is not None:
        from genios_engine.platform import card_refusals

        try:
            with engine.begin() as c:
                card_refusals.record(c, org_id=org_id, writer=card_refusals.PIPELINE,
                                     ref=str(card.get("signal_id") or "-"), refusals=refusals)
        except Exception as exc:      # noqa: BLE001 — see the docstring
            out["refusals_unkept"] = out.get("refusals_unkept", 0) + 1
            log.warning("could not keep the card contract's refusal org=%s: %s", org_id, exc)
    return True


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

    The ADDRESSES are every address of ours, from the one answer (`platform/self_identity`,
    STEP-04): the active seats, the org's own, the connected accounts and what the tenant
    declared. Quote attribution (`from_counterparty`) reads them, so a sentence written from any
    of them is never printed as the counterparty's.
    """
    try:
        with graph.engine.connect() as c:
            us = identity_for(c, org_id)
            row = c.execute(text(
                "select name, first_name, last_name, company from orgs where id=:o"),
                {"o": org_id}).first()
            # And what the mail calls us: the display name each address of ours carries in the
            # graph ("Mr Rohit Swerashi", from his own From header) — the name a card's subject
            # chain actually meets (STEP-04).
            shown = [r[0] for r in c.execute(text(
                "select distinct display_name from graph_nodes where org_id=:o and valid_to is null "
                "and node_type in ('person', 'service') and canonical_key = any(:a)"),
                {"o": org_id, "a": sorted(us.addresses)}) if r[0] and "@" not in r[0]]
    except Exception:      # noqa: BLE001 — grounding is an enrichment, never a reason to fail
        return ()
    names = () if row is None else (row.name, row.first_name, row.last_name, row.company)
    parts = [*names, *sorted(shown), *sorted(us.addresses)]
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
           # A card whose subject is one of us, refused by `build_draft` (STEP-04) — zeroed so a
           # pass that refused nothing says so.
           "refused_subject_is_us": 0,
           "over_budget_no_push": 0,
           "not_pushed_abstained": 0, "not_pushed_reason_saturated": 0,
           "pushed": 0, "agent_pushed": 0,
           # ⛔ L2-7 · THE COLLAPSE, MEASURED ON EVERY SWEEP WHETHER THE FLAG IS ON OR OFF.
           # "Both paths measured side by side on the same sweep before the old one is removed" —
           # and a comparison that only exists AFTER the cutover cannot inform the cutover.
           # Initialised at zero for the same reason `BY REASON` prints its zeros: a key that
           # appears only when it fires is a key nobody knows exists.
           "cards_from_signal": 0, "cards_from_situation": 0, "cards_uninterpreted": 0,
           # STEP-13 · the cards a held file asks its question on (`_build_question_cards`), zeroed so a
           # pass that asked nothing says so.
           "question_cards": 0,
           # STEP-14 · one file, one card: the versions written (and of them the quiet ones, never pushed), a file's
           # next version waiting on an agent or refused, the file cards no version reached, and the measurement.
           "versioned": 0, "renewed": 0, "reworded": 0, "quiet_version_not_pushed": 0, "version_waits": 0,
           "version_refused": 0, "file_cards_replaced": 0, "files_with_two_open_cards": 0,
           # STEP-14 fix (the crosscheck's finding 3): a file's card left as it was, its next version refused.
           "file_cards_kept_on_refusal": 0,
           # STEP-14 · the card contract — each rule counted from zero (M43.C4.L-integration.V1.U02).
           **{f"refused_contract:{rule}": 0 for rule in card_contract.RULES},
           # ⛔ THE LANE MIX. Zeroed for the same reason as the three above — "a key that appears
           # only when it fires is a key nobody knows exists" — and ALL SIX are zeroed, including
           # `unrouted`, because today every production signal is unrouted and a mix that hid that
           # would read as though the router had run.
           **{k: 0 for k in TALLY_KEYS}}
    from .bands import band
    from .card_source import cards_from_situations, tally_source
    # How many of one situation type may interrupt in a single pass. Counted per pass rather than
    # per day: the point is that a finding which fires across ten accounts is one thing to tell
    # somebody, and the tenth copy carries no information the first did not.
    surfaced_by_reason: dict[str, int] = {}
    identities = _tenant_identities(graph, org_id)   # once per org, not per card
    # WHO IS US, for the subject check (STEP-04): the identity and the tenant's own names, once per
    # pass. A card whose subject is one of us is refused below and counted, never built.
    try:
        us = identity_for(graph, org_id)
    except Exception:      # noqa: BLE001 — unreadable: nothing is refused, as before STEP-04
        us = None
    our_names = tuple(i for i in identities if "@" not in i)
    # The files whose next version the card contract refused this pass: their cards stay as they were.
    refused_files: set[str] = set()
    signals = _open_signals_without_cards(graph, org_id, eval_time)

    # ⛔ L2-7 · THE COLLAPSE RATIO, READ ON EVERY SWEEP. One extra grouped SELECT, no writes, and
    # it is the number the whole Layer 2 plan is measured by: 38 cards becoming N is a CLAIM until
    # somebody prints the ratio. `situation_id` is NULL for every signal written before migration
    # 0182 and for every signal whose situation never formed, and those group as their own bucket
    # rather than vanishing from the join — because "fewer cards must come from merging, never
    # from dropping".
    try:
        for group in _open_situations_without_cards(graph, org_id, eval_time):
            tally_source(out, situation_id=group.get("situation_id"))
    except Exception as exc:      # noqa: BLE001 — a MEASUREMENT may never kill what it measures
        # The rule this obeys is already written down for `BundleStore.record_call`: "a receipt
        # that can abort the thing it is a receipt for turns an accounting failure into a product
        # failure." A missing `situation_id` column before migration 0182, or a graph object that
        # cannot open a connection, must cost a number on a dashboard and never a card.
        import logging

        logging.getLogger(__name__).warning(
            "could not measure the card collapse for org=%s: %s", org_id, exc)
        # ⛔ RECORDED, NEVER SILENT. A pass that could not measure itself must not look identical
        # to one that measured zero — that is the invisible refusal L2-0 spent a whole step on.
        out["collapse_unmeasured"] = 1
    out["cards_from_signal"] = len(signals)

    # THE FLIP, PER TENANT AND OFF UNTIL A ROW SAYS OTHERWISE. `live_lane` recorded what a global
    # boolean costs: "one boolean for every tenant at once… it only ever turns lanes ON". The way
    # back is deleting the activation row, and until one exists the loop below is unchanged.
    _situation_lane = cards_from_situations(activated=_activated_features(graph, org_id))
    out["cards_lane"] = "situation" if _situation_lane else "signal"

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
            # reviewed and accepted. Downgrading keeps the observation (which is real and useful)
            # and drops only the instruction.
            #
            # THE WORLD THIS COMMENT USED TO DESCRIBE IS OVER. It read "the corpus currently holds
            # 152 capabilities, 0 of them accepted, so every prescription shipped on unreviewed
            # authority" — and a reader arriving today would conclude that every compiled card is
            # downgraded and stop looking. Every authored capability now clears the admission
            # ceremony (155 of 155 at the time of writing; the count moves as the corpus is
            # authored, the property does not — except the Founder Office's, authored stub-first
            # by STEP-11 and stamped one by one as the founder accepts them):
            # `identity.status == 'stable'`, `metadata.review_status == 'approved'` with
            # a named reviewer, and `admission.accepted_content_hash` equal to the hash of the
            # routed bytes minus the admission block. `capability_resolver._admission_reason`
            # returns None for every one of them, so `RoutePlan.admitted` is True, the package's
            # `metadata['review_state']` is `accepted`, and a STAMPED capability's signal reaches
            # this gate as `prescriptive` and leaves it un-downgraded.
            #
            # What still downgrades is a DRAFT, and there are now TWO ways to be one.
            #
            # (a) A measurement compile (`require_admission=False`) over content whose acceptance
            #     hash no longer matches its bytes. The gate reads the LIVE admission state — the
            #     hash pin is recomputed on every compile, so an edit after review un-accepts the
            #     capability by itself — never a cached count.
            #
            # (b) A SITUATION whose own words nobody accepted. `capability_resolver.
            #     situation_admission_reason` asks a situation the same three questions the
            #     capability ceremony asks its bytes — stable identity, approved review, a named
            #     reviewer — because a machine-written situation file whose owning capability was
            #     approved used to ship a fully prescriptive card on somebody else's signature.
            #     Measured when it was added: 24 of 62 authored situations, 15 reviewed by nobody.
            #
            #     THIS ONE FLAGS ON EVERY COMPILE, live or measurement, and that asymmetry with
            #     (a) is deliberate: a situation's DETECTION is Layer 2's and is evidence-backed
            #     whatever a reviewer thinks of its prose, so the finding still ships — it just
            #     stops instructing. A fully live, fully hash-accepted compile of one of those
            #     types is therefore still `draft`, and that is the intended reading, not a gap.
            # `tests/packs/compiler/test_stamped_vs_draft_abstention.py` drives both halves.
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
            try:
                draft = build_draft(graph, org_id, sig, effective, eval_time,   # E0
                                    quotes=quotes, us=us, our_names=our_names)
            except SubjectIsUs as refused:
                # Counted and said, never silent, and never the end of the pass (STEP-04).
                out["refused_subject_is_us"] += 1
                import logging

                logging.getLogger(__name__).warning("card refused for org=%s: %s", org_id, refused)
                continue
            # STEP-12 M33 · A COVERED FILE'S CARD IS ITS REVIEW'S (M33.C1.L-interface.V1.U08). The
            # expert already wrote the words — the move, its reading of the file, the draft — and
            # they were validated against its dossier (`contracts/expert_review.validate`); a
            # narrator would write them again, paid for, from less. So no narrator is asked: the
            # copy is the review's own (`reason/expert/decide._render`).
            from_review = is_expert(sig.get("capability_id"))
            copy = render_copy(                                                    # E1
                reason_code=draft["_reason_code"], template=draft["_template"],
                facts=draft["_facts"], slots=draft["_slots"], llm=None if from_review else llm,
                cost_sink=graph.record_cost, org_id=org_id,
                # The tenant's own names and addresses. A draft signed by the account holder is
                # not inventing them, but the grounding corpus was built from the SUBJECT's facts
                # alone, so "Best, Rohit" was rejected as a hallucinated person on the founder's
                # own outgoing mail — and the whole card shipped as an empty stub because of it.
                # THE RECIPIENT'S quotes, not the loader's. `build_draft` narrows them to what the
                # assignee may see (`_visible_quotes`); handing the renderer the unfiltered list
                # let the LLM write a private or other-thread sentence into the card body that the
                # evidence block itself had just withheld.
                identities=identities, quotes=draft.get("_quotes", quotes),
                subject_ref=f"signal:{sig['signal_id']}")
            # THE HEADLINE MUST NOT OUTRANK THE CARD. E0 decides the level and withdraws the
            # authority to instruct; E1 writes the sentence and, until this line, had no reference
            # to `level` anywhere in it. On the pilot's fifteen live cards ELEVEN carry `review`
            # and three `observation` — one is prescriptive — and their headlines read "Deliver
            # fundraising opportunities to sanchiconnect.tech NOW". The push gate below already
            # honours the level; the sentence did not, and the sentence is what the reader sees
            # first. This is the one point where both facts are in hand.
            if from_review:
                copy = review_copy(copy, draft["_template"])
            copy = {**copy, "headline": state_not_command(copy.get("headline"), draft["level"])}
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
            # STEP-14 · THE CARD CONTRACT FIRST: refused, nothing is written — not a card, not a version.
            if from_review:
                draft["_recipient"] = (sig.get("play_metadata") or {}).get("to") \
                    if isinstance(sig.get("play_metadata"), dict) else None
                draft["_checked_quotes"] = [q for part in ((sig.get("capability_render") or {}).get("sources")
                                                           or {}).values() if isinstance(part, dict)
                                            for q in (part.get("quotes") or ())]
                draft["_cited_texts"] = _cited_texts(graph, org_id,
                                                     (sig.get("capability_render") or {}).get("sources"))
            if _refused(out, org_id, draft, _contract_refusals(draft, copy, us=us, our_names=our_names,
                                                               identities=identities, expert=from_review),
                        engine=getattr(graph, "engine", None)):
                if draft.get("file_id"):
                    refused_files.add(str(draft["file_id"]))      # its card stays as it was (`_close_the_files_pass`)
                continue
            # STEP-14: an expert card is its FILE's — the file's next decision VERSIONS it, never a second card.
            if draft.get("file_id"):
                draft["_words"] = _decision_words(sig, draft)
            versioned = _version_file_card(card_store, draft, copy, claim_token, out)
            if versioned is not None:
                if not versioned:
                    continue
                tally_lane(out, lane=draft.get("output_lane"))
                card_id = draft["_versioned"]["card_id"]
                if not draft["_versioned"]["material"]:
                    # A rewording or a renewal is a quiet version — kept in its history, pushed to nobody (s14-D1).
                    out["quiet_version_not_pushed"] += 1
                    continue
            else:
                card_id, created, refreshed = card_store.insert_card(
                    draft, copy, build_claim_token=claim_token)
            if versioned is None and (card_id is None or not created):
                if refreshed:
                    # The words on an existing card improved. Counted apart from `already_built`
                    # because they mean opposite things — one is work done, the other is work
                    # correctly skipped — and deliberately NOT pushed: the user has already been
                    # shown this card, and a rewrite is not a new event to interrupt them with.
                    out["refreshed"] += 1
                    out["llm" if copy["render_mode"] == "llm" else "raw_slot"] += 1
                    tally_lane(out, lane=draft.get("output_lane"))
                elif card_id is not None:
                    out["already_built"] += 1
                continue
            if versioned is None:
                out["built"] += 1
            # ⛔ WHICH KIND OF OUTPUT, COUNTED — INCLUDING `suppress` AND INCLUDING `unrouted`.
            #
            # AT THE TWO SITES WHERE A CARD IS WRITTEN, not where a draft is composed. A draft can
            # end as `built`, `refreshed`, `already_built` or a refused persist, and only the first
            # two put something in front of a reader. Counting at composition time would make the
            # lane mix describe a population that includes cards nobody received — and would make
            # `lane_recall.recall_verdict` a tautology, since the tally and the comparison would
            # then be incremented by the same line. Two independently incremented counters that
            # must agree is the only version of this check worth having.
            #
            # The lane the DRAFT resolved, never the raw column: `build_draft` already read the
            # pair through `lane_display.describe`, and resolving it twice is how a count and a
            # label come to give two answers to one question.
            if versioned is None:
                tally_lane(out, lane=draft.get("output_lane"))
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
            # THE CANONICAL OUTCOME, folded here because here is where every input to it exists.
            #
            # `contracts/outcomes` was written to be "the one place that names what happened",
            # and nothing in genios_engine/ imported it — eleven outcomes, forty-two tests, zero
            # consumers. This is the seam that makes it true, and it changes one behaviour:
            #
            # ASK_DECISION NOW INTERRUPTS. The gate used to be `is_actionable(level)`, which is
            # False for `review`, so a card whose whole purpose is to put one precise question in
            # front of the person who can answer it waited in the queue exactly as long as a card
            # saying nothing needed doing. That is the catalogue's DM-03 ("no backup authority
            # exists — request one precise decision from the authorized manager") having no route
            # at all.
            #
            # AND ONLY WHEN IT IS ADDRESSED. `draft["assignee"]` is required below for every push,
            # so a review card with nobody to ask still waits — a question addressed to no one is
            # not a decision request, it is the "a human must look" abstention the flood guard
            # above exists to keep out of the surface.
            outcome = project("abstention.Level", str(draft.get("level") or ""))
            if not interrupts(outcome):
                out["not_pushed_abstained"] += 1
                out[f"outcome_{outcome.value if outcome else 'unmapped'}"] = \
                    out.get(f"outcome_{outcome.value if outcome else 'unmapped'}", 0) + 1
            elif floods:
                out["not_pushed_reason_saturated"] += 1
            elif (band(int(sig["score"]), bands_cfg) in ("high", "critical")
                    and draft["assignee"] and not over_budget
                    and card_store.transition(
                        card_id, org_id, "surfaced", "card.surfaced", cause="push",
                        # A material VERSION may interrupt again, from where it sits (STEP-14, s14-D1).
                        allowed_from=("queued", "surfaced") if versioned else ("queued",))):
                out["pushed"] += 1
                # Counted under its canonical name as well as the mechanical one, so an operator
                # asking "how many decision requests did we surface" has an answer that is not
                # inferred from a reason-code string.
                key = f"outcome_{outcome.value}"
                out[key] = out.get(key, 0) + 1
                surfaced_by_reason[reason_code] = surfaced_by_reason.get(reason_code, 0) + 1
        finally:
            card_store.release_build(org_id, sig["signal_id"], claim_token)

    # STEP-13 · the questions held files ask, each on its own card (M36.C2.L-interface.V3.U05) — after the
    # decisions, inside the recall guard below: a question card is a card, its lane tallied.
    _build_question_cards(graph, card_store, org_id, eval_time, out, us=us, our_names=our_names,
                          identities=identities, refused_files=refused_files)
    # STEP-14 · the file cards no version reached, and the files with two open cards (see `_close_the_files_pass`).
    _close_the_files_pass(graph, org_id, out, refused_files)

    # ⛔ THE RECALL GUARD, RUN — and until 2026-10-01 it was written, tested and never invoked.
    #
    # `lane_recall.py` was built on 2026-09-30 with 24 tests to "prove nothing died quietly", and
    # nothing imported it. The comment ~80 lines above — explaining that the lane is tallied at the
    # two sites where a card is WRITTEN so that `recall_verdict` would not be a tautology — was
    # reasoning about the correctness of a verdict nobody computed. ⛔ A comment that reasons about
    # a guard's correctness is not evidence the guard runs.
    #
    # ⛔ IT MAY NEVER RAISE, and the rule is already written down in this file: "a receipt that can
    # abort the thing it is a receipt for turns an accounting failure into a product failure." An
    # unbalanced tally means cards went somewhere nobody is looking; dropping the whole pass over
    # it would mean they went nowhere at all.
    try:
        verdict = recall_verdict(out)
        out["lane_recall"] = verdict.explain()
        out["lane_recall_balanced"] = verdict.balanced
        if not verdict.balanced:
            import logging

            logging.getLogger(__name__).warning(
                "lane recall unbalanced for org=%s: %s", org_id, verdict.explain())
    except Exception as exc:      # noqa: BLE001 — a MEASUREMENT may never kill what it measures
        import logging

        logging.getLogger(__name__).warning(
            "could not compute the lane recall for org=%s: %s", org_id, exc)
        # ⛔ The same rule as `collapse_unmeasured` above: a pass that could not measure itself must
        # not look identical to one that measured zero.
        out["lane_recall_unmeasured"] = 1
    return out
