"""The parked-queue drain — a park is a decision to look again, not a slower delete.

A queue nobody empties is a black hole with better paperwork. This org accumulated 347 parked
events, every one of them ``status='pending'`` since the day it landed, and the only consumer in
the entire engine was a manual ``POST /parked/{event_id}/recover`` that requires a human to
already know the event id. ``DOC-05``'s own comment in ``gate/rules.py`` says *"retryable, never
silent"* and nothing ever retried it.

It also covers JUDGED DROPS. A drop the model made on judgment is exactly as re-adjudicable as
a park — the difference was never in the evidence, only in how confident the gate happened to
be — and 657 dropped events with no retained payload made "did we lose anything real?"
permanently unanswerable. Deterministic drops (a provider SPAM label) stay out: those are facts,
not opinions, and L1 is a filter rather than a warehouse.

Two classes of park, and the honest thing is to treat them differently:

  RE-ADJUDICABLE  the payload we kept is enough to decide again, because what changed is our
                  JUDGMENT — a relevance threshold, a newly-registered structured mapping, a
                  gate that got better. Re-entering the pipeline can genuinely flip these.

  NEEDS REFETCH   the payload we kept is an attachment STUB (``_attachment_stub`` hardcodes
                  ``body: ""``), so the bytes never existed locally. Re-running the pipeline on
                  a stub re-parks it forever and reports progress. These need the connector to
                  fetch again, which is a sync concern, not a drain concern.

The second class is the majority here, and pretending otherwise would be the same silence in a
different costume. So the drain re-adjudicates what it can and REPORTS the rest with its age,
which is what turns an invisible backlog into an operable one.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.capture.parked.drain")

#: Parks whose verdict can change from the retained payload alone.
RE_ADJUDICABLE: frozenset[str] = frozenset({
    "llm_junk_unconfident",   # the gate was not confident; a better gate may keep it
    "llm_junk",               # a confident model verdict is still a model verdict
    "low_relevance",          # threshold or classifier moved
    "mapping_missing",        # a structured mapping may have been registered since
})

#: Parks that need the source fetched again — the stored payload cannot answer them.
#:
#: EVERY park code the gate can emit must appear here, in `RE_ADJUDICABLE`, or in
#: `recapture.NEEDS_RECAPTURE`, and `tests/capture/parked/test_park_code_coverage.py` enumerates
#: the park SITES out of `capture/gate/` to prove it — driving `content_integrity_rule` with every
#: `DocumentStatus` was not enough, because that rule has a branch (``MUT-01``) no status reaches
#: and `gate/gate.py` parks under two codes of its own.
#: A code in NO set is worse than an unhandled one:
#: `drain_parked` counts it into `by_reason` and then walks past it, `parked_aging` labels it
#: ``"terminal"`` — a claim nobody made — the refetch claim's ``reason_code = any(:reasons)``
#: never selects it, and `read_aging`, which IS the G2 metric in `scripts/l1_s1_report.py`,
#: filters on this same set. So the documents sit at ``status='pending'`` forever while every
#: surface that could show them reads clean. That is what happened to DOC-07/08/09 below: they
#: were added to the gate and never to a drain.
NEEDS_REFETCH: frozenset[str] = frozenset({
    "DOC-02",                 # unsupported binary; only OCR/native support changes this
    "DOC-04",                 # OCR ran but scored too low to trust
    "DOC-05",                 # the attachment download itself failed
    "DOC-06",                 # readable in principle, no OCR engine was wired
    # The three that were orphaned. All describe bytes we could not turn into text, so the
    # retained payload is the same empty stub `_attachment_stub` writes and re-adjudicating it
    # would re-park it — the definition of this class, not of the other one.
    "DOC-07",                 # an engine ran and read nothing: a corrupt download, a noisy scan
    "DOC-08",                 # audio arrived and no speech engine is wired anywhere yet
    "DOC-09",                 # a speech engine ran and produced no usable transcript
})

#: How old a pending park has to be before it is worth an operator's attention.
STALE_AFTER = timedelta(days=3)


def drain_parked(engine, *, org_id: str | None = None, limit: int = 200,
                 now: datetime | None = None) -> dict:
    """Re-adjudicate what can be re-adjudicated; age-report the rest.

    Re-injection mirrors ``recover_parked``: flip ``source_events.outcome`` back to ``emitted``
    so the next L2 pass picks the event up using the payload we retained, and mark the park
    ``recovered``. It is deliberately the same mechanism a human promotion uses — one recovery
    path, not two that can drift apart.
    """
    from genios_engine.capture.parked.recapture import NEEDS_RECAPTURE   # see `parked_aging`

    now = now or datetime.now(timezone.utc)
    out = {"examined": 0, "reinjected": 0, "blocked_no_payload": 0,
           "needs_refetch": 0, "needs_recapture": 0, "stale": 0, "by_reason": {}}

    where_org = " and pe.org_id=:o" if org_id else ""
    params: dict = {"lim": limit}
    if org_id:
        params["o"] = org_id

    with engine.begin() as c:
        # Parked events AND judged drops. A drop the model made on judgment is exactly as
        # re-adjudicable as a park — the difference was never in the evidence, only in how
        # confident the gate happened to be — and treating drops as out of scope is what made a
        # "we improved the filter" claim unverifiable against the mail it had already deleted.
        rows = c.execute(text(
            "select pe.event_id, pe.org_id, pe.reason_code, pe.created_at, "
            "       (rp.event_id is not null) as has_payload "
            "from parked_events pe "
            "left join raw_payloads rp on rp.event_id = pe.event_id "
            f"where pe.status='pending'{where_org} "
            "union all "
            "select se.event_id, se.org_id, et.reason_code, se.captured_at, true "
            "from source_events se "
            "join raw_payloads rp on rp.event_id = se.event_id "
            "join event_trace et on et.event_id = se.event_id and et.action = 'drop' "
            f"where se.outcome='dropped' and et.reason_code = any(:judged)"
            + (" and se.org_id=:o" if org_id else "") +
            " order by 4 asc limit :lim"),
            {**params, "judged": sorted(RE_ADJUDICABLE)}).fetchall()

        for r in rows:
            out["examined"] += 1
            bucket = out["by_reason"].setdefault(r.reason_code, {"seen": 0, "reinjected": 0})
            bucket["seen"] += 1

            if r.created_at is not None and (now - r.created_at) > STALE_AFTER:
                out["stale"] += 1

            if r.reason_code in NEEDS_REFETCH:
                # Honest accounting: the retained payload is a stub, so re-entering the pipeline
                # would re-park it and report work that did not happen.
                out["needs_refetch"] += 1
                continue

            if r.reason_code in NEEDS_RECAPTURE:
                # Owned by `recapture.drain_recapture`, which re-derives an audience or settles
                # a superseded version stamp. Counted here rather than walked past, so a reader
                # of THIS report can see the whole queue rather than the part this drain owns.
                out["needs_recapture"] += 1
                continue

            if r.reason_code not in RE_ADJUDICABLE:
                continue

            if not r.has_payload:
                # Nothing to re-read. Say so rather than leaving it pending forever.
                out["blocked_no_payload"] += 1
                c.execute(text("update parked_events set status='dropped' where event_id=:e"),
                          {"e": r.event_id})
                continue

            flipped = c.execute(text(
                "update source_events set outcome='emitted' "
                "where org_id=:o and event_id=:e and outcome in ('parked', 'dropped')"),
                {"o": r.org_id, "e": r.event_id}).rowcount
            if flipped:
                # Only a real parked row has a status to update; a re-admitted drop has none,
                # and inventing one would put a row in the park queue that was never parked.
                c.execute(text("update parked_events set status='recovered' where event_id=:e"),
                          {"e": r.event_id})
                out["reinjected"] += 1
                bucket["reinjected"] += 1

    if out["examined"]:
        _log.info("parked drain: examined=%d reinjected=%d needs_refetch=%d "
                  "needs_recapture=%d stale=%d",
                  out["examined"], out["reinjected"], out["needs_refetch"],
                  out["needs_recapture"], out["stale"])
    return out


def parked_aging(engine, *, org_id: str | None = None, now: datetime | None = None) -> list[dict]:
    """Per-reason backlog with its oldest entry — the surface an operator can alarm on.

    ``status='pending'`` on its own tells you nothing about whether the queue is moving, and
    ``status='dead_letter'`` on its own tells you nothing about whether it should have. So the
    grouping carries ``refetch_failure_kind`` (`refetch_policy.AttemptFailure`, written by every
    settlement the attachment resolver makes) alongside the status: `transient` means a ladder ran
    out and the connection is worth a look, `permanent` means the provider says the bytes are
    gone, `capability` means we hold bytes nothing here can read and a requeue is worth running
    the day an engine lands. Three different actions behind one word, and the column is the only
    thing that separates them — a truncated error message is not an answer.

    Null for every row this component never touched, which groups exactly as it did before.
    """
    # Imported inside the function, not at module scope: `recapture.py` reads `STALE_AFTER`
    # from here, so a top-level import would close the cycle. The set lives THERE because that
    # module owns the settlement — the same reason `refetch_policy.py` imports NEEDS_REFETCH
    # from here rather than restating it.
    from genios_engine.capture.parked.recapture import NEEDS_RECAPTURE

    now = now or datetime.now(timezone.utc)
    where_org = " and org_id=:o" if org_id else ""
    params = {"o": org_id} if org_id else {}
    with engine.connect() as c:
        rows = c.execute(text(
            "select reason_code, status, refetch_failure_kind, count(*) as n, "
            "       min(created_at) as oldest "
            f"from parked_events where 1=1{where_org} "
            "group by reason_code, status, refetch_failure_kind order by n desc"),
            params).fetchall()
    return [{"reason_code": r.reason_code, "status": r.status, "count": int(r.n),
             "failure_kind": r.refetch_failure_kind,
             "oldest": r.oldest.isoformat() if r.oldest else None,
             "age_days": round((now - r.oldest).total_seconds() / 86400, 1) if r.oldest else None,
             # `terminal` is a CLAIM — "stop looking at these" — and it was being made about
             # every code no set happened to name. It is now reachable only for a code all
             # THREE drains disown, and `tests/capture/parked/test_park_code_coverage.py`
             # proves the gate cannot emit one.
             "class": ("needs_refetch" if r.reason_code in NEEDS_REFETCH
                       else "re_adjudicable" if r.reason_code in RE_ADJUDICABLE
                       else "needs_recapture" if r.reason_code in NEEDS_RECAPTURE
                       else "terminal")}
            for r in rows]
