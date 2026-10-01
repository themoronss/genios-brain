# L6 · plan — three steps, and one of them is narrower than it was written

**Written for:** Harsh (CTO) and Rohit. **Date:** 2026-09-30. **Reads with:** `01-CROSSCHECK.md`.

---

## STEP 01 · `M14.C1.U01` · the attribution vocabulary

**What is there.** `feedback/calibrate.TAXONOMY` — 7 keys, 3 of them `wrong:*`. It routes a reason
to a *consequence* (`numerator` / `denominator` / `none`) and a *label*. It does not say **which
layer to go and look at**.

**What to build.** `contracts/learning_attribution.py` — eleven reasons, each mapped to exactly one
layer, closed in both directions at import time.

⛔ **A NEW FILE, NOT AN ADDITION TO `contracts/learning.py`.** That file holds `LearningObject` v2,
which is content-addressed and round-trip verified. Adding a member to an enum it validates against
would change identities already minted. `M14.C1.U01` names `learning.py` as its artifact; this is a
deliberate departure and the reason is the hash.

⛔ **ONE LAYER PER REASON, AND EXACTLY ONE.** A reason that debits two layers debits neither: the
next person to read the number cannot act on it. Where a reason genuinely spans two, the reason is
drawn wrongly and must be split — which is what having eleven instead of three is *for*.

⛔ **THE LAYER NUMBER COMES FROM `LAYERS.py`.** It is the single source of layer numbers and
`tests/test_layer_topology.py` fails the build on a violation. A second hand-written list of layer
names is a second source of truth, and the first time somebody renames a package the two disagree
silently.

**Outcome.** *"A wrong card debits the layer that failed"* becomes expressible.

---

## STEP 02 · `M14.C1.U02` · the reasons, on the card and past the door

**What is there.** Three reasons, and **five readers of the three**:

| | |
|---|---|
| `deliver/card_builder.py:849` | what the card OFFERS |
| `deliver/actions.py:31` `WRONG_REASONS` | what the API ACCEPTS |
| `feedback/calibrate.py` `TAXONOMY` | what calibration MAPS |
| `feedback/units.py:124` | what the counter BRANCHES on |
| `context/correlation_history.py:148` | what a retry decision READS |

**What to build.** Widen all of them from one place.

⛔ **THE FIVE MOVE TOGETHER OR NOT AT ALL.** Widening what the card offers without widening what the
API accepts gives the founder a button the server refuses. Widening both without `TAXONOMY` lets a
reason reach calibration that nothing maps. That is `FEATURE_CARDS_FROM_SITUATIONS` again — *"the
reader was looking for a word the writer rejected"* — and it cost this codebase a lane that could
never be switched on for any tenant.

⛔ **BACKWARD COMPATIBLE BY CONSTRUCTION.** The three existing reasons keep their exact spellings and
their exact precision roles. Every judgment already recorded must still grade the way it graded, or
the 28-day window silently re-scores history.

**⛔ A concern I am flagging and then building anyway, because the tree asks for it.** Eleven radio
buttons under *"Wrong"* is a worse experience than three: a founder who has to classify our failure
for us will pick the first plausible option, and precise-looking data gathered that way is worse
than coarse data gathered honestly. The eleven are right as a **machine** vocabulary. Whether all
eleven should be *shown* is a product decision — Rohit's, not mine. **I am building the full eleven
and the card grouping, and leaving the display set as one constant with a comment naming the
trade-off**, so narrowing it later is a one-line change and not a migration.

**Outcome.** A founder's *"this was wrong"* arrives carrying which layer to go and look at.

---

## STEP 03 · `M14.C1.U03` · ⛔ **narrowed** — the layer debit, and a guard on what already works

**Why narrowed.** The unit reads *"the router — reason to layer to the thing that changes, and
`bad_timing` reaches L5 timing rather than the rule's precision."* ⛔ **The second clause is already
true in three independent places** — `TAXONOMY["wrong:bad_timing"]["precision"] = "none"`,
`units.py:135`, and `_PRECISION_SQL`'s `in ('not_relevant','wrong_facts')`. Building it would mean
building it twice.

**What to build.**

| | |
|---|---|
| `feedback/attribution.py` | the router: a judgment → the layer debited → what changes there. Pure |
| `tests/feedback/test_the_right_layer_is_debited.py` | ⛔ including the **guard** that fails if anybody makes a timing complaint grade accuracy — asserted against `TAXONOMY` and `_PRECISION_SQL`, because a property enforced in three places can be broken in three places |

⛔ **THE DEBIT IS A COUNT, NOT A JUDGMENT, AND IT DOES NOT CHANGE ANY WEIGHT.** L6 already changes
one thing — a rule's precision, bounded by `OFFSET_BOUND = 15`. A layer debit is a **direction to
look**, and wiring it to a weight would let one founder's misclassification retune a layer. What it
produces is a ranked answer to *"where is this tenant's pipeline actually failing?"* — which is the
question the funnel counters (`0188`) were built to ask and currently answer only by volume.

**Outcome.** A wrong card names the layer that failed, and the thing that already works is guarded.

---

## What this plan does NOT do

| | Why |
|---|---|
| touch `LearningObject` | content-addressed; a new enum member rewrites minted identities |
| rebuild the precision rule | three places already enforce it; a fourth would be a place to disagree |
| let a debit change a weight | one founder's misclassification must not retune a layer |
| put a model anywhere in L6 | an attribution is a route. §4 |
| add a reason that debits two layers | a reason that debits two debits neither |
