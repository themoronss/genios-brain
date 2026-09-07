"""Adapt a Layer 3 ExpertisePackage into a Layer 4 CapabilityManifest.

This is the L3->L4 weld. The DomainCompiler emits knowledge (authored capabilities + objects +
four-brain rules); Layer 4's orchestrator reasons only over a `CapabilityManifest` — a DAG of
reasoning units plus plays. The authored corpus deliberately carries NO reasoner DAG (a capability
declares outcomes/failure-modes/KPIs, an object declares inference patterns), so this adapter
supplies a conservative default DAG and derives the load-bearing `required_fields` from the objects'
executable inference patterns. Package knowledge is content-hashed into the manifest version so an
overlay change yields new immutable bytes (same discipline as `legacy_capability_manifest`).

Knowledge-in, DAG-supplied. It never decides — it only shapes what Layer 4 will reason over.

WAVE Y1 · THE WELD (doc 03). Until this version, this adapter consumed `organization_rules` and
nothing else. Every authored rule, heuristic, mental model and decision framework — 446 of the
corpus's 712 artifacts — was retrieved, content-hashed into the manifest version, and dropped, and
the only receipt any of them got was `no_steps_artifact_unsupported`, which described this
function rather than the system. Law 4: knowledge is not shipped until Layer 4 can consume it,
TYPED. So each class now has a reader, and this module is where the three of them meet:

    rules (CLG-06)          `rule_compiler` -> compiled constraints; a blocking rule that fires
                            eliminates the plays in its own capability through `core.constraint`'s
                            existing tenant block seam, and names itself on the decision.
    heuristics (CLG-08)     `citations` -> quoted claims on the decision, byte-identical.
    models + frameworks     `citations` -> framing blocks: input material for the renderer.
    playbooks (CLG-07)      plays, with a cap that RANKS instead of sorting by filename.

`metadata["weld"]` carries all of it plus the receipt, and `decision_maker` reads three fields out
of it — nothing here decides anything, which is Law 1.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from genios_engine.contracts.domain_expertise import (
    BusinessSituationObject,
    ExpertisePackage,
    SituationContextSlice,
    require_weld_receipt,
)
from genios_engine.platform.canonical import stable_id
from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    FailurePolicy,
    Goal,
    PlayDefinition,
    ReasonerSpec,
)
from genios_engine.packs.compiler.context_adapter import ContextAdapter
from genios_engine.platform.canonical import semantic_hash

from .citations import UNDATED, bind_citations, descending_date
from .rule_compiler import artifact_class, compile_package_rules, play_id_for

ADAPTER_ID = "expertise_to_capability"
# 2.0.0 — the typed consumers (doc 03, wave Y1). Every artifact class the corpus carries now has
# a reader at this seam, so a manifest built by 1.0.0 and one built by this version are different
# objects even from identical knowledge: the version says which is which.
ADAPTER_VERSION = "2.0.0"

#: The weld's own schema name, carried in `manifest.metadata["weld"]` so a downstream reader can
#: tell a manifest that carries compiled doctrine from one that predates the typed consumers.
WELD_SCHEMA = "weld.v1"
_REQUIRED = FailurePolicy.REQUIRED


def _executable_required_fields(package: ExpertisePackage) -> tuple[str, ...]:
    """The graph fact paths Layer 4 must pull, taken only from EXECUTABLE inference patterns.

    `needs_signal` / `requires_signals` patterns name inputs that do not exist yet, so their
    fields are skipped — pulling them would fail the native context selector for no benefit.
    """
    fields: set[str] = set()
    for obj in package.objects:
        definition = obj.get("definition") if isinstance(obj, Mapping) else None
        patterns = (definition or {}).get("inference_patterns") or {}
        if not isinstance(patterns, Mapping):
            continue
        for group in ("deterministic", "heuristic"):
            for pattern in patterns.get(group, []) or []:
                if not isinstance(pattern, Mapping) or pattern.get("status") != "executable":
                    continue
                for path in pattern.get("evidence_fields", []) or []:
                    fields.add(str(path))
                for cond in pattern.get("when", []) or []:
                    if isinstance(cond, Mapping) and cond.get("path"):
                        fields.add(str(cond["path"]))
    return tuple(sorted(fields))


def _universal_required_fields(package: ExpertisePackage) -> tuple[str, ...]:
    """Fields EVERY executable pattern needs — the ones without which nothing can run.

    The selector should pull the union of what any pattern might use; the sufficiency gate must
    ask for far less. Stamping the union onto `core.context` made a single value-dependent pattern
    veto the whole capability: `expertise.opportunity` requires `deal.value` because one pattern
    reads it, and almost no email states a deal size, so all 18 situations on the design partner's
    org returned INSUFFICIENT_CONTEXT while every other field they needed was present.

    That contradicted this DAG's own stated intent — "a thin situation degrades confidence instead
    of being blocked out of reasoning entirely". A pattern whose inputs are absent simply does not
    fire; the patterns that CAN fire still should.
    """
    per_pattern: list[set[str]] = []
    for obj in package.objects:
        definition = obj.get("definition") if isinstance(obj, Mapping) else None
        patterns = (definition or {}).get("inference_patterns") or {}
        if not isinstance(patterns, Mapping):
            continue
        for group in ("deterministic", "heuristic"):
            for pattern in patterns.get(group, []) or []:
                if not isinstance(pattern, Mapping) or pattern.get("status") != "executable":
                    continue
                fields = {str(f) for f in pattern.get("evidence_fields", []) or []}
                fields |= {str(c["path"]) for c in pattern.get("when", []) or []
                           if isinstance(c, Mapping) and c.get("path")}
                if fields:
                    per_pattern.append(fields)
    if not per_pattern:
        return ()
    return tuple(sorted(set.intersection(*per_pattern)))


def _default_dag(required_fields: tuple[str, ...],
                 authored_priority_bp: int | None = None,
                 blocked_play_ids: tuple[str, ...] = ()) -> tuple[ReasonerSpec, ...]:
    """A conservative, situation-agnostic reasoning DAG that always terminates in a decision.

    understand (context) -> evaluate (risk) -> the mandatory REQUIRED constraint -> rank/score
    (priority + confidence, both sourced from risk) -> plan. No situation-specific gating unit, so
    a thin situation degrades confidence instead of being blocked out of reasoning entirely.
    """
    context = ReasonerSpec(
        "core.context", "1.0.0",
        required_fields=required_fields,
        failure_policy=_REQUIRED,
    )
    risk = ReasonerSpec(
        "core.risk", "1.0.0",
        dependencies=("core.context",),
        failure_policy=_REQUIRED,
    )
    # THE ORGANISATION BRAIN'S ONE HARD LEVER. `core.constraint` already reads
    # `blocked_play_ids` off its own config and eliminates those plays with a
    # `tenant_policy_block` row that `reason/store.py` and `reason/authority.py` both re-prove —
    # a seam built for exactly this and never wired to the brain that should drive it. An
    # organisation rule now removes an option BEFORE ranking, which is the difference between a
    # policy and a preference.
    constraint_config: dict[str, object] = {}
    if blocked_play_ids:
        constraint_config["blocked_play_ids"] = list(blocked_play_ids)
    constraint = ReasonerSpec(
        "core.constraint", "1.0.0",
        dependencies=("core.context",),
        input_kind="candidate_plays",
        output_kind="candidate_checks",
        config=constraint_config,
        failure_policy=_REQUIRED,
    )
    # `core.risk` measures pressure; it does not RULE on priority, so the declared-override path
    # found nothing and every compiled candidate fell back to a neutral 5000 utility — which is
    # why every compiled card scored exactly 50. The situation author already ruled: the corpus
    # carries 30 distinct `priority_bp` values across 48 situations. Handing that ruling to the
    # unit as config is what turns it back into a ranking.
    priority_config: dict[str, object] = {"source_reasoner": "core.risk"}
    if authored_priority_bp is not None:
        priority_config["authored_priority_bp"] = int(authored_priority_bp)
    priority = ReasonerSpec(
        "core.priority", "1.0.0",
        dependencies=("core.risk", "core.constraint"),
        config=priority_config,
        failure_policy=_REQUIRED,
    )
    confidence = ReasonerSpec(
        "core.confidence", "1.0.0",
        dependencies=("core.risk",),
        config={"source_reasoner": "core.risk"},
        failure_policy=_REQUIRED,
    )
    planning = ReasonerSpec(
        "core.planning", "1.0.0",
        dependencies=("core.constraint", "core.priority", "core.confidence"),
        input_kind="ranked_candidates",
        output_kind="planning_checks",
        failure_policy=_REQUIRED,
    )
    return (context, risk, constraint, priority, confidence, planning)


#: How many plays a manifest carries. A cap is legitimate (the Decision Maker ranks a small
#: candidate set, not a corpus); a SILENT cap is not — see `_plays`' receipt fields.
#: How many authored strategies may reach Layer 4 as candidates.
#:
#: Raised from 4. A play is a CANDIDATE, not a card — the Decision Maker picks one — so the cap
#: was never limiting output, it was limiting choice, and it did so by dropping whatever sorted
#: last alphabetically. `account_admin` routes thirteen capabilities and therefore thirteen
#: playbooks: nine authored strategies were cut by rule id, which is file-naming, not judgment.
#:
#: Still bounded, and deliberately. An unbounded list would let one wide route dominate the
#: reasoning budget, and `play_receipt` records anything still cut — a silent truncation is the
#: failure this number is meant to make visible, not the number itself.
MAX_PLAYS = 16


def _learned_play_efficacy(package: ExpertisePackage) -> dict[str, tuple[int, str]]:
    """This tenant's OWN measured success rate per play — {play_id: (success_bp, entry_id)}.

    THE CONVENTION IS L6's, NOT INVENTED HERE. `feedback/units.unit_recommendation_learning`
    already publishes into the ADAPTIVE brain, one entry per play, carrying
    ``{"play": <id>, "success_rate_bp": ..., "attention_per_outcome_bp": ..., "efficacy_bp": ...}``
    — real outcomes, labelled, over a minimum observation count the learning policy enforces. It
    has been writing that shape into `learned_brain_entries` and nothing has ever read it.

    `success_rate_bp` rather than `efficacy_bp` deliberately. Efficacy discounts success by the
    attention the play cost, which is a judgment about whether a play is WORTH it — and that
    judgment belongs to the ranking model, which already penalises `effort_bp` on its own terms.
    Feeding efficacy here would apply the attention penalty twice.
    """
    learned: dict[str, tuple[int, str]] = {}
    for entry in package.adaptive_preferences or ():
        if not isinstance(entry, Mapping):
            continue
        value = entry.get("value")
        if not isinstance(value, Mapping):
            continue
        play_id = str(value.get("play") or "").strip()
        rate = value.get("success_rate_bp")
        if not play_id or isinstance(rate, bool) or not isinstance(rate, int):
            continue
        learned[play_id] = (max(0, min(10_000, rate)), str(entry.get("entry_id") or ""))
    return learned


def _blocked_play_ids(package: ExpertisePackage) -> tuple[str, ...]:
    """Plays this ORGANISATION has forbidden, for `core.constraint`'s tenant block list.

    The constraint unit already owns this seam and documents it as "a hard, id-level retirement
    that a tenant can apply without touching authored expertise" — it emits a `tenant_policy_block`
    ELIMINATE row, which `reason/store.py` and `reason/authority.py` both re-prove. So an
    organisation rule reaches the decision through a path that was BUILT for it and that two
    independent verifiers already understand; no new check row, no frozen-shape change, no replay
    break. It was simply never connected to the organisation brain.

    Only permission-axis entries may block. `packs/compiler/runtime_brains._PERMISSION_CATEGORIES`
    is the same list the compiler uses to decide which entries carry permission authority at all,
    read from there rather than restated, so the two cannot drift into disagreeing about what
    counts as a policy.
    """
    from genios_engine.packs.compiler.runtime_brains import _PERMISSION_CATEGORIES

    blocked: set[str] = set()
    for entry in package.organization_rules or ():
        if not isinstance(entry, Mapping):
            continue
        value = entry.get("value")
        if not isinstance(value, Mapping):
            continue
        category = str(value.get("category") or value.get("kind") or "").lower()
        if category not in _PERMISSION_CATEGORIES:
            continue
        named = value.get("blocked_play_ids") or value.get("blocks_plays")
        if isinstance(named, str):
            named = [named]
        for item in list(named or ()) + [value.get("blocks_play")]:
            if isinstance(item, str) and item.strip():
                blocked.add(item.strip())
    return tuple(sorted(blocked))


#: Which artifact classes are consumed by a reader OTHER than the play converter, and by which
#: one. This mapping is the whole of the J1 gate's "`no_steps_artifact_unsupported` receipts on
#: rules / heuristics / models / frameworks: 0" — those four now have consumers, so the receipt
#: that said nobody read them is replaced by a receipt naming who does.
_CONSUMED_ELSEWHERE: Mapping[str, str] = {
    "rule": "consumed_as_compiled_constraint",
    "heuristic": "consumed_as_citation",
    "mental_model": "consumed_as_framing_block",
    "decision_framework": "consumed_as_framing_block",
}

#: Sorts last in the recency term. THE citation binder's constant, imported rather than restated,
#: so "undated" cannot come to mean two different positions in two rankings.
_UNDATED = UNDATED


def _capability_recency(package: ExpertisePackage) -> dict[str, str]:
    """capability id -> the date its document was last stamped.

    Doc 03 asks the play cap to rank on "capability admission recency (re-stamped = maintained)".
    The `admission` block holds a content hash and NO timestamp — re-stamping proves the reviewer
    saw the current bytes, not when — so the date the corpus actually carries is
    `metadata.last_updated`, which `_tools/admit.py` and the author move together. Named here
    rather than quietly substituted: this is a proxy, and a reader deserves to know which.
    """
    out: dict[str, str] = {}
    for capability in package.capabilities or ():
        if not isinstance(capability, Mapping):
            continue
        definition = capability.get("definition")
        metadata = definition.get("metadata") if isinstance(definition, Mapping) else None
        last_updated = (metadata or {}).get("last_updated") if isinstance(metadata, Mapping) else None
        out[str(capability.get("id") or "")] = str(last_updated or _UNDATED)
    return out


def _authored_play_priority(definition: Mapping[str, Any]) -> int | None:
    """A playbook's own declared priority, in basis points, or None when it declares none.

    Nothing in the shipped corpus declares one. The term exists because doc 03 names it and
    because an author who wants to order two plays inside one capability has nowhere else to say
    so; the receipt reports how many plays used it, so "this rank term is currently constant" is a
    number rather than a thing to rediscover.
    """
    metadata = definition.get("metadata") if isinstance(definition, Mapping) else None
    raw = (metadata or {}).get("priority_bp") if isinstance(metadata, Mapping) else None
    if isinstance(raw, bool) or not isinstance(raw, int) or not 0 <= raw <= 10_000:
        return None
    return raw


def _plays(package: ExpertisePackage) -> tuple[tuple[PlayDefinition, ...], dict]:
    """Playbook `expert_rules` (definitions carrying steps) become read-only review plays —
    plus a RECEIPT of everything this conversion refused or cut.

    The old shape was three silent judgments in a row: a rule without steps was `continue`d (no
    trace), the fifth play onward was `break`ed (no trace), and an empty result appended a
    hardcoded "review the situation" (indistinguishable from authored content). Consequence,
    `[MODELLED]` but structural: a 1,748-file corpus could compile successfully, hash into a new
    manifest version, and still emit one generic play — activation would LOOK successful while
    producing generic output, which is precisely the state L3's flip must be able to detect.

    CLG-07 · THE CAP IS LEGITIMATE; ALPHABETICAL SELECTION WAS NOT. Ordering was deterministic
    (rule id, not corpus iteration order) and that fixed the enumeration bug — but it left the
    SELECTION to file naming. On the design partner's `deal` route that is not academic: 21
    playbooks compile, sixteen survive, and the five cut are `need_analysis`, `pipeline_management`,
    `procurement`, `stakeholder_mapping` and `value_proposition` — four of which declare the very
    situation that fired — while five `icp_definition` plays survive because "i" sorts before "n".
    A cut decided by the first letter of a filename is not judgment.

    Plays are now ranked by what the author actually declared, in doc 03's order:

      1. SITUATION FIT   the play's `when_to_use.situations` names one of the situations that
                         matched. The strongest authored statement of relevance there is.
      2. ADMISSION RECENCY  the owning capability's `metadata.last_updated` — a re-stamped
                         capability is a maintained one. The `admission` block itself carries only
                         a content hash and no date, so this is the recency signal the corpus
                         actually holds, named here rather than implied.
      3. AUTHORED PRIORITY  `metadata.priority_bp` on the playbook, if declared. NOTHING in the
                         shipped corpus declares one today, so this term is currently constant and
                         the receipt says so with a count rather than leaving it to be discovered.
      4. RULE ID         the final tie-break, LAST — where a deterministic tie-break belongs, not
                         first, where it was the selector.

    Everything Layer 3 supplies is advisory knowledge, so every play is read_only and leaves any
    outreach to explicit human approval.
    """
    situations = frozenset(str(item) for item in
                           (package.metadata.get("matched_situation_ids") or ()))
    recency = _capability_recency(package)
    candidates: list[tuple[tuple, str, PlayDefinition]] = []
    skipped: dict[str, str] = {}
    seen: set[str] = set()
    fits = 0
    prioritised = 0
    efficacy = _learned_play_efficacy(package)
    for position, rule in enumerate(package.expert_rules):
        if not isinstance(rule, Mapping):
            skipped[f"unmapped_{position}"] = "not_a_mapping"
            continue
        rule_id = str(rule.get("id") or f"rule_{position}")
        definition = rule.get("definition") or {}
        klass = artifact_class(rule)
        if klass in _CONSUMED_ELSEWHERE:
            # THE RECEIPT THAT USED TO SAY `no_steps_artifact_unsupported` FOR ALL OF THESE. It
            # was accurate about this function and wrong about the system: a heuristic has no steps
            # because it is a claim, not a procedure, and it now travels as a citation. Naming the
            # consumer per class is what makes "5 of 5 artifact classes have a typed consumer"
            # readable from the receipt instead of assertable only in a review.
            skipped[rule_id] = _CONSUMED_ELSEWHERE[klass]
            continue
        raw_steps = definition.get("steps") if isinstance(definition, Mapping) else None
        if not raw_steps:
            # A PLAYBOOK with no steps is a real authoring defect (the schema requires them); an
            # artifact class this adapter has never heard of is the honest survivor of the old
            # receipt, and it stays, because the day a sixth class is authored this is the line
            # that says nobody consumes it.
            skipped[rule_id] = ("playbook_without_steps" if klass == "playbook"
                                else "no_steps_artifact_unsupported")
            continue
        steps = tuple(
            str(step.get("description") or step.get("name")) if isinstance(step, Mapping)
            else str(step)
            for step in raw_steps
        )
        steps = tuple(s for s in steps if s and s != "None")
        if not steps:
            skipped[rule_id] = "steps_empty_after_normalisation"
            continue
        # ONE spelling of a play id, shared with the rule compiler's scope map. Two copies of
        # this line would let a rule's blast radius and the manifest's play list disagree about
        # what the same playbook is called, which is an elimination pointing at nothing.
        play_id = play_id_for(rule_id)
        if play_id in seen:
            skipped[rule_id] = "duplicate_play_id"
            continue
        seen.add(play_id)
        # THE ORG'S OWN MEASURED SUCCESS RATE, where it has one. `success_probability_bp` is a
        # weighted term in `decision_maker._weighted_utility`, and every compiled play carried the
        # 5,000bp default — so the same expertise ranked its options identically for a tenant
        # where a play works and one where it does not. This is the whole of "it learns how we
        # operate", and it is not a new mechanism: the field already means exactly this, the
        # learning already measured it, and the two had simply never been joined.
        learned = efficacy.get(play_id)
        identity = definition.get("identity") if isinstance(definition, Mapping) else {}
        owner = str((identity or {}).get("owner_capability") or "")
        declared = frozenset(str(item) for item in
                             ((definition.get("when_to_use") or {}).get("situations") or ()))
        fit = bool(declared & situations)
        priority_bp = _authored_play_priority(definition)
        fits += int(fit)
        prioritised += int(priority_bp is not None)
        rank = (0 if fit else 1, descending_date(recency.get(owner, _UNDATED)),
                -(priority_bp or 0), play_id)
        candidates.append((rank, play_id, PlayDefinition(
            play_id, "1.0.0", str(definition.get("name") or play_id)[:200],
            steps=steps,
            read_only=True,
            success_probability_bp=learned[0] if learned else 5_000,
            tags=("human_approval", "playbook"),
            metadata={"source": "expert_playbook", "external_recipient_required": False,
                      # Provenance on the play itself, so an auditor reading a candidate can see
                      # WHICH learned entry moved it rather than inferring it from a score.
                      **({"learned_success_from": learned[1]} if learned else {})},
        )))

    candidates.sort(key=lambda item: item[0])
    plays = [play for _, _, play in candidates[:MAX_PLAYS]]
    truncated = [play_id for _, play_id, _ in candidates[MAX_PLAYS:]]
    for play_id in truncated:
        skipped[play_id] = f"over_play_cap_{MAX_PLAYS}"

    receipt = {
        "authored_rules": len(package.expert_rules),
        "plays_emitted": len(plays),
        # CLG-07's own numbers. "Ranked, not alphabetical" is only a claim if the ranking's inputs
        # are visible: how many plays declared the situation that fired, how many the corpus gave
        # an authored priority (zero today), and which plays the ranked cap actually cut.
        "plays_situation_fit": fits,
        "plays_with_authored_priority": prioritised,
        "plays_truncated": sorted(truncated),
        "selection": "situation_fit, capability recency, authored priority, then rule id",
        # Which plays this tenant's own outcomes re-scored, and which kept the 5,000bp default.
        # A number, not a boolean: "the adaptive brain influenced this decision" is only a real
        # claim if you can say how many of the options it touched.
        "plays_rescored_by_learning": sorted(
            play.play_id for play in plays if play.metadata.get("learned_success_from")),
        "skipped_rule_ids": dict(sorted(skipped.items())),
        "truncation_reason": (f"ranked cap at {MAX_PLAYS} plays: situation fit first, "
                              "rule id last" if truncated else None),
        "generic_fallback_used": not plays,
    }
    if not plays:
        plays.append(PlayDefinition(
            "review_situation", "1.0.0", "Review the compiled expertise",
            steps=(
                "Review the compiled expert, organization, behavior and adaptive knowledge.",
                "Choose the safest next step with the owner.",
                "Leave any outreach or system change for explicit human approval.",
            ),
            read_only=True,
            # `review` AND `non_prescriptive`: this play was written by the ADAPTER, not by any
            # expert, and a card built from it must never render as a confident instruction —
            # that would be the compiler failing while its output reads as advice.
            tags=("human_approval", "review", "non_prescriptive"),
            metadata={"source": "adapter_default", "external_recipient_required": False},
        ))
    return tuple(plays), receipt


@dataclass(frozen=True, slots=True)
class Weld:
    """Everything the typed consumers produced for one package — CLG-06, CLG-07 and CLG-08.

    One object rather than three return values because the three consumers are not independent:
    a rule's scope is resolved against the plays that survived the cap, a citation is refused when
    it contradicts a rule that fired, and the receipt has to add up across all of them. Assembling
    them in one place is what makes "every refusal named and counted" checkable in one read.
    """

    compiled_constraints: tuple[Mapping[str, Any], ...] = ()
    citations: tuple[Mapping[str, Any], ...] = ()
    framing_blocks: tuple[Mapping[str, Any], ...] = ()
    rule_verdicts: tuple[Mapping[str, Any], ...] = ()
    conflicts: tuple[Mapping[str, Any], ...] = ()
    abstain_on_conflict: bool = False
    blocked_play_ids: tuple[str, ...] = ()
    receipt: Mapping[str, Any] = field(default_factory=dict)
    bound: bool = False

    def as_metadata(self) -> dict[str, Any]:
        """The manifest-borne form. Plain lists and dicts, because this crosses `jsonb` on the way
        into `reasoning_capability_snapshots` and comes back through `capability_from_manifest`;
        `freeze` normalises list and tuple identically, so the round trip is hash-stable."""
        return {
            "schema": WELD_SCHEMA,
            "adapter_version": ADAPTER_VERSION,
            # False when no situation slice reached this adapter — every rule is then `unevaluable`
            # naming `situation_slice_not_supplied`, and this flag is what stops a reader taking
            # that for "no rule applied".
            "bound": self.bound,
            "compiled_constraints": [dict(item) for item in self.compiled_constraints],
            "citations": [dict(item) for item in self.citations],
            "framing_blocks": [dict(item) for item in self.framing_blocks],
            "rule_verdicts": [dict(item) for item in self.rule_verdicts],
            "conflicts": [dict(item) for item in self.conflicts],
            "abstain_on_conflict": self.abstain_on_conflict,
            "blocked_play_ids": list(self.blocked_play_ids),
            "weld_receipt": dict(self.receipt),
        }


def weld_package(package: ExpertisePackage, *, declared_play_ids: frozenset[str],
                 play_receipt: Mapping[str, Any],
                 adapter: ContextAdapter | None = None) -> Weld:
    """Run every typed consumer over one package and account for the result.

    ORDER IS LOAD-BEARING. Plays are already chosen when this runs, so a blocking rule can only
    eliminate a candidate that exists (`declared_play_ids`). Rules are compiled and bound before
    citations, so the binder knows which doctrine fired and can refuse a claim that denies it.
    The receipt is built last, from what the other two actually produced, and is validated by the
    contract's `require_weld_receipt` — all eight counters, zeros included, arithmetic checked.
    """
    rules = compile_package_rules(package, adapter, declared_play_ids=declared_play_ids)
    binding = bind_citations(package, rules.verdicts)

    refusals = dict(rules.refusals)
    for reason, count in binding.refusals.items():
        refusals[reason] = refusals.get(reason, 0) + count

    receipt = require_weld_receipt({
        "rules_compiled": len(rules.constraints),
        "rules_fired": len(rules.fired),
        "rules_unevaluable": len(rules.unevaluable),
        "rules_skipped": len(rules.skipped),
        "citations_attached": len(binding.citations),
        "citations_truncated": binding.citations_truncated,
        "plays_selected": int(play_receipt.get("plays_emitted") or 0),
        "plays_over_cap": len(play_receipt.get("plays_truncated") or ()),
        # Beyond the eight the contract fixes. Framing blocks are capped by this adapter rather
        # than by the contract, so their truncation is counted here or nowhere.
        "framing_blocks_attached": len(binding.framing_blocks),
        "framing_blocks_truncated": binding.framing_truncated,
        "rules_blocking_fired": sum(1 for verdict in rules.verdicts if verdict.blocks),
        "conflicts_named": len(binding.conflicts),
        "by_class": binding.by_class,
        "refusals": [{"reason": reason, "count": count}
                     for reason, count in sorted(refusals.items())],
        "skipped_rule_ids": dict(rules.skipped),
    }, "weld receipt")

    return Weld(
        compiled_constraints=rules.constraints,
        citations=binding.citations,
        framing_blocks=binding.framing_blocks,
        rule_verdicts=tuple(verdict.as_record() for verdict in rules.verdicts),
        conflicts=binding.conflicts,
        abstain_on_conflict=binding.abstain,
        blocked_play_ids=rules.blocked_play_ids,
        receipt=receipt,
        bound=adapter is not None,
    )


def _goal(package: ExpertisePackage, situation_type: str) -> Goal:
    """The FIRST capability's question is the statement; the rest become success criteria.

    Taking only the first and dropping the others silently meant a package compiled from three
    capabilities looked identical to one compiled from one — the other two questions vanished
    without a trace. They are secondary by position (the router ordered them), not disposable.
    """
    questions = []
    for capability in package.capabilities:
        definition = capability.get("definition") if isinstance(capability, Mapping) else None
        question = (definition or {}).get("question")
        if question:
            questions.append(str(question))
    statement = questions[0] if questions else (
        f"Resolve the {situation_type} situation using the compiled expertise.")
    return Goal(
        f"expertise.{situation_type}",
        statement,
        success_criteria=tuple(questions[1:4]),
        constraints=("Never send or mutate an external system autonomously.",),
    )


def expertise_capability_manifest(
    package: ExpertisePackage, *, root_entity_type: str,
    live_delivery_enabled: bool = False,
    situation: BusinessSituationObject | None = None,
    context: SituationContextSlice | None = None,
) -> CapabilityManifest:
    """One ExpertisePackage -> one CapabilityManifest driving Layer 4's reasoning.

    ``situation`` and ``context`` are what CLG-06 BINDS against, and they are parameters rather
    than something read off the package because the package does not carry them: an
    `ExpertisePackage` holds the knowledge that was selected, not the facts it was selected for.
    `ContextAdapter` is the compiler's own three-state evaluator and needs both — and it is the
    only thing that can tell an UNKNOWABLE absence from an unmet one, which is the difference
    between a blocking rule firing and a blocking rule abstaining. `domain_shadow` has both in
    scope at the call site.

    Omitting them is legal and honest, not silent: every rule is then `unevaluable` naming
    `situation_slice_not_supplied`, `metadata["weld"]["bound"]` is False, and nothing is
    eliminated. A caller that only wants the manifest's shape gets it without the weld claiming a
    binding it never performed.

    ``live_delivery_enabled`` defaults to False — the measurement pass must stay advisory. It is
    True only on the cutover path, because the delivery authority predicate reads it directly
    (``rcap.manifest->'live_delivery_enabled' = 'true'``): a signal whose capability snapshot says
    False can never become a card, however complete the rest of its audit bundle is.
    """
    situation_type = str(package.metadata.get("situation_type") or "situation")
    plays, play_receipt = _plays(package)
    adapter = ContextAdapter(situation, context) if situation is not None else None
    weld = weld_package(package, declared_play_ids=frozenset(play.play_id for play in plays),
                        play_receipt=play_receipt, adapter=adapter)
    # TWO SOURCES, ONE BLOCK LIST. The organisation brain's permission entries and the corpus's
    # own blocking doctrine both reach `core.constraint` through the seam it already owns and that
    # `reason/store.py` and `reason/authority.py` already re-prove. Merged and sorted so the
    # config is a property of what was decided rather than of which source was read first.
    blocked_plays = tuple(sorted(set(_blocked_play_ids(package)) | set(weld.blocked_play_ids)))
    domain_ids = package.metadata.get("domain_ids") or ()
    domain = str(domain_ids[0]) if domain_ids else "general"
    required_fields = _executable_required_fields(package)
    # SELECT the union, GATE on the intersection — two different questions that shared one answer.
    # The manifest's own `required_fields` is BOTH: the orchestrator gates on it
    # (`initial_missing`) and native's selector seeds from it. It carries the gate set, and the
    # union reaches the selector through the reasoner specs and play preconditions, which
    # `_selected_fields` unions in anyway. So nothing stops being pulled; a capability simply
    # stops being vetoed by a field only one of its patterns reads.
    gate_fields = _universal_required_fields(package)

    knowledge_hash = semantic_hash({
        "capabilities": package.capabilities,
        "objects": package.objects,
        "expert_rules": package.expert_rules,
        "organization_rules": package.organization_rules,
        "behavior_patterns": package.behavior_patterns,
        "adaptive_preferences": package.adaptive_preferences,
        "brain_snapshot_id": package.brain_snapshot_id,
    })

    manifest = CapabilityManifest(
        capability_id=f"expertise.{situation_type}",
        # Provisional — replaced below once the manifest's own content can be hashed.
        version=f"exp.{knowledge_hash[:16]}",
        domain=domain,
        root_entity_type=str(root_entity_type or "entity"),
        goal=_goal(package, situation_type),
        reasoners=_default_dag(gate_fields, package.metadata.get("authored_priority_bp"),
                               blocked_play_ids=blocked_plays),
        plays=plays,
        required_fields=gate_fields,
        selection_fields=required_fields,
        policies=("read_only", "human_approval_required", "evidence_required"),
        live_delivery_enabled=live_delivery_enabled,   # advisory by default; True only on cutover
        do_nothing_consequence=(
            f"The {situation_type} situation is left unaddressed while its evidence compounds."
        ),
        metadata={
            "adapter": ADAPTER_ID,
            "adapter_version": ADAPTER_VERSION,
            # What the play conversion refused or cut — so "compiled fine, emitted one generic
            # play" is a readable state instead of a successful-looking silence.
            "play_receipt": play_receipt,
            # THE WELD (doc 03). Compiled constraints, quoted citations, framing blocks, the
            # per-rule verdicts the Decision Maker turns into `constraints_applied` once candidate
            # ids exist, and the receipt that says what every artifact class contributed or why it
            # did not. This is the structure that makes Law 4 checkable: knowledge that is not
            # here was not consumed.
            "weld": weld.as_metadata(),
            "situation_type": situation_type,
            # The situation's own card copy. Delivery reads it off `rcap.manifest` — the same
            # audited snapshot the authority predicate already joins — so a card's wording is
            # pinned to the capability version that produced it and cannot drift underneath it.
            "render": package.metadata.get("render"),
            "render_situation_id": package.metadata.get("render_situation_id"),
            "expertise_id": package.id,
            "brain_snapshot_id": package.brain_snapshot_id,
            "object_coverage_bp": package.metadata.get("object_coverage_bp"),
            "knowledge_hash": knowledge_hash,
            "schema": "capability.v1",
            # The three learned brains, TYPED — not only folded into `knowledge_hash`.
            #
            # Organization, Behavior and Adaptive values entered the decision at exactly two
            # places, both identity-only: the manifest `version` string and this `knowledge_hash`.
            # A repo-wide grep for the three names under `reason/` found zero read sites. So a
            # tenant could approve an organization rule, watch the hash change, and nothing about
            # any decision would differ — governance and personalisation were provenance theatre.
            #
            # Carrying them as structure is what lets a reasoner CONSULT them. Counts travel
            # alongside so "did any brain actually influence this?" is answerable from the
            # manifest rather than by diffing hashes between runs.
            "brains": {
                "organization": list(package.organization_rules or ()),
                "behavior": list(package.behavior_patterns or ()),
                "adaptive": list(package.adaptive_preferences or ()),
            },
            "brain_influence": {
                "organization": len(package.organization_rules or ()),
                "behavior": len(package.behavior_patterns or ()),
                "adaptive": len(package.adaptive_preferences or ()),
                # True when every brain is empty: the manifest is authored expertise only, and a
                # personalisation claim about this decision would be false.
                "hash_only": not any((package.organization_rules,
                                      package.behavior_patterns,
                                      package.adaptive_preferences)),
                # WHAT THE BRAINS ACTUALLY DID, which is a different question from how many
                # entries came along. Carrying only the counts was how "the brains reached the
                # decision" stayed true-sounding and unfalsifiable for as long as it did: a
                # tenant could hold forty entries, every one of them about a play this capability
                # does not declare, and the count would say forty.
                "plays_blocked_by_organization": list(blocked_plays),
                "plays_rescored_by_adaptive": play_receipt["plays_rescored_by_learning"],
                # Behavior has no consumer yet and says so. The three brains are not equivalent —
                # organization states policy, adaptive measures outcomes, and behavior describes
                # how the org works — and the third has no seam in this DAG that would not be an
                # invented one. Named as absent rather than implied to be working.
                "behavior_consumed": False,
            },
        },
    )

    # Re-version on the MANIFEST's content, not only the knowledge's.
    #
    # `knowledge_hash` covers the compiled expertise, but the manifest built from it also varies
    # with the situation: goal, root entity type, the plays that survived conversion, the gate and
    # selection sets. Two situations therefore produced two different manifests under one version,
    # and the audit store's immutability guard correctly refused the second — "immutable capability
    # version mismatch". A version that does not move when the thing it names moves is not a
    # version. Two hashes, not one: knowledge first so the lineage stays legible at a glance,
    # manifest second so the identity is honest.
    content = stable_id("capmanifest", manifest.to_semantic_dict()).split("_", 1)[-1]
    return replace(manifest, version=f"exp.{knowledge_hash[:12]}.{content[:12]}")


__all__ = ["ADAPTER_ID", "ADAPTER_VERSION", "MAX_PLAYS", "WELD_SCHEMA", "Weld",
           "expertise_capability_manifest", "weld_package"]
