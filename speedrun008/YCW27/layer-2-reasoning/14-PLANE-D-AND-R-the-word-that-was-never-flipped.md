# PLANE D & PLANE R · the word that was never flipped, and the axis that never fired

> **Date:** 2026-10-01 · read-only against production and the corpus · model off.
> Built in the order asked: push → Plane D → Plane R → align.

---
---

# PART 1 · PLANE D — "23 unreviewed situations" was a count without its dimension

## What was there

Every document in this programme — `STATUS.md`, the ledger, the memory index — said **23 unreviewed
situations**. Measured with the product's own catalog, the corpus is:

    CAPABILITIES   155    stable + approved   155               waiting on nothing
    SITUATIONS      69    stable + approved    46   live
                          draft  + unreviewed  18   genuinely awaiting a reader
                          draft  + APPROVED     5   ⛔ waiting on one word

**All 23 are refused for one reason — `identity_status_draft` — and not one of them for missing
content.** 18 carry nine authored fields (`matches`, `objects`, `render`, `signals_of_progress`,
`signals_of_decay`, `priority_bp`, `typical_duration_days`, `also_serves`, `description`); the other
5 carry the same minus `render`.

## ⛔ The finding: five of the 23 are not unreviewed at all

    admin.sit.asset_in_custody              reviewed_by: harsh   2026-08-29
    admin.sit.employee_lifecycle_event      reviewed_by: harsh   2026-08-29
    admin.sit.obligation_falls_due          reviewed_by: harsh   2026-08-29
    admin.sit.spend_against_a_commitment    reviewed_by: harsh   2026-08-29
    customer_support.sit.issue_under_diagnosis  reviewed_by: harsh  2026-08-29

`capability_resolver.situation_admission_reason` requires **both** `identity.status == "stable"`
**and** `metadata.review_status == "approved"`. These five have the second and not the first. A
named human reviewed them, and **`reviewed_at == last_updated` on all five**, so the approval covers
the bytes that are in the files now. Zero stale.

> **The review is done. Nobody flipped the word.**

⛔ **And it has happened before in this repo, and was found by hand.** Commit `90f8edf0` is titled,
exactly: *"Six situations were finished and nobody flipped the word."* Six then, five now, and
nothing in between was counting.

**So "23 unreviewed" bundled two states with two different movers** — eighteen need a reader, five
need an editor — and reported them as one number. *A count without its dimension is not a
measurement*: this programme's own first rule, broken by this programme's own status page.

## What was built, and what was deliberately NOT

**`review_done_but_not_flipped()` in `Domain Expertise/_tools/validate.py`**, wired at the
situations walk. It warns, names the reviewer and names the mover. 40 warnings, 0 errors.

⛔ **It warns; it does not flip.** `identity.status` is the authoring lifecycle and the author owns
it; `review_status` is the human ceremony. The gate wants both precisely so neither alone can grant
production authority, and a tool that flipped the first on the strength of the second would be the
forgery the ceremony exists to prevent — the corpus's own words: *"an author flipping
`stub: true -> false` in a text editor granted production authority."*

⛔ **And it reports the stale case separately, because it needs the opposite action.** If a file was
edited after its approval, the approval does not cover what is in it now: the answer is another
review, never a flip. None of the five is in that state — but the check says which, so the two can
never be confused.

**A pure function**, for the reason its sibling `registry_staleness` states: *a guard that has to
modify the corpus in order to prove it works cannot be trusted in CI.*

**`tests/packs/test_a_review_that_was_never_flipped.py` — 9 tests.** Including a vacuous-pass guard
that immediately earned its place: my first corpus loader globbed `*/situations/*.yaml`, found
**nothing**, and the five-known-ones test passed empty until that guard caught it. Replaced with the
product's own `ExpertBrainCatalog` — *a test that re-derives the corpus layout is a second
implementation that can disagree with the first.*

### ⛔ ALARM D-A2 · five one-word edits, and they are not mine
`identity.status: draft -> stable` on five files. **Mover: the author, or Harsh**, who already
reviewed them. Doing it would take five Admin/Support situations from *cannot instruct* to *live*,
and that is a production authority change on an inference about what `draft` was meant to signal.
**Not done.** The check now reports it on every validator run, so it cannot go quiet again.

---
---

# PART 2 · PLANE R — ALARM A6 retired, and a reader for the axis that never fired

## ⛔ A6 was queued work that would have been a defect

`STATUS.md` carried **ALARM A6** as *"mine, on request"*, from a comment in `priority.py`:

> *"The read is `or ""`, so a manifest that FORGETS `source_reasoner` yields an empty source string
> rather than a refusal — the unit then reads a prior metric from `""`, gets the sentinel, and is
> silent. Safe today because every manifest sets it. Changing `or ""` to a refusal changes behaviour
> and is its own unit."*

Measured, **all three of its claims are wrong:**

| | Claim | Measured |
|---|---|---|
| 1 | *"every manifest sets it"* | ⛔ `sales.deal_cooling` schedules `core.confidence` with the key **ABSENT**. `core.priority` sets `core.temporal`. Both branches ship |
| 2 | *"reads a prior metric from `""`"* | ⛔ it does not. `priority._declared_source` and `confidence._bridged_confidence_bp` are both `if not source: return None`, **before** any lookup |
| 3 | *"change `or ""` to a refusal"* | ⛔ **that fix would have been the defect.** Falsy is the BRANCH SELECTOR — `_source_reasoner`'s docstring: *"Falsy config means 'no source declared' and routes to the derived path"*; `confidence.py:27`: *"Two branches, one output… The bridge is not a fallback; it is a declaration by the capability author"* |

**A6 is retired, retracted in place in `priority.py` with the measurement**, and
`tests/reason/test_an_absent_source_is_a_branch_not_a_fault.py` (6 tests) pins the behaviour so the
retired claim cannot be acted on later. One of them asserts the retraction text is still there,
because *a retired claim deleted silently is a claim that comes back*.

What is genuinely true is narrower and costs nothing today: a key deliberately omitted and a key
forgotten are indistinguishable — and **neither unit requires a source**, so a forgotten key always
lands on a designed path. It would begin to cost something the day a unit is written that cannot
work without one, and **that unit should declare the requirement; the shared accessor should not
refuse on its behalf.**

## The reader: `scripts/l2_tradeoff_axes.py`

`unit_health`'s header had already decided the shape — *"`axis_count` is ALREADY published on every
run and read by nobody, so the fix is a reader, not a field"* — because a field present on ~100% of
runs breaks replay for every stored trace (`contracts/reasoning.py:845`).

Measured over 1,973 completed `core.tradeoff` runs:

    axis_count = 0       16 runs    margin_bp 0 · tension_bp 0 · contested_count 0 · no findings
    axis_count = 1      929 runs   47%
    axis_count = 2    1,028 runs   52%
    axis_count = 3        0 runs   ⛔ a THREE-axis comparator that has never compared three

    speed_vs_certainty  1,897 firings   96%
    risk_vs_reward      1,088 firings   55%
    cost_vs_benefit         0 firings   ⛔ has NEVER fired

    cost_vs_benefit needs  core.impact.impact_bp   ⛔ absent — declared, mover Harsh (deal.status)
                           core.cost.effort_bp     ✅ healthy, 1,973 of 1,973 runs

**`axes_unavailable` has 0 occurrences in 1,973 rows** — it was added in S5.U02, every stored row
predates it, and it will first appear on the next run. **A field awaiting exercise, not one that
failed**, and the probe says which rather than leaving a reader to guess.

**The 16 silent runs do not make the silence receipt wrong.** 16 of 1,973 is 0.8% and
`SILENT_THRESHOLD_PCT` is 90 — *"one silent completion out of a thousand is noise; ninety per cent
is a unit that does not work."* A share, not a count. So the probe reports them; no receipt fails.

## ⛔ The probe's own two bugs, recorded because both looked exactly like findings

**It read `AXIS_SOURCES[*][0]` as the axis name.** It is the SOURCE KEY (`benefit_source`), so the
probe announced *"a 6-axis comparator that has never compared 6"* and *"every axis has NEVER
fired"*. Both false. Axis names now come from `tradeoff_unit.AXES`, exported for the purpose rather
than retyped.

**It inferred absence from the declaration list.** It reported **`core.cost` as an undeclared cause**
of `cost_vs_benefit`. `core.cost` publishes `effort_bp` on **1,973 of 1,973** runs — it is healthy,
and it is absent from the declarations *because* it is healthy.

> **A declaration list answers "is this absence declared". It never answers "is there an absence."**

Third artefact of this shape in one session. Closed by measuring each side's metric **first** and
only then consulting the declarations — and the rule is now `classify_lost_axes()`, a pure function
with 8 tests, each one a wrong verdict the probe actually produced.
