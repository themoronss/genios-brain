"""Pinned readers for Organization, Behavior, and Adaptive brain entries.

Layer 6 owns publication.  Layer 3 receives immutable versions and never updates them.  Selection
is explicit by capability, entity/subject key, or a subject key named on the situation; unrelated
tenant memory is not swept into a package merely because it exists.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import text

from genios_engine.contracts.brain_address import (
    address_tokens,
    legacy_tokens,
    selection_basis,
    token,
)
from genios_engine.contracts.domain_expertise import (
    BrainKind,
    BusinessSituationObject,
    ExpertiseEvidence,
)
from genios_engine.contracts.visibility import SCOPES, Visibility
from genios_engine.platform.canonical import semantic_hash, stable_id

from .errors import BrainPolicyViolation
from .models import (RoutePlan, RuntimeBrainEntry, RuntimeBrainSnapshot,
                     entity_fields)

_PERMISSION_CATEGORIES = frozenset({
    "approval", "compliance", "constraint", "permission", "policy", "retention", "security",
})
_PREFERENCE_PRECEDENCE = {
    BrainKind.BEHAVIOR: 1,
    BrainKind.ORGANIZATION: 2,
    BrainKind.ADAPTIVE: 3,
}


class RuntimeBrains(Protocol):
    def snapshot(self, *, situation: BusinessSituationObject, plan: RoutePlan,
                 object_ids: Sequence[str],
                 eval_time: datetime | None = None) -> RuntimeBrainSnapshot: ...


def _row_value(row: Any, name: str, default: Any = None) -> Any:
    if isinstance(row, Mapping):
        return row.get(name, default)
    return getattr(row, name, default)


def _json(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    return dict(value or {})


# harsh/mvp's Layer 6 (built ground-up) stores brain visibility with its own scope token
# `organization`, while this compiler's Visibility model (contracts/visibility.py) names the
# same scope `org`.  We normalise at the DB read boundary only — the rest of the compiler stays
# a faithful copy — so an Organization-brain entry is not rejected as an "unknown scope".
_L6_SCOPE_ALIASES = {"organization": "org"}

# harsh/mvp's learned_brain_entries has no confidence column; Layer 6 only publishes entries
# that already cleared the governance confidence floor (default min_confidence_bp = 6000), so a
# published+active row is treated as at-least-floor confident unless its value carries its own.
_DEFAULT_RUNTIME_CONFIDENCE_BP = 6000


def _normalize_l6_visibility(visibility: Mapping[str, Any]) -> dict[str, Any]:
    scope = visibility.get("scope")
    if scope in _L6_SCOPE_ALIASES:
        return {**visibility, "scope": _L6_SCOPE_ALIASES[scope]}
    return dict(visibility)


def _entry_from_l6_row(row: Any) -> RuntimeBrainEntry:
    """Map one harsh/mvp learned_brain_entries row onto the compiler's RuntimeBrainEntry.

    That table keys entries by (org_id, brain, subject, version) with no surrogate id and no
    confidence/trace/effective columns, so entry_id/trace_id are synthesised deterministically
    and effective_at comes from created_at.
    """
    brain = str(_row_value(row, "brain"))
    subject = str(_row_value(row, "subject"))
    version = int(_row_value(row, "version"))
    value = _json(_row_value(row, "value"))
    learning_id = str(_row_value(row, "learning_id"))
    return RuntimeBrainEntry(
        org_id=str(_row_value(row, "org_id")),
        brain=BrainKind(brain),
        entry_id=f"{brain}:{subject}:v{version}",
        subject_key=subject,
        version=version,
        value=value,
        confidence_bp=int(value.get("confidence_bp", _DEFAULT_RUNTIME_CONFIDENCE_BP)),
        learning_id=learning_id,
        effective_at=_row_value(row, "created_at"),
        visibility=_normalize_l6_visibility(_json(_row_value(row, "visibility"))),
        trace_id=learning_id,
    )


def _visibility_allows_package(entry: Mapping[str, Any], package: Mapping[str, Any]) -> bool:
    """Can every member of the package audience also see the brain evidence?"""
    source = Visibility.model_validate(dict(entry))
    target = Visibility.model_validate(dict(package))
    if SCOPES.index(source.scope) > SCOPES.index(target.scope):
        return False
    if source.scope in {"participants", "private"}:
        return set(target.principals) <= set(source.principals)
    return True


def _selectors(situation: BusinessSituationObject, plan: RoutePlan,
               object_ids: Sequence[str]) -> tuple[str, ...]:
    """The BARE values a subject key may be matched against, unchanged from before the address.

    Kept exactly as it was, and still consulted, because it is what every pre-address entry was
    published to be found by. `_situation_tokens` below is the vocabulary that actually binds; this
    is the compatibility half, and the two are deliberately separate so that deleting the legacy
    lane later is deleting a function rather than untangling one.
    """
    values = set(situation.brain_subject_keys)
    values.update(plan.capability_ids)
    values.update(object_ids)
    values.add(situation.id)
    for entity in situation.entities:
        fields = entity_fields(entity)
        value = fields.get("id") or fields.get("entity_id")
        if value:
            values.add(str(value))
    return tuple(sorted(values))


def _situation_tokens(situation: BusinessSituationObject, plan: RoutePlan,
                      object_ids: Sequence[str]) -> tuple[str, ...]:
    """WHAT THIS SITUATION IS ABOUT, in `contracts/brain_address`'s vocabulary.

    Two sources, and the distinction matters. `situation.brain_subject_keys` is what LAYER 2
    declared — written by `context/situation_bso.gather_brain_subject_keys`, which is the reader
    this metadata key waited for since it shipped. Everything else here is derived from the route
    and the situation's own fields, so a tenant whose sweep predates that writer still binds on
    capability, object, situation and entity — it just does not get the node ids and typed entity
    kinds only Layer 2 can resolve.

    A `brain_subject_key` that is ALREADY a token (`node:...`, `capability:...`) is passed through;
    one that is a bare value is promoted to whichever kind it looks like. That promotion is why an
    older Layer 2 does not have to be redeployed in lockstep with this compiler.
    """
    values: set[str] = set()

    def add(kind: str, value: Any) -> None:
        if not value:
            return
        try:
            values.add(token(kind, value))
        except ValueError:
            # A value the vocabulary refuses — a node id with a colon in it, an empty capability.
            # Dropped, never raised: one malformed entity must not cost this situation every other
            # piece of knowledge it could have bound.
            return

    add("org", situation.org_id)
    values.add(token("orgwide", situation.org_id))
    add("situation", situation.id)
    add("situation_type", situation.type)
    for domain_id in (*plan.domain_ids, *situation.domain_hints):
        add("domain", domain_id)
    for capability_id in plan.capability_ids:
        add("capability", capability_id)
    for object_id in (*object_ids, *plan.required_object_ids, *plan.optional_object_ids):
        add("object", object_id)
    for entity in situation.entities:
        fields = entity_fields(entity)
        identifier = fields.get("id") or fields.get("entity_id")
        if not identifier:
            continue
        identifier = str(identifier)
        # An entity id is EITHER a graph node id or an email address, and which one it is decides
        # which brain can find it. `gather_members` emits emails; the anchor path emits node ids.
        # Both are emitted under their own kind, so neither has to pretend to be the other.
        if "@" in identifier:
            add("email", identifier)
        else:
            add("node", identifier)
        kind = str(fields.get("type") or "").lower()
        if kind in {"person", "external_contact", "user"}:
            add("person", identifier)
        elif kind in {"organization", "company", "account"}:
            add("company", identifier)
        # `node_id` is the resolved graph identity Layer 2 attaches beside the email — the one
        # thing that lets a Behaviour pattern measured on a node reach a situation known by
        # address. Absent on the anchor-only path, which is why it is read rather than required.
        add("node", fields.get("node_id"))
    for raw in situation.brain_subject_keys:
        kind, _, rest = str(raw).partition(":")
        if kind in {"org", "orgwide", "domain", "capability", "object", "situation",
                    "situation_type", "node", "email", "person", "company", "jurisdiction",
                    "metric", "actor"} and rest:
            values.add(str(raw))
        elif "@" in str(raw):
            add("email", raw)
        else:
            add("node", raw)
    return tuple(sorted(values))


def _entry_tokens(entry: RuntimeBrainEntry) -> tuple[str, ...]:
    """The entry's address — declared if the producer wrote one, derived if it did not."""
    declared = address_tokens(entry.value)
    if declared:
        return declared
    return legacy_tokens(entry.brain.value, entry.subject_key, entry.org_id)


def _relevant(entry: RuntimeBrainEntry, *, capabilities: set[str],
              selectors: set[str], situation_tokens: set[str]) -> tuple[str, ...] | None:
    """The matched tokens when this entry applies, `None` when it does not.

    Returns the RECEIPT rather than a boolean on purpose. "This policy was applied" that cannot
    say which dimension matched is a claim an operator has to take on faith, and Layer 3 spent
    three months reporting a brain-slice count of zero precisely because nothing on this path was
    answerable from the outside.

    Four ways to match, in descending order of how much we trust them:

    1. the ADDRESS — token intersection, the contract, the only one a new producer should use;
    2. the entry's own `capability_id`, which the Adaptive lease has always carried;
    3. the whole subject key appearing as a selector;
    4. the subject key's `:`-segments intersecting the selectors — the pre-address heuristic,
       kept so nothing that binds today stops binding, and reported as `legacy_segment` so the
       receipts say when a match rested on it.
    """
    matched = selection_basis(_entry_tokens(entry), situation_tokens)
    if matched:
        return matched
    capability = entry.value.get("capability_id")
    if capability is not None and str(capability) in capabilities:
        return (f"capability:{capability}",)
    if entry.subject_key in selectors:
        return (f"legacy_subject:{entry.subject_key}",)
    segments = set(entry.subject_key.split(":")) & selectors
    if segments:
        return tuple(f"legacy_segment:{segment}" for segment in sorted(segments))
    return None


def _validate_axis(entry: RuntimeBrainEntry) -> None:
    category = str(entry.value.get("category") or entry.value.get("kind") or "").lower()
    if entry.brain in {BrainKind.BEHAVIOR, BrainKind.ADAPTIVE} \
            and category in _PERMISSION_CATEGORIES:
        raise BrainPolicyViolation(
            f"{entry.brain.value} entry {entry.entry_id!r} attempts to define "
            f"permission-axis knowledge ({category})")


def _category(entry: RuntimeBrainEntry) -> str:
    return str(entry.value.get("category") or entry.value.get("kind") or "").lower()


def _resolve_conflicts(entries: Sequence[RuntimeBrainEntry]) \
        -> tuple[tuple[RuntimeBrainEntry, ...], tuple[str, ...], tuple[Mapping[str, Any], ...]]:
    """Resolve only explicitly-declared conflicts; unrelated knowledge is never deep-merged."""
    unkeyed: list[RuntimeBrainEntry] = []
    groups: dict[tuple[str, str], list[RuntimeBrainEntry]] = {}
    for entry in entries:
        raw_key = entry.value.get("conflict_key")
        if not raw_key:
            unkeyed.append(entry)
            continue
        axis = "permission" if _category(entry) in _PERMISSION_CATEGORIES else "preference"
        groups.setdefault((axis, str(raw_key)), []).append(entry)

    selected = list(unkeyed)
    shadowed: list[str] = []
    resolutions: list[Mapping[str, Any]] = []
    for (axis, conflict_key), candidates in sorted(groups.items()):
        if axis == "permission":
            ranked = [(1 if item.brain is BrainKind.ORGANIZATION else 0, item)
                      for item in candidates]
        else:
            ranked = [(_PREFERENCE_PRECEDENCE[item.brain], item) for item in candidates]
        top = max(rank for rank, _ in ranked)
        winners = [item for rank, item in ranked if rank == top]
        if len(winners) != 1:
            raise BrainPolicyViolation(
                f"ambiguous {axis} conflict {conflict_key!r} has {len(winners)} "
                f"entries at the same precedence: {sorted(item.entry_id for item in winners)}")
        winner = winners[0]
        losers = sorted(item.entry_id for item in candidates if item is not winner)
        selected.append(winner)
        shadowed.extend(losers)
        resolutions.append({
            "axis": axis,
            "conflict_key": conflict_key,
            "winner_entry_id": winner.entry_id,
            "winner_brain": winner.brain.value,
            "shadowed_entry_ids": tuple(losers),
        })
    ordered = tuple(sorted(selected, key=lambda item: (
        item.brain.value, item.subject_key, item.version, item.entry_id)))
    return ordered, tuple(sorted(shadowed)), tuple(resolutions)


def _build_snapshot(entries: Iterable[RuntimeBrainEntry], *,
                    situation: BusinessSituationObject, plan: RoutePlan,
                    object_ids: Sequence[str]) -> RuntimeBrainSnapshot:
    selectors = set(_selectors(situation, plan, object_ids))
    situation_tokens = set(_situation_tokens(situation, plan, object_ids))
    capabilities = set(plan.capability_ids)
    included: list[RuntimeBrainEntry] = []
    excluded: list[str] = []
    #: entry id -> the tokens that selected it. Reaches the evidence rows below, so every applied
    #: piece of runtime knowledge can name WHY it was applied.
    bases: dict[str, tuple[str, ...]] = {}
    for entry in sorted(entries, key=lambda item: (
            item.brain.value, item.subject_key, item.version, item.entry_id)):
        if entry.org_id != situation.org_id:
            continue
        basis = _relevant(entry, capabilities=capabilities, selectors=selectors,
                          situation_tokens=situation_tokens)
        if basis is None:
            continue
        _validate_axis(entry)
        if not _visibility_allows_package(entry.visibility, situation.visibility):
            excluded.append(entry.entry_id)
            continue
        bases[entry.entry_id] = basis
        included.append(entry)

    selected, shadowed, resolutions = _resolve_conflicts(included)
    selected_ids = {entry.entry_id for entry in selected}
    manifest = [{
        "brain": entry.brain,
        "entry_id": entry.entry_id,
        "subject_key": entry.subject_key,
        "version": entry.version,
        "content_hash": semantic_hash(entry.value),
        "confidence_bp": entry.confidence_bp,
        "learning_id": entry.learning_id,
        "selected": entry.entry_id in selected_ids,
    } for entry in included]
    snapshot_id = stable_id("runtime_brains", {
        "org_id": situation.org_id,
        "entries": manifest,
    })
    evidence = tuple(ExpertiseEvidence(
        brain=entry.brain,
        source_ref=f"brain:{entry.entry_id}",
        source_version=str(entry.version),
        content_hash=semantic_hash(entry.value),
        confidence_bp=entry.confidence_bp,
        visibility=entry.visibility,
        trace_ids=(entry.trace_id,),
        metadata={
            "learning_id": entry.learning_id,
            "subject_key": entry.subject_key,
            "selection": "selected" if entry.entry_id in selected_ids else "shadowed",
            "conflict_key": entry.value.get("conflict_key"),
            # WHICH DIMENSION BOUND THIS. See `_relevant` — a receipt, not a boolean. A value
            # starting `legacy_` means the match rested on the pre-address heuristic and this
            # entry's producer has not been taught to publish an address yet.
            "selection_basis": bases.get(entry.entry_id, ()),
        },
    ) for entry in included)
    return RuntimeBrainSnapshot(
        entries=selected,
        evidence=evidence,
        snapshot_id=snapshot_id,
        excluded_entry_ids=tuple(sorted(excluded)),
        shadowed_entry_ids=shadowed,
        conflict_resolutions=resolutions,
    )


def _entry_from_lease_row(row: Any, *, org_id: str) -> RuntimeBrainEntry:
    """Map one `temporary_memories` row onto the compiler's RuntimeBrainEntry.

    THE TABLE IS SHAPED FOR A LEASE, NOT FOR A BRAIN ENTRY, and the three differences are the
    reason this reader is separate from `_entry_from_l6_row` rather than a `union all` in SQL:

    * there is no `brain` column. A row in this table is Adaptive by construction — Layer 6's only
      path here is `LearningTarget.TEMPORARY` — so the kind is stamped rather than read.
    * there is no `version` column. A lease is replaced, not versioned; the constant 1 is honest
      about that, and `memory_id` carries the identity the version would otherwise supply.
    * there is no `confidence` column, exactly as `learned_brain_entries` has none, so the same
      governance floor applies for the same reason.

    `expires_at` travels into `value` as `lease_expires_at` so a decision that rested on a
    preference can say when that preference stops being true. It is NOT used for filtering here —
    the SQL already filtered on the frozen evaluation time, and a second clock in Python would be
    a second answer to the same question.
    """
    value = _json(_row_value(row, "value"))
    memory_id = str(_row_value(row, "memory_id"))
    subject = str(_row_value(row, "subject"))
    expires_at = _row_value(row, "expires_at")
    learning_id = str(_row_value(row, "learning_id") or memory_id)
    return RuntimeBrainEntry(
        org_id=org_id,
        brain=BrainKind.ADAPTIVE,
        entry_id=f"adaptive:{subject}:{memory_id}",
        subject_key=subject,
        version=1,
        value={**value, "lease_expires_at": (
            expires_at.isoformat() if hasattr(expires_at, "isoformat") else str(expires_at))},
        confidence_bp=int(value.get("confidence_bp", _DEFAULT_RUNTIME_CONFIDENCE_BP)),
        learning_id=learning_id,
        effective_at=_row_value(row, "created_at"),
        visibility=_normalize_l6_visibility(_json(_row_value(row, "visibility"))),
        trace_id=learning_id,
    )


class InMemoryRuntimeBrains:
    def __init__(self, entries: Iterable[RuntimeBrainEntry] = ()) -> None:
        self.entries = tuple(entries)

    def snapshot(self, *, situation: BusinessSituationObject, plan: RoutePlan,
                 object_ids: Sequence[str],
                 eval_time: datetime | None = None) -> RuntimeBrainSnapshot:
        # `eval_time` is accepted and unused: an in-memory brain holds whatever the caller put in
        # it, and filtering a hand-built fixture by a clock would make a test's own setup
        # conditional on the test's own clock. The Postgres reader is where the lease TTL lives.
        return _build_snapshot(self.entries, situation=situation, plan=plan,
                               object_ids=object_ids)


class PostgresRuntimeBrains:
    """Read what Layer 6 published — BOTH of its stores — through two tenant-scoped queries.

    **THE SECOND QUERY IS THE POINT.** Doc 02 §1 names the Adaptive store as
    `learned_brain_entries` **plus** `temporary_memories`; the build split them and taught this
    reader only the first. `feedback/brain_pipeline.publish_runtime` writes a founder's
    `bad_timing` verdict into `temporary_memories`, this class selected from
    `learned_brain_entries` alone, and so `ExpertisePackage.adaptive_preferences` was structurally
    always empty — every piece of card feedback the product has ever collected was stored, governed,
    expired on schedule, and read by nothing.
    """

    def __init__(self, connection) -> None:
        self.connection = connection

    def snapshot(self, *, situation: BusinessSituationObject, plan: RoutePlan,
                 object_ids: Sequence[str],
                 eval_time: datetime | None = None) -> RuntimeBrainSnapshot:
        selectors = _selectors(situation, plan, object_ids)
        tokens = _situation_tokens(situation, plan, object_ids)
        # THE PREFILTER MUST NOT BE NARROWER THAN `_relevant`, and it used to be wider in one place
        # and narrower in another. The `position(':'||sel||':' ...)` clause matched a colon-bearing
        # selector that Python's `set(subject.split(':'))` then threw away; the address clause below
        # is the one that actually binds, and the three legacy clauses are kept verbatim so nothing
        # that reaches a package today stops reaching it.
        params = {"o": situation.org_id, "capabilities": list(plan.capability_ids),
                  "selectors": list(selectors), "tokens": list(tokens)}
        rows = self.connection.execute(text(
            "select org_id,brain,subject,version,value,learning_id,created_at,visibility "
            "from learned_brain_entries "
            "where org_id=:o and active and brain in ('organization','behavior','adaptive') "
            "and (jsonb_exists_any(coalesce(value->'address'->'tokens','[]'::jsonb), "
            "                      cast(:tokens as text[])) "
            "or brain='organization' "
            "or (value->>'capability_id')=any(cast(:capabilities as text[])) "
            "or subject=any(cast(:selectors as text[])) "
            "or exists (select 1 from unnest(cast(:selectors as text[])) selected(value) "
            "where position(':' || selected.value || ':' in ':' || subject || ':')>0)) "
            "order by brain,subject,version"), params).mappings().all()
        entries = list(_entry_from_l6_row(row) for row in rows)

        # ── The Adaptive lease store. Filtered on the FROZEN evaluation time, never `now()`.
        #
        # `eval_time` is the sweep's own clock, the same one the situation, the context slice and
        # the decision are all pinned to. Using `now()` here would mean a compile replayed for an
        # audit could select a preference that had already expired when the decision was taken —
        # a package that is not reproducible, which is the one property Layer 3 is required to
        # have. When the caller supplies no evaluation time we read NO leases at all rather than
        # falling back to the wall clock: a missing clock is a reason to apply no preference, not
        # a licence to invent one.
        if eval_time is not None:
            lease_rows = self.connection.execute(text(
                "select memory_id,subject,value,learning_id,created_at,visibility,expires_at "
                "from temporary_memories "
                "where org_id=:o and active and expires_at > :at "
                "and (jsonb_exists_any(coalesce(value->'address'->'tokens','[]'::jsonb), "
                "                      cast(:tokens as text[])) "
                "or (value->>'capability_id')=any(cast(:capabilities as text[])) "
                "or subject=any(cast(:selectors as text[])) "
                "or exists (select 1 from unnest(cast(:selectors as text[])) selected(value) "
                "where position(':' || selected.value || ':' in ':' || subject || ':')>0)) "
                "order by subject,memory_id"),
                {**params, "at": eval_time}).mappings().all()
            entries.extend(_entry_from_lease_row(row, org_id=situation.org_id)
                           for row in lease_rows)

        return _build_snapshot(tuple(entries), situation=situation, plan=plan,
                              object_ids=object_ids)


__all__ = [
    "InMemoryRuntimeBrains",
    "PostgresRuntimeBrains",
    "RuntimeBrainEntry",
    "RuntimeBrains",
]
