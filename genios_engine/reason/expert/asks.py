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

⛔ IT HANDS THE FILE ON (STEP-14, `yc2_w27_s14` M42.C2.L-integration.V2.U05; `03` F176, s14-F13). A file's question is
its card's next version, and so is the decision after it: a new question, and a decision after a question, retire
the old signal and LEAVE ITS CARD — delivery versions it onto the file's new signal (`deliver/store`, M42.C3) —
never expired REPLACED, which made each a second card. Only a question nothing will version closes its card: one the
file already answered, one whose file left the expert's coverage, one no decision follows.
"""
from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy import text

from genios_engine.contracts import claim_check
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
#: What leaves the file's question standing — what the change gate remembers as STANDING on its window.
ASKING: frozenset[str] = frozenset({ASKED, STANDING})


# ── what is asked, in checked words (STEP-13 M36.C2.L-logic.V2.U10, `03` X06, X10, X34) ──────────────────────────
#
# Every word a question card says is a word the check let stand, or one of ours, closed. A held file asks
# the check's own question (`contracts/claim_check.CheckedReview.question`). A file that must find out first
# asks YOU a real question: its review's unknowns in order, the first that is a question — or reads as one —
# and every name and number of which is in the checked words; else its checked move, WHEN THAT IS A QUESTION;
# else our closed one. ⛔ NEVER AN INSTRUCTION (M36.C2.L-logic.V2.U17, the second crosscheck G8): a move is
# an instruction ("Find out whether…", "Check the count…") and "Can you tell us: <it>?" asked you to do it.
# Never the raw reading (`frames.primary`): a find-out reading is checked like any other, and the check may
# have withheld it. And WHY is one closed, founder-facing phrase — never the check's internal reason string.
#
# One name to a line: `tests/test_no_missing_module_deps` reads a module's names by their assignments.
WHY_FIND_OUT = "we hold this file until you answer"
WHY_NOT_CONFIRMED = "we could not confirm what it rests on from what it cites"
WHY_SAYS_MORE = "its next step says more than the file shows"
WHY_ADDRESSED_TO_YOU = "its next step is addressed to you"
WHY_TO_THE_CONNECTOR = "its next step goes to whoever introduced them"
WHY_CONFIRM = "its next step rests only on what you told us, so we confirm it with you first"
#: Why a file asks after your answer, when its review asks what you already answered (M36.C2.L-data.V2.U14).
WHY_AFTER_YOUR_ANSWER = "we read your answer, and what its next step rests on still does not hold"
WHYS: tuple[str, ...] = (WHY_FIND_OUT, WHY_NOT_CONFIRMED, WHY_SAYS_MORE, WHY_ADDRESSED_TO_YOU,
                         WHY_TO_THE_CONNECTOR, WHY_CONFIRM, WHY_AFTER_YOUR_ANSWER)
#: What a file asks when nothing checked can be asked — ours, closed (`contracts/claim_check`, one place).
NOTHING_TO_ASK = claim_check.NOTHING_TO_ASK
#: An unknown written as an indirect question ("Whether the examiner has raised a query.") reads as one.
_INDIRECT = re.compile(r"^(?:whether|if|what|which|who|whom|whose|when|where|why|how)\b", re.I)
_FACT_LINE = re.compile(r"^fact:(\d+)$")


def _checked_corpus(review, checked) -> str:
    """The words the check let stand: the card's words, the quotes it matched, the facts it kept."""
    kept = {int(m.group(1)) for v in checked.verdicts
            if v.verdict == "kept" and (m := _FACT_LINE.match(v.line)) is not None}
    facts = [f.claim for n, f in enumerate(review.facts, start=1) if n in kept]
    w = checked.words
    return "\n".join(str(t) for t in (w.headline, w.situation, w.done_when, w.draft, *w.quotes, *facts) if t)


def _stands_on(text: str, corpus: str) -> bool:
    """Is every name and number of `text` in `corpus` — the card validator's own rule
    (`platform/grounding.invention_ok`)? Its first word is read as the start of a sentence, not a name."""
    from genios_engine.platform.grounding import corpus_of, digit_runs, invention_ok

    held, nums = corpus_of([corpus])
    plain = text[:1].lower() + text[1:]
    # Each number whole — a "1" is not held by a "12" — and each name by the card validator's rule.
    return digit_runs(plain) <= nums and invention_ok(plain, held, nums)[0]


def _as_question(text: str) -> str | None:
    """`text` as a question to you — as written, when it is one; framed, when it reads as one; else None."""
    said = " ".join(str(text or "").split()).rstrip(" .;:")
    if not said:
        return None
    if said.endswith("?"):
        return said
    if _INDIRECT.match(said):
        return f"Can you tell us {said[:1].lower()}{said[1:]}?"
    return None


def _find_out_question(review, checked, ours=None, you=None) -> str:
    """A find-out file's question: its first unknown, or its checked move (see above) — never one that names us
    (`ours`, the sweep's `platform/self_identity.speaks_of_us` over the tenant's names: STEP-04's rule — we are
    never a card's party; the golden lane, 12 Oct, F22 and F52). ⛔ A QUESTION TO YOU NEVER NAMES YOU
    (M36.C2.L-logic.V2.U19, second crosscheck F3): one that does is asked in the second person (`you`,
    `platform/self_identity.to_you`: "whether Arjun went" → "whether you went"), else passed over; else the
    closed question."""
    corpus = _checked_corpus(review, checked) if checked is not None else ""
    candidates = []
    for unknown in review.unknowns:
        said = " ".join(unknown.question.split())
        asked = _as_question(said)
        if asked is not None and _stands_on(said, corpus):
            candidates.append(asked)
    move = checked.words.headline if checked is not None else None
    if move and (asked := _as_question(move)) is not None:
        candidates.append(asked)                      # a move that IS a question — never one framed as one
    for candidate in candidates:
        if ours is None or not ours(candidate):
            return candidate
        said = you(candidate) if you is not None else None
        if said and not ours(said):
            return said
    return NOTHING_TO_ASK


def _why_held(review, checked) -> str:
    """Why a held file asks, in one closed phrase — read off the check's verdicts in the order its fate is
    decided (`reason/expert/verify`): a fact the move rests on, then the move's own words, then whom it
    goes to."""
    dropped = [(v.line, v.reason) for v in checked.verdicts if v.verdict == "dropped"]
    move = review.next_move
    named = {int(m.group(1)) for r in (move.rests_on if move is not None else ())
             if (m := _FACT_LINE.match(r)) is not None}
    rested = named or set(range(1, len(review.facts) + 1))
    if any((m := _FACT_LINE.match(line)) is not None and int(m.group(1)) in rested for line, _ in dropped):
        return WHY_NOT_CONFIRMED
    if any(line == "move" for line, _ in dropped):
        return WHY_SAYS_MORE
    if ("rests_on", "on_your_answer") in dropped:
        return WHY_CONFIRM
    if ("to", "recipient_is_us") in dropped:
        return WHY_ADDRESSED_TO_YOU
    if ("to", "recipient_is_connector") in dropped:
        return WHY_TO_THE_CONNECTOR
    return WHY_FIND_OUT


def _names_us_for(conn, org_id: str):
    """Whether a text names one of us — and the same text said to you — over the tenant's identity and names, as
    `reason/expert/sweep` reads them (`03` F158): ⛔ as PROSE (`platform/self_identity.speaks_of_us`,
    M36.C2.L-logic.V2.U19 — the company's name at any length, a first or full name, our domains), never as a
    subject (`names_us`, where "GeniOS" alone and "Rohit" claim nothing)."""
    from genios_engine.platform.self_identity import identity_for, speaks_of_us, to_you

    us = identity_for(conn, org_id)
    org = conn.execute(text("select name, company, first_name, last_name from orgs where id = :o"),
                       {"o": org_id}).first()
    names = tuple(n for n in ((org.company, org.name, " ".join(p for p in (org.first_name, org.last_name) if p))
                              if org is not None else ()) if n)
    return (lambda words: speaks_of_us(words, us, names=names)), (lambda words: to_you(words, us, names=names))


def question_words(review, *, ours=None, you=None) -> tuple[str, str]:
    """What the file asks, and why — in checked words (see above): a held file the check's own question (which
    names none of us: `reason/expert/verify`), a find-out file a real question to you that names none of us
    (`ours`; said to you, `you`, where it can be); why, one of `WHYS`."""
    checked = review.checked
    if checked is not None and checked.fate == "held" and checked.question:
        return " ".join(checked.question.split()), _why_held(review.review, checked)
    return _find_out_question(review.review, checked, ours, you), WHY_FIND_OUT


def after_your_answer(words: str) -> str:
    """What a file asks when its review asks again what you already answered (M36.C2.L-data.V2.U14, second
    crosscheck F2): your latest words, and what should happen next — ours, closed, and your own words."""
    return f"You answered: “{' '.join(str(words).split())}”. What should happen next on this file?"


def ask_the_founder(store, *, org_id: str, file_id: str, review, decision, bundle: dict, pack: dict,
                     eval_time, situation_id: str | None) -> str:
    """File the file's question and its signal: `asked`, or `standing` (re-bound to this run). Words the file
    already answered are never asked again (M36.C2.L-data.V2.U12, `03` X25) — ⛔ and the file is never silenced
    by them (M36.C2.L-data.V2.U14, the second crosscheck F2): it asks what should happen next instead
    (`after_your_answer`), quoting your latest words. Only when that was answered too: `answered_already` — no
    signal is filed, and the file's open question signal expires, its card REPLACED (the question it carried
    is one this review no longer asks: `context/founder_questions.ask` retired it)."""
    from genios_engine.context import founder_questions as questions

    run, output = bundle.get("run") or {}, bundle.get("output") or {}
    with store.engine.begin() as conn:
        questions.lock_file(conn, org_id, file_id)       # ⛔ the file's question first (G11, `lock_file`)
        ours, you = _names_us_for(conn, org_id)
        question, why = question_words(review, ours=ours, you=you)
        before = questions.open_question(conn, org_id, file_id)
        asked = questions.ask(conn, org_id=org_id, file_id=file_id, fingerprint=review.fingerprint,
                              run_id=run.get("run_id"), question=question, why=why, at=eval_time)
        if asked.state == questions.ANSWERED:
            # ⛔ NEVER SILENCED (M36.C2.L-data.V2.U14, second crosscheck F2): the review asks what you already
            # answered — it read your answer and its move still does not stand. The file does not go quiet: it
            # asks what should happen next, quoting your latest words. Only when THAT was answered too — your
            # latest words are the answer to it — is there nothing left to ask.
            latest = questions.answers_for(conn, org_id, file_id)[0]
            asked = questions.ask(conn, org_id=org_id, file_id=file_id, fingerprint=review.fingerprint,
                                  run_id=run.get("run_id"), question=after_your_answer(latest.answer),
                                  why=WHY_AFTER_YOUR_ANSWER, at=eval_time)
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
            # RE-BOUND, ITS CARD'S WINDOW WITH IT (M36.C2.L-integration.V2.U11, `03` X04): one statement, so
            # the signal's authority and the window of its unresolved card never disagree — a card is never
            # capped at an authority its signal has since outgrown. A card that already lapsed stays lapsed
            # here: reviving it is the card builder's (`deliver/store`), and a resolved one is nobody's.
            conn.execute(text(
                "with rebound as (update signals set reasoning_run_id = :run, reasoning_decision_hash = :dhash, "
                "authority_expires_at = :exp, config_snapshot_id = :cfg, eval_time = :et "
                "where org_id = :o and signal_id = :s returning signal_id) "
                "update cards set expires_at = :exp where org_id = :o and signal_id = :s "
                "and resolved_at is null"), {**bound, "s": standing.signal_id})
            return STANDING
        if standing is not None:
            # A NEW question retires the old one's signal; its card is the new question's to version (STEP-14).
            conn.execute(text("update signals set status = 'expired' where org_id = :o and signal_id = :s"),
                         {"o": org_id, "s": standing.signal_id})
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


def retire_question(store, *, org_id: str, file_id: str, eval_time, why: str | None = None,
                    hand_on: bool = False) -> bool:
    """A decision that is no question — or a file no longer the expert's to decide (`LEFT_COVERAGE`): the
    file's open question retires, saying why, and its signal with it. Its card goes too — unless `hand_on`: the
    decision the file emits (or keeps) is the card's next version, and delivery versions it (STEP-14)."""
    from genios_engine.context import founder_questions as questions

    with store.engine.begin() as conn:
        questions.lock_file(conn, org_id, file_id)       # ⛔ the file's question first (G11, `lock_file`)
        retired = questions.retire(conn, org_id=org_id, file_id=file_id, why=why or questions.NO_LONGER_ASKED,
                                   at=eval_time)
        expired = conn.execute(text(_EXPIRE_QUESTION_SIGNALS), {"o": org_id, "n": file_id}).fetchall()
        if expired and not hand_on:
            card_lifecycle.expire_cards(conn, org_id=org_id, cause=card_lifecycle.REPLACED,
                                        signal_ids=[item.signal_id for item in expired])
    return bool(retired or expired)
