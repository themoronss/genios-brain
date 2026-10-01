# Layer 3 — how many steps, cross-checked

**2026-09-25** · a premise check run on this plan's own step list

---

## 1. The count

| | |
|---|---|
| draft in `13-THE-COMPLETE-STEPS.md` | **20** |
| ＋ `L3-02b` from the benchmark (`14`) | 21 |
| ＋ `L3-0A` the window (`15`) | 22 |
| ⛔ **＋ 4 found by this cross-check** | **26** |

**The plan was incomplete. Four genuine Layer 3 steps had no step.**

---

## 2. ⛔ The four that were missing

### 2.1 · Situation identity is correlation-based, not obligation-based

```sql
-- migrations/0038_l2_situations.sql:51
unique (org_id, correlation_id)
```

The specs are explicit:

```
situation_key = tenant + business_object + obligation_or_condition + period + episode
```

| measured | |
|---|---|
| `situation_key` | **1 file** |
| `obligation_id` / `obligation_key` | 6 files |
| `episode` | 5 files |

⛔ **Two audits with the same vendor, the same people and the same document titles but different
periods cannot be told apart by `correlation_id`** — and that is BS-07, BS-17, CC-26, CC-39, INT-08
and LCX-27 all at once.

> LCX-27: *"Next month's recurring obligation resembles last month's resolved one → new risk is
> lost as a duplicate, or the old episode gets overwritten."*

**And L2-7 already found the near side of this:** `context_situations` unique on
`(org_id, correlation_id)` means *"one node carries several genuinely different situations."*
That was recorded as a reason **not** to group cards by node. **The root cause was never given a
step.**

### 2.2 · Parent/child situation hierarchy does not exist

```
parent_situation  ⛔ absent      child_situation  ⛔ absent      parent_id  ⛔ absent
```

> BS-08: *"One audit contains several document requirements, and two require independently
> accountable corrective work. Flattening hides accountable work, while unrelated child publication
> floods the founder."*

⛔ **This is the "one blocker produces ten cards" failure (FX-39, APP-02, DP-05)** — and it is the
same shape as L2-7's three-Nitesh-cards defect, **one level up**: L2-7 merged cards under one
situation; nothing merges situations under one parent.

### 2.3 · Held candidates have no recovery policy

```
hold_reason  ⛔ absent      missing_predicate trigger  ⛔ absent
```

> BS-16 / LCX-28: *"A Held candidate receives better coverage but no new business message — the
> system never revisits a now-provable situation."*

⛔ **This is the exact failure mode Phase A creates.** Raise the backfill window and coverage
improves for thousands of held facts — **and nothing re-examines them.** A step that widens history
without a recovery trigger widens a blind spot.

### 2.4 · Change records are untyped

```sql
graph_change_outbox.payload jsonb not null    -- no schema
changed_fields ⛔ absent    changed_predicates ⛔ absent
```

> LCW-05: *"Dependency graph lacks field/predicate provenance. Either stale derivatives survive or
> everything recomputes."*
> LCX-24: *"A display-name change must not cancel a valid approval; an authority change must."*

The outbox exists and carries an **untyped blob**, so a consumer cannot tell a spelling correction
from an authority expiry. ⛔ **Without this, L3-06's timer and L3-17's read either re-run
everything or trust stale state.**

---

## 3. ✅ Three suspicions that were WRONG — already built correctly

Recorded because a plan that adds work it does not need is as wrong as one that misses work.

| suspected gap | measured | verdict |
|---|---|---|
| **Visibility is a scalar ranking** | `contracts/visibility.narrowest()` — *"its principals are the **INTERSECTION** of the constrained ones… `excluded_subjects` merges the OTHER way — by **UNION**"* | ✅ **exactly what A11 / CD-09 / CQ-HCS-06 demand. No step needed.** |
| **No revision barriers on writes** | `expected_version` / conditional writes in **13 files** | ✅ mechanism exists (LCX-29) |
| **No versioned situation templates** | `template_version` 4 files · `pattern_version` 6 files | ✅ BW-02's authoring path exists |

⛔ **`narrowest()` is the sharpest of the three.** The specs warn at length that *"privacy is not a
scalar visibility ranking"* and that *"two incomparable audience restrictions may yield no eligible
viewer."* **The code already implements the harder, correct version, and it was written before the
spec asked for it.**

---

## 4. The 26 steps, in eight waves

| wave | | steps |
|---|---|---|
| **A · SEE** | the window ＋ progressive sync | **1** |
| **0 · Vocabulary** | layer numbering · name the Decision Object | **2** |
| **1 · Honesty** | coverage record · ⛔ carry it across the seam · `scoped_absence` · knowledge time · evidence lineage | **5** |
| **2 · Time & change** | the timer · Freshness Manager · ⛔ **typed change records** | **3** |
| **3 · Correlation** | ⛔ Cross Tool · typed relations · decision record | **3** |
| **4 · Situation** ⛔ NEW | ⛔ **identity/episode** · ⛔ **parent/child** · ⛔ **held recovery** | **3** |
| **5 · Quality** | three-valued predicates · the four graph views | **2** |
| **6 · Memory** | `intel_nodes`＋`intel_edges` · lift `about` · write-back · revision | **4** |
| **7 · Read & ship** | ⛔ the read · the surface · turn it on | **3** |
| | | **26** |

### Why Wave 4 sits exactly there

⛔ **It is a hard dependency of Wave 6.** An `intel_nodes` row of kind `situation` needs a stable
id to point at — and today that id is a `correlation_id`, which changes when the correlation
regroups. **A graph of decisions built on an unstable situation key records the wrong history.**

And it depends on Wave 3: obligation identity comes from **typed relations** (`fulfills`,
`requires`), which is L3-09.

---

## 5. Is it complete now?

**Complete against what was supplied — yes, and this is what that means:**

| source | covered |
|---|---|
| Context Lifecycle spec — 40 LCX ＋ 16 HCS ＋ 12 LCW | ✅ every case maps to a step, or to L1/L5/L6 |
| Eight-Group HCC — 160 cases | ✅ groups 2, 3, 4, 5 are Layer 3 and all map |
| Business Situation spec — 24 BSX ＋ 16 BW | ✅ incl. the four found above |
| Cross-Correlation spec — 96 ＋ 48 ＋ 12 E2E | ✅ |
| The benchmark — 5 prompts, 6 checks | ✅ each has a step and a pass/fail test |

**⛔ Four honest limits on that word:**

1. **Some cases are not Layer 3 and are marked so** — adversarial source text is L1, card-cache
   invalidation is L5, learning governance is L6. **Covered ≠ built here.**
2. **Goal and metric versioning (LCX-39, BW-08)** lands in **Domain Expertise**, which under the new
   numbering is **L2**. It is a real gap; it is not an L3 step.
3. **The specs say so themselves:** *"A finite catalogue cannot guarantee zero future errors."*
   **26 steps is complete against four documents and one benchmark, not against reality.**
4. ⛔ **Every step so far has corrected its own premise.** Nine of nine in Layer 2 did.
   **Expect this list to move again — the first step that does not find something is the one to
   distrust.**
