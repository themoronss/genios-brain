# L2 · FINDINGS — the index

> **This file is an index, not a source.** Every finding below is recorded in full somewhere else in
> this folder; the point of the page is that L2's findings ended up spread across seven numbered
> documents, and the folder convention asks for one place that lists them.
> **Date:** 2026-10-01.

---

## The findings, in the order they were found

| | Finding | Full record |
|---|---|---|
| **1** | ⛔ **The Atlas badged built things as gaps.** 1 of the first 3 spot-checked was wrong, and the whole build order rested on those badges. Verified already built but badged a gap: coverage receipts, absence machinery, `ReasoningRequest`, `ContextSnapshot`, `CritiqueVerdict`, `DeliveryObject`, `brief.v1` | `STEP-01-DONE-prove-the-claims.md` |
| **2** | ⛔ **A step was retired rather than built.** The receipt S2 planned was already proved by an existing test file — which also proved a *different* gap S2 actually has | `STEP-02-RETIRED-skip-receipt.md` |
| **3** | **Two units complete and compute nothing.** `core.impact` 100% silent over 1,973 completions, `core.opportunity` 94%. Root cause is upstream: `deal.status` has **3 rows** and no writer | `08-AUDIT-AND-PLAN-the-silence-receipt.md` → declared in `reason/unit_health.DECLARED_SILENT` |
| **4** | ⛔ **I refused a correct fix on a false reading.** `08` PART 1.3 claimed the lost-axis receipt would rehash ~100% of 12,170 traces. `ReasoningStore._verify_replay_bundle` hashes **stored content against its stored hash** and never re-runs a unit — **zero rows rewritten**. `contracts/reasoning.py:845` warns about changing `to_semantic_dict`, a different operation | `09-AUDIT` PART 0; `08` carries a header marking PART 1.3 wrong |
| **5** | **`tradeoff.cost_vs_benefit` has fired 0 times in 1,200 production rows** while its test passes — on a prior the test supplies itself. `axis_count` is 1 on 63% of runs, 2 on 37%, **never 3** | `09-AUDIT-the-lost-axis-receipt.md` |
| **6** | **14 of 22 bound fact paths have no writer**, across **5** movers | `10-AUDIT-B-the-fact-writer-census.md` → declared in `DECLARED_UNWRITTEN` |
| **7** | ⛔ **The `evaluate()` cascade.** One failing receipt left the connection invalid for every receipt after it, so **12 phantom ERRORs hid 9 real findings** and named the wrong twelve. Fixed with `c.rollback()` in a **`finally`**, not an `except` | `10-AUDIT-B` |
| **8** | ⛔ **Three claims in `07` were wrong and are corrected there, not deleted.** `core.signal_composition` **is** scheduled by `DEAL_HEALTH_V1`; `deal.status` has **3 rows**, not "no writer at all"; and **ALARM A5 was overstated** — I claimed the live lane schedules none of `core.impact`/`core.cost`/`core.opportunity` when all three have completed thousands of times | `07-DOES-IT-ACTUALLY-WORK.md`; A5 corrected in 3 files |
| **9** | **Atlas required behaviour: 8 of 12 met, 4 partial, 0 absent.** `rejected_candidates` is carried by **151 of 165 cards (91%)**, which refutes the Atlas's two sharpest accusations | `11-ATLAS-CHECK-layer-2-required-behaviour.md` |
| **10** | ⛔ **A receipt that could never go green.** L4's frozen-formula receipt asked a correct question with **no date on it**: 59 candidates carried the forbidden 5000 neutral default (53 of them on all five components), the defect closed **2026-09-08** by `75096bab`, and 34,167 candidates have been clean since — but the table is append-only, so it returned 59 forever | `12-AUDIT-D-the-frozen-formula-receipt.md` |
| **11** | ⛔ **A third kind of silence, invisible to the receipt that asks about silence.** `core.relationship` has **929 runs and 0 completions**. `_UNDECLARED_SILENT_UNITS_SQL` filters `where status = 'completed'`, so a unit with no completed rows is not a low row — **it is not a row** — and the silence receipt was green. The fact was already written in prose **twice**, once in `receipts.py` and once inside `DECLARED_SILENT["core.impact"]`'s own reason text as an argument for a *different* unit's entry | `13-ATLAS-RECHECK-the-two-planes-and-the-third-silence.md` |
| **12** | **Plane D is complete; the Atlas's accusation about it has EXPIRED, and its Plane R accusation was exact.** Admin was *"all 57 stubs, zero reviewed/accepted, zero routes"* on 2026-08-22; measured 2026-10-01 it is **59 capabilities, all admitted, 0 hollow, 34 situations**, and the corpus is **155 capabilities with 0 hollow**. Meanwhile `CORE_UNITS` really is **17** and `BUILTIN_CAPABILITIES` really does schedule **7** — but **22 of 23** units now run in production, so *"registered is not active"* no longer holds | `13-ATLAS-RECHECK` PARTS 1–2 |

---

## ⛔ The two that changed how the rest of the programme was run

**Finding 4** is the most important entry on this page, and it is a finding about me rather than
about the code. I read a warning in `contracts/reasoning.py`, applied it to a different operation,
and **refused a correct fix in writing.** The correction is recorded as a new section rather than an
edit, which is the only reason it is visible at all.

**Finding 7** is why every receipt number taken before it is suspect. Twelve of thirteen reported
ERRORs were an artefact of the first failure, and the operator page named the wrong twelve things as
broken. **A measurement taken through a broken instrument is not a measurement**, and the nine real
findings underneath it had been invisible for as long as the cascade existed.

---

## Where the rest lives

* the two planes have their own findings pages — `plane-d-domain-expertise/03-FINDINGS.md` and
  `plane-r-reasoning-units/03-FINDINGS.md`
* every fix with its reasoning: `../05-FIX-LOG.md`, append-only
* current status of everything: `../07-LEDGER-every-step-what-why-how-outcome.md`
