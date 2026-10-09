"""Merge the four brain slices into the one Layer 3 boundary object."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from genios_engine.contracts.domain_expertise import (
    BrainKind,
    ExpertiseEvidence,
    ExpertisePackage,
    SituationContextSlice,
    expertise_id,
)
# ⛔ THE ADMITTED OBJECT, NOT THE CANDIDATE. `domain_shadow.py:881` passes
# `publication.situation`, which `PublicationResult` types as this class — the compiler
# never sees an unadmitted one. This import said `contracts.domain_expertise` until L2-1,
# naming a 16-field candidate while receiving a 28-field admitted object; it survived
# because the two spelled the same and v2 carries v1-named compatibility properties.
from genios_engine.contracts.situation import BusinessSituationObject
# The package's OWN normaliser, imported rather than restated. It is underscore-private to
# `contracts.domain_expertise` and this is the one importer: `ExpertisePackage.__post_init__`
# runs it on `visibility` a moment after `expertise_id` hashes the same field, so a second
# implementation here would be two spellings of one rule that can drift into a content address.
from genios_engine.contracts.domain_expertise import _visibility

from .context_adapter import ContextAdapter
from .capability_resolver import artifact_admission_reason
from .models import ExpertSlice, RoutePlan, RuntimeBrainEntry, RuntimeBrainSnapshot

COMPILER_VERSION = "domain-compiler.v1"

#: ⛔ WHAT AN **OBJECT**'S `definition` MAY CARRY INTO A PACKAGE — a closed list, because the whole
#: authored document used to travel and almost none of it was ever read.
#:
#: MEASURED 2026-10-02 on production: `expertise_packages` was **460 MB over 1,163 rows** — 388 kB
#: average, one row 1,338 kB — and `objects` was **85% of the biggest payload** (1,143 kB for 13
#: objects, ~88 kB each). That is what took the database over its 0.5 GB quota and put it into
#: read-only, which in turn crash-looped every deploy (`platform/migrate` raises when migrations
#: are pending and the server will not accept writes). It is the THIRD time this table has done it;
#: the module already carries the scars of the other two ("the 995 MB that took a production
#: database read-only", and `e1a0c47`).
#:
#: AND THE DESIGN ALWAYS SAID SO. `objects.yaml` is specified as *"the load-set — references only"*.
#: The package was inlining the full definition instead: `attributes` (1,008 kB across the corpus),
#: `relationships`, `anti_patterns`, `states`, `business_rules`, `exceptions`, `actions` — none of
#: which any consumer of `package.objects` opens.
#:
#: ⛔ THE LIST IS WHAT CONSUMERS ACTUALLY READ, grepped rather than guessed:
#:   * `reason/adapters/expertise._executable_required_fields` and `._universal_required_fields`
#:     read `definition["inference_patterns"]` and nothing else.
#:   * `reason/adapters/citations.situation_tags` reads an object's `id` only — never its
#:     definition. (`citations._definition` exists, but it is applied to `expert_rules`.)
#:   * `contracts/domain_expertise` requires objects to be non-empty mappings and names no key
#:     inside them.
#: `identity` is kept on top of that: it is the header every authored document carries, it is
#: ~1% of the bytes, and dropping the thing that says WHICH object a record is would make a package
#: unreadable by a human debugging one. Measured saving with both kept: **82.6%** of object bytes
#: across the 97 authored objects (4,499 kB -> 783 kB).
#:
#: ⛔ CAPABILITIES AND EXPERT RULES ARE NOT PRUNED, deliberately. `rule_compiler` reads a rule's
#: `definition["rule"]`, and `adapters/expertise` reads several capability keys; they are also an
#: order of magnitude smaller (41 kB and 109 kB against 1,143 kB in the measured payload). A
#: closed list is only safe where the readers are known, so it is applied where they are.
#:
#: Adding a key here is cheap and safe. REMOVING one re-mints every package's content address, so
#: it costs one compile — see the churn note on `metadata` below for why that matters.
OBJECT_DEFINITION_KEYS: frozenset[str] = frozenset({"identity", "inference_patterns"})


def _authored(document, *, bindings: Mapping[str, tuple[str, ...]] | None = None,
              keep: frozenset[str] | None = None) -> dict[str, Any]:
    content = document.content
    if keep is not None and isinstance(content, Mapping):
        # Insertion order is preserved so the pruned mapping canonicalizes the same way the full
        # one did for the keys that survive — the content address must change exactly once, when
        # the keys leave, and never again because a dict was rebuilt in a different order.
        content = {key: value for key, value in content.items() if key in keep}
    result = {
        "id": document.id,
        "kind": document.kind,
        "version": document.version,
        "definition": content,
    }
    if bindings is not None:
        result["entity_bindings"] = bindings.get(document.id, ())
    return result


def _runtime(entry: RuntimeBrainEntry) -> dict[str, Any]:
    return {
        "entry_id": entry.entry_id,
        "subject_key": entry.subject_key,
        "version": entry.version,
        "value": entry.value,
        "confidence_bp": entry.confidence_bp,
        "learning_id": entry.learning_id,
        "effective_at": entry.effective_at,
        "trace_id": entry.trace_id,
    }


class ExpertiseBuilder:
    def build(self, *, situation: BusinessSituationObject, plan: RoutePlan,
              expert: ExpertSlice, runtime: RuntimeBrainSnapshot,
              brain_snapshot_id: str, evidence: tuple[ExpertiseEvidence, ...],
              context: SituationContextSlice | None = None) \
            -> ExpertisePackage:
        bindings = ContextAdapter(situation, context).bind_objects(expert.objects)
        by_brain: dict[BrainKind, list[RuntimeBrainEntry]] = {
            BrainKind.ORGANIZATION: [],
            BrainKind.BEHAVIOR: [],
            BrainKind.ADAPTIVE: [],
        }
        for entry in runtime.entries:
            by_brain[entry.brain].append(entry)

        capabilities = tuple(_authored(item) for item in expert.capabilities)
        objects = tuple(_authored(item, bindings=bindings, keep=OBJECT_DEFINITION_KEYS)
                        for item in expert.objects)
        expert_rules = tuple(_authored(item) for item in (
            *expert.artifacts, *expert.variants))
        organization = tuple(_runtime(item) for item in by_brain[BrainKind.ORGANIZATION])
        behavior = tuple(_runtime(item) for item in by_brain[BrainKind.BEHAVIOR])
        adaptive = tuple(_runtime(item) for item in by_brain[BrainKind.ADAPTIVE])
        confidence_bp = min(situation.confidence_bp, expert.coverage_bp)
        metadata = {
            "compiler_version": COMPILER_VERSION,
            "situation_type": situation.type,
            "situation_hash": situation.semantic_hash,
            "domain_ids": plan.domain_ids,
            "matched_situation_ids": plan.situation_ids,
            "required_object_ids": plan.required_object_ids,
            "optional_object_ids": plan.optional_object_ids,
            "never_object_ids": plan.never_object_ids,
            "missing_optional_object_ids": expert.missing_optional,
            "missing_artifact_ids": expert.missing_artifacts,
            "unresolved_route_predicates": plan.unresolved_predicates,
            "skipped_capability_ids": plan.skipped_capability_ids,
            # What the abstention gate downstream reads. `accepted` ONLY when every routed
            # capability cleared admission (stable + approved by a named reviewer + accepted
            # hash matching the routed bytes); a measurement compile over drafts says `draft`
            # here and everything built from it stays non-prescriptive at the card layer.
            "review_state": "accepted" if plan.admitted else "draft",
            "admission_gaps": plan.admission_gaps,
            # How much of this answer came from placeholders. Deliberately NOT folded into
            # `review_state`: a thin capability is a content gap, an unadmitted one is an
            # authority gap, and one number cannot mean both.
            "hollow_capability_ids": plan.hollow_capability_ids,
            # ⛔ THE THIRD LAYER OF THE ADMISSION CEREMONY, COUNTED RATHER THAN ENFORCED.
            #
            # A capability that fails review is dropped; a situation that fails is flagged and its
            # card stops instructing. An OBJECT and a HEURISTIC were asked nothing at all — measured
            # 2026-09-30, 66 of 75 objects and 218 of 283 heuristics are `draft` and NOT ONE of
            # either carries an admission hash. And `heuristics/` is where `reads:` lives, so the
            # widest surface in the corpus by file count is the one where somebody can change what
            # the expertise consults with nothing noticing.
            #
            # ⛔ COUNTED, NOT GATED — see `artifact_admission_reason`. Refusing them today would make
            # 284 documents inadmissible in one step on a corpus whose capabilities all pass;
            # `card_source` already wrote the rule for the other cutover here — measure before you
            # retire. These two lists are that measurement, and they are DELIBERATELY kept apart
            # from `review_state` for exactly the reason `hollow_capability_ids` is: an unreviewed
            # heuristic is a governance gap, an unadmitted capability is an authority gap, and one
            # number cannot mean both.
            "unreviewed_object_ids": tuple(
                item.id for item in expert.objects
                if artifact_admission_reason(item.content) is not None),
            "unreviewed_artifact_ids": tuple(
                item.id for item in expert.artifacts
                if artifact_admission_reason(item.content) is not None),
            "excluded_runtime_entry_ids": runtime.excluded_entry_ids,
            "shadowed_runtime_entry_ids": runtime.shadowed_entry_ids,
            "runtime_conflict_resolutions": runtime.conflict_resolutions,
            "object_coverage_bp": expert.coverage_bp,
            "importance_bp": situation.importance_bp,
            "context_bindings": bindings,
            "expert_snapshot_id": expert.snapshot_id,
            "runtime_snapshot_id": runtime.snapshot_id,
            "context_slice_id": context.id if context is not None else None,
            "context_slice_hash": context.semantic_hash if context is not None else None,
            "context_graph_version": context.graph_version if context is not None else None,
            "context_selector_version": context.selector_version if context is not None else None,
            # The authored card copy, and which situation it came from. Carried on the package so
            # it is hashed into the manifest with the rest of the knowledge: rewording a headline
            # mints a new capability version rather than silently changing what an already-audited
            # card claimed.
            "render": plan.render,
            "render_situation_id": plan.render_situation_id,
            # The authored priority, carried for the same reason and hashed the same way. It is a
            # property of the SITUATION, not of this evaluation, so it is stable across compiles
            # and does not churn the content address the way `trace_id` did.
            "authored_priority_bp": plan.priority_bp,
            "priority_situation_id": plan.priority_situation_id,
        }
        # L3.1-U2 · the routing receipt, WRITTEN ONLY WHEN THERE IS ONE.
        #
        # A key written `None` on every package would be a key hashed into every package's
        # content address, which re-mints the id of every package that already exists for a fact
        # nobody has — the exact shape of the churn `e1a0c47` stopped and of the 995 MB that took
        # a production database read-only. `build_context_slice.absence_metadata` omits its keys
        # on the same argument, and this follows it: a tenant with no pattern fire compiles to a
        # byte-identical package before and after this wave.
        #
        # AND NO NEW CHURN CLASS FOR A TENANT THAT DOES HAVE FIRES. These keys appear only when
        # the BSO carries a pattern fire — and a BSO carrying one already hashes differently from
        # one that does not, because `situation_bso._pattern_metadata` puts `pattern_id`,
        # `pattern_version`, `pattern_activated` and `matched_conditions` into the situation's own
        # metadata, which is `metadata['situation_hash']` above. The address of such a package
        # moved when the FIRE arrived, not when this receipt did; the receipt costs one re-mint on
        # the sweep it lands and nothing per sweep after it.
        # Declared variants that resolved to nothing or to several documents — written ONLY
        # when non-empty, on this block's own omit-when-empty rule, so a tenant that declared
        # nothing mints exactly the package it always has.
        unresolved = tuple(getattr(expert, "unresolved_variants", ()) or ())
        if unresolved:
            metadata["unresolved_variant_ids"] = list(unresolved)
        if plan.pattern_route_state is not None:
            metadata["pattern_route_state"] = plan.pattern_route_state
        if plan.pattern_route_id is not None:
            metadata["pattern_route_id"] = plan.pattern_route_id
        # STEP-11 · the situation's own do-nothing sentence, WRITTEN ONLY WHEN ONE WAS AUTHORED — this
        # block's omit-when-empty rule, for its reason: every package compiled today keeps its id.
        if plan.do_nothing_consequence:
            metadata["do_nothing_consequence"] = plan.do_nothing_consequence
            metadata["do_nothing_situation_id"] = plan.do_nothing_situation_id
        body = {
            "org_id": situation.org_id,
            "schema_version": "expertise-package.v1",
            "trace_id": situation.trace_id,
            # NORMALIZED BEFORE HASHING, not after. `ExpertisePackage.__post_init__` runs
            # `_visibility` on this field anyway, but `expertise_id(body)` is computed on the raw
            # `body` one line down, and `canonicalize` has no rule for a pydantic model: L2's
            # admission gate hands `shadow_compile` the upgraded strict object, whose
            # `visibility` is a `Visibility` and not the mapping the v1 lane carried, so every
            # admitted situation died with `CanonicalizationError: unsupported semantic value:
            # Visibility` inside `compile` -- caught per situation, counted `error`, and the
            # compiled lane published nothing. Normalising here also makes the content address
            # what it always claimed to be: the id is now taken over the same shape the package
            # actually holds, so the two cannot disagree about what was hashed.
            "visibility": _visibility(situation.visibility),
            "situation_id": situation.id,
            "brain_snapshot_id": brain_snapshot_id,
            "capabilities": capabilities,
            "objects": objects,
            "expert_rules": expert_rules,
            "organization_rules": organization,
            "behavior_patterns": behavior,
            "adaptive_preferences": adaptive,
            "confidence_bp": confidence_bp,
            "evidence": evidence,
            "metadata": metadata,
        }
        return ExpertisePackage(id=expertise_id(body), **body)


__all__ = ["COMPILER_VERSION", "ExpertiseBuilder"]
