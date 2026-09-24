# Harsh — everything blocked on you, in the order to do it

> **Branch:** `speedrun008` · **Updated:** 2026-09-24 · **Steps covered:** 1 – 15
> **This file replaces `HANDOFF-CTO.md`**, which only covered steps 1–3 and is now stale.
> **Read time:** 6 minutes. Each row links to its full runbook.

---

## The one-screen version

| # | Do this | Type | Blocks | Time |
|---|---|---|---|---|
| **1** | **Give us a scratch Postgres URL** | access | **618 tests across every step** | 30 min |
| **2** | Apply `0176_delivery_failure.sql` | migration | step 2 code | 2 min |
| **3** | Apply `0177_qualified_signals_subject_key.sql` | migration | step 3 code | 2 min |
| **4** | Apply `0178_sync_completeness.sql` | migration | step 5 code | 2 min |
| **4b** | Apply `0179_signal_world_instants.sql` | migration | step 14 code | 2 min |
| **4c** | Apply `0180_signal_coverage.sql` | migration | step 15 code | 2 min |
| **4d** | Apply `0181_signal_conversation.sql` | migration | step 18 code | 2 min |
| **5** | Deploy an image built from `Dockerfile` | deploy | step 1 (OCR) | 1 hr |
| **6** | **DECIDE: legacy receipts — keep or drop?** | decision | step 4 merge | 10 min |
| **7** | **DECIDE: raise the 60-day backfill window?** | decision | **the benchmark** | 15 min |
| **8** | Run the SQL in §6 — size the re-extraction bill | measure | step 4 deploy | 5 min |
| **9** | Answer: was the 19 Sept tenant re-sync intentional? | question | our baseline | 2 min |
| **10** | **Run the domain-coverage query (step 6 §3)** | measure | **step 6's target** | 5 min |
| **11** | **DECIDE: turn the domain proposer on?** | decision | step 6's value | 15 min |
| **12** | **DECIDE: split intent into its own model call?** (I built the free version) | decision | nothing — either way | 10 min |
| **13** | **Run the relevance query (step 8 §3)** — metric 5 has no live baseline | measure | step 8's last criterion | 5 min |
| **14** | **Hit `GET /parked/refetch`** — 13 PDFs sit at `fetch_failed` and the ladder should have cleared them | diagnose | step 1's last criterion | 2 min |
| **15** | **Run step 10's measurement** — it decides whether step 10 should exist at all | measure | **all of step 10** | 10 min |
| **16** | **The 425-item golden corpus + a second mailbox** — the benchmark's third column cannot be filled without them | data | **the whole benchmark claim** | days |
| **17** | **The pilot's commitment-state distribution** — it tests whether step 12's coverage gate is actually wired | measure | step 12's last criterion | 10 min |
| **18** | **The joinability figure** — what share of calendar attendees have an email-side counterpart | measure | step 13's last criterion · **P4's falsifiability** | 10 min |
| **19** | **DECIDE: re-sync the mailbox?** Every prompt we have ever sent said *"message 1 of 1"*. The fix is live for new mail; old mail needs a re-fetch | decision | **the quality of every threaded extraction** | 15 min |
| **20** | ⛔ **Item 1 again, and now it BLOCKS a done criterion.** Step 17's adversarial suite cannot run: **991 of 995 skips are one missing URL** | access | **618 tests · step 17's last criterion** | see #1 |
| **21** | ⛔ **Run the L2 refusal report on the pilot** — `python scripts/l2_refusal_report.py --org <pilot> --database-url <url>`. Read-only, every statement a `select`. It is the **denominator every Layer 2 step is measured against** | measure | **L2-0's last open half · every later L2 number** | 5 min |
| **22** | ⛔ **DECIDE: flip the 24 `draft` situations?** 16 of Customer Support's 20. Every card built from one is downgraded to an OBSERVATION — it describes and does not instruct. **One word per file, no code** | decision | **the cheapest quality win in L2** | 20 min |
| **23** | 📅 **Diary note only — nothing to do now.** `contracts.domain_expertise.BusinessSituationObject` is a deprecated alias and may be deleted **after 2026-12-24**. The date lives in `contracts/situation_stages.ALIAS_REMOVAL` and a test reads it from there | dated | nothing | 0 min |
| **24** | ⛔ **Run the L2 refusal report again AFTER item 21 and read `BY LAW`.** L2-2 added two laws — V-9 (an interpretation citing nothing) and V-10 (an empty `missing_facts` under low coverage) — both declared **OBSERVE**, so they report and do not block. **Arming either is one line, after somebody knows the count** | measure + decision | **whether L2 starts refusing unreceipted interpretations** | 10 min |
| **25** | **Run `python scripts/slice_weight.py --org <pilot> --sample 20`** — read-only. It prints what a real context slice costs in tokens, p50/p90/max. **L2-5's entire cost check rests on this number** | measure | **L2-5's cost check** | 5 min |
| **26** | ⛔⛔ **DECIDE: point `fundraising` at the `sales` corpus.** The investor doctrine is **already authored, stable and approved** and the pilot's dominant domain cannot reach it. One line, reversible, and `live_lane` still requires the corpus to be activated. Run `python scripts/unroutable_report.py --org <pilot>` for the count first | **decision** | **whether the pilot tenant sees anything at all** | 15 min |
| **4e** | Apply `0182_signal_situation.sql` | migration | **step L2-7 code** | 2 min |
| **27** | **Run `python scripts/card_collapse_report.py --org <pilot>`** AFTER 4e — it prints how many cards the founder sees and how many situations they are about. **The headline number of the whole Layer 2 plan** | measure | **the 38→N claim** | 5 min |

**Migrations 2, 3 and 4 must all be applied BEFORE the code that uses them ships.** All three are
idempotent and safe to re-run. Apply in number order.


---

## 21 · Run the Layer 2 refusal report — 5 minutes, read-only

⛔ **Layer 2's dominant failure is a refusal that is RIGHT and INVISIBLE**, and L2-0 built the
surface that tells a refusal apart from nothing having happened. Its own code says so:

> *"Such a card today simply exists, ranks, and quietly never becomes anything, while **no surface
> says 'its best evidence scored 1360 against a floor of 2500'**. That is the fifth time this
> codebase has carried a refusal that was right and invisible."*

```bash
python scripts/l2_refusal_report.py --org <pilot-org-id> \
       --database-url "$GENIOS_TARGET_DATABASE_URL"
```

**Read-only and structurally so.** The URL resolves through `scripts/_db.py`, which has no fallback
to `Settings`, and every statement in the script is a `select`.

### What comes back

```
admitted / held / rejected            the three outcomes
BY REASON                             all 7 HoldReasons, zeros included
REFUSED BY LAYER 1, WITH THE NUMBER   "scored 1360 against a floor of 2500", per situation
DOMAINS NO AUTHORED CORPUS CAN READ   fundraising — the pilot's OWN domain
THE AUTHORED CORPUS                   155 capabilities, per domain
TOTAL SITUATIONS PRODUCING NOTHING
```

### Why it matters more than it looks

Every later Layer 2 step claims a number — *situations reasoned*, *cards collapsed*, *domains
routed*. **Without this run none of them has a denominator.**

### One part already ran, and it found something

The corpus section needs **no database** and was run today:

```bash
python scripts/l2_refusal_report.py --corpus-only
```

⛔ **It contradicted the plan.** We had recorded *"534 capabilities, 200 admissible (37%), so
`require_admission=True` takes 334 dark"*. Measured: **155 capabilities, 155 admissible, 0 hollow.**
The 534 counted **files** — a capability is a directory of `capability.yaml` + `objects.yaml` +
`knowledge.yaml`. All 155 content-hashes were recomputed and verify.

**So the Layer 2 cutover flag is free, not a cliff** — and the number had been wrong for weeks
purely because nothing printed it.

> **The one decision this may raise for you:** `fundraising` is the pilot's own domain and has **no
> authored corpus**, so Layer 2 mints `investor_relationship` and `investor_contact` situations that
> nothing can read. That is **authoring work, not code** — and it is the largest non-code item in
> the Layer 2 plan.

---

## 27 · What the founder actually sees — 5 minutes, read-only, AFTER 0182

⛔ **This is the headline number of the whole Layer 2 plan.** *"38 cards becoming N"* has been a
claim since the plan was written, and nothing has ever printed the ratio.

```bash
python scripts/card_collapse_report.py --org <pilot-org-id> \
       --database-url "$GENIOS_TARGET_DATABASE_URL"
```

It refuses to report at all if 0182 is missing, rather than printing a collapse of 1.00 and
letting somebody conclude there is nothing to merge.

### What it tells you

```
open signals without a card       ← cards today
situations they belong to
signals with no situation         ← surfaced, LABELLED, never dropped
cards after the collapse
collapse                          N.NN×
```

plus the widest fan-outs — one situation, many rules, many cards.

### Why the fan-out happens

Signals are emitted **per (pack, rule, node)**. One situation compiles a package, the package
fires several rules, and each rule becomes a card:

```
"Nitesh's inbound messages dropping over 28 days"        rule 1 → card 1
"Nitesh Pant's touch frequency declining over 28 days"   rule 2 → card 2
"Check in with Nitesh Pant on engagement"                rule 3 → card 3
```

They could never merge, because **the builder had no way to see they were one situation** — the
`situation_id` was in scope at emit time and thrown away. 0182 gives it somewhere to go.

> **Nothing changes for a founder until a tenant is activated.** The loop is still the old one;
> what 0182 buys today is the *measurement*, and the measurement is what the cutover decision
> needs. A signal whose situation never formed is **surfaced with a label**, never dropped —
> fewer cards must come from merging.

---

## 26 · ⛔⛔ The fundraising doctrine exists. One `None` hides it.

**This is the largest single thing in Layer 2, and it is one line.**

The Layer 2 plan said the pilot's dominant domain was dark because *"no fundraising corpus
exists — the fix is authoring, not code."* Measured against the catalog on 2026-09-24:

```
sales.sit.live_investor_relationship      stable · approved
   "An ongoing relationship with a party that might fund us, read at the ACCOUNT level:
    the fund, the accelerator, the syndicate"

sales.sit.live_investor_contact           stable · approved
   "A named individual at an investor, accelerator or programme, read at the PERSON level"

sales.investor_relations.investor_relations
   "Reading and running the relationships with the people who might fund the company:
    funds, accelerators, angels and the operators who introduce them."
```

**It was authored inside the Sales corpus.** `_L2_TO_L3_DOMAIN["fundraising"]` answers `None`, so
every investor situation on the tenant publishes no package and emits no signal.

### Why this is safe, and how we know

The old objection was *"mapping fundraising onto admin would put Admin doctrine on a fundraising
situation."* True — and **routing is per situation type, not a domain blanket:**

| fundraising mints | routes to |
|---|---|
| `investor_relationship` | `sales.sit.live_investor_relationship` |
| `investor_contact` | `sales.sit.live_investor_contact` |

**Those are the only two types fundraising can mint, and both land on investor doctrine.** No
generic deal doctrine is reachable. A test proves it and will keep proving it.

### Why it is not already done

Arming it makes every fundraising situation activatable **at once**, and nobody has counted them
on the pilot. Same discipline as the two new laws: measure, then arm.

```bash
python scripts/unroutable_report.py --org <pilot-org-id> \
       --database-url "$GENIOS_TARGET_DATABASE_URL"
```

Read the per-type counts. Then the change is:

```python
# genios_engine/reason/domain_shadow.py
"fundraising": "sales",     # was None — see CANDIDATE_ROUTES
```

**Two switches, not one.** `live_lane` still requires the tenant to have activated the `sales`
corpus, so this makes fundraising *activatable*, not live. Reversible by putting the `None` back.

> **`general` is NOT the same decision and must not be bundled with it.** Its `relationship` type
> is claimed by **all three** corpora, so routing it means picking one by hand — which is how
> Admin doctrine lands on a support thread. It stays dark until a census says what actually lands
> there.

---

## 25 · What a context slice actually costs — 5 minutes, read-only

L2-5 puts a model on Layer 2. **What it costs is decided by how many tokens a slice weighs**, and
the step file is blunt about guessing: *"the cost check for L2-5 depends on this number, and
guessing it would make that check theatre."*

```bash
python scripts/slice_weight.py --org <pilot-org-id> --sample 20 \
       --database-url "$GENIOS_TARGET_DATABASE_URL"
```

Read-only through `scripts/_db.py`, every statement a `select`, and it builds each slice **exactly
the way the sweep does** — so what it weighs is what the reasoner would be handed.

### What we already know, and where the plan was wrong

Measured through the real builder on constructed shapes:

| facts / obs / neighbours | tokens |
|---|---|
| 8 / 6 / 4 | **714** ← the plan's *"900-token slice"* |
| 30 / 25 / 20 | 2,509 |
| 100 / 80 / 60 | **8,049** ← the plan's *"10,000-token thread"* |

⛔ **The plan says a slice is cheap because it is a slice. It is cheap because the node is small.**
A busy account — the kind a founder most wants reasoned about — produces a slice that costs as
much as the raw thread it replaced.

`SLICE_TOKEN_BUDGET` is set to **2,000** and **reports rather than truncates**: dropping facts to
hit a number is how a reasoner concludes from evidence nobody chose to remove. The run above says
how many of the pilot's situations break it.

> **What this changes if the tail is fat:** L2-5 either narrows what goes in a slice, or reasons
> over fewer situations, or costs more than planned. All three are decisions — and none can be
> made without this number.

---

## 24 · ⛔ Two new laws are watching, and neither blocks yet

L2-2 added **V-9** and **V-10** to the Layer 2 gate. Both are declared `OBSERVE`: they are
recorded on the decision and **the situation still publishes.** Nothing that shipped yesterday
stopped shipping.

| law | what it sees |
|---|---|
| **V-9** | an interpretation that cites nothing. `Anomaly`, `MetricCorrelation`, `CohortPosition` and `ImportanceAttribution` carried **no evidence reference at all** — `MatchedCondition` has enforced the same rule on itself for months: *"'this fired because of these facts' is what makes a situation defensible"* |
| **V-10** | an empty `missing_facts` on a situation whose coverage was never good enough to conclude that nothing was missing |

### Why they are not armed

Arming them means refusing live situations, and **nobody has counted how many.** L1's step 10 set
the precedent by gating itself on a measurement rather than guessing. `LawAction`'s own docstring
had already designed for this: *"a law that later downgrades or parks is a one-line change here
plus a branch in `validate_situation`."*

### What to do, after item 21

```bash
python scripts/l2_refusal_report.py --org <pilot> --database-url "$GENIOS_TARGET_DATABASE_URL"
```

Read the **`BY LAW`** block. It prints every law including zeros.

| V-9 count | what it means |
|---|---|
| **low** | arm it — `LAW_ACTIONS[V9] = REJECT`, one line, and L2 stops publishing interpretations nobody can check |
| **high** | the producers owe receipts first. The report names which |

Same reading for V-10.

> **This is the cheapest possible way to make a decision like this**: the law is written, it is
> running, it is recording, and it costs nothing until you decide it should.

---

## 22 · ⛔ DECIDE — 24 authored situations are `draft`, and their cards cannot instruct

The corpus's **capabilities** are whole: 155 of 155 admissible, every hash verified. The gap is on
the other half of the ceremony.

| domain | situations | **`draft`** |
|---|---|---|
| Admin | 34 | **8** |
| Sales | 15 | 0 |
| **Customer Support** | 20 | **16** |
| | **69** | **24** |

### What a `draft` situation costs — from the rule's own docstring

> *"the gap lands in `admission_gaps` → `plan.admitted=False` → the package's
> `review_state='draft'` → **`deliver/pipeline._apply_abstention` downgrades the card to an
> OBSERVATION.** The intelligence still ships; **it stops instructing.** Removing the situation
> would delete the finding to punish its prose."*

So a support situation routing through one of those sixteen produces a card that says *what is
happening* and cannot say *what to do*. **That is the complaint, precisely.**

### The decision

Each of the 24 is either **genuinely unfinished** (leave it `draft`) or **finished and never
flipped** (`identity.status: draft` → `stable`, one word). Nobody has looked, because until today
nothing printed the list.

```bash
python scripts/l2_refusal_report.py --corpus-only     # no database needed
```

**No code, no migration, no model call.** If a meaningful share of the 24 are merely un-flipped,
this is the largest quality gain in Layer 2 for the least work — and it is reversible.

---

## 1 · Scratch Postgres — the single biggest unblock

**618 tests are SKIPPED, not passing.** They are the ones marked `pg`, and they are exactly the
L1→L2 seam tests that every step so far depends on. A skip is not a pass, so until this exists
every step ends with "verified hermetically, real-DB proof pending".

```bash
export GENIOS_TEST_DATABASE_URL="postgres://..."
.venv/bin/python -m pytest -m pg -q
```

Any throwaway Postgres 15+ works. **It must not be production** — the suite drops and recreates
the schema.

> This one line closes the open half of steps 1, 2, 3 and 5 at once.

---

## 2–4 · The three migrations

```bash
psql "<url>" -f migrations/0176_delivery_failure.sql
psql "<url>" -f migrations/0177_qualified_signals_subject_key.sql
psql "<url>" -f migrations/0178_sync_completeness.sql
psql "<url>" -f migrations/0179_signal_world_instants.sql
psql "<url>" -f migrations/0180_signal_coverage.sql
psql "<url>" -f migrations/0181_signal_conversation.sql
```

| Migration | What it does | If you skip it |
|---|---|---|
| **0176** | widens two CHECK constraints for `delivery_failure` | **every bounce signal fails to INSERT.** The step produces nothing and looks like it worked |
| **0177** | `qualified_signals.subject_key` + index | **every situation read fails** — the widened projection SELECTs a column that is not there |
| **0178** | four completeness columns on `l1_sync_runs` | **every sync-ledger write fails silently.** It is wrapped in a `try/except` that never raises, so syncs keep working and simply stop being recorded — which is worse than crashing |
| **0179** | four world instants on `qualified_signals` (`due_at`, `effective_at`, `resolved_at`, `superseded_at`) + a partial index on `due_at` | **every signal INSERT fails** — the store now names these columns. Without them a signal still cannot say *"8 days overdue"*, which is the question P2 asks |
| **0181** | five conversation columns on `qualified_signals` (`thread_key`, `direction`, `turn_index`, `thread_depth`, `ball_in_court`) + two partial indexes | **every signal INSERT fails** (same reason). And Layer 2 keeps recomputing *whose turn it is* from Gmail labels because L1's real answer never arrives — it moved the benchmark 20 → 24 |
| **0182** | `signals.situation_id` text + a partial index | **every compiled signal INSERT fails** — `domain_shadow` now names the column. And without it the card loop stays one-card-per-SIGNAL: one situation that fires three rules keeps producing three cards that can never merge, which is the *"Nitesh Pant × 3"* symptom exactly. **Nullable and no FK, deliberately**: a situation archives on its own lifecycle while its signals stay open |
| **0180** | `qualified_signals.coverage` jsonb — the window and per-source completeness a negative claim rests on | **every signal INSERT fails** (same reason). And without it **a signal in state `broken` cannot publish at all** — the contract refuses a negative claim with no proof behind it, which is deliberate |

Full detail: [step 2](plan/layer-1/STEP-02-PENDING-HARSH.md) ·
[step 3](plan/layer-1/STEP-03-PENDING-HARSH.md) · [step 5](plan/layer-1/STEP-05-PENDING-HARSH.md)

---

## 5 · Deploy from the Dockerfile — OCR has never run, once

`document_jobs` in production: **every row `ocr_engine = NULL`, `ocr_pages = 0`.** Not a flag, not
a code path — the image that contains tesseract has never reached the host. 28 attachments are
OCR-addressable today and none has ever been read.

I already corrected a stale note in the `Dockerfile` that claimed two env vars were still required;
both clauses were false. Nothing else in the repo blocks this.

Full detail: [step 1](plan/layer-1/STEP-01-PENDING-HARSH.md)

---

## 6 · DECISION — legacy receipts: keep or drop?

**Context.** Step 4 typed three claim lanes. Every extraction already cached in
`l1_extraction_results` carries the old shape, and Layer 2 rehydrates those rows on the **live**
path. I wrote a read-side migration so they keep loading.

**The question:** the old shape carried `evidence_text`, a free receipt string nothing ever
checked. What should happen to it?

| | What it means |
|---|---|
| **A — keep it as an ungraded probe span** *(built, recommended)* | no data loss; ALG-08 grades it on read; nothing is trusted that was not checked |
| **B — drop it** | cleaner doctrine, but **silently removes existing `party.role` facts from the live graph** |

I built A because B deletes data without a human ever seeing what was deleted. It is a product
call about a live graph, so it is yours. **Reply "A" or "B".**

Full detail: [step 4 §4](plan/layer-1/STEP-04-PENDING-HARSH.md)

---

## 7 · ⛔ DECISION — the 60-day window. This is the big one.

**The backfill window is 60 days.** The plan said 540; it was 540 once and was deliberately reduced
because an 18-month first sync meant hours staring at an empty graph.

| Benchmark | Asks about | A default connection holds |
|---|---|---|
| **P3** | 6 months = 180 days | **60 days** |
| **P4** | 12 months = 365 days | **60 days** |

> **P3 and P4 are not "unproven". They are structurally impossible — the mail was never fetched.**
> No amount of coverage reporting fixes that.

| Option | What it means |
|---|---|
| **A — raise it for the benchmark tenant only** *(recommended)* | one admin write, one connection, no deploy, bounded cost, reversible |
| **B — raise the default** | the slow-first-sync problem comes back for everyone |
| **C — leave it** | P3 and P4 stay impossible and **we should stop citing them** |

Full detail: [step 5 §2](plan/layer-1/STEP-05-PENDING-HARSH.md)

---

## 8 · Measure — what does step 4 cost to ship?

Step 4 changes the extraction prompt, so `vocabulary_fingerprint` moved
(`151b9dabf235 → a3d5496aa0d3`) and **every cached extraction misses. The whole corpus re-extracts
on the first sweep after deploy.**

That is *correct* — a cache that survived a prompt change is how "260 cached extractions survived a
prompt fix and the numbers did not move" happened before — but it is a real bill nobody has priced.

```sql
select count(*)                        as rows_to_reextract,
       count(distinct org_id)          as tenants,
       sum(coalesce(input_tokens, 0))  as input_tokens_last_time,
       sum(coalesce(output_tokens, 0)) as output_tokens_last_time
from l1_extraction_results;
```

`input_tokens_last_time` × current price ≈ the re-extraction. Then: **accept / stage to one tenant
/ defer to a billing window.** Do **not** try to keep the old fingerprint.

Full detail: [step 4 §5](plan/layer-1/STEP-04-PENDING-HARSH.md)

---

## 9 · One question

**Was the tenant re-sync on 19 September intentional?** The pilot corpus we measured against
(12 Aug – 8 Sep) no longer exists; production now holds 1,202 events dated 19–23 Sep. Every
"before" number in these documents was taken against the old corpus, so knowing whether this was
deliberate tells us whether our baseline is a baseline or an accident.

---

## 10–11 · Step 6 — one query and one decision

**Step 6 is built and merging it changes production behaviour for nobody** — the domain proposer is
off by default and proved byte-identical to today's output. No migration, no env var, no table.

**10 · The query.** Our 8% domain-coverage baseline is from the tenant that was re-synced away, so
metric 4 has no target. The SQL is in [step 6 §3](plan/layer-1/STEP-06-PENDING-HARSH.md). Four
numbers, and they decide item 11: if domains are already being tagged well, the proposer is not
worth switching on.

**11 · The decision.** One small model call per message that reads the text and names domains —
for the case `hints.py` already admits it cannot handle (*"container held at Nhava Sheva, BIS
certificate pending, L/C expires Friday"* matches none of the four shipped patterns).

Bounded three ways: its own call (so the extraction cache is **untouched** — no repeat of item 8's
bill), skipped under 80 characters, 256 max output tokens. Metered separately as
`domain_proposal`.

| | |
|---|---|
| **A — on for one tenant, watch the meter** *(recommended)* | bounded, reversible, metric 4 becomes measurable |
| **B — on everywhere** | if the query says coverage is bad enough |
| **C — leave it off** | the code is dormant and costs nothing |

---

## 12 · Step 7 — one decision, and it costs nothing either way

**Step 7 is the cheapest step in the plan: no migration, no new model call, no re-extraction.**

The plan wanted intent pulled out of LLM-2 into its own call, so "intent was wrong" could be told
from "the whole extraction was wrong". **That costs a third full re-extraction** (`intent` is in the
vocabulary that feeds the cache key) **plus a permanent second call on every message.**

I built the free version instead: a confidence **derived** from the axes the model already answers.
Doctrine 1 required that anyway — a model may describe, never score, so its self-reported certainty
must never become a stored confidence.

| | |
|---|---|
| **A — keep the derived version** *(built, recommended)* | attribution for zero cost |
| **B — split it anyway** | a third re-extraction + a permanent per-message call, for attribution we now have |

> **While you are here:** step 7 found the clean example of the bug it was written for.
> `DELIVERY_FAILURE` has 19 tests, fires in all of them, and has produced **zero** production
> signals — because **migration 0176 is not applied** and the table refuses the INSERT. The
> detector reports success and the row never lands. **That is item 2 above.**

---

## 13 · Step 8 — one query, and the good news inside it

**Step 8 needs no migration, no re-extraction and no extra model spend.** The LLM-5 budget is
unchanged — it is now *allocated* instead of refused.

**13 · The query.** Metric 5 (`69 events, 31%, never judged`) is from the tenant re-synced away, so
it has no live baseline. The SQL is in [step 8 §3](plan/layer-1/STEP-08-PENDING-HARSH.md).

### Two things worth knowing from this step

**Our scores were never as bad as they looked.** The tenant topped out at 4,640 of 10,000 across
395 signals. ALG-17 puts **30% of the scale on the money term**, this inbox carries almost no
amounts, and the graph was three weeks old — so the effective range was roughly 0–5,000 **and the
tenant used all of it.** `achievable_ceiling_bp` now publishes that: 4,640 against a reachable
7,000 is a high score, not a mediocre one. Same number, opposite conclusion, and Layer 4 ranks on
it.

**An over-budget page used to judge nothing at all.** Above the ambiguous share the guard alerted
and stopped — and on a young tenant almost every sender is unknown, so it always tripped. The
component that could have said *"this is a mass programme announcement"* never ran once. Same
budget now judges the head and **names** the tail, so an event nobody assessed is finally
distinguishable from one judged relevant.

---

## 14 · Step 1's last open item — and it is a diagnosis, not a build

**13 PDFs in production sit at `DOC-05 fetch_failed`.** Step 1 recorded this as *"needs its own
unit"*. **That premise was wrong** — checked 2026-09-24:

* `capture/parked/refetch.py` is a five-rung retry ladder with a dead letter at the end
* it runs on the **heartbeat** — `api/routes.py:1039` → `_drain_attachment_refetch`, automatic
* it is passed an OCR engine (a defect already closed)
* it exposes **`GET /parked/refetch`** for status

**So nothing is left to build, and 13 stuck rows mean one of three things:**

| What the endpoint shows | What it means |
|---|---|
| the queue is non-empty and untouched | **the heartbeat is not running in production.** That is the finding, and it affects every drain, not just this one |
| rows mid-ladder with attempts < 5 | working as designed; they will clear |
| dead-lettered rows with an error | terminal — and the error string says whether the message was deleted or the provider failed |

**One curl tells us which.** If it is the first, it is a much bigger finding than 13 PDFs.

---

## 15 · Step 10 — the step gated ITSELF, and the gate is yours

**Nothing was shipped for step 10.** No migration, no contract change, no routing, no cost. That is
the correct outcome, not a shortfall: the step's own §5 makes the measurement its first unit and
gives it the power to cancel the rest —

> *"68 or 0 both mean the thresholds are wrong — and **0 means the step is not needed yet**."*

The 68 is from the tenant re-synced away. So I built **the measurement** as a pure tested function
and stopped. `PublicationOutcome` is still closed at three, which its own docstring demands:
*"a fourth outcome invented at a call site would be an emit nobody reviewed."*

The SQL and the interpretation table are in
[step 10 §3](plan/layer-1/STEP-10-PENDING-HARSH.md).

### The thing worth reading across three steps

| Step | Found |
|---|---|
| **4** | `relationship_change` — published 4, **dropped 54**. Its ceiling sits *below* the floor |
| **8** | *why* — the money term is 30% of the scale and unearnable here, so `achievable_ceiling_bp` now says so |
| **10** | the population step 10 was reaching for **is that same set** |

**Steps 4 → 8 → 10 are one finding seen three times.** If the measurement shows one type dominating,
the answer is not a review queue at all — it is **8-U3**, a floor relative to the tenant's own
distribution, already deferred and waiting on the same corpus.

---

## 16 · Step 11 — the harness is built, the corpus is not

**The scoreboard is now code and runs in CI.** Its first act was to find two errors in our own
audit:

1. **`L1_P1_P5_AUDIT.md` miscounted itself** — its summary says *"16 built"*, its own tables show
   **15**. In the flattering direction, quoted into the plan, used as metric 6's baseline, and
   invisible because nothing re-derived it. The document now carries a SUPERSEDED banner.
2. **It was already stale** — five objects have moved since it was written. **The live score is
   20 of 38**, up from 15.

### The number that matters most

```
MISSES BY CLASS:  not_carried 11 · entity 2 · layer_two 1 · temporal 1 · ...
```

**11 of 18 misses are `not_carried`** — computed in Layer 1 and dropped at the seam. Not *"we
cannot extract this"*; the work is done and the answer is thrown away. Direction, who spoke last,
whose turn it is, turn index, thread depth.

Step 3 widened the seam 9 → 17 columns, but those were **signal-level**. The **thread-level**
values still do not cross: `QualifiedEnterpriseSignal` has 30 fields and not one is `direction`,
`ball_in_court` or `turn_index`. **That is the largest and cheapest block of benchmark objects left
in Layer 1**, and it is mostly step 14's work.

### What I need from you — and why I will not fake it

```
behavioural quotable?  False — 'corpus is 8 items, below the 425 the spec asks for'
```

The golden corpus is **8 files**. The spec asks for 425 annotated items (300 email · 50 calendar ·
50 documents · 25 transcripts), and E4 requires **a second high-volume mailbox** because *"N=1
mailbox with unusually low outbound flatters sent-side prompts."*

The harness **refuses** to print a behavioural number until both exist. A number from 8 files would
be the most convincing wrong number in the repo — and quoting one externally is precisely the
failure the benchmark was written to expose in somebody else's product.

Needs real customer data (tenant-isolation guards, E1) and **two annotators** (E2). Both are yours.

---

## 17 · Step 12 — one measurement, and it is a trap-detector

Step 12 built the vocabulary for *"did the promise get kept?"* and, more importantly, **the rule
that stops us saying `BROKEN` on a corpus we barely read.**

> Claude's benchmark run marked four promises **Broken** and was right — it could see nearly the
> whole sent folder. On a mailbox where we read 8%, the identical absence means **UNKNOWN**.
>
> **Telling a founder they broke a promise they actually kept is worse than saying nothing.**

`BROKEN` now requires a coverage figure **≥ 9000 bp**. No figure at all also means `UNKNOWN` —
`None` is nobody having measured, not zero.

### The measurement, and why it is really a self-check

The step's own §3 predicts: **most commitments must land in `UNKNOWN`.**

> *"If most land in `BROKEN`, the coverage gate is not wired and the step has produced a confident
> lie."*

So the distribution is not a nice-to-have number — **it is how we find out whether the most
important rule in the step is actually running.** Run it with the coverage figure beside it.

---

## 18 · Step 13 — one figure, and it decides whether P4's answer means anything

Step 13 stopped Layer 1 destroying the keys P4's join needs. The finding is worth knowing:

> `to` and `cc` are read separately from the headers, **flattened one line later**, preserved in the
> raw dict, and **flattened again** by the only consumer that reads them. Three chances, all missed.

Fixed additively — `recipients` still means everyone on the message, so nothing downstream shifts —
and **the prompt is byte-identical**, because `envelope_hash` is a cache-key component and rendering
a `cc:` line would have re-extracted the whole corpus for something the model does not need.

### The figure I need

**Without joinability, P4's answer is unfalsifiable.** *"No follow-up found"* could mean no
follow-up happened, or that the calendar side and the email side were never joinable at all — and
those have opposite fixes. It is Gemini's 18-of-18 with a different denominator.

`joinability_bp(attendee_emails=..., email_side_emails=...)` over the pilot org.

### Two things fixed that were quietly costing us

**Calendar attendees were being reduced to address strings**, so a room booking or a guest invited
by name **vanished from the participant set**, and `responseStatus` — the difference between *"we
invited them"* and *"they came"* — went with it. P4 asks about meetings that **happened**.

**`meeting_kind` now exists.** On the pilot's 7 calendar events **5 were cohort sessions** where no
follow-up is expected, so *"0 of 7 followed up"* was a true number and a misleading finding. The
code already knew the cost — `calendar.py`'s own comment: *"'send a recap' shipped on twenty-person
cohort workshops the founder attended as one participant."*

---

## 19 · Step 16 — ⛔ the one you should read even if you read nothing else

**Every prompt Layer 1 has ever sent told the model the message was the first and only one in its
thread.**

```
thread position: message 1 of 1
```

On a twelve-message renewal negotiation. On the fourth round of a contract redline. On every
message in the corpus, without exception, since the day the envelope was written.

Not a bug in a rule. `pipeline._thread_place` has read `thread_position` and `thread_depth` since it
was written, and **no connector ever wrote either**, so it returned the default every single time.
The default is *correct* — a lone message really is the first of one — which is exactly why nothing
caught it. **A missing field fails loudly at its first reader. A wrongly-stated one never fails at
all**, and 12,700 tests did not see it.

### Fixed, and it cost nothing

RFC 5322 already carries the answer. `References` lists a message's ancestors, so N references means
this is message N+1 — from a header we now capture anyway. **No extra API call.** I did not add
`threads.get`: an exact thread size costs one request per thread on every sync, and the position is
the part that matters.

### What I need from you: one decision

The fix is **forward-only**, and not by choice — the raw Gmail payload is encrypted and expires, so
a backfill cannot retrofit a header onto a landed event. The bytes are gone. Only a **re-sync from
Gmail** can fill it for old mail.

| | | |
|---|---|---|
| **A · re-sync the pilot mailbox** | old threaded mail gets real positions | a re-fetch, plus a re-extraction of **replies only** |
| **B · forward-only** | new mail is correct from today; old mail keeps `(1, 1)` | the corpus is mixed in precision |

**B is not wrong.** `(1, 1)` on a thread we cannot see is the *honest* answer — that is why the
default was written that way. The corpus would be mixed in **precision**, not in **truth**.

**The re-extraction is bounded and I would not call it a cost.** An opening message still renders
`message 1 of 1` byte-for-byte, so it keeps its cache entry. Only replies miss — and **a reply's
cached extraction was produced from a prompt that stated a falsehood.** Re-extracting it is not the
price of the fix; it is the fix. `vocabulary_fingerprint` is unchanged, so the whole-corpus trigger
does not fire.

### One number would decide it, and it needs the corpus

```sql
select count(*) filter (where raw->'headers' ? 'References') as replies,
       count(*) as total
  from source_events
 where source = 'gmail';
```

If replies are a small share, **A** is cheap and worth it. If most of the mailbox is threaded, the
re-extraction is real and **B** buys time. I cannot run it — read-only, and this is a shape question
about your corpus.

### Two other things from this step

**Two of the three gaps this step was written to close were already wrong.** `responseStatus` was
closed by step 13. **`bcc` is impossible** — Gmail's API does not supply it, and on a message we
*received* it is invisible by definition. That is the second time a premise check has spent effort
rediscovering it, so it is now a row in `connectors/manifest.py` with the reason written down, and
nobody re-opens it as an oversight.

**`assemble_chain` still has not run on a real thread.** It implements full RFC 5322 parent
resolution, it is correct, and the pipeline hands it a list of **one** message. Capturing the
headers was necessary and is **not sufficient** — I carried them to the seam so it is already right
the day a caller supplies the siblings, and wrote the limit down as a passing test rather than
letting it read as finished.

---

## 20 · Step 17 — the adversarial pass ran, and one criterion cannot be ticked

Step 17 does not build a feature. **It tries to break the other sixteen.** Its output is a list of
things that are wrong.

### What it found

**29 of 40 scenarios are closed and each one dies when its fix is removed** — that last clause is
the whole value. A green test proves nothing on its own; the build record already says so in as
many words: *"Each was found by adversarial review, never by the test suite — because a unit test
passes perfectly well on code nobody calls."*

**One row is still open.** `pipeline.py` hands the thread reconstructor a list of **ONE** message,
so RFC 5322 parent resolution still has not run on real data. Step 16 carried the headers to that
seam, so closing it is one caller change. It is now a **failing test with an address**, not a TODO.

**One is impossible** — bcc, for the third time. It is a row in the manifest with the reason
written down so nobody spends another hour rediscovering it.

**Three regressions that actually happened in this round are now reproduced as tests**, so they
cannot happen twice: step 9's directness constant that silently discounted every confidence in the
system by 10%, step 13's meeting-kind rung order that would have chased a twenty-person cohort for
a recap, and step 4's evidence walker that skipped three claim lanes.

### ⛔ What I need from you: nothing new — it is item 1

```
12875 passed · 14 failed (all pre-existing) · 995 skipped
                                              └── 991 say "GENIOS_TEST_DATABASE_URL not set"
                                                  618 tests carry the `pg` marker
```

The criterion is *"the full suite on a **freshly recreated** Postgres, **0 skips**"*. **A skip is
not a pass**, so I have left it unticked rather than call it done.

This matters more than the count suggests. The last time a scratch DB was pointed at this suite it
surfaced **12 failures the green suite never showed — and 10 of them came from a DIRTY scratch DB**,
which is why the run has to drop and recreate first:

```bash
export GENIOS_TEST_DATABASE_URL="<scratch>"   # NEVER production — the suite drops and recreates
uv run --no-sync pytest -q -p no:randomly
```

**Any throwaway Postgres works.** Docker, a Supabase branch, a free Neon instance — it needs no
data, because the suite builds its own schema.

### One thing worth knowing about the six numbers

I wrote the START-vs-END table into `STATUS.md`, and **three of the six say "unmeasurable" rather
than carrying a figure.** Metrics 1 (attachments), 4 (domain coverage) and 5 (relevance) are all
*"the code is built, the number needs the corpus"*.

I could have put numbers there. **Putting a figure nobody measured into a results table is the exact
failure this entire round was built to end** — it is Gemini reporting the size of its context as
the size of the mailbox. So they say unmeasurable, and they name which of your items unblocks each.

The three that DID move: the seam went **9 → 17 columns declared**, claim lanes that can hold a
receipt went **8 → 11 of 15**, and the benchmark went **15 → 20 of 38**. That last baseline was
itself wrong — the audit's summary said 16 while its own tables showed 15 — and the calibration
reports **0 unexplained and 0 regressed**, so the +5 is real movement rather than a harness that
learned to flatter itself.

---

## What is NOT yours — I am carrying these

| Item | Step |
|---|---|
| 5-U5 — the coverage ratio on the signal | deferred to step 15; needs a `run_id` on `source_events` |
| Wiring the symmetry check to a scheduled report | step 5; the pure function is done |
| `proposed_unknown` review surface | step 6; the names are carried, the report belongs with the open-lane discovery report |
| A weekly report over the new per-sweep counters | step 7; the counters exist, the report is a reporting task |
| 8-U3, a floor relative to the tenant's distribution | step 8; deferred — needs a live corpus, and interacts with `relationship_change`'s ceiling |
| Step 10's U1–U4 | gated on item 15's answer — and it may cancel them |
| Carrying the thread-level values to the seam | the 11 `not_carried` misses — step 14 |
| 12-U3 · fulfilment detection | a cross-event join; L1's unit is one event. Belongs beside step 15 or in L2's correlator |
| 13-U4 · participation edges | 3 of 4 are derivable from what step 13 preserved; the 4th is cross-event, like step 12's |
| Teaching L2 to read the to/cc split | `runner.py:161` still flattens it — a Layer 2 change |
| Steps 14–17 | queued; step 14 starting next |

---

## Send it all back in one table

| # | Item | Your answer |
|---|---|---|
| 1 | scratch Postgres URL | |
| 2–4 | migrations 0176 / 0177 / 0178 / **0179 / 0180 / 0181** applied? | |
| 5 | Dockerfile image deployed? | |
| 6 | legacy receipts: **A** or **B**? | |
| 7 | backfill window: **A**, **B** or **C**? | |
| 8 | `rows_to_reextract` and `input_tokens_last_time` | |
| 8 | accept / stage / defer the re-extraction? | |
| 9 | was the 19 Sept re-sync intentional? | |
| 10 | domain-coverage query: the four numbers | |
| 11 | domain proposer: **A**, **B** or **C**? | |
| 12 | intent split: **A** (keep derived) or **B** (split)? | |
| 13 | relevance query: `never_judged` / `deferred_new` / `model_judged` | |
| 14 | `GET /parked/refetch` — what does it say? | |
| 15 | step 10 measurement: `candidates` / `unassessable` / `by_type` | |
| 16 | golden corpus: can we get to 425 annotated items + a 2nd mailbox? | |
| 17 | commitment-state distribution + the coverage figure beside it | |
| 18 | joinability: what share of attendees have an email-side key? | |
| 19 | replies-vs-total query, and **A (re-sync)** or **B (forward-only)**? | |
| 20 | scratch Postgres URL — **same as #1**, and it now blocks step 17 | |
