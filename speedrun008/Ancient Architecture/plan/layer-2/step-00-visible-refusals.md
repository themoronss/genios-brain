# L2-0 · Make every refusal visible

**Needs Harsh:** counts need the pilot · **Migration:** none · **Model calls:** none
**Build this first.** It is the cheapest step in the plan and it is what makes every later step
measurable.

> ## ✅ COMPLETE — 2026-09-24 · [findings](findings/step-00-visible-refusals.md)
>
> 29 tests · 12,914 passed · 0 regressions · no migration · no model call.
>
> ⛔ **AND IT FOUND THAT THIS PLAN'S CORPUS NUMBER WAS WRONG BY 3.4×.** "534 capabilities, 200
> admissible, 334 dark at cutover" was a FILE count. Measured: **155 capabilities, 155 admissible,
> 0 hollow.** `require_admission=True` costs **nothing**, which re-shapes steps 4 and 8.
>
> ⛔ **AND THE REAL CORPUS GAP WAS UNDERNEATH IT: 24 of 69 authored situations are `draft`** —
> **16 of Customer Support's 20** — and each downgrades its card to an OBSERVATION. It describes,
> and it does not instruct. **One word per file, by an author. Harsh item 22.**

---

## 1. ⛔ Premise — Layer 2's dominant failure is a refusal that is right and invisible

Four separate defects, one shape. Each is quoted from the code that carries it.

### 1 · 63 of 159 situations held, because Layer 1 published nothing

`situation_bso.py:565`:

> *"MEASURED ON THE PILOT 2026-09-16: **159 active situations, 96 reaching a live scored signal, and
> 63 reaching none.** Layer 3 holds every one of those 63, and `qes_required` and
> `verified_evidence_required` are the SAME cards rather than two gaps — both read what Layer 1
> published, and **Layer 1 published nothing.**"*
>
> *"**THE REFUSAL IS CORRECT.** The 71 events behind those cards scored **528–1920 basis points
> against a floor of 2500**, and a card whose only evidence Layer 1 declined to publish should not
> carry authority. That is what the floor is for."*
>
> *"**THE SILENCE IS NOT.** Such a card today simply exists, ranks, and quietly never becomes
> anything, while **no surface says 'its best evidence scored 1360 against a floor of 2500'.** That
> is **the fifth time** this codebase has carried a refusal that was right and invisible."*

### 2 · 33 support situations, unrouted by a spelling seam

`domain_shadow.py`:

> *"it silently returned `()` for every support situation on the tenant — **33 of them** — so that
> corpus could never receive an overlay however it was declared. `admin` and `sales` spell the same
> on both sides, **which is why the miss was invisible.**"*

### 3 · Fundraising, dark on every tenant configuration

`_L2_TO_L3_DOMAIN` maps `fundraising` to nothing — correctly, because no corpus was authored — and
`live_lane()` then returns `False`. **The pilot is a fundraising founder.** No package, no signal, no
surface saying so.

### 4 · 21 untraceable commitments — caught, but ten cards late

`outreach_situations.py:876`:

> *"all 21 sit at `verified_evidence_required` — but the situation was minted, ranked and **in ten
> cases carded** before that refusal, so the cost was paid and **the founder saw promises nobody
> made.**"*

---

## 2. The pattern, stated once

```
the system refuses           ← correctly, almost always
the refusal is not surfaced  ← the defect
the founder sees a gap and cannot tell a gap from an answer
```

⛔ **This is not a quality problem. It is an accounting problem** — and it is why *"domain expertise
kuch kaam hi nahi kar raha hai"* reads as a mystery instead of a number.

Layer 1 already solved the same problem for signals and wrote the rule down:

> **`DROP ≠ DELETE`** — *"you log why dropped, which rule, which threshold, which evidence. So when
> the founder says 'why didn't GeniOS tell me about this?' you can trace the failure."*

**L2 has the refusals and not the ledger.**

---

## 3. Units

### L2-0-U0 · One report, every refusal, counted by reason
Not four dashboards — **one**. Every place L2 declines, with its count and its reason:

```
HELD        qes_required · verified_evidence_required      → and the score vs the floor
UNROUTED    domain = None                                  → by L2 domain
UNTRACEABLE commitments with no message                    → count
REFUSED     admission laws                                 → by law
```

```
verify:  scripts/l2_refusal_report.py --org <pilot>
```

### L2-0-U1 · A held situation states its own number
⛔ **The sentence the code says is missing.** A situation held at `qes_required` must be able to say
**"its best evidence scored 1360 against a floor of 2500"** — the number exists, `l1_refusal()`
already fetches it, and nothing renders it.

That single sentence turns *"nothing happened"* into *"here is exactly why, and here is the
threshold you could change."*

```
verify:  pytest tests/context/test_a_held_situation_names_its_score.py -q
```

### L2-0-U2 · `UNROUTED` in the pass tallies
Shared with L2-4-U1. A domain that routes nowhere is **counted with its name**, never a `None` that
disappears.

### L2-0-U3 · The refusal ledger is durable
A row per refusal: situation, reason, threshold, the value that missed it, `eval_time`. **Durable,
because the question arrives days later** — *"why didn't GeniOS tell me?"* is never asked during the
sweep.

### L2-0-U4 · A sixth-time guard
⛔ The code says this is the **fifth** time a right-but-invisible refusal shipped. Add the check that
makes a sixth harder: **every `HoldReason` and every refusal path must appear in the report**, proven
by a totality test over the enum — the same idiom as `PRECEDENCE` and `ANCHOR_FAMILIES`.

```
verify:  pytest tests/context/test_every_hold_reason_is_reported.py -q
```

---

## 4. Cost check

| | |
|---|---|
| model calls | **none** |
| migration | none — one table for the ledger, or reuse `situation_admission_decisions` |
| runtime | a report, run on demand |

---

## 5. What this step does NOT do

* **It does not lower the floor.** 2500 stands. *"The refusal is correct"* — the code is right and
  this step agrees with it.
* **It does not admit anything.** It explains what was refused and why.
* **It does not build a dashboard.** One script, one output, readable in a terminal.

---

## 6. Completion criteria

| # | criterion | verdict |
|---|---|---|
| 1 | One report naming every refusal path with counts, run against the pilot and **written into findings** | ⚠️ **HALF.** The report is built and the **corpus section runs today** (§2 of findings). The three database sections replay the pilot's *measured shape* through the real code — a live read is **Harsh item 1** |
| 2 | A held situation can state its score against its floor | ✅ `ScoredRefusal.sentence` — *"its best evidence scored 1360 against a floor of 2500"*, and an unscored one **says it was never scored** rather than rendering `None` as zero |
| 3 | `UNROUTED` counted with its domain | ✅ `context/domain_silence.DARK_DOMAINS` — declared, with a reason and an **ENDS WHEN**, checked in both directions |
| 4 | The ledger is durable and survives the sweep | ✅ **already true before this step.** `situation_admission_decisions` carries `outcome`, `reasons`, the candidate's bytes and `reevaluate_after`. Nothing was built; the premise check found it |
| 5 | A totality test refuses a new `HoldReason` that no surface reports | ✅ `_reason_table()` is built **from the enum**. The same guard was added for the corpus: `canonical_admission_reason()` **raises** on an undeclared reason rather than bucketing it as "other" |

**Four closed, one half-closed, and the open half is a database rather than a design.**

### 6.1 · What the units actually became

| planned | built |
|---|---|
| U0 · one report | `context/quality/refusals.py` + `scripts/l2_refusal_report.py` |
| U1 · a held situation states its number | `ScoredRefusal` — **the number already existed**, `l1_refusal()` returns it |
| U2 · `UNROUTED` in the tallies | `domain_silence.DARK_DOMAINS` |
| U3 · a durable ledger | **struck — already built.** `situation_admission_decisions` |
| U4 · a sixth-time guard | `_reason_table()` from `HoldReason`, **and** `ADMISSION_REASONS` from the compiler's rule |
| — | **U5, unplanned: `corpus_health()`.** The refusal path nobody was counting, the one whose number was wrong, and the one that found the 24 `draft` situations |

---

## 7. Why this is first

Every later step claims a number: *situations reasoned*, *cards collapsed*, *domains routed*.
**Without this step none of those numbers has a denominator**, and the plan would measure its own
progress against an unknown. L1 learned that in step 11 and never measured blind again.
