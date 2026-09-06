"""L1.3.4-U3 · Speech-to-Text — the seam, tested; the provider, DESCOPED.

**This unit has no input source and that is deliberate, not an oversight.** doc-01 lists its
connector as priority **P5 · Voice / transcripts** and P5 appears in no wave of doc-09's build
order, so nothing in this repo can hand `transcribe_media` a real recording. Wiring a
transcription provider would buy a monthly bill for an unreachable path. doc-04 set the
precedent for exactly this shape — the `chat` and `transcript` extraction profiles are *"written
and unit-tested against synthetic fixtures so the registry is complete and the code path
exists"* while their connectors are unbuilt — and these tests follow it: everything below runs
against `FakeSpeechEngine`, and the fake is not standing in for a real engine elsewhere.

What is genuinely delivered, and is worth having before P5 lands:

* audio arriving **today** (a voice memo attached to an email is not hypothetical) parks as
  `transcription_unavailable` instead of being mislabelled `unsupported` — the same
  empty-with-a-true-reason rule U2 enforces, one medium over;
* doc-03's named failure mode is implemented rather than deferred: *diarization errors attribute
  a commitment to the wrong person*, mitigated by a below-threshold speaker becoming `unknown`
  rather than a guess. A commitment filed against the wrong human is acted on. An unattributed
  one is not, and that asymmetry is the entire argument.
"""
from __future__ import annotations

import pytest

from genios_engine.capture.documents.base import (SPEAKER_MIN_CONFIDENCE_BP, UNKNOWN_SPEAKER,
                                                  DocumentStatus)
from genios_engine.capture.documents.fake import FakeSpeechEngine
from genios_engine.capture.documents.transcript import (TranscriptSegment, is_audio,
                                                        render_transcript, transcribe_media)


@pytest.mark.parametrize("mime, filename, expected", [
    ("audio/mpeg",               "call.mp3",  True),
    ("video/mp4",                "demo.mp4",  True),
    ("audio/x-m4a; codecs=aac",  "vm.m4a",    True),
    ("application/octet-stream", "memo.m4a",  True),    # Gmail's mime for a voice memo
    ("application/octet-stream", "notes.zip", False),
    ("application/pdf",          "deck.pdf",  False),
    ("",                         "",          False),
])
def test_a_recording_is_recognised_by_mime_or_by_extension(mime, filename, expected):
    assert is_audio(mime, filename) is expected


@pytest.mark.parametrize("media_ref, engine, status, detail_contains", [
    ("meeting-1",       None,                DocumentStatus.TRANSCRIPTION_UNAVAILABLE.value,
     "P5"),
    ("raise:meeting-1", FakeSpeechEngine(),  DocumentStatus.TRANSCRIPTION_FAILED.value,
     "provider unavailable"),
    ("silent:meeting",  FakeSpeechEngine(),  DocumentStatus.TRANSCRIPTION_FAILED.value,
     "no usable segments"),
    ("meeting-1",       FakeSpeechEngine(),  DocumentStatus.ACCEPTED.value, None),
])
def test_every_ending_names_itself_and_none_of_them_is_a_bare_empty_string(
        media_ref, engine, status, detail_contains):
    r = transcribe_media(media_ref=media_ref, engine=engine)
    assert r.status == status
    if status == DocumentStatus.ACCEPTED.value:
        assert r.text and r.detail is None
    else:
        assert r.text == "" and detail_contains in (r.detail or "")


def test_the_transcript_carries_speakers_and_timestamps():
    r = transcribe_media(media_ref="meeting-1", engine=FakeSpeechEngine())
    assert r.text.splitlines() == [
        "[00:00:00] Rohit: We will send the signed contract by Friday.",
        "[00:00:04] Priya: Finance still needs to approve the increase.",
    ]
    assert r.engine == "fake-speech" and r.unattributed_segments == 0


def test_replay_reads_the_same_transcript_rather_than_re_transcribing():
    """doc-03: *"output persisted and hashed exactly like any other extraction so replay reads
    the transcript, never re-transcribes."* That only holds if two runs render byte-identically,
    so the hash is over the rendered text and the rendering is deterministic."""
    a = transcribe_media(media_ref="meeting-1", engine=FakeSpeechEngine())
    b = transcribe_media(media_ref="meeting-1", engine=FakeSpeechEngine())
    assert a.content_hash == b.content_hash and len(a.content_hash) == 64
    assert a.text == b.text


def test_an_unsure_speaker_becomes_unknown_rather_than_a_guess():
    """The mitigation for the failure mode doc-03 names. A wrong attribution is acted on."""
    r = transcribe_media(media_ref="unsure:meeting", engine=FakeSpeechEngine())
    assert r.status == DocumentStatus.ACCEPTED.value
    assert r.text == "[00:00:00] unknown: We will send the signed contract by Friday."
    assert r.unattributed_segments == 1
    # the engine's own claim survives for anyone auditing the demotion
    assert r.segments[0].speaker == "Rohit" and r.segments[0].speaker_confidence_bp == 3_100


@pytest.mark.parametrize("confidence_bp, expected", [
    (10_000, "Rohit"),
    (SPEAKER_MIN_CONFIDENCE_BP, "Rohit"),                    # the floor is inclusive
    (SPEAKER_MIN_CONFIDENCE_BP - 1, UNKNOWN_SPEAKER),
    (0, UNKNOWN_SPEAKER),
])
def test_the_speaker_floor_is_compared_in_basis_points(confidence_bp, expected):
    seg = TranscriptSegment(speaker="Rohit", speaker_confidence_bp=confidence_bp,
                            start_ms=0, end_ms=1_000, text="ok")
    assert seg.attributed_speaker == expected


def test_a_blank_speaker_label_is_unknown_even_at_full_confidence():
    seg = TranscriptSegment(speaker="  ", speaker_confidence_bp=10_000,
                            start_ms=0, end_ms=1, text="ok")
    assert seg.attributed_speaker == UNKNOWN_SPEAKER


@pytest.mark.parametrize("start_ms, stamp", [
    (0, "00:00:00"), (1_000, "00:00:01"), (61_000, "00:01:01"),
    (3_723_000, "01:02:03"), (-5, "00:00:00"),
])
def test_timestamps_render_from_integer_milliseconds(start_ms, stamp):
    seg = TranscriptSegment(speaker="A", speaker_confidence_bp=9_000,
                            start_ms=start_ms, end_ms=start_ms + 1, text="hi")
    assert render_transcript([seg]).startswith(f"[{stamp}] ")


def test_empty_segments_are_skipped_rather_than_rendered_as_blank_lines():
    segs = [TranscriptSegment(speaker="A", speaker_confidence_bp=9_000, start_ms=0,
                              end_ms=1, text="   "),
            TranscriptSegment(speaker="B", speaker_confidence_bp=9_000, start_ms=1_000,
                              end_ms=2_000, text="real words")]
    assert render_transcript(segs) == "[00:00:01] B: real words"
