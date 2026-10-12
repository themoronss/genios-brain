"""A held file asks the founder its one question (STEP-13, `yc2_w27_s13` M36.C2.L-integration.V2.U03).

A covered file decided INSUFFICIENT on its answer — its review's move HELD by the check, or a review that must
find out first — asks the founder ONE question (`06` D60, `03` F184): filed in `founder_questions` by the run
that asked it, and carried by a question signal — the Investigation lane, bound to that run's decision
(binding 0: no candidate, no selected move), authorised as a question
(`reason/authority.QUESTION_SIGNAL_PREDICATE`) and never as a decision. One open question signal per file:
the same question asked again keeps its signal, RE-BOUND to the run asking it now — its card is not torn
down and rebuilt; a new question replaces it, its card REPLACED; any other decision retires the file's
question and expires its signal. Words the file already ANSWERED are never asked again, whatever review
asks them (M36.C2.L-data.V2.U12, `03` X25): no signal, and the file's open question signal expires.

ITS OWN MODULE, because it is its own writer of `signals` (`reason/situation_binding.SIGNAL_WRITERS`, one
function each): a question is not the compiled lane's decision, and folding its insert into
`reason/domain_shadow` hid a second writer behind the first's declaration. `domain_shadow` calls it, a
covered file at a time.
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import text

from genios_engine.platform import card_lifecycle

QUESTION_RULE = "founder_question"

_OPEN_QUESTION_SIGNAL = (
    "select signal_id from signals where org_id = :o and rule_id = 'founder_question' "
    "and subject_node_id = :n and status = 'open'")
#: Every open question signal of the file, expired — by a decision that is no question, or by a question
#: the file already answered (`retire_question`, `ask_the_founder`).
_EXPIRE_QUESTION_SIGNALS = (
    "update signals set status = 'expired' where org_id = :o and rule_id = 'founder_question' "
    "and subject_node_id = :n and status = 'open' returning signal_id")
#: What asking came to: a question filed, the one already open re-bound, or words the file already answered.
ASKED = "asked"
STANDING = "standing"
ANSWERED_ALREADY = "answered_already"


def question_words(review) -> tuple[str, str]:
    """What the file asks, and why — the check's own question and its reason; a review that must find
    out first asks its own move, because the file cannot be read on without its answer."""
    checked = review.checked
    move = review.review.next_move
    question = (checked.question if checked is not None and checked.question else None) \
        or (move.what if move is not None else review.review.frames.primary)
    why = (checked.because if checked is not None and checked.because else None) \
        or "the expert cannot read this file on without your answer: " + review.review.frames.primary
    return question, why


def ask_the_founder(store, *, org_id: str, file_id: str, review, decision, bundle: dict, pack: dict,
                     eval_time, situation_id: str | None) -> str:
    """File the file's question and its signal: `asked`, or `standing` (re-bound to this run) — or
    `answered_already`: words the file already answered are not asked again (M36.C2.L-data.V2.U12, `03`
    X25), so no signal is filed, and the file's open question signal expires, its card REPLACED — the
    question it carried is one this review no longer asks (`context/founder_questions.ask` retired it)."""
    from genios_engine.context import founder_questions as questions

    run, output = bundle.get("run") or {}, bundle.get("output") or {}
    question, why = question_words(review)
    with store.engine.begin() as conn:
        before = questions.open_question(conn, org_id, file_id)
        asked = questions.ask(conn, org_id=org_id, file_id=file_id, fingerprint=review.fingerprint,
                              run_id=run.get("run_id"), question=question, why=why, at=eval_time)
        if asked.state == questions.ANSWERED:
            expired = conn.execute(text(_EXPIRE_QUESTION_SIGNALS), {"o": org_id, "n": file_id}).fetchall()
            if expired:
                card_lifecycle.expire_cards(conn, org_id=org_id, cause=card_lifecycle.REPLACED,
                                            signal_ids=[item.signal_id for item in expired])
            return ANSWERED_ALREADY
        standing = conn.execute(text(_OPEN_QUESTION_SIGNAL), {"o": org_id, "n": file_id}).first()
        bound = {"o": org_id, "run": run.get("run_id"), "dhash": output.get("decision_hash"),
                 "exp": decision.expires_at, "cfg": run.get("config_snapshot_id"), "et": eval_time}
        if standing is not None and before is not None and before.question_id == asked.question_id:
            conn.execute(text(
                "update signals set reasoning_run_id = :run, reasoning_decision_hash = :dhash, "
                "authority_expires_at = :exp, config_snapshot_id = :cfg, eval_time = :et "
                "where org_id = :o and signal_id = :s"), {**bound, "s": standing.signal_id})
            return STANDING
        if standing is not None:
            conn.execute(text("update signals set status = 'expired' where org_id = :o and signal_id = :s"),
                         {"o": org_id, "s": standing.signal_id})
            card_lifecycle.expire_cards(conn, org_id=org_id, cause=card_lifecycle.REPLACED,
                                        signal_ids=[standing.signal_id])
        conn.execute(text(
            "insert into signals (signal_id, org_id, pack_id, pack_version, rule_id, rule_version, level, "
            "subject_node_id, score, reason_code, evidence, eval_time, config_snapshot_id, reasoning_run_id, "
            "reasoning_decision_hash, authority_expires_at, authority_binding_version, output_lane, "
            "lane_reason, capability_id, capability_version, situation_id) values (:id, :o, :pack, :packv, "
            "'founder_question', 1, 'observation', :n, 0, 'founder_question', cast(:ev as jsonb), :et, :cfg, "
            ":run, :dhash, :exp, 0, :lane, :lreason, :cap, :capv, :sit)"), {
                # Its id is its content's — the question and the run asking it — so asking mints no id
                # another part of the run would have minted (`03` F170's rule).
                **bound, "id": "sig_" + hashlib.sha256(
                    f"{org_id}\x1f{asked.question_id}\x1f{run.get('run_id')}".encode()).hexdigest()[:24],
                "pack": pack["pack_id"], "packv": pack["version"],
                "n": file_id,
                "ev": json.dumps([{"field": "founder_question", "value": asked.question_id}]),
                "lane": decision.output_lane.value if decision.output_lane is not None else None,
                "lreason": decision.lane_reason,
                "cap": decision.capability_id, "capv": decision.capability_version,
                "sit": (str(situation_id).strip() or None) if situation_id else None})
    return ASKED


def retire_question(store, *, org_id: str, file_id: str, eval_time) -> bool:
    """A decision that is no question: the file's open question retires, and its signal and card with it."""
    from genios_engine.context import founder_questions as questions

    with store.engine.begin() as conn:
        retired = questions.retire(conn, org_id=org_id, file_id=file_id, why=questions.NO_LONGER_ASKED,
                                   at=eval_time)
        expired = conn.execute(text(_EXPIRE_QUESTION_SIGNALS), {"o": org_id, "n": file_id}).fetchall()
        if expired:
            card_lifecycle.expire_cards(conn, org_id=org_id, cause=card_lifecycle.REPLACED,
                                        signal_ids=[item.signal_id for item in expired])
    return bool(retired or expired)
