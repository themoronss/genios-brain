# Layer 2 — Context Intelligence

**Last updated:** 6 August 2026
**Branch:** `harsh/mvp`
**Tests:** 659 passing (Layer 2 added 192 of them)
**Status:** feature-complete and green in tests — **NOT yet running against a real database**

**The one-line summary for a CTO:** every planned piece of Layer 2 is built and tested,
and none of its SQL has ever executed. Part 5 is the action list. Item 1 is the only thing
standing between "written" and "working."

Layer 2 is where reality becomes context. Layer 1 collects what arrived. Layer 2 answers
one question and refuses every other:

> **"What is true right now?"**

Not what should happen. Not what's best practice. Not what to recommend. Only what
currently exists.

This file is written so a CTO can pick it up, act on it, and make the layer live.
**Start at Part 5 if you want the action list.**

---

## Part 1 — What already existed (and was good)

Layer 2 was not empty. A lot of the hard, correct work was already done:

| What | Where |
|---|---|
| **The graph itself** — entities, facts, relationships, observations | `context/graph_store.py` |
| **Every fact carries evidence** — traces back to the exact email and sentence | `graph_source_refs` table |
| **Facts are versioned** — history is never overwritten | `graph_facts.valid_from/valid_to` |
| **Conflicts are recorded, not silently resolved** | `discrepancies` table |
| **Attention scoring** — "look here first", 0–100 per entity | `context/attention.py` |
| **Trust levels on facts** — a system-of-record beats a guess | `authority_rank` |
| **Freshness decided before authority** — old data can't pin a field | `graph_store.fact_write_action` |

**The most important thing that was already right:** the graph stores **facts, not
documents.** It holds *"Acme is waiting, 3 days"* — not the email. The email is evidence.

### What was missing

| Missing | Consequence |
|---|---|
| Entity resolution beyond exact match | "Acme" in an email never reached the `acme.io` entity |
| Any use of company knowledge | Your own policies and projects sat in the graph, connected to nothing |
| **Correlation Engine — zero code, searched the whole repo** | Four systems reporting one reality stayed four unrelated events |
| Situations | Nothing existed for reasoning to consume except raw graph |
| Any maintenance at all | Nothing ever checked whether the graph was still trustworthy |
| Projections | No way to see "the Sales view" |

---

## Part 2 — What we built

Six steps. Each shipped with tests and a self-review pass that found real bugs — the
review pass found more than the building did.

### Step 1 — Entity Resolution
**`context/identity.py`, `context/merge.py`, migration `0036`**

Before: two entities were the same only if their identity strings matched **letter for
letter.**

Now every entity has a list of names it can be found by:

```
Acme company
  ├── acme.io                (its domain)
  ├── "acme"                 (from the domain)
  └── "acme technologies"    (from its name)
```

**The rule we did not break** — already written into the codebase:

> Exact match is the only automatic merge. Name similarity finds candidates; it never has
> the authority to merge.

There is **no** "87% similar, close enough." Everything is exact string matching. The
fuzziness is only in how a name gets *cleaned* (dropping "Inc.", lowercasing) — never in
how two names get *compared*. **Because two colleagues really do share a name.**

When two entities claim the same name, the system **asks a human**:

```
GET  /api/org/{org}/identity/proposals
POST /api/org/{org}/identity/proposals/{id}/merge
POST /api/org/{org}/identity/proposals/{id}/reject      ← never asks again
GET  /api/org/{org}/identity/merges
POST /api/org/{org}/identity/merges/{id}/reverse        ← undo
```

Merging is careful: everything is snapshotted first, the old entity is **closed not
deleted** (its ID may already sit in a notification sent last week), and two silent
corruptions are repaired — duplicate values for one field, and "Acme is connected to
Acme."

### Step 2 — Correlation Engine
**`context/correlation.py`, migration `0037`**

The thing you called the moat. It had **zero lines of code**.

Slack says *"need pricing approval."* Email says *"customer is waiting."* Calendar has
*"Pricing Review tomorrow."* CRM says *Enterprise deal.* Before: four unrelated events.
Now: **one situation with four pieces of evidence.**

**The governing rule:**

> **When unsure, leave things apart.**

The two mistakes are not equal. Splitting one situation gives you a duplicate card —
annoying. **Merging two situations builds a monster and reasons about it at full
confidence** — two customers' problems fused into one recommendation.

Anchored on **(who it's about, which domain)**. Email threads act as glue, so a bare
*"sounds good, thanks"* inherits its conversation instead of becoming an island.

### Step 3 — Situation Engine
**`context/situations.py`, migration `0038`**

The object reasoning actually consumes. Reasoning should never wake up and ask for the
graph — it should ask for the **active situations**.

```
GET  /api/org/{org}/situations
GET  /api/org/{org}/situations/{id}          ← with all its evidence
POST /api/org/{org}/situations/{id}/resolve
POST /api/org/{org}/situations/backfill      ← see Part 5
```

**Confidence is a vector, and `overall` is the MINIMUM:**

| Dimension | Question |
|---|---|
| evidence | how much independent material backs it |
| freshness | how current that material is |
| consistency | do the sources contradict each other |
| identity | are we sure *who* it's about |

Minimum, never average. **Perfect evidence about an entity we can't identify isn't "60%
confident" — it's unusable.** An average would report it as fine.

*Coverage* (completeness) sits **outside** `overall` deliberately: not knowing a deal's
close date doesn't make the stage we *do* know less true.

**Two kinds of "done":**
- **Closed by data** (CRM says closed-won) → recomputed every refresh. If the stage moves
  back, it **un-resolves by itself.**
- **Closed by a person** → sticks until new evidence arrives, then reopens. Marking
  something handled is a statement about the past, not a promise about the future.

### Step 4 — Graph Maintenance
**`context/health.py`, migration `0039`**

Steps 1–3 **build** the graph. Nothing until now **kept** it.

```
GET /api/org/{org}/graph/health
GET /api/org/{org}/graph/health/history
```

Eight integrity checks, each targeting a way *this* graph actually breaks: broken edges,
self-edges, orphan facts, duplicate active facts, facts without evidence, orphan entities,
aliases pointing at closed entities, situations anchored on closed entities.

Runs automatically on the scheduler sweep (hourly-scale, not per event).

### Step 5 — Projections + Domain Registry
**`context/projections.py`, `context/domain_spec.py`, migration `0040`**

```
GET /api/org/{org}/projections                    ← lenses this tenant has
GET /api/org/{org}/projections/{domain}
GET /api/org/{org}/projections/_/unclassified     ← what falls through every lens
```

**Because domains will grow, a projection is a derived query — not a stored table.**
Nothing in the module names a domain. Lenses are discovered from the data, so adding
"engineering" upstream makes its lens exist immediately with **zero Layer 2 changes.**

A **domain registry** (`domain_spec.py`) holds what a domain *means*, with a `register()`
seam so Layer 3 takes over without Layer 2 being edited. An unregistered domain isn't an
error — it gets a working generic spec.

---

### Step 6 — Canon Correlation
**`context/canon.py`, `capture/internal_knowledge.py` — no migration needed**

The seam between the Layer 1 work and Layer 2. Layer 1 gave company knowledge the
**highest authority in the system** (rank 4, above any connected tool). Layer 2 then did
almost nothing with it:

```
you write a refund policy
   → the author is an internal seat
   → sender_node = the AUTHOR's person node
   → every extracted fact attaches to the author
   → internal nodes are excluded from correlation
   → the policy reaches NO situation
```

**Your refund policy became facts about you.** The most authoritative material in the
system was also the least connected.

Now a canon document is its own entity — `internal:policy:refund-policy` — and its facts
belong to *it*.

**The decision that mattered most: anchoring vs reference.**

| Class | Kinds | Can other signals group under it? |
|---|---|---|
| **Anchoring** | `project` | Yes — a Slack thread, a commit and a meeting about Project Phoenix are one situation |
| **Reference** | policy, sop, pricing, product, goal, kpi, org_structure, employee_profile, asset, wiki | No — a refund policy is true continuously; it is not something *happening* |

The line is not importance — pricing may matter more than any single project. It is
whether other events **cluster** around it. Letting every policy open its own situation
would bury the handful that need attention under a filing cabinet.

`task` is deliberately not anchoring yet: one situation per to-do item would swamp the
same list, and nothing downstream ranks at that granularity.

**Mentions resolve by name, not by type — and that was forced, not chosen.** The
extraction prompt never asks for a "project" entity type and `_NODE_TYPES` has no entry
for one, so a type-based lookup would have silently never fired.

---

## Part 3 — Mistakes we found and fixed

These were all real. Every one would have shipped silently.

### Found while building

| # | Bug | Why it mattered |
|---|---|---|
| 1 | **Every outbound email anchored on *us*** | Sending mail creates a company entity from your *own* domain — every outbound message would file into one giant situation containing your entire company |
| 2 | **CRM and calendar never correlated at all** | Correlation only ran in the email path. **The headline example would have failed** — Slack and email would group, the CRM deal and calendar invite would sit outside |
| 3 | Same person anchored differently per source | Email from `john@acme.io` → Acme. Calendar with `john@acme.io` → John. One deal, two situations that never meet |
| 4 | Merging two customers would **crash** | Their situations collide on a uniqueness rule; Postgres aborts the whole merge |
| 5 | Newsletters joined live deals | A marketing blast naming your contact became evidence in their deal |
| 6 | **Archived situations could never reopen** | Archiving nulled the timestamp the reopen check needs. The logic said "reopens on new evidence" and passed its test; the SQL made it impossible |
| 7 | Missing-info was **always right, never useful** | Checked facts on the anchor entity — but *"whose turn it is"* lives on **people**, so every company situation reported it missing forever |
| 8 | The health alarm fired on **healthy** systems | Measured correlation reach against *every* event, but a newsletter correctly reaches no situation. Normal marketing volume → 10% score → **an alarm people switch off** |
| 9 | Maintenance could become an outage | One database round-trip per entity — 50,000 round-trips in one transaction on a large tenant |
| 10 | **Three definitions of "in the lens"** in one 197-line file | A participant in the Sales lens was *simultaneously* reported as belonging to no lens at all |

### Found by auditing our own claims

| # | Problem |
|---|---|
| 11 | **The code promised an undo it didn't have.** `merge.py` documented `reverse_merge` in its own docstring. That function did not exist. Snapshots were taken and nothing could read them |
| 12 | **None of Steps 1–3 worked on data you already have.** Everything only fired on *new* traffic. A tenant with months of history would see nothing — the features looking broken while being correctly implemented |
| 13 | **We put domain knowledge inside Layer 2.** Step 3 shipped `("company","sales") → "opportunity"` in `situations.py`. Every new domain would have required editing Layer 2 |
| 14 | **A test that checked everywhere the problem wasn't.** It asserted "Layer 2 holds no domain knowledge" while *excluding* the one file that names domains |
| 15 | **No index on `graph_facts.created_by_event_id`** — verified, it exists in no migration. Fine when the join ran once per drain; not fine now it runs per API request |

### Found in Step 6 — three that would have made the feature inert

| # | Bug | Why it mattered |
|---|---|---|
| 16 | **Mention resolution couldn't have worked at all.** The plan was to find a project by entity *type*. The extraction prompt never asks for a "project" type and `_NODE_TYPES` has no entry for one | The lookup would have **silently never fired.** Built, green, doing nothing. Now resolves by name |
| 17 | **The resolver returned only an ID — correlation anchors on *type*.** So a Slack message naming "Project Phoenix" would resolve perfectly and then correlate under **nothing** | Same failure one level down: the feature looks wired and is inert |
| 18 | **The code contradicted its own comment.** It documented "a company mention resolves to the company first" and then checked canon first | A project named "Acme" would have shadowed the customer Acme |

Plus one prevented before it shipped: a 30-chunk pricing PDF would have created **thirty
separate "Pricing" entities**, each holding a slice of one document. Keyed on the file now.

### The pattern worth noticing

Bugs 2, 16 and 17 are the same shape: **code that is written, tested, green — and does
nothing.** Not a crash, not a wrong answer. Silence. That is the failure mode this
codebase is most exposed to, because the tests can't reach a database, and it is the
reason Part 5 item 1 is not optional.

---

## Part 4 — What is still wrong or unfinished

**Read this section before deploying anything.**

### 🔴 BLOCKING — the SQL has never executed

There is **no database in the test suite.** 637 tests run in 2.5 seconds because nothing
connects. That is worth keeping, but it means a whole class of bug is invisible.

**Six migrations have never been run against Postgres:**

```
0035_l1_internal_knowledge.sql      (Layer 1)
0036_l2_entity_resolution.sql       graph_aliases
0037_l2_correlation.sql             context_correlations + members
0038_l2_situations.sql              context_situations
0039_l2_graph_health.sql            context_node_lifecycle + graph_health
0040_l2_projection_reads.sql        the index projections depend on
```

*(Step 6 needed no migration — canon reuses `graph_nodes` and `graph_aliases`.)*

What **is** verified: every table the code queries exists in a migration
(`tests/test_sql_references_real_tables.py`). Every query was reviewed column-by-column
against the schema, using only SQL patterns already proven elsewhere in this repo.

What is **not** verified: **column names, types, and semantics.** If something is wrong,
it is here — not in the logic.

### 🟠 Layer 1 bugs still feeding bad data into Layer 2

From `Layer 1.md`, still open. These matter *more* now, because Layer 2 builds on them:

1. **Uploads over ~50 pages are silently truncated** and report `"indexed"`
2. **Text is cut at arbitrary 2000-character points**, mid-sentence — facts split across a
   boundary are lost
3. **Scanned PDFs work by email but not by upload** (upload path never wired to OCR)
4. Uploading the same file twice creates two copies
5. Written knowledge can't be listed or deleted

> A situation is only as good as its evidence. Fix 1 and 2 before trusting confidence
> scores on any document-heavy tenant.

### 🟡 Known limitations — decisions, not oversights

**Two separate deals with the same company, with no CRM connected, become one situation.**
Nothing available can tell them apart — same people, same domain, same weeks. Splitting
them by guessing at wording is exactly the over-merging we refuse. Connect a CRM and they
separate properly. There's a test pinning both halves.

**Internal-only situations don't correlate yet.** "Engineering release blocked", "Hiring
pipeline stalled" need project/candidate entities that nothing currently produces.
Anchoring them on our own company would be wrong.

### 🟡 Test-quality weakness — worth a junior engineer's week

Many Layer 2 tests assert on **source text** (`assert "not exists" in source`) rather than
behaviour. They pin the prose. Two of them broke during a refactor for exactly that
reason, and the multi-agent review flagged it as systemic.

The cause is the no-database constraint. **The fix is a test Postgres** (see Part 5), which
would let the SQL-dependent logic be tested behaviourally instead of textually.

### 🟡 Performance items, not yet a problem

| Item | Detail |
|---|---|
| `refresh_situations` | Rebuilds the whole org every L2 drain. Same shape as the existing attention refresh. Fine now; needs incremental scoping at scale |
| `compute_health` | ~17 full-table scans per org, per sweep. Acceptable at hourly cadence; not at minute cadence |
| `boundary_edges` | Passes a node-id array to Postgres; capped at 500 members |

### ⚪ Two recommendations deliberately NOT acted on — CTO's call

1. **Drop the unused `graph_facts.visibility_scope` column.** Verified: zero readers,
   zero writers repo-wide. It sits inside the versioned fact row, so a future predicate on
   it would silently gate evaluation input. *Destructive schema change — not done
   unilaterally.*
2. **Delete `_DEAL_REASON_CODES` in `api/intelligence_routes.py`.** Verified byte-identical
   to the sales pack's `signal_vocab`. A second hand-copy of pack data. *Layer 4 concern,
   outside this scope.*

---

## Part 5 — What to do, in order

### 1. Stand up a database and run the migrations ← **do this first**

```bash
export DATABASE_URL=postgres://...
python -m genios_engine.platform.migrate      # or just boot the app — it migrates on start
```

The app migrates at boot and **crashes loudly** if a migration fails, by design. Expect
the first run to surface anything wrong. **Everything else waits on this.**

### 2. Add a test database to CI

This is the highest-leverage engineering task in the whole layer. It converts ~40 brittle
source-text tests into real behavioural ones, and closes the only remaining verification
gap.

Suggested: `testing.postgresql` or a docker-compose Postgres, with a marked test session
that runs migrations and exercises the SQL paths.

### 3. Backfill every existing tenant

```
POST /api/org/{org}/situations/backfill
POST /api/org/{org}/situations/backfill?limit=5000     # large tenants, in passes
```

**Without this, Layer 2 does nothing on data you already have.** Aliases are claimed when
an entity is created and correlation runs when an event arrives — both only fire on *new*
traffic.

Safe to re-run. Runs aliases → correlations → situations, in that order (the only order
that works).

### 4. Put the identity queue in front of a human

`GET /api/org/{org}/identity/proposals` will have entries after the backfill. **Every
unresolved duplicate lowers the confidence of every situation about that entity** — that
connection is deliberate. Unreviewed proposals are a measurable defect, not a quiet queue.

### 5. Watch graph health for a week

`GET /api/org/{org}/graph/health`. Look for:

- `correlation_reach` — the single best signal that Layer 2 has quietly stopped working
- `identity` — unresolved duplicates piling up
- `evidence` — facts with no source reference (should be zero)

The sweep logs a warning for any org scoring below 80.

### 6. Fix the Layer 1 upload bugs

Especially silent truncation and blind chunking. Everything above inherits their quality.

---

## Part 6 — Rules a future engineer must not break

These are enforced by tests. If one fails, **the change is wrong, not the test.**

### 1. A label may narrow retrieval. It may never narrow evaluation.

This appears **three times** in Layer 2 — attention scores, lifecycle states, and now
projections — and it's the same trap each time:

> If a quiet entity stopped being evaluated, it would produce no signals, so it would stay
> quiet, so it would stay dormant. **The customer who went silent — exactly the one worth
> noticing — is the one the system would go permanently blind to**, with nothing in the
> logs.

Enforced: `tests/test_attention.py`, `tests/test_graph_health.py`,
`tests/test_projections.py`. No module under `reason/` may read attention, lifecycle, or
projections.

### 2. Absence is never negative evidence.

An entity with no dated evidence is not stale — we can't tell. A new domain with no
expected fields is 100% covered, not 0% known. An empty graph scores 100 "not measured,"
never 0% healthy. **A health page that calls fresh accounts broken is one nobody reads.**

### 3. Exact match is the only automatic merge.

No edit distance. No embeddings. No "similar enough." A shared name is a **proposal**, and
a human decides.

### 4. Nothing repairs itself.

Every integrity check is read-only. An auto-fix that runs unattended turns a small
inconsistency into silent data loss: it deletes the rows it decided were wrong, and nobody
finds out until a decision can't be explained.

### 5. Nothing is ever deleted — only archived.

Volume is controlled at Layer 1, where the gate drops noise *before* it becomes an entity.
Anything in the graph has already passed that bar. **An old customer is a dormant
relationship, not a mistake to erase.**

### 6. This layer does not decide.

No priority. No risk score. No recommendation. Those belong to Layer 4. Building them here
would give **two layers an opinion about the same thing and no way to tell which one was
wrong.**

---

## Part 7 — Where we disagreed with the architecture spec

Documented so they're decisions, not drift.

| Spec says | We did | Why |
|---|---|---|
| Risk Detector + Opportunity Detector live in Layer 2 | Kept in the packs (Layer 4) | The spec also says context never decides. Two layers detecting risk = no way to tell which was wrong |
| A Pruning Engine, so the graph "never grows forever" | Pruning = **archival**, never deletion | Volume is already controlled at Layer 1. Deleting later destroys evidence needed to explain a decision the system already made |
| `Email`, `Document`, `Meeting` are Entities | They stay **evidence** | The spec also says "documents disappear, facts remain." Both can't be true; the code picked the better one |
| Separate Sales / HR / Engineering graphs | One graph, many derived lenses | Separate graphs mean the same customer exists twice, and no way to say which is right when they disagree |

---

## Summary

| Capability | Status |
|---|---|
| Entity resolution ("Acme" = "Acme Inc." = acme.io) | ✅ Built, human-reviewed, reversible |
| Correlation (4 systems → 1 situation) | ✅ Built, both lanes |
| Situations with confidence vectors | ✅ Built, lifecycle + reopening |
| Graph health & maintenance | ✅ Built, on the scheduler |
| Projections (Sales / Support / any future domain) | ✅ Built, zero-code for new domains |
| Company knowledge participates in context | ✅ Built (Step 6) |
| Works on existing tenant data | ⚠️ Needs the backfill endpoint run once |
| **Ever executed against Postgres** | ❌ **Not once. Do this first.** |
| Test suite exercises real SQL | ❌ Needs a test database |
| Layer 1 evidence quality | ⚠️ 5 known bugs still open |

**Layer 2 is feature-complete.** Nothing is half-built and nothing is planned-but-missing.
What remains is proving it, and that is one afternoon of work that must happen before
anyone trusts a number this layer produces.

---

## Appendix — the 60-second version for a CTO

**What Layer 2 does now that it didn't before:**
Four tools reporting one reality become one situation, with a confidence score you can
argue with, anchored on an entity that means the same thing however it was spelled.

**What it will not do, on purpose:**
Decide anything. No priority, no risk, no recommendation. Those are Layer 4's, and
building them here would give two layers an opinion about the same thing with no way to
tell which one was wrong.

**The one number to watch after go-live:**
`correlation_reach` in `GET /graph/health`. It is the fraction of knowledge-bearing events
that reached a situation. If it drops, Layer 2 has quietly stopped working — and quietly
is how this layer fails.

**The biggest risk:**
Not that something crashes. That something is written, tested, green, and does nothing.
Three of the eighteen bugs found were exactly that. The test suite cannot reach a
database, so it cannot catch the fourth.

**Where to spend a junior engineer's first week:**
Part 5, item 2 — a test Postgres in CI. It converts ~40 brittle source-text assertions
into real behavioural tests and closes the only remaining verification gap in one move.
