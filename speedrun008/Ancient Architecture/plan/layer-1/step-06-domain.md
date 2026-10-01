# Step 6 — Domain mapping

**Status:** PLANNED · **Effort:** days, not weeks · **Depends on:** 3, 4 (both code-complete)
**Engine:** L proposes, R validates · **Moves:** metric 4 — non-fallback domain coverage

> **REWRITTEN 2026-09-24 after reading the code.** Three of this step's original premises were
> wrong and one unit was already built. The original said *"weeks"*; with the corrections it is
> days. Everything below is checked against the shipping modules, not against the plan.

---

## 0. Premise check — done BEFORE planning, per the rule that has paid off five times

| Original premise | Verdict |
|---|---|
| *"Four keyword tables"* | ❌ **stale** — four SHIPPED plus any number **authored by L3 corpora** (`_authored_hints`, `domain.yaml`) |
| *"single-label"* · *"Domains per event: 1 or 0"* | ❌ **WRONG — it is already multi-label** |
| *"the never-filter rule has no test"* | ❌ **WRONG — it has 14 of them, all green** |
| *"815 of 889 events carried no domain / 8%"* | ⚠️ **STALE CORPUS** — measured on a tenant that no longer exists |
| No per-domain confidence | ✅ confirmed — `DomainHint` is `{domain, source}` and nothing else |
| No model proposes a domain | ✅ confirmed — every path is regex + source prior |

### 0.1 · Already multi-label — the headline correction

`capture/domain/hints.py::domain_hints` loops and appends:

```python
for domain, pat in _ordered_keywords():
    if pat.search(text) and not any(h.domain == domain for h in hints):
        hints.append(DomainHint(domain=domain, source="keyword"))
```

Every matching pattern contributes. The file's own comment still says *"the FIRST match wins in
`resolve_domain`"* — **`resolve_domain` no longer exists.** The function was made multi-label and
the comment was never updated, which is how the plan inherited a wrong premise from a stale line.

> So *"Security questionnaire is blocking procurement is Sales AND Security AND Procurement —
> today it is none of them"* is **half right**. The shape supports several domains. What it cannot
> do is recognise *Security* or *Procurement* at all, because no pattern knows those words, and it
> cannot say how sure it is about any of them.

**6-U1 is therefore not "make it multi-label". It is "give it a proposer that knows more words
than a regex, and a confidence per domain".**

### 0.2 · The never-filter rule is already tested — 6-U4 is DONE

`tests/capture/esqe/test_domain.py`, 14 tests green, including the strongest form:

```python
def test_coverage_changes_the_flag_and_nothing_else():
    """the tag list is byte-identical whether the tenant has full coverage, no coverage,
    or no coverage function at all."""
    assert everything.domains == nothing.domains == unwired.domains
```

**6-U4 is struck from this step.** It stays in §9 as a rule this step must not break.

### 0.3 · The 8% is from a corpus that no longer exists

`815 of 889` was measured on the pilot tenant, 12 Aug – 8 Sep. That tenant was re-synced on
19 September; production now holds 1,202 events dated 19–23 Sep. **The number must be re-taken
before the target is set** — §3 is blocked on it, and setting a target against a vanished baseline
is the mistake this whole plan is built to avoid.

---

## 1. Why this step exists

A keyword table only knows the language somebody thought to write down in advance. A real mailbox
is mostly ordinary sentences — *"can you send that across"*, *"are we still on for Thursday"* —
and those match nothing, so most events arrive with no domain and Layer 2 has nothing to select a
corpus by.

Two consequences, and the second is worse:

1. **L3 cannot choose a corpus.** The activated corpus never spoke because nothing routed to it.
2. **The domains we DO assign are wrong in a specific, expensive way.** `hints.py` records it
   itself: letting the generic sales words claim investor threads turned *"six VCs and three
   accelerator programmes into sales opportunities. Not one of its sixteen sales situations was a
   customer."*

A confidence per domain is what lets a reader tell *"probably sales"* from *"certainly sales"*,
and today both render identically.

---

## 2. Current status, with file and line

| Piece | Where | State |
|---|---|---|
| Keyword + source-prior matcher | `capture/domain/hints.py:158` `domain_hints` | multi-label, no confidence |
| Shipped domains | `hints.py:106` `_SHIPPED_RANK` | `fundraising 10 · sales 20 · support 30 · admin 40` |
| Authored domains | `hints.py:109` `_authored_hints` | reads every corpus `domain.yaml`; fails soft |
| Fallback | `hints.py:77` `FALLBACK_DOMAIN = "admin"` | emitted events only; stamped `source="fallback"` |
| Coverage + never-filter | `capture/esqe/domain.py:137` `tag_domains` | ✅ done and tested |
| The contract | `contracts/gated_event.py:11` `DomainHint` | `{domain, source}` — **nowhere to put a confidence** |
| L1 vocabulary | `capture/semantic/vocabulary.py:109` `_SETS` | six sets, **no domain set** — see §5.0 |

---

## 3. Expected result

| | Before | After |
|---|---|---|
| Events with a non-fallback domain | **RE-MEASURE FIRST** (§0.3) | target written down before any code |
| Confidence per domain | none | integer basis points, per domain |
| Domains a tenant can recognise | 4 shipped + authored | + whatever the proposer reads |
| `proposed_unknown` recorded | no | yes, never dropped |
| Coverage reported per sweep | no | yes |

> **The target is set AFTER §7.1 is run and BEFORE any code is written.** Writing it here now
> would be a number invented against a corpus nobody has measured.

---

## 4. Edge cases and failure scenarios

| # | Scenario | What must happen |
|---|---|---|
| **E1** | proposer names a domain this tenant does not run | `proposed_unknown`, recorded, **never dropped** |
| **E2** | every domain uncovered | signal still emits, `degraded_compile=True` — the never-filter rule |
| **E3** | proposer invents a domain that exists nowhere | the ontology refuses it; **the signal survives** |
| **E4** | proposer returns a float confidence | converted to integer bp **at the adapter edge**; V-7 rejects floats |
| **E5** | proposer returns "all five" every time | useless. **Measure the DISTRIBUTION, not just coverage** — a proposer that tags everything has 100% coverage and zero information |
| **E6** | cost | one more model site → must be metered with its own `purpose`; `tests/test_every_llm_call_site_is_metered.py` fails in both directions |
| **E7** | proposer is down or times out | fall back to the keyword hints. **Domain is never a hard dependency of capture** |
| **E8** | keyword says `sales`, proposer says `fundraising` | **keep both, with their sources.** This is the six-VCs failure, and the fix is not to pick a winner silently |
| **E9** | an authored corpus and the proposer name the same domain | one entry, highest confidence, both sources recorded |
| **E10** | the message is one word (*"thanks"*) | no proposal. **Do not spend a model call to tag an acknowledgement** |

---

## 5. How to do it, unit by unit

### 5.0 · ⛔ THE ARCHITECTURE DECISION, made by the cost check before any code

`vocabulary_fingerprint()` is a component of the `l1_extraction_results` cache key, and it folds in
every closed set in `_SETS`. **Adding a `domain` set to LLM-2's vocabulary would change the
fingerprint and re-extract the entire corpus — a second full bill on top of step 4's.**

> **Therefore: the domain proposer is its OWN model call, not a field added to LLM-2's prompt.**

| Consequence | |
|---|---|
| Cache | untouched. No fingerprint change, no re-extraction |
| Metering | it needs its own `purpose` anyway (6-U6), which a separate site gives for free |
| Cost control | it can be skipped for short or low-value messages (**E10**) — impossible if it rides inside LLM-2 |
| Failure | it can fail without failing extraction (**E7**) |

This is the step-4 lesson working: **check the cost consequence before building, not after.**

### 5.1 · The units

| Unit | What | Artifact | Depends on |
|---|---|---|---|
| **6-U0** | **re-measure the baseline** on the live corpus and write the target down | a number in `STATUS.md` | — |
| **6-U1** | `DomainHint` gains `confidence_bp: int` | `contracts/gated_event.py` | — |
| **6-U2** | a domain **ontology** — the registered set = shipped ∪ authored, with one function that validates a proposal | `capture/domain/ontology.py` | — |
| **6-U3** | `proposed_unknown` as a recorded outcome, never a drop | `capture/domain/ontology.py` + store | 6-U2 |
| **6-U4** | ~~never-filter becomes a test~~ | **ALREADY DONE** — §0.2 | — |
| **6-U5** | per-sweep coverage + **distribution** metric | `capture/domain/` + the sync ledger | 6-U1 |
| **6-U6** | the proposer: its own model site, metered, `purpose="domain_proposal"` | `capture/domain/proposer.py` | 6-U1, 6-U2 |
| **6-U7** | merge proposer + keyword hints keeping **both sources** (E8, E9) | `capture/domain/hints.py` | 6-U6 |

**Build order:** 6-U0 → 6-U1 → 6-U2 → 6-U3 → 6-U5 → 6-U6 → 6-U7.
Contract first, ontology before anything that validates against it, the model site last so every
deterministic piece is green before a single token is spent.

### 5.2 · Where each unit is wired — the "six times" check

Every unit names the **real request path** that reaches it. A unit with no row here is not done.

| Unit | Reached by | Driven by a test on that path |
|---|---|---|
| 6-U1 | `hints.domain_hints` → `esqe/domain.tag_domains` → `GatedEvent.domain_hints` → `qualified_signals.domain_hints` → L2 | `tests/capture/esqe/test_domain.py` |
| 6-U2 | `tag_domains` validates every hint before it leaves | new |
| 6-U3 | the same call; the unknown is written, not discarded | new |
| 6-U5 | `run_sync` → `SyncSummary` → `_run_ledger` (**the seam step 5 just opened**) | new |
| 6-U6 | `capture_event` → the proposer, guarded by E7/E10 | new |
| 6-U7 | `domain_hints` returns the merged list | `test_domain.py` extended |

> **The step-5 ledger is what 6-U5 lands in.** `l1_sync_runs` now has completeness columns; domain
> coverage is the same kind of per-sweep fact and belongs beside them, not in a new table.

---

## 6. Test cases — RED first, every one

| # | Test | Must be RED on today's code because |
|---|---|---|
| **T1** | a domain hint carries a confidence | `DomainHint` has no such field |
| **T2** | a proposal outside the ontology is recorded as `proposed_unknown` | the concept does not exist |
| **T3** | an all-uncovered signal still emits, degraded | *(GREEN today — regression guard, §0.2)* |
| **T4** | no float reaches storage from any domain path | V-7 |
| **T5** | the metering register knows `domain_proposal` | new site |
| **T6** | a proposer that returns "all five" is visible in the distribution metric | E5 — coverage alone cannot see it |
| **T7** | a dead proposer leaves the keyword hints intact | E7 |
| **T8** | keyword `sales` + proposer `fundraising` yields BOTH, with sources | E8 — the six-VCs failure |
| **T9** | a one-word message spends no model call | E10 |
| **T10** | the ontology = shipped ∪ authored, derived not listed | a hand-written list drifts the day a corpus is authored |

---

## 7. Verify

### 7.1 · The baseline, FIRST — 6-U0, before any code

```sql
select count(*) filter (where domain_hints is null or domain_hints = '[]')          as no_domain,
       count(*) filter (where domain_hints::text like '%"source":"fallback"%')      as fallback_only,
       count(*)                                                                      as total
from qualified_signals where org_id = '<org>';
```

Write the result and the chosen target into `STATUS.md` **before** writing code.

### 7.2 · Hermetic

```bash
.venv/bin/python -m pytest tests/capture/domain tests/capture/esqe/test_domain.py -q -p no:randomly
.venv/bin/python -m pytest tests/test_every_llm_call_site_is_metered.py -q -p no:randomly
```

### 7.3 · The cost guard

```bash
.venv/bin/python -c "from genios_engine.capture.semantic.vocabulary import vocabulary_fingerprint as f; print(f())"
```

**Must still print `a3d5496aa0d3`.** If it moved, the proposer leaked into LLM-2's vocabulary and
the corpus is about to re-extract — see §5.0.

---

## 8. Done criteria

**Ticked 2026-09-24.** Four closed, three cannot be closed from this machine and are named in the
Harsh runbook rather than quietly ticked.

- [ ] **6-U0: the baseline re-measured on the LIVE corpus, target written down** — **NOT DONE and
      it is the one blocking item.** The 8% is from a tenant re-synced away on 19 Sept. The SQL is
      §3 of the runbook. **Deliberately not ticked**, and no domain code was written that depends
      on a target.
- [ ] **measured coverage moved to the target, or the shortfall is explained** — cannot move until
      6-U0 sets it, and until the proposer is switched on (runbook §2).
- [x] **the distribution is reported, not only the coverage (E5)** — `DomainDistribution` carries
      `mean_domains_per_event_bp`, `is_indiscriminate` and `dominant_share_bp`, and the sweep
      counts `domain_tagged` apart from `domain_fallback_only`. Driven through a real `run_sync`
      by `test_metric_four_is_counted_by_the_sweep_that_produces_it`, not asserted on a dataclass.
- [~] **`proposed_unknown` is recorded somewhere a human reads** — it is CARRIED on
      `DomainTagging.proposed_unknown` and tested at the seam, but it is not yet persisted to a
      review surface. That belongs with the open-lane discovery report, which already exists for
      the same purpose. **Half, and marked half.**
- [x] **the model site is metered and appears in `_SITES`** — `domain_proposal`. The register's
      own guard caught the unregistered site before I did.
- [x] **`vocabulary_fingerprint()` is unchanged** — `a3d5496aa0d3`, pinned by
      `test_the_extraction_cache_fingerprint_is_untouched`. **No second re-extraction bill.**
- [x] **never-filter still green** — 14 tests, plus a new regression guard in this step's own file.

### 8.1 · Two defects this step's own build committed

1. **`domain_tagged` was a field nothing filled** — added to `SyncSummary`, tests green, nothing
   incremented it. Step 5's `claimed_total` mistake, two steps later.
2. **The test that caught it measured nothing at first** — the fixture used `source="fake"`, which
   has no visibility rule, so the event parked at S0.6 and metric 4 was computed over zero events,
   reading a perfect `0`.

> **A test can be green, drive the real path, and still measure nothing.** Both are in
> `findings/step-06-domain.md` §4 and in the runbook §5.

---

## 9. What this step must NOT do

- **Do not let domain mapping filter anything.** Tag, never route, never drop. It is already
  tested; do not be the change that breaks it.
- **Do not let a model's confidence become a ranking number.** ALG-17 does not read it.
- **Do not add a fifth keyword table and call it a fix.**
- **Do not add a domain set to LLM-2's vocabulary.** §5.0 — it costs a full re-extraction.
- **Do not make domain a hard dependency of capture.** E7: a dead proposer must not stop a message
  landing.
- **Do not overwrite the shipped four from an authored corpus.** Their patterns are calibrated
  against a live graph; `hints.py` skips a same-named corpus deliberately.
