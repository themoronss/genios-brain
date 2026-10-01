# Step 7 — ✅ DONE · a reminder names the step it waits on

> **Unit** U3 · **11 tests · 6 mutations, all caught** · ⛔ **the first tests `blocking_action`
> has ever had**
> **UNREACHED: 6 → 5.** The only entry with no tests is now the only entry that is wired.

---

## 1 · What was actually wrong — and it is worse than the plan described

`unreached.py` said every stalled-commitment escalation is *"your Acme follow-up is stalled"*
rather than *"stuck on getting it approved"* — a **missing** nicety. The code said something else:

    contracts/execution.py:508   first_action  ->  self.actions[0]              ⛔ no completion filter
    executive/monitor.py         _next_action  ->  first action NOT in completed   ✅ correct
    executive/reminder.py:214    "next_action": execution.first_action.label      ⛔ the defect

`reminder_facts` is, in its own words, *"quite literally the vocabulary of what a reminder is
allowed to say"*. And `next_action` travels out of it:

    reminder_facts  ->  store.record_reminder(facts=…)
                    ->  deliver/executive_bridge.py:105   "next_action": str(facts.get(…) or "")
                    ->  deliver/channels/slack.py:125     into the message

⛔ **So a commitment whose first step was finished was reminded about the finished step.** That is
the thing `sweep.py`'s own docstring calls the worst this layer can do:

> *"The single most damaging thing a system like this can do is nudge somebody about work the world
> already finished, and the only structural defence is to make the guard unskippable."*

The existing guard (`execution_guard.validate`) stops a reminder about a **resolved situation**. It
never stopped one from **naming a completed step inside a live commitment**.

⛔ **And the function that fixes it was already written** — `monitor.blocking_action` is
`_next_action`, which skips completed actions. It was one of two `UNREACHED` entries and **the only
one with no tests at all.**

## 2 · ⛔ LATENT, not live — and this is where it was nearly got wrong

    executions                         186
      with >= 1 completed action         0     ⛔ ZERO
      with the first action completed    0
      that AND reminded                  0
    execution_actions          794 rows, 0 completed

**Not one action has ever been completed**, so `first_action` and `_next_action` have agreed on
every commitment in existence and the defect has never fired. ⛔ **Fourteenth near-miss** — it
would have been reported as live.

**It fires on the first completion, and `api/executive_routes.complete_action` is a live route.**

> ⛔ **A defect that fires on the first use of a feature is better fixed before the feature is
> used.** That is the argument for building this now rather than filing it — and it is the
> opposite of U2's, where the prerequisite was missing and building would have produced a column
> `None` fills.

## 3 · What was built

| Artifact | What |
|---|---|
| `executive/reminder.reminder_facts` | takes `report`, **required and keyword-only**; `next_action` is the blocking step |
| `executive/sweep.py:477` | passes the `report` that was **already in scope** at that line (from `observe` at 435) |
| `executive/unreached.py` | the `monitor.blocking_action` entry **deleted** — the function is called now |
| `tests/executive/test_a_reminder_names_the_step_it_waits_on.py` | 11 tests, six of them `blocking_action`'s first ever |

### ⛔ `report` is required, not optional with a fallback

An optional `report` defaulting to `first_action` leaves the wrong value **reachable**, and this
codebase has two names for a wrong value left reachable — `not_carried` and the six-times defect —
because it gets reached. There was exactly **one** caller and the report was already in scope at
that line, so a default buys nothing and costs the guarantee.

### ⛔ The key is ABSENT when nothing is outstanding — not empty, not the last step

`reminder_facts` is a **closed vocabulary**: a key being present is what *licenses* a sentence
about it. With every step complete there is no next action, so offering one — even `""`, even the
last step — licenses a reminder to name something. `executive_bridge.py:105` already reads it as
`str(facts.get("next_action") or "")`, so absence renders as nothing rather than raising.

### ⛔ One fix covers both rungs

The escalation rung fires at `sweep.py:465`, immediately before `record_reminder` at `:473` — **the
same facts corpus serves remind and escalate.** The plan said *"the `remind` and `escalate` rungs
carry the blocking step"*; they share one vocabulary, so it is one change.

⛔ **And timing did not move.** Day 1/3/7/14 and `max_rungs: 6` are untouched. This is escalation
**copy**, not ladder **policy** — and the field went on the **vocabulary**, never on the plan, so
execution objects stay frozen and content-addressed and *"why did this escalate on day 7?"* is
still answerable months later.

## 4 · Scenario → result

| Scenario | Result |
|---|---|
| nothing done | names `actions[0]` — unchanged |
| first step done | ⛔ names the **second**, where it used to name the first |
| first two done | names the third |
| a later step done first | names the earliest outstanding — membership, not a cursor |
| everything done | `blocking_action` → `None`, and `next_action` is **absent from the vocabulary** |
| an unknown completed id | ignored; it consumes no step |

## 5 · The mutations — all six caught

| | Mutation | Caught by |
|---|---|---|
| M1 | back to `first_action` (the original defect) | 3 tests |
| M2 | name the last step instead of `None` when all are done | 2 tests |
| M3 | drop the completed filter | 6 tests |
| M4 | make `report` optional | the signature test |
| M5 | `""` instead of absent | the vocabulary test |
| M6 | ⛔ put the `UNREACHED` entry **back** | the both-directions guard, 2 tests |

## 6 · ⛔ Two of my own mistakes, and the second is the fifteenth of its kind

**1 · The fixture.** My first draft hand-built an `ExecutionObject` from a dict. `ExecutionObject`
holds a dozen invariants — a commitment may not outlive its decision, a read-only action may not
carry an external kind, autonomy fails closed — and a hand-built dict either trips them or, worse,
is shaped to dodge them and stops being a commitment. Replaced with
`tests/test_executive_execution.build`, which goes through `build_from_decision` — **the
object-shaped front door that `unreached.py` declares, and whose only callers are tests.** The
tests now exercise an object the production builder would also produce.

And they assert against the plan's **own** ids and labels rather than hard-coded `"a1"`, because a
hard-coded id makes a test a statement about the fixture rather than about the function.

**2 · ⛔ My own blunt-grep.** `test_the_vocabulary_reads_the_blocking_helper` asserted
`"first_action" not in inspect.getsource(reminder_facts)`. It **failed on correct code**, because
`getsource` includes the docstring and that docstring *explains the old `first_action` read* in
order to warn the next reader.

> ⛔ **Fifteenth instance in this programme of an assertion reading prose as code.** Replaced with
> an AST walk: no `ast.Attribute` named `first_action` in the body, and `blocking_action` among the
> called names. Structure cannot be satisfied or broken by prose.

## 7 · And the declaration's own count guard

`tests/test_the_executive_says_what_it_does_not_call::test_the_count_is_six_and_they_are_the_measured_six`
pinned the exact set, with *"It may shrink; it may not grow without somebody writing down why."*

**It shrank the way the docstring invites**: 6 → 5, renamed, and the reason written into it — what
`blocking_action` was doing wrong, where the value travelled, that 0 of 794 actions were completed,
and where the tests are.

⛔ **And two stale facts in that file's own docstring were corrected while there**: `executive/` is
**27 files / 6,167 lines** (it said 25 / 5,731) and the sweep is called at **`api/routes.py:1195`**
(it said `:1150`) — which is **F11**, now fixed at its source as well as recorded.

    UNREACHED  6 -> 5
    real product gaps  2 -> 1   (`assignment.resolve_approver_seat`, blocked twice — see STEP-06)
