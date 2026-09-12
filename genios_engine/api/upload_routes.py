"""Resource uploads (dashboard → Resources → Uploads). A file becomes a data source: stored to disk,
parsed to text, chunked, and each chunk injected as a source_events row (source='upload') so the SAME
chain a connector sync runs (L2 `process_pending` → reasoning → cards, via the warm lane in
`platform/warm_lane.py`) pulls entities + facts into the graph and reasons over them.
No user credits are charged (upload isn't /v1/intelligence/query); the LLM extraction cost lands in
llm_costs like any sync. These endpoints lived only in the old genios-brain; ported to the engine's
raw-SQL + `_org` conventions.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.capture.documents.chunking import (SECTION, SENTENCE, Chunk, chunk_document)
from genios_engine.capture.documents.native import native_page_map
from genios_engine.capture.esqe.finalize import L1Stores, ManualSweep, finalize_l1
from genios_engine.capture.documents.native import extract_text_best_effort
from genios_engine.capture.internal_knowledge import (authority_rank_for, is_canon,
                                                      normalize_kind)
from genios_engine.contracts.visibility import PRIVATE, Visibility
from genios_engine.platform.auth import AuthCtx, get_current_org, require_workspace_user
from genios_engine.platform.config import get_settings
from genios_engine.platform.logging import get_logger
from genios_engine.platform.wiring import (make_conflict_store, make_coverage_fn,
                                           make_drop_ledger, make_esqe_stage, make_floor_store,
                                           make_graph_store, make_lifecycle_store,
                                           make_llm_client, make_ocr, make_parked_store,
                                           make_payload_store, make_prepared_store,
                                           make_rejection_ledger, make_repo,
                                           make_semantic_lane, make_signal_store,
                                           make_trace_repo)

router = APIRouter()
_log = get_logger("genios.uploads")
_graph = make_graph_store()
_llm = make_llm_client()
_payloads = make_payload_store()
_repo = make_repo()
_prepared = make_prepared_store()
_trace_repo = make_trace_repo()
# L1.6.10 · the same seven stores the sync door finalizes through. Built here rather than
# imported from `api/routes.py` so this module keeps no dependency on that one; they are thin
# wrappers over the same engine URL, so two handles cost nothing a connection pool notices.
_parked = make_parked_store()

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"   # genios-engine/uploads/
MAX_BYTES = 10 * 1024 * 1024                                    # 10 MiB
CHUNK_CHARS = 2000
MAX_CHUNKS = 300                                               # cap per file so one upload can't runaway
                                                               # (~300 pages); if exceeded it is REPORTED, never silently dropped
_PROGRESS = {"queued": 10, "extracting": 55, "indexed": 100, "failed": 0}


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    """Resolve the tenant from the credential; refuse a path that names a different org."""
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


#: company  = org-visible knowledge — every upload that existed before seats, and the canon path
#:            for SOP / policy tags.
#: personal = private to the uploading seat: listed to nobody else, and every event it produces
#:            carries `private` visibility naming only that seat's address.
UPLOAD_SCOPES = ("company", "personal")


def _upload_ctx(org_id: str, ctx: AuthCtx = Depends(require_workspace_user)) -> AuthCtx:
    """Anyone who works here — owner, admin or member seat. What each may SEE and CHANGE is decided
    per file (`_may_change`, the list filter), never by this dependency."""
    if org_id != ctx.org_id:
        raise HTTPException(403, "org mismatch")
    return ctx


def _upload_org(org_id: str, ctx: AuthCtx = Depends(_upload_ctx)) -> str:
    return ctx.org_id


def _is_company(r) -> bool:
    return (getattr(r, "scope", None) or "company") == "company"


def _may_change(ctx: AuthCtx, owner) -> None:
    """Who may delete or retag a file. A PERSONAL file: only the seat that uploaded it — anyone
    else is told it does not exist, because a personal file is not theirs to know about. A COMPANY
    file: an admin / the owner, or the seat that uploaded it."""
    seat = getattr(owner, "seat_id", None)
    if not _is_company(owner) and seat != ctx.seat_id:
        raise HTTPException(404, {"error": "not_found", "message": "upload not found"})
    if _is_company(owner) and ctx.is_member and seat != ctx.seat_id:
        raise HTTPException(403, {"error": "admin_required",
                                  "message": "only an admin or the uploader can change a company file"})


def _ext(name: str) -> str:
    return (name.rsplit(".", 1)[-1] if "." in name else "").lower()


def _extract_text(name: str, data: bytes, content_type: str = "",
                  org_id: str | None = None) -> str:
    """Native extraction + OCR fallback — the SAME document path email/Drive attachments use, so a
    scanned PDF/image uploaded here reads exactly like one that arrived by email. (The upload door
    was pypdf-only before, so a scanned file returned "" even with OCR enabled.) Plain-text formats
    still decode to utf-8; a binary that yields nothing returns "" → honest 'no extractable text'."""
    return extract_text_best_effort(mime=content_type or "", data=data, filename=name,
                                    ocr=make_ocr(org_id))


def _chunk(text_content: str) -> list[Chunk]:
    """Boundary-aware chunking (capture.documents.chunking) — a fact is never sliced
    mid-sentence, and never across a HEADING. Returns ALL chunks; the caller applies MAX_CHUNKS
    and reports any truncation, so a big file is never silently cut off while status reports
    success.

    The SECTION strategy, which is what doc-04 assigns to the `document` profile and what an
    upload is. The door used to chunk by sentence, so a clause could be split at the point of its
    own emphasis and — the reason this changed — no chunk knew which heading it sat under, which
    is half of what makes a citation checkable by a person.

    The `Chunk` OBJECTS now, not `chunk_text`'s strings: each one carries its own `start_offset`
    into the document and the `section_title` the chunker detected, and both are the locator an
    evidence span needs to say *page 4 · Termination* instead of *character 4,812*. They exist
    for the length of this function and are unrecoverable afterwards — `chunk_text`'s own
    docstring says it drops them because the upload door "has no use for offsets yet", which
    stopped being true the moment a receipt had to be human-checkable.
    """
    sections = chunk_document(text_content, max_chars=CHUNK_CHARS, strategy=SECTION)
    out: list[Chunk] = []
    for piece in sections:
        if not piece.oversized:
            out.append(replace(piece, index=len(out)))
            continue
        # A section longer than the chunk cap is emitted WHOLE by the section strategy — the
        # chunker refuses to tear a clause apart, and says so — which leaves the caller the
        # choice its docstring names: "pay for the longer prompt, or page the chunk yourself".
        # We page it, by sentence, and every piece INHERITS the heading it came from. Paying the
        # longer prompt would put a 50-page agreement into one model call; dropping the heading
        # to get sentence chunking would trade a citation that says *Termination* for one that
        # says "somewhere in the agreement".
        for inner in chunk_document(piece.text, max_chars=CHUNK_CHARS, strategy=SENTENCE):
            out.append(replace(
                inner, index=len(out), section_title=piece.section_title,
                start_offset=piece.start_offset + inner.start_offset,
                end_offset=piece.start_offset + inner.end_offset))
    return out


def _l1_stores() -> L1Stores:
    """The bundle `finalize_l1` writes through — see `api/routes._l1_stores`, same seven stores."""
    return L1Stores(conflicts=make_conflict_store(), floors=make_floor_store(),
                    drops=make_drop_ledger(), lifecycle=make_lifecycle_store(),
                    signals=make_signal_store(), parked=_parked,
                    rejections=make_rejection_ledger())


def _emit_chunk(org_id: str, file_id: str, idx: int, subject: str, body: str,
                uploader_email: str, internal_kind: str | None = None,
                coverage_fn=None, semantic=None, esqe=None, locator: dict | None = None,
                visibility: Visibility | None = None):
    """One upload chunk → THE ONE DOOR (capture_event via intake): deduped, traced,
    W-05-whitelisted, payload + prepared text persisted — identical to a connector sync.
    (Was a hand-rolled SQL insert that skipped the gate, the trace and the seam.)
    source/object_type ('upload','document_chunk') miss the structured registry, so the
    chunk takes the LLM extraction lane.

    A tag that names one of INTERNAL_KINDS makes the file COMPANY CANON: the chunks land
    in the `internal` family at authority rank 4, so an uploaded price list outranks what
    a billing system inferred. An unrecognised tag stays an ordinary label and the chunk
    keeps observed authority — the id shape is untouched either way, so `_ingest`'s
    reconciliation prefix still matches.

    `coverage_fn` is a PARAMETER, computed once per file by the caller, because it is one
    connections read plus one count query and a 30-chunk PDF would otherwise pay for both
    thirty times. Omitting it is what made every uploaded chunk land with
    `coverage_ready=None` — the same 100%-None population the sweep was fixed for, entered by
    a different door.

    RETURNS the `CaptureResult` — it used to return None, and that is how the signals an upload
    produced were lost: the caller had nothing to hand `finalize_l1`, so the floor, the lifecycle
    and the publisher never saw a file the tenant chose by hand. A chunk that lands as a
    duplicate returns one too; `qualify_sweep` reads `result.esqe` and a duplicate has none."""
    from genios_engine.capture.intake import ingest_manual
    return ingest_manual(
        org_id=org_id, source="upload", object_type="document_chunk",
        source_object_id=f"{file_id}:chunk_{idx}", body=body, subject=subject,
        actor_type="internal_user", actor_email=uploader_email,
        internal_kind=internal_kind,
        # One canon node per FILE, not per chunk. Keying on the event would give
        # a 30-chunk pricing PDF thirty separate "Pricing" entities, each holding
        # a slice of one document — the graph would look like thirty price lists.
        # Two independent things ride in `raw_extra` and neither may erase the other: the canon
        # key (one node per FILE) and the chunk's own locator (which page and section its text
        # came from). Merged into one mapping rather than passed as two arguments, because
        # `ingest_manual` writes `raw_extra` straight onto the raw object.
        raw_extra=({**({"knowledge_key": file_id, "title": subject} if internal_kind else {}),
                    **({"document": locator} if locator else {})} or None),
        repo=_repo, payload_store=_payloads, prepared_store=_prepared,
        trace_repo=_trace_repo, coverage_fn=coverage_fn, connection_id="upload",
        # S2 and S4, threaded from the caller for the same reason `coverage_fn` is: they are
        # facts about the TENANT (an activation row, an importance baseline), computed once per
        # file, and a 30-chunk PDF must not buy either of them thirty times.
        semantic=semantic, esqe=esqe,
        # None = the `upload` rule's org scope; a personal file passes its private audience.
        visibility=visibility)


_WARM_WAIT_S = 1800.0     # how long the count reconciliation waits for the warm lane's run


def _run_chain_for_upload(org_id: str, file_id: str, event_ids: tuple[str, ...]) -> None:
    """The FULL chain for the file's events — L2, reasoning, cards — not L2 alone (G-26: this door
    called `process_pending` and nothing else, so an uploaded contract reached the graph and
    never a card). The upload request already queued the events on the warm lane; with a worker
    running in this process we wait for it, otherwise the chain runs here, under the same org
    lease every other caller takes."""
    if not event_ids:
        return                         # nothing new landed (a re-land of chunks already known)
    from genios_engine.platform import warm_lane
    if warm_lane.worker_alive():
        if not warm_lane.wait_until_done(_graph.engine, org_id, event_ids, timeout_s=_WARM_WAIT_S):
            _log.warning("upload org=%s file=%s: warm lane still running after %ss — counting "
                         "what has landed so far", org_id, file_id, int(_WARM_WAIT_S))
        return
    from genios_engine.api.routes import _run_l2       # lazy: keeps this module off routes' import
    outcome = _run_l2(org_id)
    if outcome is not None and outcome.status == "busy":
        # Deferred behind a run that started before these events: wait for the one that follows.
        warm_lane.wait_until_done(_graph.engine, org_id, event_ids, timeout_s=_WARM_WAIT_S)


def _ingest(org_id: str, file_id: str, prefix: str, truncated: int = 0,
            event_ids: tuple[str, ...] | list[str] = ()) -> None:
    """Background: run the chain for the file's events (graph + reasoning + cards, via the warm
    lane), then reconcile this file's real fact/entity counts + flip status to 'indexed'.
    Best-effort, per-org isolated. Two dedup shapes are matched: the one-door key
    'upload:document_chunk:{file}:…' and the legacy pre-door key 'upload:{file}:…'."""
    like_new = f"upload:document_chunk:{file_id}:%"
    like_old = f"{prefix}:%"
    try:
        _run_chain_for_upload(org_id, file_id, tuple(event_ids))
    except Exception:
        _log.exception("upload L2 extraction failed org=%s file=%s", org_id, file_id)
    try:
        with _graph.engine.begin() as c:
            facts = c.execute(text(
                "select count(*) from graph_facts where org_id=:o and valid_to is null and status='active' "
                "and created_by_event_id in (select event_id from source_events where org_id=:o "
                "and (dedup_key like :p or dedup_key like :p2))"),
                {"o": org_id, "p": like_old, "p2": like_new}).scalar()
            ents = c.execute(text(
                "select count(*) from graph_nodes where org_id=:o and valid_to is null "
                "and created_by_event_id in (select event_id from source_events where org_id=:o "
                "and (dedup_key like :p or dedup_key like :p2))"),
                {"o": org_id, "p": like_old, "p2": like_new}).scalar()
            notes = []
            if _llm is None:
                notes.append("Stored — AI extraction is currently disabled (no model configured).")
            if truncated:
                # Honest partial-index report — the old path silently dropped everything past
                # the cap and still flipped status to 'indexed', so the user believed the whole
                # file was read. Never claim full coverage we did not deliver.
                notes.append(
                    f"Indexed the first {MAX_CHUNKS} sections; {truncated} more were not indexed "
                    f"(this file is larger than the current {MAX_CHUNKS}-section limit).")
            note = " ".join(notes) or None
            c.execute(text(
                "update resource_uploads set status='indexed', facts_count=:f, entities_count=:e, "
                "error=:err, processed_at=now() where org_id=:o and file_id=:fid"),
                {"f": int(facts or 0), "e": int(ents or 0), "err": note, "o": org_id, "fid": file_id})
    except Exception:
        _log.exception("upload count/status update failed org=%s file=%s", org_id, file_id)


def _row(r) -> dict:
    return {
        "id": r.file_id, "file_name": r.file_name, "file_type": r.file_type,
        "file_size": int(r.file_size_bytes or 0),
        "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None,
        "tag": r.tag, "status": r.status,
        "facts_count": int(r.facts_count or 0),
        "entities_count": int(r.entities_count or 0),
        "contacts_count": int(r.entities_count or 0),   # UI maps contacts→entities
        "progress": _PROGRESS.get(r.status, 0),
        "error": r.error,
        # Reported, not asserted. This was a hardcoded 1.0 on every row while the facts
        # underneath all landed at rank 2 — the UI claimed an authority the graph did not
        # honour, on a 0–1 scale nothing else in the API uses. Now it is the real rank,
        # matching /entity and the fact read models (2 observed · 4 company canon).
        "authority": authority_rank_for(r.tag if _is_company(r) else None),
        "internal_kind": normalize_kind(r.tag) if _is_company(r) else None,
        "is_canon": is_canon(r.tag) and _is_company(r),
        "scope": getattr(r, "scope", None) or "company",
    }


@router.post("/api/org/{org_id}/upload")
async def upload_resource(org_id: str, background_tasks: BackgroundTasks,
                          file: UploadFile = File(...), tag: str | None = Form(None),
                          scope: str = Form("company"),
                          ctx: AuthCtx = Depends(_upload_ctx)) -> dict:
    """`scope` = company (default — org-visible, today's behaviour, canon for SOP/policy tags) or
    personal (private to the uploading seat)."""
    org = ctx.org_id
    scope = (scope or "company").strip().lower()
    if scope not in UPLOAD_SCOPES:
        raise HTTPException(422, {"error": "invalid_scope",
                                  "message": "scope must be company or personal"})
    if scope == "personal" and not (ctx.seat_id and ctx.email):
        raise HTTPException(403, {"error": "seat_required",
                                  "message": "a personal upload needs a signed-in seat"})
    if scope == "company" and ctx.is_member and normalize_kind(tag):
        # Company canon outranks every observed source (authority rank 4). Declaring it is an
        # admin's act, not any teammate's.
        raise HTTPException(403, {"error": "admin_required",
                                  "message": "only an admin can add company policy or SOP documents"})
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    data = await file.read()
    if not data:
        raise HTTPException(422, {"error": "empty_file", "message": "file is empty"})
    if len(data) > MAX_BYTES:
        raise HTTPException(413, {"error": "too_large", "message": "file exceeds 10 MiB"})

    name = file.filename or "upload"
    # Content-addressed id → re-uploading the SAME file is idempotent: identical bytes → same file_id
    # → same chunk dedup keys → no duplicate events (MD Part 3.4). Org-scoped so two tenants uploading
    # the same file never collide.
    # A PERSONAL file's id is keyed on the seat too: two teammates uploading the same bytes each get
    # a private copy, and neither learns from a "duplicate" answer that the other has it. A company
    # file keeps the id it always had.
    salt = org.encode() + (b":personal:" + ctx.seat_id.encode() if scope == "personal" else b"")
    content_hash = hashlib.sha256(salt + b":" + data).hexdigest()
    file_id = "upl_" + content_hash[:24]
    prefix = f"upload:{file_id}"

    with _graph.engine.connect() as c:                 # already have this exact file? → idempotent
        existing = c.execute(text(
            "select status, chunks from resource_uploads where org_id=:o and file_id=:f"),
            {"o": org, "f": file_id}).first()
    if existing is not None:
        return {"file_id": file_id, "status": existing.status,
                "chunks": int(existing.chunks or 0), "duplicate": True}

    text_content = _extract_text(name, data, file.content_type or "", org_id=org_id)
    all_chunks = _chunk(text_content)
    chunks = all_chunks[:MAX_CHUNKS]
    # ONE page map for the whole file, sliced per chunk below. Computed here rather than inside
    # `_extract_text` because the best-effort extractor has three fallback paths and only one of
    # them produces a paged document; asking for the map separately keeps "what is the text" and
    # "where are its pages" from having to agree inside a function that answers the first.
    page_map = native_page_map(mime=file.content_type or "", data=data, filename=name)
    truncated = len(all_chunks) - len(chunks)          # >0 → reported in _ingest, never silent
    status = "extracting" if chunks else "failed"
    err = None if chunks else "No extractable text found in this file."

    storage_path = None
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120]
        p = UPLOAD_DIR / f"{file_id}_{safe}"
        p.write_bytes(data)
        storage_path = str(p)
    except Exception:                                           # noqa: BLE001 — disk record is a nicety
        _log.warning("upload disk write failed for %s", file_id)

    if ctx.seat_id and ctx.email:
        uploader = ctx.email                     # the signed-in person — owner or teammate
    else:
        with _graph.engine.connect() as c:
            uploader = c.execute(text("select email from orgs where id=:o"), {"o": org}).scalar()
        uploader = uploader or f"owner@{org}"

    try:
        with _graph.engine.begin() as c:
            c.execute(text(
                "insert into resource_uploads (file_id, org_id, file_name, file_type, "
                "file_size_bytes, storage_path, tag, status, source_item_prefix, chunks, error, "
                "uploaded_by, scope, seat_id) "
                "values (:fid,:o,:fn,:ft,:sz,:sp,:tag,:st,:pref,:ch,:err,:by,:scope,:seat) "
                "on conflict do nothing"),                # race safety; the pre-check handles the common case
                {"fid": file_id, "o": org, "fn": name, "ft": _ext(name), "sz": len(data),
                 "sp": storage_path, "tag": tag, "st": status, "pref": prefix, "ch": len(chunks),
                 "err": err, "by": uploader, "scope": scope, "seat": ctx.seat_id})
    except Exception:
        # In particular, an account deletion may revoke the org while this upload waits on its FK
        # lock. Never leave the bytes orphaned when the metadata insert cannot commit.
        if storage_path:
            try:
                Path(storage_path).unlink(missing_ok=True)
            except OSError:
                _log.exception("failed to clean upload after metadata insert failure: %s", file_id)
        raise

    # A canon tag promotes the whole file to rank 4 — for a COMPANY file only. A personal copy of a
    # policy is one person's file, not the company's policy.
    kind = normalize_kind(tag) if scope == "company" else None
    visibility = (Visibility(scope=PRIVATE, principals=[uploader.strip().lower()],
                             derived_from=f"upload:personal:{ctx.seat_id}")
                  if scope == "personal" else None)
    # ONE declaration for the whole file, not one per chunk: the inputs are a connections read
    # and a count(distinct source_object_id), and they are facts about the TENANT's sources, not
    # about a paragraph of a PDF.
    coverage_fn = make_coverage_fn(org)
    # ONE lane and ONE baseline for the whole file, on the same argument `coverage_fn` makes
    # above: `make_semantic_lane` reads the tenant's activation row and builds a cost governor,
    # `make_esqe_stage` computes L1.6.7's org baseline off a windowed scan. Per chunk, a 30-page
    # PDF would pay for both thirty times. `semantic` is None for a tenant with no activation
    # row, which is the state every tenant is in until a pilot switches one on — and the file
    # still lands, is still chunked and still reaches L2 exactly as before.
    semantic = make_semantic_lane(org, engine=getattr(_graph, "engine", None))
    esqe = make_esqe_stage(org, engine=getattr(_graph, "engine", None))
    results = []
    for i, ch in enumerate(chunks):
        # The chunk's slice of the file's page map, re-expressed in the CHUNK's own coordinates —
        # a chunk starting halfway down page 3 gets a one-entry map numbered 3, so every span in
        # it cites page 3. Plus the section heading the chunker detected, which is a property of
        # the whole chunk.
        chunk_pages = page_map.for_slice(ch.start_offset, ch.end_offset)
        locator = {**chunk_pages.as_record(), "section_title": ch.section_title} \
            if (chunk_pages or ch.section_title) else None
        res = _emit_chunk(org, file_id, i, name, ch.text, uploader, internal_kind=kind,
                          coverage_fn=coverage_fn, semantic=semantic, esqe=esqe,
                          locator=locator, visibility=visibility)
        if res is not None:
            results.append(res)
    if results:
        # L1.6.10 · THE SAME FINALIZER THE SYNC DOOR USES. Without this the chunks were captured,
        # extracted and SCORED and then nothing filed the conflicts, ran the floor, aged the
        # lifecycle or published — so `qualified_signals` held no row for the one source the
        # tenant chose deliberately. Synchronous rather than a background task: it is four
        # in-process passes over the events this request just captured, it never raises, and
        # deferring it would put the publish behind `_ingest`'s L2 drain, which reads what this
        # writes.
        finalize_l1(ManualSweep(org_id=org, results=tuple(results), emitted=len(results),
                                scanned=len(chunks)),
                    org_id=org, stores=_l1_stores())
    # WARM LANE: queue what this file emitted, after the finalizer published it. The worker runs
    # the whole chain — graph, reasoning, cards — for these and anything else the org has queued.
    emitted_ids = [r.event.event_id for r in results
                   if r.outcome == "emitted" and getattr(r, "event", None) is not None]
    if emitted_ids and _graph is not None:
        from genios_engine.platform import warm_lane
        warm_lane.enqueue(_graph.engine, org, emitted_ids, source="upload")
    if chunks:
        background_tasks.add_task(_ingest, org, file_id, prefix, truncated, tuple(emitted_ids))
        # N-3 · ORG-BRAIN DISCOVERY (L3.2-U1 step 1) — the SECOND canon door. A file tagged with
        # a rule-bearing kind (policy, sop, pricing, org_structure) is the company's own written
        # rules arriving; doc 02's trigger is "on canon ingest" and this is it. A sweep rather
        # than a per-chunk call because the chunk event ids are not kept here, and it is
        # idempotent on the document version, so an already-read chunk costs one indexed read.
        # Queued AFTER `_ingest` so L2's drain has run first and an approver named in the policy
        # has a node to resolve to.
        if scope == "company":                 # a personal file is nobody's company rules
            from genios_engine.feedback.org_rule_ingest import sweep_org_rule_discovery
            background_tasks.add_task(sweep_org_rule_discovery, org)

    from genios_engine.platform.audit import record
    record(org, "data_accessed", actor_type="user", actor_id=uploader, target_type="upload",
           target_id=file_id, metadata={"file_name": name, "bytes": len(data), "chunks": len(chunks)})
    return {"file_id": file_id, "status": status, "chunks": len(chunks), "scope": scope}


@router.get("/api/org/{org_id}/uploads")
def list_uploads(org_id: str, ctx: AuthCtx = Depends(_upload_ctx)) -> dict:
    """Company files to everyone who works here; a PERSONAL file only to the seat that uploaded it
    — not to an admin, not to the owner."""
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            "select file_id, file_name, file_type, file_size_bytes, uploaded_at, tag, status, "
            "facts_count, entities_count, error, scope, seat_id from resource_uploads "
            "where org_id=:o and (scope='company' or seat_id=cast(:seat as text)) "
            "order by uploaded_at desc"), {"o": ctx.org_id, "seat": ctx.seat_id}).fetchall()
    return {"uploads": [_row(r) for r in rows]}


@router.delete("/api/org/{org_id}/uploads/{file_id}")
def delete_upload(org_id: str, file_id: str, org: str = Depends(_upload_org),
                  ctx: AuthCtx = Depends(_upload_ctx)) -> dict:
    # Called directly (tests, internal callers) there is no request credential: it acts with the
    # reach of an owner-level one, which is what the function always did.
    ctx = ctx if isinstance(ctx, AuthCtx) else AuthCtx(org_id=org)
    like_old = f"upload:{file_id}:%"                      # pre-door key shape
    like_new = f"upload:document_chunk:{file_id}:%"       # one-door key shape
    with _graph.engine.begin() as c:
        rec = c.execute(text("select storage_path from resource_uploads where org_id=:o and file_id=:f"),
                        {"o": org, "f": file_id}).first()
        if rec is None:
            raise HTTPException(404, {"error": "not_found", "message": "upload not found"})
        _may_change(ctx, c.execute(text(
            "select scope, seat_id from resource_uploads where org_id=:o and file_id=:f"),
            {"o": org, "f": file_id}).first())
        evids = [r.event_id for r in c.execute(text(
            "select event_id from source_events where org_id=:o "
            "and (dedup_key like :p or dedup_key like :p2)"),
            {"o": org, "p": like_old, "p2": like_new})]
        if evids:
            # remove the facts learned from THIS file + its capture artifacts (raw payload,
            # prepared text, observations). Shared graph_nodes are left in place (they may
            # be referenced by other sources).
            # Lock/bump the tenant graph version in this SAME transaction before changing
            # graph state. Layer 4 holds a shared lock on this row while publishing decisions,
            # so an erasure can never commit halfway through a reasoning emission window.
            _graph.bump_version(c, org)
            c.execute(text("delete from graph_facts where org_id=:o and created_by_event_id = any(:e)"),
                      {"o": org, "e": evids})
            c.execute(text("delete from graph_observations where org_id=:o "
                           "and created_by_event_id = any(:e)"), {"o": org, "e": evids})
            c.execute(text("delete from raw_payloads where org_id=:o and event_id = any(:e)"),
                      {"o": org, "e": evids})
            c.execute(text("delete from prepared_content where org_id=:o and event_id = any(:e)"),
                      {"o": org, "e": evids})
            c.execute(text("delete from source_events where org_id=:o and event_id = any(:e)"),
                      {"o": org, "e": evids})
        c.execute(text("delete from resource_uploads where org_id=:o and file_id=:f"),
                  {"o": org, "f": file_id})
    try:
        if rec.storage_path and os.path.exists(rec.storage_path):
            os.remove(rec.storage_path)
    except Exception:                                           # noqa: BLE001
        pass
    from genios_engine.platform.audit import record
    record(org, "data_subject_erasure", actor_type="user", target_type="upload", target_id=file_id,
           metadata={"events_removed": len(evids)})
    return {"deleted": True}


class TagUpdate(BaseModel):
    tag: str


@router.patch("/api/org/{org_id}/uploads/{file_id}/tag")
def retag_upload(org_id: str, file_id: str, body: TagUpdate,
                 ctx: AuthCtx = Depends(_upload_ctx)) -> dict:
    org = ctx.org_id
    with _graph.engine.begin() as c:
        owner = c.execute(text(
            "select scope, seat_id from resource_uploads where org_id=:o and file_id=:f for update"),
            {"o": org, "f": file_id}).first()
        if owner is None:
            raise HTTPException(404, {"error": "not_found", "message": "upload not found"})
        _may_change(ctx, owner)
        if _is_company(owner) and ctx.is_member and normalize_kind(body.tag):
            raise HTTPException(403, {"error": "admin_required",
                                      "message": "only an admin can make a file company policy or SOP"})
        c.execute(text("update resource_uploads set tag=:t where org_id=:o and file_id=:f"),
                  {"t": body.tag, "o": org, "f": file_id})
    return {"retagged": True}
