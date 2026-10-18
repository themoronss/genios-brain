"""What `deliver/` deliberately does not do — and what it does not do by accident.

⛔ WHY THIS MODULE EXISTS. Three of the four large packages state their own silences in code:
`reason/unit_health.py` (four grains, plus `REASONING_ERAS`), `context/lane_health.DORMANT_LANES`,
and `executive/unreached.py` (`UNREACHED` and `PULL_ONLY`, each entry carrying a reason AND a mover).
`deliver/` had nothing, and it is the largest of the four: **123 top-level public functions, of which
24 are not called by anything in the engine.** A reader could not tell any of the 24 apart from an
oversight, and nineteen of them were never read by anybody before 2026-10-01.

⛔ THREE TABLES, NOT ONE, AND THE SHAPE IS THE FINDING. L4 needed `UNREACHED` and `PULL_ONLY`. The
triage of `deliver/`'s 24 (`speedrun008/YCW27/layer-5-delivery/07-AUDIT-the-second-delivery-
architecture.md`) found that they are not 24 separate accidents:

    UNCUT_OVER      11  a second delivery architecture, built beside the running one
    UNREACHED        8  deliberate, explained, with a mover
    KNOWN_UNWIRED    5  ⛔ defects. Built, correct, SHOULD be called, and are not

Collapsing those into one table would file a product promise nobody keeps next to a shim that raises
on purpose, under the same word. **A declaration that cannot distinguish a decision from a defect is
paperwork.**

⛔ AND `KNOWN_UNWIRED` IS NOT A PARKING LOT. Every entry names the step that closes it, and
`tests/deliver/test_the_delivery_layer_says_what_it_does_not_call.py` fails the build on an entry
with no step. A declared defect with no owner is an undeclared defect with better manners.
"""
from __future__ import annotations

import ast
from pathlib import Path

from genios_engine.platform.reachability import (public_functions, qualified_call_counts,
                                                 qualified_call_sites)

#: ⛔ THE HELPERS MOVED TO `platform/reachability.py` ON 2026-10-01, EXACTLY AS THIS NOTE SAID
#: THEY WOULD. It read: *"they move to `platform/` when a THIRD package needs them, not before: two
#: users is an import, three is an extraction."* `STEP-17` is that third package and eight more —
#: and the trigger was sharper than "a third user": `capture/` is PRODUCT layer **1**, so
#: `capture/ -> executive/` is an UPWARD import `tests/test_layer_topology.py` fails the build over.
#: The eleventh package could not have imported them from where they were.
_PKG = Path(__file__).resolve().parent
_ENGINE = _PKG.parent


# ---------------------------------------------------------------------------------------------
# the v2 control plane — a second delivery architecture, and the cutover is a GRADIENT
# ---------------------------------------------------------------------------------------------

#: ⛔ Built, tested, and outside the running path — `{name: (tier, why, what measures it)}`.
#:
#: The live path is `outbox.drain`. Beside it sits a complete second control plane, and the useful
#: fact is not that it is uncalled but **how far the cutover has got, tier by tier**:
#:
#:     1 resolution   orchestrator.resolve / presence / audience   ⛔ SHADOW-MEASURED in production
#:     2 persistence  spine.materialize + its two companions       no evidence
#:     3 claiming     spine.claim_due / recover_expired_claims     no evidence, and no test either
#:     4 policy       rate_limiter / retry                         ⛔ no evidence — NOT EVEN IMPORTED
#:
#: ⛔ So a decision to cut over would be taken on evidence about ROUTING, while the three tiers that
#: touch the network have none. `outbox.shadow_resolve_v2` (`outbox.py:1254`) is the measurement:
#: it runs tier 1 over every live card, sends nothing, and accumulates `v2_shadow_resolved` /
#: `v2_shadow_unroutable` into the sweep totals. It is this package's `COMPARISON_KEYS`, under a
#: name the YCW27 plan searched for and missed — *a measurement can be present under a name you did
#: not search for.*
#:
#: ⛔ THE TWO PATHS ARE MECHANICALLY DISJOINT, which is why none of this is a live defect:
#: `outbox.drain` takes `dedupe_key is null`, `spine.claim_due` takes `is not null`. `outbox.py:838`
#: wrote the hazard down before closing it — *"Risk was zero only because the v2 path has never
#: written a row yet; the moment it does, both workers could select the same one and double-send."*
UNCUT_OVER: dict[str, tuple[int, str, str | None, str]] = {
    "spine.materialize": (
        2,
        "Inserts one logical delivery plus its `queued` event atomically, idempotent on the dedupe "
        "key. ⛔ `outbox.py:804` names it in writing: *'`delivery_id` was written by exactly ONE "
        "function in the whole codebase — `deliver/spine.py::materialize`, which has no production "
        "caller'* — and records the harm that already followed: `feedback/delivery_facts.py` "
        "filters on `delivery_id is not null`, so **a fully working legacy delivery path fed L7 "
        "zero DeliveryFacts, forever**, until the legacy row's own id was reused as its "
        "`delivery_id`. The repair is live; the function is still uncalled.",
        None,
        "MOVES WHEN tier 2 is cut over. ⛔ `shadow_resolve_v2` stops at resolution and never "
        "persists, so nothing measures this tier"),

    "spine.logical_dedupe_key": (
        2,
        "*'The deterministic logical key that makes ten destinations one delivery'* — keyed on the "
        "source (execution plus which of its events this is), never on the route, so two workers "
        "materialising the same event compute the same key and the unique index elects one winner. "
        "The legacy path needs no such key because it writes one row per destination.",
        None,
        "MOVES WHEN tier 2 is cut over — unmeasured until then"),

    "spine.record_materialization_failure": (
        2,
        "*'A frozen object we could not turn into a delivery. Visible to ops, never silently "
        "dropped.'* The failure path of a writer with no caller, so it cannot fire.",
        None,
        "MOVES WHEN tier 2 is cut over — unmeasured until then"),

    "spine.claim_due": (
        3,
        "⛔ THE ONE L4's RESOLVER REPORTS AS REACHED, AND IT IS NOT. The single engine call site is "
        "`capture/parked/refetch.py:267` — `queue.claim_due()` — which is "
        "`InMemoryRefetchQueue.claim_due`, a different function in a different package with a "
        "different signature (`eval_time=`/`policy=`/`org_id=` against this one's "
        "`worker_id=`/`at=`/`lease_seconds=`). `called_names` matches an `ast.Attribute` call by "
        "`attr`, which is what lets it resolve aliased imports and is also what lets any same-named "
        "method anywhere in the engine mask an unrelated function. ⛔ **A call resolved by name "
        "alone is a call to any function with that name** — which is why the both-directions guard "
        "in this module's test uses `qualified_call_sites` below and not `called_names`.",
        None,
        "MOVES WHEN tier 3 is cut over. ⛔ And L4's own UNREACHED table uses the same resolver, so "
        "an `executive/` function sharing a name with any method in the engine would be silently "
        "dropped from that declaration — logged as STEP-13, unfixed here because it changes a tool "
        "four L4 tests depend on"),

    "spine.recover_expired_claims": (
        3,
        "⛔ THE ONLY COMPONENT OF THE v2 PATH WITH NO TEST EITHER. *'An expired worker may have "
        "POSTed to a provider before dying; we must never silently retry over that ambiguity.'* It "
        "marks an expired claim's unsettled attempt `unknown` before the row is reclaimed. ⛔ IT IS "
        "NOT A LIVE DOUBLE-SEND: `claim_due` is uncalled too, so the ambiguity it guards cannot "
        "arise yet. **An uncalled function on an un-cut-over path is not a bug; it is an unguarded "
        "cutover**, and the two want opposite fixes — a bug wants wiring now, an unguarded cutover "
        "wants a guard that fires when the cutover is taken.",
        None,
        "⛔ EXERCISED BY NOTHING — not production, not a test. "
        "`tests/deliver/test_the_spine_cutover_cannot_be_taken_unguarded.py` (STEP-06) is the guard"),

    "rate_limiter.hour_recipient_key": (
        4,
        "*'The rolling-hour bucket key: a shared stream for chat families, else the seat.'* ⛔ AND "
        "THE BUCKET IS THE ONE THING THIS DOES BETTER RATHER THAN MERELY MORE SAFELY: `timing.py` "
        "counts per (org, recipient, channel), while this shares ONE bucket across a chat family — "
        "because two messages in the same stream are one interruption. So the race-free version is "
        "also the more accurate one about what an interruption IS.",
        None,
        "MOVES WITH `reserve_slot` — see that entry. ⛔ Nothing in the engine imports "
        "`rate_limiter` at all, and the ceiling it implements is already enforced, less precisely, "
        "by `timing.py`"),

    "rate_limiter.reserve_slot": (
        4,
        "⛔ THE RACE-FREE VERSION OF A CEILING THAT IS ALREADY ENFORCED — NOT A SECOND OPINION ON "
        "WHETHER ONE SHOULD EXIST. *'Atomically reserve one attention slot… the `where` on the "
        "conflict update is what makes two concurrent workers'* safe. "
        "⛔ MEASURED 2026-10-01, AND IT WITHDREW A QUESTION I HAD PUT TO ROHIT: `deliver/timing.py` "
        "ALREADY enforces a per-recipient hourly ceiling on every delivery — `_BURST_WINDOW = 1 "
        "hour`, `AttentionProfile.max_interrupts_per_hour = 3`, and `timing.py:229` DEFERS when the "
        "count reaches it — reached through the live chain `outbox.drain -> gate.admit -> "
        "evaluate_delivery -> evaluate_timing`. So this module is not the only ceiling; it is the "
        "only RACE-FREE one. "
        "⛔ AND THE RACE IT CLOSES IS OPENED DELIBERATELY: `PgDeliveryContext.resolve` counts the "
        "hour's deliveries and then calls `_release()`, because *'the connection stops sitting idle "
        "in transaction across an outbound HTTP call'* — holding it across a webhook POST would be "
        "worse than the overshoot. Two workers can both read 2 < 3 and both send, making four "
        "against a ceiling of three. "
        "⛔ THAT CANNOT HAPPEN TODAY: `Procfile` runs uvicorn with no `--workers` (one process) and "
        "`scheduler.py` uses `ThreadPoolExecutor(max_workers=1)`. ONE drain worker, so no "
        "concurrency and no overshoot; the `for update skip locked` in the drain is for a "
        "deployment that does not exist yet. "
        "⛔ A separate `budget` suppression also runs — `reason/runner.py:1294` — but per RULE, per "
        "NODE, DAILY. **Two implementations of one word can be two different questions**, and that "
        "comparison was right; what it missed was the THIRD implementation in this same package, "
        "which answers exactly this one.",
        None,
        "⛔ MOVES WITH THE WORKER COUNT, NOT ONLY WITH THE CUTOVER — and that is the finding "
        "`STEP-16` became when it was withdrawn. The live ceiling is exact at one worker and "
        "silently approximate at two, so this is wanted the moment anybody sets `--workers 2`, "
        "cutover or no cutover. "
        "`tests/deliver/test_the_hourly_ceiling_is_exact_at_one_worker.py` pins the count so "
        "raising it fails the build there rather than widening a ceiling in production. See "
        "`layer-5-delivery/STEP-16-WITHDRAWN-the-hourly-ceiling-already-exists.md`"),

    "rate_limiter.release_slot": (
        4,
        "*'Give a reserved slot back — only on a DEFINITE non-delivery. Never below zero.'* The "
        "release half of a reservation nothing takes.",
        None,
        "MOVES WHEN tier 4 is cut over — unmeasured until then"),

    "retry.next_attempt_at": (
        4,
        "*'When the next provider attempt may run after a DEFINITE failure, or None if terminal'* — "
        "honours a provider `Retry-After` and never pulls the delay in below the ladder. The legacy "
        "drain computes its own `next_attempt_at` inline from a per-channel lease, which is correct "
        "for a crashed sender and knows nothing about a provider's own backoff request.",
        None,
        "MOVES WHEN tier 4 is cut over — ⛔ nothing in the engine imports `retry` at all"),

    "retry.may_cross_channel_failover": (
        4,
        "⛔ THE SAME RULE AS `recover_expired_claims`, AT A DIFFERENT GRAIN, AND BOTH HALVES ARE "
        "OUTSIDE THE RUNNING PATH. *'An UNKNOWN outcome must not fail over: the first provider may "
        "already have delivered, and a second channel would then be a duplicate human "
        "interruption. Ambiguity stops for reconciliation.'* The legacy path has no concept of an "
        "ambiguous outcome — not a bug in it, a narrower contract — and **it is the reason the "
        "cutover was designed**, which is invisible from the running code.",
        None,
        "MOVES WHEN tier 4 is cut over — unmeasured until then"),

    "retry.defer_until": (
        4,
        "*'A deferral moves the clock and nothing else \u2014 it does not touch the failure ladder.'* "
        "\u26d4 The distinction is the whole point: a deferral is not a strike, so it must not "
        "advance the retry ladder or the route cursor. `gate.defer_until` \u2014 a DIFFERENT function "
        "with the same name, in the module that decides the moment \u2014 IS called; this one is the "
        "outbox-side half and is not. That collision is why it was invisible until STEP-13.",
        None,
        "MOVES WHEN tier 4 is cut over \u2014 \u26d4 nothing in the engine imports `retry` at all"),

    "presence.absent": (
        1,
        "*'A minimal already-expired context so callers can treat \"no lease\" uniformly.'* A tier-1 "
        "helper on the resolution path, so unlike tiers 2-4 it IS exercised in production — but "
        "only through `shadow_resolve_v2`, which sends nothing. `card_builder.py:497` records the "
        "same shape for its own helper: *'its one caller is `outbox.shadow_resolve_v2`, which sends "
        "nothing'*.",
        "outbox.shadow_resolve_v2",
        "⛔ MOVES WHEN tier 1 sends rather than measures. It is the ONLY tier with production "
        "evidence: counters `v2_shadow_resolved` and `v2_shadow_unroutable`, accumulated at "
        "`outbox.py:1441`"),
}


# ---------------------------------------------------------------------------------------------
# deliberate silences — explained, with a mover
# ---------------------------------------------------------------------------------------------

#: ⛔ Public functions in `deliver/` that production does not call ON PURPOSE — `{name: (why, mover)}`.
#:
#: CLOSED, and checked in BOTH directions by the test module, using `qualified_call_sites` rather
#: than `called_names` for the "is it called now" half — see `spine.claim_due` above for why.
#: An entry naming a function that is now called is as much a lie as a function that is unreached
#: and undeclared; L4 learned that when `summary.build_summary` sat in `PULL_ONLY` after quietly
#: acquiring a producer, and **one direction alone is half a guard.**
UNREACHED: dict[str, tuple[str, str]] = {
    "push.push_action_to_agents": (
        "⛔ CORRECTLY UNCALLED, AND THE DOCSTRING IS THE REASON: *'External actions go through the "
        "delegation protocol, never through a broadcast. This shim stays fail-closed for its old "
        "signature — an org-wide unapproved action fan-out is exactly what the protocol exists to "
        "make impossible.'* It raises. The governed path is `executive/delegation.py`. ⛔ Listed so "
        "nobody wires it on the strength of its name, which is the one thing that would turn a "
        "correct refusal into the incident it refuses.",
        "MOVES WHEN the shim's old signature has no callers left anywhere and it can be deleted — "
        "not when something wants to call it"),

    "push.push_card_to_agents": (
        "⛔ THE PUSH HALF OF A SURFACE SERVED BY PULL. `agent_api.py` gives agents `poll_signals`, "
        "`get_artifact`, `claim` and `result`, and `push.py`'s own header states *'Body == the "
        "/v1/signals poll projection, so push and poll are interchangeable'* — so a polling agent "
        "gets everything a pushed one would. See PULL_ONLY below, which carries the surface claim "
        "and its own guard. ⛔ `push.py:19` claimed this function was *'fired by L5 when a card is "
        "emitted'* until 2026-10-01; nothing fired it, and a comment that states a wiring reads as "
        "a measurement somebody took.",
        "MOVES WHEN somebody decides agents should be notified rather than asked to poll — a "
        "product decision about whether an executor runs a loop or a listener"),

    "claim_validator.observed_claims": (
        "*'The sentences this card presents as lifted from a source. The set a reviewer should "
        "read.'* M13 STEP-03/04 built the claim vocabulary and its validator, both of which ARE "
        "called. ⛔ This is the reviewer's projection, and there is no reviewer surface: nothing "
        "renders a per-claim read for a human to check.",
        "MOVES WHEN a review surface exists. It is the natural reader and nobody has asked for it"),

    "claims.by_state": (
        "*'The mix, with every state declared — including the states that did not occur. A key that "
        "appears only when it fires is a key nobody knows exists.'* The same shape as "
        "`observed_claims`: a correct projection with no renderer.",
        "MOVES WHEN a review surface exists — the same mover, and the two should land together or "
        "the second will look like an oversight"),

    "scheduler.schedule_order": (
        "⛔ SUPERSEDED IN PLACE, NOT FORGOTTEN. *'Order due rows: highest effective (aged) priority "
        "first, then oldest first.'* The ORDERING RULE is live — `scheduler.rank_sql` is used by "
        "`api/delivery_routes.py` and by `spine.claim_due`'s `order by` — so what is uncalled is "
        "this in-process COMPOSITION of a rule that runs in SQL. Both exist because the rank must "
        "be identical in both places: the rule was moved into SQL after a text `priority` column "
        "sorted `background < critical` alphabetically and claimed critical work last.",
        "MOVES WHEN an in-process scheduler claims rows (the v2 path's tier 4). Until then it is "
        "the reference implementation the SQL is checked against"),

    "routing.is_agent_transport": (
        "⛔ NO DOCSTRING, AND THAT IS THE ENTRY. A leaf predicate with one test caller and no "
        "production caller, and **why it is unreached is recorded nowhere in the codebase.** "
        "Declaring it as deliberate would be inventing a reason; declaring it as a defect would be "
        "inventing a severity. What is true is that nobody wrote down what it is for.",
        "⛔ MOVES WHEN somebody who knows what it is for writes one line above it. Flagged for "
        "Harsh in HANDOFF-HARSH.md rather than guessed at here"),

    "lane_recall.low_confidence_is_never_silent": (
        "⛔ A BUILD-TIME PROPERTY GUARD, AND I FIRST FILED IT AS A DEFECT. *'Walk the real router: "
        "no decision under the floor may land in a silent lane.'* It takes **no data** — only "
        "`floor_bp`, with a default — and `lane_recall.py`'s header states the module is *'PURE. No "
        "I/O, no clock, no model.'* So it is not a production measurement at all: it walks the "
        "router over the confidence range and returns counter-examples, which is a question about "
        "CODE, answerable at build time and pointless at runtime. Its five callers in "
        "`tests/deliver/test_nothing_dies_of_low_confidence.py` are the correct and only ones. ⛔ "
        "**A function that takes no data cannot be measuring production.**",
        "MOVES WHEN it is deleted, or when the router's lane rules change and it is rewritten. ⛔ "
        "Never by being wired into a pass — calling it per org per tick would re-derive the same "
        "answer about unchanged code every time"),

    "lane_recall.every_lane_is_visible_or_deliberately_silent": (
        "⛔ THE SAME SHAPE, AND IT TAKES NO ARGUMENTS AT ALL. *'Totality, both directions, over the "
        "display vocabulary. Every lane a card can carry must be classified as one or the other.'* "
        "A closed-set totality check over two frozen tables — the answer cannot differ between two "
        "runs of the same build, so a runtime caller would be asking a settled question. Its one "
        "caller is the test that enforces it.",
        "MOVES WHEN the display vocabulary gains a lane and this is rewritten, or when it is "
        "deleted. ⛔ Not by being wired"),

    "act_pump.stop": (
        "⛔ CORRECTLY UNCALLED BY THE ENGINE, AND ITS OWN DOCSTRING SAYS WHO CALLS IT: *'Stop the "
        "pump (tests, shutdown).'* A lifecycle hook for a process boundary, not for engine code. "
        "It read as reached until STEP-13 because `stop` is a name four other objects in the "
        "engine also use — so the one entry here that is unambiguously fine was invisible for the "
        "same reason as the five that were not.",
        "MOVES WHEN a supervised shutdown path in `api/` or a worker entry point calls it. ⛔ Until "
        "then its absence from engine code is the correct state, not a gap."),

    "units.get_unit": (
        "⛔ NO DOCSTRING — same as `routing.is_agent_transport`. `units.py`'s public surface is "
        "`capability_report`, which IS called; this is a single-unit lookup beside it with two test "
        "callers and no production caller.",
        "⛔ MOVES WHEN a caller wants one unit rather than the report, or when it is deleted. "
        "Recorded as undocumented rather than described, because describing it would be a guess"),
}


#: ⛔ Built, reachable, and only ever PULLED — `{surface: (route, why it is not pushed)}`.
#:
#: These are NOT unreached: each has a live route and a caller. What none has is a PRODUCER — nothing
#: in the sweep composes it, so it exists for a client that asks. ⛔ The both-directions guard here is
#: different from `UNREACHED`'s and that difference is the point: a pull-only surface goes stale when
#: it acquires a producer, so the test asserts **the pull half is still reached AND the push half is
#: still not.** L4 shipped `PULL_ONLY` with only the first half and `summary.build_summary` sat in it
#: for weeks after `outbox._drain_claimed` started sending it on a tick.
PULL_ONLY: dict[str, tuple[str, str]] = {
    "agent_api.poll_signals": (
        "GET /v1/signals",
        "⛔ The agent surface is a LOOP, not a LISTENER, and that is a design rather than a gap. "
        "`poll_signals` plus `get_artifact`, `claim` and `result` is a complete executor contract, "
        "metered per agent per period. The push half — `push.push_card_to_agents` — is written, "
        "HMAC-signed, and wired to nothing; `push.py` states the bodies are identical, so pushing "
        "would change WHO initiates, not WHAT arrives. ⛔ And the transport for it exists: "
        "`channels/agent.py` is the largest adapter in `channels/` and `get_channel('agent_push')` "
        "returns it, so this is a decision not to fan out, not an absence of the means.",
        ),
}


# ---------------------------------------------------------------------------------------------
# ⛔ not decisions. defects — built, correct, and nothing calls them
# ---------------------------------------------------------------------------------------------

#: ⛔ `{name: (what is wrong, the step that closes it)}`.
#:
#: These are NOT declared silences and must never be read as any. Each is a function that is
#: correct, tested, and SHOULD be called by production code, and is not. They are in this module
#: rather than only in a plan document because a plan is not checked by the build and this is.
#:
#: ⛔ EVERY ENTRY NAMES A STEP, enforced by the test module. A declared defect with no owner is an
#: undeclared defect with better manners — the rule `reason/unit_health.DeclaredSilence` already
#: applies by refusing construction without a mover.
KNOWN_UNWIRED: dict[str, tuple[str, str]] = {
}


#: The union the undeclared-check walks. ⛔ `PULL_ONLY` is deliberately NOT in it: those surfaces are
#: REACHED, so including them would let a pull-only entry satisfy the unreached guard and a function
#: could go quiet without anybody noticing.
DECLARED: frozenset[str] = frozenset(UNCUT_OVER) | frozenset(UNREACHED) | frozenset(KNOWN_UNWIRED)


# ---------------------------------------------------------------------------------------------
# the walk
# ---------------------------------------------------------------------------------------------

def engine_sources() -> dict[str, str]:
    """Every engine module's source — ⛔ the ENGINE only, and that is the whole convention.

    A test is not a caller. Passing `tests/` in alongside `genios_engine/` makes any function with
    a unit test look reached, and it is how this layer's unreached count was first reported as 4
    when L4's own convention gives 24. ⛔ **A reachability number is meaningless without its source
    set**, so the set lives here, in code, where the test that uses it cannot quietly differ.
    """
    return {str(p): p.read_text(encoding="utf-8") for p in _ENGINE.rglob("*.py")}


def package_functions() -> dict[str, str]:
    """`{"module.function": module}` for every top-level public function in `deliver/`.

    `glob`, not `rglob` — top-level files only, matching `executive/unreached.py`'s scope. The four
    functions in `channels/` are adapters behind a registry seam, reached through `get_channel`
    rather than by name, so a by-name reachability walk reports them as dead and they are not.
    """
    out: dict[str, str] = {}
    for path in sorted(_PKG.glob("*.py")):
        if path.name in ("__init__.py", "delivery_health.py"):
            continue
        for fn in public_functions(path):
            out[f"{path.stem}.{fn}"] = path.stem
    return out


#: ⛔ `qualified_call_sites` AND `qualified_call_counts` NOW LIVE IN `executive/unreached.py`.
#: This module defined the first version, and STEP-13 promoted it beside `called_names` once a
#: second package needed it — two users is an import, three is an extraction, and L4's own
#: declaration needed it more urgently than L5 did: switching `_unreached()` to it found FIVE
#: `executive/` functions that had read as reached because they share a name with some method
#: elsewhere in the engine. `readiness.read` had 11 apparent callers and has none.
#:
#: ⛔ Re-exported here so this module's own callers and tests keep one import site.

def undeclared() -> tuple[str, ...]:
    """Public functions in `deliver/` the engine does not call and this module does not declare.

    ⛔ SWITCHED FROM `called_names` TO `qualified_call_counts` IN STEP-13, AND IT FOUND TWO MORE —
    `act_pump.stop` and `retry.defer_until`, both of which read as reached because another module
    has a function of the same name (`gate.defer_until` IS called; this one is not).

    The asymmetry argument this function was first written under — *keep the loose resolver here,
    because a false UNREACHED would demand a declaration for genuinely wired code* — ⛔ **stopped
    holding once the resolver became alias-aware.** The naive version did produce false unreached
    (`lane_display.describe`, called through `describe_lane`); resolving aliases to
    `(module, original)` removed that risk, and with it the reason to accept a false reached.
    """
    counts = qualified_call_counts(engine_sources())
    return tuple(sorted(
        q for q, module in package_functions().items()
        if counts.get((module, q.split(".", 1)[1]), 0) == 0 and q not in DECLARED))


def missing() -> tuple[str, ...]:
    """⛔ Declared entries naming a function that does not exist — the second direction.

    Declared-and-written are two directions, and one alone is half a guard: an entry for a deleted
    function reads as a considered decision about live code.
    """
    present = set(package_functions())
    return tuple(sorted(q for q in DECLARED if q not in present))


def now_called() -> tuple[str, ...]:
    """⛔ Declared entries the engine HAS started calling — the entry that has become a lie.

    One pass, not one per entry: `qualified_call_sites` re-parses the engine on every call, and 24
    entries meant 24 full parses. A guard too slow to run is a guard people skip.
    """
    counts = qualified_call_counts(engine_sources())
    return tuple(sorted(q for q in DECLARED
                        if counts.get((q.partition(".")[0], q.partition(".")[2]), 0) > 0))


__all__ = ["DECLARED", "KNOWN_UNWIRED", "PULL_ONLY", "UNCUT_OVER", "UNREACHED",
           "engine_sources", "missing", "now_called", "package_functions",
           "qualified_call_sites", "undeclared"]
