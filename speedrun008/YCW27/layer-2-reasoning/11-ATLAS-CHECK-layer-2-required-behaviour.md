# L2 · the Atlas's "required behaviour", measured card by card

**Written for:** Rohit and Harsh (CTO). **Date:** 2026-10-01.
**Against:** `04-Layer-4-Reasoning/03-Current-Successes.../README.md` — *"A valid authoritative decision
must contain a state-based situation, exact remaining loop, primary candidate, materially different
fallback when feasible, explicit wait/stop option, rejection receipts, business stakes, expiry,
separated confidence vector, owner/approval boundary, observable completion and outcome window."*

**Method:** one `set transaction read only` connection. 165 cards joined to their signals.

---

# ⛔ THE RESULT — 8 of 12 met, 4 partial, 0 absent

| Atlas requirement | present | share | |
|---|---|---|---|
| state-based situation | 165 | **100%** | ✅ |
| primary candidate | 165 | **100%** | ✅ |
| expiry | 165 | **100%** | ✅ |
| owner / approval boundary | 159 | **96%** | ✅ |
| business stakes | 158 | **95%** | ✅ |
| outcome window | 158 | **95%** | ✅ |
| separated confidence vector | 158 | **95%** | ✅ |
| **materially distinct fallback** | 151 | **91%** | ✅ |
| **rejection receipts** | 151 | **91%** | ✅ |
| a draft to act with | 127 | 76% | ⚠ |
| explicit wait/stop option | 104 | 63% | ⚠ |
| uncertainty declared | 57 | 34% | ⚠ |
| candidate steps | 57 | 34% | ⚠ |
| observable completion | 54 | 32% | ⚠ |

⛔ **The Atlas's two sharpest accusations are no longer true.** It said:

> *"Legacy adapter commonly supplies one generic play, so 'winner' may have no meaningful
> alternative."* · *"Active one-play path and UI projection omit meaningful alternatives/trade-offs."*

**Measured: 151 of 165 cards (91%) carry `rejected_candidates`** — a materially distinct alternative
AND its rejection receipt. And `stakes`, `outcome window` and the `confidence vector` are at 95%, all
three of which the Atlas recorded as `missing` placeholders.

---

# ⛔ AND THREE OF MY OWN SUSPICIONS WERE WRONG IN THIS ONE PASS

Recording them, because the audit's value kept being in **not** changing things.

| I suspected | Measured |
|---|---|
| `L4 · at least one seat has a manager` asks only about `manager_seat_id` while the code reads dated `reports_to` first — so the receipt is too narrow | ⛔ **wrong.** `seat_responsibilities` has **0 rows** and no `reports_to` column. Both paths are empty; the receipt is correct |
| `L6 · there is a channel` asks `channel in ('slack')` while the tenant has 3 active `in_app` — too narrow | ⛔ **wrong.** `in_app` is the **PULL** surface — *"the card surface — always available, never interrupts"*, and *"there is nothing to send, because the card is already on"* it. `org_channels` is for push. The receipt is correct, and a comment already said so |
| `rejected_candidates` / `uncertainty` / `candidate_steps` are computed by `build_draft` and **not** in `insert_card`'s column list → `not_carried` | ⛔ **wrong.** They live on `signals` and the API reads them through the join (`s.rejected_candidates`). **91% populated.** Not dropped — produced once and read where they are |

---

# PART 2 · THE FOUR PARTIALS, and what each one actually is

## ⚠ `uncertainty` 34% · `candidate_steps` 34% — the same 57 cards

Both at exactly 57 of 165. ⛔ **The same population: the compiled lane.** `candidate_steps` and
`uncertainty` come from `ReasoningDecision` (migration `0070`), and the 108 cards without them predate
that wave or came from the legacy rule path, which produces neither.

**Not a defect — a cutover that is 34% through.** The mover is `ALARM A2`: the roster and
`DEAL_HEALTH_V1` are unswept, so the compiled lane is not the authoritative one.

## ⚠ observable completion 32%

`success_signal` comes from the pack's play definition (`_play_success`). **54 cards had a play that
declared one; 111 had a play that did not.** ⛔ **Authoring, not engineering** — a play with no stated
success signal cannot produce one, and `card_builder` correctly writes NULL rather than inventing it.

## ⚠ explicit wait/stop 63%

104 of 165 are `review` or `observation`. ⛔ **This is the abstention vocabulary WORKING**, not a gap —
the Atlas's complaint was that abstention *"can be bypassed/degraded in API fallbacks"* and that a
*"generic imperative survives uncertainty"*. 63% of cards decline to instruct. The remaining 37% are
`prescriptive`/`predictive`, which is what an instructing card is supposed to be.

## ⚠ a draft to act with 76%

127 of 165 carry an artifact body. Of the 38 that do not, **19 abstained** — correctly, by design — and
**18 are `prescriptive` and not abstained**: ⛔ **a card giving an order with nothing to act with.** That
is finding #7 in `../06-C-AUDIT-the-nine-findings.md`, and the receipt now names exactly those 18.

---

# PART 3 · WHAT THE ATLAS GOT RIGHT AND IS STILL RIGHT

> *"Wiring all 17 units without richer Layer 3 plays and golden decisions would add machinery, not
> judgment."*

**Still the sharpest sentence in the dossier.** Measured today: 20 units run, 22 fact paths are bound,
**14 have no writer**, and two units complete while computing nothing. The machinery is wired far
beyond what the dossier described — and it is fed by a graph with no deal object.

> *"Score, confidence and urgency must be separate; no scalar may substitute for another."*

**Fixed because the dossier said it** — `confidence_score` / `priority_score`, 95% populated, with the
code carrying the comment *"never the score"*.

---

# ⛔ PART 4 · THE SINGLE ROOT, STATED ONCE

Every ⚠ above reduces to one of three things, and none is a defect in Layer 2:

| | root | mover |
|---|---|---|
| `uncertainty`, `candidate_steps` at 34% | the compiled lane is not authoritative — `BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)` | **Rohit** · `ALARM A2` |
| `observable completion` at 32% | plays that declare no success signal | **authoring** |
| 18 instructing cards with no draft | the model has refused every call since **2026-09-25 11:09 UTC** | **Rohit** · the spend limit |
| `0189` / `0190` not applied | `signals.output_lane` and `cards.output_lane` do not exist in production | **Harsh** |

⛔ **And one measurement that settles a doubt I have carried all session:** no card has been written
since 2026-09-25. `insert_card` now writes `output_lane`, and the column does not exist — so **the next
card write will fail** until `0190` is applied. That is not a prediction; it is the schema.
