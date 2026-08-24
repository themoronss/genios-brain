"""The zero-clarity gate's requirements, derived from the packs instead of hand-maintained.

`api/routes.py::_actionability` used to be an if/elif chain over three reason codes ending in an
unconditional `return {"state": "actionable"}`. That default is the wrong way round twice over:

  * it covered 34 of 41 live signals and left the sales-critical remainder — `closed_lost_risk`,
    `objection_open`, `demo_requested`, `timeline_slip` — ungated, so those cards asserted a
    confident imperative with no grounding check at all;
  * every rule added to a pack afterwards inherited the ungated default silently. Adding a rule
    is a pack-data edit; nobody editing one would think to also edit an API projection helper.

So the requirement moves next to the rule that needs it, and an undeclared reason code fails
CLOSED. "We have not said what this action needs" and "this action needs nothing" are different
statements, and only one of them is safe to guess.

Read from BUILTIN_PACKS, not from the tenant's effective pack. The gate is a projection concern,
not a tenant-versioned rule: an org pinned to an older pack version would otherwise resolve an
empty map and have every one of its cards downgraded to context_incomplete by an upgrade it never
took. Rules stay versioned; how honestly we describe their output does not.
"""
from __future__ import annotations

from dataclasses import dataclass

from genios_engine.packs.general_v1 import GENERAL_V1_ACTIONABILITY
from genios_engine.packs.sales_v1 import SALES_V1_ACTIONABILITY
from genios_engine.packs.wiring import BUILTIN_PACKS


@dataclass(frozen=True, slots=True)
class Decisive:
    """What the card's ACTION needs, as opposed to what the rule's MATCH needed.

    The two are routinely different, and conflating them is what produced "deliver the commitment"
    on a commitment whose text was never captured: `commitment.due_at` is enough to know something
    is overdue and not nearly enough to know what to deliver.
    """

    #: Satisfied when ANY of these fact fields is grounded …
    facts: tuple[str, ...] = ()
    #: … or ANY of these observation kinds was extracted. Either is sufficient; a rule that needs
    #: both should express that as a single richer fact rather than an AND here.
    obs: tuple[str, ...] = ()
    label: str = ""
    message: str = ""
    recommended: str = ""

    def satisfied(self, obs_kinds: set, fact_fields: set) -> bool:
        return bool((set(self.facts) & set(fact_fields)) or (set(self.obs) & set(obs_kinds)))


#: Authored beside the rules they describe, but deliberately NOT inside the pack dict: the pack
#: registry content-addresses that dict and refuses to re-register a changed one under the same
#: version. These requirements are a projection concern, not rule semantics — folding them in
#: would force a rule-version bump on every wording change while changing no rule at all.
_SOURCES = (SALES_V1_ACTIONABILITY, GENERAL_V1_ACTIONABILITY)


def _requirements() -> dict[str, Decisive]:
    out: dict[str, Decisive] = {}
    for spec_map in _SOURCES:
        for code, spec in spec_map.items():
            out[code] = Decisive(
                facts=tuple(spec.get("facts", ())), obs=tuple(spec.get("obs", ())),
                label=spec["label"], message=spec["message"],
                recommended=spec["recommended"])
    return out


REQUIREMENTS: dict[str, Decisive] = _requirements()

#: Returned for a reason code no pack describes. Not an error state — a card still ships, it just
#: ships as "review the source" instead of as an imperative we cannot back.
UNDECLARED = Decisive(
    label="what this situation needs",
    message="We detected this situation but haven't verified what it needs from you.",
    recommended="Open the source and review it before acting.")


def evaluate(reason_code: str | None, obs_kinds: set, fact_fields: set) -> dict:
    """`actionable` only when the decisive context for this reason code is grounded."""
    req = REQUIREMENTS.get(reason_code or "")
    if req is None:
        req = UNDECLARED
    elif req.satisfied(obs_kinds, fact_fields):
        return {"state": "actionable"}
    return {"state": "context_incomplete", "missing": [req.label],
            "message": req.message, "recommended": req.recommended}


def undeclared_reason_codes() -> set[str]:
    """Rule reason codes no pack gives an actionability requirement — the drift this module
    exists to make visible. Enforced by tests, not at import: a pack author should see a named
    test failure, not an ImportError from an unrelated module."""
    declared = set(REQUIREMENTS)
    return {r["reason_code"] for p in BUILTIN_PACKS for r in p["rules"]} - declared
