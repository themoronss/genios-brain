# Plane D · plan — six units, built bottom-up, leaf first

**Written for:** Rohit and Harsh (CTO). **Date:** 2026-09-30.
**Reads with:** `01-CROSSCHECK.md`. **Nothing here was written before that was measured.**

---

## The unit table

The plan's four became six. ⛔ **`M11.C5.U01` is RETIRED, not renumbered** — the tree's own rule:
*"IDs are permanent. When work is dropped, the ID is retired, never reused. When a unit splits, the
original retires and new IDs are minted."* So `U05`, `U06`, `U07` are new numbers, and `U02`–`U04`
keep theirs.

| id | layer | level | what | artifact |
|---|---|---|---|---|
| ~~`U01`~~ | — | — | ⛔ **RETIRED** — "the unrouted types become a runtime counter". One exists | — |
| `U05` | contract | **0** | `NoExpertiseRoute` carries a **validated** refusal reason | `packs/compiler/errors.py` |
| `U02` | data | **0** | the validator **generates** `unrouted_l2_types` | `Domain Expertise/_tools/validate.py` |
| `U03` | logic | **0** | a `draft` situation may not **instruct**, and the downgrade names it | `packs/compiler/expertise_builder.py` |
| `U06` | logic | **1** | route refusals counted by **(reason × situation type)** | `reason/domain_shadow.py` |
| `U04` | data | **1** | Customer Support's `deferrals.yaml` — all seven | `Domain Expertise/Customer Support Expertise/deferrals.yaml` |
| `U07` | interface | **2** | the probe reads the **field**, never the message | `scripts/corpus_route_probe.py` |

### The dependency graph, and why the order is what it is

```
level 0 ──  U05 contract: the refusal reason exists and is closed
            U02 data:     the unrouted list is computed, not typed
            U03 logic:    a draft situation cannot instruct

level 1 ──  U06 logic:    count by (reason × type)      needs U05
            U04 data:     Support's deferrals            needs U02 (same validator run)

level 2 ──  U07 interface: the probe reads the field     needs U05 and U06
```

⛔ **Bottom-up, one unit at a time, and never a parent before its children are green.** `U07` deletes
the blunt grep, and it cannot be built first: deleting a string match before the field exists would
leave the probe with no way to tell the three causes apart at all. `U06` cannot precede `U05` for the
same reason — a dimension needs something to be dimensioned by.

---
---

# LEVEL 0
---

## `U05` · contract · `NoExpertiseRoute` carries a validated reason

### What is there

```python
class NoExpertiseRoute(DomainCompilerError):
    pass
```

Nothing. And fourteen lines above it, `UnsupportedCoverage` does exactly the right thing — validates
its reason at construction, against a closed set, with a docstring explaining that folding distinct
causes into one count *"could never separate 'broken' from 'not built yet'."*

### What to build

Three reasons, closed both directions, **the three `corpus_route_probe` already distinguishes** — so
this is not a new taxonomy, it is the existing one moved from string matching into the type:

| reason | means | who fixes it |
|---|---|---|
| `unknown_domain_hint` | the situation named a domain with no corpus folder | whoever set the hint — a **routing** bug |
| `no_situation_binds_type` | no situation in any domain binds this L2 type | an **authoring** gap — somebody must own the type |
| `predicate_rejected` | a situation binds the type and its authored `when` refused this instance | the **author** of that predicate, or nobody — it may be correct |

⛔ **Three reasons, three different teams.** That is why they cannot share a bucket, and why the
`else`-branch catch-all in the probe is the defect: `predicate_rejected` may be entirely correct
behaviour, and it currently lands in the same number as a missing corpus folder.

⛔ **`reason` is REQUIRED, not optional with a default.** A default would let a new raise site produce
an unlabelled refusal that reads as one of the three, and the whole point is to stop guessing which.

⛔ **`situation_type` rides on the exception too.** `domain_shadow` catches the exception in a loop
whose row it still has, so it could pass the type separately — but then two call sites decide what
the pair means, and a raise that knows its own type and does not say so invites a caller to guess.

**Verify:** `tests/packs/compiler/test_a_refusal_says_which_kind_it_is.py`
— every reason reachable, every reason documented, a bad reason refused, and ⛔ **no reason inferred
from a message anywhere in `packs/`**.

**Outcome.** A refusal is machine-readable. Nothing behaves differently yet — deliberately: a contract
unit that changes behaviour is two units.

---

## `U02` · data · the validator generates `unrouted_l2_types`

### What is there

The validator computes `l2_types - bound_anywhere` and prints five warnings. The corpus **also** keeps
the same five by hand, in `Admin Expertise/registry/situation-capability-map.yaml`, under a comment
saying *"Global, not this domain's fault."*

### What to build

`_tools/validate.py --write-routing` regenerates the block, and plain `validate.py` **fails** when the
file disagrees with the computation.

⛔ **The check runs by default; the write does not.** A tool that rewrites the corpus whenever
somebody validates it makes `git status` unreadable and turns a read into a write. A tool that only
warns gets ignored. So: **compute always, compare always, write only when asked.**

⛔ **Sorted output, and a stable header.** An unordered regeneration produces a diff every run and
teaches everyone to ignore the diff.

⛔ **And the global-fact-in-one-domain oddity is RECORDED, not fixed here.** Moving the block out of
Admin's registry is a corpus reorganisation that touches every reader of that file; it is a separate
unit with its own decision. What this unit guarantees is that wherever it lives, it is **true**.

**Verify:** `.venv/bin/python "Domain Expertise/_tools/validate.py"` — exits 0 today, and
`tests/packs/test_the_unrouted_list_cannot_drift.py` proves it exits non-zero on a hand-edit.

**Outcome.** The list everybody reads for routing coverage cannot be wrong in the safe-looking
direction.

---

## `U03` · logic · a draft situation may not instruct, and the downgrade names it

### ⛔ REWRITTEN. The plan said *"may not compile a card"*

It must still compile one. The repo's own doctrine, in this plane's README:

> *"A situation that fails is **flagged, not removed** … **The intelligence still ships; it stops
> instructing.**"*

And an author refused the alternative explicitly, in `organization-gone-quiet.yaml:153`: *"the silence
IS observed … **not by demoting the whole card to a review queue.**"* Refusing the card would delete
an evidence-backed finding because a sentence next to it is unreviewed.

### What is there, and why it cannot fire

| | |
|---|---|
| `status: draft` on a situation | ⛔ **gates nothing.** `authoring.py` reads no admission block for a situation; `_admission_reason` takes a capability |
| `states_absence` | the right guard for a **different** question — *is this finding itself an absence* |
| `review_state = "accepted" if plan.admitted else "draft"` | correct, and **unreachable**: all 155 capabilities are stable + approved + hash-accepted, so `plan.admitted` is always True |
| Admin draft situations with nothing holding the card back | ⛔ **6 of 7** |

### What to build

The route plan already knows which situations it matched (`plan.situation_ids`) and the resolver
already reads those files. So:

1. `RoutePlan` carries `draft_situation_ids` — which of the matched situations are `status: draft`.
2. `expertise_builder` sets `review_state = "draft"` when **either** a capability failed admission
   **or** the rendering situation is draft, and records `draft_situations` in the metadata.
3. The existing `_apply_abstention` chain then downgrades the card to an observation, **unchanged** —
   because it already does the right thing and has for a while.

⛔ **`review_state` is REUSED, not joined by a second field.** The abstention gate, the API projection
(`expertise_review_state`), `cards.capability_review_state` and `domain_shadow`'s insert all read that
one value. A second parallel field means two things a card layer must check, and the first time
somebody adds a surface they will check one.

⛔ **And it must name the situation.** A downgrade that says only *"draft"* sends somebody hunting
through 1,426 files. `admission_gaps` is the existing shape for exactly this and the new ids go beside
it, not inside it: an unreviewed **situation** and an unadmitted **capability** are different gaps,
and `hollow_capability_ids` is already kept apart from `review_state` on precisely that argument —
*"a thin capability is a content gap, an unadmitted one is an authority gap, and one number cannot
mean both."*

⛔ **What this does NOT do:** it does not touch `states_absence`, and it does not change any of the
four stable situations that declare it. Those cards are gap-cards **by design**.

**Verify:** `tests/packs/compiler/test_a_draft_situation_cannot_instruct.py`

**Outcome.** Six Admin cards stop giving orders from unreviewed copy, and keep telling the founder
what is true.

---
---

# LEVEL 1
---

## `U06` · logic · refusals counted by (reason × situation type)

### What is there

```python
except NoExpertiseRoute:
    counts["no_route"] += 1
```

One flat number. *Twelve situations found no route* — one type twelve times, or twelve types once?
Opposite problems, opposite fixes, same number.

### What to build

`counts["no_route"]` **stays exactly as it is** — and the breakdown lands beside it:

```
no_route                              12      ← unchanged, every existing reader keeps working
no_route_by_reason                    {"no_situation_binds_type": 9, "predicate_rejected": 3}
no_route_by_type                      {"vendor_renewal_decision": 9, "reply_owed": 3}
```

⛔ **The flat total is not replaced.** `tests/reason/test_the_cutover_is_declared_before_it_happens.py`
asserts on `"no_route": 0`, and `scripts/` read the same key. Replacing a counter to improve it is how
a measurement wave breaks the gate that was watching it.

⛔ **The two breakdowns must sum to the total, and a test says so.** Two numbers that are supposed to
agree and are never compared eventually disagree — that is the L5 recall guard's whole argument, and
it applies verbatim here.

⛔ **NO new migration.** `counts` is a returned dict, already surfaced by the sweep. The funnel's stage
vocabulary is **closed** and enforced by a check constraint in `0188`; a route-refusal reason is not a
sixth funnel stage, it is the **why** behind an existing drop between `situations_formed` and
`capability_resolved`. Widening a closed taxonomy to hold a different kind of thing is how the taxonomy
stops meaning anything — and five migrations are already unapplied. A sixth for a dashboard number is
not the trade to make now.

**Verify:** `tests/reason/test_a_situation_that_binds_nothing_is_counted.py`

**Outcome.** *"Where is this tenant's routing actually failing?"* has an answer with a name on it.

---

## `U04` · data · Customer Support's `deferrals.yaml`

### What is there

| Domain | `deferrals.yaml` | routed-by-nothing |
|---|---|---|
| Admin | ✅ 30 entries | 0 |
| Customer Support | ⛔ none | **7** |
| Sales | ⛔ none | 0 |

### ⛔ The thing to know before starting

Creating the file **converts 7 warnings into 7 errors** unless all seven are covered in the same
commit — `validate.py:595` errors on an unrouted capability with no deferral **only when the file
exists**. It also refuses a deferral on a capability that is routed (*"deferral must be structural"*)
and a reason that is only a category (*"a category is not a reason"*).

So this unit is **all-or-nothing**, and a partial commit leaves the corpus at `ERROR`.

### What to build

Seven authored reasons — `issue_reproduction`, `resolution_delivery`, `root_cause_analysis`,
`verification_and_closure`, `incident_management`, `major_incident_communication`, `postmortem` — each
naming what is missing and what would open the door.

⛔ **Scope:** this is authored **explanation**, not activation. Support stays on hold. The reason it is
in scope at all is that *"the difference between 'deferred, and here is why' and 'forgotten' is the
entire declared-silence doctrine"*, and Support currently has nowhere to say the first.

⛔ **Sales gets nothing.** It has no unrouted capability to explain. Creating an empty `deferrals.yaml`
there would raise its error bar for zero present benefit and would be a file whose only content is
that it exists.

**Verify:** `.venv/bin/python "Domain Expertise/_tools/validate.py"` — **0 errors**, and the 7 warnings
gone.

**Outcome.** No capability in the corpus is authored, unreachable, and unexplained.

---
---

# LEVEL 2
---

## `U07` · interface · the probe reads the field, never the message

### What is there

`scripts/corpus_route_probe.py:106` tells three defects apart by substring:

```python
if "unknown domains" in text_:      ...
elif "no authored" in text_:        ...
else:                               key = "no_route_type"
```

⛔ **The blunt-grep family, in the tool the corpus's routing coverage is read from.** *"Assert on
structure — never on text that happens to sit near a thing."* And the `else` is a catch-all, so any
rewording silently reclassifies real failures into the one bucket this section exists to measure.

### What to build

Read `exc.reason`. Delete the three string tests. Keep the probe's output key names **unchanged** so
every report and every reader of its CSV keeps working.

⛔ **And a guard so it cannot come back:** a test that walks `scripts/corpus_route_probe.py` and
`reason/domain_shadow.py` and fails on any string comparison against an exception's text. Written as
an **AST walk**, because a grep for `str(exc)` would match the comment explaining why it is forbidden —
which is a mistake this session made four times and is now written into the tests it produced.

**Verify:** `tests/packs/test_a_refusal_is_never_diagnosed_from_its_message.py`

**Outcome.** The three causes are told apart by the type system.

---
---

## What this plan does NOT do

| | Why |
|---|---|
| bind the five unrouted types | **authoring**, and three of five are not obviously Admin's. Deciding who owns each is yours |
| move `unrouted_l2_types` out of Admin's registry | a corpus reorganisation touching every reader — its own unit, its own decision |
| touch `states_absence` on any situation | it answers a different question, and an author has already refused conflating them in writing |
| add a sixth funnel stage | the vocabulary is closed and check-constrained; a refusal reason is not a stage |
| add a migration | five are already unapplied; a dashboard number is not worth the sixth |
| activate Customer Support or Sales | `U04` is an authored explanation, not a switch |
| put a model anywhere in Plane D | Plane D retrieves, filters, binds, scopes, versions and permission-checks. **The thinking is Plane R's** |
| author the 217 *"planned but not authored"* warnings | the corpus declaring its own frontier. Content work, not engineering |

## What you decide, and neither blocks a unit

1. **Who owns each of the five unrouted L2 types.** `U06` makes the loss visible with a name; binding
   them is authoring.
2. **Whether the 6 Admin draft situations get reviewed or stay draft.** `U03` makes the consequence
   correct either way — reviewed, they instruct; draft, they inform.
