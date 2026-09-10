"""PreparedContent persistence — the L1→L2 seam, stored.

L1 pays once (HTML strip, quote strip, PII mask, offset map) at ingestion; L2 and every
later re-extraction read the SAME prepared text instead of re-deriving it. The offset
map is what makes '[start,end] evidence → exact source sentence' possible downstream.

Retention: prepared text is the MASKED, replayable form — kept 180 days (longer than the
encrypted raw payload's 30) so an improved extractor can re-run history without re-paying
or re-fetching. Both clocks are enforced by purge jobs, and both stores erase by org for
account deletion."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Protocol

from sqlalchemy import text

from genios_engine.contracts.prepared_content import PreparedContent
from genios_engine.platform.db import get_engine

PREPARED_TTL_DAYS = 180


class PreparedContentStore(Protocol):
    def put(self, *, org_id: str, prepared: PreparedContent,
            ttl_days: int = PREPARED_TTL_DAYS) -> None: ...
    def get_text(self, *, org_id: str, event_id: str) -> str | None: ...


def message_form(clean_text: str | None) -> dict[str, int | None]:
    """Five numbers about the SHAPE of a message, derived from text this row already holds.

    Length, structure and how much it asks — the three things a founder can actually change
    about an email, and the three that no table in this system could previously distinguish.

    MEASURED ON `clean_text`, DELIBERATELY. That is the PII-masked, signature-stripped,
    quote-stripped form. Measuring the raw body would count the disclaimer, the previous six
    replies and the phone number in the footer, and a thread would look longer every time
    somebody answered it — the reply-chain growing would read as the founder writing more.

    A QUESTION IS COUNTED, NOT JUDGED. `question_count` is literally the number of `?` characters.
    It is not "how engaging the email is": a message with six questions may be thorough or may be
    an interrogation, and nothing here knows which. It is recorded because it is the one
    structural property of an ask that a writer controls and can see the effect of.

    NULL, NEVER ZERO, when there is no text. A zero would read as "they sent an empty message";
    None reads as "not measured", which is what is true.
    """
    if clean_text is None:
        return {"body_chars": None, "body_words": None,
                "paragraph_count": None, "question_count": None}
    text_value = str(clean_text)
    # A paragraph is a run separated by a blank line. `splitlines()` would count every wrapped
    # line, which measures the mail client's window rather than the writer's structure.
    paragraphs = [block for block in text_value.split("\n\n") if block.strip()]
    # A TOKEN IS A WORD ONLY IF IT HOLDS A LETTER OR A DIGIT. Bare `split()` counts an em-dash,
    # a lone bullet and a `>` quote marker as words, so a note written with dashes scores longer
    # than the same note written without them — a difference in punctuation reading as a
    # difference in length is exactly the confound this column exists to avoid.
    words = [token for token in text_value.split() if any(ch.isalnum() for ch in token)]
    return {"body_chars": len(text_value),
            "body_words": len(words),
            "paragraph_count": len(paragraphs),
            "question_count": text_value.count("?")}


class InMemoryPreparedContentStore:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}                 # event_id -> row

    def put(self, *, org_id, prepared: PreparedContent, ttl_days=PREPARED_TTL_DAYS,
            direction: str | None = None):
        self.rows[prepared.event_id] = {"org_id": org_id, "prepared": prepared,
                                        "direction": direction,
                                        **message_form(prepared.clean_text)}

    def get_text(self, *, org_id, event_id) -> str | None:
        row = self.rows.get(event_id)
        if row is None or row["org_id"] != org_id:
            return None
        return row["prepared"].clean_text


class PostgresPreparedContentStore:
    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    def put(self, *, org_id, prepared: PreparedContent, ttl_days=PREPARED_TTL_DAYS,
            direction: str | None = None):
        expires = datetime.now(timezone.utc) + timedelta(days=ttl_days)
        form = message_form(prepared.clean_text)
        with self._engine.begin() as c:
            c.execute(text(
                "insert into prepared_content (event_id, org_id, prepared_content_id, "
                "clean_text, language, masked_spans, protected_spans, offset_map, "
                "signature_hints, preprocessor_version, expires_at, "
                "direction, body_chars, body_words, paragraph_count, question_count) "
                "values (:e, :o, :pid, :txt, :lang, cast(:ms as jsonb), cast(:ps as jsonb), "
                "cast(:om as jsonb), cast(:sh as jsonb), :pv, :exp, "
                ":dir, :bc, :bw, :pc, :qc) "
                "on conflict (event_id) do nothing"),
                {"e": prepared.event_id, "o": org_id,
                 "pid": prepared.prepared_content_id, "txt": prepared.clean_text,
                 "lang": prepared.language,
                 "ms": json.dumps([m.model_dump() for m in prepared.masked_spans]),
                 "ps": json.dumps([list(p) for p in prepared.protected_spans]),
                 "om": json.dumps([s.model_dump() for s in prepared.offset_map]),
                 "sh": json.dumps(prepared.signature_hints, default=str),
                 "pv": prepared.preprocessor_version, "exp": expires,
                 "dir": direction, "bc": form["body_chars"], "bw": form["body_words"],
                 "pc": form["paragraph_count"], "qc": form["question_count"]})

    def get_text(self, *, org_id, event_id) -> str | None:
        with self._engine.connect() as c:
            r = c.execute(text(
                "select clean_text from prepared_content "
                "where event_id=:e and org_id=:o"), {"e": event_id, "o": org_id}).first()
        return r.clean_text if r else None

    def purge_expired(self, *, eval_time=None) -> int:
        now = eval_time or datetime.now(timezone.utc)
        with self._engine.begin() as c:
            return c.execute(text(
                "delete from prepared_content where expires_at < :now"),
                {"now": now}).rowcount
