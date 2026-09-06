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
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from genios_engine.context.domain_spec import spec_for
from genios_engine.context.situations import SCORE_MAX
from genios_engine.contracts.domain_expertise import (
    BusinessSituationObject,
    SituationContextSlice,
)
from genios_engine.contracts.visibility import Visibility, narrowest

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


def _span_key(span: Mapping[str, Any]) -> tuple[Any, ...]:
    return (span.get("source_ref"), span.get("start_offset"), span.get("end_offset"),
            span.get("quote"))


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
    rows = conn.execute(text(
        "select qs.signal_id, qs.state, qs.importance_bp, qs.importance_version, "
        "qs.importance_components, qs.evidence_refs, qs.conflict_ids "
        "from qualified_signals qs "
        "join context_correlation_members m "
        "  on m.event_id = qs.event_id and m.org_id = qs.org_id "
        "where qs.org_id = :o and m.correlation_id = :c "
        "order by qs.importance_bp desc, qs.signal_id"),
        {"o": org_id, "c": correlation_id}).mappings().all()
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
        importance_bp=(int(top["importance_bp"]) if top is not None else None),
        importance_version=(str(top["importance_version"]) if top is not None
                            else UNSCORED_VERSION),
        components=dict(_json(top["importance_components"], {})) if top is not None else {},
        evidence=tuple(evidence[:MAX_EVIDENCE]),
        conflict_ids=tuple(sorted(conflicts)),
        signal_count=len(live),
        scored_count=len(live_scored),
    )


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


def _distinct_external_domains(members: tuple[Mapping[str, Any], ...]) -> set[str]:
    domains = set()
    for m in members:
        if m.get("type") != "external_contact":
            continue
        email = str(m.get("id") or "")
        if "@" in email:
            domains.add(email.rsplit("@", 1)[1].lower())
    return domains


def build_business_situation(
    *, org_id: str, situation: Mapping[str, Any],
    signal_ids: list[str], evidence: list[Mapping[str, Any]], trace_id: str,
    members: tuple[Mapping[str, Any], ...] = (),
    visibility: Visibility | None = None,
    l1: L1Signals | None = None,
) -> BusinessSituationObject:
    """``members`` — real correlated counterparties from ``gather_members`` — is a separate,
    explicit parameter rather than a key smuggled onto ``situation``. Callers pass a raw DB row
    for ``situation`` in every existing call site; making a new field's absence silently produce
    the OLD anchor-only behaviour is safer than requiring every caller to know a magic key.

    ``l1`` — ``gather_l1_signals``' answer — is optional for the same reason and reads the same
    way: absent, this builds exactly the BSO it built before `qualified_signals` existed, which
    is what keeps a pre-activation tenant working. Present, Layer 1's own verdict WINS over every
    default in this function: its score, its receipts and its signal ids, because re-deriving
    what Layer 1 already decided is how two layers end up disagreeing about one situation."""
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
    # THE SCORE. Layer 1's if Layer 1 published one; the neutral default only when it did not.
    # `importance_source` is stored beside it so a package can never be read as scored when it
    # was defaulted — the state the constant made indistinguishable for 193 of 223 signals.
    if l1 is not None and l1.importance_bp is not None:
        importance_bp, importance_source = l1.importance_bp, "l1_qualified_signals"
    elif l1 is not None and l1.signal_count:
        importance_bp, importance_source = DEFAULT_IMPORTANCE_BP, "l1_unscored"
    elif l1 is not None:
        # Signals exist, and ALG-19 has retired every one of them. Distinct from `l1_unscored`
        # (live signals the floor could not measure) because they are different facts: one says
        # "nobody scored this", the other says "this situation has nothing live left in it", and
        # a reader deciding whether to trust the neutral default needs to know which.
        importance_bp, importance_source = DEFAULT_IMPORTANCE_BP, "l1_all_retired"
    else:
        importance_bp, importance_source = DEFAULT_IMPORTANCE_BP, "default"
    if l1 is not None and l1.signal_ids:
        # The REAL qualified signal ids. `gather_evidence_and_signals` returns event ids under
        # this name because, before `qualified_signals`, no signal id existed to return.
        signal_ids = list(l1.signal_ids)
    if l1 is not None and l1.evidence:
        # Layer 1's verified spans lead; the correlation's graph refs follow as context. The
        # synthetic `reconstructed` receipt is dropped — it exists only so the contract's
        # non-empty rule holds when there is nothing real to show, and now there is.
        evidence = [*l1.evidence,
                    *(e for e in evidence if not e.get("reconstructed"))][:MAX_EVIDENCE]
    return BusinessSituationObject(
        org_id=org_id,
        trace_id=trace_id,
        visibility=visibility or Visibility(scope="org", derived_from="l2:situation"),
        id=str(situation["situation_id"]),
        signal_ids=tuple(signal_ids),
        type=str(situation["situation_type"]),
        confidence_bp=_bp(situation.get("confidence_overall")),
        importance_bp=importance_bp,
        evidence=tuple(_no_floats(dict(e)) for e in evidence),
        entities=entities,
        timeline=timeline,
        state=str(situation.get("status") or "active"),
        metadata={
            "domain_ids": [str(domain)] if domain else [],
            "coverage_bp": _bp(situation.get("coverage")),
            "importance_source": importance_source,
            # The explanation travels with the number, on `qualified_signals`' own argument:
            # "why is this an 8100" must be answerable from data, and it must stay answerable
            # after ALG-17's weights move.
            "importance_version": (l1.importance_version if l1 is not None else None),
            "importance_components": (
                {k: v for k, v in l1.components.items() if k != _UNSTABLE_COMPONENT}
                if l1 is not None else {}),
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
) -> SituationContextSlice:
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
        metadata={"shadow": True},
    )


__all__ = [
    "SELECTOR_VERSION",
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
