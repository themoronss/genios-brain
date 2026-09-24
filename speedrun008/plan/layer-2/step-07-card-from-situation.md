# L2-7 · Cut the card over from the signal to the situation

**Needs Harsh:** ⛔ **migration 0182** · **Model calls:** none

> ## ✅ COMPLETE · PENDING · HARSH (migration 0182) — 2026-09-24 · [findings](findings/step-07-card-from-situation.md)
>
> 15 tests · 13,045 passed · 0 regressions · no model call.
>
> ⛔⛔ **THE LINK THAT WOULD COLLAPSE THE CARDS WAS IN SCOPE AND THROWN AWAY.** `signals` has no
> `situation_id`, and `shadow_compile` reads `row["situation_id"]` **four times within twenty
> lines of the emit** before dropping it. That is `not_carried` — the class L1 step 18 named:
> *"every measured loss is a value that is computed correctly and then not carried."*
>
> And the fan-out is sharper than this file says: signals are emitted **per (pack, rule, node)**,
> so the three Nitesh cards are **three RULES on one situation**.
>
> ⛔ **`subject_node_id` IS NOT A SUBSTITUTE.** `context_situations` is unique on
> `(org_id, correlation_id)`, so one node carries several genuinely different situations — a
> support case and an admin follow-up about the same person. Grouping by node merges things that
> are not the same thing, **which is worse than the fan-out it fixes.**
>
> ⛔ **THE MIGRATION IS NOT "none".** 0182, one nullable column, **no FK** — a situation archives
> on its own lifecycle while its signals stay open.
>
> ⛔ **AND THE FULL SUITE CAUGHT THE WIRE BEING DANGEROUS**: the collapse read could kill the
> delivery pass on a tenant without 0182. *"A receipt that can abort the thing it is a receipt
> for turns an accounting failure into a product failure."* Guarded, and the guard is guarded.

⛔ **This is the step that changes what the founder actually sees.** Everything before it improves
an object nobody reads yet.

---

## 1. ⛔ Premise — the loop runs over signals

`deliver/pipeline.py:269`:

```python
signals = _open_signals_without_cards(graph, org_id, eval_time)
for sig in signals:
    ...                              # one signal → one card
```

`situation` appears **nine** times in that file. `expertise` appears **six**. **The loop runs over
signals.**

So:

```
"Nitesh's inbound messages dropping over 28 days"      ← signal 1 → card 1
"Nitesh Pant's touch frequency declining over 28 days" ← signal 2 → card 2
"Check in with Nitesh Pant on engagement"              ← signal 3 → card 3
```

Three cards because three signals. **They can never merge, because the builder never sees a
situation.** No amount of work between L1 and the card changes this while the loop is where it is.

---

## 2. What the card becomes

```
FROM                                    TO
one signal                              one situation
a measurement                           what is happening + why + what is unknown
no expertise                            the doctrine that read it
no receipts in the UI                   click any claim → the source span
```

The card's job stops being *"surface a signal"* and becomes **"present what L2 concluded"** — which
is what the card was always described as: *"the final presentation of intelligence, not the
intelligence itself."*

---

## 3. Units

### L2-7-U0 · Measure the collapse before changing the loop
On the pilot: how many open signals, how many situations they belong to. **The ratio is the headline
number of this whole plan** — 38 cards becoming N is the claim, and it must be measured rather than
asserted.

```
verify:  scripts/card_collapse_report.py --org <pilot>   # signals → situations ratio
```

### L2-7-U1 · `_open_situations_without_cards`
The sibling of the existing selector. Same shape, different subject. **Build it beside the old one**
— do not edit the old one yet.

### L2-7-U2 · The card builder takes a situation
Reads `observed_facts` for the evidence, `inferred_state` for the headline, `implications` for why
it matters, `unknowns` for what the system does not know.

⛔ **`unknowns` must be visible in the card.** *"⚠ Fulfilment unknown"* is more valuable than a
confident wrong state, and this is where that value either reaches the founder or does not.

### L2-7-U3 · A signal with no situation still surfaces — degraded, and labelled
⛔ **The recall guard.** If every signal must belong to a situation to be seen, then a correlator
gap becomes a silent disappearance — the exact failure L2-4 exists to end. A signal whose situation
never formed still surfaces, **marked as uninterpreted**, and is counted.

```
verify:  pytest tests/deliver/test_an_uninterpreted_signal_still_surfaces.py -q
```

### L2-7-U4 · Flip the loop, behind a per-tenant flag
The old path stays runnable for one release. **Both paths measured side by side on the same sweep**
before the old one is removed.

### L2-7-U5 · The card cites, and the citation resolves
Click a claim → the source span opens. A card whose evidence link 404s is worse than no link,
because it teaches the founder the receipts are decorative.

---

## 4. What this step does NOT do

* **It does not delete the signal path.** It runs beside it, flagged, until the numbers agree.
* **It does not change ranking.** Which card comes first is Decision Intelligence.
* **It does not hide uninterpreted signals.** Fewer cards must come from merging, never from
  dropping.

---

## 5. Completion criteria

| # | criterion | verdict |
|---|---|---|
| 1 | the collapse ratio, before and after | ⚠️ **measured on every sweep** and printed by `scripts/card_collapse_report.py`. The numbers need the pilot **with 0182 applied** — Harsh 27 |
| 2 | a situation-shaped builder beside the signal one | ✅ `_open_situations_without_cards` — **beside**, and a test asserts the old selector is untouched |
| 3 | an uninterpreted signal reaches the founder, labelled and counted | ✅ `CardSource.UNINTERPRETED` — **a label on the CARD**, not only a counter on a dashboard |
| 4 | every card claim resolves to a source span | ⚠️ **already enforced** by `test_a_card_must_quote_what_was_said.py`; this step moves the loop, not the receipts |
| 5 | both paths compared on one sweep | ✅ three keys, **initialised at zero**, on every sweep regardless of the flag |

### 5.1 · ⛔ What U2 asked for does not exist, and this is the same re-aim step 6 made

U2 reads `observed_facts` / `inferred_state` / `implications` / `unknowns`. **None of those are
v2 fields.** L2-2 measured that v2 is already full of interpretation and classified its 28 fields
rather than minting six more, deferring the absent ones to **L2-5, with their writer**.

**What exists to render today:** `missing_facts` — *which is the `unknowns` this step wants
visible, and it is five-state typed* — plus `evidence`, `importance` with its attribution, and
`type`. **The card BODY therefore travels with L2-5's output**, and is recorded on step 5's
ledger rather than half-built here against fields that do not exist.

### 5.2 · What the units became

| planned | built |
|---|---|
| U0 · measure the collapse | ✅ wired into **every sweep**, plus `scripts/card_collapse_report.py` |
| U1 · `_open_situations_without_cards` | ✅ beside the old one, grouping by **situation**, NULL as its own bucket |
| U2 · the card builder takes a situation | ⛔ **the fields it names do not exist** — §5.1. The link it needs is now carried |
| U3 · an uninterpreted signal still surfaces | ✅ **labelled and counted** |
| U4 · flip behind a per-tenant flag | ✅ `cards_from_situations` — a row, not a boolean |
| U5 · the card cites, and it resolves | ⚠️ already enforced; untouched |
| — | **unplanned: migration 0182** — the plan said "none" and the link did not exist |
| — | **unplanned: the measurement may not kill the pass** — caught by the full suite |
