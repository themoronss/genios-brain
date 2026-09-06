"""L1.3.4-U3 · Speech-to-Text (LLM-3) — the seam, built; the provider, DESCOPED.

**Read this before using it.** Doc-03 marks U3 "🆕 MISSING ENTIRELY" and doc-01 lists its input
as priority **P5 · Voice / transcripts**, which is in **no wave of the build order**. There is
therefore no connector anywhere in this repo that can hand this unit a real audio file, and
wiring a transcription provider now would buy a monthly bill for a code path nothing can
reach. Doc-04 already set the precedent for exactly this situation — the `chat` and
`transcript` extraction profiles are *"written and unit-tested against synthetic fixtures so
the registry is complete and the code path exists"* while their connectors are unbuilt — and
this unit follows it: **the shape, the failure modes and the router seam are real and tested;
the provider binding is not here.** See `fake.FakeSpeechEngine` for the fixture engine the
tests drive it with.

What that buys, concretely: the day the P5 connector lands it calls `transcribe_media` with a
real engine and nothing else in Layer 1 changes — the router already recognises audio mimes,
the status vocabulary already has words for both failure modes, and audio arriving *today*
parks as `transcription_unavailable` instead of silently reporting `unsupported`, which is the
same silent-loss shape G2 exists to eliminate one medium over.

**The one design decision that is not deferrable.** Doc-03 names diarization as the failure
mode — *"diarization errors attribute a commitment to the wrong person"* — and its mitigation
as speaker labels carrying confidence, with a below-threshold speaker becoming `unknown`
rather than a guess. That rule is implemented here rather than left to the caller, because it
is the difference between "Rohit committed to the 30th" filed against Rohit and filed against
whoever else was in the room. A wrong attribution is acted on; an unattributed one is not.
The label is replaced at *render* time, so the segment keeps the engine's raw claim and its
confidence for anyone auditing the decision, while the text that Layer 2 reads says `unknown`.
"""
from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from .base import (SPEAKER_MIN_CONFIDENCE_BP, UNKNOWN_SPEAKER, DocumentStatus)

#: Mime prefixes and extensions that mean "this is a recording, not a document". Kept here
#: rather than in the router so the medium is defined once, beside the unit that reads it.
AUDIO_MIME_PREFIXES = ("audio/", "video/")
AUDIO_EXTENSIONS = (".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus", ".aac",
                    ".mp4", ".mov", ".webm", ".mkv", ".m4v")


def is_audio(mime: str, filename: str = "") -> bool:
    """True when this object is a recording. Mime first, extension as the fallback, because
    Gmail hands us `application/octet-stream` for a voice memo often enough to matter."""
    m = (mime or "").lower().split(";", 1)[0].strip()
    if m.startswith(AUDIO_MIME_PREFIXES):
        return True
    return (filename or "").lower().endswith(AUDIO_EXTENSIONS)


@dataclass(frozen=True)
class TranscriptSegment:
    """One diarized utterance: who, when, what, and how sure the engine was about the who.

    Timestamps are integer milliseconds from the start of the recording — the same reason
    confidence is basis points, one level down: a float second is a number two systems
    disagree about at the sixth decimal, and a transcript offset is compared for equality.
    """

    speaker: str
    speaker_confidence_bp: int
    start_ms: int
    end_ms: int
    text: str

    @property
    def attributed_speaker(self) -> str:
        """The label Layer 2 is allowed to read: the engine's, or `unknown` when the engine was
        not confident enough to name anybody. Doc-03's stated mitigation, as a property."""
        if self.speaker_confidence_bp < SPEAKER_MIN_CONFIDENCE_BP or not self.speaker.strip():
            return UNKNOWN_SPEAKER
        return self.speaker


@dataclass(frozen=True)
class TranscriptResult:
    """A recording, read. `text` is the rendered transcript Layer 2 extracts from; `segments`
    is the structure it was rendered from, kept so an attribution can be audited back to the
    engine's own claim and confidence."""

    text: str
    segments: tuple[TranscriptSegment, ...] = ()
    engine: str | None = None
    status: str = DocumentStatus.TRANSCRIPTION_UNAVAILABLE.value
    detail: str | None = None
    content_hash: str | None = None
    #: Segments whose speaker was demoted to `unknown` — the diarization-quality signal.
    unattributed_segments: int = 0


class SpeechEngine(Protocol):
    """Audio → diarized segments. Implementations may raise; `transcribe_media` converts a
    raised engine into `transcription_failed`, never into an exception that stops a sync."""

    name: str

    def transcribe(self, media_ref: str) -> Sequence[TranscriptSegment]: ...


def _timestamp(ms: int) -> str:
    """`3_723_000` → `01:02:03`. Integer arithmetic; a transcript timestamp is an index, and an
    index rendered through a float is an index that moves."""
    total = max(0, int(ms)) // 1000
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def render_transcript(segments: Sequence[TranscriptSegment]) -> str:
    """Segments → the text Layer 2 reads: one line per utterance, `[hh:mm:ss] speaker: text`.

    Deterministic and total-order-preserving, because this string is what gets hashed, stored
    and chunked. Doc-03 requires the transcript be *"persisted and hashed exactly like any
    other extraction so replay reads the transcript, never re-transcribes"* — which only holds
    if two runs over the same segments render byte-identical text.
    """
    return "\n".join(
        f"[{_timestamp(s.start_ms)}] {s.attributed_speaker}: {s.text.strip()}"
        for s in segments if s.text.strip())


def transcribe_media(*, media_ref: str, engine: SpeechEngine | None) -> TranscriptResult:
    """Transcribe one recording, or say precisely why there is no transcript.

    Three endings, none of them an empty string on its own:

    * **no engine** → `transcription_unavailable`. The honest state of this repo today (P5 is
      unbuilt), and the state the router puts every audio attachment into.
    * **the engine raised, or produced nothing usable** → `transcription_failed`.
    * **segments** → `accepted`, with the rendered text hashed for replay.
    """
    if engine is None:
        return TranscriptResult(
            text="", status=DocumentStatus.TRANSCRIPTION_UNAVAILABLE.value,
            detail="audio/video received and no speech-to-text engine is wired "
                   "(L1.3.4-U3 has no connector: source P5 is unbuilt)")
    try:
        segments = tuple(engine.transcribe(media_ref))
    except Exception as exc:                       # a bad recording must not kill a sync batch
        return TranscriptResult(
            text="", engine=getattr(engine, "name", None),
            status=DocumentStatus.TRANSCRIPTION_FAILED.value,
            detail=f"speech engine raised: {type(exc).__name__}: {exc}")
    text = render_transcript(segments)
    name = getattr(engine, "name", None)
    if not text.strip():
        return TranscriptResult(
            text="", segments=segments, engine=name,
            status=DocumentStatus.TRANSCRIPTION_FAILED.value,
            detail="speech engine returned no usable segments")
    unattributed = sum(1 for s in segments
                       if s.text.strip() and s.attributed_speaker == UNKNOWN_SPEAKER)
    return TranscriptResult(
        text=text, segments=segments, engine=name,
        status=DocumentStatus.ACCEPTED.value, detail=None,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        unattributed_segments=unattributed)
