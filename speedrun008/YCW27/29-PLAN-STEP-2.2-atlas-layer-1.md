# ⛔ STEP 2.2 · ATLAS LAYER 1 — the five open claims

**Written 2026-10-04, after the re-check and before any build.** The rule is the Atlas check comes
first, and `2.1` is the reason it is not negotiable: re-measuring nine claims closed two of them,
corrected five scorecard rows, and turned *"safe today"* into *live* on `L2-11` because the first
measurement stopped at the first writer it found.

`L1-02/03/04/05/11` were graded **Present + Wired + Tested** by the Atlas itself. `L1-06` and
`L1-12` are already **EXPIRED**. That leaves five: **`L1-01`, `L1-07`, `L1-08`, `L1-09`, `L1-10`.**

---

# PART 1 · THE RE-CHECK

## ⛔⛔ L1-08 — the scorecard's evidence is false, and the claim is closed at four layers

**The Atlas:** *"`RawObject`, `SourceEvent` and `GatedEvent` do not require visibility."*
**The scorecard's evidence:** *"all three measured: **zero** declare a `visibility` field."*

⛔ **That measurement is wrong. All three declare one.**

| contract | field | required? |
|---|---|---|
| `capture/connectors/base.RawObject` | `visibility: Any = None` | no — ⛔ and typed **`Any`**, not `Visibility` |
| `contracts/source_event.SourceEvent` | `visibility: Visibility \| None = None` | no |
| `contracts/gated_event.GatedEvent` | `visibility: Visibility \| None = None` | no |

So the **Atlas's wording is right** — they do not *require* it — and the scorecard turned "optional"
into "absent", which are different facts with different fixes.

✅ **And the consequence the claim implies does not occur, because four layers stop it:**

```
1  landing/normalize.py:62   visibility=(getattr(raw,"visibility",None) or derive_visibility(…))
2  gate/gate.py:48           None → re-derive → if still None: PARK "visibility_unknown"
3  parked/recapture.py:170   on re-drain, still None → STILL_BLOCKED
4  the schema               5 of 6 visibility columns are NOT NULL; the 6th
                            (learning_event_inbox) pairs a nullable jsonb with
                            visibility_scope text NOT NULL DEFAULT 'private'
```

The gate says why in its own words: *"An event whose audience no derivation rule can name must not
publish under a guessed one… by Layer 2 the recipient list is gone, so **this is the last gate that
can still refuse**."*

### ⛔ So what IS the finding

**Three in-memory readers treat `visibility is None` as VISIBLE TO EVERYONE**, and two more default
it to org-wide:

| site | what `None` means there |
|---|---|
| `context/framing/timeline.py:104` | `if e.visibility is None or e.visibility.can_view(…)` → **shown** |
| `context/framing/headline.py:157` | same shape → **shown** |
| `context/fact_visibility.py:118` | `if visibility is None or scope != PRIVATE` → **treated as not private** |
| `context/situation_bso.py:1566, 2075` | `visibility or Visibility(scope="org", …)` → **org-wide** |

⛔ These are safe **only because the gate parks**, and **nothing connects them to it.** A new
ingestion path that did not pass the gate — a backfill, an import, an MCP write, a test double
promoted to production — would make all five permissive at once, in a layer the gate's own comment
says can no longer re-derive. **The safety of a privacy default rests on one `if` in one file, and
the five readers that depend on it do not know it exists.**

**U01's deliverable:** declare the dependency where the readers live, guarded **both ways** — the
permissive branches must be declared, and the four layers must still be there. ⛔ Not a repair: making
`visibility` required on three contracts is a change to every constructor and every test double, and
the gate already achieves the outcome.

## ⛔ L1-01 — the scorecard's number is wrong, and the registry's own example has expired

**The Atlas:** *"only **eight** canonical source IDs are buildable… catalogued is not connected."*
**The scorecard:** *"`SOURCES` 36 catalogued · `BUILDABLE_SOURCES` **13 ids**, but
`calendar/gcal/google_calendar` and `drive/gdrive/google_drive` and `database/mysql/postgres` are
aliases → **~7 distinct providers**."*

⛔⛔ **It is 9, not 7** — and the error is instructive. The descriptor carries a declared `aliases`
field, and folding by it gives:

| canonical | declared aliases | capability |
|---|---|---|
| `gcal` | `calendar`, `google_calendar` | calendar |
| `gdrive` | `drive`, `google_drive` | document_store |
| `gmail` · `hubspot` · `linear` · `notion` · `postgres` | — | communication · crm · task_tracker · document_store · product_usage |
| ⛔ `database` · `mysql` | — | **None** |

The first two folds are right. ⛔ **The third is not**: `database`, `mysql` and `postgres` are
**three separate canonical descriptors with three different capabilities**, not aliases of one
provider. *The fold was done by reading the names rather than the field that declares it* — the same
mistake `2.1` made twice with module filenames.

### ⛔ Two findings fall out of measuring it properly

1. ⛔⛔ **`database` and `mysql` are BUILDABLE with `capability = None` and `object_types = 0`.** A
   tenant can connect one and it satisfies **no pack's coverage** and has **no object mappings** —
   it contributes to nothing. This is the exact inverse of the drift the module was built to close
   (*"carried a coverage capability but NO family"*), and it is declared nowhere.
2. ⛔ **The module docstring's own example has expired.** It says *"`hubspot` advertises the `crm`
   capability that the `sales` pack REQUIRES, while no connector can be built for it — so `sales`
   can never be coverage_ready, and nothing in the codebase could say so."* **`hubspot` is
   buildable now.** The *shape* of the claim is still true through **eleven** other sources —
   `salesforce` (also `crm`), `slack`, `outlook`, `zendesk`, `intercom`, `stripe`, `razorpay`,
   `mscal`, `gdocs`, `gsheets`, `mixpanel` — so the sentence is right and its subject is wrong,
   which is the worst kind of stale comment: it reads as a current measurement.

**U03's deliverable:** a receipt for a connected source that satisfies nothing, the docstring's
example corrected to a source that is actually in that state, and the scorecard's number fixed.

## ⛔ L1-09 — the claim is true, and the contract makes a promise nothing checks

**The Atlas:** *"the coverage snapshot is not mandatory on each emitted signal."* ✅ Confirmed:
`GatedEvent.coverage_ready: bool | None = None`, and `qualified_signals.coverage_ready boolean` is
**nullable**.

⛔ But reading the field's own comment turns this from a shape complaint into a measurable claim.
The contract says, of the field one along:

> *"`None` means no tagger ran (a pre-S4 row); **a freshly gated event always carries a real bool**."*

and of `coverage_ready` itself:

> *"A dead field on a contract is worse than a missing one: it invites a consumer to trust a seam
> that carries nothing, and **`None` reads as 'unknown' exactly where a caller most wants a yes**."*

**Nothing checks either sentence.** *"A freshly gated event always carries a real bool"* is a claim
about every row the system writes, and it is exactly what a receipt is for. ⛔ The time window is
load-bearing and must be **derived**, not chosen: old rows are legitimately null and counting them
would make the receipt red for ever.

## ⚠️ L1-07 — partly expired; roles ARE typed

**The Atlas:** *"no mandatory typed business roles leave L1."*

| half | verdict |
|---|---|
| *typed* | ⛔ **EXPIRED.** `ExtractionResult.roles: list[RoleAssertion]`, and `extraction.py:771` records that `roles` was `list[str]` / `list[dict]` **until this date** |
| *mandatory* | ✅ **still true** — `Field(default_factory=list)`, so an extraction with no role is valid |
| *leave L1* | ✅ **declared by design, with the owner named.** `gated_event.py`: *"Still deliberately absent, by design not omission: … typed role candidates (roles need the extraction the envelope feeds; **L2's b3-3 prompt owns them**)"* |

**U04:** paperwork. ⛔ Whether a role should be *mandatory* is a product decision — an extraction
from a message that names nobody has no role to carry, and refusing it would drop the message.

## ✅ L1-10 — confirmed exactly as graded

`contracts/signal.SIGNAL_STATES = {active, expired, resolved, superseded}` — **4 states**.
⛔ Missing `new`, `revoked`, `satisfied`; extra `resolved`. The Atlas wanted six.

**U04:** paperwork, and the row is **Rohit's** — a 4-state vs 6-state signal lifecycle is a product
decision about what the engine must be able to say, not a missing function. ⛔ `satisfied` vs
`resolved` is a rename; `new` and `revoked` are new behaviour.

---

# PART 2 · THE UNITS

```
U01  L1-08  the visibility chain — declare the five permissive readers, guard the four layers
U02  L1-09  receipt 47 — a freshly qualified signal carries its coverage verdict
U03  L1-01  receipt 48 — a connected source that satisfies no capability
            + the docstring's expired example + the scorecard's wrong number
U04  L1-07 · L1-10  paperwork, and two rows that are Rohit's
```

Bottom-up, one at a time, each with its own suite run and its own mutation run with the baseline
asserted **both sides**.

⛔ **Done** means the full suite green with no new skips, every mutation caught or reported invalid
**with its reason**, the audit written, and `19-PENDING` carrying whatever turned out to be Rohit's.

⛔ **What this step will NOT do**, stated up front so it is not mistaken for an omission:

| not doing | why |
|---|---|
| making `visibility` required on the three contracts | every constructor and test double changes, and the gate already achieves the outcome by parking |
| adding `new` / `revoked` / `satisfied` to `SIGNAL_STATES` | a lifecycle is a product decision; a rename plus two new behaviours |
| making a typed role mandatory | a message that names nobody has no role to carry |
| building connectors for the 11 unbuildable capability-advertising sources | that is the roadmap |


---
---

# ⛔ CLOSED 2026-10-04 · PLAN vs ACTUAL

| | planned | ⛔ actual |
|---|---|---|
| **units** | 4 | **4** — the shape held again |
| **receipts** | 2 (`U02`, `U03`) | **2** |
| **tests** | — | **48** (15 · 17 · 14, plus 2 from a per-claim parametrised guard) |
| **mutations** | — | **51 caught · 1 surviving by design** |
| ⛔ **holes in my own guards** | 0 anticipated | **3**, every one found by mutation after the suite was green |

## ✅ Where the plan was right

* **The re-check before drawing units.** Two of the five rows carried **false evidence** and one
  was partly expired, so `U04` existed only because the re-check found them. Planning against the
  badges would have produced work for `L1-07` that was already done and missed both larger
  findings.
* **The "what this step will NOT do" table.** Written up front, and it held: `visibility` is still
  optional on three contracts, `SIGNAL_STATES` is still four, a role is still not mandatory, and
  no connectors were built. Each one is on Rohit's page with its cost rather than half-done.
* **Reading the field's own comment rather than its type.** `L1-09` planned as *"the claim is true,
  and the contract makes a promise nothing checks"* — and that promise is exactly what receipt 47
  became. The type signature alone would have produced a shape complaint.

## ⛔ Where the plan was wrong, and it was the same direction both times

**1 · `U01` was planned as one site count.** The plan named **five** permissive sites from a grep.
⛔ The AST sweep found **eight** — and the three extra needed a *different* verdict (`fail-closed`),
which only measuring `can_view` settled. A declaration written from the plan would have been
incomplete in one direction and wrong in the other.

**2 · `U02` was planned as "receipt 47".** ⛔ The plan did not anticipate that measuring
`coverage_ready` would surface **five carried-dead fields**, nor that `degraded_compile`'s own
comment claims the defect was fixed. The receipt was one quarter of the unit.

⛔ **Both misses are under-estimates from reading one layer.** The plan read the contract and not
the sweep; it read `coverage_ready` and not its neighbours. *Broaden the measurement before you
believe it* — a rule in this programme's memory that cost a correction in `2.1` and cost two more
here.

## ⛔⛔ And the lesson the plan could not have contained

Three of my own guards had holes, found **after** each suite was green:

| ⛔ the hole | the shape |
|---|---|
| no converse grade check | *"the open ones are open"* with no *"the closed ones are closed"* |
| a declaration satisfying the test that its own source exists | the evidence and the claim in one file, nothing keeping them apart |
| a correction whose names nothing checked | **the fix for a stale comment was about to be a stale comment**, in the same file |

⛔ And `assert len(what) > 40` **came back one step after `2.1` replaced `assert len(why) > 80` for
exactly that reason.** The doctrine table is not the guard. The next step's plan should carry a
written check of its own guards against the previous step's doctrine, because reading the table was
demonstrably not enough.
