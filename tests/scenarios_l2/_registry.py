"""L2-8-U3/U6 · Layer 2's scenarios, their failure classes, and what each one is actually worth.

L1's step-17 shape, applied here: **a table with a row per scenario and an import-time check that
nothing is missing from either side** — the same idiom as `PRECEDENCE`, `SITUATION_STAGES`,
`ADMISSION_REASONS`, `DARK_DOMAINS` and `CHECKS`.

⛔ **AND THE SAME PREMISE CORRECTION L1 STEP 17 HAD TO MAKE.** §5 wants *"mutation probes for every
fix in L2-1…L2-7, each proven sensitive"*, and RED-first is unavailable for a defect a completed
step already closed. Technique 3 replaces it and is stronger: *"neutralise the fix and confirm the
probe goes red. A probe that passes with the fix removed proves nothing."*

⛔ **A VERDICT WITH NO REASON IS A LABEL**, so `OPEN`, `HARSH` and `IMPOSSIBLE` each owe one.
"""
from __future__ import annotations

from dataclasses import dataclass

#: A step in L2-0…L2-7 fixed it, and a probe proves the check is sensitive to THAT fix.
CLOSED = "closed"
#: It was already true and must stay true. **Not evidence of progress** — evidence it cost nothing.
GUARD = "guard"
#: Still open, with its reason. This is the output the step asks for.
OPEN = "open"
#: Needs the pilot database. The LOGIC is proven; the DISTRIBUTION is what waits.
HARSH = "harsh"
#: Cannot be satisfied as written. Recorded, with the reason, so nobody re-opens it.
IMPOSSIBLE = "impossible"


@dataclass(frozen=True, slots=True)
class Scenario:
    id: str
    failure_class: tuple[str, ...]
    title: str
    verdict: str
    owner: str
    note: str = ""


def _s(id_: str, classes: str, title: str, verdict: str, owner: str, note: str = "") -> Scenario:
    return Scenario(id=id_, failure_class=tuple(classes.split("/")), title=title,
                    verdict=verdict, owner=owner, note=note)


#: ⛔ L2's twelve failure classes. `F20` is L1's and is kept by its own number, because it is the
#: SAME failure — "unknown → true" — wearing this layer's clothes.
FAILURE_CLASSES: frozenset[str] = frozenset({
    "L01",  # a refusal that is right and invisible
    "L02",  # a value computed correctly and not carried
    "L03",  # two names for one thing
    "L04",  # a field, unit or law built and never switched on
    "L05",  # a rule with two copies that can disagree
    "L06",  # a domain that routes nowhere and says nothing
    "L07",  # a count that exists and cannot be acted on
    "L08",  # a measurement that can kill what it measures
    "L09",  # a number asserted rather than measured
    "L10",  # a receipt that does not resolve
    "L11",  # a layer importing upward
    "F20",  # ⛔ unknown → true. Here: a hypothesis that hardened into an observation
    "—",
})


SCENARIOS: dict[str, Scenario] = {s.id: s for s in (
    # --- L2-0 · the refusals ---------------------------------------------------------------------
    _s("S01", "L01", "every hold reason appears in the report, zeros included", CLOSED, "0"),
    _s("S02", "L01", "a held situation states its score against its floor", CLOSED, "0"),
    _s("S03", "L09", "the corpus reports its own size rather than a remembered one", CLOSED, "0",
       ""),
    _s("S04", "L01", "24 authored situations are draft and their cards cannot instruct", HARSH, "0",
       "Measured in repo: 8 admin, 16 of customer_support's 20, 0 sales. Whether each is "
       "genuinely unfinished or merely un-flipped is an authoring judgement — Harsh 22."),
    # --- L2-1 · the names ------------------------------------------------------------------------
    _s("S05", "L03", "one situation type per stage, and a third cannot arrive undeclared",
       CLOSED, "1"),
    _s("S06", "L03", "the compiler names the stage it actually receives", CLOSED, "1"),
    _s("S07", "L04", "the compiler is exercised with what production sends it", OPEN, "1",
       "⛔ `l3_inputs.py` and `test_domain_expertise_compiler.py` build a SituationCandidate and "
       "hand it to the compiler; production builds one in two files, neither of which feeds it. "
       "The annotations now say the truth and NO test drives the compiler with what "
       "`publish_situation` returns. Recorded in STATUS as its own unit."),
    # --- L2-2 · the claim states -----------------------------------------------------------------
    _s("S08", "L05", "every v2 field is classified, both directions", CLOSED, "2"),
    _s("S09", "F20", "a model may never write an observation", CLOSED, "2"),
    _s("S10", "L10", "an interpretation that cites nothing is named by V-9", CLOSED, "2"),
    _s("S11", "F20", "empty unknowns under thin coverage is named by V-10", CLOSED, "2"),
    _s("S12", "L04", "V-9 and V-10 are armed", HARSH, "2",
       "Both OBSERVE deliberately: arming them refuses live situations and nobody has counted "
       "how many. The count is the `BY LAW` block of the refusal report — Harsh 24."),
    # --- L2-3 · the slice ------------------------------------------------------------------------
    _s("S13", "—", "the slice builder performs no I/O and cannot N+1", GUARD, "3"),
    _s("S14", "—", "a private seat fact never reaches a situation slice", GUARD, "3"),
    _s("S15", "L09", "a slice states what it weighs, against a declared budget", CLOSED, "3"),
    _s("S16", "L04", "`slice.evidence` is empty by design and says so", CLOSED, "3"),
    # --- L2-4 · the routing ----------------------------------------------------------------------
    _s("S17", "L06", "every registered L2 domain has a row, and the Nones are DARK_DOMAINS",
       CLOSED, "4"),
    _s("S18", "L07", "an unroutable situation is counted with its domain AND its type", CLOSED, "4"),
    _s("S19", "L06", "fundraising reaches the investor doctrine that already exists", HARSH, "4",
       "⛔ `sales.sit.live_investor_relationship` is authored, stable and approved, and one `None` "
       "makes it unreachable. Declared in CANDIDATE_ROUTES, evidenced, not armed until the pilot "
       "count exists — Harsh 26."),
    _s("S20", "L06", "general is routed", IMPOSSIBLE, "4",
       "Its `relationship` type is claimed by ALL THREE corpora, so a route is a CHOICE nobody "
       "has made. Picking one by hand is how Admin doctrine lands on a support thread. It ends "
       "with a CENSUS of what actually lands there, not with a corpus."),
    # --- L2-6 · the validator --------------------------------------------------------------------
    _s("S21", "F20", "a proposal naming an observation is refused with its check", CLOSED, "6"),
    _s("S22", "L10", "a citation that does not resolve is refused apart from one that is absent",
       CLOSED, "6"),
    _s("S23", "L04", "UNKNOWN commits instead of reading as a failed generation", CLOSED, "6"),
    _s("S24", "L05", "every check reads its rule rather than owning a copy", CLOSED, "6"),
    # --- L2-7 · the card -------------------------------------------------------------------------
    _s("S25", "L02", "a signal records the situation it came from", HARSH, "7",
       "The code carries it; migration 0182 is not applied. Until it is, every signal reads NULL "
       "and the collapse cannot be measured — Harsh 4e."),
    _s("S26", "F20", "a signal with no situation surfaces LABELLED, never dropped", CLOSED, "7"),
    _s("S27", "L08", "the collapse measurement cannot kill the delivery pass", CLOSED, "7"),
    _s("S28", "L09", "the collapse ratio is measured rather than claimed", HARSH, "7",
       "38→N has been a claim since the plan was written. `scripts/card_collapse_report.py` "
       "prints it and refuses to report at all without 0182 — Harsh 27."),
    # --- L2-5 · the reasoner ---------------------------------------------------------------------
    _s("S29", "L04", "the reasoner registers as a site and builds no second gate", CLOSED, "5"),
    _s("S30", "F20", "a model cannot raise a confidence", CLOSED, "5"),
    _s("S31", "F20", "a model cannot write its own expiry or its own trace", CLOSED, "5"),
    _s("S32", "L11", "no Layer 2 module imports Layer 4", GUARD, "5"),
    _s("S33", "L09", "the cost check ran before the prompt", CLOSED, "5"),
    _s("S34", "L04", "the reasoner is switched on for a tenant", HARSH, "5",
       "Registered, wired and off. ~$15.64/month at Haiku on the measured shape, and migration "
       "0183 first — Harsh 4f and 28."),
    # --- L2-8 · the cutover ----------------------------------------------------------------------
    _s("S35", "L04", "every cutover switch is enumerated with its mover", CLOSED, "8"),
    _s("S36", "L09", "the parity gate is a number fixed before the run", CLOSED, "8"),
    _s("S37", "L09", "the shadow pass's tallies are read", HARSH, "8",
       "⛔ The pass has been counting for months and nobody has read it. The parity gate is "
       "written and cannot be evaluated — Harsh 29."),
)}

VERDICTS: frozenset[str] = frozenset({CLOSED, GUARD, OPEN, HARSH, IMPOSSIBLE})
_NEEDS_A_REASON: frozenset[str] = frozenset({OPEN, HARSH, IMPOSSIBLE})


def _check() -> None:
    """Import-time totality, the way this codebase does it everywhere else."""
    for one in SCENARIOS.values():
        assert one.verdict in VERDICTS, f"{one.id}: unknown verdict {one.verdict!r}"
        for klass in one.failure_class:
            assert klass in FAILURE_CLASSES, f"{one.id}: unknown failure class {klass!r}"
        if one.verdict in _NEEDS_A_REASON:
            assert one.note, f"{one.id} is {one.verdict} and gives no reason"


_check()


def by_verdict(verdict: str) -> tuple[Scenario, ...]:
    return tuple(s for s in SCENARIOS.values() if s.verdict == verdict)


def by_owner(step: str) -> tuple[Scenario, ...]:
    return tuple(s for s in SCENARIOS.values() if s.owner == step)


__all__ = ["CLOSED", "FAILURE_CLASSES", "GUARD", "HARSH", "IMPOSSIBLE", "OPEN", "SCENARIOS",
           "VERDICTS", "Scenario", "by_owner", "by_verdict"]
