# L5 STEP 01 · `M13.C2.U03` — the lane reaches the card · **DONE**

## What was there

`0189` added `signals.output_lane` + `lane_reason`. `reason/decision_maker` routes every decision
through `reason/output_lane.route`. `reason/domain_shadow` writes both onto the row. Then:

```
grep -rn "output_lane\|lane_reason" genios_engine/deliver/   ->   nothing
```

⛔ **Built, tested, green, and called by nothing** — the eighth instance this programme has found,
and **the first it created itself**, one step earlier, in a vocabulary added to end a different
instance of exactly that.

## What was built

| File | |
|---|---|
| `deliver/lane_display.py` | NEW · `LANE_COPY`, `LaneOnCard`, `describe()`, `tally_lane()`, `TALLY_KEYS` |
| `deliver/pipeline.py` | selector reads `s.output_lane, s.lane_reason`; six lane counters zeroed; tally at the two persist sites |
| `deliver/card_builder.py` | `build_draft` returns `output_lane`, `lane_reason`, `lane_label` |
| `migrations/0190_card_lane.sql` | `cards.output_lane` + `lane_reason`, two check constraints, a partial index |
| `deliver/store.py` | persists both; a refresh may move a card between lanes |

**31 tests**, `tests/deliver/test_the_lane_reaches_the_card.py`.

## Three real defects the tests found, in the code and not in the tests

**1 · An `OutputLane` member did not resolve.** `str(OutputLane.DECISION)` is `"OutputLane.DECISION"`,
which is in no vocabulary — so **every in-process caller holding the enum would have been labelled
`unrouted`**, while the database path (plain text) kept working and hid it. Fixed with
`getattr(output_lane, "value", output_lane)`.

**2 · The count and the label gave two answers.** `tally_lane` took the raw column and re-described
it with no reason to hand; `describe` treats a lane without its reason as no route at all, so a
routed card was **displayed as `decision` and counted as `unrouted` in the same pass**. Fixed by
taking the already-resolved lane — one resolution per card, by construction.

**3 · The tally was at the wrong place.** Counting on the composed draft would have described a
population including cards nobody received, **and** made the STEP-02 recall check a tautology,
since the tally and its comparison would be incremented by the same line. Moved to the two sites
where a card is actually written.

## The rules this step is built on

⛔ **NULL is an answer.** An unrouted card is labelled and counted, **never** defaulted to
`decision` — that would have the card assert an authority no router granted it.

⛔ **Half a pair is not half a route.** `0189` makes lane+reason atomic. A lane without its reason
is something the writer was not allowed to write, so the reader refuses it rather than displaying
an unexplainable lane and violating `cards_lane_has_a_reason` on the way in.

⛔ **This step does not gate delivery.** `suppress` is displayed and counted, not hidden. Hiding
would change what reaches a founder on the strength of a column that, under the spend limit, has
never once been written in production. Carry first, measure, then decide.

⛔ **`cards_output_lane_*`, not `cards_lane_*`.** `pipeline` already writes `cards_lane`, meaning
which code *path* built the card. Two near-identical prefixes over two unrelated vocabularies is
how somebody reads a path name as a lane name and reports the wrong number with total confidence.

## A correction recorded in `0190`, because `0189` cannot be edited

`0189`'s header says the lane is inside `decision_hash`. **It was, it broke four replay tests, and
it was removed.** `route()` is pure over `outcome`, `confidence_bp` and the conflict flag — all
already hashed — so the lane adds zero information, and a derived value has no business in a
content hash. A migration's checksum is its immutability, so the correction is append-only, in
`0190`, and a test asserts it is there.

## What you do

`0190` has to be applied. It is the **fifth** unapplied migration (`0186`, `0187`, `0188`, `0189`,
`0190`). Until then `cards.output_lane` does not exist and `insert_card` will fail on write.
