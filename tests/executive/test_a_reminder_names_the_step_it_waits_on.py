r"""`U3` · a reminder named `actions[0]` whether or not `actions[0]` was already done.

⛔ WHAT WAS WRONG, AND IT IS NOT THE MISSING FEATURE `unreached.py` DESCRIBES. That entry says
every stalled-commitment escalation is *"your Acme follow-up is stalled"* rather than *"stuck on
getting it approved"*. The code says something worse:

    contracts/execution.py:508   first_action   ->  self.actions[0]        no completion filter
    executive/monitor.py         _next_action   ->  first action NOT in completed   ✅ correct
    executive/reminder.py:214    "next_action": execution.first_action.label          ⛔

`reminder_facts` is *"quite literally the vocabulary of what a reminder is allowed to say"*, and
`next_action` travels out of it into `deliver/executive_bridge.py:105` and onto a Slack message at
`deliver/channels/slack.py:125`. ⛔ **So a commitment whose first step is finished is reminded
about the finished step** — which is the exact thing `sweep.py`'s own docstring calls the worst
thing this layer can do:

> *"The single most damaging thing a system like this can do is nudge somebody about work the
> world already finished, and the only structural defence is to make the guard unskippable."*

The existing guard (`execution_guard.validate`) stops a reminder about a **resolved situation**. It
does not stop one from **naming a completed step inside a live commitment**.

⛔ AND THE FUNCTION THAT FIXES IT WAS ALREADY WRITTEN, UNCALLED AND UNTESTED. `monitor.blocking_action`
is `_next_action` — it skips completed actions — and it is one of two entries in
`executive/unreached.UNREACHED`, the only one with **no tests at all**.

⛔ LATENT, NOT LIVE — measured 2026-10-01, and this is the part that was nearly got wrong:

    executions                        186
      with >= 1 completed action        0     ⛔ ZERO
      with the first action completed   0
    execution_actions          794 rows, 0 completed

**Not one action has ever been completed**, so `first_action` and `_next_action` have agreed on
every commitment that exists and the defect has never fired. It fires on **the first completion**,
and `api/executive_routes.complete_action` is a live route.

> ⛔ **A defect that fires on the first use of a feature is better fixed before the feature is
> used.** That is why this was built now rather than filed.

## Living log

    2026-10-01   0 of 794 actions completed, so 0 rows are affected today
                 reminder_facts had exactly ONE caller (`sweep.py:477`), and the same facts
                 corpus serves the remind rung AND the escalate rung — one fix covers both
"""
from __future__ import annotations

import inspect

from genios_engine.executive.monitor import ProgressReport, blocking_action
from genios_engine.executive.reminder import reminder_facts

# ⛔ THE EXISTING FIXTURE, NOT A SECOND ONE. `ExecutionObject` holds a dozen invariants — a
# commitment may not outlive its decision, a read-only action may not carry an external kind,
# autonomy fails closed — and a hand-built dict either trips them or, worse, is shaped to avoid
# them and stops being a commitment. `tests/test_executive_execution.build` already goes through
# `build_from_decision`, which is the object-shaped front door, so these tests exercise an object
# the production builder would also produce.
from tests.test_executive_execution import NOW, build


def _report(*completed: str, stalled: bool = True) -> ProgressReport:
    return ProgressReport(completed_action_ids=tuple(completed), current_stage=1,
                          progress_bp=0, stalled=stalled, last_progress_at=None,
                          outcome_kind=None, outcome_observed_at=None, detail="")


def _execution():
    """A real commitment from the shared builder, with at least two steps to block on."""
    execution = build().require()
    assert len(execution.actions) >= 2, (
        "⛔ this file's whole question is which of SEVERAL steps is outstanding. The shared "
        f"fixture now builds {len(execution.actions)} action(s); these tests cannot distinguish "
        "`first_action` from the blocking one on a single-step plan")
    return execution


def _ids(execution) -> tuple[str, ...]:
    return tuple(action.action_id for action in execution.actions)


def _decision(execution):
    """A reminder decision for a live, un-nudged commitment.

    ⛔ `state` is the commitment's `ExecutionState`, not the reminder's own `ReminderState` —
    `decide_reminder` takes BOTH and the second is `history`. The first draft of this file passed a
    `ReminderState()` as `state` and died on `.value`, which is the shape of mistake a keyword-only
    signature exists to make loud instead of silent.
    """
    from genios_engine.contracts.execution import ExecutionState
    from genios_engine.executive.reminder import ReminderState, decide_reminder

    return decide_reminder(execution, state=ExecutionState.RUNNING,
                           history=ReminderState(), now=NOW)


# ══ 1 · `blocking_action` itself — it had NO tests ════════════════════════════════
#
# ⛔ Every assertion below is relative to the plan's OWN ids and labels, read off the fixture.
# Hard-coding "a1" would make these tests a statement about the fixture rather than about the
# function, and the first pack change would turn them green on nothing.

def test_it_names_the_first_step_nobody_has_done() -> None:
    execution = _execution()
    assert blocking_action(execution, _report()) is execution.actions[0]


def test_it_SKIPS_a_completed_step_and_this_is_the_whole_point() -> None:
    """⛔ The one behaviour that distinguishes it from `first_action`, which is what ships today."""
    execution = _execution()
    first, second = execution.actions[0], execution.actions[1]

    assert blocking_action(execution, _report(first.action_id)) is second
    assert execution.first_action is first, (
        "`first_action` must still be actions[0] — this test shows the two DISAGREE, it does not "
        "change the contract property")
    assert second.label != first.label, "the fixture's steps must be distinguishable"


def test_it_skips_a_run_of_completed_steps() -> None:
    execution = _execution()
    done = [a.action_id for a in execution.actions[:-1]]
    assert blocking_action(execution, _report(*done)) is execution.actions[-1]


def test_completion_order_does_not_matter_only_membership() -> None:
    """A later step finished first is still finished. The report is a SET of ids, not a cursor."""
    execution = _execution()
    assert blocking_action(execution, _report(execution.actions[1].action_id)) is (
        execution.actions[0])
    if len(execution.actions) >= 3:
        out_of_order = _report(execution.actions[2].action_id, execution.actions[0].action_id)
        assert blocking_action(execution, out_of_order) is execution.actions[1]


def test_everything_done_is_None_and_not_the_last_step() -> None:
    """⛔ `None` is a real answer. Returning the last action would name finished work — the defect
    this function exists to avoid, one step further along."""
    execution = _execution()
    assert blocking_action(execution, _report(*_ids(execution))) is None


def test_an_unknown_completed_id_is_ignored_rather_than_shifting_the_answer() -> None:
    """A stale or foreign id must not consume a step. Membership is checked against the plan's own
    ids, so an unrecognised one matches nothing."""
    execution = _execution()
    assert "act_99" not in _ids(execution)
    assert blocking_action(execution, _report("act_99")) is execution.actions[0]


# ══ 2 · the vocabulary — what a reminder is ALLOWED to say ════════════════════════

def test_the_vocabulary_names_the_blocking_step_not_the_first_one() -> None:
    """⛔ THE DEFECT, AS A TEST. With `act_1` done, the old code offered "call the vendor" — a
    step the owner has already completed — to the Slack renderer."""
    execution = _execution()
    first, second = execution.actions[0], execution.actions[1]
    decision = _decision(execution)
    facts = reminder_facts(execution, decision, NOW, report=_report(first.action_id))

    assert facts["next_action"] == second.label
    assert facts["next_action"] != execution.first_action.label, (
        "the vocabulary still carries actions[0] — a reminder can name work that is done")


def test_nothing_left_to_do_leaves_next_action_OUT_of_the_vocabulary() -> None:
    """⛔ ABSENT, NOT EMPTY, AND NOT THE LAST STEP.

    `reminder_facts` is the closed vocabulary the invention validator checks against: a key that
    is present licenses a sentence. With every step complete there is no next action, so the key
    must not be there at all — anything else licenses a reminder to name something.

    `deliver/executive_bridge.py:105` already reads it as `str(facts.get("next_action") or "")`,
    so an absent key renders as nothing rather than raising.
    """
    execution = _execution()
    decision = _decision(execution)
    facts = reminder_facts(execution, decision, NOW, report=_report(*_ids(execution)))

    assert "next_action" not in facts, (
        "with nothing outstanding the vocabulary must not offer a next action at all")


def test_the_report_is_REQUIRED_so_the_wrong_value_is_unreachable() -> None:
    """⛔ NOT AN OPTIONAL ARGUMENT WITH A FALLBACK.

    An optional `report` defaulting to `first_action` would leave the wrong value reachable, and
    this codebase has a name for a wrong value left reachable: it gets reached. `reminder_facts`
    had exactly ONE caller, and the report was already in scope at that line, so there is no cost
    to making it required and a real cost to not.
    """
    signature = inspect.signature(reminder_facts)
    report = signature.parameters.get("report")
    assert report is not None, "`reminder_facts` must take the progress report"
    assert report.kind is report.KEYWORD_ONLY, "keyword-only, like every other seam here"
    assert report.default is inspect.Parameter.empty, (
        "⛔ a default makes the actions[0] behaviour reachable again. One caller; no default")


def test_the_vocabulary_reads_the_blocking_helper_rather_than_reimplementing_it() -> None:
    """Two spellings of "which step is outstanding" is how the two drift. `monitor` owns it."""
    # ⛔ THE AST, NOT THE TEXT — and the first draft of this assertion was itself the defect it
    # guards against. `inspect.getsource` includes the docstring, and that docstring EXPLAINS the
    # old `first_action` read in order to warn the next reader. A substring check therefore failed
    # on correct code because of its own prose. Fifteenth instance in this programme of an
    # assertion reading prose as code; the structural read cannot.
    import ast
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(reminder_facts)))
    function = tree.body[0]
    assert isinstance(function, ast.FunctionDef)

    called = {node.func.id if isinstance(node.func, ast.Name) else
              node.func.attr if isinstance(node.func, ast.Attribute) else ""
              for node in ast.walk(function) if isinstance(node, ast.Call)}
    assert "blocking_action" in called, (
        "`reminder_facts` must CALL `monitor.blocking_action`, not re-derive the outstanding step "
        "— two spellings of 'which step is outstanding' is how the two drift")

    read = {node.attr for node in ast.walk(function) if isinstance(node, ast.Attribute)}
    assert "first_action" not in read, (
        "⛔ `first_action` is still read in the body — that is the defect. It is `actions[0]` with "
        "no completion filter, and this vocabulary is what a Slack message is worded from")


# ══ 3 · and the declaration must stop claiming it is uncalled ════════════════════

def test_the_unreached_entry_is_GONE_because_the_function_is_now_called() -> None:
    """⛔ BOTH DIRECTIONS, OR IT IS HALF A GUARD.

    `tests/test_the_executive_says_what_it_does_not_call` checks that an entry naming a function
    which IS called is as much a lie as a function unreached and undeclared. `blocking_action` is
    now on the reminder path, so its entry must be gone — and that test failing is how a reader
    would know it had been left behind.
    """
    from genios_engine.executive import unreached

    assert "monitor.blocking_action" not in unreached.UNREACHED, (
        "the function is called from `reminder_facts` now; the declaration must not still say it "
        "is unreached")
