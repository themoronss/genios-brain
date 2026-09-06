"""Deterministic engines for dev and tests — no Tesseract binary, no transcription bill.

Both fakes encode their outcome in the reference they are handed, so a test names the case it
wants in the fixture instead of monkeypatching an engine into a shape. That matters most for
the failure cases: `raise:` and `blank:` are the two OCR endings that used to be unreachable
from a test (one crashed the caller, the other was indistinguishable from success), and they
are the two the G2 marker invariant is actually about.
"""
from __future__ import annotations

from .base import OcrResult
from .transcript import TranscriptSegment


class FakeOcr:
    """Deterministic OCR. The `image_ref` prefix selects the outcome:

    * ``weak:``  — real text, below the confidence floor  -> `ocr_review_required`
    * ``blank:`` — high confidence, no text at all        -> `ocr_failed` (the silent-empty case)
    * ``raise:`` — the engine throws, as a missing binary does -> `ocr_failed`
    * anything else — a good read                        -> `accepted`
    """

    name = "fake-ocr"

    def ocr(self, image_ref: str) -> OcrResult:
        if image_ref.startswith("raise:"):
            raise RuntimeError("tesseract is not installed on this host")
        if image_ref.startswith("blank:"):
            # Tesseract on a blank scan: certain, and certain there is nothing there.
            return OcrResult(text="   \n ", confidence_bp=9_900, pages=1, engine=self.name)
        if image_ref.startswith("weak:"):
            return OcrResult(text="blurr d cntract renews 30 sept",
                             confidence_bp=4_200, pages=1, engine=self.name)
        return OcrResult(text="Agreement renews automatically on 30 September.",
                         confidence_bp=9_100, pages=1, engine=self.name)


class FakeSpeechEngine:
    """Deterministic diarized transcription for L1.3.4-U3's synthetic fixtures.

    There is no real provider behind this unit (source P5 is unbuilt), so this fake is the ONLY
    engine in the repo. It is not a stand-in for one that exists elsewhere — it is the fixture
    the seam is tested against, which is exactly what doc-04 does for the `chat` and
    `transcript` profiles whose connectors are also unbuilt.

    The `media_ref` prefix selects the outcome:

    * ``raise:``   — the provider errors               -> `transcription_failed`
    * ``silent:``  — a recording with no speech in it  -> `transcription_failed`
    * ``unsure:``  — diarization below the floor       -> the speaker becomes `unknown`
    * anything else — two speakers, confidently labelled
    """

    name = "fake-speech"

    def transcribe(self, media_ref: str) -> tuple[TranscriptSegment, ...]:
        if media_ref.startswith("raise:"):
            raise RuntimeError("transcription provider unavailable")
        if media_ref.startswith("silent:"):
            return ()
        if media_ref.startswith("unsure:"):
            return (
                TranscriptSegment(speaker="Rohit", speaker_confidence_bp=3_100,
                                  start_ms=0, end_ms=4_000,
                                  text="We will send the signed contract by Friday."),
            )
        return (
            TranscriptSegment(speaker="Rohit", speaker_confidence_bp=9_400,
                              start_ms=0, end_ms=4_000,
                              text="We will send the signed contract by Friday."),
            TranscriptSegment(speaker="Priya", speaker_confidence_bp=8_800,
                              start_ms=4_000, end_ms=9_500,
                              text="Finance still needs to approve the increase."),
        )
