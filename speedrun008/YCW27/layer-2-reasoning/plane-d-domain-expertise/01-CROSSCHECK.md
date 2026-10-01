# Plane D · cross-check — what is actually true in `packs/` + `Domain Expertise/`

**Written for:** Rohit and Harsh (CTO). **Date:** 2026-09-30. **No code written yet.**

`packs/` — 34 files, 7,957 lines. `Domain Expertise/` — 1,426 YAML files.
**Section S6, 4 units as the L2 plan specifies them.**

Every number below was produced by running something, in this session, before anything was written.

---

## The verdict first

| Unit as `02-PLAN.md` specifies it | Verdict |
|---|---|
| `M11.C5.U01` the 5 unrouted types become a **runtime counter**, not a YAML comment | ⛔ **a runtime counter already exists** — and it is missing its dimension |
| `M11.C5.U02` `unrouted_l2_types` is **generated**, not hand-kept | ✅ gap, and confirmed: the validator computes it, the YAML is typed |
| `M11.C5.U03` a `draft` situation may not compile a card — **and the refusal names it** | ⛔ **too strong, and the corpus explains why** |
| `M11.C5.U04` a `deferrals.yaml` line for the 7 routed-by-nothing capabilities | ✅ gap, larger than stated: **two** domains have no `deferrals.yaml` |

---

## 0 · The baseline, re-measured

```
$ .venv/bin/python "Domain Expertise/_tools/validate.py"
0 error(s), 290 warning(s) — OK
```

| Domain | Capabilities | Situations | `status: draft` |
|---|---|---|---|
| **Admin** | 59 | 34 | **7** |
| Customer Support | 49 | 20 | **16** |
| Sales | 47 | 15 | 0 |
| **total** | **155** | **69** | **23** |

And every one of the 155:

```
155  status: stable
155  review_status: approved
155  files carrying accepted_content_hash
```

⛔ **So `plan.admitted` is True for every capability in the corpus, always.** Which matters enormously
for `U03` — see §3.

---

## 1 · ⛔ Finding 1 · The runtime counter exists. What it lacks is its dimension

`reason/domain_shadow.py:1237`:

```python
except NoExpertiseRoute:
    counts["no_route"] += 1
```

The plan says *"nothing in the engine reports it at runtime."* **That is wrong** — every situation
that finds no route is counted, per sweep, and has been.

> ⛔ **What is missing is WHICH TYPE.** The number says *"twelve situations found no route."* It does
> not say whether that is one type twelve times or twelve types once, and those are opposite problems
> with opposite fixes.

**This lands squarely on a rule this programme wrote for itself in L1:**
**"a count without its dimension is not a measurement."**

### And the worse half: the three-way diagnosis is a blunt grep

`scripts/corpus_route_probe.py:106` already separates the three real causes — and does it like this:

```python
text_ = str(exc)
if "unknown domains" in text_:
    key = "unknown_domain_hint"
elif "no authored" in text_:
    key = "no_route_predicate"
else:
    key = "no_route_type"
```

⛔ **Three different defects, needing three different teams, told apart by the wording of an exception
message.** The `else` branch is the catch-all, so *any* rewording of either sentence silently
reclassifies real failures into `no_route_type` — the bucket this whole section is about.

`NoExpertiseRoute` is `class NoExpertiseRoute(DomainCompilerError): pass`. It carries nothing.

⛔ **And the right pattern is fourteen lines above it in the same file.** `UnsupportedCoverage`
validates its own reason at construction:

```python
if reason not in {"no_route", "all_stub", "unreviewed", "unsupported_domain"}:
    raise ValueError(f"unknown UnsupportedCoverage reason: {reason!r}")
```

with a docstring explaining exactly why: *"`domain_shadow.py`'s catch-all folded both into the same
`counts["error"]`, so the route-coverage metric could never separate 'broken' from 'not built yet'."*
**The same argument applies one class down and was not applied.**

---

## 2 · ✅ Finding 2 · The list is computed and also typed, in two places

The validator computes it, at `_tools/validate.py:614`:

```python
for t in sorted(l2_types - bound_anywhere):
    WARNINGS.append(f"<routing>: Layer 2 emits {t!r} and no situation in any domain binds it …")
```

And the corpus **also** stores it by hand, at
`Admin Expertise/registry/situation-capability-map.yaml:718`:

```yaml
# Layer 2 emits these and NO situation in ANY domain binds them. Each is a signal
# that compiles to nothing, silently. Global, not this domain's fault.
unrouted_l2_types:
  - commitment_unresolved
  - founder_bottleneck
  - meeting_preparation_gap
  - relationship_going_cold
  - vendor_renewal_decision
```

They agree today. ⛔ **A hand-kept list of what is unrouted will eventually disagree with what is
actually unrouted, and it will disagree in the safe-looking direction** — the list will look shorter
than the truth, because the failure mode is forgetting to add, not forgetting to remove.

⛔ **And one structural oddity the plan did not name:** the block's own comment says *"Global, not this
domain's fault"*, and it lives inside **Admin's** registry. A global fact stored in one domain's folder
is read by whoever opens that folder and missed by everyone else.

---

## 3 · ⛔ Finding 3 · `U03` is too strong, and the corpus argues the case itself

### First, the part the plan got right

`condition-awaiting-review.yaml:33` — written by a previous author, unprompted:

> *"WHAT ACTUALLY HOLDS THIS CARD BACK, and it is NOT the status field. The first draft of this header
> claimed `review_status: unreviewed` kept the situation out of a live compile. **That is FALSE** and
> worth recording rather than quietly deleting: `packs/compiler/authoring.py` reads no `admission`
> block for a situation at all, and `capability_resolver._admission_reason` takes a CAPABILITY.
> **A situation's status gates nothing.**"*

I verified it. `status: draft` on a situation is read by no gate.

### Then the measurement

`states_absence` is the guard that file names, at `render.fallback.states_absence`, read by
`deliver/card_builder.states_absence`. Measured across all 69 situations:

| | |
|---|---|
| `states_absence: true` anywhere in the corpus | **5** |
| of those, `draft` | **1** — `condition-awaiting-review`, exactly as its header says |
| Admin `draft` situations with **nothing** holding the card back | ⛔ **6 of 7** |
| Customer Support `draft` with nothing (out of scope, but recorded) | 16 of 16 |

*(My first pass read `render.states_absence` and reported 23 of 23 ungated. Wrong path — the field is
`render.fallback.states_absence`. Corrected before it reached this page.)*

### ⛔ And then the reason `U03` must not be written as the plan writes it

`organization-gone-quiet.yaml:153` — the same author, refusing the flag **deliberately**:

> *"**NOT `states_absence`.** Its sibling `condition-awaiting-review.yaml` declares that flag because
> nothing in it can establish whether the condition holds. This is the opposite: the silence IS
> observed, on the same `thread.days_waiting` arithmetic the per-person card is built on, and the
> firm's membership is an edge in the graph. What is unknown here is the RELATIONSHIP, and that is
> carried in `missing` where a coverage score can see it — **not by demoting the whole card to a
> review queue.**"*

**They are two different questions:**

| | means | is a property of |
|---|---|---|
| `states_absence` | *the finding itself is a gap in our records* | the **content** |
| `status: draft` | *this copy has not been reviewed* | the **authoring process** |

⛔ **So `U03` must not reuse `states_absence`, and must not refuse the card.** Conflating them would
demote correct, evidence-backed findings into a review queue — precisely what that author refused,
with reasons, in writing.

**The repo already states the right doctrine**, in this plane's own README:

> *"A situation that fails is **flagged, not removed** … delivery downgrades its card to an
> observation. Its detection belongs to L3 and is evidence-backed whatever a reviewer thinks of the
> copy; only its prescriptive words are unreviewed. **The intelligence still ships; it stops
> instructing.**"*

`U03` is therefore: **a draft situation's card may not INSTRUCT**, and the downgrade must name the
situation. Not *"may not compile a card."*

### ⛔ And the mechanism that was supposed to do this can never fire

`expertise_builder.py:99`:

```python
"review_state": "accepted" if plan.admitted else "draft",
```

with `capability_resolver.py:174` documenting the chain:
`admission_gaps → plan.admitted=False → review_state='draft' → _apply_abstention → the card becomes
an OBSERVATION`.

⛔ **The chain is correct and its first link never breaks.** `plan.admitted` is about
**capabilities** — and all 155 are `stable`, `approved`, and hash-accepted. So `review_state` is
always `accepted`, `capability_review_state` on every card is always `accepted`, and the abstention
gate has **never once** been triggered by a draft situation. The machinery is real, tested, green —
and unreachable from the condition `U03` cares about.

---

## 4 · ✅ Finding 4 · `U04` is larger than stated, and adding the file raises the bar

Measured:

| Domain | `deferrals.yaml` | routed-by-nothing warnings |
|---|---|---|
| Admin | ✅ **30 entries** | 0 |
| Customer Support | ⛔ **none** | **7** |
| Sales | ⛔ **none** | **0** |

The plan says *"Admin has one; Customer Support does not."* True, and **Sales does not either** — it
simply has nothing unrouted to explain yet, so no warning fires.

⛔ **And the validator's behaviour is not the same on both sides of that file** —
`_tools/validate.py:595`:

```python
if deferrals_exists:
    for cid in sorted(set(capabilities) - routed_caps - set(deferred)):
        err(...)          # ⛔ an ERROR
else:
    for cid in sorted(set(capabilities) - routed_caps):
        warn(...)         # a warning
```

So creating `Customer Support Expertise/deferrals.yaml` **converts 7 warnings into 7 errors** unless
every one of the seven is covered. That is the file doing its job — but it means the unit is
all-or-nothing, and a partial commit leaves the corpus at `ERROR`.

It also refuses a deferral on a capability that IS routed (*"deferral must be structural"*), and
refuses a deferral whose reason is only a category (*"a category is not a reason"*).

---

## 5 · What is NOT wrong here

| | |
|---|---|
| the corpus | 155 capabilities, **0 errors**, all admitted. It is large, validated, and clean |
| the 217 *"planned but not authored"* warnings | ⛔ **not a defect** — the corpus declaring its own frontier. Declared silence, working |
| compiler order | `capability_resolver → object_resolver → knowledge_retriever`, fixed, with variants resolved early on purpose |
| the admission asymmetry | a capability that fails is dropped; a situation that fails is flagged. Right both times |
| the hash pin | *"the difference between accepting a FILE and accepting its CONTENT"* — an edit after review un-accepts, deliberately |
| `_tools/admit.py` | re-stamps but **refuses to grant review** |
| `UnsupportedCoverage` | separates *"broken"* from *"not built yet"*, and is deliberately not a `DomainCompilerError` subclass so a bare `except` cannot swallow it |
| the per-situation rollback | one bad situation used to take every situation after it — already found and fixed |

---

## 6 · What S6 actually is

| Plan unit | Action |
|---|---|
| `U01` | ⛔ **RETIRE AND SPLIT.** The counter exists; the work is a **structured refusal reason** (contract), **counting by dimension** (logic), and **deleting the blunt grep** (interface). Three artifacts, three verifies |
| `U02` | ✅ build — generate the block |
| `U03` | ⛔ **REWRITE.** A draft situation's card may not **instruct**; it still ships. And the existing chain cannot fire, so the condition must be read where it is actually known |
| `U04` | ✅ build — and all seven at once, or the corpus goes to `ERROR` |

---

## 7 · The pattern, seven sections running

| Where | The document said | The code said |
|---|---|---|
| L1 | `no_model_wired` is broken wiring | one lane is model-free **on purpose** |
| L3 | nothing guards the graph revision | `reason/runner.py:570` is the guard |
| L2 S1 | plan compile should fail on an unproduced source | it did — **six units lost to one absent fact** |
| L2 S3 | the lane belongs in `decision_hash` | it is **derived** — zero information, four broken replays |
| L4 | never read `manager_seat_id` | it is the **standing line** the dated override sits on |
| L5 | replace the scalar publication floor | there is none in `deliver/` |
| L6 | make a timing complaint stop lowering precision | it already does not, in **three** places |
| **Plane D** | **the unrouted types need a runtime counter** | **they have one — it is missing its dimension, and the three-way diagnosis behind it is a blunt grep on an exception message** |

**Eleventh correction.** And the first one that lands on a rule this programme wrote for itself.

---
---

# ⛔ RETRACTIONS — two findings above are WRONG

**Added 2026-09-30, during the build.** The sections stay as written; the corrections are appended
rather than edited in, because a cross-check that quietly rewrites its own findings cannot be audited
and because *how* a wrong conclusion was reached is the part worth keeping.

---

## ⛔ R1 · §2 is wrong. The list is NOT hand-kept

§2 says the corpus *"**also** stores it by hand"* and calls it a hand-kept list.

**It is generated.** `_tools/index.py:205` emits the `unrouted_l2_types` block — **including the
comment I quoted as evidence of hand-keeping** — from `all_l2 - bound_globally`, computed at line 61.
The whole registry file is machine-written by `index.py`.

**Measured before writing the unit:** backed up all three registries, ran `index.py`, diffed.
**Byte-identical.** Nothing hand-kept, nothing drifted.

### How the wrong conclusion was reached

I read `validate.py`, found it computing the same set, saw the block in the YAML, and concluded there
were two maintainers of one fact. I did not check whether the YAML had a generator. **The name
`index.py` never appeared in anything I had read** — the same one-name-absence trap as
`no_model_wired` (L1), the graph-revision guard (L3) and `invention_ok` (L5). Fourth occurrence.

### What survived, and it is a better unit

`index.py` has to be **run**. Nothing failed when the committed file went stale, and `validate.py`
computed the same set three lines away and never compared them. **Two computations of one fact, never
compared** — the argument `deliver/lane_recall` makes about the per-lane tallies. `U02` became that
guard, and `tests/packs/test_the_unrouted_list_cannot_drift.py` drives the real tool over a real edit
in both directions.

---

## ⛔ R2 · §3 is wrong in two ways, and `U03` had already been built

§3 says (a) *"`status: draft` on a situation is read by no gate"* and (b) *"`plan.admitted` is True
for every capability in the corpus, always … the abstention gate has never once been triggered by a
draft situation."*

**Both false.**

`capability_resolver.py:154` — `situation_admission_reason`. It exists, and its docstring describes
the whole unit I was about to build, including the reasoning I had derived independently:

> *"THE HOLE THIS CLOSES … A SITUATION was never asked anything. Its `identity.status` and
> `metadata.review_status` are read by nothing … IT FLAGS, IT DOES NOT REMOVE … the gap lands in
> `admission_gaps` → `plan.admitted=False` → the package's `review_state='draft'` →
> `deliver/pipeline._apply_abstention` downgrades the card to an OBSERVATION. **The intelligence
> still ships; it stops instructing.** Removing the situation would delete the finding to punish its
> prose."*

And `capability_resolver.py:790` — `admitted=not admission_gaps`. A **situation** gap sets
`admitted=False`. My claim that `admitted` concerns capabilities alone was simply wrong.

### Measured, over the whole corpus

```
verdicts: {None: 46, 'identity_status_draft': 23}
draft situations that MAY instruct: NONE
```

All 23 draft situations are flagged, in every domain. The refusal already names the situation —
`f"{situation_id}:{situation_gap}"`. And it is already tested: **11 tests** in
`tests/packs/compiler/test_situation_admission.py`, including *"a draft identity may not"* and *"the
gate reaches the corpus and is not vacuous"*, plus 4 more in `test_stamped_vs_draft_abstention.py`.

> ⛔ **`M11.C5.U03` is WITHDRAWN. Nothing was left to build.**

### How the wrong conclusion was reached, and it is the sharpest lesson here

**I believed a comment in the corpus.** `condition-awaiting-review.yaml:33` says, in capitals,
*"A situation's status gates nothing."* It was **true when it was written** and
`situation_admission_reason` closed the hole afterwards. I quoted it as current evidence and built a
measurement on top of it.

⛔ **A stale comment is more dangerous than no comment**, because it reads as a measurement somebody
already took. The corpus comment is itself now a defect, and correcting it is the one thing left in
`U03`'s territory — a documentation fix, not a unit.

---

## What this does to the verdict table

| Unit | Verdict in §0 | Actual |
|---|---|---|
| `U01` | counter exists, missing its dimension | ✅ **stands** — and a FOURTH cause was found during the build (`domain_not_activated` reported as an authoring gap). Retired and split into `U05`/`U06`/`U07` |
| `U02` | *"the validator computes it, the YAML is typed"* | ⛔ **wrong** — see R1. Rewritten as a staleness guard |
| `U03` | *"too strong, and the corpus explains why"* | ⛔ **wrong** — see R2. **Withdrawn**; already built and tested |
| `U04` | gap, larger than stated | ✅ **stands** |

**Two of four findings in this document were wrong.** Both were caught by continuing to measure while
building rather than by review, and both are recorded here in full rather than corrected in place.


---

## ⛔ 2026-10-01 · *"No code written yet"* at the top of this file was true on the day it was written

**Plane D has since been built: 7 steps — 6 DONE, 1 WITHDRAWN (it was already built), 203 tests.**

This file is a **crosscheck**, so *"no code written yet"* is not an error — it is what a crosscheck
says, and the date beside it is what makes it honest. It is noted here anyway because a reader
scanning for status reads that line as current, and this programme has now paid for that mistake
three separate times: a corpus comment that was true when written sent a whole unit to be specified
before it was withdrawn; seven step files carried `TO BUILD` titles on finished work; and
`02-DECISIONS.md` said *"all four open"* when two were closed.

**Nothing above is retracted.** The findings in this crosscheck are what the build was planned from,
and where one of them turned out to be wrong the retraction is recorded at the point it was found,
not here. For current status read
[`../07-LEDGER-every-step-what-why-how-outcome.md`](../07-LEDGER-every-step-what-why-how-outcome.md)
— or `../../07-LEDGER-...` from a plane folder.
