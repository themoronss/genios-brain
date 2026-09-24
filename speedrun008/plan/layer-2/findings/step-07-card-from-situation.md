# L2-7 · Cut the card over to the situation — findings

**Run:** 2026-09-24 · premise checked BEFORE any code · **migration 0182** · **no model call**
**Against:** `speedrun008` @ `aa39e7c5`
**Result:** 15 tests, **13,045 passed · 14 failed (all pre-existing) · 0 regressions**

---

## 1. ⛔ The premise is right, and the diagnosis is sharper than the plan's

The plan says the loop runs over signals. It does. But **the fan-out is at the RULE, not the
signal**: `domain_shadow._emit_capability_signal` writes *"one OPEN compiled signal per
(pack, rule, node)"*. So one situation compiles a package, the package fires several rules, and
each rule becomes a card:

```
"Nitesh's inbound messages dropping over 28 days"        rule 1 → signal 1 → card 1
"Nitesh Pant's touch frequency declining over 28 days"   rule 2 → signal 2 → card 2
"Check in with Nitesh Pant on engagement"                rule 3 → signal 3 → card 3
```

---

## 2. ⛔⛔ THE FINDING — the link that would collapse them was in scope and thrown away

`signals` has **no `situation_id` column**. And `shadow_compile` reads `row["situation_id"]`
**four times within twenty lines of the emit** — at 884, 921, 936 and 967 — then calls
`_persist_live` → `_emit_capability_signal` without it.

**That is `not_carried`**, the class of defect L1 step 18 named:

> *"Every measured loss is a value that is computed correctly and then not carried."*

The value existed, was used four times, and was dropped at the one seam where a card needs it.

### 2.1 · And `subject_node_id` is not a substitute

`context_situations` is unique on `(org_id, correlation_id)`, so **one node carries several
genuinely different situations** — a support case and an admin follow-up about the same person.
Grouping cards by node would merge things that are not the same thing, **which is worse than the
fan-out it fixes.** A test refuses the node join by name.

### 2.2 · So the step carries it — migration 0182

| | |
|---|---|
| column | `signals.situation_id text` — **nullable, no default** |
| index | partial: `(org_id, situation_id) where status='open' and situation_id is not null` |
| foreign key | **none, deliberately** — a situation archives on its own lifecycle while its signals stay open, and an FK would either block the archive or cascade a card away from a founder reading it |
| writers | `_emit_capability_signal`, the only one, reached through `_persist_live` |

---

## 3. ⛔ The recall guard is the unit that decides whether fewer cards is a merge or a loss

The moment a card **requires** a situation, a correlator gap becomes a silent disappearance —
the exact failure L2-4 exists to end.

**`situation_id IS NULL` is an ANSWER, not a gap.** A signal written before 0182, and a signal
whose situation never formed, both read NULL — and both still reach the founder:

```python
CardSource.UNINTERPRETED.label
  "uninterpreted — this is a measurement, not a conclusion. No situation formed around it,
   so nothing has read it against your domain's doctrine"
```

⛔ **A number on a dashboard is not a label on a card.** The founder has to be able to tell an
interpretation from a raw measurement, or the two become one undifferentiated feed and the
interpretation is worth nothing. So `CardSource` carries both: a `label` for the card and a tally
key for the pass.

And the selector **groups NULL as its own bucket** rather than excluding it, so the uninterpreted
arrive as one countable row instead of rows that quietly fail a join.

---

## 4. ⛔ The wire, which is what this step was asked for

| | |
|---|---|
| `_open_situations_without_cards` | built **beside** the old selector; a test asserts the old one is untouched |
| the collapse measurement | runs on **every sweep**, flag on or off — *"a comparison that only exists after the cutover cannot inform the cutover"* |
| `cards_from_signal` · `cards_from_situation` · `cards_uninterpreted` | **initialised at zero**, so a zero is readable. Same declared-silence rule as `BY REASON` and `BY LAW` |
| the flip | `cards_from_situations(activated=…)` — **per tenant, off until a row says otherwise** |

`live_lane` recorded what the alternative costs: *"`forced` is one boolean for every tenant at
once… it only ever turns lanes ON: switching it off does not take an activated tenant off the live
lane."* **The way back is deleting a row.**

---

## 5. ⛔ The full suite caught the wire being dangerous, and the rule was already written down

The first draft called the selector unguarded.
`test_worker_without_card_build_lease_never_invokes_renderer` went red:

```
AttributeError: 'object' object has no attribute 'engine'
```

A fake graph in a delivery test — **and the same thing would happen on a real tenant before 0182
is applied**, because the column the selector reads would not exist.

`BundleStore.record_call` states the rule:

> *"A receipt that can abort the thing it is a receipt for turns an accounting failure into a
> product failure. A lost row mis-states a dashboard; a raised exception here costs the
> narration."*

**A measurement may never kill the pass it measures.** The collapse read is wrapped, and a pass
that could not measure itself records `collapse_unmeasured` — because a pass that failed to
measure must not look identical to one that measured zero. A test now guards the guard.

---

## 6. ⛔ A consistency defect from L2-4, found and removed

L2-4 corrected the *"no corpus was authored for them"* sentence in `DARK_DOMAINS` and in
`CANDIDATE_ROUTES` — and left **a third copy** stranded above `CandidateRoute` as an orphaned
`#:` block, still saying the wrong thing.

**Deleted rather than edited.** Two paragraphs stating one fact is how the fact goes stale in the
one nobody reads — the drift this repository has caught five times, and which L2-4's own finding
was about.

---

## 7. Cost check

| | |
|---|---|
| model calls | **none** |
| migration | **0182** — one nullable column, one partial index |
| extra reads per sweep | **one grouped SELECT**, read-only, guarded |
| existing rows | carry NULL, which reads as *uninterpreted* — true, and surfaced rather than dropped |
| runtime behaviour | **unchanged until a tenant is activated.** The loop is the old one; the measurement is new |

---

## 8. Completion criteria

| # | criterion | verdict |
|---|---|---|
| 1 | the collapse ratio measured before and after | ⚠️ **the measurement is wired into every sweep** and `scripts/card_collapse_report.py` prints it. The **numbers need the pilot with 0182 applied** — Harsh 27 |
| 2 | a situation-shaped card builder beside the signal one | ✅ `_open_situations_without_cards`, built beside; the old selector is untouched and a test says so |
| 3 | an uninterpreted signal still reaches the founder, labelled and counted | ✅ `CardSource.UNINTERPRETED` — **a label on the card**, not only a counter |
| 4 | every card claim resolves to a source span | ⚠️ **already enforced** — `test_a_card_must_quote_what_was_said.py`, and `signals.citations` is read by the builder. **Unchanged by this step**, which moves the loop and not the receipts |
| 5 | both paths run on one sweep and are compared | ✅ **three keys, initialised at zero, on every sweep regardless of the flag** |

**Four closed, one measured-and-wired with its pilot numbers open.**

---

## 9. ⛔ What this step does NOT do, and one of them matters

* **It does not build the situation-shaped card body.** U2 says it reads `observed_facts` /
  `inferred_state` / `implications` / `unknowns` — **and those fields do not exist**, for the same
  reason step 6 had to re-aim: L2-2 classified v2's existing fields rather than minting six, and
  deferred the absent ones to L2-5 with their writer. **What exists today to render is
  `missing_facts` (the `unknowns` the step wants visible, five-state typed), `evidence`,
  `importance` with its attribution, and `type`.** The body belongs with L2-5's output and is
  recorded on step 5's ledger.
* **It does not delete the signal path.** It runs beside it, measured, until the numbers agree.
* **It does not change ranking.** Which card comes first is Decision Intelligence.
* **It does not hide an uninterpreted signal.** §3.
