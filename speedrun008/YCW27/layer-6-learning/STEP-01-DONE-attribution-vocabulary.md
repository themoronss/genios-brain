# L6 STEP 01 · `M14.C1.U01` — the attribution vocabulary · **DONE**

## What was there

Three reasons. `not_relevant`, `wrong_facts`, `bad_timing`.

⛔ `wrong_facts` alone covered **a mis-read email** (capture), **a fact linked to the wrong company**
(context), and **a stale value nobody refreshed** (capture again) — three different teams, one word,
and no way to debit any of them. `grep -rn "layer" genios_engine/feedback/` returned seven hits,
every one prose in a comment about the import topology.

## What was built

`genios_engine/contracts/learning_attribution.py` — `WrongReason` (11, closed), `PrecisionRole`,
`Attribution`, `ATTRIBUTION`, `DEBITABLE_LAYERS`, `LAYER_ORDER`, `attribute()`,
`reasons_for_layer()`.

| reason | layer | precision |
|---|---|---|
| `misread_source` | capture | denominator |
| `stale_data` | capture | **none** |
| `wrong_subject` | context | denominator |
| `bad_link` | context | denominator |
| `wrong_playbook` | packs | none |
| `bad_reasoning` | reason | denominator |
| `not_relevant` | reason | denominator |
| `wrong_facts` | reason | denominator |
| `wrong_person` | executive | none |
| `bad_timing` | deliver | none |
| `badly_written` | deliver | none |

## ⛔ The topology gate caught my own violation

The first version imported `genios_engine.LAYERS` so the layer names could be checked at import
time. `test_layer_topology.py::test_contracts_import_nothing_above_platform` **failed the build**:
*"contracts/ is the boundary vocabulary — it may depend on platform/stdlib only."*

**The gate was right.** `contracts/` is what every layer imports, so a dependency added there is a
dependency added everywhere — and `LAYERS.py` exists to be read by the topology *test*, not by
shipped code (nothing else in `genios_engine/` imports it). The requirement stands and moved: the
module holds its own `DEBITABLE_LAYERS` and `LAYER_ORDER`, and two tests assert both against
`LAYERS.py`. A test is a weaker place than an import guard, and it is the strongest place available
without making the boundary vocabulary depend on the topology it describes.

**Same lesson as `capture → context` in L1 Step 10.**

## Three calls worth defending

⛔ **`stale_data` is `none`, not `denominator`** — the sharpest call in the map. The rule concluded
correctly from what it was given. Debiting its precision for the *age of the input* is the same
error `_PRECISION_SQL` already refuses on the abstention axis: *"counting that as a precision
failure made answering the system's own question evidence the system was wrong."*

⛔ **`wrong_facts` lands on `reason`, and that is an admission, not a finding.** A founder choosing
it has told us a fact is wrong and nothing about where it was lost. Attributing it to `capture` on a
guess would produce a confident number pointing at the wrong team — worse than an honest one
pointing at the layer that *published* the claim. The narrower reasons exist so this one gets picked
less often, and its `fix` string says so out loud.

⛔ **`feedback` is not debitable.** L6 reads these debits; a reason attributing failure to the
learner would have the learner grade itself. If learning is wrong, that shows up as every other
layer's debits being wrong at once — a different investigation, not a button on a card.

## Not `contracts/learning.py`, which the unit names as its artifact

That file holds `LearningObject` v2 — content-addressed and round-trip verified. Adding a member to
an enum it validates against would **change identities already minted**. The departure is deliberate
and the reason is the hash.
