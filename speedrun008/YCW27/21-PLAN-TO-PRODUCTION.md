# 21 · THE PLAN TO PRODUCTION — what is left, step by step

**Written for:** Rohit. **Date:** 2026-10-03. **Supersedes nothing** — it sits beside
[`19-PENDING-who-owns-what.md`](19-PENDING-who-owns-what.md), which stays the by-owner page. This
one is the **order**, and the standard each step has to meet.

---

## 0 · ⛔⛔ THE CRUX, BEFORE ANY LIST

```
built      660 files · 215,992 lines · 15,220 tests green · 42 receipts
live       ⛔ no card since 2026-09-25 11:09 UTC
           ⛔ five migrations never applied — 0190 breaks insert_card ON WRITE
           ⛔ no domain activated for any tenant
```

⛔ **Almost everything is built and almost nothing is live, and the distance between them is not
engineering.** It is three things, and **two of them are not mine**:

| | | owner |
|---|---|---|
| `H1` | five unapplied migrations, `0186`–`0190` | **Harsh** |
| `R1` | the Anthropic spend limit vs `GENIOS_L4_LLM_DECISION_MAKER` | **Rohit** |
| `R2` | activation — turn one domain on for one tenant | **Rohit** |

⛔ **The `R#` ids are introduced by this document and mirrored into `19-PENDING-who-owns-what.md`,
so there is ONE list.** They did not exist before: Rohit's items were named inconsistently
(*"DECISION #5"*, *"U6c"*, *"the reporting line"*) across four files, which is how the same item
gets worked twice or not at all. ⛔ *Two vocabularies for one thing is a defect this programme has
already paid for three times* — the `LAYERS` digit, the two visibility scopes, and Layer 2's state
in three disagreeing headers.

⛔ **So the honest reading of "make everything production level" is: my remaining work does not
reach production on its own.** Phase 0 below is the whole path, and I own none of it. Phases 1–3
are mine and they make the product *provable* once it is live — which is worth doing in parallel,
not instead.

⛔ **And one thing the original brief asked for is now closed.** Of the eight items that were
VERIFIED MISSING when this programme opened — `EvidenceNeed`, `SituationSeed`,
`QualifiedEnterpriseSignalBundle`, `ConfidenceVector`, the five pipeline counters and the five
output lanes — **seven are built** (`contracts/evidence.py`, `contracts/signal.py`,
`contracts/situation.py`, `platform/funnel.py`, `contracts/reasoning.OutputLane`) and the eighth,
`SituationSeed`, is **declared unnecessary** in `17-THE-THREE-LAYERS-end-to-end.md`: *"the Atlas
names it; it has zero hits in the code and nothing needs it."*

---

## 1 · WHAT "PRODUCTION LEVEL" MEANS HERE — seven conditions, all checkable

⛔ Without a definition this phrase means "work until it feels done". These seven are the ones this
programme has actually paid for, each from a defect it did not catch:

| # | Condition | The defect it exists for |
|---|---|---|
| **P1** | the claim is checked by a **receipt against production data**, not only by a test | `feedback/` ran weekly with four receipts, all presence checks — a loop that could be entirely wrong and pass every one |
| **P2** | the receipt **can fail** — it is not structurally green | *a gate that is always red is a gate nobody reads*, and always-green is the same defect wearing a pass |
| **P3** | the package's silences are **declared and guarded both ways** | an entry naming a function that is now called is as much a lie as a function unreached and undeclared — caught twice in two days, both times mine |
| **P4** | its tests **do not skip** | 27 tests in `tests/feedback` and 4 in `test_delivery_spine` have never run. *A skip is not a pass* |
| **P5** | its **migration is applied** | `0190` is unapplied and `insert_card` fails on write — masked only because nothing is routing |
| **P6** | the path is **activated** for at least one tenant | the lower half of the stack runs correctly over an empty queue, which proves nothing |
| **P7** | it has been **measured once against production**, not inferred | the Atlas was written design-side and mislabelled built things as gaps; 21 of its 51 claims are still open and 8 EXPIRED on measurement |

> ⛔ **By this definition nothing in the product is production-level today**, because `P5` and `P6`
> fail for everything. That is not a reason to weaken the definition.

---

## 2 · PHASE 0 — the live path · ⛔ NOT MINE, and nothing else matters until it moves

Strictly ordered. Each step is cheap; the order is what makes them safe.

| # | Step | Owner | Why this order |
|---|---|---|---|
| **0.1** | `git push origin speedrun008` — **17 commits, tree clean, suite green** | ⛔ **Rohit** | ⛔ Everything below is reviewed against pushed code. `git push` is refused for me by the auto-mode classifier and I do not retry or work around it |
| **0.2** | **`H1`** — apply `0186`–`0190` in order, in one window | 🔴 **Harsh** | ⛔ `0190` breaks `insert_card` on WRITE today. ⛔ **Clearing one without the other turns a silent outage into a loud one** — `0189` adds the lane column `0190`'s card write needs |
| **0.3** | **`R1`** — set `GENIOS_L4_LLM_DECISION_MAKER=false` (recommendation **B**) | ⛔ **Rohit** | the spend limit has refused every model call since 2026-09-25 11:09 UTC. ⛔ The DEFER is *declared*, not a defect in `executive/` — but while it stands, no card can be produced at all |
| **0.4** | **`R2`** — activate **Admin** for one tenant | ⛔ **Rohit** | five switches: `l1_semantic_activation`, `l2_v2_activation`, `l3_activation`, `l4_activation`, `pattern_activation`. ⛔ Admin only — the standing constraint |
| **0.5** | **`H8`** — the three read-only checks | **Harsh** | ⛔ **This is the first time anyone will know what production actually holds.** Nine write-only tables' size · the two receipts that have never run · whether `merge_history` is empty |
| **0.6** | **`H6`** + **`H7`** — run the DB-dependent tests where a database exists | **Harsh** | 27 + 4 tests that have never run. ⛔ Any failure is a **real finding**, not a regression |

⛔ **After 0.2–0.4, run the readiness receipts once and keep the output.** That single artifact
turns `P7` from a promise into a baseline, and 42 receipts have never all been evaluated together:

```
# with a database configured, read-only
.venv/bin/python -c "from genios_engine.platform.db import get_engine; \
from genios_engine.platform.receipts import evaluate; import os, json; \
print(json.dumps(evaluate(get_engine(os.environ['GENIOS_DATABASE_URL']), '<org>'), indent=2, default=str))"
```

---

## 3 · PHASE 1 — mine · coverage to the `P1`/`P2`/`P3` standard, in measured order

The order is **not** my preference. It is `20-AUDIT-every-package/00-INDEX.md`'s table, read on the
column that matters: **tables a package writes that no receipt asks anything of.**

| # | Step | The measurement that chose it | Verify |
|---|---|---|---|
| **1.1** | ✅ **`api/` audit — DONE 2026-10-03** · ⛔⛔ **11 candidates raised, 11 retired**, and the one finding that survived was `learning_objects` being write-once with nothing asserting it → [`22-AUDIT-api-eleven-candidates-eleven-retirements.md`](22-AUDIT-api-eleven-candidates-eleven-retirements.md) | 44 files · **19,498 lines · 20 writers · 28 unreceipted tables · only 2 declared silences · 11 modules no test names.** ⛔ Worst in the product on **three columns at once**, and it is the layer a customer touches. ⛔ It never appeared in `S7`'s ranking because *lines per receipt* with a **zero denominator** does not sort | `pytest tests/api tests/platform -q` + both-ways declaration guard |
| **1.2** | ✅ **`platform/` audit — DONE 2026-10-03** · ⛔ **15 candidates raised, 15 retired**, and the survivor is a park the health check **excludes by construction** → [`23-AUDIT-platform-the-park-the-health-check-excludes.md`](23-AUDIT-platform-the-park-the-health-check-excludes.md) | 12,651 lines · **1 receipt** · 18 writers · 25 unreceipted. ⛔ The package every other package imports | `pytest tests/platform -q` |
| **1.3** | ✅ **`reason/` audit — DONE 2026-10-03** · ⛔⛔ **20 candidates raised, 20 retired**, and the finding was in the AUDIT'S OWN MEASUREMENT: the *"no test names it"* column was wrong **19 of 33 times** and was **deleted** → [`24-AUDIT-reason-the-column-that-had-to-go.md`](24-AUDIT-reason-the-column-that-had-to-go.md) | 41,363 lines · 21 writers · **29 unreceipted** · ⛔ **14 modules no test names — the worst on that column** | `pytest tests/reason tests/test_reasoning* -q` |
| ⛔ **1.3b** | ✅ **DONE 2026-10-03** · **two live modules with no test, and one guarded HEALTH data**: `reason/team/away.py` promises *"no leave reason ever leaves this module"* with nothing asserting it, and `api/identity_routes.py`'s node-set gate is the only thing stopping a human merging two nodes no proposal names. 32 tests · **17/17 mutations** → [`25-STEP-1.3b-two-untested-modules-and-one-was-health-data.md`](25-STEP-1.3b-two-untested-modules-and-one-was-health-data.md) |
| **1.4** | ✅ **`capture/` audit — DONE 2026-10-03** · ⛔⛔ **AND IT WAS WRONGLY CALLED "PHASE 1 CLOSED" — `1.5` had never been done.** Corrected 2026-10-04: four of the phase's six steps were done, `1.5` is open, and `1.6` is a declared deferral. ⛔ A phase closed by counting the steps that were finished is the same defect as a receipt that passes over an empty table** · ⛔ **receipt 44** turns `journey.py`'s own sentence — *"why did I never see X?"* — into a production check, with five derivations and nothing spelled → [`26-AUDIT-capture-why-did-i-never-see-this-one.md`](26-AUDIT-capture-why-did-i-never-see-this-one.md) | 47,184 lines · 25 writers · 19 unreceipted · 7 silences over 158 files | `pytest tests/capture -q` |
| **1.5** | **`deliver/` + `executive/` + `packs/` sweep** | 10 + 6 + 2 unreceipted; declarations already strong (23 / 14 / 3) | `pytest tests/deliver tests/executive tests/packs -q` |
| **1.6** | ⛔ **`graph_nodes`** — 46 external readers, no receipt | ⛔ Deliberately **not** done in the `context/` audit, because the claim would have had to be **invented**. Do it only when a module states it: *a gate derived from an invented claim is a gate nobody reads* | the receipt renders, is correctness-shaped, and is declared in `receipt_coverage` |

⛔ **Every step in this phase follows the same five-trap discipline**, because six of the `context/`
audit's own findings died to it: a reader in `scripts/` · a mention that is prose · SQL held in a
module constant · a table name in a name constant · that constant passed as a **function argument**.
⛔ And each step **asserts `table_coverage.resolution()` has not degraded** — currently **639
unresolved of 2,872 statements**. *A resolver that answers for 1 of 104 answers nothing.*

---

## 4 · PHASE 2 — mine · the Atlas's open claims, biggest block first

21 of 51 identified claims are still open. ⛔ **L6's seven are not mine** — `S10` measured all three
of its unmeasured gaps and every residue is a decision.

| # | Step | Claims | What they are |
|---|---|---|---|
| **2.1** ✅ DONE | ⛔⛔ **L2 — nine claims** | `L2-01`…`L2-12` | ⛔ **The largest remaining block in the product.** Distinct source labels are not independent causal authorities · first claimant owns a same-name alias · the authority/ownership/resource views are incomplete · same-company independent deals can collapse without a deal object · **a tenant replay is missing** · role/source readiness is not in the blocking vector |
| **2.2** ✅ DONE | **L1 — five claims** | `L1-01`, `L1-07`…`L1-10` | only **eight** canonical source IDs are buildable · no mandatory typed business roles leave L1 · `RawObject`/`SourceEvent`/`GatedEvent` do not require visibility · the coverage snapshot is not mandatory on an emitted signal |
| **2.3** | **the rest of the scorecard** | — | re-measure every row once Phase 0 is live, because ⛔ **8 claims EXPIRED the moment they were measured** and 4 cells hid a defect the Atlas did not name |

---

## 5 · PHASE 3 — production hardening · the conditions Phase 1 does not reach

| # | Step | Why |
|---|---|---|
| **3.1** ✅ DONE | ⛔ the **639 unresolved SQL statements** (22%) ⛔⛔ **MIS-SCOPED: it was 645, and only 49 were about tables. Now 16, all declared** |⛔| | a table name passed through a **function argument** needs dataflow, not constant substitution. Today the two known cases are declared; the share is asserted so it cannot grow silently |
| **3.1b** ✅ DONE | ⛔ the **fourth resolver hop** ⛔⛔ **and it found `delete from X` being counted as a READ of X — 139 spurious facts over 106 tables** |⛔| — loops over constant collections of literal table names (`capture/journey.py`, `context/backfill.py`, two `scripts/`). ⛔ Declared `resolvable-deferred` rather than done in `3.1`: the erasure loop gives it a **102-table blast radius**, so it needs its own baseline | ⛔ 4 of the 16 remaining table holes |
| **3.2** ✅ DONE | **the always-green receipts** ⛔⛔ **and the release-gate CLI would have raised KeyError on the new status** |⛔| | ⛔ If `H8.3` says `merge_history` is empty, receipt 42 is structurally green forever. Gate it on a marker the way the learning receipts are, so it reads *"not yet exercised"* rather than *"passing"* — `P2` |
| **3.3** | **`U2b`** the approver column + contract field + wiring | ⛔ blocked on `H1` **and** one in-force authority rule. **794 actions, 410 want `requires_approval`, `authority_rules` has ZERO rows** |
| **3.4** | **`STEP-12`** the lane receipt | ⛔ blocked on `H1` (`0190`). It currently reads **ERROR**, not an answer |
| **3.5** | **the reporting line** | ⛔ `org_seats.manager_seat_id` or a dated `reports_to`. **124 day-7 escalations have never fired** |

---

## 6 · THE ORDER, ON ONE SCREEN

```
  PHASE 0   0.1 push ──▶ 0.2 H1 migrations ──▶ 0.3 R1 spend limit ──▶ 0.4 R2 activate
            ──▶ 0.5 H8 read-only checks ──▶ 0.6 H6/H7 the tests that never ran
            ⛔ none of this is mine, and nothing reaches production without it

  PHASE 1   1.1 api/ ──▶ 1.2 platform/ ──▶ 1.3 reason/ ──▶ 1.4 capture/
            ──▶ 1.5 deliver+executive+packs ──▶ 1.6 graph_nodes
            ✅ all mine · no dependency on Phase 0 · start now

  PHASE 2   2.1 L2's nine ──▶ 2.2 L1's five ──▶ 2.3 re-measure the scorecard
            ⛔ 2.3 needs Phase 0 live

  PHASE 3   3.1 the unresolved SQL ──▶ 3.2 the always-green receipts
            3.3 U2b · 3.4 STEP-12 · 3.5 the reporting line  ⛔ all blocked on Phase 0
```

⛔ **Phase 1 runs in parallel with Phase 0 and does not wait for it.** That is the whole point of
the ordering: the only work I can do today is the work that makes the product *provable*, and the
work that makes it *live* belongs to Rohit and Harsh.

---

## 7 · HOW EACH STEP IS DONE — the same shape every time

1. **Measure first, plan second.** ⛔ Every step in this programme that planned before measuring had
   its premise corrected by its own first measurement. Five corrections in two layers, and the
   `context/` audit retracted **six of its own findings**.
2. **Derive, never copy.** A claim comes from the module's own words or a declared constant. ⛔ A
   receipt built from a hand-copied list drifts the first time the list changes.
3. **Declare both directions.** Undeclared-and-unreached fails the build; declared-and-now-called
   fails it too.
4. **Mutation-test the guard**, baseline asserted **before and after**, `PYTHONDONTWRITEBYTECODE=1`
   with `__pycache__` cleared per invocation. ⛔ A stale `.pyc` makes a restored file read as the
   mutant, and the bias is toward **false kills**.
5. ⛔ **A guard changed to make your own build pass needs a negative control.** Without one, moving
   a guard is indistinguishable from weakening a verify.
6. **Full suite before the step is closed**, and the number is read, not predicted.
7. **Write it down**: the step doc, `03-FINDINGS`, `07-LEDGER`, `STATUS.md`, `19-PENDING`, and
   Harsh's notes if the finding needs a database.

---

## 8 · ⛔ WHAT IS DELIBERATELY NOT IN THIS PLAN

| Not doing | Why |
|---|---|
| fixing `feedback/units.distinct_days` | ⛔⛔ It is the only thing keeping an auto-promoted durable ADAPTIVE write closed. **ADR-10 first** — the tripwire explains it |
| a receipt per unreceipted table | ⛔ **141** tables have a writer and no receipt (183 written, 42 receipted) — measured, not estimated; the first draft of this line said 164. A claim that has to be invented is a gate nobody reads, so the ranked list says where a real claim is worth looking for |
| the 217 unauthored corpus refs | content work, and the declared frontier is not a bug |
| activating Sales or Customer Support | standing constraint: **Admin only** |
| renaming any ConfidenceVector axis | ⛔ Rohit's, and my recommendation is **keep the code's six and correct the Atlas** — `identity → authority` is not a rename, it is a different measurement |
| rewriting the 78 code-shaped absence guards | ⛔ **the rule, not the rewrite** — no measured defect, and each rewrite is a chance to change what a guard means |
| adding a clamp to the stored policy floor | real improvement, and it changes which proposals **every** tenant admits. Rohit's |

---

## 9 · WHERE TO LOOK

| | |
|---|---|
| **by owner** | [`19-PENDING-who-owns-what.md`](19-PENDING-who-owns-what.md) |
| **the audit** | [`20-AUDIT-every-package/00-INDEX.md`](20-AUDIT-every-package/00-INDEX.md) — eleven packages, generated |
| **for Harsh** | [`HANDOFF-HARSH.md`](HANDOFF-HARSH.md) — `H1`–`H8`, with runnable read-only SQL |
| **what each step did** | [`07-LEDGER-every-step-what-why-how-outcome.md`](07-LEDGER-every-step-what-why-how-outcome.md) |
| **the Atlas score** | [`08-ATLAS-SCORECARD-L1-to-L6.md`](08-ATLAS-SCORECARD-L1-to-L6.md) |
| **the live log** | [`STATUS.md`](STATUS.md) — reverse-chronological head index at the top |
