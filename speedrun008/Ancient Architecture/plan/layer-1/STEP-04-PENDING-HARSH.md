# Step 4 — PENDING · owner: Harsh

> **Status:** code COMPLETE and green · **NO migration · NO deploy step · one review call**
> **What it does:** the three claim lanes L1 fires real signals off could not carry a receipt.
> Now they can, and ALG-08 grades them.
> **Written:** 2026-09-23 · **Evidence:** [`findings/step-04-typed-claims.md`](findings/step-04-typed-claims.md)

---

## 1. TL;DR — what you have to do

| # | Action | Blocking? | Effort |
|---|---|---|---|
| **1** | **⚠️ Budget the re-extraction.** This step re-extracts the WHOLE corpus on the first sweep after deploy. See §5 — it needs one SQL query from you | **YES — before deploy** | 5 min |
| **2** | **Read §4 and answer ONE question**: is the legacy-row read migration the behaviour you want? | **YES — before merge** | 10 min |
| **3** | Scratch Postgres *(same standing ask as steps 1–3)* | no, for the replay proof | ~30 min |
| **4** | Nothing else. **No migration. No env var. No table.** | — | — |

**No schema change** — steps 1–3 each needed a migration; this one touches no table. **But it is
not free**, and §5 is the part I nearly shipped without telling you.

---

## 2. What this step is

Doctrine 3 of Layer 1 is **"no claim without a receipt."** `ExtractionResult` had fifteen claim
lanes. Eight were typed and each carried `evidence: EvidenceSpan` + `confidence_bp`. Seven were
`list[str]` or `list[dict[str, Any]]` — and those **could not obey the doctrine, not because the
receipts were lost but because the type had no field to put one in.**

`esqe/detector.py` fired three real signal types off the untyped half, and said so itself:

> *"it carries no EvidenceSpan (the lane is `list[dict]` by contract), hence no receipt on that
> detection."*

**A comment is not a guard.** Three lanes are now claims:

| Lane | Question it answers | Type |
|---|---|---|
| `roles` | who somebody is | `RoleAssertion` |
| `availability` | when somebody cannot act | `AvailabilityWindow` |
| `questions` | what was asked and not answered | `OpenQuestion` |

Two lanes stay free-form **on purpose**: `topics` (*"free text by design"*) and `implied_actions`
(*"the model's words about what should happen"*). Judgements about the message, not claims about
the world. A receipt on a judgement adds ceremony without adding truth.

---

## 3. ⚠️ The plan's stated reason was WRONG — read this before anyone quotes it

The plan said typing these lanes would lift `relationship_change` over the qualification floor.

**It will not. Measured in production before any code was written:**

```
relationship_change   published 4 · DROPPED 54 · band 880–1560 bp
                      (the CEILING sits BELOW the floor)
best row's terms:     monetary_exposure_bp 0 · deadline_proximity_bp 0
```

Those zeros are **policy, not a defect**:

```python
normalize.DATE_POLICY[RELATIONSHIP_CHANGE]   = none
normalize.AMOUNT_POLICY[RELATIONSHIP_CHANGE] = claims_only
```

A role change genuinely states no amount and no deadline. ALG-17 reads `primary_date` and
`primary_amount`, both `None` **by design**, so typing changes the score by **zero basis points**.

**That a type's ceiling sits below the floor is a FLOOR question → step 8.** Metric 3 in
`STATUS.md` has been corrected.

> Fourth step in a row whose written premise production corrected. Step 2: *"the gate deletes
> bounces"* — it did not. Step 3: *"`array_agg[1]` loses signals"* — it does not. Step 4: *"typing
> lifts the score"* — it does not. **All three caught by measuring, none by reasoning.** That is
> the discipline, and it is working.

---

## 4. ⭐ THE ONE THING I NEED YOUR CALL ON

### 4.1 The problem

`context/qes_adapter.adapt_qes_extraction` rehydrates cached rows on the **live L2 path**:

```python
result = ExtractionResult.model_validate(dict(payload))    # ← every cached row
```

Every row already in `l1_extraction_results` carries the OLD lane shape. Without a read-side
migration, the promotion does not merely change the wire —

> **every cached extraction in every tenant becomes unreadable, and Layer 2 stops receiving
> anything from the cache on the day it ships.**

The cache is keyed on content version and only turns over when a message changes, so *"it will age
out"* is not an answer for a corpus nobody re-sends.

### 4.2 What I did

`ExtractionResult._rehydrate_legacy_lanes`, a `mode="before"` model validator:

| Old shape | Becomes |
|---|---|
| `questions: ["Can we sign Friday?"]` | `OpenQuestion(text=..., evidence=[], confidence_bp=5000)` |
| `roles: [{party, role, evidence_text: "<quote>"}]` | `RoleAssertion(party, role, evidence=[PROBE span], confidence_bp=5000)` |
| entry with no `evidence_text` | `evidence=[]` — honest *"stored without a receipt"* |
| already the new shape | **untouched** |

The **PROBE span** is the model's own words at offsets `0..len` with `verified=False` — the same
convention `extractor._spans_from_payload` already uses for a model that quoted correctly and
counted in the wrong frame. ALG-08 relocates it against the source.

**It never invents a quote.** `LEGACY_LANE_CONFIDENCE_BP = 5000` is deliberately below anything the
extractor states for itself, so a rehydrated legacy claim never outranks a graded one.

### 4.3 The question for you

> **Do you want legacy `evidence_text` preserved as an ungraded probe span (what I built), or
> dropped so that only claims the binder grounded ever reach Layer 2?**

| Option | Consequence |
|---|---|
| **A — preserve as probe** *(built)* | no data loss; L2 keeps receiving legacy roles; their receipts are graded on read, not trusted |
| **B — drop** | cleaner doctrine; **silently removes existing `party.role` facts from the graph** for every cached row |

**I recommend A** and built A, because B deletes data without a human ever seeing what was deleted.
But it is a product call about a live graph, not a code call, so it is yours.

**Reply with just "A" or "B".** If A, nothing changes and this step is done.

---

## 5. ⚠️ THE BILL — this step re-extracts the entire corpus

### 5.1 What I measured

```
vocabulary_fingerprint()    151b9dabf235   ->   a3d5496aa0d3
```

Measured by stashing the branch, reading the digest, and restoring. `UNTYPED_LANE_KEYS` is folded
into that digest; the digest is a component of the `l1_extraction_results` cache key. So:

> **every cached extraction misses, and every message in every tenant is sent to the model again
> on the first sweep after deploy.**

### 5.2 This is correct, not a bug — but it is a bill

The fingerprint is *supposed* to move when the prompt changes, and the prompt genuinely did:
`schema_gen` now renders three lanes as typed objects instead of open dicts. The module records
why it works this way, against a real failure:

> *"260 cached extractions survived a prompt fix, the numbers did not move, and the conclusion
> drawn was that the fix had not worked."*

A cache that survived this change would make step 4 invisible in production — the code would ship,
the receipts would not appear, and we would conclude the step failed.

**What is wrong is that nothing in the step's plan named this cost.** I found it while ticking the
done criteria, not while designing the step. It is now pinned by
`test_promoting_a_lane_changes_the_vocabulary_fingerprint_and_therefore_the_cache_key`, which
fails the day the digest moves again — so the next person is told rather than invoiced.

### 5.3 The one number I cannot get from here — run this

```sql
select count(*)                             as rows_to_reextract,
       count(distinct org_id)               as tenants,
       sum(coalesce(input_tokens, 0))       as input_tokens_last_time,
       sum(coalesce(output_tokens, 0))      as output_tokens_last_time
from l1_extraction_results;
```

`input_tokens_last_time` × the current price is a close estimate of the re-extraction, because the
same messages go to the same model under a prompt of near-identical length.

### 5.4 Your options

| Option | What it means |
|---|---|
| **Accept** | one-off spend, corpus re-extracted with receipts. Recommended |
| **Stage it** | deploy to one tenant, read the invoice, then roll on |
| **Defer** | hold the branch until a billing window suits. Nothing degrades while you wait |

**Do NOT** try to keep the old fingerprint. That reintroduces exactly the 260-row failure above.

---

## 6. What actually changed, for your review

### 6.1 The lanes now go through the real binder

The first implementation used a lenient reader that defaulted `evidence=[]`. That built claims
**schema rule S-4 then refuses** — so one unquotable question triggered a repair retry and then a
**parked extraction that lost every commitment, amount and decision in the same message**.

Fixed properly. The three lanes joined `CLAIM_FIELDS`, so they run the same path as every claim:

```
draft  →  bind_evidence  →  _build_claim  →  S-1..S-9
```

* cited nothing but the words ARE in the text → synthesized span at `bp * 7 // 10`
* words are nowhere → dropped and counted
* **S-4 holds by construction**

### 6.2 ALG-08 never walked these lanes — found by a failing test

After promotion, `test_schema.py` failed S-7 post-verification. The symptom was S-7; the defect was
that `evidence_from_claims()` did not list the three lanes and `apply_verdicts` did not rebuild
them. **The only three signal types derived from unverifiable claims were also the only three whose
receipts ALG-08 never saw.** Both fixed.

New drop-policy rows (`_policy_drops` raises on an unlisted type, so these are deliberate):

| Type | Policy | Reason |
|---|---|---|
| `RoleAssertion` | KEEP | filed with `EntityMention` — deleting it removes somebody from the graph |
| `AvailabilityWindow` | **DROP** | filed with `ResolvedDate` — an invented *"back on Monday"* suppresses a chase that should have happened |
| `OpenQuestion` | KEEP | dropping deletes the awaited item rather than doubting it |

### 6.3 Four detector predicates now cite their source

| Signal | Was | Now |
|---|---|---|
| `RELATIONSHIP_CHANGE` / `role_asserted` | no span + a comment saying so | `_spans(ex.roles)` |
| `AVAILABILITY_CHANGE` / `availability_stated` | no span | `_spans(ex.availability)` |
| `ANOMALY` / `non_routine_structure` | **no span at all** | spans of all four claim inputs |

`ANOMALY` is the one worth noticing: the catch-all, the type most likely to reach a human with no
explanation of why, was the one type that cited nothing.

---

## 7. How to cross-check me

### 7.1 Hermetic — runs anywhere, no database

```bash
.venv/bin/python -m pytest tests -q -p no:randomly          # ~7 minutes
```

**Expect:** `12470 passed · 1061 skipped · 152 xfailed · 14 failed`. All 14 are pre-existing and
named in §8. Baseline before this step was `12450 passed · 14 failed` — **zero regressions, 20
more tests passing.**

```bash
.venv/bin/python -m pytest tests/capture/test_every_claim_carries_a_receipt.py -q
```

**Expect:** `18 passed`. This is the file that states what the step is for. Ten of the eighteen
were written *after* the implementation, because the implementation is what surfaced §6.2, §4
and §5 — none of the three was in the plan.

### 7.2 The legacy read path — the §4 behaviour, in one command

```bash
.venv/bin/python -c "
from genios_engine.contracts.extraction import ExtractionResult
r = ExtractionResult.model_validate({
 'intent':'inform','stance':'neutral','model_snapshot':'m','prompt_version':'p',
 'schema_version':'s','extraction_profile':'email','input_tokens':1,'output_tokens':1,
 'questions':['Can we sign Friday?'],
 'roles':[{'party':'Acme','role':'counterparty','evidence_text':'Acme will send the renewal'}],
})
print(r.roles[0].evidence[0])
"
```

**Expect:** an `EvidenceSpan` with `quote='Acme will send the renewal'`, `verified=False`,
`source_ref='legacy_lane:roles'`. If `verified` is ever `True` here, stop — the read path is
stamping its own receipt and S-9 exists to prevent exactly that.

### 7.3 Gated on your scratch Postgres

```bash
GENIOS_TEST_DATABASE_URL=<scratch> .venv/bin/python -m pytest -m pg -q
```

Then replay a real event through `capture_event` and check `l1_extraction_results` — a fresh
extraction's `roles[*].evidence[0].source_ref` should read `prepared_content:<event_id>`, **not**
`legacy_lane:roles`. If you see `legacy_lane:` on a fresh row, the binder is not being reached and
the lenient path came back.

### 7.4 The pre-existing-failure claim, verified independently

I claimed the 11 L2 failures are not mine. Reproduce it yourself:

```bash
.venv/bin/python -m pytest tests/context -q -p no:randomly 2>&1 | grep ^FAILED | sort > /tmp/now.txt
git stash
.venv/bin/python -m pytest tests/context -q -p no:randomly 2>&1 | grep ^FAILED | sort > /tmp/base.txt
git stash pop
comm -13 /tmp/base.txt /tmp/now.txt      # must print NOTHING
```

`comm -13` printing nothing means every failure on the branch also fails on a clean tree.

---

## 8. Known failures, and why each is not this step

| Test | Reason |
|---|---|
| `test_ocr_enablement.py::test_the_wiring_returns_no_engine...` | no local tesseract — this is step 1's, and yours |
| `test_g9_gate_probes.py::test_probe_deleting_an_org...` | needs Postgres |
| `test_h0_gate.py::test_every_layer_two_placeholder_skips...` | meta-test; reports the 11 below |
| 11 × `tests/context/...` | L2's angle-audit writer, `store.py:328` — pre-existing, verified by §7.4 |

> One modelling error was found late and is worth knowing about: **`AvailabilityWindow.person`
> shipped required and had to become optional.** An out-of-office auto-reply names nobody — and
> `context/extract/availability._person` already read it that way (*"None when it names the
> author"*). `None` now means the author. Requiring a name would have made the extractor invent
> an identity the message never stated.

**A skipped test is not a pass.** The 618 `pg`-marked tests are SKIPPED here, not green. §6.3 is
what turns them green and it needs your scratch database.

---

## 9. What this step does NOT fix

* **`relationship_change` is still below the floor.** See §3. Step 8.
* **`relationships` and `scheduling_proposals` are still untyped.** `relationships` is next;
  `scheduling_proposals` needs L2's scheduler to declare what it reads first.
* **Nothing is backfilled.** Legacy rows rehydrate on read; nothing rewrites
  `l1_extraction_results` in place.

---

## 10. Send back to me

| Item | Your answer |
|---|---|
| **§5.3 — `rows_to_reextract` and `input_tokens_last_time` from the query** | |
| **§5.4 — accept / stage / defer the re-extraction?** | |
| §4.3 — legacy receipts: **A** (preserve as probe) or **B** (drop)? | |
| §6.1 — hermetic run: passed / failed count | |
| §6.2 — did `verified` come back `False`? | |
| §6.3 — `pg` lane run, or still blocked on the scratch DB? | |
| §6.4 — did `comm -13` print nothing? | |
