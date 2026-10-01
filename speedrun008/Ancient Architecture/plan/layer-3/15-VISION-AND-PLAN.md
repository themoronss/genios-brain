# Layer 3 — the vision, and the plan that gets there

**2026-09-25** · the decision document. Detail in `10`–`14`.

---

## 1. What "working" means — one question, five parts

The specs and the benchmark converge on the same acceptance test:

> **Given the evidence GeniOS actually has, does it tell Rohit the right next move, with the right
> owner, at the right time, for the right reason — and change that advice when reality changes?**

| part | needs | today |
|---|---|---|
| the right **next move** | correlation ＋ reasoning | ✅ mostly built |
| the right **owner** | roles, authority, scope | ⚠️ partial |
| the right **time** | ⛔ a clock that fires with no new mail | ⛔ **absent** |
| the right **reason** | receipts ＋ **coverage** | ✅ receipts · ⛔ coverage not carried |
| **change when reality changes** | the Intelligence Graph | ⛔ **absent** |

**Two of five are missing outright. One is built and not delivered.**

---

## 2. ⛔ The measurement that reorders everything

The benchmark's eight "awaiting you" rows, tested against `DEFAULT_BACKFILL_DAYS = 60`:

```
⛔ INVISIBLE   Keshav (RocketSDR)     evidence  77d old
⛔ INVISIBLE   Aditya (IIMA)          evidence  79d old
⛔ INVISIBLE   Radhesh (Suvan)        evidence  69d old
⛔ INVISIBLE   John (Actual.ai)       evidence  63d old
⛔ INVISIBLE   Vatsa (Valiron)        evidence  61d old
✅ visible     Manik (Titan)          evidence  46d old
✅ visible     Pankaj (Saka)          evidence  16d old
✅ visible     Onur Eren              evidence   7d old
```

⛔ **5 of 8. And 3 of the 4 broken-promise source messages.**

**GeniOS run on this mailbox today would find 3 of 8 waiting relationships and 1 of 4 broken
promises — and not one of those misses is a reasoning failure. It is one integer.**

> *"Two months is not enough history to be worth reasoning over… the questions a tenant actually
> asks were unanswerable by construction."* — `backfill.py`, its own docstring

**The module already knows. Nobody raised the number.**

---

## 3. What a founder would see today, honestly

| | |
|---|---|
| ✅ **the bounces** | Afore ×2 and Surge — `capture/delivery_status.py` names them by address |
| ✅ **receipts** | every claim carries `{span, text, page, bbox}` — Gemini's invented *"$2–3k MRR"* cannot happen |
| ✅ **refuses to print 100%** | `completeness_bp` returns `None`, not `10000` |
| ⚠️ **3 of 8 waiting rows** | the rest is outside the window |
| ⛔ **no coverage on any card** | `context/` reads L1's coverage **zero** times |
| ⛔ **would not notice 28 days of silence** | the sweep is event-driven; nothing fires without mail |
| ⛔ **would say it again next week** | `prior_decision` = 0 occurrences |

**The engine is good. It is looking through a two-month window, cannot say how small the window
is, and forgets everything it said.**

---

## 4. The plan — six phases, and what each one buys

### ⛔ PHASE A · **SEE** — without this, everything else operates on 3 of 8 facts

| | |
|---|---|
| **A1** | raise `backfill_days` for the pilot |
| **A2** | ⛔ **progressive sync, newest-first** — L2 runs from minute one |

**Buys:** 5 of 8 waiting rows and 3 of 4 broken promises become **visible at all**.
**Cost:** a setting ＋ one sync change. **No new intelligence is built.**

⚠️ **A2 is not optional.** The module records why the default was lowered: at 540 days a first sync
walked 18 months *"before Layer 2 ran at all — hours with an empty graph."* **Raising the window
without progressive sync makes the pilot's first impression a blank product.**

---

### PHASE B · **SAY HONESTLY** — ⛔ this is the wedge

| | |
|---|---|
| **B1** | the coverage record — `sync_health` · `pagination_complete` · `known_gaps` · `observation_interval` |
| **B2** | ⛔ **carry it across the seam** — QES → situation → card. *The value exists and is dropped.* |
| **B3** | `scoped_absence()` — six ingredients, refusing by default |

**Buys:** every card carries *"read 37 of ~465"*, and *"0 commitments"* can never again mean *"0 in
the 4%."*

⛔ **Why this beats Claude and not just Gemini.** Claude's honesty is **manual and per-answer** — it
happened to run one extra query. **GeniOS's would be structural**: coverage is a property of the
sync, so it is on every card whether or not anyone asked. **That is a product property. Claude's is
a good day.**

---

### PHASE C · **NOTICE** — what did *not* happen

| | |
|---|---|
| **C1** | `next_evaluation_at` ＋ the durable drain in `context/periodic.py` |
| **C2** | the Freshness Manager — `freshness_policy_id` gets a writer |

**Buys:** the 28-day silence surfaces **on day 3, not day 28**. P5 becomes answerable.
⛔ **Five of the supplied documents name this gap independently.**

---

### PHASE D · **JOIN** — what kind of link is this

| | |
|---|---|
| **D1** | ⛔ **Cross Tool** — the Gmail ↔ Calendar correlator that does not exist |
| **D2** | the typed relation vocabulary — 7 of 12 missing, incl. the **Radhesh miss** |
| **D3** | the correlation decision record — accept / reject / hold with reasons |

**Buys:** P4 (*40 meetings joined against **one** email thread*), P3 terminal states, check #2.

---

### PHASE E · **REMEMBER** — stop deciding from scratch

`intel_nodes` ＋ `intel_edges` · lift `about` out of `signals` · `deliver/` and `feedback/` write
back · the five-word revision action.

**Buys:** the fourth identical card cannot be produced, *"stop telling me this"* has somewhere to
attach, and **"of last month's decisions, how many landed" becomes answerable for the first time.**

---

### PHASE F · **SHOW**

The card line · the side-panel summary · the founder count · ⛔ **structured-to-visible equality**
(E2E-12: correct correlation, correct decision, and the card still said *"six investors ignored
you"*) · cutover ＋ sensitivity.

---

## 5. Why this order and not the spec's

The specs order by architecture. **This orders by what a founder would notice**, and the benchmark
is the evidence for it:

| | if built first | a founder sees |
|---|---|---|
| **A** window | — | ⛔ **five relationships that were invisible** |
| **B** coverage | A | *"we read 37 of 465"* — the sentence no competitor can say |
| **C** timer | — | *"you have not written to anyone in 28 days"* |
| **D** correlation | B | *"you met them and never followed up"* |
| **E** memory | A–D | *"3rd time · you dismissed this Tuesday"* |
| **F** surface | all | any of the above, correctly worded |

⛔ **A and C have no dependencies and buy the most.** They can start immediately and in parallel.

---

## 6. Three decisions that are yours

### ⛔ D1 · How far back for the pilot?

| | one-time cost | buys |
|---|---|---|
| **180 days** | moderate | all 8 waiting rows · all 4 broken promises · **P3 (6 months)** |
| **365 days** ✅ *recommended* | higher, still one-time | **＋ P4 (12 months)** — the calendar×email prompt |
| 540+ | the *"hours with an empty graph"* case | P5, and only with A2 |

**Recommendation: 365 with progressive sync.** The extraction cache means a document is extracted
**once, ever** — so the cost is one-time and bounded, and 365 is what P4 needs.

### D2 · Which mailbox is the pilot?

The benchmark is **N = 1, and the friendliest possible case** — 39 sent threads in 90 days. *"The
win is a property of your low outbound volume."* **The same flatters GeniOS.** A second, higher-
volume mailbox is what turns this from a demo into evidence.

### ⛔ D3 · What is the milestone — beat Claude, or answer what Claude cannot?

| | build | proves |
|---|---|---|
| **"Beat Claude on P1/P2"** | **A ＋ B** only | *"they read 8% and say 100%; we read all of it and say so"* — the pitch sentence |
| **"Answer P3/P4/P5 at all"** | A ＋ B ＋ C ＋ D | the thing no LLM can do at any prompt length |

**Recommendation: A ＋ B first, as one shippable slice.** It is the shortest path to a sentence a
prospect understands, and **every later phase needs it anyway.**

---

## 7. What this plan does not fix

**Finding #5 of the benchmark is not an engineering finding.** Six rejections in six weeks, then 28
days of zero outbound. The document says it plainly: *"a founder-behaviour problem in the data, not
a product or architecture problem."*

**No step here changes it.** ⛔ **But Phase C is exactly what surfaces it on day 3** — and a product
that says *"you have not replied to anyone in three days, and four people are waiting"* is the
product being described.

---

## 8. The vision, in one paragraph

**Every LLM answers from what fits in its context window and calls that the mailbox.** GeniOS
indexes instead — so coverage becomes a property of the **sync**, not of the **question**, and the
system can state what it read, refuse the claims it cannot support, notice what did not happen, and
remember what it already said.

⛔ **Four of those five capabilities already exist in the code. The plan is mostly about carrying
them six inches further.**
