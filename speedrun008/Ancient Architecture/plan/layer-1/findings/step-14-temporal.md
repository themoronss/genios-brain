# Step 14 · The temporal field set and reply pairing — findings

**Run:** 2026-09-24 · premise checked and cost checked BEFORE any code ·
`context/waiting.py` **read first**, as §8 requires
**Status:** 14-U1…U6 **DONE** · migration **0179** · a step-6 leak found and closed

---

## 1. Premise check — every premise confirmed

| Written premise | Verdict |
|---|---|
| QES carries 2 world instants + 1 processing | ✅ `occurred_at` · `expires_at` · `ingested_at` |
| `due_at` / `effective_at` / `resolved_at` / `superseded_at` absent | ✅ confirmed |
| Reply pairing lives in L2 | ✅ `context/waiting.py`, returning **float** days |
| E7's auto-reply rule already exists | ✅ `gate/rules.availability_marker` → `AUTO_REPLY` |
| T7 · purity grep in `capture/validate/` | ✅ **already empty** — and it still is |

Cost check: instants are **lifted from claims the model already produced**; pairing is arithmetic
over timestamps. No prompt, no vocabulary, no model. `vocabulary_fingerprint` = `a3d5496aa0d3`.

---

## 2. §8's instruction, followed literally

> *"`context/waiting.py`'s two rules (E5, E7) preserved exactly — **verified by reading it first**."*

Read first. Its logic, as it actually stands:

```python
pending = None
for direction, at in timeline:
    if direction == "out":
        if pending is None:        # consecutive outbounds: only the FIRST is pending
            pending = at
    elif pending is not None:      # only the FIRST reply after an outbound counts
        gaps.append(...); pending = None
```

And its own words, which are the better statement of the rule:

> *"A thread where they answered once and then sent four more messages describes one reply latency,
> not five. Consecutive outbounds with no reply between them contribute nothing — an unanswered
> message has no latency yet, and **scoring it as zero would make a silent counterparty look
> fast**."*

`pair_replies` reproduces that loop exactly. **Not a second version** (14-U5), and E7 reuses the
gate's `AUTO_REPLY` marker rather than a second regex — two regexes for one rule is how the gate and
this module come to disagree about what an out-of-office is.

### 2.1 · One deliberate difference

`waiting.py` returns float days (`total_seconds() / 86400.0`). Fine inside L2; **not fine crossing a
seam** — V-7, and a float reaches jsonb as a number nobody can trace back to two timestamps. L1
emits **integer seconds**: same pairing, same rules, a unit that survives storage.

---

## 3. What was built

| Unit | What |
|---|---|
| **14-U1** | `due_at` · `effective_at` · `resolved_at` · `superseded_at` on C-12, all optional, all tz-aware |
| **14-U2** | `due_at_of` lifts the deadline from `Commitment.due` — **never re-derived** |
| **14-U3** | `instants_are_ordered` — E2's tz rule and E4's ordering, as a model validator |
| **14-U4** | `pair_replies` — both message ids and an integer Δ |
| **14-U5** | §2 |
| **14-U6** | no clock: every instant is a parameter |

Plus **migration 0179** and the store's INSERT, upsert and parameter map.

### 3.1 · The two exemptions in the ordering rule

`resolved_at` and `superseded_at` may not precede `occurred_at` — a signal resolved before it
happened is not a late row, it is a wrong one.

**`due_at` and `effective_at` are exempt, deliberately.** E3: a deadline in the past at capture time
is legal, because *a stale promise is still a promise* — and refusing it at the contract would
delete exactly the overdue commitments P2 asks about. `effective_at` is exempt for the mirror
reason: a price change can be announced after it took effect.

### 3.2 · `due_at` takes the FAR end of a range

E1 and step 12's argument, again: a promise is overdue when the range the speaker **committed to**
has passed. Taking the near end invents a deadline — the failure `Commitment`'s own contract names,
*"an invented deadline must not be able to produce a false overdue."* The range is not destroyed; it
stays on the claim where ALG-09 put it.

The **soonest** deadline wins when a signal rests on several: a sweep asking *"what is overdue"* must
not miss the earlier of two because the later happened to be stored.

---

## 4. ⭐ Two defects found while wiring

### 4.1 · A `getattr` against my own contract — the exact smell step 5 named

The first publisher edit read:

```python
superseded_at=(stamp.superseded_at if getattr(stamp, "superseded_at", None) else None)
```

`LifecycleStamp` has **three** fields (`state`, `supersedes`, `expires_at`). That line was **dead
code that could never fire** — and step 5's own lesson says why it was invisible: *"`getattr(x,
"field", default)` against your own contract is a smell. It cannot fail, so it cannot tell you the
field is missing."*

Removed, and the absence is now documented as deliberate: **a signal is superseded by a LATER
sweep.** ALG-19 stamps it when the replacement arrives, which is a different write. Filling it at
publish time would mean guessing when a future event will occur.

### 4.2 · A STEP 6 LEAK — the domain confidence never reached storage

`build_signal`'s row builder constructed `domain_hints` **by hand**:

```python
{"domain": ..., "source": ...}      # ← no confidence_bp
```

So step 6's `DomainHint.confidence_bp`, carried correctly by `DomainTagging.as_dicts` and asserted
at that seam, **stopped dead at `qualified_signals`**. Two hand-written copies of one projection,
and only one of them learned the new field.

> That is the exact drift `situation_bso.py` warns about at the **other** end of this pipe — *"two
> hand-written copies of this select is how the two paths end up disagreeing, and only one of them
> has a test."* Step 3 built the test there. This is the same test at this end, and it took a step
> 14 wiring pass to find it.

**Step 6 was reported complete and its headline field was not reaching storage.** Closed, with a
test.

---

## 5. Test result

```
FULL SUITE      12695 passed · 1061 skipped · 152 xfailed · 14 failed
                                                           └── all 14 pre-existing
before step 14: 12669 passed · 14 failed
```

**Zero regressions, +26 tests.** Migration 0179 · no model call · no re-extraction · no prompt
change.

### 5.1 · One assertion of mine was too blunt

`assert "not null" not in sql` flagged the partial index's `where due_at is not null` — which is
correct and desirable, since the rows that matter are the minority carrying a deadline. Tightened to
match a **column declaration**, because a guard nobody can keep green is a guard somebody deletes.

---

## 6. What this step does NOT do

* **It does not compute a latency judgement.** §9 — *"binary responder"* is a pattern over many
  pairs and one pair cannot support it. `instants.__all__` exposes no median, percentile or label,
  and a test asserts the public surface rather than grepping the prose that explains why.
* **It does not remove L2's copy.** `context/waiting.py` still computes its own float-day latencies
  over the graph timeline. L1 now emits the pairs; retiring the L2 derivation is a Layer 2 change.
* **It does not populate `effective_at` or `resolved_at`.** The columns and the validator exist;
  the producers are step 12's state machine (`resolved_at`) and a business-fact effective date
  nothing extracts yet. Recorded rather than half-filled.
* **It does not apply the migration.** Harsh's.
