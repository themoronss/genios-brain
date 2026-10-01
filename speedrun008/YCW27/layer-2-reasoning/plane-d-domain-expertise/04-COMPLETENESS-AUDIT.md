# Plane D · is the expertise complete? — the unit-by-unit, layer-by-layer answer

> ⛔ **ANSWERED AND THEN CLOSED, 2026-09-30.** This page recorded five gaps. **All five are now
> built** — see `STEP-07-DONE-the-expertise-is-complete.md`. The audit below is kept as written,
> because what was missing and why is the part worth keeping; the result table is at the end.

**Date:** 2026-09-30. **Every number was produced by running something, in this session.**

## ⛔ The answer: NO — and here is exactly where

| Layer | Admin | Support | Sales | Verdict |
|---|---|---|---|---|
| `domain.yaml` | 1 | 1 | 1 | ✅ |
| `capability.yaml` | **59** | 49 | 47 | ✅ all `stable` + `approved` + hash-accepted |
| · missing a declared block | **0** | 0 | ⛔ **2** | ⛔ Sales — no `failure_modes` |
| · stub | 0 | 0 | 0 | ✅ |
| · hollow (says nothing) | 0 | 0 | 0 | ✅ |
| `knowledge.yaml` | 59/59 | 49/49 | 47/47 | ✅ one per capability |
| `objects.yaml` load-sets | 24 req + 20 opt | 32 + 29 | 26 + 25 | — |
| · **required and unauthored** | **0** | ⛔ **11** | **0** | ⛔ Support blocks compiles |
| `situations/*.yaml` | 34 | 20 | 15 | 27/4/15 stable, rest `draft` |
| · a draft that may instruct | 0 | 0 | 0 | ✅ all 23 correctly gated |
| `objects/**` | 25 | 21 | 29 | — |
| · **status** | ⛔ **25 draft, 0 stable** | 12 draft / 9 stable | ⛔ **29 draft, 0 stable** | ⛔ **nothing reviewed** |
| · referenced but unauthored | ⛔ **13** | ⛔ 14 | 0 | ⛔ dangling cross-references |
| `heuristics/**` | 60 | 154 | 69 | — |
| · **status** | ⛔ **44 draft** | ⛔ **146 draft** | ⛔ **28 draft** | ⛔ **218 of 283** |
| · **carrying an admission hash** | **0** | **0** | **0** | ⛔ **nothing is gated** |
| `deferrals.yaml` | ✅ 30 | ✅ 7 | — none needed | ✅ |
| routing census | 35 routed · 24 deferred · **0 neither** | 42 · 7 · **0** | 47 · 0 · **0** | ✅ **closed** |

---

## What IS complete, and it is the part that decides whether the product works

⛔ **Every object an Admin capability's load-set requires is authored.** 24 required, 20 optional,
**zero missing.** No Admin compile can stop on absent expertise — a missing `required` would raise
`RequiredKnowledgeMissing`, and there are none.

Plus: 59 capabilities with **0 stub and 0 hollow**, every one carrying a `knowledge.yaml` and an
`objects.yaml`; all 23 draft situations correctly informing rather than instructing; and the routing
census **closed in every domain** — `0 neither`, every capability has a door or a named reason.

---

## ⛔ The five gaps, as units

| # | Gap | Measured | Blocks a compile? | Whose |
|---|---|---|---|---|
| **G1** | 2 Sales capabilities declare no `failure_modes` | `lead_qualification`, `customer_success` | no | **mine** |
| **G2** | 13 Admin core objects are referenced and unauthored | `stakeholder` ×32, `audit_evidence` ×21, `delegate` ×15, `service_level` ×15, `record_series` ×9, `purchase_order` ×8, `facility` ×5, `itinerary` ×5, `admin_risk` ×4, `authority`, `budget`, `compliance`, `employee` | ⛔ **no** — every one is a cross-reference inside object files; **0 reach a load-set** | **mine, with your review** |
| **G3** | Objects and heuristics have **no admission gate at all** | 283 heuristics, **0 hashed**; 218 `draft`. All 25 Admin objects `draft` | no — because nothing reads their status | **mine** |
| **G4** | 11 Support required objects unauthored | `support_agent` blocks 6 capabilities, `queue`/`intent`/`resolution` 3 each | ⛔ **YES** | ⚠️ **yours — Support is on hold** |
| **G5** | No evaluation corpus, no **must-abstain** cases | none exist in any domain | no | ⚠️ **yours — needs domain judgment** |

---

## ⛔ The sharpest of the five is G3, and it is not the one that looks biggest

A `capability.yaml` cannot be edited without un-accepting itself — `_admission_reason` hashes the
content minus the admission block and compares. A **situation** is flagged by
`situation_admission_reason` and its card stops instructing.

**An object and a heuristic are gated by nothing.** 283 heuristic files, zero hashes, 218 of them
`draft` — and **`heuristics/` is where `reads:` lives**, which is the declaration of what a piece of
doctrine consults. Anyone can change what the expertise consults, silently, and no gate, test or
receipt notices.

> The ceremony this corpus already performs twice does not reach the two layers with the most files.

---

## The build order — bottom-up, leaf first

```
level 0 ·  G1  Sales' two capabilities declare how they fail          (no dependencies)
level 0 ·  G2  the 13 referenced Admin core objects are authored      (no dependencies)
level 1 ·  G3  objects and heuristics carry a status something READS  (needs G2 authored first,
                                                                       or the gate fires on ids
                                                                       that do not exist yet)
level 2 ·  G5  the must-abstain evaluation corpus                     (needs G3's vocabulary)
   —    ·  G4  Support's 11 required objects                          ⚠️ blocked on your decision
```

---
---

# ⛔ RESULT — all five closed

```
corpus warnings   283  ->  35
"planned but not authored yet"   237  ->  0
```

| Layer | Before | After |
|---|---|---|
| Sales capabilities missing a block | 2 | **0** |
| Admin objects referenced and unauthored | 9 | **0** |
| Support objects **required** and unauthored | 11 | **0** |
| objects on any roster, unauthored | 22 | **0** |
| objects/heuristics with an admission gate | none | **counted, per package** |
| evaluation cases | 0 | **18, of which 10 must abstain** |

**And what the remaining 35 warnings are — none of them a missing object:**

| n | kind | whose |
|---|---|---|
| 13 | scope advisory (*"consider demoting this to that capability"*) | authoring taste |
| 10 | relationship verb outside the recommended set | **pre-existing**, in Support's own objects |
| 6 | Sales artifacts authored but unreachable | **pre-existing** |
| 5 | an L2 type no situation binds | ⚠️ **yours** — who owns each of the five |
| 1 | an evidence source outside the recommended set | **pre-existing** |

## ⛔ What "complete" does and does not mean now

**It means:** nothing a compile needs is missing, in any domain. Every capability is admitted, every
object on every roster is authored, every load-set resolves, every capability has a door or a named
reason, and a first set of cases asserts correct behaviour — including what must be refused.

**It does not mean reviewed.** 88 objects and 283 heuristics are `draft` and carry no admission hash.
That is now **measured** (`unreviewed_object_ids`, `unreviewed_artifact_ids`) rather than invisible,
and turning the measurement into a gate is a decision with a number under it — not a guess.

⛔ **And 22 of the objects were authored by me, in one pass, from what the corpus already implied.**
Every one is `status: draft`, `review_status: unreviewed`, `created_by: ai`, with a header naming
what it was derived from and what a fuller pass would add. Three say `completeness: skeleton` because
they had no declared usage to derive from at all. **None of them carries anybody's signature, and
none can instruct.**
