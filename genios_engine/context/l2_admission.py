"""L2 rebuild B3 (GeniOS-008 L2-G2) · Layer 3 admits what the Layer 2 judgment proposed — ADMIT / HOLD / REJECT.

THE ORDER (Design Atlas v2, L3 §). The Evidence Graph — what the sources say — is written by L1's facts. The
Intelligence Graph — what GeniOS concluded — is written only by "L3 admission of L2's mutations". Today's joins
and readings still file a situation row per file BEFORE any reasoning (`context/runner.process_pending`); from
here those rows are SEEDS (Atlas L2.2: "L1 bundle → SituationSeed → L2 reasoning → ReasoningResult → L3 admits").
A seed becomes a situation GeniOS stands behind only when its file's judgment is admitted here — so reasoning
comes first, and the conclusion after it.

WHY THE SEED, NOT A NEW ROW. A `create` proposal carries the situation in words only — no type, no anchor, no
correlation — and `context_situations` holds one row per correlation. A proposal cannot be a row; it can only
confirm, change or end the seed the joins already built for that file. So:

  for each situation the file's dossier printed (`sit:<id>`, `parts.lifecycle`):
    named by an `update` / `close`         → ADMIT, with that op
    named by a `merge` / `link`            → HOLD — no applier for either yet; recorded, never guessed
    the judgment found nothing material    → REJECT (lane `suppress`, or intervention `abstain`)
    live, and the judgment proposed `create` → ADMIT `create` — the seed it reasoned about is the situation
    live, the file's ONLY live one          → ADMIT `unchanged` — what the judgment is about
    live, one of several, not named        → HOLD — which one the judgment meant is not settled here
  a seed subject (no file yet) that proposed `create` → HOLD at subject level (`situation_id='-'`)
  a run with no result (refused, failed, carried)     → nothing: the last decision stands

Pure `decide`; `write_admissions` upserts the latest decision per (subject, situation) on the caller's
transaction — the L2 sweep's one. ⛔ SHADOW: nothing here touches `context_situations`.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.reasoning_result import MUTATION_NEEDS_REF

ADMIT = "admit"
HOLD = "hold"
REJECT = "reject"
#: Situation statuses a seed is still live in.
LIVE = frozenset({"active", "partial"})
#: The subject-level key for a decision with no situation row behind it.
NO_SITUATION = "-"
#: Lanes / modes in which the judgment found nothing material to stand behind.
_NOTHING_LANES = frozenset({"suppress"})
_NOTHING_MODES = frozenset({"abstain"})
#: The ops L3 can apply to the seed they name, and the ones it holds (no applier yet).
_HELD_OPS = frozenset({"merge", "link"})
_APPLIED_OPS = frozenset(MUTATION_NEEDS_REF) - _HELD_OPS


@dataclass(frozen=True, slots=True)
class Admission:
    org_id: str
    subject_ref: str
    situation_id: str
    decision: str
    op: str
    reason: str | None
    result_fingerprint: str
    lane: str | None

    def params(self, at: datetime) -> dict[str, Any]:
        return {"o": self.org_id, "s": self.subject_ref, "sit": self.situation_id, "d": self.decision,
                "op": self.op, "r": (self.reason or "")[:500] or None, "fp": self.result_fingerprint,
                "ln": self.lane, "at": at}


def _sid(ref: str | None) -> str | None:
    if not ref:
        return None
    return ref.split(":", 1)[1] if ref.startswith("sit:") else ref


def decide(*, org_id: str, subject_ref: str, fingerprint: str, result: Any,
           situations: Sequence[Any] = ()) -> list[Admission]:
    """The admission of one judged subject. Pure. `situations` are the file's (`parts.lifecycle.situations`);
    `result` a `ReasoningResult`, or None for a run that concluded nothing."""
    if result is None:
        return []
    lane = getattr(result, "lane", None)
    mutations = tuple(getattr(result, "proposed_mutations", ()) or ())
    named = {_sid(m.situation_ref): m for m in mutations if _sid(getattr(m, "situation_ref", None))}
    creates = [m for m in mutations if m.op == "create"]
    nothing = lane in _NOTHING_LANES or getattr(result, "intervention_mode", None) in _NOTHING_MODES
    live = [s for s in situations if (getattr(s, "status", None) or "") in LIVE]

    def one(situation_id: str, decision: str, op: str, reason: str | None) -> Admission:
        return Admission(org_id=org_id, subject_ref=subject_ref, situation_id=situation_id, decision=decision,
                         op=op, reason=reason, result_fingerprint=fingerprint, lane=lane)

    out: list[Admission] = []
    if not situations:
        if creates and not nothing:
            out.append(one(NO_SITUATION, HOLD, "create",
                           "no situation seed for this subject yet — no join has filed it"))
        return out
    for s in situations:
        sid = str(s.situation_id)
        m = named.get(sid)
        if m is not None and m.op in _APPLIED_OPS:
            out.append(one(sid, ADMIT, m.op, m.why))
        elif m is not None and m.op in _HELD_OPS:
            out.append(one(sid, HOLD, m.op, f"no {m.op} applier yet — {m.why}"))
        elif s not in live:
            continue                         # an ended seed nobody named: nothing to decide
        elif nothing:
            out.append(one(sid, REJECT, "none", getattr(result, "lane_reason", None)))
        elif creates:
            out.append(one(sid, ADMIT, "create", creates[0].why))
        elif len(live) == 1:
            out.append(one(sid, ADMIT, "unchanged", getattr(result, "lane_reason", None)))
        else:
            out.append(one(sid, HOLD, "unchanged",
                           "one of several live situations, and the judgment named none of them"))
    return out


_UPSERT = text(
    "insert into l2_admissions (org_id, subject_ref, situation_id, decision, op, reason, result_fingerprint, "
    "  lane, decided_at) values (:o, :s, :sit, :d, :op, :r, :fp, :ln, :at) "
    "on conflict (org_id, subject_ref, situation_id) do update set decision = excluded.decision, "
    "  op = excluded.op, reason = excluded.reason, result_fingerprint = excluded.result_fingerprint, "
    "  lane = excluded.lane, decided_at = excluded.decided_at")


def write_admissions(conn, admissions: Iterable[Admission], *, at: datetime) -> int:
    """The latest decision per (subject, situation), on the caller's transaction. One statement, all rows."""
    params = [a.params(at) for a in admissions]
    if not params:
        return 0
    conn.execute(_UPSERT, params)
    return len(params)


#: L3 rebuild 5a/5b · the version of what an L2 interpretation row holds.
INTERPRETATION_VERSION = "l2-interpretation.v1"


def interpretation_of(admission: Admission, result: Any) -> dict[str, Any] | None:
    """L3 rebuild 5a/5b · what an ADMITTED judgment concluded about its situation, as Layer 3 records it (Atlas
    v2, L3 §: "carried as typed, versioned fields on situation interpretations — append a new interpretation,
    never overwrite"; "L3 records the DecisionObject without reasoning — L4 decides"). Pure. None for anything
    but an admitted judgment of a real situation.

    Holds the conclusions only — the frame and its rivals, the unknowns, the hypotheses, expected against actual,
    the intervention, and the DECISION OBJECT (whether a human must decide, who, what, by when) — never the
    dossier: the result and its dossier are `reasoning_results`', and a second copy is storage the free tier pays."""
    if admission.decision != ADMIT or admission.situation_id == NO_SITUATION or result is None:
        return None
    m = result.as_mapping()
    review, judgment = m.get("review") or {}, m.get("judgment") or {}
    need = judgment.get("decision_need") or {}
    move = review.get("next_move") or {}
    frames = review.get("frames") or {}
    return {
        "version": INTERPRETATION_VERSION, "op": admission.op, "lane": admission.lane,
        "frame": frames.get("primary"), "rivals": list(frames.get("rivals") or ()),
        "unknowns": list(review.get("unknowns") or ()), "hypotheses": list(review.get("hypotheses") or ()),
        "expected_vs_actual": review.get("expected_vs_actual"),
        "intervention_mode": judgment.get("intervention_mode"),
        "decision": {"needed": bool(need.get("needed")), "who": need.get("who"), "what": need.get("what"),
                     "by_when": move.get("by_when") if need.get("needed") else None},
    }


_INTERPRET = text(
    "insert into situation_interpretations (interpretation_id, org_id, situation_id, slice_digest, context_slice, "
    "  proposal, outcome, reason_codes, reasoning_trace) "
    "values (:id, :o, :sit, :fp, cast(:slice as jsonb), cast(:proposal as jsonb), :outcome, '[]'::jsonb, :why) "
    # APPEND-ONLY: one row per (situation, judgment fingerprint) — a judgment of unchanged inputs is the same row.
    "on conflict (org_id, situation_id, slice_digest) do nothing")


def record_interpretations(conn, rows: Iterable[tuple[Admission, Any]]) -> int:
    """Append what each admitted judgment concluded about its situation, on the caller's transaction. Returns rows
    sent. One statement for all."""
    import hashlib
    import json
    params = []
    for adm, result in rows:
        proposal = interpretation_of(adm, result)
        if proposal is None:
            continue
        key = f"{adm.org_id}|{adm.situation_id}|{adm.result_fingerprint}"
        params.append({"id": "sint_l2_" + hashlib.sha256(key.encode()).hexdigest()[:32], "o": adm.org_id,
                       "sit": adm.situation_id, "fp": adm.result_fingerprint,
                       "slice": json.dumps({"subject_ref": adm.subject_ref,
                                            "context_ref": getattr(result, "context_ref", None)}),
                       "proposal": json.dumps(proposal, sort_keys=True, default=str), "outcome": adm.op,
                       "why": (adm.reason or "")[:500] or None})
    if not params:
        return 0
    conn.execute(_INTERPRET, params)
    return len(params)


_ADMITTED = text(
    "select subject_ref, situation_id, op, reason, result_fingerprint, lane, decided_at from l2_admissions "
    " where org_id = :o and decision = 'admit' order by decided_at desc, subject_ref, situation_id limit :n")


def admitted(conn, org_id: str, *, limit: int = 200) -> list[Any]:
    """A tenant's admitted situations, newest decision first — the card path's read (L2 rebuild Phase C)."""
    return list(conn.execute(_ADMITTED, {"o": org_id, "n": max(1, int(limit))}))


__all__ = ["ADMIT", "HOLD", "INTERPRETATION_VERSION", "LIVE", "NO_SITUATION", "REJECT", "Admission", "admitted",
           "decide", "interpretation_of", "record_interpretations", "write_admissions"]
