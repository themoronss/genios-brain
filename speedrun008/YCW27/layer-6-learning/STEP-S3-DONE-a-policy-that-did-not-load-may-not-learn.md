# S3 — DONE · an empty prohibition list is a decision; a NULL one is an absence

**Unit:** `M14.C2.S3` · **Owner:** me · ✅ **2026-10-02** · **40 tests · 8/8 mutations caught**
**Atlas:** Layer 7 gap **#10**, *"loaded policy is weaker than stored policy"* — the residue
**Plan:** [`08-PLAN-v2-from-the-atlas.md`](08-PLAN-v2-from-the-atlas.md) §4

---

## 1 · What was wrong — a fail-OPEN on an authority list

`learning_policies.blocked_targets` and `.blocked_subject_prefixes` are nullable `jsonb`
(`migrations/0045`), and the orchestrator's seed writes `cast('[]' as jsonb)` with this comment:

> *"Seeded EMPTY rather than NULL: an empty prohibition list is a decision ("nothing is blocked"),
> NULL is an absence. **Keeping them distinct is what lets the guard below tell a deliberate empty
> policy from one that failed to load**."*

⛔⛔ **There was no guard below.** `_as_tuple` returned `()` for `None`, for a dict, for a bare
string and for a list of integers alike:

```python
def _as_tuple(value) -> tuple[str, ...]:
    """A jsonb prohibition list as a tuple, refusing to silently invent an empty one.

    A NULL here on a revision the tenant actually authored means the policy did not load, and
    treating that as "nothing is blocked" is the failure mode this whole field guards against.
    """
    if value is None:
        return ()                                   # ⛔ exactly what the docstring forbids
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value if v)    # ⛔ coerces a malformed list into a valid one
    return ()                                       # ⛔ and swallows everything else
```

> ⛔ **The database kept the two apart and the load collapsed them one line later.** A tenant whose
> *"never learn about these targets"* list failed to read was indistinguishable from a tenant who
> blocks nothing, and `governance.preflight` returned **`admitted`** for the exact target they meant
> to forbid.

⛔ **And the function could not keep the promise in its own docstring.** It received only the value,
never the revision, so it could not tell an absence from a decision. *A docstring can promise a
behaviour the signature makes impossible* — and the fix therefore could not live in it.

## 2 · The Atlas's required repair, verbatim

> *"Store and load `blocked_targets` and `blocked_subject_prefixes` losslessly for every revision;
> **unknown/malformed policy fields block the run rather than defaulting to permissive empty
> tuples**."*
>
> Acceptance: *"round-trip fixtures prove both block lists survive seed/load/restart and preflight
> rejects the exact target/prefix under the loaded revision."*

⛔ The `SELECT` half was already fixed before this step — both columns are selected, with a comment
recording that omitting them meant *"a tenant's 'never learn about these targets' list was loaded as
empty on every run."* **The residue was the load, and it was the half that mattered.**

## 3 · Built bottom-up, five units, lowest layer first

### ⛔ Unit 1 · `contracts/learning.py` — make the absence REPRESENTABLE

`blocked_targets: tuple[str, ...] = ()` has **no third state**. A tuple cannot say *"empty because
nobody blocked anything"* and *"empty because I could not read it"*, and that is why the collapse
was invisible. So the contract gained one field:

```python
PROHIBITIONS_LOADED    = "loaded"      # both columns were JSON arrays of non-empty strings
PROHIBITIONS_ABSENT    = "absent"      # a STORED revision had NULL where a list belongs
PROHIBITIONS_MALFORMED = "malformed"   # a STORED revision held something else entirely

prohibitions_state: str = PROHIBITIONS_LOADED        # default: trusted
@property
def prohibitions_loaded(self) -> bool: ...
```

| Decision | Why |
|---|---|
| default `"loaded"` | every policy **authored in code**, including the protective seeded default, is trusted by construction. ⛔ Only a policy *reconstructed from a row* can be untrustworthy, and only the loader can know |
| the constructor does **not** refuse an untrusted policy | ⛔ it must be constructible in order to **represent** the failure. The refusal belongs at the gate |
| an **unknown** state raises | it would make `prohibitions_loaded` lie in the permissive direction |
| module constants, not `ClassVar` | `LearningPolicy` is `slots=True`, and this module already keeps its vocabularies at module level (`LEARNING_VERSION`, `TERMINAL_LEARNING_STATES`) |

⛔ **Safe to add at all only because `LearningPolicy` is NOT content-addressed** — `policy_key` is
`f"policy:{org}:{revision}"`, derived from two fields. `LearningObject` is the hashed one, and M14's
crosscheck had already recorded why a new enum member there would change identities already minted.

### ⛔ Unit 2 · `orchestrator` — a resolver that reports WHICH case

```
a JSON array of non-empty strings  → loaded      the only trustworthy shape
None                               → absent      a stored revision that did not load
anything else                      → malformed   a dict · a bare string · a number ·
                                                 a list containing a non-string ·
                                                 a list containing an EMPTY string
```

⛔ **The two bad shapes fail in OPPOSITE directions, which is why neither may be repaired
silently:** a non-string can never equal a target value, so `[1, 2]` blocks **nothing**; and
`"any-subject".startswith("")` is always true, so `[""]` blocks **everything**. The old
`str(v) for v in value if v` turned the first into a quiet fail-open and dropped the second.

And `_prohibitions(targets, prefixes)` takes the **worse** of the two states and returns **empty for
both** — *an untrusted list is not partially usable*; a half-populated policy is the shape somebody
later reads as complete.

### ⛔ Unit 3 · `governance.preflight` — the gate all three producers share

```python
if not policy.prohibitions_loaded:
    return PreflightResult(False, f"policy_prohibitions_{policy.prohibitions_state}")
```

⛔ **Placed BEFORE the two block-list checks.** After them it would never be reached for an allowed
target: the empty list admits, `preflight` returns `admitted`, and the refusal never happens.
`test_the_prohibitions_gate_runs_before_the_block_list_checks` asserts the order from the source.

⛔ **And it belongs here because all three producers call this exact function** —
`orchestrator.run_learning`, `brain_pipeline.admit_proposals` and `org_rule_ingest
.run_org_discovery`. `brain_pipeline`'s own header says it reuses *"the same preflight, the same
`govern()`"*, and only one of the three passes through `run_learning`.

### ⛔⛔ Unit 4 · `run_learning` — blocked BEFORE the weekly claim, and the order is the whole point

```python
if not policy.prohibitions_loaded:
    return {"org_id": org_id, "skipped": f"policy_prohibitions_{policy.prohibitions_state}",
            "policy_revision": policy.revision}

run_id = _claim_week(conn, org_id, policy, now)        # ← must come AFTER
```

> ⛔⛔ **A fail-closed placed after the claim converts a policy problem into a LOST WEEK.**
> `_claim_week` inserts `on conflict (org_id, week_key) do nothing`, so a claimed week stays
> claimed: every later heartbeat answers `already_ran_this_week`, and **a policy row somebody fixed
> on Tuesday would not be learned from until the following Monday.** That is strictly worse than
> the fail-open it replaces.

⛔ The harm only appears on the **second** tick, so no behavioural unit test would see it —
`test_run_learning_blocks_before_it_claims_the_week` asserts it on the **AST**, and
`test_the_claim_is_still_idempotent_on_conflict` pins the premise so the argument cannot rot.

### ⛔ Unit 5 · `run_learning_sweep` — the reader, without which this is a silent stop

It returned `{orgs, passes, skipped}`. ⛔ **A tenant who turned learning off, a tenant whose week was
already claimed, and a tenant whose transaction raised were the same number.**

```python
return {"orgs": len(orgs), "passes": passes, "skipped": skipped,
        "skipped_by_reason": by_reason}          # ⛔ additive — the existing keys are untouched
```

⛔ **A refusal nobody can see is worse than the fail-open it replaces**, because at least a
fail-open is loud in its consequences. *The reader is half the unit.* The `except` still counts a
crash as a skip — one tenant's failure is not the rest's — but records the **type**, because
`{"error": True}` hid a `NameError` in the executive sweep for 15 days.

## 4 · ⛔ The two refusals are now told apart by name

```
loaded block list containing "organization"   → preflight: target_blocked              ← a DECISION
a stored revision with NULL                   → preflight: policy_prohibitions_absent  ← an ABSENCE
                                                 ⛔ before this change: ADMITTED
```

## 5 · The mutation run — baseline first, and 8/8

```
✅ baseline: 40 passed

  M1 · delete the preflight gate entirely                  ✅ CAUGHT (4 failed)
  M2 · claim the week BEFORE the gate                      ✅ CAUGHT
  M3 · NULL becomes "loaded" again (the old fail-open)     ✅ CAUGHT (5 failed)
  M4 · coerce non-strings instead of refusing              ✅ CAUGHT (4 failed)
  M5 · a bad column no longer poisons the other            ✅ CAUGHT
  M6 · the sweep stops reporting WHY                       ✅ CAUGHT (3 failed)
  M7 · the seed writes NULL instead of []                  ✅ CAUGHT
  M8 · the contract accepts an unknown state               ✅ CAUGHT

✅ baseline again: 40 passed            8 caught · 0 survived
```

## 6 · ⛔ A false finding I nearly wrote, and the check that stopped it

While reading `load_or_seed_policy` I noticed `knowledge_requires_review` is **selected and then
overwritten with a literal `True`**, and started writing it up as *"a selected column that
configures nothing — a setting that lies."*

⛔ `migrations/0045_l6_learning.sql:37`:

```sql
constraint learning_policies_knowledge_review_locked check (knowledge_requires_review)
```

…and the table comment: *"knowledge_requires_review is **CHECK-locked true** — it can never be
disabled."* **It is an invariant enforced in three places** — the database CHECK, the contract's
`raise ValueError("knowledge_requires_review cannot be disabled")`, and the loader's literal — and
the selected column is **redundant, not misleading**, because it can only ever be `true`.

> ⛔ **Sixth time in this programme that verifying a suspicion before writing it prevented a false
> finding.** *A redundant read is not a lie; a lie is a read whose value could differ and does not
> matter.*

## 7 · Blast radius, and what I could not measure

| | |
|---|---|
| **can a stored row have NULL today?** | ⛔ **Unknown from this checkout.** `0045` creates both columns nullable; the only `INSERT` is the seed, which writes `[]` — **but the seed's comment implies it was changed**, so legacy rows written before that change could hold NULL |
| **so the fail-closed is a SKIP, not an exception** | a legacy row yields `{"skipped": "policy_prohibitions_absent"}` and **does not burn the week**. When somebody backfills `[]`, the tenant resumes on the next tick with no further action |
| **the read-only query that would settle it** | `select revision, blocked_targets is null, blocked_subject_prefixes is null from learning_policies` inside `set transaction read only` |
| **a minor residue** | the sweep's `except` still writes no log line; the reason now reaches the heartbeat response but not the logs. ⛔ Adjacent — *new unit, not a silent fix* |

## 8 · Verify

```bash
.venv/bin/pytest tests/feedback/test_a_policy_that_did_not_load_may_not_learn.py -q    # 40 passed
.venv/bin/pytest tests/feedback tests/test_learning_governance.py \
    tests/test_learning_orchestrator.py tests/test_extraction_envelope_and_vocab.py \
    tests/contracts tests/platform/test_every_package_says_what_it_does_not_call.py -q # 931 passed
.venv/bin/pytest -q                                                                   # FULL suite
```

## 9 · Doctrine

| Rule |
|---|
| ⛔ **an empty list is a decision and a NULL is an absence — a type with two states cannot hold three** |
| ⛔ **a fail-closed placed after the claim converts a policy problem into a lost week** |
| ⛔ **a refusal nobody can see is a silent stop, and worse than the fail-open it replaces** |
| ⛔ **two malformed shapes can fail in opposite directions — neither may be repaired silently** |
| ⛔ **an untrusted list is not partially usable** |
| ⛔ **a docstring can promise a behaviour the signature makes impossible** — the fix belongs where the knowledge is |
| **the gate goes where every producer passes, and the skip goes where the cost is paid** |
| **a redundant read is not a lie** — verify a suspicion before writing it up |
