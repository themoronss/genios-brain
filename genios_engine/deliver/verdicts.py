"""The one writer of a verdict — what you said about a card, kept once, whichever door you said it by.

STEP-16 (`yc2_w27_s16` M46.C2.L-data.V1.U02; `s16-F1`). ⛔ WHY ONE WRITER. Your verdict on a card came in by
two doors and landed in two places: the extension's (`POST /v1/intelligence/feedback`) wrote
`card_feedback_verdicts` with two statements of its own, and the dashboard's button
(`deliver/actions.ingest_action`) wrote `card_events` only. Calibration reads both; the eight other readers
— the expert's dossier and its file fingerprint, the change gate's inputs, the learning batch, the adaptive
lease, a file's history facts, the counterfactual ledger, the receipt "a human verdict has reached the loop"
— read the ledger only. So the reason you pressed on a card never reached the expert.

This module is the ledger's only writer in the engine. The route's two statements moved here byte for
byte: the verdict (one row per card — idempotent, its version bumped only when what you said changed) and
its revision (one per version), `occurred_at` the request's ONE instant (`as_of` — the same instant the
caller judged the card's authority against and the adaptive lease counts its cohort up to).

A VERDICT IS: `run_play` or `do_it_myself` (you took the card), or `wrong` with one of the eleven reasons
(`contracts/learning_attribution.ALL_REASONS`, the set `0210` admits). `snooze` and `requeue` NEVER are — a
deferral says nothing about whether the card was right — and `answer` is your answer to a question, kept on
the file (`context/founder_questions`), not a verdict. Each is refused before any statement runs.

BOUND TO THE CARD'S OWN AUTHORITY. `binding_of` reads what the ledger records the verdict against:
  * a DECISION's card — the audited decision it rests on (`reason/authority.AUTHORITATIVE_SIGNAL_JOINS` and
    `AUTHORITATIVE_SIGNAL_PREDICATE`): its pack, version and authority revision, its capability and rule;
  * a QUESTION's card — the question's own authority (`QUESTION_SIGNAL_JOINS`, `QUESTION_SIGNAL_PREDICATE`),
    never the decision's: the run that asked it, its rule `founder_question`, and no pack revision (`0` — a
    question binds none). `founder_question` is a rule of no pack manifest and calibration joins only cards
    a pack revision authorises, so calibration never scores it (`tests/feedback/
    test_learning_from_you_arms_nothing.py`).
Read while the card's signal is still open — before the caller acts on it. A card neither authority binds
(a team or verify situation card, a stale one) has no binding, and no verdict is written for it.

The caller owns the transaction: the route evaluates the adaptive lease in it after a changed verdict, as
it always has; this module writes the ledger and nothing else.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text

from genios_engine.contracts.learning_attribution import ALL_REASONS
from genios_engine.platform.canonical import stable_id
from genios_engine.reason.authority import (
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
    QUESTION_SIGNAL_JOINS,
    QUESTION_SIGNAL_PREDICATE,
)

#: What a verdict is: you took the card, or it was wrong.
VERDICT_CAUSES = frozenset({"run_play", "do_it_myself", "wrong"})
#: ⛔ A deferral is never a verdict — it says nothing about whether the card was right.
NEVER_VERDICTS = frozenset({"snooze", "requeue"})
#: The eleven reasons the ledger admits (`0210`), imported — never a copy spelled here.
WRONG_REASONS = frozenset(ALL_REASONS)

#: Which authority bound the verdict.
OF_DECISION = "decision"
OF_QUESTION = "question"

#: The decision's authority on a card whose signal is still open (the extension's door's own read).
DECISION_BINDING_SQL = (
    "select authority_cfg.pack_id, authority_cfg.effective->>'version' as pack_version, "
    "s.authority_pack_revision, rr.capability_id, rr.capability_version, "
    "regexp_replace(rr.capability_id, '^.*\\.', '') as rule_id "
    "from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id "
    + AUTHORITATIVE_SIGNAL_JOINS +
    " where k.card_id=:card and k.org_id=:o and s.status='open' "
    "and k.expires_at > :authority_time and " + AUTHORITATIVE_SIGNAL_PREDICATE
)

#: A question's own authority: the run that asked it, the signal's own rule (`founder_question`), and no
#: pack revision — a question binds none, so the ledger records `0`.
QUESTION_BINDING_SQL = (
    "select s.pack_id, s.pack_version, coalesce(s.authority_pack_revision, 0) as authority_pack_revision, "
    "question_rr.capability_id, question_rr.capability_version, s.rule_id "
    "from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id "
    + QUESTION_SIGNAL_JOINS +
    " where k.card_id=:card and k.org_id=:o and s.status='open' "
    "and k.expires_at > :authority_time and " + QUESTION_SIGNAL_PREDICATE
)


@dataclass(frozen=True, slots=True)
class Binding:
    """What the ledger records a verdict against: the authority that put the card in front of you."""

    pack_id: str
    pack_version: str
    authority_pack_revision: int
    capability_id: str
    capability_version: str
    rule_id: str
    of: str = OF_DECISION


@dataclass(frozen=True, slots=True)
class Recorded:
    """The verdict as the ledger now holds it, and whether this call changed it."""

    feedback_id: str
    verdict_version: int
    changed: bool


def feedback_id_of(org_id: str, card_id: str) -> str:
    """One card, one verdict id — the extension's since it was written, so a verdict already kept is the
    same verdict whichever door changes it next."""
    return stable_id("fb", {"org_id": org_id, "card_id": card_id, "decision_id": ""})


def binding_of(conn, *, org_id: str, card_id: str, at: datetime) -> Binding | None:
    """The card's own authority — a decision's, else a question's — while its signal is open; else None."""
    params = {"card": card_id, "o": org_id, "authority_time": at}
    row = conn.execute(text(DECISION_BINDING_SQL), params).first()
    of = OF_DECISION
    if row is None:
        row = conn.execute(text(QUESTION_BINDING_SQL), params).first()
        of = OF_QUESTION
    if row is None:
        return None
    return Binding(pack_id=row.pack_id, pack_version=row.pack_version,
                   authority_pack_revision=int(row.authority_pack_revision),
                   capability_id=row.capability_id, capability_version=row.capability_version,
                   rule_id=row.rule_id, of=of)


def _refused(cause: str, reason: str | None) -> str | None:
    if cause not in VERDICT_CAUSES:            # a deferral (`NEVER_VERDICTS`) among them
        return f"{cause!r} is no verdict: {sorted(VERDICT_CAUSES)}"
    if cause == "wrong" and reason not in WRONG_REASONS:
        return f"a 'wrong' verdict needs one of the eleven reasons, not {reason!r}"
    if cause != "wrong" and reason is not None:
        return "a reason belongs to a 'wrong' verdict"
    return None


def record(conn, *, org_id: str, card_id: str, binding: Binding, cause: str, reason: str | None,
           detail: Mapping, actor: str, as_of: datetime, feedback_id: str | None = None) -> Recorded:
    """Keep your verdict on the card, in the caller's transaction: once per card, a new version only when
    what you said changed, each version a revision. ``as_of`` is the request's one instant."""
    refused = _refused(cause, reason)
    if refused is not None:
        raise ValueError(refused)
    encoded_detail = json.dumps(
        dict(detail), sort_keys=True, separators=(",", ":"), default=str, allow_nan=False)
    fid = feedback_id or feedback_id_of(org_id, card_id)
    verdict_version = None
    changed = False
    inserted = conn.execute(text(
        "insert into card_feedback_verdicts "
        "(feedback_id,org_id,card_id,pack_id,pack_version,authority_pack_revision,"
        "capability_id,"
        "capability_version,rule_id,cause,reason,detail,actor_id,verdict_version,"
        "occurred_at) "
        "values (:id,:o,:card,:p,:pv,:pr,:cap,:capv,:r,:cause,:reason,"
        "cast(:d as jsonb),:actor,1,:as_of) "
        "on conflict (org_id,card_id) do nothing returning verdict_version"),
        {"id": fid, "o": org_id, "card": card_id,
         "p": binding.pack_id, "pv": binding.pack_version,
         "pr": int(binding.authority_pack_revision),
         "cap": binding.capability_id, "capv": binding.capability_version,
         "r": binding.rule_id, "cause": cause, "reason": reason,
         "d": encoded_detail, "actor": actor, "as_of": as_of}).first()
    if inserted is not None:
        verdict_version = int(inserted.verdict_version)
        changed = True
    else:
        updated = conn.execute(text(
            "update card_feedback_verdicts set cause=:cause,reason=:reason,"
            "detail=cast(:d as jsonb),actor_id=:actor,"
            "verdict_version=verdict_version+1,occurred_at=:as_of "
            "where org_id=:o and card_id=:card and "
            "(cause,reason,detail) is distinct from "
            "(:cause,:reason,cast(:d as jsonb)) returning verdict_version"),
            {"o": org_id, "card": card_id, "cause": cause,
             "reason": reason, "d": encoded_detail, "actor": actor,
             "as_of": as_of}).first()
        if updated is not None:
            verdict_version = int(updated.verdict_version)
            changed = True
        else:
            existing = conn.execute(text(
                "select feedback_id,verdict_version from card_feedback_verdicts "
                "where org_id=:o and card_id=:card"),
                {"o": org_id, "card": card_id}).first()
            if existing is None:
                raise RuntimeError("feedback verdict disappeared while card was locked")
            fid = existing.feedback_id
            verdict_version = int(existing.verdict_version)
    if changed:
        revision_id = stable_id("fbrev", {
            "feedback_id": fid, "verdict_version": verdict_version})
        conn.execute(text(
            "insert into card_feedback_revisions "
            "(revision_id,feedback_id,org_id,card_id,verdict_version,cause,reason,"
            "detail,actor_id) values (:rid,:fid,:o,:card,:v,:cause,:reason,"
            "cast(:d as jsonb),:actor)"),
            {"rid": revision_id, "fid": fid, "o": org_id,
             "card": card_id, "v": verdict_version, "cause": cause,
             "reason": reason, "d": encoded_detail, "actor": actor})
    return Recorded(feedback_id=fid, verdict_version=verdict_version, changed=changed)


__all__ = ["Binding", "DECISION_BINDING_SQL", "NEVER_VERDICTS", "OF_DECISION", "OF_QUESTION",
           "QUESTION_BINDING_SQL", "Recorded", "VERDICT_CAUSES", "WRONG_REASONS", "binding_of",
           "feedback_id_of", "record"]
