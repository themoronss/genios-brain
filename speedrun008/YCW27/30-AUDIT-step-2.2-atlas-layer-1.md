# ⛔⛔ AUDIT · STEP 2.2 · ATLAS LAYER 1 — five claims, two receipts, and three holes in my own guards

**2026-10-04.** Five open claims. ⛔ **Two scorecard rows turned out to carry false evidence**, one
claim was partly expired, and measuring the two that were true found **larger findings underneath
both**. ⛔⛔ And three of my own guards had holes that only mutation found.

```
units        U01 L1-08 declaration · U02 L1-09 receipt 47 · U03 L1-01 receipt 48 · U04 paperwork
receipts     46 → 48   both correctness, both L1, both org-scoped
tests        48 new    15 + 17 + 14, plus 2 from a per-claim parametrised guard
mutations    51 caught · 1 surviving BY DESIGN (recorded in place) · 3 REAL HOLES found and closed
claims       5 re-checked · 2 rows had FALSE evidence · 1 partly expired · 2 Rohit's · 0 unmeasured
```

⛔ **NEITHER RECEIPT HAS EVER BEEN EXECUTED.** No database URL in this checkout, and the platform
suite drives receipts through a fake engine. Everything below is about the query they render and
the conditions under which they refuse — never a number they returned. That is **P1** of this
programme's definition of production level, unmet for all 48.

---

# PART 1 · THE TWO ROWS WHOSE EVIDENCE WAS FALSE

## ⛔⛔ L1-08 — *"zero declare a `visibility` field"* · all three declare one

The Atlas said the three capture contracts *"do not **require** visibility"*, which is right. The
scorecard's evidence line said *"all three measured: **zero** declare a `visibility` field"*, which
is a different claim and false:

| contract | field | required? |
|---|---|---|
| `RawObject` | `visibility: Any = None` | no — ⛔ and typed **`Any`**, not `Visibility` |
| `SourceEvent` | `visibility: Visibility \| None = None` | no |
| `GatedEvent` | `visibility: Visibility \| None = None` | no |

**Optional is not absent, and the two have different fixes.** Making the field required changes
every constructor and test double; closing the *consequence* is a different job, and it is already
done — four times over.

### ✅ Four layers refuse before `None` can reach a reader

```
1  landing/normalize.py   visibility=(getattr(raw,"visibility",None) or derive_visibility(…))
2  gate/gate.py           None → re-derive → still None: PARK "visibility_unknown"
3  parked/recapture.py    on re-drain, still None → STILL_BLOCKED, never aged out
4  the schema             5 of 6 visibility columns NOT NULL; the 6th pairs a nullable jsonb
                          with visibility_scope text NOT NULL DEFAULT 'private'
```

The gate states the doctrine itself: *"An event whose audience no derivation rule can name must not
publish under a guessed one… by Layer 2 the recipient list is gone, so **this is the last gate that
can still refuse**."*

### ⛔⛔ So the finding is the five readers that do not know that

| site | what a MISSING audience means there |
|---|---|
| `context/framing/timeline.py` | ⛔ `e.visibility is None or e.visibility.can_view(…)` → **shown** |
| `context/framing/headline.py` | ⛔ the same shape over facts → **included**, and then `narrowest()` computes an audience from a set that already contains it |
| `context/fact_visibility.py` | ⛔ `visibility is None or scope != PRIVATE` → read as **not private** |
| `context/situation_bso.py` ×2 | ⛔ `visibility or Visibility(scope="org", …)` → **org-wide** |

**The safety of a privacy default rested on one `if` in one file, and the five readers that depend
on it did not know it existed.** A new ingestion path that skipped the gate — a backfill, an
import, an MCP write, a test double promoted to production — would make all five permissive at
once, in a layer that by its own account can no longer re-derive an audience.

### ⛔ Found by AST. Grep found five of the eight sites

The sweep found **three more**: `correlation_people.py`, `graph_store.py` and a third in
`situation_bso.py`, all `visibility_principals or ()`. ✅ And measuring rather than assuming showed
them **fail-closed**: `Visibility(scope="private", principals=[]).can_view(...)` is `False` for
every caller, org member or not. **An empty principal list under `private` means NOBODY.** That is
asserted in the guard, not reasoned about in a comment.

**`MISSING_VISIBILITY_SITES`** declares all six modules with a **per-module site count**, so a
second site added to an already-declared module cannot slip through on the strength of the first.
**`MISSING_VISIBILITY_REFUSALS`** declares the four layers, each asserted.

## ⛔ L1-07 — *"no roles contract in `contracts/`"* · roles are typed

| half of the claim | verdict |
|---|---|
| *typed* | ⛔ **EXPIRED.** `ExtractionResult.roles: list[RoleAssertion]`, and the contract records that `roles` was `list[str]`/`list[dict]` *"until this date"* |
| *leave L1* | ✅ **declared by design, with the owner named**: *"typed role candidates (roles need the extraction the envelope feeds; **L2's b3-3 prompt owns them**)"* |
| *mandatory* | ✅ **still true** — `Field(default_factory=list)`. ⛔ And it should be: a message naming nobody has no role to carry, so requiring one would drop the message. **Rohit's** |

---

# PART 2 · THE TWO THAT WERE TRUE, AND WHAT WAS UNDERNEATH THEM

## ⛔⛔ L1-09 — the contract promises something nothing checked, and five of its fields die at the boundary

✅ The claim is exact: `GatedEvent.coverage_ready: bool | None = None`, column nullable. ⛔ But the
field's own comment states a **rule** and the field one along states a **promise**:

> *"A dead field on a contract is worse than a missing one: **it invites a consumer to trust a seam
> that carries nothing**, and `None` reads as 'unknown' exactly where a caller most wants a yes."*

> *"`None` means no tagger ran (a pre-S4 row); **a freshly gated event always carries a real
> bool**."*

**Receipt 47** asks the promise as a question. ⛔ The horizon is the whole design: the comment says
an **old** row is legitimately null, so an unbounded query would be red for ever and tell nobody
anything. Four sweep ticks, derived from `sync_interval_hours`. And it asks for `is null`, never
`= false` — ⛔ `false` is an **answer** (this domain is not covered); only `null` means nobody
looked.

### ⛔⛔ And five of the contract's twenty-one fields break its own rule

Set on the boundary object, then **stored in no column, absent from the declared envelope key set,
and read by nothing**:

| field | state |
|---|---|
| **`degraded_compile`** | ⛔⛔ **the worst, because its own comment says this defect was fixed.** It records that *"`tag_domains` computed it, the trace row recorded it, and **the boundary object dropped it** — so L2… could not tell a full compile from a degraded one."* The fix put the field on `GatedEvent` **and stopped**. It is in no migration, not in `ENVELOPE_KEYS`, absent from `contracts/signal.py` — so L2, which reads the **stored** signal, still cannot tell. The same defect one layer along, now wearing a comment that reads as closed. ⛔ And `coverage_ready`, the FIRST half of the same answer, **is** a column — half the verdict crosses the boundary and half does not |
| `prepared_content_ref` | ✅ **already declared, and well**, by a GAP FLAG in `contracts/signal.py`. ⛔ Whose own claim has **half expired**: it says *"no `payload_ref` / `prepared_content_ref`"* and `payload_ref` is now a column with readers |
| `structured_fields` · `linkage_hints` · `availability_marker` | ⛔ zero attribute loads anywhere. Each has a **same-named local or function that IS used**, which is what made a first sweep report them alive |

### ⛔ A test's own label was the false witness

`tests/capture/test_g56_verify_probes.py` headed its probe *"D9 — degraded_compile survives to the
published **envelope**"* while asserting `gated.degraded_compile` — the object one layer **earlier**
than the envelope it names, and the flag is not in `ENVELOPE_KEYS` at all. The assertion was right
and the heading was not. Corrected in place.

### ⛔ How the sweep errs, stated because a resolver that hides its direction reads as a proof

It counts attribute loads named `X` anywhere, which **over-counts** — a load may be on another
object. So **0 proves never-read**, and more than 0 proves nothing. Four of the five are proven by
the sweep; `degraded_compile` shows two loads and both were **hand-checked** to be
`outcome.domains.degraded_compile`, the tagging result. ⛔ A first version instead *excluded the
carrying module*, **under**-counted, and produced two false positives.

## ⛔ L1-01 — the number was wrong, and the registry's own example had expired

✅ The registry is **honest**: `BUILDABLE_SOURCES` is a derived view over one descriptor per source,
`tests/test_source_registry.py` enforces the invariants that let four hand-maintained lists drift,
and `L1.1-U2` exists so the connect screen renders one answer. This is a stated product position,
not a gap.

⛔⛔ **But the scorecard said ~7 distinct providers and it is 9.** The descriptor carries a declared
`aliases` field. Folding by **it**:

| canonical | declared aliases | capability |
|---|---|---|
| `gcal` | `calendar`, `google_calendar` | calendar |
| `gdrive` | `drive`, `google_drive` | document_store |
| `gmail` · `hubspot` · `linear` · `notion` · `postgres` | — | communication · crm · task_tracker · document_store · product_usage |
| ⛔ `database` · `mysql` | — | **None** |

The first two folds are right. **`database`, `mysql` and `postgres` are three separate descriptors
with three different capabilities** — *the fold was done by reading the names rather than the field
that declares it*, the same mistake `2.1` made twice with module filenames.

### ⛔ Two findings fell out of measuring it properly

1. ⛔⛔ **`database` and `mysql` are buildable with `capability = None` and `object_types = 0`.** A
   tenant can connect one, see the connect screen report success, and contribute to no pack's
   coverage while mapping no objects. This is the **inverse** of every drift the registry was built
   to close — its docstring lists sources that *"carried a coverage capability but NO family"*, and
   nobody asked the other direction. **Receipt 48**, with the set derived from the descriptors.
2. ⛔ **The registry's own example had expired.** *"`hubspot` advertises the `crm` capability that
   the `sales` pack REQUIRES, while no connector can be built for it"* — and `hubspot` is buildable
   now. The shape survived through **eleven** other sources (`salesforce` is also `crm`) and the
   subject did not. ✅ The corrected sentence **names nobody**, because naming one is how it went
   stale, and the eleven are **counted in a test** instead.

---

# PART 3 · ⛔⛔ THREE HOLES IN MY OWN GUARDS, EACH FOUND BY MUTATION

This is the part worth reading. Every one passed its own suite first.

| # | the guard | ⛔ the hole | what it took |
|---|---|---|---|
| **1** | `U01`'s grade checks | `test_the_open_sites_are_graded_open` existed and **its converse did not** — so regrading a fail-closed site, *in either direction*, passed everything. The dangerous direction is ⛔→✅: it would hide the finding | a mutation flipping one grade |
| **2** | `U02`'s *"the rule is still in the file"* | ⛔⛔ **the declaration QUOTES the rule as its own justification**, so deleting the original sentence left the quote behind and the check passed. **A declaration that cites its source satisfies the test that the source exists.** Now the rule must exist *outside* the block that cites it | a mutation deleting the original |
| **3** | `U03`'s registry warning | the warning I added names *"`database` and `mysql`"*, and nothing checked those names against the measurement. ⛔ **So my fix for a stale comment would have introduced one, two paragraphs below it, in the file whose expired example this unit exists to correct** | a mutation giving `mysql` a capability |

### ⛔ And four more weak checks, each exposed by a mutation that did not do what its label said

| the check | ⛔ why it was weak |
|---|---|
| `assert "derive_visibility" in source` | a substring. `import derive_visibility as _unused` satisfies it while nothing calls it. Now an AST call check |
| `assert "FAIL-CLOSED" in verdict` | the **word** is not the explanation — stripping the explanation left the word. Now it must name the mechanism |
| `assert len(what) > 40` | ⛔⛔ **length is not content — and `2.1` had already replaced an `assert len(why) > 80` for exactly this reason.** I wrote the same guard again. *A rule learned in a doctrine table is not a rule applied* |
| `any(token in text for token in (...))` | an OR over a hand-listed set; ⛔ this one survived from `2.1` too |

### ⛔ One mutation survives on purpose, and it is recorded where the decision was made

Weakening the `4-not-null` statement from *"five of the six columns are NOT NULL"* to *"are
constrained"* passes. ⛔ **Tightening it would mean asserting a COUNT in prose** — and `2.1`
produced the rule that *a comment's count ages faster than its claim*. So the prose is deliberately
the weaker guard: the fact is measured independently, from the migrations, by a test that requires
at most one nullable column and requires that one to sit beside a fail-closed default. The comment
in the test says so, so the next reader does not "fix" it.

⛔ **Its cousin in `U03` was NOT left surviving**, and the distinction is the point: there the
docstring is where somebody goes to **add a source**, and it is the only place they would learn the
rule at the moment they could break it. A receipt catches that after a tenant has connected; the
docstring catches it before the descriptor is written.

---

# PART 4 · THE FIVE, SETTLED

| claim | state after 2.2 |
|---|---|
| **L1-01** | ⚠️ true · ⛔ **number corrected 7→9** · **receipt 48** · the expired example fixed |
| **L1-07** | ⚠️ **partly expired** — roles ARE typed; *mandatory* is **Rohit's** |
| **L1-08** | ⚠️ true at the contract · ⛔ **the evidence line was false** · consequence **closed at four layers** · the five permissive readers **declared** |
| **L1-09** | ⛔ true · **receipt 47** · and **five carried-dead fields declared**, one of them a defect its own comment calls fixed |
| **L1-10** | **partly expired** · a 4-vs-6 state lifecycle is **Rohit's** |

```
5 claims · 2 rows had FALSE evidence · 1 partly expired · 2 Rohit's · ⛔ 0 unmeasured
```

---

# DOCTRINE THIS STEP PRODUCED

| rule |
|---|
| ⛔⛔ **a declaration that cites its source satisfies the test that the source exists** — require the source outside the block that quotes it |
| ⛔⛔ **a grade needs its converse guarded** — "the open ones are open" without "the closed ones are closed" lets the finding be hidden |
| ⛔⛔ **the fix for a stale comment can be a stale comment** — check the names in your correction against the measurement |
| ⛔ **optional is not absent** — they are different facts with different fixes |
| ⛔ **a one-sided resolver must say which side it errs on** — over-counting proves nothing; a zero proves everything |
| ⛔ **excluding the carrying module under-counts; counting every same-named attribute over-counts** — pick one and hand-check the rest |
| ⛔ **a same-named local or function makes a dead field look alive** |
| ⛔ **a law enforced at the write is invisible at the read** |
| ⛔ **a rule learned in a doctrine table is not a rule applied** — `len() > N` came back one step later |
| ⛔ **a prose guard is belt; the measurement is braces** — leave it weak only where the fact is independently measured, and never where the prose is read at the moment the rule could be broken |
