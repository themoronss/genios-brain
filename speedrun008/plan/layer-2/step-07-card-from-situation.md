# L2-7 · Cut the card over from the signal to the situation

**Needs Harsh:** no · **Migration:** none · **Model calls:** none

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

1. The collapse ratio measured **before and after**, both in findings.
2. A situation-shaped card builder exists beside the signal one.
3. An uninterpreted signal still reaches the founder, labelled and counted.
4. Every card claim resolves to a source span that opens.
5. Both paths run on one sweep and are compared before the old one is retired.
