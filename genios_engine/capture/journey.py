"""L1.6.8's own question, finally answerable about ONE event: *"why did I never see X?"*

`qualification.py` opens on the sentence this module exists to satisfy:

    a system that discards 92% of what a founder was sent has to be able to answer
    "why did I never see X?" in one query

Every layer kept its half of that bargain and wrote its refusal down. Nothing ever joined them.
Measured on the pilot org: `event_trace` holds 10,840 rows and had NO read surface at all — not
an endpoint, not a script — while the two ledgers that DO have endpoints (`qualification_drops`,
`parked_events`) between them hold none of the reasons that actually stopped the mail. Of 138
events one support question was really about, 103 stopped at `s4_esqe short_circuit bulk_headers`
and 33 at `llm5_not_business`; a founder reading `/qualification/drops` would have found nothing
and concluded the events were lost.

`scripts/pipeline_funnel_report.py` answers the OTHER shape of this — "we synced 400 emails, what
happened to them" — per org, in aggregate. This is the per-event half, and the two are kept apart
deliberately: an aggregate cannot answer a support ticket, and a per-event walk cannot tell you a
stage is quietly eating a tenth of the corpus.

**NOTHING HERE DECIDES ANYTHING.** Every field returned was written by the layer that made the
call, at the moment it made it. This module reads five tables, orders them by the clock they each
recorded, and names the last thing that stopped the event. It re-scores nothing — the same reason
`get_qualification_drop` renders `explain_drop` from the stored components rather than from a live
score: a weight change next month must not silently re-explain a decision made under the old one.

**NO PROSE TABLE, AND THAT IS DELIBERATE.** The obvious way to make this friendly is a dict from
`reason_code` to an English sentence. It is not written here. A phrase table is a second place
where a reason's meaning lives, it goes stale the moment a layer adds a code, and it would answer
in English for a tenant whose product is not in English. The reason codes ARE the vocabulary; a
caller that wants prose renders it where prose belongs.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from sqlalchemy import text

from genios_engine.capture.landing.resync import FREED, NOT_LISTED, REPLACED, STAGE as RESYNC

#: The event moved ON. Measured across every `event_trace` row in every org, not assumed: the
#: column holds exactly five values and these two are the ones that mean "and then".
TRACE_ADVANCING = frozenset({"pass", "emit"})

#: The event stopped HERE. The other three, and the reason each carries is the answer this whole
#: module is for. `archive` joined them with STEP-03 (`yc2_w27_s03`): the gate keeps what it used to
#: drop — read by no model — so an archived mail stopped at the gate as surely as a dropped one did,
#: and the walk must not report it as still in flight.
TRACE_STOPPING = frozenset({"drop", "park", "short_circuit", "archive"})

#: MEASUREMENT: `select distinct action from event_trace` returns five values, and the two sets
#: above partition them exactly — six from STEP-03 on, `archive` documented by migration 0192. MOVES WHEN a sixth appears — a new stage verb, a rename — at
#: which point `unclassified_actions` starts returning it and `stopped_by` reports the step as
#: `advancing: null` instead of guessing. A partition that silently classified an unknown verb as
#: "advancing" would report an event as still in flight for the one reason it was actually lost,
#: which is the failure this module was built to end.
UNCLASSIFIED = None

#: Terminal ledgers, in the order the pipeline writes them. Each is (table, time column, org
#: column) and each is read defensively: a table that does not exist in this deployment is a gap
#: in the answer, never a 500 on a support question.
_LEDGERS = (
    ("parked_events", "created_at"),
    ("qualification_drops", "evaluated_at"),
    ("publication_rejections", "evaluated_at"),
    ("qualified_signals", "created_at"),
)

#: Which columns carry a ledger's verdict, since none of them spell it the same way. A table of
#: COLUMN NAMES, not of sentences — the distinction the module docstring is strict about: this
#: goes stale loudly (a missing key reads as `None`) where a phrase table goes stale silently.
_VERDICT_COLUMNS = {
    "parked_events": ("status", "reason_code", ("stage", "refetch_failure_kind")),
    "qualification_drops": (None, None, ("signal_type", "importance_bp", "floor_bp",
                                         "importance_version", "subject_key")),
    "publication_rejections": ("outcome", "reason", ("signal_type", "rules")),
}

#: `qualification_drops` is the one ledger that is per-SIGNAL rather than per-event, and one
#: event can produce up to `detector.MAX_SIGNALS_PER_EVENT` of them. So a drop row answers "why
#: did this signal not travel", never "why did I never see this event" — an event with one
#: dropped signal and one qualified signal WAS seen. Naming the drop as the stop in that case is
#: the single most misleading answer this module could give to the question it exists for.
_PER_SIGNAL_LEDGERS = frozenset({"qualification_drops", "publication_rejections"})


def _jsonable(value: Any) -> Any:
    """Whatever the driver handed back, as something a response can carry."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _rows(conn, sql: str, params: Mapping[str, Any]) -> list[Any]:
    """A missing table is a gap in the answer, not a crash — `pipeline_funnel_report`'s rule,
    for the same reason: this is the surface somebody opens BECAUSE something is already wrong."""
    try:
        return list(conn.execute(text(sql), params))
    except Exception:            # noqa: BLE001 — see the docstring
        return []


def unclassified_actions(engine, *, org_id: str | None = None) -> list[str]:
    """Any `event_trace.action` the two sets above do not name. Empty is the declared state.

    This is the MEASUREMENT half of the declaration on `UNCLASSIFIED`, and it is a function
    rather than a comment so the claim can be tested against a real database instead of trusted.
    """
    where = " where org_id=:o" if org_id else ""
    with engine.connect() as c:
        rows = _rows(c, f"select distinct action from event_trace{where}",
                     {"o": org_id} if org_id else {})
    known = TRACE_ADVANCING | TRACE_STOPPING
    return sorted(str(r[0]) for r in rows if str(r[0]) not in known)


def event_journey(engine, *, org_id: str, event_id: str) -> dict:
    """Every decision any layer recorded about one event, in the order they were recorded.

    `found` is False for an id this org never captured — which is itself an answer to the support
    question, and a different one from "captured and refused". The two were indistinguishable
    before this module existed, and that ambiguity is most of why "why did I never see X?" could
    not be answered: an absence looks identical whether the event was dropped, parked, refused,
    or never arrived at all.
    """
    params = {"o": org_id, "e": event_id}
    with engine.connect() as c:
        events = _rows(c, (
            "select event_id, source, object_type, source_object_id, occurred_at, captured_at, "
            "       outcome, route, triage_lane, internal_kind, attention, attention_reason "
            "  from source_events where org_id=:o and event_id=:e"), params)
        steps = [
            {"at": _jsonable(r.at), "stage": r.stage, "action": r.action,
             "reason_code": r.reason_code, "detail": _jsonable(_loads(r.detail)),
             # Tri-state on purpose: True advanced, False stopped, null means the action is not
             # in either declared set and this module refuses to guess which.
             "advancing": (True if r.action in TRACE_ADVANCING
                           else False if r.action in TRACE_STOPPING else UNCLASSIFIED)}
            for r in _rows(c, (
                "select stage, action, reason_code, detail, at from event_trace "
                " where org_id=:o and event_id=:e order by at, id"), params)]
        ledgers = {
            table: [{k: _jsonable(v) for k, v in row._mapping.items()}
                    for row in _rows(c, f"select * from {table} "
                                        f"where org_id=:o and event_id=:e order by {when}",
                                     params)]
            for table, when in _LEDGERS}
        # STEP-06: the memory run, the one hop past Layer 1 this walk did not read.
        runs = _rows(c, ("select status, attempts, last_error, updated_at from l2_processing_runs "
                         " where org_id=:o and event_id=:e"), params)
        # STEP-08: the deleted row this event replaced, from that row's own re-sync trace.
        replaced = _rows(c, ("select event_id from event_trace where org_id=:o and stage=:stage "
                             "   and reason_code=:code and detail ->> 'replaced_by' = :e "
                             " order by at, id"),
                         {**params, "stage": RESYNC, "code": REPLACED})

    event = ({k: _jsonable(v) for k, v in events[0]._mapping.items()} if events else None)
    memory = ({k: _jsonable(v) for k, v in runs[0]._mapping.items()} if runs else None)
    return {
        "event_id": event_id,
        "found": event is not None,
        "event": event,
        "steps": steps,
        "ledgers": ledgers,
        "reached": steps[-1]["stage"] if steps else None,
        "stopped_by": _stopped_by(steps, ledgers),
        "memory": memory,
        # STEP-06 · exactly one end for the event — see `_end`.
        "end": _end(event, steps, ledgers, memory),
        # STEP-08 · what the re-sync did with it — see `_resync`.
        "resync": _resync(steps, [r.event_id for r in replaced]),
        # Named so a caller can tell "this deployment has no such table" from "this event has no
        # such row" — the distinction a support answer lives or dies on.
        "unclassified_actions": sorted({s["stage"] + ":" + s["action"] for s in steps
                                        if s["advancing"] is UNCLASSIFIED}),
    }


def _loads(value: Any) -> Any:
    """`event_trace.detail` crosses as text in some deployments and jsonb in others."""
    if isinstance(value, (str, bytes)):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def _stopped_by(steps: list[dict], ledgers: Mapping[str, list[dict]]) -> dict | None:
    """The last recorded thing that stopped this event, or `None` if nothing did.

    A floor drop outranks a stopping trace step ONLY by being later, never by being a floor drop:
    the ordering is the clock each layer wrote, so a pipeline that grows a stage between two
    existing ones needs no change here. `qualified_signals` deliberately does not appear — an
    event that qualified was not stopped, and saying so in this field would make "why did I never
    see X?" answer "you did".
    """
    stopping = [s for s in steps if s["advancing"] is False]
    last = {"kind": "trace", "at": stopping[-1]["at"], "stage": stopping[-1]["stage"],
            "action": stopping[-1]["action"], "reason_code": stopping[-1]["reason_code"],
            "detail": {}} if stopping else None
    # An event that produced even one qualified signal was not stopped by a ledger that refuses
    # signals one at a time. See `_PER_SIGNAL_LEDGERS`.
    travelled = bool(ledgers.get("qualified_signals"))
    for table, (act_col, reason_col, detail_cols) in _VERDICT_COLUMNS.items():
        if travelled and table in _PER_SIGNAL_LEDGERS:
            continue
        for row in ledgers.get(table, ()):
            at = row.get("created_at") or row.get("evaluated_at")
            if at is None:
                continue
            if last is None or str(at) > str(last["at"]):
                last = {"kind": table, "at": at, "stage": row.get("stage"),
                        "action": row.get(act_col) if act_col else None,
                        "reason_code": row.get(reason_col) if reason_col else None,
                        # The numbers the layer stored. `qualification_drops` carries no reason
                        # column at all because its reason IS the comparison, and returning two
                        # nulls where `importance_bp` and `floor_bp` live would make the one
                        # ledger with a complete explanation look like the one with none.
                        "detail": {k: row.get(k) for k in detail_cols if k in row}}
    return last


def _resync(steps: list[dict], replaced: list[str]) -> dict | None:
    """STEP-08 · the re-sync, in both directions (`capture/landing/resync`). A deleted row it freed says
    so, and then either names the event that replaced it or why its mail did not come back; the event
    that replaced one names it. None for every event the re-sync never touched. Read from the trace each
    side wrote — the old row's own steps, and the old row's trace naming this event."""
    out: dict = {}
    for s in steps:
        detail = s["detail"] if isinstance(s["detail"], dict) else {}
        if s["reason_code"] == FREED:
            out["freed"] = s["at"]
        elif s["reason_code"] == REPLACED:
            out["replaced_by"] = detail.get("replaced_by")
        elif s["reason_code"] == NOT_LISTED:
            out["not_listed"] = detail
    if replaced:
        out["replaces"] = replaced[-1]
    return out or None


#: Every end an event can have — exactly one each (STEP-06, `yc2_w27_s06 · M24.C3.L-logic.V1.U01`).
ENDS = ("not_captured", "superseded", "in_memory", "failed", "parked", "waiting", "archived",
        "stopped", "none")

#: A kept mail is owed memory (`context/memory_lanes.KEPT_OUTCOMES`, spelled here because capture
#: may not import context — `LAYERS.py`); a screen archive is the one kept item with no road (`06` D22).
_KEPT = ("emitted", "archived")
_SCREEN = "screen_session"


def _end(event: Mapping[str, Any] | None, steps: list[dict], ledgers: Mapping[str, list[dict]],
         memory: Mapping[str, Any] | None) -> dict:
    """The one end of one event, from what each layer recorded — never re-derived.

    ⛔ THE ORDER IS THE ANSWER'S. A run that finished is the end whatever stopped the event before it
    (an archive, a re-read); a failed run comes next; then the park queue; then a kept mail still owed
    memory — waiting for the drain, or for its re-read when a pending park says so; then what stopped
    it. `none` is the population nothing explains, and it must stay empty.
    """
    if event is None:
        return {"end": "not_captured"}
    outcome = event.get("outcome")
    if outcome == "superseded":
        # STEP-08: a deleted mail the re-sync brought back names the event that replaced it.
        by = [s["detail"].get("replaced_by") for s in steps
              if s["reason_code"] == REPLACED and isinstance(s["detail"], dict)]
        return {"end": "superseded", **({"replaced_by": by[-1]} if by and by[-1] else {})}
    if memory and memory.get("status") == "done":
        return {"end": "in_memory", "attention": event.get("attention"),
                "attempts": memory.get("attempts")}
    if memory and memory.get("status") in ("failed", "parked"):
        return {"end": "failed", "status": memory.get("status"),
                "error": memory.get("last_error"), "attempts": memory.get("attempts")}
    parks = list(ledgers.get("parked_events") or ())
    pending = [p for p in parks if p.get("status") == "pending"]
    if outcome == "parked" and parks:
        park = (pending or parks)[-1]
        return {"end": "parked", "reason_code": park.get("reason_code"),
                "status": park.get("status"),
                "next_attempt_at": park.get("refetch_next_attempt_at")}
    if outcome in _KEPT:
        if pending:
            return {"end": "waiting", "for": "re-read", "reason_code": pending[-1].get("reason_code")}
        if memory and memory.get("status") == "held":
            return {"end": "waiting", "for": "memory", "held": memory.get("last_error")}
        if outcome == "archived" and event.get("source") == _SCREEN:
            return {"end": "archived", "reason": event.get("attention_reason")}
        return {"end": "waiting", "for": "the drain", "attention": event.get("attention")}
    stop = _stopped_by(steps, ledgers)
    if stop is not None:
        return {"end": "stopped", "stage": stop.get("stage"), "action": stop.get("action"),
                "reason_code": stop.get("reason_code")}
    return {"end": "none"}


__all__ = ["ENDS", "TRACE_ADVANCING", "TRACE_STOPPING", "event_journey", "unclassified_actions"]
