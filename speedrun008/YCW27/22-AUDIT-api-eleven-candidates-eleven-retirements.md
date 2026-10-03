# 22 · `api/` AUDIT — eleven candidates, eleven retirements, and one real finding

**Written for:** Rohit. **Date:** 2026-10-03. ⛔ **Step `1.1` of
[`21-PLAN-TO-PRODUCTION.md`](21-PLAN-TO-PRODUCTION.md).**

```
api/        44 files · 19,498 lines · 20 writers · 42 tables · ⛔ 28 with no receipt
new tests   22  ·  mutations 10 caught · 0 survived
⛔ candidates 11 raised · 11 retired · 1 finding survived
```

---

## 0 · Why `api/` was first

`20-AUDIT-every-package/00-INDEX.md` ranked every package on the column that matters — **tables a
package writes that no receipt asks anything of** — and `api/` led it with **28**, over a package
with **zero receipts**, in the layer a customer actually touches. ⛔ And it had never appeared in
`S7`'s ranking at all, because *lines per receipt* with a **zero denominator** does not sort.

---

## 1 · ⛔⛔ Eleven candidates, and every one died on reading the code

This is the result, not a preamble to it. Each row was a plausible defect until the code or the
declaration beside it was read.

| | Candidate | ⛔ Why it died |
|---|---|---|
| 1 | `decisions` is written **only by an API route** and read by `executive/memory.py` — a backwards dependency | ✅ `_persist_decision_envelope` durably binds **the envelope the route returned**, content-addressed, `ON CONFLICT DO NOTHING` with a read-back in the same transaction and **fail-closed on any collision**. The API is the thing that answers, so it is the correct writer |
| 2 | `approvals_queue` is written and read **only by its own route module** — a queue nothing consumes | ✅ **Already declared.** `api_health.UNREACHED` holds `approval_routes.enqueue`, and the entry is sharper than my candidate: *"its docstring claims a caller it does not have… **the policy enforcement path does not exist**, so 'called from' is a sentence about a future"* |
| 3 | `policy_routes.evaluate` has no caller | ✅ declared, and the declaration calls it *"the honest half of the pair: it says future, and it is"* |
| 4 | `learning_objects` has **three writers** — an immutable proposal table | ✅ `api/learning_routes` only **UPDATES `state`** on an existing row, under `for update`, 404 if missing and 409 if not `human_review`. It never inserts a proposal |
| 5 | `api_keys` is written by **four** modules including `platform/auth.py` | ✅ minting, revocation and the key cache. Expected for a credential table whose reads go through one module |
| 6 | `card_events` has **eight** writers | ✅ an append-only event log fanning in from `deliver/`, `executive/` and `reason/`. Eight writers is the shape, not a defect |
| 7 | `agent_registry` — 8 external readers, no receipt | ⚠️ **true and left as a measurement.** A claim about it would have to be invented, and *a gate derived from an invented claim is a gate nobody reads* |
| 8 | `api/`'s **2 declared silences over 44 files** are thin | ⛔⛔ **MY OWN MIS-SIGNAL.** `api_health.py` explains it: **25 route handlers are deliberately excluded** — a `@router.get` function is wired by a decorator and has no Python caller by design, pinned by `tests/executive/test_a_call_resolved_by_name_is_not_a_call.py`. Auth dependencies too: `require_session_seat` has **8** `Depends()` references |
| 9 | `api/` has **zero receipts**, so its invariants are unguarded | ⚠️ **partly a filing question, and the filing is reasoned.** *"a deleted tenant leaves nothing behind"* imports `RETAINED_AFTER_ERASURE` **from `api/account_routes`**, and is filed under `platform` with its reason written: *"A claim about the SCHEMA, not a tenant… `platform/` owns migrations and the cascade"* |
| 10 | the **11 modules no test names** are untested | ⚠️ **the column does not say that**, and its caveat says so. When it ran for `context/`, **both** rows were live and reached |
| 11 | `workspace_routes.py` — 595 lines, 13 public functions, no test names it | ⚠️ same reading. A route module is decorator-wired; the column finds *no test of its own*, which is smaller and different |

> ⛔⛔ **Eleven raised, eleven retired. That is the audit's headline, and it is a finding about the
> MEASUREMENT as much as about `api/`:** the coverage table mis-signals for a package whose
> functions are wired by decorators and dependencies rather than calls. ⛔ **The unreceipted-tables
> column is the one that holds; the other two need their caveats read before their numbers are
> quoted.** `00-INDEX.md` is corrected in place.

---

## 2 · ⛔⛔ The one finding that survived — and it was never guarded

**`learning_objects` rows are write-once except for `state`, and nothing asserted it.**

⛔ `feedback/publisher.persist` states the contract in its own first line:

> *"Insert an **immutable** proposal at `state`. Idempotent on `learning_id`."*

and keeps it — an existing row is **never updated**, only reported as `reevaluated` (Observed or
Candidate, eligible again) or `unchanged` (*"later/terminal — never reopened"*). Measured:

```
every `update learning_objects` in the engine:
  genios_engine/api/learning_routes.py        set state = :st
  genios_engine/feedback/org_rule_ingest.py   set state = :st
⛔ statements touching proposed_value / semantic_hash / evidence / visibility:  NONE
⛔ tests asserting any of it:                                                   NONE
```

⛔ **The day somebody writes `set proposed_value = …`** — to "fix" a bad proposal, which is the
obvious thing to want — `semantic_hash` stops describing the row it is derived from,
`learning_transitions` points at an object that no longer says what it said when the transition was
logged, and the Atlas's *"immutable proposal storage"* becomes a sentence about the past.

### The repair · `tests/api/test_a_proposal_is_written_once.py` · 22 tests

`platform/table_coverage.WRITE_ONCE_TABLES` declares `{table: (mutable columns, why, mover)}` and
`illegal_column_updates()` measures every violation. Guarded both ways: a value column updated
fails, **and** a third updater fails even if it only sets `state`, because a third authority over
the learning ledger needs reading.

⛔ **The producer's half is BEHAVIOURAL, with a double that records what it was asked to run.**
A double that only checked the return value would not notice a `persist` that quietly rewrote a
row, so this one keeps every statement and the test asserts the second one never happens — for
each of the five states, plus the negative half (no existing row ⇒ it really does insert).

### ⛔ Why there is NO receipt, and that is deliberate

Production cannot answer this. A value rewritten in place leaves no trace unless `semantic_hash` is
recomputed, and recomputing it in SQL would mean reimplementing the canonical serialisation in a
second language. ⛔ **Same decision the `context/` audit took for `graph_nodes`** — *a gate derived
from an invented claim is a gate nobody reads.* The absence is declared in the table's own `why`.

---

## 3 · ⛔ One mutation survived, and removing the code was the answer

`M6` turned a **paren-depth-aware** comma split back into a plain one, and every test still passed.

⛔ The reason: an identifier filter (`fullmatch [a-z_][a-z_0-9]*`) drops the wreckage either way —
`set active = false, expires_at = least(expires_at, :at)`, which `feedback/reset.py` really writes,
yields a third fragment `:at)` that the filter rejects. **The paren-awareness changed no answer I
could construct.**

> ⛔ *A mutation that survives because something else catches it is a guard nobody is checking* —
> and **a branch whose mutation cannot fail is complexity, not safety.** The depth-split was
> **removed**, the filter is named in the docstring as the safeguard, and the mutations that matter
> now land: removing the filter is **caught**, loosening it to `re.match` with `:` is **caught**.

⛔ This is the second time in two days that the honest answer to a surviving mutation was *delete
the branch* rather than *test it harder*.

---

## 4 · Doctrine

| Rule |
|---|
| ⛔ **a coverage column mis-signals for a package whose functions are decorator-wired** — read the caveat before quoting the number |
| ⛔ **eleven retirements is a result**, not a failed audit |
| ⛔ **a branch whose mutation cannot fail is complexity, not safety** — delete it and name the real safeguard |
| ⛔ **a test that reimplements the parser proves the copy, not the code** — call the shipped function |
| ⛔ **a double that only checks the return value cannot see a quiet write** — record the statements |
| ⛔ **no receipt is a decision too**, and it gets written down beside the claim |
| **a third writer is a finding even when it writes the right column** |

---

## 5 · What `api/` leaves open

| | |
|---|---|
| ⚠️ **`agent_registry`** | 8 external readers, no receipt. Left as a measurement until a module states a claim about it |
| ⚠️ **28 unreceipted tables** | measured split: **13** have readers outside `api/` · **13** are read only **inside** `api/` — a route writes and a GET serves it, which is legitimate · ⛔ **2 have no reader at all** (`card_feedback_revisions`, `domain_requests`) **and both are already declared** in `table_coverage.UNREAD_WRITES`. ⛔ The first draft of this row said *"15 … read inside"*, which was neither number |
| ⛔ **`R15`** | `domain_requests` is one of the three tables that survive a `/reset` and is written by `api/expertise_routes.py`. Rohit's — `HANDOFF-HARSH.md` §H8.4 |
| ⛔ **the policy enforcement path** | declared absent by `api_health`, and it is `D2`'s other half: **794 actions, 410 want `requires_approval`, `authority_rules` has ZERO rows** |
