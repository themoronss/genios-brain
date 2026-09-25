# How both graphs are built, and exactly how they work

**2026-09-25** · the Evidence half read out of `context/graph_store.py`; the Intelligence half
designed onto the same machinery.

---

# PART 1 · The Evidence Graph — how it is actually built

## 1.1 · Identity comes first, and it is a LOOKUP, not a hash

```python
find_or_create_node(org_id, node_type, canonical_key, display_name, event_id)
```

1. `select node_id from graph_nodes where org_id=… and canonical_key=… and valid_to is null`
2. found → **return it**, and re-register its aliases
3. not found → `new_id("node")` = `node_3f2a…`, **a random uuid4**, and claim its alias keys

⛔ **The id is opaque and random. Identity lives in `canonical_key`, never in the content.**
That is the 995 MB incident's lesson applied: a derived content address that churns creates a new
row every sweep. `node_id` never churns because nothing about the content is in it.

And `find_or_create_node` **re-registers on every sighting, not just at creation** — because a name
usually arrives *after* its anchor: *"an email gives you acme.io today and the words 'Acme
Technologies' next week, and that later name is exactly the key a prose mention needs to find it
by."*

**Alias collision → merge proposal, not error.** The first claimant keeps the key, lookups stay
stable, a human decides.

## 1.2 · ⛔ Then one pure function decides everything

```python
fact_write_action(held_value, held_rank, held_occurred_at,
                  new_value, new_rank, new_occurred_at, replay) -> str
```

It returns **exactly one of five words**, and the order of its checks is the design:

| # | returns | when | what happens |
|---|---|---|---|
| 1 | **`insert`** | nothing is held | new fact row, `valid_to = null` |
| 2 | **`noop`** | same value | ⛔ **CORROBORATION** — see §1.3 |
| 3 | **`historical`** | `new.occurred_at < held.occurred_at` | recorded with **`valid_from = valid_to = now()`** — an **empty window** |
| 4 | **`discrepancy`** | lower authority disagrees | held value **stays**; a `discrepancies` row opens |
| 5 | **`supersede`** | newer, equal-or-higher authority | held row gets `valid_to = now()`, new row opens |

**Staleness is checked BEFORE authority, deliberately:**

> *"Without this, any backfill/re-extract replays a 2024 `thread.ball_in_court=us` over today's
> `them` and the correct value is already stamped superseded — an unrecoverable corruption."*

**And `historical`'s empty window is the elegant part.** A backfilled 2024 value gets
`valid_from = valid_to = now()`, so it matches **no** point-in-time read — not even 2024's.
It is kept as a record and is invisible to history, because **we did not know it then**.

## 1.3 · `noop` is not "nothing happened"

> *"A second source asserting the SAME value is independent confirmation, and it is what the scoring
> ladder (**one:60 / two:85 / three+:100**) and `src_count` read. This branch used to return None
> before any ref was written, so `src_count` could never exceed 1 and **the whole ladder was dead
> code** — email + CRM agreeing looked identical to email alone."*

So `noop` still writes a `graph_source_refs` row, attached to the **held** version, **deduped per
event** so a re-sync cannot inflate it.

## 1.4 · The read path is one predicate

```
as at T   →   valid_from <= T  and (valid_to is null or valid_to > T)
live      →   valid_to is null
```

**Half-open `[valid_from, valid_to)`.** A row closed at noon and its successor opened at noon must
not both match noon, *"or the read returns two contradictory versions of one thing and the replay
has no single answer."*

⛔ **And there is deliberately no `graph_snapshots` table.** All three tables are already fully
versioned, so the delta walk is exact on its own; a snapshot would be a cache in front of a read
that is already correct — *"precisely the 'unit that nothing calls' this wave exists to stop."*

## 1.5 · So one event, end to end

```
event arrives
 │
 ├─ find_or_create_node()      identity by canonical_key   → node_id
 ├─ write_fact()               fact_write_action() → 1 of 5
 │    └─ graph_source_refs     ⛔ the receipt: event_id + {span,text,page,bbox}
 ├─ write_edge()               same versioning
 ├─ write_observation()        something happened, no value asserted
 └─ bump_version(org_id)       graph_versions += 1
        └─ graph_change_outbox  so downstream knows
```

Then, on the sweep: **9 correlators read** → **7 producers** → **`BusinessSituationObject`**.

---

# PART 2 · The Intelligence Graph — the same machinery, different rules

## 2.1 · Its identity key is not a person, it is a QUESTION

| Evidence | Intelligence |
|---|---|
| `canonical_key` = `acme.io` | `canonical_key` = **`(situation_id, slice_digest)`** |

⛔ **This already exists.** `situation_interpretations` (0183) is
`unique (org_id, situation_id, slice_digest)`. *"Two sweeps over an unchanged slice must resolve to
one row rather than paying twice."*

**Same discipline, different subject:** the Evidence Graph deduplicates **the world**; the
Intelligence Graph deduplicates **the question**.

## 2.2 · Its five-way decision, by the same shape

```python
interpretation_write_action(held_conclusion, held_slice_digest, held_valid_until,
                            new_conclusion, new_slice_digest, now) -> str
```

| # | returns | when | what happens |
|---|---|---|---|
| 1 | **`insert`** | first reading of this situation | conclusion row opens |
| 2 | **`noop`** | same slice, same conclusion | nothing paid, nothing written |
| 3 | **`restated`** | ⛔ **different slice, same conclusion** | **confidence rises** — this is `noop`'s corroboration ladder, one level up |
| 4 | **`reversed`** | different slice, different conclusion | held closes, new opens, **`supersedes` edge written** |
| 5 | **`expired`** | `valid_until` passed, nothing renewed it | ⛔ closes with **no successor** |

### ⛔ Two of these have no Evidence-Graph equivalent, and that is the real difference

**`expired` cannot exist in the Evidence Graph.** A fact about the world does not stop being true
because time passed — a source has to say otherwise. **A conclusion does.** *"An interpretation that
never expires is not an interpretation"* — 0183's comment on `valid_until`.

**And there is no `discrepancy`.** The Evidence Graph resolves conflict by **authority rank R1–R4**,
because a CRM outranks a guess. ⛔ **We have no rank over ourselves.** Two readings by GeniOS are
both by GeniOS. So what supersedes what is not *who said it* but **which one saw more** — which is
why the key is the **slice digest**, and why 0183 stores **the slice itself, not its hash**.

## 2.3 · Its receipt is a slice, not a span

| Evidence Graph | Intelligence Graph |
|---|---|
| `graph_source_refs` → `event_id` ＋ `{span, text, page, bbox}` | **`context_slice jsonb`** — everything the reasoner was shown |
| *"which sentence said this"* | *"what was on the table when we concluded this"* |

⛔ **Already built, in 0183, and unlinked.** L2-3 weighed the slice; L2-5 stored it.

## 2.4 · It writes at four moments, not on every event

The Evidence Graph writes **synchronously, per event**. The Intelligence Graph has four write
points, and all four already produce their data:

| when | writes | source that already exists |
|---|---|---|
| a situation is produced | `situation` node | `context_situations` |
| a decision is made | `decision` node ＋ `about` edge | ⛔ **the missing edge** |
| a card is delivered | `delivery` node ＋ `delivered_as` | `deliver/` — writes nothing back today |
| an outcome lands | `outcome` node ＋ `resulted_in` | `execution_outcomes` — **7 terminal labels ready** |

## 2.5 · And the read closes the loop

```
9 correlators
   ├─ read the Evidence Graph      →  what is true
   └─ read the Intelligence Graph  →  ⛔ what we already said about it
              ↓
       7 producers
              ↓
   BusinessSituationObject  —  now carrying "decided 3 times · ignored · ignored · dismissed"
```

**That one extra read is the entire product difference.** Everything before it is plumbing.

---

# PART 3 · Side by side — mechanism

| | **EVIDENCE GRAPH** | **INTELLIGENCE GRAPH** |
|---|---|---|
| **identity key** | `canonical_key` — `acme.io`, a message-id | **`(situation_id, slice_digest)`** |
| **id scheme** | `uuid4` — opaque, random, never churns | same |
| **dedups** | **the world** — one node per entity | **the question** — one reading per (situation, slice) |
| **write trigger** | **every event**, synchronously | **four moments** — produced · decided · delivered · resolved |
| **decision fn** | `fact_write_action` → 5 words | `interpretation_write_action` → 5 words |
| **the 5** | insert · noop · historical · discrepancy · supersede | insert · noop · **restated** · **reversed** · **expired** |
| **repeat = ?** | ⛔ **corroboration** — ladder 60/85/100 | ⛔ **restated** — same ladder, over slices not sources |
| **conflict resolved by** | **authority rank R1–R4** | ⛔ **recency of the slice** — we have no rank over ourselves |
| **out-of-order** | `historical`, **empty window**, invisible to history | same rule applies |
| **can something lapse?** | ⛔ **no** — a fact needs a source to contradict it | ⛔ **yes** — `expired`, `valid_until` |
| **receipt** | `event_id` ＋ span/page/bbox | **the context slice itself** |
| **read predicate** | `valid_from <= T < valid_to`, half-open | identical |
| **version counter** | `graph_versions` bigint per org | the same, so a decision can name the graph it saw |
| **health** | `graph_health` — MIN, empty scores 100 | the same discipline |
| **failure it prevents** | **inventing a fact nobody said** | **repeating a decision that already failed** |

---

# PART 4 · One situation, traced through both

**"Acme का deal चुप हो गया"**

| | Evidence Graph | Intelligence Graph |
|---|---|---|
| **Mon** — 3 emails, 1 meeting | `person`, `company`, `deal`, `thread` nodes · `works_at`, `attended` edges · `deal.stage='negotiation'` R2 · `thread.ball_in_court='them'` · 4 source_refs | — |
| **Mon** — sweep | correlators group them → producer emits a `deal` situation → **BSO** | `situation` node opens |
| **Mon** — reasoner runs | — | reads slice → concludes *"chase"* → **`insert`** · `valid_until = Thu` |
| **Mon** — card sent | — | `delivery` node · `delivered_as` edge |
| **Tue** — nothing changes | nothing written | ⛔ **`noop`** — same slice. **Nothing paid.** |
| **Wed** — CRM also says `negotiation` | ⛔ **`noop` = corroboration.** `src_count` 1→2, confidence **60→85** | — |
| **Wed** — user ignores the card | — | `outcome` node, `expired_untouched` · `resulted_in` edge |
| **Thu** — reply arrives | `thread.ball_in_court` `them`→`us`: **`supersede`**, held closed | slice changed → new reading → *"no chase"* → **`reversed`**, `supersedes` edge |
| **Thu** — sweep | correlators read | ⛔ **correlators read this too** — situation now carries *"chased once, ignored"* |
| **Thu** — the card | — | ⛔ **not sent again.** Not because a rule said so — because **the correlator could see it** |

**Today the last three rows do not happen.** The Evidence Graph columns are all real; the
Intelligence column is four tables that never link and that nothing reads back.

---

# PART 5 · Why they must stay separate

⛔ **The Evidence Graph must never hold a conclusion. The Intelligence Graph must never hold a
fact.**

The moment *"this deal is at risk"* is written as a `graph_fact`:

- it gets an `authority_rank`, so **our guess starts competing with a CRM on the same ladder**
- `noop` counts it as **corroboration**, so **the same model agreeing with itself twice reads as two
  independent sources** and confidence climbs 60 → 85 on nothing
- a replay can no longer separate **what a source said** from **what a model guessed**

That is `Observation ≠ Inference ≠ Hypothesis`, enforced by **two stores instead of one flag** —
because a flag can be forgotten on one write path, and a table cannot.
