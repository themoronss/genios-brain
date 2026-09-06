"""L2.6 · the pattern surface — evaluate, read the fire rates, and turn a pattern on.

WHY THE REGISTRY GETS A ROUTE AT ALL, AND NOT ONLY A DRAIN. Two of the four things this package
owes need a human on the other end of the request:

  * **activation is a decision.** Doc 06's guard blocks a pattern that fires on everything, and
    doc 09 puts activation *"per tenant, in a table"*. Somebody has to ask, and the refusal has to
    reach them with the rate in it rather than into a log line nobody opens.
  * **the fire report is an operator surface.** `scripts/pattern_fire_report.py` prints it for a
    terminal; this returns the same numbers as JSON for the console.

`POST .../patterns/evaluate` is also the real path that reaches the evaluator, the candidate
builder, the scorer and both framing sites in one request. Layer 1 shipped six units that were
green and called by nothing; a route that a test drives end to end is what stops this package
being the seventh. The drain call — one line in `context/runner.process_pending` — belongs to the
wave that switches situations over, and is deliberately not made here: doc 06 says the anchor path
keeps running for seven days first.

THE CLOCK IS READ HERE, at the process boundary, and passed down. Every function below this file
takes `eval_time` as a parameter, which is what makes a fire report replayable and a match
diffable across runs.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from genios_engine.context.framing.headline import (Asker, FramingFact, FramingInput, frame)
from genios_engine.context.framing.timeline import TimelineEvent, narrate
from genios_engine.context.patterns.candidate import SituationCandidate
from genios_engine.context.patterns.registry import (breaching_patterns, seed_registry,
                                                     silent_patterns)
from genios_engine.context.patterns.scorer import score_candidate
from genios_engine.context.patterns.store import (activate, activation_state, deactivate,
                                                  evaluate_org, fire_observations, utc_now)
from genios_engine.platform.auth import AuthCtx, get_auth_ctx, get_current_org
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()

#: How far back the default fire window looks. 30 days, because that is the window every declared
#: `expected_fire_rate` is stated in and comparing a 7-day count against a 30-day rate is how a
#: healthy pattern gets reported as silent.
DEFAULT_WINDOW_DAYS = 30


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


def _store():
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    return _graph


def framing_asker() -> Asker | None:
    """The M-6 / M-7 model, or `None` for the deterministic path.

    `None` in this wave, deliberately. Both framing sites are span-constrained and fall back to a
    deterministic template, so the route exercises the real code path either way; wiring a live
    model is a per-tenant activation decision with a budget attached, and doc 12's own rule is that
    every site degrades toward doing less. A test overrides this function to drive the model
    branch, which is how both halves of the site are proven from a real request.
    """
    return None


class ActivateIn(BaseModel):
    #: Optional override so an operator can ask "would it activate as at this instant?" against a
    #: window they name. Absent means now.
    as_of: datetime | None = None


def _instant(value: datetime | None) -> datetime:
    if value is None:
        return utc_now()
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _framing_for(candidate: SituationCandidate, *, eval_time: datetime,
                 viewer_email: str | None) -> dict[str, Any]:
    """M-6 and M-7 over one candidate — built from the MATCH's own evidence, nothing else.

    Every `FramingFact` here comes from a `ConditionEvidence` the evaluator produced, so a framing
    can only ever describe a condition that actually held. The visibility filter runs inside
    `FramingInput.for_viewer`, before any prompt exists.
    """
    facts: list[FramingFact] = []
    events: list[TimelineEvent] = []
    for evidence in candidate.per_condition_evidence:
        record = dict(evidence.record)
        facts.append(FramingFact(
            fact_id=evidence.ref, field_path=evidence.field_path,
            label=str(record.get("subject_node_id") or candidate.anchor_node_id),
            value=evidence.observed if isinstance(evidence.observed, (str, int)) else "",
            spans=evidence.spans))
        when = record.get("dated_value") or record.get("occurred_at")
        if isinstance(when, str):
            try:
                events.append(TimelineEvent(
                    event_id=evidence.ref, occurred_at=datetime.fromisoformat(when),
                    label=evidence.field_path, spans=evidence.spans))
            except ValueError:
                pass
    inp = FramingInput.for_viewer(
        candidate.provisional_type, facts,
        matched_conditions=[e.field_path for e in candidate.per_condition_evidence],
        # The subject is the ANCHOR, stated rather than guessed from whichever fact sorts first —
        # a renewal card whose subject reads "days left" is what happens otherwise.
        subject_label=candidate.anchor_node_id, viewer_email=viewer_email)
    framing = frame(inp, ask=framing_asker(), eval_time=eval_time)
    narrative = narrate(events, situation_type=candidate.provisional_type, eval_time=eval_time,
                        anchor_event_ids=[e.event_id for e in events[:1]],
                        ask=framing_asker(), viewer_email=viewer_email)
    return {"framing": framing.as_record(), "timeline": narrative.as_record()}


@router.post("/api/org/{org_id}/patterns/evaluate")
def evaluate_patterns(org_id: str, as_of: datetime | None = None,
                      org: str = Depends(_org), ctx: AuthCtx = Depends(get_auth_ctx)) -> dict:
    """Run every registered pattern over this tenant and record what happened.

    SHADOW BY DEFAULT. A fire is logged with `activated=false` unless the pattern has been
    activated for this tenant through the guard, and nothing here writes `context_situations` —
    anchor-based detection is untouched and both paths can be compared for the seven days doc 06
    asks for before anything switches over.
    """
    eval_time = _instant(as_of)
    report = evaluate_org(_store(), org, eval_time=eval_time)
    viewer = (ctx.actor_id or "").strip().lower() or None
    candidates = []
    for run in report.runs:
        for candidate in run.candidates:
            score = score_candidate(candidate)
            candidates.append({**candidate.as_record(), "score": score.as_record(),
                               **_framing_for(candidate, eval_time=eval_time,
                                              viewer_email=viewer)})
    return {"org_id": org, "eval_time": eval_time.isoformat(),
            "runs": [r.as_record() for r in report.runs],
            "candidates": candidates,
            "note": "shadow — pattern matches are logged and reach no card until the pattern is "
                    "activated for this tenant"}


@router.get("/api/org/{org_id}/patterns")
def list_patterns(org_id: str, since_days: int = DEFAULT_WINDOW_DAYS,
                  as_of: datetime | None = None, org: str = Depends(_org)) -> dict:
    """Every registered pattern, what it did here, and whether it may activate.

    BOTH FAILURES ARE ON THIS PAGE, which is the point of the surface: `silent` names the patterns
    that fired zero times in the window, `breaching` names the ones that fired more than ten times
    their declared rate. A page that showed only one of them would make the other one worse.
    """
    eval_time = _instant(as_of)
    since = eval_time - timedelta(days=max(1, int(since_days)))
    registry = seed_registry()
    with _store().engine.connect() as conn:
        observations = fire_observations(conn, org, since=since, until=eval_time)
        active = activation_state(conn, org)
    by_id = {o.pattern_id: o for o in observations}
    return {
        "org_id": org, "as_of": eval_time.isoformat(), "window_days": int(since_days),
        "patterns": [{
            **pattern.as_record(),
            "activated": bool(active.get(pattern.pattern_id)),
            "fires": by_id[pattern.pattern_id].fires if pattern.pattern_id in by_id else 0,
            "anchors": by_id[pattern.pattern_id].anchors if pattern.pattern_id in by_id else 0,
        } for pattern in registry.all()],
        "silent": list(silent_patterns(registry, observations)),
        "breaching": [d.as_record() for d in breaching_patterns(registry, observations)],
        "registered": len(registry)}


@router.post("/api/org/{org_id}/patterns/{pattern_id}/activate")
def activate_pattern(org_id: str, pattern_id: str, body: ActivateIn | None = None,
                     org: str = Depends(_org), ctx: AuthCtx = Depends(get_auth_ctx)) -> dict:
    """Turn a pattern on for this tenant — if its measured fire rate allows it.

    `activated_by` comes from the AUTHENTICATED PRINCIPAL and never from the body: "who turned
    this on" is the field an operator appeals to when a pattern floods a queue, and a
    caller-supplied name puts it beyond anybody's reach. A refusal is a 409 with the rate in it,
    not a 400: the request was well formed and the answer is no.
    """
    actor = (ctx.actor_id or "").strip()
    if not actor:
        raise HTTPException(403, "activating a pattern needs a signed-in person: this credential "
                                 "names none")
    eval_time = _instant(body.as_of if body else None)
    try:
        decision = activate(_store(), org, pattern_id, activated_by=actor, eval_time=eval_time)
    except KeyError:
        raise HTTPException(404, f"no registered pattern {pattern_id!r}") from None
    if not decision.allowed:
        raise HTTPException(409, {"activated": False, **decision.as_record()})
    return {"activated": True, **decision.as_record()}


@router.post("/api/org/{org_id}/patterns/{pattern_id}/deactivate")
def deactivate_pattern(org_id: str, pattern_id: str, body: ActivateIn | None = None,
                       org: str = Depends(_org)) -> dict:
    """Back to shadow. A pattern that could not be turned off is a pattern nobody dares turn on."""
    eval_time = _instant(body.as_of if body else None)
    changed = deactivate(_store(), org, pattern_id, eval_time=eval_time)
    return {"pattern_id": pattern_id, "activated": False, "changed": changed}


__all__ = ["DEFAULT_WINDOW_DAYS", "framing_asker", "router"]
