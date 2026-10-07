r"""What `context/` deliberately does not call — L2/L3's graph plane's declared silence.

⛔ THE BIGGEST CLUSTER IN THE ENGINE OF *BUILT, HEAVILY TESTED, AND NOT WIRED* — and the sharpest
entry in all of `STEP-17` is here, already written down by the code itself.
`capture/acquire/need_executor.py` says: *"`context/evidence_need_store.py` files needs.
`evidence_need.execute()` works ONE need. **Nothing ran**"*, and at `:125` it names
`read_open_needs` and adds **"which this layer may not import."** `capture/` is PRODUCT layer 1 and
`context/` is 2, so **the executor cannot read its own queue.** The gap is STRUCTURAL and declared —
the same shape as the problem that moved `reachability.py` into `platform/`.

⛔ Four functions carry the EvidenceNeed chain (`read_open_needs`, `close_need`, `needs_from_holds`,
`resolve_hold` — the last with **22** test callers, the most of any unreached function in the
engine), and the chain is broken at a layer boundary rather than by an oversight.

The machinery is `platform/reachability.py`, shared rather than copied. ⛔ Three wiring mechanisms
are subtracted before anything reaches this table — a **call**, a **decorator**, a **reference**
(`Depends(f)`, a dispatch table, a registry) — and a fourth cannot be: **duck-typed dispatch**
(`store.purge_expired()` on a variable) is invisible to any static walk, so every entry below was
hand-checked against it. One function was rescued that way; sixteen candidates turned out to be name
collisions.
"""
from __future__ import annotations

from pathlib import Path

from genios_engine.platform.reachability import (engine_sources, missing, now_called,
                                                 package_functions, undeclared)

_PKG = Path(__file__).resolve().parent
_ENGINE = _PKG.parent


#: ⛔ Public functions in `context/` with no production caller — `{name: (why, mover)}`.
#:
#: CLOSED, and checked in BOTH directions by `tests/context/test_the_context_layer_says_what_it_does_not_call.py`.
UNREACHED: dict[str, tuple[str, str]] = {
    "evidence_need_store.read_open_needs": (
        "⛔⛔ THE BEST ENTRY IN THIS WHOLE LEVEL, AND THE CODEBASE ALREADY WROTE IT DOWN. *'The executor's queue: this tenant's open needs, oldest first.'* The executor EXISTS — `capture/acquire/need_executor.py` — and its own header says: *'`context/evidence_need_store.py` files needs. `evidence_need.execute()` works ONE need. Nothing ran'*, with a second note at `:125` naming this function and adding **'which this layer may not import.'** `capture/` is PRODUCT layer 1 and `context/` is 2, so the executor cannot read its own queue. ⛔ **The gap is STRUCTURAL and declared, not an oversight** — and it is the same shape as the problem that moved `reachability.py` into `platform/` three steps ago",
        "⛔ MOVES WHEN SOMEBODY TAKES THE SEAM DECISION, and there are exactly two shapes: lift the queue read into `platform/` (where layer 1 may reach it, which is what the reachability machinery did), or invert it so `context/` pushes needs down. **Nobody has taken it**, and the Atlas listed EvidenceNeed as VERIFIED MISSING at the start of this programme — it was built since and never connected"),

    "hold_resolution.resolve_hold": (
        "⛔ TWENTY-TWO TEST CALLERS AND NO PRODUCTION CALLER — the most heavily tested unreached function in the engine. *'What to do with a held situation, given the state of the needs it raised.'* So the decision logic for a hold is specified to the hilt and nothing asks it: a situation that goes on hold stays held. ⛔ It is the far end of the same chain as `read_open_needs` — holds raise needs, needs get executed, resolution reads the outcome — and that chain is broken at the layer boundary above",
        "MOVES WITH the EvidenceNeed seam — see `evidence_need_store.read_open_needs`. ⛔ Wiring resolution before the needs can be executed would ask it to read outcomes nothing produces"),

    "hold_needs.needs_from_holds": (
        "*'A sweep's worth of holds → the needs worth asking, de-duplicated by id.'* Three test callers. The middle link of the same chain: holds in, needs out. Correct, and asked by nothing",
        "MOVES WITH the EvidenceNeed seam — the three links move together or none do"),

    "evidence_need_store.close_need": (
        "*'Record an outcome. Returns False when the need was already closed by someone else.'* Four test callers, and the concurrency answer is already in it — a second closer gets False rather than an exception. The WRITE half of a queue nothing reads",
        "MOVES WITH `read_open_needs`. ⛔ A closer with no executor has nothing to close"),

    "situation_bso.gather_l1_signals": (
        "⛔ ITS OWN DOCSTRING SHOUTS WHAT IT IS FOR: *'THE READ THIS MODULE EXISTED WITHOUT. Layer 1's published verdicts for this situation'*. Fifteen test callers, zero production callers. So the module still exists without it. ⛔ **A function whose docstring names the absence it was written to end, and is not called, means the absence is unchanged** — and the capitals make it read as fixed",
        "MOVES WHEN the BSO build reads L1's verdicts rather than inferring them. ⛔ That is a change to what a situation object CONTAINS, so it moves a content hash and every snapshot replay is verified against — the reason it is not a one-line wiring"),

    "bounded_read.read_bounded": (
        "*'The bounded read, against a live connection, carrying the revision it saw.'* No callers and no tests. ⛔ L3's own bounded read, and L4 spent `STEP-08` bounding a different unbounded query by hand — so the pattern this function implements was wanted at least once and solved locally instead",
        "⛔ MOVES WHEN a reader wants the revision alongside the rows. The CODING-AGENT handoff already carries a brief about bounded reads; this is the function that brief should use rather than writing a third one"),

    "backfill.backfill_business_facts": (
        "*'Re-grade stored L1 extractions and write the business facts today's code would produce.'* No callers and no tests — and `scripts/` IS in the source set, so not even an ops CLI runs it. ⛔ A backfill is by nature run by hand once; what is unusual is that nothing records HOW, so the next person re-derives the invocation",
        "⛔ MOVES WHEN it is run, which needs an operator and a window. Until then it is a migration written in Python with no runner — flagged for Harsh, who owns the backfills"),

    "identity.resolve_alias_candidates": (
        "*'Every node answering to a key — so a caller can SEE an ambiguity rather than infer it.'* No callers, no tests. ⛔ The whole point is to make an ambiguity visible, and nothing looks: identity resolution today picks a winner, and this is the function that would show the alternatives",
        "MOVES WHEN a merge or disambiguation surface exists. ⛔ `api/merge_routes` is the obvious caller and resolves its own candidates instead"),

    "fact_visibility.readable_fact_idx": (
        "*'An org-wide per-node fact index with the private fields `audience` may not read removed.'* No callers, no tests. The visibility RULES are live — `_visible_quotes` enforces them per card — and this is the pre-built index a wider reader would need",
        "MOVES WHEN something reads facts org-wide for one audience. ⛔ Every live reader is node-scoped, so the index would be built and then used once"),

    "fact_visibility.situation_audience": (
        "*'The principals a situation is private to, or None when it is wider than one owner.'* No callers, no tests. The sibling of the index above and the same shape: a visibility question asked at a grain nothing currently reads",
        "MOVES WITH `readable_fact_idx` — one audience answer and one index over it"),

    "correlation.merged_span": (
        "*'The group's span after admitting this event. Widens in BOTH directions, because a'* late arrival can move the start as well as the end. Three test callers. ⛔ The correlators ARE live — ten modules of them — and this is the span arithmetic stated once for all of them, which each currently does inline",
        "MOVES WHEN a correlator is refactored onto it. ⛔ Ten callers to change at once, and the inline versions are not wrong — so this is a tidy-up with a real regression surface"),

    "correlation_timeline.conditions_from": (
        "*'STEP 1 over a claim stream. `resolve` is the injected identity cascade — the benef'*iciary of the correlation. Five test callers. A documented pipeline STEP with no pipeline running it: the timeline correlator is built and the conditions step is specified and unwired",
        "MOVES WHEN the claim-stream timeline runs on a sweep. ⛔ It is the first step of a sequence whose later steps are also unwired, so wiring this alone produces conditions nothing reads"),

    "domain_spec.extend": (
        "*'Adjust one registered domain without restating it. Convenience for L3.'* No callers and no tests. ⛔ And it is the single most collision-prone name in the engine: under the name-only resolver `extend` had **96** apparent callers, every one of them `list.extend`. The qualified resolver is why this entry exists at all",
        "MOVES WHEN a domain is adjusted in code rather than restated. ⛔ Every current registration restates the whole spec, which is verbose and unambiguous — so the convenience has never been wanted enough"),

    "tenant_profile.declare": (
        "*'Record what this tenant is, and point Layer 3's branches at it.'* Seven test callers. ⛔ AND IT SURVIVED A HAND-CHECK THAT LOOKED LIKE A RESCUE: `api/authority_routes.py:121` calls `_view().declare(org, [rule])`, which is `AuthorityView.declare` — a method on a different class with a different signature. **Duck-typed dispatch cannot be resolved statically**, so this one was verified by reading the callee, and it is genuinely unreached",
        "MOVES WHEN onboarding records a tenant profile. ⛔ The profile VOCABULARY is live — `categories` and `reader_roles` below are its closed sets — and the writing of one is not"),

    "tenant_profile.categories": (
        "*'What kinds of company the corpus can speak to. Group A's closed set.'* One test caller. A closed set read by the tests that prove the corpus stays inside it, which is a real job for an enumeration",
        "MOVES WITH `declare` — the sets exist to validate a profile nobody writes yet"),

    "tenant_profile.reader_roles": (
        "*'What readers the corpus can speak as. Group B's closed set.'* One test caller. The other half of the pair above, and closed for the same reason: a reader role the corpus cannot speak as is a card nobody can be shown",
        "MOVES WITH `declare` and `categories` — three parts of one unwritten profile"),

    "tenant_profile.resolvable_slugs": (
        "*'Slugs whose folder name matches the last segment of their own declared id.'* One test caller. ⛔ A both-directions guard over the corpus layout: this is the half that passes",
        "MOVES WITH `unreachable_slugs` — see that entry. A guard shipped one-sided is half a guard"),

    "tenant_profile.unreachable_slugs": (
        "⛔ *'`(slug, declared_id)` for branches whose folder name is not one of their own alias'*es — the FAILING half of the pair above, and the one that would catch a real misfiling. One test caller. **Declared and written are two directions**, and this package states that rule over its own folder names",
        "MOVES WITH `resolvable_slugs`. ⛔ Wiring the passing half without the failing one would report a healthy corpus by construction"),

    "availability.availability_for_person": (
        "*'Current and upcoming windows for one person (by node id or email), soonest first.'* One test caller. The availability READ at person grain; the live callers ask at team grain (`reason/team/readiness` reads `counts` and `load_*`)",
        "MOVES WHEN a card or a brief names when one person is free. ⛔ Today the product answers *is the team available*, which is a different question and already wired"),

    "canon.anchors_situations": (
        "*'Whether a canon document of this kind should anchor situations.'* Two test callers. A predicate over document kinds, and the live anchoring path decides inline",
        "MOVES WHEN the anchoring decision is read from one place instead of two"),

    "canon.anchoring_node_types": (
        "⛔ NO DOCSTRING, and no test either — the only function in `context/` with nothing anywhere. ⛔ **Why it is unreached is recorded nowhere**, so declaring it deliberate would invent a reason and declaring it a defect would invent a severity. Its name suggests the node types `anchors_situations` ought to consult, which would make the two a pair — but that is a reading of a name, not a measurement",
        "⛔ MOVES WHEN somebody who knows whether `anchors_situations` should consult it writes one line above it. Flagged in `HANDOFF-CODING-AGENT.md` rather than guessed at here"),

    "projections.node_projections": (
        "*'Every lens one entity appears in.'* One test caller. The multi-lens view of a node, and every live reader asks for one lens at a time",
        "MOVES WHEN a surface shows one entity across lenses — an entity page is the obvious caller and does not exist"),

    "correlation_conversation.find_waves": (
        "STEP-10's wave (`yc2_w27_s10 · M29.C4.L-logic.V2.U01`): one outreach to several outside people as one object — recognised by the sentence a qualified signal quoted, else by its subject within seven days to three or more outside addresses — with who it went to, who wrote back, whose address bounced, whom we wrote to again and the days since its last send. A read model built before the card that shows it, so it is unreached between this unit and that one",
        "MOVES WHEN a card for a wave reads it — `outreach_situations._gather` stamping waves beside `_campaigns` (STEP-14)"),

}


def _sources() -> dict[str, str]:
    return engine_sources(_ENGINE)


def context_functions() -> dict[str, str]:
    """`{"module.function": module}` for every declarable public function in `context/`."""
    return package_functions(_PKG)


def context_undeclared() -> tuple[str, ...]:
    """Unreached public functions in `context/` that this module does not declare."""
    return undeclared(_PKG, _sources(), frozenset(UNREACHED))


def context_missing() -> tuple[str, ...]:
    """⛔ Declared entries naming a function that does not exist — the second direction."""
    return missing(_PKG, frozenset(UNREACHED))


def context_now_called() -> tuple[str, ...]:
    """⛔ Declared entries the engine HAS started calling — the entry that has become a lie."""
    return now_called(_sources(), frozenset(UNREACHED))


__all__ = ["UNREACHED", "context_functions", "context_missing", "context_now_called", "context_undeclared"]
