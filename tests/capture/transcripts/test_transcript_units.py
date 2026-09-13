"""P5 group A · hermetic units: every export format parses, speaker mapping never guesses
outside the meeting, parts are turn-bounded, and the routing/profile/Drive seams line up."""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from genios_engine.capture.transcripts.ingest import (DRIVE_OBJECT_TYPE, OBJECT_TYPE,
                                                      PART_MAX_CHARS, build_parts)
from genios_engine.capture.transcripts.parse import (Turn, clean_title,
                                                     decode_transcript_bytes, parse_transcript)
from genios_engine.capture.transcripts.speakers import Candidate, map_speakers, resolve_label

FX = Path(__file__).parent / "fixtures"


def _p(name: str, **kw):
    return parse_transcript((FX / name).read_text(encoding="utf-8"), filename=name, **kw)


# ── parsers: ≥ 95 % of dialogue lines attributed, per format ─────────────────────────────────
@pytest.mark.parametrize("name,provider,labels", [
    ("meet_iso_audit.txt", "gmeet",
     ("Rohit Mehta", "Emru Khan", "Shalini Iyer", "Priya Shah")),
    ("teams.vtt", "teams", ("Rohit Mehta", "Shalini Iyer", "Emru Khan")),
    ("zoom.vtt", "zoom", ("Rohit Mehta", "Shalini Iyer", "Priya Shah")),
    ("call.srt", "other", ("Rohit Mehta", "Shalini Iyer", "Emru Khan")),
    ("otter.txt", "otter", ("Rohit Mehta", "Shalini Iyer", "Emru Khan")),
    ("fireflies.txt", "fireflies", ("Rohit Mehta", "Shalini Iyer", "Priya Shah")),
    ("granola.txt", "granola", ("Me", "Them")),
])
def test_every_format_attributes_its_lines(name, provider, labels):
    p = _p(name, provider_hint="granola" if name == "granola.txt" else None)
    assert p.provider == provider
    assert p.labels == labels
    assert p.attribution_bp >= 9500, (p.content_lines, p.attributed_lines)


def test_meet_doc_metadata_and_turns():
    p = _p("meet_iso_audit.txt")
    assert p.title == "ISO audit prep – Voltex"
    assert p.date.isoformat() == "2026-09-14"
    assert p.attendees == ("Emru Khan", "Rohit Mehta", "Priya Shah", "Shalini Iyer")
    assert len(p.turns) == 9 and p.turns[2].speaker == "Shalini Iyer"
    assert p.turns[0].start_ms == 4000
    assert "supplier quality records" in p.turns[2].text


def test_multiline_cues_and_continuations_join_their_speaker():
    srt = _p("call.srt")
    assert srt.turns[1].text.endswith("by Wednesday the 17th.")
    otter = _p("otter.txt")
    assert otter.turns[1].speaker == "Shalini Iyer"
    assert "supplier quality records" in otter.turns[1].text
    teams = _p("teams.vtt")                      # consecutive same-speaker cues merge
    assert teams.turns[-1].text.endswith("Everyone gets it.")


def test_a_line_before_any_speaker_is_never_given_one():
    p = parse_transcript("Some preamble line\nstray words, no speaker\nRohit: hello there")
    assert p.turns[0].speaker == "" and p.turns[-1].speaker == "Rohit"
    assert p.render().startswith("unknown: ")


def test_docx_goes_through_the_native_reader():
    docx = pytest.importorskip("docx")
    d = docx.Document()
    d.add_paragraph("Rohit Mehta: Okay, let's start.")
    d.add_paragraph("Emru Khan: I will send the audit checklist by Friday.")
    buf = io.BytesIO()
    d.save(buf)
    text = decode_transcript_bytes(buf.getvalue(), filename="call.docx")
    assert parse_transcript(text).labels == ("Rohit Mehta", "Emru Khan")


def test_vtt_bytes_decode_to_text_not_nothing():
    raw = (FX / "zoom.vtt").read_bytes()
    assert "Shalini Iyer:" in decode_transcript_bytes(raw, filename="zoom.vtt")


def test_clean_title_drops_the_meet_suffix_and_date():
    assert clean_title("Acme review (2026-09-14 10:00 GMT+5:30) - Transcript") == "Acme review"


# ── speaker mapping: attendees + uploader only ───────────────────────────────────────────────
ATT = [Candidate(email="rohit@voltex.in", name="Rohit Mehta", person_node_id="n_r"),
       Candidate(email="shalini.iyer@voltex.in", name=None, person_node_id="n_s"),
       Candidate(email="emru@voltex.in", name="Emru Khan", aliases=("emru k",)),
       Candidate(email="priya@acme.io", name="Priya Shah", person_node_id="n_p"),
       Candidate(email="me@voltex.in", name="Harsh T", is_uploader=True)]


@pytest.mark.parametrize("label,email,match", [
    ("Rohit Mehta", "rohit@voltex.in", "name"),
    ("Shalini Iyer", "shalini.iyer@voltex.in", "name"),      # local-part name, same attendee
    ("emru k", "emru@voltex.in", "name"),                   # an alias
    ("Priya", "priya@acme.io", "first_name"),
    ("Priya S.", "priya@acme.io", "first_name"),
    ("priya@acme.io", "priya@acme.io", "email"),
    ("Me", "me@voltex.in", "self"),
    ("You", "me@voltex.in", "self"),
    ("Priya Kapoor", None, "unknown"),                      # not the attendee Priya
    ("Anisha", None, "unknown"),                            # an org name, not an attendee
    ("anisha@voltex.in", None, "unknown"),                  # an address outside the meeting
    ("Speaker 3", None, "unknown"),
])
def test_resolve_label(label, email, match):
    cand, got = resolve_label(label, ATT)
    assert got == match
    assert (cand.email if cand else None) == email


def test_an_ambiguous_first_name_resolves_to_nobody():
    two = ATT + [Candidate(email="rohit.s@voltex.in", name="Rohit Sharma")]
    assert resolve_label("Rohit", two) == (None, "unknown")


def test_manual_mapping_wins_and_null_clears():
    out = map_speakers(["Anisha", "Rohit Mehta"], ATT,
                       manual={"Anisha": Candidate(email="anisha@voltex.in"),
                               "Rohit Mehta": None})
    assert out[0]["match"] == "manual" and out[0]["email"] == "anisha@voltex.in"
    assert out[1] == {"label": "Rohit Mehta", "email": None, "person_node_id": None,
                      "seat_id": None, "match": "manual"}


# ── parts ────────────────────────────────────────────────────────────────────────────────────
def test_parts_split_on_turn_boundaries_with_a_context_tail():
    turns = [Turn(speaker=f"S{i % 3}", text=("word " * 400).strip()) for i in range(20)]
    parts = build_parts(turns)
    assert len(parts) > 1
    for body in parts:
        new = body.split("\n\ncontext — do not extract\n", 1)[0]
        assert len(new) <= PART_MAX_CHARS
        assert all(ln.split(":", 1)[0] in ("S0", "S1", "S2") for ln in new.splitlines())
    assert "context — do not extract" not in parts[0]
    ctx = parts[1].split("context — do not extract\n", 1)[1]
    assert all(ln.startswith("> ") for ln in ctx.splitlines())
    assert max(len(b) for b in parts) < 16_000      # fits the transcript profile in one call


def test_a_monster_turn_is_split_and_keeps_its_speaker():
    parts = build_parts([Turn(speaker="Emru Khan", text="A sentence here. " * 2000)])
    assert len(parts) > 1
    assert all(p.startswith("Emru Khan: ") for p in parts)


# ── seams ────────────────────────────────────────────────────────────────────────────────────
def test_routing_and_profile():
    """Routing + the speaker rule. The tier (T1 / 16k, eval-gated) is pinned in its own commit by
    test_profiles / test_batch, so reverting that commit leaves this test green."""
    from genios_engine.capture.semantic.profiles import get_profile
    from genios_engine.capture.semantic.router import RoutingInput, select_profile
    for source, ot in (("upload", OBJECT_TYPE), ("gdrive", OBJECT_TYPE),
                       ("gdrive", "gmeet_transcript"), ("zoom", "zoom_transcript"),
                       ("teams", "msteams_transcript")):
        assert select_profile(RoutingInput(source=source, object_type=ot)).profile_id == "transcript"
    prof = get_profile("transcript")
    assert prof.max_input_chars >= 16_000             # a full part + context fits one call
    assert "speaker label before the colon" in prof.prompt_template


def test_drive_transcript_doc_is_exported_and_carries_no_body():
    from genios_engine.capture.connectors import drive as DR
    assert DR.MEET_TRANSCRIPT_OBJECT_TYPE == DRIVE_OBJECT_TYPE
    calls = []

    class X:
        def execute(self, action, args):
            calls.append((action, args))
            return {"content": "Rohit Mehta: hi\nEmru Khan: I will send it."}
    c = DR.ComposioDriveConnector.__new__(DR.ComposioDriveConnector)
    c._x, c._ocr = X(), None
    raw = c._to_raw({"id": "f1", "name": "ISO audit prep (2026-09-14) - Transcript",
                     "mimeType": DR.GOOGLE_DOC_MIME, "modifiedTime": "2026-09-14T11:00:00Z",
                     "owners": [{"emailAddress": "Rohit@Voltex.in"}]})
    assert calls == [(DR.DOC_TEXT_EXPORT["action"],
                      {"mime_type": "text/plain", "file_id": "f1"})]
    assert raw.object_type == DRIVE_OBJECT_TYPE and raw.raw["body"] == ""
    assert raw.raw["transcript_export"]["text"].startswith("Rohit Mehta:")
    assert raw.actor_email == "rohit@voltex.in"
    # an ordinary Doc is not a transcript
    assert not DR.is_meet_transcript({"mimeType": DR.GOOGLE_DOC_MIME, "name": "Q3 plan"})


def test_calendar_carries_attachments_and_conference_id():
    from genios_engine.capture.connectors.calendar import ComposioCalendarConnector
    c = ComposioCalendarConnector.__new__(ComposioCalendarConnector)
    c._internal_emails = None
    raw = c._to_raw({"id": "e1", "summary": "ISO audit prep",
                     "start": {"dateTime": "2026-09-14T10:00:00Z"},
                     "conferenceData": {"conferenceId": "abc-defg-hij"},
                     "attachments": [{"fileId": "f1", "title": "Transcript"},
                                     {"fileId": "f2", "title": "Notes"}]})
    assert raw.raw["conferenceId"] == "abc-defg-hij"
    assert raw.raw["attachment_file_ids"] == "f1,f2"


def test_gdrive_polls_hourly():
    from genios_engine.capture.acquire.cadence import DEFAULT_CADENCE_POLICY
    assert {e.source: e.interval_seconds for e in DEFAULT_CADENCE_POLICY.entries}["gdrive"] == 3600
