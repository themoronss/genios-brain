# Step 9 — ✅ DONE · a weights version is derived, not stored

> **Unit** U5 · **8 tests · 4 mutations, all caught** · ⛔ **F10 RETRACTED · ZERO production code
> changed**
> Worked **newest-row-first**, and the first query refuted the finding's scope.

---

## 1 · ⛔ F10 was wrong in the scope, the reasoning AND the conclusion

> *"Present on **1,973 of 2,681** new outputs. The missing 708 are exactly the
> `legacy.rule` + `legacy.score_gate` run count. Two scoring lanes, one of which **cannot say which
> weights it used** — so it is not replayable. Either the legacy lane records its weights, or it
> declares that it has none."*

### The scope — refuted by the first query, which looked at the newest day first

    day          outputs   with_key   without
    2026-09-30     1,519      1,122       397
    2026-09-29     2,063      1,508       555
    2026-09-28     1,784      1,281       503
    …
    'without' spans   2026-08-17 -> 2026-09-30   (the entire history)
    'with'    spans   2026-09-18 -> 2026-09-30   (the key landed on the 18th)

⛔ **Not 708 of 2,681 — 3,512 of 12,170.** And ~27% on **every single day including the newest**,
so it is not a time boundary and never was. Starting at the newest row is what showed this in one
query; starting at the oldest would have found the 18 Sep feature landing and stopped there.

### The reasoning — `708 == 708` was a coincidence

Replaced with a **join**, not a count match. The split is a **perfect partition**:

    legacy.general.unanswered_email      2,872  ->      0 with the key   ⛔
    legacy.general.commitment_overdue      616  ->      0 with the key   ⛔
    expertise.dependency_stated          2,513  ->  2,513 with the key   ✅
    expertise.analytic_movement          1,963  ->  1,963 with the key   ✅
    expertise.account_admin              1,303  ->  1,303 with the key   ✅

### The conclusion — false for all 12,170

⛔ `CapabilityManifest.ranking_weights_version` is a **property**, and **both shapes have one**:

    @property
    def ranking_weights_version(self) -> str:
        """`ranking_weights@1` for the legacy five, `ranking_weights@2` for G-06's six."""
        return require_ranking_weights(self.ranking_weights)[1]

And the weights are **persisted per decision** in `reasoning_capability_snapshots.manifest`:

    expertise   8,658 runs   6 keys  effort,impact,importance,risk,success,urgency  -> @2
    legacy      3,500 runs   5 keys  effort,impact,risk,success,urgency             -> @1
    expertise      12 runs   5 keys  effort,impact,risk,success,urgency             -> @1
    ──────────────────────────────────────────────────────────────────────────────────────
                12,170 runs — every one resolves, ZERO carry no weights at all

**So "not replayable" is false.** The version is recoverable exactly, for every decision ever made,
from the snapshot that decision pins.

## 2 · ⛔ And the fix F10 proposed would have broken replay

The contract says why, at the exact line I would have changed:

> *"Properties, not fields, and that is the whole reason old capabilities still address to the same
> bytes: a stored `ranking_weights_version` column would have entered `to_semantic_dict`, changed
> `capability_snapshot_id` for every capability in the tree, and **invalidated the
> `reasoning_capability_snapshots` rows replay is verified against** — in exchange for a string the
> key set already determines."*

**Twentieth near-miss, and the third consecutive one whose fix would have caused harm:**

| | Finding | What the fix would have done |
|---|---|---|
| F9 | *"bound `occurred_at` at ingest"* | ⛔ discarded every future calendar event |
| F10 | *"store the weights version"* | ⛔ invalidated every persisted capability snapshot |

## 3 · ⛔ Twelve rows prove the design is right

**Twelve `expertise.*` runs are on the v1 five weights.** The obvious shortcut — `legacy.*` means
`@1`, `expertise.*` means `@2`, which is precisely what the `708 == 708` coincidence pointed at —
would have labelled those twelve **wrong**.

And it is not cosmetic: the two shapes have **different divisors** (100 vs 10,000), so a
mislabelled version also mis-divides a weighted sum **by a factor of 100**.

> ⛔ **A lane name is not a version.** `require_ranking_weights` reads the key set *"never by their
> sum"* and never off an activation table, and twelve production rows need exactly that.

## 4 · What was built — nothing in production

| Artifact | What |
|---|---|
| `tests/reason/test_a_weights_version_is_derived_not_stored.py` | 8 tests |
| production code | ⛔ **zero files changed** |

The tests exist so the next reader who measures 3,512 absent keys finds the **answer** rather than
re-opening the symptom. They pin: both shapes resolve; `importance` is the single discriminator;
the version set is closed at two; the scales differ by 100×; `require_ranking_weights` takes the
**weights and nothing else**, so a capability id can never become its input; the manifest attribute
is a **property** and not a dataclass field; and the decision's field is optional **by design**.

### ⛔ And deliberately NO receipt

12,170 of 12,170 resolve, and the contract validates the shape at construction — so a receipt
asserting *"every snapshot's weights resolve to a version"* would be **green forever and could
never go red.**

> ⛔ **A receipt that cannot fail is not a gate.** U1's and U2's went red on the day they shipped;
> that is the test of whether one is worth adding.

## 5 · The mutations

| | Mutation | Caught by |
|---|---|---|
| M1 | ⛔ the property → a **stored field** (what F10 told me to do) | the property test |
| M2 | ⛔ `require_ranking_weights` gains a `capability_id` parameter (the lane shortcut) | the lane-name test |
| M3 | a third version added to the closed set | the closed-set test |
| M4 | the decision's optional field made required | the optionality test |

⛔ **M1 and M2 are the two shortcuts F10 pointed at**, and each is caught by the test written
against the retraction rather than against the code.

## 6 · Scenario → result

| Scenario | Result |
|---|---|
| a legacy decision, no `ranking_weights_version` in `decision_core` | ✅ **correct** — recoverable from the pinned snapshot as `@1` |
| an `expertise.*` capability on the five weights | ✅ **`@1`**, because the key set decides and not the name |
| somebody stores the version as a column | ⛔ test fails, and the reason is in the failure message |
| somebody adds a third version | ⛔ test fails — the set is closed at two |
| a weights map that does not sum to its scale | `ValueError` at construction |

## 7 · Why reverse-chronological mattered here

Working **newest-first** refuted the scope in the **first** query: every recent day carries both
kinds, so there is no boundary to find. Working oldest-first would have surfaced the 18 September
feature landing — a true but useless fact — and the 708-coincidence would have survived another
step.

> ⛔ **Start at the newest row. A defect that is still happening shows up there; one that stopped
> shows up by its absence there.** Both answers are visible in one query, and only one of them is
> visible from the other end.
