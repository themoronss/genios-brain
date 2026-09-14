"""L2 · the ANGLE EVALUATOR — the half that decides NOT to spend a call.

`angles/contract.py` says what may be asked. This says when, how often, and at what cost, and
almost everything it does is a refusal. `lifecycle/gate.py` describes the same shape one module
over: *"Everything this module does is decide NOT to spend a call, and it is written as a cascade
of named refusals rather than one boolean because 'the sweep made 4000 calls' and 'the sweep made
none' are both answerable only if the reason each situation was skipped is a value."*

THE FIVE LAWS, ENFORCED HERE RATHER THAN DESCRIBED. Each is lifted from
`reason/llm_interpretation.py`, which already does this correctly at Layer 4:

1. **A GATE MISS NEVER PAYS.** The gate is a query. Subjects that do not satisfy it are never
   counted, never summarised and never reach a prompt, so the common case — a tenant with an
   empty queue — costs one SELECT and nothing else.

2. **AN UNCHANGED SLICE IS NEVER RE-ASKED.** `saw_hash` digests the exact field values the model
   was shown. A subject whose slice has not moved is skipped at any price, on any sweep, for
   ever. This is what makes an angle's steady-state cost the rate at which its queue CHANGES
   rather than the size of the queue.

3. **THE ONE-HOP LAW.** A subject is never asked about on evidence an angle itself produced.
   Enforced by construction rather than by a filter: `sees` names `graph_facts` fields and a
   verdict is written to `context_angle_verdicts`, which is a different table that no gate and no
   slice reads. A model cannot reach its own output without someone editing `GateSource`.

4. **CLOSED ENUM, BANDED CONFIDENCE.** Both belong to the contract and `AngleVerdict.of` refuses
   anything outside them, so this module never has to check and cannot forget to.

5. **THE MODEL IS INJECTED, NEVER CONSTRUCTED.** `analytic/cohort.llm_predicate_drafter` gives the
   reason and it is the one that matters most: *"a test drives the same code path with a stub
   drafter and no network, and the sweep path cannot reach a model even by accident because it
   never receives one."* `asker=None` is not an error here — it is the default, and it means this
   pass costs exactly one query per angle.

WHAT A FAILURE COSTS. One cycle of an opinion nobody had before, and never an event. Every
exception inside the per-subject loop is contained to that subject, and the pass itself is never
fatal — an angle is an addition to what the deterministic layer produced, so its absence can only
ever return the tenant to the state it was in before any of this existed.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from sqlalchemy import text

from genios_engine.context.angles.contract import Angle, AngleVerdict, GateSource, registered

#: What an asker is handed and what it must return. A mapping of the angle's `sees` names to the
#: subject's values, and one `(verdict, confidence_bp)` back. Deliberately not a model client:
#: this module never learns a model's name, and a test's stub satisfies the same signature.
Asker = Callable[[Angle, str, Mapping[str, Any]], tuple[str, int]]

#: The audit site name every angle files under, so one query answers "what did the angle layer
#: cost this tenant" without knowing which angles exist.
AUDIT_SITE = "l2_angle"


@dataclass(frozen=True, slots=True)
class AngleRun:
    """What one angle did for one tenant on one sweep, including everything it declined to do."""

    angle_id: str
    gated: int = 0          # subjects the gate admitted
    unchanged: int = 0      # skipped — slice identical to the last verdict
    asked: int = 0          # calls actually made
    refused: int = 0        # asked, and the model said it could not tell
    failed: int = 0         # asked, and the call or the answer was unusable
    retired: int = 0        # verdicts deleted because the subject left the gate
    budget_exhausted: bool = False
    #: No asker was supplied, so nothing was asked and that is not a failure. Reported because a
    #: pass that made no calls because it COULD not must not read as a pass with nothing to do.
    no_asker: bool = False

    def as_record(self) -> dict:
        return {"angle_id": self.angle_id, "gated": self.gated, "unchanged": self.unchanged,
                "asked": self.asked, "refused": self.refused, "failed": self.failed,
                "retired": self.retired, "budget_exhausted": self.budget_exhausted,
                "no_asker": self.no_asker}


@dataclass(frozen=True, slots=True)
class AngleReport:
    runs: tuple[AngleRun, ...] = ()

    @property
    def asked(self) -> int:
        return sum(run.asked for run in self.runs)

    def as_record(self) -> dict:
        return {"asked": self.asked, "runs": [run.as_record() for run in self.runs]}


def _digest(seen: Mapping[str, Any]) -> str:
    """The content address of one slice. Sorted keys and a stable dump, so the same values in a
    different dict order are the same slice — otherwise law 2 would be defeated by an iteration
    order nobody controls."""
    return hashlib.sha256(
        json.dumps({k: seen[k] for k in sorted(seen)}, default=str, sort_keys=True).encode()
    ).hexdigest()[:32]


# ── the gate: one query per angle, and nothing beyond it is ever looked at ────────────────────

_FACTS_GATE = (
    "select f.subject_node_id as ref, f.field as name, f.value as value "
    "from graph_facts f "
    "where f.org_id = :o and f.field in :fields "
    "  and f.status = 'active' and f.valid_to is null"
)

_RESIDUE_GATE = (
    "select r.subject_ref as ref, r.residue_kind as name, r.detail as value "
    "from context_residue r "
    "where r.org_id = :o and r.residue_kind in :fields"
)


def _slices(conn, org_id: str, angle: Angle) -> dict[str, dict[str, Any]]:
    """`{subject_ref: {gate field: value}}` for every subject the gate admits.

    A subject must carry EVERY name in the gate, not any of them. An angle declaring two
    preconditions and firing on one is not a narrower angle — it is a looser one that still reads
    correctly in review, which is the failure `patterns/contract.py` calls "the single most
    important refusal in the file" in its own domain.
    """
    from sqlalchemy import bindparam

    sql = _FACTS_GATE if angle.gate_source is GateSource.FACTS else _RESIDUE_GATE
    statement = text(sql).bindparams(bindparam("fields", expanding=True))
    held: dict[str, dict[str, Any]] = {}
    for row in conn.execute(statement, {"o": org_id, "fields": list(angle.gate)}):
        held.setdefault(str(row.ref), {})[str(row.name)] = row.value
    return {ref: values for ref, values in held.items() if len(values) == len(angle.gate)}


def _seen(conn, org_id: str, angle: Angle, subject_ref: str,
          gate_values: Mapping[str, Any]) -> dict[str, Any]:
    """Exactly the fields `sees` names, and nothing else.

    A field the prompt would like and the declaration does not name is not fetched, so the
    reviewer's one-line answer to "what leaves the tenant" stays true no matter what a caller
    later wants. Gate values are reused rather than re-read: they are already in hand and a second
    read could disagree with the first inside one sweep.
    """
    from sqlalchemy import bindparam

    wanted = [name for name in angle.sees if name not in gate_values]
    seen: dict[str, Any] = {name: gate_values[name] for name in angle.sees if name in gate_values}
    if wanted:
        statement = text(
            "select field as name, value as value from graph_facts "
            "where org_id = :o and subject_node_id = :s and field in :fields "
            "  and status = 'active' and valid_to is null"
        ).bindparams(bindparam("fields", expanding=True))
        for row in conn.execute(statement, {"o": org_id, "s": subject_ref, "fields": wanted}):
            seen[str(row.name)] = row.value
    return seen


_HELD = ("select subject_ref, saw_hash from context_angle_verdicts "
         "where org_id = :o and angle_id = :a and angle_version = :v")

_WRITE = (
    "insert into context_angle_verdicts (org_id, angle_id, angle_version, subject_ref, verdict, "
    "  confidence_bp, refused, saw_hash, model_run_id, first_seen_at, last_seen_at) "
    "values (:o, :a, :v, :s, :verdict, :conf, :refused, :hash, :run, :now, :now) "
    "on conflict (org_id, angle_id, subject_ref) do update set "
    "  angle_version = excluded.angle_version, verdict = excluded.verdict, "
    "  confidence_bp = excluded.confidence_bp, refused = excluded.refused, "
    "  saw_hash = excluded.saw_hash, model_run_id = excluded.model_run_id, "
    # `first_seen_at` is never updated: how long an angle has been saying this is the number that
    # makes a verdict reviewable rather than a snapshot.
    "  last_seen_at = excluded.last_seen_at"
)


def evaluate_angle(store, org_id: str, angle: Angle, *, eval_time: datetime | None = None,
                   asker: Asker | None = None) -> AngleRun:
    """Ask one angle about one tenant, and mostly decline to.

    `eval_time` is a parameter all the way down; the clock is read at the call site, so two runs
    at one instant produce identical rows and the second is an overwrite rather than a second
    opinion.
    """
    now = eval_time or datetime.now(timezone.utc)
    gated = unchanged = asked = refused = failed = retired = 0
    exhausted = False

    with store.engine.begin() as conn:
        slices = _slices(conn, org_id, angle)
        gated = len(slices)

        held = {str(row.subject_ref): str(row.saw_hash)
                for row in conn.execute(text(_HELD),
                                        {"o": org_id, "a": angle.angle_id, "v": angle.version})}

        # A SUBJECT THAT LEFT THE GATE HAS NO VERDICT. The queue emptied because the
        # deterministic layer resolved it — a condition was parsed, a residue row was explained —
        # and an opinion about a question nobody is asking any more is worse than no opinion.
        departed = sorted(set(held) - set(slices))
        if departed:
            from sqlalchemy import bindparam
            retired = int(conn.execute(text(
                "delete from context_angle_verdicts where org_id = :o and angle_id = :a "
                "and subject_ref in :refs"
            ).bindparams(bindparam("refs", expanding=True)),
                {"o": org_id, "a": angle.angle_id, "refs": departed}).rowcount or 0)

        if asker is None:
            # NOT A FAILURE, AND THE DEFAULT. The sweep does not construct a model client, so this
            # pass costs one query per angle unless a caller deliberately supplies one.
            return AngleRun(angle_id=angle.angle_id, gated=gated, retired=retired, no_asker=True)

        for subject_ref in sorted(slices):
            if asked >= angle.max_per_sweep:
                exhausted = True
                break
            seen = _seen(conn, org_id, angle, subject_ref, slices[subject_ref])
            saw_hash = _digest(seen)
            if held.get(subject_ref) == saw_hash:
                unchanged += 1
                continue
            try:
                word, confidence_bp = asker(angle, subject_ref, seen)
                verdict = AngleVerdict.of(angle, subject_ref=subject_ref, verdict=word,
                                          confidence_bp=confidence_bp,
                                          model_run_id=_record(store, org_id, angle, subject_ref,
                                                               seen, word, now))
            except Exception:      # noqa: BLE001 — one subject's failure is not the sweep's
                failed += 1
                continue
            asked += 1
            refused += int(verdict.refused)
            conn.execute(text(_WRITE), {
                "o": org_id, "a": verdict.angle_id, "v": verdict.angle_version,
                "s": verdict.subject_ref, "verdict": verdict.verdict,
                "conf": verdict.confidence_bp, "refused": verdict.refused,
                "hash": saw_hash, "run": verdict.model_run_id, "now": now})

    return AngleRun(angle_id=angle.angle_id, gated=gated, unchanged=unchanged, asked=asked,
                    refused=refused, failed=failed, retired=retired, budget_exhausted=exhausted)


def _record(store, org_id: str, angle: Angle, subject_ref: str, seen: Mapping[str, Any],
            word: str, now: datetime) -> str | None:
    """File the durable audit envelope, and never let filing it cost the verdict.

    `model_audit` stores "the prompt hash and the complete returned artifact, not the prompt
    itself" — source text stays in its governed store — which is what lets a replay prove which
    bytes were used. A failure to WRITE that receipt is a lost audit row, not a reason to discard
    an answer the tenant has already paid for.
    """
    try:
        from genios_engine.context.model_audit import record_model_run

        return record_model_run(
            store.engine, org_id=org_id, site=AUDIT_SITE,
            subject_ref=f"{angle.angle_id}:{subject_ref}",
            prompt_version=f"{angle.angle_id}.v{angle.version}",
            prompt=json.dumps({k: seen[k] for k in sorted(seen)}, default=str, sort_keys=True),
            result=word, called_at=now, max_tokens=0)
    except Exception:      # noqa: BLE001 — an audit row must never cost a verdict
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception("angle audit write failed org=%s angle=%s",
                                          org_id, angle.angle_id)
        return None


def evaluate_org(store, org_id: str, *, eval_time: datetime | None = None,
                 asker: Asker | None = None) -> AngleReport:
    """Every registered angle, each contained to itself.

    ONE ANGLE'S FAILURE IS NOT THE OTHERS'. The same boundary every pass in `runner.py` carries,
    and for the reason that file records: a single bad pass once skipped the six behind it while
    the sweep still reported a clean run.
    """
    runs: list[AngleRun] = []
    for angle in registered():
        try:
            runs.append(evaluate_angle(store, org_id, angle, eval_time=eval_time, asker=asker))
        except Exception:      # noqa: BLE001 — an angle is an addition; its loss returns the
            # tenant to the state it was in before any of this existed
            from genios_engine.platform.logging import get_logger
            get_logger("genios.l2").exception("angle %s failed for org=%s",
                                              angle.angle_id, org_id)
            runs.append(AngleRun(angle_id=angle.angle_id, failed=1))
    return AngleReport(runs=tuple(runs))


def read_verdicts(conn, org_id: str, *, angle_id: str | None = None,
                  limit: int = 100) -> list[dict]:
    """What the angle layer currently believes, longest-held first."""
    sql = ("select angle_id, angle_version, subject_ref, verdict, confidence_bp, refused, "
           "       model_run_id, first_seen_at, last_seen_at "
           "from context_angle_verdicts where org_id = :o "
           + ("" if angle_id is None else "and angle_id = :a ")
           + "order by first_seen_at asc limit :lim")
    params: dict = {"o": org_id, "lim": limit}
    if angle_id is not None:
        params["a"] = angle_id
    return [dict(r) for r in conn.execute(text(sql), params).mappings().all()]


__all__ = ["AUDIT_SITE", "AngleReport", "AngleRun", "Asker", "evaluate_angle", "evaluate_org",
           "read_verdicts"]
