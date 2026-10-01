# Step 2 — PENDING · owner: Harsh

> **Status:** code COMPLETE and green · **two things left, both yours**
> **What it does:** makes GeniOS able to say *"your pitch to Afore never arrived"* — the single
> highest-value finding in the Gemini/Claude benchmark, which neither model could reach reliably.
> **Written:** 2026-09-23 · **Evidence:** [`findings/step-02-bounce.md`](findings/step-02-bounce.md)

---

## 1. What this step is, in one paragraph

On 11 August the tenant pitched Afore and Surge. Three of those messages never reached anyone —
`madison@afore.vc` and `joseph@afore.vc` did not exist, `apply@surgeahead.com` failed permanently
after 47 hours of retries. **All five bounce notices were captured by Layer 1, emitted, and
produced zero signals.** The founder believes they pitched two funds. They did not, and nothing in
the product could say so.

That is now fixed in code. It is not yet fixed in production, and the two reasons are below.

---

## 2. What you need to do

| # | Action | Blocking? | Effort |
|---|---|---|---|
| **1** | **Apply migration `0176_delivery_failure.sql`** | **YES — without it every bounce signal fails to insert** | minutes |
| **2** | **Give us a scratch Postgres URL** *(same ask as step 1)* | yes, for the replay proof | ~30 min |

### 2.1 · The migration — and why it is not optional

`qualified_signals.signal_type` and `qualification_drops.signal_type` carry **CHECK constraints**
listing the permitted values. Confirmed in production today:

```
CHECK (signal_type = ANY (ARRAY['commitment_made', 'commitment_due', ... 'availability_change']))
```

`delivery_failure` is not in that list. So **without the migration**: the detector fires, the
qualification floor lets it through, and the INSERT is refused by the constraint. The step would
produce nothing and look like it worked.

`migrations/0176_delivery_failure.sql` widens both CHECKs by exactly one value. It follows
`0139_availability.sql` verbatim — that is the precedent, written when `availability_change` became
member fifteen. **Idempotent**: drop-if-exists + add, one transaction per table, safe to re-run.

> **Order matters.** Apply `0176` **before** the code that emits the new type reaches production.
> Constraint first, then the writer.

### 2.2 · The scratch Postgres

Unchanged from step 1's ask: **618 of 13,660 tests cannot run without one**, and the end-to-end
proof for this step is among them. We have run everything that is runnable here — see §4 — but the
number that matters has not moved yet, because moving it means replaying the five real bounces.

**Not production, not a copy of it.** The suite drops and recreates schema.

---

## 3. What was built, and how it is wired

```
  bounce arrives
        │
        ▼
  gate/rules.py            availability_marker no longer files it as an out-of-office
        │                  (it was being called `auto_reply` — that saved it from the N-03 drop
        │                   by accident, but "the message did not arrive" is not availability)
        ▼
  capture/delivery_status.py   NEW · the recogniser
        │                  · two conditions, both required: a daemon sender AND a body that
        │                    reads like a delivery report. Either alone is a false positive
        │                  · FAILED vs DELAYED vs UNKNOWN — a message still being retried has
        │                    NOT failed, and saying it has is the worst error this can make
        │                  · reads the recipient out of the prose. No MIME walk, no OCR needed
        ▼
  esqe/relevance.py        a RULE_DELIVERY_FAILURE rung ABOVE the bulk-header rung
        │                  · this is the actual fix. A DSN carries bulk headers by construction,
        │                    so the bulk rung was refusing it on its ENVELOPE, before S2 — which
        │                    is why no extraction ran and no predicate could fire
        ▼
  capture/pipeline.py      ONE reader, called from both candidate builders and the detector,
        │                  so the envelope path and the full path cannot disagree
        ▼
  esqe/detector.py         the predicate — reads the ENVELOPE, not a claim. A bounce is a machine
        │                  notice with no commitment, amount or date in it, so a predicate waiting
        │                  for a claim would never fire
        ▼
  esqe/classifier.py       precedence SECOND, above every claim-derived type. Gmail returns the
        │                  original message inside the bounce, so its claims are visible; ranked
        │                  lower, an undelivered pitch's primary type would be "a commitment was
        │                  made" — for a commitment nobody ever received
        ▼
  esqe/importance.py       ALG-17 weight 9000, tied top. **The formula is untouched.**
        ▼
  esqe/qualification.py    DELIVERY_FAILURE_OVERRIDE — see §5, this one needs explaining
        ▼
  esqe/normalize.py        the subject is the FAILED ADDRESS, so three bounces to one address
        │                  group as one story and ALG-19 can supersede across them
        ▼
  context/observations/kinds.yaml   Layer 2's meaning row — polarity neutral, not an ask,
                           not progress. Layer 2 keeps its own totality table over Layer 1's
                           taxonomy, and it failed the build until this row existed
```

**Files changed:** `capture/delivery_status.py` (new) · `capture/pipeline.py` ·
`capture/gate/rules.py` · `capture/esqe/{relevance,detector,classifier,importance,normalize,qualification}.py` ·
`contracts/signal.py` · `context/{vocabulary.py,observations/kinds.yaml}` ·
`migrations/0176_delivery_failure.sql` (new) · `tests/capture/test_delivery_failure.py` (new)
plus four existing tests updated for the new member count.

---

## 4. What has been verified, and what has not

| | Result |
|---|---|
| `tests/capture/test_delivery_failure.py` | **19 passed** |
| `tests/contracts` + `tests/capture` | **5,489 passed** · 3 failed |
| `tests/context` | **2,390 passed** · 11 failed |
| **Regressions** | **zero** |

All 14 remaining failures are pre-existing or environmental, each identified: 11 are a
`llm_costs has no column named cache_read_tokens` fixture drift in `tests/context`, one is in
`tree.yaml`'s supplied baseline, one needs Postgres, one needs tesseract on this machine.

**NOT verified — and this is the honest gap:**

* the **migration has not been applied anywhere**. It is written and follows 0139 exactly; it has
  not been run, because that needs Postgres.
* the **five real bounces have not been replayed**. The unit tests and the wiring test pass; the
  production number is still zero signals.

---

## 5. One design decision worth your review

A delivery failure **cannot clear the qualification floor on its own score**, and that is
structural rather than a quirk of this tenant. Measured:

```
tenant floor (default)   2500
delivery_failure         1080     escalation 1080 · contract_renewal 1000
```

ALG-17's five terms are money, deadline, actor authority, entity criticality and a type nudge.
A bounce states no amount and no deadline, its actor is a mail daemon, and the one entity it names
is by definition one we could not reach — **four of five are zero by construction**, so the type
nudge alone decides, and it can never reach 2500 whatever weight it is given.

**ALG-17 was not touched.** No weight was nudged to make a number pass; the score is 1080 and is
reported as 1080. What was used is the floor's own existing mechanism: a named, ledgered override,
exactly like `AVAILABILITY_OVERRIDE` — which exists for the mirror-image reason, a type whose
weight is deliberately the *lowest* and which the floor would otherwise silence entirely.

The refusal stays fully auditable: `qualification_drops` still records the score and the reason.

> **If you disagree with that override, the alternative is step 8** — the floor work, where three
> of four types checked die at the default floor on a cold-start tenant. Say so and we will move
> it there instead of carrying it here.

---

## 6. Cross-check — the procedure, in order

Every step is runnable. **Do them in this order**; each one is a gate on the next.

### 6.0 · Before anything — record the BEFORE numbers

```sql
-- how many delivery-failure signals exist today (expect 0)
select count(*) from qualified_signals
 where org_id = 'org_e97e86f858ad48b2bbf64b8a' and signal_type = 'delivery_failure';

-- how many events die on the envelope rule today (expect ~30)
select reason_code, count(*) from event_trace
 where org_id = 'org_e97e86f858ad48b2bbf64b8a'
   and stage = 's2_semantic_extraction' and action = 'short_circuit'
 group by 1 order by 2 desc;
```

**Write both down.** A step whose number does not move is not done, and you cannot say it moved
without the before.

---

### 6.1 · GATE 1 — apply the migration, then prove the constraint changed

```bash
psql "<url>" -f migrations/0176_delivery_failure.sql
```

```sql
select pg_get_constraintdef(oid) from pg_constraint
 where conname = 'qualified_signals_signal_type';
```

**PASS:** the list ends with `'delivery_failure'::text`.
**If it does not, stop.** Everything below will appear to work and write nothing.

Repeat for `qualification_drops_signal_type` — both tables are constrained and the migration
widens both.

---

### 6.2 · GATE 2 — the code is live

The new type has to be in the running image, not only in the repo. Same question as step 1's, and
if the deployed branch is the one without the Dockerfile it is very likely the same answer.

```sql
-- after one sweep, any row at all with the new type
select count(*) from qualified_signals where signal_type = 'delivery_failure';
```

**If this is 0 after a sweep that included mail, the code is not live** — check the deployed
branch before debugging anything in Layer 1.

---

### 6.3 · GATE 3 — the three real bounces

This is the finding. The five delivery-status events already exist in the tenant; they need
re-processing, not re-fetching.

```sql
select qs.signal_type, qs.importance_bp, qs.qualification_reason, se.event_id
  from qualified_signals qs
  join source_events se on se.event_id = qs.event_id and se.org_id = qs.org_id
 where qs.org_id = 'org_e97e86f858ad48b2bbf64b8a'
   and qs.signal_type = 'delivery_failure'
 order by se.occurred_at;
```

**PASS — exactly three rows**, and their subjects are:

| Expected subject | Address |
|---|---|
| `delivery:madison@afore.vc` | Afore |
| `delivery:joseph@afore.vc` | Afore |
| `delivery:apply@surgeahead.com` | Surge |

*(`subject_key` reaches `qualified_signals` only after step 3's migration `0177`. Until then read
it from `signal_lifecycle`, which already carries the column.)*

**Each row should carry `qualification_reason = 'delivery_failure_override'` and
`importance_bp` around 1080** — see §5. A row at or above the floor would mean the score changed,
which nothing in this step was supposed to do.

---

### 6.4 · GATE 4 — the three things that must NOT happen

These matter as much as gate 3. A step that finds bounces and also breaks the noise gate is a net
loss.

```sql
-- 1 · the two DELAY notices must produce NOTHING. A message Gmail is still retrying has not
--     failed, and saying it has is the worst error this feature can make.
select count(*) from qualified_signals qs
  join prepared_content pc on pc.event_id = qs.event_id
 where qs.signal_type = 'delivery_failure'
   and pc.clean_text ilike '%(Delay)%';
-- PASS: 0

-- 2 · newsletters must still die on their envelope. The exemption is narrow by design;
--     this rule saved 522,143 input tokens on the pilot org.
select count(*) from event_trace
 where org_id = 'org_e97e86f858ad48b2bbf64b8a'
   and stage = 's2_semantic_extraction' and reason_code = 'envelope_bulk_headers';
-- PASS: lower than the BEFORE number, but NOT zero. Zero means the exemption widened.

-- 3 · out-of-office handling is untouched. N-05 is the only route by which
--     "who is away, until when" ever reaches the graph.
select count(*) from qualified_signals
 where org_id = 'org_e97e86f858ad48b2bbf64b8a' and signal_type = 'availability_change';
-- PASS: unchanged, or higher. A DROP here means the availability path was broken.
```

---

### 6.5 · GATE 5 — nothing else moved

```bash
python -m scripts.pipeline_funnel_report --org org_e97e86f858ad48b2bbf64b8a --database-url "<url>"
```

**PASS:** captured / emitted / dropped / parked counts are unchanged except for the DSN events
moving from "no signal" to "one signal". **This step adds a signal type. It does not change what
is captured or what is dropped**, and if those numbers move, something else changed with it.

---

### 6.6 · Run the suite on a real database

The 618 Postgres-marked tests have never run against this change — that is the honest gap in §4.

```bash
export GENIOS_TEST_DATABASE_URL="<scratch>"     # NOT production; the suite drops and recreates
uv run --no-sync pytest -q -p no:randomly
```

**A skipped test is not a pass.** Expect the 14 pre-existing failures listed in §4 and no others.

---

### 6.7 · What to send back

Four numbers, and they close the step:

| | BEFORE | AFTER |
|---|---|---|
| `delivery_failure` signals | 0 | ? *(expect 3)* |
| `envelope_bulk_headers` short-circuits | ~30 | ? *(expect lower, not zero)* |
| `availability_change` signals | ? | ? *(expect unchanged)* |
| Suite failures on real Postgres | — | ? *(expect 14, the known set)* |

## 7. What is still ours, not yours

| | |
|---|---|
| **The join to the sent message** | the signal now carries the failed address as its subject, which is what Layer 2 needs to correlate. Turning that into *"your 11 Aug pitch to Afore"* is L2's correlation work, not L1's — **Layer 1 preserves the key, Layer 2 resolves identity.** Tracked in step 13 |
| **Step 3** | the seam. `subject_key` currently does not cross to Layer 2 at all, so even a perfect bounce signal arrives without the thing that makes it groupable. Its migration is now `0177` |

---

## 8. The two mistakes this step made, recorded because they are the useful part

1. **The written premise was wrong.** The step said the gate deletes bounces on the `mailer-daemon`
   sender. It does not — N-03 fires on `not att and machine`, and a Gmail DSN returns the original
   message as an attachment. Production said `emitted`. The planned first test would have gone
   **green on unchanged code** and "proved" a defect that was not there.

2. **The first implementation passed every unit test on a system that would still have refused
   every bounce.** It read `candidate.subject`, which `pipeline.envelope_candidate` leaves empty on
   purpose. That is the defect the build record says this layer shipped **six times** — *"a unit
   built, tested, green, and called by nothing on a real request path."*

Both were caught by measuring against production, not by reasoning. Neither would have been caught
by a green suite.
