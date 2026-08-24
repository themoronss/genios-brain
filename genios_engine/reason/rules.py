from __future__ import annotations

from dataclasses import dataclass, field

# Rules are DATA that live in an L4 pack (see genios_engine/packs/sales_v1.py). The engine
# holds NO domain rules — it builds Rule objects from the effective pack config at eval time.


@dataclass
class Rule:
    id: str
    level: str
    scope: str                       # node_type this rule applies to
    when: list[dict]                 # all() conditions
    urgency: dict                    # {type: elapsed|countdown, path, h}
    reason_code: str
    play: str | None = None
    cooldown_hours: int = 72
    linked_deal: bool = True
    version: int = 1
    evidence_fields: list[str] = field(default_factory=list)


def rule_from_dict(d: dict) -> Rule:
    return Rule(id=d["id"], level=d.get("level", "prescriptive"), scope=d["scope"],
                when=d["when"], urgency=d["urgency"], reason_code=d["reason_code"],
                play=d.get("play"), cooldown_hours=int(d.get("cooldown_hours", 72)),
                linked_deal=bool(d.get("linked_deal", True)), version=int(d.get("version", 1)),
                evidence_fields=list(d.get("evidence_fields", [])))


def rules_for_scope(rules: list[Rule], node_type: str) -> list[Rule]:
    return [r for r in rules if r.scope == node_type]
