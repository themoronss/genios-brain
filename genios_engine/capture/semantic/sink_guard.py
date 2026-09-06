"""L1.4.5-U0 · THE SINK GUARD — the last thing between an extraction and storage.

W3 exists to give the model a sink with a shape. `vocabulary.py` closes what it may SAY,
`schema_gen.py` shows it that shape, `capture/validate/schema.py` checks S-1..S-9 over what came
back. Three of the fields it fills were outside all of that.

THE HOLE
--------
`ExtractionResult` declares `roles`, `relationships` and `scheduling_proposals` as
`list[dict[str, Any]]` — "the three untyped lanes", in `contracts/extraction.py`'s own words.
Nothing on the path from the model to `l1_extraction_results` ever asked what the KEYS of those
dicts were:

* the prompt invited invention: `generate_schema_block` rendered all three as
  `[{"<key>": "<any JSON value>"}]`, and `profiles.py` points the `chat` profile at
  `scheduling_proposals` and the `transcript` profile at `roles` — two of the five registered
  profiles actively asked a model to fill an open object;
* the parse kept whatever arrived: `extractor._open_lane_entries` returns
  `{str(key): item for key, item in entry.items()}`, which normalises the key's TYPE and says
  nothing about its NAME;
* the validator waved it through: `_Shape.MAPPING_LIST` checks only that each key is a string.
  S-3 — the membership rule, the entire reason this wave was built — is applied to `intent`,
  `stance`, `extraction_profile` and four claim attributes, and to no mapping's keys anywhere.

So `roles: [{"deal_stage": "negotiation"}]` was a conforming extraction. It cached permanently,
under a name no consumer reads, with nothing anywhere recording that the model had wanted a
field we do not have. `context/extract/vocab.py` records where that ends: *268 distinct field
names in one org, 192 of them used exactly once*. The lanes were reproducing it one layer inside
the unit built to prevent it.

THE OTHER HALF OF THE HOLE
--------------------------
`open_lane.capture_unclassified` — the discovery lane's only entry point — had no caller.
`grep -rn capture_unclassified genios_engine/` returned its own definition and its own `__all__`
and nothing else, so the table could not receive a row and the vocabulary could not grow from
evidence. That failure is silent by construction: a discovery mechanism that stops discovering
breaks nothing and raises nothing, and the only symptom is a report that stays empty.

The two are one fix, and this module is it. **The point where a closed vocabulary REFUSES a name
is the natural producer for the lane that exists to hold what the vocabulary has no word for.**
The guard sifts the three dicts against `UNTYPED_LANE_KEYS` and hands every key it took out to
`capture_unclassified` as a typed `UnclassifiedObservation` — so the name survives, in the one
place designed to hold an unpromoted name, where no rule may read it (the import fence in
`tests/capture/semantic/test_import_graph.py`) and a human may promote it (L1.4.5-U2).

TWO UNITS
---------
* **`sift_untyped_lanes`** — PURE. No clock, no store, no model, no DB. Lanes in, sifted lanes
  plus typed observations out. It is the vocabulary refusal itself, and it is separated from
  persistence so it can be asserted without a database and run twice without consequence.
* **`guard_typed_sink`** — the composition, and the one call a wiring agent makes: sift, then
  persist through `capture_unclassified`. Impure only because the open lane is a table.

WHERE THIS IS CALLED (the seam D6a asked for, now taken)
-------------------------------------------------------
`capture/semantic/extractor.py::_run_calls`, at the single `return` that ends a successful
parse. The line reads::

        if parsed.usable and parsed.result is not None:
            return _guarded(parsed.result, request, open_lane)

and `extractor._guarded` is the two-line dispatch this module's two units were split for:
`sift_untyped_lanes` when there is no store (the lanes are still CLOSED — an invented name never
reaches storage — the refused names are simply not kept for review), `guard_typed_sink` when
there is one. `open_lane: OpenLaneStore | None = None` is a keyword on `extract()`, threaded into
`_run_calls` beside the cache `store` it already threads, and `None` behaves exactly as
`store=None` already does.

**Inside `_run_calls`, not around `extract()`, and the reason is the cache.** `extract` wraps
the call in `cached_extraction`, which writes the returned result into `l1_extraction_results`.
A guard applied to `outcome.result` would sift the copy the caller sees and leave the unsifted
dicts in the cached row — and every later replay reads the row, not the caller. The guard has to
run on the value the thunk returns, which is this line.

`ExtractionRequest` already carries everything else the guard needs — `org_id`, `event_id`,
`source_ref`, `content` (the prepared `clean_text` every offset is measured against) and
`eval_time` — so nothing has to be recomputed or guessed at the seam. The lane store itself
reaches `extract()` from `pipeline.SemanticLane.open_lane`, built by
`platform/wiring.make_open_lane_store`.

BASIS POINTS, AND A CLOCK THAT IS A PARAMETER. `REFUSED_KEY_CONFIDENCE_BP` is an integer bp
like every score in Layer 1, and `eval_time` is passed in so a capture and the report that reads
it agree about when "now" was.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from genios_engine.capture.semantic.open_lane import OpenLaneCapture, OpenLaneStore, \
    capture_unclassified
from genios_engine.capture.semantic.vocabulary import UNTYPED_LANES, untyped_lane_sets
from genios_engine.contracts.evidence import MAX_QUOTE_CHARS, EvidenceSpan
from genios_engine.contracts.extraction import ExtractionResult, UnclassifiedObservation

log = logging.getLogger(__name__)

#: The receipt key every one of the three lanes carries by convention (see
#: `context/extract/prompt.py`, which asks for it on `roles`, `relationships` and
#: `scheduling_proposals` alike). The guard prefers it when minting a probe span, because the
#: refused value is usually a LABEL — citing a label as though it were source text is the
#: fabrication the open lane exists to detect, not to manufacture.
EVIDENCE_TEXT_KEY = "evidence_text"

#: What a salvaged key is worth, in integer basis points. The guard is certain the key was
#: refused and has NO opinion about the world, so it does not get to claim one: 5000 is the
#: honest reading of a claim nobody graded.
#:
#: It is also deliberately modest, because `_most_significant` trims the open lane by confidence
#: and the model's own deliberate noticing must outrank the guard's bookkeeping. A guard that
#: scored its salvage at 10000 would quietly turn a discovery lane into a defect log — five real
#: observations evicted per message by five mis-keyed dict entries.
REFUSED_KEY_CONFIDENCE_BP = 5000

#: The `key` recorded for an entry that was not an object at all. Not a real key name — no key
#: was reachable — and deliberately unmistakable for one, since it is what a reviewer reads.
WHOLE_ENTRY = "<entry>"

#: The `key` recorded when the LANE itself was not a list. Paired with `entry_index=None`, which
#: is what distinguishes "this lane is malformed" from "entry 0 of this lane is malformed".
WHOLE_LANE = "<lane>"

#: How much of a refused value the description echoes. A description is read in a weekly report
#: beside four others; a 400-character value inlined there buries the name that is the point.
_VALUE_ECHO = 80


@dataclass(frozen=True)
class RefusedKey:
    """One key the closed lane vocabulary would not accept, and where it came from.

    A typed record rather than a string for the same reason `SchemaViolation` is one: "the
    extraction had an unknown field" is unactionable, and `roles[2].deal_stage` names the lane
    whose prompt is drifting. Frozen — it is a record of a decision that was made.
    """

    #: One of `UNTYPED_LANES`.
    lane: str
    #: Position in the lane list as it arrived, so a reviewer can go straight to the entry.
    #: `None` when the LANE itself was refused and there was no entry to point at.
    entry_index: int | None
    #: The key as the model spelled it, verbatim. `WHOLE_ENTRY` when the entry was not an object,
    #: `WHOLE_LANE` when the lane was not a list.
    key: str
    #: WHY, in one line. It stands alone in a log row.
    reason: str

    @property
    def path(self) -> str:
        """`roles[2].deal_stage` — the dotted path a reader greps for.

        `roles.<lane>` when there was no entry index, because `roles[None]` reads as a bug in
        this property rather than as the fact it is reporting.
        """
        if self.entry_index is None:
            return f"{self.lane}.{self.key}"
        return f"{self.lane}[{self.entry_index}].{self.key}"


@dataclass(frozen=True)
class SiftedExtraction:
    """What the pure sift produced: a result whose three lanes carry only declared keys.

    `result.unclassified_observations` already contains the salvaged names — the model's own
    observations first, so the cap's index tie-break keeps them — because the open lane is where
    an unrecognised name BELONGS, not a side channel the caller may forget to read.
    """

    result: ExtractionResult
    #: Every key taken out, including the ones that became observations.
    refused: tuple[RefusedKey, ...] = ()
    #: The subset of `refused` that could not be given a receipt, and so could not become an
    #: observation at all. See `_probe` for why that is a real outcome and not a swallowed error.
    unreceiptable: tuple[RefusedKey, ...] = ()


@dataclass(frozen=True)
class GuardedExtraction:
    """`SiftedExtraction` plus what the open lane did with it. The guard's whole outcome."""

    result: ExtractionResult
    refused: tuple[RefusedKey, ...] = ()
    unreceiptable: tuple[RefusedKey, ...] = ()
    capture: OpenLaneCapture = OpenLaneCapture()


def _echo(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= _VALUE_ECHO else f"{text[:_VALUE_ECHO]}…"


def _probe(entry: Mapping[str, Any], key: str, source_ref: str) -> EvidenceSpan | None:
    """The receipt for a salvaged key, or `None` when the entry holds no text to cite.

    A PROBE, not a claim about position: offsets 0..len and `verified=False`, exactly as
    `extractor._spans_from_payload` does for a model that quoted well and counted badly. ALG-08's
    cascade is what decides whether the words are real — `capture_unclassified` re-grades every
    receipt it stores — so the guard never gets to assert that its own salvage was checked.

    `evidence_text` first, the refused value second. The entry's own receipt points at the
    sentence the entry is ABOUT; the refused value is usually a label ("negotiation"), and a
    label that happens to appear in the text would grade VERIFIED while citing nothing.

    `None` is a real answer. `UnclassifiedObservation` refuses a receiptless observation — "the
    one thing this lane must not accumulate" — so a key whose entry carries no text cannot become
    a row. It is still REMOVED from the dict and still NAMED, in `SiftedExtraction.unreceiptable`;
    what it does not get is a table row asserting evidence that does not exist.
    """
    for candidate in (entry.get(EVIDENCE_TEXT_KEY), entry.get(key)):
        if isinstance(candidate, str) and candidate.strip():
            quote = candidate[:MAX_QUOTE_CHARS]
            return EvidenceSpan(source_ref=source_ref, quote=quote, start_offset=0,
                                end_offset=len(quote), verified=False)
    return None


def _observation(lane: str, key: str, value: Any, span: EvidenceSpan) -> UnclassifiedObservation:
    """One refused key -> one open-lane observation.

    `proposed_kind` is the key AS THE MODEL SPELLED IT, not `roles.deal_stage`. The lane is
    context and belongs in the description; the label is what a human eventually promotes into
    `vocabulary.py`, and `roles_deal_stage` is not a name anybody would promote. It also means
    the same invented name arriving through two different lanes groups as one candidate, which
    is the whole reason `canonical_kind` exists.
    """
    return UnclassifiedObservation(
        proposed_kind=key,
        description=(f"the extractor named {key!r} in the {lane} lane, which the closed key set "
                     f"for that lane does not carry; the value was {_echo(value)}"),
        evidence=[span], confidence_bp=REFUSED_KEY_CONFIDENCE_BP)


def _sift_lane(lane: str, entries: Any, allowed: frozenset[str], source_ref: str,
               ) -> tuple[list[dict[str, Any]], list[RefusedKey], list[RefusedKey],
                          list[UnclassifiedObservation]]:
    """One lane: the entries that survive, what was taken out, and what the lane learned.

    An entry that is not a mapping is refused WHOLE. The contract's `_open_lane_dicts` raises on
    one, so it cannot arrive through the constructor — but `model_construct` and a rehydrated
    cache row both skip validation by documented design, and `capture/validate/schema.py` names
    those two routes for exactly this reason. A guard that indexed into it would raise inside
    the one function whose job is to be the last line.

    An entry whose every key is refused is dropped rather than kept as `{}`: an empty object is
    a row every consumer iterates over and none can read, and it would leave the lane looking
    populated while carrying nothing.
    """
    kept: list[dict[str, Any]] = []
    refused: list[RefusedKey] = []
    unreceiptable: list[RefusedKey] = []
    observations: list[UnclassifiedObservation] = []

    if entries is None:
        return kept, refused, unreceiptable, observations
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        record = RefusedKey(lane=lane, entry_index=None, key=WHOLE_LANE,
                            reason=f"{lane} is a {type(entries).__name__}, not a list of objects "
                                   "— there is no entry in it whose keys could be checked")
        refused.append(record)
        unreceiptable.append(record)
        return kept, refused, unreceiptable, observations

    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            record = RefusedKey(lane=lane, entry_index=index, key=WHOLE_ENTRY,
                                reason=f"{lane}[{index}] is a {type(entry).__name__}, not an "
                                       "object — it carries no key that could be checked")
            refused.append(record)
            unreceiptable.append(record)
            continue

        # Keys are stringified ONCE, up front, and everything below reads the normalised entry.
        # `extractor._open_lane_entries` normalises the same way, so this is the shape the lane
        # actually arrives in; doing it per-lookup instead would let a non-string key be refused
        # under its stringified name and then probed under a name the entry does not have.
        normalised = {str(key): value for key, value in entry.items()}
        survivors = {key: value for key, value in normalised.items() if key in allowed}
        for key, value in normalised.items():
            if key in allowed:
                continue
            record = RefusedKey(lane=lane, entry_index=index, key=key,
                                reason=f"{key!r} is not a key of the {lane} lane; the closed set "
                                       f"is {' | '.join(sorted(allowed))}")
            refused.append(record)
            span = _probe(normalised, key, source_ref)
            if span is None:
                unreceiptable.append(record)
                continue
            observations.append(_observation(lane, key, value, span))
        if survivors:
            kept.append(survivors)

    return kept, refused, unreceiptable, observations


def _rebuilt(result: ExtractionResult, lanes: Mapping[str, list[dict[str, Any]]],
             observations: Sequence[UnclassifiedObservation]) -> ExtractionResult:
    """The sifted extraction, through the real constructor.

    Fields are read off `ExtractionResult.model_fields` and passed as the TYPED objects they
    already are, so a field added to the contract next year is carried automatically instead of
    being silently dropped by a hand-written reconstruction — which is the same
    extractor-writes-one-name-reader-reads-another failure in constructor form.

    `model_copy(update=...)` would be shorter and is deliberately not used: it skips validation,
    and the thing this function returns is the object that reaches storage. `all_evidence` is
    EXTENDED rather than recomputed, because `evidence_from_claims()` would drop any span the
    extraction asserted without attaching to a claim — S-7 permits those and losing them is data
    loss — while S-7 requires every span a claim carries to be indexed, including the new probes.
    """
    fields = {name: getattr(result, name, None) for name in ExtractionResult.model_fields}
    fields.update(lanes)
    fields["unclassified_observations"] = list(observations)

    indexed = list(fields.get("all_evidence") or [])
    seen = set(indexed)
    for observation in observations:
        for span in observation.evidence:
            if span not in seen:
                seen.add(span)
                indexed.append(span)
    fields["all_evidence"] = indexed
    return ExtractionResult(**fields)


def sift_untyped_lanes(result: ExtractionResult, *, source_ref: str) -> SiftedExtraction:
    """L1.4.5-U0a · close the three untyped lanes. Pure: no clock, no store, no model, no DB.

    Every key outside `UNTYPED_LANE_KEYS[lane]` is removed from the dict and re-expressed as an
    `UnclassifiedObservation` on the result — typed, receipted, and in the one place an
    unpromoted name is allowed to live. The model's own observations keep their positions at the
    front of the list so that `capture_unclassified`'s confidence cap, which breaks ties by
    index, trims salvage before it trims noticing.

    Idempotent by construction: sifted output carries no refused keys, so a second pass changes
    nothing. That matters at the seam it is called from — a repair retry, a replay and a re-drain
    can all put the same extraction through it.

    `source_ref` is the frame the probe spans are stamped with, and it is a parameter rather than
    derived: `ExtractionRequest.source_ref` is the one place that string is built, and a second
    place that assembled it by hand is a second place for the two to disagree.
    """
    lanes: dict[str, list[dict[str, Any]]] = {}
    refused: list[RefusedKey] = []
    unreceiptable: list[RefusedKey] = []
    salvaged: list[UnclassifiedObservation] = []
    allowed_by_lane = untyped_lane_sets()

    for lane in UNTYPED_LANES:
        kept, lane_refused, lane_unreceiptable, observations = _sift_lane(
            lane, getattr(result, lane, None), allowed_by_lane[lane], source_ref)
        lanes[lane] = kept
        refused.extend(lane_refused)
        unreceiptable.extend(lane_unreceiptable)
        salvaged.extend(observations)

    if not refused:
        return SiftedExtraction(result=result)

    log.info("sink guard: refused %d lane key(s) into the open lane (%s)",
             len(refused), ", ".join(record.path for record in refused))
    observations = list(result.unclassified_observations) + salvaged
    return SiftedExtraction(result=_rebuilt(result, lanes, observations),
                            refused=tuple(refused), unreceiptable=tuple(unreceiptable))


def guard_typed_sink(result: ExtractionResult, *, org_id: str, event_id: str, source_ref: str,
                     source_text: str, eval_time: datetime,
                     store: OpenLaneStore) -> GuardedExtraction:
    """L1.4.5-U0 · the boundary guard, and the open lane's producer. Sift, then persist.

    The one call the wiring agent makes; the module docstring names the exact line. Returns a
    `GuardedExtraction` whose `result` is what may reach storage: a typed `ExtractionResult`
    whose three lanes carry only declared keys and whose open lane carries every name they did
    not. `capture` says what the discovery table did with those names — how many rows were new,
    how many were trimmed by the cap, how many cited a sentence that is not in the source.

    `source_text` is the PREPARED clean text the extractor was shown, because that is the only
    coordinate system in which a span can be graded; `capture_unclassified` re-grades every
    probe this guard minted against it and stores the CORRECTED offsets with the verdict ALG-08
    gave, never the flag the guard set.

    An extraction with nothing refused and nothing to observe touches no storage at all, which is
    the overwhelmingly common case and must cost nothing.
    """
    sifted = sift_untyped_lanes(result, source_ref=source_ref)
    capture = capture_unclassified(sifted.result, org_id=org_id, event_id=event_id,
                                   source_text=source_text, eval_time=eval_time, store=store)
    return GuardedExtraction(result=sifted.result, refused=sifted.refused,
                             unreceiptable=sifted.unreceiptable, capture=capture)


__all__ = ["EVIDENCE_TEXT_KEY", "REFUSED_KEY_CONFIDENCE_BP", "WHOLE_ENTRY", "WHOLE_LANE",
           "GuardedExtraction", "RefusedKey", "SiftedExtraction", "guard_typed_sink",
           "sift_untyped_lanes"]
