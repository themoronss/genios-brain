# HANDOFF · Harsh (CTO) — five items, in the order that unblocks the most

> **Written:** 2026-10-01 · **by:** Claude, from the YCW27 programme
> **Nothing here needs a code change in `genios-brain`.** Every item is a deployment, a dependency
> or a connector. The code side of all five is built, tested and merged into the working tree.
> **Read H1 first.** It is the only item that is actively breaking a write path.

---

## ⛔ 2026-10-01 · READ THIS BEFORE H1 AND H2 — they will not produce a card on their own

Measured the same day: **L1, L2 and L3 wrote rows on 2026-09-30. L4 and L5 stopped on 09-25.**

The cause is not a deploy and not a migration. `GENIOS_L4_LLM_DECISION_MAKER = true` for every
org, the Anthropic spend limit has refused every call since 2026-09-25 11:09 UTC, and
`reason/llm_decision_maker.py:20` says *"**Failure is DEFER, never the formula**"* — by design,
with a stated reason. So every decision defers, nothing is selected, no signal is emitted, and the
card pipeline is stopped.

    the 8,044 candidates on the 2,681 runs since 09-29:
      formula_utility  5,469   ✅ the deterministic scorer is HEALTHY
      llm_utility          0   ⛔
      final_utility_bp     0   ⛔      outcome_kind: decision ZERO

⛔ **H1 and H2 are still worth doing and still unblock what their briefs say.** But neither
produces a single card until **DECISION #5** is answered (`02-DECISIONS.md`) — raise the limit,
flip the switch, or build the third path. That is Rohit's, it is one line, and it is not yours.

**Full trace:** `layer-4-executive/05-RECROSSCHECK-why-the-queue-is-empty.md`.

---

## 2026-10-01 · H1 RE-VERIFIED AGAINST PRODUCTION

Measured read-only, so this is not a reconstruction from the branch:

```
select version from schema_migrations order by 1 desc limit 1;
  -> 0185_capture_policy_teams_default.sql     applied 2026-09-26 08:10:36 UTC

select column_name from information_schema.columns
 where table_name='cards' and column_name='lane';
  -> ⛔ ZERO ROWS — the column the card writer names DOES NOT EXIST
```

`0186`–`0190` have still never run, five days on. ⛔ **`version` holds the full filename, not the
number**, which is worth knowing before you write the check query.

**The full end-to-end picture for L1, L2 and L3 — every number measured the same day — is
`17-THE-THREE-LAYERS-end-to-end.md`. PART 7 of that document is this handoff expanded: what each
item unblocks, how to know it worked, and the four things not to do.**

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

---
---

# ⛔ H6 · 🟠 ADDED 2026-10-01 · run `tests/test_delivery_spine.py` where a database exists

**Not a deployment. A test run.** It takes one command and needs nothing built.

```
.venv/bin/pytest tests/test_delivery_spine.py -q
```

## What it is

L5 `STEP-06` gave `deliver/spine.recover_expired_claims` its **first tests ever**. That function is
the ambiguity-marker of the v2 delivery control plane:

> *"An expired worker may have POSTed to a provider before dying; **we must never silently retry over
> that ambiguity.**"*

Four new tests cover it: an expired claim's unsettled attempt becomes `unknown`; a **live** claim's
attempt is untouched; a **settled** attempt is never rewritten (`delivered` must not become
`unknown`); and an attempt under a stale fence is *not* recovered — which pins a known blind spot
rather than hiding it.

## ⛔ Why I cannot run them

The file proves the spine against **real PostgreSQL**, deliberately: its SQL uses
`for update skip locked` and a partial-index `on conflict`, and *a fake cannot model that*. It runs
inside one transaction and rolls back, leaving the database byte-identical — and it uses the
**scratch** database when one is set, never the configured production one
(`tests/conftest.py::live_test_database_url` enforces the ordering).

**No database is configured in this checkout.** Result here:

```
7 skipped in 0.15s       # all 7 — including the 3 that predate this step
```

Collection succeeded, so the imports and the syntax are sound. ⛔ **The behaviour is unverified, and
a skip is not a pass.** Five database-free tests in
`tests/deliver/test_the_spine_cutover_cannot_be_taken_unguarded.py` assert the recovery's SQL
contract structurally, which is weaker evidence than behaviour and is not zero.

## What a failure would mean

| Outcome | Reading |
|---|---|
| 7 passed | ⛔ the best case, and the one to report. The v2 claiming tier is now behaviourally proven |
| any failure | ⛔ **a real finding** — the recovery has never run, so a failure is a defect in code nobody has executed, not a regression. Send the output; it goes into `layer-5-delivery/03-FINDINGS.md` |
| still skipped | the scratch database is not reachable. ⛔ **Do not point it at production to make it run** — it writes, and the rollback is a property of the test, not a promise to the database |

## Why it is worth your five minutes

The v2 control plane is **un-cut-over**: nothing in production calls any of it, which is why none of
this is urgent. But `outbox.py:838` records the hazard waiting at the other end — *"the moment it
does, both workers could select the same one and double-send"* — and the day somebody takes that
cutover, these four tests are the only thing that has ever exercised the step that prevents it.

⛔ **Everything else on this page changes what production does. This one only changes what we know.**


---
---

# ⛔ H7 · 🟠 ADDED 2026-10-02 · 27 learning tests have never run — and they are the two that matter

**Same shape as `H6`, different layer.** Five minutes with a database, and it answers the one
question the L6 pass could not.

## What it is

```
$ .venv/bin/pytest tests/feedback -q -rs
60 passed, 27 skipped

14  tests/feedback/test_org_brain_filled_through_the_routes.py                    ENTIRELY skipped
13  tests/feedback/test_behavior_and_adaptive_brains_filled_through_the_paths.py   ENTIRELY skipped
--
    every one: "GENIOS_TEST_DATABASE_URL not set — J4's org row / brain rows need real Postgres"
```

⛔ **Read the two filenames.** *"filled through the routes"* and *"filled through the paths"* — these
are the tests that prove the **brains actually get filled end to end**. The 60 that pass are the
deterministic ones: maps, taxonomies, attribution routing, property guards.

## ⛔ Why this matters more than a skip count

The L6 re-crosscheck measured that `feedback/` is guarded by **four receipts and all four are
presence checks** — *"has the learning engine executed"*, *"has calibration executed"*. Every one is
satisfied by a single successful tick. **Nothing in production asks whether what the loop wrote is
correct.**

So the only evidence that a brain value arrives intact is these 27 tests, **and they do not run.**

> ⛔ **A skip is not a pass.** Two entire files of end-to-end evidence are currently reported as
> neither passing nor failing, and no document in `layer-6-learning/` had mentioned them.

## What to run

```bash
export GENIOS_TEST_DATABASE_URL='postgres://…'        # a scratch database, not production
.venv/bin/pytest tests/feedback -q -rs
```

⛔ **`GENIOS_TEST_DATABASE_URL`, not `GENIOS_DATABASE_URL`** — the tests write. And ⛔ **do not set
`GENIOS_ALLOW_PROD_WRITE`**: that variable is named for writes because it was written for writes.

## What a failure would mean

| | |
|---|---|
| **27 passed** | the brains fill correctly end to end, and L6's missing correctness receipts are a **monitoring** gap rather than a correctness one. That is a materially different plan |
| **any failure** | a brain value does not arrive the way the deterministic tests say it should — and ⛔ **production has no receipt that would notice**, because all four are presence checks |

## Why it is worth your five minutes

It is the difference between *"the learning loop is unguarded"* and *"the learning loop is unguarded
**and** untested where it touches the database."* ⛔ **I cannot tell those apart from this
checkout**, and the plan for L6's correctness receipts (`U03`–`U05`) is shaped differently
depending on the answer.

→ `layer-6-learning/05-RECROSSCHECK-the-loop-that-runs-and-is-never-questioned.md` §6,
`03-FINDINGS.md` §F15

---
---

# H8 · 🟠 Three questions only the database can answer, and one decision that is yours

Added 2026-10-02 by the `context/` coverage audit. ⛔ **All three checks are read-only and take
about two minutes together.** The decision at the end is a product/infra call, not a code change we
should make on our own.

## What we measured, and what we could not

We measured every SQL statement in `genios_engine/` and `scripts/` — 2,867 of them — and
cross-referenced each table against every reader, every writer and all 42 receipts. ⛔ **Nine
tables are written by the product and read by nothing at all:**

```
contract_spend_attributions   context/correlation_resource.py
source_identity_map           context/graph_store.py + context/merge.py
situation_interpretations     context/interpretation_store.py
learning_metrics              feedback/publisher.py
human_events                  capture/events_store.py + deliver/actions.py
card_feedback_revisions       api/intelligence_routes.py
agent_metering                deliver/agent_api.py
delivery_rate_windows         deliver/rate_limiter.py
domain_requests               api/expertise_routes.py
```

⛔ **That is a statement about the CODE, which is all we can see from here.** Whether those tables
are large, whether they are growing, and whether anything outside this repo reads them (a dashboard,
a notebook, a cron you own) is a question about the deployment.

---

### H8.1 · How much are the nine costing, and is anything growing?

```sql
set transaction read only;

select relname as table_name,
       n_live_tup as approx_rows,
       pg_size_pretty(pg_total_relation_size(relid)) as total_size
  from pg_stat_user_tables
 where relname in ('contract_spend_attributions','source_identity_map',
                   'situation_interpretations','learning_metrics','human_events',
                   'card_feedback_revisions','agent_metering','delivery_rate_windows',
                   'domain_requests')
 order by pg_total_relation_size(relid) desc;
```

**What the answer changes.** A table with a handful of rows is a tidy-up nobody is blocked on. ⛔ One
with millions of rows and a live write path is paying storage and vacuum cost for a number no
decision has ever used — and `learning_metrics` in particular receives a row from **every** one of
the eleven weekly analysis units.

---

### H8.2 · ⛔ Two receipts have never once run against a real database

`platform/receipts.py` now has **42** claims. Two of them have never been evaluated anywhere,
because this checkout has no database configured:

```sql
set transaction read only;

-- 1 · "a deleted tenant leaves nothing behind" — asks the DEPLOYED schema whether any org-scoped
--     table outlives an erased tenant. It is the ONLY thing that can see a child table cascading
--     through a parent, which no code-level list can show.
select c.table_name
  from information_schema.columns c
  join information_schema.tables t
    on t.table_schema = c.table_schema and t.table_name = c.table_name
 where c.table_schema = 'public' and c.column_name = 'org_id'
   and t.table_type = 'BASE TABLE'
   and c.table_name not in ('llm_costs','credit_ledger','subscriptions','orgs_archive','orgs')
   and exists (select 1 from orgs_archive)          -- only meaningful once a tenant was erased
 limit 20;

-- 2 · "no live row points at a node a merge absorbed" — the new one. Expected: 0.
select count(*) from graph_facts t
  join merge_history m on m.org_id = t.org_id and m.merged_node_id = t.subject_node_id
 where not m.reversed;
```

**What the answer changes.** `merge.py`'s own comment is the claim: *"Missing one leaves rows
pointing at a closed node — invisible in the UI, still returned by any query that joins on
node_id."* ⛔ A non-zero count is live graph corruption after an entity merge, and `context/` had
**two** receipts over 50,877 lines before this one, neither about merge.

---

### H8.3 · ⛔ Is `merge_history` empty? — because that decides whether the new receipt means anything

```sql
set transaction read only;
select count(*) as merges, count(*) filter (where reversed) as reversed from merge_history;
```

**What the answer changes.** If no merge has ever run, the receipt above is **structurally green
forever** and tells nobody anything — *a gate that is always green is a gate nobody reads*. Say so
and we will gate it on the same marker pattern the learning receipts use, so it reads
*"not yet exercised"* rather than *"passing"*.

---

### H8.4 · ⛔ The decision: three tables survive a tenant `/reset`, and nothing says whether they should

`api/account_routes.py` has two declared lists — `_ORG_SCOPED_TABLES` (what `/reset` erases, 102
tables) and `RETAINED_AFTER_ERASURE` (what may outlive an erased account, 5). ⛔ **These three are
in neither:**

| table | writer | what it holds |
|---|---|---|
| `agent_metering` | `deliver/agent_api.py` | per-call metering for the Agent API |
| `delivery_rate_windows` | `deliver/rate_limiter.py` | the rate limiter's window state |
| `domain_requests` | `api/expertise_routes.py` | a tenant asking for a domain that does not exist yet |

⛔ **For account DELETION this is fine** — migration `0033`'s foreign keys take everything that
hangs off `orgs`, directly or through a parent, and we verified the four `reasoning_*` children
reach `orgs` transitively. ⛔ **For `/reset` it is a question**: that endpoint promises *"wipe this
org's learned graph + signals + cards (keeps the account, connections, tasks)"*, and whether
metering, rate windows and unfulfilled domain requests belong on the "keeps" side has never been
written down.

**Our read:** metering and rate windows probably SHOULD survive a reset (they are accounting and
abuse-control state, not tenant content), and `domain_requests` probably should too (it is a
request to us, not data about them). ⛔ **If you agree, they belong in `RETAINED_AFTER_ERASURE` with
that reasoning** — and the comment beside that list already says why it matters that the answer be
written rather than implied: *"a comment cannot be asked"*, and the loop beside it *"runs with no
try/except by design, so a name missing here leaks silently."*

### Why it is yours and not ours

⛔ We can measure which tables are in which list; we cannot decide what a tenant reset is **for**.
Moving a name into `RETAINED_AFTER_ERASURE` changes what survives a customer pressing a destructive
button in Settings, and it changes what we would tell a customer asking a data question. That is
your call and Rohit's, not a tidy-up.

→ `layer-3-context-graph/04-AUDIT-PLAN-the-worst-covered-package.md`,
`genios_engine/platform/table_coverage.py` (the measurement, with its limits declared)
