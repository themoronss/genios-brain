# Step 7 — DONE · four comments that read as measurements

**Unit:** `M13.C3.U07` · **Owner:** me · ✅ **2026-10-01** · 6 tests · 5 mutations
⛔ **Planned as two corrections. There were four, and one of them was in a test.**

## 1 · What is there

### 1.1 `push.py:19`

> *"`push_card_to_agents` — proactive "here's a new signal" **(fired by L5 when a card is emitted)**."*

⛔ **Nothing fires it.** Zero references in the repo.

### 1.2 `units.py`, justifying `PUSH_REQUIRES_ADAPTER`

> *"`channels/base.get_channel` returns Slack or None — **one implementation** across every push channel
> named here."*

⛔ Measured: `get_channel` returns Slack **or `AgentWebhookChannel`**.

```
IMPLEMENTED push channels: ['agent_push', 'slack']  (2 of 6)
MISSING adapter          : ['api', 'email', 'teams', 'webhook']
```

`channels/agent.py` is 11,906 bytes — the **largest** adapter in the folder — dated two days after
`base.py`. The transport was built after the comment, and the comment was never revisited.

## 2 · Why these matter more than their size suggests

⛔ **A stale comment reads as a measurement.** Sixth occurrence in this programme, and the two here are
the dangerous kind: **the behaviour is correct and the prose is not.** `_implemented_channels()` computes
the answer at runtime, so `capability_report` has always been right. Only the sentence a human reads is
wrong — so no test fails, no receipt goes red, and the error is invisible until somebody answers a
customer question from it.

The specific harm, in each case:

| Comment | What the next reader concludes |
|---|---|
| `push.py:19` | agents **are** notified when a card is emitted. They are not — they poll |
| `units.py` | the agent surface has **no** adapter, so building one is open work. It exists and is registered |

⛔ The second is worse than it looks: it is the **justification** for a frozen set that governs which
units can ever be reported operational. A reader deciding whether to build the agent adapter reads that
sentence and builds a second one.

## 3 · What to build

| | |
|---|---|
| `deliver/push.py:19` | correct the comment: proactive push is **written and not wired**; agents receive via `agent_api.poll_signals`; point at the `PULL_ONLY` entry from STEP-05 |
| `deliver/units.py` | correct to *"Slack and `agent_push` have adapters; `api`, `email`, `teams`, `webhook` do not"*, and keep the reasoning, which is still right |
| `tests/deliver/test_a_comment_is_not_a_measurement.py` | ⛔ NEW |

## 4 · The test, and ⛔ the one way it must not be written

The useful assertion is **not** "the comment contains the right words" — that is a blunt grep against
prose, and it would pass the moment somebody rephrases. It checks the **claim**:

| Test | Assertion |
|---|---|
| `test_the_implemented_channel_set_is_computed_not_described` | `_implemented_channels()` equals the set of names for which `get_channel` returns non-`None`, derived **by calling it** over `PUSH_REQUIRES_ADAPTER` — so the day a third adapter lands, the comment is the only thing that can be stale, and §4's second test catches that |
| `test_no_comment_in_deliver_claims_an_unreached_function_is_fired` | ⛔ walk the AST for every name in `delivery_health.UNREACHED` / `PULL_ONLY`, and assert no **comment** in the package asserts it is called, using the closed verb set `fired`, `called by`, `invoked`, `triggered by`. Comments are read from the token stream (`tokenize`), not from docstrings |
| `test_the_adapter_count_matches_the_registry` | 2 of 6 today, named explicitly, so adding an adapter forces a deliberate edit here |

⛔ **The second test is the general guard** and the reason this step is not just two edits. It makes
*"declared unreached, but a comment says it is fired"* a build failure for every future entry — the
general form of the specific defect. **A guard written for one member of a closed table is half of
that.**

## 5 · Verify

```
.venv/bin/pytest tests/deliver/test_a_comment_is_not_a_measurement.py -q
.venv/bin/pytest tests/deliver/ -q
```

## 6 · Mutations

| # | Mutation | Must go red |
|---|---|---|
| M1 | restore `(fired by L5 when a card is emitted)` | the comment-claim test |
| M2 | add a third adapter to `get_channel` without touching the comment | the adapter-count test |
| M3 | hard-code `_implemented_channels()` to `{"slack"}` | the computed-not-described test |

## 7 · Expected outcome

Two sentences that answered a question wrongly now answer it correctly, and a test makes the general
case — a declared-unreached function with a comment claiming it is called — fail the build.


---
---

# ✅ DONE — 2026-10-01

## 1 · ⛔ The step planned two. Measuring found four, and the fourth is the worst kind

| # | Where | What it said | Truth |
|---|---|---|---|
| 1 | `deliver/push.py:19` | *"push_card_to_agents — proactive … **(fired by L5 when a card is emitted)**"* | ⛔ **nothing fires it.** Agents POLL — `agent_api.poll_signals` |
| 2 | `deliver/push.py:18-22` | *"**Two flavours**, one transport:"* then **one** bullet, then a line beginning *"in the org that registered a webhook"* | ⛔ the `push_action_to_agents` bullet was **deleted and its tail left behind**, reading as a sentence about the bullet above it |
| 3 | `deliver/units.py:70` | *"`get_channel` returns Slack or None — **one implementation** across every push channel named here"* | ⛔ it returns Slack **and** `agent_push`. **Two of six**, not one |
| 4 | ⛔ `tests/test_delivery_units.py:67` | *"`get_channel` returns Slack or None."* | ⛔ **THE SAME WRONG SENTENCE, IN THE TEST THAT GUARDS THE THING** |

⛔ **#4 is the one that matters most and it was not in the plan.** The wrong sentence had propagated
into the docstring of the test guarding that behaviour — so anybody checking *"is this claim
guarded?"* found a test repeating the claim. Its **assertion** was always correct: it is about
`teams`, which genuinely has no adapter. Only the prose above it was wrong.

> ⛔ **In all four cases the behaviour was correct and only the sentence a human reads was wrong.**
> `_implemented_channels()` calls `get_channel` and counts the answer rather than trusting the
> comment, so `capability_report` has been right the whole time. **That is the dangerous
> combination**: no test fails, no receipt goes red, and the error surfaces only when somebody
> answers a question from it.

### And #2 was never a wording problem

`push.py`'s header announced a **count** and listed fewer. The deleted bullet's second half —
*"in the org that registered a webhook (Hermes or the client's own tool)"* — survived as a line that
**parses as English**, attached to the wrong bullet. A reader would conclude that proactive card push
goes to every webhook-registered agent in the org, which is a sentence about
`push_action_to_agents`, the flavour that **raises on purpose.**

## 2 · ⛔ The guard I nearly wrote, which would have failed on its own correction

The obvious guard for #3 and #4: assert the string `"returns Slack or None"` appears nowhere.

⛔ **It fails on the corrected comment**, which says *"this comment said 'returns Slack or None'
until 2026-10-01."* **A grep for a known-false phrase matches the record of its own correction.**

That would have been the **seventeenth** time a substring check in this programme matched the
author's own words — and the first where the match was the fix.

> **So a factual claim is not guarded by forbidding its wrong form. It is guarded by making the fact
> DERIVABLE and naming it in exactly one place**, so the next change forces somebody back to the
> paragraph that explains it. A missing claim is guarded structurally, by coverage.

## 3 · What was built

`tests/deliver/test_a_comment_is_not_a_measurement.py` — ⛔ NEW, **6 tests**, none of which reads
prose for correctness.

| Test | What it guards | Shape |
|---|---|---|
| `test_no_comment_claims_a_declared_unreached_function_is_called` | ⛔ **the general form** — walks all 25 `delivery_health` entries against every COMMENT token in `deliver/` | closed verb set, `tokenize` |
| `test_the_guard_can_actually_fire` | ⛔ that the detector works, using the **exact comment removed** from `push.py:19` | a guard matching nothing passes on any codebase |
| `test_the_implemented_adapter_set_is_computed_and_not_described` | `_implemented_channels()` must equal the set from **calling** `get_channel`, and equal the two named here | derivable fact, named once |
| `test_four_of_the_six_push_channels_still_have_no_adapter` | `api`, `email`, `teams`, `webhook` — stated as a number | a measurement, not an impression |
| `test_every_push_entry_point_is_named_in_the_module_header` | ⛔ **the deleted bullet, guarded generally** — every `push_*` function must appear in the leading comment block, and there must be exactly two | AST for names, `tokenize` for the header |
| `test_the_unwired_flavour_is_declared_and_the_fail_closed_one_is_too` | both halves declared, for **opposite** reasons | pinned as a pair |

### ⛔ The general guard is the half that outlives the four corrections

Four comment edits fix four comments. `test_no_comment_claims_a_declared_unreached_function_is_called`
makes *"declared uncalled, but a comment says it is called"* a build failure for **every future
entry** — because **a guard written for one member of a closed table is half of that.**

Validated before it was written: run read-only against the *stale* source it reported **exactly one**
hit — `push.py:19` — and **zero false positives across all 36 files** in the package.

### ⛔ Two deliberate scope decisions, both recorded in the test

**`push_*` only, not every public function.** The header guard found a third public function,
`authoritative_card_projection`, which the block never mentioned. It is the projection **both**
flavours share, not a flavour — and demanding the header list it would be asserting a convention the
module never adopted. *Widening a check until it accepts everything leaves it asserting that a file
contains some words.*

**`deliver/` only, not the engine.** The declaration this walks exists in two packages out of eleven.
The engine-wide form needs `STEP-17` first.

## 4 · Mutations

⛔ **Baseline established first this time, and re-verified after** — the discipline `STEP-14` paid for.

```
baseline        35 passed
restore verify  35 passed
```

| # | Mutation | Result |
|---|---|---|
| M1 | put *"(fired by L5 when a card is emitted)"* back | 🔴 1 failed |
| M2 | delete the `push_action_to_agents` bullet from the header | 🔴 1 failed |
| M3 | add a third adapter to `get_channel` | 🔴 2 failed |
| M4 | hard-code `_implemented_channels()` to `{"slack"}` | 🔴 2 failed |
| M5 | empty the closed verb set | 🔴 1 failed |

⛔ **M3 is the one that justifies naming the adapters instead of deriving them.** A purely derived
assertion would have passed, and nobody would have been sent back to the `units.py` paragraph that
explains `PUSH_REQUIRES_ADAPTER` — which is how that paragraph went out of date for four weeks in the
first place.

## 5 · ⛔ What is NOT guarded, said plainly

**Correction #4 — the test docstring — has no guard.** Restoring the stale sentence in
`tests/test_delivery_units.py` would fail nothing. Prose in a docstring is not checkable without
either reading it for meaning or grepping for a phrase, and §2 is why the grep is worse than nothing.

> ⛔ **Recorded rather than papered over.** The honest position: three of the four corrections are
> now defended by a test, and the fourth is defended by having been written down here.

## 6 · Verify

```
.venv/bin/pytest tests/deliver/test_a_comment_is_not_a_measurement.py -q          # 6 passed
.venv/bin/pytest tests/deliver/test_a_comment_is_not_a_measurement.py \
                 tests/test_delivery_units.py \
                 tests/deliver/test_the_delivery_layer_says_what_it_does_not_call.py -q   # 35 passed
```

## 7 · Doctrine

| Rule |
|---|
| ⛔ **a grep for a known-false phrase matches the record of its own correction** |
| ⛔ **a factual claim is guarded by making the fact derivable and naming it in one place, never by forbidding its wrong form** |
| ⛔ **a header that announces a count and lists fewer is how a deleted bullet leaves its tail behind** |
| **the behaviour can be right while the sentence a human reads is wrong — and then nothing fails** |
| **a guard that matches nothing passes on any codebase** |
| **a stale comment reads as a measurement — including when it has propagated into the test that guards it** |
