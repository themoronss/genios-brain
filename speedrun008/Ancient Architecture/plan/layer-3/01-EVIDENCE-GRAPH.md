# The Evidence Graph — what it is, and whether it is needed at all

**Read from the code, 2026-09-25** · answering: *"hum memory layer toh bana nahi rahe, hum toh
tools, resources, DB sab padh rahe hain — to iski zarurat kyun hai, ya hai bhi?"*

⛔ **That is the right question and it deserves a measured answer, not a defence.** Everything
below is read from the schema and the code. The honest verdict is in §6, and §7 says plainly what
the graph does NOT earn.

---

## 1. What it is, in one line

**Not a memory layer. A ledger of claims.**

```
a source says something     →    a CLAIM, with who said it, when, how strongly, and the quote
many sources say things     →    a RESOLVED value, with the disagreements kept
time passes                 →    the old value is CLOSED, not overwritten
```

It is not *"what we know"*. It is **"what was claimed, by whom, when, and what we concluded from
that"** — and the difference is the entire point.

---

## 2. What is actually in it — six tables, measured

| table | cols | holds |
|---|---|---|
| `graph_nodes` | 12 | the things — a person, a company, a thread, a deal. `canonical_key`, `identity_strength`, `valid_from`/`valid_to` |
| `graph_facts` | 17 | **the claims.** `field`, `value`, `authority_rank`, `confidence`, `occurred_at`, `status`, `visibility_scope`, `valid_from`/`valid_to` |
| `graph_edges` | 12 | the relationships — who works where, what blocks what |
| `graph_observations` | 11 | the things that *happened* — an email arrived, a meeting occurred |
| `graph_source_refs` | 14 | ⛔ **the receipts.** `event_id`, `source`, `source_field_path`, `evidence`, `independence_group`, `extractor_version` |
| `graph_versions` | 3 | one monotonic counter per org |

**Four more** support it: `graph_aliases` (identity), `graph_segments`, `graph_health`,
`graph_change_outbox`.

### 2.1 · The one column that explains the design

`graph_facts.fact_version_id` **and** `fact_id`. Two ids, deliberately.

* `fact_id` — *"Nitesh's title"*, the thing.
* `fact_version_id` — *"what we believed Nitesh's title was, between March and June"*.

**A fact is never updated. A new version opens and the old one closes.** Every receipt, every
citation, every decision points at a `fact_version_id` — so a claim made in March still resolves
to what March actually said, after June changed its mind.

---

## 3. Where it is built, and where it is stored

```
capture/          reads Gmail, Calendar, uploads          → a SourceEvent + a QES
   ↓  the L1→L2 seam
context/pipeline  turns the QES into nodes, facts,        → 59 modules in context/ read it
                  observations and edges
   ↓
Postgres          10 tables. Same database, same tenant boundary as everything else.
                  Every read filters on org_id; private facts are excluded at the SQL level
```

**Nothing separate. No vector store, no second database, no embedding index.** It is ordinary
relational storage with `valid_from`/`valid_to` on three tables.

**Who reads it:** `context` 59 · `reason` 24 · `api` 12 · `executive` 9 · `capture` 7 ·
`packs` 7 · `deliver` 4 · `feedback` 1.

---

## 4. How it works — four rules, all in the code

### 4.1 · A write is a DECISION, not an assignment

`graph_store.fact_write_action` is a pure function returning one of five answers:

| answer | when |
|---|---|
| `insert` | nothing held |
| `noop` | the same value again |
| `historical` | ⛔ the new claim is **older** than the held one — recorded, never overwrites |
| `discrepancy` | ⛔ a **lower-authority** source disagrees — flagged, held value kept |
| `supersede` | a newer, at-least-equal-authority claim wins |

> *"The load-bearing rule is `historical`: a fact whose `occurred_at` is OLDER than the held row's
> may never overwrite current state. Without this, any backfill replays a 2024
> `thread.ball_in_court=us` over today's `them` and the correct value is already stamped
> superseded — **an unrecoverable corruption.**"*

### 4.2 · Sources are RANKED, and the ranking is doctrine

Seven provenance classes, rank 0–5: company canon (5) → signed document → attachment →
structured source → email prose → chat aside → inferred / unattributed (0).

**A signed contract and an email guessing about it are not the same claim**, and a store that
overwrote one with the other would have no way to say so.

### 4.3 · Agreement is counted, not assumed

`graph_source_refs.independence_group` — `"source:gmail"` or `"unattributed"` — plus `src_count`.

**Three emails from one thread are not three sources.** Without this, a value repeated in a quoted
reply chain looks independently corroborated.

### 4.4 · Time is a predicate, not a timestamp

```
as at T   →  valid_from <= T and (valid_to is null or valid_to > T)
live      →  valid_to is null
```

Half-open, so a row closed at noon and its successor opened at noon never both match noon.

---

## 5. ⛔ THE REAL QUESTION — why not just read Gmail, the DB and the tools each time?

**Because four of the six things the product does cannot be answered by a source read, and one of
them is not a design choice — it is a fact about retention.**

### 5.1 · ⛔ The source is gone. Measured.

```python
_EMITTED_PAYLOAD_TTL_DAYS = 30        # capture/pipeline.py
```

**The raw body is deleted after 30 days.** A fact extracted in March cannot be re-derived in June
— there is nothing left to re-read.

And the connector cannot fetch it back: the default backfill window is **60 days**, which is why
benchmark P3 (6 months) and P4 (12 months) are recorded as *impossible, not unproven*.

> ⛔ **This alone settles it.** Without the graph, everything older than a month is not "slower to
> answer" — it is **unanswerable**.

### 5.2 · Gmail cannot be asked what you believed on Tuesday

A source read returns **the world now**. Three of the product's obligations need **the world
then**:

| | |
|---|---|
| **replay** | a decision replay needs the graph that produced it, or the replay is half-exact |
| **audit** | *"what did GeniOS know when it recommended that?"* — the question every security review asks |
| **explanation** | *"you told me X in March"* is only defensible against **March's** graph |

A mailbox has no `as_of`. The graph has one predicate.

### 5.3 · A source cannot resolve a disagreement with another source

The contract PDF says the renewal is 31 March. An email says *"I think it's April sometime."*
Reading both gives you two answers. The graph gives you **one value, the rank that decided it,
and the discrepancy kept beside it** — which is what `discrepancy` in §4.1 is.

**No individual tool can do this, because the conflict is between tools.**

### 5.4 · Identity is not in any source

Gmail knows `rohit@genios.ai`. Calendar knows `Rohit Swerashi`. The contract PDF says
*"R. Swerashi, Director"*. **No source knows they are one person.** `graph_aliases`,
`canonical_key` and `identity_strength` are where that is decided once instead of re-guessed on
every read.

### 5.5 · Cost and determinism

A situation sweep reads the whole org's facts in **one query** (`_bulk_load_facts`). The same
thing against the tools is N API calls, rate-limited, and **different every time** — which makes
`test_a_repeat_compile_does_not_mint_a_new_package` unwritable and the replay meaningless.

---

## 6. ⛔ The honest verdict

**Yes, it is needed — but not as "memory".** Calling it memory is what makes the question feel
uncomfortable, because *memory* sounds like a cache and a cache is optional.

**It is needed as four things a source read structurally cannot be:**

| | |
|---|---|
| **a survivor** | the source is deleted at 30 days. §5.1 — this is the one that is not arguable |
| **a clock** | *as of* is a predicate here and does not exist in any tool |
| **a referee** | conflicts are between sources, so no source can settle one |
| **a receipt** | `graph_source_refs` is what lets a card quote the sentence it came from |

**What it is NOT:** it is not remembering conversations, not a vector store, not an embedding
index, not a second brain. There is no similarity search in it. It stores **claims and their
provenance**, and every read is a `where` clause.

---

## 7. ⛔ Where the graph does NOT earn its keep, and it should be said

| | |
|---|---|
| **A single-source, current-state question** | *"what is this person's email address"* — Gmail is authoritative, now, and the graph adds a hop. `mcp/` and `api/` read tools directly for exactly this, and should |
| **Anything the tool owns better** | a calendar's free/busy, a document's current text. The graph should reference, not copy |
| **`graph_health` and `graph_segments`** | 2 of the 10 tables, and this analysis did not find a live reader for either. **Worth auditing in Layer 3's first step**, which is a `reason/`-and-graph measurement pass |
| ⛔ **The 995 MB incident** | the graph's *derived* layer did earn a real cost once: a content address that churned every sweep put 4,086 rows and 995 MB on one tenant — 67% of the database — and took the project read-only. Recorded in `to_semantic_dict`'s docstring. **The lesson is not "no graph"; it is that anything derived needs a content address that is stable** |

---

## 8. What this means for Layer 3

The Evidence Graph answers *"what was claimed."* **It does not answer "what did we conclude, and
was it right"** — and it should not, because those are interpretations and mixing them is the one
thing `Observation ≠ Inference ≠ Hypothesis` exists to prevent.

```
Evidence Graph          what SOURCES said           exists · 10 tables · upstream
Intelligence Graph      what WE concluded           ⛔ does not exist · Layer 3
```

**They must stay separate**, and the separation is already enforced: a model may propose an
inference and may never write an observation (`claim_state.model_may_write`), and every
interpretation cites `fact_version_id`s **into** the Evidence Graph rather than copying them out.

That citation is the join between the two graphs, and it already works.
