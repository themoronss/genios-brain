# Plane D — what a professional knows · `packs/` + `Domain Expertise/`

**34 files · 7,957 lines of code, plus a corpus that is not code at all.**

> How would an experienced admin manager understand this situation — **without deciding what to do
> about it**?

---

## Three things it is not

| | |
|---|---|
| **Not an answer book** | it never says "renew the vendor". It says what to examine, what normally matters, what could explain the facts, and what would prove the explanation wrong |
| **Not a reasoning engine** | it retrieves, filters, binds, scopes, versions and permission-checks. The thinking happens in Plane R |
| **Not a place for company facts** | Acme's approval limit is the organisation brain's, not the expert brain's. Mixing them is how one company's habit gets taught as a universal rule |

---

## The corpus

```
Domain Expertise/<Domain> Expertise/
    domain.yaml                  the domain's identity
    capabilities/<group>/<capability>/
        capability.yaml          identity · question · outcomes · failure_modes · kpis · admission
        knowledge.yaml           the knowledge block
        objects.yaml             the LOAD-SET: core/scoped × required/optional
        situations/*.yaml        the situations this capability owns
    heuristics/                  the executable doctrine — where `reads:` lives
    deferrals.yaml               the named reason a capability has no door
    registry/                    the generated situation ↔ capability map
    _schema/vocabulary.yaml      the 141 substrate fact paths offered to authors
    _tools/                      admit · validate · index · plan · render
```

**Compiler order is fixed:** `capability_resolver → object_resolver → knowledge_retriever`.
Variants used to resolve in the last of the three, so a branch could be selected, loaded, carried
into the package and hashed into its address — and could not affect the **plan**, which had already
decided which. That is why `resolve_declared_variants` moved earlier.

---

## ⛔ Three file types, three different edit rules

The most practical thing to know before touching the corpus.

| File | Has `admission` hash? | Compiler checks it? | Safe to edit? |
|---|---|---|---|
| `capability.yaml` | yes | **yes** | ❌ **no — an edit un-accepts it** |
| `situations/*.yaml` | recorded | no | ✅ yes |
| `heuristics/*.yaml` | 60 of 60 have none | — | ✅ **freely** |

`capability_resolver._admission_reason` hashes the document *minus* its admission block and
compares: *"the hash pin is the difference between accepting a FILE and accepting its CONTENT — an
edit after review silently un-accepts, which is the point."* `_tools/admit.py` re-stamps but
**refuses to grant review**.

### The admission asymmetry, and why it is right

A **capability** that fails admission is dropped in live mode. A **situation** that fails is
**flagged, not removed** — it lands in `admission_gaps`, `review_state` becomes `draft`, and
delivery downgrades its card to an **observation**. Its detection belongs to L3 and is
evidence-backed whatever a reviewer thinks of the copy; only its prescriptive words are unreviewed.

> **The intelligence still ships; it stops instructing.**

⛔ **`review_status: approved` is necessary and NOT sufficient.** On 28 Sep six drafts were flipped
on that reading; five had to be reverted the next day because
`registry/situation-capability-map.yaml` declares them `pending_l2_types`, and one records in its
own file that flipping it *"would cost a false assurance"*. **The registry is the other half of the
answer. Read both.**

---

## Four brains — and only one is full

| Brain | Answers | Store | State |
|---|---|---|---|
| **Expert** | what a competent professional generally knows | **Git** → compiled pack | ✅ **full** |
| Organisation | what this company officially requires | `learned_brain_entries` | ⛔ **empty** |
| Behaviour | how this company actually operates | `learned_brain_entries` | ⛔ **empty** |
| Adaptive | what matters right now | `temporary_memories` | ⛔ **empty** |

Machinery has existed since migration **0045**; both tables are empty because nothing produced
proposals. All four supply modules run from `feedback/orchestrator.py`.

**Precedence when they conflict:** law and safety → approved organisation policy → explicit
authority decision → active constraint → domain expertise → observed behaviour → generic heuristic.

⛔ **Without the three empty brains, GeniOS gives consulting advice** — correct, generic, and not
about *this* company. The compiled judgment that no single brain contains ("the formal approval
limit, the observed CFO delay and the current cash priority together shrink the decision window")
is unavailable until they are populated.

---

## Measured today

| | |
|---|---|
| Admin capabilities | **59 admitted · 0 hollow** |
| Admin situations | **34** — 27 stable, 7 draft |
| Of the 7 drafts | **4 declared `pending_l2_types` and must stay draft**; 3 await a named reviewer |
| Heuristics | 60 files, **none hashed** |
| Vocabulary | 141 fact paths · **61 consumed by no capability** |
| Of those 61 | ~40 belong to Support's desk anchors, and Support is on hold. **Admin's real gap is `document.*` (8) and `derived.history.*` (4)** |

---

## The polish this plane needs

1. **Close Admin's real vocabulary gap** — `document.*` and `derived.history.*`. Not all 61; the
   Support 40 are on hold by design.
2. **Governance for `heuristics/`** — version, hash, reviewer, tests, shadow run, rollback. 60 of
   60 files are freely editable today, which is the widest unguarded surface in the corpus.
3. **Admission tests and golden cases for `situations/*.yaml`** — the compiler does not check them.
4. **Populate the organisation brain at onboarding** — roles, owners, approval thresholds, critical
   vendors. Ten minutes of setup beats weeks of inference.
5. **Behaviour brain in observe-only mode** — approval latency, follow-up latency, review timing.
   **Never auto-promote.**
6. **Depth before breadth.** Four capabilities built deep — commitments and follow-ups, decisions
   and approvals, meetings to actions, vendor and subscription renewals — each with a ten-case
   evaluation corpus **including must-abstain cases**.

⛔ **Sales and Support stay in shadow** until they pass Admin's evaluation bar. Shipping them at a
lower bar under the same brand is the fastest way to lose the trust the corpus exists to earn.

## Read these first

`packs/compiler/capability_resolver.py` — `_admission_reason` ·
`Domain Expertise/Admin Expertise/registry/situation-capability-map.yaml` ·
`Domain Expertise/_schema/vocabulary.yaml` · `Domain Expertise/Admin Expertise/deferrals.yaml`
