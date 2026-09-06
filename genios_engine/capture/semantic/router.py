"""L1.4.1 · the content-type router — which reading task is this?

One decision, made before a single token is spent: an email, a Slack line, a meeting
transcript, a forty-page agreement and a CRM note are five different reading tasks, and doc 04
registers five prompts for them (`capture/semantic/profiles.py`). This module is the only thing
that says which one applies. Wrong profile means the wrong prompt, which means the model is
asked the wrong questions and answers them well — the failure that leaves no error anywhere,
only thinner meaning.

**A table, not a chain of ifs.** Doc 04 states the rules as a numbered table and asks for a
table-driven test with one row per condition. Both halves are honoured literally: `RULES` below
IS the doc's table, ordered, each row carrying its number, the profile it selects and the
sentence that explains the selection. A chain of `if` statements can be reordered by an edit
that looks like a formatting change; a tuple of rows cannot, and `test_router.py` walks the
same tuple the router walks, so a rule that gains a row without a test row is visible.

**Order is the semantics.** Rule 3 (transcript) sits above rule 4 (document) deliberately: an
`email_attachment` whose mime is `audio/m4a` is a recording, and reading it under the document
profile would prompt for clauses and amounts against a diarized conversation. Rule 5 (CRM note)
sits below rule 4 because a file attached to a HubSpot deal is still a file.

**Two units.**

* **U1 · `select_profile`** — the table, applied. Returns the choice *and why*, because "this
  went to the document profile" is a sentence somebody has to be able to check against a stored
  event six weeks later, and a bare string cannot be checked.
* **U2 · `routing_input_for`** — the derivation the doc's table quietly assumes. Rules 3 and 5
  are not stated in terms of `object_type` at all: rule 3 says *"mime is audio-derived"* and
  rule 5 says *"field is a note"*, and neither fact is on `SourceEvent`. This unit is where a
  captured event plus the document metadata become the typed input the table reads, so
  "audio-derived" is defined once (by `capture/documents/transcript.py::is_audio`, the tree's
  existing answer) rather than re-guessed at every call site.

**Pure.** No clock, no model, no database, no float. The router decides which model will be
asked; asking a model which prompt to use would be the same circularity ALG-05 forbids one
component over, and it would cost a call to save a call.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from genios_engine.capture.documents.transcript import is_audio
from genios_engine.capture.semantic.profiles import (FALLBACK_PROFILE_ID, PROFILES,
                                                    ExtractionProfile)
from genios_engine.capture.source_registry import PROVIDER_CAPABILITY
from genios_engine.contracts.source_event import SourceEvent

# --------------------------------------------------------------------------------------------
# The vocabularies the table matches on
# --------------------------------------------------------------------------------------------

#: Object types that mean "a person wrote prose and sent it to named recipients".
#:
#: Two spellings per source, deliberately. Doc 04 writes `email_message`; the source registry's
#: gmail descriptor declares the object type `message`, and the two have to meet somewhere.
#: `_object_tokens` produces both the bare name and the `source/name` qualification, so the
#: doc's word and the connector's word both land here and neither had to be renamed.
EMAIL_OBJECT_TYPES: frozenset[str] = frozenset({
    "email_message", "email", "gmail/message", "outlook/message", "imap/message",
    "inkbox/message",
})

#: Short, fast, low-context turns. `-30` on the tier score downstream: a Slack line put through
#: a frontier model is the single most expensive way to learn nothing.
CHAT_OBJECT_TYPES: frozenset[str] = frozenset({
    "slack_message", "chat_message", "chat", "slack/message", "teams/message",
    "whatsapp/message", "sms/message",
})

#: A recording, already turned into text. Named object types only — the *medium* test lives in
#: `is_audio`, and an object that is still audio has not reached this router yet.
TRANSCRIPT_OBJECT_TYPES: frozenset[str] = frozenset({
    "transcript", "meeting_transcript", "call_transcript", "recording", "call_recording",
    "voice_memo",
})

#: Sources whose every object is a meeting recording.
#:
#: NONE of these is in `capture/source_registry.py` today: P5 · Voice is in no wave of the build
#: order, which is why `capture/documents/transcript.py` is a seam with no engine behind it. The
#: set is declared anyway, because routing that is correct only after somebody remembers to edit
#: it is routing that will be wrong on the first day the connector lands — the same ordering
#: `tests/capture/semantic/test_import_graph.py` already argues for, where a rule is asserted
#: before the file it protects exists.
TRANSCRIPT_SOURCES: frozenset[str] = frozenset({
    "gong", "fireflies", "otter", "chorus", "grain", "fathom", "tldv", "granola", "read_ai",
})

#: Anything read page-by-page rather than turn-by-turn. `page` and `document_chunk` are the
#: registry's bare names for what doc 04 spells `notion_page` and `upload/document_chunk`.
DOCUMENT_OBJECT_TYPES: frozenset[str] = frozenset({
    "file", "email_attachment", "attachment", "document", "document_chunk",
    "upload/document_chunk", "notion_page", "page", "gdrive/file", "notion/page",
    "confluence/page",
})

#: Doc 04 rule 5 names `{hubspot, salesforce}` — DERIVED here rather than transcribed, from the
#: one place a source is described. A third CRM added to the registry with `capability="crm"` is
#: routed correctly without an edit to this file, and a transcribed literal would instead have
#: sent its notes to the email prompt until somebody noticed.
CRM_SOURCES: frozenset[str] = frozenset(
    source for source, capability in PROVIDER_CAPABILITY.items() if capability == "crm")

#: Field names on a CRM object that carry a human's written note, as opposed to a typed column.
#: The `"note" in token` widening below catches `hs_note_body`, `engagement_note` and whatever
#: the next CRM calls it; this set carries the ones whose names do not contain the word.
NOTE_FIELD_NAMES: frozenset[str] = frozenset({
    "body", "comment", "comments", "description", "activity_body", "call_notes", "meeting_notes",
})


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def _object_tokens(source: str, object_type: str) -> tuple[str, ...]:
    """Every spelling of this object type the table may legitimately be written against.

    Three, at most, and they exist because doc 04 and the source registry disagree about naming
    and neither is wrong: the doc writes `upload/document_chunk` and `notion_page` (source
    folded into the name), the registry declares `document_chunk` and `page` (source held
    separately on the event). Rather than rename one side — which would break either the spec
    trace or every connector — both spellings are produced and the table may match either.

    Order is stable and duplicates are dropped, so the tokens are also a usable audit string.
    """
    source_id = _normalize(source)
    object_id = _normalize(object_type)
    if not object_id:
        return ()
    tokens = [object_id]
    if "/" in object_id:
        tokens.append(object_id.rsplit("/", 1)[1])
    if source_id:
        tokens.append(f"{source_id}/{object_id}")
    return tuple(dict.fromkeys(tokens))


def is_note_field(field_name: str | None) -> bool:
    """Does this CRM field hold a written note rather than a typed value?

    Public because rule 5 is the one rule whose input is not on the envelope: the caller reading
    a HubSpot engagement decides which field it is handing over, and it needs the same answer
    the router will give rather than its own opinion of it.
    """
    token = _normalize(field_name)
    if not token:
        return False
    return "note" in token or token in NOTE_FIELD_NAMES


# --------------------------------------------------------------------------------------------
# L1.4.1-U2 · the routing input
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class RoutingInput:
    """Exactly what the decision table reads, and nothing else.

    Narrow on purpose. A router handed a whole `SourceEvent` can grow an opinion about the
    actor, the org or the occurred_at, and the first time it does the profile stops being a
    property of the CONTENT and starts being a property of the tenant — at which point two
    identical PDFs extract differently and the L1.4.9 cache key, which contains `profile_id`,
    silently forks.

    `mime` and `filename` are both carried because Gmail hands us `application/octet-stream` for
    a voice memo often enough to matter, and the extension is then the only surviving evidence
    of what the object is (`capture/documents/transcript.py` made the same call, for the same
    reason).
    """

    source: str
    object_type: str
    mime: str = ""
    filename: str = ""
    field_name: str | None = None

    def __post_init__(self) -> None:
        if not _normalize(self.source):
            raise ValueError("source is required — rules 3 and 5 are stated in terms of it, and "
                             "an empty source would silently take every event to the fallback")

    @property
    def object_tokens(self) -> tuple[str, ...]:
        return _object_tokens(self.source, self.object_type)

    @property
    def source_id(self) -> str:
        return _normalize(self.source)


def routing_input_for(event: SourceEvent, *, mime: str = "", filename: str = "",
                      field_name: str | None = None) -> RoutingInput:
    """L1.4.1-U2 — a captured event plus its document metadata, as the table's input.

    **Derived unit** (the component map promises an L1.4.1-U2 and doc 04 writes no block for
    it). It exists because two of the doc's six conditions are not expressible over
    `SourceEvent` alone:

    * rule 3 tests *"mime is audio-derived"*, and `SourceEvent` carries no mime — the mime lives
      on the `DocumentInput` the attachment/upload lane built, one seam earlier;
    * rule 5 tests *"field is a note"*, and which field of a CRM object is being extracted is a
      decision the structured lane makes, not a fact on the envelope.

    Without this unit every caller re-derives both, and the second caller derives them slightly
    differently — which is how the same PDF ends up extracted under two profiles and cached
    twice under keys that both claim to be canonical.
    """
    return RoutingInput(source=event.source, object_type=event.object_type, mime=mime,
                        filename=filename, field_name=field_name)


# --------------------------------------------------------------------------------------------
# L1.4.1-U1 · the decision table
# --------------------------------------------------------------------------------------------

def _rule_1_email(routing: RoutingInput) -> bool:
    return any(token in EMAIL_OBJECT_TYPES for token in routing.object_tokens)


def _rule_2_chat(routing: RoutingInput) -> bool:
    return any(token in CHAT_OBJECT_TYPES for token in routing.object_tokens)


def _rule_3_transcript(routing: RoutingInput) -> bool:
    if routing.source_id in TRANSCRIPT_SOURCES:
        return True
    if any(token in TRANSCRIPT_OBJECT_TYPES for token in routing.object_tokens):
        return True
    return is_audio(routing.mime, routing.filename)


def _rule_4_document(routing: RoutingInput) -> bool:
    return any(token in DOCUMENT_OBJECT_TYPES for token in routing.object_tokens)


def _rule_5_crm_note(routing: RoutingInput) -> bool:
    return routing.source_id in CRM_SOURCES and is_note_field(routing.field_name)


def _rule_6_fallback(routing: RoutingInput) -> bool:  # noqa: ARG001 — the table needs an arity
    return True


@dataclass(frozen=True)
class RoutingRule:
    """One row of doc 04's L1.4.1-U1 table.

    `number` is the doc's own row number and is asserted contiguous at import: the table is
    ORDERED, first match wins, and a row silently moved above another is a change of meaning
    that reads in a diff as a change of layout.
    """

    number: int
    name: str
    profile_id: str
    matches: Callable[[RoutingInput], bool]
    why: str

    def __post_init__(self) -> None:
        if self.profile_id not in PROFILES:
            raise ValueError(f"rule {self.number} ({self.name}) selects unregistered profile "
                             f"{self.profile_id!r}; the extractor would then render no prompt")
        if not callable(self.matches):
            raise TypeError(f"rule {self.number} ({self.name}) has a non-callable predicate")


#: Doc 04, L1.4.1-U1, verbatim in order. The last row is the fallback and always matches.
RULES: tuple[RoutingRule, ...] = (
    RoutingRule(1, "email_object_type", "email", _rule_1_email,
                "object_type is an email message"),
    RoutingRule(2, "chat_object_type", "chat", _rule_2_chat,
                "object_type is a chat or Slack message"),
    RoutingRule(3, "transcript_source_or_audio_mime", "transcript", _rule_3_transcript,
                "the source is a meeting recorder, the object type names a transcript, or the "
                "mime is audio-derived"),
    RoutingRule(4, "document_object_type", "document", _rule_4_document,
                "object_type is a file, an attachment, an uploaded chunk or a wiki page"),
    RoutingRule(5, "crm_note_field", "crm_note", _rule_5_crm_note,
                "a CRM source, and the field being extracted holds a written note"),
    RoutingRule(6, "fallback", FALLBACK_PROFILE_ID, _rule_6_fallback,
                "no rule matched; the email profile is the widest prose reader, so an unknown "
                "shape is read thinly rather than wrongly"),
)

#: The number of the row that always matches. Anything after it is unreachable.
FALLBACK_RULE_NUMBER = RULES[-1].number


def _check_table() -> None:
    """The table is ordered 1..n, every profile is registered, and exactly one row is total."""
    numbers = tuple(rule.number for rule in RULES)
    if numbers != tuple(range(1, len(RULES) + 1)):
        raise ValueError(f"RULES must be numbered 1..{len(RULES)} in order, got {numbers}")
    names = [rule.name for rule in RULES]
    if len(set(names)) != len(names):
        raise ValueError(f"RULES has duplicate names {names}; a decision cannot then be "
                         "explained by the name it reports")
    if RULES[-1].matches is not _rule_6_fallback:
        raise ValueError("the last rule must be the total fallback, or an event can reach the "
                         "end of the table with no profile at all")


_check_table()


@dataclass(frozen=True)
class ProfileChoice:
    """Which profile, by which rule, and the sentence that says why.

    The explanation travels because the decision is invisible in its own output: a thin
    extraction under the wrong profile looks exactly like a thin extraction of thin content, and
    the only way to tell them apart six weeks later is a stored record of which row fired.
    `fell_back` is separated from `rule_number` so a monitor can count fallbacks without
    knowing how many rules there happen to be this month — a rising fallback rate is a connector
    emitting an object type nobody mapped, which is a fixable bug and not a shrug.
    """

    profile_id: str
    rule_number: int
    rule_name: str
    reason: str
    fell_back: bool

    @property
    def profile(self) -> ExtractionProfile:
        """The registered `ExtractionProfile` this choice names."""
        return PROFILES[self.profile_id]


def select_profile(routing: RoutingInput) -> ProfileChoice:
    """L1.4.1-U1 — the profile for this content, and the rule that chose it.

    First match wins, walking `RULES` in the doc's own order. Never raises and never returns an
    unregistered profile: row 6 matches everything, so an object type nobody has seen becomes a
    thin email extraction with `fell_back=True` rather than a parked event and a stuck drain.
    """
    for rule in RULES:
        if rule.matches(routing):
            return ProfileChoice(profile_id=rule.profile_id, rule_number=rule.number,
                                 rule_name=rule.name, reason=rule.why,
                                 fell_back=rule.number == FALLBACK_RULE_NUMBER)
    raise AssertionError(  # unreachable: _check_table proves row 6 is total
        f"no rule matched {routing!r} — the fallback row is not total")


__all__ = ["CHAT_OBJECT_TYPES", "CRM_SOURCES", "DOCUMENT_OBJECT_TYPES", "EMAIL_OBJECT_TYPES",
           "FALLBACK_RULE_NUMBER", "NOTE_FIELD_NAMES", "RULES", "TRANSCRIPT_OBJECT_TYPES",
           "TRANSCRIPT_SOURCES", "ProfileChoice", "RoutingInput", "RoutingRule",
           "is_note_field", "routing_input_for", "select_profile"]
