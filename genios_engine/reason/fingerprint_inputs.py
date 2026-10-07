"""The fingerprint inputs outside a decision's request, read once per sweep (STEP-02, STEP-07).

`reason/fingerprint.MaterialInputs` carries what can change the right answer without touching the
request the decider is handed: the pack's `authority_revision`, the human verdicts on the subject's
cards, and the company brief's version. This reads them for a whole tenant once, so a sweep pays the
same few round trips however many subjects it fingerprints.

THE BRIEF IS READ WHERE THE PROMPTS READ IT — `platform/company_brief.current`, the per-process copy.
That copy only moves forward in time, so a sweep's fingerprint can name an OLDER brief than the one
its decider's prompt read — and then the next sweep decides once more, the harmless direction — but
never a newer one, which would record a decision as made under a brief it never saw.

A verdict is about the subject its card's signal names — the legacy lane's (rule, node), or the
compiled lane's (situation, capability). Keyed both ways, because a compiled signal also carries the
rule id it was emitted under (the capability id's last segment) and the node it anchors on.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field

from sqlalchemy import text

from genios_engine.reason.fingerprint import MaterialInputs, verdict_key


def decider_identity(org_id: str) -> str:
    """Who decides this tenant's subjects: the formula, or the LLM decider and the model it runs.

    `llm_decision_maker.enabled_for` is the switch every lane reads; R-1 runs on the same switch in
    the orchestrator, so one word covers both. A caller that also hands R-1 to a lane (the compiled
    lane's interpreter) adds `+r1` itself.
    """
    from genios_engine.platform.config import get_settings
    from genios_engine.reason import llm_decision_maker

    if not llm_decision_maker.enabled_for(org_id):
        return "formula"
    settings = get_settings()
    model = (str(getattr(settings, "l4_llm_decision_model", "") or "").strip()
             or str(getattr(settings, "anthropic_model", "") or ""))
    return f"llm:{model}"


@dataclass(frozen=True)
class InputsIndex:
    """One tenant's MaterialInputs, ready to hand out per subject."""

    revisions: Mapping[str, int] = field(default_factory=dict)
    by_rule: Mapping[tuple[str, str], tuple[str, ...]] = field(default_factory=dict)
    by_situation: Mapping[tuple[str, str], tuple[str, ...]] = field(default_factory=dict)
    decider: str = "formula"
    brief: str = ""

    def for_rule(self, pack_id: str, rule_id: str, node_id: str) -> MaterialInputs:
        return MaterialInputs(authority_revision=self.revisions.get(pack_id),
                              verdicts=self.by_rule.get((rule_id, node_id), ()),
                              decider=self.decider, brief=self.brief)

    def for_situation(self, pack_id: str, situation_id: str, capability_id: str, *,
                      interpreted: bool = False) -> MaterialInputs:
        return MaterialInputs(authority_revision=self.revisions.get(pack_id),
                              verdicts=self.by_situation.get((situation_id, capability_id), ()),
                              decider=self.decider + ("+r1" if interpreted else ""),
                              brief=self.brief)


def read_inputs(conn, org_id: str) -> InputsIndex:
    """Every pack revision and every card verdict of one tenant, by the subject it is about, and the
    version of the company brief its prompts read."""
    from genios_engine.platform.company_brief import current
    revisions = {r.pack_id: int(r.authority_revision) for r in conn.execute(text(
        "select pack_id, authority_revision from tenant_packs where org_id = :o"), {"o": org_id})}
    by_rule: dict[tuple[str, str], list[str]] = defaultdict(list)
    by_situation: dict[tuple[str, str], list[str]] = defaultdict(list)
    for r in conn.execute(text(
            "select s.rule_id, s.subject_node_id, s.situation_id, s.capability_id, "
            "       v.feedback_id, v.verdict_version "
            "  from card_feedback_verdicts v "
            "  join cards c on c.org_id = v.org_id and c.card_id = v.card_id "
            "  join signals s on s.org_id = c.org_id and s.signal_id = c.signal_id "
            " where v.org_id = :o"), {"o": org_id}):
        key = verdict_key(r.feedback_id, r.verdict_version)
        if r.rule_id and r.subject_node_id:
            by_rule[(r.rule_id, r.subject_node_id)].append(key)
        if r.situation_id and r.capability_id:
            by_situation[(r.situation_id, r.capability_id)].append(key)
    return InputsIndex(revisions=revisions,
                       by_rule={k: tuple(sorted(v)) for k, v in by_rule.items()},
                       by_situation={k: tuple(sorted(v)) for k, v in by_situation.items()},
                       decider=decider_identity(org_id),
                       brief=current(getattr(conn, "engine", conn), org_id).version)
