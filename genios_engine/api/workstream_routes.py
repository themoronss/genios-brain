"""The founder's files, readable — `GET /v1/workstreams` (STEP-09) and `GET /v1/workstreams/{file_id}` (STEP-10).

The read model `context/workstreams.files_for` over the signed-in member's tenant: every file with the
kind the company brief gives it, its counterparty, its evidence, its last touch, its open asks and
whose move it is — and every counterparty the brief names, with how much of its mail is filed, the
ones with mail and no file named. Nothing is written, nothing calls a model, and nothing a seat
captured privately is listed (an org-level reader, `context/fact_visibility`).

ONE FILE, WITH ITS NUMBERS (STEP-10, `yc2_w27_s10 · M29.C2.L-interface.V3.U02`). The file as the list
gives it; its timeline — every touch both ways, who did it, the evidence, the gaps, whether the silence
outlasts them (`context/workstream_timeline`); and its numbers — each person's reply time and yours
with their n and basis, the normals that hold, a bounce, the mailboxes its mail came through and whether
"no reply" may be said (`context/workstream_numbers`). A file of another tenant, or none, is 404 — the
same answer, so a file id says nothing about who has one. Nothing is written.

AND WHAT A PROFESSIONAL KNOWS ABOUT ITS WORK (STEP-11, `yc2_w27_s11 · M30.C5.L-interface.V3.U02`). A file
knows its kind of work from the in-motion line of the brief that names it (`06` D31); the one-file read
carries `packs/compiler/playbook_reader.playbook_for(file.work_kind)` beside it — the kind's playbook
with its stages (each typical duration a labelled prior with its source), moves, claims, what doing
nothing costs, when the work is dormant and whether it was reviewed ("playbook not yet reviewed", `06`
D3), or the named reason there is none. What STEP-12's expert will read, readable first. The list does
not carry it: the corpus is read for the file a reader opened.

AND WHAT THE EXPERT CONCLUDED (STEP-12, `yc2_w27_s12 · M32.C3.L-interface.V3.U05`). `review` carries the
file's latest STANDING review — valid, refused or truncated, with its reason, what triggered it, the
model, the prompt version and its cost — and its latest VALID review, the one a decision may read
(`reason/expert/store`). A failed or carried attempt judged nothing and is not the file's review; the
health check counts those. A file never reviewed says so: both null.

AND ONLY WHAT ITS CHECK LET STAND (STEP-13, `yc2_w27_s13 · M35.C3.L-interface.V3.U07`, crosscheck X28). A review is
shown as `says` — the checked card words (`contracts/claim_check.CardWords`), and only when a check ran and did
not refuse it — and `check`, the check itself: its fate, why, the question it asked and each line's verdict. The
review's raw words are never served: unchecked they are what "nothing reaches the founder unchecked" forbids, and
a re-check that refused them leaves them data, as a refused answer's always were.

AND WHAT YOU CORRECTED (STEP-16, `yc2_w27_s16 · M46.C3.L-interface.V2.U03`; S16-D1). The one-file read lists
the file's standing corrections — its own and its kind of work's, newest first, the cut counted
(`context/founder_corrections.standing_for`) — and your door on a file is here: `POST
/v1/workstreams/{file_id}/corrections` keeps your words with their scope (`file`, `kind` or `company`) and,
optionally, the card they are about; `POST …/corrections/{id}/withdraw` takes one back. Nothing is deleted.

WHO READS. Anyone the dashboard already lets read the tenant (`get_current_org`), as the company
brief's own read is (`api/company_brief_routes`). A scoped key is refused there, as everywhere.

WHO CORRECTS (`06` D27's rule). A correction for a kind of work or for the company steers every file it
reaches, so it is the account OWNER's alone (`require_account_owner`'s test). A correction of one file is
the owner's, or the seat a card of that file is routed to — by assignment or declared responsibility
(`deliver/seat_access.card_reaches_seat`) — through that card. A `kind` correction on a file the brief
names no kind of work for is refused, saying so: there is no kind for it to reach.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.context import founder_corrections as corrections
from genios_engine.contracts import claim_check
from genios_engine.context.workstream_numbers import as_dict as numbers_as_dict
from genios_engine.context.workstream_numbers import numbers_for
from genios_engine.context.workstream_timeline import as_dict as timeline_as_dict
from genios_engine.context.workstream_timeline import timeline_for
from genios_engine.context.workstreams import as_dict, file_as_dict, file_for, files_for
from genios_engine.packs.compiler.playbook_reader import playbook_for
from genios_engine.deliver.seat_access import card_reaches_seat
from genios_engine.platform.auth import ROLE_OWNER, AuthCtx, get_current_org, require_workspace_user
from genios_engine.platform.wiring import make_graph_store
from genios_engine.reason.expert import store as reviews

router = APIRouter()
_graph = make_graph_store()


def _engine():
    if _graph is None:
        raise HTTPException(503, "no database")
    return _graph.engine


def _now() -> datetime:
    """The clock is read here, at the request boundary; the read model takes it as a parameter."""
    return datetime.now(timezone.utc)


def _review_as_dict(row: reviews.StoredReview | None) -> dict | None:
    """One stored review as the read model shows it: what its check let stand, and the check — never its raw
    words."""
    if row is None:
        return None
    checked = row.checked
    stands = row.review is not None and checked is not None and checked.fate != claim_check.REFUSED
    return {"fingerprint": row.fingerprint, "status": row.status, "reason": row.reason,
            "says": checked.words.as_mapping() if stands else None,
            "check": checked.as_mapping() if checked is not None else None,
            "triggers": [{"kind": kind, "says": says} for kind, says in (row.triggers or ())],
            "model": row.model, "prompt_version": row.prompt_version,
            "dossier_digest": row.dossier_digest, "cost_micro_usd": row.cost_micro_usd,
            "reviewed_at": row.reviewed_at.isoformat()}


class CorrectionIn(BaseModel):
    words: str
    scope: str = corrections.FILE
    card_id: str | None = None


def _correction_as_dict(item: corrections.Correction) -> dict:
    return {"correction_id": item.correction_id, "file_id": item.file_id, "card_id": item.card_id,
            "feedback_id": item.feedback_id, "reason": item.reason, "words": item.words, "scope": item.scope,
            "kind": item.kind, "brief_line_id": item.brief_line_id, "corrected_by": item.corrected_by,
            "corrected_at": item.corrected_at.isoformat(), "state": item.state,
            "withdrawn_by": item.withdrawn_by,
            "withdrawn_at": item.withdrawn_at.isoformat() if item.withdrawn_at else None}


def _standing_as_dict(standing: corrections.Standing) -> dict:
    return {"standing": [_correction_as_dict(item) for item in standing.corrections], "cut": standing.cut}


def _is_owner(ctx: AuthCtx) -> bool:
    """The account's owner — `require_account_owner`'s own test: no scope list, and the owner's role (or an
    owner-level key, which has no seat)."""
    return ctx.scopes is None and ctx.role in (None, ROLE_OWNER)


#: The card a seat corrects a file through: this tenant's, about the file (its anchor or one of its people).
_CARD_OF_THE_FILE = text(
    "select k.card_id from cards k join signals s on s.org_id = k.org_id and s.signal_id = k.signal_id "
    "where k.org_id = :o and k.card_id = :c and s.subject_node_id = any(:ids)")


def _may_correct(conn, ctx: AuthCtx, file, scope: str, card_id: str | None) -> bool:
    if _is_owner(ctx):
        return True
    if scope != corrections.FILE or not card_id:
        return False
    ids = sorted({str(file.file_id), *(str(p) for p in file.people)})
    if conn.execute(_CARD_OF_THE_FILE, {"o": ctx.org_id, "c": card_id, "ids": ids}).first() is None:
        return False
    return card_reaches_seat(conn, ctx.org_id, card_id, ctx.seat_id)


@router.get("/v1/workstreams")
def list_workstreams(org_id: str = Depends(get_current_org)) -> dict:
    """Every file of the tenant, most recently touched first, with what the founder's brief names."""
    now = _now()
    with _engine().connect() as conn:
        return as_dict(files_for(conn, org_id, now=now), now=now)


@router.get("/v1/workstreams/{file_id}")
def read_workstream(file_id: str, org_id: str = Depends(get_current_org)) -> dict:
    """One file of the tenant: what it is, its timeline, and its numbers, each with what it rests on."""
    now = _now()
    with _engine().connect() as conn:
        file = file_for(conn, org_id, file_id, now=now)
        if file is None:
            raise HTTPException(404, "no such file")
        timeline = timeline_for(conn, org_id, file_id, now=now)
        return {"as_of": now.isoformat(), "file": file_as_dict(file),
                "timeline": timeline_as_dict(timeline),
                "numbers": numbers_as_dict(numbers_for(conn, org_id, file, timeline, now=now)),
                "playbook": playbook_for(file.work_kind).as_dict(),
                "review": {"latest": _review_as_dict(reviews.latest_standing(conn, org_id, file_id)),
                           "valid": _review_as_dict(reviews.latest_valid(conn, org_id, file_id))},
                "corrections": _standing_as_dict(corrections.standing_for(
                    conn, org_id, file_id, people=file.people, kind=file.work_kind))}


@router.post("/v1/workstreams/{file_id}/corrections")
def correct_workstream(file_id: str, body: CorrectionIn, ctx: AuthCtx = Depends(require_workspace_user)) -> dict:
    """Your correction of the file, in your words, with its scope — kept once (the same words again are the
    same correction). 404 for a file this tenant does not hold; 403 for a correction this seat may not make;
    422 for words or a scope the store refuses, or a `kind` on a file the brief names no kind of work for."""
    now = _now()
    with _engine().begin() as conn:
        file = file_for(conn, ctx.org_id, file_id, now=now)
        if file is None:
            raise HTTPException(404, "no such file")
        if not _may_correct(conn, ctx, file, body.scope, body.card_id):
            raise HTTPException(403, "a correction of every file of a kind, or of the company, is the owner's; "
                                     "a seat corrects a file through a card of it routed to them")
        if body.scope == corrections.KIND and not file.work_kind:
            raise HTTPException(422, "the brief names no kind of work for this file — say which in the brief, "
                                     "or correct this file alone")
        try:
            kept = corrections.correct(
                conn, org_id=ctx.org_id, file_id=file_id, words=body.words, scope=body.scope,
                by=ctx.actor_id or ctx.org_id, at=now, card_id=body.card_id,
                kind=file.work_kind if body.scope == corrections.KIND else None)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"correction": _correction_as_dict(kept)}


@router.post("/v1/workstreams/{file_id}/corrections/{correction_id}/withdraw")
def withdraw_workstream_correction(file_id: str, correction_id: str,
                                   ctx: AuthCtx = Depends(require_workspace_user)) -> dict:
    """Take a correction of this file back — kept, withdrawn. The owner may withdraw any; a seat, a correction
    of one file it wrote. 404 for a correction this file does not hold; 409 for one already withdrawn."""
    now = _now()
    with _engine().begin() as conn:
        file = file_for(conn, ctx.org_id, file_id, now=now)
        item = corrections.by_id(conn, ctx.org_id, correction_id)
        if file is None or item is None or item.file_id not in {str(file.file_id), *file.people}:
            raise HTTPException(404, "no such correction of this file")
        mine = item.scope == corrections.FILE and item.corrected_by == (ctx.actor_id or ctx.org_id)
        if not (_is_owner(ctx) or mine):
            raise HTTPException(403, "only the owner, or the seat that wrote it, takes a correction back")
        try:
            gone = corrections.withdraw(conn, org_id=ctx.org_id, correction_id=correction_id,
                                        by=ctx.actor_id or ctx.org_id, at=now)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"correction": _correction_as_dict(gone)}
