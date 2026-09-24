"""L2-3 · the slice fields nothing writes — declared, with a reason and what would end them.

⛔ **`SituationContextSlice.evidence` IS WRITTEN BY NOTHING, READ BY NOTHING, AND IS PART OF THE
CONTENT ADDRESS.** Measured 2026-09-24:

* `build_context_slice` has no `evidence` parameter, so no caller can supply one;
* no consumer reads `.evidence` — `context_adapter`, `expertise_builder`, `capability_resolver`,
  `reason/adapters/expertise` and `situation_projection` between them read twelve other fields;
* `to_semantic_dict` includes it, so it pins the slice hash at `()` on every slice ever made.

That is a field in exactly the state L2-0 spent a whole step on — **except here it is empty by
design, and a design nobody wrote down is indistinguishable from an oversight.** This module is
the writing-down, in the idiom this repository already uses three times:
`patterns/routing.UNROUTED_PATTERN_TYPES`, `lane_health.SILENT_LANES` and
`context/domain_silence.DARK_DOMAINS` — *declared, with a reason and a mover*, checked in both
directions.
"""
from __future__ import annotations

import inspect

EMPTY_BY_DESIGN: dict[str, str] = {
    "evidence": (
        "⛔ THE RECEIPTS ALREADY TRAVEL, INSIDE THE FACTS. Every entry in `facts` and "
        "`neighbor_facts` carries `source_ref_id`, `fact_version_id`, `independence_group` and "
        "`src_count` — the pointer to what the fact rests on — so a second list of the same "
        "pointers would be the duplication L2-1 spent a step removing at the type level. "
        "AND FILLING IT IS NOT FREE: `to_semantic_dict` hashes it, so every slice hash, every "
        "expertise package content address and every stored package row would move at once. The "
        "last time an address churned, that table reached 4,086 rows and 995 MB — 67% of the "
        "whole database for 127 situations — and the project crossed its disk quota into "
        "read-only. ENDS WHEN: a consumer needs a receipt the fact does not already carry, and "
        "the one-time re-address is measured and accepted. Not before."),
    # ⛔ FOUND BY THIS GUARD ON ITS FIRST RUN — and it is correct rather than missing.
    "schema_version": (
        "THE CONTRACT PINS IT, NOT THE CALLER. `SITUATION_CONTEXT_VERSION` is the dataclass "
        "default, so the version a slice claims is decided in exactly one place. A builder that "
        "passed it would be a second copy of the same constant, and the two would eventually "
        "disagree about which schema a stored slice obeys — which is the defect that made L1's "
        "step 18 return an empty dict rather than a dict of Nones. ENDS WHEN: a caller must "
        "produce a slice at a version other than the current one, which nothing does today."),
}


def reason_for(field: str | None) -> str | None:
    return EMPTY_BY_DESIGN.get(str(field or ""))


def is_empty_by_design(field: str | None) -> bool:
    return str(field or "") in EMPTY_BY_DESIGN


def undeclared_unwritten_fields() -> frozenset[str]:
    """⛔ The other direction: a slice field `build_context_slice` never names, and this file
    never explains.

    Read from the builder's source rather than from a hand list, because a hand list is the thing
    that goes stale. `**` expansions and computed keyword names are not resolvable this way, so a
    field set indirectly would show up here and would need a row saying so — which is the right
    failure, not the wrong one.
    """
    from genios_engine.context.situation_bso import build_context_slice
    from genios_engine.contracts.domain_expertise import SituationContextSlice

    src = inspect.getsource(build_context_slice)
    written = {name for name in SituationContextSlice.__dataclass_fields__
               if f"{name}=" in src}
    return frozenset(SituationContextSlice.__dataclass_fields__) - written - set(EMPTY_BY_DESIGN)


def _check() -> None:
    for field, why in EMPTY_BY_DESIGN.items():
        from genios_engine.contracts.domain_expertise import SituationContextSlice
        assert field in SituationContextSlice.__dataclass_fields__, (
            f"{field} is declared empty-by-design and is not a slice field")
        assert "ENDS WHEN" in why, f"{field} is declared silent and says nothing about what ends it"


_check()

__all__ = ["EMPTY_BY_DESIGN", "is_empty_by_design", "reason_for", "undeclared_unwritten_fields"]
