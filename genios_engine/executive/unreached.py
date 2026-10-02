"""What this layer built and does not call, declared — each with a reason and a mover.

⛔ THE DEFECT CLASS THIS FILE EXISTS FOR. A unit that is built, tested, green, and called by
nothing on a real path is indistinguishable from one that works — its tests pass, its coverage
looks fine, and the only symptom is a product that quietly does less than its code implies. Layer 2
counted it nine times, Layer 3 counted it twelve, and `reason/uncited_lanes` and
`reason/situation_binding` are the two places that made it visible there.

⛔ `executive/` HAD NO SUCH DECLARATION AT ALL, and that is why this file is the first thing to
land here. Every other layer can say which of its silences are deliberate; this one could not, so a
reader finding `monitor.blocking_action` with no caller had no way to tell a deferred feature from
a forgotten one. That ambiguity is the thing being fixed — not the silences themselves, which may
well be correct.

WHAT IS *NOT* WRONG WITH THIS LAYER, measured 2026-09-25, so nobody spends a day re-checking it:
the execution half is fully wired and runs on every heartbeat tick. `api/routes.py:1150` calls
`sweep.run_executive` for every org, before distribution, which plans commitments from
authoritative decisions and then validates, transitions, reminds, escalates and closes them.
`record_outcome` feeds Layer 7. Five tables (migration 0041) and delegation wiring (0157) exist.
`deliver/` imports eight things from here. Fourteen test files cover it.
"""

from __future__ import annotations

import ast
from pathlib import Path

#: ⛔ Public functions in `executive/` with no caller anywhere in the engine — `{name: (why, mover)}`.
#:
#: CLOSED, and checked in BOTH directions by `tests/test_the_executive_says_what_it_does_not_call`:
#: an entry naming a function that is now called is as much a lie as a function that is unreached
#: and undeclared. One direction alone is how `mcp/` escaped the import ratchet in L3-01.
UNREACHED: dict[str, tuple[str, str]] = {
    "coordination.can_complete": (
        "⛔ SUPERSEDED, NOT FORGOTTEN — and the difference is written down at its replacement. "
        "`can_complete` answers 'does this action exist, is it unticked, and are its deps done'. "
        "The live completion route (`api/executive_routes.complete_action`) deliberately calls "
        "`dependencies_met` instead and handles the already-ticked case differently: its own "
        "comment says 'only gate a KNOWN action with UNMET deps — an already-completed or unknown "
        "id falls through to the store, which is idempotent and returns recorded=false rather "
        "than a 409'. Routing an idempotent re-submit through `can_complete` would turn a "
        "double-click into an error. So the helper is correct and its composition is not what the "
        "surface wants.",
        "MOVES WHEN a second completion path appears that does want the combined check — an agent "
        "completing steps in bulk is the obvious candidate. Until then it is a helper with no "
        "caller, kept because deleting it would delete the test that documents the distinction."),

    "coordination.coordination_snapshot": (
        "Classifies every planned action as completed / ready / waiting, in ordinal order. "
        "Nothing renders that today: a commitment card shows its steps and their completion, not "
        "which are UNBLOCKED right now. The snapshot is the shape a 'what can I do next' view "
        "would read, and that view has not been asked for.",
        "MOVES WHEN a commitment surface shows next-actionable steps rather than all steps. It is "
        "the natural reader and it does not exist yet."),

    # -----------------------------------------------------------------------------------------
    # ⛔ FIVE ENTRIES ADDED 2026-10-01, EVERY ONE INVISIBLE UNTIL THE RESOLVER WAS FIXED.
    #
    # `called_names` counts by NAME ALONE, so each of these looked reached because some other
    # object in the engine has a method of the same name — `read` had 11 apparent callers, `is_live`
    # 3, `supersede` 2, `propose` 1. `qualified_call_counts` keys on `(module, name)` and resolves
    # aliases, and all five come back ZERO. Engine-wide the same measurement found 28 such
    # functions, which is `STEP-17` in the YCW27 programme.
    #
    # ⛔ The declaration was never WRONG. It was answering a question the tool could not ask.
    # -----------------------------------------------------------------------------------------

    "readiness.read": (
        "⛔ THE WHOLE MODULE IS UNREACHED, NOT JUST THIS FUNCTION. `read` -> `assess` -> `_verdict` "
        "is the entire public chain of `executive/readiness.py`, and `assess`'s single caller is "
        "`read` itself at `readiness.py:172`. Nothing calls `read`, and **no route exposes it**. "
        "⛔ Production still answers the question: `platform/receipts.py` reads the same three "
        "counts through `platform/org_readiness_sql.COUNT_SQL` — the module this file also imports, "
        "extracted precisely so *'duplicating them would let one drift from'* the other. So the "
        "extraction worked, the receipt works, and the executive-layer READER of it has no surface. "
        "What is missing is not logic; it is an API that asks for org readiness.",
        "MOVES WHEN a surface asks for organisation readiness per tenant. ⛔ Its docstring states "
        "what that surface would gain over re-reading the SQL: *'Every failed read becomes "
        "`unknown`, never `missing`. Each count is caught on its own, so one unreadable table does "
        "not turn the other two into `unknown`'* — a per-row seam a caller doing three reads would "
        "have to reimplement."),

    "execution_store.supersede": (
        "⛔ A RACE-FREE REPLACEMENT PATH WITH NO CALLER. *'Close a commitment because a newer plan "
        "replaces it. A changed plan is a changed commitment, so it gets its own row and its own "
        "identity rather than mutating the old one in place. Closing the predecessor frees the "
        "partial unique key, which is how the replacement lands without a race.'* Measured: zero "
        "qualified callers. So **a revised plan never closes the commitment it replaces** — and the "
        "partial unique key this function exists to free is the thing a replacement would collide "
        "with. It has not bitten because no decision has produced a second plan in production "
        "since the API spend limit began refusing calls on 2026-09-25.",
        "MOVES WHEN re-planning an open commitment is a path anyone takes. ⛔ Whether a revision "
        "should supersede or branch is a product question, and the function answers only one of "
        "the two."),

    "delegation.propose": (
        "⛔ SUPERSEDED IN PLACE BY TWO BETTER-NAMED SIBLINGS. *'The engine proposes handing one "
        "action to one agent. Nothing is sent.'* Measured against the live call sites: "
        "`propose_action` has 2 qualified callers and `create_proposal` 1, both reached through "
        "`from genios_engine.executive import delegation as DLG`; `DLG.propose` appears nowhere. "
        "Three entry points to one idea and the plainest name is the unused one, which is exactly "
        "the shape that makes a reader wire the wrong one.",
        "MOVES WHEN it is deleted, or when the three entry points are collapsed into one. ⛔ Listed "
        "rather than deleted here because deleting a public function is a boundary change nobody "
        "asked for -- see UNIT_NUMBERING_UNRESOLVED for the same restraint."),

    "execution_guard.is_live": (
        "⛔ NO DOCSTRING, AND THE THIRD SPELLING OF A SET THIS LAYER ALREADY FOUND. A bare state "
        "predicate over `ExecutionState`, sitting beside `lifecycle.is_terminal` — which this "
        "programme found untested in L4-STEP-10 and guarded in "
        "`tests/executive/test_a_closed_set_with_two_spellings.py`. `is_live`, `is_open` and "
        "`is_terminal` are three partitions of one closed table, written in three files, and **not "
        "one of them has a production caller.** ⛔ A guard written for one member of a closed table "
        "is half of that -- and this is the half that was invisible, because `is_live` is a name "
        "three other objects in the engine also use.",
        "MOVES WHEN all three spellings move together -- `lifecycle.is_open` and "
        "`lifecycle.is_terminal` with it, or none of them. ⛔ The open product question is L4's U6c, "
        "whether `CREATED` belongs in a state set, and answering it for one spelling while two "
        "others disagree is how the set drifts."),

    "lifecycle.is_open": (
        "⛔ NO DOCSTRING. The second of the three spellings above, in the module that also holds "
        "`is_terminal`. Two predicates over one closed table, in one file, neither called by "
        "production, and `is_terminal` got its first tests only on 2026-10-01.",
        "MOVES WHEN the three spellings move together -- see `execution_guard.is_live`. ⛔ Moving one "
        "alone is what produced three spellings in the first place."),

    "assignment.resolve_approver_seat": (
        "⛔ THE SECOND REAL PRODUCT GAP, AND ITS OWN DOCSTRING PREDICTS THE SYMPTOM: *'a card that "
        "says \"this needs sign-off\" and cannot say whose is less useful than one that can'*. "
        "Measured: the `requires_approval` FLAG is read — `contracts/execution.py:233` gates "
        "autonomy on it — but nothing ever resolves WHO must sign. So a commitment can announce "
        "that approval is required and can never name the approver. The function is careful about "
        "exactly the thing that makes this hard: `AuthorityView.resolve` has three outcomes, and "
        "only `enforced` may name anybody — `suggested` means observed behaviour matched and a "
        "human must confirm, `no_authority_rule` means the org holds no rule, which is NOT "
        "'anyone may approve'. Eight tests cover that distinction and no live path uses it.",
        "MOVES WHEN a commitment carrying `requires_approval` routes to an approver. That needs "
        "the org to have published authority rules at all — until it has, the honest answer is "
        "None and the card is right to say only that sign-off is needed. "
        "⛔ NOW COUNTED, 2026-10-01: `execution_actions` holds 794 rows and **410 carry "
        "`requires_approval`** — 52% of every action this layer has planned (182, 121, 107 across "
        "the three orgs) — against **zero** rows in `authority_rules`. A mover without a number "
        "is a wish, so receipt #32 `every action that needs sign-off can name who signs` now "
        "counts it and is RED at 410. "
        "⛔ AND THE WIRING IS BLOCKED TWICE, which is why this entry is not being deleted: "
        "neither `execution_actions` nor `executions` has an approver column, so consuming an "
        "answer needs a contract field and a migration — and `0186`-`0190` have never run. "
        "Wiring it today would add a column that `None` fills on every row while deleting the "
        "only place this reason is written down."),

    "execution.build_from_decision": (
        "AN ALTERNATIVE ENTRY SHAPE, NOT A BYPASSED GATE — and the distinction took a measurement. "
        "Its docstring says it exists 'so callers — the sweep, the API, the tests — cannot "
        "accidentally assemble the units in a different order', which reads like the sweep should "
        "be using it and is not. It is not: `build_from_decision` starts from a "
        "`ReasoningDecision` OBJECT via `interpret_decision`, while `plan_commitments` starts "
        "from a SQL ROW via `build_context`. Both then run the identical `resolve_owner` -> "
        "`build_execution` tail, so the ordering the docstring protects is not actually at risk. "
        "What has no live caller is the object-shaped front door, because nothing on a real path "
        "holds a decision object when it wants a commitment.",
        "MOVES WHEN something builds a commitment from a decision it already has in memory — the "
        "compiled lane emitting directly, or an API that accepts a decision. Neither exists."),

    "lifecycle.is_terminal": (
        "The trivial half of a pair: `is_open` is used, `is_terminal` is not. `state in "
        "TERMINAL_STATES` is a one-line membership test that every caller happens to phrase "
        "directly. ⛔ It is declared here rather than deleted for one reason: `TERMINAL_STATES` is "
        "the closed set that decides when a commitment stops being advanced, and a named "
        "predicate over it is where a future reader will look. Deleting it would push the next "
        "caller to re-inline the membership test, which is how a closed set acquires a second "
        "spelling. ⛔ It carries NO tests, which is the weaker state — same as `blocking_action`.",
        "⛔ MEASURED 2026-10-01, AND THE ANSWER IS THAT IT CANNOT MOVE WHERE IT WOULD BE WANTED. "
        "The prediction above came true: `execution_guard.py:126` re-inlines "
        "`state.state in TERMINAL_STATES` as its very first branch — a second spelling of the "
        "closed set already exists, in the one place that most wants the predicate. "
        "⛔ AND IT CANNOT HAVE IT: `lifecycle.py:39` imports `GuardAction` and `GuardVerdict` "
        "FROM `execution_guard`, so the dependency runs lifecycle -> guard and importing "
        "`is_terminal` back would be a circular import. The caller that wants it is the one "
        "caller that may not have it. "
        "MOVES WHEN either the predicate moves to `contracts/execution`, beside the "
        "`TERMINAL_STATES` it reads — which adds no dependency, since the set is already there — "
        "or a caller outside that cycle wants it. ⛔ IT NOW CARRIES TESTS "
        "(`tests/executive/test_a_closed_set_with_two_spellings.py`), so it is no longer in the "
        "weaker of the two states; `blocking_action` was the other and is now wired."),

}

#: ⛔ Built, reachable, and only ever PULLED — `{surface: (route, why it is not pushed)}`.
#:
#: ⛔ `summary.build_summary` WAS HERE AND IS NOT ANY MORE, 2026-10-01. Its entry said the ladder
#: *"is still only composed where a caller asks for a summary, never as a scheduled digest"*, and
#: that had stopped being true: `deliver/outbox._current_digest_payload` composes a `one_minute`
#: summary and `_drain_claimed` sends it on the very next line (`outbox.py:1073`, inside `drain`).
#: It has a route AND a producer, so it is not pull-only — it is simply shipped.
#:
#: ⛔ AND THE ONLY REASON THAT SURVIVED is that this table had no both-directions guard. `UNREACHED`
#: has one, and `modes.load_preventive` had a BESPOKE one
#: (`test_the_preventive_surface_records_that_no_card_is_built`) that was never generalised — so
#: four of the five surfaces were never asked whether they had acquired a producer.
#: `test_no_pull_only_surface_has_quietly_acquired_a_producer` is the general form.
#: **One direction alone is half a guard, and a guard written for one member of a closed table is
#: half of that.**
#:
#: These are not unreached: each has a live HTTP route and a caller. What none of them has is a
#: producer — nothing in the sweep composes them, so they exist only for a client that asks. That
#: is a product decision rather than a defect, and it is recorded here because "there is an
#: endpoint" and "the founder sees it" are different claims that look identical from the code.
PULL_ONLY: dict[str, tuple[str, str]] = {
    "brief.load_briefs": (
        "GET /briefs",
        "⛔ `brief.py` calls the Decision Brief *'brief.v1, the executive unit of output'* — the "
        "layer's own name for what it produces. Nothing in `sweep.py` composes one, so the unit "
        "of output is never produced on a tick; a client must ask. Whether a brief should arrive "
        "each morning or be fetched on demand is a product question nobody has answered."),

    "modes.load_preventive": (
        "GET /preventive",
        "⛔ THE ONE THAT MATTERS MOST. `modes.py` names preventive mode *'the vision's USP'* and "
        "quotes the product's own sentence for it. Measured: `deliver/` contains NO reference to "
        "preventive anything, so no preventive finding has ever become a card. The warning exists "
        "and has to be requested. ⛔ Turning it into a push is NOT a small change: every "
        "elapsed-time rule condition on every node produces a clock reading, so a naive 'one card "
        "per finding' would spend the daily card budget on warnings. It needs a threshold, and "
        "the threshold is a product decision about how many warnings a founder should see a day."),

    "memory": (
        "GET /memory",
        "Executive memory is WORKING CONTEXT — what was recently decided — not storage. Nothing "
        "carries it into a later decision automatically; a client reads it. Making it push would "
        "mean deciding what 'recently' means per tenant, which nobody has."),

    "explain.why_not": (
        "GET /why-not",
        "*'Why did GeniOS not tell me about X?'* — answered from `signal_suppression_log`, which "
        "the reasoner has written a reason-coded row to since day one. This is CORRECTLY pull: a "
        "receipt for a silence is asked for, never volunteered. Listed so it is not mistaken for "
        "a missing push."),
}

#: ⛔ A declared UNKNOWN, not a finding. The module docstrings number the units 1, 2, 2.5, 3, 4, 5,
#: 7, 9 and 10; `assignment`, `escalation` and `execution_guard` say "Unit" with no number; 6 and 8
#: are absent. THREE unnumbered files and TWO gaps do not divide cleanly, so they are not simply
#: the missing numbers.
#:
#: NO CONCLUSION IS DRAWN, DELIBERATELY. The L5 specification that assigned these numbers is not in
#: this repository, and Layer 3 spent a step learning what happens when a capability is declared
#: missing on the strength of a search for names nobody uses — `prior_decision 0` was a grep, and
#: the capability it declared absent had been running on every sweep for months. An absent number
#: is not an absent unit.
UNIT_NUMBERING_UNRESOLVED: str = (
    "Units 6 and 8 have no file and three files carry no number. Cannot be resolved without the "
    "L5 spec. MOVES WHEN somebody supplies it; until then this is an open question, not a gap.")


# ---------------------------------------------------------------------------------------------
# ⛔ THE MACHINERY MOVED TO `platform/reachability.py` — 2026-10-01, STEP-17
# ---------------------------------------------------------------------------------------------
#
# This module wrote the AST walk and the two resolvers, and `deliver/delivery_health.py` imported
# them from here, which was correct while there were two users: `deliver/` is PRODUCT layer 6 and
# `executive/` is 5, so that import is DOWNWARD and legal.
#
# ⛔ `capture/` IS LAYER 1. `capture/ -> executive/` is an UPWARD import that
# `tests/test_layer_topology.py` fails the build over, so the eleventh package could not have used
# this. **Two users is an import; eleven is an extraction**, and the only place every layer may
# import from is `CROSS_CUTTING`.
#
# They are RE-EXPORTED here, not merely moved, because L4's own tests import them from this module
# and a public surface is not changed as a side effect of an extraction. Every docstring, every
# recorded mistake and the asymmetry between the two resolvers travelled with them.
from genios_engine.platform.reachability import (  # noqa: E402  (deliberate: after the tables)
    call_sites,
    called_names,
    public_functions,
    qualified_call_counts,
    qualified_call_sites,
)


def undeclared(unreached: frozenset[str]) -> tuple[str, ...]:
    """Unreached functions with no entry above — a silence nobody wrote down."""
    return tuple(sorted(unreached - set(UNREACHED)))


def missing(unreached: frozenset[str]) -> tuple[str, ...]:
    """Declared entries that are now called, or gone — the declaration having gone stale."""
    return tuple(sorted(set(UNREACHED) - unreached))


__all__ = ["PULL_ONLY", "UNIT_NUMBERING_UNRESOLVED", "UNREACHED", "call_sites",
           "called_names", "missing", "public_functions", "qualified_call_counts",
           "qualified_call_sites", "undeclared"]
