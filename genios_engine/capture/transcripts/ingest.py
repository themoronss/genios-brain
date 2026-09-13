"""P5 · a transcript → private, turn-bounded `meeting_transcript` events + a `transcripts` row.

    text → parse → link meeting → map speakers (attendees + uploader only) → parts (≤ 12k chars,
    split on turn boundaries, each after the first carrying the previous part's tail under a
    "context — do not extract" header) → `ingest_manual(object_type="meeting_transcript")` per
    part, PRIVATE to attendees ∪ uploader (personal / unlinked → the uploader alone) → row.

THE AUDIENCE IS STAMPED HERE, never derived later. A Drive file would otherwise take the knowledge
family's ORG scope and an upload the deliberate-intake ORG scope (`visibility_rules.py`); a meeting
is neither — it is its attendees' conversation. Every part event carries the explicit PRIVATE
visibility, and Layer 2 treats a transcript's work facts (commitments) as private too
(`context/fact_visibility.strict_private_evidence`).

IDEMPOTENT on `(org, source, source_ref)` + the content version. The version is the transcript's
content hash plus a hash of the speaker map, the meeting link and the audience, so an identical
re-upload changes nothing, while a speaker re-map (`PUT /v1/transcripts/{id}/speakers`) or a new
link lands as a new content version of the same parts.

Every part event carries `raw.transcript` (the §3 object without the text) — the seam Layer 2 reads
to seed speaker → person resolution and to refuse the uploader as a fallback owner.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from typing import Any, Callable, Mapping

from sqlalchemy import text

from genios_engine.capture.documents.base import UNKNOWN_SPEAKER
from genios_engine.capture.semantic.profiles import SCREEN_CONTEXT_HEADER
from genios_engine.contracts.visibility import PRIVATE, Visibility
from genios_engine.platform.logging import get_logger

from .link import LinkResult, link_meeting
from .parse import ParsedTranscript, Turn, clean_title, parse_date, parse_transcript
from .speakers import Candidate, candidate_from_entry, load_candidates, map_speakers

_log = get_logger("genios.transcripts")

SCHEMA_VERSION = 1
#: The object type every transcript part lands under — `router.TRANSCRIPT_OBJECT_TYPES` routes it
#: to the `transcript` profile.
OBJECT_TYPE = "meeting_transcript"
#: What the Drive connector emits for a Meet transcript Doc. It never reaches `capture_event` as
#: itself: `sync_runner` diverts it here (its body is empty by construction, so even a missed
#: diversion would extract nothing under the ORG scope).
DRIVE_OBJECT_TYPE = "gmeet_transcript"
PART_MAX_CHARS = 12_000
CONTEXT_MAX_CHARS = 1_500
CONTEXT_LINES = 4
SCOPES = ("attendees", "personal")
STATUSES = ("queued", "extracting", "extracted", "failed")


class TranscriptError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class TranscriptDoors:
    """The capture stores, threaded from the door that owns them (upload route / sync run)."""

    repo: Any
    payload_store: Any = None
    prepared_store: Any = None
    trace_repo: Any = None
    coverage_fn: Any = None
    semantic: Any = None
    esqe: Any = None
    connection_id: str = "upload"
    #: Called with the part results (the upload door's `finalize_l1`); None for a sync, whose
    #: caller finalizes the whole sweep.
    finalize: Callable[[list], None] | None = None
    #: Called with the emitted event ids (the warm lane); None for a sync.
    enqueue: Callable[[list[str]], None] | None = None
    #: Called as (org_id, transcript_id, keep_version) BEFORE a new content version lands, to
    #: retire what the previous version extracted. None leaves the old version's facts in place.
    retire: Callable[[str, str, str], None] | None = None


@dataclass
class IngestOutcome:
    transcript: dict
    duplicate: bool
    results: list = field(default_factory=list)
    emitted_ids: list[str] = field(default_factory=list)
    parsed: ParsedTranscript | None = None


# ── parts ──────────────────────────────────────────────────────────────────────────────────────
def _split_long(label: str, said: str, budget: int) -> list[str]:
    """One turn longer than a part → sentence pieces, each re-labelled with its speaker."""
    head = f"{label}: "
    room = max(200, budget - len(head))
    pieces, cur = [], ""
    for sent in re.split(r"(?<=[.!?])\s+", said):
        while len(sent) > room:                        # a sentence with no stop in 12k chars
            if cur:
                pieces.append(cur)
                cur = ""
            pieces.append(sent[:room])
            sent = sent[room:]
        if cur and len(cur) + 1 + len(sent) > room:
            pieces.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        pieces.append(cur)
    return [head + p for p in pieces]


def _context(lines: list[str], budget: int) -> list[str]:
    kept: list[str] = []
    used = len(SCREEN_CONTEXT_HEADER) + 2
    for ln in reversed(lines[-CONTEXT_LINES:]):
        q = "> " + (ln if len(ln) <= budget - used - 3 else ln[: max(40, budget - used - 4)] + "…")
        if used + len(q) + 1 > budget:
            break
        kept.append(q)
        used += len(q) + 1
    return list(reversed(kept))


def build_parts(turns: tuple[Turn, ...] | list[Turn], *, max_chars: int = PART_MAX_CHARS,
                context_chars: int = CONTEXT_MAX_CHARS) -> list[str]:
    """Turn-bounded parts. A part never splits a turn unless the turn alone exceeds the budget;
    each part after the first ends with the previous part's last lines, quoted, as context."""
    lines: list[str] = []
    for t in turns:
        label = t.speaker or UNKNOWN_SPEAKER
        line = f"{label}: {t.text}"
        lines.extend([line] if len(line) <= max_chars else _split_long(label, t.text, max_chars))
    groups: list[list[str]] = []
    cur: list[str] = []
    used = 0
    for ln in lines:
        if cur and used + len(ln) + 1 > max_chars:
            groups.append(cur)
            cur, used = [], 0
        cur.append(ln)
        used += len(ln) + 1
    if cur:
        groups.append(cur)
    bodies = []
    for i, group in enumerate(groups):
        body = "\n".join(group)
        if i:
            ctx = _context(groups[i - 1], context_chars)
            if ctx:
                body += "\n\n" + SCREEN_CONTEXT_HEADER + "\n" + "\n".join(ctx)
        bodies.append(body)
    return bodies


# ── the §3 object ──────────────────────────────────────────────────────────────────────────────
def transcript_id_for(org_id: str, source: str, source_ref: str) -> str:
    return "trn_" + hashlib.sha256(f"{org_id}:{source}:{source_ref}".encode()).hexdigest()[:24]


def _iso(v) -> str | None:
    return v.isoformat() if isinstance(v, (datetime, date)) else (v or None)


def view(row: Any) -> dict:
    """A `transcripts` row → the frozen §3 transcript object (+ `attendees`, pinned §3)."""
    m = _json(row.meeting, {})
    speakers = _json(row.speakers, [])
    return {"schema_version": SCHEMA_VERSION, "transcript_id": row.transcript_id,
            "provider": row.provider,
            "meeting": {"calendar_event_id": row.calendar_event_id,
                        "meeting_node_id": row.meeting_node_id,
                        "title": row.title, "started_at": _iso(row.started_at),
                        "ended_at": _iso(row.ended_at),
                        "candidates": list(m.get("candidates") or [])},
            "speakers": speakers, "attendees": _json(row.attendees, []),
            "scope": row.scope, "principals": list(row.principals or []),
            "parts": int(row.parts or 0), "content_hash": row.content_hash,
            "status": row.status}


def _json(value, default):
    if value is None:
        return default
    return value if isinstance(value, (dict, list)) else json.loads(value)


_SELECT = ("select transcript_id, org_id, source, source_ref, file_id, seat_id, uploader_email, "
           "provider, scope, calendar_event_id, meeting_node_id, title, started_at, ended_at, "
           "meeting, speakers, attendees, principals, parts, event_ids, content_hash, "
           "content_version, enc_text, status, error, created_at, updated_at from transcripts ")


def load_row(conn, org_id: str, transcript_id: str):
    return conn.execute(text(_SELECT + "where org_id=:o and transcript_id=:t"),
                        {"o": org_id, "t": transcript_id}).first()


def visible_rows(conn, org_id: str, email: str | None, *, limit: int = 100) -> list:
    """The rows a seat may see: those naming its address as a principal. Nobody else — not an
    admin, not the owner: a meeting's transcript is its attendees' conversation."""
    e = (email or "").strip().lower()
    if not e:
        return []
    return conn.execute(text(_SELECT + "where org_id=:o and :e = any(principals) "
                             "order by coalesce(started_at, created_at) desc limit :n"),
                        {"o": org_id, "e": e, "n": limit}).fetchall()


def may_read(row: Any, email: str | None) -> bool:
    e = (email or "").strip().lower()
    return bool(e) and e in {str(p).lower() for p in (row.principals or [])}


# ── the door ───────────────────────────────────────────────────────────────────────────────────
def _occurred(started_at: datetime | None, day: date | None) -> datetime:
    """The instant relative due dates ("by Friday") resolve against: the meeting's start, else its
    day at noon UTC (noon, so no zone moves it to another day), else now."""
    if started_at is not None:
        return started_at
    if day is not None:
        return datetime.combine(day, time(12, 0), tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _attendee_views(link: LinkResult, candidates: list[Candidate]) -> list[dict]:
    names = {a.get("email"): a for a in (link.meeting.attendees if link.meeting else ())}
    out = []
    for c in candidates:
        base = c.view()
        known = names.get(c.email)
        if known and known.get("name"):
            base["name"] = known["name"]
        out.append(base)
    return out


def ingest_transcript(engine, *, org_id: str, text_content: str, source: str, source_ref: str,
                      uploader_email: str, seat_id: str | None, doors: TranscriptDoors,
                      provider_hint: str | None = None, filename: str = "",
                      meeting_node_id: str | None = None, calendar_event_id: str | None = None,
                      drive_file_id: str | None = None, meeting_title: str | None = None,
                      meeting_date: date | None = None, scope: str = "attendees",
                      file_id: str | None = None,
                      manual: Mapping[str, Candidate | None] | None = None,
                      crypto_key: str | None = None) -> IngestOutcome:
    scope = (scope or "attendees").strip().lower()
    if scope not in SCOPES:
        raise TranscriptError("invalid_scope", "scope must be attendees or personal")
    uploader = (uploader_email or "").strip().lower()
    if "@" not in uploader:
        raise TranscriptError("uploader_required", "a transcript needs its uploader's address")
    parsed = parse_transcript(text_content, filename=filename, provider_hint=provider_hint)
    if not parsed.turns:
        raise TranscriptError("no_turns", "No speaker turns could be read from this transcript.")
    title = clean_title(meeting_title) or parsed.title or clean_title(filename.rsplit(".", 1)[0]) \
        or "Meeting"
    day = meeting_date or parsed.date
    transcript_id = transcript_id_for(org_id, source, source_ref)

    with engine.connect() as c:
        existing = load_row(c, org_id, transcript_id)
        link = link_meeting(c, org_id, seat_email=uploader, meeting_node_id=meeting_node_id,
                            calendar_event_id=calendar_event_id, drive_file_id=drive_file_id,
                            title=title, day=day)
        attendee_emails = link.meeting.attendee_emails if link.meeting else ()
        candidates = load_candidates(c, org_id, attendee_emails, uploader_email=uploader)
    # A person's earlier explicit mapping survives a re-ingest; an explicit new one replaces it.
    carried: dict[str, Candidate | None] = {}
    if existing is not None:
        for entry in (existing.speakers if isinstance(existing.speakers, list)
                      else json.loads(existing.speakers or "[]")):
            if entry.get("match") == "manual":
                carried[entry["label"]] = candidate_from_entry(entry)
    carried.update(manual or {})
    speakers = map_speakers(parsed.labels, candidates, manual=carried or None)
    meeting = link.meeting
    principals = sorted({*attendee_emails, uploader}) if (scope == "attendees" and meeting) \
        else [uploader]
    started_at = meeting.start_at if meeting else None
    ended_at = meeting.end_at if meeting else None
    if meeting and meeting.title:
        title = meeting.title
    rendered = parsed.render()
    content_hash = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    shape = json.dumps({"s": [(s["label"], s["person_node_id"] or s["email"]) for s in speakers],
                        "m": meeting.meeting_node_id if meeting else None, "p": principals},
                       sort_keys=True)
    content_version = content_hash[:16] + "." + hashlib.sha256(shape.encode()).hexdigest()[:12]
    # §3's `meeting`, verbatim — the column group B's follow-up pass reads (§4 pin).
    meeting_obj = {"calendar_event_id": link.calendar_event_id,
                   "meeting_node_id": meeting.meeting_node_id if meeting else None,
                   "title": title, "started_at": _iso(started_at), "ended_at": _iso(ended_at),
                   "candidates": [m.candidate() for m in link.candidates]}
    attendees = _attendee_views(link, candidates)
    if (existing is not None and existing.content_version == content_version
            and existing.status != "failed"):
        return IngestOutcome(transcript=view(existing), duplicate=True, parsed=parsed)

    parts = build_parts(parsed.turns)
    enc = None
    if crypto_key:
        from genios_engine.platform.crypto import encrypt
        enc = encrypt(text_content, crypto_key)
    params = {"t": transcript_id, "o": org_id, "src": source, "ref": source_ref, "fid": file_id,
              "seat": seat_id, "up": uploader, "prov": parsed.provider, "scope": scope,
              "cal": link.calendar_event_id, "mn": meeting.meeting_node_id if meeting else None,
              "title": title, "sa": started_at, "ea": ended_at, "m": json.dumps(meeting_obj),
              "sp": json.dumps(speakers), "att": json.dumps(attendees), "pr": principals,
              "parts": len(parts), "h": content_hash, "cv": content_version, "enc": enc,
              "st": "extracting"}
    with engine.begin() as c:
        c.execute(text(
            "insert into transcripts (transcript_id, org_id, source, source_ref, file_id, seat_id, "
            "uploader_email, provider, scope, calendar_event_id, meeting_node_id, title, "
            "started_at, ended_at, meeting, speakers, attendees, principals, parts, content_hash, "
            "content_version, enc_text, status, error, updated_at) values (:t, :o, :src, :ref, "
            ":fid, :seat, :up, :prov, :scope, :cal, :mn, :title, :sa, :ea, cast(:m as jsonb), "
            "cast(:sp as jsonb), cast(:att as jsonb), cast(:pr as text[]), :parts, :h, :cv, "
            ":enc, :st, null, now()) "
            "on conflict (org_id, source, source_ref) do update set "
            "file_id=coalesce(excluded.file_id, transcripts.file_id), seat_id=excluded.seat_id, "
            "uploader_email=excluded.uploader_email, provider=excluded.provider, "
            "scope=excluded.scope, calendar_event_id=excluded.calendar_event_id, "
            "meeting_node_id=excluded.meeting_node_id, title=excluded.title, "
            "started_at=excluded.started_at, ended_at=excluded.ended_at, "
            "meeting=excluded.meeting, speakers=excluded.speakers, "
            "attendees=excluded.attendees, "
            "principals=excluded.principals, parts=excluded.parts, "
            "content_hash=excluded.content_hash, content_version=excluded.content_version, "
            "enc_text=coalesce(excluded.enc_text, transcripts.enc_text), status=excluded.status, "
            "error=null, updated_at=now()"), params)

    if existing is not None and doors.retire is not None:
        try:
            doors.retire(org_id, transcript_id, content_version)
        except Exception:                          # noqa: BLE001 — retire is a refinement
            _log.exception("transcript retire failed org=%s t=%s", org_id, transcript_id)

    row_obj = {"schema_version": SCHEMA_VERSION, "transcript_id": transcript_id,
               "provider": parsed.provider, "meeting": meeting_obj,
               "speakers": speakers, "scope": scope, "principals": principals,
               "parts": len(parts), "content_hash": content_hash}
    visibility = Visibility(scope=PRIVATE, principals=principals,
                            derived_from=f"transcript:{scope}:{'linked' if meeting else 'unlinked'}")
    occurred = _occurred(started_at, day)
    from genios_engine.capture.intake import ingest_manual
    results = []
    for n, body in enumerate(parts):
        res = ingest_manual(
            org_id=org_id, source=source, object_type=OBJECT_TYPE,
            source_object_id=f"{transcript_id}:part_{n}", body=body, subject=title,
            actor_type="internal_user", actor_email=uploader, occurred_at=occurred,
            raw_extra={"transcript": row_obj, "part": n + 1, "parts": len(parts)},
            content_version=content_version, repo=doors.repo,
            payload_store=doors.payload_store, prepared_store=doors.prepared_store,
            trace_repo=doors.trace_repo, coverage_fn=doors.coverage_fn,
            semantic=doors.semantic, esqe=doors.esqe, connection_id=doors.connection_id,
            visibility=visibility)
        if res is not None:
            results.append(res)
    if results and doors.finalize is not None:
        doors.finalize(results)
    emitted = [r.event.event_id for r in results
               if r.outcome == "emitted" and getattr(r, "event", None) is not None]
    if emitted and doors.enqueue is not None:
        doors.enqueue(emitted)
    # §4 pin: the part events of THIS version — group B's follow-up reads commitments and
    # decisions through them, which is the only way to reach an unlinked transcript's.
    part_ids = list(dict.fromkeys(r.event.event_id for r in results
                                  if getattr(r, "event", None) is not None))
    with engine.begin() as c:
        c.execute(text("update transcripts set event_ids=cast(:e as text[]), updated_at=now() "
                       "where org_id=:o and transcript_id=:t"),
                  {"e": part_ids, "o": org_id, "t": transcript_id})
        row = load_row(c, org_id, transcript_id)
    return IngestOutcome(transcript=view(row), duplicate=False, results=results,
                         emitted_ids=emitted, parsed=parsed)


def set_status(engine, org_id: str, transcript_id: str, status: str,
               error: str | None = None) -> None:
    if status not in STATUSES:
        raise ValueError(status)
    with engine.begin() as c:
        c.execute(text("update transcripts set status=:s, error=:e, updated_at=now() "
                       "where org_id=:o and transcript_id=:t"),
                  {"s": status, "e": error, "o": org_id, "t": transcript_id})


def settle_transcripts(engine, org_id: str, event_ids) -> int:
    """After an L2 drain: every still-`extracting` transcript whose part events the drain touched
    becomes `failed` (a part was PARKED — the drain gave up on it) or `extracted` (every part is
    `done`). Drive transcripts reach `extracted` only this way — the sync door has no background
    wait like the upload door — and group B's follow-up pass acts on `extracted`. Returns rows
    changed. Two indexed statements; a no-op when the drain touched no transcript."""
    ids = sorted({str(e) for e in event_ids if e})
    if not ids:
        return 0
    with engine.begin() as c:
        failed = c.execute(text(
            "update transcripts t set status='failed', updated_at=now(), "
            " error=coalesce((select r.last_error from l2_processing_runs r where r.org_id=t.org_id "
            "  and r.event_id = any(t.event_ids) and r.status='parked' limit 1), 'extraction failed') "
            "where t.org_id=:o and t.status='extracting' and t.event_ids && cast(:ids as text[]) "
            "and exists (select 1 from l2_processing_runs r where r.org_id=t.org_id "
            "  and r.event_id = any(t.event_ids) and r.status='parked')"),
            {"o": org_id, "ids": ids}).rowcount
        done = c.execute(text(
            "update transcripts t set status='extracted', error=null, updated_at=now() "
            "where t.org_id=:o and t.status='extracting' and t.event_ids && cast(:ids as text[]) "
            "and cardinality(t.event_ids) > 0 and not exists (select 1 from unnest(t.event_ids) e "
            "  where not exists (select 1 from l2_processing_runs r where r.org_id=t.org_id "
            "  and r.event_id=e and r.status='done'))"),
            {"o": org_id, "ids": ids}).rowcount
    return int(failed or 0) + int(done or 0)


def event_prefix(source: str, transcript_id: str) -> str:
    """The dedup-key prefix of every part event of a transcript (all content versions)."""
    return f"{source}:{OBJECT_TYPE}:{transcript_id}:"


# ── the connector door (Drive Meet transcript Docs) ────────────────────────────────────────────
_NAME_DAY = re.compile(r"(\d{4})[-/](\d{2})[-/](\d{2})")


def _day_from(name: str, created_at: str | None) -> date | None:
    m = _NAME_DAY.search(name or "")
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    if created_at:
        try:
            return datetime.fromisoformat(str(created_at).replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return None


def transcripts_enabled(engine, org_id: str) -> bool:
    """`capture_policies.transcripts` — the org's opt-in for connector-found transcripts."""
    try:
        with engine.connect() as c:
            return bool(c.execute(text("select transcripts from capture_policies where org_id=:o"),
                                  {"o": org_id}).scalar())
    except Exception:                              # noqa: BLE001 — unknown policy = off
        return False


def ingest_connector_transcript(raw, *, org_id: str, connection_id: str, repo,
                                payload_store=None, prepared_store=None, trace_repo=None,
                                coverage_fn=None, semantic=None, esqe=None,
                                engine=None) -> list:
    """A Drive `gmeet_transcript` object → transcript parts, or nothing. Returns the part
    results for the sweep to tally and finalize; [] when the org has not opted in, the export is
    empty, or there is no database. Never routes the Doc through the generic ORG path."""
    from genios_engine.platform.config import get_settings
    s = get_settings()
    if engine is None:
        if not s.use_real_db:
            return []
        from genios_engine.platform.db import get_engine
        engine = get_engine(s.database_url)
    if not transcripts_enabled(engine, org_id):
        _log.info("drive transcript skipped: org=%s has transcripts off", org_id)
        return []
    body = raw.raw or {}
    export = body.get("transcript_export") or {}
    content = str(export.get("text") or "")
    owner = (raw.actor_email or export.get("owner_email") or "").strip().lower()
    file_id = str(export.get("file_id") or raw.source_object_id)
    if not content.strip() or "@" not in owner:
        return []
    with engine.connect() as c:
        seat = c.execute(text("select seat_id from org_seats where org_id=:o and active "
                              "and lower(email)=:e limit 1"), {"o": org_id, "e": owner}).scalar()
    name = str(export.get("name") or body.get("subject") or "")
    try:
        out = ingest_transcript(
            engine, org_id=org_id, text_content=content, source=raw.source, source_ref=file_id,
            uploader_email=owner, seat_id=seat, provider_hint="gmeet", filename=name,
            drive_file_id=file_id, meeting_title=name,
            meeting_date=_day_from(name, export.get("created_at")), scope="attendees",
            doors=TranscriptDoors(repo=repo, payload_store=payload_store,
                                  prepared_store=prepared_store, trace_repo=trace_repo,
                                  coverage_fn=coverage_fn, semantic=semantic, esqe=esqe,
                                  connection_id=connection_id),
            crypto_key=s.crypto_key or None)
    except TranscriptError as exc:
        _log.info("drive transcript not ingested org=%s file=%s: %s", org_id, file_id, exc.code)
        return []
    return list(out.results)


__all__ = ["DRIVE_OBJECT_TYPE", "IngestOutcome", "OBJECT_TYPE", "PART_MAX_CHARS", "SCOPES",
           "TranscriptDoors", "TranscriptError", "build_parts", "event_prefix",
           "ingest_connector_transcript", "ingest_transcript", "load_row", "may_read",
           "set_status", "transcript_id_for", "transcripts_enabled", "view", "visible_rows"]
