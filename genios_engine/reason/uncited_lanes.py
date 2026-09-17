"""Which pack lanes deliver cards that can never quote an expert, declared — with a mover.

A CARD WITH NO CITATION IS INDISTINGUISHABLE FROM A CARD WHOSE DOCTRINE FAILED TO BIND. From the
screen, from `signals`, and from the L3 funnel, `citations = 0` reads the same whether the lane
never had a corpus or whether its corpus silently resolved to nothing. Layer 2 lost five readings
to exactly that ambiguity (`context/lane_health.DORMANT_LANES`), and this is the same fact one
layer up, where the unit is a PACK rather than a reading.

THE ASYMMETRY THIS FILE EXISTS TO NAME. Two lanes write `signals`, and only one of them can cite:

  * the COMPILED lane — `reason/domain_shadow._persist_live` — resolves a corpus for the
    situation's domain and writes `capability_id`, `capability_version` and `citations` onto the
    row. Measured 2026-09-16 on the pilot: admin 13 of 13 cited, sales 5 of 5.
  * the PACK lane — `reason/runner._emit` — evaluates authored rules against graph nodes. Its
    column list has no `citations`, because a pack rule has no corpus behind it to quote.

NOT CITING IS NOT THE SAME AS NOT REASONING, and conflating the two is the error this file blocks.
Every pack-lane signal below still runs the full reasoner and still carries a real, versioned
capability — `legacy.general.commitment_overdue@1.5.0-a4-500` — through `reasoning_runs`, which is
where `reason/authority.AUDITED_CARD_JUDGMENTS_CTES` reads it from. So L7 CAN attribute an outcome
to a pack-lane card and calibrate its precision. What the card cannot do is show the human a
sentence an expert wrote.

A PERMANENT EXCEPTION LIST IS A WAY TO NEVER FIX ANYTHING, so — the rule this file inherits from
`patterns/routing.UNROUTED_PATTERN_TYPES` — every entry names the MEASUREMENT that made it true
and the thing that would END it.
"""

from __future__ import annotations

#: `{pack_id: why its cards carry no citation, and what would change that}`.
UNCITED_LANES: dict[str, str] = {
    "general":
        "THERE IS NO `general` CORPUS AND THERE MUST NOT BE ONE. `general` is not the name of a "
        "domain — it is what `context/correlation.DEFAULT_DOMAIN` says when no hint fired, which "
        "is why `packs/compiler/capability_resolver.UNCLASSIFIED_DOMAINS` already refuses to look "
        "one up. Authoring doctrine for it would mean writing expert rules for 'we could not tell "
        "what this is about', and every card produced under them would cite an expert on a "
        "subject the expert was never shown. The pack's two live rules are relationship hygiene "
        "that holds regardless of domain — an overdue promise is overdue whoever it is owed to — "
        "and `packs/general_v1.py` records that they were moved OUT of sales precisely so their "
        "cards would stop being mislabelled with a domain they never had. "
        "Measured 2026-09-16 on the pilot: 53 of 74 signals and 51 of 72 delivered cards, from "
        "exactly two rules (`commitment_overdue` 29, `unanswered_email` 24), 0 citations, 2 "
        "capabilities, and 0 of the tenant's 208 situations classified `general`. "
        "MOVES WHEN: never for this lane by adding a corpus. The gap worth closing is a "
        "different one and is declared below as its own question — 9 of 11 OPEN general-pack "
        "signals sit on a subject that ALSO holds an active L2 situation, so the understanding "
        "exists and the card is simply not bound to it. Binding the pack lane to the situation "
        "its subject already has is an architecture decision, not a repair, and it is the user's "
        "to make. Nothing here changes until it is made.",

    "":
        "THE TEAM LANE PUBLISHES WITHOUT A PACK AT ALL. `reason/team/emit.py` writes `signals` "
        "with no `pack_id` and no `reasoning_run_id`; its rows carry a `capability_id` but no "
        "audited run, so `AUDITED_SIGNAL_PREDICATE` excludes them from calibration as well as "
        "from citation. That exclusion is correct — an unaudited row must not grade a capability "
        "— and it is listed here so the zero is read as a boundary rather than as a lane that "
        "broke. Measured 2026-09-16: 3 signals, rule `verify.situation`, 0 citations, 0 "
        "reasoning runs. "
        "MOVES WHEN: the team lane publishes through an audited execution, which is the same "
        "prerequisite `reason/publication.publish_native_signal` already satisfies for native "
        "capabilities.",
}


def undeclared(citing: dict[str, tuple[int, int]]) -> tuple[str, ...]:
    """Pack lanes that delivered signals, cited on none of them, and are not declared above.

    `citing` is `{pack_id: (signals, cited)}` as the lane actually published; a `pack_id` of
    ``None`` arrives as ``""``. Returns the lanes a reader has to explain — the class that hid a
    dead corpus behind a healthy-looking funnel.

    A lane that published nothing at all is NOT reported here. Zero signals is a question about
    whether the lane ran, which `packs/registry` and the sweep's own outcome counters answer;
    reporting it as an uncited lane would put two different failures under one name.
    """
    return tuple(sorted(
        lane for lane, (signals, cited) in citing.items()
        if signals and not cited and lane not in UNCITED_LANES))


def now_citing(citing: dict[str, tuple[int, int]]) -> tuple[str, ...]:
    """Lanes declared uncitable that have started citing — the entry above is now a lie."""
    return tuple(sorted(
        lane for lane, (_signals, cited) in citing.items()
        if cited and lane in UNCITED_LANES))


__all__ = ["UNCITED_LANES", "now_citing", "undeclared"]
