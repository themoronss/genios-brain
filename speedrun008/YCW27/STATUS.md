# STATUS — where the whole programme stands

**One page. Read this first, always.** Updated **2026-10-02**.

> ⛔ **THIS HEAD WAS STALE FOR TWO DAYS AND IT IS THE "READ THIS FIRST" PAGE.** It said
> `Updated 2026-09-30` and `EVERY SECTION IS BUILT · L5 ✅ · L6 ✅` while ~1,000 lines of
> re-measurement were appended below it, L5 took **17** steps rather than 4, and L6 was
> **re-opened**. ⛔ The detail below is an append-only log and stays chronological; **this head
> carries the reverse-chronological index**, so a reader never has to scroll 2,800 lines to learn
> what is true. *A status line is read as current whether or not it is.*

---

## ⛔ NEWEST FIRST — the reverse-chronological index

| When | What | Where |
|---|---|---|
| **2026-10-04** | ⛔⛔ **`3.1b` DONE — the hop was the small part. `delete from X` was being counted as a READ of X.** `_VERBS["read"]` was `(?:from|join) (…)` and `delete from cards` contains `from cards` — latent since the module existed, and ⛔ **the loop hop amplified it 102-fold** through the tenant erasure loop, so **four tables stopped being reported write-only** and four correct declarations were about to be retired. ✅ Caught by the before/after comparison the plan committed to in writing. Fixing it removed **139 spurious read facts across 106 tables** and ⛔ **five tables lost their ONLY read attribution — `macv_ledger` among them**, which mechanically proves what `19-PENDING` records. ⛔ `written_and_unread` stayed **9 → 9 while its MEMBERSHIP turned over** | [`34-AUDIT-step-3.1b-a-delete-is-not-a-read.md`](34-AUDIT-step-3.1b-a-delete-is-not-a-read.md) |
| **2026-10-04** | ⛔⛔ **`3.1` DONE — the number this step was scoped around was the WRONG NUMBER.** Of **645** *"unresolved SQL statements"*, only **49 (7%)** had a hole where a TABLE belongs; **596 (92%)** were predicates and column lists built from shared fragment constants — ⛔ **and 17 of those were our own `_org_filter`.** ⛔⛔ **Three more were this module's own regexes: the observer was counting its instrument.** Three resolver hops took the table figure **49 → 16**, all 16 now declared with a category. ⛔ The ratchet the plan credits *did* exist — `unresolved/statements <= 0.30` against a 22.4% actual, **about 220 statements of headroom**, which is how 639 became 645 unnoticed. ⛔ Every dependent finding captured before and after: **16 attributions recovered, 0 verdicts moved** | [`32-AUDIT-step-3.1-the-number-that-was-the-wrong-number.md`](32-AUDIT-step-3.1-the-number-that-was-the-wrong-number.md) |
| **2026-10-04** | ⛔⛔ **`2.2` DONE — Atlas L1 settled, and TWO SCORECARD ROWS CARRIED FALSE EVIDENCE.** ⛔ `L1-08`'s said *"zero declare a visibility field"* — **all three declare one**; optional is not absent. ✅ Its consequence is closed at **four layers** (derive → **gate PARKS** → re-drain STILL_BLOCKED → 5 of 6 columns NOT NULL). ⛔ The finding is **five readers in `context/` that treat a missing audience as permitted or org-wide**, safe only by that chain and declared nowhere — found by AST; grep found 5 of 8 sites. ⛔⛔ `L1-09` led to **five of `GatedEvent`'s 21 fields carried and read by nothing**, worst `degraded_compile`, whose own comment calls this defect FIXED while L2 reads the stored signal, which has no column for it. ⛔ `L1-01`'s number was **7, and it is 9**. ⛔⛔ **And three of my own guards had holes only mutation found** — including a declaration that satisfied the test that its own source exists | [`30-AUDIT-step-2.2-atlas-layer-1.md`](30-AUDIT-step-2.2-atlas-layer-1.md) |
| **2026-10-03** | ⛔⛔ **`2.1` DONE — Atlas L2's nine claims settled, and the two nobody had located are now receipts.** ⛔⛔ **L2-11**: `expertise.py:1463` takes `domain_ids[0]` out of a `tuple(sorted(set))`, so the **alphabetically first** domain becomes `CapabilityManifest.domain` and `domain_shadow.py:1169` uses it to pick **which tenant pack the reasoning reads** — nothing records the choice while the package's own citation tags carry every domain. ⛔⛔ **L2-01**: `graph_facts.authority_rank` carries **two scales** — the dense 0..6 ladder and `DEFAULT_AUTHORITY_RANK = 100`, same column — and `fact_write_action` compares raw integers, so a row at 100 is unsupersedable and a **signed document** arriving against one is returned a `discrepancy` and dropped. ✅ **L2-03 was simply WRONG** and is closed in code both ways. ⛔ **Eleven corrections, nine to my own first reading**, including a declaration that **falsified its own count** | [`28-AUDIT-step-2.1-atlas-layer-2-nine-claims.md`](28-AUDIT-step-2.1-atlas-layer-2-nine-claims.md) |
| **2026-10-03** | ⛔⛔ **`1.4 capture/` DONE — PHASE 1 CLOSED, and *"why did I never see X?"* is now a receipt.** `capture/journey.py` was built for one sentence — *a system that discards 92% of what a founder was sent has to be able to answer "why did I never see X?" in one query* — and records that *"every layer wrote its refusal down. **Nothing ever joined them.**"* ✅ The join is reachable; ⛔ **nothing checked that every event HAS an answer.** **Receipt 44**, five derivations and nothing spelled: stopping actions from `TRACE_STOPPING`, event-keyed ledgers from `_LEDGERS` minus `_PER_SIGNAL_LEDGERS`, horizon from 4 sweep ticks. ⛔ Two mutations survived, **both about EMPTINESS** — an empty set made a loop assertion vacuous | [`26-AUDIT-capture-why-did-i-never-see-this-one.md`](26-AUDIT-capture-why-did-i-never-see-this-one.md) |
| **2026-10-03** | ⛔⛔ **`1.3b` DONE — and one of the two untested modules was guarding HEALTH INFORMATION.** `reason/team/away.py` promises in its own docstring *"no leave reason ever leaves this module — the `sick` kind is reported as `leave`"*, and **nothing asserted it**: one line changed, or one new kind unmapped, and every seat learns why a colleague is off. ⛔ `api/identity_routes.py`'s node-set gate is the only thing stopping a human merging two nodes **no proposal names** — a rewrite of every fact and edge about them. ⛔ The test asserts the merge **did not happen**, not that a 422 came back: moving the merge above the gate fails four tests while still returning 422. 32 tests · **17/17 mutations** | [`25-STEP-1.3b-two-untested-modules-and-one-was-health-data.md`](25-STEP-1.3b-two-untested-modules-and-one-was-health-data.md) |
| **2026-10-03** | ⛔⛔ **`reason/` AUDIT DONE — 20 candidates, 20 RETIRED, 0 receipts, and the finding was in the AUDIT'S OWN MEASUREMENT.** ⛔ Every derivable claim was already enforced: `signals`' *"byte-identical bindings"* is a partial unique index · 16 of 23 reasoning units ARE exercised by `parametrize(ALL_UNITS)` · a suppression log IS read by `executive/explain`. ⛔⛔ **The *"no test names it"* column was wrong 19 of 33 times across three audits, six repairs each over-corrected the other way, and the guard written FOR it named two functions in its own docstring — making the module it asserted was untested read as named. DELETED**, with the reasoning in every page and a guard against all six heuristics returning | [`24-AUDIT-reason-the-column-that-had-to-go.md`](24-AUDIT-reason-the-column-that-had-to-go.md) |
| **2026-10-03** | ⛔⛔ **`platform/` AUDIT DONE — 15 candidates, 15 RETIRED, and the survivor is a park the health check EXCLUDES BY CONSTRUCTION.** `warm_lane` sets `parked_at` for a row whose attempts ran out — the schema says *"parked for a human"* — and every reader uses the column only as an exclusion: `_OPEN`, the backlog count, the staleness warning. ⛔⛔ **Nothing selects a parked row, the prune never removes one, so a stuck tenant reports a CLEAN lane and the invisible set grows.** Receipt **43**, predicate DERIVED from `warm_lane._OPEN`. ⛔ Fifteenth retirement was mine, five minutes old: Atlas `L2-02` is **declared** in `LINEAGE_UNPROTECTED`, and its mover — *"the third connector"* — is now a one-line query (`H8.5`) | [`23-AUDIT-platform-the-park-the-health-check-excludes.md`](23-AUDIT-platform-the-park-the-health-check-excludes.md) |
| **2026-10-03** | ⛔⛔ **`api/` AUDIT DONE — 11 candidates raised, 11 RETIRED, and the one finding was never guarded.** ⛔ Every candidate died on reading the code or the declaration beside it: `decisions` is written by the route that **returned** the envelope · `approvals_queue` and `policy_routes.evaluate` are **already declared** (*"the policy enforcement path does not exist"*) · `api/learning_routes` only updates `state`. ⛔⛔ **Two of the three columns I called `api/` worst on were my own mis-signal** — 25 route handlers are decorator-excluded by design. ✅ The survivor: **`learning_objects` is write-once except `state` and NOTHING asserted it** — `publisher.persist`'s own first line says *"Insert an **immutable** proposal"*. 22 tests · 10/10 mutations | [`22-AUDIT-api-eleven-candidates-eleven-retirements.md`](22-AUDIT-api-eleven-candidates-eleven-retirements.md) |
| **2026-10-03** | ⛔⛔ **THE PLAN TO PRODUCTION, AND THE AUDIT OF ALL ELEVEN PACKAGES.** ⛔ The crux measured: everything is **built**, almost nothing is **live**, and the three things between them are **`H1` migrations · `R1` the spend limit · `R2` activation** — **none of them mine**. ⛔⛔ `api/` is the least-guarded package in the product on THREE columns at once (19,498 lines · 28 unreceipted tables · 2 declared silences · 11 modules no test names), and it never appeared in `S7`'s ranking because a ratio with a zero denominator does not sort. ✅ The original brief's eight VERIFIED-MISSING items are **closed** — 7 built, 1 declared unnecessary. Seven checkable conditions now define *production level*, and ⛔ **by them nothing in the product qualifies today** | [`21-PLAN-TO-PRODUCTION.md`](21-PLAN-TO-PRODUCTION.md) |
| **2026-10-02** | ⛔⛔ **L3 `context/` COVERAGE AUDIT DONE — and it retracted SIX of its own findings.** `S7`'s number put `context/` last (2 receipts / 50,885 lines); ⛔ the headline was **wrong** — 306 test files import it and both receipts are correctness ones. The real gap is that nothing checks the **44 tables it writes** in production. ⛔⛔ The largest retraction: **77 org-scoped tables that read as a data-retention hole and are not one** — `/reset` deliberately keeps the account, and ACCOUNT erasure is foreign keys plus an existing receipt. **9 write-only tables declared · receipt 42 (merge) · 37 tests · 11/11 mutations** | [`layer-3-context-graph/04-AUDIT-PLAN-the-worst-covered-package.md`](layer-3-context-graph/04-AUDIT-PLAN-the-worst-covered-package.md) |
| **2026-10-02** | ⛔⛔ **L6 `S10` DONE — `M14.C2` IS COMPLETE, 10 of 10.** The three gaps nobody had measured. ⛔⛔ **0 of 11 Atlas Layer 7 gaps now unmeasured — and none of the three became CLOSED**: each has one clause left and all three are Rohit's. ⛔⛔ `#3`'s real finding is a TRAP — `recommendation_learning`'s durable ADAPTIVE path is unreachable by **arithmetic**, and the obvious repair springs it. ⛔ `#5`'s enforcement is **proven**; the rendered surface is **unreached**. ⛔ `#6`'s reset **propagates into delivery**, uncredited by the Atlas. **4 of my own guards needed repair.** 69 tests · 27/27 mutations | [`layer-6-learning/STEP-S10-DONE-the-three-unmeasured-gaps.md`](layer-6-learning/STEP-S10-DONE-the-three-unmeasured-gaps.md) |
| **2026-10-02** | ⛔⛔ **L6 `S9` DONE — and a finding of mine is RETRACTED.** `F17` called `MOVES WITH` a convention deviation; measured, it is in **nine of thirteen** declaration modules (29 vs 115). ⛔ The gate stopped me tightening a guard onto **29 correct entries**, and the mutation proves it: narrowing the form fails **9 modules**. The 104 absence guards got **the rule, not 78 rewrites**. +10 tests · 2/2 mutations | [`layer-6-learning/STEP-S9-DONE-the-paperwork-and-a-finding-of-mine-refuted.md`](layer-6-learning/STEP-S9-DONE-the-paperwork-and-a-finding-of-mine-refuted.md) |
| **2026-10-02** | ⛔⛔ **L6 `S8` DONE — the scorecard reaches the learning layer.** `08-ATLAS-SCORECARD-L1-to-L5` → **`-L1-to-L6`**, 45 → **56** claims. **4 EXPIRED · 4 PARTLY · 3 still true** — and ⛔ **four cells hid a defect the Atlas did not name**, three of them under badges that read as reassuring. 21 tests · 2/2 mutations | [`layer-6-learning/STEP-S8-DONE-the-scorecard-reaches-the-learning-layer.md`](layer-6-learning/STEP-S8-DONE-the-scorecard-reaches-the-learning-layer.md) |
| **2026-10-02** | ⛔⛔ **L6 `S7` DONE — the count becomes data, and it points at `context/`.** Guards per package is declared and guarded both ways; derived, **`context/` is 50,877 lines with TWO guards** — 5.4x worse than the figure that triggered `STEP-10`. Plus a quarantined seam read as an empty one (`L7-29`), and the delivery seam reported degraded on **every run**. 20 + 55 tests · 9/9 + 8/8 mutations | [`layer-6-learning/STEP-S7-DONE-the-count-becomes-data-and-a-lost-seam-gets-a-name.md`](layer-6-learning/STEP-S7-DONE-the-count-becomes-data-and-a-lost-seam-gets-a-name.md) |
| **2026-10-02** | ⛔⛔ **L6 `S6` DONE — an illegal lifecycle edge, on every brain publish.** `publisher.publish` wrote `governed → published`, which `ALLOWED_LEARNING_TRANSITIONS` forbids, into the one ledger nothing reads. Plus the Atlas's **no-silent-drop contract**, broken in nine lines. ⛔ **`U03` un-retracted.** 46 tests · 9/9 mutations | [`layer-6-learning/STEP-S6-DONE-no-silent-drop-and-an-illegal-edge.md`](layer-6-learning/STEP-S6-DONE-no-silent-drop-and-an-illegal-edge.md) |
| **2026-10-02** | ⛔⛔ **L6 `S5` DONE — the inbox landed and nothing consumes it.** `learning_event_inbox` is **written in production**, loaded into every weekly batch, and **read by no unit** — the rows are counted as `inbox_unconsumed` and dropped. ⛔ **The gap is a `kind`, not a table.** Plus the layer's **first CORRECTNESS receipt**. 27 tests · 8/8 mutations | [`layer-6-learning/STEP-S5-DONE-...md`](layer-6-learning/STEP-S5-DONE-the-inbox-landed-and-nothing-consumes-it.md) |
| **2026-10-02** | ⛔⛔ **L6 `S4` DONE — the Atlas's only LIVE gap was a wrong conclusion.** *"Direct personalization evolution is missing"* — both components are **built one package down** (`packs/brains/behavior_distill` 776 lines, `adaptive_lease` 301) and appended to the same weekly run. ⛔ **The stub outlived its replacement by a month.** 23 tests · 8/8 mutations | [`layer-6-learning/STEP-S4-DONE-...md`](layer-6-learning/STEP-S4-DONE-a-silent-unit-names-its-producer.md) |
| **2026-10-02** | ⛔⛔ **L6 `S3` DONE — a fail-OPEN on an authority list.** A tenant's *"never learn about these targets"* list that failed to read was indistinguishable from *"nothing is blocked"*, and `preflight` returned **`admitted`**. **Atlas gap #10 CLOSED.** 40 tests · 8/8 mutations | [`layer-6-learning/STEP-S3-DONE-...md`](layer-6-learning/STEP-S3-DONE-a-policy-that-did-not-load-may-not-learn.md) |
| **2026-10-02** | ⛔⛔ **L6 `S2` DONE — the North Star ledger has never had a writer.** `macv_ledger` (*"the number the customer can verify"*) appears 5× repo-wide and **the only code that touches it deletes it.** 18 tests · 6/6 mutations | [`layer-6-learning/STEP-S2-DONE-the-north-star-has-no-writer.md`](layer-6-learning/STEP-S2-DONE-the-north-star-has-no-writer.md) |
| **2026-10-02** | ⛔ **L6 `S1` DONE — a unit may not write a durable brain from a measurement.** `unit_recommendation_learning` publishes `efficacy_bp` into durable `ADAPTIVE`, auto-promoted, and the pack compiler reads it back — the Atlas's *"no self-training from recommendation score."* 27 tests · 4/4 mutations | [`layer-6-learning/STEP-S1-DONE-a-measurement-into-a-durable-brain.md`](layer-6-learning/STEP-S1-DONE-a-measurement-into-a-durable-brain.md) |
| **2026-10-02** | ⛔ **L6 ATLAS CHECK — 11 gaps verified claim by claim.** 3 CLOSED · 4 PARTLY · 1 LIVE · 3 unmeasured. ⛔ **It retracted three of my own planned units** | [`layer-6-learning/07-ATLAS-CHECK-...md`](layer-6-learning/07-ATLAS-CHECK-layer-7-learning-claim-by-claim.md) → [`08-PLAN-v2`](layer-6-learning/08-PLAN-v2-from-the-atlas.md) |
| **2026-10-02** | ⛔ **L6 RE-CROSSCHECK — the loop runs, and is never questioned.** 4 receipts, **all four presence checks**; 4 ledgers nobody reads. `F9`–`F22` | [`layer-6-learning/05-RECROSSCHECK-...md`](layer-6-learning/05-RECROSSCHECK-the-loop-that-runs-and-is-never-questioned.md) |
| **2026-10-02** | ⛔ **CORRECTION on L5 `STEP-10` — a receipt label is not a package.** `deliver/` carried **5** receipts and **4 working**, not 2 and 1. 11 documents marked in place | [`layer-5-delivery/08-CORRECTION-...md`](layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md) |
| **2026-10-01** | **L5 `STEP-17` — every package says what it does not call.** 10 declaration modules, 109 entries, ONE guard over eleven packages | [`layer-5-delivery/STEP-17-DONE-...md`](layer-5-delivery/STEP-17-DONE-nine-packages-nobody-asked.md) |
| **2026-10-01** | **L5 CLOSED — 15 steps DONE, 1 WITHDRAWN** | [`layer-5-delivery/00-START-HERE.md`](layer-5-delivery/00-START-HERE.md) |
| — | **every remaining item, by owner — one page** | [`19-PENDING-who-owns-what.md`](19-PENDING-who-owns-what.md) |

```
full suite   15,220 passed · 1,067 skipped · 152 xfailed · 0 failed      (14,534 when YCW27 began)
⛔ built≠live  5 migrations unapplied · no domain activated · no card since 25 Sep 11:09 UTC
⛔ coverage    141 of 183 written tables have NO receipt · api/ leads it (28 of 42)
✅ api/        AUDITED 2026-10-03 · ⛔ 11 candidates, 11 retirements · write-once guard added
✅ platform/   AUDITED 2026-10-03 · ⛔ 15 candidates, 15 retirements · receipt 43 · 1 → 2 receipts
✅ reason/     AUDITED 2026-10-03 · ⛔ 20 candidates, 20 retirements, 0 receipts — and the
             audit's own naming column DELETED for being wrong 19 of 33 times
✅ 1.3b        DONE 2026-10-03 · ⛔ a health-data privacy transformation had no test
✅ PHASE 1      CLOSED 2026-10-03 · 5 steps · ⛔ 52 candidates raised, 52 retired · 3 receipts
✅ PHASE 2      2.1 DONE · ⛔ 0 unmeasured L2 claims left on my side
⛔ 2.3 BLOCKED   needs Phase 0 live — Rohit's and Harsh's
⛔ next up     3.2 the always-green receipts
L6 M14.C2    ⛔⛔ COMPLETE — 10 of 10 DONE · 0 failed at every step
Atlas L7     11 gaps: 5 CLOSED · 6 PARTLY · ⛔ 0 LIVE · ⛔⛔ 0 UNMEASURED
scorecard    08-ATLAS-SCORECARD-L1-to-L6.md · ⛔ 56 Atlas claims verified or refuted
receipts     35 → 48 · ⛔ feedback/ 0 → 6 correctness · context/ 2 → 3 · platform/ 1 → 2 · capture/ 5 → 9 · reason/ 8 → 9
unresolved_table  49 → 16 (3.1) → 7 (3.1b) · ceiling absolute, slack 0
ledgers      ⛔ unread of F11's four: 4 → 1 — asking them found FOUR live defects
✅ coverage   context/ AUDITED 2026-10-02 · ⛔ 306 test files import it — the gap was RECEIPTS,
             not tests. 2 → 3 receipts · 9 write-only tables declared engine-wide
⛔ next up    api/ — 19,498 lines, 42 tables written, ZERO receipts. It never appeared in
             S7's ranking: a ratio with a zero denominator does not sort
```

---

## ⛔ WHICH LAYER ARE WE ON? — the one-line answer

> ⛔ **EVERY SECTION IS BUILT — and "built" is not "measured".**
> L1 ✅ · L3 ✅ · L2 S1–S4 ✅ · **S6 Plane D ✅** · **S5 Plane R ✅** · L4 ✅ · L5 ✅ · L6 ✅
>
> ⛔ **RE-OPENED AND RE-MEASURED SINCE:** **L5** said `COMPLETE` and took **17** steps (14 findings);
> **L6** said `COMPLETE` and is now `M14.C2` — **10 units, 2 DONE, `S3` next.** Both passes found
> the same shape: *the layer ran, and nothing asked whether what it wrote was right.*
>
> **What remains besides `M14.C2`: 3 activation decisions, 5 unapplied migrations, and review** —
> plus ⛔ **two new product decisions for Rohit** (the Adaptive durable path; the MACV writer).
> See [`19-PENDING-who-owns-what.md`](19-PENDING-who-owns-what.md), which is the live list.

### Why the numbers look backwards

The product layer **numbers do not follow the data flow.** We build in data-flow order:

```
data flows:   L1 capture ──▶ L3 context ──▶ L2 reason ──▶ L4 exec ──▶ L5 deliver ──▶ L6 learn
we build:     M9         ──▶ M10        ──▶ M11       ──▶ M12     ──▶ M13        ──▶ M14
done?         ✅ built      ✅ built       ✅ S1–S4      ✅ built    ✅ built      ✅ built
                                          ⏸ S5, S6 yours
```

So *"layer 1, then layer 3, then layer 2"* is correct and deliberate — **nothing above can be fed
better than the layer below hands up.** Recorded in `tree.yaml` as `requested_order`.

> **From here on, "next layer" means next in the DATA FLOW, never next number.**

---

## The whole programme at a glance

| | Layer | Package | Milestone | Units | Built | Left | Docs |
|---|---|---|---|---|---|---|---|
| 1 | Enterprise Signals | `capture/` | M9 | **10** | 10 ✅ | 0 *(3 pending are not code)* | 5 + 10 steps |
| 2 | **Reasoning** | `reason/` + `packs/` | **M11** | **33** | 27 ✅ + 3 ⛔ | **0** | 7 + 14 steps |
| 3 | Context Graph | `context/` | M10 | **5** | 4 ✅ + 1 ⛔ withdrawn | **0** | 5 + 5 steps |
| 4 | Executive | `executive/` | M12 | **4** | 4 ✅ | **0** | 5 + 4 steps |
| 5 | Delivery | `deliver/` | M13 | **4** → ⛔ **+17** | 4 ✅ + **15 ✅** *(1 withdrawn)* | **0** *(1 is Harsh's)* | 8 + 17 steps |
| 6 | Learning | `feedback/` | M14 → ⛔ **M14.C2** | **3** → ⛔ **+10** | 3 ✅ + **2 ✅** | ⛔ **8** | 9 + 5 steps |

**Code written this session:** 17 new modules + **26 new corpus files**, 3 migrations, 37 files
modified, **~926 new tests.** Full suite **14,397 passed / 1 failed** (the 1 is L1's known
`pytesseract`-missing test, which fails on any machine without the binding).

> ⛔ **CORRECTED 2026-10-02 — that paragraph is a snapshot of 2026-09-30, not of today.** The suite
> is **14,891 passed · 0 failed**, and L5's 17 steps plus L6's `M14.C2` landed after it was written.
> It is left in place because the log is append-only; the current numbers are in the
> reverse-chronological index at the top of this page. *A paragraph that says "this session" has no
> date in it, and reads as today for as long as nobody checks.*

⛔ **Corrections 12 and 13 are on MY OWN cross-check**, not the programme's plan — both caught by
continuing to measure while building, and both recorded as appended retractions rather than edited in
place. #13's cause is the sharpest lesson so far: **a stale comment is more dangerous than no comment,
because it reads as a measurement somebody already took.**

⛔ **NINETEEN corrections to the programme's own planning documents**, every one from reading code or
running a query *before* writing anything:

| # | Layer | The document said | The code said |
|---|---|---|---|
| 1 | L1 | `no_model_wired` is broken wiring | one lane is model-free **on purpose** |
| 2 | L3 | nothing guards the graph revision | `reason/runner.py:570` is the guard |
| 3 | L2 | plan compile should fail on an unproduced source | it did — **six units to one absent fact** |
| 4 | L2 | the skip receipt needs building | it was already built |
| 5 | L2 | `core.risk` never fires | it does |
| 6 | L2 | Plane D is not in scope | it is where the routing lives |
| 7 | L2 | the lane belongs in `decision_hash` | it is **derived** — zero information, four broken replays |
| 8 | L4 | never read `manager_seat_id` | it is the **standing line** the dated override sits on |
| 9 | **L5** | replace the scalar publication floor | **there is none in `deliver/`** — the gate is in `reason/` and its receipt is already read |
| 10 | **L6** | make a timing complaint stop lowering precision | **it already does not**, in three places, one going further than asked |
| 11 | **Plane D** | the unrouted types need a runtime counter | **they have one** — missing its DIMENSION, and a FOURTH cause was being mis-reported |
| 12 | **Plane D** | `unrouted_l2_types` is hand-kept | ⛔ **my own cross-check was wrong** — `index.py:205` generates it |
| 13 | **Plane D** | a draft situation may not compile a card | ⛔ **my own cross-check was wrong** — already built, 15 tests. **I believed a stale corpus comment** |
| 14 | **Plane D** | 13 Admin objects are missing | **9** — my regex truncated three hyphenated ids that were already authored. `domain.yaml`'s roster is authoritative |
| 15 | **Plane D** | `unrouted_l2_types` is hand-kept | `_tools/index.py:205` generates it — *(same as #12, found twice from different angles)* |
| 16 | **Plane R** | a guard is waiting for declarations | ⛔ **the guard RUNS on every registration and validated ZERO** — nothing needed wiring |
| 17 | **Plane R** | *"the two `AXIS_SOURCES` units"* | there is **one** |
| 18 | **Plane R** | *"`source_units` on `legacy.score_gate`"* | it reads **no source at all** |
| 19 | **Atlas dossier** | 8 claims about the reasoning layer, audited 2026-08-22 | ⛔ **5 of 8 STALE** — corrected in `Rohit_Updates/.../04-Layer-4-Reasoning/00-CORRECTIONS-2026-10-01.md` |

**Nothing committed. Nothing deployed.**

---
---

# LAYER 1 — `capture/` — ✅ our work is DONE

**9 steps. 6 done by us. 3 pending, and not one of them is code in this repo.**

| # | Step | Status | Owner | Blocks build? |
|---|---|---|---|---|
| 1 | Relevance judgment | ✅ DONE — no defect; probe built | us | — |
| 2 | `temperature` on refusing models | ✅ DONE — 600 calls that never worked | us | — |
| 3 | Provider-refusal alert | ✅ DONE — a 5-day outage was invisible, twice | us | — |
| 4 | **API spend limit** | ⏳ **PENDING** | **Rohit** | ❌ no — blocks *measurement* |
| 5 | Where the four objects live | ✅ DONE — rule + 4 guards | us | — |
| 6 | The signal bundle | ✅ DONE — 5 units | us | — |
| 7 | The evidence-need door | ✅ DONE — 4 units | us | — |
| 8 | **OCR has never run** | ⏳ **PENDING** | **Harsh** | ❌ no |
| 9 | **The 60-day window** | ⏳ **PENDING** | **Harsh** | ❌ no |

**139 tests.** Files: `00-START-HERE` · `01-CROSSCHECK` · `02-PLAN` (328 lines) · `03-FINDINGS` ·
`10-LAYER-REFERENCE` · 9 STEP files · `findings/` (3 probes).

### ⛔ What is NOT done in Layer 1, stated plainly

| # | Left | Whose | Why it is not ours |
|---|---|---|---|
| 1 | Raise the Anthropic spend limit | Rohit | a setting on the account. No code in this repo can move it |
| 2 | Deploy from the Dockerfile so OCR runs | Harsh | the fix is a deploy, not a change |
| 3 | Backfill 60 → 365 days | Harsh | an ops run. Migration `0184` is already applied |
| 4 | Wire the executor's `fetchers` to real connectors | Harsh | needs live connector credentials |
| 5 | Re-base the parity gate (100 of 66 is unreachable) | Rohit | a target nobody can hit is not a gate |

⛔ **The consequence of #1, and it is the biggest single caveat in this programme:** since
**2026-09-25 11:09 UTC** every model call has been refused. **Every production number taken since
then — including Harsh's shadow-pass tallies — was taken with the model off.**

---
---

# LAYER 3 — `context/` — ✅ COMPLETE

**5 steps. 4 built, 1 withdrawn because the finding behind it was wrong. 0 left.**

| # | Step | Status | Tests |
|---|---|---|---|
| 1 | The bounded query API | ✅ **DONE** | 22 |
| 2 | Compare-and-set on write | ⛔ **WITHDRAWN** — already built | — |
| 3 | A hold that asks | ✅ **DONE** | 27 |
| 4 | A met need clears its hold | ✅ **DONE** | 22 |
| 5 | Residue reaches the sweep | ✅ **DONE** — and wired | 20 |

**91 tests. `tests/context` whole: 2,679 passed, 0 failed.**

### What Layer 3 can now do that it could not

| | Before | After |
|---|---|---|
| ask the graph a bounded question | ❌ whole tenant only | ✅ seeds, hops, node cap, edge types |
| know a read was cut short | ❌ silently partial | ✅ `truncated_by` names the cap |
| turn a hold into a question | ❌ the reason went to a ledger and stopped | ✅ `hold_needs.py` |
| act on an answered question | ❌ nothing read the outcome | ✅ 4 dispositions |
| file a question at all | ❌ nothing persisted a need | ✅ called by the sweep |

### ⛔ What is NOT done in Layer 3 — the loop is HALF-CLOSED

```
residue ──▶ need ──▶ [ evidence_needs table ] ──▶  ???
   ✅         ✅            ✅ written             ❌ nothing works them
```

| # | Left | Whose |
|---|---|---|
| 1 | Apply `migrations/0187_evidence_needs.sql` — **never run in production** | Harsh |
| 2 | The executor pass: `read_open_needs` → `execute` → `close_need` | Harsh — needs real `fetchers` |
| 3 | Wire `hold_needs` into the publisher — **needs a decision first** (inside the publication transaction, or a later pass reading the ledger; the second is safer) | Rohit / Harsh |

⛔ **So today the queue is write-only.** Every filed need stays `open`, so `resolve_hold` returns
`keep_waiting` for all of them. **Nothing regresses** — situations hold today anyway — but
**`evidence_needs_filed > 0` must NOT be read as "something is being fetched."**

---
---

# LAYER 2 — `reason/` + `packs/` — 📋 PLANNED, NO CODE

**This is where we are. 48,022 lines — the second-largest surface in the product.**

**⛔ 18 units across 7 sections. 10 BUILT, 1 retired, 7 left — and the 7 are BOTH PLANES ONLY.**

⛔ **Everything except Plane R (S5) and Plane D (S6) is built.** On Rohit's instruction the two planes
are last and will be done unit by unit together. **264 new tests** across S1–S4.

⛔ **The count went 11 → 18** after Plane R and Plane D were measured. The plan's first draft had
written both out of scope saying *"nothing in the cross-check found a defect there"* — it had not
looked. Each has one, and the Plane R defect is the sharpest thing in the layer: **23 units, zero
declare what they read**, while `registry.py:49` exists specifically to check that.

👉 **Full list: [`layer-2-reasoning/04-STEPS.md`](layer-2-reasoning/04-STEPS.md)**

⛔ **S1's first unit is done and it did what S1 exists for: it destroyed a claim.**
`scripts/l2_unit_silence.py` measured production read-only and found `core.risk` is **one** unit (not
three plugins) which completed **1,165 of 1,165** — zero silent. The sentence `M11.C1` was built on
describes a structure this codebase does not have. See
[`layer-2-reasoning/STEP-01-DONE-prove-the-claims.md`](layer-2-reasoning/STEP-01-DONE-prove-the-claims.md).

| | Section | Units | What | Blocked? |
|---|---|---|---|---|
| **S1** | Prove the claims before changing anything | **2** | ✅ **COMPLETE** — 1 done, 1 **retired** | — |
| **S2** | A kept unit that lost a source says so | **3** | ✅ **DONE** · 38 tests · a receipt, never a refusal | — |
| **S3** | The five output lanes + router | **4** | new vocabulary | needs S4 |
| **S4** | The five pipeline counters | **2** | ✅ **DONE** · 42 tests · ⛔ `signals_detected` refused rather than faked | — |
| **S3** | The five output lanes + router | **4** | ✅ **DONE** · 170 tests · totality both directions | — |
| **S5** | ⛔ **Plane R — the unit contract** | **3** | 23 units, **0 declare what they read** | ⬜ **NEXT — unit by unit with Rohit** |
| **S6** | ⛔ **Plane D — routing + draft corpus** | **4** | 155 capabilities, 23 draft situations, 5 unrouted types | ❌ no |
| **S7** | The ConfidenceVector axes | **0** | ⛔ **Rohit's decision.** Blocks M13, not M11 | ⛔ yes |

**Files written:** `00-START-HERE` (87) · `01-CROSSCHECK` (354) · `02-PLAN` (451) · `README` (100).
**No STEP files yet** — those get written as each step is built, the same as L1 and L3.

### ⛔ The headline: 2 of the 4 specified units were WRONG

| `03-PROGRAM.md` said | Verdict | What the plan does |
|---|---|---|
| plan compile **fails** when a scheduled unit names an unproduced source | ⛔ **REGRESSION.** `plan.py:229` records removing exactly this rule — *"six units lost to one absent fact"* | **rewritten as a receipt** |
| a dropped unit leaves a `SkippedStep` naming its missing input | ✅ **already built** — `plan.py:258` | **verify, don't build** |
| *"two of `core.risk`'s three plugins are silent — the live defect"* | ⛔ **UNVERIFIED.** No source anywhere; unmeasurable while the API limit is on | **measure or withdraw, first** |
| the five output lanes + router | ✅ **stands** — `"investigation"` = 0 hits | build it |

**One addition found:** the five pipeline counters do not exist (**0 hits** for all five). Without a
funnel, *"we made 28 cards"* cannot be told apart from *"28 out of 4,000, and 3,900 died somewhere
nobody can name."*

### What is left in Layer 2 — all 11 units

| Section | Unit | What |
|---|---|---|
| S1 | `M11.C0.U01` | ✅ **DONE** — the claim is false, and no unit silence is attributable yet |
| S1 | `M11.C1.U02` | ⛔ **RETIRED** — the code AND a passing test already existed. No code, no test written |
| S2 | `M11.C1.U01a` | the `DegradedStep` receipt contract |
| S2 | `M11.C1.U01b` | compute it in `_select`, **provably without changing what is kept or dropped** |
| S2 | `M11.C1.U01c` | carry it to the decision's `uncertainty` — ⛔ *not done until a human can read it* |
| S3 | `M11.C2.U01` | the lane vocabulary, closed enum |
| S3 | `M11.C2.U02` | the router — pure, deterministic, **no model** (a lane is a route) |
| S3 | `M11.C2.U03` | the totality guard, both directions |
| S3 | `M11.C2.U04` | the lane on all five `DECISION_PROJECTIONS` |
| S4 | `M11.C3.U01` | the counter table — ⛔ **a zero is written, not skipped** |
| S4 | `M11.C3.U02` | five writers, one per layer. Never a central collector |

---
---

## ⛔ WHAT ROHIT HAS TO DECIDE — 2 things, neither blocks S1

| # | Decision | My recommendation |
|---|---|---|
| 1 | **ConfidenceVector axes.** Code: `evidence`·`freshness`·`consistency`·`identity`·`coverage`·`analytic`. Atlas: `evidence`·`frame`·`temporal`·`causal`·`authority`·`coverage`. **2 of 6 overlap** | ⛔ **Keep the code's six, correct the Atlas.** Cost measured: **3 construction sites, 0 migrations**, 2–6 files per axis. But `identity` → `authority` is **not a rename — it is a different measurement.** And the code **refuses to compose an axis nobody measures**, so `causal` and `authority` would be `None` forever |
| 2 | Call the lane concept **`output_lane`**, never a bare `lane` | ⛔ **yes** — `reason/uncited_lanes.py` already means something else by "lane", and that exact conflation *"lost Layer 2 five readings"* |

**Still open from earlier, not blocking:** correlation placement, and "is a layer the package or the
product layer" (`02-DECISIONS.md`). Object placement and the revision-guard naming are settled.

---

## ⛔ WHAT HARSH HAS TO DO — 5 things, none blocking us

| # | Task | From |
|---|---|---|
| 1 | Deploy from the Dockerfile — **OCR has never run** | L1 STEP-08 |
| 2 | Backfill 60 → 365 days | L1 STEP-09 |
| 3 | Apply `migrations/0186_signal_bundles.sql` | L1 STEP-06 |
| 4 | Apply `migrations/0187_evidence_needs.sql` | L3 STEP-05 |
| 5 | Write the executor pass with **real connector `fetchers`** | L1 STEP-07 + L3 STEP-05 |

⛔ **#5 is the one that matters most.** Until it exists, L1 and L3 built a complete question-asking
pipeline that asks and never listens.

---

## Three unsound verifies, named so nobody trusts them

| # | Problem | Status |
|---|---|---|
| 1 | `tests/platform/test_migrations_apply.py` **does not exist** and is named by 3 units | ⛔ **open** — so `0186`, `0187` and the coming `0188` have no automated proof they apply |
| 2 | `tree.yaml` has **two blocks with `id: M11`** — an old retired one and the L2 one | ⛔ **open** — an id is never reused. Flagged, not silently fixed |
| 3 | `M11.C1.U01`'s row in `tree.yaml` still describes the **regression** | ⛔ **open** — the plan rewrites it; the tree row has not been edited yet |

---

## ⛔ The pattern — three layers, three false findings

> **This codebase's comments record decisions its planning documents do not. Read the comment before
> you "fix" the code.**

| Layer | The false finding | What the code's own comment said |
|---|---|---|
| L1 | `no_model_wired` — 632 failures looked like broken wiring | one lane is model-free **on purpose** (`screen_promoter.py:183`) → *"a count without its dimension is not a measurement"* |
| L3 | "nothing guards the graph revision" | `reason/runner.py:570` **is** the guard, 6 passing tests → *"a guard lives with the reader, not the writer"* |
| L2 | "plan compile should fail on an unproduced source" | it used to, and it **cost six units to one absent fact** (`plan.py:229`) |

---

## THE NEXT ACTION

⛔ **Everything except the two planes is done.** Per Rohit: both planes last, unit by unit, together.

**Layer 2, Section S5 — Plane R's unit contract**, 3 units. **23 of 23 reasoning units declare nothing
about what they read**, while `reason/registry.py:49` exists specifically to check that and names the
pattern it was written for. `tradeoff_unit.py:59` has that literal `AXIS_SOURCES` map naming **six unit
ids**; `legacy_gate.py:23` hardcodes `prior_results.get("legacy.rule")`. None declares anything, so
`validate_sources()` validates an empty set — **a guard that passes because it has nothing to check.**

Then **S6** — Plane D, 4 units: 155 capabilities (all stable), 23 draft situations, 5 unrouted Layer 2
types the corpus already declares.

---

## Migrations waiting on Harsh — 4, none applied

| Migration | From |
|---|---|
| `0186_signal_bundles.sql` | L1 STEP-06 |
| `0187_evidence_needs.sql` | L3 STEP-05 |
| `0188_pipeline_counters.sql` | L2 STEP-04 |
| `0189_output_lane.sql` | L2 STEP-05 |

Every write against them is inside `try/except` and logs, so nothing breaks while they are missing —
and nothing is measured either.

---

## ⛔ Running score on this programme's own planning documents

| Layer | Planned | What it turned out to be |
|---|---|---|
| L3 | `M10.C1.U03` compare-and-set | **already built** — `reason/runner.py:570`, 6 passing tests |
| L2 | `M11.C1.U01` fail on unproduced source | **a regression** — `plan.py:229` removed it for measured reasons |
| L2 | `M11.C1.U02` skip receipt | **already built AND already tested** |
| L2 | *"two of `core.risk`'s three plugins silent"* | **false** — one unit, not three; 1,165 of 1,165 completed |
| L2 | *"Plane D is not in M11's scope"* | **wrong** — nobody had looked. S5 and S6 exist because of it |
| L2 | `M11.C2.U04` the lane on all five projections | **trimmed to one** — the audited row already carries it |
| L2 | *"a routed decision is a different decision, so the lane belongs in `decision_hash`"* | ⛔ **wrong, and it was mine.** `route()` is a pure function of fields already in the hash, so the lane adds **zero** information. **Four replay tests in three files I never touched** caught it |

**Seven corrections in two layers.** Six came from reading the code or running a query before writing
any. **Three came from tests catching my own fresh code**, and those are the ones worth noting:

| Caught by | What was wrong |
|---|---|
| my own new test | the bounded reader returned an edge to a node it refused to contain |
| a **pre-existing** test | `DegradedStep` refused the single most important case it existed to record — a REQUIRED unit running on none of its sources |
| **four pre-existing replay tests** | the lane in `decision_hash` broke every bundle's verification. A derived value has no business in a content hash |

⛔ **This is why the full suite runs before a step is called done.** The last one was caught by tests in
three files this work never touched, asserting a property I did not know I was breaking.

---
---

# LAYER 4 — `executive/` — ✅ COMPLETE

**4 units, 77 new tests.** `01-CROSSCHECK` · `02-PLAN` · `00-START-HERE` · 4 step docs.

| # | Unit | What it is |
|---|---|---|
| 1 | `M12.C1.U01` | the reporting line resolves — dated `reports_to` first, then the `manager_seat_id` column |
| 2 | `M12.C1.U02` | an unroutable tenant says **why**, with a named fix, and distinguishes `MISSING` from `UNKNOWN` |
| 3 | `M12.C2.U03` | the activation receipt — 3 new receipts, including *"the live pass has actually run, not only the shadow pass"* |
| 4 | `M12.C2.U04` | activity is not outcome — `done_but_unproven` never reads as `COMPLETED` |

⛔ **Correction #8:** the plan said never to read `manager_seat_id`. It is the **standing line** the
dated override sits on — `assignment.manager_of` reads `reports_to` first and falls through to it.

⛔ **The topology test PASSED on an unsafe import** (`platform` → `executive`) because `platform` is
exempt. *"An import nothing fails the build on is not a safe one; it is an unchecked one."* The SQL
moved to `platform/org_readiness_sql.py`.

⛔ **`org_seats` has no `channel` column.** My first CHANNELS query could never have run and would
have reported `unknown` forever. There is no per-seat channel in the schema at all, and a channel
receipt already existed — mine was dropped rather than duplicated.

---
---

# LAYER 5 — `deliver/` — ✅ COMPLETE

**4 units, 91 new tests.** `01-CROSSCHECK` · `02-PLAN` · `00-START-HERE` · 4 step docs.

| # | Unit | What it is |
|---|---|---|
| 1 | `M13.C2.U03` | the lane reaches the card — `lane_display.py`, `0190`, pipeline, builder, store |
| 2 | `M13.C2.U04` | ⛔ **rewritten** — the recall guard, `lane_recall.py` + 1 receipt (27 total) |
| 3 | `M13.C1.U01` | the claim extractor — sentences tagged with the existing `ClaimState` |
| 4 | `M13.C1.U02` | the validator, per claim — `invention_ok` **called**, never reimplemented |

⛔ **Correction #9:** `U04` said to replace the scalar publication floor. **There is none in
`deliver/`.** The score gate is `reason/runner.py:1133` and its receipt is already read by
`executive/explain.py`.

⛔ **We created a defect and found it one step later.** `signals.output_lane` had **zero readers in
`deliver/`** — built, tested, green, called by nothing, the eighth instance and the first of our own.

⛔ **Three real bugs my own tests found:** `str(OutputLane.DECISION)` is `"OutputLane.DECISION"`, so
every in-process caller would have been labelled `unrouted`; the tally and the label gave two answers
to one question; and the tally was counting a population nobody received.

### ⛔ What you have to do

**`0190` must be applied.** Fifth unapplied migration (`0186`–`0190`). Until then `cards.output_lane`
does not exist and `insert_card` **fails on write**.

---
---

# LAYER 6 — `feedback/` — ✅ COMPLETE

**3 units, 53 new tests.** `01-CROSSCHECK` · `02-PLAN` · `00-START-HERE` · 3 step docs.

| # | Unit | What it is |
|---|---|---|
| 1 | `M14.C1.U01` | eleven reasons, one layer each — `contracts/learning_attribution.py` |
| 2 | `M14.C1.U02` | the card offers exactly what the API accepts, and all five readers moved together |
| 3 | `M14.C1.U03` | ⛔ **narrowed** — the layer debit, plus the first guard over what already worked |

⛔ **Correction #10:** *"a timing complaint never lowers a correct rule's precision"* was **already
true in three places**, one going further than the milestone asked.

⛔ **The widening would have broken it in both directions.** `units.py` branched on one literal, so
four new "the card was right" reasons would have debited accuracy; and `_PRECISION_SQL`'s two-reason
list would have left four real quality failures **counted by nothing**. Both closed.

⛔ **The topology gate caught my own `contracts/` violation** — it imported `LAYERS`, and *"contracts/
may depend on platform/stdlib only."* Same lesson as `capture → context` in L1.

### ⛔ What is yours to decide

**Eleven radio buttons under "Wrong" is a worse experience than three.** A founder asked to classify
*our* failure will pick the first plausible option. The eleven are right as a **machine** vocabulary;
whether all eleven are **shown** is your call. `_WRONG_REASON_GROUPS` gives a surface four headings a
person can pick, and narrowing the display is a one-line change — never a change to the vocabulary.

**`BUILDER_VERSION` was bumped** to `card-builder.v6-lane-and-eleven-reasons`, so every untouched card
in production is recomposed on the next sweep. That is the documented behaviour of the field, and it
is how the lane and the new reasons reach cards a founder is already looking at.

---
---

# ⛔ ALARMS — what is left, and whose

**Nothing below is engineering. Every item is a decision, a deployment, or a review.**

| | | Whose | Why it bites |
|---|---|---|---|
| 🔴 | **A8 · 5 migrations unapplied** (`0186`–`0190`) | **Harsh** | ⛔ `0190` makes `insert_card` **fail on write**. The other four degrade quietly; this one does not |
| 🔴 | **A2 · the 20-unit roster has never run** | **Rohit** | `BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)`. Built, budgeted, dependency-complete, unswept — the largest built-and-not-called surface in the product. Activation is a runbook step |
| 🔴 | **A3 · the Organisation Brain lever is empty** | **Rohit** | `blocked_play_ids` → `core.constraint` **works**; `learned_brain_entries` has had machinery since `0045` and nothing has produced a proposal. A policy mechanism that has never carried a policy |
| 🟠 | **A5 · `core.tradeoff` would compare 1 of 6 axes** | **Rohit** | the live lane schedules none of `core.impact`, `core.cost`, `core.opportunity`. Schedule them **before** switching it on. `S5.U08` pins the gap so it cannot widen silently |
| 🟠 | **A6 · `or ""` instead of a refusal** | mine, on request | `core.confidence` / `core.priority`: a manifest that forgets `source_reasoner` gets an empty source string. Safe today; changing it changes behaviour, so it is its own unit |
| 🟠 | **14 Sales paragraphs carry your name, unread** | **Rohit** | `plane-d-domain-expertise/PENDING-REVIEW-sales-failure-modes.md` |
| 🟠 | **5 unrouted L2 types have no owner** | **Rohit** | `commitment_unresolved`, `founder_bottleneck`, `meeting_preparation_gap`, `relationship_going_cold`, `vendor_renewal_decision` |
| 🟡 | **97 objects + 283 heuristics are `draft`, 0 hashed** | **Rohit / Harsh** | now **measured** per package (`unreviewed_object_ids`), not invisible. Gating it is a decision with a number under it |
| 🟡 | **ConfidenceVector axes** | **Rohit** | 3 options; recommendation **A** — keep the code's six, correct the Atlas |
| ⚪ | **Nothing is committed** | **Rohit** | 300+ files in the working tree, last commit `c7cdf4c1` predates this session |

---
---

# D · 2026-10-01 · the tenth finding — a gate that could never go green

A, B and C examined nine of the ten receipt findings. The tenth was L4's *"the score components are
measured, not placeholders"*, failing at 59, and it turned out to be a **different defect shape from
any of the nine**: a correct question asked with no date on it.

**What was actually wrong.** The defect it detects was real — 59 candidates where `impact`, `risk` and
`effort` were all the forbidden 5000 neutral default, and for **53 of them all five** ranking
components, so the whole formula was one constant. **And it was closed on 2026-09-08** by commit
`75096bab`. The last affected row is `2026-09-07 23:55` — the day before. 34,167 candidates since,
zero frozen.

`reasoning_candidates` is append-only and this codebase soft-deletes only, so those 59 rows are
permanent and the receipt returned 59 **forever**. `api/routes.py:161` computes `ready = not failed`
over it, so one unfixable receipt was holding the release gate shut for a defect that no longer exists.

> ⛔ **A receipt over append-only history needs a lower bound, or it is not a gate but a monument.**

**What landed.** `ClosedDefect` in `reason/unit_health.py` — the third declared fact there, and the
first carrying a **boundary** instead of a mover, because a closed defect needs nobody to act but does
need to be recognisable if it returns. It demands the commit that establishes the date, so the boundary
is never one somebody chose. The L4 receipt reads it through `_PLACEHOLDER_COMPONENTS_SQL`, keeping its
three equalities byte-for-byte and adding exactly one clause. 17 tests, including two that prove the
predicate was not weakened and one that proves the receipt can still fail.

    the D receipt                 PASS, value 0
    29 receipts, fleet-wide       21 PASS   7 FAIL   1 ERROR     (was 21 / 8 / 1)

### ⛔ The result worth more than the receipt

**Not one remaining receipt failure is a mis-asked question.** Every FAIL and the one ERROR is now a
true statement about a real gap with a named mover — which means the operator page can be trusted for
the first time, and every item on it is on the ALARMS table below rather than in the code.

### ⛔ ALARM D-A1 — recorded as a bound, not raised as a fix
Six of the 59 rows were `disposition=eligible` candidates ranked on a formula that was entirely
constant, inside `org_2f1bc0f366a149e18bd17b06`. **Any card delivered from those 59 was ranked by
nothing.** Nothing is live — they predate the 2026-09-25 freeze — but if that org's card history is
ever used as training or evaluation data for L6 learning, these 59 are not evidence. Whose: **Rohit**,
at the point L6 reads history.

---

# E · 2026-10-01 · the suite's one red test, read at last

It had been carried all session as *"L1's known `pytesseract`-missing test"*. **The product was
right; the test was measuring the host.** `tesseract_available()` requires the Tesseract binary
**and** the Python bindings; the test stubbed only the binary and then asserted an engine comes
back, so it passed where `pytesseract` happened to be installed and failed where it was not.

**And the unstubbed half is the half that actually broke production** — the deploy image once gained
the apt packages while the bindings were in no requirements file, and every scanned document came
back `ocr_failed: ModuleNotFoundError`. **No test covered that**, proved by mutation: with the
bindings check replaced by `return True` the old suite stayed green. Three new tests now catch it.
Product code untouched.

    tests/capture/documents/test_ocr_enablement.py    19 passed   (was 18 passed, 1 failed)

### ⛔ ALARM E-A1 — this made nothing readable
`[L1] attachments carry readable text` **still FAILS at 872**. The test was measuring the host; the
receipt is measuring the deploy image, and it is right to stay red. Whose: **Harsh** — `pytesseract`
and `Pillow` in `requirements`, the apt package in the image, together. Full audit:
`layer-1-enterprise-signals/11-AUDIT-E-the-test-that-measured-the-host.md`, and `STEP-08` section 5
closes its own section 3.

---

## 2026-10-01 · the suite is green for the first time this session

    14,534 passed · 1,063 skipped · 152 xfailed · 0 FAILED        (8m45s)
    29 receipts, fleet-wide:   21 PASS   7 FAIL   1 ERROR

The last red test is gone, and it was never a product defect — see **E** above.

⛔ **The full suite caught two failures the targeted runs could not**, both mine: D's receipt
docstring cited `.../12-AUDIT-D` and the file is `12-AUDIT-D-the-frozen-formula-receipt.md`, so
`tests/test_spec_deferrals_resolve.py` refused it. A comment that cites a record reads as a record
somebody can go and read, and an abbreviated path is indistinguishable from a real one to every
reader except that guard. Fixed by completing the path; recorded in `12-AUDIT-D` PART 9 rather than
edited away. **Two targeted runs are not a suite run.**

### Where the receipts stand, and why this is the line worth reading

| | | Value | Whose |
|---|---|---|---|
| L1 | the parked queue is not a black hole | 1662 | ops — no drain path has been run |
| L1 | every drop we might be wrong about can still be reviewed | 26 | ops |
| L1 | attachments carry readable text | 872 | **Harsh** — bindings in `requirements` + apt in image |
| L4 | at least one seat has a manager | 0 | **Rohit** — no reporting line authored |
| L5 | every delivered card carries a lane | ERROR | **Harsh** — `0190` unapplied |
| L6 | no card gives an order with an empty draft | 18 | spend limit — cards frozen since 09-25 |
| L6 | there is a channel this tenant can be reached on | 0 | **Rohit** — Slack not connected |
| L7 | a human verdict has reached the loop | 0 | **Rohit** — no verdict submitted yet |

⛔ **Not one of these is a mis-asked question.** All ten findings have now been examined across A, B,
C and D: one asked the wrong question (C, the L6 draft receipt, which still fails at **18** because
*a receipt is not fixed by making it green*), one asked a correct question with no date on it (D),
and eight were correct as written — including three I suspected and cleared. Every row above is a
true statement about a real gap with a named mover, which is the first time the operator page can be
read as-is.

---
---

# 2026-10-01 · THE ALIGNMENT PASS, AND THE THREE DOCUMENTS TO READ FROM NOW ON

## ⛔ Read these three, in this order

| | Document | For |
|---|---|---|
| **1** | [`07-LEDGER-every-step-what-why-how-outcome.md`](07-LEDGER-every-step-what-why-how-outcome.md) | **every step in the programme** — the task, why it mattered, what was expected, what actually came out, layer by layer. All six layers, both planes, the five audits, and the doctrine the programme produced |
| **2** | [`HANDOFF-HARSH.md`](HANDOFF-HARSH.md) | **five items for Harsh**, ordered by what they unblock, each with the exact command, the verification query, and what breaks if it is skipped. **H1 is breaking a write path right now** |
| **3** | [`HANDOFF-CODING-AGENT.md`](HANDOFF-CODING-AGENT.md) | **three standalone briefs** plus the twelve rules this repo fails a build over. Two build, one measures first |

## What the alignment pass found

Six places where a label read as a status somebody had checked. The full table is `07-LEDGER` PART 6.
The largest: **seven step files** whose titles said `TO BUILD` while their filenames said `DONE` and
their own bodies carried `✅ DONE — 2026-09-30` with the artifacts named and present. Four in
`layer-3-context-graph`, three in `layer-1-enterprise-signals`.

Also: this file's own README said *"Layer 2 is planned, no code written"*; `02-DECISIONS.md` said
*"all four open"* when **two are closed**; three folders had no `03-FINDINGS.md`; and Plane R had
**eight units built with only one written up** — a built unit with no record is indistinguishable
from one nobody built.

Every title was corrected **only after verifying its named artifacts exist**, and each carries a
dated note saying what it used to say. Nothing was silently rewritten.

## ⛔ Now wired, so it cannot drift again

`tests/test_programme_step_status_is_consistent.py` — **6 tests, each proved by mutation.** Filename
and title must agree; statuses come from a closed set; a **PENDING** step must name its owner;
every layer and plane folder carries all four documents; the folder list is **derived** from where
step files are rather than hard-coded; and the step list must be non-empty so the others cannot pass
vacuously.

## ⛔ Two decisions you can now close cheaply

`02-DECISIONS.md` called four decisions *blocking* — *"every upper layer depends on them."* **All six
layers and both planes were built without #1 and #3 being settled**, because they are about axis
labels and names, not data flow. **#4 was the one that actually blocked, and it blocked because it
was enforceable in a test.**

| | Decision | Yours to do |
|---|---|---|
| **#1** | ConfidenceVector axes | recommendation on record is **A** — keep the code's six, correct the Atlas. Only 2 of 6 overlap, so it cannot be split |
| **#3** | the naming freeze | **nothing is blocked on it.** Every layer was built on the code's names, so this is now a documentation decision. It got cheaper by being deferred |

## State

    full suite              14,540 passed · 0 failed   (14,538 above was taken mid-pass)
    step files              40 · 34 DONE · 3 PENDING · 2 WITHDRAWN · 1 RETIRED
    layer/plane folders     8 · all four documents each
    production receipts     29 · 21 PASS · 7 FAIL · 1 ERROR

⛔ **Still nothing committed.** 300+ files in the working tree; last commit `c7cdf4c1` predates all
of this work.

---
---

# 2026-10-01 · THE ATLAS RE-CHECK · the two planes, re-measured

Full audit: `layer-2-reasoning/13-ATLAS-RECHECK-the-two-planes-and-the-third-silence.md`.

The source was the Atlas's own matrix — `Rohit_Updates/Secret War Updates/08-Cross-Layer-Synthesis/
01-Master-Atlas-vs-Code-Coverage-Matrix.md`, seven layer audits against `harsh/mvp@b739bd5c` on
**2026-08-22**. It is a good document and it is **six weeks old**, so our own rule applied to it:
*a measurement read six weeks later is a claim.* Every number was taken again.

## ⛔ PLANE D IS COMPLETE — and the Atlas's sharpest accusation about it has EXPIRED

| | Atlas · 2026-08-22 | Measured · 2026-10-01 |
|---|---|---|
| **Admin** | *"**Stub.** 57 files, **all 57 stubs**, zero non-stub, zero reviewed/accepted and **zero routes**. No current basis exists for prescriptive Admin expertise"* | **59 capabilities · 59 admitted · 0 hollow · 34 situations** |
| Support | 49 / 40 stubs / 9 non-stub | 49 · all admitted · 0 hollow · 20 situations |
| Sales | 46 / 43 stubs / 3 non-stub | 47 · all admitted · 0 hollow · 15 situations |
| corpus | *"**zero** reviewed or accepted"* | **155 capabilities, every one admitted, 0 hollow** |

Measured with `corpus_health()` — the function the code's own comment points at, not a count of
mine. **Remaining honest gap: 23 DRAFT situations** (Support 16/20, Admin 7/34, Sales 0/15).
⛔ *Corrected 2026-10-01: calling all 23 "unreviewed" was wrong. **Five are reviewed and
approved by harsh** and wait only on `identity.status: draft -> stable`. See `14-PLANE-D-AND-R`.*
A `draft` situation's cards **cannot instruct** and all 23 are flagged, so this is the designed
refusal. ⛔ Whether `draft` should also **gate** is still yours. *(Two earlier records say 24; it is
23 today.)*

## PLANE R — the Atlas's counts were exact; its conclusion has expired

*"Seventeen units are registered; the manifest schedules roughly six"* — **both right.**
`CORE_UNITS` is 17; `BUILTIN_CAPABILITIES` is one capability scheduling 7.

But *"registered is not active"* no longer holds:

    registered in code        23  (17 core + 6 supplementary)
    ever ran in production    22
    never ran                  1  core.signal_composition — DEAL_HEALTH_V1 unswept = ALARM A2
    ran but not registered     0  — the registry and production agree exactly

## ⛔ THE FINDING — and it was one unit

`core.relationship`: **929 runs, 0 completions.** Invisible to the silence receipt, because that
query filters `where status = 'completed'` and a unit with no completed rows is not a low row — **it
is not a row.** Not an unwritten fact either: it binds `deal.status`, which has 3 rows. The fact was
written in prose **twice** and declared nowhere a receipt could read.

Built: `NeverCompleted` — the third grain in `reason/unit_health` — plus a 30th receipt and 17 tests,
mutation-proved. `core.policy` (165 runs, 0 completions) is **excused by derivation**, not by a second
declaration: all four paths it binds are already in `DECLARED_UNWRITTEN`.

    30 receipts, fleet-wide:   22 PASS · 7 FAIL · 1 ERROR     (was 21/7/1 of 29)

### ⛔ ALARM R-A1 · the receipts break `LAYERS.py`'s own rule
All 30 receipts are labelled `L1`–`L7` — **bare digits in the package vocabulary** — and
`GET /health/readiness` returns them as `{"layer": "L2"}`. Against the PRODUCT vocabulary you read,
`L2` is Reasoning; the receipt means Context. `LAYERS.py` states the rule — *"always name the
package, never the digit alone"* — and documents all four vocabularies. Cheap to fix, changes a
response shape, so it is its own unit. **Not done.**

⛔ I nearly filed the folder names as the programme's largest defect. Reading `LAYERS.py` first
stopped it: the YCW27 folders are the PRODUCT column, which that file names as legitimate. Fifth
time in this programme that reading the thing a name points at prevented a false finding.

### What this did NOT fix
`core.relationship` still never completes. The chain is unchanged and still four deep —
`deal.status` 3 of 293 → `core.relationship` 0 completions → `core.impact` 100% silent →
`cost_vs_benefit` 0 fires in 1,200 rows. **Three of the four links are now declared facts rather
than prose.** The connector is **Harsh, H4**.

---
---

# 2026-10-01 · PLANE D AND PLANE R, in the order you asked

Full audit: `layer-2-reasoning/14-PLANE-D-AND-R-the-word-that-was-never-flipped.md`.

## ⛔ PLANE D · five of your "23 unreviewed" are already reviewed

    CAPABILITIES   155   stable + approved  155          nothing waiting
    SITUATIONS      69   stable + approved   46   live
                         draft  + unreviewed 18   need a READER
                         draft  + APPROVED    5   ⛔ need one WORD

All 23 are refused for one reason — `identity_status_draft` — and **not one for missing content**.
Five of them carry `reviewed_by: harsh`, `review_status: approved`, and
**`reviewed_at == last_updated`**, so the approval covers the bytes in the file right now:

    admin.sit.asset_in_custody · admin.sit.employee_lifecycle_event
    admin.sit.obligation_falls_due · admin.sit.spend_against_a_commitment
    customer_support.sit.issue_under_diagnosis

The gate wants **both** `identity.status == "stable"` **and** `review_status == "approved"`. These
have the second. **The review is done; nobody flipped the word** — and commit `90f8edf0` in this
repo is titled, exactly, *"Six situations were finished and nobody flipped the word."* Six then,
five now, nothing counting in between.

**So "23 unreviewed" was a count without its dimension** — my own first rule, broken on my own
status page. It bundled 18 reviews with 5 one-word edits. Corrected in every document and in memory.

### ⛔ ALARM D-A2 · five one-word edits — **yours or Harsh's**
`identity.status: draft -> stable` on those five files. It takes them from *cannot instruct* to
*live*, which is a production-authority change, so I did **not** do it: `identity.status` is the
authoring lifecycle, and flipping it on the strength of `review_status` is the forgery the two-gate
design exists to prevent. `Domain Expertise/_tools/validate.py` now **reports it on every run** with
the reviewer and mover named, and a test pins the set at five — a sixth turns it red.

## PLANE R · ALARM A6 is retired — it was asking for a defect

A6 sat on the table above as *"mine, on request"*. Measured, **all three of its claims are false**:

| | A6 claimed | Measured |
|---|---|---|
| 1 | *"every manifest sets `source_reasoner`"* | ⛔ `sales.deal_cooling` schedules `core.confidence` with the key **absent** — and that is correct |
| 2 | *"the unit reads a prior metric from `""`"* | ⛔ it does not. Both units are `if not source: return None`, **before** any lookup |
| 3 | *"change `or """` to a refusal"* | ⛔ **that would have broken the designed branch.** Falsy is the branch selector: *"no declared source, use the derived path"* |

Retracted in place in `priority.py` with the measurement, and 6 tests pin the behaviour so the
retired claim cannot be acted on later. **A6 comes off the table — not done, not deferred, wrong.**

### The reader for the axis that never fired

    axis_count = 0       16 runs    four zeros, no findings
    axis_count = 1      929 runs   47%
    axis_count = 2    1,028 runs   52%
    axis_count = 3        0 runs   ⛔ a THREE-axis comparator that has never compared three

    speed_vs_certainty  1,897 firings  96%      risk_vs_reward  1,088  55%
    cost_vs_benefit         0 firings  ⛔ NEVER — needs core.impact.impact_bp (absent, declared,
                                        mover Harsh) and core.cost.effort_bp (healthy, 1973/1973)

`scripts/l2_tradeoff_axes.py`, read-only, 8 tests on its pure verdict rule. `axes_unavailable` has
**0 occurrences in 1,973 rows** — every stored row predates the field, so it awaits exercise rather
than having failed, and the probe says which.

⛔ **The probe had two bugs of mine and both looked like findings**: it read the source key as the
axis name (announcing a "6-axis comparator"), and it inferred absence from the declaration list,
reporting the perfectly healthy `core.cost` as a cause. **A declaration list answers "is this
absence declared". It never answers "is there an absence."** Both recorded, both now tested.

## What is left for you, after this

| | Item | Whose |
|---|---|---|
| 🔴 | **the push** — 5 commits ready, clean tree, fast-forward. The classifier blocks me; one line from you | **Rohit** |
| 🔴 | `0186`–`0190` | **Harsh** · H1 |
| 🟠 | **D-A2** · five `identity.status` flips | **you or Harsh** |
| 🟠 | **18 situations to review** | **you or Harsh** |
| 🟠 | `deal.status` writer — it is the single root under `cost_vs_benefit` | **Harsh** · H4 |
| 🟡 | ALARM A2 roster activation (A5 ordering first) | **Rohit** |
| ⚪ | ~~A6~~ | **retired — it was wrong** |

---
---

# ⛔ 2026-10-01 · ALARM D-A2 IS RETRACTED — it was wrong, and the corpus had already said so

**What I told you:** five situations carry `review_status: approved` with `identity.status: draft`,
so *"the review is done and nobody flipped the word"* — five one-word edits waiting on you or
Harsh. It went on the ALARMS table.

**What is actually true.** All five are declared in their domain registry's `pending_l2_types`:

    admin.sit.asset_in_custody · admin.sit.employee_lifecycle_event
    admin.sit.obligation_falls_due · admin.sit.spend_against_a_commitment
    customer_support.sit.issue_under_diagnosis

`tests/packs/test_the_corpus_states_its_own_health.py` says it in its own words — they **MUST NOT
be flipped** — and one of them records that flipping it *"would cost a false assurance"*. For those
five, `draft` + `approved` is **not a half-state**: the content is approved and the lifecycle is
held on purpose, because the L2 type the situation needs does not exist yet.

> **A document in two states is not automatically in a half-state.** Check whether somebody
> declared the combination before calling it an oversight.

**What it cost, and what fixed it.** The validator check I shipped on that reading was crying wolf
on five correct files. `review_done_but_not_flipped()` now takes a `protected` set **read from the
domain's own registry**, and reports **zero**. Warnings 40 → 35.

⛔ **And the first attempt at that fix was itself broken**: it read a name called `registry` that
was a loop variable in scope holding `oid -> path`, so the exemption came back empty and the check
kept reporting all five. A test now asserts the exemption is non-empty, because an exemption that
silently becomes empty is indistinguishable from no fix.

**Eighth time in this programme** that a state was called a defect before the declaration that
created it was read.

## ⛔ What this means for the three I DID flip

It is why they were safe. `campaign_awaiting_reply`, `condition_awaiting_review` and
`organization_gone_quiet` were checked against `pending_l2_types` **before** the flip —
**zero overlap** — and each file records the check. Admin's drafts went 7 → 4, and the four that
remain are four of the five declared-pending above.

    situations that cannot instruct      23 -> 20
    Admin drafts                          7 -> 4     (all four declared pending_l2_types)
    validator "never flipped" warnings    5 -> 0

### So the ALARMS table loses a row
| | Was | Now |
|---|---|---|
| ~~🟠 **D-A2** · five `identity.status` flips, yours or Harsh's~~ | queued work | ⛔ **retracted — the five are correctly held. No action, by anybody.** |

---
---

# 2026-10-01 · THE LIST — what is actually left, and whose it is

⛔ **The table at line 745 is stale.** It lists the push (done, `3e36951b`), D-A2 (retracted — no
action by anybody) and *"18 situations to review"* (collapsed to 3, all 3 accepted). This section
replaces it. The log is append-only, so the old table stays where it is; this one is the live one.

**Nothing below blocks anything else below.** All six layers and both planes are built, the suite
is green at **14,585 passed / 0 failed**, and every remaining item is a deploy, a connector, a
decision or one unit of mine.

## MINE — 1 item

| | Item | Why it is mine | Status |
|---|---|---|---|
| 1 | **readiness axis** — a 7th `ConfidenceVector` axis computed from `capture/coverage`'s readiness model | the only honest way to close Atlas cell **L2-07** (*"role/source-readiness completeness is not part of the blocking vector"*). Unblocked by your **A**. | ready to start — needs your go-ahead, because it **changes behaviour**: a 7th axis binds `overall_bp` through the weakest-axis law |

## HARSH — 5 items, one of them breaking a write path

| | Item | What it unblocks | Brief |
|---|---|---|---|
| H1 | 🔴 **apply migrations `0186`–`0190`** | ⛔ **`0190` — the next card write FAILS without it.** Never run in production. | `HANDOFF-HARSH.md` |
| H2 | 🔴 **OCR stack** — `pytesseract`+`Pillow` in requirements **and** `tesseract-ocr` apt in the image. **Both together or neither works.** | **1,696 rows**: 872 attachments + 824 parked `NEEDS_REFETCH` (half the parked queue) | `HANDOFF-HARSH.md` |
| H3 | 🟠 backfill window 60 → 365 days | history depth for every freshness axis | `HANDOFF-HARSH.md` |
| H4 | 🟠 a **`deal.status` writer** | the single root under `cost_vs_benefit` — that axis has fired **0 times in 1,973 runs** | `HANDOFF-HARSH.md` |
| H5 | 🟡 an **approval-workflow source** | `core.relationship`: 929 runs, **0 completions** | `HANDOFF-HARSH.md` |

## ROHIT — 6 items

| | Item | What it is | Blocking? |
|---|---|---|---|
| R1 | 🔴 **push `e6125684`** | 1 commit, clean tree, fast-forward. The classifier blocks me; one line from you. | no, but it is the record |
| R2 | 🟠 **raise the Anthropic spend limit** | the API has refused **every** model call since 2026-09-25 11:09 UTC. Every production number in this programme is model-off. | nothing is blocked — but no LLM path can be measured until it is lifted |
| R3 | 🟠 **roster activation** (ALARM A2) — ⛔ **ALARM A5's ordering FIRST**: schedule `core.impact` / `core.cost` / `core.opportunity` **before** `core.tradeoff` | `core.signal_composition` has **never run** — 0 runs, which is why `NeverCompleted` refuses `runs <= 0` at construction | no |
| R4 | 🟡 **the 709 `low_relevance` parks** | terminal state, or narrow the receipt? 43% of the parked queue. Not a bug either way — a product call. | no |
| R5 | 🟡 **three Atlas documentation edits** | from your **A**: the Atlas's axis list is wrong, not the code's. `frame_bp`/`causal_bp` have **0 references**; `authority_bp` means three different things in three places. | no |
| R6 | 🟡 **Atlas cell L2-08**, and the **97 `draft` objects** gating question | both are "what should this mean", not "is this broken" | no |

## NOT PENDING — do not re-open these

| | Why |
|---|---|
| ~~ALARM D-A2~~ | **retracted.** The five are declared `pending_l2_types` and the repo's own test says they MUST NOT be flipped. No action, by anybody. |
| ~~ALARM A6~~ | **retired.** All three of its claims were false, and its proposed fix would have broken a designed derived branch. |
| ~~CA1~~ | retired · ~~**CA2**~~ built (`scripts/l2_tradeoff_axes.py`) · ~~**CA3**~~ measured: **zero code gap** in the parked queue |
| ~~the 15 remaining Customer Support situations~~ | domain on hold. Only Admin is in scope. |

---
---

# 2026-10-01 · THE READINESS AXIS — audited, and U1 + U2 BUILT

Atlas cell **L2-07** — *"role/source-readiness completeness is not part of the blocking vector"*.
Unblocked by decision #1 = **A**. Audit and plan:
`layer-2-reasoning/16-AUDIT-AND-PLAN-the-readiness-axis.md`.

## The cell is real, and it has a number

`coverage_bp` — the axis that SOUNDS like readiness — is not readiness. It reads
`context_situations.coverage`, written by `situations.coverage_score(present_fields, expected)`:
**how many of a situation's own expected FIELDS are known.** Source readiness is computed in
`capture/coverage/model.compute_coverage`, enters L1's **four**-component signal vector at
`capture/esqe/publisher.py:415` as `10000 if coverage_ready else 0`, and **stops there.**

    source_coverage      admin FALSE x3 orgs · sales FALSE x3 · support FALSE x3 · fundraising TRUE x3
                         fresh in all three orgs: {calendar, communication}
                         ⛔ `finance` has NEVER been connected -> admin has never been ready
    context_situations   admin 310 · support 73 · sales 61 · fundraising 11 · general 4   (459)
                         103 of the 459 carry coverage = -1, and ALL 103 are admin's

**Admin is the only activated domain, it is 67% of every stored situation, it has never been
coverage-ready, and the blocking vector could not see that.**

## What was built

| | Unit | State |
|---|---|---|
| **U1** | `situations.readiness_score(required, freshness)` — pure, keyword-only, no clock, no connection. Empty `required` returns `COVERAGE_UNKNOWN`, **never 0**. Admin = 50 with `['finance (not connected)']`. | ✅ **DONE** · 8 tests, 3 mutations proved |
| **U2** | the 7th axis on `contracts/situation.ConfidenceVector` + `situations.Confidence`, **declared and NOT composed** | ✅ **DONE** · 6 tests, mutation proved |
| **U3** | `0191_situation_readiness.sql` + the writer + a 31st receipt | ⛔ **BLOCKED on Harsh's H1** — `0186`–`0190` have never run |
| **U4** | whether readiness should COMPOSE | ⛔ **blocked on U3, and it is Rohit's call** |

### ⛔ `overall` did not move, and that is the unit's whole promise

`readiness` is **REPORTED, not composed** — exactly as `coverage` and `analytic` already are.
Admin scores 1-of-2, so composing it would cap `overall_bp` at 5000 on **all 310 admin
situations** through the weakest-axis law. That is two thirds of the corpus re-scored by a line in
a scorer, it is a product decision about what the product should refuse to say, and it is not
answerable before the axis has been stored for a full sweep.

    score_situation(... no readiness row ...)      overall=100  readiness=-1  known=False
    score_situation(... admin's real row ...)      overall=100  readiness=50  missing=['finance (not connected)']
                                                   ^^^^^^^^^^^ identical

### ⛔ The 5000 problem, and why the axis returns a tuple

Admin's honest readiness is 1-of-2 = 50 = **5000 basis points** — the forbidden neutral default
(`reason/decision_maker.py:181`: *"Never substitute 5000."*). A **measured** 5000 is legitimate;
a **substituted** one is the bug; and on a stored column six months later the two are
indistinguishable by inspection. So the missing list travels with the number and U3 stores it.
`ConfidenceVector.composed_from`'s discipline, applied one field down.

## ⛔ F-1 · the axis names were declared THREE times and only two were constants

`context/situation_publisher.py:161` held a **hand-written tuple** of the six names. A seventh
axis added to the contract would have been read by nothing there, published as `None` on every
situation, and **reported as working by every test that only asked the contract**. The publisher
now reads `CONFIDENCE_AXES` and splats the dict, and an AST test keeps it reading it — proved by
mutating it back to a hardcoded list with the *correct seven names*, which the test still caught.

> A vocabulary declared in three places and named in two is not a vocabulary; it is a coincidence
> that has not failed yet.

### The two lists differ by exactly one name, declared

`contracts/situation.CONFIDENCE_AXES` has **7**; `contracts/situation_evidence.CONFIDENCE_AXES`
has **6**. The second is the STORAGE vector and its `complete` property **is the group gate's own
row** ("confidence vector axes present — all 6") taken as a count. Declaring a seventh axis there
before `context_situations.confidence_readiness` exists would turn that gate permanently red for
a reason nobody could look up, because there would be no column to inspect. The divergence is one
unit long and asserted as an **exact set difference**, not a length — a second axis quietly added
to one list would pass a length check on the day it landed.

## Two findings handed to L1 — their own units, not fixed here

| | Finding | Severity |
|---|---|---|
| **F-2** | `compute_coverage` gates on the constant `PACK_REQUIREMENTS` while `declaration.py:163` iterates the function `pack_requirements()` — an authored corpus is asked about, then answered `unknown_domain` with every predicate FALSE, the exact failure `_authored_requirements()` says it exists to prevent. ⛔ **MEASURED: zero authored domains exist, so it is LATENT, not live.** Reporting it as a live bug would have been the ninth time this programme called a state a defect before counting it. | 🟡 latent · 0 rows |
| **F-3** | `coverage_ready` is a **tri-state** and `10000 if coverage_ready else 0` turns `None` into **0** — "we looked and it was terrible" standing in for "we never looked", the one error `AXIS_UNKNOWN_BP` exists to prevent. | 🟠 |

---

# 2026-10-01 · DOC 17 — the three layers, end to end

`17-THE-THREE-LAYERS-end-to-end.md` · 834 lines · **written for Harsh and a coding agent.**
Every number in it was measured read-only against production the same day.

    PART 0   ⛔ the layer numbers are NOT the data flow: L1 -> L3 -> L2 -> L4
    PART 1   what each layer IS — package, size, job, in, out, sub-stages
    PART 2   the flow traced on ONE real email, table by table, plus all 11 seam contracts
    PART 3   the production funnel, measured
    PART 4   what was done per layer + ⛔ the NINE times a state was called a defect first
    PART 5   expected vs actual per layer + ⛔ F-3, a LIVE defect on 141 rows
    PART 6   why this architecture is better — and its honest cost
    PART 7   ⛔ HARSH's five items in full: what each unblocks, how to verify, what NOT to do
    PART 8   the 14 open items with owners
    PART 9   the road to L4, and the crosscheck question it must start from

## ⛔ What writing it found that nothing else had

**F-3 is LIVE, not latent — 141 rows.** `capture/esqe/publisher.py:415` reads
`10000 if coverage_ready else 0`, and `coverage_ready` is a **tri-state**:

    coverage_ready = NULL    141 signals  ->  coverage axis = 0 on ALL 141
    coverage_ready = FALSE   353 signals  ->  coverage axis = 0 on ALL 353
    coverage_ready = TRUE     61 signals  ->  coverage axis = 10000 on all 61

So **141 of 555 qualified signals (25%) assert "we looked and found nothing connected" when the
truth is "nobody ever assessed it"** — and they are indistinguishable from the 353 that are
honestly FALSE. 494 rows look the same and 141 of them are a different fact. This is exactly the
error `AXIS_UNKNOWN_BP = -1` exists to prevent, one layer down, where the sentinel was not used.

**It is mine, it is blocked on nothing, and it is the highest-value small fix left in L1-L3.**

## And two numbers worth knowing before touching the funnel

- **The 552 drops were not borderline.** Average floor **2,500 bp**, average dropped importance
  **1,251 bp** — they scored *half* the floor. Lowering it admits noise; it does not recover signal.
- **150 of 165 cards are expired**, 6 surfaced. ⛔ That is L4's first crosscheck question, not a
  finding: expiry is a window, and a window over a queue starved since the OCR deploy expires
  everything in it. Answerable by measuring expiry dates against the deploy date.

---

# 2026-10-01 · ⛔ L4 RE-CROSSCHECK — the queue is empty for ONE reason, and it is not L4

`layer-4-executive/05-RECROSSCHECK-why-the-queue-is-empty.md` · 364 lines · every number
measured read-only against production the same day.

## L4 does not need building

27 files, 6,167 lines, running on every heartbeat tick, 186 executions · 794 actions ·
466 escalations · 186 outcomes. ⛔ And it is the **only** layer that shipped with its own
declared-silence module (`executive/unreached.py`) — every function it built and does not call,
each with a reason **and** a mover. L2 needed nine findings to learn that discipline.

## ⛔ The chain, every link counted

    L1 / L2 / L3 wrote rows 2026-09-30.   L4 stopped 09-25.   L5 stopped 09-25.

    sweep._PLANNABLE_SIGNALS decomposed:  42 open signals survive joins 1-5, then
      join 6 (core.constraint completed on the run)  ->  0     ⛔ ZERO HERE

    two eras of reasoning run:
      2,681 WITH unit results    evaluated 09-29 -> 09-30
      9,489 WITHOUT              evaluated 08-17 -> 09-29
      open signals pointing at the second:  98 = 100%

    the 2,681 new runs:  8,044 candidates, 7,872 'eligible', selected_candidate_id NULL on ALL
      impact 7,351 · risk 1,758 · effort 6,610 · urgency 5,182 · success 6,658
      formula_utility 5,469   ✅ THE DETERMINISTIC SCORER IS HEALTHY
      llm_utility         0   ⛔ zero on all 8,044
      final_utility_bp    0   ⛔ zero on all 8,044
      outcome_kind    defer 2,669 · blocked 12 · decision ZERO   ->  0 signals emitted

    GENIOS_L4_LLM_DECISION_MAKER = true, for every org

## ⛔ And it is NOT a defect — the tenth near-miss

`reason/llm_decision_maker.py:20`: *"**Failure is DEFER, never the formula.** A missing key, an
exhausted budget, a network error... all DEFER with a reason code. Falling back to the formula
would make a test of 'what does the model decide' silently measure the formula."*

The reasoning is sound. **What nobody declared is that the measurement mode is the production
mode.** So the Anthropic spend limit did not merely switch off LLM features — it stopped the card
pipeline, in a way that reads from outside as a delivery defect.

> ⛔ **A deliberate refusal to degrade is still a stop.**

**This is now DECISION #5 in `02-DECISIONS.md`** — three options, recommendation **B now, C as a
unit, A when the budget allows**. It is Rohit's, it is one line, and nothing in `executive/`
changes either way.

## The Atlas got L4 right — 11 claims checked, 1 superseded

Including, exactly: *"Units 6 and 8 have no file and three files carry no number"* — numbered are
1, 2, 2.5, 3, 4, 5, 7, 9, 10; unnumbered are `assignment`, `escalation`, `execution_guard`.
Its one superseded claim is *"the queue is empty because no domain is activated"* — true when
written, and no longer the binding constraint, because L4 produced 165 cards.

## Six units planned · four buildable · two blocked on a product number

| | Unit | State |
|---|---|---|
| **U0** | ⛔ decision #5 — raise, flip, or build the third path | **Rohit's. Nothing produces a card until this is answered** |
| **U1** | a 32nd receipt: *"no reasoning era selects zero candidates"* — ⛔ a **conjunction**, not a count: a high defer rate is healthy (the old era deferred 8,208 times and still made 1,157 decisions); a **100%** defer rate is the defect | buildable |
| **U2** | **G2** `assignment.resolve_approver_seat` reaches a live path — 8 tests already written, `None` stays `None` | buildable · safest |
| **U3** | **G1** `monitor.blocking_action` — escalations name the step they wait on. ⛔ **the only `UNREACHED` entry with no tests**, so tests first | buildable |
| **U4** | **F-4** ⛔ `source_events.occurred_at` max = **2056-04-20** — a date 30 years in the future in production | buildable · L1 |
| **U5** | **F-5** 708 outputs carry no `ranking_weights_version` — the legacy lane cannot say which weights it used | buildable · L2 |
| **U6** | **G3** brief push + **G4** preventive push | ⛔ **blocked**: needs *how many warnings a founder sees a day*. `modes.py` calls preventive *"the vision's USP"* and `deliver/` has **zero** references to it |

## ⛔ F-6 · and one of my own citations was stale

`unreached.py` cites `api/routes.py:1150` for the `run_executive` call. It is at **1195**. The
claim is true, the address is not — the exact shape of *"a comment that cites a record reads as a
record somebody can go and read"*. ⛔ **`tests/test_spec_deferrals_resolve.py` cannot catch it**:
it resolves document paths, not `file.py:line` citations in prose. That generalises, and it is
U-next.

**Five load-bearing citations in the document were opened by hand. One in five was wrong.**

---

# 2026-10-01 · ⛔ BLOCK 2 — STEP-02 was right too, and it cost 124 escalations

The re-crosscheck above found what stops work **entering** L4. It does **not** supersede
`STEP-02-DONE-organisation-readiness.md`. Both were re-measured today, through STEP-02's own
diagnostic:

    org_readiness, all three orgs:    seats 1 ✅   channels 1 ✅   reporting_line 0 ⛔
    manager_of has two sources:       org_seats.manager_seat_id  0 of 3
                                      seat_responsibilities      0 rows

    execution_escalations, 466 rows:
      day 1 notify   owner    175   127 fired   127 targeted   ✅
      day 2 remind   owner      1     1 fired     1 targeted   ✅
      day 3 remind   owner    165    75 fired    75 targeted   ✅
      day 5 escalate manager    1     1 fired     1 targeted   ✅
      day 7 escalate manager  124     0 fired     0 targeted   ⛔⛔

⛔ **124 day-7 manager escalations were scheduled and not one ever fired.** The ladder works to
day 3 and stops. Seats and channels existing is exactly why 186 executions and 165 cards exist at
all — so organisation data is **partial, not absent**, and STEP-02's finding is **narrowed, not
wrong**: its scope is the **ladder**, not the queue's input.

> ⛔ **Two blocks at two places.** Fixing either alone leaves the other.

**Block 2 is not a unit.** `readiness.py:66` has said what to do since STEP-02: *set
`org_seats.manager_seat_id` for the standing line, or file a dated `reports_to` responsibility.*

## ⛔ F8 · and `seat_responsibilities.reports_to` is not a column

`03-FINDINGS.md` F1 and the Atlas both write it as one. The table's columns are `org_id, seat_id,
scope_kind, scope_key, accountability, source, evidence_ref, valid_from, valid_until, created_at`;
`assignment.REPORTS_TO = "reports_to"` is a **value of `accountability`**, and `reports_to` appears
in **no migration**. **The code is right** — `readiness.py:66` names both paths exactly. Two
documents' prose was imprecise, and that is now corrected in both.

---

# 2026-10-01 · EVERY FILE UPDATED THIS ROUND

| File | What changed |
|---|---|
| `layer-4-executive/05-RECROSSCHECK-why-the-queue-is-empty.md` | **NEW**, 420 lines — the chain link by link, the two blocks, 11 Atlas claims, 6 units, and the five citations opened by hand |
| `layer-4-executive/00-START-HERE.md` | the two blocks at the top; `05` is now the first read; the six planned units |
| `layer-4-executive/01-CROSSCHECK.md` | its two "why the queue is empty" lines — one confirmed-and-narrowed, one now given a dated reason |
| `layer-4-executive/02-PLAN.md` | **round 2**, six units with the *why* and the *do not* for each |
| `layer-4-executive/03-FINDINGS.md` | **F6–F12** |
| `layer-4-executive/STEP-02-DONE-...md` | narrowed, not wrong — with the 124 |
| `02-DECISIONS.md` | **DECISION #5**, three options, recommendation **B now, C as a unit, A when affordable** |
| `07-LEDGER-...md` | the L4 step — ⛔ **the one with no build in it** — and the five doctrine rules it produced |
| `08-ATLAS-SCORECARD-L1-to-L4.md` | **renamed** from `-L1-L2-L3`, every citation fixed; L4's 11 claims added · **35 total**. ⛔ *Renamed again to `-L1-to-L5` on 2026-10-01 (STEP-11); this row records the state on the day it was written* |
| `17-THE-THREE-LAYERS-end-to-end.md` | PART 9's open question **answered**; PART 8 raises R2 from 🟠 to 🔴 |
| `HANDOFF-HARSH.md` | ⛔ a warning above H1: **H1 and H2 produce no card until decision #5** |
| `HANDOFF-CODING-AGENT.md` | **four new briefs** (A–D) and an explicit **DO NOT BUILD** list |

⛔ **Nothing was built this round, and that is the finding.** L4 needed a cause, not code.

---

# 2026-10-01 · ✅ U1 DONE — receipt #31, and it goes RED

`layer-4-executive/STEP-05-DONE-the-receipt-that-says-the-product-stopped.md` · 16 tests ·
5 mutations · **full suite 14,615 passed, 0 failed.**

## ⛔ First, the measurement that justified it

All thirty receipts were run against production. **Every receipt that could plausibly have caught
the stop was GREEN:**

    #19 more than one candidate is ever considered   = 11      candidates ARE produced (8,044)
    #21 the system has abstained at least once       = 1,772   ⛔ green BECAUSE of the defect
    #22 decisions become tracked commitments         = 75      green on append-only history
    #14 the live pass has actually run               = 2,376   the pass runs, and emits nothing
    #20 score components written NOW are measured    = 0       the components are fine

**#21 is the one to read twice.** Abstention is healthy and that receipt measures that it
*happens* — so a system abstaining **100% of the time** satisfies it perfectly.

⛔ **The one receipt red for the right reason was #13** *"at least one seat has a manager"* = 0 —
which is **block 2**. **Block 1 had no receipt at all.** That is what U1 built.

    30 receipts vs production:  20 PASS · 9 FAIL · 1 ERROR
    (#18 ERRORs on `output_lane` — migration 0189, which is Harsh's H1)

## What was built

| Artifact | What |
|---|---|
| `reason/unit_health.ReasoningEra` · `REASONING_ERAS` · `current_reasoning_era()` | the era boundary **declared with the measurement that establishes it** |
| `platform/receipts._ERA_SELECTS_NOTHING_SQL` | the query, with the reasoning for every line |
| **receipt #31** · L2 | *"the current reasoning era selects, not only defers"* |

    -1   the era produced no runs with candidates   -> FAIL, a DIFFERENT sentence
     N   N runs had candidates and selected NONE     -> FAIL, N says how many
     0   at least one selection happened             -> PASS

⛔ **The `-1` is the design.** `having count(*) > 0 and count(selected) = 0` returns **no rows** for
an empty era, every caller reads that as "no violation", and the receipt goes **green on a dead
pipeline** — the exact state it exists to detect.

## ⛔ It is RED, and that was the success condition

    org_66bca8…     480     org_2f1bc0…     849     org_e97e86…   2,253
    ALL ORGS      3,582    ⛔ correctly FAIL

    with the era bound REMOVED (both eras)       0    ✅ GREEN

**The previous era's 1,157 selections hide the current era's zero.** The bound is not a weakening;
it is the entire thing that makes the receipt work. *A receipt over append-only history needs a
lower bound, or it is not a gate but a monument* — audit D, second application.

## ⛔ The mutation that found a half-guard I had shipped

| | Mutation | Caught? |
|---|---|---|
| M1 | the `-1` arm → `0` | ✅ |
| **M2** | **the era bound → `where 1=1`** | ⛔ **SURVIVED all 15 tests** |
| M3 | count defers instead of selections | ✅ |
| M4 | drop the `exists (candidates)` restriction | ✅ |
| M5 | strip the measurement out of the era declaration | ✅ |

M2 turns 3,582 red into 0 green on production — the receipt becomes a liar while every test
passes. It survived because one test proved the boundary is **imported** and nothing proved it was
**used**.

> ⛔ **Declared and written are two directions, and one alone is half a guard.**

`test_the_boundary_actually_REACHES_the_sql` closes it. 15 → 16 tests.

## And my own test failed on its own prose — the eleventh instance

The AST walk for inlined dates excluded the docstring **by value**. ⛔ `ast.get_docstring()`
returns the **cleaned** text while the node holds the **raw** one, so the comparison never matched
and the assertion failed on the builder's own docstring. Excluding the node **by identity** — the
function's first statement — is exact.

## ⛔ What is next, and what this receipt does not claim

It reports a **state**, never a cause. The cause is `GENIOS_L4_LLM_DECISION_MAKER = true` + the
spend limit + the declared *"Failure is DEFER, never the formula"*.

⛔ **Receipt #31 stays red until DECISION #5 is answered, and that is correct.**

    remaining buildable:  U2 (G2 approver) · U3 (G1 blocking step) · U4 (F9) · U5 (F10)
    blocked on a number:  U6 (G3 brief push · G4 preventive push)
    Rohit's:              DECISION #5 · the reporting line · the rest of the list above

---

# 2026-10-01 · ✅ U2 DONE — but NOT as the plan wrote it

`layer-4-executive/STEP-06-DONE-410-approvals-nobody-can-attribute.md` · 10 tests · 6 mutations ·
**full suite 14,626 passed, 0 failed** · **receipts 31 → 32**

## ⛔ The plan said "safest, only the wiring is missing". The measurement refuted it twice.

    execution_actions          794 rows
      requires_approval        410   ⛔ 52% of every action this layer has ever planned
                                        182 · 121 · 107 across the three orgs
    authority_rules              0   ⛔ ZERO rows — nobody can ever be named
    authority.* graph facts      0

    an approver column on execution_actions   ⛔ does not exist
    an approver column on executions          ⛔ does not exist

**Blocked twice:** no place to put an answer (needs a contract field **and** migration `0191`,
behind `0186`–`0190` which have never run), and no answer to put there (zero rules → the column
would be `None` on all 410 rows).

⛔ **And `unreached.py` had already declared it** — *"That needs the org to have published
authority rules at all — until it has, the honest answer is None."* The plan told me to **delete**
that entry. Doing so would have traded the only written record of *why* nobody can be named for a
call that still names nobody.

> ⛔ **A plan is not evidence.** This one was written one step earlier, by me, and still had to be
> measured before it could be believed. **Twelfth** correction-before-code in the programme, and
> the first where the wrong plan was my own from the previous step.

## What was built — the half that needs no migration and no rules

**Receipt #32** · L4 · *"every action that needs sign-off can name who signs"* — ⛔ **RED at 410**
(107 · 182 · 121, per-org sum exact). It goes **green the moment one in-force rule with an approver
is published**, before any wiring exists — because the prerequisite is what has not moved.

    where a.requires_approval
      and not exists (select 1 from authority_rules r
                       where r.org_id = a.org_id
                         and r.approver_node_id is not null       -- a threshold names nobody
                         and r.valid_from  <= now()               -- not one starting next quarter
                         and (r.valid_until is null
                              or r.valid_until > now()))          -- ⛔ not an EXPIRED one

⛔ **`requires_approval` alone is HEALTHY** — it is the autonomy gate working, and 410 gated
actions is the layer being careful. ⛔ **And zero is a TRUE pass here, the opposite of #31**, which
returns `-1` on an empty window because a dead era is not a pass. The two receipts disagree about
emptiness on purpose, and a test pins the difference.

And the `unreached` entry was **STRENGTHENED, not deleted**: it now carries 410 / 794 / zero rules
and names **both** blockers. *A mover without a number is a wish.*

## ⛔ Three of my own mistakes, each caught by a different mechanism

| | Mistake | Caught by |
|---|---|---|
| 1 | the plan's "only the wiring is missing" | **the measurement**, before any code |
| 2 | `"not exists" in sql` — presence, not effect. `and false` neutralises the subquery and 410 red becomes 0 green | **mutation M1** — and it is U1's M2 in different clothes, twice in two units |
| 3 | a global `len(receipts(None))` literal, and a duplicate claim-uniqueness test | ⛔ **the full suite**, on `test_activation_changes_the_pass.py` — a file I had not thought to run |

### ⛔ Mistake 3 is the one worth reading

I had grepped `len(receipts(` , found only my own, and wrote *"canonical jagah thi hi nahi"*. The
guard existed, counted **per layer**, and the grep could not see it. Its docstring had already
rejected my design in advance:

> *"the cheap fix for that is to bump the number, **which is how a decision gate becomes a rubber
> stamp.**"*

And `test_no_receipt_claim_is_duplicated` — the replacement I wrote — **already existed eleven
lines below the test that failed.**

> ⛔ **A grep that finds nothing is not evidence that nothing is there.** Thirteenth instance.
> ⛔ **Presence is not effect.** Two units, two files, same shape.
> ⛔ **Two targeted test runs are not a suite run** — `pytest tests/platform/` was green on the
> broken design, because the file that failed was the one I had not run.

**The gate worked on the person who did not know it existed, which is the only real test of a gate.**
L4's count is now `== 7`, with the decision — and the fact that it caught its own author — written
into the docstring.

## Where U2 stands

    ✅ U2a  receipt #32, RED at 410                                    DONE
    ⛔ U2b  the approver column + contract field + wiring
              blocked on  H1 (migrations 0186-0190)                    Harsh
              blocked on  the org publishing one authority rule        Rohit

    remaining buildable:  U3 (G1 blocking step) · U4 (F9) · U5 (F10)

---

# 2026-10-01 · ✅ U3 DONE — a reminder could name work that was already finished

`layer-4-executive/STEP-07-DONE-a-reminder-names-the-step-it-waits-on.md` · 11 tests ·
6 mutations, all caught · **suite 14,637 passed, 0 failed** · ⛔ **UNREACHED 6 → 5**

## ⛔ The defect was worse than `unreached.py` described

It said escalations say *"your Acme follow-up is stalled"* instead of *"stuck on getting it
approved"* — a missing nicety. The code said this:

    contracts/execution.py:508   first_action  ->  self.actions[0]        ⛔ NO completion filter
    executive/monitor.py         _next_action  ->  skips completed        ✅ correct
    executive/reminder.py:214    "next_action": execution.first_action.label        ⛔

    and that value travels:  reminder_facts -> store.record_reminder(facts=…)
                             -> deliver/executive_bridge.py:105
                             -> deliver/channels/slack.py:125  -> the message

**So a commitment whose first step was finished was reminded about the finished step** — the exact
thing `sweep.py`'s own docstring calls *"the single most damaging thing a system like this can
do"*. The existing guard stops a reminder about a resolved **situation**; it never stopped one
naming a completed **step** inside a live commitment.

⛔ **And the function that fixes it was already written, uncalled and untested** —
`monitor.blocking_action`, the only `UNREACHED` entry with no tests at all.

## ⛔ LATENT, not live — the fourteenth near-miss

    executions                       186 · with >=1 completed action  0 · first action done  0
    execution_actions          794 rows · completed                   0

**Not one action has ever been completed**, so the two agreed on every commitment in existence.
**It fires on the first completion**, and `api/executive_routes.complete_action` is live.

> ⛔ **A defect that fires on the first use of a feature is better fixed before the feature is
> used.** The opposite of U2, where the prerequisite was missing and building would have produced
> a column `None` fills.

## What was built

`reminder_facts` now takes `report` — ⛔ **required and keyword-only**, because an optional one with
a fallback leaves `actions[0]` reachable and this codebase has two names for a wrong value left
reachable. One caller, and the report was already in scope at that line.

⛔ **The key is ABSENT when nothing is outstanding** — not `""`, not the last step. The dict is a
closed vocabulary and a key being present is what *licenses* a sentence about it.

⛔ **One fix covers both rungs**: the escalation fires at `sweep.py:465`, immediately before
`record_reminder` at `:473`, so remind and escalate share one vocabulary. And **timing did not
move** — day 1/3/7/14 and `max_rungs: 6` untouched; the field went on the **vocabulary**, never the
plan, so execution objects stay frozen and *"why did this escalate on day 7?"* stays answerable.

## Two of my own mistakes

**1 · the fixture.** A hand-built `ExecutionObject` dict either trips its dozen invariants or is
shaped to dodge them and stops being a commitment. Replaced with
`tests/test_executive_execution.build`, which goes through `build_from_decision` — ⛔ the
object-shaped front door `unreached.py` declares, whose only callers are tests. And the assertions
read the plan's **own** ids, because a hard-coded `"a1"` makes a test a statement about the fixture.

**2 · ⛔ my own blunt-grep, fifteenth of its kind.** The test asserted
`"first_action" not in inspect.getsource(reminder_facts)` and **failed on correct code**, because
`getsource` includes the docstring and that docstring *explains the old read* to warn the next
reader. Replaced with an AST walk: no `ast.Attribute` named `first_action` in the body,
`blocking_action` among the called names.

## And the declaration's count guard shrank the way it invited

`test_the_count_is_six_and_they_are_the_measured_six` said *"It may shrink; it may not grow without
somebody writing down why."* **6 → 5**, renamed, with the reason written in. Real product gaps
**2 → 1**.

⛔ **F11 fixed at its source too**: that file's own docstring said `executive/` is 25 files / 5,731
lines (it is **27 / 6,167**) and cited `api/routes.py:1150` (it is **1195**).

    receipts   32 · #31 RED at 3,582 · #32 RED at 410
    UNREACHED   5 · real product gaps 1
    remaining buildable:  U4 (F9 the 2056 date) · U5 (F10 ranking weights)

---

# 2026-10-01 · ✅ U4 DONE — ⛔ F9 RETRACTED, and its retraction found the real defect

`layer-4-executive/STEP-08-DONE-a-baseline-is-a-statement-about-the-past.md` · 6 tests ·
5 mutations · **suite 14,643 passed, 0 failed**

## ⛔ F9 was wrong, and the fix it proposed would have destroyed correct data

**F9 said:** *"`source_events.occurred_at` max = 2056-04-20 … one row shaped like a parser escape.
One row is a finding; the absence of a bound at ingest is the defect."*

    future-dated rows        37, not one
    source / object_type     gcal / calendar_event — every single one
    the far ones             2051-04-20 · 2052 · 2053 · 2054 · 2055 · 2056-04-20
    captured_at              all 2026-09-19 06:15:11, within milliseconds
    captured_at in future    0
    outcome                  'emitted' on all 37

⛔ **An annual recurring calendar event — a birthday.** `occurred_at` for a calendar event is
**when the meeting happens**, so a future value is *correct*. **A bound at ingest would have
discarded every future meeting**, which is exactly what a calendar connector must not do.

> **Seventeenth near-miss, and the most dangerous.** The others would have produced a wrong
> report. This one would have produced a wrong **product**.

## ⛔ And the retraction found the real defect — three people lost their cold-start

Three of the four reads that order by this column already bound it (`occurred_at <= :until`);
`capture/landing/unread.py` filters on `captured_at`; receipt #4 uses `captured_at` and is immune.
⛔ **`reason/baselines.build_baselines` was the one with no bound.**

**And the cost is not magnitude.** `anisha@vaultex.in` has 697 events of which 30 are future, and
her median gap is **identical** either way — 667 real gaps drown 30. **0 of 222 baselines changed
value.**

The cost is at the `MIN_SAMPLES` boundary, where one row is decisive:

    person                 all  past  future   computed(all)  computed(past)
    aditi@noveum.ai          4     3       1       True          False      ⛔ FLIPS
    asmit@supymem.com        4     3       1       True          False      ⛔ FLIPS
    tejas@tryclean.ai        4     3       1       True          False      ⛔ FLIPS

Three real events is below `MIN_SAMPLES` and must be `cold_start` — *"we do not know this person's
rhythm yet"*. Four crosses it, so each was given a **computed** `reply_cadence` from a gap set
ending in a future year. Downstream, *"this relationship is going cold"* was judged against that
instead of the honest default.

⛔ **My first measurement reported ZERO** — it compared medians and skipped every person whose
past-only sample fell below `MIN_SAMPLES`, which is **exactly the affected population**.

> ⛔ **A statistic can be unchanged while the verdict flips.** 0 of 222 medians moved; 3 of 222
> people stopped being cold-start.

## The fix — at the read, where its three siblings already put it

`and occurred_at <= :until` with `until = eval_time`. ⛔ **`eval_time`, not `now()`** — it is
already the function's parameter, so a replay of a September sweep uses September's cutoff. **No
new concept**: an omission closed, and `baselines.py` made consistent with three reads that already
did this.

## ⛔ Two of my own mistakes — one invalidated a mutation result

**1 · an over-broad assertion**, caught by my own test: it asserted *no `now()` anywhere* in
`build_baselines`'s SQL and failed, because the function also writes `computed_at=now()` — which is
**correct**, a row timestamp rather than a cutoff. Narrowed to the one read.

**2 · ⛔ a stale `.pyc` invalidated a mutation run.** M3 wrote `MIN_SAMPLES = 2`; the restore copied
the source back but Python served **cached bytecode**, so the next mutation and the restore check
both ran against the mutated value. The symptom was `grep` showing `3` in a file whose import
returned `2`.

> ⛔ **A mutation harness that restores by copying a file must invalidate the bytecode cache, or a
> later mutation reads an earlier one's compiled output.** M4 and M5 were re-run clean; the first
> results were discarded rather than reported.

## And what this unit deliberately did NOT build

⛔ A receipt for "unbounded reads over `occurred_at`" — **the scope is wrong**: most
`order by … occurred_at` hits in the engine are over **`graph_facts`**, a different column where
the question does not apply. **Eighteenth near-miss, caught by measuring the scope before writing
the guard.** The three-sibling consistency test is the narrow version that is actually true.

    receipts   32 · #31 RED at 3,582 · #32 RED at 410
    UNREACHED   5 · real product gaps 1
    remaining buildable:  U5 (F10 — 708 outputs with no `ranking_weights_version`)

---

# 2026-10-01 · ✅ U5 DONE — ⛔ F10 RETRACTED · all five units closed

`layer-4-executive/STEP-09-DONE-a-weights-version-is-derived-not-stored.md` · 8 tests ·
4 mutations · **suite 14,651 passed, 0 failed** · ⛔ **zero production code changed**

## ⛔ F10 was wrong in the scope, the reasoning AND the conclusion

| | F10 said | Measured |
|---|---|---|
| scope | 708 of 2,681 | ⛔ **3,512 of 12,170**, ~27% on **every day including the newest** — no boundary at all |
| cause | inferred from `708 == 708` | ⛔ a coincidence of a narrow window. A **join** shows a perfect partition on the weights **key set** |
| conclusion | *"cannot say which weights it used … not replayable"* | ⛔ **false for all 12,170** |

    expertise   8,658 runs   6 keys  effort,impact,importance,risk,success,urgency  -> @2
    legacy      3,500 runs   5 keys  effort,impact,risk,success,urgency             -> @1
    expertise      12 runs   5 keys  effort,impact,risk,success,urgency             -> @1
                12,170 — every one resolves, ZERO carry no weights at all

`CapabilityManifest.ranking_weights_version` is a **property** and both shapes have one; the
weights are persisted per decision in `reasoning_capability_snapshots.manifest`.

## ⛔ And the fix would have broken replay — the third such finding in a row

> *"a stored `ranking_weights_version` column would have entered `to_semantic_dict`, changed
> `capability_snapshot_id` for every capability in the tree, and **invalidated the
> `reasoning_capability_snapshots` rows replay is verified against** — in exchange for a string the
> key set already determines."*

| | Finding | What my fix would have done |
|---|---|---|
| F9 | bound `occurred_at` at ingest | ⛔ discarded every future calendar event |
| F10 | store the weights version | ⛔ invalidated every persisted capability snapshot |

**Twentieth near-miss, and the third consecutive one whose fix would have caused harm.**

## ⛔ Twelve rows prove the design is right

**Twelve `expertise.*` runs are on the v1 five weights.** The shortcut the `708 == 708` pointed at
— `legacy.*`→`@1`, `expertise.*`→`@2` — would have labelled them wrong. And the scales differ by
**100×**, so a mislabelled version also mis-divides.

> ⛔ **A lane name is not a version.**

## And deliberately NO receipt

All 12,170 resolve and the contract validates at construction, so it could never go red.

> ⛔ **A receipt that cannot fail is not a gate.** #31 and #32 went red the day they shipped; that
> is the test of whether one is worth adding.

## ⛔ Why reverse-chronological mattered

Newest-first refuted the scope in the **first** query — every recent day carries both kinds, so
there is no boundary. Oldest-first would have found the 18 September feature landing, a true but
useless fact, and the coincidence would have survived another step.

> ⛔ **Start at the newest row.** A defect still happening shows up there; one that stopped shows
> up by its absence there. Both answers in one query; only one is visible from the other end.

---

# 2026-10-01 · ALL FIVE L4 UNITS CLOSED — the scoreboard

| | Unit | Outcome | Tests |
|---|---|---|---|
| **U1** | receipt #31 *"the current reasoning era selects, not only defers"* | ✅ built · ⛔ **RED at 3,582** | 16 |
| **U2** | receipt #32 *"every action that needs sign-off can name who signs"* | ✅ built · ⛔ **RED at 410** · wiring blocked twice | 10 |
| **U3** | `blocking_action` wired — a reminder stopped naming finished work | ✅ built · **UNREACHED 6 → 5** | 11 |
| **U4** | the baseline read bounded at `eval_time` | ✅ built · ⛔ **F9 retracted** | 6 |
| **U5** | the weights version is derived | ⛔ **F10 retracted · nothing built** | 8 |

    51 tests · 26 mutations · 2 findings retracted · 2 receipts RED on the day they shipped
    full suite 14,651 passed · 0 failed      (14,599 when the L4 pass began)

## ⛔ What is left, and none of it is mine

| | Item | Whose |
|---|---|---|
| **DECISION #5** — raise the limit · flip the switch · build the third path | ⛔ **Rohit.** #31 stays red until answered |
| the reporting line — `org_seats.manager_seat_id` or a dated `reports_to` | **Rohit.** 124 day-7 escalations have never fired |
| one in-force authority rule with an approver | **Rohit.** #32 goes green on the first one |
| **H1** `0186`–`0190` · **H2** OCR · H3 backfill · H4 `deal.status` · H5 approval source | **Harsh** |
| **U2b** the approver column + wiring | blocked on H1 **and** on an authority rule |
| **U6** brief push · preventive push | blocked on a product number |

---
---

# 2026-10-01 · ⛔ LAYER 4 · THE COMPLETENESS AUDIT — and it found two more things

STEP-09 closed U1–U5 and I wrote *"none of it is mine."* ⛔ **That was an assertion, not a
measurement.** Re-deriving from `executive/unreached.py` found two items that were mine and
buildable, and a third stale statement one layer down.

> ⛔ **"Nothing is left" is a claim like any other and has to be measured.**

`layer-4-executive/STEP-10-DONE-the-declaration-had-one-stale-line.md` · 10 tests · 3 mutations ·
**suite 14,661 passed, 0 failed**

## ⛔ U7 · `summary.build_summary`'s declaration was false, and had been for weeks

Its `PULL_ONLY` entry said the ladder *"is still only composed where a caller asks for a summary,
**never as a scheduled digest**"*. Measured:

    deliver/outbox.py:313   _current_digest_payload  composes build_summary("one_minute", …)
    deliver/outbox.py:1073  inside `_drain_claimed`, from `drain(engine, …)`
                            payload = _current_digest_payload(…)
                            res = ch.send(payload, cfg)        ⛔ THE VERY NEXT LINE

**A route AND a producer, sent on every drain that claims a digest.** Not pull-only — shipped.
**Removed, with the reason recorded.** `PULL_ONLY` **5 → 4**.

### ⛔ And it survived because the table had half a guard

`UNREACHED` is checked both ways. `PULL_ONLY` had three tests — routes exist, no overlap, and a
**bespoke** check on `modes.load_preventive` that was never generalised. **Four of five surfaces
were never asked whether they had grown a producer.**

> ⛔ **One direction alone is half a guard, and a guard written for one member of a closed table is
> half of that.**

`test_no_pull_only_surface_has_quietly_acquired_a_producer` is the general form, read through
`unreached.called_names` so a renamed import still counts. The preventive test stays, renamed,
because its claim is **stronger**: `deliver/` must not reach preventive by **any** spelling.

## ⛔ U6 · `is_terminal` had no tests — and the caller that wants it may not have it

The declaration predicted it: *"Deleting it would push the next caller to re-inline the membership
test, which is how a closed set acquires a second spelling."* ⛔ **The second spelling already
exists** — `execution_guard.py:126` opens `validate` with `if state.state in TERMINAL_STATES:`.

⛔ **And it cannot have the predicate.** `lifecycle.py:39` imports `GuardAction` and `GuardVerdict`
**from** `execution_guard`, so the dependency runs lifecycle → guard and importing back is a cycle.

> ⛔ **An unreached function is not always a forgotten one; sometimes it is an unreachable one.**
> **Twenty-third near-miss** — the plan for this step said *"wire it"*.

The entry stays, with the measured reason, and what would resolve it named: move the predicate to
`contracts/execution` beside the `TERMINAL_STATES` it reads, which adds no dependency. ⛔ Not done
— it changes a public boundary and nobody asked.

**And `CREATED` is in neither set** (4 open · 4 terminal · 1 neither, disjoint but not exhaustive).
⛔ **Pinned, not corrected.**

## ⛔ And one stale line one layer down

`layer-1-enterprise-signals/STEP-04-PENDING-api-limit.md` said *"not blocked on any code in this
repo · **no build waits on it**"*. **Everything downstream of L2 waits on it.** Corrected in place,
with the measurement and a link to **DECISION #5**.

---

# ⛔ LAYER 4 · FINAL STATE, MEASURED

    executive/              27 files · 6,167 lines · runs on every heartbeat tick
    production rows         186 executions · 794 actions · 466 escalations · 1,021 events · 186 outcomes
    step files              10, ALL DONE — no PENDING in this folder
    L4 receipts              7   (was 6)
    UNREACHED                5   and ⛔ ZERO of them untested   (was 6, two untested)
    PULL_ONLY                4   each with a producer-free guard (was 5, one guarded)
    Atlas claims            11 checked · 1 superseded · 2 imprecise, both corrected

## The seven units

| | Unit | Outcome | Tests |
|---|---|---|---|
| **U1** | receipt **#31** *"the current reasoning era selects, not only defers"* | ⛔ **RED at 3,582** | 16 |
| **U2** | receipt **#32** *"every action that needs sign-off can name who signs"* | ⛔ **RED at 410** | 10 |
| **U3** | `blocking_action` wired — a reminder stopped naming finished work | **UNREACHED 6 → 5** | 11 |
| **U4** | the baseline read bounded at `eval_time` | ⛔ **F9 retracted** | 6 |
| **U5** | the weights version is derived | ⛔ **F10 retracted · nothing built** | 8 |
| **U6** | `is_terminal`'s first tests · the cycle recorded | the untested count → 0 | 9 |
| **U7** | a stale declaration removed · the half-guard generalised | **PULL_ONLY 5 → 4** | 1 |

    61 tests · 29 mutations · 2 findings retracted · 3 stale statements corrected
    2 receipts RED on the day they shipped
    full suite 14,661 passed · 0 failed      (14,599 when the L4 pass began)

⛔ **Four of the seven units' plans were wrong**, each caught by measuring before building:
U2 (blocked twice, not "safest") · U4 (F9's fix would have discarded calendar data) · U5 (F10's
would have invalidated every snapshot) · U6 ("wire it" was a circular import).

## ⛔ WHAT IS LEFT IN L4 — nothing of mine, and now that is measured

| | Item | Whose | Blocked on |
|---|---|---|---|
| **DECISION #5** | ⛔ **Rohit** | nothing. **Receipt #31 stays red until answered** |
| the reporting line — `org_seats.manager_seat_id` or a dated `reports_to` | **Rohit** | nothing. **124 day-7 escalations have never fired** |
| one in-force authority rule with an approver | **Rohit** | nothing. **Receipt #32 goes green on the first one** |
| **U2b** the approver column + contract field + wiring | me | ⛔ **H1** *and* an authority rule |
| **U6b** move `is_terminal` to `contracts/execution` | me | ⛔ nobody asked — it changes a public boundary |
| **U6c** whether `CREATED` belongs in a set | ⛔ **a product question** | nobody has stated what `CREATED` means operationally |
| **U6d** brief push · preventive push | ⛔ **Rohit** | *how many warnings a founder should see a day* |
| **H1**–**H5** | **Harsh** | nothing |

## And the three PENDING steps in the whole programme — none of them mine

    layer-1 · STEP-04-PENDING-api-limit      ⛔ now DECISION #5 · Rohit
    layer-1 · STEP-08-PENDING-HARSH-ocr      H2 · Harsh
    layer-1 · STEP-09-PENDING-HARSH-backfill H3 · Harsh

---
---

# ⛔ 2026-10-01 · L5 DELIVERY RE-CROSS-CHECK — **PLAN WRITTEN, NOTHING BUILT**

`layer-5-delivery/00-START-HERE.md` said **COMPLETE** until today. It was true of M13's four units.
It was not true of the layer.

**Read:** [`layer-5-delivery/05-RECROSSCHECK-the-silences-of-the-delivery-spine.md`](layer-5-delivery/05-RECROSSCHECK-the-silences-of-the-delivery-spine.md)
(342 lines) → `layer-5-delivery/02-PLAN.md` (second half) → `STEP-05` … `STEP-12`.

    deliver/  40 files · 9,431 lines    (the Atlas says 36 · 8,674 — it counted top-level only)
              123 top-level public functions · ⛔ 24 reached by nothing · 0 declared
              of the 24, 4 have no test caller either   (corrected from 133/4 — see 06-AUDIT)
              2 of 32 production receipts · and one of the two ERRORs

## The five findings

| | |
|---|---|
| ⛔ **F8** | `deliver/` is the **only large package with no declared-silence module**. `reason/` has `unit_health.py`, `context/` has `DORMANT_LANES`, `executive/` has `unreached.py`. ⛔ **24 of 123 public functions — 19.5% of the layer's public surface — are not called by production code**, including the WHOLE v2 spine and the recall guard this programme built on 2026-09-30. Nothing distinguishes any of them from an oversight |
| ⛔ **F9** | **L5 carries 2 receipts for 9,431 lines** — 4,715 lines per guard, against L4's 881. And #20 **ERRORs** (`cards.output_lane` does not exist), so the layer that physically touches the customer has **one** working production guard |
| ⛔ **CORRECTED 2026-10-02** | `L5` is a hand-written LABEL, not a package. `deliver/`'s four tables are guarded by **8** receipts (4 labelled `L5` + 4 labelled `L6`); before YCW27 by **5**, of which **4 worked**. **1,886** lines per guard, not 4,715 — and 1,886 was already true before this pass began. → [`08-CORRECTION-a-receipt-label-is-not-a-package.md`](layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md) |
| ⛔ **F10** | two comments state something untrue — `push.py:19` says an unreached function is *"fired by L5 when a card is emitted"*, and `units.py` says `get_channel` returns *"Slack or None — one implementation"* when it returns **Slack and `agent_push`**. ⛔ **The behaviour is correct and the prose is not**, so no test fails |
| ⛔ **F11** | `card_builder.resolved_person_name` is unwired, carrying its own measurement: *"35 of 38 person cards named an address in the headline"* |
| ⛔ **F12/F13** | **three Atlas L5 badges are superseded** — claim-level validation and lanes-on-the-card were both built by **this programme, four days ago, one step before the document that calls them gaps** — and the Atlas names **none** of the six-module "Layer 5.2" architecture that is actually there |

## ⛔ And one finding retracted before it was written

`spine.recover_expired_claims` looked like a live silent double-send: nothing calls it, `claim_due`
frees an expired row regardless and writes a **new** fence while the recovery matches the old one.
One more grep killed it — **`spine.claim_due` is called by nothing in production either**, and
`outbox.py:838` already said *"the v2 path has never written a row yet."*

> **New doctrine: *an uncalled function on an un-cut-over path is not a bug; it is an unguarded
> cutover.*** The two want **opposite** fixes. Fifth time measuring the callers first prevented a
> wrong finding.

## The eight steps — seven mine, one Harsh's

| Step | What | Owner |
|---|---|---|
| 05 | `deliver/delivery_health.py` — declare the 4, with reasons and movers. ⛔ **Build first; 06–09 write into it** | me |
| 06 | a guard so the v2 cutover cannot be taken with the recovery unwired · + its first test · + a receipt | me |
| 07 | both comments corrected · + the **general** guard for declared-unreached-but-claimed-called | me |
| 08 | wire `resolved_person_name` · keep the address as fallback · prove it passes `invention_ok` **without weakening it** | me |
| 09 | `gate.describe_decision` — ⛔ **wire it or declare it**, decided by measuring whether a sink fits the grain | me |
| 10 | L5 receipts — up to 4 candidates, **each measured before it is written**, per-layer count raised deliberately | me |
| 11 | `08-ATLAS-SCORECARD` → **`-L1-to-L5`**, the three badges dated, the omission written down | me |
| 12 | ⛔ **receipt #20 cannot run until `0190` is applied** | **Harsh (H1)** |

    1 new module · 6 new test files · 2 corrected comments · 4 declared silences
    1 certain receipt + 4 candidates · 19 planned mutations

## ⛔ What Rohit has to do

**Read `STEP-05` … `STEP-12` and say go.** Nothing is built until then. No new decision is requested —
`STEP-09` and `STEP-10` each contain a measurement that may change their own plan, and both say so.

⛔ **And `0190` is still the most urgent thing in L5 and I cannot touch it.** `insert_card` **fails on
write** without it, masked only because no production signal has been routed since the spend limit
began refusing calls on 2026-09-25 11:09 UTC. **The spend limit is hiding a broken write path.**

---

## ✅ 2026-10-01 · L5 STEP-05 BUILT — and the step's own measurement tripled the rest of the plan

    genios_engine/deliver/delivery_health.py                            NEW   470 lines
    tests/deliver/test_the_delivery_layer_says_what_it_does_not_call.py NEW   16 tests
    8 mutations, every one red
    full suite  14,677 passed · 0 failed   (14,661 when the L5 pass began — exactly +16)

⛔ **STEP-05's first instruction to itself was a measurement, and it found STEP-05's premise wrong.**

| | Planned | ⛔ Actual |
|---|---|---|
| public functions in `deliver/` | 133 | **123** top-level — 133 counted `channels/` |
| unreached | 4 | ⛔ **24** — 23 reported, plus one the resolver hid |
| tables needed | 1 | ⛔ **3** — the 24 are three different kinds of thing |

The **"4"** was a real number answering a different question: no caller anywhere **including tests**.
L4's convention is engine-only callers → **24**. Both deviations erred toward reporting fewer problems.
⛔ So `engine_sources()` now lives in **code**, where a test can refuse it — *a reachability number is
meaningless without its source set*, and a convention written only into a document is one nothing checks.

Written up in full: `layer-5-delivery/06-AUDIT-the-measurement-that-corrected-itself.md` and
`layer-5-delivery/07-AUDIT-the-second-delivery-architecture.md`.

### ⛔ The headline the triage replaced "4 unreached functions" with

**A second delivery architecture exists beside the running one — built, tested, and connected at one
tier of four.** `outbox.drain` is live; beside it sits a complete v2 control plane:

| Tier | Modules | Production evidence |
|---|---|---|
| 1 · resolution | `orchestrator.resolve` · `presence` · `audience` | ⛔ **shadow-measured** — `outbox.shadow_resolve_v2`, counters at `outbox.py:1441` |
| 2 · persistence | `spine.materialize` + 2 | ⛔ none — `outbox.py:804` says so in writing |
| 3 · claiming | `spine.claim_due` · `recover_expired_claims` | ⛔ none, and the recovery has no test either |
| 4 · policy | `rate_limiter` ×3 · `retry` ×2 | ⛔ none — **these two modules are not even imported** |

**So a cutover decision would rest on evidence about routing, while the three tiers that touch the
network have none.** ⛔ And `STEP-06` said the cutover had no measurement at all — it has one, under a
name I searched for and missed. *A measurement can be present under a name you did not search for.*

### ⛔ Five findings the plan did not have

| | Step | Owner |
|---|---|---|
| ⛔ **`lane_recall` is an orphan module** — the recall guard this programme built on **2026-09-30**, 24 tests, referenced by **three comments** and imported by nothing. `pipeline.py:516` even reasons about its correctness | **14** | me |
| ⛔ `outbox.revive_undeliverable` — *"a card must become deliverable the moment a channel exists"*, the rejected alternatives listed, **and no caller.** A tenant registers Slack and every card parked before that stays parked | **15** | me |
| ⛔ `rate_limiter.py` implements a **per-recipient hourly ceiling** and nothing imports it. The live `budget` rule (`reason/runner.py:1294`) is per-rule-**daily** — a different question, and only one is being asked | **16** | ⛔ **Rohit** |
| ⛔ `called_names` resolves by **bare name**, so `queue.claim_due()` in `capture/` masked `deliver/spine.claim_due` — **and L4's own `UNREACHED` uses that resolver** | **13** | me |
| `routing.is_agent_transport` and `units.get_unit` have **no docstring**, so why they are unreached is recorded nowhere | declared | Harsh |

> ⛔ **STEP-14 is the highest-value item in L5 and this programme built the defect.** The unit that
> closed *"a lane nothing reads"* produced *"a guard nothing calls."* **Doctrine: a finding's fix is the
> most likely place for the next instance of the same finding** — it ships under the confidence of
> having just understood the problem, and the question asked was *"what should this compute?"* rather
> than *"who calls it?"*

### Two errors of mine, both caught by the tests I was writing

**No file imports itself** — `qualified_call_sites` required an import, so `outbox.shadow_resolve_v2`
(called inside its own file) read as unreached, which would have reported this package's one production
measurement as dead.

⛔ **A substring check on prose, the sixteenth in this programme.** The measured-tier test was
`"shadow_resolve_v2" in <prose>` and **failed on correct data** — the string is there both when a tier
names its measurement and when a tier says the shadow does *not* measure it. The repair was not a
cleverer pattern: `measured_by` became a structured field. **A claim worth asserting is worth storing
as data.**

### ⛔ What Rohit has to do

**STEP-16 is new and it is yours.** Should a per-recipient hourly ceiling exist?
**A** wire it with a number (pack config, like `bands.py`) · **B** no — ⛔ then `rate_limiter.py` is
**deleted**, not declared, because a ceiling nobody wants is dead code with a convincing docstring ·
**C** the daily rule is enough for now, decided rather than deferred.

⛔ It is the same question as L4's **U6d** in a different layer, and two ceilings set independently will
interact — which is what a founder actually experiences. **They should be answered together.**

---

## ✅ 2026-10-01 · L5 STEP-13 and STEP-14 BUILT — and 13 produced the programme's largest finding

    STEP-13   executive/unreached.py      qualified_call_counts + 5 new entries    9 tests · 5 mutations
    STEP-14   deliver/pipeline.py         recall_verdict WIRED                    12 tests · 5 mutations

### ⛔ STEP-13 · L4's declared inventory went from FIVE to TEN, and the layer did not get worse

`executive/unreached.called_names` counts by **name alone**, so any function sharing a name with any
method anywhere in the engine read as reached. Switching L4's own guard to a resolver keyed on
`(module, name)` — which also resolves aliases — found five that were never called:

| | apparent callers | truth |
|---|---|---|
| `readiness.read` | **11** | ⛔ **0 — and the WHOLE module is unreached** |
| `execution_guard.is_live` | 3 | ⛔ 0 — third spelling of one closed set |
| `lifecycle.is_open` | 2 | ⛔ 0 — second spelling of the same set |
| `execution_store.supersede` | 2 | 0 — a race-free replacement path, uncalled |
| `delegation.propose` | 1 | 0 — superseded by two better-named siblings |

⛔ **`executive/readiness.py` is an entirely unreached module.** `read` → `assess` → `_verdict` is its
whole public chain and `assess`'s only caller is `read` itself. **No route exposes it.** L4 `STEP-02`
built organisation readiness and nothing reads it — production answers the same question through
`platform/receipts.py` and the shared `org_readiness_sql.COUNT_SQL`.

⛔ **And a closed set with THREE spellings, not two.** L4 `STEP-10` found `lifecycle.is_terminal`
untested. `is_terminal`, `is_open` and `execution_guard.is_live` are three partitions of one table,
two of them with **no docstring**, and **not one has a production caller.**

> ⛔ **The declaration was never wrong. It was answering a question the tool could not ask** — which
> is the failure that leaves no trace: nothing goes red and the guard reports success.

### ⛔⛔ The largest finding in the programme — 147 functions, nine packages

Running the corrected resolver over **every** package:

    147 top-level public functions are unreached by production and declared NOWHERE
     18 of them were hidden by the name collision
    129 of them were visible to both resolvers all along

    context 48 · reason 29 · platform 26 · feedback 17 · capture 8 · contracts 8 · mcp 5 · packs 3 · api 3

⛔ **This was never mainly a tool problem.** Only `executive/` and `deliver/` have a reachability
guard. `reason/unit_health.py` and `context/lane_health.DORMANT_LANES` declare *lanes and eras*, not
functions. **A guard that exists in two places out of eleven reads, from either of those two, as a
solved problem.**

⛔ **147 is NOT 147 defects.** L5's 24 were 12 un-cut-over, 7 deliberate, 5 defects — and `deliver/`
was unusual in carrying a second architecture. Full audit: `18-AUDIT-the-engine-wide-reachability-gap.md`.
→ **`STEP-17`**, a **level** of nine units, and ⛔ **the last thing in the programme, not the next.**

### ✅ STEP-14 · the recall guard runs — and my diagnosis was wrong about two of its three functions

`recall_verdict` is now called at the end of `build_cards_for_org`, writing `out["lane_recall"]`,
warning when unbalanced, ⛔ **never raising** — *"a receipt that can abort the thing it is a receipt
for turns an accounting failure into a product failure."*

⛔ **But `low_confidence_is_never_silent` and `every_lane_is_visible_or_deliberately_silent` are NOT
defects.** One takes no data but a default; the other takes **no arguments at all**. The module header
says *"PURE. No I/O, no clock, no model."* They ask questions about **code**, identical on every run,
so their test callers are the correct and only ones.

> ⛔ **A function that takes no data cannot be measuring production.** Filing them as unwired defects
> — which F17 did — would have led to wiring a settled question into a per-org, per-tick loop.

`KNOWN_UNWIRED` **5 → 2**: `card_builder.resolved_person_name` and `outbox.revive_undeliverable` are
the two real defects left in `deliver/`.

### What Rohit has to do — unchanged, still one item

**`STEP-16`**: should a per-recipient hourly ceiling exist? **A** wire with a number · **B** no, and
then `rate_limiter.py` is **deleted** rather than declared · **C** the daily rule is enough, decided
rather than deferred. ⛔ Answer it together with L4's `U6d`.


---

## ✅ 2026-10-01 · L5 STEP-06 BUILT — the cutover guard, and 4 tests I could not run

    tests/deliver/test_the_spine_cutover_cannot_be_taken_unguarded.py   NEW   14 tests
    tests/test_delivery_spine.py                                        +4    ⛔ NOT RUN HERE
    platform/receipts.py            receipt #21, L5                     receipts 32 -> 33, L5 2 -> 3

### The guard

```python
claimed   = calls to spine.claim_due               # 0 today
recovered = calls to spine.recover_expired_claims  # 0 today
assert not (claimed and not recovered)
```

Vacuously true now, and ⛔ **mutation M4 proves it is a guard**: one production call to
`spine.claim_due` added to `deliver/tracker.py` — the cutover, taken in a single line — turned **5
tests red**. Without this, that commit would have been green.

### ⛔ The design decision · a guard must not inherit the blind spot of the thing it guards

`recover_expired_claims` joins `a.claim_token = d.fence_token`, and `claim_due` writes a **new** fence
when it reclaims. **So once a row is handed to a fresh worker, the previous worker's orphaned attempt
can never match the recovery again** — and those are exactly the cases where a retry already
happened.

Receipt #21 is therefore **deliberately fence-free**: `outcome='started'`, `settled_at is null`,
`started_at < now() - interval '1 hour'`, no fence and no `claim_expires_at`. One hour is **twelve**
leases and **nine hundred** provider timeouts, asserted arithmetically rather than stated.

⛔ The blind spot is **recorded, not fixed** — changing the join is a behaviour change on a path
nobody runs — and one test asserts the asymmetry **as a pair**, so whoever fixes it is told which
rationale and which test then need rewriting.

### ⛔ Unlike receipt #20, this one CAN run today

`migrations/0043_l52_delivery_control_plane.sql` is **applied**, so `delivery_attempts` exists and
#21 executes, returning **0**. *A receipt that cannot fail is not a gate* — this one cannot fail
**yet**, which is a different statement: it starts answering the moment the cutover is taken.

### ⛔ AND FOUR TESTS ARE WRITTEN AND UNVERIFIED — this is not a win I am counting

`tests/test_delivery_spine.py` proves the spine against **real PostgreSQL** on purpose
(`for update skip locked`, a partial-index `on conflict` — a fake cannot model either). **No database
is configured in this checkout**, so all 7 of its tests skip, including the 3 that predate this step.

    .venv/bin/pytest tests/test_delivery_spine.py -q   ->   7 skipped

Collection succeeded, so imports and syntax are sound. **The behaviour is unverified. A skip is not a
pass.** Five database-free tests assert the recovery's SQL contract structurally instead — weaker
evidence than behaviour, and not zero.

⛔ **New item: `HANDOFF-HARSH.md` H6.** One command, no deployment, five minutes:
`.venv/bin/pytest tests/test_delivery_spine.py -q`. Any failure there is **a real finding**, not a
regression — the function has never run.

---

## ⛔⛔ 2026-10-01 · A CORRECTION I OWE · my mutation runs for STEP-14 proved nothing

**Found by running `tests/deliver/` and `tests/platform/` together** — something I had not done since
STEP-14 landed.

### What was wrong

`test_the_defects_are_not_filed_as_decisions`, written in `STEP-05`, demanded that
`lane_recall.recall_verdict` be listed in `KNOWN_UNWIRED`. `STEP-14` correctly **deleted** that entry
when it wired the function. **So that test had been failing from the moment STEP-14 landed**, and my
mutation harness never noticed, because:

> ⛔ **it restored each file and never re-ran the suite clean.** I never established a baseline, so
> every mutation count was "the stale failure plus whatever the mutation did".

### ⛔ And it hid a surviving mutation

| | first reported | ⛔ actual, against a verified 52-passed baseline |
|---|---|---|
| STEP-14 M1 | 6 failed | 🔴 5 failed |
| **STEP-14 M4** — *raise on an unbalanced verdict* | 1 failed | ⛔⛔ **52 passed — SURVIVED** |
| STEP-14 M5 | 2 failed | 🔴 2 failed |
| STEP-06 M1–M5 | 2·2·2·5·3 | 🔴 1·1·1·**4**·2 — all still caught, every number one too high |

**M4's "1 failed" was the stale test and nothing else.** A mutation that makes the recall guard
**kill the build pass** was caught by nothing, and I reported it as caught.

> ⛔ **A mutation harness that does not re-run clean cannot tell you what it caught.** This programme
> already knew the neighbouring rule — *a harness that restores by copying a file must clear
> `__pycache__`* — and this is the same failure one level up: in the control, not the cache.
> **Establish the baseline, or the harness is theatre.**

### ⛔ Why M4 survived — a real defect in the wiring, not only in the test

The recall guard sits inside `try/except Exception` so a broken measurement cannot kill the pass.
M4's `raise` lands **inside that try**, so the pass's own safety net swallowed a defect in the half
that ACTS on the verdict, set `lane_recall_unmeasured = 1`, and returned normally. Every assertion
still held — all of them were written before the raise.

> ⛔ **"I could not measure this" and "I measured it and it is wrong" are different sentences**, and
> the guard had one state where it needed two.

**Fixed:** the test now also asserts `"lane_recall_unmeasured" not in out`. M4 re-run → 🔴 1 failed.
Baseline re-verified → 12 passed. ⛔ **M2 and M3 of STEP-14 were not re-run and remain unverified**;
what is recorded is what was measured.

### One more of my own: `pytest -q | tail -5`

The earlier full-suite runs captured only the last five lines, so when one came back **6 failed** the
FAILED list was truncated to four names and **two were unaccounted for**. A run that may need
diagnosing must not be piped through `tail -5`. Fixed: the suite now captures every `FAILED` line.

---

## ✅ 2026-10-01 · L5 STEP-07 BUILT — planned as two corrections, there were four

    tests/deliver/test_a_comment_is_not_a_measurement.py   NEW   6 tests · 5 mutations, all red
    baseline 35 passed · restore verify 35 passed          ⛔ the discipline STEP-14 paid for

| # | Where | Said | Truth |
|---|---|---|---|
| 1 | `push.py:19` | *"(fired by L5 when a card is emitted)"* | ⛔ nothing fired it; agents **poll** |
| 2 | `push.py:18-22` | *"**Two flavours**"* then **one** bullet | ⛔ the second bullet was deleted and **its tail left behind**, parsing as English attached to the wrong bullet |
| 3 | `units.py:70` | *"returns Slack or None — **one implementation**"* | ⛔ Slack **and** `agent_push` — **two of six** |
| 4 | ⛔ `tests/test_delivery_units.py:67` | the same sentence | ⛔ **in the docstring of the test that guards the behaviour** |

⛔ **#4 is the shape that defeats checking.** Anybody asking *"is this claim guarded?"* found a test
repeating the claim. Its assertion was always right — it is about `teams`, which genuinely has no
adapter. ⛔ **In all four cases the behaviour was correct and only the sentence a human reads was
wrong**, so no test failed and no receipt went red.

### ⛔ And the obvious guard would have failed on its own correction

Asserting that `"returns Slack or None"` appears nowhere **fails on the corrected comment**, which
records *"this comment said 'returns Slack or None' until 2026-10-01."*

> **A grep for a known-false phrase matches the record of its own correction** — nearly the
> seventeenth blunt-grep instance in this programme, and the first where the match would have been
> the fix. **A factual claim is guarded by making the fact DERIVABLE and naming it in exactly one
> place.** A missing claim is guarded structurally, by coverage.

### What the six tests do, and the half that outlives the four edits

The general guard walks **all 25** `delivery_health` entries against every COMMENT token in
`deliver/`, so *"declared uncalled, but a comment says it is called"* is a build failure for every
future entry — **a guard written for one member of a closed table is half of that.** Validated
read-only against the stale source first: **exactly one hit, zero false positives across 36 files.**

The header guard catches the deleted bullet generally: every `push_*` entry point must appear in the
leading comment block, and there must be exactly two.

⛔ **And what is NOT guarded, said plainly:** correction #4 has none. Restoring that docstring
sentence would fail nothing. Three of four are defended by a test; the fourth is defended by being
written down.

---

## 📊 L5 so far — 9 steps done, 8 planned

| Step | What | Tests | Mutations |
|---|---|---|---|
| 05 | `delivery_health.py` — 25 declared silences, three tables | 16 | 8 |
| 13 | ⛔ `qualified_call_counts` — **L4's inventory 5 → 10** | 9 | 5 |
| 14 | the recall guard **runs** | 12 | 5 (⛔ **1 survived, now caught**) |
| 06 | the cutover guard + receipt #21 | 18 | 5 (⛔ **4 tests unrun**) |
| 07 | ⛔ **four** stale statements, one inside a test | 6 | 5 |
| 01–04 | M13's original four (2026-09-30) | 89 | — |

    full suite   14,712 passed · 0 failed · 1,067 skipped     (before STEP-07's 6)
    receipts     33        L5: 3        L4: 7
    declared     deliver/ 25  ·  executive/ 10 + 4 PULL_ONLY

**Left:** `08` → `09` → `15` → `10` → `11`, then ⛔ `17` **last** (nine packages, 147 functions).
⛔ **Rohit: `16`.** ⛔ **Harsh: `12` (`0190`) and `H6` (run the spine tests).**

---

## ✅ 2026-10-01 · L5 STEP-08 BUILT — a one-line wiring that needed two decisions

    genios_engine/deliver/card_builder.py                    resolver WIRED + docstring corrected
    genios_engine/deliver/delivery_health.py                 KNOWN_UNWIRED entry DELETED  (2 -> 1)
    tests/deliver/test_a_person_card_names_a_person.py  NEW  14 tests · 6 mutations, all red
    baseline 45 passed · restore verify 14 passed            ⛔ the discipline STEP-14 paid for

`card_builder.resolved_person_name` carried its own measurement — ***"35 of 38 person cards named an
address in the headline"*** — and nothing called it. The plan said *"wire it"*. It **is** one line.
⛔ **The line needed two decisions the plan did not have.**

### ⛔ One choke point, found by reading the AST rather than the code

`name` inside `build_draft` has exactly **two assignments and three uses** — the override chain,
then `compute_slots` and `"business_subject"`. **So one edit covers the headline AND the slots**; a
change at either consumer would have fixed half the defect.

### ⛔ Decision 1 · the resolver goes LAST, because the chain's precedence is load-bearing

The chain already prefers `outreach.counterparty` / `commitment.owed_to`, and its comment says why:
*"A SYNTHETIC ANCHOR'S DISPLAY NAME IS NOT THE CARD'S SUBJECT"* — using one produced *"Investor A —
awaiting reply — waiting 4d on a reply"*, the situation said twice. **Those are FACTS about who the
reading concerns; a `mention:person` name is an OBSERVATION.** Mutation M4 puts the resolver first →
a test fails.

### ⛔ Decision 2 · the gate, and the harm it prevents

Without `node_type == "person"`, a **company** card is renamed after whichever of its people spoke
first — `card_builder`'s own comment: a company node's quotes are *"observations of the people who
`works_at` it… the card names the company, and these are its people."* Mutation M3 removes the gate
→ **3 tests fail.**

### ⛔ And the function's own docstring made a claim that had stopped being true

It said *"the invention guard rejected any draft that wrote 'Maria'."* Measured — `render._corpus`
appends `q["name"]` for every quote, so the name **is** grounded:

    invention_ok("Maria Exconde asked about pricing")   -> PASS
    invention_ok("Nikhil Sharma asked about pricing")   -> FAIL  (name:Nikhil)

⛔ **The grounding half of this defect was already closed. Only the headline half was open.** Fifth
stale statement in L5 after STEP-07's four — and this one inside the docstring of the function being
fixed. Now **asserted**, not repeated. ⛔ My own first probe was wrong too: `'Maria' in corpus` was
`False` while `invention_ok` passed, because the corpus is case-folded. **A substring check against
a normalised corpus is not the test; the validator is.**

⛔ **The 35 was NOT re-measured** — no database URL is configured here, and `GENIOS_ALLOW_PROD_WRITE`
is never set to run a report. It also predates M13's card rebuild with no signal routed since
2026-09-25. **The wiring is justified by the function being correct, not by the number.**

### ⛔ A test of mine failed on correct code — twice — and this time I fixed the design

`test_the_defects_are_not_filed_as_decisions` hard-coded the defect list, so it broke when STEP-14
wired `recall_verdict` and **again** when STEP-08 deleted this entry. ⛔ **The first repair diagnosed
it in the docstring and left the hard-coded names in**, so the same failure arrived one step later.

> ⛔ **A membership list shrinks every time the work succeeds; an invariant does not.**

Rewritten to assert the invariant only. **Caught immediately this time** — baseline before the patch,
affected set re-run straight after: 310 → 324, zero regression.

---

## 📊 L5 — 10 steps done, 7 left

    full suite  14,718 passed · 0 failed · 1,067 skipped       (before STEP-08's 14)
    receipts    33      L5: 3     L4: 7
    declared    deliver/ 24  ·  executive/ 10 + 4 PULL_ONLY
    ⛔ KNOWN_UNWIRED  1 — only outbox.revive_undeliverable (STEP-15)

**Left:** `09` → `15` → `10` → `11`, then ⛔ `17` **last** (nine packages, 147 functions).
⛔ **Rohit: `16`.** ⛔ **Harsh: `12` (`0190`) and `H6` (run the spine tests).**

---

## ✅ 2026-10-01 · L5 STEP-09 BUILT — a three-part unit the plan called "the lowest severity of the four"

    genios_engine/deliver/gate.py          describe_decision now carries "settings"
    genios_engine/deliver/outbox.py        BOTH refusal paths write the full record
    genios_engine/api/delivery_routes.py   ⛔ the result endpoint READS it
    tests/deliver/test_the_gate_records_the_admission_it_refused.py  NEW  13 tests · 6 mutations
    baseline 83 passed · restore verify 13 passed          UNREACHED 11 -> 10

`gate.admit` wrote the purpose down years before anybody asked:

> *"Returns the context alongside the verdict so the caller can put the resolved settings into the
> audit row. **'It was held because quiet hours' is only half an answer; '…and this tenant's quiet
> hours are 21:00-08:00 Asia/Kolkata' is the half that ends the support ticket.**"*

### ⛔ Part 1 · both refusal paths had both halves in hand and dropped one

`_suppress` and `_defer` are handed `(decision, context)` and wrote `{"reason": decision.reason_code}`
— one key, and not even the contract's name for it. ⛔ **And `_defer` took `context` as a parameter
and read nothing from it** — presence without effect, in the signature, while the answer a founder
wants sat inside it.

⛔ **And neither candidate sink in the plan was right.** `spine.log_delivery_event` directly is *the
right table, the wrong call* — `_mark_lifecycle` exists so the lifecycle column and its event
*"cannot disagree"*. `store.log_event` is card-scoped. **The answer was `_mark_lifecycle`'s own
`detail` dict, which the plan never listed.** Fourth time in L5 a candidate list was wrong, fourth
time measuring first cost one command.

### ⛔ Part 2 · the function was not keeping its own docstring's third promise

*"verdict, reason, **and the settings behind it**"* — and it read only `context.config_error`. The
settings are `DeliveryContext.to_semantic_dict()`, which is **literally `admit`'s worked example**:

    settings["profile"]["timezone"]  -> "Asia/Kolkata"    quiet 21 -> 8     437 bytes of jsonb

⛔ **And the capability was already exposed on the wrong path:** `api/delivery_routes.py:168` calls
`to_semantic_dict()` for the **preview** endpoint — so a dry run could show a founder their own quiet
hours while the **live** refusal recorded none of them.

### ⛔ Part 3 · the writer alone would have been decoration

`GET /delivery/results/{delivery_id}` selected `kind, occurred_at, actor` — **not `detail`**. That is
the endpoint a support question lands on, and it returned the event *kinds* and not why.
**Nothing in the engine read `delivery_events.detail`.**

> ⛔ **A record nobody reads is presence without effect — the reader is half the unit.** Mutation M3
> removes that one word from the SELECT and a test fails.

### Two smaller things worth keeping

⛔ **A test of mine built an illegal object** — a `SUPPRESS` decision carrying a `not_before`.
`DeliveryDecision` refused it: *"only a deferral carries a clock."* **The contract knew something my
test assumed away, and said so at construction.**

⛔ **The flag stays separate from the blob, deliberately.** Top-level `config_error` is conditional
(this function's contract); `to_semantic_dict` carries it unconditionally (the preview endpoint's
shape). **A key always present and usually null teaches a reader to ignore it.**

### ⛔ What was deliberately NOT done

Record the **admitted** case — it would write 437 bytes on every successful delivery, a volume
decision on the happy path, and `admit`'s docstring is about HELDS. **Recorded, not taken.**

---

## 📊 L5 — 11 steps done, 6 left

    full suite  14,732 passed · 0 failed · 1,067 skipped      (before STEP-09's 13)
    receipts    33      L5: 3     L4: 7
    declared    deliver/ 23  ·  executive/ 10 + 4 PULL_ONLY
    KNOWN_UNWIRED  1 — only outbox.revive_undeliverable (STEP-15)

**Left:** `15` → `10` → `11`, then ⛔ `17` **last** (nine packages, 147 functions).
⛔ **Rohit: `16`.** ⛔ **Harsh: `12` (`0190`) and `H6` (run the spine tests).**

---

## ✅ 2026-10-01 · L5 STEP-15 BUILT — ⛔ and `KNOWN_UNWIRED` is now EMPTY

    genios_engine/api/channel_routes.py      the registration route revives the backlog
    genios_engine/deliver/delivery_health.py the LAST KNOWN_UNWIRED entry deleted   1 -> 0
    tests/deliver/test_a_parked_card_revives_when_a_channel_appears.py  NEW  12 tests · 6 mutations
    baseline 28 passed · restore verify 12 passed

### ⛔⛔ THE FIX THIS STEP'S OWN PLAN PROPOSED WOULD HAVE CAUSED HARM

`STEP-15 §3` named *"the risk nobody has checked"* — a revived card must not resurrect one past
`expires_at` — and proposed that bound. **The function's docstring had already answered it, in the
opposite direction:**

> *"Reviving a stale card is SAFE… the drain re-proves authority immediately before every send, so a
> revived row whose card has since expired is `cancelled` on its way out rather than delivered.
> **Waking an old message and letting the authority check kill it is strictly better than leaving it
> dead, because the second option cannot tell 'we chose not to send' from 'we lost it'.**"*

⛔ **A bounded revive leaves the row dead, and a dead row is indistinguishable from a decision not to
send.** Third retracted fix in the programme after L4's F9 and F10 — **and all three were caught by
reading the thing being changed before changing it.** Mutation M4 re-adds the bound and a test fails.

### ⛔ Two writers of `org_channels`, and one is a trap

`platform/seats.py` writes the `in_app` PULL surface: *"It is emphatically NOT a transport…
**Making that row a transport is what produced production's entire delivery history: 3 rows, all
`failed_terminal`.**"*

So the gate is `deliverable_channels`, **never a hand-written `if body.active and ch == "slack"`** —
which was my first instinct, and is that gate's own defect written by hand. Its docstring is the
argument: *"every historical delivery failure in this database is one of [its two conditions] being
assumed rather than checked."* Looping the canonical answer also means **a second channel route needs
no edit here.** Mutation M2 hand-writes it and 3 tests fail.

### ⛔ KNOWN_UNWIRED: 5 → 0 · `deliver/` has no known-unwired defects left

| | Closed by |
|---|---|
| `lane_recall.recall_verdict` | `STEP-14` — wired |
| `lane_recall.low_confidence_is_never_silent` | ⛔ `STEP-14` — **reclassified**, a build-time guard |
| `lane_recall.every_lane_is_visible_or_deliberately_silent` | ⛔ `STEP-14` — same |
| `card_builder.resolved_person_name` | `STEP-08` — wired, gated, last in the chain |
| `outbox.revive_undeliverable` | **this step** |

### ⛔ A THIRD membership list of mine broke, and I wrote the rule against it one step earlier

`test_one_defect_is_left_in_the_known_unwired_table` was written **in `STEP-08`** — the step where I
diagnosed this pattern, rewrote the other test as an invariant, and wrote down *"a membership list
shrinks every time the work succeeds; an invariant does not"* — **then wrote a new membership list a
few sections later in the same session.**

> ⛔ **A doctrine applied only to the instance that produced it is not a doctrine.**

Rewritten so an **empty** table is a legitimate state, with the history in prose where a log belongs.

---

## 📊 L5 — 12 steps done, 5 left

    full suite  14,745 passed · 0 failed · 1,067 skipped      (before STEP-15's 12)
    receipts    33      L5: 3     L4: 7
    declared    deliver/ 22  ·  executive/ 10 + 4 PULL_ONLY
    ⛔ KNOWN_UNWIRED  0

**Left:** `10` (L5 receipts) → `11` (the Atlas scorecard), then ⛔ `17` **last** (nine packages, 147
functions). ⛔ **Rohit: `16`.** ⛔ **Harsh: `12` (`0190`) and `H6` (run the spine tests).**

---

## ✅ 2026-10-01 · L5 STEP-10 BUILT — receipts 33 → 35, and ⛔ two of five candidates could not fail

    genios_engine/platform/receipts.py                      2 new L5 receipts
    tests/platform/test_two_receipts_for_nine_thousand_lines.py   NEW  10 tests
    tests/deliver/test_nothing_dies_of_low_confidence.py    ⛔ the L5 COUNT GUARD
    11 documents + 1 filename                               receipt numbers -> claims
    baseline 35 passed · restore verify 10 passed           L5: 3 -> 5

### ⛔ Two rejections, and they are the valuable half

| Candidate | Verdict |
|---|---|
| a delivery row with no attempt | ⛔ **0 forever** while nothing calls `spine.materialize` |
| a card delivered on an adapter-less channel | ⛔ **impossible** — `outbox.py:935` parks first |
| `UNDELIVERABLE` kept apart from `failed_terminal` | ⛔ a **code** property, already guarded by a test |
| a card past `expires_at`, still live | ✅ built |
| a row parked for want of a channel, for an org that **now has one** | ✅ built |

*A receipt that cannot fail is not a gate*, and one asking the wrong question **goes green and is
believed**. ⛔ And the rejections are **checkable**: a test asserts `spine.materialize` is still
un-cut-over and the send path still parks on a missing adapter — **if either premise changes, the
candidate becomes viable and the test says so.**

### ⛔ The window was measured, and my instinct would have cried wolf on every tenant

`sweep_lifecycle` runs on `run_maintenance_sweep`'s heavy tick. **`config.sync_interval_hours` =
6.0.** A one-hour grace — my first number — fires on every card that expired in the normal
six-hour gap between ticks: **latency reported as an alarm**, and *the fix for a false alarm is
always to loosen the check.* Twelve hours = two full cycles, asserted against the live setting.

### ⛔ L4's own docstring promised an L5 count guard that did not exist

`test_activation_changes_the_pass.py` is the canonical argument for per-layer counts — *"the cheap
fix for that is to bump the number, which is how a decision gate becomes a rubber stamp"* — and ends
*"L5's own count is guarded in `tests/deliver/test_nothing_dies_of_low_confidence.py`."* **That file
held only presence filters.** In STEP-06 I read it and said there was no L5 count guard: **I was
right and the docstring was wrong.** The guard now exists *where it points*, so the promise is kept
rather than redirected. **L5: 2 → 5**, every addition named; a sixth fails the build.

### ⛔ Receipt numbers are POSITIONAL — eleven of my references rotted at once

Inserting two receipts moved STEP-06's from **#21 to #23**. **Every test filtered by claim and stayed
green**; eleven document cross-references and one filename did not. All now use claims.

⛔ **But `receipts.py:190` quotes `#19/#21/#22/#14` with values under *"Measured 2026-10-01"* and is
correct forever** — a snapshot's numbering is part of its measurement.

> ⛔ **Refer to a receipt by its claim, never by its position — unless you are quoting a dated run.**

⛔ **And a test I wrote failed on its own assertion string**: it scanned its module for
`len(receipts(None))` to forbid a global total, and that text sits in the `assert` that forbids it.
**Seventeenth instance**, and the first where the match was the guard itself. Deleted, reason
recorded: *a convention is enforced by the guard that implements it, not by a test that greps for its
own prose.*

---

## 📊 L5 — 13 steps done, 4 left

    full suite  14,757 passed · 0 failed · 1,067 skipped      (before STEP-10's 11)
    receipts    35      L5: 5     L4: 7        lines per L5 guard: 4,715 -> 1,886
    ⛔ CORRECTED 2026-10-02 — "L5" is a LABEL, not a package. deliver/ holds 8 receipts
    ⛔ (4 labelled L5 + 4 labelled L6) = 1,252 lines per guard. 4,715 was never true.
    declared    deliver/ 22  ·  executive/ 10 + 4 PULL_ONLY
    KNOWN_UNWIRED  0

**Left:** `11` (the Atlas scorecard → `-L1-to-L5`), then ⛔ `17` **last** (nine packages, 147
functions). ⛔ **Rohit: `16`.** ⛔ **Harsh: `12` (`0190`) and `H6` (run the spine tests).**

---

## ✅ 2026-10-01 · L5 STEP-11 BUILT — the scorecard covers L5, and ⛔ one cross-layer break

    08-ATLAS-SCORECARD-L1-to-L4.md -> -L1-to-L5.md     35 -> 45 claims, 125 -> 200 lines
    17-THE-THREE-LAYERS-end-to-end.md                  the LIVE pointer updated
    STATUS.md (line ~1114)                             the HISTORICAL row dated, not rewritten
    tests/executive/test_an_unroutable_tenant_says_why.py  ⛔ the guard now counts the question
    ⛔ NEW: 19-PENDING-who-owns-what.md                 one page, every remaining item, by owner

### L5 contributes 10 claims — ⛔ 5 superseded, 1 OMISSION, 2 imprecise

**The least accurate layer in the Atlas, and three of the five supersessions were created by THIS
PROGRAMME four days before the document was read.** Claim-level validation (`target` → built) ·
lanes on the card (*"L5's biggest gap"* → built) · the three delivery failures to design out (all
three already guarded) · the scalar publication floor (there is none in `deliver/`) · the invention
validator (it exists).

⛔ **And the omission is the finding.** Six modules, five phases, named **nowhere**: `presence` ·
`orchestrator` · `spine` · `tracker` · `units` · `analytics`.

> ⛔ **A `gap` badge on built work costs a wasted unit. An OMISSION costs a rebuild**, because
> nothing in the document tells you to look. L2 paid **six units** for one absent fact.

### ⛔ And it was not only a document correction

`STEP-10`'s two receipts failed a test in **`tests/executive/`** — a directory **neither of my
targeted runs touched**:

    assert sum("channel" in c for c in claims) == 1      ->   assert 2 == 1

⛔ **It counted the WORD, not the QUESTION.** Measured, the two receipts are opposite-conditioned:
L6 asks whether a channel exists (`from org_channels`, passes > 0); L5 asks whether a backlog
cleared (`from delivery_outbox`, passes == 0, **and only counts anything when a channel exists**).
They cannot disagree.

⛔ **Rewritten STRICTER:** it counts receipts whose **outer subject** is `org_channels`, so a
duplicate is caught even if its claim never says "channel". **And my first attempt at that was
substring-shaped too** — `"from org_channels" in r.sql` caught the new L5 receipt through its
`EXISTS` subquery. Two substring-shaped guards in a row, and the second was mine.

> ⛔ **Two targeted test runs are not a suite run** — written down twice before today. **And an
> arbitrary subset is not a smaller suite**: re-running every receipt-touching file by hand produced
> **8 errors** in a file that passes alone (13) and had **zero** in the full run.

---

## 📊 L5 COMPLETE — 14 steps, 1 item of mine left and it goes last

    full suite      14,768 tests · 0 failed        (14,534 when YCW27 began)
    receipts        35      L5: 5   L4: 7          lines per L5 guard: 4,715 -> 1,886
    ⛔ CORRECTED 2026-10-02 — "L5" is a LABEL, not a package. deliver/ holds 8 receipts
    ⛔ (4 labelled L5 + 4 labelled L6) = 1,252 lines per guard. 4,715 was never true.
    declared        deliver/ 22  ·  executive/ 10 + 4 PULL_ONLY
    KNOWN_UNWIRED   ⛔ 0
    scorecard       45 claims · 7 superseded · 1 OMISSION · 4 imprecise

⛔ **READ `19-PENDING-who-owns-what.md`** — one page, every remaining item, by owner. 1 mine
(`STEP-17`, and it is **last**), 8 Rohit's, 6 Harsh's, 3 of mine blocked on those.

---

## ⛔⛔ 2026-10-01 · STEP-16 WITHDRAWN — I asked you a question the code had already answered

    genios_engine/deliver/delivery_health.py   rate_limiter's 2 entries rewritten with the facts
    tests/deliver/test_the_hourly_ceiling_is_exact_at_one_worker.py   NEW  7 tests · 6 mutations
    18-AUDIT-the-engine-wide-reachability-gap.md   ⛔ the two STEP-17 decisions PRICED: 147 -> 123
    baseline 7 passed · restore verify 7 passed

I asked: **"should a per-recipient hourly ceiling exist?"** (A wire / B delete / C defer). My
premise: *"there is no per-recipient hourly ceiling in the running path."*

⛔ **There is. It is live, with a default:**

    timing.py:59   _BURST_WINDOW = 1 hour      timing.py:86  max_interrupts_per_hour = 3
    timing.py:229  count >= limit -> DEFER     (never drops)

    outbox.drain(1) -> gate.admit(1) -> evaluate_delivery(2) -> evaluate_timing(1)
    rate_limiter.reserve_slot = 0

**So `rate_limiter.py` is not a duplicate — it is the RACE-FREE version.** `timing.py` reads a count
and decides; `rate_limiter` atomically reserves. ⛔ **And that gap is deliberate**: `resolve()`
releases its read transaction because *"the connection stops sitting idle in transaction across an
outbound HTTP call"* — holding one across a webhook POST is worse than the overshoot.

⛔ **And the race cannot happen today**: one uvicorn process (no `--workers`), `max_workers=1`.
**One drain worker.**

**A** wrong (two limiters on one question) · **B** wrong (it is the fix the cutover needs) ·
**C** right — ⛔ **and `delivery_health` tier 4 already said so, three steps before I asked.**

> ⛔ **Fourth retraction in the programme, and the first where what is retracted is a QUESTION
> rather than a fix.** F9, F10 and the `expires_at` bound were fixes that would have caused harm.
> **This one spent your attention on a decision that did not exist.**
>
> ⛔ **I read one module and concluded the layer lacked a capability.** The grain comparison was
> right — per-recipient-hourly vs per-rule-daily — and **the search was one module wide.** Sixth
> instance of *a conclusion drawn from one name's absence*, and the first to reach you as a decision.

### What survived — a latent condition, not a decision

The ceiling is **exact at one worker and silently approximate at two**, and nothing said so.
`rate_limiter`'s mover is now **the worker count, not only the cutover**, and a test pins it:
`--workers 4` in the Procfile fails the build.

---

## ⛔ STEP-17 · the two decisions are now PRICED — scope 147 → 123

    147   engine-only callers, nothing excluded
    134   - 13   scripts/ counts as a caller
    123   - 11   declaration modules exclude themselves (the rule L4 and L5 already use)

    context 41 · platform 24 · feedback 17 · reason 15 · contracts 8 · capture 7 · mcp 5 · packs 3 · api 3

⛔ **The 13 that `scripts/` rescues are ALL diagnostics or ops reads** — `unit_health` ×5,
`uncited_lanes` ×2, `slice_weight` ×2, `l2_activation`, `stage_timer`, `journey`, `lane_health`.
**My recommendation: count it.** `tests/` is excluded because nobody runs a test to learn something
about production; **a script an operator runs is exactly that.** Seven of the thirteen would be
self-excluded anyway, so the call genuinely resolves **six**.

⛔ **But it is a policy across all eleven packages, so it is Rohit's one-line call — and `STEP-17`'s
first unit (`capture/`, 7) waits on it.** I am not assuming the answer.

---

## ✅⛔ 2026-10-01 · STEP-17 CLOSED — every package says what it does not call, and MY LIST IS EMPTY

    genios_engine/platform/reachability.py      NEW  the shared machinery, imports nothing from the engine
    8 new declaration modules                        capture · context · packs · reason · feedback
                                                     platform · contracts · api
    executive/unreached.py · deliver/delivery_health.py   pointed at the shared machinery
    tests/platform/test_every_package_says_what_it_does_not_call.py  NEW  58 tests, ONE guard
    tests/capture/test_the_capture_layer_says_what_it_does_not_call.py  NEW  13 tests

    109 declared entries across TEN declaration modules

### ⛔⛔ A function is reached FOUR ways, and only three can be measured

| | Mechanism | Found |
|---|---|---|
| 1 | `f()` — a **call** | the resolver already had it |
| 2 | `@router.get(...)` — a **decorator** | 14 route handlers, no Python caller by design |
| 3 | ⛔ `Depends(f)` · a dispatch table · a registry — a **reference** | ⛔ **46 of 109** |
| 4 | ⛔ `store.purge_expired()` — **duck-typed dispatch** | ⛔ **unmeasurable; hand-checked entry by entry** |

**`platform/auth.require_owner` has 35 references and ZERO calls.** `get_auth_ctx` 29,
`require_admin` 25, twelve `outreach_situations.read_*_for_dispatch`, twelve `feedback/units.unit_*`,
five `mcp/server.tool_*` — ⛔ **`mcp/` went to ZERO and needs no declaration module at all.**

> ⛔ **Had the 123 been declared without that measurement, 46 of the entries would have been lies**,
> each reading as a considered decision about live code.

⛔ **And the fourth mechanism gave one rescue and sixteen false alarms.** `realtime.purge_expired`
looked unreached and claimed *"(maintenance heartbeat)"* — **it IS called**, behind a `hasattr` at
`api/routes.py:964`. **Retention is enforced**, and I was one grep from recording a false *stale
comment* finding. The other sixteen were collisions: `list.extend` **96** apparent hits,
`Path.resolve` **74**.

### ⛔ The sharpest finding, and the code had already written it down

`capture/acquire/need_executor.py:125` names `context/evidence_need_store.read_open_needs` and adds
**"which this layer may not import."** `capture/` is layer 1 and `context/` is 2 — ⛔ **the
EvidenceNeed executor cannot read its own queue.** Four functions carry that chain, one of them
(`hold_resolution.resolve_hold`) with **22 test callers, the most of any unreached function in the
engine**, and it is broken **at a layer boundary** rather than by an oversight.

⛔ **The Atlas listed EvidenceNeed as VERIFIED MISSING when this programme began.** It was built
since and never connected. The seam decision has two shapes: lift the queue read into `platform/`
(what the reachability machinery just did), or invert it so `context/` pushes down.

### ⛔ ONE guard over eleven packages, not nine copies of a test

The plan said *"a level, one unit per package"*. It is one module, parametrised over a registry — and
**that is what makes a NEW package forgetting its declaration a build failure**, which nine
hand-written copies could never have caught.

### ⛔ `scripts/` was decided by me, and it is one constant to flip

`SCRIPTS_ARE_CALLERS = True` in `platform/reachability.py`. The question was open with Rohit and the
work was authorised, so I took it and recorded it as mine. All 13 functions it rescues are
diagnostics or ops reads; `tests/` stays excluded for the opposite reason — **nobody runs a test to
learn something about production.**

### Three faults of mine, all caught before shipping

⛔ The self-exclusion was a **hand-maintained list** and I forgot to add my own new module **within a
minute** of writing it — *a list you must remember to extend is a list that will be wrong.* Now
derived. ⛔ The generic mover check demanded two long strings and **failed on two correct tables**.
⛔ And the decorator check took a **union** across `api/` instead of per module — *the same
name-collision class the qualified resolver exists to fix, reproduced in the test that documents it.*

---

## 📊⛔ NOTHING IS LEFT ON MY LIST

    MINE        ⛔ 0 — STEP-17 was the last of them
    ROHIT'S     7   4 decisions, 2 data gaps, 1 push      (STEP-16 WITHDRAWN)
    HARSH'S     6   5 deployments + 1 test run            ⛔ H1 is breaking a write path
    BLOCKED     3   mine, each waiting on one of the above — and only on those

    full suite  14,846 passed · 0 failed      (14,775 when STEP-17 began — exactly +71)
    receipts    35      L5: 5     L4: 7
    declared    109 entries across TEN declaration modules
    scorecard   45 claims · 7 superseded · 1 OMISSION · 4 imprecise

⛔ **14,534 tests when YCW27 began. 14,846 now — and 0 failed at every single step of this pass.**

⛔ **READ `19-PENDING-who-owns-what.md`** — one page, every remaining item, by owner.


---
---

## ⛔⛔ 2026-10-02 · A CORRECTION I OWE ON L5 — the receipt label was never a package

**Found by:** asking which receipts guard `feedback/`, as the first question of the L6 re-crosscheck.

`Receipt.layer` is a **hand-written string**. I counted `deliver/`'s guards with
`[r for r in receipts(None) if r.layer == "L5"]` — and `genios_engine/LAYERS.py` warns in its own
docstring: *"Atlas 5.2 is our `deliver` (6), and Atlas 6 is our `feedback` (7) — **so always name
the package, never the digit alone**."* I read the digit as a package.

Resolved by the table each receipt queries:

```
label   tables                                                package(s)
L1 ×6   sync_cursors parked_events source_events …            capture/            consistent
L2 ×7   graph_facts l2_convergence + reasoning_*              ⛔ context/ AND reason/
L3 ×2   expertise_packages tenant_packs                       ⛔ packs/  (Atlas L3 is context/)
L4 ×7   reasoning_* + execution_actions                       ⛔ reason/ AND executive/
L5 ×5   cards delivery_outbox delivery_attempts + executions  ⛔ deliver/ AND executive/
L6 ×4   cards ×2 org_channels delivery_outbox                 ⛔ deliver/
L7 ×4   learning_runs calibration_runs …                      feedback/
```

> ⛔ **The label follows NEITHER vocabulary consistently.** `L3` is `packs/`; `L2`, `L4` and `L5`
> each span two packages. It is a hand-written tag that drifted, and it was never a package
> attribute to count.

```
                        receipts about deliver/   working   lines    lines per guard
  before YCW27                      5               4       9,431        1,886
  today                             8               7      10,020        1,252
  ⛔ what I claimed                  2               1       9,431        4,715
```

⛔ **`1,886` was already true before I wrote a line.** I reported it as what `STEP-10` *achieved*.
Only `every delivered card carries a lane` ERRORs (`cards.output_lane`, `0189`/`0190` unapplied);
the other four read columns from `0008`/`0044`/`0064` and work. The fifth `L5`-labelled receipt,
`decisions become tracked commitments`, reads `executions` and guards `executive/`.

**NOT retracted:** the two new receipts (each shown able to go red), the three rejections
(structurally 0 forever, or already a code property), and the 12-hour window derived from a measured
6.0-hour sweep interval. ⛔ **No assertion depended on the count — which is exactly why the wrong
number survived.** *A guard that asserts the label is correct cannot notice that the label means
nothing.*

**Corrected in 11 documents + 1 test docstring**, each marked in place rather than rewritten.
Full record: `layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md`.
⛔ **I have not touched a single label** — `receipts(layer)` filters on it, so a relabel changes
operator behaviour. That is Rohit's call.

---

## ⛔⛔ 2026-10-02 · L6 SECOND PASS — the loop runs, and is never questioned

`layer-6-learning/00-START-HERE.md` said **`COMPLETE`**. The re-crosscheck found twelve things.
M14's three units ARE done and none is retracted — what was complete was **the attribution
milestone**, not the layer.

```
feedback/   14 files · 3,111 lines   the smallest layer   (12 · 2,737 at M14's crosscheck)
receipts    4, all labelled L7       778 lines per guard — ⛔ the BEST ratio of any layer
tests       60 passed                ⛔ 27 SKIPPED
ledgers     19 written               ⛔ 4 read by NOTHING
```

### ✅ It runs — the opposite of L5

| | Where |
|---|---|
| the learning sweep | `api/routes.py:1274-1278`, **inside the heartbeat** |
| calibration | `api/routes.py:1247-1264`, per org × per active pack, same heartbeat |
| org-rule discovery | `api/upload_routes.py:489`, `api/knowledge_routes.py:94`, on upload |

*"Weekly per tenant, enforced by a PostgreSQL tenant/week claim (not process memory), so it is safe
to call every heartbeat."* **Eleven public functions reached from outside the package.** No cutover
gap, no dead control plane. ⛔ **So this is a READING pass, not a wiring pass.**

### ⛔⛔ And not one of its four guards asks whether the result is right

| Package | Receipts | correctness (`expect(0)` True) | presence |
|---|---|---|---|
| `deliver/` | 8 | **5** | 3 |
| ⛔ **`feedback/`** | **4** | ⛔ **0** | **4** |

**All four are satisfied by a single successful tick.** Nothing asks whether a published brain value
was governed, whether a proposal took a legal transition, whether a rule was muted on enough
evidence, or whether an expired lease actually expired.

⛔ **This retires guards-per-line as a diagnostic.** `feedback/` has the best ratio in the product
and zero correctness guards: *the metric counts guards; it does not read them.* It is also the
metric whose number `08-CORRECTION` had to fix.

### ⛔⛔ The four ledgers nobody reads are the four that would answer those questions

| Ledger | Written at | The question it already holds the answer to |
|---|---|---|
| `learning_transitions` | `publisher.py:34` ⛔ **+ `api/learning_routes.py:141`** | an **illegal** transition? `ALLOWED_LEARNING_TRANSITIONS` already exists |
| `learning_object_evaluations` | `orchestrator.py:197` | a publish with **no material change**, or outside its policy revision? |
| `learning_input_rejections` | `store.py:193`, `org_rule_ingest.py:181` | is the loop **refusing everything**? |
| `learning_metrics` | `publisher.py:151` | *"measurement artifacts (not a brain)"* |

⛔ **`learning_object_evaluations` carries TWO indexes — `_replay` and `_by_run` — for queries
nobody wrote.** An index is a statement that a query exists.

⛔ **And `record_refusal`'s own docstring states the defect**: *"A refusal that lives only in a
return value is indistinguishable from a candidate the model never produced."* The record was
promoted out of a return value into a ledger **with no reader** — so it is indistinguishable one
layer further down. **The fix moved the record and never built the reader.**

### ⛔ All 27 skips are the two files that matter most

```
14  test_org_brain_filled_through_the_routes.py                    ENTIRELY skipped
13  test_behavior_and_adaptive_brains_filled_through_the_paths.py   ENTIRELY skipped
--  every one: "GENIOS_TEST_DATABASE_URL not set — J4's … need real Postgres"
```

⛔ **The two files that prove the brains are actually FILLED are the two that do not run here.**
→ joins Harsh's `H6`.

### ⛔ Two near-misses of mine, both caught before anything was written

| | |
|---|---|
| *`counterfactual_ledger` has no writer* | TRUE, inference FALSE — it is a **VIEW** (`0072`), by design. Second time in two layers; the first was `realtime.purge_expired` |
| ⛔ *the reader scan undercounts* | `context/authority_view.py:55` holds `AUTHORITY_TABLE = "authority_rules"` and builds the query from the constant — **3 readers read as 1**. Every *"read by nothing"* claim was re-verified by direct grep. **A name-constant is a read** |

⛔ Plus: `[a-z_]+` cannot match a digit, so the first resolver read `l2_convergence` as table **`l`**
— fourth time a name-shaped regex produced a confident wrong answer.

### Smaller, each measured

| | |
|---|---|
| ⛔ three documents disagree on the test count | `00-START-HERE` 53 · `01-CROSSCHECK` addendum 87 · measured **60 + 27** |
| ⛔ `00-START-HERE` said `COMPLETE` | and `01-CROSSCHECK`'s own addendum warns about this pattern, **in the same folder** — fourth instance, first inside a file documenting it |
| ⛔ a mover-convention deviation the guard cannot see | `feedback_health.py` uses `MOVES WITH`; the guard requires only *"two parts"*. **A guard hole, not a defect** |
| ⛔ a stale comment in `scripts/wipe_org_data.py:40` | calls `counterfactual_ledger` MATERIALIZED; `0072` says plain and says why. Reason wrong, fix correct. **Sixth instance** |

### The plan — 10 units, nothing built yet

```
U01  the 27 skips                  ⛔ MEASURED on the day it was planned → all DB skips → HARSH
U02  guards per package as DATA    the STEP-10 error, made impossible
U03  an illegal transition         ⛔ gated: CAN IT FAIL? a second writer is the whole question
U04  a publish outside its policy  gated: can policy_revision ever differ?
U05  the refusal ledger            gated: is a refusal-rate receipt able to fail at all?
U06  UNREAD_LEDGERS, engine-wide   ⛔ LAST on purpose — U03–U05 each shrink it
U07  the mover convention          measure the distribution BEFORE touching either side
U08  the Atlas scorecard → L6
U09  the status lines
U10  the stale comment in scripts/
```

⛔ **Nothing is built until the plan is confirmed.** →
`layer-6-learning/06-PLAN-the-second-pass.md`

### Doctrine this pass produced

| Rule |
|---|
| ⛔ **a receipt's layer label is its author's intent; the table it queries is what it guards** |
| ⛔ **"always name the package, never the digit alone" binds the COUNTER as much as the writer** |
| ⛔ **a name-constant is a read** — a table reached through `TABLE = "x"` is invisible to a `from x` scan |
| ⛔ **a presence receipt cannot fail for the right reason** — four of them are one successful tick |
| ⛔ **guards per line counts guards; it does not read them** |
| **a number repeated in eleven documents was derived once — repetition is not corroboration** |
| **a motivation number no step depends on is a number nobody checks** |
| **an index is a statement that a query exists** |


---
---

## ⛔⛔ 2026-10-02 · THE ATLAS CHECK RETRACTED THREE OF MY OWN UNITS — and found two defects they did not contain

**Rohit:** *"tum analyze karke karo na usko"* — and the analysis was the missing step. My L6 plan put
the Atlas verification at `U08`, near the end, and derived its units from the **ledgers** I had
measured. ⛔ **The programme's own Step 0 rule is the opposite:** verify every badge claim by claim
first, because the build order rests on the badges.

```
Rohit_Updates/Secret War Updates/07-Layer-7-Learning-Atlas-6/    six documents · 624 lines
```

### ⛔ The numbering question, settled by the Atlas's own first line

> *"Numbering: this is current code **Layer 7** (`feedback/`) and **Atlas Layer 6**. 'Layer 6' in
> Atlas quotations below does not mean the current `deliver/` package."*

So the receipt labels were **never drifted**. `944b4f76` *("close 97 of 106 audited gaps across all
**seven** layers")* used the `LAYERS.py` vocabulary **consistently** — L5=executive, L6=deliver,
L7=feedback. ⛔ `22d598b1` *("align all **six** product layers — L1 to L6")* put receipts under the
**Atlas** numbering into the same field, **mixing both vocabularies inside one commit** — and
⛔ **I then added three more** under the wrong one, following `lane`'s label.
→ `layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md`, whose §3 this sharpens.

### The eleven Atlas architecture gaps, verified against the working tree

```
   3 CLOSED            #7 counterfactual ledger · #8 the stats zero · #9 approval-must-publish
   4 PARTLY CLOSED     #1 stub units · #4 population floors · #10 policy load · #11 Adaptive TTL
   1 ⛔ LIVE            #2 _cohort_candidate returns []
   ⛔ CORRECTED 2026-10-02 by S4 — #2 is CLOSED. 0 live. See the S4 section below.
   3 not measured      #3 outcome reconciliation · #5 permitted-use · #6 company reset
```

| Atlas said | The code says |
|---|---|
| **#9** *"review approval does not publish"* | ✅ **CLOSED** — *"APPROVAL MUST PUBLISH… left the object approved-but-unpublished. A reviewer who approves has every reason to believe the system now knows something — and it did not."* `_publish_approved` runs in the same transaction |
| **#8** *"the stats endpoint says zero outcomes"* | ✅ **CLOSED** — a real count, and `acted` carries its own fix: the predicate matched `kind` while every writer puts the verb in `cause`. ⛔ **But the handler still says `value_state: "unavailable_no_counterfactual_ledger"` and comments the ledger *"does not exist"* — `0072` creates it** |
| **#10** *"the policy load drops the block lists"* | ⚠️ the `SELECT` is fixed. ⛔ `_as_tuple` still returns `()` for `None` **and any malformed value**, while its docstring says it *"refus[es] to silently invent an empty one"*. **A docstring promising a behaviour the signature makes impossible** |
| **#2** *"Behavior/Adaptive evolution emits nothing"* | ⛔⛔ **LIVE, and now LESS visible** — the two units look wired; `_cohort_candidate`'s entire body is `return []`. **I was one step from recording this CLOSED from the call site alone** |
| ⛔⛔ **#2 — CORRECTED 2026-10-02 BY `S4`** | ✅ **CLOSED, BY REFUTATION.** Both components are built one package down — `packs/brains/behavior_distill.distill` (776 lines) and `packs/brains/adaptive_lease.lease_proposals` (301) — and appended to the same weekly run by `brain_pipeline.brain_pipeline_proposals`. ⛔ The stub predates the implementation by a month. ⛔ **And the row above is itself a wrong conclusion**: *"one step from recording this CLOSED"* — it IS closed. → `layer-6-learning/STEP-S4-DONE-a-silent-unit-names-its-producer.md` |
| **#11** *"Adaptive cannot carry a TTL"* | ⚠️ **PARTLY CLOSED, and my first write-up overstated it.** `packs/brains/adaptive_lease.py` already implements the Atlas's option B — `RUNTIME` → `temporary_memories`, 7-day TTL clamped to the tenant ceiling, enforced three ways. ⛔ **A file's NAME was the counter-evidence.** The residue is ONE producer |

### ⛔⛔ The sharpest live defect — one unit, verified end to end

```
units.py:452    unit_recommendation_learning → target=ADAPTIVE, _org_visibility()   ⛔ not a stub
governance:53   preflight  → "org-derived — ALLOWED"   ⛔ THREE expiry checks for RUNTIME, NONE
                                                           for ADAPTIVE
governance:112  govern     → PROMOTED, "auto_promote"  ⛔ no human review
publisher:95    publish_brain → learned_brain_entries, active=true, ⛔ no expiry column at all
contracts:226   expires_at → raises unless the target is RUNTIME
```

| | |
|---|---|
| **the shape** | four sibling units emit rates and counts to `METRICS`; this one emits `success_rate_bp`, `attention_per_outcome_bp`, `efficacy_bp` to **`ADAPTIVE`** |
| ⛔ **the boundary it breaks** | the Atlas's authority boundary for this exact unit is **"No self-training from recommendation score."** `packs/compiler/runtime_brains.py:497` selects `brain in ('organization','behavior','adaptive')` **into the compiled expertise package**, and the recommender reasons from it. **The score trains the thing that produced it** |
| ⛔ **and the user is promised otherwise** | `api/brain_routes.py:106` — the adaptive brain *"Moves this current signal forward in the executive brief **while it applies**."* The durable half cannot express "while" |
| ⛔ **the principle, in the codebase's own words** | `adaptive_lease.py`: *"**a lease that never expires is a permanent memory wearing a temporary label**… it is the entire difference between this brain and the Organization brain"* |

## ✅⛔ S1 BUILT — the violation is held as data, and the repair is NOT mine

⛔ **I did not fix it.** All three repairs — add TTL/decay to `ADAPTIVE`, prohibit durable `ADAPTIVE`
publication, retarget the unit to `METRICS` — change what the Adaptive brain **contains**, and the
pack compiler reads it. **Rohit's.**

```
genios_engine/feedback/target_policy.py    UNIT_TARGETS (11 units, target + why)
                                           DURABLE_FROM_A_MEASUREMENT — the declared violation
                                           DURABLE_BRAIN_TARGETS — asserted == publisher's
tests/feedback/test_a_unit_may_not_write_a_durable_brain_from_a_measurement.py    27 tests
genios_engine/feedback/feedback_health.py  +4 declared silences (build-time property guards)

⛔ mutations:  baseline clean  →  M1 drifted · M2 missing · M3 undeclared · M4 drifted
               4 caught · 0 survived  →  baseline clean again
```

⛔ **And the harness refused to score two mutations it could not apply** — M2 and M3's first anchors
had the wrong comment spacing and the run printed *"ANCHOR MISSING — counts nothing"*. That is the
direct repair of `STEP-14`, where a stale anchor let a survivor be reported as caught.

### ⛔ Three faults of mine inside this one unit, each now a regression test

| | Fault |
|---|---|
| 1 | ⛔ **`grep 'target=LearningTarget'` finds NINE of eleven.** `behavior_evolution` and `adaptive_evolution` pass their target as a keyword *into* `_cohort_candidate`. **A grep for a keyword argument misses the call that passes it through** |
| 2 | ⛔ `ALL_ANALYSIS_UNITS` is an **`ast.AnnAssign`**, not an `ast.Assign`. My resolver matched only `Assign`, found zero units, and `missing_units()` reported all eleven declarations as stale. ⛔ **The second direction caught the first direction's resolver** |
| 3 | ⛔ `_proposes_something` saw only *delegation* to a `[]`-returning helper, so it called `unit_preference_learning` — whose own body **is** `return []` — a proposer |

### ⛔ A measurement nothing had recorded

```
eleven analysis units run every weekly pass — ⛔ FOUR cannot emit a proposal at all:
   unit_preference_learning · unit_temporary_memory        declared stubs, "until the inbox lands"
   unit_behavior_evolution  · unit_adaptive_evolution      ⛔ Atlas gap #2, via _cohort_candidate
   ⛔ CORRECTED by S4: they propose nothing AND their work is built in packs/brains/ —
   ⛔ a PLACEHOLDER, not a gap. Declared in target_policy.DELEGATED, five links guarded.
```

⛔ **That distinction narrows the finding from three violations to one.** Both evolution units also
declare durable brains; they are excluded because they propose nothing. **Without it the report
names three alarms where there is one finding.**

### Doctrine

| Rule |
|---|
| ⛔ **a plan derived from the code alone cannot find a gap the code is silent about** |
| ⛔ **a call site that looks wired is not a wired call site** |
| ⛔ **a grep for a keyword argument misses the call that passes it through** |
| ⛔ **a file's NAME can be the counter-evidence** — `adaptive_lease.py` narrowed gap #11 |
| ⛔ **a totality guard that runs one way is half a guard** — the second direction caught the first's resolver |
| ⛔ **a mutation whose anchor did not match counts nothing, and the harness must say so** |
| ⛔ **the fix for a wrong reason is the reason, not the answer** |
| **a copy that can disagree with the thing it copies is worse than no copy** |
| **hold a violation as data when the repair is not yours to make** |


---
---

## ✅⛔⛔ 2026-10-02 · S2 BUILT — the North Star ledger has never had a writer

**Planned as** *"a stale `value_state` string — contained, and do NOT invent a value."*
⛔ **The measure-first gate turned it into the sharpest product-level finding in the layer.**

### The gate, three steps, and each one moved the finding

```
step 1   does anything branch on the literal?      ⛔ NO — the only occurrence was the writer itself
step 2   does the counterfactual ledger exist?     ⛔ YES — migration 0072, and it has a receipt
step 3   then what WOULD carry a rupee value?      ⛔⛔ macv_ledger — and nothing writes it
```

### ⛔ The claim was wrong in two ways at once

`api/intelligence_routes.py` returned `value_state: "unavailable_no_counterfactual_ledger"` and
commented *"value attribution needs the counterfactual ledger (L7-12), **which does not exist**."*

| | |
|---|---|
| ⛔ wrong 1 | it **exists** — `0072`, a view joining signal → card → `card_events` → verdict → `delivery_outbox` → `executions` → `execution_outcomes` → `llm_costs`, one row per recommendation, with a receipt. **Atlas gap #7 is CLOSED** |
| ⛔ wrong 2 | it was never the ledger that would carry money. It answers *"did this lead to anything"*. **No monetary column** — and neither has `execution_outcomes` (a label and durations) or `llm_costs` (tokens only) |

> ⛔ **The first sentence of that comment is one of the best in the repository and the citation under
> it was false.** *The principle was right; the evidence it pointed at was not.*

### ⛔⛔ THE FINDING · `macv_ledger`, and only the delete list knows it

`migrations/0012_l6_feedback.sql:35` — *"F8 MACV ledger — **the North Star**. caught→acted→resolved;
distinct-deal SUM + non-deal COUNT (anti-inflation double-count rule). **The number the customer can
verify**."* Columns `period`, `deal_id`, `amount`, `resolved_signal_id`.

```
migrations/0012_l6_feedback.sql        creates it, names it the North Star
migrations/0033_org_data_cascade.sql   the org cascade FK
api/account_routes.py:670              ⛔ the DELETION list
tests/test_reasoning_retention.py:27   ⛔ the retention test's table list
docs/LAYER_MAP.md:15                   ⛔ claimed feedback/ WRITES it — it does not
```

> ⛔⛔ **Five occurrences repo-wide and not one is a read or a write. The only code that touches the
> product's headline value ledger is the code that deletes it.** *A record nobody reads is presence
> without effect* turned inside out: both of its code references say "remember to wipe this."

⛔ **`None` stays.** Reading the empty ledger to report `0` would be exactly the defect the handler's
own first sentence exists to prevent. **So this was a REASON change, not a value change.**

### What changed

| File | Change |
|---|---|
| `api/intelligence_routes.py` | the false citation replaced with the measurement (quoting the old sentence so the record survives) · `value_state` → **`"unavailable_macv_ledger_has_no_writer"`** · ⛔ **the docstring**, which said *"ROI / intervention rate stay null"* and was stale in **both** halves: `intervention_rate` is computed from `acted / fired`, `outcomes_recorded` is a real `count(*)` |
| `docs/LAYER_MAP.md` | the `feedback/` cell said *"Precision windows, nudges, mutes, MACV."* ⛔ **MACV removed** — and the other three asserted real by test, because *correcting one cell is where a second false claim slips in* |
| `tests/api/test_the_value_is_withheld_for_the_right_reason.py` | **18 tests** |

### ⛔ The rename, and the risk taken knowingly

Measured first: **nothing in this repository branches on the literal**, and `value_state` has only
ever had **one** value, so no client can be switching on a set. ⛔ **A client OUTSIDE this checkout
cannot be measured from here, and I am saying so rather than implying I checked.** One that
string-matches falls through to its default — strictly better than showing a founder a false cause.

### ⛔ The guard's teeth point at the reason

```
✅ baseline: 18 passed
  M1 · the FALSE ledger name back in value_state      ✅ CAUGHT (2 failed)
  M2 · value_recovered_inr becomes 0                  ✅ CAUGHT
  M3 · a WRITER appears for macv_ledger               ✅ CAUGHT
  M4 · a READER appears for macv_ledger               ✅ CAUGHT
  M5 · the false claim ASSERTED again, unattributed   ✅ CAUGHT
  M6 · LAYER_MAP claims MACV again                    ✅ CAUGHT
✅ baseline again: 18 passed            6 caught · 0 survived
```

**Add an `insert into macv_ledger` anywhere in `genios_engine/` or `scripts/` and the guard fails**,
naming the endpoint, its comment and `LAYER_MAP.md` as the three things to update together.

### ⛔⛔ My own fault — and the rule was in the docstring of the test that broke on it

My first guard asserted the old false sentence was **absent**. ⛔ **It failed on the correct fix**,
because the corrected comment **quotes** that sentence in order to say it is false — and the
docstring directly above the assertion read *"a grep for a known-false phrase matches the record of
its own correction."*

> ⛔ **Eighteenth instance in this programme, and the first where I wrote the rule into the docstring
> of the test that then violated it.**

The repair generalises: ⛔ **a guard must check ATTRIBUTION, not PRESENCE** — the phrase may appear,
and every occurrence must sit within four lines of a marker identifying it as the old wording. A
relapse adds an **unmarked** occurrence and fails, which `M5` proves.

⛔ **Measured scope of the consequence, and what it is NOT:**

```
584   assert "..." not in <anything>                                   across tests/
104   assert "..." not in src|code|source|text|blob|content|body       ⛔ SOURCE-TEXT guards
```

⛔ *"104 broken guards"* **would be an overstatement** and this programme has paid for those. Most
assert a **construct** is absent (`"insert into" not in source` proving a module is read-only).
**All 104 are structurally vulnerable** — the moment anybody documents the forbidden thing in a
comment, including to explain why it is forbidden, the guard fires on correct code — but **which are
actually at risk needs 104 readings**, and that reading is `S9`'s.

### ⛔ And the "read this first" page was stale for two days

`STATUS.md`'s head said `Updated 2026-09-30` and `EVERY SECTION IS BUILT · L5 ✅ · L6 ✅` while
~1,000 lines were appended below it, L5 took **17** steps rather than 4, and L6 was **re-opened**.
⛔ **Fixed by splitting the two jobs:** the log below stays append-only and chronological; the head
now carries a **reverse-chronological index**, so nobody scrolls 2,800 lines to learn what is true.

### What this hands to Rohit

⛔ **The product's headline number has no producer.** `macv_ledger` was designed as `feedback/`'s job
— it lives in `0012_l6_feedback.sql` and `LAYER_MAP` listed it there — and the writer was never
built. ⛔ **Not a quiet fix:** what counts as recovered value, which deals attribute, and the
*"anti-inflation double-count rule"* the migration names are product decisions, and
`distinct-deal SUM + non-deal COUNT` is a specification nobody implemented.

```
full suite   14,891 passed · 1,067 skipped · 152 xfailed · 0 failed      (14,873 before S2)
```

### Doctrine

| Rule |
|---|
| ⛔ **a guard must check attribution, not presence** — a correction quotes what it corrects |
| ⛔ **the fix for a wrong reason is the reason, not the answer** — and measuring the reason moved this from a comment fix to a product finding |
| ⛔ **a table nobody writes is not a table nobody built** |
| ⛔ **a ledger that appears only in the delete list is presence without effect, inside out** |
| ⛔ **correcting one cell is where a second false claim slips in** — assert the survivors |
| ⛔ **a paragraph that says "this session" has no date in it, and reads as today until somebody checks** |
| **a string that states a fact about the repository must be checked against the repository** |
| **say what you could not measure** — a client outside this checkout is invisible from here |


---
---

## ✅⛔⛔ 2026-10-02 · S3 BUILT — an empty prohibition list is a decision; a NULL one is an absence

**Atlas Layer 7 gap #10 — CLOSED.** *"Loaded policy is weaker than stored policy."*

### ⛔ The fail-OPEN, and the comment that described the guard that did not exist

`learning_policies.blocked_targets` / `.blocked_subject_prefixes` are nullable `jsonb` (`0045`) and
the seed writes `cast('[]' as jsonb)` with this comment:

> *"Seeded EMPTY rather than NULL: an empty prohibition list is a decision ("nothing is blocked"),
> NULL is an absence. **Keeping them distinct is what lets the guard below tell a deliberate empty
> policy from one that failed to load**."*

⛔⛔ **There was no guard below.** `_as_tuple` returned `()` for `None`, a dict, a bare string and a
list of integers alike — so a tenant whose *"never learn about these targets"* list failed to read
was indistinguishable from one who blocks nothing, and `preflight` returned **`admitted`** for the
exact target they meant to forbid. **The database kept the two apart and the load collapsed them one
line later.**

⛔ **And the helper could not keep the promise in its own docstring** — *"refusing to silently invent
an empty one"* — because it received only the value, never the revision. *A docstring can promise a
behaviour the signature makes impossible.*

### Built bottom-up, five units

| | Unit | Why there |
|---|---|---|
| 1 | `contracts/learning.py` — `prohibitions_state` (`loaded` / `absent` / `malformed`) | ⛔ **a tuple has no third state**, which is why the collapse was invisible. Default `loaded`: a policy authored in code is trusted; only one reconstructed from a row can fail. ⛔ The constructor does **not** refuse an untrusted policy — it must be constructible to *represent* the failure |
| 2 | `orchestrator._prohibition_list` / `_prohibitions` | ⛔ the two bad shapes fail in **opposite** directions — `[1,2]` blocks nothing, `[""]` blocks everything via `startswith("")` — so neither may be repaired silently. Both columns take the **worse** state and return empty for both: *an untrusted list is not partially usable* |
| 3 | `governance.preflight` | ⛔ **before** the block-list checks, or it is never reached. And **all three producers** call this exact function — `run_learning`, `brain_pipeline.admit_proposals`, `org_rule_ingest.run_org_discovery` |
| 4 | `run_learning` | ⛔⛔ **before `_claim_week`.** `on conflict (org_id, week_key) do nothing` means a claimed week stays claimed — **a fail-closed after the claim converts a policy problem into a lost week.** The harm appears only on the *second* tick, so it is asserted on the AST |
| 5 | `run_learning_sweep` | ⛔ it returned `{orgs, passes, skipped}` — **consent-off, already-ran and a crashed tenant were the same number.** A refusal nobody can see is a silent stop. *The reader is half the unit* |

### ⛔ The two refusals are now told apart by name

```
a loaded block list containing "organization"  → target_blocked               ← the tenant's DECISION
a stored revision with NULL                    → policy_prohibitions_absent   ← our ABSENCE
                                                  ⛔ before this change: ADMITTED
```

### The mutation run — baseline first, 8/8

```
✅ baseline: 40 passed
  M1 delete the preflight gate      ✅   M5 a bad column stops poisoning the other  ✅
  M2 claim the week BEFORE the gate ✅   M6 the sweep stops reporting WHY           ✅
  M3 NULL becomes "loaded" again    ✅   M7 the seed writes NULL instead of []      ✅
  M4 coerce non-strings             ✅   M8 the contract accepts an unknown state   ✅
✅ baseline again: 40 passed          8 caught · 0 survived
```

### ✅ A false finding refuted before it was written

`load_or_seed_policy` selects `knowledge_requires_review` and then passes a literal `True`. I began
writing *"a selected column that configures nothing."* ⛔ `0045:37` holds
`check (knowledge_requires_review)` and the table comment says *"**CHECK-locked true** — it can
never be disabled."* **An invariant in three places; the column is redundant, not misleading.**
⛔ **Sixth time verifying a suspicion first prevented a false finding.** *A redundant read is not a
lie; a lie is a read whose value could differ and does not matter.*

### What I could not measure

⛔ **Whether any stored row holds NULL today is unknowable from this checkout** — the seed's own
comment implies it was changed, so legacy rows are possible. **That is why the fail-closed is a
SKIP, not an exception**: a legacy row does not burn the week, and the tenant resumes on the next
tick once somebody backfills `[]`. The settling query is
`select revision, blocked_targets is null, blocked_subject_prefixes is null from learning_policies`
inside `set transaction read only`.

```
full suite   14,931 passed · 1,067 skipped · 152 xfailed · 0 failed      (14,891 before S3)
```

### Doctrine

| Rule |
|---|
| ⛔ **an empty list is a decision and a NULL is an absence — a type with two states cannot hold three** |
| ⛔ **a fail-closed placed after the claim converts a policy problem into a lost week** |
| ⛔ **a refusal nobody can see is a silent stop, and worse than the fail-open it replaces** |
| ⛔ **two malformed shapes can fail in opposite directions — neither may be repaired silently** |
| ⛔ **an untrusted list is not partially usable** |
| ⛔ **a docstring can promise a behaviour the signature makes impossible** |
| **the gate goes where every producer passes, and the skip goes where the cost is paid** |
| **a redundant read is not a lie** — verify a suspicion before writing it up |


---
---

## ✅⛔⛔ 2026-10-02 · S4 BUILT — the Atlas's only LIVE gap was a wrong conclusion, not missing code

**Atlas Layer 7 gap #2 — CLOSED, BY REFUTATION.** *"Direct personalization evolution is missing.
Behavior and Adaptive cohort builder returns no proposals."*

### ⛔ The gate said "build, or DECLARE". The answer was neither: MEASURE WHERE THE WORK IS

`genios_engine/packs/brains/__init__.py`, first paragraph:

> *"Layer 3 · the CONTENT pipelines for the three runtime brains … **This package is the supply
> side** … The drivers live on the Layer 6 side — `feedback/brain_pipeline.py` (the evidence route)
> and `feedback/org_rule_ingest.py` (the declaration route)."*

```
packs/brains/behavior_distill.py   776 lines  distill()         → LearningTarget.BEHAVIOR
packs/brains/adaptive_lease.py     301 lines  lease_proposals() → LearningTarget.RUNTIME, 7-day TTL
```

…and `brain_pipeline_proposals` appends both into the **same weekly run**, each inside a
`begin_nested()` savepoint, from the line directly after `run_all_units`:

```python
proposals = list(run_all_units(batch, policy, now))                      # the 11 units
proposals.extend(brain_pipeline_proposals(conn, org_id=org_id, policy=policy, now=now))
```

### ⛔ The stub outlived its replacement by a month

```
365cf7a6  2026-08-08  "Layer 6 Phase 3: the ten analysis units"   ← _cohort_candidate, the stub
ed1b10c3  2026-09-07  "Layer 3 v2: … the four brains …"           ← the real producers
```

The work was built one package down and the placeholder was never removed or declared, so
`ALL_ANALYSIS_UNITS` — the one list a reader scans to see which Layer 7 components exist — still
shows a silent unit where a built component belongs.

### ⛔⛔ Two readers reached the same wrong verdict from the same evidence

| | |
|---|---|
| the **Atlas** | *"Behavior Evolution \| calls a cohort builder that returns `[]` \| **Stub**"* |
| ⛔ **this programme** | `07-ATLAS-CHECK` filed #2 as *"LIVE — and now less visible than the Atlas found it"* |

⛔ **And that note was itself a wrong conclusion.** It read *"I was one step from recording this as
CLOSED from the call site alone"* — **it IS closed.** The call site was the wrong evidence in both
directions. ⛔ **A call site that looks wired is not a wired call site — and a call site that looks
DEAD is not a dead feature.**

⛔ **One grep made it worse:** `behavior_distill.py:551` reads *"NOTHING wires this adapter today"*
— about the optional **LLM labeler**, not about `distill`. **A grep hands over a sentence without
its subject.**

### What was built: a declaration, and five links

⛔ **The placeholders stay.** Deleting them would take the Atlas's component names out of the
canonical registry, and they cost nothing: they return `()`.

| | Link | What losing it looks like |
|---|---|---|
| 1 | the producer file and function exist | a rename; the registry still lists the component |
| 2 | the producer does work — not `return []`/`()`, **and not a body with no calls** | a chain of placeholders reading as a built feature |
| 3 | `brain_pipeline_proposals` calls it | one component silently stops |
| 4 | `run_learning` calls that driver | ⛔ **both** stop, from one deleted line |
| 5 | ⛔ the producer still emits the **declared target** | the SINK changes — expire, wait for a human, or become permanent |

⛔ **Link 5 closes a blind spot in `S1`'s guard.** `durable_from_a_measurement()` reads
`UNIT_TARGETS`, which is `units.py`'s registry — so *"which producer may write which brain"* was
guarded for **eleven units** and **unguarded for the two that actually produce.** *A guard that
stops at a package boundary catches nothing across it.*

### The two sinks, and why only one needs a clock

| Producer | Target | Bounded? |
|---|---|---|
| `adaptive_lease.lease_proposals` | **`RUNTIME`** | ✅ `temporary_memories.expires_at` is `NOT NULL`; 7 days clamped to the tenant ceiling; enforced three ways |
| `behavior_distill.distill` | **`BEHAVIOR`** (durable) | ⛔ **correct here** — a behaviour pattern is a **CLAIM**, like `pattern_learning`'s ORGANIZATION proposals, and the Atlas's boundary for it is *"population and identity scoped"*, not *"decays and expires"* |

So `DURABLE_FROM_A_MEASUREMENT` still has **exactly one** entry, and a test asserts `S4` did not
move `S1`'s finding while widening its guard.

### ⛔ One widening I stopped myself from making

`unit_temporary_memory` returns `[]` and `adaptive_lease` writes exactly its sink. I began adding it
to `DELEGATED`. ⛔ **The inputs differ** — that unit wants an **explicit human directive** from an
inbox that does not exist; `adaptive_lease` **infers** a lease from card verdicts. **Same sink,
different input**, so recording it as a delegation would have been a lie about which capability
exists. **Atlas gap #1's residue is real.**

### The mutation run — and one invalid mutation, reported honestly

```
✅ baseline: 50 passed            (23 from S4 + 27 from S1, run together)
  M1 link 4 driver call removed   ✅     M5 ⛔ the LEASE becomes a DURABLE row   ✅
  M2 link 2 producer stubbed      ✅     M6 the shared stub gains a body         ✅
  M3 link 3 driver stops calling  ✅     M7 a DELEGATED entry is lost            ✅
  M4 link 5 SINK → METRICS        ✅     M8 link 1 producer renamed              ✅
✅ baseline again: 50 passed          8 caught · 0 survived
```

⛔ **`M2` SURVIVED on its first run and the fault was the mutation.** I appended the stub
`def distill(...)` **before** the real one — at module level Python's **last** definition wins — so
it was dead code, not a stub, and the guard was right to pass. ⛔ **An invalid mutation is not a
surviving mutation**, and the distinction exists only because the harness reported the survival
instead of rounding it up. `STEP-14`'s lesson, holding in the opposite direction.

### Atlas Layer 7 after S4

```
   5 CLOSED            #2 (by refutation) · #7 · #8 · #9 · #10
   3 PARTLY CLOSED     #1 the two inboxes · #4 population caps · #11 the ADAPTIVE residue (Rohit's)
   0 ⛔ LIVE            — none
   3 not yet measured  #3 outcome reconciliation · #5 permitted-use · #6 company reset

full suite   14,954 passed · 1,067 skipped · 152 xfailed · 0 failed      (14,931 before S4)
```

⛔ **No Atlas Layer 7 gap is fully LIVE any more.**

### Doctrine

| Rule |
|---|
| ⛔ **a call site that looks DEAD is not a dead feature** — the mirror of `S1`'s rule, and it cost two readings |
| ⛔ **a grep hands over a sentence without its subject** |
| ⛔ **a guard that stops at a package boundary catches nothing across it** |
| ⛔ **an invalid mutation is not a surviving mutation** |
| ⛔ **same sink, different input is not the same job** |
| **a placeholder that names its replacement is worth more than a deleted one** |
| **a stub of any shape calls nothing** |


---
---

## ✅⛔⛔ 2026-10-02 · S5 BUILT — the inbox landed, and nothing consumes it

**Atlas Layer 7 gap #1's residue — ⛔ NARROWED from *"no inbox"* to *"no `kind`"*.**

### ⛔ One grep changed the unit

`08-PLAN-v2` priced this as two declared silences: *"a structured preference inbox is a surface that
does not exist."* Then `orchestrator.py:188` turned out to mention an inbox.

```
migrations/0046_l6_learning_hardening.sql   learning_event_inbox — idempotent, with a lease
reason/moments/store.record_feedback        ⛔ INSERTS a row per moment-feedback action
api/moment_routes.py:746                    ⛔ reached in PRODUCTION
feedback/store.py                           loaded into EVERY weekly batch as `batch.inbox`
feedback/units.py                           ⛔ NO unit reads it  (asserted on the AST)
orchestrator.run_learning                   counts the drop as `inbox_unconsumed` → learning_runs.counts
```

And the orchestrator's own justification for that counter read:

> *"Empty at both ends today, so it costs nothing — **but the day something starts writing to that
> table**, rows would be read and dropped on the floor with no counter moving anywhere."*

> ⛔⛔ **That day had already come, and the comment's own prediction is what happened.** The
> reasoning was right; only the premise went stale.

### ⛔ The gap is a `kind`, not a table — and that decides who can close it

Every row carries `payload.kind == "moment_feedback"` — a card action, not an explicit first-person
instruction with a subject, a scope and exceptions.

| | |
|---|---|
| a **table** | a migration. The inbox exists, idempotent on `(org, actor, source_ref)`, with `payload`, `visibility`, `observed_at` and ⛔ a **`lease_until`** column for exactly a dated directive |
| a **`kind`** | ⛔ a **SURFACE** where a founder states a preference or a dated directive. **There is none** |

⛔ **Everything downstream of `unit_temporary_memory` is already built** — `LearningTarget.RUNTIME`,
`govern()` → `TEMPORARY`, `publish_runtime` → `temporary_memories` with `expires_at NOT NULL`,
`preflight`'s three expiry checks, `expire_leases`. **The missing input is the whole of the gap.**

⛔ **And not a model.** The Atlas, now quoted in the code: *"Adding a model directly to empty units
would produce eloquent ungrounded preferences. **First wire typed evidence**."* Its improvements
table makes the **inboxes** P1 — not the extraction.

### ⛔⛔ What was BUILT: the layer's first correctness receipt

The re-crosscheck measured `feedback/` at **four receipts, all four presence checks.** ⛔
`inbox_unconsumed` was written into `learning_runs.counts` every week and **read by nothing.**

```
receipts            35 → 36
feedback/ receipts  4 → 5      ⛔ CORRECTNESS: 0 → 1
```

⛔ **The claim guards the VISIBILITY, not the drop.** `inbox_unconsumed > 0` is the known state of a
declared gap, and `platform/receipts.py` already carries the rule: *"a gate that is always red is a
gate nobody reads. The claim is the one that is true today and false when it gets worse."* So the
receipt asks whether the count is **recorded at all** — delete the counter, or complete a run
without it, and it goes red.

### The mutation run — baseline first, 8/8

```
✅ baseline: 27 passed
  M1 the receipt is removed              ✅   M5 the stale sentence re-ASSERTED   ✅
  M2 ⛔ the ALWAYS-RED claim              ✅   M6 expires_at loses NOT NULL        ✅
  M3 the count stops being persisted     ✅   M7 a SECOND inbox writer appears    ✅
  M4 ⛔ a unit consumes the inbox          ✅   M8 a NEW inbox kind appears         ✅
✅ baseline again: 27 passed          8 caught · 0 survived
```

⛔ `M4` and `M6` reported **"ANCHOR MISSING — COUNTS NOTHING"** first time (a line-wrapped docstring,
a differently-spaced column), were fixed and re-run. *An invalid mutation is not a surviving
mutation.*

### ⛔⛔ My own fault — the same class, THIRD time in one session

My guard read `assert "batch.inbox" not in units` and **failed on correct code**: the corrected
docstring I had just written **explains** that the inbox is *"loaded into every weekly batch as
`batch.inbox`"*. ⛔ **A docstring that explains a gap contains the words of the gap.**

| | The three |
|---|---|
| `S2` | asserted a false phrase was absent; the correction **quoted** it |
| `S2` again | the rule was in the **docstring of the test that broke on it** |
| ⛔ **`S5`** | asserted a **code** string was absent from a file whose **documentation** names it |

> ⛔ **The sharper form: for a claim about code, check the AST — not the text, and not even
> attribution.** An attribution window would have passed here and would have been the **wrong
> tool**: the question is not *"who said this"* but *"does any unit read this attribute"*. The guard
> now walks the AST for `*.inbox` **and** `getattr(batch, "inbox", …)`.

⛔ **This widens `S9` again:** of the 104 source-text guards, those asserting a CODE fact need the
AST, not an attribution window.

```
full suite   14,981 passed · 1,067 skipped · 152 xfailed · 0 failed      (14,954 before S5)
```

### Doctrine

| Rule |
|---|
| ⛔ **a claim about code must be checked against the AST, not against the text** |
| ⛔ **a docstring that explains a gap contains the words of the gap** |
| ⛔ **the gap is a `kind`, not a table** — a table is a migration, a `kind` is a surface |
| ⛔ **a gate that is always red is a gate nobody reads** — guard the visibility, not the known drop |
| ⛔ **a comment's reasoning can be right while its premise goes stale** |
| **the missing input can be the whole of the gap** |


---
---

## ✅⛔⛔ 2026-10-02 · S6 BUILT — every refusal is named, and an illegal lifecycle edge was being written

**Planned as *"the four unread ledgers, demoted to monitoring."*** ⛔ **Asking each ledger what
question it would answer found two live defects.**

### ⛔⛔ 1 · The no-silent-drop contract, broken in nine lines

```python
ok, _ = validate_learning(obj, policy)       # ⛔ the reason is DISCARDED
if not ok: held += 1; continue                #    counted, never named
if not preflight(obj, policy, now=now).ok:    # ⛔ PreflightResult.reason_code DISCARDED
    refused += 1; continue
decision = govern(obj, policy)
if decision.rejected: refused += 1; continue  # ⛔ GovernanceDecision.reason_code DISCARDED
```

The Atlas: *"Every rejected or deferred candidate must retain run_id, tenant, unit, evidence IDs,
**reason code**, failed gate, policy version, timestamp, and recovery status… **A weekly sweep that
returns zero objects without this accounting is operationally indistinguishable from broken
wiring.**"*

⛔ **And `migrations/0046` names the held case itself** — *"append-only: every actual per-run
decision (new or **HELD** object)"*. ⛔ **No migration was needed**: the ledger already carries every
field the Atlas asks for, and `learning_id` has **no foreign key**, so a proposal that never reached
`persist` can still be recorded. *Checked before writing.*

### ⛔⛔ 2 · `governed → published` — illegal, live, on every brain publish

```
ALLOWED_LEARNING_TRANSITIONS[GOVERNED] = (temporary, human_review, promoted, rejected)
learning_can_transition(GOVERNED, PUBLISHED) = False                      ⛔ ILLEGAL
```

`publisher.publish()` fixes `from_state = GOVERNED`, reassigns `target_state = PUBLISHED` after a
brain publish, and logs **once**. ⛔ The map's own docstring states **two hops** and the publisher
skipped `PROMOTED` — the state that distinguishes *"promoted, publisher not yet done"* from
*"published"*, which is exactly the ambiguity the Atlas's **`L7-30`** names.

> ⛔ **`ALLOWED_LEARNING_TRANSITIONS` existed from the start and nothing checked it on this path** —
> because `learning_transitions`, written by five call sites, is read by **none**.

### ⛔⛔ 3 · And my retraction of `U03` was wrong

`07-ATLAS-CHECK` §3 retracted *"an illegal learning transition"* because *"its gate question — does
the second writer validate? — is answered by Atlas #9."* ⛔ **That conflated two questions.** The
second writer (`api/learning_routes.py`) is the repaired approval path and both its edges are legal;
the **first** writer was emitting the illegal edge, and I never looked at it.

> ⛔ **Fifth retraction in this programme, and the first of a RETRACTION.** *A retraction is a claim
> like any other and needs its own evidence, not a neighbouring fact.*

### What changed

| File | Change |
|---|---|
| `feedback/orchestrator.py` | all three refusal paths record their reason; `evaluations` counts every row and enters `counts` as the receipt's marker |
| `feedback/publisher.py` | the missing `governed → promoted` hop; ⛔ `log_transition` **refuses** an illegal edge and an unknown state, exempting `from_state=None` |
| `platform/receipts.py` | ⛔ **two** correctness receipts; `_ILLEGAL_TRANSITION_SQL` derives its 23 legal pairs **from the contract** |

```
receipts                     36 → 38        feedback/ CORRECTNESS   1 → 3   (0 before S5)
unread ledgers of the four    4 → 2
```

⛔ **Six call sites were enumerated before the raise was added.** One writer — the API review route
— uses raw SQL because it builds a deterministic id for idempotency that `new_id("ltr")` would
break; both its edges are legal and a test asserts that from its own source. **An unguarded writer
that is checked at build time is not an unguarded writer.**

### The mutation run — baseline first, 9/9

```
✅ baseline: 46 passed
  M1 the publisher goes back to ONE hop     ✅   M6 ⛔ the MAP is WIDENED so the bug
  M2 log_transition stops validating        ✅      becomes legal           ✅ (3 failed)
  M3 the reason is DISCARDED again          ✅   M7 the legal set is hand-copied   ✅
  M4 a refusal path stops recording         ✅   M8 persist's edge stops being excluded ✅
  M5 the marker key is dropped              ✅   M9 a reader appears for learning_metrics ✅
✅ baseline again: 46 passed              9 caught · 0 survived
```

⛔ **`M6` is the one that matters most.** Widening the map so `governed → published` becomes legal —
**the "fix" that weakens the verify instead of the code** — is caught by **three** tests. *Never
weaken a verify to make it pass* is now enforced rather than remembered.

### ⛔ What this hands to Rohit

```sql
set transaction read only;
select from_state, to_state, count(*) from learning_transitions group by 1, 2;
```

A `governed → published` row means a brain value **was** published before today's fix. ⛔ **No rows
at all** means **no brain value has ever been published** — `L7-27`'s question, and the same answer
the Adaptive decision (`#11`) needs.

```
full suite   15,027 passed · 1,067 skipped · 152 xfailed · 0 failed      (14,981 before S6)
```

### Doctrine

| Rule |
|---|
| ⛔ **a retraction needs its own measurement, not a neighbouring one** |
| ⛔ **a counted refusal is not a named refusal** |
| ⛔ **the reason the callee computed is the reason to record** |
| ⛔ **derive the legal set from the contract; a copied list drifts in the permissive direction** |
| ⛔ **never weaken a verify to make it pass** — enforced by three tests now |
| ⛔ **an unguarded writer that is checked at build time is not an unguarded writer** |
| **enumerate every caller before adding a raise** |
| **a guard at the writer protects the future and says nothing about the past** |


---
---

## ✅⛔⛔ 2026-10-02 · S7 BUILT — the count becomes data, and a lost seam gets a name

**Two halves, both planned as `S7`.**

### PART b · ⛔⛔ a seam we threw away was reported as a seam that had nothing

`08-PLAN-v2` planned a refusal-rate receipt over `learning_input_rejections` *"once a denominator
exists"*. ⛔ **It already does, and not there**: `org_rule_discovery_runs.counters` holds
`candidates`, `admitted`, `human_review`, `refused` and `refused_<reason>` per run, in a table that
**is** read. The discovery route's accounting is complete — **the gap was the ledger's other
writer.**

`store._read_optional_seam` catches a read that raises, records it, and returns `()`. Its own
comment: *"nothing in the codebase ever wrote to it… an input the system deliberately quarantined
was indistinguishable from one that never arrived. **That is the no-silent-drop contract failing in
the one place built to uphold it.**"* ⛔ **The WRITE was built and the READ never was** — and the
return value stayed `()`, so *"no human has judged a card yet"* and *"the verdict table read raised
and we threw it away"* were one line in `degraded_seams`. Atlas **`L7-29`** requires the **empty
reason**.

### ⛔⛔ And the delivery seam was reported degraded on EVERY run, forever

```python
("deliveries", getattr(batch, "deliveries", ())),   # ⛔ the field is `delivery`
```

The default fired every time, so `degraded` was **always True**. ⛔ *A flag that is always set is a
flag nobody reads.* ⛔ **A `getattr` with a default converts a wrong attribute name into a plausible
value** — on a dataclass it would have raised immediately. The seam names now live beside
`LearningBatch` and a test asserts each is a real field.

### PART a · ⛔⛔ guards per package, derived — and `STEP-10` was aimed at the wrong package

```
package     receipts  correctness    lines  lines/guard
feedback           9            5    4,040          448     ← best
reason             8            5   41,363        5,170
deliver            7            5   10,020        1,431     ← STEP-10's subject
capture            5            5   47,184        9,436
readiness          5            0        —            —
context            2            2   50,877       25,438     ⛔⛔ WORST
executive          2            1    6,230        3,115
platform           1            1   11,950       11,950
packs              1            0    8,188        8,188
```

⛔⛔ **`context/` is 5.4× worse than the 4,715 that triggered `STEP-10`**, and `deliver/` is now the
third-best covered package. ⛔ `packs/` has one PRESENCE receipt and **zero** correctness — the
state `feedback/` was in before `S5`.

⛔ The mapping is **declared**: an outer-`from` resolver fails on **4 of 40** receipts. A third
category, `READINESS`, covers claims no package can repair — forcing those into a package would
inflate its coverage with work it cannot do. ⛔ `Receipt.layer` is never read, and a test asserts
it.

⛔ **The second direction caught me twice on its first run:** I built the declaration from a dump
that truncated each claim at 62 characters, so two keys were cut short — direction one called them
undeclared and direction two called them stale, **naming both halves of one mistake.**

### ⛔⛔ A harness defect that could have falsified every mutation run in this session

`S7(a)`'s *"baseline again"* assertion failed with a layer `L8` that appears **nowhere** in the
source. ⛔ **A stale `__pycache__`**: the harness mutates, runs pytest in a subprocess that caches
the MUTANT, then restores — and a restore in the same mtime-second with the same size lets Python
reuse the mutant's bytecode. **A restored file was read as the mutant**, and the bias is toward
**false kills**.

⛔ **All seven harnesses re-run** with `PYTHONDONTWRITEBYTECODE=1` and a cache clear per
invocation: `s2 6·0 · s3 8·0 · s4 8·0 · s5 8·0 · s6 9·0 · s7b 9·0 · s7a 8·0` — ⛔ **every count
identical to the original.** Nothing was mis-scored, *and the only reason that is known is that the
harness asserts its baseline AFTER the run as well as before.*

⛔ **I also killed a healthy suite run at 64%**, reading post-cache-wipe slowness as a stall. Re-run
clean: **15,101 passed**.

### ✅ And one guard forced its own update

`S6`'s declared-silence test was parametrised over `["learning_input_rejections",
"learning_metrics"]` with the docstring *"when one gets a reader this fails and the `F11` tally is
updated deliberately."* ⛔ `S7` gave the first a reader and **the test failed, exactly as
promised.** *A declared silence that fails the build when it stops being true is the only kind
worth writing.*

```
receipts                       38 → 40        feedback/ CORRECTNESS   3 → 5   (0 before S5)
unread of F11's four ledgers    2 → 1          only `learning_metrics` remains
full suite   15,101 passed · 1,067 skipped · 152 xfailed · 0 failed    (15,027 before S7)
```

### ⛔ What this hands to Rohit

⛔⛔ **`context/` is the next layer to re-measure, and that is your call.** 50,877 lines, two
guards. The programme spent `STEP-10` on `deliver/` because a hand-derived number pointed there; the
**derived** number points at `context/`, and `packs/` has no correctness question at all.

### Doctrine

| Rule |
|---|
| ⛔ **a flag that is always set is a flag nobody reads** |
| ⛔ **a `getattr` with a default converts a wrong attribute name into a plausible value** |
| ⛔ **a test double that cannot fail the way production fails is a test that proves nothing** |
| ⛔ **a stale `__pycache__` makes a restored file read as the mutant** — bias toward FALSE KILLS |
| ⛔ **a declared silence that fails the build when it stops being true is the only kind worth writing** |
| ⛔ **an absent seam is not a lost seam, and a routine refusal is neither** |
| **derive the list from the source of truth** — health seams from the dataclass, quarantinable seams from the reader, legal pairs from the contract |
| **slow is not stalled** — I killed a healthy suite at 64% |


---
---

## ✅⛔⛔ 2026-10-02 · S8 BUILT — the scorecard reaches the learning layer

`08-ATLAS-SCORECARD-L1-to-L5.md` → **`-L1-to-L6.md`**, 45 → **56 claims**. All eleven
`L7 Learning` rows of the master coverage matrix, measured against the current code.

### ⛔ The measure-first gate caught my own numbering before a line was written

The gate was: *"the scorecard is named `L1-to-L5` — check whether it already carries L6 badges, or I
will write a section twice."* It carries none. ⛔⛔ **But the same check caught a mistake of mine**:
I had planned the step as *"`L1-to-L7`"*. **This scorecard numbers `deliver/` as L5**, so the
learning layer is **L6** here — while the source matrix labels the very same rows **`L7 Learning`**,
using `LAYERS.py`'s column where `feedback` is 7.

> ⛔ **Third time this programme has paid for that collision**: `STEP-10`'s receipt count, the three
> `L5`-labelled receipts I added to `deliver/`, and this step's own title. `LAYERS.py` says it in one
> line — *"always name the package, never the digit alone."* The new section states the mapping in
> its first paragraph rather than assuming a reader shares it.

### The eleven claims

```
EXPIRED           4    L6-02 explicit feedback · L6-06 Behavior evolution ·
                       L6-09 publisher/policy seams · L6-11 value analytics
PARTLY EXPIRED    4    L6-01 input health · L6-04 temporary memory ·
                       L6-05 outcome identity · L6-10 pivot/reset
STILL TRUE        3    L6-03 preference inbox · L6-07 Adaptive lifecycle · L6-08 review SLA
```

⛔⛔ **All four expirations run the same way: the Atlas calls built things stubs.** `L6-06` is the
clearest — *"Behavior cohort builder returns `[]`"* against a **776-line component wired into the
weekly run**, because the stub that preceded it by a month was never removed.

### ⛔⛔ And four cells hid a defect the Atlas did not name

| Cell | The Atlas's badge | ⛔ What measuring it found |
|---|---|---|
| `L6-01` | *"live input health **Unknown**"* | the health gate **was broken** — `degraded` was always True (`S7`) |
| `L6-09` | *"broken seams"* — both named ones **fixed** | ⛔ `governed → published` on **every brain publish** (`S6`) |
| `L6-10` | *"does not fully supersede Behavior"* | ⛔ **the module's stated REASON is now false** |
| `L6-11` | *"hardcodes zero"* — **fixed** | ⛔ `macv_ledger` **has never had a writer** (`S2`) |

> ⛔ **A cell the Atlas marks *Present* is not a cell that needs no measurement.** Three of these
> four sit under reassuring badges; the fourth sits under one already corrected.

### ⛔⛔ The new defect: a stale sentence that justifies a gap

`feedback/reset.py` explains why a pivot does not touch the Behavior brain —
*"`unit_behavior_evolution` … is presently an **unwired stub that always returns `[]`** — **there is
no live Behavior Brain content to decay**."* ⛔ **True when written, false now**:
`packs/brains/behavior_distill.distill` (776 lines) proposes `BEHAVIOR` and is appended to the same
weekly run. **So a pivot can leave live Behaviour content in place and the module's reason for
leaving it no longer holds** — the Atlas's `L7-20` / `L7-40`.

⛔ **Corrected, not repaired**: superseding a durable brain entry is a governed decision and part of
Rohit's Adaptive-lifecycle call. ⛔ **A cross-package guard now ties the prose to the fact** —
nothing connected `reset.py` to `behavior_distill` before, which is why the sentence could rot for a
month. Checked by **attribution, not presence**, because the correction quotes what it corrects.

> ⛔ **The most expensive stale comment is the one that explains why something was left undone.**

### The mutation run — baseline first, 2/2

```
✅ baseline: 21 passed
  M1 · the stale claim is ASSERTED again, far from any marker   ✅ CAUGHT
  M2 · the delegation stops naming behavior_distill             ✅ CAUGHT
✅ baseline again: 21 passed                        2 caught · 0 survived
```

⛔ `M1` **SURVIVED on its first attempt** — I removed one marker phrase while two others sat in the
same window. The faithful failure mode is a **relapse**: the stale sentence written again, far from
any marker. *An invalid mutation is not a surviving mutation*, and this harness has refused to round
one up **four times** in one session.

### ⛔ Two documents needed rebuilding rather than patching

`19-PENDING`'s MINE table (`F33`) and now `08-PLAN-v2`'s order block: eight steps of incremental
edits each replaced their own line and appended the next, so the v1 lines for `S3` and `S9` were
never removed — the block listed `S3` as *"fail-CLOSED; the docstring already promises it"* three
steps after it was DONE, plus a doubled `← next`. ⛔ *A list edited one line at a time accumulates
the lines nobody edited.*

```
scorecard    45 → 56 claims        full suite  15,102 passed · 0 failed   (15,101 before S8)
```

### Doctrine

| Rule |
|---|
| ⛔ **a cell the Atlas marks *Present* is not a cell that needs no measurement** |
| ⛔ **the most expensive stale comment is the one that explains why something was left undone** |
| ⛔ **tie a claim to its fact across packages, or it rots** |
| ⛔ **always name the package, never the digit alone** — paid for a third time, in my own step title |
| ⛔ **a list edited one line at a time accumulates the lines nobody edited** |
| **a correction is not a repair, and saying which is which is the honest part** |


---
---

## ✅⛔⛔ 2026-10-02 · S9 BUILT — the paperwork, and a finding of mine refuted by its own gate

### ⛔⛔ `F17` IS RETRACTED — it was my own false finding

`03-FINDINGS` §F17 recorded *"a mover-convention deviation the guard cannot see"*:
`feedback_health.py` uses `MOVES WITH` where the convention is `MOVES WHEN`. ⛔ **The plan's gate was
*"measure the distribution BEFORE touching either side."***

```
MOVES WHEN   115 occurrences
MOVES WITH    29 occurrences, across NINE of the thirteen declaration modules
             (context 8 · platform 7 · feedback 3 · six more with 1–2 each)
```

⛔ **It is a CONVENTION**, and it says what `MOVES WHEN` cannot: *"this entry moves when its PAIR
moves"* — two guards over one map from opposite sides, where naming a separate condition would be a
lie. **The existing guard is right to accept both.**

> ⛔ **The gate stopped me tightening a guard onto 29 correct entries** — and `F17`'s own closing
> sentence was *"do not weaken a verify to make it pass; do not tighten one to make it fail."*
> **Seventh time this discipline prevented a false finding.**

⛔ **The mutation executes the refutation**: narrowing `MOVER_FORMS` to `("MOVES WHEN",)` — the "fix"
`F17` implied — fails **9 modules**.

### ⛔ But a third form did exist, and now cannot

`context_health.py` carried `MOVES ON A SEAM DECISION` — normalised to `MOVES WHEN`, a wording
change. A new guard (+10 tests, one per declaration module) rejects a third form ⛔ **without
demanding a mover**: three tables correctly have none (`PULL_ONLY` ×2, `UNIT_TARGETS`), and
demanding one everywhere is *exactly the mistake the guard above it records making*.

### ⛔ The 104 absence guards: the rule, not the rewrite

```
584   assert "..." not in <anything>
104   assert "..." not in src|code|source|text|blob|content|body
       78 CODE-shaped · 13 SQL-shaped · 13 that LOOK like prose, mostly code fragments
```

⛔ I built a resolver to check each guard's phrase against **its own target file's** prose.
⛔⛔ **It resolved 1 of 104** — the dominant form is `inspect.getsource(<an imported function>)`, and
a function's module can only be found by importing it.

> ⛔ **A resolver that answers for 1 of 104 answers nothing.** An earlier version reported *"0 at
> risk"* from that sample — **the most reassuring wrong number this programme could have produced.**
> Fourth name-shaped resolver of the session, and the first caught by checking its COVERAGE rather
> than its output.

⛔ **So: the rule, in `tests/README.md`** — a claim about **prose** needs **attribution**; a claim
about **code** needs the **AST** (an attribution window there is the *wrong tool*, not a weaker
one); a **SQL construct** can stay a text check. ⛔ **78 mechanical rewrites with no measured defect
is speculative work**, and each one is a chance to change what a guard means. The three that broke
are fixed and pinned.

### `F18` closed — a real fix with an invented reason

`scripts/wipe_org_data.py` blamed *"MATERIALIZED views"*; `0072` creates a **plain** view and says
why, and a plain view **is** listed in `information_schema.views`. ⛔ **No second cause was
invented** — it is not recoverable from the file, and guessing would repeat the first mistake. The
comment now says why the fix is right **independently of the story**: `table_type='BASE TABLE'`
excludes every non-table, present and future. **A positive selection cannot be out of date.**

### `F16` closed — three counts, three meanings, none wrong when written

```
00-START-HERE  "53 tests"  ← ONE file, the day M14 shipped
01-CROSSCHECK  "87 tests"  ← a different scope, 2026-10-01
S5 measured     60 passed, 27 skipped        S9 measured  243 passed, 27 skipped
```

⛔ **The fix is the date, not the number.** Neither page carries a total now; the command is the
answer — `.venv/bin/pytest tests/feedback -q -rs`, ⛔ **`-rs` not optional**, because the 27 skips
are `H7` and *a skip is not a pass*.

```
full suite   15,112 passed · 1,067 skipped · 152 xfailed · 0 failed    (15,102 before S9)
```

### Doctrine

| Rule |
|---|
| ⛔ **measure the distribution before calling one instance a deviation** |
| ⛔ **a resolver that answers for 1 of 104 answers nothing** — check its COVERAGE, not its output |
| ⛔ **a claim about prose needs attribution; a claim about code needs the AST** |
| ⛔ **a hardcoded count in a document is wrong the next day** |
| ⛔ **a real fix with an invented reason is the harder stale comment to notice** |
| ⛔ **do not invent a second cause to replace a wrong one** — say it is not recoverable |
| **a guard may reject a third form without demanding a first** |
| **the rule, not the rewrite** |


---
---

## ✅⛔⛔ 2026-10-02 · S10 BUILT — the three unmeasured gaps, and `M14.C2` is complete

```
Atlas Layer 7   5 CLOSED · 6 PARTLY · ⛔ 0 LIVE · ⛔⛔ 0 UNMEASURED
new tests       69   (U10c 16 · U10b 37 · U10a 16)
mutations       27 actionable caught · 0 survived — after FOUR guard repairs
                + 2 negative controls that correctly survived
receipts        40 -> 41 · feedback/ correctness 5 -> 6
full suite      15,182 passed · 1,067 skipped · 152 xfailed · 0 failed
```

⛔ **`S10` closed no gap, and that is the result rather than a shortfall.** Each of `#3`/`#5`/`#6`
has exactly one clause left, and every one is a decision rather than a defect.

### ⛔⛔ `U10a` · #3 — a trap, and the obvious repair is what springs it

Two of three Atlas clauses were already closed by things already there: `migrations/0041:248`'s
`unique (org_id, execution_id)` makes *"the same external event counted once"* a **database
guarantee** — its comment is in Layer 7's own words — and `label_class` keeps `unknown` out of the
confidence denominator. The third, *"correction retracts derived proposal"*, is **blocked behind
`#1`**: every unit reading `card_feedback_verdicts` targets `METRICS`, so no durable proposal is
derived from a correction.

⛔⛔ **The finding:** `unit_recommendation_learning` pins `evidence.distinct_days = 1` while
`min_distinct_days` defaults to **2**, and `run_learning` validates **before** `preflight`/`govern`
and short-circuits. **So `DURABLE_FROM_A_MEASUREMENT`'s declared authority violation — mine, from
`S1` — is unreachable.** Five sibling constants are harmless (`METRICS`/`KNOWLEDGE_SUGGESTION`
return `(True, "artifact")` first).

> ⛔⛔⛔ **Measuring the days properly is correct for the siblings, is what `unit_pattern_learning`
> already does, and the data is loaded — so a future engineer would make that fix and silently
> unblock an auto-promoted durable ADAPTIVE write that trains the recommender on its own score.**

⛔ Three things would each open it, and all three are asserted — including **a stored
`min_distinct_days = 1`**, because `load_or_seed_policy` takes every column verbatim and `0045` has
**no CHECK**. ⛔ `LearningPolicy`'s docstring claimed *"a tenant can only narrow them"* and nothing
enforced it: **the fourth stale protective claim this programme has corrected.**

### ⛔ `U10b` · #5 — the enforcement is proven; the residue is unreached

`_visibility_allows_package` is wired into a live exclusion and requires **audience containment**,
not overlap; `learned_state._visible` is fail-closed including an **unknown scope**. ⛔ The dashboard
route renders both sinks with no principal check behind an org-only dependency — **safe only
because all three durable producers declare `ORGANIZATION`**, so the pair is declared together and
receipt **41** covers the approval path that rehydrates visibility from the database.

⛔⛔ And the bijection `VisibilityScope` ↔ `contracts/visibility.SCOPES` was **unguarded**, kept
alive by a two-entry alias table — `runtime_brains` records the last failure of that shape as
*"A SILENT TOTAL LOSS … the whole package was never built."* It bit inside this very step: my own
test failed at collection for writing `ORGANIZATION` where the compiler says `org`.

### ⛔ `U10c` · #6 — the reset goes further than the Atlas credits

`deliver/outbox.py` reads the latest reset at SEND time and cancels any card built before it, same
connection and locks, fail-closed-to-send. ⛔ Two of three callers are seat lifecycle, **both
justified in writing** — that candidate retired before it was recorded. ⛔⛔ The finding was mine:
`feedback_health` called `latest_reset_at` *"a surface that was never built"*; **the reader is one
layer DOWN and may not import upward**, so the duplication is **forced by the topology**.

### ⛔⛔ Four of my own guards failed their mutations

a word matched inside a cited **file path** · `all` where the question was **per-query** · a call
left in place under `if False` · and an existing line scan that a **split SQL string** defeats.

> ⛔ **A guard changed to make your own build pass needs a negative control.** The line-scan repair
> ran three mutations: a split write (**caught** — the hole closed), a single-line write
> (**caught** — no regression), and prose about the insert (**correctly survives**).

### Doctrine

| Rule |
|---|
| ⛔ **the obvious repair can be the trap** — declare the blocked path, do not open it |
| ⛔ **two gates in series: declare both** |
| ⛔ **a call that is syntactically present is not a call that is made** |
| ⛔ **assert the phrase, not the word** — a file's NAME can be the false witness |
| ⛔ **`any`, not `all`**, when the question is per-item |
| ⛔ **before repairing a guard, check whether the suite already catches it** |
| ⛔ **a guard changed to pass your own build needs a negative control** |
| ⛔ **read the call site's own justification before calling it a defect** |
| ⛔ **a protective claim nothing enforces is the kind that gets built on** |
| **a citation is a claim, so check it** · **the counts come out of the prose** |


---
---

## ✅⛔⛔ 2026-10-02 · CONTEXT AUDIT BUILT — the worst-covered package, and six retractions

```
context/        124 files · 50,885 lines · 44 tables written · 306 test files import it
new tests       37  ·  mutations 11 caught · 0 survived (after 2 repairs, 1 invalid re-run)
receipts        41 -> 42 · context/ correctness 2 -> 3
new modules     platform/table_coverage.py · scripts/context_coverage_report.py
⛔ retractions   6 — every one to a BROADENING of the measurement
full suite      15,220 passed · 1,067 skipped · 152 xfailed · 0 failed
```

### ⛔ The headline was wrong, and that is the first finding

`S7` turned *receipts per package* into data and it pointed here. ⛔ `context/` is **not**
under-tested: **306 test files** import it, only **2** modules of 100+ lines are named by no test
(and both are live and reached), and **both** of its receipts are CORRECTNESS receipts. What it
lacked was any check that the **44 tables it writes** behave in production.

### ⛔⛔ Six of the audit's own findings died, every one to a wider measurement

```
[a-z_]+ cannot match a digit        l2_convergence resolved as table `l`; l2_model_runs INVISIBLE
the engine is not the reader set    situation_admission_decisions — FIVE operator scripts read it
a bare-name grep has no subject     context_node_lifecycle — runner.py reads it
a pair-tuple contributes its column node_id and anchor_node_id became TABLES
SQL held in a module constant       retracted edge_coverage_declarations AND l2_model_runs
a name constant as an ARGUMENT      learning_event_inbox — a table S5 had PROVEN is read
printing a query is not running one activate_tenant.py prints SQL for a human to paste
```

> ⛔⛔ **Nine findings survived three broadenings. That is the only reason to believe them** — and
> `resolution()` now reports **639 unresolved of 2,867 statements** beside every verdict.

### ⛔⛔ The largest retraction would have been a catastrophe

**183** org-scoped tables · **102** in the `/reset` erasure loop · **4** declared retained ·
⛔ **77 in neither**, including `transcripts` and `screen_thread_summaries`, which hold verbatim
customer mail. ⛔ **It is not a retention hole.** `_ORG_SCOPED_TABLES` governs **`/reset`**, whose
docstring says it *"keeps the account, connections, tasks"*; **ACCOUNT erasure is done by migration
`0033`'s foreign keys** and already has a receipt, because — as the keep-list says — *"a comment
cannot be asked"*. The four `reasoning_*` children with no direct FK cascade **through a parent**,
verified transitively rather than trusted.

> ⛔ **Read the endpoint's contract before calling a list incomplete.**

### What survived

⛔ **Nine tables written by the product and read by nothing**, declared with writer and mover —
three `context/`'s, and ⛔ **`learning_metrics`, which is `F11`'s last unread ledger, rediscovered
from the other side**. ⛔ **Receipt 42** — *"no live row points at a node a merge absorbed"*,
`context/`'s first about entity merge, **derived** from `merge.py`'s own three constants so a sixth
table entering the merge loop enters the receipt. `merge.py` states the claim itself: *"Missing one
leaves rows pointing at a closed node — invisible in the UI, still returned by any query that joins
on node_id."*

### ⛔⛔ And the last finding is about the measurement that sent the audit here

Re-ranking with the **tables-written** column beside the receipt count:

```
api        44 files · 19,498 lines · ⛔ 0 receipts · 42 tables written · 28 uncovered
context   124 files · 50,885 lines ·    3 receipts · 44 tables written · 33 uncovered
contracts  41 files · 14,617 lines ·    0 receipts · ✅ 0 tables written  ← the control
platform   49 files · 12,649 lines · ⛔ 1 receipt  · 29 tables written · 25 uncovered
```

⛔⛔ **`api/` is the worst-covered package in the product and it never appeared in `S7`'s ranking at
all**, because *lines per receipt* with a **zero denominator** is not a number you can sort. The
package that had never been measured was invisible to the measurement built to find it. ⛔
`contracts/` is the control that makes the column readable: 14,617 lines, zero receipts, and **zero
tables written** — its zero is correct, not a gap.

**→ The next package to audit is `api/`, not another slice of `context/`.**

### Doctrine

| Rule |
|---|
| ⛔ **print the raw terms beside the ratio** — a ratio hides what its denominator cannot express |
| ⛔ **broaden the measurement before you believe a finding** — nine of fifteen survived |
| ⛔ **read the endpoint's contract before calling a list incomplete** |
| ⛔ **a resolver reports its COVERAGE beside its verdict**, and the guard asserts it |
| ⛔ **a receipt is not a reader** — "nothing consults it" and "nothing checks it" are two questions |
| ⛔ **a mutation that survives because something else catches it is a guard nobody is checking** |
| ⛔ **verify a transitive claim transitively** — a direct-FK check cannot see a parent |
| **a 124-file audit is generated, not written** |


---
---

## ✅⛔⛔ 2026-10-03 · THE PLAN TO PRODUCTION — and the audit of all eleven packages

```
engine          660 files · 215,992 lines · 42 receipts · 189 tables in the migrations
⛔ coverage      183 tables have a writer · 42 have a receipt · 141 have NONE
⛔ built≠live    5 migrations unapplied · 0 domains activated · 0 cards since 25 Sep
```

### ⛔⛔ The crux, and it is not engineering

Everything is built and almost nothing is live. The distance is **three things, two of them not
mine**: `H1` the five unapplied migrations (⛔ `0190` breaks `insert_card` **on write**), `R1` the
spend limit decision, `R2` activation for one tenant. ⛔ **My remaining work does not reach
production on its own** — it makes the product *provable* once it is live, which is worth doing in
parallel, not instead.

### ✅ The original brief's VERIFIED-MISSING list is CLOSED

Of the eight items that were missing when this programme opened — `EvidenceNeed`, `SituationSeed`,
`QualifiedEnterpriseSignalBundle`, `ConfidenceVector`, the five pipeline counters and the five
output lanes — ⛔ **seven are built** and the eighth, `SituationSeed`, is **declared unnecessary**:
*"the Atlas names it; it has zero hits in the code and nothing needs it."*

### ⛔ Seven conditions now define "production level", and nothing meets them

receipt against production data · the receipt **can fail** · silences declared **both ways** ·
tests **do not skip** · migration **applied** · path **activated** · measured **once** against
production. ⛔ **`P5` and `P6` fail for everything**, which is not a reason to weaken the
definition.

### ⛔⛔ `api/` is the answer `S7` could not see

```
api        44 files · 19,498 lines · ⛔ 0 receipts · 42 tables · 28 unreceipted · 2 silences · 11 untested modules
context   124 files · 50,885 lines ·    3 receipts · 44 tables · 33 unreceipted
contracts  41 files · 14,617 lines ·    0 receipts · ✅ 0 tables written   ← the control
```

⛔ `S7` ranked by *lines per receipt* and a **zero denominator does not sort**, so the worst-covered
package was invisible to the measurement built to find it. ⛔ `contracts/` is the control that makes
the column readable: zero receipts **and** zero tables written, so its zero is correct.

### ⛔ Four defects in my own paperwork, all found before it shipped

| | |
|---|---|
| the report's **declaration column read 0** for four packages | it derived the module name from the directory, and they are named for what they describe — `delivery_health`, `reasoning_health`, `pack_health`, `executive/unreached.py`. ⛔ `deliver/` showed **0** silences with **23** declared |
| a **context-specific paragraph in a reusable tool** | the caveat named two `context/` modules — true there, a **lie** on the other ten pages |
| a **total I added instead of measuring** | twice: `657 · 215,591` then `667 · 215,091`, and ⛔ **the correction broke a file count that had been right**. Both are now printed by one script |
| **`164` unreceipted tables** | the real number is **141**. Stated before measuring |

⛔ Every one is the class this report exists to surface. *A report whose own numbers are wrong is
worse than no report*, because it is read as a measurement.

### Paperwork

⛔ **`HANDOFF-HARSH.md` said "five items" and has eight** — `H6`, `H7` and `H8` each landed at the
bottom without the header being touched. It now opens with a do-this-in-this-order table, and names
the three items that are **read-only or one command**: `H8`, `H7`, `H6`.

⛔ **Rohit's items had no stable ids** and were named differently in four files. **`R1`–`R15` plus
`D1`/`D2` and `P`** are introduced in the plan and mirrored into `19-PENDING`, so one item cannot be
worked twice or dropped silently.

### Doctrine

| Rule |
|---|
| ⛔ **a total is a measurement, not an addition of other people's measurements** |
| ⛔ **and a correction needs the same measurement the original needed** |
| ⛔ **a name derived from a directory is a guess; a name found on disk is a measurement** |
| ⛔ **context-specific prose does not belong in a reusable tool** |
| ⛔ **print the raw terms beside the ratio** — a ratio hides what its denominator cannot express |
| ⛔ **define "production level" before claiming it**, or it means "work until it feels done" |
| **a link that may not resolve is a stale pointer** |


---
---

## ✅⛔⛔ 2026-10-03 · API AUDIT BUILT — eleven candidates, eleven retirements, one real finding

```
api/        44 files · 19,498 lines · 20 writers · 42 tables · ⛔ 28 with no receipt
new tests   22 · mutations 10 caught · 0 survived
⛔ 11 candidates raised · 11 retired · 1 survived
full suite  15,242 passed · 1,067 skipped · 152 xfailed · 0 failed
```

### ⛔⛔ Eleven retirements IS the result

| | Candidate | Why it died |
|---|---|---|
| `decisions` written only by an API route, read by `executive/` | ✅ `_persist_decision_envelope` binds **the envelope the route returned**, content-addressed, fail-closed on collision. The API is the correct writer |
| `approvals_queue` — a queue nothing consumes | ✅ **already declared**, and more sharply than my candidate: *"the policy enforcement path does not exist, so 'called from' is a sentence about a future"* |
| `learning_objects` has three writers | ✅ `api/learning_routes` only updates `state`, under `for update`, 404 + 409 gated |
| `api_keys` has four writers · `card_events` has eight | ✅ a credential table's lifecycle, and an append-only event log |
| ⛔⛔ **`api/`'s 2 declared silences are thin** | ⛔ **MY OWN MIS-SIGNAL.** 25 route handlers are excluded **by design** — a decorator-wired function has no Python caller, pinned by a test. `require_session_seat` has 8 `Depends()` references |
| `api/` has zero receipts | ⚠️ the erasure receipt imports `RETAINED_AFTER_ERASURE` **from `api/account_routes`** and is filed under `platform` **with its reason written** |
| the 11 modules no test names | ⚠️ the column does not say untested, and its own caveat says so |

> ⛔ **A coverage column mis-signals for a package whose functions are wired by decorators and
> dependencies rather than calls.** The unreceipted-tables column is the one that holds;
> `00-INDEX.md` is corrected in place.

### ⛔⛔ The survivor: an immutable table nothing called immutable

`publisher.persist`'s first line is the contract — *"Insert an **immutable** proposal at `state`"* —
and it keeps it: an existing row is never updated, only reported `reevaluated` or `unchanged`.

```
every `update learning_objects` in the engine:
  api/learning_routes.py        set state = :st
  feedback/org_rule_ingest.py   set state = :st
⛔ touching proposed_value / semantic_hash / evidence / visibility:  NONE
⛔ tests asserting it:                                              NONE
```

⛔ The day somebody writes `set proposed_value = …` to "fix" a bad proposal, `semantic_hash` stops
describing its row and every transition already logged against it points at something else.
`WRITE_ONCE_TABLES` + `illegal_column_updates()` guard it **both ways** — a value column fails, and
**a third updater fails even if it only sets `state`**.

⛔ **The producer's half is behavioural, with a double that RECORDS what it was asked to run** — a
double that only checked the return value could not see a `persist` that quietly rewrote a row.

⛔ **And there is deliberately NO receipt**: a value rewritten in place leaves no trace unless
`semantic_hash` is recomputed, and recomputing it in SQL means reimplementing the canonical
serialisation in a second language. Same decision as `graph_nodes`.

### ⛔ One mutation survived, and the answer was to DELETE the code

`M6` reverted a paren-depth-aware comma split to a plain one and nothing failed — an identifier
filter drops the wreckage either way. ⛔ **A branch whose mutation cannot fail is complexity, not
safety.** The branch is gone, the filter is named as the safeguard, and both mutations against the
filter are now caught. **Second time in two days the honest answer was deletion.**

### Doctrine

| Rule |
|---|
| ⛔ **eleven retirements is a result, not a failed audit** |
| ⛔ **a branch whose mutation cannot fail is complexity — delete it and name the real safeguard** |
| ⛔ **a test that reimplements the parser proves the copy, not the code** |
| ⛔ **a double that only checks the return value cannot see a quiet write** |
| ⛔ **no receipt is a decision too**, written down beside the claim |
| **a third writer is a finding even when it writes the right column** |


---
---

## ✅⛔⛔ 2026-10-03 · PLATFORM AUDIT BUILT — fifteen retirements, and a park nobody can see

```
platform/   49 files · 12,651 lines · 18 writers · 29 tables · ⛔ 25 with no receipt
new tests   23 · mutations 16 caught · 0 survived    (the receipt, plus a guard it forced)
⛔ 15 candidates raised · 15 retired · 1 survived     (26 across both audits today)
receipts    42 → 43 · platform/ 1 → 2
full suite  15,266 passed · 1,067 skipped · 152 xfailed · 0 failed
```

### ⛔⛔ The finding: a health predicate that hides a failure twice

`migrations/0136_warm_lane.sql` comments the column itself — *"attempts ran out: **parked for a
human**, never retried"* — and then:

```
warm_lane.py:480   parked_at = now()                                ← the park
warm_lane.py:383   _OPEN = "done_at is null and parked_at is null"
api/routes.py:225  backlog count — the same predicate
housekeep()        warns on the OPEN backlog · prunes only done_at rows
⛔ statements that SELECT a parked row:  NONE      ⛔ receipts:  NONE
```

⛔⛔ **A tenant whose rows park stops being processed silently and permanently, and the health
signal reports zero open rows.** A lane with a hundred parked rows and none open is
indistinguishable from an idle one — and because the prune only touches finished rows, **the
invisible set grows.**

> ⛔ *A refusal nobody can see is a silent stop* — and this is the worst version in the product: the
> health check does not **miss** these rows, it **excludes them by construction**.

**Receipt 43**, with its predicate **derived** from `warm_lane._OPEN` and the builder asserting the
shape — change `_OPEN` and five tests fail. ⛔ And it is a **precedent, not an invention**: L1
already makes this claim for `parked_events` (*"the parked queue is not a black hole"*), and a test
pins that the precedent still exists.

### ⛔ Fifteen retirements, two of them about the MEASUREMENT

| | |
|---|---|
| `pipeline_counters` — written, zero readers | ✅ read through `funnel.read_sweep`, which `api/routes` calls. ⛔ **A table read through its module's own accessor shows zero external SQL readers** — the second column mis-signal in two audits, after `api/`'s decorator-wired functions |
| the four activation tables have no receipt | ⚠️ true, and ⛔ **a cross-layer ordering receipt would have to be INVENTED** — no module states that L3 must precede L4. Declined |
| `use_domain_compiler` still exists | ✅ kept in capitals: *"THIS MODULE DOES NOT RETIRE THE GLOBAL FLAG, AND MUST NOT YET"* |
| `org_run_leases` could stick | ✅ self-healing: 120 s TTL, heart-beaten, `lease_until < now()` is claimable |
| ⛔⛔ Atlas `L2-02` — an ungrouped ref counts as independent | ⛔ **MINE, AND WRONG FIVE MINUTES AFTER I WROTE IT.** `reason/runner.LINEAGE_UNPROTECTED` declares it: *"NOT BUILT, ON PURPOSE. A two-connector tenant cannot produce the case"*, mover **"the third connector"** |

⛔ **And that mover is now a one-line query.** The code implements more than two connector kinds;
whether a LIVE tenant has three connected at once is `H8.5`, and **three or more means a correct
declared silence has become real work.**

### ⛔⛔ And adding the receipt broke a test — which turned out to be the TEST's defect

```python
found = [r for r in R.receipts(None) if "lane" in r.claim]
receipt = found[0];  assert receipt.layer == "L5"    # ⛔ got 'L1'
```

⛔ **Three claims contain `lane`:** the L5 one it meant, L6's *"the delivery control **p-lane** has
run"* — the substring inside `plane` — and receipt 43. ⛔⛔ **It had been one receipt-ordering away
from asserting about the wrong receipt since the L6 claim was written.**

⛔ **The rule, not the rewrite:** ten sites use the idiom, **exactly one** was ambiguous (measured),
so one site now names its claim and a new guard fails on any future collision — in one named place
instead of inside whichever test loses the ordering. It fails the other way too: a claim reworded
out from under a lookup matches **nothing**.

⛔⛔ **The guard needed three corrections of its own**, each a rule already written down: a regex
over file text matched the **repair comment** (⛔ fifth instance — *a claim about CODE needs the
AST*) · counting every `in …claim` flagged `assert "declared" in receipt.claim`, an assertion about
an **already-selected** receipt (⛔ a pattern matching the shape without its subject) · and a
surviving mutation on the `receipts(...)` check was fixed by **extracting a pure function over
source text** so both branches are exercised, rather than deleting a check that will matter later.

⛔ My first measurement of the class was wrong too: a regex said *"5 of 6 unique"*, the AST found
**two** ambiguous — and one of those two was the false positive above.

### Doctrine

| Rule |
|---|
| ⛔ **adding a receipt can break a test, and the break can be the TEST's defect** |
| ⛔ **a substring lookup that takes `[0]` tests whichever row is first** — name the exact claim |
| ⛔ **a health predicate that excludes a failure state hides it twice** — from the count and from the alarm |
| ⛔ **an invisible set that is never pruned grows** — which is what makes it a receipt, not a note |
| ⛔ **a table read through its module's accessor shows zero external SQL readers** |
| ⛔ **derive the predicate from the module's own constant and assert its shape** |
| ⛔ **a receipt whose subject cannot occur is green forever** — pin the writer |
| ⛔ **declined: an ordering nobody states** — the claim would have been invented |
| **a declared silence's MOVER can be a one-line query** — which turns paperwork into a decision |


---
---

## ✅⛔⛔ 2026-10-03 · REASON AUDIT BUILT — and the audit deleted one of its own columns

```
reason/     121 files · 41,363 lines · 21 writers · 35 tables · ⛔ 29 with no receipt
new tests   26 · two guards · ⛔ 20 candidates raised · 20 retired · 0 receipts added
full suite  15,292 passed · 1,067 skipped · 152 xfailed · 0 failed
```

### ⛔ Twenty retirements and no receipt — which is a result

`signals` leads the uncovered list with 29 readers and six writers, and its owner states the
contract itself: *"**Projection, not decision.** … publishing twice from the same execution produces
**byte-identical bindings**."* ⛔ **It is database-enforced** — a partial unique index matching the
insert's `on conflict`. ⛔ My two follow-up suspicions were both wrong: a single-line grep said the
index did not exist, and then a flattened read of every migration showed **two** overlapping indexes
when `0034` **drops and recreates** one. *A measurement that flattens history cannot see a
replacement.*

⛔ 16 of 23 reasoning units looked untested; `tests/test_unit_roster.py` is
`parametrize("unit", ALL_UNITS)` — **all 23 exercised, not one class name in the file.** A
suppression log looked unread; `executive/explain.py` reads it. A silent unit is already receipted.

> ⛔ After `context/`'s receipt 42 and `platform/`'s 43 — both derived from a module's own sentence
> — `reason/` had no sentence left to derive from, and *a gate derived from an invented claim is a
> gate nobody reads.*

### ⛔⛔ THE FINDING: the "no test names it" column was wrong 19 of 33 times

```
a @router.get handler has no caller and no test imports its module         api/
a table read through funnel.read_sweep — reached, path written nowhere     platform/
⛔ parametrize(ALL_UNITS): 23 units run, no class named                     reason/  x16
ConstraintReasoner = ConstraintUnit — an alias a ClassDef scan misses      reason/
```

⛔ **Six repairs, and every one over-corrected** — a generic `CAPABILITY` constant rescued a module
with no test at all; counting `__all__` as a *definition* made all 23 unit names ambiguous and the
column collapsed to **zero**; reading the corpus from the AST brought back two modules already
hand-verified as reached, because `*_health.py` is reached by `importlib` over a **string**.

⛔⛔ **And the sharpest: the guard written FOR the column named `deadline_situations` and `team_away`
in its own docstring** — so the corpus scan counted those words and the module became *named by the
test claiming it was not.* **The observer altered the thing it measured.**

> ⛔⛔ **A column whose error rate is unknown in BOTH directions is a column nobody should act on.**
> Zero surviving findings in three audits, nineteen false leads, and each repair traded false
> positives for false negatives — which are worse, because a false negative **hides** a live module.
> **Deleted**, not repaired a seventh time.

⛔ Its one real contribution is kept as a finding, verified by hand: **`api/identity_routes.py` — five
routes, 130 lines, mentioned by no test by any means**, plus `reason/team/away.py`. Both are step
`1.3b`. ⛔ And the generator went from **minutes to 1.6 s**.

### ⛔ A second drift, found while writing the first guard

`00-INDEX.md`'s table is hand-written over **generated** pages, and today's `platform/` code moved
three of its numbers while the index kept the old ones. A second guard now compares every row with
the page it links, per package, and fails if a row stops parsing — *an unparsed row is an unchecked
row.*

### Doctrine

| Rule |
|---|
| ⛔⛔ **a column whose error rate is unknown in both directions is a column nobody should act on** |
| ⛔ **delete a measurement rather than repair it a seventh time** — and record why, or it gets rebuilt |
| ⛔ **a false negative is worse than a false positive** |
| ⛔⛔ **the observer can alter what it measures** |
| ⛔ **a measurement that flattens history cannot see a replacement** |
| ⛔ **a re-export is not a definition** · **a name that is not distinctive is not evidence** |
| ⛔ **an index over generated pages is an addition, not a measurement** |
| **twenty retirements and no receipt is a result** |


---
---

## ✅⛔⛔ 2026-10-03 · 1.3b BUILT — two untested modules, and one was health information

```
new tests   32  (18 + 14) · mutations 17 caught · 0 survived
full suite  15,324 passed · 1,067 skipped · 152 xfailed · 0 failed
```

### ⛔⛔ `team_away` promised health information never leaves it, and nothing checked

> *"**No leave reason ever leaves this module**: windows are reported as who + when; the `sick`
> kind is reported as `leave`."* · `_PUBLIC_KIND = {"sick": "leave"}` — *"`sick` is health
> information → reported as leave."*

⛔ A one-line change to that dict, or a kind added to `AVAILABILITY_KINDS` and not mapped, tells
every seat in the org why a colleague is off. ⛔ **The emitted vocabulary is now DERIVED** from the
contract, with one parametrised case per kind — so the newest kind is covered without an edit. And
the mapping must **transform, not suppress**: a dropped window hides that somebody is away at all.

⛔ No database: the collaborators are module-level imports, and the doubles return the **real**
`AvailabilityWindow` and `Person` dataclasses, so a renamed field breaks the test rather than
passing it.

### ⛔ `identity_routes` — a destructive operation whose gate had no test

> *"Merging is destructive (it rewrites who every fact and edge is about)."*

A human confirming a proposal about `A` and `B` may send a body naming `A` and `C`, and one line
stops it. ⛔⛔ **The test asserts `apply_merge` was never called, not that a 422 came back** — a gate
placed *after* the act still returns the right status. The mutation proves it: moving the merge
above the gate fails **four** tests while the response stays 422.

### ⛔ And one of my own tests was theatre

`test_a_row_carries_only_who_and_when` set the field it was about with
`object.__setattr__(...) if hasattr(...) else None` — an expression that asserted nothing. It now
builds a window that really carries a cover and checks the fixture carries it **before** checking
the row does not.

### Doctrine

| Rule |
|---|
| ⛔⛔ **assert the destructive call did not happen, not that an error was returned** |
| ⛔ **derive the vocabulary from the contract** — a hand-written list stops covering the newest member |
| ⛔ **a privacy transformation must transform, not suppress** |
| ⛔ **a double returns the real dataclass** — a stand-in cannot fail the way a renamed field fails |
| ⛔ **a test that cannot observe the thing it names proves nothing** |
| **two modules that survived six heuristic repairs and a hand check were worth testing; the other nineteen were not** |


---
---

## ✅⛔⛔ 2026-10-03 · CAPTURE AUDIT BUILT — Phase 1 closed, and a founder's question becomes a check

```
capture/    158 files · 47,184 lines · 25 writers · 25 tables · ⛔ 19 with no receipt
new tests   12 · mutations 10 caught · 0 survived
receipts    43 → 44 · capture/ 5 → 6, all correctness
full suite  15,337 passed · 0 failed · 11:39
```

### ⛔⛔ The claim is the module's own first sentence

`capture/journey.py`, quoting `qualification.py`:

> *"a system that discards 92% of what a founder was sent has to be able to answer **'why did I
> never see X?'** in one query"*

and then: *"Every layer kept its half of that bargain and wrote its refusal down. **Nothing ever
joined them.** … `event_trace` holds 10,840 rows and had **NO read surface at all** … **a founder
reading `/qualification/drops` would have found nothing and concluded the events were lost.**"*

✅ The join exists and is reachable. ⛔⛔ **Nothing checked that every event has an answer for it to
render** — which is **receipt 44**, with five derivations and nothing spelled: the stopping actions
from `TRACE_STOPPING`; the event-keyed ledgers from `_LEDGERS` **minus** `_PER_SIGNAL_LEDGERS`,
because ⛔ a per-SIGNAL refusal cannot name an event that never produced a signal; the horizon from
**4 × the declared sweep tick**. ⛔ The multiplier is the one judgement and it is named in the
builder's docstring. A fifth event-keyed ledger joins without an edit, and the builder **refuses
rather than guesses** when its source changes shape.

⛔ It does not duplicate its sibling: *"every drop we might be wrong about can still be reviewed"*
asks whether a model's **judgment** can be re-examined; this asks whether an answer exists **at
all**. A test pins that the sibling still asks the narrower question.

### ⛔ Two mutations survived, both about emptiness

⛔⛔ **Emptying `_PER_SIGNAL_LEDGERS` made my loop run zero times** while the per-signal tables
flowed into an event-keyed query — *an empty collection makes an assertion over it vacuous*,
the same defect as a gate that can never be red. Non-emptiness is now asserted first.

⛔ The second was **invalid**: the quoted sentence appears **three** times and one change left it
present. And a third was a **no-op** — `() or (x,)` is `(x,)`.

⛔ **The harness needed two repairs too**: a missing file **crashed** it and took the whole run's
results with it, and a phrase appearing more than once could not be changed deliberately. *A
missing file is not a surviving mutation either.*

### ✅ PHASE 1 IS CLOSED

```
1.1  api/        11 candidates, 11 retired · learning_objects write-once guard
1.2  platform/   15 retired · receipt 43 — a park the health check excludes
1.3  reason/     20 retired, 0 receipts · ⛔ the audit's own naming column DELETED
1.3b —           ⛔⛔ a health-data privacy guard, and a destructive-merge gate
1.4  capture/     6 retired · receipt 44 — "why did I never see X?"

⛔ 52 candidates raised · 52 retired · 3 receipts · 6 guard suites · 0 failed at every step
```

### Doctrine

| Rule |
|---|
| ⛔⛔ **an empty collection makes an assertion over it vacuous** — assert non-emptiness before iterating |
| ⛔ **a no-op mutation is not a survivor** · **a phrase appearing three times needs all three changed** |
| ⛔ **a missing file must be reported, not raised** — a crashing harness loses the run |
| ⛔ **name the one judgement in a derived query** |
| ⛔ **a builder refuses rather than guesses** when its declared source changes shape |
| **two receipts about one ledger must each pin what the other does not ask** |


---
---

## ⛔⛔ 2026-10-03 · ATLAS LAYER 2 SETTLED — nine claims, two receipts, eleven corrections

```
claims      9 re-checked · 1 EXPIRED · 2 located with a receipt · 1 partly expired
            1 measured · 4 Rohit's · ⛔ 0 unmeasured
receipts    44 → 46   both correctness, both L2, both org-scoped
tests       50 new    mutations 49 valid, 49 caught · 0 surviving · 2 invalid
full suite  15,389 passed · 0 failed · 11:40
```

### ⛔⛔ L2-11 · the alphabetically first domain picks the reasoning's playbook

```
capability_resolver.py:833   domain_ids=tuple(sorted(selected_domains))        ← a SET
expertise_builder.py:87      "domain_ids": plan.domain_ids                     ← written
expertise.py:1463            domain = str(domain_ids[0]) …                     ← PICKED
expertise.py:1511            CapabilityManifest(domain=domain, …)
domain_shadow.py:1169        packs[manifest.domain] = _tenant_pack(…)          ← the KNOWLEDGE
runner.py:760                if capability.domain == effective["pack_id"]      ← gated
```

⛔ **The index does not pick a label, it picks the pack** — and because the list is `sorted()` over
a set, `[0]` is the **alphabetically first** domain. A situation with no usable hint resolves
against *every authored domain*. **Nothing records that a choice was made**, while the same
package's citation tags carry all of them. ✅ The contract already owns the accessor that returns
every entry (`domain_hints`); the routing site reaches past it. **Receipt 45.**

### ⛔⛔ L2-01 · two authority scales in one integer column

`capture/validate/authority` is a **dense 0..6 ladder** — `inferred` 0 … `signed_document` 6, no
ties. `context/analytic/publish.DEFAULT_AUTHORITY_RANK` is **100**, into the **same column of the
same table**. And `fact_write_action` compares the raw integers:

```python
if held_rank is not None and new_rank < held_rank:
    return "discrepancy"      # lower authority disagrees -> flag, keep held
return "supersede"
```

⛔ So a row at 100 is **unsupersedable**, and a countersigned contract arriving against one is
returned a `discrepancy` and **dropped**. Three more ranks do not say how they were decided: the
unmapped floor is `inferred`'s own 0; `write_fact`/`build_evidence_ref` default to a **bare 1** =
`chat_aside`; `write_edge` to a **bare 2** = `email_prose`. ⛔ And rank 1's ambiguity is
load-bearing — `graph_store` promotes on `held.authority_rank == 1` exactly.

✅ **Measured as NOT firing today**: the derived writer is prefix-scoped and the two writers share
no literal field name. ⛔ But `write_fact`'s lookup is **not** prefix-scoped, so the separation
rests on two vocabularies never meeting — and **31 `field=` arguments could not be resolved
statically**, which the measurement states beside its verdict. **Receipt 46** + `UNINTERPRETABLE_RANKS`.

### ✅ Two claims were already closed, and one of them the scorecard had simply wrong

**L2-03** — `observe_person_name` marks `origin='contended'`, `resolve_alias` excludes it **and**
returns `None` on 2+ rows, `resolve_alias_candidates` keeps *"nobody"* and *"several"* apart, and a
test guards it. ⛔ I nearly got it wrong the other way: `resolve_person_name` is a one-line
delegation and looks like a lie — **the law is enforced at the WRITE, 200 lines away.**

**L2-09** — `situation_bso.py` really does mention `relationships` and `dependencies` **0 times** in
2,133 lines, and both are **declared twice** with the X8 cutover named. ✅ But *"0 derived facts"* is
visible: `context/conversion.py` has a writer, a **reader**, and a test. ⛔ This is the one I
expected to find unread.

### ⛔⛔ Eleven corrections, nine to my own first reading

| ⛔ what I was about to claim | what was true |
|---|---|
| *"the only writer emits ≤1 domain"* | **a SECOND writer** — `plan.domain_ids` is multi-valued by construction |
| *"`ExpertisePackage._NON_CONTENT_METADATA`"* | **wrong class** — that is `SituationCandidate`'s, 300 lines earlier in the same file |
| *"`AuthorityBasis` is thrown away"* | **persisted** at `pipeline.py:1685` |
| *"two call sites disagree about arity"* | ⛔ **unfair** — a tag set takes all correctly; the defect is that the pick is SILENT |
| *"three of four views absent"* | `authority` is **built and imported in production**; `ownership`'s DATA is written |
| *"the eighth view over the one graph"* | ⛔ **uncheckable** — the phrase appears once, no list anywhere. Now attributed |
| my guard `len(why) > 80` | measures **length, not content** — caught by a surviving mutation |
| my declaration *"0 files engine-wide"* | ⛔⛔ **false the moment it was written.** *The observer can alter what it measures* |

⛔ **And two mutations were invalid, which is reported rather than rounded up.** **M17** mutated the
*test's own* threshold — a test cannot catch a weakening of itself; re-run against the SOURCE it
failed 10 tests. **M9**'s label said it stripped a citation and it stripped the *reasoning*; it
still exposed a real hole, which is why an invalid mutation is read and not discarded.

### Doctrine

| rule |
|---|
| ⛔⛔ **a declaration can falsify its own measurement** |
| ⛔⛔ **two `to_semantic_dict` methods in one module make the right-looking name the wrong object** |
| ⛔ **a citation that does not resolve is worse than none** — it reads as a measurement somebody took |
| ⛔ **a test cannot catch a weakening of itself** — mutate the source |
| ⛔ **an invalid mutation is read, not discarded** |
| ⛔ **a law enforced at the write is invisible at the read** |
| ⛔ **grep every spelling of a key, not the first one found** |
| ⛔ **a comment's count ages faster than its claim** — *"the four writers"*, and there are eight callers |


---
---

## ⛔⛔ 2026-10-04 · ATLAS LAYER 1 SETTLED — and three holes in my own guards

```
claims      5 · ⛔ 2 rows carried FALSE evidence · 1 partly expired · 2 Rohit's · 0 unmeasured
receipts    46 → 48   both correctness, both L1, both org-scoped
tests       48 new    mutations 51 caught · 1 surviving BY DESIGN · ⛔ 3 REAL HOLES in my guards
full suite  15,437 passed · 0 failed · 12:15
```

### ⛔⛔ L1-08 · *"zero declare a visibility field"* — all three declare one

Optional is not absent, and the two have different fixes. ✅ The consequence is closed **four
times**: `landing/normalize` derives · **the gate PARKS `visibility_unknown`** · a re-drain stays
`STILL_BLOCKED` · 5 of 6 columns are NOT NULL and the 6th pairs a nullable jsonb with
`visibility_scope text NOT NULL DEFAULT 'private'`. The gate says why: *"by Layer 2 the recipient
list is gone, so **this is the last gate that can still refuse**."*

⛔ **So the finding is the readers.** Three sites in `context/` read a missing audience as
**permitted** and two more default it to **org-wide** — and nothing connected them to the gate.
**The safety of a privacy default rested on one `if` in one file.** ⛔ Found by AST: grep found
**five** of the **eight** sites, and the three extra turned out **fail-closed** —
`Visibility(scope="private", principals=[]).can_view(...)` is `False` for everyone, which is
asserted rather than reasoned about.

### ⛔⛔ L1-09 · five of this contract's own fields break its own rule

The contract states it: *"A dead field on a contract is worse than a missing one: **it invites a
consumer to trust a seam that carries nothing**."* Five of its 21 fields are set at the boundary
and then stored in no column, absent from `ENVELOPE_KEYS`, and read by nothing.

⛔⛔ **`degraded_compile` is the worst because its own comment says this defect was fixed.** It
records that *"the boundary object dropped it — so L2 … could not tell a full compile from a
degraded one"*, and the fix put the field on `GatedEvent` **and stopped**. L2 reads the **stored**
signal. ⛔ `coverage_ready`, the first half of the same answer, **is** a column — half the verdict
crosses and half does not. **Receipt 47** holds the contract's other promise (*"a freshly gated
event always carries a real bool"*), bounded by four sweep ticks because an old null is legitimate.

⛔ And a test's own heading was the false witness: *"survives to the published **envelope**"* while
asserting the object one layer earlier.

### ⛔ L1-01 · the number was 7 and it is 9, and the registry's example had expired

The descriptor carries a declared `aliases` field; folding by **it** gives 9. `database`, `mysql`
and `postgres` are **three descriptors with three capabilities**, not aliases — *the fold was done
by reading the names.* ⛔ And **`database` and `mysql` are buildable with `capability = None` and
`object_types = 0`**: connect one, see a success, feed nothing. **Receipt 48.** ⛔ The registry's own
example named `hubspot` as unbuildable and `hubspot` is buildable now — eleven other sources are in
that state, and the corrected sentence names **nobody**, because naming one is how it went stale.

### ⛔⛔ Three holes in my own guards, every one found by mutation after the suite was green

| ⛔ the guard | the hole |
|---|---|
| `U01`'s grade checks | *"the open ones are open"* existed and **its converse did not** — a fail-closed site could be regraded in either direction and everything passed |
| `U02`'s *"the rule is in the file"* | ⛔⛔ **the declaration QUOTES the rule as its justification**, so deleting the original left the quote and the check passed. *A declaration that cites its source satisfies the test that the source exists* |
| `U03`'s registry warning | my warning names *"`database` and `mysql`"* and nothing checked the names against the measurement. ⛔ **My fix for a stale comment would have introduced one, two paragraphs below it** |

⛔ **And `len(what) > 40` came back.** `2.1` replaced an `assert len(why) > 80` for exactly this
reason — length is not content — and this step wrote the same guard again. *A rule learned in a
doctrine table is not a rule applied.*

⛔ **One mutation survives on purpose**, recorded in the test: tightening it would mean asserting a
count in prose, which `2.1` forbids. Its cousin in `U03` was **not** left surviving, because that
docstring is read at the moment the rule could be broken.

### Doctrine

| rule |
|---|
| ⛔⛔ **a declaration that cites its source satisfies the test that the source exists** |
| ⛔⛔ **a grade needs its converse guarded** |
| ⛔⛔ **the fix for a stale comment can be a stale comment** |
| ⛔ **optional is not absent** |
| ⛔ **a one-sided resolver must say which side it errs on** |
| ⛔ **a same-named local or function makes a dead field look alive** |
| ⛔ **a rule learned in a doctrine table is not a rule applied** |


---
---

## ⛔⛔ 2026-10-04 · `3.1` — THE NUMBER THAT WAS THE WRONG NUMBER

```
"unresolved SQL statements"      645 → 621
⛔ holes in a TABLE POSITION      49 → 16     the figure that bears on table coverage
   holes ELSEWHERE ONLY          596 → 605    predicates, column lists, bind parameters
sites accounted for                2 → 11     with a CATEGORY each
tests  29 · mutations 20 caught · 0 surviving · ⛔ 2 real holes closed
full suite  15,466 passed · 0 failed · 12:16
```

### ⛔⛔ 92% of the headline was never about tables — and 17 of it was ours

`{AUTHORITATIVE_SIGNAL_JOINS}` ×133 · `{AUTHORITATIVE_SCORE_SQL}` ×116 ·
`{AUTHORITATIVE_REASON_CODE_SQL}` ×81 · `{_COLUMNS}` ×27 — **shared SQL fragment constants**,
which is good practice. ⛔ And `{o}` in `platform/receipts.py` is `_org_filter`'s output, the
string `" and org_id = :org"`: **a correctly parameterised filter counted as unresolved SQL,
seventeen times, one module from the one defining the measurement.** The filter is right; the
metric was wrong, and the fix belongs in the metric.

### ⛔⛔ Three were the resolver's own regexes

`_VERBS` interpolates `_TABLE` — the table-name **pattern** — into four templates shaped exactly
like SQL. **The observer was counting its own instrument.** ⛔ Excluded by declaration, not by
heuristic: *"skip a statement with a regex character class"* would hide real SQL, because
`0047_l3_domain_compiler.sql` contains `expertise_id ~ '^expertise_[0-9a-f]{64}$'`.

### Three hops, and only one recovered knowledge

| hop | effect |
|---|---|
| **imported constants** | 49 → 27. `HISTORY_TABLE` is in `history.py`; the 15 statements using it are in `anomaly.py`, which imports it. ✅ **Recovered 16 (table, file) attributions** |
| **own regexes** | 27 → 24, by declaration |
| **local aliases** | 24 → 16. All three activation modules do `table = L3_ACTIVATION_TABLE`. ⛔ **Added ZERO attributions** — every aliasing module already referenced its own table in a plain literal. Said plainly rather than implied |

### ⛔ The observer problem, checked rather than assumed

Captured before, compared after: `known_tables` 189 ✅ · `table_usage` 185 ✅ ·
`written_and_unread` the same 9 ✅ · `undeclared_unread_writes` () ✅ · unreceipted per package
identical ✅ · `deletion_list` 102 ✅. **No verdict moved** — ⛔ and that was **luck, not design**: a
table referenced ONLY through an imported constant would have been reported write-only, the bug
this module says it has paid for three times. The values are now pinned in the guard.

### ⛔ The ratchet, and why it failed

It existed: `unresolved / statements <= 0.30` against **22.4%** — about **220 statements of
headroom**. ⛔ A ceiling that loose cannot notice. And the guard's docstring still said *"639 of
2,867"*. It is now **absolute** on `unresolved_table`, **asserted to be within 2 of the actual**,
with a floor under `statements` — and the fragment count deliberately **not** ratcheted, because
extracting a `where` clause into a constant is good practice.

### ⛔⛔ The self-witness family, fourth variant

My test expected four verb patterns in the source and found **five**: the fifth is inside
`SELF_MEASURED_PATTERNS`' own comment, which **quotes** the pattern it excludes.

| step | variant |
|---|---|
| `2.1` | a declaration **falsifies its own count** |
| `2.2` | a declaration **satisfies the test that its source exists** |
| `2.2` | a **correction's names** were checked against nothing |
| `3.1` | a **quoted example counted as a real one** |

⛔ And two of my own guards had real holes: `STATEMENT_FLOOR` was read from the constant the test
asserted against (**lowering it weakened the test**), and an `or` let half the evidence go — the
**fourth** time that disjunction has done it.

### Doctrine

| rule |
|---|
| ⛔⛔ **the observer counts its own instrument** |
| ⛔⛔ **a quoted example is counted as a real one** — count distinctly, never delete the quote |
| ⛔ **a threshold a test reads from the thing it guards is a variable with a confident name** |
| ⛔ **a ceiling with slack is not a ratchet** |
| ⛔ **a resolvable hole declared unresolvable says there is nothing to do** |
| ⛔ **the test must read what the measurement reads** |
| ⛔ **state an expectation only after measuring it** |


---
---

## ⛔⛔ 2026-10-04 · `3.1b` — A DELETE IS NOT A READ

```
unresolved_table      16 → 7     ceiling re-ratcheted to 7, slack 0
statements               2,885   ✅ unchanged — the measured decision
⛔ written_and_unread     9 → 9   SAME COUNT, MEMBERSHIP TURNED OVER
declarations   6 retired · 1 retracted · 1 added · ⛔ 2 CATEGORIES retired
tests 56 (28 + 28) · mutations 17 caught · ⛔ 1 real hole · 1 dead clause removed
full suite  15,494 passed · 0 failed · 12:44
```

### ⛔⛔ The bug the deferral found

```python
"delete": rf"delete from {_TABLE}"
"read":   rf"(?:from|join) {_TABLE}"      # ⛔ `delete from cards` matches BOTH
```

⛔ The loop hop amplified it a hundredfold — `api/account_routes.py` runs `delete from {tbl}` over
**102 tables** — so resolving one hole attributed a spurious read to a hundred tables and **four
stopped being reported write-only**. ✅ **The before/after comparison is the only reason four
correct declarations were not retired on the strength of a regex bug.**

Fixing it (`(?<!delete )`) removed **139 spurious read facts across 106 tables**, and ⛔ **five
tables lost their ONLY read attribution** — including **`macv_ledger`**, whose only "read" was
`delete from macv_ledger`. ✅ That mechanically proves what `19-PENDING` already records as a
product finding. ✅ And a subquery's read survives, which is tested.

### ⛔ The naive hop was wrong, and it was measured before building

| | before | ⛔ naive | ✅ built |
|---|---|---|---|
| `statements` | 2,885 | **3,036** | **2,885** |
| `unresolved` | 621 | **631** — *rises* | 621 |
| `unresolved_table` | 16 | 7 | **7** |

⛔ `statements` is the share assertion's denominator and a number the coverage report prints. **A
number other things read does not change meaning for a resolver improvement.** So attribution
expands and the statement count does not.

### ⛔ The count held while the membership turned over

`source_identity_map` **left** — `context/merge.py` has always read it, inside the very loop this
hop resolves, and ⛔ **the retracted entry had predicted its own retraction**: *"Read by nothing…
MOVES WHEN identity resolution reads back its own map."* Answered by a resolver change, not by new
code.

`warm_lane_slots` **arrived** — ⛔ **hidden by its own delete.** ✅ And write-only **by design**: a
lease table where the row's existence IS the state, read through `insert … RETURNING slot` and
`update … rowcount`. ⛔ **A fifth blind spot: `returning` and `rowcount` are reads no verb pattern
here can express.**

### ⛔ `3.1`'s own declaration was misfiled, and two categories were retired

`scripts/rebuild_graph.py` was filed `not-a-table` describing a `create table` statement that
**`_SQL_SHAPE` never counted**; the one counted statement is a plain `delete` of eight real tables.
⛔ Wrong in both halves. `not-a-table` and `resolvable-deferred` are both **retired with their
membership**, and the test guarding the latter was **deleted with it** — a test over an empty set
reads as coverage.

### ⛔ The guard had drifted

`3.1` put the exclusion logic in `resolution()` and its guard re-derived it. When this hop landed
**the metric stopped counting nine holes and the guard's copy did not.** *Two implementations of
one question will disagree on the day one of them is right.* `open_table_holes()` is now the single
answer.

### Doctrine

| rule |
|---|
| ⛔⛔ **`delete from X` is not a read of X** — a regex that cannot tell them apart hides write-only tables behind their own deletes |
| ⛔⛔ **a resolver improvement must not change what a shared number MEANS** |
| ⛔⛔ **two implementations of one question will disagree on the day one is right** |
| ⛔ **a count that holds while its membership turns over is a finding a bare count hides** |
| ⛔ **clearing two of three caches is theatre with a prop** |
| ⛔ **a mixed collection answers for nothing** |
| ⛔ **`returning` and `rowcount` are reads no verb pattern can express** |
| ⛔ **retire an emptied category, and delete the test that guarded it** |
| ✅ **a deferred unit is where a pre-existing bug surfaces** |
