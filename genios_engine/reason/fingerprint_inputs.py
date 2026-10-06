"""The two fingerprint inputs outside a decision's request, read once per sweep (STEP-02).

`reason/fingerprint.MaterialInputs` carries what can change the right answer without touching the
request the decider is handed: the pack's `authority_revision`, and the human verdicts on the
subject's cards. This reads both for a whole tenant in two statements, so a sweep pays two round
trips for every subject it fingerprints, not two per subject.

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


@dataclass(frozen=True)
class InputsIndex:
    """One tenant's MaterialInputs, ready to hand out per subject."""

    revisions: Mapping[str, int] = field(default_factory=dict)
    by_rule: Mapping[tuple[str, str], tuple[str, ...]] = field(default_factory=dict)
    by_situation: Mapping[tuple[str, str], tuple[str, ...]] = field(default_factory=dict)

    def for_rule(self, pack_id: str, rule_id: str, node_id: str) -> MaterialInputs:
        return MaterialInputs(authority_revision=self.revisions.get(pack_id),
                              verdicts=self.by_rule.get((rule_id, node_id), ()))

    def for_situation(self, pack_id: str, situation_id: str, capability_id: str) -> MaterialInputs:
        return MaterialInputs(authority_revision=self.revisions.get(pack_id),
                              verdicts=self.by_situation.get((situation_id, capability_id), ()))


def read_inputs(conn, org_id: str) -> InputsIndex:
    """Every pack revision and every card verdict of one tenant, by the subject it is about."""
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
                       by_situation={k: tuple(sorted(v)) for k, v in by_situation.items()})
