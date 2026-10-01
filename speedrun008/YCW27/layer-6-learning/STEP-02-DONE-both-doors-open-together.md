# L6 STEP 02 · `M14.C1.U02` — eleven reasons, and all five readers · **DONE**

## The five readers of the three

| Where | What it does |
|---|---|
| `deliver/card_builder.py:849` | what the card **offers** |
| `deliver/actions.py:31` `WRONG_REASONS` | what the API **accepts** |
| `feedback/calibrate.py` `TAXONOMY` | what calibration **maps** |
| `feedback/units.py:124` | what the counter **branches on** |
| `context/correlation_history.py:148` | what a retry decision **reads** |

⛔ **All five moved together.** Widening what the card offers without widening what the API accepts
gives the founder a button the server refuses with `allowed_reasons`. Widening both without
`TAXONOMY` lets a reason reach calibration that nothing maps. That is
`FEATURE_CARDS_FROM_SITUATIONS` again — *"the reader was looking for a word the writer rejected"* —
which cost this codebase a lane no tenant could switch on.

## ⛔ The hole this step would have fallen into, in both directions

**Over-counting.** `feedback/units.py` read:

```python
elif reason == "bad_timing":
    c["bad_timing"] += 1
else:
    c["wrong"] += 1
```

One literal. Five of the eleven reasons say the card was **right** and something else was not —
`bad_timing`, `stale_data`, `wrong_playbook`, `wrong_person`, `badly_written`. **Four of those five
would have landed in the `else` and debited the rule's accuracy:** the exact defect this milestone
exists to end, created for four new reasons by the step meant to fix it for one. Now
`not _grades_accuracy(reason)`, which asks the map.

**Under-counting, and the harder one to notice.** `calibrate._PRECISION_SQL` held
`in ('not_relevant','wrong_facts')`. Six reasons now count against a rule. Four real quality
failures — `misread_source`, `wrong_subject`, `bad_link`, `bad_reasoning` — could have been recorded
by a founder and **counted by nothing**. Nothing breaks and precision merely looks better than it
is. The list is now generated from the map, sorted so the emitted SQL is byte-stable.

> ⛔ **Totality guards both directions** — here, literally: a reason that grades when it should not,
> and a reason that does not grade when it should.

## Two smaller corrections made on the way

**`label` was about to record a falsehood.** The first derivation mapped every `none` reason to
`"timing"`, which would have filed `wrong_person` and `wrong_playbook` as *scheduling* complaints.
The old four-word label vocabulary was designed for three reasons. A `fit` label was added.

**And `label` has no code reader.** Grepped: `TAXONOMY` is read by
`attribution.timing_never_grades_accuracy` (which reads `precision`) and named in two comments. That
is near-miss territory for *"built and called by nothing"* — it predates this work and is
documentation-only, so it is **recorded rather than removed**, because deleting a field two comments
describe is a bigger change than labelling it correctly.

## `BUILDER_VERSION` bumped: `v5-evidence-backed-copy` → `v6-lane-and-eleven-reasons`

Its own rule: *"BUMP THIS whenever what a card can SAY changes."* A card now carries a lane (L5
STEP 01) and eleven reasons. Without the bump the improvement lands only on signals nobody has seen
yet, and `CardStore.claim_build` cannot reclaim a stale-but-untouched card to rewrite it.

## ⛔ A product concern, flagged and then built anyway

**Eleven radio buttons under *"Wrong"* is a worse experience than three.** A founder asked to
classify *our* failure will pick the first plausible option, and precise-looking data gathered that
way is worse than coarse data gathered honestly.

The eleven are right as a **machine** vocabulary. Whether all eleven should be *shown* is your call,
not mine. So: `_WRONG_REASON_GROUPS` gives a surface four headings a person can actually pick —
*"the facts are wrong"*, *"the conclusion is wrong"*, *"this is not how we work"*, *"right card,
wrong delivery"* — and narrowing what is **displayed** stays a one-line change on a surface rather
than a change to the vocabulary underneath. A test asserts every reason appears in exactly one
group, so a reason in no group (nobody can choose it) and a reason in two (two buttons, one answer)
both fail.
