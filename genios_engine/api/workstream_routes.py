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

WHO READS. Anyone the dashboard already lets read the tenant (`get_current_org`), as the company
brief's own read is (`api/company_brief_routes`). A scoped key is refused there, as everywhere.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from genios_engine.context.workstream_numbers import as_dict as numbers_as_dict
from genios_engine.context.workstream_numbers import numbers_for
from genios_engine.context.workstream_timeline import as_dict as timeline_as_dict
from genios_engine.context.workstream_timeline import timeline_for
from genios_engine.context.workstreams import as_dict, file_as_dict, files_for
from genios_engine.packs.compiler.playbook_reader import playbook_for
from genios_engine.platform.auth import get_current_org
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()


def _engine():
    if _graph is None:
        raise HTTPException(503, "no database")
    return _graph.engine


def _now() -> datetime:
    """The clock is read here, at the request boundary; the read model takes it as a parameter."""
    return datetime.now(timezone.utc)


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
        file = next((f for f in files_for(conn, org_id, now=now).files if f.file_id == file_id),
                    None)
        if file is None:
            raise HTTPException(404, "no such file")
        timeline = timeline_for(conn, org_id, file_id, now=now)
        return {"as_of": now.isoformat(), "file": file_as_dict(file),
                "timeline": timeline_as_dict(timeline),
                "numbers": numbers_as_dict(numbers_for(conn, org_id, file, timeline, now=now)),
                "playbook": playbook_for(file.work_kind).as_dict()}
