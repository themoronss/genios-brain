# Step 6 — PENDING · owner: Harsh

> **Status:** code COMPLETE and green · **NO migration · nothing deployed changes behaviour**
> **What it does:** domains had no confidence, no ontology, and nothing that reads more than a regex.
> **Written:** 2026-09-24 · **Evidence:** [`findings/step-06-domain.md`](findings/step-06-domain.md)

---

## 1. TL;DR — what you have to do

| # | Action | Blocking? | Time |
|---|---|---|---|
| **1** | **Run one SQL query (§3) so we can set metric 4's target** | **YES — 6-U0 is the only unfinished unit** | 5 min |
| **2** | **DECIDE: turn the domain proposer on?** It is built, tested, and **OFF by default** | **YES, before it is worth anything** | 15 min |
| **3** | Nothing else. **No migration. No env var. No table. No deploy risk.** | — | — |

> **Merging this changes production behaviour for nobody.** `proposer=None` is the shipping
> default and is proved byte-identical to today's output
> (`test_no_proposer_is_the_shipping_default_and_changes_nothing`). Everything else is additive.

---

## 2. ⛔ DECISION — turn the proposer on?

### 2.1 What it is

A keyword table only knows the language somebody wrote down in advance. A real mailbox is mostly
ordinary sentences, and `hints.py` already names the case it cannot handle: a footwear exporter's
core domain is *"container held at Nhava Sheva, BIS certificate pending, L/C expires Friday"* —
which matches none of the four shipped patterns, so the signal is tagged with nothing.

The proposer is **one small model call per message** that reads the text and names domains. It is
built, tested (53 tests) and **off**.

### 2.2 What it costs, and the three things that bound it

| Bound | Effect |
|---|---|
| **Its own model call** | the L1 extraction cache is **untouched** — no re-extraction bill (unlike step 4) |
| **Skipped under 80 characters** | *"thanks"*, *"+1"*, *"sounds good"* spend nothing. At a mailbox's scale this is most of the saving |
| **256 max output tokens** | it returns a short JSON list, not prose |

Metered under `purpose="domain_proposal"`, so it appears separately in `/admin` and can be watched
or switched off without touching extraction.

### 2.3 Why it is its own call and not part of the extraction prompt

Because the cost check ran before the code was written:

> `vocabulary_fingerprint()` folds in every closed set in the L1 extraction vocabulary and is part
> of the `l1_extraction_results` cache key. **Adding domains to LLM-2's prompt would have moved it
> and re-extracted the whole corpus — a second full bill on top of step 4's.**

A test now holds that line: if the fingerprint ever moves during a domain change, it fails.

### 2.4 Your options

| Option | What it means |
|---|---|
| **A — on for one tenant, watch the `domain_proposal` line** *(recommended)* | bounded, reversible, and metric 4 becomes measurable |
| **B — on everywhere** | fine if §3's numbers say coverage is bad enough to justify it |
| **C — leave it off** | the code is dormant and costs nothing. Metric 4 stays where the keywords put it |

**Reply "A", "B" or "C".**

---

## 3. ⭐ The one number I cannot get — 6-U0

**The 8% baseline in our plan is from a tenant that no longer exists** (re-synced 19 Sept). Setting
a target against a vanished corpus is the exact mistake this plan exists to prevent, so 6-U0 is
open until this runs:

```sql
select count(*)                                                          as signals,
       count(*) filter (where domain_hints is null
                           or domain_hints::text = '[]')                 as no_domain,
       count(*) filter (where domain_hints::text like '%"fallback"%')    as fallback_only,
       count(*) filter (where domain_hints is not null
                           and domain_hints::text <> '[]'
                           and domain_hints::text not like '%"fallback"%') as really_tagged
from qualified_signals
where org_id = '<pilot org>';
```

Send me the four numbers. I will write the measured baseline **and** the chosen target into
`STATUS.md` before writing another line of domain code.

> **Why it matters more than it looks.** If `really_tagged` is already high, step 6's remaining
> value is confidence and the ontology, not the proposer — and option **C** above becomes the right
> answer. The query decides the decision.

---

## 4. What changed, for your review

### 4.1 Three of this step's premises were wrong

| We believed | Reality |
|---|---|
| single-label, 1 or 0 domains per event | **already multi-label** — the comment saying otherwise referenced `resolve_domain`, which no longer exists |
| the never-filter rule has no test | **14 tests, all green.** Unit 6-U4 struck from the step |
| four keyword tables | four **shipped** plus any number **authored by an L3 corpus** |

Effort dropped from *"weeks"* to *"days"* on those corrections alone.

### 4.2 What was actually built

| Unit | What |
|---|---|
| **6-U1** | `DomainHint.confidence_bp` — `scope 9000 · keyword 6000 · proposed 4500 · fallback 1000`. A float is **refused, not rounded** (rounding stores `0.85` as 1 bp) |
| **6-U2** | an ontology **derived** from the shipped + authored tables, never a hand-written list |
| **6-U3** | `proposed_unknown` — a domain we do not run is **recorded, never dropped**, and never mistaken for a real one |
| **6-U5** | coverage **and distribution** — see below |
| **6-U6** | the proposer: own model call, own metering purpose, off by default |
| **6-U7** | the merge: keyword and proposal **both survive** |

### 4.3 Why coverage alone would have been a useless metric

> **A tagger that returns all five domains for every message has 100% coverage and zero
> information.**

That is the failure `hints.py` already records — the generic sales words claimed investor threads
and *"six VCs and three accelerator programmes became sales opportunities. Not one of its sixteen
sales situations was a customer."* Every one of those events **had** a domain. Coverage looked
excellent until somebody read a card.

So the sweep reports `tagged`, `fallback_only` and `mean_domains_per_event` together, plus
`is_indiscriminate` and `dominant_share_bp`. **The fallback is counted apart from coverage** — it
exists to make unmatched mail visible, and counting it as coverage restates the problem as a
solution.

### 4.4 The merge keeps both sides

Keyword says `sales`, proposer says `fundraising` → **both**, with their sources. Picking a winner
silently is how the six-VCs failure happened; doing it again with a model's authority behind it
would be worse.

---

## 5. Two defects this step's own build committed — recorded, not hidden

**Both are the same class, and it is the class this plan exists to find.**

1. **`domain_tagged` was a field nothing filled.** Added to `SyncSummary`, tests green, and no code
   incremented it. Exactly step 5's `claimed_total` mistake, two steps later. Caught by writing a
   test that drives a real `run_sync`.

2. **The test that proved it measured nothing.** The fixture used `source="fake"`, which has no
   visibility rule, so the event parked at S0.6 — `gated` was empty, metric 4 was computed over
   zero events, and it read a perfect `0`.

> **A test can be green, drive the real path, and still measure nothing.** Worth knowing when you
> read any "verified" claim of mine.

---

## 6. How to cross-check me

```bash
.venv/bin/python -m pytest tests -q -p no:randomly          # ~7 min
```
**Expect:** `12551 passed · 14 failed`. All 14 pre-existing — §7.

```bash
.venv/bin/python -m pytest tests/capture/domain -q -p no:randomly
```
**Expect:** `53 passed`.

### The cost guard — the most important single command here

```bash
.venv/bin/python -c "from genios_engine.capture.semantic.vocabulary import vocabulary_fingerprint as f; print(f())"
```

**Must print `a3d5496aa0d3`.** If it moved, the proposer leaked into the extraction vocabulary and
the whole corpus is about to re-extract. There is a test for it too, but this is the one-liner.

### Verify the "changes nothing" claim yourself

```bash
.venv/bin/python -c "
from genios_engine.capture.esqe.domain import tag_domains
t = tag_domains('hubspot', 'the term sheet and the renewal contract')
print(t.as_dicts)"
```

Every entry should carry `source` and `confidence_bp`, and **no entry should say `proposed`** —
because no proposer was passed.

---

## 7. Known failures, and why none is this step

Unchanged from steps 4 and 5 — **14, all pre-dating this branch**: `test_ocr_enablement` (no local
tesseract), `test_g9_gate_probes::test_probe_deleting_an_org` (needs Postgres),
`test_h0_gate` (meta-test), and 11 × `tests/context/` (L2's angle-audit writer, `store.py:328`).

Verify without trusting me:

```bash
.venv/bin/python -m pytest tests -q -p no:randomly 2>&1 | grep ^FAILED | sort > /tmp/now.txt
git stash && .venv/bin/python -m pytest tests -q -p no:randomly 2>&1 | grep ^FAILED | sort > /tmp/base.txt
git stash pop
comm -13 /tmp/base.txt /tmp/now.txt      # must print NOTHING
```

---

## 8. What this step does NOT do

* **It does not turn the proposer on.** §2.
* **It does not set metric 4's target.** §3 — blocked on you.
* **It does not put `proposed_unknown` in front of a human yet.** It is carried on the tagging; the
  review surface belongs with the open-lane discovery report.
* **It does not author any new domains.** That is a corpus task, and `hints.py` already reads
  `domain.yaml` from every authored corpus.

---

## 9. Send back to me

| # | Item | Your answer |
|---|---|---|
| 1 | §3 — the four numbers from the query | |
| 2 | §2.4 — proposer: **A**, **B** or **C**? | |
| 3 | §6 — did the fingerprint still print `a3d5496aa0d3`? | |
| 4 | §6 — full suite passed / failed counts | |
| 5 | §7 — did `comm -13` print nothing? | |
