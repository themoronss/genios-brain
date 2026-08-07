# 1 · Feedback Learning

**Status:** Built

Builds ACL-scoped response metrics from the latest explicit canonical card feedback revision while
keeping positive, negative and neutral/timing evidence separate.

| Boundary | Value |
|---|---|
| Input | explicit `FeedbackFact` values grouped by subject and identical source ACL |
| Dashboard authority | `run_play` / `do_it_myself` / `wrong` atomically version one canonical verdict; dashboard/extension snooze and dashboard requeue are non-verdict events |
| Positive | accepted, executed, run_play, do_it_myself |
| Negative | rejected, cancelled, `wrong:not_relevant`, `wrong:wrong_facts` |
| Timing/neutral | `wrong:bad_timing` is canonical but neutral for quality; normalized explicit snooze is timing/neutral; silence is excluded |
| Output | Metrics-target LearningObject with accepted/rejected/timing/neutral counts and exact lineage |
| Primary code | `feedback/units.py::feedback_learning` |
| Integration requirement | product surfaces must continue writing canonical feedback revisions and exact card/execution lineage |

## Atlas-named component map

| Atlas component | Live implementation |
|---|---|
| Feedback Collector | latest `card_feedback_revisions` joined to verdict, card and verified execution; terminal dashboard actions write it atomically |
| Parser | frozen `FeedbackFact`; no raw-prose interpretation or silence inference |
| Categorizer | explicit action sets for positive/negative/neutral |
| Confidence | labelled agreement capped by independent card support; neutral contributes zero support |
| Object Builder | immutable Metrics-target v2 `LearningObject` with ACL audience suffix |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
