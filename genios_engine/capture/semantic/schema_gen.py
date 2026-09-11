"""L1.4.4-U2 · the JSON schema generator — the prompt's shape, derived from the type.

One callable, `generate_schema_block()`, which walks `ExtractionResult.model_fields` and returns
the JSON skeleton the prompt's SCHEMA block embeds (doc 04, L1.4.2-U2, block 3).

**Why it is generated and not written.** The recorded v1 failure is prompt/type drift in its
purest form: *"rules read `deal.status` while the extractor, never told the name, wrote
`status` — so the rule was dead on arrival"* (`context/extract/vocab.py`). A hand-written JSON
example in a prompt template is a second declaration of the schema, in a second file, in a
format no type checker reads, maintained by whoever last edited the prompt. It does not drift
loudly — it drifts by staying exactly as correct as it was on the day the field was renamed, and
what a reader sees afterwards is a field that is always empty, which looks like a model that
never noticed rather than a prompt that never asked. Deriving the block from the contract means
the only way to change what the prompt asks for is to change the type every consumer reads.

**Everything the model is allowed to say appears here, and nothing else does.** Enum-shaped
fields are inlined with their allowed values straight from `vocabulary.py`, so the SCHEMA block
and the VOCAB block cannot disagree, and neither can disagree with the S-3 membership check in
`capture/validate/schema.py` — three readers, one word list.

**And everything it is allowed to NAME.** `roles`, `relationships` and `scheduling_proposals`
are `list[dict[str, Any]]` on the contract and this generator used to render all three as
`[{"<key>": "<any JSON value>"}]` — an explicit invitation to invent a field name, issued to
the two profiles (`chat`, `transcript`) that emphasise those very lanes. Nothing between there
and `l1_extraction_results` refused what came back: S-2 checked that the keys were strings and
S-3 was never applied to a mapping list at all. `vocabulary.UNTYPED_LANE_KEYS` closes the key
sets, this file renders them, and `capture/semantic/sink_guard.py` enforces them at the sink,
routing a refused name into the open lane instead of into a dict nobody reads.

**Four fields are shown but marked not-yours**, rather than omitted, and the distinction is the
interesting design decision in this file:

* the provenance fields (`model_snapshot`, `prompt_version`, `schema_version`,
  `extraction_profile`, `input_tokens`, `output_tokens`) are stamped by the extractor, which is
  the only thing that knows them;
* `all_evidence` is assembled by the evidence binder (L1.4.6) out of the spans already carried
  by the claims, so asking the model for it a second time buys a duplicate list at full token
  price and one more chance for the two copies to disagree;
* `verified` on a span is set by span verification (ALG-08) alone — S-9, "the extractor may not
  stamp its own receipts", refuses an extraction that arrives with it already true.

Omitting them instead would make the block a partial view of the type, and a partial view is
exactly what the acceptance assert *"adding a field to ExtractionResult changes the generated
block"* is there to prevent: a filter is a place a new field can land and be silently dropped.
Every declared field appears; six of them appear saying whose job they are.

**The walk refuses what it does not understand.** An annotation with no rendering rule raises
`SchemaGenerationError` at generation time rather than emitting a vague `"<value>"`, because a
vague placeholder is how a new field gets into the prompt with no shape and comes back as
whatever the model guessed. `float` and `Decimal` are refused by name with their own message:
every score in this system is integer basis points, and a fractional field on the extraction
type would be a ratio the model produced — the thing `contracts/extraction.py` spends three
paragraphs refusing.

**Deterministic and cached.** Same type in, byte-identical block out, on every machine and in
every process — the block is part of the prompt, the prompt is part of the extraction cache key,
and a key that varied with dict ordering would re-extract the world.
"""

from __future__ import annotations

import json
import types
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from functools import lru_cache
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel

from genios_engine.capture.semantic.vocabulary import (FIELD_TO_SET, untyped_lane_sets,
                                                       vocabulary_sets)
from genios_engine.contracts.extraction import ExtractionResult


class SchemaGenerationError(TypeError):
    """The walk met an annotation it has no rendering rule for, and said so.

    A `TypeError` because that is what it is — a type this generator cannot describe — and an
    exception rather than a fallback placeholder because the fallback would be invisible: the
    prompt would keep generating, the new field would be described to the model as `"<value>"`,
    and the shape of what came back would be whatever the model inferred from the field's name.
    """


#: Field name -> who fills it, for the six that are not the model's to answer. Keyed by the leaf
#: field name, which is unique across `ExtractionResult` and its claim types (`verified` exists
#: only on `EvidenceSpan`), so one flat table covers every depth without per-type dispatch —
#: `capture/validate/schema.py` keys its own vocabulary tables the same way and for the same
#: reason.
_CALLER_FILLED: Mapping[str, str] = {
    "model_snapshot": "omit — the extractor stamps the exact model id it called",
    "prompt_version": "omit — the extractor stamps the prompt version it used",
    "schema_version": "omit — the extractor stamps the schema version of this block",
    "extraction_profile": "omit — the extractor stamps which profile it ran",
    "input_tokens": "omit — counted by the caller, not by you",
    "output_tokens": "omit — counted by the caller, not by you",
    "all_evidence": "omit — assembled from the evidence you attached to each claim",
    "verified": "omit — set only by span verification, never by you",
    "source_ref": "omit — the extractor stamps which content your offsets point into",
}

#: Field name -> the placeholder that says what the number MEANS, where the bare type would say
#: only `<integer>`. Basis points are the whole reason this table exists: a model told "integer"
#: and shown `0.87` in its own head writes 1, and a confidence of 1 basis point is not a rounding
#: error, it is a claim the pipeline will treat as noise.
_FIELD_HINT: Mapping[str, str] = {
    "confidence_bp": "integer basis points 0..10000 — 8700 means 87%, never 0.87",
    "start_offset": "integer character offset into the content, 0-based, inclusive",
    "end_offset": "integer character offset into the content, exclusive",
    "minor_units": "integer minor units — 8400000 for $84,000.00, never a decimal",
    "currency": "ISO 4217 code, e.g. USD",
    "as_written": "the amount or date exactly as the text spells it",
    "quote": "verbatim from the content, character for character",
    "field_confidence": "integer basis points 0..10000 for that field — 8700 means 87%",
}

#: The placeholder key inside an open mapping. A JSON object needs a key to demonstrate shape,
#: and an invented realistic-looking one (`"deal_stage"`) would be read as a required field —
#: which is the 268-invented-names failure arriving through the example instead of the schema.
#:
#: It is now reached only by a mapping with NO closed key set. `roles`, `relationships` and
#: `scheduling_proposals` used to render as `[{"<key>": "<any JSON value>"}]`, and that was the
#: same failure by the opposite route: rather than showing one invented name, it invited any
#: name at all, in the three lanes two of the five registered profiles explicitly emphasise.
#: `vocabulary.UNTYPED_LANE_KEYS` closes them, and `_lane_object` below renders them.
_DICT_KEY = "<key>"

#: What each key of a closed lane object is filled with. The VALUES stay open — a `text` on a
#: scheduling proposal is free text and always was; it is the NAMES that decide whether anything
#: downstream can read the entry, and those are now enumerated rather than invited.
_LANE_VALUE = "<string, or omit this key>"

#: Field name -> a better key placeholder than `_DICT_KEY`, where the keys of a mapping mean
#: something specific. `field_confidence` is keyed by the names of the fields above it, and
#: `"<key>"` there invites the model to invent a key namespace of its own.
_DICT_KEY_HINT: Mapping[str, str] = {
    "field_confidence": "<the name of one field above>",
}

#: Rendering rules for the scalar leaves, by exact type. A tuple of (type, placeholder) pairs
#: rather than a dict keyed by type so `bool` is matched before `int` — `issubclass(bool, int)`
#: is true, and an ordered walk is the one place that is easy to get right.
_SCALARS: tuple[tuple[type, str], ...] = (
    (bool, "true or false"),
    (str, "string"),
    (int, "integer"),
    (datetime, "ISO 8601 timestamp with timezone, e.g. 2026-01-14T09:00:00Z"),
    (date, "ISO 8601 date, e.g. 2026-01-14"),
)

#: Refused by name, with a message that says why rather than "unsupported type". Both would
#: otherwise fall through to the generic error and read as an oversight in this file instead of
#: as the deliberate rule they break.
_REFUSED: Mapping[type, str] = {
    float: ("every score in Layer 1 is integer basis points — a float on the extraction type is "
            "a ratio the model produced, and it composes irreproducibly across replays"),
    Decimal: ("money is integer minor units plus an ISO code (contracts/units.py::Money); a "
              "Decimal field would be a second, unvalidated way to spell an amount"),
}


def generate_schema_block(model: type[BaseModel] = ExtractionResult) -> str:
    """L1.4.4-U2 · the JSON skeleton for `model`, ready to paste into a prompt.

    Returns pretty-printed JSON in the type's own field order: every declared field, one
    placeholder per field describing its type, its allowed values where a closed vocabulary
    governs it, and whose job it is where the answer is not the model's. The result parses with
    `json.loads` — it is a template, not prose about a template, so the prompt shows the model an
    object of exactly the shape it must return.

    `model` is a parameter with a default rather than a hardcoded reference so the acceptance
    test can generate from a variant type and prove the block follows the contract instead of
    following this file. Anything with `model_fields` works; nothing about the walk is specific
    to `ExtractionResult` beyond the tables above, which are keyed by field name and simply do
    not match on a type that has no such fields.

    Cached per type. It is deterministic — sorted vocabularies, declaration-ordered fields, no
    clock and no randomness — and it is generated once per prompt build, on a path that runs per
    message.
    """
    return _generate(model)


@lru_cache(maxsize=None)
def _generate(model: type[BaseModel]) -> str:
    """The cache. Separate from the public callable so the docstring above is not a cache entry's
    worth of indirection, and so `generate_schema_block` keeps its default argument — an
    `lru_cache` over a defaulted parameter stores the same block under two keys."""
    fields = getattr(model, "model_fields", None)
    if not isinstance(fields, Mapping) or not fields:
        raise SchemaGenerationError(
            f"{getattr(model, '__name__', model)!r} declares no model_fields — a schema block "
            "generated from nothing would tell the model to return an empty object")
    template = {name: _render(name, field.annotation, (model,))
                for name, field in fields.items()}
    return json.dumps(template, indent=2, ensure_ascii=False)


def _render(name: str, annotation: Any, stack: tuple[type, ...]) -> Any:
    """One field -> its placeholder. `name` is the leaf field name the tables are keyed by.

    The name travels INTO containers: a list's element and a mapping's value both describe the
    same field, so `field_confidence`'s values pick up the basis-point hint and `topics`' entries
    do not pick up anything they should not. It does NOT travel into a nested model — there the
    nested type's own field names take over, which is what makes `confidence_bp` mean the same
    thing on a `Commitment` as on an `EntityMention`.
    """
    if name in _CALLER_FILLED:
        return f"<{_CALLER_FILLED[name]}>"

    lane = untyped_lane_sets().get(name)
    if lane is not None:
        if get_origin(annotation) is not list or get_args(annotation) != (dict[str, Any],):
            raise SchemaGenerationError(
                f"{name!r} has a closed lane key set but is typed {annotation!r}, not "
                "list[dict[str, Any]] — a key list can only describe a list of objects, and a "
                "lane that quietly stopped being one would be described to the model by a rule "
                "that no longer applies to it")
        return [_lane_object(lane)]

    annotation, nullable = _strip_optional(annotation)

    # Seven business fields had no writer (2026-09-10). This discriminated text/Money value
    # must stay typed in the prompt; generic ambiguous unions remain refused below.
    from genios_engine.contracts.extraction import BusinessFact
    from genios_engine.contracts.units import Money
    if stack[-1] is BusinessFact and name == "value" and annotation == str | Money:
        money = json.dumps(_render_model(Money, stack), ensure_ascii=False)
        return f"<string except for deal.value; for deal.value use this Money object: {money}>"

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _render_model(annotation, stack)

    origin = get_origin(annotation)
    if origin in (list, Sequence):
        return [_render(name, _element_of(name, annotation), stack)]
    if origin in (dict, Mapping):
        key = _DICT_KEY_HINT.get(name, _DICT_KEY)
        return {key: _render(name, _value_of(name, annotation), stack)}

    return _describe_scalar(name, annotation, nullable)


def _lane_object(keys: frozenset[str]) -> dict[str, str]:
    """One untyped lane -> an object showing every key it may carry, and no others.

    Sorted, because the block is part of the prompt and the prompt is part of the cache key: a
    set's iteration order is stable within a process and not across them, and a key order that
    moved with `PYTHONHASHSEED` would re-extract the world on every deploy.
    """
    return {key: _LANE_VALUE for key in sorted(keys)}


def _render_model(model: type[BaseModel], stack: tuple[type, ...]) -> dict[str, Any]:
    """A nested claim type -> a nested object, in its own declaration order.

    The stack is a cycle guard, not decoration: a self-referential claim type would otherwise
    recurse until the interpreter stopped it, and a `RecursionError` out of a prompt build names
    neither the type nor the field that caused it.
    """
    if model in stack:
        raise SchemaGenerationError(
            f"{model.__name__} contains itself ({' -> '.join(m.__name__ for m in stack)} -> "
            f"{model.__name__}) — a recursive claim type has no finite JSON template")
    fields = getattr(model, "model_fields", {})
    if not fields:
        raise SchemaGenerationError(f"{model.__name__} declares no model_fields")
    return {name: _render(name, field.annotation, stack + (model,))
            for name, field in fields.items()}


def _describe_scalar(name: str, annotation: Any, nullable: bool) -> str:
    """A leaf -> the one string the model reads. Vocabulary first, then hint, then type.

    Order matters: a closed set is more informative than "string", and "integer basis points" is
    more informative than "integer". `or null` is appended rather than modelled, because JSON has
    no way to show "this key may be absent" in an example object and a second example is a second
    thing to keep in sync.
    """
    suffix = " or null" if nullable else ""

    if get_origin(annotation) is Literal and all(isinstance(v, str) for v in get_args(annotation)):
        return f"<one of: {' | '.join(get_args(annotation))}{suffix}>"

    if name in FIELD_TO_SET:
        if annotation is not str:
            raise SchemaGenerationError(
                f"{name!r} is governed by the closed {FIELD_TO_SET[name]!r} vocabulary but is "
                f"typed {annotation!r}, not str — the prompt cannot offer a word list for a "
                "field that does not hold a word")
        members = vocabulary_sets()[FIELD_TO_SET[name]]
        return f"<one of: {' | '.join(sorted(members))}{suffix}>"

    if name in _FIELD_HINT:
        return f"<{_FIELD_HINT[name]}{suffix}>"

    if annotation is Any:
        return f"<any JSON value{suffix}>"

    if isinstance(annotation, type):
        if annotation in _REFUSED:
            raise SchemaGenerationError(f"{name!r} is typed {annotation.__name__}: "
                                        f"{_REFUSED[annotation]}")
        if issubclass(annotation, Enum):
            values = " | ".join(str(member.value) for member in annotation)
            return f"<one of: {values}{suffix}>"
        for kind, described in _SCALARS:
            if issubclass(annotation, kind):
                return f"<{described}{suffix}>"

    raise SchemaGenerationError(
        f"no rendering rule for field {name!r} of type {annotation!r} — add one to schema_gen "
        "rather than letting the prompt describe a new field as an untyped value")


def _strip_optional(annotation: Any) -> tuple[Any, bool]:
    """`X | None` -> `(X, True)`; anything else -> `(annotation, False)`.

    Both spellings of a union are handled — `typing.Optional[X]` and PEP 604's `X | None` are the
    same type to pydantic and two different objects to `get_origin`, and this file is read
    through `from __future__ import annotations`, so which one arrives depends on how the
    contract happened to be written. A union of two real types is left alone and falls through to
    the error below, deliberately: `str | int` in a prompt template is a question the model
    answers differently every time.
    """
    if get_origin(annotation) in (Union, types.UnionType):
        members = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(members) == 1:
            return members[0], True
    return annotation, False


def _element_of(name: str, annotation: Any) -> Any:
    args = get_args(annotation)
    if len(args) != 1:
        raise SchemaGenerationError(
            f"{name!r} is a list with no single element type ({annotation!r}) — a bare list "
            "tells the model nothing about what belongs in it")
    return args[0]


def _value_of(name: str, annotation: Any) -> Any:
    args = get_args(annotation)
    if len(args) != 2:
        raise SchemaGenerationError(
            f"{name!r} is a mapping with no declared key/value types ({annotation!r})")
    if args[0] is not str:
        raise SchemaGenerationError(
            f"{name!r} is a mapping keyed by {args[0]!r} — JSON object keys are strings, so a "
            "non-string key cannot survive the round trip the prompt asks for")
    return args[1]


__all__ = ["SchemaGenerationError", "generate_schema_block"]
