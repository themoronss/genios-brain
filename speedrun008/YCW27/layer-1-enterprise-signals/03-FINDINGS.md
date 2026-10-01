# Layer 1 — every finding, in one place

Each row was read in the code or measured in production. Nothing here is inferred from a plan.
The evidence for each sits in [`findings/`](findings/).

---

## A · Defects found — and what happened to them

| # | Finding | Severity | Status |
|---|---|---|---|
| A1 | **`l4_bundle` had made 600 model calls and succeeded zero times**, 13→25 Sep, because the shared client sent `temperature` to a model that refuses it. The narrator has never once produced a bundle | high | ✅ **fixed** — [Step 2](STEP-02-DONE-temperature.md) |
| A2 | **Five days with no working model call anywhere in the product**, and no alert. It had also happened 16–17 Sep and recovered unnoticed | critical | ✅ **alert built** — [Step 3](STEP-03-DONE-provider-alert.md) · the limit itself is [Step 4](STEP-04-PENDING-api-limit.md) |
| A3 | **OCR has never run once.** 122 document rows, 0 ever carried an engine; 830 `ocr_unavailable`; 341 attachments at `fetch_failed` | high | ⏳ **Harsh** — [Step 8](STEP-08-PENDING-HARSH-ocr.md) |
| A4 | **The 60-day window makes two benchmark prompts structurally unanswerable** — not unproven, impossible | high | ⏳ **Harsh** — [Step 9](STEP-09-PENDING-HARSH-backfill.md) |
| A5 | An OCR test **fails on any machine without `pytesseract`**, which the repo's own comment says is in no requirements file | low | ⏳ with [Step 8](STEP-08-PENDING-HARSH-ocr.md) |

## B · Alarms that turned out not to be defects

⛔ **Four confident explanations, all wrong.** Each would have produced a code change to a file that
was already correct.

| # | The alarm | What it actually was |
|---|---|---|
| B1 | *"relevance has no model wired in production"* | `wiring.py` is correct and builds the client properly |
| B2 | *"it is a one-line fix in `wiring.py`"* | `wiring.py` needs no change at all |
| B3 | *"the `l1_semantic_activation` switch was never turned on"* | **LIVE since 18 Sep**, by `system:onboarding` |
| B4 | *"a regression landed on 19–20 Sep"* | those commits are a memory trim and a cost-ledger widening |
| B5 | *"3,152 failures a day is a retry loop hammering the API"* | 7.4 calls per subject per **day** — about one an hour. A periodic sweep meeting a closed door |

**What it really was:** `no_model_wired = 632` is **100% screen sessions**, and the screen instant
lane deliberately makes one AI call at S2 inside a 3.5 s timeout and does not build the S4 lane so
it cannot buy a second. Gmail: 0 unjudged. Calendar: rules settle it.

> ⛔ **A count without its dimension is not a measurement.**

## C · Things the Design Atlas calls missing that are already built

| Atlas says | Reality |
|---|---|
| no coverage receipts (`gap`) | `capture/coverage/signal_coverage.py` — **per source, frozen at capture, never 100% by default**. Plus `context/quality/window.py`, the coverage read |
| untrusted-content boundary (`target`) | `capture/semantic/injection.py` — and **stronger than specified**: the real defence is that the model cannot set `_bp`, `signal_type` or `visibility` because they are not in its output schema. *"Prompt text is advisory; the schema is enforcement"* |
| version and supersession (`target`) | `esqe/lifecycle.py` — and it **decided the pointer direction** where two specs disagreed |
| role extraction (`target`) | `actor_role` on the pipeline stage; `Commitment.actor` / `.beneficiary` typed |
| entity resolution with doubt (`target`) | `EntityMention.canonical_hint` nullable with `confidence_bp` |
| four-value importance split | **three of four already exist with the right owners** — `importance_bp` (capture), `priority_bp` (executive), `urgency_bp` (reason). Only L2 *materiality* is missing |

And one the Atlas treats as a doctrine is already a shipped field: **`BusinessFact.standing` is
`observed | judgement`.** Observation ≠ inference is enforced in the contract, not just believed.

## D · The two things genuinely missing

| # | Missing | Consequence today |
|---|---|---|
| D1 | **the signal bundle** | related signals arrive as separate loose events — four signals about one renewal become four weak situations | [Step 6](STEP-06-signal-bundle.md) |
| D2 | **`EvidenceNeed`** | a HOLD can only wait. `context/residue.py` already computes the demand (`signal_unreached`) and it reaches the model angles and stops there — **the measurement half exists, only the wire does not** | [Step 7](STEP-07-evidence-need.md) |

## E · Open questions nobody has resolved

| # | Question | Why it matters |
|---|---|---|
| E1 | **Does the heartbeat run in production?** The baseline says no (packages never purged, 341 attachments stuck). But `l4_llm_decision` fired **hourly across 21 hours** on 29 Sep. Both cannot be simply true | it is the top item in the baseline and may be half wrong |
| E2 | **Where do the four objects live?** open question · meeting follow-up · condition object · thread terminal state | [Step 5](STEP-05-NEXT-object-placement.md) — recommendation on record |
| E3 | **Thread terminal state does not exist at thread level** | either build it at L3 or declare it deferred **with a reason** |
| E4 | **37 events carry no domain** (125 of 162 tagged, 77%) | investigate after judgment is restored — the denominator may change |

## F · Measured, for the record

| | |
|---|---|
| `capture/` | 154 files · 46,377 lines · 19 subsystems |
| `esqe/` | 17 files · 9,278 lines |
| Signal types | **16** (an earlier note said 15 — `DELIVERY_FAILURE` joined them) |
| Relevance, by source | gmail 141 (0 unjudged) · gcal 55 (0) · screen 632 (632, by design) |
| Domain coverage | 125 of 162 tagged · 77% |
| Threads | 705 messages · 358 (51%) multi-message · 132 threads · longest 9 |
| Joinability | 83 of 85 · 97.6% |
| Full suite after our changes | **13,365 passed · 1 failed** (the 1 is A5) |
