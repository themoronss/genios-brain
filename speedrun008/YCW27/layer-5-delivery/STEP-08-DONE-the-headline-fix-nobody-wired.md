# Step 8 — DONE · the headline fix nobody wired

**Unit:** `M13.C3.U08` · **Owner:** me · ✅ **2026-10-01** · 14 tests · 6 mutations
⛔ **Planned as a one-line wiring. It was one line, and the line needed two decisions the plan did not have.**

## 1 · What is there

`deliver/card_builder.py:610` carries its own evidence:

```python
def resolved_person_name(quotes: list[dict], fallback: str) -> str:
    """... 35 of 38 person cards named an address in the headline ...
    a `mention:person` observation carries the real name."""
```

Somebody measured 38 person cards, found **35** with an email address where a human name belonged, wrote
the function that resolves it from a `mention:person` observation, and **never called it.** Zero
references in the repo — not in `card_builder.py` itself, not in a test.

⛔ **This is the one of the four unreached functions that is a plain defect.** The other three are an
un-cut-over path, a PULL_ONLY surface and an unlogged record. This one is a fix for a measured,
customer-visible fault, built and left on the floor.

## 2 · Two questions, in this order

### 2.1 Is the 35-of-38 still live?

Needs a read-only production read:

```sql
set transaction read only;
-- person cards whose headline contains '@'
```

⛔ **Not available in this checkout.** No database URL is configured — only `.env.example`. So the step
builds the wiring and its test, and the production confirmation is logged as a **separate read** for
whoever has access. ⛔ **`GENIOS_ALLOW_PROD_WRITE` is never set to run a report.** That variable is named
for writes because it was written for writes, and setting it to run a report is the wrong shape of
permission.

⛔ **And the number is probably stale in a specific direction**: it was taken before M13 rebuilt the card
path, and no production signal has been routed since the API spend limit began refusing calls on
**2026-09-25 11:09 UTC**. So the headline population may not have changed at all. *A stale comment reads
as a measurement* — including this one, including when the measurement is mine. The wiring is justified
by the function existing and being correct, **not** by the 35.

### 2.2 Does wiring it produce a headline the invention validator refuses?

`invention_ok` (`render.py:334`) rejects any rendered sentence containing a name, number or date not in
the grounded corpus. A `mention:person` observation **is** in the corpus, so the expected answer is no.

⛔ **That is a prediction until a test exists.** And the rule is absolute: **the validator must not be
weakened to accommodate the fix.** If a resolved name fails `invention_ok`, the fix is wrong, not the
validator — *never weaken a verify to make it pass.*

## 3 · What to build

| | |
|---|---|
| `deliver/card_builder.py` | call `resolved_person_name` on the person-card headline path. ⛔ The fallback stays: a card with no `mention:person` observation keeps the address rather than inventing a name — **null is an answer**, the same rule the lane step established |
| `tests/deliver/test_a_person_card_names_a_person.py` | ⛔ NEW |

## 4 · The tests

| Test | Assertion |
|---|---|
| `test_a_mention_person_observation_supplies_the_headline_name` | the resolved name reaches the headline |
| `test_a_card_with_no_observation_keeps_the_address` | ⛔ no invented name, ever |
| `test_the_resolved_name_passes_the_invention_validator` | ⛔ the real risk of the step, asserted rather than predicted |
| `test_the_resolver_actually_REACHES_the_headline` | ⛔ the **M2 mutation shape**: in L4, removing an era bound turned production 3,582 → 0 while 15 tests passed, because one test proved the boundary was *imported* and nothing proved it was *used* |
| `test_the_fallback_is_not_a_neutral_default` | the fallback is the real address, never a placeholder |

## 5 · Verify

```
.venv/bin/pytest tests/deliver/test_a_person_card_names_a_person.py -q
.venv/bin/pytest tests/test_delivery.py tests/deliver/ -q
```

## 6 · Mutations

| # | Mutation | Must go red |
|---|---|---|
| M1 | revert the call site, leave the import | `test_the_resolver_actually_REACHES_the_headline` |
| M2 | return `fallback` unconditionally | the observation-supplies-the-name test |
| M3 | return `"Unknown"` when no observation exists | the no-neutral-default test |
| M4 | bypass `invention_ok` on the headline | the validator test |

## 7 · Expected outcome

A person card names a person. A person card with nothing to name says the address, as it does now, and
never invents. And the production re-measure is a logged read, not an assumption.


---
---

# ✅ DONE — 2026-10-01

## 1 · ⛔ What the measurement changed, before a line was written

### 1.1 The choke point — one edit, complete coverage

`name` inside `build_draft` has **exactly two assignments and three uses**, read from the AST:

```
SET    load_node(...)                                    -> the display_name (an email address)
SET    name = _fval("outreach.counterparty") or _fval("commitment.owed_to") or name
use    compute_slots(reason_code, name, facts, ...)      -> the {entity} slot
use    "business_subject": name                          -> the headline subject
```

⛔ **So the override chain is a single choke point**, and both consumers read from it. One edit
covers the headline *and* the slots — which is why the fix is one line and why checking first
mattered: a change at either consumer would have fixed half the defect.

### 1.2 ⛔ The chain already had a precedence, and it is load-bearing

```python
name = _fval(facts, "outreach.counterparty") or _fval(facts, "commitment.owed_to") or name
```

Its own comment says why: *"A SYNTHETIC ANCHOR'S DISPLAY NAME IS NOT THE CARD'S SUBJECT"* —
`context/outreach_situations.py` names nodes *"Investor A — awaiting reply"*, and using that as
`{entity}` produced *"Investor A — awaiting reply — waiting 4d on a reply"*: the situation said
twice.

⛔ **`outreach.counterparty` and `commitment.owed_to` are FACTS the extractor wrote about who the
reading concerns. A `mention:person` name is an OBSERVATION.** So the resolver goes **last**,
replacing only the `or name` fallback — which is exactly the shape
`resolved_person_name(quotes, fallback)` was written for. Putting it first would let an observation
override the fact that names the counterparty. **Mutation M4 does precisely that, and a test fails.**

### 1.3 ⛔ The gate the plan did not have, and the harm it prevents

`card_builder`'s own comment on the quote loader, by node type:

| node type | what the quotes are |
|---|---|
| `person` | *"its own, which is what already worked for 7 of 55"* |
| ⛔ `company` | *"observations of the people who `works_at` it. Broader by nature, and honest at that width: **the card names the company, and these are its people.**"* |
| `thread` | *"observations minted from events in THAT EXACT THREAD"* |
| `outreach`/`commitment`/`cohort` | *"the counterparty they `concerns`… they are not people, they are readings about a person"* |

⛔ **So an ungated resolver renames a COMPANY card after whichever of its people spoke first.** The
gate is `node_type == "person"`, and **mutation M3 removes it — three tests fail.**

The minted anchors are already served by the two facts in §1.2. Extending the resolver to them when
those facts are absent is a real improvement and **nobody asked for it** — recorded here, not taken.
*Noticed something adjacent? New unit, not a silent fix.*

## 2 · ⛔ The plan's §2.2 prediction was right, and the function's own docstring says otherwise

`§2.2` asked whether a resolved name would produce a headline `invention_ok` refuses, and predicted
no. ⛔ **`resolved_person_name`'s docstring says it DID:** *"…and the invention guard rejected any
draft that wrote 'Maria'."*

Measured rather than read. `render._corpus`:

```python
for q in quotes or ():
    parts.append(str(q.get("quote") or ""))
    if q.get("name"):
        parts.append(str(q["name"]))          # ← the mention:person name IS grounded
```

```
invention_ok("Maria Exconde asked about pricing")        -> PASS
invention_ok("maria@alystventures.com asked about ...")  -> PASS
invention_ok("Nikhil Sharma asked about pricing")        -> FAIL  (name:Nikhil)
```

⛔ **So the docstring's claim is stale** — true before the corpus was widened to include quote names.
**The grounding half of this defect was already closed; only the headline half was open**, and that
is what wiring the function fixes. The docstring is corrected in place, and the claim is now
*asserted* by `test_the_resolved_name_passes_the_invention_validator` rather than repeated in prose.

> ⛔ **A stale sentence inside the docstring of the very function the step is about** — the fifth
> instance of this pattern in L5, after the four in `STEP-07`. And the rule stands unchanged: **if a
> resolved name had failed `invention_ok`, the fix would be wrong, not the validator.** Never weaken
> a verify to make it pass.

⛔ **My own probe was wrong first, too.** `'Maria' in corpus` returned `False` while `invention_ok`
passed, because the corpus is case-folded (`'maria exconde'`). **A substring check against a
normalised corpus is not the test; the validator is.**

## 3 · What the 35 is worth, and why it did not justify anything

⛔ **The production number was NOT re-measured, and could not be**: no database URL is configured in
this checkout — only `.env.example`. And `GENIOS_ALLOW_PROD_WRITE` is **never** set to run a report;
that variable is named for writes because it was written for writes.

⛔ **The 35 is also stale in a known direction:** it predates M13's card rebuild, and no production
signal has been routed since the Anthropic spend limit began refusing calls on **2026-09-25 11:09
UTC**. So the headline population may not have moved at all.

> **The wiring is justified by the function existing and being correct, not by the number.** The
> number is why somebody wrote it; it is not why it should be called.

## 4 · What was built

| | |
|---|---|
| `deliver/card_builder.py` | the resolver wired into the subject chain — **last**, gated on `node_type == "person"` — plus its docstring's stale validator claim corrected |
| `deliver/delivery_health.py` | ⛔ the `KNOWN_UNWIRED` entry **deleted**, because it is wired |
| `tests/deliver/test_a_person_card_names_a_person.py` | ⛔ NEW, **14 tests** |

```
KNOWN_UNWIRED   2 -> 1      only outbox.revive_undeliverable is left   (STEP-15)
DECLARED       25 -> 24
```

### The 14 tests

| group | what it pins |
|---|---|
| **the defect closed** (4) | a `mention:person` observation supplies the subject · ⛔ **no observation → the address stands** · a non-person quote supplies nothing · an **empty** name is not a name |
| ⛔ **the gate** (3) | a company card is **not** renamed after one of its people · nor is a thread card · ⛔ a `counterparty` **fact still wins** over an observation |
| ⛔ **the validator** (2) | the resolved name **passes** — asserted, not predicted · and an ungrounded name still **fails**, so the first test is not passing because the validator accepts everything |
| **mutation shapes** (3) | the resolver **REACHES** the chain (AST) and is **gated** (AST) · the fallback is the real address, never a placeholder · the first mention wins, and the loader's order is pinned |
| **the declaration** (2) | the entry is gone, both directions clean · and ⛔ **exactly one defect is left**, with its step number |

## 5 · ⛔ A test of mine failed on correct code, for the second time, and this time I fixed the design

`test_the_defects_are_not_filed_as_decisions` (written in `STEP-05`) **hard-coded the defect list**.
It failed when `STEP-14` wired `lane_recall.recall_verdict`, and failed again here when
`card_builder.resolved_person_name`'s entry was correctly deleted.

⛔ **The first repair diagnosed it and did not fix it.** I corrected the docstring to say *"the list
of defects is not a constant"* — and left the hard-coded names in place, so the same failure arrived
one step later.

> ⛔ **A membership list shrinks every time the work succeeds; an invariant does not.**

Rewritten to assert the invariant and nothing else: no function in two tables · the fail-closed shim
is permanently a **decision** · and the table may only shrink by a function acquiring a caller, which
`undeclared()` checks from the other side.

⛔ **Caught immediately this time** — because the baseline was established *before* the patch and the
affected set was re-run *immediately after*. 310 before, 324 after, 14 new tests, zero regression.

## 6 · Mutations

⛔ **Baseline first and restore re-verified** — the discipline `STEP-14` paid for.

```
baseline        45 passed, 6 skipped
restore verify  14 passed
```

| # | Mutation | Result |
|---|---|---|
| M1 | remove the call site, keep the import | 🔴 **5 failed** |
| M2 | make the resolver always return the fallback | 🔴 2 failed |
| M3 | ⛔ **remove the `node_type == "person"` gate** | 🔴 **3 failed** — the company card is protected |
| M4 | put the resolver **first** in the chain | 🔴 1 failed — the precedence holds |
| M5 | return `"Unknown"` when no observation exists | 🔴 **4 failed** |
| M6 | put the `KNOWN_UNWIRED` entry back | 🔴 3 failed |

## 7 · Verify

```
.venv/bin/pytest tests/deliver/test_a_person_card_names_a_person.py -q           # 14 passed
.venv/bin/pytest tests/test_a_card_must_quote_what_was_said.py \
                 tests/test_delivery.py tests/deliver/ -q                        # 324 passed
```

## 8 · Doctrine

| Rule |
|---|
| ⛔ **a membership list shrinks every time the work succeeds; an invariant does not** |
| ⛔ **a substring check against a normalised corpus is not the test; the validator is** |
| ⛔ **a one-line wiring can still need two decisions — the precedence it joins and the scope it applies to** |
| **the wiring is justified by the function being correct, not by the number that prompted it** |
| **a stale comment reads as a measurement — including inside the docstring of the function being fixed** |
| **never weaken a verify to make it pass** |
