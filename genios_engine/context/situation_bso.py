"""Produce the typed Layer 2 -> Layer 3 boundary objects from live L2 situation output.

Layer 2 stores situations in ``context_situations`` and their evidence across
``context_correlation_members`` + ``graph_source_refs``; the graph slice comes from the same
``NodeContext`` the reasoning engine already loads. This module packs those into the two frozen
contracts the Domain Expertise compiler consumes — ``BusinessSituationObject`` and
``SituationContextSlice`` — WITHOUT reaching past Layer 2 (Layer 3 never reads the graph itself).

WHERE IMPORTANCE COMES FROM. Layer 1 scores every signal it publishes (ALG-17) and stores that
score, its components and its version in ``qualified_signals``. This module READS that row — see
``gather_l1_signals`` — and never re-derives it. The constant it used to stamp instead is kept as
``DEFAULT_IMPORTANCE_BP``, reachable only when the situation's events published no live signal at
all (a pre-L1-v2 tenant, or a correlation whose signals have all expired), and the BSO says which
of the two it is in ``metadata['importance_source']``.

Deliberately honest about the seam's remaining gaps (see the design doc's Layer 3 gaps):
  * signal ids / evidence fall back to a reconstruction from the correlation when no qualified
    signal exists for the situation's events;
  * missing_fields uses field-path keys, never the plain-language ``missing`` labels (those have
    spaces and are not identifiers) — so it is derived here from the domain spec's expected
    fields rather than copied off the situation row.
These are marked in metadata so a shadow package is never mistaken for a fully-sourced one.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import bindparam, text

from genios_engine.capture.validate.spans import SpanVerdict, verify_span
from genios_engine.context.domain_spec import spec_for
from genios_engine.context.importance import (
    READ_CHUNK as _READ_CHUNK,
)
from genios_engine.context.importance import (
    ComposedImportance,
    ImportanceBase,
    ModifierInputs,
    SituationRef,
    assess_l1_supply,
    compose_situation_importance,
    load_modifier_inputs,
    read_constituent_signals,
)
from genios_engine.context.quality.inference import absence_metadata
from genios_engine.context.quality.missing import absent_fields, unknowable_fields
from genios_engine.context.situations import COVERAGE_UNKNOWN, SCORE_MAX, analytic_receipt
from genios_engine.contracts.domain_expertise import (
    BusinessSituationObject,
    SituationContextSlice,
)
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.situation_evidence import (
    AXIS_UNKNOWN_BP,
    VERDICT_INVALID_BOUNDS,
    VERIFICATION_L1,
    VERIFICATION_NONE,
    VERIFICATION_REVERIFIED,
    SituationConfidenceVector,
    VerifiedEvidenceSpan,
)
from genios_engine.contracts.visibility import Visibility, narrowest
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.context.situation_bso")

# The selector identity for this producer. Bump when the field mapping below changes so a
# replayed slice is never silently attributed to a different extraction.
SELECTOR_VERSION = "l2-situation-selector.v1"

# The FALLBACK importance, and nothing else. A situation whose events published no live
# qualified signal has no score to carry, and a neutral midpoint neither inflates nor suppresses
# the package. It stopped being the answer for scored situations the day `qualified_signals`
# landed: see `gather_l1_signals` and the module docstring.
DEFAULT_IMPORTANCE_BP = 5000

#: `importance_version` on a signal the floor let through WITHOUT a score (doc 06: a floor must
#: never refuse what it could not measure). Such a row publishes at `importance_bp = 0`, and 0 is
#: an ABSENCE, not a low score — reading it as one would rank an unmeasured signal below every
#: measured one. Spelled here rather than imported so Layer 2 does not take a hard dependency on
#: a Layer 1 module for one string; `test_l2_reads_what_l1_publishes` pins the two together.
UNSCORED_VERSION = "unscored"

#: `qualified_signals.state` for a signal ALG-19 has not retired. Spelled here for the same
#: reason as `UNSCORED_VERSION` above: Layer 2 does not take a hard dependency on a Layer 1
#: module for one word, and `test_l2_reads_what_l1_publishes` pins the two together.
SIGNAL_ACTIVE = "active"

#: The one component that is a WRITE TIME rather than a judgement. `ImportanceComponents.
#: as_record` stamps the sweep's frozen instant into every stored components dict, and this
#: module's output is CONTENT-ADDRESSED: `BusinessSituationObject.to_semantic_dict` hashes
#: `metadata`, so carrying the instant would mint a brand-new `expertise_packages` row on every
#: sweep for a situation nothing had changed about. That exact failure — a fresh ~238 kB row per
#: situation per sweep — put 995 MB on one tenant's database and took the project read-only; see
#: `to_semantic_dict`'s docstring for the trace-id version of it. The instant is not lost: it is
#: on the `qualified_signals` row the BSO's `signal_ids` now point at.
_UNSTABLE_COMPONENT = "eval_time"

#: How many receipts a BSO carries. It is a summary a human or an LLM reads, not the evidence
#: table — the same reason `entities` is capped at 20.
MAX_EVIDENCE = 20

#: How many raw spans one situation's verification pass may grade before `MAX_EVIDENCE` picks the
#: ones it publishes. The cap used to be applied BEFORE grading, which is the wrong order once
#: grading exists: the twenty spans a correlation happens to list first are not the twenty that
#: resolve, so a situation carrying one verified quote in position 34 published as if it had none.
#: Ten times the publishing cap, because the pool is only ever read to find twenty and a
#: correlation with 200 distinct quoted sentences has already told us everything it can.
EVIDENCE_POOL = MAX_EVIDENCE * 10

#: How many disagreements a BSO names. Same argument as `MAX_EVIDENCE`: the pointer is the
#: product, the table is where the rest lives.
MAX_CONFLICTS = 20

#: ALG-08's four RESOLVED grades — "these words are in that text". Listed positively, as the enum
#: members rather than as strings, so a seventh grade added to the cascade is a type error here
#: instead of silently defaulting to ACCEPTED. `contracts/situation_evidence.VERIFIED_VERDICTS`
#: is the same set spelled as strings for the contract layer, and
#: `tests/context/test_situation_publisher.py` pins the two together the way
#: `test_l2_reads_what_l1_publishes` pins `UNSCORED_VERSION`.
RESOLVED_GRADES: frozenset[SpanVerdict] = frozenset({
    SpanVerdict.VERIFIED,
    SpanVerdict.VERIFIED_WHITESPACE,
    SpanVerdict.VERIFIED_RELOCATED,
    SpanVerdict.VERIFIED_FUZZY,
})

#: The one `EvidenceSpan.source_ref` frame Layer 2 can resolve text for. C-01 documents two —
#: `prepared_content:<id>` and `chunk:<doc_id>:<n>` — and the second has no store: chunks are
#: transient inside the extraction that produced them (an uploaded document's chunks each become
#: their own `source_events` row, so they arrive here in the first frame anyway). A span in an
#: unresolvable frame is NOT failed for it: it falls back to Layer 1's own verdict, which is a
#: check that happened rather than one we can repeat. Refusing it would delete real receipts for
#: the sin of being old.
PREPARED_FRAME = "prepared_content:"


def _bp(percent: Any) -> int:
    """L2 confidence/coverage are int 0..SCORE_MAX percent; the contracts want basis points.

    The clamp is a floor/ceiling on a legal percent, NOT a scale converter. Feed it a number
    already in basis points and it saturates silently: 2500 (a knowledge_gap coverage honestly
    capped at a quarter) and 3000 (escalation) both came out of here as 10000 — the same value a
    fully-covered recorded situation produces — which is exactly the "reports coverage it does not
    have" failure the caps exist to prevent, and it left
    `expertise_builder`'s `min(situation.confidence_bp, expert.coverage_bp)` with nothing to cap.
    `situations.SCORE_MAX` now names the storage unit so a writer cannot pick the other one by
    accident, and `tests/test_situation_bso.py` pins that an inferred situation can never reach a
    recorded one's coverage across this seam.
    """
    try:
        value = int(percent or 0) * 100
    except (TypeError, ValueError):
        value = 0
    return max(0, min(SCORE_MAX * 100, value))


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else (str(value) if value else None)


def _no_floats(value: Any) -> Any:
    """The frozen contracts forbid floats (they are not replay-stable). L2 graph facts carry
    numeric confidence as float, so convert any float to Decimal (which canonicalisation allows)
    before it enters a semantic artifact. Recurses through mappings and sequences."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, Mapping):
        return {k: _no_floats(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_no_floats(v) for v in value]
    return value


def gather_evidence_and_signals(
    conn, org_id: str, correlation_id: str | None, situation_id: str,
) -> tuple[list[str], list[Mapping[str, Any]]]:
    """Reconstruct the situation's qualified signal ids + evidence receipts from L2 tables.

    Both BSO fields are required and non-empty; when the correlation has no members yet we fall
    back to a single synthetic receipt derived from the situation id so the contract still holds
    and the reconstruction is visibly labelled rather than faked as source evidence.
    """
    signal_ids: list[str] = []
    evidence: list[Mapping[str, Any]] = []
    if correlation_id:
        events = conn.execute(text(
            "select event_id from context_correlation_members "
            "where org_id=:o and correlation_id=:c order by event_id"),
            {"o": org_id, "c": correlation_id}).scalars().all()
        signal_ids = [str(e) for e in events]
        if signal_ids:
            refs = conn.execute(text(
                "select event_id, source, source_object_id, evidence from graph_source_refs "
                "where org_id=:o and event_id = any(cast(:ev as text[])) order by event_id"),
                {"o": org_id, "ev": signal_ids}).mappings().all()
            evidence = [{
                "event_id": str(r["event_id"]),
                "source": r["source"],
                "source_object_id": r["source_object_id"],
                "evidence": r["evidence"],
            } for r in refs]
    if not signal_ids:
        signal_ids = [f"sig:{situation_id}"]
    if not evidence:
        evidence = [{"event_id": signal_ids[0], "source": "situation",
                     "reconstructed": True}]
    return signal_ids, evidence


def _json(value: Any, fallback: Any) -> Any:
    """One jsonb column on the way back. psycopg2 decodes jsonb to dicts and lists already; a
    driver that hands back text is the other case, and anything unreadable is the fallback rather
    than an exception — a receipt that cannot be parsed must not stop a situation compiling."""
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):      # pragma: no cover - a column that is not JSON at all
        return fallback


@dataclass(frozen=True)
class L1Signals:
    """What Layer 1 already concluded about the events this situation is built from.

    A record rather than a tuple because the caller uses five of its fields in three different
    ways, and because `importance_bp = None` (nothing scored) and `importance_bp = 0` (scored,
    and genuinely worth nothing) are different answers that a bare int cannot tell apart.

    TWO READINGS, DELIBERATELY SEPARATED — this is the shape of the fix in `gather_l1_signals`.

    * The PROVENANCE (`signal_ids`, `scored_signal_ids`, `evidence`, `conflict_ids`): every
      qualified signal this situation rests on, in every lifecycle state. It answers "what is
      this situation built from", it only ever grows (when Layer 1 publishes something new), and
      it is therefore safe to content-address.
    * The LIVE reading (`importance_bp` and everything that travels with it, `signal_count`,
      `scored_count`): the `state='active'` subset, at the instant the sweep looked. ALG-19 moves
      it on every sync. It decides the SCORE and nothing else.
    """

    #: `qualified_signals.signal_id` — the REAL ids, not the event ids the reconstruction uses.
    #: EVERY state, not just the live ones: see the class docstring, and `gather_l1_signals`.
    signal_ids: tuple[str, ...] = ()
    #: Those of `signal_ids` that carry a measured score (ALG-17 ran on them). Provenance, so
    #: all-state like `signal_ids` — an expired signal was still scored when it was published.
    scored_signal_ids: tuple[str, ...] = ()
    #: ALG-17's score, from the highest-scoring SCORED signal that is still LIVE. `None` when
    #: every live signal the situation rests on published unscored.
    importance_bp: int | None = None
    importance_version: str | None = None
    #: That signal's own components — "why is this an 8100" travels with the number.
    components: Mapping[str, Any] = field(default_factory=dict)
    #: The evidence spans Layer 1 verified, deduplicated across signals. Provenance: an expired
    #: signal's verified quote is still the receipt this situation was built on.
    evidence: tuple[Mapping[str, Any], ...] = ()
    #: `signal_conflicts.conflict_id` for every disagreement these signals took part in.
    conflict_ids: tuple[str, ...] = ()
    #: How many LIVE signals were read, and how many of those carried a score. The reading of the
    #: moment — never put either in a content address; `signal_ids` is what the situation IS.
    signal_count: int = 0
    scored_count: int = 0
    #: `qualified_signals.signal_type` for every signal the situation rests on, deduplicated and
    #: sorted. L2.7.8's `type` row: *"QES signal_type + pattern match"*. Provenance, so all-state —
    #: what a situation IS about does not change when one of its signals ages out.
    signal_types: tuple[str, ...] = ()
    #: The `signal_conflicts` rows behind `conflict_ids`, projected to the stable fields (doc
    #: L2.7.8: *"conflicts from L1 v2 arrive in metadata"*). A POINTER was never enough on its own:
    #: Layer 3 cannot decide whether a situation is contested without knowing WHAT was contested,
    #: and it may not reach past Layer 2 to find out.
    conflicts: tuple[Mapping[str, Any], ...] = ()
    #: The QES's own `coverage_ready`, CARRIED and never re-derived (doc 08's addition list says
    #: exactly that). Tri-state: True/False is Layer 1's assessment for the signal that set this
    #: situation's score, and `None` is "no live scored signal, or Layer 1 did not assess" — which
    #: must not arrive at a predicate as False, or every `no_obs` rule silently stops for a tenant
    #: whose coverage row has simply not been filed yet.
    coverage_ready: bool | None = None
    #: How many spans were graded and how many of those resolved. The publisher's own measurement,
    #: carried so the group gate's "BSOs with a verified evidence span — 100%" row is a count over
    #: stored metadata rather than a re-run of the validator.
    span_count: int = 0
    verified_span_count: int = 0


def _span_key(span: Mapping[str, Any]) -> tuple[Any, ...]:
    return (span.get("source_ref"), span.get("start_offset"), span.get("end_offset"),
            span.get("quote"))


# =================================================================================================
# L2.7.8 — THE EVIDENCE UPGRADE: event references become span-validated verbatim quotes
# =================================================================================================
#
# Doc 07, in its own words: *"today a situation's evidence is a list of event references. In v2 it
# is a list of span-validated verbatim quotes — so a card can show the sentence, not just name the
# email."* That is the difference between "there is an email about this" and "he wrote: *we're
# pausing until Q3*", and it is the difference between a card a founder acts on and one they open
# the mailbox to check.
#
# THE VALIDATOR IS L1'S. `capture/validate/spans.verify_span` (ALG-08) is the one that exists, and
# `context/lifecycle/judge.py` already imports it for M-4 — the precedent this follows. A second
# implementation here would be a second policy: two answers to "is this quote real", differing at
# exactly the whitespace and relocation cases the cascade was written for, with only one of them
# tested.


def gather_span_sources(conn, org_id: str, source_refs: Sequence[str]) -> dict[str, str]:
    """The stored source text behind each `prepared_content:` reference, in ONE read per chunk.

    Keyed by the REFERENCE, not by the event: `EvidenceSpan.source_ref` is the join key the card
    renderer and the audit row carry verbatim, and two spellings of it are in circulation —
    `capture/pipeline` stamps `prepared_content:<prepared_content_id>` while
    `context/lifecycle/contract` and doc 08 use `prepared_content:<event_id>`. Both are answered
    here, from the same row, because a resolver that knew only one of them would silently grade
    half the corpus as unverifiable and the half would depend on which lane captured it.

    A reference this returns nothing for is not an error and not a failure: see `PREPARED_FRAME`.
    """
    wanted = {str(ref) for ref in source_refs if str(ref).startswith(PREPARED_FRAME)}
    if not wanted:
        return {}
    ids = sorted({ref[len(PREPARED_FRAME):] for ref in wanted})
    out: dict[str, str] = {}
    for start in range(0, len(ids), _READ_CHUNK):
        chunk = ids[start:start + _READ_CHUNK]
        rows = conn.execute(text(
            "select event_id, prepared_content_id, clean_text from prepared_content "
            "where org_id = :o and (event_id = any(cast(:ids as text[])) "
            "                       or prepared_content_id = any(cast(:ids as text[])))"),
            {"o": org_id, "ids": chunk}).mappings().all()
        for row in rows:
            body = row["clean_text"]
            if not body:
                continue
            for key in (row["event_id"], row["prepared_content_id"]):
                if key:
                    out[f"{PREPARED_FRAME}{key}"] = str(body)
    return {ref: body for ref, body in out.items() if ref in wanted}


def verify_evidence_spans(raw: Sequence[Mapping[str, Any]],
                          sources: Mapping[str, str]) -> tuple[VerifiedEvidenceSpan, ...]:
    """Grade every stored span against the source text, with ALG-08, and record what it decided.

    PURE — the read is `gather_span_sources`' job and the clock is nobody's. Three outcomes, and
    the reason each is a separate state is that they are three different claims about the same
    quote (see `contracts/situation_evidence`'s verification vocabulary):

    * source text in hand and the cascade resolved it -> `l2_reverified`, and the span is REWRITTEN
      at the offsets ALG-08 actually found. A relocated quote whose stored offsets were wrong
      publishes with the offsets that work, because a receipt whose numbers do not point at the
      sentence is not a receipt a card can highlight;
    * source text in hand and the cascade did NOT resolve it -> `unverified`, whatever Layer 1's
      own flag said. The check we can repeat outranks the flag we cannot;
    * no source text (retention window passed, or a frame with no store) -> Layer 1's flag stands,
      as `l1_verified`, and no grade is invented for it.

    A span that cannot be expressed as a span at all — an inverted range, a quote whose length
    disagrees with its offsets — is graded `invalid_bounds` and kept, unverified. Kept rather than
    dropped for ALG-08's own reason: *"the assertion is evidence about the extractor even when it
    is not evidence about the world"*, and a receipt that silently disappeared is a receipt nobody
    ever fixes.
    """
    graded: list[VerifiedEvidenceSpan] = []
    for span in raw:
        source_ref = str(span.get("source_ref") or "")
        quote = span.get("quote")
        signal_id = str(span.get("signal_id") or "")
        if not source_ref or not isinstance(quote, str) or not quote.strip() or not signal_id:
            # Not a receipt in any state: it names no text, quotes nothing, or cannot be traced
            # back to the signal that carried it. There is nothing here to grade or to show.
            continue
        start, end = _offset(span.get("start_offset")), _offset(span.get("end_offset"))
        verdict, verification = "", (VERIFICATION_L1 if span.get("verified") is True
                                     else VERIFICATION_NONE)
        body = sources.get(source_ref)
        if body is not None:
            try:
                probe = EvidenceSpan(source_ref=source_ref, quote=quote,
                                     start_offset=start, end_offset=end)
            except (TypeError, ValueError):
                verdict, verification = VERDICT_INVALID_BOUNDS, VERIFICATION_NONE
            else:
                grade, resolved = verify_span(probe, body)
                verdict = grade.value
                if grade in RESOLVED_GRADES:
                    verification = VERIFICATION_REVERIFIED
                    quote, start, end = (resolved.quote, resolved.start_offset,
                                         resolved.end_offset)
                else:
                    verification = VERIFICATION_NONE
        try:
            graded.append(VerifiedEvidenceSpan.build(
                source_ref=source_ref, quote=quote, start_offset=start, end_offset=end,
                verdict=verdict, verification=verification, signal_id=signal_id))
        except (TypeError, ValueError):   # pragma: no cover - a row from a writer that is not L1
            # A receipt the contract refuses (a signal id that is not an identifier, a quote that
            # is nothing but whitespace) is dropped rather than raised. The rule this module keeps
            # everywhere: a receipt that cannot be parsed must not stop a situation compiling.
            _log.warning("dropping an unciteable evidence span from signal %r", signal_id)
    return tuple(graded)


def _offset(value: Any) -> int:
    """A stored offset, or 0. `None` and a non-numeric body both mean "the writer said nothing",
    and 0 is what `EvidenceSpan` will then refuse coherently rather than what this function has
    to decide about."""
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _graded_evidence(l1: L1Signals, sources: Mapping[str, str]) -> L1Signals:
    """One situation's receipts, graded and ORDERED SO THE VERIFIED ONES SURVIVE THE CAP.

    The ordering is the whole reason the pool exists. `MAX_EVIDENCE` used to be applied to the raw
    list before anything was graded, so which receipts a BSO carried was decided by which signals
    happened to score highest — and a situation whose one verified quote sat in position 34
    published as though it had none, failing the acceptance row for a reason that had nothing to do
    with its evidence. Verified first, then the rest in their existing order (importance, then
    signal id), then the cap.
    """
    graded = verify_evidence_spans(l1.evidence[:EVIDENCE_POOL], sources)
    ordered = [span for span in graded if span.verified] + [
        span for span in graded if not span.verified]
    return replace(l1,
                   evidence=tuple(span.as_record() for span in ordered[:MAX_EVIDENCE]),
                   span_count=len(graded),
                   verified_span_count=sum(1 for span in graded if span.verified))


def _verify_evidence(conn, org_id: str, folded: dict[str, L1Signals]) -> dict[str, L1Signals]:
    """The verification pass for a whole sweep: ONE source read, then a pure grading per situation.

    Shaped like every other reader in this module and for the same reason
    (`docs/plans/PERFORMANCE_HARDENING.md`): a per-situation text fetch would be one round trip per
    situation against a table that answers the whole org in one.
    """
    if not folded:
        return folded
    refs = {str(span.get("source_ref") or "")
            for l1 in folded.values() for span in l1.evidence[:EVIDENCE_POOL]}
    sources = gather_span_sources(conn, org_id, sorted(refs - {""}))
    return {key: _graded_evidence(l1, sources) for key, l1 in folded.items()}


#: The `signal_conflicts` projection a BSO carries. `detected_at` is DELIBERATELY ABSENT — the
#: metadata this lands in is hashed into the expertise package's content address, and a clock there
#: mints a fresh package row per situation per sweep (the 995 MB read-only incident's mechanism).
#: `claims` is counted rather than copied for a second reason: it holds both sides of a
#: disagreement verbatim, including the losing claim's quoted text, and a BSO is a summary.
_CONFLICT_SELECT = (
    "select conflict_id, signal_id, field, subject_key, resolution, resolved_value, event_ids, "
    "       jsonb_array_length(claims) as claim_count "
    "from signal_conflicts where org_id = :o and conflict_id = any(cast(:ids as text[])) "
    "order by conflict_id")


def gather_conflicts(conn, org_id: str,
                     conflict_ids: Sequence[str]) -> dict[str, Mapping[str, Any]]:
    """The disagreements behind `qualified_signals.conflict_ids`, as records rather than pointers.

    L2.7.8's third acceptance row is *"conflicts from L1 v2 arrive in metadata"*, and an id alone
    does not arrive anywhere: Layer 3 may not read past Layer 2, so a situation resting on a
    contested claim reached the compiler looking exactly as settled as one that was never
    contested. What travels is WHICH FIELD disagreed, HOW Layer 1 resolved it, and how many claims
    were in the disagreement — enough for a reader to refuse to be confident, without copying the
    losing side's prose into a content-addressed artifact.
    """
    ordered = sorted({str(c) for c in conflict_ids if c})
    out: dict[str, Mapping[str, Any]] = {}
    for start in range(0, len(ordered), _READ_CHUNK):
        chunk = ordered[start:start + _READ_CHUNK]
        for row in conn.execute(text(_CONFLICT_SELECT),
                                {"o": org_id, "ids": chunk}).mappings().all():
            out[str(row["conflict_id"])] = {
                "conflict_id": str(row["conflict_id"]),
                "signal_id": str(row["signal_id"]),
                "field": str(row["field"]),
                "subject_key": str(row["subject_key"]),
                "resolution": str(row["resolution"]),
                "resolved_value": _no_floats(_json(row["resolved_value"], None)),
                "event_ids": [str(e) for e in _json(row["event_ids"], [])],
                "claim_count": int(row["claim_count"] or 0),
            }
    return out


def _attach_conflicts(conn, org_id: str, folded: dict[str, L1Signals]) -> dict[str, L1Signals]:
    """Every situation's conflict records, in ONE read for the sweep. See `_verify_evidence`."""
    ids = {cid for l1 in folded.values() for cid in l1.conflict_ids}
    if not ids:
        return folded
    records = gather_conflicts(conn, org_id, sorted(ids))
    return {key: replace(l1, conflicts=tuple(
        records[cid] for cid in l1.conflict_ids[:MAX_CONFLICTS] if cid in records))
        for key, l1 in folded.items()}


#: The one projection of `qualified_signals` this module reads, spelled once. `gather_l1_signals`
#: and `gather_l1_signals_bulk` differ ONLY in their correlation predicate and must not differ in
#: anything else: the single-situation read is what `test_l2_reads_what_l1_publishes` pins, and the
#: sweep read is what every situation in production is actually composed from. Two hand-written
#: copies of this select is how the two paths end up disagreeing about which signals a situation
#: rests on, and only one of them has a test.
_L1_SELECT = (
    "select m.correlation_id as correlation_id, qs.signal_id, qs.state, qs.importance_bp, "
    "qs.importance_version, qs.importance_components, qs.evidence_refs, qs.conflict_ids, "
    # L2.7.8's `type` row. Layer 1 already named what KIND of thing each signal is; Layer 2 spent
    # every sweep re-deriving a type from the anchor's node type and never once read this.
    "qs.signal_type, qs.coverage_ready "
    "from qualified_signals qs "
    "join context_correlation_members m "
    "  on m.event_id = qs.event_id and m.org_id = qs.org_id "
    "where qs.org_id = :o and {predicate} "
    "order by qs.importance_bp desc, qs.signal_id")


def gather_l1_signals(conn, org_id: str, correlation_id: str | None) -> L1Signals | None:
    """THE READ THIS MODULE EXISTED WITHOUT. Layer 1's published verdicts for this situation.

    `qualified_signals` (migration 0089) is the durable set the publisher writes after V-1..V-7
    return EMIT. Until this function, nothing on a request path read it: Layer 1 scored, qualified,
    aged and stored every signal, and Layer 2 then stamped a constant over the result — so 193 of
    223 signals shared one importance and Layer 4's utility formula had nothing to rank on.

    JOINED THROUGH THE CORRELATION, not through the anchor. The correlation already decided which
    events are one thing; the anchor is one node inside it. Joining on the anchor would attach a
    counterparty's whole history to whichever situation happened to name them.

    THE STATE FILTER APPLIES TO THE SCORE, AND ONLY TO THE SCORE. A superseded or expired signal
    is precisely the one that must not set a live situation's importance — ALG-19 spent a pass
    deciding that, and reading past it there would undo it silently. It is equally precisely the
    one that must still appear in the situation's PROVENANCE, for two reasons:

    * a receipt does not stop being a receipt when its clock runs out. Filtering `signal_ids` and
      `evidence` by state made a situation's own account of itself decay as it aged, until an
      old situation could name none of the signals it was built from.
    * `signal_ids`, `evidence` and `metadata` are all hashed by
      `BusinessSituationObject.to_semantic_dict`, and that hash reaches the expertise package's
      content address through `metadata['situation_hash']`. ALG-19 expires and supersedes signals
      on EVERY sync, so a state-filtered provenance re-minted the package id of every affected
      situation on every sweep, `on conflict (org_id, expertise_id) do nothing` never fired, and
      the table grew by a ~238 kB row per situation per sweep. That is not a hypothetical: the
      trace-id form of the same mechanism put 995 MB on one tenant's database — 67% of the whole
      database — and took the project read-only, which stops every write the product makes.
      `tests/test_expertise_packages_survive_an_alg19_sweep.py` is the guard.

    The score is the one thing here that MAY move the address, and it must: a situation whose
    importance genuinely dropped because its best signal expired is a different situation to
    Layer 3, and a content address that ignored that would serve last month's ranking for ever.

    THE MAX, not the mean. A situation is as important as the most important thing in it: a
    renewal worth $84k correlated with three scheduling notes is a renewal, and averaging is how
    it becomes a scheduling note. Ordered by score then id so two equal scores cannot swap the
    components the BSO carries between two reads of an unchanged database.

    Returns `None` when the situation has no live qualified signal at all — the honest absence,
    which keeps the pre-activation fallback reachable rather than publishing a zero.
    """
    if not correlation_id:
        return None
    rows = conn.execute(text(_L1_SELECT.format(predicate="m.correlation_id = :c")),
                        {"o": org_id, "c": correlation_id}).mappings().all()
    folded = _l1_from_rows(rows)
    if folded is None:
        return None
    # L2.7.8 — the two enrichments that need the connection this function already holds: the
    # spans get graded against the stored source text, and the conflict POINTERS become records.
    # Both run through the same functions the sweep read uses, on a one-entry mapping, so the
    # per-situation path and the org path cannot answer differently.
    enriched = _attach_conflicts(conn, org_id,
                                 _verify_evidence(conn, org_id, {correlation_id: folded}))
    return enriched[correlation_id]


def _l1_from_rows(rows) -> L1Signals | None:
    """The derivation, extracted so the per-situation read and the sweep read share it exactly.

    Every judgement in `gather_l1_signals`' docstring lives HERE — the max over the LIVE SCORED
    subset, the unscored exclusion, the all-state provenance, the deduplicated evidence. The
    functions above only decide which rows to fetch.
    """
    if not rows:
        return None

    # An UNSCORED row publishes at 0 because the floor refused to invent a number, not because
    # the signal is worthless. Reading that 0 as a score would rank every unmeasured signal below
    # every measured one — the opposite of what "a floor must never refuse what it could not
    # measure" is protecting.
    scored = [r for r in rows if r["importance_version"] != UNSCORED_VERSION]
    # ALG-19's verdict, applied HERE and nowhere else in this function. `SIGNAL_ACTIVE` is spelled
    # rather than imported for the reason `UNSCORED_VERSION` is: Layer 2 does not take a hard
    # dependency on a Layer 1 module for one word, and `test_l2_reads_what_l1_publishes` pins the
    # two together.
    live = [r for r in rows if str(r["state"]) == SIGNAL_ACTIVE]
    live_scored = [r for r in live if r["importance_version"] != UNSCORED_VERSION]
    top = live_scored[0] if live_scored else None

    evidence: list[Mapping[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    conflicts: set[str] = set()
    for row in rows:
        conflicts.update(str(c) for c in _json(row["conflict_ids"], []) if c)
        for span in _json(row["evidence_refs"], []):
            if not isinstance(span, Mapping):
                continue
            key = _span_key(span)
            if key in seen:
                # One sentence cited by two signals is one receipt. Repeating it would make a
                # single quote look like corroboration.
                continue
            seen.add(key)
            evidence.append({**dict(span), "signal_id": str(row["signal_id"]),
                             "source": "l1_qualified_signal"})

    return L1Signals(
        signal_ids=tuple(str(r["signal_id"]) for r in rows),
        scored_signal_ids=tuple(str(r["signal_id"]) for r in scored),
        signal_types=tuple(sorted({str(r["signal_type"]) for r in rows if r["signal_type"]})),
        importance_bp=(int(top["importance_bp"]) if top is not None else None),
        importance_version=(str(top["importance_version"]) if top is not None
                            else UNSCORED_VERSION),
        components=dict(_json(top["importance_components"], {})) if top is not None else {},
        coverage_ready=(top["coverage_ready"] if top is not None else None),
        # POOL, not the publishing cap. `_graded_evidence` applies `MAX_EVIDENCE` after ALG-08
        # has said which of these resolve — truncating first is what published a situation whose
        # one verified quote sat in position 34 as though it had none.
        evidence=tuple(evidence[:EVIDENCE_POOL]),
        conflict_ids=tuple(sorted(conflicts)),
        signal_count=len(live),
        scored_count=len(live_scored),
    )


def gather_l1_signals_bulk(conn, org_id: str,
                           correlation_ids: Sequence[str]) -> dict[str, L1Signals]:
    """`gather_l1_signals` for a whole sweep, in ONE statement.

    THE SHAPE IS THE POINT. `refresh_situations` composes every situation the tenant holds, and a
    per-situation read here would be one query per situation against a table that fits in one:
    `docs/plans/PERFORMANCE_HARDENING.md` records the same shape at Layer 3 — ~1000 per-node reads
    per org — taking a reasoning pass past thirty minutes and blocking emission entirely. The
    modifier readers in `context/importance.py` are bulk for the same reason; this is the last
    per-situation read on the composition path.

    Identical in every judgement to the single read: same projection (`_L1_SELECT`), same folding
    (`_l1_from_rows`). A correlation with no qualified signal is ABSENT from the mapping rather
    than present with an empty record — absent is what `gather_l1_signals` returns as `None`, and
    it is the state that keeps the documented fallback reachable.
    """
    ordered = tuple(sorted({str(c) for c in correlation_ids if c}))
    out: dict[str, L1Signals] = {}
    for start in range(0, len(ordered), _READ_CHUNK):
        chunk = list(ordered[start:start + _READ_CHUNK])
        grouped: dict[str, list] = {}
        for row in conn.execute(
                text(_L1_SELECT.format(
                    predicate="m.correlation_id = any(cast(:cids as text[]))")),
                {"o": org_id, "cids": chunk}).mappings().all():
            grouped.setdefault(str(row["correlation_id"]), []).append(row)
        for correlation_id, rows in grouped.items():
            folded = _l1_from_rows(rows)
            if folded is not None:
                out[correlation_id] = folded
    return _attach_conflicts(conn, org_id, _verify_evidence(conn, org_id, out))


# =================================================================================================
# THE ABSENCE PATH. Why these two reads exist.
#
# `awaiting_response` and `first_response_overdue` are the two commonest readings in any inbox —
# 114 of them on the pilot tenant — and not one had ever been published. The publisher held every
# one on VERIFIED_EVIDENCE_REQUIRED, and the obvious diagnosis is wrong: it is not that a silence
# cannot be quoted.
#
# It is that nobody looked. These situations anchor on a synthetic correlation the correlation
# engine deliberately cannot reach (`outreach_situations` module docstring), so
# `gather_l1_signals_bulk` above misses, `l1` is None, and `evidence_verified_spans` is written as
# 0 at the BSO seam. The gate then refuses a claim on the strength of a number that was never
# computed for it, and `_signals_and_evidence` supplies a `reconstructed: True` placeholder that
# carries no quote, so the receipt half fails too. Two failures, one cause, and neither of them is
# "this claim has no evidence".
#
# The claim is "WE WROTE TO THEM AND NOTHING CAME BACK". The first half of that is a message we
# sent: a real event, extracted like any other, carrying real spans that quote real text we typed.
# That is the receipt, it has existed the whole time, and Rule 04 is satisfied on its own terms
# rather than by widening the gate to admit claims without receipts. The gate is right. It was
# starving.
# =================================================================================================

#: The events in which WE wrote to this counterparty. `thread.last_outbound` is written onto the
#: RECIPIENT's own person node on the outbound leg (`context/pipeline.py`), and `graph_source_refs`
#: maps a fact version back to the event that produced it — so "which messages did we send this
#: person" is already answerable and this read invents nothing.
_OUTBOUND_EVENTS_SQL = (
    "select distinct r.event_id as event_id "
    "from graph_facts f "
    "join graph_source_refs r "
    "  on r.fact_version_id = f.fact_version_id and r.org_id = f.org_id "
    "where f.org_id = :o and f.subject_node_id = :n and f.field = 'thread.last_outbound' "
    "order by r.event_id"
)

#: `_L1_SELECT` reaches qualified signals THROUGH `context_correlation_members`, which is exactly
#: why it cannot see an absence anchor. This is the same projection and is folded by the same
#: `_l1_from_rows`, joined on the event instead. Identical in every judgement — the state filter,
#: the max over the live scored subset, the all-state provenance — it just starts from a set of
#: events rather than from a correlation.
#:
#: `in :ev` with an EXPANDING bindparam rather than `= any(cast(:ev as text[]))`, which is what the
#: reads above use: the array cast is Postgres-only, and a query whose correctness can only be
#: demonstrated against production is a query nobody can hold to account. This form runs on both.
_L1_BY_EVENT_SELECT = (
    "select qs.signal_id, qs.state, qs.importance_bp, "
    "qs.importance_version, qs.importance_components, qs.evidence_refs, qs.conflict_ids, "
    "qs.signal_type, qs.coverage_ready "
    "from qualified_signals qs "
    "where qs.org_id = :o and qs.event_id in :ev "
    "order by qs.importance_bp desc, qs.signal_id"
)

#: How many of our own messages may ground one absence. The newest is the one the claim is really
#: about ("we wrote, and since then nothing"); the rest are the follow-ups, which are part of the
#: same story. Bounded so a decade-long thread cannot drag its whole history into one card.
MAX_ABSENCE_RECEIPTS = 5


def outbound_event_ids(conn, org_id: str, anchor_node_id: str,
                       limit: int = MAX_ABSENCE_RECEIPTS) -> tuple[str, ...]:
    """The events in which we wrote TO `anchor_node_id`. Empty when we never have.

    Empty is the honest answer and the important one: a counterparty we have never written to has
    no absence to describe, because nothing was ever awaited. Every one of the pilot's marketing
    senders is in that state.
    """
    if not anchor_node_id:
        return ()
    rows = conn.execute(text(_OUTBOUND_EVENTS_SQL),
                        {"o": org_id, "n": anchor_node_id}).mappings().all()
    return tuple(str(r["event_id"]) for r in rows if r["event_id"])[:limit]


#: WHICH MESSAGE GROUNDS WHICH ABSENCE. Measured on the pilot, not assumed: of the 84 absence
#: situations held there, `awaiting_response` anchors on an `outreach` node that carries only
#: `outreach.*` facts, and `first_response_overdue` anchors on a `thread` node carrying
#: `thread.last_inbound` and no `thread.last_outbound` at all. One direction read for both finds
#: nothing, which is exactly what the first cut of this backfill did.
#:
#: THE INBOUND ENTRY IS NOT A LOOPHOLE, and the distinction is the whole safety argument. A
#: marketing sender only ever produces inbound mail, so admitting inbound as a receipt everywhere
#: would hand every blast a receipt. It is admitted for `first_response_overdue` ALONE, whose
#: claim is literally about a message they sent us and we have not answered — there, their
#: message is not evidence of our interest, it is the thing the claim is about.
#: SITUATION TYPES WHOSE CLAIM IS AN ABSENCE. A card here says something did NOT happen, and
#: `contracts/absence` states the rule these depend on: "not observed" is not "does not exist".
#:
#: Wider than `ABSENCE_RECEIPT_FIELDS` below on purpose. That map answers "which outbound fact is
#: the receipt for this silence", and only three types have one. This answers "does this claim
#: depend on having looked everywhere", which is true of every silence — including the two group
#: readings this branch added, whose subject is several silences at once.
ABSENCE_CLAIMING_TYPES: frozenset[str] = frozenset({
    "awaiting_response", "cohort_outreach_gap", "first_response_overdue",
    "commitment_overdue", "organization_gone_quiet", "campaign_awaiting_reply",
    "condition_in_review",
})

ABSENCE_RECEIPT_FIELDS: Mapping[str, tuple[str, ...]] = {
    "awaiting_response": ("thread.last_outbound",),
    "cohort_outreach_gap": ("thread.last_outbound",),
    "first_response_overdue": ("thread.last_inbound",),
}

#: The same read as `_OUTBOUND_EVENTS_SQL`, with the field set as a parameter and `status` pinned
#: to `active`. The status filter is new and it is a tightening: the pilot's anchors carry 19
#: `superseded` and 3 `historical` versions of the same field, and grounding "nothing has happened
#: since" on a superseded message would date the claim to a message that was itself replaced.
_RECEIPT_EVENTS_SQL = (
    "select distinct r.event_id as event_id "
    "from graph_facts f "
    "join graph_source_refs r "
    "  on r.fact_version_id = f.fact_version_id and r.org_id = f.org_id "
    "where f.org_id = :o and f.subject_node_id = :n and f.field in :fields "
    "  and f.status = 'active' "
    "order by r.event_id"
)

#: ONE HOP, through `concerns`, and no further. An `outreach` node is a claim ABOUT a thread or a
#: person; it holds the waiting arithmetic and the counterparty's name, and the messages live on
#: the node it points at. All 41 of the pilot's `awaiting_response` anchors reach a real qualified
#: signal this way and none reaches one without it.
#:
#: The hop is directional (`from_node_id = :n`) and the edge type is fixed, so this cannot wander
#: the graph: it reads the nodes THIS situation declares itself to be about, which is the same set
#: `gather_subject_nodes` reads for every other purpose.
_RECEIPT_VIA_CONCERNS_SQL = (
    "select distinct r.event_id as event_id "
    "from graph_edges e "
    "join graph_facts f "
    "  on f.org_id = e.org_id and f.subject_node_id = e.to_node_id "
    "join graph_source_refs r "
    "  on r.fact_version_id = f.fact_version_id and r.org_id = f.org_id "
    "where e.org_id = :o and e.from_node_id = :n and e.edge_type = 'concerns' "
    "  and e.valid_to is null and f.field in :fields and f.status = 'active' "
    "order by r.event_id"
)


def absence_receipt_event_ids(conn, org_id: str, anchor_node_id: str, situation_type: str,
                              limit: int = MAX_ABSENCE_RECEIPTS) -> tuple[str, ...]:
    """The messages that ground THIS absence, in the direction its claim actually points.

    Empty is the honest answer and the important one, in three separate ways. A situation type
    with no entry in `ABSENCE_RECEIPT_FIELDS` is not an absence and gets nothing. An anchor whose
    thread carries no message in the claimed direction gets nothing — every marketing sender on
    the pilot is in that state for `awaiting_response`, because we never wrote to them. And an
    anchor that reaches no `concerns` edge and holds no facts of its own gets nothing.

    The anchor is read first and the hop is taken only when it yields nothing, so a node that
    holds its own messages is never traded for a neighbour's.
    """
    fields = ABSENCE_RECEIPT_FIELDS.get((situation_type or "").strip())
    if not anchor_node_id or not fields:
        return ()
    for sql in (_RECEIPT_EVENTS_SQL, _RECEIPT_VIA_CONCERNS_SQL):
        stmt = text(sql).bindparams(bindparam("fields", expanding=True))
        rows = conn.execute(stmt, {"o": org_id, "n": anchor_node_id,
                                   "fields": list(fields)}).mappings().all()
        found = tuple(str(r["event_id"]) for r in rows if r["event_id"])[:limit]
        if found:
            return found
    return ()


def gather_l1_signals_for_events(conn, org_id: str,
                                 event_ids: Sequence[str]) -> L1Signals | None:
    """Layer 1's verdicts for a specific set of EVENTS, folded exactly as the correlation read
    folds them. `None` when those events produced no qualified signal at all — the same honest
    absence `gather_l1_signals` returns, which keeps the pre-activation fallback reachable.
    """
    ids = [str(e) for e in event_ids if e]
    if not ids:
        return None
    stmt = text(_L1_BY_EVENT_SELECT).bindparams(bindparam("ev", expanding=True))
    rows = conn.execute(stmt, {"o": org_id, "ev": ids}).mappings().all()
    folded = _l1_from_rows(rows)
    if folded is None:
        return None
    # The same two enrichment passes the bulk read applies, so an absence receipt is graded and
    # conflict-aware on exactly the terms every other receipt is. `verified` on these spans still
    # means L1.5.1 found the quote in real source text; nothing here can set it.
    keyed = _attach_conflicts(conn, org_id,
                              _verify_evidence(conn, org_id, {"absence": folded}))
    return keyed.get("absence")


def backfill_absence_l1(conn, org_id: str, subjects, l1_by_correlation: dict):
    """Give the situations the correlation read could not reach the receipts they already have.

    ADDITIVE ONLY, and that is the whole safety argument. A correlation that `gather_l1_signals_bulk`
    already answered is never touched, so every situation that publishes today publishes on exactly
    the evidence it publishes on today. This can only ever ADD a bundle where there was `None`, and
    `None` is the state that was producing a permanent hold.

    It also cannot invent one. `absence_receipt_event_ids` returns empty for a situation that is
    not an absence, for an anchor whose thread holds no message in the claimed direction, and for
    an anchor that reaches nothing; `gather_l1_signals_for_events` returns `None` when those events
    carry no qualified signal. So a situation with nothing behind it keeps its `None`, keeps its
    zero, and keeps being held. That is correct: the gate should refuse a claim with no receipt,
    and after this change it still does. What it stops doing is refusing claims whose receipts
    nobody fetched.

    AND IT HAS TO RUN ON THE PUBLISH PATH, which for a long time it did not. This function was
    called from exactly one place — `compose_org_importance`, the IMPORTANCE sweep — while
    `reason/domain_shadow` did its own `gather_l1_signals_bulk` and never backfilled. So on the
    path that actually decides publication, `l1` stayed `None` for every absence situation and
    both hold reasons below fired anyway. Measured on the pilot: 504 held against 28 admitted,
    and 480 of those holds carry `qes_required` AND `verified_evidence_required` — the exact
    pair this function exists to clear.

    ONE HOLD REASON OR TWO. `_preflight` raises `verified_evidence_required` on a missing span AND
    `qes_required` when `importance_source` is not `l1_qualified_signals` — and on the pilot all
    349 held candidates carry both, which reads like two independent defects. It is one: both are
    downstream of `l1` being `None` here, because `importance_base(l1)` returns the
    `l1_qualified_signals` arm only when a bundle arrived. Feeding the bundle clears both.
    """
    def field(subject, name: str):
        """The importance sweep passes dataclass-ish rows; the PUBLISH path passes SQLAlchemy
        `RowMapping`s, which have no attributes for their columns. Reading both is what let this
        function be called from the seam that actually publishes."""
        value = getattr(subject, name, None)
        if value is None and hasattr(subject, "get"):
            value = subject.get(name)
        return value

    for subject in subjects:
        key = field(subject, "correlation_id")
        anchor = field(subject, "anchor_node_id")
        if not key or not anchor or key in l1_by_correlation:
            continue
        events = absence_receipt_event_ids(conn, org_id, str(anchor),
                                           str(field(subject, "situation_type") or ""))
        if not events:
            continue
        folded = gather_l1_signals_for_events(conn, org_id, events)
        if folded is not None:
            l1_by_correlation[key] = folded
    return l1_by_correlation


def gather_subject_nodes(conn, org_id: str,
                         correlation_ids: Sequence[str]) -> dict[str, tuple[str, ...]]:
    """WHICH GRAPH NODES A SITUATION IS ABOUT — the join every L2 modifier hangs on.

    A `derived.trend.*` / `derived.cohort_position.*` / `derived.anomaly.*` /
    `derived.dependency.blocked_count` fact is filed against a `subject_node_id`, and modifiers
    3a-3d may only read the facts about nodes THIS situation is about. This is that set: the nodes
    whose facts were written by the situation's own correlated events.

    IT IS THE SAME JOIN `situations.refresh_situations` ALREADY USES for coverage
    (`fields_by_correlation`), and deliberately so — "what this situation's evidence established,
    wherever it landed". A deal's stage sits on the deal node, whose turn it is sits on a person,
    and a company node holds almost no facts of its own (15 of 18 held literally zero), so a
    modifier read against the anchor alone would be a rule that is always right and never fires.

    WHAT IT IS NOT. It is not the anchor's 1-hop neighbourhood: that is every person the company
    ever mailed, and one declining metric on a shared contact would then raise every situation
    that contact appears in — a raise with no nameable evidence, which is what Rule 11 refuses.
    The caller adds the anchor itself (see `SituationSubject`); this function answers only for the
    evidence.

    `gather_members` is NOT the source here even though it names the counterparties: it returns
    EMAIL ADDRESSES as ids (grouped off `source_events.actor`), and `graph_facts.subject_node_id`
    holds minted `node_*` ids. Passing one where the other is expected reads as an empty modifier
    set on every situation — a silent, total dead rule.
    """
    ordered = tuple(sorted({str(c) for c in correlation_ids if c}))
    out: dict[str, set[str]] = {}
    for start in range(0, len(ordered), _READ_CHUNK):
        chunk = list(ordered[start:start + _READ_CHUNK])
        rows = conn.execute(text(
            "select distinct m.correlation_id as correlation_id, f.subject_node_id as node_id "
            "from context_correlation_members m "
            "join graph_facts f on f.org_id = m.org_id and f.created_by_event_id = m.event_id "
            "where m.org_id = :o and m.correlation_id = any(cast(:cids as text[])) "
            "  and f.subject_node_id is not null"),
            {"o": org_id, "cids": chunk}).mappings().all()
        for row in rows:
            out.setdefault(str(row["correlation_id"]), set()).add(str(row["node_id"]))
    return {k: tuple(sorted(v)) for k, v in out.items()}



#: Above this many distinct external counterparties, one anchor is not describing one
#: relationship — it is doing multi-relationship duty. Two is the honest floor: a genuine
#: 1:1 relationship has exactly one, and a warm intro (one sender, one new contact) has two
#: without being a chimera. Three or more distinct external parties correlated onto a single
#: anchor is the Boardy shape — a connector's own address absorbing everyone it introduced.
SPLIT_REQUIRED_THRESHOLD = 2


def gather_visibility(conn, org_id: str, correlation_id: str | None) -> Visibility:
    """The situation's audience = the NARROWEST merge of its evidence's audiences.

    Both builders stamped `Visibility(scope="org")` as a literal. Harmless while every event was
    org-scoped — and L1-04 ended that: communication events now land `participants`-scoped with
    real principals, so a situation built from a two-person thread claiming org visibility is
    exactly the widening `contracts/visibility.narrowest` exists to prevent. The merge can only
    narrow; a situation with no member evidence stays org (there is nothing narrower to honour).
    """
    if not correlation_id:
        return Visibility(scope="org", derived_from="l2:situation:no_members")
    rows = conn.execute(text(
        "select distinct se.visibility_scope, se.visibility_principals "
        "from context_correlation_members m "
        "join source_events se on se.event_id = m.event_id and se.org_id = m.org_id "
        "where m.org_id = :o and m.correlation_id = :c and se.visibility_scope is not null"),
        {"o": org_id, "c": correlation_id}).fetchall()
    if not rows:
        return Visibility(scope="org", derived_from="l2:situation:pre_visibility_capture")
    merged = narrowest(*(
        Visibility(scope=r.visibility_scope, principals=list(r.visibility_principals or ()),
                   derived_from="source_event")
        for r in rows))
    return Visibility(scope=merged.scope, principals=merged.principals,
                      derived_from="l2:narrowest_of_members",
                      excluded_subjects=merged.excluded_subjects)


def gather_members(conn, org_id: str, correlation_id: str | None) -> tuple[Mapping[str, Any], ...]:
    """The DISTINCT real counterparties actually correlated onto this situation.

    `build_business_situation` used to build `entities` as a one-element tuple from
    `anchor_node_id` alone — so a situation anchored on `boardy.ai` with 68 correlated events
    reported as being about ONE entity, the connector bot, rather than the dozens of real people
    it introduced. Every later layer inherited that: L3 reasoned about "the Boardy relationship"
    as a unit, and a rejected pitch to one introduced founder read as evidence about all of them.

    This is "real member evidence" in the sense the gap asks for: derived from the actor on each
    correlated event, not synthesised or defaulted. Grouped by email so the same person across
    several events is one entity, not one per message.
    """
    if not correlation_id:
        return ()
    rows = conn.execute(text(
        "select se.actor->>'email' as email, se.actor->>'type' as actor_type, "
        "min(se.occurred_at) as first_seen, count(*) as n "
        "from context_correlation_members m "
        "join source_events se on se.event_id = m.event_id and se.org_id = m.org_id "
        "where m.org_id = :o and m.correlation_id = :c and se.actor->>'email' is not null "
        "group by 1, 2 order by n desc, email"),
        {"o": org_id, "c": correlation_id}).mappings().all()
    return tuple({
        "id": str(r["email"]),
        "type": str(r["actor_type"] or "unknown"),
        "name": str(r["email"]),
        "event_count": int(r["n"]),
    } for r in rows)


def gather_brain_subject_keys(conn, org_id: str, situation: Mapping[str, Any],
                              members: tuple[Mapping[str, Any], ...] = ()) -> tuple[str, ...]:
    """WHAT THIS SITUATION IS ABOUT, in `contracts/brain_address`'s vocabulary.

    **THE READER THIS WRITES FOR HAS BEEN WAITING SINCE IT SHIPPED.**
    `packs/compiler/runtime_brains._selectors` reads `situation.brain_subject_keys`;
    `contracts/domain_expertise.py:506` reads it off `metadata["brain_subject_keys"]`; and
    `grep -rn brain_subject_keys genios_engine/` returned those two readers and NO WRITER. The one
    selector meant to bind a live situation to the tenant's own learned knowledge was dead metadata,
    which is most of why `packages_with_a_brain_slice` measured 0 on a tenant holding eleven
    published brain entries and a live lease.

    **WHY THE NODE IDS ARE THE WHOLE POINT.** `gather_members` groups correlated counterparties by
    `actor->>'email'`, so a situation's entity ids are EMAIL ADDRESSES. A Behaviour pattern is
    published as `behavior:<metric>:<node_id>` because that is what Layer 2's trend facts are keyed
    by. Those two identities are the same people and have never been the same string, so the match
    could not fire. This resolves the emails to their graph nodes through `graph_nodes.canonical_key`
    — one indexed query per situation — and emits BOTH identities as their own token kinds, so
    neither has to pretend to be the other and knowledge published under either binds.

    **ONE QUERY, AND IT MAY RETURN NOTHING.** A tenant whose graph has no node for a correspondent
    (a first-contact address, a connector that has not been reconciled) yields no `node:` token for
    them, and the situation still carries every other dimension. The absence is a narrower address,
    never an error: a situation that failed to resolve one member must not lose the policy that
    applies to its whole organization.
    """
    from genios_engine.contracts.brain_address import token

    tokens: set[str] = set()

    def add(kind: str, value: Any) -> None:
        if not value:
            return
        try:
            tokens.add(token(kind, value))
        except ValueError:
            # A value the vocabulary refuses. Dropped rather than raised, for the reason above:
            # one malformed identity must not cost this situation every other binding it has.
            return

    add("org", org_id)
    add("situation", situation.get("situation_id"))
    add("domain", situation.get("domain"))
    anchor = situation.get("anchor_node_id")
    add("node", anchor)
    anchor_type = str(situation.get("anchor_type") or "").lower()
    if anchor and anchor_type in {"person", "external_contact", "user"}:
        add("person", anchor)
    elif anchor and anchor_type in {"company", "organization", "account"}:
        add("company", anchor)

    emails = sorted({str(m.get("id")).lower() for m in members
                     if m.get("id") and "@" in str(m.get("id"))})
    for email in emails:
        add("email", email)
    if emails and conn is not None:
        try:
            rows = conn.execute(text(
                "select node_id, node_type from graph_nodes "
                "where org_id = :o and valid_to is null "
                "and lower(canonical_key) = any(cast(:keys as text[]))"),
                {"o": org_id, "keys": emails}).mappings().all()
        except Exception:      # noqa: BLE001 — an address is a refinement; the situation is the product
            _log.exception("could not resolve member node ids for org=%s", org_id)
            rows = []
        for row in rows:
            add("node", row["node_id"])
            kind = str(row["node_type"] or "").lower()
            if kind in {"person", "external_contact", "user"}:
                add("person", row["node_id"])
            elif kind in {"company", "organization", "account"}:
                add("company", row["node_id"])
    return tuple(sorted(tokens))


def _distinct_external_domains(members: tuple[Mapping[str, Any], ...]) -> set[str]:
    domains = set()
    for m in members:
        if m.get("type") != "external_contact":
            continue
        email = str(m.get("id") or "")
        if "@" in email:
            domains.add(email.rsplit("@", 1)[1].lower())
    return domains


@dataclass(frozen=True, slots=True)
class PatternFire:
    """One `pattern_fires` row — L2.6's answer to *"do these five things hold together?"*.

    `activated` is the field everything turns on and it is the reason this record exists rather
    than a `pattern_id: str | None`. A shadow fire and a live one are the same match and completely
    different facts about the product: `context/patterns/store.py` states the migration rule in its
    own docstring — *"keep anchor-based detection running alongside; compare fire sets on a pilot
    for 7 days before switching; do not delete the anchor path in this wave"* — so a fire the
    tenant has not activated ANNOTATES a situation and may not rename it.
    """

    pattern_id: str
    pattern_version: int
    situation_type: str
    match_strength_bp: int
    activated: bool
    #: The per-condition receipts, verbatim from the match. Doc 09's H8 row —
    #: *"a pattern-matched situation with per-condition evidence >= 1"* — is a count over this.
    #: *"It fired because of these five facts"* is unreconstructible once the graph moves on.
    matched_conditions: tuple[Mapping[str, Any], ...] = ()


#: The newest, strongest fire per anchor. `distinct on` with an explicit order rather than a
#: `max()` join: two patterns can match one anchor, and which one names the situation must be
#: decided by a stated rule (activated first, then strength, then recency, then id) instead of by
#: whichever row Postgres returned first — an order that is stable between two reads of an
#: unchanged database is what stops a BSO's content address flipping on a sweep that changed
#: nothing. `evaluated_at` is READ here and never published: see `_pattern_metadata`.
_PATTERN_SELECT = (
    "select distinct on (anchor_node_id) anchor_node_id, pattern_id, pattern_version, "
    "       situation_type, match_strength_bp, activated, evidence "
    "from pattern_fires where org_id = :o and anchor_node_id = any(cast(:ids as text[])) "
    "order by anchor_node_id, activated desc, match_strength_bp desc, evaluated_at desc, "
    "         pattern_id")


def gather_pattern_fires(conn, org_id: str,
                         anchor_node_ids: Sequence[str]) -> dict[str, PatternFire]:
    """Which declared pattern matched each anchor, for a whole sweep, in one read per chunk.

    ABSENT rather than empty for an anchor nothing matched — the same discipline
    `gather_l1_signals_bulk` keeps — because "no pattern matched this" and "we did not look" are
    different facts and only one of them is worth writing on a card.
    """
    ordered = tuple(sorted({str(a) for a in anchor_node_ids if a}))
    out: dict[str, PatternFire] = {}
    for start in range(0, len(ordered), _READ_CHUNK):
        chunk = list(ordered[start:start + _READ_CHUNK])
        for row in conn.execute(text(_PATTERN_SELECT),
                                {"o": org_id, "ids": chunk}).mappings().all():
            conditions = _json(row["evidence"], [])
            out[str(row["anchor_node_id"])] = PatternFire(
                pattern_id=str(row["pattern_id"]),
                pattern_version=int(row["pattern_version"] or 0),
                situation_type=str(row["situation_type"] or ""),
                match_strength_bp=int(row["match_strength_bp"] or 0),
                activated=bool(row["activated"]),
                matched_conditions=tuple(dict(c) for c in conditions
                                         if isinstance(c, Mapping)))
    return out


def situation_confidence_vector(situation: Mapping[str, Any]) -> SituationConfidenceVector:
    """The SIX axes off a `context_situations` row, in basis points.

    **Never collapsed to a scalar** (doc 09, must-not-regress row 3). `confidence_bp` on the BSO is
    the minimum of the axes that apply, and a reader who needs to know WHICH dimension is weak —
    "we cannot identify who this is about" is a different problem from "the sources disagree" —
    has to be able to ask. Until this function the BSO carried only the minimum, so nobody could.

    BASIS POINTS, resolving A-7 AT THIS SEAM AND ONLY HERE. `situations.py` scores the axes on a
    0..100 percent scale and doc 08's V-8 says integer basis points; the plan (`L2_MISSING_UNIT_
    SPECS.md` §3 A-7) leaves the choice open and asks that neither be pre-empted. The BSO's own
    `confidence_bp` has been `_bp(confidence_overall)` since this module shipped, so a vector in
    percent beside the scalar it explains would put two scales on one object — the one confusion
    the seam cannot afford. `situations.py` is untouched, so doc 09's must-not-regress item 3 is
    unaffected and the storage-side choice is still open.

    Two sentinels, kept apart on purpose. A NULL column is a sweep that predates the axis
    (`confidence_analytic` arrived in migration 0099); `situations.COVERAGE_UNKNOWN` is an axis
    that ran and found nothing to measure. Both publish as `AXIS_UNKNOWN_BP`, which is not a score
    and must never be read as one — a 0 would rank an unassessed situation below every assessed
    one, the same error `UNSCORED_VERSION` prevents one field up.
    """
    def axis(column: str) -> int:
        value = situation.get(column)
        if value is None:
            return AXIS_UNKNOWN_BP
        try:
            score = int(value)
        except (TypeError, ValueError):              # pragma: no cover - a column from elsewhere
            return AXIS_UNKNOWN_BP
        return AXIS_UNKNOWN_BP if score == COVERAGE_UNKNOWN else _bp(score)

    return SituationConfidenceVector(
        evidence=axis("confidence_evidence"), freshness=axis("confidence_freshness"),
        consistency=axis("confidence_consistency"), identity=axis("confidence_identity"),
        coverage=axis("coverage"), analytic=axis("confidence_analytic"))


#: Which stored modifier term supplies which analytic list in the BSO's metadata. Three of the six
#: modifiers ARE the analytic stratum (L2.4), and their receipts are the only record of the
#: comparison that moved the number — `ComposedImportance.leaned_on` can rebuild the full
#: qualifying set but only from `ModifierInputs`, which exists for the length of the composing
#: sweep and is gone by the time anything publishes.
_ANALYTIC_TERMS = (("trends", "trend"), ("cohort_positions", "cohort_position"),
                   ("anomalies", "anomaly"))


def analytic_context(composed: ComposedImportance | None) -> dict[str, list]:
    """L2.7.8's `metadata` row: *"+ conflicts, trends, cohort_positions"*.

    Read off the STORED composition, not recomputed: `refresh_situation_importance` already ran the
    analytic stratum once for the whole org and wrote the terms it leaned on, and re-deriving them
    here would be four more queries per situation for facts that are on the row being read — the
    shape `PERFORMANCE_HARDENING.md` records taking a pass past thirty minutes.

    A modifier that did NOT fire contributes an empty list, and that is a claim worth making: it
    says this situation's importance leaned on no comparison of that kind. What it deliberately
    does not say is that no such comparison exists — a trend that was found and then judged too
    thin to act on is `fired=False` with its reason on the stored term, where a reader who wants it
    can read it.
    """
    out: dict[str, list] = {key: [] for key, _ in _ANALYTIC_TERMS}
    if composed is None:
        return out
    terms = {term.name.value: term for term in composed.modifiers}
    for key, name in _ANALYTIC_TERMS:
        term = terms.get(name)
        if term is not None and term.fired and term.evidence:
            out[key] = [_no_floats(dict(term.evidence))]
    return out


#: `metadata['type_source']` — WHICH detection path named this situation. The pilot comparison is
#: the whole reason it exists: doc 06 requires seven days of fire-set comparison before the pattern
#: path may replace the anchor path, and a comparison needs to be able to say, per situation, which
#: one spoke. Two values, and no third: a situation is named by a pattern or by its anchor.
TYPE_SOURCE_PATTERN = "pattern"
TYPE_SOURCE_ANCHOR = "anchor"


def _type_source(pattern: PatternFire | None) -> str:
    return (TYPE_SOURCE_PATTERN if pattern is not None and pattern.activated
            and pattern.situation_type else TYPE_SOURCE_ANCHOR)


def _situation_type(situation: Mapping[str, Any], pattern: PatternFire | None) -> str:
    """What this situation is CALLED — L2.7.8's `type` row, with the migration rule enforced.

    Three inputs and a stated precedence, because this string is the routing identity every layer
    above uses (`packs/compiler` binds capabilities by it, `domain_spec` declares expected fields
    by it) and a type that moved for the wrong reason routes a real situation into nothing:

    1. an ACTIVATED pattern names it. That is the whole point of the registry — no anchor type can
       express "renewal AND auto-renew AND high value AND a short cancellation window AND a
       migration discussion AND no scheduled decision" — and activation is the tenant's own
       statement that the pattern has earned it;
    2. a SHADOW fire does not. `context/patterns/store.py` states the rule this obeys: *"compare
       fire sets on a pilot for 7 days before switching. Do not delete the anchor path in this
       wave."* The fire still travels, in metadata, which is what makes the comparison possible;
    3. otherwise the anchor-derived type stands, unchanged.

    **The QES `signal_type` deliberately does not decide this**, though doc 07's table pairs it
    with the pattern match. Layer 1 names what kind of SIGNAL an email carried
    (`commitment_made`, `decision_pending`); this names what kind of THING the situation is, and
    the two vocabularies are not the same one. Overwriting the second with the first would route
    every situation to a capability set that does not exist, which is a silent total route miss —
    the failure mode `tests/test_situation_bso.py` already guards by asserting the type against the
    registry rather than a literal. `metadata['signal_types']` carries Layer 1's answer beside
    Layer 2's so the two can be compared on the pilot instead of one being assumed.
    """
    if pattern is not None and pattern.activated and pattern.situation_type:
        return pattern.situation_type
    return str(situation["situation_type"])


#: How many per-condition receipts a BSO carries from one match. A pattern has a handful of
#: conditions by construction; the cap is a guard against a registry entry nobody bounded, not an
#: expected truncation.
MAX_MATCHED_CONDITIONS = 20


def _pattern_metadata(pattern: PatternFire | None) -> dict[str, Any]:
    """The fire, in metadata, whether or not it was allowed to name the situation.

    **Every key is present even with no fire**, set to None/False/[]. An absent key and a key
    saying "nothing matched" read identically to a consumer and mean opposite things, and this one
    is going into a content-addressed artifact: a key that appears only sometimes makes two
    situations with the same facts hash differently depending on which of them a pattern happened
    to touch.

    `evaluated_at` and `fire_id` are NOT here. They move on every sweep for a match that did not
    change, and this mapping is hashed into the expertise package's content address — the
    mechanism that put 995 MB on one tenant's database and took the project read-only.
    """
    if pattern is None:
        return {"pattern_id": None, "pattern_version": None, "pattern_activated": False,
                "pattern_match_strength_bp": None, "matched_conditions": []}
    return {
        "pattern_id": pattern.pattern_id,
        "pattern_version": pattern.pattern_version,
        "pattern_activated": pattern.activated,
        "pattern_match_strength_bp": pattern.match_strength_bp,
        # THE RECEIPT, and H8's third bold row: "a pattern-matched situation with per-condition
        # evidence". Doc 08: "matched_conditions is the one to insist on — *this fired because of
        # these five facts* is what makes a situation explainable at L3 and defensible on a card.
        # Without it, a pattern match is an assertion."
        "matched_conditions": [_no_floats(dict(c))
                               for c in pattern.matched_conditions[:MAX_MATCHED_CONDITIONS]],
    }


def _log_importance_fallback(situation: Mapping[str, Any], base: ImportanceBase,
                             composed: ComposedImportance | None,
                             l1: L1Signals | None) -> None:
    """The "AND LOGGED" half of doc 07's acceptance row, and the only reason it is a log line.

    *"importance_bp is not 5000 unless the fallback path fired AND logged."* The number alone
    cannot be audited — a composed 5000 and a defaulted one are the same integer — and
    `metadata['importance_fallback']` answers it for anyone holding the object. This answers it for
    the operator who is not: a tenant whose every situation prints this line has no Layer 1 supply
    reaching Layer 2, which is a deployment fact, is invisible in the distribution (a flat one
    looks like a flat business), and was the state that persisted long enough for 193 of 223
    signals to share one score.

    ONE LINE PER FALLBACK PUBLISH, at INFO, naming which of the three arms fired. A pre-activation
    tenant therefore prints one per situation per sweep, and that volume is the signal rather than
    noise to be suppressed: the day Layer 1 starts scoring, the lines stop.
    """
    if base.source == "l1_qualified_signals":
        return
    _log.info(
        "situation %s publishes on the importance FALLBACK (%s): base=%d, published=%d, "
        "live signals=%d of which scored=%d. Layer 1 published no live scored signal for this "
        "correlation, so DEFAULT_IMPORTANCE_BP is the base rather than a measurement.",
        situation.get("situation_id"), base.source, base.importance_bp,
        composed.importance_bp if composed is not None else base.importance_bp,
        l1.signal_count if l1 is not None else 0, l1.scored_count if l1 is not None else 0)


def build_business_situation(
    *, org_id: str, situation: Mapping[str, Any],
    signal_ids: list[str], evidence: list[Mapping[str, Any]], trace_id: str,
    members: tuple[Mapping[str, Any], ...] = (),
    visibility: Visibility | None = None,
    l1: L1Signals | None = None,
    composed: ComposedImportance | None = None,
    pattern: PatternFire | None = None,
    brain_subject_keys: tuple[str, ...] = (),
    contradicted_by: tuple[str, ...] = (),
) -> BusinessSituationObject:
    """``members`` — real correlated counterparties from ``gather_members`` — is a separate,
    explicit parameter rather than a key smuggled onto ``situation``. Callers pass a raw DB row
    for ``situation`` in every existing call site; making a new field's absence silently produce
    the OLD anchor-only behaviour is safer than requiring every caller to know a magic key.

    ``l1`` — ``gather_l1_signals``' answer — is optional for the same reason and reads the same
    way: absent, this builds exactly the BSO it built before `qualified_signals` existed, which
    is what keeps a pre-activation tenant working. Present, Layer 1's own verdict WINS over every
    default in this function: its score, its receipts and its signal ids, because re-deriving
    what Layer 1 already decided is how two layers end up disagreeing about one situation.

    ``composed`` — BLG-18 steps 2..6, as `compose_org_importance` ran them and
    `refresh_situations` STORED them — is optional on the same argument once more, and is a parsed
    `ComposedImportance` rather than a raw row so the number and the arithmetic that produced it
    cannot arrive separately. Absent, the BSO carries the base alone, which is exactly what this
    function published before the composer existed. Present, `importance_bp` is the COMPOSED
    number and `metadata['importance_components']` is the whole term-by-term record — the row H5
    measures at 100%, readable without recomputing anything.

    ``pattern`` — L2.6's fire for this anchor, if one matched — is optional on the same argument a
    third time, and is the ONLY input that may change what this situation is CALLED. See
    `_situation_type`: an activated pattern renames it, a shadow fire annotates it, and no fire at
    all leaves the anchor-derived type exactly as it was."""
    anchor = situation.get("anchor_node_id")
    if members:
        # Real distinct counterparties, not the anchor alone. Capped like every other list this
        # module emits — a BSO is a summary a human or an LLM reads, not the correlation table.
        entities = tuple(dict(m) for m in sorted(
            members, key=lambda m: -int(m.get("event_count", 0)))[:20])
    elif anchor:
        # No correlation membership to draw from (a fresh or synthetic situation) — the anchor
        # is still the only entity we can honestly name, same as before this fix.
        entities = ({
            "id": str(anchor),
            "type": str(situation.get("anchor_type") or "unknown"),
            "name": str(situation.get("anchor_name") or anchor),
        },)
    else:
        entities = ()
    split_required = len(_distinct_external_domains(members)) > SPLIT_REQUIRED_THRESHOLD
    timeline: tuple[Mapping[str, Any], ...] = ()
    first_seen, last_seen = situation.get("first_seen_at"), situation.get("last_seen_at")
    if first_seen or last_seen:
        timeline = ({"first_seen_at": _iso(first_seen), "last_seen_at": _iso(last_seen)},)
    domain = situation.get("domain")
    # STEP 1 — THE BASE. Layer 1's score if Layer 1 published one; the documented fallback only
    # when it did not. `importance_source` travels beside it so a package can never be read as
    # scored when it was defaulted — the state the constant made indistinguishable for 193 of 223
    # signals. The four-way branch lives in `importance_base` so this builder and the sweep's
    # composer cannot disagree about which of the four fired.
    base = importance_base(l1)
    importance_bp, importance_source = base.importance_bp, base.source

    # STEPS 2-6 — corroboration, the six L2-only modifiers, the cap, the coverage penalty, the
    # clamp. NOT COMPUTED HERE. `compose_org_importance` ran them once for the whole sweep and
    # `refresh_situations` stored the answer on `context_situations`; the caller reads that row
    # back and hands it over. Recomposing at this seam would need six more queries per situation
    # and would let the number a card shows drift from the number the gate measures.
    if composed is not None:
        importance_bp = composed.importance_bp
    if l1 is not None and l1.signal_ids:
        # The REAL qualified signal ids. `gather_evidence_and_signals` returns event ids under
        # this name because, before `qualified_signals`, no signal id existed to return.
        signal_ids = list(l1.signal_ids)
    if l1 is not None and l1.evidence:
        # L2.7.8 — the evidence upgrade, at the seam it publishes through. `l1.evidence` is no
        # longer a list of event references: `_graded_evidence` has run ALG-08 over every stored
        # span and put the ones that RESOLVE first, so what leads here is the sentence itself,
        # at offsets that point at it. The correlation's graph refs follow as context, and the
        # synthetic `reconstructed` receipt is dropped — it exists only so the contract's
        # non-empty rule holds when there is nothing real to show, and now there is.
        evidence = [*l1.evidence,
                    *(e for e in evidence if not e.get("reconstructed"))][:MAX_EVIDENCE]
    _log_importance_fallback(situation, base, composed, l1)
    confidence_vector = situation_confidence_vector(situation)
    return BusinessSituationObject(
        org_id=org_id,
        trace_id=trace_id,
        visibility=visibility or Visibility(scope="org", derived_from="l2:situation"),
        id=str(situation["situation_id"]),
        signal_ids=tuple(signal_ids),
        type=_situation_type(situation, pattern),
        confidence_bp=_bp(situation.get("confidence_overall")),
        importance_bp=importance_bp,
        evidence=tuple(_no_floats(dict(e)) for e in evidence),
        entities=entities,
        timeline=timeline,
        state=str(situation.get("status") or "active"),
        metadata={
            "domain_ids": [str(domain)] if domain else [],
            # THE BRAIN ADDRESS. `gather_brain_subject_keys`' answer, carried on the one metadata
            # key `packs/compiler/runtime_brains` has always read and nothing has ever written.
            # An empty tuple is the pre-writer behaviour exactly: the compiler then binds on
            # capability, object and situation alone, which is what it did before this existed.
            #
            # It IS part of `to_semantic_dict`, so a situation that gains an address mints a new
            # expertise package once. That is correct — a package compiled with the tenant's policy
            # in it is not the package compiled without it — and it happens once per situation, not
            # per sweep, because the address is derived from the graph and not from a clock.
            "brain_subject_keys": list(brain_subject_keys),
            "coverage_bp": _bp(situation.get("coverage")),
            "importance_source": importance_source,
            # THE FALLBACK, DECLARED. Doc 07's acceptance row reads "importance_bp is not 5000
            # unless the fallback path fired AND logged", and a reader cannot check that from the
            # number: a composed 5000 and a defaulted one are the same integer. This says which,
            # `importance_source` says which of the three fallback arms, and
            # `_log_importance_fallback` is the "and logged".
            "importance_fallback": base.source != "l1_qualified_signals",
            # The explanation travels with the number, on `qualified_signals`' own argument:
            # "why is this an 8100" must be answerable from data, and it must stay answerable
            # after ALG-17's weights move.
            #
            # WHICH VERSION, AND WHY IT SWITCHES. A version field describes THE NUMBER STORED
            # BESIDE IT. With no composition the stored number is Layer 1's, so the version is
            # ALG-17's; with one, the stored number is the composer's and the version must be the
            # composer's or a replay would re-derive 7400 with the wrong weights. Layer 1's own
            # version is not lost — `importance_components['base_version']` carries it, next to
            # the base it describes.
            "importance_version": (
                composed.version if composed is not None
                else (l1.importance_version if l1 is not None else None)),
            # STEP 6, the stored components. The composer's record SUPERSEDES Layer 1's here
            # rather than sitting beside it: the record already points at the base signal
            # (`base_signal_id`, `base_version`, `base_bp`), and carrying a second components map
            # for a number this object no longer publishes is how a reader ends up explaining
            # 5000 while the card shows 7400. Layer 1's own components stay on the
            # `qualified_signals` row the pointer names — a POINTER, not a copy, for the reason
            # `conflict_ids` is one.
            #
            # `as_record()` is clock-free by construction, so this key cannot re-mint the
            # expertise package's content address on a sweep where nothing changed; Layer 1's
            # components need `_UNSTABLE_COMPONENT` stripped for exactly that reason.
            "importance_components": (
                composed.as_record() if composed is not None
                else ({k: v for k, v in l1.components.items() if k != _UNSTABLE_COMPONENT}
                      if l1 is not None else {})),
            # THE PROVENANCE COUNTS, never the live ones. `l1.signal_count` / `l1.scored_count`
            # are the `state='active'` reading at the instant the sweep looked, and ALG-19 moves
            # that on every sync — putting either here would re-mint this situation's expertise
            # package every time a signal aged out, which is the 995 MB read-only incident's
            # mechanism with a new input. These two count the whole set the situation rests on,
            # so they move only when Layer 1 publishes something genuinely new.
            "l1_signal_count": (len(l1.signal_ids) if l1 is not None else 0),
            "l1_scored_count": (len(l1.scored_signal_ids) if l1 is not None else 0),
            # The disagreements these signals took part in, POINTED at rather than copied — the
            # same discipline `qualified_signals.conflict_ids` keeps one layer down. A situation
            # built on a contradicted claim must not reach Layer 3 looking settled.
            "conflict_ids": list(l1.conflict_ids) if l1 is not None else [],
            # THE SAME DISCIPLINE ONE LAYER UP. `conflict_ids` above points at Layer 1's
            # incompatible FACTS; this points at another SITUATION that claims the opposite of
            # this one about the same subject. `context/correlation_domain.py` finds them against
            # a declared list of impossibilities and refuses to delete anything, so the decision
            # lands where `conflict_ids`' does — `situation_publisher._preflight`, which holds.
            #
            # Measured on the pilot: three counterparties carried `admin:awaiting_response` (they
            # owe us a reply) and `support:first_response_overdue` (we never answered them) at
            # once, and both cards would have gone out. Empty is the ordinary case and is exactly
            # the behaviour this pass had before the correlator existed.
            "contradicted_by": list(contradicted_by),
            # L2.5.1's confidence VECTOR, carried whole rather than as the minimum alone. The
            # group gate's second row ("confidence vector axes present — all 6") is a count over
            # this key; `confidence_vector_complete` is that count already taken, so a gate does
            # not have to know the sentinel to read it.
            "confidence_vector": confidence_vector.as_record(),
            "confidence_vector_complete": confidence_vector.complete,
            # THE EVIDENCE MEASUREMENT, stored beside the evidence. "BSOs with a verified evidence
            # span — 100%" is a count over `verified_span_count`, and a BSO that carries none says
            # so here rather than being indistinguishable from one nobody measured.
            "evidence_spans": (l1.span_count if l1 is not None else 0),
            "evidence_verified_spans": (l1.verified_span_count if l1 is not None else 0),
            # Layer 1's own answer to "what kind of thing is this", which Layer 2 had never read.
            # It does NOT set `type` (see `_situation_type`) — it is what a reader compares the
            # anchor-derived type AGAINST while the two detection paths run side by side.
            "signal_types": (list(l1.signal_types) if l1 is not None else []),
            # The disagreements, as RECORDS. `conflict_ids` above still points; this says what was
            # contested and how Layer 1 resolved it, because Layer 3 may not read past Layer 2 to
            # find out and a contested claim that arrives looking settled is a card built on one.
            "conflicts": [_no_floats(dict(c)) for c in
                          (l1.conflicts[:MAX_CONFLICTS] if l1 is not None else ())],
            # The comparisons the importance leaned on, from the stored composition.
            **analytic_context(composed),
            # L2.6's fire for this anchor, whether or not it was allowed to name the situation.
            **_pattern_metadata(pattern),
            # WHICH path named it. Doc 06 requires the two detection paths to run alongside for a
            # seven-day pilot comparison, and a comparison of fire SETS needs a per-situation
            # answer to "who said so" — otherwise the two paths' agreement can only be counted in
            # aggregate, where a pattern naming the wrong thing and the anchor naming the right
            # thing cancel out.
            "type_source": _type_source(pattern),
            # X6's lifecycle, carried through the publish. `state` above is the status verbatim —
            # `partial` publishes as `partial`, never rounded to `active` or to `resolved` — and
            # these two say who closed it and whether the closure was total. A partially-resolved
            # situation read as fully open is a nag about work that is mostly done; read as fully
            # closed it is work silently dropped.
            "resolved_by": (str(situation["resolved_by"])
                            if situation.get("resolved_by") else None),
            "partially_resolved": str(situation.get("status") or "") == "partial",
            # Layer 1's coverage verdict, carried rather than re-derived. Tri-state in, tri-state
            # out: `None` omits no key but says "not assessed", which is a different fact from
            # "assessed and not ready" — the same discipline `build_context_slice` keeps for the
            # slice's `observation_licensed`.
            "coverage_ready": (l1.coverage_ready if l1 is not None else None),
            # A8 / BS-03 · AN EMPTY SEARCH IS NOT PROOF OF NONEXISTENCE, and this is the writer
            # that hold reason never had.
            #
            # `situation_publisher._preflight` reads `requires_complete_coverage` and NOTHING in
            # genios_engine ever set it, so `SOURCE_COVERAGE_INSUFFICIENT` could not fire on any
            # tenant, ever — measured: zero, against 480 `qes_required` and 24 `conflict_open`.
            # The only test that exercised it set the key by hand.
            #
            # ONLY A SITUATION THAT CLAIMS AN ABSENCE, because only an absence claim depends on
            # having looked everywhere. "They have not replied" is a statement about what is NOT
            # in a source, and it is worth nothing if the source was not covered. A situation
            # that reports something PRESENT is unaffected by a gap elsewhere.
            #
            # AND THE HOLD ITSELF IS GATED ON `coverage_ready is False`, not on "not True" —
            # `_preflight` compares against `is not True` and the tri-state is what makes that
            # safe. `False` means Layer 1 ASSESSED coverage and found it incomplete: a real
            # reason to refuse an absence claim. `None` means nobody assessed it, which is an
            # absence of information about coverage and must not masquerade as bad news — the
            # same discipline `freshness_score` keeps for an undated row. On the pilot that is
            # the difference between holding 55 and holding 274.
            "requires_complete_coverage": (
                str(situation.get("situation_type") or "") in ABSENCE_CLAIMING_TYPES
                and (l1.coverage_ready if l1 is not None else None) is False),
            "shadow": True,
            # One anchor correlating more than SPLIT_REQUIRED_THRESHOLD distinct external
            # counterparties is not describing one relationship. Surfaced rather than silently
            # reasoned over as a unit — a reviewer (or, later, an L2 re-correlation pass) decides
            # whether and how to split it; this module only refuses to hide that the question
            # exists.
            "split_required": split_required,
            "distinct_counterparty_count": len(entities),
        },
    )



# =================================================================================================
# BLG-18 STEPS 2-6 — THE COMPOSITION, FOR A WHOLE SWEEP
# =================================================================================================
#
# WHERE THIS RUNS AND WHY IT IS NOT IN THE BSO BUILDER. `build_business_situation` is called once
# per situation on the Layer 3 seam, and it is pure. The composition needs five bulk reads, so
# doing it there would be five queries x every situation — the shape
# `docs/plans/PERFORMANCE_HARDENING.md` records taking a Layer 3 pass past thirty minutes and
# blocking emission. It runs instead where the situation itself is written
# (`situations.refresh_situations`), once per org, and the answer is STORED. Everything downstream
# — the BSO, the gate script, an operator asking "why is this a 7400" — READS the row.


def importance_base(l1: L1Signals | None) -> ImportanceBase:
    """STEP 1, THE FOUR-WAY BRANCH, in one place. **Nothing here is new** — this is exactly the
    branch `build_business_situation` has run since the `qualified_signals` seam landed, lifted out
    so the builder and the sweep's composer cannot disagree about which of the four fired.

    `DEFAULT_IMPORTANCE_BP` is REACHABLE from three of the four arms and that is correct: a
    situation whose events published no live score has no score to carry, and a neutral midpoint
    neither inflates nor suppresses it. What the constant may no longer be is the answer for a
    situation Layer 1 DID score, which is what the first arm is.
    """
    if l1 is not None and l1.importance_bp is not None:
        return ImportanceBase(importance_bp=l1.importance_bp, source="l1_qualified_signals",
                              signal_id=(l1.scored_signal_ids[0] if l1.scored_signal_ids
                                         else None),
                              version=l1.importance_version)
    if l1 is not None and l1.signal_count:
        return ImportanceBase(importance_bp=DEFAULT_IMPORTANCE_BP, source="l1_unscored",
                              version=l1.importance_version)
    if l1 is not None:
        # Signals exist, and ALG-19 has retired every one of them. Distinct from `l1_unscored`
        # (live signals the floor could not measure) because they are different facts: one says
        # "nobody scored this", the other says "this situation has nothing live left in it", and
        # a reader deciding whether to trust the neutral default needs to know which.
        return ImportanceBase(importance_bp=DEFAULT_IMPORTANCE_BP, source="l1_all_retired",
                              version=l1.importance_version)
    return ImportanceBase(importance_bp=DEFAULT_IMPORTANCE_BP, source="default")


def stored_importance(situation: Mapping[str, Any]) -> ComposedImportance | None:
    """READ BACK the composition `refresh_situations` stored, from a `context_situations` row.

    **A parse, not a recomputation** — which is the whole content of doc 07 step 6 and of H5's
    "100% populated" row. Every term of the arithmetic is in the stored JSONB, so this hands the
    BSO builder the same object the composer produced without touching a fact, a cohort or a
    clock.

    `None` for a row whose sweep predates the composer (the column is null) or whose body cannot
    be read. Absence is the pre-composition path, unchanged and still correct: the BSO then
    carries Layer 1's base alone. A body that is present but unreadable is treated the same way
    rather than raising, for the reason `_json` gives — a receipt that cannot be parsed must not
    stop a situation compiling — but it is the one case worth noticing, so it is logged.
    """
    record = _json(situation.get("importance_components"), None)
    if not isinstance(record, Mapping) or not record:
        return None
    try:
        return ComposedImportance.from_record(record)
    except (KeyError, TypeError, ValueError):     # pragma: no cover - a body from another writer
        _log.warning("situation %s carries an unreadable importance_components body; the BSO "
                     "falls back to Layer 1's base", situation.get("situation_id"))
        return None


@dataclass(frozen=True, slots=True)
class SituationSubject:
    """What the sweep already knows about one situation before its importance can be composed.

    Keyed by `correlation_id`, not by `situation_id`, because `refresh_situations` composes BEFORE
    it mints the id for a situation it has never written (`context_situations` is unique on
    `(org_id, correlation_id)`, so the two are 1:1 and either is a key). Every field is already on
    the `context_correlations` row the sweep is iterating — this asks the caller to derive nothing.
    """

    #: The row to write the answer back to. Carried beside `correlation_id` rather than derived
    #: from it because the six writers of `context_situations` mint their own synthetic
    #: correlation ids (`corr_touch_*`, `corr_period_*`, ...) that appear in no
    #: `context_correlations` row — the situation id is the only key all six share.
    situation_id: str
    correlation_id: str
    domain: str
    #: WHICH MESSAGE GROUNDS AN ABSENCE DEPENDS ON WHICH ABSENCE IT IS, and only the type says.
    #: `awaiting_response` claims "we wrote and nothing came back" — our outbound message is the
    #: receipt. `first_response_overdue` claims the mirror image, "they wrote and we have not
    #: answered" — THEIR inbound message is. Reading one direction for both is what made the
    #: backfill find nothing on the pilot. Defaulted so the dataclass stays constructible without
    #: it; an empty type simply resolves no receipt, which is the pre-existing behaviour.
    situation_type: str = ""
    anchor_node_id: str | None = None
    #: `context_correlations.last_event_at`, which becomes `context_situations.last_seen_at` — THE
    #: SITUATION's own newest evidence, never the subject's. A company node is busy with forty
    #: other threads while the renewal this situation is about has been silent since June; reading
    #: the subject's newest evidence would hold a dead situation at full weight.
    last_event_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SituationImportance:
    """One situation's composed importance, with the inputs that produced it kept beside it.

    The inputs are carried rather than dropped because the SIXTH CONFIDENCE AXIS is derived from
    them and from the composition together: `ComposedImportance.leaned_on(modifiers)` returns only
    the comparisons whose modifiers actually FIRED, which is what L2.5.1 asks the axis to measure.
    Recomputing that set from the stored record alone is impossible — the record names the winning
    receipt, not the whole qualifying set — so the axis has to be scored in the same pass.
    """

    composed: ComposedImportance
    modifiers: ModifierInputs
    l1: L1Signals | None

    @property
    def analytic_inputs(self) -> dict[str, tuple[Mapping[str, Any], ...]]:
        """`situations.score_situation(trends=, cohort_positions=, anomalies=)`, ready to splat."""
        return self.composed.leaned_on(self.modifiers)


def compose_org_importance(conn, org_id: str, subjects: Sequence[SituationSubject], *,
                           eval_time: datetime) -> dict[str, SituationImportance]:
    """BLG-18 steps 2..6 for every situation in one org, in FIVE statements total.

    The whole read plan, once, regardless of how many situations the tenant holds:

      1. `gather_l1_signals_bulk` — Layer 1's verdicts, per correlation (step 1's base, and the
         signal ids modifier 3e joins on);
      2. `gather_subject_nodes` — which graph nodes each situation is about (modifiers 3a-3d);
      3. `read_constituent_signals` — the distinct source systems behind each correlation (step 2);
      4-5. `load_modifier_inputs` — the derived facts, the unresolved conflicts and the domain
         coverage, three statements for the whole org.

    THE SUPPLY GUARD RUNS FIRST AND ONCE. Doc 07's hard rule 7: when over 90% of Layer 1's scored
    output for this tenant sits at exactly 5000, ALG-17 is not live here, and the honest answer is
    a flat distribution reported flat — NOT a spread this layer invented on top of a constant. The
    verdict is a property of the SUPPLY, so it is measured over the org's whole scored population
    and passed to every composition, never re-decided per situation.

    Returns a mapping keyed by `situation_id`, which is the key every writer of
    `context_situations` shares.
    """
    if not subjects:
        return {}
    correlations = [s.correlation_id for s in subjects if s.correlation_id]
    l1_by_correlation = gather_l1_signals_bulk(conn, org_id, correlations)
    l1_by_correlation = backfill_absence_l1(conn, org_id, subjects, l1_by_correlation)
    nodes_by_correlation = gather_subject_nodes(conn, org_id, correlations)
    constituents = read_constituent_signals(conn, org_id, correlations)

    # Doc 07 hard rule 7, measured on what Layer 1 actually published to this tenant. The SCORED
    # rows only: an unscored signal publishes at 0 because the floor refused to invent a number,
    # and counting those would dilute the flat share with rows that were never scored at all.
    supply = assess_l1_supply(
        l1.importance_bp for l1 in l1_by_correlation.values() if l1.importance_bp is not None)

    refs = tuple(SituationRef(
        # `SituationRef.situation_id` is a BUNDLE KEY, and the correlation is what the modifier
        # reads are grouped by, so the correlation id is what goes here. The answer is re-keyed
        # onto the real situation id below.
        situation_id=subject.correlation_id,
        domain=str(subject.domain or ""),
        # THE ANCHOR PLUS THE EVIDENCE'S OWN NODES. The anchor is what the situation is filed
        # under; the evidence nodes are where its facts actually landed (a deal's stage on the
        # deal, whose turn it is on a person). Neither alone is the situation's subject.
        subject_node_ids=tuple(sorted(
            ({subject.anchor_node_id} if subject.anchor_node_id else set())
            | set(nodes_by_correlation.get(subject.correlation_id, ())))),
        signal_ids=(l1_by_correlation[subject.correlation_id].signal_ids
                    if subject.correlation_id in l1_by_correlation else ()),
        newest_evidence_at=subject.last_event_at,
    ) for subject in subjects)
    bundles = load_modifier_inputs(conn, org_id, refs, eval_time=eval_time)

    out: dict[str, SituationImportance] = {}
    for subject in subjects:
        key = subject.correlation_id
        l1 = l1_by_correlation.get(key)
        bundle = bundles.get(key, ModifierInputs(newest_evidence_at=subject.last_event_at,
                                                 coverage_domain=str(subject.domain or "")))
        out[subject.situation_id] = SituationImportance(
            composed=compose_situation_importance(
                base=importance_base(l1),
                signals=constituents.get(key, ()),
                modifiers=bundle,
                eval_time=eval_time,
                l1_active=supply.active),
            modifiers=bundle, l1=l1)
    return out



#: Every situation this org holds, in the shape `compose_org_importance` needs. ALL STATUSES, not
#: just `active`: a dormant or resolved situation keeps its ranking so a reader looking at why it
#: was closed still sees what it was worth, and re-opening one (`decide_lifecycle` does, by
#: itself, when new evidence post-dates the resolution) must not surface a row with a null
#: importance among ranked ones.
#: ARCHIVED ROWS ARE EXCLUDED, and they were not. The comment above argues — correctly — that a
#: dormant or resolved row keeps its ranking, so a reader can see what a closed situation was
#: worth and a reopened one does not surface with a null importance. ARCHIVED is the state past
#: that: 180 days after it resolved, out of the working set by definition, and nothing reopens it
#: except the contradiction path, which recomposes on its own when it does. Recomposing an
#: importance for it on every sweep was work whose answer nobody could ever read — and since
#: nothing prunes `context_situations` at all, that set only grows.
_ORG_SITUATIONS = (
    "select situation_id, correlation_id, domain, situation_type, anchor_node_id, last_seen_at "
    "from context_situations where org_id = :o and coalesce(status, '') <> 'archived' "
    "order by situation_id")

#: One UPDATE, executed once per situation as a batched parameter set. `inputs` is MERGED rather
#: than replaced — the five other writers of this table put their own arithmetic in that column
#: and this pass has no business overwriting it; it adds the three analytic keys and nothing else.
_STORE_IMPORTANCE = (
    "update context_situations set importance_bp = :bp, importance_version = :ver, "
    "  importance_components = cast(:components as jsonb), confidence_analytic = :analytic, "
    "  inputs = coalesce(inputs, '{}'::jsonb) || cast(:analytic_inputs as jsonb) "
    "where org_id = :o and situation_id = :sid")


def refresh_situation_importance(store, org_id: str, *, eval_time: datetime) -> int:
    """BLG-18 steps 2..6 for one org, STORED. The composer's production caller.

    **WHY THIS IS A PASS OF ITS OWN AND NOT A LINE INSIDE `refresh_situations`.** Two reasons,
    either of which is sufficient:

    * ORDER. Every one of the six modifiers reads a `derived.*` fact — trend, cohort position,
      anomaly, blocked count — and `reason/runner` writes all four of those families AFTER it
      refreshes situations. Composing inside that function would read last sweep's analytic
      stratum, and on a tenant's FIRST sweep it would read an empty one: every modifier silent,
      the distribution flat, and the cause nothing to do with the composer.
    * COVERAGE OF THE WRITERS. `context_situations` has SIX writers, not one —
      `situations.refresh_situations`, `periodic`, `support_situations`, `meeting_touch`,
      `outreach_situations` and `document_register`. Five of them mint synthetic correlation ids
      and never call `score_situation` at all. A composition welded to one writer would leave the
      other five carrying a null importance, and a null is invisible to the gate rather than
      failing it — the situations nobody ranks would be exactly the ones nobody notices.

    IDEMPOTENT, and byte-stable. `ComposedImportance.as_record()` carries nothing derived from the
    clock, so running this twice at two instants over an unchanged graph writes an identical body.
    That is not tidiness: the record reaches `BusinessSituationObject.metadata`, whose hash is the
    expertise package's content address, and a per-sweep value there mints a fresh ~238 kB package
    row per situation per sweep — the mechanism that put 995 MB on one tenant's database.

    `eval_time` is a PARAMETER. The sweep reads its clock once (`runner.sweep_at`) and every pass
    in it — the sampler, the trend, the anomaly detector, this — answers against that one instant,
    so a replay of a past sweep reproduces that sweep's inputs rather than today's.

    Returns the number of situations composed.
    """
    with store.engine.connect() as conn:
        rows = conn.execute(text(_ORG_SITUATIONS), {"o": org_id}).mappings().all()
        if not rows:
            return 0
        composed = compose_org_importance(conn, org_id, tuple(
            SituationSubject(situation_id=str(row["situation_id"]),
                             correlation_id=str(row["correlation_id"]),
                             domain=str(row["domain"] or ""),
                             situation_type=str(row["situation_type"] or ""),
                             anchor_node_id=(str(row["anchor_node_id"])
                                             if row["anchor_node_id"] else None),
                             last_event_at=row["last_seen_at"])
            for row in rows), eval_time=eval_time)

    params = []
    for situation_id, importance in composed.items():
        leaned_on = importance.analytic_inputs
        analytic, receipt = analytic_receipt(**leaned_on)
        params.append({
            "o": org_id, "sid": situation_id,
            "bp": importance.composed.importance_bp,
            "ver": importance.composed.version,
            "components": json.dumps(importance.composed.as_record(), default=str),
            "analytic": analytic,
            "analytic_inputs": json.dumps(receipt, default=str)})
    if not params:
        return 0
    # ONE transaction for the whole org. The pass is a recomputation of a derived view, so a
    # partial write is the state worth avoiding: half a tenant ranked against this sweep's facts
    # and half against last sweep's is a ranking nobody can reason about, and there is nothing to
    # salvage from a failed pass — the next drain recomputes the same numbers from the same graph.
    with store.engine.begin() as conn:
        conn.execute(text(_STORE_IMPORTANCE), params)
    return len(params)



def _missing_paths(situation: Mapping[str, Any], facts: Mapping[str, Any],
                   neighbor_facts: Mapping[str, Any]) -> tuple[str, ...]:
    """Which of this situation type's expected fields the graph does not hold, as FIELD PATHS.

    This used to be a hardcoded empty tuple, and an empty `missing_fields` is not a neutral
    default — it is a claim. `packs/compiler/context_adapter.evaluate` consults exactly this set
    to decide whether a predicate is UNKNOWN, so with it empty an `exists:` test on a field
    nothing ever wrote returned a confident FALSE. The situation was then silently not routed,
    indistinguishable from a situation correctly judged not to apply, and every downstream reader
    was told the context was complete.

    Derived from `domain_spec.expected_fields` — the same declaration `situations.coverage_score`
    already scores against — so the two can never disagree about what a situation type is supposed
    to know. The neighbourhood counts as held: `reason/adapters/native.py` borrows a missing root
    field from the 1-hop neighbours, so a field present there is one the reasoner can actually
    read, and calling it missing here would abstain over evidence we have.

    An unregistered domain declares no expected fields and therefore reports nothing missing —
    unchanged behaviour, and correct: we cannot name a gap in a domain nobody has described.
    """
    expected = spec_for(situation.get("domain")).fields_for(str(situation["situation_type"]))
    if not expected:
        return ()
    held = set(facts or ()) | set(neighbor_facts or ())
    return tuple(sorted(path for path in expected if path not in held))

def build_context_slice(
    *, org_id: str, situation: Mapping[str, Any], facts: Mapping[str, Any],
    observations: list[Mapping[str, Any]], neighbor: tuple[int, set, Mapping[str, Any]],
    graph_version: int, eval_time: datetime, trace_id: str,
    visibility: Visibility | None = None,
    absences: Sequence[Any] = (), coverage_ready: bool | None = None,
) -> SituationContextSlice:
    """The frozen context Layer 3 is allowed to look inside.

    `absences` are this situation's `StoredAbsence` rows (L2.5.5) and `coverage_ready` its
    domain's tri-state coverage. Both are OPTIONAL and both default to saying nothing, because a
    caller with no absence data must produce the slice it produced before this landed — a slice
    is content-addressed and its metadata is part of the address, so a key written empty on every
    slice would change every package hash for a fact nobody has.

    What they add is the difference between `{absent: contract.amendment}` meaning *"there is no
    amendment"* and meaning *"we have no source that could hold one"*. `ContextAdapter` answered
    TRUE to both until this argument existed.
    """
    edge_count, neighbor_obs, neighbor_facts = neighbor
    anchor = str(situation["anchor_node_id"])
    return SituationContextSlice(
        org_id=org_id,
        trace_id=trace_id,
        visibility=visibility or Visibility(scope="org", derived_from="l2:situation"),
        id=f"slice:{situation['situation_id']}",
        graph_version=int(graph_version),
        selector_version=SELECTOR_VERSION,
        evaluation_time=eval_time,
        root_entity_ids=(anchor,),
        facts=_no_floats(dict(facts)),
        observations=tuple(_no_floats(dict(o)) for o in observations),
        neighbor_facts=_no_floats(dict(neighbor_facts)),
        neighbor_observations=tuple(sorted({str(k) for k in neighbor_obs})),
        edge_count=int(edge_count),
        missing_fields=_missing_paths(situation, facts, neighbor_facts),
        metadata={"shadow": True,
                  **absence_metadata(
                      unknowable=unknowable_fields(absences),
                      absent=absent_fields(absences),
                      # Tri-state in, tri-state out. `None` — a domain nobody declared — omits
                      # the key entirely rather than writing `False`: "we did not assess" must
                      # not arrive at the predicate layer as "no observation absence is a
                      # finding", which would silently stop every `no_obs` rule for a tenant
                      # whose coverage row has simply not been filed yet.
                      observation_licensed=coverage_ready)},
    )


__all__ = [
    "SELECTOR_VERSION",
    "TYPE_SOURCE_ANCHOR",
    "TYPE_SOURCE_PATTERN",
    "EVIDENCE_POOL",
    "MAX_CONFLICTS",
    "MAX_MATCHED_CONDITIONS",
    "PREPARED_FRAME",
    "RESOLVED_GRADES",
    "PatternFire",
    "analytic_context",
    "gather_conflicts",
    "gather_pattern_fires",
    "gather_span_sources",
    "situation_confidence_vector",
    "verify_evidence_spans",
    "SituationImportance",
    "SituationSubject",
    "compose_org_importance",
    "refresh_situation_importance",
    "stored_importance",
    "gather_l1_signals_bulk",
    "gather_subject_nodes",
    "importance_base",
    "gather_visibility",
    "DEFAULT_IMPORTANCE_BP",
    "MAX_EVIDENCE",
    "UNSCORED_VERSION",
    "L1Signals",
    "gather_l1_signals",
    "gather_evidence_and_signals",
    "build_business_situation",
    "build_context_slice",
]
