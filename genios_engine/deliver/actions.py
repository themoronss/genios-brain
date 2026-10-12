from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.contracts.execution import ExecutionState
from genios_engine.executive.execution_store import (
    apply_transition as _apply_execution_transition,
)
from genios_engine.executive.execution_store import link_card as _link_execution_card
from genios_engine.executive.lifecycle import transition as _execution_transition
from genios_engine.platform.ids import new_id
from genios_engine.reason.authority import (
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
    QUESTION_SIGNAL_JOINS,
)

#: Buttons that mean a human started doing the work, as opposed to `wrong` (this was never a
#: real signal) or `snooze`/`requeue` (deferral, not engagement).
_CLAIMING_ACTIONS = frozenset({"run_play", "do_it_myself"})

# E8 · Action Ingester (§5.12) — the round trip both L1 and L6 depend on. Four buttons + requeue,
# each landing as an L1 human event AND a card lifecycle transition, all timestamped. A Wrong
# verdict requires one closed reason so a terminal action cannot silently disappear from learning.
# Requeue
# is NOT a fifth button: logged ui.requeued, excluded from precision math, expires normally.

from genios_engine.contracts.learning_attribution import ALL_REASONS as _ALL_WRONG_REASONS

BUTTONS = {"run_play", "do_it_myself", "snooze", "wrong", "requeue", "answer"}

# STEP-13 · YOUR ANSWER (`yc2_w27_s13` M36.C2.L-interface.V4.U06; `06` D60). A held file asks one question on
# its own card (`deliver/pipeline.question_card`), and `answer` — with your words — answers it: kept once on
# the file (`context/founder_questions.answer`), the card resolved, its signal acted. The file's dossier
# shows the answer, its fingerprint moves, and the next sweep reviews the file with your answer in front of
# the expert. A question card offers `answer` and the deferrals, nothing else; no other card is a question.
QUESTION_OFFERS = frozenset({"answer", "snooze", "requeue"})
# ⛔ STEP-14 · YOUR ANSWER KEEPS THE FILE'S CARD (`yc2_w27_s14` M42.C3.L-interface.V4.U05, s14-D3 — amends the above). The
# card is no longer resolved nor its signal acted: it is VERSIONED — answered, "your answer is in; the file is read
# again", the question you answered as its situation, the Monitor lane, nothing to press but later — and the file's
# next review versions it again (a decision, or another question): one card from question to move. Its signal
# stays open, so nothing closes the card in between; its question answered, no door shows it until then.
ANSWERED_HEADLINE = "Your answer is in; the file is read again"
#: What an answered card offers: later, and nothing else — there is nothing left to press until the file moves.
ANSWERED_ACTIONS = [{"type": "snooze", "options": ["4h", "tomorrow_09", "3d", "custom"]}]
#: The lane an answered card waits in (`reason/output_lane`): the file is watched, not decided.
ANSWERED_LANE = "monitor"
ANSWERED_LANE_REASON = "your answer is in; the file's next review decides it"
#: A founder's answer is a sentence or a paragraph, not a document.
MAX_ANSWER_CHARS = 4000
# ⛔ THE ONE VOCABULARY, IMPORTED — never a fourth hand-written copy of it.
#
# This held three literals while the card offered three, and widening one without the other gives
# the founder a button the server refuses with `allowed_reasons`. `api/intelligence_routes.py`
# re-exports this set as `_FB_WRONG_REASONS` and validates against it, so both doors open together
# or neither does.
#
# ⛔ AND NOTHING IS REMOVED. The three original spellings are members of `WrongReason`, so every
# client and every recorded judgment keeps working unchanged.
WRONG_REASONS = frozenset(_ALL_WRONG_REASONS)


def snooze_until(option: str | None, eval_time: datetime, custom=None) -> datetime:
    if option == "3d":
        return eval_time + timedelta(days=3)
    if option == "tomorrow_09":
        return (eval_time + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    if option == "custom" and custom:
        try:
            return datetime.fromisoformat(str(custom).replace("Z", "+00:00"))
        except ValueError:
            pass
    return eval_time + timedelta(hours=4)          # default '4h'


def ingest_action(*, card_store, graph, org_id: str, card_id: str, actor: str, action: str,
                  reason: str | None = None, snooze_option: str | None = None,
                  custom_until=None, eval_time: datetime | None = None,
                  allow_any_assignee: bool = False, surface: str | None = None,
                  words: str | None = None) -> dict:
    """Land a button press. Returns the resulting card state. Orphan actions (no card) are a
    counted no-op (V-09), never an exception loop."""
    eval_time = eval_time or datetime.now(timezone.utc)
    if action not in BUTTONS:
        return {"ok": False, "error": "unknown_action"}
    if action == "wrong" and reason not in WRONG_REASONS:
        return {"ok": False, "error": "invalid_wrong_reason",
                "allowed_reasons": sorted(WRONG_REASONS)}
    if action == "answer":
        words = str(words or "").strip()
        if not words:
            return {"ok": False, "error": "answer_says_nothing"}
        if len(words) > MAX_ANSWER_CHARS:
            return {"ok": False, "error": "answer_too_long", "max_chars": MAX_ANSWER_CHARS}
    del card_store  # production actions commit through the graph/database transaction below
    allowed = {
        "run_play": ("queued", "surfaced", "snoozed", "delivered"),
        "do_it_myself": ("queued", "surfaced", "snoozed", "delivered"),
        "wrong": ("queued", "surfaced", "snoozed", "delivered"),
        "snooze": ("queued", "surfaced", "delivered"),
        "requeue": ("snoozed", "surfaced", "delivered"),
        "answer": ("queued", "surfaced", "snoozed", "delivered"),
    }
    with graph.engine.begin() as c:
        # All graph writers lock this tenant row when bumping the graph version. Holding a shared
        # lock closes the check-to-action race for this irreversible authority transition.
        c.execute(text("select graph_version from graph_versions where org_id=:o for share"),
                  {"o": org_id})
        card = c.execute(text(
            "select k.card_id, k.signal_id, k.org_id, k.assignee, k.state, k.expires_at "
            "from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id "
            + AUTHORITATIVE_SIGNAL_JOINS +
            " where k.card_id=:card and k.org_id=:o and s.status='open' "
            "and k.expires_at > :authority_time and " + AUTHORITATIVE_SIGNAL_PREDICATE +
            " for update of k, s for share of rr, ro, selected_rc, rcap, authority_ctx, "
            "authority_cfg, authority_pack"),
            {"card": card_id, "o": org_id,
             "authority_time": eval_time}).mappings().first()
        if card is None:
            # A P4 team/verify situation card (deliver/store.SITUATION_CARD_SQL): no L4 run by
            # construction, so it is proved by its own open signal instead. Nothing else passes.
            from genios_engine.deliver.store import SITUATION_CARD_BUILDER, SITUATION_CARD_SQL
            card = c.execute(text(
                "select k.card_id, k.signal_id, k.org_id, k.assignee, k.state, k.expires_at "
                "from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id "
                "where k.card_id=:card and k.org_id=:o and s.status='open' "
                "and k.expires_at > :authority_time and " + SITUATION_CARD_SQL +
                " for update of k, s"),
                {"card": card_id, "o": org_id, "authority_time": eval_time,
                 "situation_builder": SITUATION_CARD_BUILDER}).mappings().first()
        question_id = None
        if card is None:
            # A QUESTION CARD (deliver/store.QUESTION_CARD_SQL): proved by its own question's authority —
            # the run that asked it, the signal bound to that run, the question still open — and nothing
            # else. Its question row is locked with the card: an answer is kept once.
            from genios_engine.deliver.store import QUESTION_CARD_BUILDER, QUESTION_CARD_SQL
            question_door = text(
                "select k.card_id, k.signal_id, k.org_id, k.assignee, k.state, k.expires_at, "
                "question_asked.question_id "
                "from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id "
                + QUESTION_SIGNAL_JOINS +
                " where k.card_id=:card and k.org_id=:o and s.status='open' "
                "and k.expires_at > :authority_time and " + QUESTION_CARD_SQL +
                " for update of k, s, question_asked for share of question_rr, question_ro")
            asked = {"card": card_id, "o": org_id, "authority_time": eval_time,
                     "question_builder": QUESTION_CARD_BUILDER}
            card = c.execute(question_door, asked).mappings().first()
            if card is None:
                # ⛔ ONCE MORE (STEP-13, `03` X43): a sweep that RE-BOUND this question — the same words, asked
                # by the run asking now (`reason/expert/asks`) — committed while this press waited on its
                # locks. PostgreSQL re-checks the locked rows at their new version against the run read
                # before (READ COMMITTED), finds the signal bound to another run, and returns nothing: the
                # answer refused V-09 with its question still open. A second read takes a fresh snapshot and
                # sees the re-bind. Once: a card that is no question, or truly stale, is refused as before.
                card = c.execute(question_door, asked).mappings().first()
            if card is not None:
                question_id = card["question_id"]
        if card is None:
            return {"ok": False, "error": "stale_or_unauthorized_card", "code": "V-09"}
        if question_id is not None and action not in QUESTION_OFFERS:
            return {"ok": False, "error": "not_offered", "offered": sorted(QUESTION_OFFERS)}
        if question_id is None and action == "answer":
            return {"ok": False, "error": "not_a_question"}
        if (not allow_any_assignee and card["assignee"] is not None
                and card["assignee"] != actor):
            return {"ok": False, "error": "assigned_to_different_seat"}
        if card["state"] not in allowed[action]:
            return {"ok": False, "error": "card_not_actionable"}

        state = "acted" if action in {"run_play", "do_it_myself", "wrong"} \
            else ("snoozed" if action == "snooze" else (card["state"] if action == "answer" else "queued"))
        detail = {"reason": reason} if reason else {}
        if action == "answer":
            # Your words are kept on the question, once — never copied into the event log.
            detail = {"question_id": question_id}
        snooze_at = None
        if action == "snooze":
            snooze_at = min(snooze_until(snooze_option, eval_time, custom_until),
                            card["expires_at"])
            detail = {"until": snooze_at.isoformat()}
        if surface:
            # Where the button was pressed (web / desktop / extension). The state is shared, so a
            # card done in the desktop app shows done on the web — this only says where it happened.
            detail["surface"] = surface

        if action != "answer":                     # an answer leaves where the card sits as it was (s14-D3)
            c.execute(text(
                "update cards set state=:state, snooze_until=:snooze "
                "where card_id=:card and org_id=:o"),
                {"state": state, "snooze": snooze_at, "card": card_id, "o": org_id})
        if state == "acted":
            c.execute(text(
                "update signals set status='acted' where signal_id=:signal and org_id=:o"),
                {"signal": card["signal_id"], "o": org_id})
        if action == "answer":
            from genios_engine.context import founder_questions

            founder_questions.answer(c, org_id=org_id, question_id=question_id, words=words, by=actor,
                                     at=eval_time)
            answered_version = _version_answered(c, org_id=org_id, card=card, question_id=question_id,
                                                 actor=actor)

        c.execute(text(
            "insert into human_events (id, org_id, type, actor_id, target, detail, occurred_at) "
            "values (:id,:o,:type,:actor,cast(:target as jsonb),cast(:detail as jsonb),:at)"),
            {"id": new_id("hev"), "o": org_id, "type": f"card.{action}", "actor": actor,
             "target": json.dumps({"card_id": card_id, "signal_id": card["signal_id"]}),
             "detail": json.dumps(detail, default=str), "at": eval_time})
        c.execute(text(
            "insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail) "
            "values (:id,:card,:o,:kind,:cause,:actor,cast(:detail as jsonb))"),
            {"id": new_id("cev"), "card": card_id, "o": org_id,
             "kind": "ui.requeued" if action == "requeue" else "human.card_action",
             "cause": action, "actor": actor, "detail": json.dumps(detail, default=str)})

        # The card surface and the execution subsystem used to be two disconnected state
        # machines: this function never touched `executions`, so a card the founder marked
        # acted left its linked commitment sitting at `created`/`pending` with the clock still
        # running — the founder's only real signal reached nowhere, L7 learned nothing from it,
        # and the divergence was invisible until L5 delivery went live and someone compared the
        # two surfaces by hand.
        #
        # A card action means "claimed", never "done" — no scoped success evidence has arrived
        # yet, only intent — so this moves PENDING/RUNNING toward RUNNING, not toward COMPLETED.
        # Same transaction as the card write, so the two surfaces can never observe a state where
        # one moved and the other did not; a lost race (already RUNNING, or not yet PENDING)
        # is a no-op here exactly as it is everywhere else `apply_transition` is called — another
        # worker's move is the one that counts, not a reason to fail the button press.
        if action in _CLAIMING_ACTIONS:
            execution = c.execute(text(
                "select execution_id, state, card_id from executions "
                "where org_id=:o and signal_id=:signal "
                "order by created_at desc limit 1 for update"),
                {"o": org_id, "signal": card["signal_id"]}).mappings().first()
            if execution is not None:
                if execution["card_id"] is None:
                    _link_execution_card(c, org_id=org_id,
                                         execution_id=execution["execution_id"], card_id=card_id)
                if execution["state"] == ExecutionState.PENDING.value:
                    move = _execution_transition(
                        ExecutionState.PENDING, ExecutionState.RUNNING,
                        reason_code="human_claimed", actor=actor, at=eval_time,
                        detail=f"card_action:{action}")
                    _apply_execution_transition(
                        c, org_id=org_id, execution_id=execution["execution_id"], move=move)

    if action == "snooze":
        return {"ok": True, "state": state, "snooze_until": snooze_at.isoformat()}
    return {"ok": True, "state": state, "action": action,
            **({"reason": reason} if action == "wrong" else {}),
            **({"question_id": question_id, "version": answered_version} if action == "answer" else {})}


def _version_answered(c, *, org_id: str, card, question_id: str, actor: str) -> int | None:
    """The answered version of the file's card (s14-D3, see `ANSWERED_HEADLINE`): one `card.versioned` event, its
    words before the question's — and none of your words — the card kept on its open signal, its words in place."""
    from genios_engine.contracts.card_version import ANSWERED_MODE, VersionWords, version_of
    from genios_engine.deliver.store import _LAST_WORDS
    from genios_engine.platform import card_lifecycle

    row = c.execute(text("select version, headline, situation, output_lane from cards "
                         "where org_id=:o and card_id=:card"), {"o": org_id, "card": card["card_id"]}).first()
    said = c.execute(text(_LAST_WORDS), {"o": org_id, "id": card["card_id"]}).scalar()
    before = (VersionWords.from_mapping(said) if said else
              VersionWords(headline=row.headline, situation=row.situation, lane=row.output_lane))
    after = VersionWords(headline=ANSWERED_HEADLINE, situation=row.headline, lane=ANSWERED_LANE,
                         mode=ANSWERED_MODE, ask=question_id)
    version = version_of(before, after, version=int(row.version) + 1, signal_id=card["signal_id"], answered=True)
    if not card_lifecycle.version_card(c, org_id=org_id, card_id=card["card_id"], version=version,
                                       expires_at=card["expires_at"], actor=actor):
        return None
    c.execute(text(
        "update cards set headline=:h, situation=:s, output_lane=:lane, lane_reason=:why, "
        "actions=cast(:act as jsonb) where org_id=:o and card_id=:card"),
        {"h": after.headline, "s": after.situation, "lane": ANSWERED_LANE, "why": ANSWERED_LANE_REASON,
         "act": json.dumps(ANSWERED_ACTIONS), "o": org_id, "card": card["card_id"]})
    return version.version
