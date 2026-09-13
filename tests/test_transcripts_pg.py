"""P5 group A against real Postgres — owners, privacy, idempotency.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://localhost/genios_p5_a pytest tests/test_transcripts_pg.py

The transcript goes through the REAL ingest door (`ingest_transcript` → `ingest_manual` → PG
source events + encrypted payloads), and Layer 2 runs the REAL `process_event` on the stored
payload, with the model's answer supplied as a qualified extraction (no key in tests) — so every
owner, edge and audience below is what the pipeline itself wrote.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text

URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
pytestmark = [pytest.mark.pg,
              pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")]

FIXTURE = Path(__file__).parent / "capture/transcripts/fixtures/meet_iso_audit.txt"
START = datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)
PEOPLE = {"rohit": "Rohit Mehta", "shalini.iyer": "Shalini Iyer", "emru": "Emru Khan",
          "priya": "Priya Shah"}


def _engine():
    from genios_engine.platform.db import get_engine
    return get_engine(URL)


def _store():
    from genios_engine.context.graph_store import GraphStore
    return GraphStore(URL)


def _org():
    """An org, a seat per attendee, an OUTSIDER seat, and a calendar meeting they attended."""
    org = f"org_p5_{uuid.uuid4().hex[:8]}"
    dom = f"{org}.test"
    emails = {k: f"{k}@{dom}" for k in PEOPLE}
    outsider = f"anisha@{dom}"
    with _engine().begin() as c:
        reqd = c.execute(text(
            "select column_name, data_type from information_schema.columns "
            "where table_name='orgs' and is_nullable='NO' and column_default is null "
            "and column_name<>'id'")).all()
        cols, vals = ["id"], {"id": org}
        for r in reqd:
            cols.append(r.column_name)
            dt = r.data_type
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                                   else 0 if ("int" in dt or "numeric" in dt) else False
                                   if dt == "boolean" else "{}" if dt in ("json", "jsonb")
                                   else f"x_{org}")
        c.execute(text(f"insert into orgs ({', '.join(cols)}) values "
                       f"({', '.join(':' + x for x in cols)})"), vals)
        c.execute(text("update orgs set timezone='UTC' where id=:o"), {"o": org})
        for k, e in [*emails.items(), ("anisha", outsider)]:
            c.execute(text("insert into org_seats (org_id, seat_id, email) values (:o, :s, :e)"),
                      {"o": org, "s": f"seat_{k}_{org}", "e": e})
    store = _store()
    with store.engine.begin() as c:
        meeting = store.find_or_create_node(c, org_id=org, node_type="meeting",
                                            canonical_key="gcal:ev_iso", event_id="ev_cal",
                                            display_name="ISO audit prep – Voltex")
        for fld, val in (("meeting.start_at", START.isoformat()),
                         ("meeting.title", "ISO audit prep – Voltex")):
            store.write_fact(c, org_id=org, subject_node_id=meeting, field=fld, value=val,
                             value_type="string", confidence=0.9, occurred_at=START,
                             event_id="ev_cal", evidence={}, source="gcal", authority_rank=3)
        nodes = {}
        for k, name in PEOPLE.items():
            nodes[k] = store.find_or_create_node(c, org_id=org, node_type="person",
                                                 canonical_key=emails[k], display_name=name,
                                                 event_id="ev_cal")
            store.write_edge(c, org_id=org, edge_type="attended", from_node_id=nodes[k],
                             to_node_id=meeting, confidence=1.0, occurred_at=START,
                             event_id="ev_cal", evidence={}, source="gcal")
    return SimpleNamespace(org=org, emails=emails, outsider=outsider, meeting=meeting,
                           nodes=nodes, store=store, seat=lambda k: f"seat_{k}_{org}")


def _doors():
    from genios_engine.capture.transcripts.ingest import TranscriptDoors
    from genios_engine.platform.wiring import make_payload_store, make_prepared_store, make_repo
    return TranscriptDoors(repo=make_repo(), payload_store=make_payload_store(),
                           prepared_store=make_prepared_store(), connection_id="upload")


def _ingest(o, text_content, *, uploader="rohit", **kw):
    from genios_engine.capture.transcripts.ingest import ingest_transcript
    from genios_engine.platform.config import get_settings
    return ingest_transcript(_engine(), org_id=o.org, text_content=text_content,
                             source="upload", source_ref=kw.pop("ref", uuid.uuid4().hex),
                             uploader_email=o.emails.get(uploader, uploader),
                             seat_id=o.seat(uploader), doors=_doors(),
                             crypto_key=get_settings().crypto_key, **kw)


def _raw(event_id):
    from genios_engine.platform.config import get_settings
    from genios_engine.platform.crypto import decrypt
    with _engine().connect() as c:
        enc = c.execute(text("select enc_content from raw_payloads where event_id=:e"),
                        {"e": event_id}).scalar()
    return json.loads(decrypt(bytes(enc), get_settings().crypto_key))


def _l2(o, event_id, commitments, sender):
    """Layer 2 on the stored payload, the model's answer given as the qualified extraction."""
    from genios_engine.context.extract.extractor import Extraction
    from genios_engine.context.pipeline import process_event
    raw = _raw(event_id)
    ex = Extraction(relevance=0.9, noise_type="none", domains=[], entity_mentions=[],
                    fact_candidates=[], commitments=commitments, questions=[], observations=[])
    return process_event(org_id=o.org, event_id=event_id, source="upload", content=raw["body"],
                         sender_email=sender, occurred_at=START, llm=None, store=o.store,
                         canon_meta=raw, qualified_extraction=ex)


def _cm(actor, action, quote, due=None):
    return {"actor": actor, "action": action, "due_text": due, "is_conditional": False,
            "condition_text": None, "evidence_text": quote}


def _commitments(o, event_ids):
    """(owner email, commitment node, text, due) for every commitment these events created."""
    with _engine().connect() as c:
        rows = c.execute(text(
            "select p.canonical_key as owner, n.node_id, "
            " (select f.value from graph_facts f where f.org_id=n.org_id and "
            "  f.subject_node_id=n.node_id and f.field='commitment.text' and f.valid_to is null "
            "  limit 1) as txt, "
            " (select f.value from graph_facts f where f.org_id=n.org_id and "
            "  f.subject_node_id=n.node_id and f.field='commitment.due_at' and f.valid_to is null "
            "  limit 1) as due "
            "from graph_nodes n join graph_edges e on e.org_id=n.org_id and e.to_node_id=n.node_id "
            " and e.edge_type='owns' and e.valid_to is null "
            "join graph_nodes p on p.org_id=n.org_id and p.node_id=e.from_node_id "
            "where n.org_id=:o and n.node_type='commitment' and n.created_by_event_id = any(:e)"),
            {"o": o.org, "e": list(event_ids)}).fetchall()
    return rows


FIXTURE_CMS = [
    _cm("Shalini Iyer", "prepare the supplier quality records",
        "I'll prepare the supplier quality records by Wednesday the 17th.",
        "2026-09-17T00:00:00+00:00"),
    _cm("Emru Khan", "send the audit checklist to everyone",
        "I will send the audit checklist to everyone by Friday.", "2026-09-18T00:00:00+00:00"),
    # UNDATED on purpose: the model returned no due bound — the promise must still be kept.
    _cm("Priya Shah", "share the signed delivery logs",
        "we will share the signed delivery logs by Thursday so you have them for the audit."),
]


def test_owners_are_the_speakers_never_the_uploader_and_undated_is_kept():
    o = _org()
    out = _ingest(o, FIXTURE.read_text())
    t = out.transcript
    assert t["meeting"]["meeting_node_id"] == o.meeting            # linked by title + day
    assert t["principals"] == sorted(o.emails.values())
    assert {s["label"]: s["match"] for s in t["speakers"]} == {
        "Rohit Mehta": "name", "Emru Khan": "name", "Shalini Iyer": "name",
        "Priya Shah": "name"}
    assert {a["email"] for a in t["attendees"]} == set(o.emails.values())
    assert len(out.emitted_ids) == 1 and t["parts"] == 1
    with _engine().connect() as c:
        ev = c.execute(text("select object_type, visibility_scope, visibility_principals "
                            "from source_events where event_id=:e"),
                       {"e": out.emitted_ids[0]}).first()
        assert c.execute(text("select event_ids from transcripts where transcript_id=:t"),
                         {"t": t["transcript_id"]}).scalar() == out.emitted_ids
    assert ev.object_type == "meeting_transcript" and ev.visibility_scope == "private"
    assert sorted(ev.visibility_principals) == sorted(o.emails.values())

    # the uploader (Rohit) sends; a promise with an actor nobody said must not land on him
    res = _l2(o, out.emitted_ids[0],
              FIXTURE_CMS + [_cm("Anisha", "cover the document pack",
                                 "her part of the document pack needs an owner.")],
              sender=o.emails["rohit"])
    assert res.outcome != "extract_failed"
    rows = _commitments(o, out.emitted_ids)
    owners = {r.owner: r for r in rows}
    assert set(owners) == {o.emails["shalini.iyer"], o.emails["emru"], o.emails["priya"]}
    assert o.emails["rohit"] not in owners                           # never the uploader
    assert owners[o.emails["priya"]].due is None                    # undated, still a commitment
    assert "delivery logs" in str(owners[o.emails["priya"]].txt)
    assert owners[o.emails["shalini.iyer"]].due is not None
    with _engine().connect() as c:
        raised = c.execute(text(
            "select count(*) from graph_edges where org_id=:o and edge_type='raised_in' "
            "and to_node_id=:m and valid_to is null and from_node_id = any(:n)"),
            {"o": o.org, "m": o.meeting, "n": [r.node_id for r in rows]}).scalar()
        facts = c.execute(text(
            "select field, visibility_scope, visibility_principals from graph_facts "
            "where org_id=:o and field like 'commitment.%' and valid_to is null "
            "and created_by_event_id = any(:e)"), {"o": o.org, "e": out.emitted_ids}).fetchall()
    assert raised == 3
    # work facts of a transcript keep the meeting's audience (strict private evidence)
    assert facts and all(f.visibility_scope == "private" for f in facts)
    assert all(sorted(f.visibility_principals) == sorted(o.emails.values()) for f in facts)
    assert {"commitment.owner", "commitment.text", "commitment.status"} <= {f.field for f in facts}


def test_unknown_speaker_gets_no_owner_until_a_person_maps_it(monkeypatch):
    o = _org()
    body = ("Title: ISO audit prep – Voltex\nDate: 2026-09-14\n\n"
            "Rohit Mehta: Can someone take the minutes?\n"
            "Speaker 3: I'll circulate the minutes by Monday.\n")
    out = _ingest(o, body)
    spk = {s["label"]: s for s in out.transcript["speakers"]}
    assert spk["Speaker 3"]["match"] == "unknown" and spk["Speaker 3"]["person_node_id"] is None
    _l2(o, out.emitted_ids[0],
        [_cm("Speaker 3", "circulate the minutes", "I'll circulate the minutes by Monday.")],
        sender=o.emails["rohit"])
    assert _commitments(o, out.emitted_ids) == []                    # no owner, no guess

    # PUT /speakers: a person maps the label (by email, then by node id) → a new content version
    client = _client(o, monkeypatch, seat="rohit")
    r = client.put(f"/v1/transcripts/{out.transcript['transcript_id']}/speakers",
                   json={"Speaker 3": o.emails["emru"]})
    assert r.status_code == 200, r.text
    got = {s["label"]: s for s in r.json()["speakers"]}["Speaker 3"]
    assert got["match"] == "manual" and got["person_node_id"] == o.nodes["emru"]
    r2 = client.put(f"/v1/transcripts/{out.transcript['transcript_id']}/speakers",
                    json={"Speaker 3": o.nodes["shalini.iyer"]})
    assert {s["label"]: s for s in r2.json()["speakers"]}["Speaker 3"]["email"] \
        == o.emails["shalini.iyer"]
    assert client.put(f"/v1/transcripts/{out.transcript['transcript_id']}/speakers",
                      json={"Nobody": None}).status_code == 422
    with _engine().connect() as c:
        versions = c.execute(text(
            "select count(*) from source_events where org_id=:o and dedup_key like :p"),
            {"o": o.org, "p": f"%:meeting_transcript:{out.transcript['transcript_id']}:%"}).scalar()
    assert versions == 3                                             # one per content version


def _client(o, monkeypatch, *, seat):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from genios_engine.api import transcript_routes as TR
    from genios_engine.api import upload_routes as U
    monkeypatch.setattr(TR, "principal", lambda request, dstore: SimpleNamespace(
        org_id=o.org, seat_id=o.seat(seat), email=o.emails.get(seat, o.outsider)))
    monkeypatch.setattr(TR.D, "stores", lambda: (None, SimpleNamespace(engine=_engine())))
    monkeypatch.setattr(U, "_run_chain_for_upload", lambda *a, **k: None)
    app = FastAPI()
    app.include_router(TR.router)
    app.include_router(U.router)
    return TestClient(app)


def test_a_non_attendee_sees_nothing_and_the_api_shapes_hold(monkeypatch):
    o = _org()
    out = _ingest(o, FIXTURE.read_text())
    tid = out.transcript["transcript_id"]
    outsider = _client(o, monkeypatch, seat="anisha")
    assert outsider.get("/v1/transcripts").json() == {"transcripts": []}
    assert outsider.get(f"/v1/transcripts/{tid}").status_code == 404
    assert outsider.put(f"/v1/transcripts/{tid}/speakers",
                        json={"Rohit Mehta": None}).status_code == 404
    assert outsider.get("/v1/meetings/recent", params={"date": "2026-09-14"}).json() \
        == {"meetings": []}

    attendee = _client(o, monkeypatch, seat="priya")
    listed = attendee.get("/v1/transcripts").json()["transcripts"]
    assert [x["transcript_id"] for x in listed] == [tid]
    one = attendee.get(f"/v1/transcripts/{tid}").json()
    assert set(one) >= {"schema_version", "transcript_id", "provider", "meeting", "speakers",
                        "attendees", "scope", "principals", "parts", "content_hash", "status"}
    assert set(one["meeting"]) == {"calendar_event_id", "meeting_node_id", "title",
                                   "started_at", "ended_at", "candidates"}
    assert all(set(a) == {"name", "email", "person_node_id"} for a in one["attendees"])
    meetings = attendee.get("/v1/meetings/recent", params={"date": "2026-09-14"}).json()
    assert [m["meeting_node_id"] for m in meetings["meetings"]] == [o.meeting]
    m = meetings["meetings"][0]
    assert set(m) == {"meeting_node_id", "calendar_event_id", "title", "start_at", "end_at",
                      "attendees"} and m["calendar_event_id"] == "ev_iso"
    assert {a["email"] for a in m["attendees"]} == set(o.emails.values())
    assert attendee.get("/v1/meetings/recent", params={"q": "nomatch",
                                                       "date": "2026-09-14"}).json() \
        == {"meetings": []}

    # the facts an outsider's surfaces read: none of the transcript's are readable by them
    from genios_engine.context.fact_visibility import viewer_may_read
    _l2(o, out.emitted_ids[0], FIXTURE_CMS, sender=o.emails["rohit"])
    with _engine().connect() as c:
        facts = c.execute(text(
            "select visibility_scope, visibility_principals from graph_facts where org_id=:o "
            "and created_by_event_id = any(:e) and valid_to is null"),
            {"o": o.org, "e": out.emitted_ids}).fetchall()
    assert facts
    assert not any(viewer_may_read(f.visibility_scope, f.visibility_principals, o.outsider)
                   for f in facts if f.visibility_scope == "private")
    assert all(f.visibility_scope == "private" for f in facts)


def test_reupload_is_idempotent_and_meeting_node_id_wins(monkeypatch):
    o = _org()
    client = _client(o, monkeypatch, seat="shalini.iyer")
    from genios_engine.api import upload_routes as U
    from genios_engine.platform.auth import AuthCtx
    client.app.dependency_overrides[U._upload_ctx] = lambda org_id: AuthCtx(
        org_id=o.org, seat_id=o.seat("shalini.iyer"), role="member",
        email=o.emails["shalini.iyer"])
    form = {"kind": "transcript", "meeting_node_id": o.meeting,
            "meeting_title": "a title that matches nothing", "meeting_date": "2020-01-01"}
    files = {"file": ("iso.txt", FIXTURE.read_bytes(), "text/plain")}
    r1 = client.post(f"/api/org/{o.org}/upload", data=form, files=files)
    assert r1.status_code == 200, r1.text
    b1 = r1.json()
    assert b1["kind"] == "transcript" and b1["scope"] == "attendees" and not b1["duplicate"]
    assert b1["transcript"]["meeting"]["meeting_node_id"] == o.meeting
    assert b1["transcript"]["status"] in ("extracting", "extracted")

    def events():
        with _engine().connect() as c:
            return c.execute(text("select count(*) from source_events where org_id=:o "
                                  "and object_type='meeting_transcript'"), {"o": o.org}).scalar()
    before = events()
    r2 = client.post(f"/api/org/{o.org}/upload", data=form,
                     files={"file": ("iso.txt", FIXTURE.read_bytes(), "text/plain")})
    b2 = r2.json()
    assert b2["duplicate"] is True and b2["file_id"] == b1["file_id"]
    assert b2["transcript"]["transcript_id"] == b1["transcript"]["transcript_id"]
    assert events() == before                                        # nothing new landed
    with _engine().connect() as c:
        n = c.execute(text("select count(*) from transcripts where org_id=:o"),
                      {"o": o.org}).scalar()
        kind = c.execute(text("select kind, scope from resource_uploads where file_id=:f"),
                         {"f": b1["file_id"]}).first()
    assert n == 1 and tuple(kind) == ("transcript", "attendees")
    # a company scope is refused for a transcript
    bad = client.post(f"/api/org/{o.org}/upload", data={**form, "scope": "company"},
                      files={"file": ("x.txt", b"A: hi", "text/plain")})
    assert bad.status_code == 422


def test_drive_transcripts_settle_to_extracted_or_failed_after_the_drain():
    """The sync door has no background wait: the L2 drain's ledger settles the status."""
    from genios_engine.capture.transcripts.ingest import settle_transcripts
    from genios_engine.context.runner import _MAX_ATTEMPTS, _record_done, _record_failure
    o = _org()
    body = FIXTURE.read_text()
    ok = _ingest(o, body, ref="drive_file_ok")
    bad = _ingest(o, body.replace("Okay, let's start.", "Right, let's begin."), ref="drive_file_bad")
    assert ok.transcript["status"] == bad.transcript["status"] == "extracting"
    for e in ok.emitted_ids:
        _record_done(o.store, o.org, e)
    for _ in range(_MAX_ATTEMPTS):
        _record_failure(o.store, o.org, bad.emitted_ids[0], "model unavailable")
    assert settle_transcripts(_engine(), o.org, ok.emitted_ids + bad.emitted_ids) == 2
    with _engine().connect() as c:
        rows = dict(c.execute(text("select transcript_id, status || ':' || coalesce(error, '') "
                                   "from transcripts where org_id=:o"), {"o": o.org}).fetchall())
    assert rows[ok.transcript["transcript_id"]] == "extracted:"
    assert rows[bad.transcript["transcript_id"]] == "failed:model unavailable"
    assert settle_transcripts(_engine(), o.org, ok.emitted_ids) == 0      # settled once


def test_personal_scope_is_private_to_the_uploader_alone():
    o = _org()
    out = _ingest(o, FIXTURE.read_text(), scope="personal")
    assert out.transcript["meeting"]["meeting_node_id"] == o.meeting   # still linked
    assert out.transcript["principals"] == [o.emails["rohit"]]
    from genios_engine.capture.transcripts.ingest import visible_rows
    with _engine().connect() as c:
        assert visible_rows(c, o.org, o.emails["priya"]) == []
        assert len(visible_rows(c, o.org, o.emails["rohit"])) == 1
