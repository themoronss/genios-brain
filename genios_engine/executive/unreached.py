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
        "None and the card is right to say only that sign-off is needed."),

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
        "MOVES WHEN a caller wants the predicate rather than the set — or it is deleted, which is "
        "an equally acceptable resolution and would simply remove this entry."),

    "monitor.blocking_action": (
        "⛔ THE ONE WORTH READING TWICE, AND THE ONLY ONE HERE THAT IS A REAL PRODUCT GAP. Its own "
        "docstring states the case: *'What a stalled-commitment escalation should actually name. "
        "\"Your Acme follow-up is stuck on getting it approved\" is a message somebody can act on; "
        "\"your Acme follow-up is stalled\" is a message somebody can only feel bad about.'* "
        "Measured: `executive/escalation.py` and `deliver/` contain no reference to a blocking "
        "step, so every stalled-commitment escalation today is the second sentence. ⛔ AND IT IS "
        "THE ONLY ENTRY IN THIS TABLE WITH NO TESTS EITHER — unreached and unexercised, which is "
        "the weaker of the two states.",
        "MOVES WHEN the escalation ladder's `remind` and `escalate` rungs name the step they are "
        "waiting on. That is a change to escalation copy, not to the ladder's timing, so it does "
        "not touch policy — but it needs the rung to carry a field it does not carry today."),
}

#: ⛔ Built, reachable, and only ever PULLED — `{surface: (route, why it is not pushed)}`.
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

    "summary.build_summary": (
        "GET /summary",
        "The one_line / one_minute / five_minute ladder. `deliver/outbox.py:315` does import it, "
        "so this one is closer to pushed than the others — it is listed because the ladder itself "
        "is still only composed where a caller asks for a summary, never as a scheduled digest."),

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


def public_functions(module_path: Path) -> tuple[str, ...]:
    """Every module-level public function in `module_path`, read from the AST.

    ⛔ THE AST, NOT THE TEXT, and module scope only — so a nested helper, a method, or a name that
    appears in a docstring cannot enter the inventory. Ten assertions on this branch went green or
    red on a word that lived only in prose; a structural read cannot.
    """
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):                            # pragma: no cover - unreadable file
        return ()
    return tuple(node.name for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and not node.name.startswith("_"))


def call_sites(name: str, sources: dict[str, str]) -> int:
    """How many times `name` is CALLED across `sources`, ignoring its own definition.

    Counts `ast.Call` nodes whose callee resolves to `name`, whether called bare (`f()`) or
    through an attribute (`mod.f()`). A definition, an `__all__` entry and a mention in prose are
    none of them calls — which is the distinction the hand-written grep that preceded this could
    not make, and it reported two functions as dead that are called on live paths.
    """
    total = 0
    for source in sources.values():
        try:
            tree = ast.parse(source)
        except SyntaxError:                                   # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id == name:
                total += 1
            elif isinstance(func, ast.Attribute) and func.attr == name:
                total += 1
    return total


def called_names(sources: dict[str, str]) -> dict[str, int]:
    """Every name CALLED anywhere in `sources`, counted — in ONE pass over each file.

    ⛔ WHY THIS EXISTS BESIDE `call_sites`. The first version of this guard asked `call_sites` once
    per candidate function, so it re-parsed all ~600 engine modules for each of ~80 public
    functions — roughly 48,000 AST parses, and the test ran for minutes instead of seconds. A
    correctness guard that is too slow to run is a guard people start skipping, which is a worse
    failure than the one it catches. Same answer, one pass.
    """
    counts: dict[str, int] = {}
    for source in sources.values():
        try:
            tree = ast.parse(source)
        except SyntaxError:                                   # pragma: no cover
            continue
        # ⛔ ALIASES FIRST, AND THIS IS NOT OPTIONAL. `deliver/actions.py` does
        # `from genios_engine.executive.execution_store import link_card as _link_execution_card`
        # and then calls the ALIAS. Counting only the bare name reported `link_card` — a function
        # on the live card-completion path — as dead, which is precisely the false verdict this
        # guard exists to prevent. Every renamed import is resolved back to its original name.
        aliases: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    if alias.asname:
                        aliases[alias.asname] = alias.name.rsplit(".", 1)[-1]
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (func.id if isinstance(func, ast.Name)
                    else func.attr if isinstance(func, ast.Attribute) else None)
            if name is None:
                continue
            name = aliases.get(name, name)
            counts[name] = counts.get(name, 0) + 1
    return counts


def undeclared(unreached: frozenset[str]) -> tuple[str, ...]:
    """Unreached functions with no entry above — a silence nobody wrote down."""
    return tuple(sorted(unreached - set(UNREACHED)))


def missing(unreached: frozenset[str]) -> tuple[str, ...]:
    """Declared entries that are now called, or gone — the declaration having gone stale."""
    return tuple(sorted(set(UNREACHED) - unreached))


__all__ = ["PULL_ONLY", "UNIT_NUMBERING_UNRESOLVED", "UNREACHED", "call_sites",
           "called_names", "missing",
           "public_functions", "undeclared"]
