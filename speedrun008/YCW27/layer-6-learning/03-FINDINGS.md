# L6 · findings — what measuring `feedback/` actually turned up

**Date:** 2026-09-30. Everything here was measured before any code was written.

---

## ⛔ F1 · The milestone's own promise was already kept, in three places

M14 ships *"a wrong card debits the layer that failed, **and a timing complaint never lowers a
correct rule's precision**."*

```
calibrate.TAXONOMY["wrong:bad_timing"]  ->  {"label": "timing", "precision": "none"}
feedback/units.py:135                   ->  judged = acted + wrong   # bad_timing does not grade
calibrate._PRECISION_SQL                ->  in ('not_relevant','wrong_facts')
```

with `packs/brains/adaptive_lease.py` documenting the same rule from the consuming side.

⛔ **And `_PRECISION_SQL` goes further than the milestone asked.** It also restricts the denominator
to `card_level in ('prescriptive','predictive')`, with the best statement of the principle anywhere
in the repo: *"counting that as a precision failure made answering the system's own question evidence
the system was wrong."* A NULL level is excluded rather than assumed, because *"defaulting it to
'instruction' is how the old behaviour comes back."*

It was work to **not break**. **Correction #10.**

---

## ⛔ F2 · Nothing in `feedback/` names a layer

`grep -rn "layer" genios_engine/feedback/` → seven hits, **every one prose in a comment** about the
import topology. No reason→layer map, no layer counter, no layer column. The milestone's *first*
clause was entirely unbuilt.

`TAXONOMY` is its ancestor: it routes a reason to a **consequence** and a **label**. It never says
which layer to go and look at.

---

## ⛔ F3 · Three reasons, and five readers of the three

| Where | What it holds |
|---|---|
| `deliver/card_builder.py:849` | what the card **offers** |
| `deliver/actions.py:31` | what the API **accepts** |
| `feedback/calibrate.py` | what calibration **maps** |
| `feedback/units.py:124` | what the counter **branches on** |
| `context/correlation_history.py:148` | what a retry decision **reads** |

Widening one without the others reproduces `FEATURE_CARDS_FROM_SITUATIONS` exactly — *"the reader was
looking for a word the writer rejected"* — which cost this codebase a lane no tenant could enable.

---

## ⛔ F4 · The widening would have broken F1, in both directions at once

**Over-counting.** `units.py` tested one literal. Five of the eleven reasons say the card was RIGHT;
**four of those five would have landed in the `else` and debited the rule's accuracy.** The defect
this milestone exists to end, created for four new reasons by the step meant to fix it for one.

**Under-counting, and harder to notice.** `_PRECISION_SQL` held two reasons. Six now count against a
rule. Four real quality failures — `misread_source`, `wrong_subject`, `bad_link`, `bad_reasoning` —
could have been recorded by a founder and **counted by nothing.** Nothing breaks, and precision
merely looks better than it is.

---

## ⛔ F5 · `contracts/learning.py` exists, and is not this

310 lines of `LearningObject` v2 — content-addressed, round-trip verified, with its own hard rules.
`M14.C1.U01` names it as its artifact. **Adding a member to an enum it validates against would change
identities already minted.** The new vocabulary went beside it, not into it.

---

## ⛔ F6 · The topology gate caught my own violation

`contracts/learning_attribution.py` imported `genios_engine.LAYERS` so the layer names could be
checked at import time. `test_contracts_import_nothing_above_platform` failed the build: *"contracts/
is the boundary vocabulary — it may depend on platform/stdlib only."*

**The gate was right.** `contracts/` is what every layer imports, so a dependency added there is added
everywhere — and `LAYERS.py` exists to be read by the topology *test*, not by shipped code (nothing
else in `genios_engine/` imports it). Same lesson as `capture → context` in L1 Step 10.

---

## ⛔ F7 · Two of my own tests were blunt greps, in one file

One asserted `"denominator" not in src` and failed on **its own docstring**, which uses the phrase
*"the precision denominator"* to explain the rule. The other matched `OFFSET_BOUND` in a module
docstring, where it appears to say that learning is bounded **and an attribution is not.** Both
rewritten as AST walks.

---

## ✅ F8 · What was already right

| | |
|---|---|
| Wilson intervals | a rule with 8 judgments does not get the same confidence as one with 800 |
| the mute floor | `MUTE_PRECISION = 0.25` with `MUTE_MIN_JUDGMENTS = 12` — a cold rule cannot be muted on noise |
| the offset bound | `OFFSET_STEP = 5`, `OFFSET_BOUND = 15` — learning cannot run away |
| the abstention exclusion | a `review` card answered by a human is not a precision failure |
| the import direction | `feedback/consumer.py` records a real correction: a consumption contract only the producing layer could import was *"a decoy seam"* |
| `(action, reason)` carried whole | *"`bad_timing` invites a later retry, `not_relevant` does not"* |

---

## What changed because of these findings

| Finding | Effect |
|---|---|
| F1 | `U03` narrowed; two **guard** functions now hold the property, with tests |
| F2 | `contracts/learning_attribution.py` — eleven reasons, one layer each |
| F3 | all five readers widened in one step; a test asserts the card and the API agree |
| F4 | `units.py` asks the map; `_PRECISION_SQL`'s list is generated from it. Both directions tested |
| F5 | a new file beside `learning.py`; `tree.yaml`'s artifact updated with the reason |
| F6 | layer names are plain strings; two tests assert them against `LAYERS.py` |
| F7 | both tests rewritten as AST walks |
| F8 | nothing rebuilt |
