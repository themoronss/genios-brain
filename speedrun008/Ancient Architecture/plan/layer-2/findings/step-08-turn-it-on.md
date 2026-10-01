# L2-8 · Turn it on, then prove it adversarially — findings

**Run:** 2026-09-24 · **no migration · no model call · nothing armed**
**Against:** `speedrun008` @ `d1556443`
**Result:** 36 tests, **13,116 passed · 14 failed (all pre-existing) · 0 regressions**

---

## 1. ⛔ The step says three flips. It is seven.

§2: *"The three flips happen together… **any one alone leaves the system in a state that looks
working and is not.**"* Written before L2-0…L2-7 ran — and **four of those steps each left a
switch behind deliberately**, with the same discipline every time: declared, evidenced, and **not
armed until somebody had the number.**

**Nothing enumerated them.** Four switches in four findings files is four switches somebody
rediscovers one at a time — the *"prose stale, code right"* drift, and the same gap L2-6 found
when three completed steps had deferred work onto L2-5 with nothing collecting it.

| switch | owner | what it breaks if flipped alone |
|---|---|---|
| `require_admission` | L3 plan | unreviewed doctrine could carry authority on a live card |
| `publisher` (`live=True`, per tenant) | L3 plan | `expertise_packages` is never written |
| `execution_mode` (`LIVE` + a `signals` row) | L3 plan | delivery cannot build a card at all |
| **`fundraising_route`** | **L2-4** | ⛔ **nothing breaks, which is why it is easy to forget** — the doctrine exists and the pilot's dominant domain keeps not reaching it |
| **`observing_laws`** (V-9, V-10 → REJECT) | **L2-2** | nothing breaks; unreceipted interpretations keep publishing |
| **`cards_from_situations`** | **L2-7** | the founder keeps seeing one card per SIGNAL |
| **`situation_reasoner`** | **L2-5** | Layer 2 never interprets anything |

`reason/cutover.py` holds the table, and **a test reads the CODE and refuses a row that
disagrees** — so a flip that forgets to update it fails the build rather than happening quietly.
`live_lane` recorded what an unrecorded flip costs: *"the one configuration in which the stated
safety property is false is the one a global flag creates."*

### 1.1 · And `require_admission` is already free

L2-0 measured it: **155 of 155 authored capabilities are admissible**, every content hash
recomputed and verified. The plan budgeted for **334 going dark**; that number counted files.
**The switch with the scariest precondition in the plan has none.**

---

## 2. The parity gate is a number, and it is older than the measurement

§3: *"Written down **before** the run, not chosen after seeing it. A threshold picked post-hoc is
not a gate."*

The shadow pass has been counting for months and **nobody has read its tallies.** The moment
somebody does, a threshold chosen afterwards is a threshold chosen to pass. So five rules are
fixed now, `PARITY_MEASURED_AT` stays `None`, and **a test asserts the gate predates the numbers.**

| rule | reads | needs | why |
|---|---|---|---|
| no unroutable errors | `error` | ≤ 0 | a per-situation exception on the shadow lane becomes a lost card on the live one |
| nothing fails to persist | `persist_error` | ≤ 0 | the live lane's whole difference is that it writes |
| most situations compile | `compiled` | ≥ 100 | 159 active; below 100 the corpus reaches a minority of the tenant |
| reasoning reaches the same rows | `reasoned` | ≥ 100 | compiled-but-not-reasoned is a package nobody read |
| no reading crashed | `reasoner_failed` | ≤ 0 | L2-5's consult cannot kill the compile by design, so a non-zero here is **silent** |

Two properties a test enforces:

* ⛔ **every reading is a key the sweep actually emits** — a gate that reads a tally nothing
  writes passes forever, which is L2-0's defect pointed at the cutover;
* ⛔ **an absent tally FAILS.** *"`None` is not a low number — it is nobody having measured."*

---

## 3. ⛔ THE ADVERSARIAL PASS FOUND A REAL HOLE — in L2-6, on the one path that matters

U4's F20 shape is *"a hypothesis that hardened into an observation"*. Attacking it directly found
that `proposal_gate._refs_in` read citations with `getattr` alone.

**A proposal arrives as parsed JSON. Its entries are dicts.** So every cited claim read as *citing
nothing*: it was refused under `l2_receipt`, and **the resolver was never called at all** — which
made the unresolvable-citation half of check 3 **dead on the real path.**

The defence was correct and it was pointed at an object shape the model never sends. **That is
what an adversarial pass is for**, and it is the third time this layer has found a rule aimed at
the wrong thing — after L2-1's fifteen annotations and L2-6's own re-aim.

### 3.1 · The four F20 attacks, and what refuses each

| attack | refused by |
|---|---|
| a hypothesis with low confidence rendered as fact | **the claim state itself** — `hypotheses` is the only field in `HYPOTHESISED`, so a renderer that treats it as observed has to *say so* |
| an inference whose only citation is another inference | **the resolver asks the GRAPH, not the payload** — a hypothesis citing a hypothesis cites an id the Evidence Graph has never heard of |
| `unknowns` emptied by a confident model on thin coverage | **twice**: L2-6 refuses the proposal, V-10 observes the assembled situation |
| an interpretation that outlived `valid_until` | **a model may not write its own expiry** — it is `ENVELOPE`. One that could set it could make its own reading immortal |

Plus R-1's rule at the number level: ⛔ **it cannot raise a confidence.**

---

## 4. The registry, and the counts a test counts

**37 scenarios** across twelve failure classes, with L1's F20 kept **by its own number** because it
is the same failure wearing this layer's clothes.

```
closed      25      a step fixed it, and a probe proves the check is sensitive to THAT fix
guard        3      already true; evidence progress cost nothing, not that progress happened
open         1      ⛔ S07 — no test drives the compiler with what production sends it
harsh        7      the logic is proven; the distribution needs the pilot
impossible   1      S20 — `general` is claimed by all three corpora; routing it is a CHOICE
```

⛔ **The counts are asserted by a test**, because L1's drifted and were caught *by counting, not by
reading* — the log said 31 CLOSED when the registry said 29. And every step from 0 to 8 must own
at least one row: **a step with no scenario is a step nobody can contradict.**

### 4.1 · Nine mutation probes, each aimed at the RULE

Breaking `proposal_gate` would only prove its own lines execute. Breaking `DARK_DOMAINS`,
`SITUATION_STAGES`, `model_may_write`, `EMPTY_BY_DESIGN`, `RECEIPT_REQUIRED` and `LAW_ACTIONS`
proves **the layer depends on them** — which is what stops a second copy being written later.

The L2-8 probe is the sharpest: **arm a law in code and `is_armed` must notice**, or the switch
table could say anything.

---

## 5. Cost check

| | |
|---|---|
| model calls | **none** |
| migration | **none** |
| runtime behaviour | **nothing armed.** Every switch is off and a test asserts each one |
| new code on a sweep | **none** — `cutover.py` is data and two pure functions |

---

## 6. Completion criteria

| # | criterion | verdict |
|---|---|---|
| 1 | the shadow pass's tallies read and written down | ⛔ **HARSH 29.** The pass has been counting for months and nobody has read it. The gate is written and cannot yet be evaluated |
| 2 | a parity number fixed **before** the flip | ✅ five rules, every reading proven to be a tally the sweep emits, and `PARITY_MEASURED_AT is None` asserted |
| 3 | three flips together, one tenant, reversible | ✅ **and there are seven** — enumerated, ordered, each with its precondition and what it breaks alone. **None armed** |
| 4 | a scenario registry with typed classes and import-time totality | ✅ 37 scenarios, 12 classes, both directions checked |
| 5 | mutation probes for every fix in L2-1…L2-7 | ✅ **nine**, each neutralising the RULE — and one **found a live hole** (§3) |
| 6 | a failure log whose counts a test verifies | ✅ and every step owns a row |

**Five closed. One is a database read.**

---

## 7. What this step does NOT do

* **It does not flip anything.** Seven switches, all off, each with its number named.
* **It does not pick the gate after seeing the result.** `PARITY_MEASURED_AT` is `None` and a test
  says so.
* **It does not close what is still open.** S07 is OPEN with its reason; S20 is IMPOSSIBLE with
  its reason; seven rows wait on the pilot and each names what it waits for.
