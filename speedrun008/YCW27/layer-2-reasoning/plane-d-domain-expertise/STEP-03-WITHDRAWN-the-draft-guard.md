# Plane D STEP 03 · `M11.C5.U03` · ⛔ **WITHDRAWN** — it was already built

**Nothing was written. This document is the retraction, kept rather than deleted**, for the same
reason `layer-3-context-graph/STEP-02-WITHDRAWN` was kept: *how* a wrong conclusion was reached is the
part worth keeping.

## What the unit said

> *"A `draft` situation may not compile a card — and the refusal names it."*

I rewrote it once already, to *"may not **instruct**"*, on the grounds that refusing the card would
delete an evidence-backed finding to punish unreviewed prose. **That reasoning was right, and it had
been written down before I derived it.**

## ⛔ It exists, end to end, and is tested

`capability_resolver.py:154` — `situation_admission_reason`. Its docstring is the unit:

> *"THE HOLE THIS CLOSES … A SITUATION was never asked anything. Its `identity.status` and
> `metadata.review_status` are read by nothing … **IT FLAGS, IT DOES NOT REMOVE** … the gap lands in
> `admission_gaps` → `plan.admitted=False` → the package's `review_state='draft'` →
> `deliver/pipeline._apply_abstention` downgrades the card to an OBSERVATION. **The intelligence still
> ships; it stops instructing.** Removing the situation would delete the finding to punish its prose."*

The chain, verified link by link:

| link | where |
|---|---|
| `status` / `review_status` / `reviewed_by` read | `capability_resolver.py:208-215` |
| the gap **names the situation** | `admission_gaps.append(f"{situation_id}:{situation_gap}")` |
| a **situation** gap sets `admitted=False` | `capability_resolver.py:790` — `admitted=not admission_gaps` |
| `review_state = 'draft'` | `expertise_builder.py:99` |
| the card is downgraded | `deliver/pipeline._apply_abstention` |

**Measured over the whole corpus:**

```
verdicts: {None: 46, 'identity_status_draft': 23}
draft situations that MAY instruct: NONE
```

**And already tested:** 11 tests in `tests/packs/compiler/test_situation_admission.py` — including
*"a draft identity may not"* and *"the gate reaches the corpus and is not vacuous"* — plus 4 in
`test_stamped_vs_draft_abstention.py`.

## ⛔ How I got it wrong: I believed a comment

`condition-awaiting-review.yaml:33` says, in capitals:

> *"`packs/compiler/authoring.py` reads no `admission` block for a situation at all, and
> `capability_resolver._admission_reason` takes a CAPABILITY. **A situation's status gates nothing.**"*

**It was true when it was written.** `situation_admission_reason` closed the hole afterwards. I quoted
it as current evidence, built a measurement on top of it, and reported that **6 of Admin's 7 draft
situations were shipping prescriptive cards.** They were not. Not one of the 23 can instruct.

I also asserted that `plan.admitted` concerns capabilities alone and is therefore always True. Line
790 says `admitted=not admission_gaps`. **I had read the docstring that said otherwise and did not
follow it to the assignment.**

> ⛔ **A stale comment is more dangerous than no comment, because it reads as a measurement somebody
> already took.**

## What was actually done in this unit's territory

**One corpus edit.** The stale paragraph now carries a dated correction naming
`situation_admission_reason`, line 790, and the measurement — plus the cost, so the next reader knows
a whole cross-check pass was spent on it. Everything else in that header still holds, including why
`states_absence` answers a **different** question from `status`, which its sibling
`organization-gone-quiet.yaml` refuses the flag for, correctly.

Situation files carry no admission hash, so the edit un-accepts nothing. `validate.py`: **0 errors**.
`test_situation_admission.py`: **14 passed**.
