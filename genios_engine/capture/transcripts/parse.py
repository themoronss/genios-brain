"""P5 · transcript parsers — every export a seat hands us → ordered speaker turns.

Six shapes cover the first cut (plan §1): a Google Meet transcript Doc (exported to text), WebVTT
(Zoom, Teams), SRT, Otter, Fireflies and Granola text exports. They differ in exactly two ways —
where the speaker's name sits and where the timestamp sits — so one line reader handles the text
family and two cue readers handle the subtitle family:

    Meet Doc      00:00:04                   (timestamp line)
                  Rohit Mehta: Okay, let's start.
    Zoom / text   [00:00:04] Rohit Mehta: Okay, let's start.
    Granola       Me: Okay, let's start.       Them: …
    Otter         Rohit Mehta  0:04           (header line: name + timestamp)
                  Okay, let's start.
    Fireflies     Rohit Mehta - 00:04         (header line) — or name line, then timestamp line
    WebVTT        <v Rohit Mehta>Okay</v>     (Teams)  ·  Rohit Mehta: Okay  (Zoom)
    SRT           1 / 00:00:04,000 --> … / Rohit Mehta: Okay

**A line with no speaker is never given one.** A continuation line joins the turn above it; a
line before any speaker stays unattributed and renders as `unknown:` — the same rule
`documents/transcript.py` applies to low-confidence diarization, because an unattributed line is
recoverable and a misattributed commitment is acted on.

Pure: no clock, no database, no model.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from genios_engine.capture.documents.base import UNKNOWN_SPEAKER

PROVIDERS: tuple[str, ...] = ("gmeet", "granola", "fireflies", "otter", "zoom", "teams", "other")

_TS = r"\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?"
_TS_ONLY = re.compile(rf"^\s*[\[(]?\s*({_TS})\s*[\])]?\s*$")
_CUE_TIME = re.compile(rf"^\s*({_TS})\s*-->\s*({_TS})")
#: A speaker label: a name of 1-5 words (letters, dots, apostrophes, hyphens, digits after the
#: first word so "Speaker 1" works), or an email address. Starts with a letter so "10:30" is never
#: read as a label.
_LABEL = r"(?:[^\W\d_][\w.'’\-]*(?:\s+[\w.'’\-()]+){0,4}|[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+)"
_COLON_LINE = re.compile(
    rf"^\s*(?:[\[(]?\s*(?P<ts>{_TS})\s*[\])]?\s*[-–|]?\s*)?"
    rf"(?:\*\*)?(?P<label>{_LABEL})(?:\*\*)?\s*:\s*(?:\*\*)?\s*(?P<text>\S.*)$")
_HEADER_LINE = re.compile(
    rf"^\s*(?P<label>{_LABEL}?)\s*(?:\s[-–|·]\s*|\s{{2,}}|\s)\s*[\[(]?(?P<ts>{_TS})[\])]?\s*$")
_VTT_VOICE = re.compile(r"<v(?:\.[\w.\-]+)?\s+([^>]+)>(.*?)(?:</v>|$)", re.S)
_TAG = re.compile(r"</?[^>]+>")

#: Labels that head METADATA, not speech. Matched case-insensitively on the whole label.
_META_LABELS = frozenset({
    "attendees", "participants", "date", "time", "title", "meeting", "transcript", "summary",
    "agenda", "action items", "notes", "location", "duration", "recording", "meeting title",
    "meeting date", "host", "invitees", "keywords", "speakers",
})
#: Whole lines that exports add around the dialogue and that are nobody's speech.
_BOILERPLATE = re.compile(
    r"^(transcribed by https?://otter\.ai.*|this editable transcript was computer generated.*|"
    r"transcription ended after .*|meeting ended after .*|webvtt.*|note:? this transcript.*|"
    r"-+|=+|\*+)$", re.I)
_DATE_FORMATS = ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%d/%m/%Y",
                 "%a, %b %d, %Y", "%A, %B %d, %Y")
_TITLE_SUFFIX = re.compile(r"\s*[-–—|:]?\s*(?:meeting\s+)?transcript(?:ion)?\s*$", re.I)
_TITLE_DATE = re.compile(r"\s*\((?:[^()]*\d{4}[^()]*)\)\s*|\s+-\s+\d{4}[/-]\d{2}[/-]\d{2}.*$")


@dataclass(frozen=True)
class Turn:
    """One uninterrupted stretch of one speaker. `speaker` is "" when the export named nobody."""

    speaker: str
    text: str
    start_ms: int | None = None


@dataclass(frozen=True)
class ParsedTranscript:
    provider: str
    turns: tuple[Turn, ...]
    title: str | None = None
    date: date | None = None
    #: The names the export itself lists as attendees (a Meet Doc's "Attendees" line).
    attendees: tuple[str, ...] = ()
    content_lines: int = 0
    attributed_lines: int = 0

    @property
    def attribution_bp(self) -> int:
        """Share of dialogue lines that landed under a named speaker, in basis points."""
        if not self.content_lines:
            return 0
        return self.attributed_lines * 10000 // self.content_lines

    @property
    def labels(self) -> tuple[str, ...]:
        """Distinct speaker labels in order of first appearance."""
        return tuple(dict.fromkeys(t.speaker for t in self.turns if t.speaker))

    def render(self) -> str:
        """`Speaker: text`, one line per turn — the canonical text that is hashed and split."""
        return "\n".join(f"{t.speaker or UNKNOWN_SPEAKER}: {t.text}" for t in self.turns)


def _ms(ts: str | None) -> int | None:
    if not ts:
        return None
    ts = ts.replace(",", ".")
    frac = 0
    if "." in ts:
        ts, f = ts.split(".", 1)
        frac = int((f + "000")[:3])
    parts = [int(p) for p in ts.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts[-3:]
    return ((h * 60 + m) * 60 + s) * 1000 + frac


def _clean_label(label: str) -> str:
    return " ".join(label.replace("**", "").split()).strip(" -–:")


def _is_label(label: str) -> bool:
    lab = _clean_label(label)
    return bool(lab) and len(lab) <= 60 and lab.casefold() not in _META_LABELS


def clean_title(title: str | None) -> str | None:
    """"ISO audit prep – Voltex – Transcript" → "ISO audit prep – Voltex". Also drops a
    parenthesised date Meet appends to its Doc names. Never returns an empty string."""
    if not title:
        return None
    t = _TITLE_DATE.sub(" ", title)
    t = _TITLE_SUFFIX.sub("", t)
    t = " ".join(t.split()).strip(" -–—|:")
    return t or None


def parse_date(line: str) -> date | None:
    s = " ".join(line.split()).strip(" ,.")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def detect_provider(text: str, *, filename: str = "", hint: str | None = None) -> str:
    """The recorder that produced this export. An explicit hint wins; else the export's own
    fingerprints; else `other`. Informational only — no parsing decision reads it."""
    h = (hint or "").strip().lower()
    if h in PROVIDERS:
        return h
    head = text[:4000].lower()
    name = (filename or "").lower()
    if head.lstrip().startswith("webvtt") or name.endswith(".vtt"):
        return "teams" if "<v " in head else "zoom"
    if "otter.ai" in head:
        return "otter"
    if "fireflies" in head or "fireflies" in name:
        return "fireflies"
    if "granola" in head or "granola" in name:
        return "granola"
    lines = {ln.strip().lower() for ln in head.splitlines()}
    if "transcript" in lines and ("attendees" in lines or any(l.startswith("attendees") for l in lines)):
        return "gmeet"
    if re.search(r"\btranscript\s*$", name.rsplit(".", 1)[0]):
        return "gmeet"
    return "other"


class _Builder:
    def __init__(self) -> None:
        self.turns: list[list] = []            # [speaker, [texts], start_ms]
        self.content = 0
        self.attributed = 0

    def add(self, speaker: str, text: str, start_ms: int | None, *, merge: bool = True) -> None:
        text = " ".join(text.split())
        if not text:
            return
        self.content += 1
        if speaker:
            self.attributed += 1
        if merge and self.turns and self.turns[-1][0] == speaker:
            self.turns[-1][1].append(text)
            return
        self.turns.append([speaker, [text], start_ms])

    def cont(self, text: str) -> None:
        """A continuation line: joins the current turn, whoever it belongs to."""
        text = " ".join(text.split())
        if not text:
            return
        self.content += 1
        if self.turns:
            if self.turns[-1][0]:
                self.attributed += 1
            self.turns[-1][1].append(text)
        else:
            self.turns.append(["", [text], None])

    def result(self) -> tuple[Turn, ...]:
        return tuple(Turn(speaker=s, text=" ".join(t), start_ms=ms) for s, t, ms in self.turns)


def _parse_cues(text: str) -> _Builder:
    """WebVTT and SRT: blocks separated by blank lines, a `-->` timing line, then cue text."""
    b = _Builder()
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n")):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        timing = next((i for i, ln in enumerate(lines) if _CUE_TIME.match(ln)), None)
        if timing is None:
            continue
        start = _ms(_CUE_TIME.match(lines[timing]).group(1))
        body = "\n".join(lines[timing + 1:])
        voices = _VTT_VOICE.findall(body)
        if voices:
            for who, said in voices:
                b.add(_clean_label(who), _TAG.sub("", said), start)
            continue
        for ln in body.split("\n"):
            ln = _TAG.sub("", ln).strip()
            m = _COLON_LINE.match(ln)
            if m and _is_label(m.group("label")) and not m.group("ts"):
                b.add(_clean_label(m.group("label")), m.group("text"), start)
            elif ln:
                b.cont(ln)
    return b


def parse_transcript(text: str, *, filename: str = "",
                     provider_hint: str | None = None) -> ParsedTranscript:
    """Any supported export → `ParsedTranscript`. Never raises; an unreadable text yields no turns."""
    text = (text or "").lstrip("﻿")
    provider = detect_provider(text, filename=filename, hint=provider_hint)
    name = (filename or "").lower()
    if (text.lstrip().upper().startswith("WEBVTT") or name.endswith((".vtt", ".srt"))
            or _looks_like_srt(text)):
        b = _parse_cues(text)
        return ParsedTranscript(provider=provider, turns=b.result(), title=None,
                                content_lines=b.content, attributed_lines=b.attributed)
    return _parse_text(text, provider)


def _looks_like_srt(text: str) -> bool:
    head = [ln.strip() for ln in text.strip().splitlines()[:3]]
    return len(head) >= 2 and head[0].isdigit() and bool(_CUE_TIME.match(head[1]))


def _parse_text(text: str, provider: str) -> ParsedTranscript:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    b = _Builder()
    title: str | None = None
    day: date | None = None
    attendees: list[str] = []
    header_speakers: set[str] = set()
    current: str | None = None             # header-mode speaker (Otter / Fireflies)
    pending_ts: int | None = None
    in_attendees = False
    started = False                        # the first speech line has been seen
    i = 0
    while i < len(lines):
        raw = lines[i]
        ln = raw.strip()
        i += 1
        if not ln:
            in_attendees = False
            continue
        if _BOILERPLATE.match(ln):
            continue
        low = ln.casefold().rstrip(":")
        # ── metadata above the dialogue ─────────────────────────────────────────────────────
        if not started:
            if low == "transcript":
                continue
            if low in ("attendees", "participants", "invitees"):
                in_attendees = True
                continue
            m_att = re.match(r"^(attendees|participants|invitees)\s*:\s*(.+)$", ln, re.I)
            if m_att:
                attendees += [a.strip() for a in re.split(r"[,;]", m_att.group(2)) if a.strip()]
                continue
            if in_attendees:
                attendees += [a.strip() for a in re.split(r"[,;]", ln) if a.strip()]
                continue
            if day is None and (d := parse_date(ln)) is not None:
                day = d
                continue
            m_date = re.match(r"^(?:date|meeting date)\s*:\s*(.+)$", ln, re.I)
            if m_date and day is None:
                day = parse_date(m_date.group(1))
                continue
            m_title = re.match(r"^(?:title|meeting title|meeting)\s*:\s*(.+)$", ln, re.I)
            if m_title and title is None:
                title = clean_title(m_title.group(1))
                continue
        # ── dialogue ────────────────────────────────────────────────────────────────────────
        m_ts = _TS_ONLY.match(ln)
        if m_ts:
            pending_ts = _ms(m_ts.group(1))
            continue
        m_head = _HEADER_LINE.match(ln)
        if m_head and m_head.group("label") and _is_label(m_head.group("label")):
            current = _clean_label(m_head.group("label"))
            header_speakers.add(current)
            pending_ts = _ms(m_head.group("ts"))
            started = True
            continue
        # A bare name line followed by a timestamp-only line (a Fireflies layout).
        nxt = next((lines[j].strip() for j in range(i, min(i + 2, len(lines)))
                    if lines[j].strip()), "")
        if (_TS_ONLY.match(nxt) and re.fullmatch(_LABEL, ln) and _is_label(ln)
                and len(ln.split()) <= 5 and not ln.endswith((".", "?", "!"))):
            current = _clean_label(ln)
            header_speakers.add(current)
            started = True
            continue
        m = _COLON_LINE.match(ln)
        if m and _is_label(m.group("label")) and (
                current is None or _clean_label(m.group("label")) in header_speakers):
            label = _clean_label(m.group("label"))
            started = True
            b.add(label, m.group("text"), _ms(m.group("ts")) or pending_ts)
            pending_ts = None
            continue
        if current is not None:
            b.add(current, ln, pending_ts)
            pending_ts = None
            continue
        if not started and title is None:
            title = clean_title(ln)
            continue
        started = True
        b.cont(ln)
    return ParsedTranscript(provider=provider, turns=b.result(), title=title, date=day,
                            attendees=tuple(dict.fromkeys(attendees)),
                            content_lines=b.content, attributed_lines=b.attributed)


def decode_transcript_bytes(data: bytes, *, filename: str = "", content_type: str = "",
                            ocr=None) -> str:
    """Upload bytes → transcript text. `.docx` through the one DOCX reader the tree has
    (`native._docx_to_text`); subtitle and text formats decoded directly (the generic extractor
    decodes `.vtt`/`.srt` to nothing); anything else through the shared best-effort path."""
    name = (filename or "").lower()
    ctype = (content_type or "").lower()
    if name.endswith(".docx") or "wordprocessingml" in ctype:
        from genios_engine.capture.documents.native import _docx_to_text
        try:
            return _docx_to_text(data)
        except Exception:                          # noqa: BLE001 — a corrupt file reads as empty
            return ""
    if (name.endswith((".txt", ".vtt", ".srt", ".md", ".text")) or ctype.startswith("text/")
            or not name or "." not in name):
        for enc in ("utf-8-sig", "utf-16") if data[:2] in (b"\xff\xfe", b"\xfe\xff") else ("utf-8-sig",):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")
    from genios_engine.capture.documents.native import extract_text_best_effort
    return extract_text_best_effort(mime=content_type, data=data, filename=filename, ocr=ocr)


__all__ = ["PROVIDERS", "ParsedTranscript", "Turn", "clean_title", "decode_transcript_bytes",
           "detect_provider", "parse_date", "parse_transcript"]
