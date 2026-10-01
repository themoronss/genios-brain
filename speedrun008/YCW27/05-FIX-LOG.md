# Fix log

One entry per fix. What was wrong, what changed, how it was proved, and what it did **not** change.

---

## 1 · `temperature` sent to models that refuse it — 30 Sep 2026

**Status:** done · tests green · not deployed

### What was wrong

`context/llm/client.py` hardcoded `temperature=0` on every request. Newer models refuse it:

```
Error code: 400 — "`temperature` is deprecated for this model."
```

Measured in `llm_costs`:

| Purpose | Model | Succeeded | Failed |
|---|---|---|---|
| `l4_bundle` | `claude-sonnet-5` | **0** | **600** |

13 → 25 September. **The narrator has never once produced a bundle**, and nothing surfaced it
because the lane fails open — a missing narrative looks exactly like a narrative nobody asked for.

### ⛔ The part worth remembering

**The knowledge existed and the module that sends the field did not have it.**
`reason/llm_decision_maker.py` already listed these models — and worked around the problem by
building *its own thin client*. That fixed decisions and left every other lane on the shared client
still sending `temperature` to the same models.

> A second copy of a closed set is a set that drifts. The module that sends the field must own
> which models accept it.

### What changed

| File | Change |
|---|---|
| `context/llm/client.py` | `NO_SAMPLING_PREFIXES` + `accepts_sampling(model)`; `call()` omits the field for those models |
| `reason/llm_decision_maker.py` | its local copy **deleted** — it now imports the one list (`reason` → `context` is a legal downward import) |
| `tests/context/test_sampling_is_omitted_where_it_is_refused.py` | new · 14 tests |

### What did NOT change

⛔ **`temperature=0` is still sent to every model that accepts it.** It is the determinism this
engine's replayability rests on. The field is *omitted where refused*, never *removed*. One test
exists purely to stop a future reader "simplifying" this into "stop sending temperature".

### How it was proved

```
tests/context/test_sampling_is_omitted_where_it_is_refused.py   14 passed
tests/test_layer_topology.py + test_every_llm_call_site_is_metered.py   12 passed
every test touching the client (35 files)                     1,163 passed · 0 failed
```

The last test in the new file pins that both modules reference the **same object**, so re-adding a
local copy fails the build. That is the guard the original defect lacked for twelve days.

### Caught on the way

`tests/scenarios/test_invariants.py` read `speedrun008/plan/layer-1/FAILURE-LOG.md` by a hardcoded
relative path and broke when that folder moved under `Ancient Architecture/`. Now resolved from the
test file's own location against both known homes, and a miss names both paths instead of
reporting "file not found". **A scoreboard test felled by a directory rename is a worse failure
than the drift it exists to catch.**

### Still true after this fix

⛔ `l4_bundle` will still produce nothing, because **the account's API spend limit has been
reached since 25 September** — see `04-URGENT-API-LIMIT.md`. This fix removes one of two reasons it
was failing. The other is not code.

---

## 2 · Nothing noticed that the provider had stopped answering — 30 Sep 2026

**Status:** done · tests green · not deployed

### What was wrong

Five days with no working model call, and no alert. It had also happened on 16–17 September and
recovered on its own — **neither occurrence was noticed**.

`llm_costs.success` and `llm_costs.error` had recorded every failure, with its text, both times.
**There was no reader.** That is this repository's own `not_carried` defect in a new place: a value
computed correctly, written down correctly, and consulted by nothing.

⛔ There *was* an alert called `platform_llm_cap_hit` — but it watches **GeniOS's own** budget
governor, which was behaving perfectly throughout. Nothing watched whether the provider answered.

### What changed

| File | Change |
|---|---|
| `platform/provider_health.py` | new · a streak watch over provider-side refusals, raising `ops_alert.notify("provider_refusing_calls", …)` |
| `context/graph_store.py` | `record_cost` observes it — *"every LLM call in the engine lands here"*, the same argument that already put PostHog reporting at this seam |
| `tests/platform/test_the_provider_refusing_calls_is_noticed.py` | new · 21 tests |

### The four design choices, and why

**A streak, not a rate.** A rate needs a window, a denominator and a clock, and all three go wrong
on a quiet tenant — two calls, one failure, 50%. Twenty consecutive refusals cannot happen by
chance, needs no clock, and says the same thing on a busy day and a quiet one.

**Only provider-side refusals count.** `unparseable JSON` and `extraction_call_failed` are *ours* —
a model answered and we could not use the answer. Counting them would make the alert fire for two
different reasons, and an alert that fires for two reasons is an alert nobody reads.

⛔ **`temperature is deprecated` is deliberately NOT a provider refusal.** That one was our bug
(fix 1 above). Alerting on it would send the on-call to the provider's console for a defect in our
own request.

**Our failures do not clear the streak either.** A bad prompt landing in the middle of an outage
must not reset the count and hide it. One test exists only for this.

**A success — any success, any lane — clears it**, because the provider is then demonstrably up.

**Cooldown of one hour.** The real outage produced 3,152 failures in a day; without it that is
3,152 messages.

### How it was proved

```
tests/platform/test_the_provider_refusing_calls_is_noticed.py     21 passed
tests/platform + tests/context + tests/reason                  3,828 passed · 0 failed
FULL SUITE                                                    13,365 passed · 1 failed
```

The last test pins that `record_cost` still calls the watch, so deleting the wire fails the build.

### ⛔ The one failing test is pre-existing and environmental

`tests/capture/documents/test_ocr_enablement.py::test_the_wiring_returns_no_engine_rather_than_one_that_raises`

It fails **in isolation too**, on a clean checkout of the files it touches, and none of the files
changed here are in the OCR path. Cause:

`tesseract_available()` checks the binary **and** the Python bindings — and its own docstring
explains why: *"the deploy image gained the apt packages while `pytesseract` and `Pillow` were in
no requirements file."* The test patches only the binary half (`shutil.which`), so it passes on a
machine that happens to have `pytesseract` installed and fails on one that does not. `pytesseract`
is not installed here and is still in no requirements file.

**Not fixed here** — it belongs with the OCR work (S5), and the fix is a decision: either patch the
second half in the test, or put the bindings in a requirements file. Recorded so the next full-suite
run does not read it as a regression.

---

## 3 · "Stop the retry loop" — investigated, NOT built, because there is no loop

**Status:** premise disproved · nothing changed

### What was claimed

That 3,152 failed calls in one day was *"a loop, not a workload"*, hammering the API.

### What was measured

29 September, failures only:

| Purpose | Calls | Distinct subjects | Calls per subject |
|---|---|---|---|
| `l4_llm_decision` | 1,319 | 178 | **7.4** |
| `l4_llm_r1` | 1,213 | 165 | **7.4** |
| `l2:resolution` | 12 | 6 | 2.0 |

And the busiest single subject:

```
l4_llm_r1   node:node_209421bb35fe4140b2   24 attempts   00:40:58 → 21:12:19
```

**Twenty-four attempts spread across twenty-one hours — roughly one an hour.** That is a periodic
sweep meeting a closed door, not a tight retry loop. There is nothing runaway to stop.

⛔ **The claim was wrong and is withdrawn.** Failed calls cost nothing, so the waste is 3,000 rows
of ledger noise a day and some sweep time — real, but not what was described.

### What is left, if it is ever worth doing

A **circuit breaker**: while the provider is refusing, skip the attempt for a cooldown instead of
re-trying every subject on every tick. `provider_health` already holds the streak this would read,
so it is small. The benefit is quieter ledgers and faster sweeps, and — the one that matters — not
adding load to a provider that is rate-limiting us, which can prolong a 429.

**Not built.** The value is modest and it is not what closes Layer 1.

### ⛔ A contradiction this uncovered, worth someone's attention

`../01-BASELINE.md` §3 records, from Harsh's 29 Sep report, that **the heartbeat does not appear to
run in production** — evidenced by expertise packages never purged and 341 attachments stuck at
`fetch_failed`.

But `l4_llm_decision` fired on the same subjects **hourly across a 21-hour span on 29 September**.
Something is running on a schedule.

Both cannot be simply true. Either a second scheduler drives the decision lane, or the heartbeat
runs and only some of its drains are wired. **Nobody should act on "the heartbeat is dead" until
this is resolved** — it is currently the top item in the baseline and it may be half wrong.

---

## 4 · "Nothing guards the graph revision" — investigated, WITHDRAWN, because something does

**Status:** retracted · no code written · `M10.C1.U03` retired

### What I claimed

In `layer-3-context-graph/01-CROSSCHECK.md`, finding 2:

> `graph_versions` holds one row per org and `bump_version` increments it. It is read in exactly two
> places, and **neither is a guard.** ... Two sweeps that both read revision *N* can both write, and
> the second silently wins. **One `select` away from being the lock it looks like.**

I had written a unit for it — `write_if_unchanged` — and a full scenario table.

### What is actually true

| Where | What it does |
|---|---|
| `reason/runner.py:570` `_graph_version_guard` | reads the tenant row `for share`, compares `current == expected`, **yields a boolean** |
| `reason/runner.py:1276` | honours it — on drift sets `graph_drifted`, counts `graph_changed_retry`, **does not publish** |
| `deliver/` × 8, `api/` × 4 | take the same lock before reading |
| `tests/test_graph_version_consistency.py` | 6 tests, 6 passing |

```
$ .venv/bin/python -m pytest tests/test_graph_version_consistency.py -q
......                                                                   [100%]
6 passed in 0.34s
```

One of those tests is literally named
`test_runner_captures_graph_version_before_tenant_p90_and_retries_on_drift` — the exact scenario my
step listed as its headline case.

The existing guard also already satisfies the one constraint I had flagged as mattering most: ⛔ *"the
refusal must be a value, not an exception."* It yields a boolean the caller branches on.

### ⛔ Why I was wrong, and the rule it adds

I grepped for the version **reader** inside `context/` and concluded from its absence there.

But the read-modify-write cycle **spans packages by design**: `context/` writes the graph and bumps
the counter, `reason/` reads the counter and guards against it. Looking for the guard beside the bump
was looking in the one place the architecture guarantees it cannot be.

> **A guard lives with the reader, not with the writer. Absence in the writer's package is not
> absence.**

**This is the second wrong finding in this programme from counting along the wrong dimension.** The
first was Layer 1's `no_model_wired`: 632 failures that looked like broken wiring and were one lane
that is model-free on purpose, which produced the rule *"a count without its dimension is not a
measurement."* This adds the package dimension to the same rule.

### What changed

**No code.** I did not refactor `_graph_version_guard`, move it, share it, or rename it. It works, it
is tested, and it is not what was asked for. Noticing something adjacent makes a new unit, not a
silent edit.

`01-CROSSCHECK.md` finding 2 is rewritten as a retraction. `STEP-02` is renamed
`STEP-02-WITHDRAWN-compare-and-set.md` and states the retraction rather than being deleted — a
deleted wrong finding teaches nothing, and Harsh may have been told the guard was missing.

### Where the surviving fragment went

`_graph_version_guard` is private to `reason/` and carries pack-authority and watermark logic. `context/`
sits below `reason/` and cannot import it, so a read-modify-write in `context/` has no guard of its
own. That was real — and it turned out not to be needed either:

- `hold_resolution.resolve_hold` **decides and does not write**, so there is no read-modify-write.
- `evidence_need_store.close_need` guards with `where need_id = :id and state = 'open'` — one
  statement, no read-modify-write, so two concurrent executor passes cannot both win.

Smaller than the guard I was going to build, and it is the right shape for the actual write.

---

## 5 · The needs queue was written by nobody — fixed 30 Sep 2026

**Status:** done · 20 tests green · migration NOT applied to production

### What was wrong

Three pieces existed and did not touch:

| Piece | State |
|---|---|
| `context/residue.py` `detect_residue` | ✅ shipped, measuring the gap every sweep |
| `context/evidence_needs.py` `needs_from_residue` | ✅ built in the L1 work, tested, green |
| `capture/acquire/evidence_need.py` `execute` | ✅ built, tested, green |
| **anything that wrote a need to the table** | ❌ **nothing** |

So the executor read an empty table. Built, tested, green, and called by nothing — the **sixth**
instance of that shape this programme has found, and the first one it created itself.

### What changed

- `genios_engine/context/evidence_need_store.py` — `store_needs`, `read_open_needs`, `close_need`,
  `file_needs`
- `genios_engine/context/runner.py` — the call, immediately after `detect_residue`, plus
  `evidence_needs_filed` in the sweep result

### ⛔ The design is one SQL verb

`on conflict (need_id) do nothing` — **never** `do update`.

Residue is re-derived every sweep, and a re-derived need is born `open`. An upsert that UPDATED would
reset every closed need back to `open` next sweep:

1. A question answered *"the document does not exist"* would be re-asked forever.
2. The executor would re-fetch and re-charge each time.
3. ⛔ The system would learn that **its questions are always eventually answered** — the exact failure
   `evidence_needs.py` excludes three of four residue kinds to avoid, undone by one verb.

`test_the_insert_does_nothing_on_conflict_and_never_updates` asserts it on the statement text.

### Two smaller decisions

**The reported count is NEW rows, not rows offered.** A count of needs derived would report the same
number every sweep and read as activity. `evidence_needs_filed == 0` means *"nothing new to ask"*.

**The trace id is `stable_id("trace", {org, sweep_at})`, not `new_id`.** `process_pending`'s own
docstring promises the same graph at the same `eval_time` replays identically; a random trace would be
the one field a replay could not reproduce.

### What it did NOT change

Nothing is fetched. No pass reads `read_open_needs` and calls `execute`, because the executor needs
real connector `fetchers` — the L1 integration gap owned by Harsh. **The queue is write-only today**,
and `evidence_needs_filed > 0` must not be read as "something is being fetched".

And migration `0187_evidence_needs.sql` has **never run in production**. The filing pass is inside
`try/except` and logs, so on a database without the table the sweep completes and the count stays 0.

---
---

# L5 · Delivery (M13) — 2026-09-30

## ⛔ The defect we created ourselves, and found one step later

`layer-2-reasoning/STEP-05` added `OutputLane`, routed every decision, migrated
`signals.output_lane` + `lane_reason` (`0189`), and wrote both onto the row. Its own document
promised *"the card layer can group by lane directly."* Then:

```
grep -rn "output_lane\|lane_reason" genios_engine/deliver/   ->   nothing
```

**Built, tested, green, and called by nothing** — the eighth instance this programme has found, and
the first it produced itself. `deliver/lane_display.py` + `0190` + `store.py` closed it.

## Three real defects my own new tests found, in the code and not in the tests

**1 · `str(OutputLane.DECISION)` is `"OutputLane.DECISION"`.** Not `"decision"` — it is a
`(str, Enum)`, not a `StrEnum`. So **every in-process caller holding the enum would have been
labelled `unrouted`**, while the database path (plain text) kept working and hid it indefinitely.
Found by a test that passed the members themselves. Fixed with `getattr(x, "value", x)`.

**2 · The count and the label gave two answers to one question.** `tally_lane` took the raw column
and re-described it with no reason in hand; `describe` treats a lane without its reason as no route
at all (the pair is atomic in `0189`), so a routed card was **displayed as `decision` and counted as
`unrouted` in the same pass.** Fixed by taking the already-resolved lane — one resolution per card,
by construction.

**3 · The tally was at the wrong place.** Counting on the composed draft would have described a
population including cards nobody received, **and** would have made the recall check a tautology
(the tally and its comparison incremented by the same line). Moved to the two sites where a card is
actually written — `built` and `refreshed` — so the check compares two independently incremented
counters.

## The correction recorded in `0190`, because `0189` cannot be edited

`0189`'s header states the lane is inside `decision_hash`. **It was, it broke four replay tests
(`ReplayIntegrityError`), and it was removed.** `route()` is pure over `outcome`, `confidence_bp` and
the conflict flag — all already hashed — so the lane adds **zero** information, and a derived value
has no business in a content hash. A migration's checksum is its immutability, so the correction is
append-only in `0190`, and a test asserts it is there.

## ⛔ The near-miss: I almost wrote that the invention validator did not exist

Grepped `reminder_facts` — the name its own docstring uses — found three files, no validator, and was
about to write *"it was never written"* into a cross-check. It is at `deliver/render.py:334`, called
at `render.py:861`, re-exported by `executive/validate.py:69`, and covered by `tests/test_delivery.py`.
It is a **generic** function taking `corpus_text`, so its subject's name appears nowhere near it.

**A conclusion drawn from one name's absence.** Third time: `no_model_wired` (L1), the graph-revision
guard (L3), this. Caught before it reached a document, which is the only improvement worth claiming.

## A brittle test made stricter, not looser

`test_the_receipt_count_grew_by_exactly_three` pinned `len(R.receipts(...)) == 26`, so the very next
layer to add a receipt broke a test about **L4** — and the cheap fix for that is to bump the number,
which is how a decision gate becomes a rubber stamp. Rescoped to count L4's own receipts: it still
fails on an undecided L4 addition and stops failing on decisions taken elsewhere.

---
---

# L6 · Learning (M14) — 2026-09-30

## ⛔ The milestone's own promise was already kept

M14 ships *"a wrong card debits the layer that failed, and a timing complaint never lowers a correct
rule's precision."* The second clause was **already true in three independent places**:

```
calibrate.TAXONOMY["wrong:bad_timing"]  ->  {"precision": "none"}
feedback/units.py:135                   ->  judged = acted + wrong   # bad_timing does not grade
calibrate._PRECISION_SQL                ->  in ('not_relevant','wrong_facts')
```

with `packs/brains/adaptive_lease.py` documenting it from the consuming side. **And `_PRECISION_SQL`
goes further than the milestone asked** — it also excludes non-prescribing cards, with the best
statement of the principle anywhere in the repo: *"counting that as a precision failure made
answering the system's own question evidence the system was wrong."*

It was work to **not break**, not work to do. `U03` became the layer debit plus the first **guard**
over the property — because a rule enforced in three places can be broken in three places, and none
of them failed a build.

## ⛔ The widening would have broken it, in both directions at once

**Over-counting.** `units.py` branched on one literal, `reason == "bad_timing"`. Five of the eleven
reasons say the card was RIGHT and something else was not. **Four of those five would have landed in
the `else` and debited the rule's accuracy** — the exact defect this milestone exists to end, created
for four new reasons by the step meant to fix it for one.

**Under-counting, and the harder one to notice.** `_PRECISION_SQL` held two reasons. Six now count
against a rule. Four real quality failures — `misread_source`, `wrong_subject`, `bad_link`,
`bad_reasoning` — could have been recorded by a founder and **counted by nothing**. Nothing breaks,
and precision merely looks better than it is.

Both closed. Both tested. **Totality guards both directions**, here literally.

## ⛔ The topology gate caught my own contracts violation

`contracts/learning_attribution.py` imported `genios_engine.LAYERS` so the layer names could be
checked at import time. `test_contracts_import_nothing_above_platform` **failed the build**:
*"contracts/ is the boundary vocabulary — it may depend on platform/stdlib only."*

The gate was right. `contracts/` is what every layer imports, so a dependency added there is added
everywhere — and `LAYERS.py` exists to be read by the topology *test*, not by shipped code (nothing
else in `genios_engine/` imports it). The requirement stands and moved to two tests. **Same lesson as
`capture → context` in L1 Step 10.**

## A label that was about to record a falsehood

The first derivation mapped every `none` reason to `"timing"`, which would have filed `wrong_person`
and `wrong_playbook` as **scheduling** complaints. The old four-word label vocabulary was designed
for three reasons; a `fit` label was added.

⛔ And `label` has **no code reader** — `TAXONOMY` is read for `precision` only. That is near-miss
territory for *"built and called by nothing"*; it predates this work and is documentation-only, so it
is **recorded rather than removed**, because deleting a field two comments describe is a bigger
change than labelling it correctly.

## ⛔ Two of my own tests were blunt greps, in one file

`test_the_guard_reads_the_taxonomy_rather_than_restating_it` asserted `"denominator" not in src` and
failed on **its own docstring**, which uses the phrase *"the precision denominator"* to explain the
rule. `test_the_report_changes_no_weight_anywhere` matched `OFFSET_BOUND` in the module docstring,
where it appears to explain that learning is bounded **and an attribution is not**.

Both rewritten as AST walks. Twice in one file is why the rule is *"assert on structure"* and not a
preference.

## Three `verify` commands pointed at files that did not exist

`tree.yaml` names one test file per unit — that is the addressing contract, and a `verify` that exits
non-zero means the unit is not green. My work had put seven units' tests into three files. Split by
AST into exactly the seven the tree names, with an assertion that **no test was dropped and none
duplicated**: 32 → 20 + 16 (one test file's helpers are shared), 53 → 23 + 5 + 25.

⛔ While splitting, `head.split('"""\n', 2)[2]` raised `IndexError` — the opening `r"""L5 STEP…`
puts no newline after the quotes, so there is **one** occurrence, not two. Counting quote marks is a
blunt grep on Python source; the AST gives the docstring's extent directly.

---
---

# Plane D · L2 Section S6 — 2026-09-30

## ⛔ Two of my own cross-check findings were wrong

Both caught by continuing to measure **while building**, not by review. Both recorded as appended
retractions in `plane-d-domain-expertise/01-CROSSCHECK.md` rather than edited in place, because *how* a
wrong conclusion was reached is the part worth keeping.

### R1 · *"`unrouted_l2_types` is hand-kept"* — false

`_tools/index.py:205` **generates** the block, **including the comment I quoted as evidence of
hand-keeping**, from `all_l2 - bound_globally` at line 61. Backed up all three registries, ran
`index.py`, diffed: **byte-identical.**

**Cause:** I read `validate.py`, found it computing the same set, saw the block in the YAML, and
concluded two maintainers of one fact. **I never checked whether the YAML had a generator, because the
name `index.py` appeared in nothing I had read.** Fourth instance of the one-name-absence trap —
`no_model_wired` (L1), the graph-revision guard (L3), `invention_ok` (L5), this.

**What survived is a better unit:** `index.py` has to be *run*, nothing failed when the committed file
went stale, and `validate.py` computed the same set three lines away and never compared them. **Two
computations of one fact, never compared.**

### R2 · *"a situation's status gates nothing"* — false, and the unit was already built

`capability_resolver.situation_admission_reason` reads `status`, `review_status` and `reviewed_by`; the
gap **names the situation**; `admitted = not admission_gaps` (line 790) carries it; `review_state`
becomes `draft`; `_apply_abstention` downgrades the card. Measured over the whole corpus: **all 23
draft situations flagged, ZERO may instruct.** Already covered by **15 tests**.

⛔ **Cause: I believed a comment in the corpus.** `condition-awaiting-review.yaml:33` says, in capitals,
*"A situation's status gates nothing."* **It was true when it was written** and
`situation_admission_reason` closed the hole afterwards. I quoted it as a current measurement and
reported that 6 of Admin's 7 draft situations were shipping prescriptive cards. **Not one of the 23
can.**

> ⛔ **A stale comment is more dangerous than no comment, because it reads as a measurement somebody
> already took.**

That paragraph now carries a dated correction naming the function, the line and the measurement — plus
the cost, so the next reader knows a whole cross-check pass was spent on it. `M11.C5.U03` is
**WITHDRAWN**; the comment fix is the only thing it produced.

## ⛔ What was genuinely wrong: an operations fact published as an authoring gap

`scripts/corpus_route_probe.py` — the tool routing coverage is **read** from — classified route
refusals like this:

```python
text_ = str(exc)
if "unknown domains" in text_:   key = "unknown_domain_hint"
elif "no authored" in text_:     key = "no_route_predicate"
else:                            key = "no_route_type"
```

**Three tests over FOUR causes, with an `else` catch-all.** Replayed over the resolver's four real
messages before writing a line: `domain_not_activated` — *"this tenant has not switched this domain
on"* — matched neither pattern and was reported as *"nobody authored a route for it."* **The raise
site's own comment says those two are different facts fixed in different places.**

And **the right pattern was fourteen lines up in the same file** — `UnsupportedCoverage` already
validates its reason against a closed set, with a docstring explaining that folding distinct causes into
one count meant the metric *"could never separate 'broken' from 'not built yet'."*

## ⛔ And `no_route` had no dimension

`counts["no_route"] += 1` and nothing else. *"Twelve situations found no route"* is one type twelve
times or twelve types once — opposite problems, opposite fixes, same number. **This programme's own L1
rule reaching its own code:** *a count without its dimension is not a measurement.*

## Four smaller things caught before they shipped

**A `Counter` was about to hold a mapping.** My first version put the breakdowns inside `counts`, which
is a `Counter` of ints — `most_common()` and `Counter.__add__` raise on a type comparison the moment
anybody reaches for either. No symptom today; moved beside it.

**Seven `also_serves` conflicts, each of which would have been a build error.** Found before writing
Support's ledger — then found the two guards (`owner in deferred`, `no l2_situation_types`) that make
all seven harmless. Verified rather than assumed.

**The ledger is all-or-nothing.** `validate.py` errors on an unrouted capability with no deferral **only
when the file exists**, so creating it converts 7 warnings into 7 errors unless all seven land in one
commit. A partial ledger is worse than none.

**Deferring suppresses situations.** Three of the seven own one situation each; all three are `draft`
and bind zero L2 types, so nothing functional changed — and the registry did, which `U02`'s new guard
would have caught if I had forgotten to re-run `index.py`. The two units verify each other.

## ⛔ My own tests raced each other, and the fix was not to weaken them

`test_the_unrouted_list_cannot_drift` and `test_every_capability_has_a_door_or_a_reason` both ran
`validate.py` as a subprocess, and the first **edited a real registry and restored it.** Run alongside a
second pytest process — which this suite does — both mutated the same file and both failed, reporting a
stale registry that was an artefact of the test harness.

⛔ **A guard that must modify the corpus in order to prove it works cannot be trusted in CI.** The
comparison was extracted into a pure `registry_staleness(computed, stored)` and the mutating tests now
drive that function with synthetic inputs. **No test in either file writes anything.** A test asserts
the function never touches the filesystem, so it cannot drift back.

---
---

# Plane D · the completeness wave (G1–G5) — 2026-09-30

Asked: *"is the expertise itself complete?"* Measured, answered **no**, and closed all five gaps.
**283 → 35 corpus warnings; the 237 `planned but not authored yet` warnings are gone entirely.**

## ⛔ The repo stopped me forging a signature, twice over

`sales.qualification.lead_qualification` and `customer_success` carry `reviewed_by: harsh`,
`reviewed_at: 2026-08-24` and an `accepted_content_hash`. Adding `failure_modes` changes the content,
so the capability un-accepts itself — **and `admit.py --accept` would have stamped it anyway**,
because it refuses only what is not already marked approved, and these were.

Two of the repo's own tests caught it within seconds (`content_changed_since_acceptance ×2`,
`153 == 155`). I reverted, staged the content, and applied it only when Rohit said to — under
**`reviewed_by: rohit`, dated today**, which is true because he authorised it. He has still not read
the fourteen paragraphs, and the staged file says so.

> ⛔ **A tool that stamps whatever is already marked approved is not a guard against the author; it is
> a guard against forgetting.** The guard against the author is the reviewer's name, and only a human
> can move it.

## ⛔ Three of the "thirteen" missing objects were my own regex

My census said 13 Admin objects missing. `domain.yaml`'s roster said **9** — `budget-line`,
`compliance-obligation` and `employee-record` were authored and my pattern truncated each at the
hyphen. **The roster is authoritative; a grep is not.** Fifth instance this session of a conclusion
drawn from what a pattern failed to match.

## ⛔ Authoring them found a defect nothing checked at all

I invented six `owner_capability` ids. **The validator reported zero errors on all six.** It surfaced
only because the load-set wiring could not find the capability — had I not been wiring them, six
invented names would have sat in `objects/core/` pointing at capabilities that do not exist.

An object id at least produces a *"planned but not authored yet"* warning. A dangling
`owner_capability` produced **nothing**, and it decides whose review covers the object.
`_tools/validate.py` now errors on it. **My own mistake bought the check.**

## What the corpus had already decided, before any of it was authored

Nine Admin objects, and eight were defined by exclusion in files that pointed at them —
*"NOT the delegate. The covering person and the delegation instrument are…"*, *"the request holds the
clock; the service level sets it"*, *"the invoice arrives long after the money was committed"*,
*"hybrid working broke most registers"*, *"a probability and an impact; an obligation is a duty that
exists whether or not anyone has assessed it"*.

Authoring invented almost nothing. It wrote down what nine files already implied. The three that had
**no** declared usage to derive from say `completeness: skeleton` and `confidence: experimental`
rather than pretending otherwise.

## ⛔ Support's gap was worse than Admin's, and the difference is the whole point

Admin's nine were cross-references between objects — they blocked nothing. **Support's eleven were in
load-sets, `required`**: `support_agent` by six capabilities, `queue`/`intent`/`resolution` by three
each. Those compiles could not have run. 13 authored; required-missing now **0** in all three domains.

`customer_support.obj.core.stakeholder` has `referenced_by: 0` — the only one of the 22 that closed a
declaration rather than a reference — and its header says so, because an object nothing references is
one edit from the defect this programme has found nine times.

## ⛔ The ceremony reached two layers and skipped the two with the most files

155 capabilities: stable, approved, hash-accepted. **88 objects and 283 heuristics: no gate at all,
218 of them `draft`, not one carrying an admission hash.** And `heuristics/` is where `reads:` lives —
the declaration of what a piece of doctrine consults.

`artifact_admission_reason` asks the same three questions, and the counts reach the package as
`unreviewed_object_ids` / `unreviewed_artifact_ids`. ⛔ **Counted, not gated** — refusing 284 documents
in one step on a corpus whose capabilities all pass is not a measurement, it is an outage.

## ⛔ Half the evaluation cases must be refusals

`Domain Expertise/_eval/` — 18 cases, **10 expecting `abstain`**. A corpus evaluated only on what it
should answer gets tuned until it answers everything, and the expensive failures here are confident
answers to questions the evidence could not settle.

The sharpest case asserts something nothing had ever checked: **`deferrals.yaml` CLAIMS a deferral is
structural** — the capability in no route, its situations suppressed from the generated map. That is a
claim about the generator, and it was untested until now.

### And two of my own cases were wrong on their first run

`sales.unanswered_email.routes` named a type **Sales does not bind** — written from what the substrate
emits rather than from what the corpus binds. And the deferral check searched everything before
`routed_l2_types:`, which **includes the `deferred_capabilities:` block**, so it found all 31
deferrals in the list of deferrals and called each a routing leak.

> ⛔ **A crude slice that happens to fail looks exactly like a real finding.** Both are recorded in
> the case file and the test rather than quietly fixed.

---
---

# L2 verification + Plane R (S5) — 2026-10-01

## ⛔ The Atlas dossier for this layer was stale in 5 of its 8 central claims

Its own baseline: `harsh/mvp@b739bd5c`, **audited 2026-08-22**. Re-measured six weeks later:

| claim | state |
|---|---|
| *"legacy_pack … a **six-unit** DAG"* | ⛔ **schedules 10**, including `core.alternative` and `core.validation` — the units the dossier says are never scheduled |
| *"alternative/trade-off/validation/recommendation omitted"* | ⛔ a **20-unit `_ROSTER`** exists with all four, bound to fact paths, with budgets and dependency edges |
| *"all four brains are **hash-only**"* | ⛔ `WAVE Y1 · THE WELD` — `organization_rules` → `blocked_play_ids` → `core.constraint` **eliminates before ranking** |
| *"score mapped to `confidence_score`"* | ⛔ **FIXED** — `"never the score"`, with a separate `priority_score` |
| *"`stakes: missing`, `completion: missing`"* | ⛔ **FIXED** — computed from real columns (migration `0065`) |

Two still hold, and they are the load-bearing two: the **17-unit capability is still out of the sweep**,
and the **brain-mutation proof is still unavailable** — in August because the wire was missing, today
because the three runtime brains are **empty**.

⛔ **The lesson is about dossiers, not this one:** an audit is a measurement with a date on it, and a
measurement read six weeks later is a claim. `00-CORRECTIONS-2026-10-01.md` says so about itself.

## ⛔ S5's premise was true and misleading, and that halved the work

The plan said *"23 units, 0 declare what they read"* — literally true. But `validate_sources()` was
**never unwired**: `registry.py:131` calls it in the constructor, `:141` fills `_sources` from
`declared_source_units` on every registration.

> **It has been running on every process start since it was written, validating zero.** Not a guard
> waiting to be built — a guard with nothing to check. Nothing needed wiring; 23 classes needed to tell
> the truth.

`registry.py` had already written the diagnosis: *"a unit whose defaults are unchecked, **which is where
every unit was**."*

## ⛔ And the bug it prevents had already shipped, in the unit with the most sources

`tradeoff_unit.py:55`: *"this unit has been **comparing two axes while declaring three** since the day
it shipped. Nothing failed, because **a missing source is indistinguishable from a source that did not
run**."*

And `risk.py` had named its constants **for this check**: *"enumerated here so the registration check
can prove they name units that exist."* **The constants existed. The check existed. The joining line did
not.**

## Two more corrections to the plan's own unit list

- *"the **two** `AXIS_SOURCES` units"* — there is **one**.
- *"`source_units` on **`legacy.score_gate`**"* — it reads **no source at all**; declaring one would
  assert a dependency it does not have.

## What `U01` bought, and why it was a unit rather than a tidy-up

`core.impact` kept its default source as an **inline literal** at `:191` while its three siblings used
module constants. A literal in a function body **cannot be derived from**, so `U05` written first would
have been `("core.relationship",)` — a retyped copy, inside the declaration meant to make the original
checkable. It was also the next silent rename: the three siblings break where a reader can see it; this
one kept running and read nothing.

## ⛔ `()` and absent are the same value and opposite facts

Before this section all 23 units read `()` — 21 because nobody declared, 2 because there is genuinely
nothing to declare. `core.confidence` and `core.priority` now declare an explicit `()` **with the
reason**, which is the only thing that tells the two kinds apart. Their comment also records `ALARM
A6`: `or ""` means a manifest that forgets yields an **empty source string**, not a refusal.

## The guard is source-derived, and it was driven rather than asserted

A test pinning `RiskUnit.source_units == (...)` passes forever and proves nothing. `U07` walks each
module's **AST** for `*_SOURCE` constants and `AXIS_SOURCES` entries and demands each appear in the
declaration. Proved by adding `DEFAULT_OWNER_SOURCE = "core.dependency"` to `risk.py` without declaring
it:

```
core.risk names {'DEFAULT_OWNER_SOURCE': 'core.dependency'} in a module constant and does not
declare it in source_units.
```

⛔ **AST, not a grep, and the reason is in these files:** `risk.py`'s comment mentions `core.temporal`
three times before the assignment. A regex matches the explanation. **Four tests earlier in this
programme failed on exactly that.**

## Found at collection time, not assertion time

**The six supplementary units have no `unit_id` class attribute** — they *"predate the framework"* and
identify through `spec.reasoner_id` on an instance. A test reaching for `cls.unit_id` failed while
pytest was building parameter ids. The fact now lives in one `_id_of()` helper.

## ⛔ `U08` pins an alarm instead of hiding it

`core.tradeoff`'s sources exist in three places; two are one value, the third is an independent copy in
`expertise._ROSTER`. Compared **both directions**, because they are different bugs — and the comparison
records that `core.tradeoff` would compare **1 of 6** axes on the live lane today, which is the exact
failure its own `AXIS_SOURCES` comment describes.

---
---

# L2 · A and B — the lost axis, the fact census, and a defect in the receipt mechanism — 2026-10-01

## ⛔ A · I refused a correct fix on a false reading of a warning

`08-AUDIT` rejected the lost-axis receipt because adding an output field would *"rehash ~100% of
12,170 traces"*. **It rewrites nothing.** `ReasoningStore._verify_replay_bundle` hashes the content
**stored inside a bundle** against the hash **stored beside it** — it never re-runs a unit. Old runs keep
their output and their hash, both consistent, and still verify.

`contracts/reasoning.py:845` warns about changing **`to_semantic_dict`** — the hashing *function* —
which makes stored hashes disagree with a re-hash of their own content. **Adding an output field is a
different operation.** I read a warning that named what I was about to do and did not follow it to the
code that implements it. Same shape as believing the stale corpus comment in Plane D.

**Real cost of A: no migration, no version bump, zero stored rows.**

## A · what the receipt says on production

Replayed over 2,681 runs, read-only:

```
unavailable.cost_vs_benefit                    2,681 runs   ← every one
absent_source.core.impact.impact_bp            2,681        ← ONE mover, unambiguous
unavailable.risk_vs_reward                     1,593
unavailable.speed_vs_certainty                   784
```

`axis_count: 1` became *"`cost_vs_benefit` lost — go and open `core.impact.impact_bp`"*. The number
said something was missing; the receipt names the unit and the metric.

⛔ **The unit asks; the plugin does not tell.** A plugin reporting an absence would emit an
*observation*, and `axis_count = len(ranked)` counts observations — so an absence counted as an axis
would corrupt the one honest number. And `axis_count + axes_unavailable == 3` on every input, asserted,
because two numbers that must agree and are never compared eventually disagree.

## ⛔ B · both B4 and B5 were mis-stated, and the truth is one root

| `07` said | Measured |
|---|---|
| `core.signal_composition` is *"scheduled by nothing"* | `deal_health.py:16` schedules it. `DEAL_HEALTH_V1` is **not swept** — `ALARM A2`, not a defect |
| `deal.status` has *"no writer"* | it has **3 rows**. A writer that reached 3 of 293 nodes is a coverage problem, not an absent connector |

**The census: `expertise._ROSTER` binds 22 fact paths and 14 have ZERO rows.** Every present path is
`thread.*`, `derived.*`, `commitment.due_at`, `meeting.start_at`; every `deal.*` beyond `status` (3) and
`last_inbound` (34) is empty. **One root — no CRM connector.**

`core.policy` has skipped all 165 of its rows because **all four of its essential fields are in that
list.** It is not failing; it is correctly refusing to run on nothing, forever.

⛔ **And `no_declared_input_available` cannot say which it is.** It conflates *"this situation did not
carry the field"* with *"nothing has ever written the field anywhere"* — different movers, and the
second is not fixable by looking at the situation at all.

**Five movers cover all fourteen**, and a test asserts they stay grouped: without that, a reader sees
fourteen problems instead of the five that exist, and the CRM connector alone unblocks four.

## ⛔ AND RUNNING THE RECEIPTS FOUND A DEFECT IN THE RECEIPT MECHANISM

```
before:  {'PASS': 12, 'FAIL': 4, 'ERROR': 13}   of 29
after:   {'PASS': 20, 'FAIL': 8, 'ERROR':  1}   of 29
```

`0190` is unapplied, so one receipt raised `UndefinedColumn` — correctly. Then **twelve** receipts
reported `InFailedSqlTransaction`, because a failed statement leaves SQLAlchemy's implicit transaction
invalid for everything after it on the same connection.

> ⛔ **Twelve phantom ERRORs were hiding four real FAILs and one real ERROR.** `api/routes.py:161`
> computes `ready = not failed`, so the operator page said thirteen things were broken when one was, and
> **named the wrong twelve.**

**The same defect `domain_shadow` already fixed for its own loop** — its comment is the diagnosis:
*"a single bad situation silently takes every situation after it … The six missing situations were not
unroutable; they were never attempted."*

⛔ **The reset goes in `finally`, not `except`.** A receipt whose query *succeeds* also leaves an open
implicit transaction; resetting only on failure would attribute the next failure to whichever receipt
happened to be running. Driven by a connection that genuinely goes invalid, not a stub that forgives
the second statement.

## One declaration, two grains, never a parallel module

`reason/unit_health.py` now declares both *"a unit that completes and says nothing"* and *"a fact path
nothing writes"*. Same doctrine — *every silent lane carries a reason and a mover* — at two grains, and a
test asserts `reason/fact_health.py` does not exist. Four readers (two probes, two receipts) and **no
copies**: `bound_by` is hand-written, `roster_fact_paths()` is derived, and a test asserts they are equal
per path.

---

# D · 2026-10-01 · the receipt that could never go green

The tenth finding, and the one A, B and C never opened: L4's *"the score components are measured, not
placeholders"*, failing at 59.

**It was a correct question with no date on it.** The defect it detects was real — three nominally
independent integers landing on 5000 together in 59 rows, never once apart, and for **53 of those 59
all five of `guards.CANDIDATE_COMPONENTS` were 5000**, so the entire ranking formula was one constant
and every reasoning unit that adjusts those components was a no-op. Both candidate seams had built
`PlayDefinition` without those fields and the dataclass defaults stood in for measurements.

**And it was closed on 2026-09-08 by `75096bab`.** The last frozen row is `2026-09-07 23:55:58` — the
day before the commit. **34,167 candidates** have been written since, across all three orgs, **zero**
frozen.

> ⛔ **A receipt over append-only history needs a lower bound, or it is not a gate but a monument.**
> `reasoning_candidates` is append-only and this codebase soft-deletes only, so those 59 rows are
> permanent. The receipt returned 59 forever, and `api/routes.py:161` computes `ready = not failed`
> over it — one unfixable receipt holding the release gate shut for a defect that no longer existed.

**The doctrine was already written, one module over.** `reason/unit_health.py`'s own header: *"A
receipt asserting 'no unit is silent' would be permanently red for an upstream reason this layer
cannot clear … A gate that is always red is a gate nobody reads."* This receipt predates it.

**The fix is a date, which is a hair's breadth from making a receipt green, so the difference is
proved.** The three equalities survive byte-for-byte as a prefix of the new SQL, and the added suffix
must equal exactly `" and created_at >= '<declared boundary>'"` — two tests, plus
`test_the_receipt_was_not_made_to_pass` asserting `expect(1) is False`.

**`ClosedDefect` is the third declared fact in `reason/unit_health.py`**, and the first that carries a
**boundary** instead of a mover — because nobody has to act on a closed defect, but somebody has to be
able to recognise it if it returns. It demands the commit that establishes the boundary, so the date is
never one somebody chose. `neutral_default_boundary()` is a function, not a constant, so the receipt
cannot drift from the declaration by copying it; a test walks the builder's AST and asserts no literal
in its **body** equals the date — the docstring excluded, because it quotes it, and a whole-file grep
would have matched the audit document, the receipt's detail and the test's own prose. Seventh instance
of the blunt-grep family this session, and the first caught before it was written.

### Where this leaves the receipts

    29 receipts, fleet-wide:   21 PASS   7 FAIL   1 ERROR     (was 21 / 8 / 1)

⛔ **Not one remaining failure is a mis-asked question.** Across A, B, C and D all ten findings were
examined: one asked the wrong question (C, the L6 draft receipt, which still fails at 18 because *a
receipt is not fixed by making it green*), one asked a correct question with no date (D), and eight
were correct as written — including three I suspected and cleared. Every remaining FAIL is now a true
statement about a real gap with a named mover: three L1 ops items, an unauthored reporting line, cards
frozen by the spend limit, an unconnected Slack, no human verdict yet, and migration `0190` unapplied.

---

# E · 2026-10-01 · the one red test in the suite was measuring the host

Carried all session as *"L1's known `pytesseract`-missing test"*. A known-failure label is the thing
that stops a test from being read, so it was finally read.

**The product was correct and the test was incompletely stubbed.** `tesseract_available()` requires
the binary **and** the bindings. The test stubbed `shutil.which` and left
`importlib.util.find_spec` to whatever the host had, then asserted an engine comes back. On a host
with `pytesseract` it passed and proved the wiring; on this host it failed and proved only what was
installed.

> ⛔ **A test that leaves one prerequisite to the host is not asserting a product property.** A
> verify that can only run on one machine is not a verify, it is a local observation.

**And the half it left to the host is the half that actually broke production.** `tesseract.py:26`:
*"the deploy image gained the apt packages while `pytesseract` and `Pillow` were in no requirements
file, so the binary probe said yes, an engine was wired, and every scanned document came back
`ocr_failed: ModuleNotFoundError`."* **Zero tests covered that**, proved by mutation — with the
bindings check replaced by `return True` the old suite stayed **green**. Three new tests now fail on
that mutant: one per binding (because `all()` over two names is one `and` away from checking one)
plus one asserting the probe asks `find_spec` about both.

**The product code was not touched.** `_bindings(monkeypatch, present=...)` puts both halves under
the test's control and delegates to the real `find_spec` for every other module. 19 passed, was
18 passed / 1 failed.

**The other option on the table was refused.** `STEP-08` offered *"patch the second half in the
test, or put the bindings in a requirements file"*. Adding `pytesseract` and `Pillow` to
requirements would have made the test pass by changing the deploy image — Harsh's call about image
size, and **a test should never be the reason a dependency enters the image.**

### ⛔ ALARM E-A1 — nothing became readable
`[L1] attachments carry readable text` **still FAILS at 872**, `tesseract_available()` is still
False on this host and still right, and zero documents gained one word of text. The test and the
receipt shared a root cause but not a fix: the test was measuring the host, the receipt is measuring
the deploy image. Whose: **Harsh** — two packages in `requirements`, one apt package in the image,
together.

---

# F · 2026-10-01 · the third kind of silence, and an Atlas claim that expired

Re-checking the two planes against the Atlas's own matrix
(`Rohit_Updates/.../01-Master-Atlas-vs-Code-Coverage-Matrix.md`, dated **2026-08-22**) produced one
build and one retirement.

## ⛔ The build: a unit that runs and never completes was invisible

`reason/unit_health` declared two grains and a receipt read each — *a unit completes and computes
nothing*, and *a bound fact path nothing writes*. One unit escaped both:

    core.relationship   929 runs   708 insufficient_context   221 skipped   0 COMPLETED
    core.policy         165 runs     0                        165 skipped   0 COMPLETED

`_UNDECLARED_SILENT_UNITS_SQL` filters `where status = 'completed'` and groups by unit, so a unit
with zero completed rows **is not a row with a low share — it is not a row.** It cannot appear in
that GROUP BY at all, and the silence receipt was green while this unit had produced nothing in 929
attempts.

> **A unit that never completes is not a quiet unit; it is an absent one, and a question asked only
> of completions cannot see it.**

And `core.relationship` was not an unwritten fact either: it binds `deal.status`, which has **3
rows**, and the declaration is for paths with *zero*. `receipts.py` draws that boundary on purpose —
*"A path with one row has a writer; that is the whole question. How WELL it is covered is
`deal.status`'s 3-of-293 problem, a different measurement with a different mover."*

**So the fact was written down twice in prose and declared nowhere a receipt could read** — once in
`receipts.py`, and once inside `DECLARED_SILENT["core.impact"]`'s own reason text, as an argument
for a different unit's entry.

`NeverCompleted` is the third grain. It demands the **run count** beside the reason, mover and date,
because that is what separates *absent* from *never scheduled*; `runs <= 0` is refused at
construction so `core.signal_composition` (0 runs, unswept capability, ALARM A2) cannot be mis-filed
here. 30th receipt, 17 tests, mutation-proved.

⛔ **My first version would have made the receipt permanently red.** It reported `core.policy` as
undeclared, when all four fact paths it binds are already in `DECLARED_UNWRITTEN` — the codebase
accounts for it at the grain that names the real mover. Closed with
`starved_by_declared_paths()`, **derived from the roster**: hard-coding `core.policy` would have put
one fact in two places and gone stale the moment a path gained a writer.

## The retirement: the Atlas's sharpest Plane D claim has expired

| | Atlas · 2026-08-22 | Measured · 2026-10-01 |
|---|---|---|
| Admin | *"**Stub.** 57 files, **all 57 stubs**, zero non-stub, zero reviewed/accepted, **zero routes**"* | **59 capabilities · all admitted · 0 hollow · 34 situations** |
| corpus | *"**zero** reviewed or accepted"* | **155 capabilities, every one admitted, 0 hollow** |

The corpus was authored out from under the matrix. **And the code had already learned this lesson
the expensive way** — `capability_resolver._hollow`'s docstring carries its own retraction: *"THAT
COUNT IS HISTORY, NOT A FACT ABOUT TODAY'S CORPUS, AND LEAVING IT UNMARKED COST A PLAN."* It fixed
it by moving the count into **a function a test can run**. The matrix has no such function, which is
why it had to be re-measured by hand.

Plane R's claim was the opposite: *"Seventeen units are registered; the manifest schedules roughly
six"* is **exactly right** (`CORE_UNITS` is 17, `BUILTIN_CAPABILITIES` schedules 7) — but **22 of 23
units now run in production** and the registry and production agree exactly, so *"registered is not
active"* no longer holds.

## ⛔ Two false findings of mine, recorded rather than deleted

**I nearly filed the programme's largest defect.** I measured that five of six YCW27 folder names
contradict `LAYERS.py`'s digits and was about to write it up. `LAYERS.py` explains the collision in
its own header, in capitals, and states the rule — *"always name the package, never the digit
alone."* The YCW27 folders are the **PRODUCT** column, a legitimate fourth vocabulary. Fifth time in
this programme that reading the thing a name points at prevented a false finding.

**And my own measurement manufactured a finding.** The first run reported *"6 registered units never
ran"*; all but one had run thousands of times. The six supplementary units carry no `unit_id` class
attribute — they are identified by `spec.reasoner_id` on an **instance** — so my id helper returned
class names and nothing matched. The artefact was indistinguishable from a real finding until the
run counts were read.
