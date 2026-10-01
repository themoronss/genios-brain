# HANDOFF · Harsh (CTO) — five items, in the order that unblocks the most

> **Written:** 2026-10-01 · **by:** Claude, from the YCW27 programme
> **Nothing here needs a code change in `genios-brain`.** Every item is a deployment, a dependency
> or a connector. The code side of all five is built, tested and merged into the working tree.
> **Read H1 first.** It is the only item that is actively breaking a write path.

---

## ⛔ BEFORE ANYTHING — one rule about reads

Any query you run to *check* something runs inside:

```sql
set transaction read only;
```

And **never** set `GENIOS_ALLOW_PROD_WRITE` in order to run a report. That variable is named for
writes because it was written for writes; setting it to read a number is the wrong shape of
permission and it is how a reporting script becomes a migration nobody reviewed.

**Also: the pooler was unreachable from this machine at 2026-10-01 while this was written**
(`aws-0-ap-southeast-1.pooler.supabase.com:6543`, connection timeout on all three hostaddrs; it had
answered 20 minutes earlier). Every number below was measured before that. **Re-verify with H0
before acting** — if the numbers disagree with this document, the database is right and this
document is stale.

### H0 · the one-minute state check

```sql
set transaction read only;

-- which of 0186..0190 are recorded as applied
select version from schema_migrations where version >= '0186' order by 1;

-- the columns they add, checked directly rather than trusted from the tracking table
select table_name, column_name from information_schema.columns
 where (table_name, column_name) in
       (('signals','output_lane'), ('signals','lane_reason'),
        ('cards','output_lane'),   ('cards','lane_reason'))
 order by 1, 2;

-- is anything still writing cards at all
select max(created_at) from cards;
```

Expected **today**: no rows from the first two queries, and `max(created_at)` at **2026-09-25** or
earlier.

---

# H1 · 🔴 Apply migrations `0186`–`0190` — this one is breaking writes

### What is wrong

Five migrations have never run in production. Four degrade quietly. **`0190` does not.**

`genios_engine/deliver/card_builder.py` → `insert_card` now writes `cards.output_lane` and
`cards.lane_reason`, and **neither column exists.** The next card write therefore fails with an
undefined-column error. It has not surfaced yet only because **no card has been written since
2026-09-25** — the API spend limit (see H4 / `STEP-04`) froze the card path first. **The moment the
spend limit lifts, card writes start failing instead of working**, and it will look like the spend
limit was never the problem.

### What each one is for

| | File | What it adds | Which step waits on it |
|---|---|---|---|
| | `0186_signal_bundles.sql` | the signals that arrived **together**, stored as one thing | L1 `STEP-06` |
| | `0187_evidence_needs.sql` | the one fact that would change the conclusion, asked for by name | L1 `STEP-07` |
| | `0188_pipeline_counters.sql` | the five numbers that turn *"we made 28 cards"* into a diagnosis | L2 `STEP-04` |
| | `0189_output_lane.sql` | `output_lane` + `lane_reason` on `signals` | L2 `STEP-05` |
| 🔴 | `0190_card_lane.sql` | the same pair on `cards` — the surface reads the card, not the signal | L5 `STEP-01` |

### Do this

```bash
cd <repo>
.venv/bin/python -m genios_engine.platform.migrate     # idempotent; safe to re-run
```

`0190` is additive only — two nullable columns and an index. No backfill, no rewrite, no lock on a
hot path. `0189` and `0190` are independent of each other in schema terms but `0190` is the one the
product reads, so if you apply only one, apply `0190`.

### ⛔ One thing in `0190` you should know about before you read `0189`

`0190`'s header carries an **append-only correction to `0189`'s header**, because a migration's
checksum is its immutability and `0189` cannot be edited. `0189` claims the lane is inside
`decision_hash`. **It is not, and it should never have been** — `output_lane.route()` is a pure
function of `outcome`, `confidence_bp` and the conflict flag, all already in the hash, so the lane
adds zero information to a decision's identity. It was removed from `contracts`, `audit` and
`store` after it broke four replay tests. If you read `0189` alone you will read a false claim.

### Verify it worked

```sql
set transaction read only;
select column_name from information_schema.columns
 where table_name = 'cards' and column_name in ('output_lane','lane_reason');
```

Then, from the repo:

```bash
.venv/bin/python -c "
import os; from genios_engine.platform.db import get_engine
from genios_engine.platform.receipts import evaluate
rows = evaluate(get_engine(os.environ['GENIOS_DATABASE_URL']), None)
print([r['status'] for r in rows if 'lane' in r['claim']])"
```

The L5 receipt *"every delivered card carries a lane, or is labelled unrouted"* is currently the
suite's **one ERROR**. After `0190` it becomes a PASS or a FAIL — either is progress; an ERROR means
the question could not be asked at all.

---

# H2 · 🔴 The OCR stack — 872 attachments are unreadable

### What is wrong

`capture/documents/tesseract.tesseract_available()` requires **two** things and both are missing:

1. the Tesseract **binary** in the running image (apt)
2. the Python **bindings** — `pytesseract` and `Pillow` — which are in **no requirements file**

So the probe answers False, `make_ocr` returns `None`, and every scanned attachment parks unread.
Measured: **872** `document_jobs` at `unsupported` / `fetch_failed`, and **0** rows that ever
carried an engine.

### ⛔ Why both, together, and in that order

This exact half-fix already shipped once. `tesseract.py:26`, in its own words:

> *"the deploy image gained the apt packages while `pytesseract` and `Pillow` were in no
> requirements file, so the binary probe said yes, an engine was wired, and every scanned document
> came back `ocr_failed: ModuleNotFoundError`."*

The probe now checks the bindings too, so a repeat of that is **safe** — it answers False instead of
wiring a broken engine. But it also means **adding only the apt package changes nothing.**

### Do this

1. `pytesseract` and `Pillow` into the requirements file the image builds from
2. `tesseract-ocr` (and the `eng` language data) into the image via apt
3. Confirm DO App Platform is building from the **Dockerfile at the repo root** — `STEP-08` §2 has
   the exact console path: Settings → Source (branch + source directory), then Activity → last
   deployment → build log, checking `Dockerfile` vs `Buildpack` and the **date**
4. `enable_ocr` is already correct and has been since 10 September. Do not change it.

### Verify it worked

```bash
.venv/bin/python -c "
from genios_engine.capture.documents.tesseract import tesseract_available
print('available:', tesseract_available())"
```

Must print `True` **in the deployed image**, not on a laptop. Then a scanned PDF arriving should
produce `document_jobs.ocr_engine = 'tesseract-eng'` and `ocr_pages > 0`.

### What is already done on our side

`tests/capture/documents/test_ocr_enablement.py` — 19 passing. The test used to fail on any machine
without `pytesseract`, because it stubbed only the binary half. That is fixed, and three new tests
now cover the bindings half, which had **zero** coverage before. Full audit:
`layer-1-enterprise-signals/11-AUDIT-E-the-test-that-measured-the-host.md`.

⛔ **We deliberately did NOT add the bindings to requirements ourselves.** That would have made our
test pass by changing your deploy image, and image size is your call. A test should never be the
reason a dependency enters an image.

---

# H3 · 🟠 Widen the pilot backfill window: 60 → 365 days

### What is wrong

The pilot connection fetches **60 days**. Anything older exists as a `"message 1 of 1"` extraction —
a twelve-message thread reads to the model as a single isolated note.

Two of the five benchmark prompts ask beyond that window:

| Prompt | Horizon | Status today |
|---|---|---|
| P3 | 6 months | ⛔ **structurally unanswerable** — the mail was never fetched |
| P4 | 12 months | ⛔ same |

These are not *unproven*, they are **impossible**, and no model or prompt change moves them.

### Do this

Widen the pilot connection's backfill window **60 → 365**.

⛔ **Prerequisite, already satisfied:** migration `0184_graph_recorded_at.sql` is applied. It is what
stops a widened window from backdating a year of edges into the as-of history and silently
rewriting *what we knew and when*. Do not widen the window on an environment where `0184` has not
run. Full detail: `layer-1-enterprise-signals/STEP-09-PENDING-HARSH-backfill.md`.

---

# H4 · 🟠 A writer for `deal.status` — the largest single unblock in the product

### What is wrong

`deal.status` has **3 rows** across 293 candidate nodes. It has no real writer, and it is upstream
of a chain that goes quiet without one error anywhere:

```
deal.status has no writer
   -> core.relationship NEVER completes (708 insufficient_context, 221 skipped)
      -> core.impact completes and publishes nothing — 100% silent, 1,973 completions
         -> core.tradeoff's benefit axis has no prior
            -> tradeoff.cost_vs_benefit has fired 0 times in 1,200 production rows
```

Every unit in that chain reports `completed`. Nothing logs an error. The test for the cost axis is
**green** — on a prior the test supplies itself.

### Why it is yours and not ours

The fix is a **CRM connector** writing deal state into `graph_facts`. Four of the 14 unwritten fact
paths share this root. Nothing in this repo can invent the data.

### What is already done on our side

`reason/unit_health.DECLARED_SILENT` declares both silent units with the reason, the mover (**you**)
and the measured share, and `reason/unit_health.DECLARED_UNWRITTEN` declares all 14 unwritten paths
across 5 movers. Two receipts read those declarations, so the claim being enforced is *"every silent
unit is a **declared** one"* — true today, false the moment it gets worse. When `deal.status` gains
a writer, `undeclared_silent()` / `written_after_all()` will report that the declarations are now
stale, which is the signal to delete them.

### Verify it worked

```sql
set transaction read only;
select count(*) from graph_facts where field = 'deal.status';
```

Then the L2 receipt *"every silent unit is a declared one"* should start reporting drift.

---

# H5 · 🟡 An approval-workflow source — six more unwritten fact paths

Six of the 14 declared-unwritten fact paths bind to approval state that no system in the product
writes. Same mechanism as H4, lower urgency, and the units that read them are correctly quiet about
it rather than fabricating a default.

The full list with the unit roles that bind each path is in
`reason/unit_health.DECLARED_UNWRITTEN` — it is the authoritative list, and
`scripts/l2_fact_writers.py` is the read-only census that produced it.

---

# Summary — what changes when each lands

| | Item | Unblocks |
|---|---|---|
| 🔴 | **H1** `0186`–`0190` | card writes stop failing; 5 built steps start being read; L5 ERROR becomes a real answer |
| 🔴 | **H2** OCR stack | 872 attachments become readable; L1 receipt can go green |
| 🟠 | **H3** window 60→365 | benchmark prompts P3 and P4 become answerable at all |
| 🟠 | **H4** `deal.status` writer | `core.relationship` → `core.impact` → `cost_vs_benefit`, a four-deep chain |
| 🟡 | **H5** approval source | 6 fact paths, 2 units |

**Not on this list, because they are Rohit's:** the Anthropic spend limit (`STEP-04`), roster
activation (ALARM A2), the Slack channel, the consent-state decision, and whether the 97 `draft`
objects should gate.

**Nothing in `genios-brain` is waiting on a decision from you.** The full suite is 14,534 passed,
0 failed, and 21 of 29 production receipts pass. The 7 FAIL + 1 ERROR are exactly the items on this
page and Rohit's list — every one a true statement about a real gap, none a mis-asked question.
