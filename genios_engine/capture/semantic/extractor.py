"""L1.4.3 · the Semantic Extractor (LLM-2) — the one model call the whole group exists to make.

Everything in `capture/semantic/` above this file is what makes this call cheap, safe, replayable
and consumable: the registry says which prompt, the vocabulary says which words, the schema
generator says which shape, the binder says every claim brings a receipt. This module is where
they meet a model, and it is the ONLY place in Layer 1 that a model is asked to read prose.

Four units. Two are specified in doc 04; two are derived and the derivation is stated here rather
than left implicit, because the group's component map promises four unit specs and the doc carries
two (`scripts/unit_ledger.py --check` names the gap as `L1.4.3-U3` and `L1.4.3-U4`):

* **U1 · call assembly** (doc 04, L1.4.3-U1) — `assemble_call`. Profile + schema + vocabulary +
  envelope + fenced content into one prompt, plus the components its cache key is made of.
* **U2 · the worked example** (doc 04, L1.4.3-U2) — an ACCEPTANCE FIXTURE, not code. It lives at
  `tests/capture/semantic/test_extractor.py` (hermetic, FakeLLM) and at
  `tests/golden/l1/worked_example.json` (the graded corpus), asserted field by field against the
  doc's table. Nothing in this module implements it; a fixture implemented by the code it grades
  grades nothing.
* **U3 · response parsing** (derived) — `parse_response`. The doc's assembly line reads
  `result = parse(raw)` and its failure table names three parse-time outcomes (invalid JSON,
  omitted evidence, an invented field) without ever specifying the unit that produces them. This
  is that unit: the model's JSON into typed claims, through the binder, into an
  `ExtractionResult` that `capture/validate/schema.py` accepts — with everything it had to refuse
  counted rather than silently dropped.
* **U4 · the extraction run** (derived) — `extract`. The rest of the doc's assembly line: the
  cache check that must make ZERO calls on an unchanged re-run, the single call, the ONE repair
  retry, and the park-never-drop failure policy the doc's own table specifies.

WHAT THE MODEL IS ALLOWED TO BE. It DESCRIBES. It never SCORES, never ROUTES, never DECIDES
VISIBILITY, and the enforcement is structural rather than textual in every case:

* it cannot raise its own importance, because `importance_bp` is not a field on
  `ExtractionResult` — the contract refuses the name at construction and S-6 refuses it again at
  the boundary. Prompt text is advisory; the schema is enforcement;
* it does not pick its own model tier — `tier` arrives on the request from L1.4.10, computed from
  deterministic counts S1 produced;
* it does not pick its own profile — same seam, from L1.4.1;
* it does not stamp a span `verified`. Every span this module emits carries `verified=False` (S-9)
  because the extractor CLAIMS and ALG-08 (`capture/validate/spans.py`) VERIFIES, and an
  extraction that graded its own receipts would make the grade worthless;
* it does not resolve its own dates. The model supplies `as_written` — the words a human typed —
  and ALG-09 (`capture/validate/dates.py`) turns them into a window against the caller's
  `eval_time`. That is a stated divergence from the generated schema block, which asks the model
  for `earliest`/`latest`/`certainty` as well: those answers are read and discarded. "Pretty soon"
  must be a RELATIVE fourteen-day window computed by a cascade every machine runs identically,
  not a timestamp a model felt like producing, and a replay of a March event has to keep
  resolving against March forever;
* it DOES supply its own per-claim `confidence_bp`, and that is the one number it is asked for.
  Doc 04's W4 reverse prompt draws the line in those words — no `_bp` field "except its own
  per-field confidence" — because that number is composed at ALG-13 alongside authority and span
  verdicts and is never read as a rank on its own. It is integer basis points or it is refused:
  a `0.87` is not a differently-spelled 8700, it is a value that composes irreproducibly, and
  there is no reading of `1` that is both safe and unambiguous.

WHAT THIS MODULE DELIBERATELY DOES NOT DO, because a unit downstream already does it and doing it
twice would make that unit's gate vacuous:

* **it does not drop an amount the source never contained.** ALG-08 does
  (`spans._money_is_grounded`), and the golden corpus MEASURES the rate at this seam — "0
  fabricated amounts, any `Money` not literally present in the source is a HARD FAIL". A filter
  here would drive that metric to zero for every prompt ever written, including a prompt that
  invents an amount in every message. The extraction records `ungrounded_amounts` in its
  diagnostics so the operator sees what the gate is about to fail on, and the amount travels on
  to the unit whose job is removing it;
* **it does not verify a span.** Same reason, same seam (S-9);
* **it does not write a row.** The cache is injected, `llm_costs` is the caller's to record from
  the token counts on the outcome, and a parked event is RETURNED rather than stored so that
  the one module allowed to call a model is not also a module that opens a database.

THE FOUR SEAMS, AND WHO OWNS EACH. The doc's assembly line names four siblings, and this module
calls three of them rather than reimplementing any:

* **L1.4.7 · the fence** — `injection.fence(content, nonce=...)`. Its escape pass is one code
  point for one code point, so no evidence offset moves, and `FencedContent.check_placement` is
  run on every prompt this module renders: exactly one delimited region, SAFETY before it,
  nothing after it. `injection.scan_output` grades what comes back, advisorily;
* **L1.4.9 · the cache** — `cache.cache_key(...)` builds the key from CONTENT rather than from a
  hash the caller supplies, and `cache.cached_extraction(store, key, extract=thunk)` is what
  makes "a hit costs zero model calls" structural: on a hit the thunk is never invoked, so
  there is no path from a hit to a model at all;
* **L1.4.1 · the router** and **L1.4.10 · the model router** are resolved by the CALLER and
  arrive as `ExtractionRequest.profile_id` and `.tier`
  (`router.select_profile(routing_input_for(...))`, `model_router.route(...)`). They are not
  called here on purpose: the module allowed to call a model must not also be the module that
  decides how much that call costs, and there is no `RoutedEvent` contract to type them against.

The fence's escape pass has one consequence this module has to own. The model sees
`fenced.body`, which is `prepared.clean_text` with any fence-shaped literal neutralised in
place; the receipts it returns are measured against `prepared.clean_text`, which is what their
`source_ref` names. The two agree everywhere except at an escaped character, so a quote that
crosses one is counted (`escaped_span_quotes`) and left for ALG-08 to grade — the count is
there so a span that fails to verify for OUR reason is not read as the model inventing.

THE OFFSET FRAME IS STATED, NOT ASSUMED. The model is shown `fenced.body` and answers with
offsets, and until `OFFSET_FRAME_BLOCK` existed the prompt never said which string those
offsets index. L1.4.2's EVIDENCE block says "into the content shown below, counting from 0 at
its first character" — and what is shown below is the CONTENT section, whose first character is
the `[` of the opening fence marker. A model that counts from the first character it can see is
therefore off by the whole marker line (31 characters for a 16-hex nonce), every span comes back
`VERIFIED_RELOCATED`, and ALG-08 prices that at `bp * 9 // 10`. A ~10% tax on every receipt in
the system, paid for a sentence nobody had written. So this module states the frame in the words
a counter needs — offset 0 is the first character AFTER the opening marker's newline, the marker
lines are not content, characters are Unicode code points, and the content is exactly N of them
— and `offset_frame_misses` counts every span that still did not land at the offsets it stated,
so the statement is monitored rather than merely present.

The statement goes into the ENVELOPE substitution and therefore into `AssembledCall.envelope`,
which is a cache-key component. Both facts are forced. It cannot go in the template, which
L1.4.2 owns; it cannot go below the fence, which L1.4.7 forbids ("anything after the untrusted
region is an instruction in the exact position a successful injection would occupy"); and it
MUST move the key, because a row extracted under an undefined frame is not an answer to this
prompt and must not be served for it.

A TOTAL LOSS PARKS. A run can produce an `ExtractionResult` that types, conforms to S-1..S-9 and
contains NOTHING — and the two ways that happens are not the same event as a message that
genuinely said nothing:

    GENUINELY EMPTY   the answer named fields it was asked for and asserted no claims. A
                      newsletter, an "ok thanks". A real extraction, correct to cache, and
                      parking it would fill the queue with every pleasantry in the org.
    TOTAL LOSS        either the answer named NONE of the fields it was asked for (`{}` decodes,
                      is a legal mapping, and is not an answer), or it asserted claims and every
                      single one of them was refused here. That is knowledge about the ANSWER,
                      not about the message, and caching it makes the emptiness permanent: the
                      re-run is a hit and costs zero calls, forever.

`total_loss_failure` draws that line and nothing else does. A total loss is UNUSABLE, which is
the word the repair path already reads, so the model gets its one retry — the commonest total
loss is an answer whose every `confidence_bp` was written as a ratio, and the repair note says
exactly that — and then it PARKS under `extraction_total_loss` rather than being stored.

`claims_offered` is what makes it measurable, and its absence was the second half of the same
defect: every existing counter counts a REFUSAL, and each refusal happens BEFORE `claims_in` is
incremented, so an answer whose four commitments all died at `_confidence` reports `claims_in=0`
— the number a newsletter reports. `claims_offered` counts what the MODEL PUT in the lanes, so
the denominator survives a pass that dropped everything.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field as dataclass_field, replace
from datetime import datetime
from typing import Any, Protocol

from genios_engine.capture.semantic.cache import (
    ExtractionCacheKey, ExtractionCacheStore, cache_key, cached_extraction)
from genios_engine.capture.documents.pages import PageMap
from genios_engine.capture.semantic.evidence_binder import (
    PREPARED_FRAME_PREFIX, AlignedSpan, BindOutcome, BoundClaim, ClaimDraft, ModelSpan,
    align_span, bind_evidence)
from genios_engine.capture.semantic.injection import FencedContent, fence, scan_output
from genios_engine.capture.semantic.profiles import (
    BLOCK_MARKERS, CONTENT_MARKER, END_MARKER, ENVELOPE_MARKER, NON_EMPHASISABLE_FIELDS, TIERS,
    ExtractionProfile, get_profile, render_prompt)
from genios_engine.capture.semantic.open_lane import OpenLaneStore
from genios_engine.capture.semantic.schema_gen import generate_schema_block
from genios_engine.capture.semantic.sink_guard import guard_typed_sink, sift_untyped_lanes
from genios_engine.capture.semantic.vocabulary import (
    DECISION_STATE, DEPENDENCY_TYPE, ENTITY_TYPE, INTENT, STANCE, vocabulary_block,
    vocabulary_fingerprint, vocabulary_sets)
from genios_engine.capture.validate.canonical import fill_canonical_hints
from genios_engine.capture.validate.dates import resolve_date
from genios_engine.capture.validate.schema import (
    ExtractionVocabulary, SchemaReport, ValidationStage, validate_extraction_schema)
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import (
    Commitment, DecisionState, Dependency, EntityMention, ExtractionResult,
    UnclassifiedObservation)
from genios_engine.contracts.parked import ParkedEvent
from genios_engine.contracts.prepared_content import PreparedContent
from genios_engine.contracts.units import Money, ResolvedDate
from genios_engine.contracts.validators import require_aware, require_bp, require_text

log = logging.getLogger(__name__)

#: `ExtractionResult.schema_version`, and the `EXTRACTION_SCHEMA_VERSION` component of the
#: L1.4.9 cache key. Hand-authored and bumped by hand, NOT derived from the generated schema
#: block: `open_lane.promote_kind` instructs a promoter to "set EXTRACTION_SCHEMA_VERSION" as
#: part of the vocabulary edit, and a digest nobody can set would make that instruction
#: unfollowable. It must equal `capture/structured/mapper.STRUCTURED_SCHEMA_VERSION` — the two
#: lanes write one table and a key that means two things is not a key. `test_extractor.py`
#: asserts the equality rather than importing it here, because the semantic lane learning its
#: schema version from the structured lane is a dependency in the wrong direction.
EXTRACTION_SCHEMA_VERSION = "1"

#: What a park row calls this seam. One literal, because a park written under two stage names
#: cannot be drained by one query.
STAGE = "s2_semantic_extraction"

#: The three park reasons doc 04's failure table names, as the codes a drain matches on.
#: `extraction_parse_failed` is the doc's own word; the other two split what it calls "model
#: times out" (no answer arrived — retry with backoff) from an answer that arrived and could not
#: be made to conform (retrying the same prompt against the same content will produce the same
#: shape, so this one waits for a prompt version, not for a backoff).
PARK_CALL_FAILED = "extraction_call_failed"
PARK_PARSE_FAILED = "extraction_parse_failed"
PARK_SCHEMA_FAILED = "extraction_schema_failed"

#: The fourth, and the one the doc's table has no row for because the doc never imagined a
#: SUCCESSFUL call producing nothing. An answer that types and conforms and carries no claim at
#: all is not an extraction of the message; it is a fact about the answer. Same `ParkedEvent`,
#: same `STAGE`, same `trace` shape as the other three — the park vocabulary in
#: `capture/parked/` is one notion and this is a reason inside it, not a second kind of park.
#: Re-adjudicable in the drain's sense (the retained payload can answer it again) once the
#: prompt or the vocabulary moves, which is exactly what `PARK_SCHEMA_FAILED` waits for too.
PARK_TOTAL_LOSS = "extraction_total_loss"

#: One call plus ONE repair retry, and the doc says one for a reason: a second repair is a third
#: charge for a model that has now failed twice to answer in the shape it was shown, and the
#: park lane exists precisely so that failure is recorded rather than paid for repeatedly.
MAX_MODEL_CALLS = 2

#: The floor values an unusable `intent` / `stance` falls back to. Both are the least-committal
#: member of their closed set: `inform` says only that the message states something, `neutral`
#: says only that it takes no side. Substituting the floor is not inventing a claim — it is
#: REFUSING the one the model made up, in a field the contract requires to be present, and the
#: substitution is counted in `vocabulary_rejects` so a prompt that keeps missing the set is
#: visible. The alternative — failing the whole extraction over one bad word — loses every
#: commitment in the message to save a scalar nothing branches on alone.
INTENT_FLOOR = "inform"
STANCE_FLOOR = "neutral"

#: `EventEnvelope.direction`. Three values because a message between two colleagues is neither
#: inbound nor outbound and calling it either one reverses who is waiting on whom.
DIRECTIONS = ("inbound", "outbound", "internal")

#: The `ExtractionResult` fields this module writes ABOUT the call rather than reads out of the
#: answer — the provenance five, the token counts, and `all_evidence`, which is derived from the
#: claims rather than supplied. `field_confidence` is deliberately NOT here: L1.4.2 refuses to
#: let a profile EMPHASISE it, but the schema block does ask for it and the parser does read it.
EXTRACTOR_WRITTEN_FIELDS = NON_EMPHASISABLE_FIELDS - {"field_confidence"}

#: Everything the model is asked to answer with, derived from the contract rather than listed —
#: a field added to `ExtractionResult` becomes answerable the day it lands. `answered_fields`
#: counts the payload's keys against this set, and a payload that hits NONE of them has not
#: answered: `{}` decodes, is a legal mapping, and would otherwise build a conforming, claim-free
#: extraction that gets cached as "this message said nothing".
ANSWERABLE_FIELDS = frozenset(ExtractionResult.model_fields) - EXTRACTOR_WRITTEN_FIELDS


#: A date draft carries no confidence — `ResolvedDate` has no such field, deliberately (ALG-08
#: drops an unresolved date rather than discounting it). The binder requires a value on every
#: draft, so dates carry this one and nothing ever reads it back.
_DATE_DRAFT_CONFIDENCE_BP = 10_000

#: The claim lanes, in `ExtractionResult` declaration order. Order is not cosmetic: it is the
#: order claims are bound in, which is the order `all_evidence` ends up in, which is what a
#: content address over the result would hash.
CLAIM_FIELDS = ("entity_mentions", "dates_mentioned", "commitments", "decision_states",
                "dependencies", "unclassified_observations")

#: Every lane a claim can arrive in: the six above, which carry receipts, plus `amounts`, whose
#: receipt is its own `as_written`. Spelled as an extension of `CLAIM_FIELDS` rather than as a
#: second list, so a lane added there is counted here the same day. This is the set the
#: total-loss test is taken over — an answer that kept one amount and lost six commitments still
#: extracted something from the message, and is a partial loss, not a total one.
CLAIM_BEARING_FIELDS = (*CLAIM_FIELDS, "amounts")

#: The label a commitment's own `due` date is bound under. Distinct from `dates_mentioned` so a
#: dropped deadline is legible as a dropped deadline in the counters rather than as one of a
#: message's several dates.
COMMITMENT_DUE_FIELD = "commitments.due"

#: Marker literals an envelope value may not carry. The envelope is assembled from HEADERS, and
#: a display name is as attacker-controlled as a body: "Priya [CONTENT]" in a From: line would
#: open a second content section inside the instruction spine, above the fence entirely.
_STRUCTURAL_MARKERS = (*BLOCK_MARKERS, END_MARKER, ENVELOPE_MARKER, CONTENT_MARKER)

#: Everything that is whitespace, for the envelope's one-line rule. A newline in a header value
#: is header injection wearing different clothes.
_WHITESPACE = re.compile(r"\s+")

#: How much of a rejected answer a PARK ROW records. The park row is storage a human reads, not
#: a prompt a model reads — see `repair_prompt` for why the repair never quotes the answer back.
PARK_EXCERPT_CHARS = 1_200

#: The repair block's marker, in the same bracketed-uppercase family as the profile's six.
REPAIR_MARKER = "[REPAIR]"

#: The offset-frame block's marker, same family, same reason: a block a model can see the edge
#: of is a block it reads as one instruction rather than as a sentence trailing off the envelope.
OFFSET_FRAME_MARKER = "[OFFSET FRAME]"

#: The frame statement itself, as a template over the content's own length.
#:
#: It names the frame in the only terms a counter can act on, and every line is a failure that
#: has actually been paid for:
#:
#: * *offset 0 is the first character after the opening marker's newline* — the whole defect.
#:   L1.4.2's EVIDENCE block says "the content shown below", and what is shown below begins with
#:   the fence's opening marker line, so a model counting from the first visible character is off
#:   by that line and every span it cites comes back `VERIFIED_RELOCATED` at `bp * 9 // 10`;
#: * *the content is exactly N characters* — a bound the model can check its own answer against,
#:   and the one number that makes "which string" concrete rather than descriptive;
#: * *count Unicode characters* — Python slices by code point, so an emoji is one character here
#:   and two in a model counting UTF-16 units, and a CRLF is two characters rather than one;
#: * *nothing above the fence is counted* — the schema block, the vocabulary and this very
#:   instruction are thousands of characters the model can see and must not count.
#:
#: The markers are DESCRIBED, never quoted: writing the opening marker into the instruction
#: spine would put a second copy of it in the prompt, and `check_placement` refuses a prompt
#: where two regions claim to be the untrusted one — correctly, because the model would then
#: pick. Same reason `CONTENT_MARKER` is not written here either.
OFFSET_FRAME_BLOCK = (
    "Every start_offset and end_offset you return is measured against the CONTENT ALONE — the "
    "text INSIDE the fenced region below, with both fence marker lines excluded.\n"
    "- Offset 0 is the first character of the line AFTER the line that opens the fenced region.\n"
    "- The two marker lines, and the newline that ends the opening one, are not part of the "
    "content and are not counted.\n"
    "- The content is exactly {content_chars} characters long, so every offset you return is "
    "between 0 and {content_chars}.\n"
    "- Count Unicode characters, not bytes and not UTF-16 code units: an emoji or any character "
    "outside the Basic Multilingual Plane is ONE character, and a Windows line ending is TWO (a "
    "carriage return, then a newline).\n"
    "- Nothing above the fenced region is counted at all — not these instructions, not the "
    "schema, not the vocabulary, not the envelope."
)


def offset_frame_block(content_chars: int) -> str:
    """The frame statement for a content of this length, marker and all. One public callable.

    A function rather than a constant because the statement carries the content's own length,
    and that number is the half of it a model can verify its own arithmetic against.
    """
    if content_chars < 1:
        raise ValueError("an offset frame over zero characters describes nothing; empty content "
                         "is refused one function up, before a token is spent")
    return f"{OFFSET_FRAME_MARKER}\n{OFFSET_FRAME_BLOCK.format(content_chars=content_chars)}"


# =============================================================================================
# The transport seam. The fence, the cache and the two routers are the siblings' (see the module
# docstring); the model client is this module's own, because L1.4.3 is the only call site.
# =============================================================================================


class LLMResponse(Protocol):
    """One model answer, in the shape `context/llm/client.LLMResult` already has.

    Duck-typed rather than imported: `capture/` must not learn its result type from `context/`
    (the import-direction ratchet), and W4 gives L1 its own client. `parsed` is the decoded JSON
    object — `{}` when decoding failed — and `ok` / `error` carry a transport failure without
    pretending it produced text.
    """

    parsed: dict[str, Any]
    raw: str
    input_tokens: int
    output_tokens: int
    model: str
    ok: bool
    error: str | None


class LLMClient(Protocol):
    """The single call site's transport. `model` is the EXACT snapshot id, not a family name.

    The client must be constructed at `temperature=0` — doc 04 states it, and this module checks
    it in `_require_deterministic` when the client exposes the attribute at all, because a
    temperature the extractor cannot see is a replay it cannot promise.
    """

    @property
    def model(self) -> str: ...

    def call(self, prompt: str, *, max_tokens: int = 4096) -> LLMResponse: ...


# =============================================================================================
# The typed inputs and outputs.
# =============================================================================================


@dataclass(frozen=True)
class EventEnvelope:
    """Direction, parties and thread position — the facts an extraction is otherwise blind to.

    Doc 04 states the consequence in one line and it is not hypothetical: *"without it an
    outbound offer reads as an inbound request — a bug that already occurred and was fixed once;
    do not regress it."* A model shown only "we can do $84K" cannot tell who is offering.

    Every value is sanitised on the way into the prompt (`_envelope_block`), because headers are
    as attacker-controlled as bodies and the envelope sits ABOVE the fence, inside the
    instruction spine.
    """

    direction: str
    sender: str = ""
    recipients: tuple[str, ...] = ()
    thread_position: int = 1
    thread_depth: int = 1
    subject: str = ""

    def __post_init__(self) -> None:
        if self.direction not in DIRECTIONS:
            raise ValueError(f"direction must be one of {DIRECTIONS}, got {self.direction!r}. "
                             "An unknown direction is the outbound-reads-as-inbound bug with an "
                             "extra step.")
        if self.thread_position < 1 or self.thread_depth < 1:
            raise ValueError("thread_position and thread_depth are 1-based counts of messages")
        if self.thread_position > self.thread_depth:
            raise ValueError(
                f"thread_position {self.thread_position} is past thread_depth "
                f"{self.thread_depth} — a message cannot be the fourth of three")
        if isinstance(self.recipients, (str, bytes)) or not isinstance(self.recipients, Sequence):
            raise TypeError("recipients must be a sequence of strings, not one string")
        object.__setattr__(self, "recipients", tuple(str(r) for r in self.recipients))


@dataclass(frozen=True)
class ExtractionRequest:
    """Everything one extraction needs, resolved. No clock, no settings, no ambient anything.

    `profile_id` and `tier` are DECIDED BEFORE this object exists — by L1.4.1 and L1.4.10, from
    deterministic counts S1 produced. They are carried rather than computed here so that the one
    module allowed to call a model is not also the module that decides how much that call costs.

    `eval_time` is the instant every relative date resolves against, and it is a parameter for
    the reason the whole layer keeps saying: a March event's "next week" has to keep resolving to
    March, and a clock read inside the pipeline makes a replay a different extraction.
    """

    org_id: str
    event_id: str
    source: str
    profile_id: str
    tier: str
    prepared: PreparedContent
    envelope: EventEnvelope
    eval_time: datetime
    #: The ORG's timezone — ALG-09 resolves in it and stores UTC.
    timezone: str = "UTC"
    #: The CONNECTION's declared locale, or None when it declares none. Threaded to ALG-09 for
    #: the day-month ambiguity; never guessed.
    locale: str | None = None
    max_output_tokens: int = 4096
    #: L1.3.4-U5 · where this event's text divides into PAGES, when it has any. Read off the
    #: document metadata the connector attached and passed straight through to the alignment
    #: seam, which is the only place that holds both a span's offsets and the map they resolve
    #: against. `PageMap()` — the empty map — for an email, a chat message, a calendar event.
    page_map: PageMap = dataclass_field(default_factory=PageMap)
    #: The heading this event's text sits under, when the chunker found one. A property of the
    #: whole event rather than of an offset: an upload chunk IS one section, and a message has
    #: none. `None` is the ordinary case.
    section: str | None = None

    def __post_init__(self) -> None:
        require_text(self.org_id, "org_id")
        require_text(self.event_id, "event_id")
        require_text(self.source, "source")
        require_text(self.profile_id, "profile_id")
        require_text(self.timezone, "timezone")
        require_aware(self.eval_time, "eval_time")
        if self.tier not in TIERS:
            raise ValueError(f"tier must be one of {TIERS}, got {self.tier!r} — the tier is "
                             "L1.4.10's answer and the model never picks its own")
        if not isinstance(self.prepared, PreparedContent):
            raise TypeError("prepared must be a PreparedContent — the offsets every span in the "
                            "extraction carries are measured against its clean_text")
        if not isinstance(self.envelope, EventEnvelope):
            raise TypeError("envelope must be an EventEnvelope")
        if self.max_output_tokens < 1:
            raise ValueError("max_output_tokens must be positive")
        if not isinstance(self.page_map, PageMap):
            raise TypeError("page_map must be a documents.pages.PageMap — an unvalidated list of "
                            "offsets is how a citation ends up naming a page the quote is not on")

    @property
    def content(self) -> str:
        """The text the model is shown, and the text every offset is measured against."""
        return self.prepared.clean_text

    @property
    def source_ref(self) -> str:
        """C-01's prepared frame for this content. One place, so no span is stamped by hand."""
        return f"{PREPARED_FRAME_PREFIX}{self.prepared.prepared_content_id}"

    @property
    def profile(self) -> ExtractionProfile:
        """The registered profile, or the email fallback. `get_profile` never raises."""
        return get_profile(self.profile_id)


@dataclass(frozen=True)
class AssembledCall:
    """U1's output: the prompt, and every component of the key that will cache its answer.

    The pairing is the unit's whole point. A caller that fetched the prompt from one place and
    its version from another would eventually cache an answer under the name of a prompt that
    did not produce it — which is a stale hit that looks like a fresh one, and is exactly the
    260-extraction failure doc 04 tells this wave not to repeat.
    """

    profile_id: str
    tier: str
    prompt: str
    prompt_version: str
    schema_version: str
    vocab_fingerprint: str
    #: Everything this module substitutes ABOVE the fence: the envelope block, then the offset
    #: frame statement. Carried as ONE string because it is one cache-key component and they are
    #: one edit — a key that moved when the envelope changed but not when the frame statement did
    #: would serve a row extracted under a frame nobody had stated for a prompt that states one.
    envelope: str
    #: L1.4.7's own object, carried whole rather than reduced to a nonce. The repair render needs
    #: the same fence, `scan_output` needs it to grade the answer, and `span_is_escaped` needs it
    #: to say whether a quote that will not verify crossed a character WE altered.
    fenced: FencedContent
    content_chars: int

    @property
    def fence_nonce(self) -> str:
        return self.fenced.nonce


@dataclass(frozen=True)
class ExtractionDiagnostics:
    """What one parse had to refuse, and why. The honest half of an extraction.

    Every counter here is a claim that did not reach the result, or reached it differently from
    the way the model stated it. They are reported rather than logged-and-forgotten because each
    one is a prompt problem wearing a different hat: `vocabulary_rejects` means the closed sets
    are not landing, `confidence_rejects` means the model is writing ratios, `unknown_fields`
    means it is inventing field names again (268 of them in one org, once), and
    `ungrounded_amounts` is the golden corpus's hard-fail metric arriving early enough to fix.
    """

    #: Claim-bearing entries the MODEL PUT in the seven lanes, before this module refused any of
    #: them. The denominator every other counter here was missing: each of the rest counts a
    #: REFUSAL, and a refusal at `_confidence` or `_build_claim` happens before `claims_in` is
    #: incremented — so an answer whose four commitments all carried `0.9` reported `claims_in=0`,
    #: which is the number a newsletter reports. This one separates the two.
    claims_offered: int = 0
    #: How many of `ANSWERABLE_FIELDS` the payload named at all. Zero means the answer answered
    #: nothing — `{}` decodes and is a legal mapping — which is a total loss rather than a
    #: message that said nothing.
    answered_fields: int = 0
    claims_in: int = 0
    claims_bound: int = 0
    synthesized_spans: int = 0
    no_evidence_drops: int = 0
    unalignable_spans: int = 0
    vocabulary_rejects: int = 0
    confidence_rejects: int = 0
    contract_rejects: int = 0
    fractional_rejects: int = 0
    unresolved_dates: int = 0
    #: Citations whose region overlaps a character L1.4.7's escape pass altered. Counted, never
    #: dropped: such a quote may fail to verify for OUR reason rather than the model's, and
    #: `FencedContent.span_is_escaped` exists precisely so the two are not confused.
    escaped_span_quotes: int = 0
    #: Citations whose quote is NOT the content's own bytes at the offsets the model stated —
    #: it quoted correctly and counted in some other frame. The monitor on `OFFSET_FRAME_BLOCK`:
    #: nothing is dropped (ALG-08 relocates such a span and charges `bp * 9 // 10` for it), but a
    #: rise here says the frame statement stopped landing, which is a ~10% tax on every receipt
    #: the prompt produces and is otherwise invisible — a relocated span looks like a working one.
    #: Spans over a character L1.4.7 escaped are excluded: those are OUR edit, counted above.
    offset_frame_misses: int = 0
    #: `injection.scan_output` findings on the answer — an echoed instruction, a forged frame, a
    #: forbidden field attempted. Advisory by that unit's own construction: the schema is what
    #: refuses a forbidden field, and this module records rather than parks.
    output_findings: tuple[str, ...] = ()
    #: Top-level keys the model invented, sorted. Ignored by the parser — doc 04's failure table
    #: says so — and named here so "the model is inventing fields again" is a number rather than
    #: a rumour.
    unknown_fields: tuple[str, ...] = ()
    #: `as_written` of every amount whose literal is NOT in the source text. NOT dropped here:
    #: ALG-08 drops it, and the golden gate measures it. See the module docstring.
    ungrounded_amounts: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedExtraction:
    """U3's output: the extraction, the schema verdict on it, and what it cost in refusals.

    `result` is None only when the payload was not a JSON object at all — everything softer than
    that produces a result with fewer claims in it, because losing a message over one malformed
    commitment is the failure the open lane and the binder were both built to end.

    `usable` is the question U4 actually asks, and it is deliberately stricter than "did we build
    an object": an `ExtractionResult` with a blocking schema violation is a well-typed object
    that S-1..S-9 refuse, and shipping it because it constructed would put the refusal off until
    a layer that cannot read it.
    """

    result: ExtractionResult | None
    report: SchemaReport | None
    diagnostics: ExtractionDiagnostics
    failure: str | None = None
    #: The result types, conforms, and contains NOTHING — and the answer is not one a message
    #: that genuinely said nothing would have produced. `total_loss_failure` draws the line and
    #: the module docstring states which side is which; the flag is carried so U4 can park it
    #: under its own reason instead of filing it as a schema failure, which it is not.
    total_loss: bool = False

    @property
    def usable(self) -> bool:
        """The question U4 asks: may this be returned, and therefore CACHED?

        A total loss fails it. That is the whole of D2's fix and it belongs on this property
        rather than at the call site: `cached_extraction` stores whatever the thunk returns, so
        an extraction that reached the thunk is an extraction that is stored forever, and the
        re-run then answers from it with zero model calls. The one place to refuse is before the
        thunk returns.
        """
        return (self.result is not None and self.report is not None and self.report.conforms
                and not self.total_loss)


@dataclass(frozen=True)
class ExtractionOutcome:
    """U4's output: one extraction, or one park row, and the ledger either way.

    Both halves are returned rather than raised so a drain can record what a failure COST — a
    parked event whose token counts are lost is a bill nobody can attribute.
    """

    event_id: str
    result: ExtractionResult | None
    parked: ParkedEvent | None
    #: L1.4.9's key with its components still legible, not just their digest — a stale-cache
    #: diagnosis starts by asking WHICH component failed to change, and a bare hash cannot say.
    cache_key: ExtractionCacheKey
    cache_hit: bool
    model_calls: int
    input_tokens: int
    output_tokens: int
    tier: str
    diagnostics: ExtractionDiagnostics
    report: SchemaReport | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.parked is None):
            raise ValueError("an outcome is exactly one of an extraction or a park row; "
                             "neither would be a silent drop and both would be a lie")

    @property
    def ok(self) -> bool:
        return self.result is not None

    @property
    def processing_key(self) -> str:
        """The `l1_extraction_results` primary key this extraction is filed under."""
        return self.cache_key.processing_key


# =============================================================================================
# L1.4.3-U1 · call assembly
# =============================================================================================


def _sanitise_envelope_value(value: str) -> str:
    """One line, no structural markers. The envelope sits above the fence, so it must not be
    able to open a block of its own.

    Whitespace collapses rather than being rejected: a display name with a newline in it is
    ordinary mail-client output as often as it is an attack, and refusing the message would
    lose a real email to protect against a header that has already been defanged by flattening.
    A marker literal is removed, not escaped, because there is no rendering of `[CONTENT]`
    inside a From: line that a reader needs.
    """
    flattened = _WHITESPACE.sub(" ", str(value)).strip()
    for marker in _STRUCTURAL_MARKERS:
        if marker in flattened:
            log.warning("envelope value contained the structural marker %r; removing it", marker)
            flattened = flattened.replace(marker, "")
    return _WHITESPACE.sub(" ", flattened).strip()


def _envelope_block(envelope: EventEnvelope) -> str:
    """The envelope as the prompt's `{envelope}` substitution — fixed key order, one line each.

    Fixed order is what makes the prompt a stable string, which is what makes a content address
    over it mean anything. An absent field is OMITTED rather than rendered empty: "to:" with
    nothing after it reads to a model as a message sent to nobody, which is a fact the envelope
    does not have.
    """
    lines = [f"direction: {envelope.direction}"]
    sender = _sanitise_envelope_value(envelope.sender)
    if sender:
        lines.append(f"from: {sender}")
    recipients = [_sanitise_envelope_value(r) for r in envelope.recipients]
    recipients = [r for r in recipients if r]
    if recipients:
        lines.append(f"to: {', '.join(recipients)}")
    subject = _sanitise_envelope_value(envelope.subject)
    if subject:
        lines.append(f"subject: {subject}")
    lines.append(f"thread position: message {envelope.thread_position} of {envelope.thread_depth}")
    return "\n".join(lines)


def envelope_chars(envelope: EventEnvelope) -> int:
    """How many characters this envelope adds to the prompt.

    The one term L1.4.8's cost governor cannot measure for itself — the envelope is built per
    event from that event's headers, so `batch.ExtractionRequest` takes its length as a declared
    value and charges for it. Measured off `_envelope_block`, the same function that renders the
    substitution, so adding a field to `EventEnvelope` re-prices the call instead of silently
    under-charging it against the 512-character default.
    """
    return len(_envelope_block(envelope))


def assemble_call(request: ExtractionRequest, *, nonce: str | None = None) -> AssembledCall:
    """L1.4.3-U1 · build the final prompt from profile + schema + vocab + envelope + content.

    The doc's assembly line, with the four substitutions coming from the four modules that own
    them: the shape from `schema_gen` (generated from `ExtractionResult`, so the prompt cannot
    drift from the type it must produce), the words from `vocabulary` (independent of the rule
    vocabulary, so discovery is not capped at what somebody already wrote a rule for), the
    envelope from the event, and the content from L1.4.7's fence.

    The content is checked against the profile's own cap BEFORE fencing, with the fence's
    overhead reserved. Doing it after would fail a message that fits by a margin thinner than
    the delimiter — and `render_prompt` refuses to truncate on purpose, because a truncated
    extraction looks complete and is not. Chunking is the caller's job with the profile's
    `chunk_strategy`; every chunk then carries offsets that resolve.

    `nonce` exists for exactly two callers, and L1.4.7 names both: a test, which cannot
    otherwise build a payload containing the fence it is testing, and a replay that must
    reproduce a stored prompt byte for byte. Production omits it and gets 64 fresh bits.

    The OFFSET FRAME statement rides in the envelope substitution, which is the only lever this
    module has above the fence: L1.4.2 owns the template, and L1.4.7 forbids anything after the
    close marker. It says which string the model's offsets index — `fenced.body`, whose offsets
    are `prepared.clean_text`'s offsets because the escape pass is one code point for one — and
    it is part of `AssembledCall.envelope` and therefore of the cache key, because a row taken
    when the prompt did not state a frame is not an answer to a prompt that does.

    The assembled prompt is handed straight back to `FencedContent.check_placement`, which is
    L1.4.7-U1's own audit of where a fence must sit: exactly one delimited region, the SAFETY
    block before it, and NOTHING after it. Rendering and then not checking would leave the guard
    as a comment — the failure it catches is a template edit that moves the content substitution,
    which no test of the guard in isolation can see.
    """
    profile = request.profile
    content = request.content
    if not content.strip():
        raise ValueError(
            f"{request.event_id}: prepared content is empty — a model asked to extract from "
            "nothing invents, which is the one thing this group may not pay for")

    fenced = fence(content, nonce=nonce)
    overhead = len(fenced.text) - len(content)
    if len(content) + overhead > profile.max_input_chars:
        raise ValueError(
            f"{profile.profile_id}: {len(content)} characters plus a {overhead}-character fence "
            f"is over the {profile.max_input_chars} this profile fits in one call. Chunk it with "
            f"the {profile.chunk_strategy!r} strategy and assemble each chunk; nothing here "
            "truncates, because a truncated extraction looks complete and is not.")

    envelope = f"{_envelope_block(request.envelope)}\n\n{offset_frame_block(len(content))}"
    rendered = render_prompt(profile.profile_id, schema=generate_schema_block(),
                             vocab=vocabulary_block(), envelope=envelope, content=fenced.text)
    fenced.check_placement(rendered.text)
    return AssembledCall(
        profile_id=profile.profile_id,
        tier=request.tier,
        prompt=rendered.text,
        prompt_version=rendered.prompt_version,
        schema_version=EXTRACTION_SCHEMA_VERSION,
        vocab_fingerprint=vocabulary_fingerprint(),
        envelope=envelope,
        fenced=fenced,
        content_chars=len(content),
    )


# =============================================================================================
# L1.4.3-U3 · response parsing  (derived — see the module docstring)
# =============================================================================================


@dataclass
class _Tally:
    """The mutable accumulator behind `ExtractionDiagnostics`. Frozen on the way out."""

    claims_offered: int = 0
    answered_fields: int = 0
    claims_in: int = 0
    claims_bound: int = 0
    synthesized_spans: int = 0
    no_evidence_drops: int = 0
    unalignable_spans: int = 0
    vocabulary_rejects: int = 0
    confidence_rejects: int = 0
    contract_rejects: int = 0
    fractional_rejects: int = 0
    unresolved_dates: int = 0
    escaped_span_quotes: int = 0
    offset_frame_misses: int = 0
    unknown_fields: set[str] = dataclass_field(default_factory=set)
    ungrounded_amounts: list[str] = dataclass_field(default_factory=list)

    def freeze(self) -> ExtractionDiagnostics:
        return ExtractionDiagnostics(
            claims_offered=self.claims_offered, answered_fields=self.answered_fields,
            claims_in=self.claims_in, claims_bound=self.claims_bound,
            synthesized_spans=self.synthesized_spans, no_evidence_drops=self.no_evidence_drops,
            unalignable_spans=self.unalignable_spans,
            vocabulary_rejects=self.vocabulary_rejects,
            confidence_rejects=self.confidence_rejects,
            contract_rejects=self.contract_rejects,
            fractional_rejects=self.fractional_rejects,
            unresolved_dates=self.unresolved_dates,
            escaped_span_quotes=self.escaped_span_quotes,
            offset_frame_misses=self.offset_frame_misses,
            unknown_fields=tuple(sorted(self.unknown_fields)),
            ungrounded_amounts=tuple(self.ungrounded_amounts))


@dataclass
class _Pending:
    """One draft on its way through the binder, with the payload it will be rebuilt from.

    The payload rides along because `ClaimDraft` deliberately carries only what the BINDER needs
    — a field name, the words to search for, a confidence and any receipts — and rebuilding a
    `Commitment` afterwards needs the actor, the beneficiary and the condition too. Matching the
    bound claims back by object identity (`bound.draft is pending.draft`) rather than by value:
    two commitments can legitimately be identical drafts, and a value match would rebuild one of
    them twice and lose the other.
    """

    draft: ClaimDraft
    payload: Mapping[str, Any]


def _text(value: Any) -> str | None:
    """A non-empty string, or None. The model's `null` and its `""` mean the same thing here."""
    return value.strip() if isinstance(value, str) and value.strip() else None


def _verbatim_text(value: Any) -> str | None:
    """Like `_text` but UNSTRIPPED — for `as_written`, whose whole contract is the source's bytes.

    Whitespace is still what decides emptiness; only the returned value keeps its edges, because
    an `as_written` this module stripped would no longer be findable in the source by the exact
    match ALG-08 does.
    """
    return value if isinstance(value, str) and value.strip() else None


def _confidence(value: Any, label: str, tally: _Tally) -> int | None:
    """The model's own per-claim confidence, in integer basis points, or None to drop the claim.

    There is no coercion and there will not be one. `0.87` is the shape a model reaches for and
    it is refused because there is no safe reading of it: 0.87 could be 8700 bp or 87 bp, `1`
    could be 10000 bp or 1 bp, and inventing the answer would put a number nobody wrote into the
    composition at ALG-13. The claim is dropped and counted, and the repair retry gives the model
    one chance to answer in the units the SCHEMA block already spells out.
    """
    try:
        return require_bp(value, label)
    except (TypeError, ValueError):
        tally.confidence_rejects += 1
        log.warning("dropping a claim whose %s was not integer basis points: %r", label, value)
        return None


def _closed(value: Any, allowed: frozenset[str], label: str, tally: _Tally) -> str | None:
    """One value against one closed set, case-folded, or None.

    Case folding is the only normalisation: `"Commit"` and `"commit"` are unambiguously one word
    and a model that shouted is not a model that invented. Anything else — a plural, an
    abbreviation, a word off the list — is a rejection, because bending it to the nearest member
    is precisely the guess the VOCAB block tells the model not to make on its own behalf.
    """
    text = value.strip().lower() if isinstance(value, str) else ""
    if text in allowed:
        return text
    tally.vocabulary_rejects += 1
    log.warning("%s: %r is not in the closed set %s", label, value, sorted(allowed))
    return None


def _boolean(value: Any) -> bool | None:
    """A JSON boolean, or the two unambiguous strings for one. Anything else is None.

    `"true"` is JSON-adjacent enough that refusing it would lose real commitments to a quoting
    habit, and it carries no ambiguity at all. A `1`, by contrast, is refused: an integer in a
    boolean field is a model answering a different question, and `Commitment.is_conditional`
    has no default precisely so that "we did not read a condition" cannot be spelled the same
    way as "there is no condition".
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    return None


def _string_list(value: Any) -> list[str]:
    """The three free-text lanes — topics, implied actions, questions. Non-strings drop out."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [text for text in (_text(item) for item in value) if text is not None]


def _has_fraction(value: Any) -> bool:
    """Does anything anywhere in this open-lane value carry a float?

    `ExtractionResult` refuses fractions inside `roles` / `relationships` /
    `scheduling_proposals` at construction — V-7's rule, one layer early — and it refuses the
    WHOLE LIST. So the check runs per entry here and the offending entry alone is dropped:
    losing one malformed scheduling proposal is a gap, losing the extraction is a message.
    """
    if isinstance(value, bool) or value is None or isinstance(value, (str, bytes, int)):
        return False
    if isinstance(value, float):
        return True
    if isinstance(value, Mapping):
        return any(_has_fraction(item) for item in value.values())
    if isinstance(value, Sequence):
        return any(_has_fraction(item) for item in value)
    return False


def _open_lane_entries(value: Any, tally: _Tally) -> list[dict[str, Any]]:
    """`roles` / `relationships` / `scheduling_proposals` — untyped by design, fraction-free."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    kept: list[dict[str, Any]] = []
    for entry in value:
        if not isinstance(entry, Mapping):
            tally.contract_rejects += 1
            continue
        if _has_fraction(entry):
            tally.fractional_rejects += 1
            log.warning("dropping an open-lane entry containing a float: %r", entry)
            continue
        kept.append({str(key): item for key, item in entry.items()})
    return kept


def _spans_from_payload(value: Any, request: ExtractionRequest, call: AssembledCall,
                        tally: _Tally) -> tuple[EvidenceSpan, ...]:
    """The model's citations, aligned into the prepared frame. Unusable ones drop out silently
    counted, leaving the claim to the binder's recovery pass.

    A citation whose quote is not the content's own bytes at the offsets it stated is KEPT and
    counted (`offset_frame_misses`). It is not a rejection and must not become one: the model
    quoted correctly and counted in the wrong frame, which is precisely the case ALG-08's
    relocation step exists for. The count is the monitor on `OFFSET_FRAME_BLOCK` — see the
    module docstring for what an unstated frame costs.

    A missing or non-integer `start_offset` becomes 0 rather than a rejection. That is a PROBE,
    not a claim about position: ALG-08's verification cascade relocates a span whose quote is
    real and whose offsets are wrong, grading it `VERIFIED_RELOCATED` and discounting it for the
    correction — which is exactly the treatment a model that quoted correctly and counted badly
    has earned. Rejecting the span instead would send a perfectly good quote to the binder as
    "no evidence".
    """
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    spans: list[EvidenceSpan] = []
    for entry in value:
        if not isinstance(entry, Mapping):
            tally.unalignable_spans += 1
            continue
        quote = entry.get("quote")
        if not isinstance(quote, str) or not quote.strip():
            tally.unalignable_spans += 1
            continue
        start = entry.get("start_offset")
        view_start = start if isinstance(start, int) and not isinstance(start, bool) else 0
        if view_start < 0:
            view_start = 0
        aligned = align_span(ModelSpan(quote=quote, view_start=view_start,
                                       view_end=view_start + len(quote)),
                             request.prepared, source_ref=request.source_ref)
        if aligned is None:
            tally.unalignable_spans += 1
            continue
        aligned = _located(aligned, request)
        if call.fenced.span_is_escaped(view_start, view_start + len(quote)):
            tally.escaped_span_quotes += 1
        elif request.content[aligned.prepared_start:aligned.prepared_end] != quote:
            # The quote is real and the arithmetic is not: the model counted in a frame that is
            # not the one `OFFSET_FRAME_BLOCK` states. ALG-08 will relocate it and charge
            # `bp * 9 // 10`, so nothing is lost — but a relocated span is indistinguishable
            # from a working one downstream, and a prompt that stopped stating its frame would
            # tax every receipt in the org with no number anywhere naming the day it started.
            # Escaped spans are excluded: their mismatch is OUR edit and is counted above.
            tally.offset_frame_misses += 1
        spans.append(aligned.span)
    return tuple(spans)


def locate_span(span: EvidenceSpan, request: ExtractionRequest, *,
                source_start: int | None = None) -> EvidenceSpan:
    """One span, with its page and section attached. The same answer for every span in an event.

    `source_start` is the span's offset in the ORIGINAL text when the caller already resolved it
    (`align_span` does); otherwise it is resolved here through `PreparedContent.to_source_offset`,
    the map the preprocessor built. The distinction matters: the page map describes the original
    text, and the prepared frame has mask tokens in it whose lengths shift every offset above
    them — so looking a page up by a prepared offset puts every citation below a redacted phone
    number on the wrong page.

    Rebuilt through the constructor rather than `model_copy`, on `EvidenceSpan`'s own terms: the
    type is frozen so that a change is revalidated.
    """
    if source_start is None:
        try:
            source_start = request.prepared.to_source_offset(span.start_offset)
        except Exception:      # noqa: BLE001 — a map that cannot answer costs a page, not a claim
            source_start = None
    page = None if source_start is None else request.page_map.page_at(source_start)
    if page is None and request.section is None:
        return span
    if span.page == page and span.section == request.section:
        return span
    return EvidenceSpan(
        source_ref=span.source_ref, quote=span.quote, start_offset=span.start_offset,
        end_offset=span.end_offset, verified=span.verified,
        page=page, section=request.section)


def _located(aligned: AlignedSpan, request: ExtractionRequest) -> AlignedSpan:
    """L1.3.4-U5 · the human-readable half of a receipt: which page, and which section.

    Attached HERE because this is the one place that holds both halves of the answer — the span's
    resolved offsets and the map they resolve against — and because a page number derived later,
    from a stored span alone, would need the document re-parsed and would silently be a guess when
    it could not be.

    The PAGE is looked up against `source_start`: the map describes the ORIGINAL text, and the
    prepared frame has mask tokens in it whose lengths shift every offset above them. Using the
    prepared offset would put every citation below a redacted phone number on the wrong page,
    which is exactly the class of error the three-frame discipline in `evidence_binder` exists to
    stop. The SECTION is a property of the whole event, not of an offset, so it is copied.

    An unpaged text (an email, a chat message) leaves both None. Nothing is invented: a
    single-page number for something with no pages is a value nobody can check.
    """
    located = locate_span(aligned.span, request, source_start=aligned.source_start)
    return aligned if located is aligned.span else replace(aligned, span=located)


def _locate_bound(outcome: BindOutcome, request: ExtractionRequest) -> BindOutcome:
    """Every bound claim's receipts, with page and section attached. Counters untouched."""
    if not outcome.claims or (not request.page_map and request.section is None):
        return outcome
    claims = tuple(
        replace(claim, evidence=tuple(locate_span(span, request) for span in claim.evidence))
        for claim in outcome.claims)
    return replace(outcome, claims=claims)


def _claim_entries(payload: Mapping[str, Any], field: str) -> list[Mapping[str, Any]]:
    """The list under one claim field, with non-object entries discarded."""
    value = payload.get(field)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [entry for entry in value if isinstance(entry, Mapping)]


#: Which key of a claim payload is the needle the binder searches for when the model cited
#: nothing. It is the model's own words for what it claims, which is what `ClaimDraft.claim_text`
#: is defined to be — an entity's surface form, a commitment's action, an observation's
#: description. A lane whose needle is missing produces an empty needle, which the binder reads
#: as unrecoverable and drops, which is the correct answer for a claim that cannot say what it
#: asserts.
_NEEDLE_KEY = {
    "entity_mentions": "surface_form",
    "dates_mentioned": "as_written",
    "commitments": "action",
    COMMITMENT_DUE_FIELD: "as_written",
    "decision_states": "subject",
    "dependencies": "blocker",
    "unclassified_observations": "description",
}


def _draft(field: str, entry: Mapping[str, Any], request: ExtractionRequest,
           call: AssembledCall, tally: _Tally) -> _Pending | None:
    """One payload entry into a `ClaimDraft`, or None when its confidence is unreadable."""
    needle = _text(entry.get(_NEEDLE_KEY[field])) or ""
    if field in ("dates_mentioned", COMMITMENT_DUE_FIELD):
        confidence_bp: int | None = _DATE_DRAFT_CONFIDENCE_BP
    else:
        confidence_bp = _confidence(entry.get("confidence_bp"), f"{field}.confidence_bp", tally)
        if confidence_bp is None:
            return None
    tally.claims_in += 1
    return _Pending(draft=ClaimDraft(field=field, claim_text=needle, confidence_bp=confidence_bp,
                                     evidence=_spans_from_payload(entry.get("evidence"), request,
                                                                  call, tally)),
                    payload=entry)


def _resolved_date(entry: Mapping[str, Any], evidence: Sequence[EvidenceSpan],
                   request: ExtractionRequest, tally: _Tally) -> ResolvedDate | None:
    """One date claim: the model's words, this machine's window.

    ALG-09 (`capture/validate/dates.py`) resolves `as_written` against the caller's `eval_time`
    in the org's timezone, and the model's own `earliest` / `latest` / `certainty` are read and
    DISCARDED. Three reasons, in order of how much they cost when ignored: a window a model
    computed is not reproducible across replays or machines; the doc's own worked example expects
    "pretty soon" to come back RELATIVE with a derived window, which is row 9 of the cascade and
    not a thing a model was asked; and `ResolvedDate` refuses an incoherent band-and-window pair
    at construction, so a model that says RELATIVE with no window would cost the whole claim.

    A phrase the cascade cannot resolve is still kept — UNRESOLVED with no window is an honest
    "somebody wrote a date-ish thing and we will not guess which day", and it is counted.
    """
    as_written = _verbatim_text(entry.get("as_written"))
    if as_written is None or not evidence:
        return None
    try:
        resolved = resolve_date(as_written, eval_time=request.eval_time, tz=request.timezone,
                                evidence=list(evidence), locale=request.locale)
    except (TypeError, ValueError) as exc:
        tally.contract_rejects += 1
        log.warning("dropping a date claim ALG-09 refused (%s): %r", exc, as_written)
        return None
    if resolved.certainty.value == "unresolved":
        tally.unresolved_dates += 1
    return resolved


def _amounts(payload: Mapping[str, Any], content: str, tally: _Tally) -> list[Money]:
    """`Money` claims, with the ungrounded ones COUNTED AND KEPT. See the module docstring.

    `Money` is the one claim type carrying no `evidence` list — its receipt is `as_written`
    itself, which C-02 defines as the source's own bytes — so "is this amount real" is answered
    by looking for the literal in the text. That answer is ALG-08's to act on and the golden
    corpus's to grade; a filter here would make the gate report zero fabrications for every
    prompt ever written, including one that invents an amount in every message.
    """
    kept: list[Money] = []
    for entry in _claim_entries(payload, "amounts"):
        as_written = _verbatim_text(entry.get("as_written"))
        currency = _text(entry.get("currency"))
        if as_written is None or currency is None:
            tally.contract_rejects += 1
            continue
        try:
            money = Money(minor_units=entry.get("minor_units"), currency=currency.upper(),
                          as_written=as_written)
        except (TypeError, ValueError) as exc:
            tally.contract_rejects += 1
            log.warning("dropping a malformed amount (%s): %r", exc, entry)
            continue
        if money.as_written not in content:
            tally.ungrounded_amounts.append(money.as_written)
        kept.append(money)
    return kept


def _field_confidence(value: Any, tally: _Tally) -> dict[str, int]:
    """`field_confidence` — per-field basis points, keyed by a field that actually exists."""
    if not isinstance(value, Mapping):
        return {}
    kept: dict[str, int] = {}
    for name, score in value.items():
        key = _text(name)
        if key is None or key not in ExtractionResult.model_fields:
            tally.unknown_fields.add(str(name))
            continue
        score_bp = _confidence(score, f"field_confidence.{key}", tally)
        if score_bp is not None:
            kept[key] = score_bp
    return kept


def _build_claim(field: str, payload: Mapping[str, Any], evidence: Sequence[EvidenceSpan],
                 confidence_bp: int, request: ExtractionRequest, tally: _Tally,
                 due: ResolvedDate | None) -> Any | None:
    """One bound draft back into its typed claim, or None when the contract refuses it.

    Every refusal is a DROP of one claim, never of the extraction. `entity_type`, `state` and
    `dependency_type` are dropped rather than floored — unlike `intent` and `stance`, the kind IS
    the claim: a dependency whose type we invented tells a reader who to escalate to on the
    strength of a guess.
    """
    try:
        if field == "entity_mentions":
            kind = _closed(payload.get("entity_type"), ENTITY_TYPE, "entity_type", tally)
            surface = _verbatim_text(payload.get("surface_form"))
            if kind is None or surface is None:
                return None
            # `canonical_hint` is L1.5.4's proposal and L2's decision; the contract says a
            # mention "arrives from the extractor without one". A model's guess at identity is
            # exactly the resolution this layer is not allowed to make.
            return EntityMention(surface_form=surface, entity_type=kind, canonical_hint=None,
                                 evidence=list(evidence), confidence_bp=confidence_bp)
        if field == "commitments":
            actor = _text(payload.get("actor"))
            action = _text(payload.get("action"))
            conditional = _boolean(payload.get("is_conditional"))
            if actor is None or action is None or conditional is None:
                return None
            return Commitment(actor=actor, action=action,
                              beneficiary=_text(payload.get("beneficiary")), due=due,
                              is_conditional=conditional,
                              condition_text=_text(payload.get("condition_text")),
                              evidence=list(evidence), confidence_bp=confidence_bp)
        if field == "decision_states":
            state = _closed(payload.get("state"), DECISION_STATE, "state", tally)
            subject = _text(payload.get("subject"))
            if state is None or subject is None:
                return None
            return DecisionState(subject=subject, state=state,
                                 blocked_on=_text(payload.get("blocked_on")),
                                 owner=_text(payload.get("owner")), evidence=list(evidence),
                                 confidence_bp=confidence_bp)
        if field == "dependencies":
            kind = _closed(payload.get("dependency_type"), DEPENDENCY_TYPE, "dependency_type",
                           tally)
            blocker = _text(payload.get("blocker"))
            blocked = _text(payload.get("blocked"))
            if kind is None or blocker is None or blocked is None:
                return None
            return Dependency(blocker=blocker, blocked=blocked, dependency_type=kind,
                              evidence=list(evidence), confidence_bp=confidence_bp)
        if field == "unclassified_observations":
            kind = _text(payload.get("proposed_kind"))
            description = _text(payload.get("description"))
            if kind is None or description is None:
                return None
            return UnclassifiedObservation(proposed_kind=kind, description=description,
                                           evidence=list(evidence),
                                           confidence_bp=confidence_bp)
        if field == "dates_mentioned":
            return _resolved_date(payload, evidence, request, tally)
    except (TypeError, ValueError) as exc:
        tally.contract_rejects += 1
        log.warning("dropping a %s claim the contract refused (%s)", field, exc)
        return None
    raise AssertionError(f"no builder for claim field {field!r}")


def claims_offered(payload: Mapping[str, Any]) -> int:
    """How many claim-bearing entries the model put in the answer, before anything refused one.

    Counted over `CLAIM_BEARING_FIELDS` with the same reader the parser uses, so "offered" and
    "read" cannot disagree about what an entry is: a lane that is not a list, or an entry that is
    not an object, was never a claim and is not counted as one lost.

    A commitment's nested `due` is NOT counted separately. It is part of the commitment it hangs
    off — ALG-08's own policy is that a commitment whose due was fabricated keeps the commitment
    and loses the date — so counting it would make a message with one dated promise report two
    claims and a dropped deadline report a 50% loss.
    """
    return sum(len(_claim_entries(payload, field)) for field in CLAIM_BEARING_FIELDS)


def answered_fields(payload: Mapping[str, Any]) -> int:
    """How many of the fields the model was ASKED for it actually named.

    Not "how many keys": an answer of `{"vibe": 9}` names one key and answers nothing, and an
    answer of `{}` — which is what a decode failure hands back and what a model occasionally
    emits on its own — names none. Both are the same fact and the count says so.
    """
    return sum(1 for key in payload if str(key) in ANSWERABLE_FIELDS)


def total_loss_failure(diagnostics: ExtractionDiagnostics,
                       result: ExtractionResult | None) -> str | None:
    """Is this a TOTAL LOSS, and if so what does the park row say? One sentence, or None.

    The boundary the module docstring states, as the only function that draws it:

    * `answered_fields == 0` — the answer named none of the fields it was asked for. `{}` is a
      legal mapping and builds a conforming, claim-free `ExtractionResult`; storing it would
      cache "this message said nothing" against a message nobody read;
    * every claim the model OFFERED was refused here. The commonest shape is an answer whose
      per-claim confidences were written as ratios, which `_confidence` refuses one by one — six
      real claims in, six gone, and a result that types and conforms;
    * anything else is not a total loss, INCLUDING an answer that offered claims and kept only
      one. A partial loss is a prompt problem the counters already name; parking it would throw
      away the claim that survived.

    A message that genuinely said nothing lands on none of these: it named the fields it was
    asked for and offered no claims, which is a real extraction and correct to cache. Conflating
    the two is the defect — one of them must be re-asked and re-read by a human, and the other
    must never reach a queue, because "thanks!" arrives a thousand times a week.

    The sentence carries COUNTS and field names only, never a fragment of the answer: it is
    written into a park row AND fed back to the model as the repair note, and the repair note
    sits in the instruction spine (`repair_prompt` states why nothing payload-derived may go
    there).
    """
    if result is None:
        return None
    if diagnostics.answered_fields == 0:
        return (f"the answer named no field the schema asks for, so it described nothing: "
                f"{diagnostics.claims_offered} claim(s) offered, "
                f"{len(ANSWERABLE_FIELDS)} fields available to answer with")
    kept = sum(len(getattr(result, field)) for field in CLAIM_BEARING_FIELDS)
    if diagnostics.claims_offered > 0 and kept == 0:
        return (f"the answer offered {diagnostics.claims_offered} claim(s) across "
                f"{len(CLAIM_BEARING_FIELDS)} lanes and none of them survived: "
                f"{diagnostics.confidence_rejects} refused for confidence, "
                f"{diagnostics.contract_rejects} by the contract, "
                f"{diagnostics.vocabulary_rejects} for vocabulary, "
                f"{diagnostics.no_evidence_drops} for having no recoverable receipt")
    return None


def parse_response(payload: Any, *, request: ExtractionRequest, call: AssembledCall,
                   model_snapshot: str, input_tokens: int,
                   output_tokens: int) -> ParsedExtraction:
    """L1.4.3-U3 · the model's JSON into a validated `ExtractionResult`, or an honest refusal.

    The pass, in the order it has to run:

    1. **shape** — a payload that is not a JSON object is unusable and says so. That is the
       repair retry's trigger, and the only failure that produces no result at all;
    2. **drafts** — every claim-bearing entry becomes a `ClaimDraft`, its citations aligned into
       the prepared frame. A claim whose `confidence_bp` is not integer basis points is dropped
       here, before it can cost a search;
    3. **binding** — ONE `bind_evidence` pass over every lane at once. One pass because the
       binder's frame check is per-pass and every draft here is measured against the same
       prepared text, and because the counters it returns are only readable with a shared
       denominator. A claim that cited nothing but whose words are in the text gets a synthesized
       span and `bp * 7 // 10`; one whose words are nowhere is dropped and counted;
    4. **typing** — bound drafts back into contract objects, each refusal dropping one claim;
    5. **schema** — `validate_extraction_schema` at `EXTRACTOR_OUTPUT`, which is the stage where
       S-9 is armed: no span leaving here may carry `verified=True`, because the extractor claims
       and ALG-08 verifies;
    6. **total loss** — `total_loss_failure`. A conforming result with NOTHING in it is either a
       message that said nothing or an answer that produced nothing, and only the counters can
       say which. The second is not usable and must not be cached; the boundary between them is
       stated in the module docstring and drawn in exactly one function.

    `all_evidence` is DERIVED, not read from the model: the result is built once with an empty
    ledger and rebuilt with `evidence_from_claims()`, so S-7 ("`all_evidence` contains every span
    the claims carry") holds by construction rather than by a mirror of the contract's own walk
    that would drift the day a claim type is added.

    An invented top-level field is ignored and counted — doc 04's failure table says so in those
    words. It is NOT rerouted into the open lane: an invented field carries no `proposed_kind`
    and no `description`, which are the two things the weekly discovery report reviews, so
    promoting it would put an unreviewable row into the one lane that must stay reviewable. The
    prompt's block 6 is what asks the model to use the lane, and the count here is how a prompt
    that is not landing becomes visible.
    """
    tally = _Tally()
    if not isinstance(payload, Mapping):
        return ParsedExtraction(
            result=None, report=None, diagnostics=tally.freeze(),
            failure=f"the answer was not a JSON object (got {type(payload).__name__})")

    tally.claims_offered = claims_offered(payload)
    tally.answered_fields = answered_fields(payload)
    known = set(ExtractionResult.model_fields)
    tally.unknown_fields.update(str(key) for key in payload if str(key) not in known)
    if tally.unknown_fields:
        log.warning("ignoring %d invented top-level field(s): %s",
                    len(tally.unknown_fields), sorted(tally.unknown_fields))

    pending: list[_Pending] = []
    #: Which commitment each `commitments.due` draft belongs to, by position in `pending`. A due
    #: is bound as its own draft — it carries its own receipt and can lose it independently,
    #: which is ALG-08's policy too ("a commitment whose due was fabricated keeps the commitment
    #: and loses the date") — so the link back has to be recorded rather than re-derived.
    due_of: dict[int, int] = {}
    for field in CLAIM_FIELDS:
        for entry in _claim_entries(payload, field):
            drafted = _draft(field, entry, request, call, tally)
            if drafted is None:
                continue
            pending.append(drafted)
            if field != "commitments":
                continue
            due_payload = entry.get("due")
            if not isinstance(due_payload, Mapping):
                continue
            due_draft = _draft(COMMITMENT_DUE_FIELD, due_payload, request, call, tally)
            if due_draft is not None:
                due_of[len(pending)] = len(pending) - 1
                pending.append(due_draft)

    outcome = bind_evidence((item.draft for item in pending), prepared_text=request.content,
                            source_ref=request.source_ref)
    # U1 SYNTHESIZES a receipt for a claim that cited nothing, and the binder knows no page map —
    # it is handed a string and a frame name and nothing else, deliberately. So the located half
    # is attached here, where the request is: without this a synthesized span is the one receipt
    # in an extraction that cannot say which page it came from, and "some of them have pages" is
    # a worse surface than either all or none.
    outcome = _locate_bound(outcome, request)
    tally.claims_bound = outcome.counters.bound
    tally.synthesized_spans = outcome.counters.synthesized
    tally.no_evidence_drops = outcome.counters.no_evidence

    bound_by_index: dict[int, BoundClaim] = {}
    cursor = 0
    for bound in outcome.claims:
        while cursor < len(pending) and pending[cursor].draft is not bound.draft:
            cursor += 1
        if cursor >= len(pending):                      # pragma: no cover - binder preserves order
            raise AssertionError("bind_evidence returned a claim that was never drafted")
        bound_by_index[cursor] = bound
        cursor += 1

    dues: dict[int, ResolvedDate | None] = {}
    for due_index, commitment_index in due_of.items():
        bound = bound_by_index.get(due_index)
        if bound is None:
            continue
        dues[commitment_index] = _resolved_date(pending[due_index].payload, bound.evidence,
                                                request, tally)

    claims: dict[str, list[Any]] = {field: [] for field in CLAIM_FIELDS}
    for index, item in enumerate(pending):
        if item.draft.field == COMMITMENT_DUE_FIELD:
            continue
        bound = bound_by_index.get(index)
        if bound is None:
            continue
        built = _build_claim(item.draft.field, item.payload, bound.evidence, bound.confidence_bp,
                             request, tally, dues.get(index))
        if built is not None:
            claims[item.draft.field].append(built)

    intent = _closed(payload.get("intent"), INTENT, "intent", tally) or INTENT_FLOOR
    stance = _closed(payload.get("stance"), STANCE, "stance", tally) or STANCE_FLOOR

    common: dict[str, Any] = {
        "intent": intent,
        "topics": _string_list(payload.get("topics")),
        "stance": stance,
        # L1.5.4-U2 (ALG-11) · the canonicalizer's seam. `fill_canonical_hints` existed,
        # fully tested, and NOTHING on a request path called it — so `canonical_hint` was None
        # on every event this product has ever captured and the shipped alias table was dead
        # code. `claim_group._org_anchor` then fell to `derive_key` on the raw surface form,
        # which is right for a name the table has never heard of and wrong for "AWS" against
        # "Amazon Web Services": two keys, two subjects, and one vendor's two renewal figures
        # never compared by ALG-12.
        #
        # Here rather than downstream because the proposal must be part of the extraction that
        # gets CACHED and replayed — a hint computed after the cache would differ between a
        # first run and its replay. Pure, deterministic, and evaluated from literals at import
        # (the table is a constant, never a database read), so it adds no I/O and no clock.
        # `overwrite=False`: a hint the model somehow already stated is left alone.
        "entity_mentions": fill_canonical_hints(claims["entity_mentions"]),
        "amounts": _amounts(payload, request.content, tally),
        "dates_mentioned": claims["dates_mentioned"],
        "commitments": claims["commitments"],
        "decision_states": claims["decision_states"],
        "dependencies": claims["dependencies"],
        "implied_actions": _string_list(payload.get("implied_actions")),
        "questions": _string_list(payload.get("questions")),
        "roles": _open_lane_entries(payload.get("roles"), tally),
        "relationships": _open_lane_entries(payload.get("relationships"), tally),
        "scheduling_proposals": _open_lane_entries(payload.get("scheduling_proposals"), tally),
        "unclassified_observations": claims["unclassified_observations"],
        "field_confidence": _field_confidence(payload.get("field_confidence"), tally),
        "model_snapshot": model_snapshot,
        "prompt_version": call.prompt_version,
        "schema_version": call.schema_version,
        "extraction_profile": call.profile_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }

    try:
        draft_result = ExtractionResult(all_evidence=[], **common)
        result = ExtractionResult(all_evidence=draft_result.evidence_from_claims(), **common)
    except (TypeError, ValueError) as exc:
        return ParsedExtraction(result=None, report=None, diagnostics=tally.freeze(),
                                failure=f"the answer could not be typed: {exc}")

    report = validate_extraction_schema(result, vocabulary=ExtractionVocabulary(
        **vocabulary_sets()), stage=ValidationStage.EXTRACTOR_OUTPUT)
    diagnostics = tally.freeze()
    if not report.conforms:
        # A schema violation is the more specific defect and keeps the reason. An extraction
        # S-1..S-9 refused is refused whether or not it also happened to be empty, and naming it
        # a total loss would send an operator looking for a prompt problem in the wrong lane.
        return ParsedExtraction(
            result=result, report=report, diagnostics=diagnostics,
            failure="; ".join(f"{v.rule.value} on {v.field}: {v.detail}"
                              for v in report.blocking_violations))
    loss = total_loss_failure(diagnostics, result)
    return ParsedExtraction(result=result, report=report, diagnostics=diagnostics,
                            failure=loss, total_loss=loss is not None)


# =============================================================================================
# L1.4.3-U4 · the extraction run  (derived — see the module docstring)
# =============================================================================================


def _require_deterministic(llm: LLMClient) -> None:
    """`temperature=0`, checked when the client will say. Doc 04 states it as a requirement of
    the call, and a sampled extraction is a cache row that answers for a call that would not
    happen the same way twice."""
    temperature = getattr(llm, "temperature", 0)
    if temperature != 0:
        raise ValueError(
            f"the extraction client is at temperature {temperature!r}; LLM-2 runs at 0. A "
            "sampled answer makes the cached row a record of one roll of the dice rather than "
            "of what this prompt does with this content.")


def _sanitised(text: str, call: AssembledCall, *, limit: int) -> str:
    """Bounded, and stripped of anything that could pass for structure. For a PARK ROW.

    A park row is read by a human and drained by a query; it never re-enters a prompt. The
    markers come out anyway because a stored excerpt is eventually pasted somewhere by somebody,
    and the nonce specifically must not survive into any text that outlives the call it fenced.
    """
    cleaned = text[:limit]
    for marker in (call.fenced.open_marker, call.fenced.close_marker, call.fenced.nonce,
                   *_STRUCTURAL_MARKERS, REPAIR_MARKER):
        cleaned = cleaned.replace(marker, "")
    return cleaned.strip()


def repair_prompt(request: ExtractionRequest, call: AssembledCall, *, failure: str) -> str:
    """The one retry doc 04 allows: the same call, with the reason its answer was unusable.

    **The repair note goes ABOVE the fence, and the model's rejected answer is not quoted back
    at all.** Both follow from L1.4.7-U1's own rule, which `check_placement` enforces on every
    prompt this module renders: nothing may follow the close fence, because *"anything after the
    untrusted region is an instruction in the exact position a successful injection would
    occupy"*. Appending a repair block after the content would put our retry instruction exactly
    there — and quoting the model's answer into it would carry text derived from the payload up
    into the instruction spine, which is the same channel one step further along. The failure
    description is our own sentence and is enough: the model still has the content, the schema
    and the vocabulary in front of it, and what it lacked was the shape, not the evidence.

    The SAME `FencedContent` is re-rendered, so the content substitution, the nonce and every
    offset frame are byte-identical to the first call. A rebuilt fence would make the second
    answer's offsets measurements against a text the first call was never shown.
    """
    note = (f"{REPAIR_MARKER}\n"
            f"A previous answer to this exact request could not be used: "
            f"{_sanitised(failure, call, limit=PARK_EXCERPT_CHARS)}\n"
            "Answer with ONE JSON object matching the SCHEMA block above and nothing else — no "
            "prose, no markdown fence, no trailing commas, no fields the schema does not list. "
            "Confidence is an integer 0..10000, never a ratio. Every claim carries a verbatim "
            "quote with its offsets, or it is not made at all.")
    rendered = render_prompt(call.profile_id, schema=generate_schema_block(),
                             vocab=vocabulary_block(), envelope=f"{call.envelope}\n\n{note}",
                             content=call.fenced.text)
    call.fenced.check_placement(rendered.text)
    return rendered.text


def _parked(request: ExtractionRequest, *, reason_code: str, failure: str, call: AssembledCall,
            model_calls: int, raw: str | None) -> ParkedEvent:
    """A park row that says enough to fix the thing that caused it.

    `created_at` is the request's `eval_time`, not a clock read: this module resolves every other
    instant from that parameter and a park row stamped from `datetime.now` would be the one row
    in a replay that moved.
    """
    trace: dict[str, Any] = {
        "stage": STAGE, "reason": reason_code, "failure": failure,
        "profile_id": call.profile_id, "tier": call.tier, "prompt_version": call.prompt_version,
        "schema_version": call.schema_version, "model_calls": model_calls,
    }
    if raw is not None:
        trace["raw_excerpt"] = _sanitised(raw, call, limit=PARK_EXCERPT_CHARS)
    return ParkedEvent(event_id=request.event_id, org_id=request.org_id, source=request.source,
                       reason_code=reason_code, stage=STAGE, trace=[trace],
                       created_at=request.eval_time)


class _Unusable(Exception):
    """The thunk's way out of `cached_extraction`, carrying the park row it produced.

    `cache.cached_extraction` types its thunk as returning an `ExtractionResult`, and rightly:
    a cache stores extractions, and a function that could also return "no extraction" would
    invite a caller to store the absence. But L1.4.3's failure policy is park-never-drop, so the
    failure has to leave by a route the cache cannot mistake for a value. An exception is that
    route, and it also makes the invariant structural rather than remembered: there is no path on
    which a park row reaches `store.put`.
    """

    def __init__(self, outcome_parts: dict[str, Any]) -> None:
        super().__init__(outcome_parts.get("failure", "extraction failed"))
        self.parts = outcome_parts


@dataclass
class _CallLedger:
    """What the calls cost, kept outside the thunk so a park row can still report the bill."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    parsed: ParsedExtraction | None = None
    findings: tuple[str, ...] = ()


def _park_reason(parsed: ParsedExtraction | None) -> str:
    """Which of the three answer-shaped park reasons this failure is, in one place.

    The split is what a drain acts on, so each one has to mean a different next step:

    * TOTAL LOSS — the answer decoded, typed and conformed, and carried nothing. Checked FIRST,
      because such an answer also satisfies "has a result" and would otherwise be filed as a
      schema failure, sending whoever reads the queue to look for a violation that is not there;
    * SCHEMA FAILED — it typed and S-1..S-9 refused it. It will be refused the same way until a
      prompt version changes;
    * PARSE FAILED — it never became an object at all.
    """
    if parsed is None:
        return PARK_PARSE_FAILED
    if parsed.total_loss:
        return PARK_TOTAL_LOSS
    return PARK_SCHEMA_FAILED if parsed.result is not None else PARK_PARSE_FAILED


def _guarded(result: ExtractionResult, request: ExtractionRequest,
             open_lane: OpenLaneStore | None) -> ExtractionResult:
    """L1.4.5-U0 applied to one parsed answer — the last thing between it and storage.

    `roles`, `relationships` and `scheduling_proposals` are `list[dict[str, Any]]` on the
    contract, and nothing on the path from the model to `l1_extraction_results` ever asked what
    their KEYS were: the prompt invited invention, the parser normalised the key's TYPE and said
    nothing about its NAME, and `_Shape.MAPPING_LIST` checked only that each key was a string. So
    `roles: [{"deal_stage": "negotiation"}]` was a conforming extraction that cached permanently
    under a name no consumer reads. `context/extract/vocab.py` records where that ends: 268
    distinct field names in one org, 192 used exactly once.

    Sifting happens whether or not there is a store, because the closure is about what may be
    STORED and a lane store is not required to enforce it. The store only decides whether the
    refused names are also KEPT — `capture_unclassified` is the discovery lane's one entry point,
    and without a caller the table cannot receive a row, which is a failure that raises no alarm
    of its own (the report simply stays empty).
    """
    if open_lane is None:
        return sift_untyped_lanes(result, source_ref=request.source_ref).result
    return guard_typed_sink(result, org_id=request.org_id, event_id=request.event_id,
                            source_ref=request.source_ref, source_text=request.content,
                            eval_time=request.eval_time, store=open_lane).result


def _run_calls(request: ExtractionRequest, call: AssembledCall, llm: LLMClient,
               ledger: _CallLedger,
               open_lane: OpenLaneStore | None = None) -> ExtractionResult:
    """One call, one repair retry, or `_Unusable`. The thunk `cached_extraction` may never run.

    The repair retry is charged once and only once. `MAX_MODEL_CALLS` is 2 and the loop cannot
    exceed it, because a third charge for a model that has now missed the shape twice buys
    nothing the park row does not already record.

    L1.4.5-U0's SEAM (D6a/D3) is the single `return` below, and it is here rather than around
    `extract()` because of the cache. `extract` wraps this in `cached_extraction`, which writes
    the returned value into `l1_extraction_results`; a guard applied to `outcome.result` would
    sift the copy the caller sees and leave the unsifted dicts in the cached row — and every
    later replay reads the row, not the caller. So the guard runs on the value the thunk returns.

    `open_lane=None` behaves exactly as `store=None` already does: the run works, the three
    untyped lanes are still closed against their key vocabulary, and nothing is persisted.
    """
    prompt = call.prompt
    raw = ""
    while ledger.calls < MAX_MODEL_CALLS:
        response = llm.call(prompt, max_tokens=request.max_output_tokens)
        ledger.calls += 1
        ledger.input_tokens += max(int(response.input_tokens), 0)
        ledger.output_tokens += max(int(response.output_tokens), 0)
        raw = response.raw or ""

        if not response.ok and not raw.strip():
            # NO ANSWER ARRIVED — a timeout, a refused connection, a 500. A repair retry has
            # nothing to repair, so this parks straight away for the drain to pick up with
            # backoff; retrying inside one extraction would spend the second call on the same
            # outage. Distinguished from an answer that arrived and would not decode by the
            # PRESENCE OF TEXT, not by the flag: `context/llm/client.py` sets `ok=False` for
            # both, and treating an unparseable answer as an outage would skip the one repair
            # retry doc 04 requires — which is the exact failure the retry exists for.
            raise _Unusable({"reason": PARK_CALL_FAILED, "raw": None,
                             "failure": response.error or "the model call did not succeed"})

        if raw.strip():
            verdict = scan_output(raw, fenced=call.fenced)
            if verdict.suspect:
                ledger.findings = tuple(finding.kind for finding in verdict.findings)
                log.warning("extraction %s: L1.4.7 flagged the answer (%s, risk %d bp)",
                            request.event_id, ledger.findings, verdict.risk_bp)

        if not response.ok:
            # Text arrived and the transport could not decode it. Deliberately NOT handed to
            # `parse_response`: its payload would be the client's empty `{}`, which is a legal
            # mapping and would build a conforming ExtractionResult with no claims in it — an
            # unparseable answer cached forever as "this message said nothing".
            parsed = ParsedExtraction(result=None, report=None,
                                      diagnostics=ExtractionDiagnostics(),
                                      failure=response.error or "the answer was not valid JSON")
        else:
            # Stamped with the CLIENT's snapshot, not the answer's. The cache key was built from
            # `llm.model` before the call, and `CacheEntry` refuses a result whose provenance
            # disagrees with the key it is filed under — rightly, since the row would then be a
            # lie about what produced it.
            if response.model and response.model != llm.model:
                log.warning("extraction %s: the client answered as %r but declares %r; the key "
                            "and the row both record the declared snapshot",
                            request.event_id, response.model, llm.model)
            parsed = parse_response(response.parsed, request=request, call=call,
                                    model_snapshot=llm.model, input_tokens=ledger.input_tokens,
                                    output_tokens=ledger.output_tokens)
        ledger.parsed = parsed
        if parsed.usable and parsed.result is not None:
            return _guarded(parsed.result, request, open_lane)
        if ledger.calls < MAX_MODEL_CALLS:
            log.warning("extraction %s: repairing an unusable answer (%s)",
                        request.event_id, parsed.failure)
            prompt = repair_prompt(request, call, failure=parsed.failure or "unknown")

    parsed = ledger.parsed
    raise _Unusable({
        "reason": _park_reason(parsed),
        "failure": (parsed.failure if parsed is not None and parsed.failure
                    else "the model produced no usable answer"),
        "raw": raw})


def extract(request: ExtractionRequest, *, llm: LLMClient,
            store: ExtractionCacheStore | None = None,
            open_lane: OpenLaneStore | None = None,
            nonce: str | None = None) -> ExtractionOutcome:
    """L1.4.3-U4 · one message, one model call, one cached answer — or one park row.

    The doc's assembly line end to end:

        profile -> tier -> key -> cached? -> prompt -> call -> parse -> bind -> cache

    **The cache is checked before anything is spent, and a hit makes ZERO calls.** That is the
    property that makes heavy L1 extraction affordable at all — the model runs once per content
    version, ever — and here it is STRUCTURAL rather than remembered:
    `cache.cached_extraction` takes the call as a thunk and returns before invoking it on a hit,
    so there is no path from a hit to a model. The golden corpus asserts it by replaying an
    unchanged set with a client that raises when called.

    **Nothing is dropped.** Every failure doc 04's table names produces a `ParkedEvent` on the
    outcome instead of an exception or a silent None: a transport failure or timeout parks under
    `extraction_call_failed` for the drain to retry with backoff; an answer that cannot be made
    to conform gets ONE repair retry and then parks under `extraction_parse_failed` (unparseable)
    or `extraction_schema_failed` (typed, refused by S-1..S-9); an answer that conformed and
    carried NO CLAIM AT ALL gets the same one retry and then parks under
    `extraction_total_loss`. The split matters because the three want different treatment: the
    first is worth trying again later, the second will fail the same way until a prompt version
    changes, and the third is the one a human has to read — it is the only failure whose output
    would otherwise have been indistinguishable from success. A park is never stored:
    `_Unusable` leaves by a route the cache cannot mistake for a value, which is what stops a
    total loss from becoming a permanent one.

    `store=None` is a caller that has no cache yet — it runs, it pays for every call, and it is
    not an error. `open_lane=None` is the same shape of answer for the discovery lane: the three
    untyped lanes are still closed against their key vocabulary (a name we have no field for
    never reaches storage), the refused names are simply not kept for review. `nonce` pins the
    fence for a test or a byte-exact replay.
    """
    _require_deterministic(llm)
    call = assemble_call(request, nonce=nonce)
    key = cache_key(org_id=request.org_id, content=request.content, profile_id=call.profile_id,
                    prompt_version=call.prompt_version, schema_version=call.schema_version,
                    model_snapshot=llm.model, vocab_fingerprint=call.vocab_fingerprint,
                    envelope=call.envelope)
    ledger = _CallLedger()

    def _thunk() -> ExtractionResult:
        return _run_calls(request, call, llm, ledger, open_lane)

    try:
        if store is None:
            result = _thunk()
            hit = False
        else:
            outcome = cached_extraction(store, key, event_id=request.event_id, tier=call.tier,
                                        extract=_thunk)
            result, hit = outcome.result, outcome.hit
    except _Unusable as unusable:
        parsed = ledger.parsed
        return ExtractionOutcome(
            event_id=request.event_id, result=None,
            parked=_parked(request, reason_code=unusable.parts["reason"],
                           failure=unusable.parts["failure"], call=call,
                           model_calls=ledger.calls, raw=unusable.parts["raw"]),
            cache_key=key, cache_hit=False, model_calls=ledger.calls,
            input_tokens=ledger.input_tokens, output_tokens=ledger.output_tokens, tier=call.tier,
            diagnostics=_with_findings(parsed.diagnostics if parsed else ExtractionDiagnostics(),
                                       ledger.findings),
            report=parsed.report if parsed is not None else None)

    diagnostics = (ExtractionDiagnostics() if hit or ledger.parsed is None
                   else _with_findings(ledger.parsed.diagnostics, ledger.findings))
    return ExtractionOutcome(
        event_id=request.event_id, result=result, parked=None, cache_key=key, cache_hit=hit,
        model_calls=ledger.calls, input_tokens=ledger.input_tokens,
        output_tokens=ledger.output_tokens, tier=call.tier, diagnostics=diagnostics,
        report=None if hit or ledger.parsed is None else ledger.parsed.report)


def _with_findings(diagnostics: ExtractionDiagnostics,
                   findings: Sequence[str]) -> ExtractionDiagnostics:
    """Attach L1.4.7's output verdict to the parse's own counters — one object for the caller.

    The two are produced by different units and are read together: "the model echoed an
    instruction AND we dropped four claims for having no receipt" is one story about one answer,
    and a caller that had to join them would eventually report half of it.
    """
    if not findings:
        return diagnostics
    return replace(diagnostics, output_findings=tuple(findings))


__all__ = ["ANSWERABLE_FIELDS", "CLAIM_BEARING_FIELDS", "CLAIM_FIELDS", "COMMITMENT_DUE_FIELD",
           "DIRECTIONS", "EXTRACTION_SCHEMA_VERSION", "EXTRACTOR_WRITTEN_FIELDS", "INTENT_FLOOR",
           "MAX_MODEL_CALLS", "OFFSET_FRAME_BLOCK", "OFFSET_FRAME_MARKER", "PARK_CALL_FAILED",
           "PARK_EXCERPT_CHARS", "PARK_PARSE_FAILED", "PARK_SCHEMA_FAILED", "PARK_TOTAL_LOSS",
           "REPAIR_MARKER", "STAGE", "STANCE_FLOOR",
           "AssembledCall", "EventEnvelope", "ExtractionDiagnostics", "ExtractionOutcome",
           "ExtractionRequest", "LLMClient", "LLMResponse", "ParsedExtraction", "answered_fields",
           "assemble_call", "claims_offered", "envelope_chars", "extract",
           "offset_frame_block", "parse_response",
           "repair_prompt", "total_loss_failure"]
