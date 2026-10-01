# Step 6 — ✅ DONE · 410 approvals nobody can attribute

> **Unit** U2 · **10 tests · 6 mutations, one of which found the same half-guard twice**
> ⛔ **And the plan for this unit was wrong. The measurement is what corrected it.**

---

## 1 · What the plan said, and why it was wrong

`02-PLAN.md` U2 said:

> *"**UNBLOCKED · safest.** Eight tests already pin the hard part … the thinking is done; only the
> wiring is missing. Build: `sweep.plan_commitments` resolves the approver beside the owner.
> ⛔ Delete the `assignment.resolve_approver_seat` entry from `unreached.UNREACHED` in the SAME
> commit."*

⛔ **Measuring it refuted "only the wiring is missing", twice over.**

    execution_actions          794 rows
      requires_approval        410   ⛔ 52% of every action this layer has ever planned
                                        (182 · 121 · 107 across the three orgs)
    authority_rules              0   ⛔ ZERO rows
    authority.* graph facts      0   ⛔ ZERO

    approver column on execution_actions   ⛔ does not exist
    approver column on executions          ⛔ does not exist

So the wiring is blocked **twice**:

1. **No place to put the answer.** Neither table has an approver column and neither contract has
   the field, so consuming an answer needs a contract change **and** a migration — and
   `0186`–`0190` have never run (H1).
2. **No answer to put there.** `authority_rules` is empty, so `AuthorityView.resolve` returns
   `no_authority_rule` for every subject and `resolve_approver_seat` correctly returns `None` for
   every call. The column would be filled by `None` on all 410 rows.

⛔ **And `unreached.py` had already said so.** Its mover: *"That needs the org to have published
authority rules at all — until it has, the honest answer is None and the card is right to say only
that sign-off is needed."*

> ⛔ **The plan told me to delete that declaration.** Doing it would have traded the only written
> record of *why* nobody can be named for a function call that still names nobody.

**Twelfth time in this programme** that a measurement corrected a plan before code was written —
and the first time the wrong plan was **mine from the previous step**.

## 2 · So what was built instead

The half that needs no migration and no rules: **make the gap legible.**

| Artifact | What |
|---|---|
| `platform/receipts._UNATTRIBUTED_APPROVALS_SQL` | the query and the reasoning for every line |
| **receipt #32** · L4 | *"every action that needs sign-off can name who signs"* — ⛔ **RED at 410** |
| `executive/unreached.py` | the entry **STRENGTHENED, not deleted** — now carries 410 / 794 / zero rules and names **both** blockers |
| `tests/platform/test_an_approval_nobody_can_attribute.py` | 10 tests |

### The query is a conjunction, and an in-force rule is not merely a row

```sql
select count(*) from execution_actions a
 where a.requires_approval
   and not exists (select 1 from authority_rules r
                    where r.org_id = a.org_id
                      and r.approver_node_id is not null      -- a threshold with no approver
                      and r.valid_from  <= now()              -- not one starting next quarter
                      and (r.valid_until is null
                           or r.valid_until > now()))         -- ⛔ not an EXPIRED one
```

⛔ **`requires_approval` on its own is HEALTHY** — it is the autonomy gate
(`contracts/execution.py:233`) doing its job, and 410 gated actions is the layer being careful. The
defect is a gated action **in an org that holds no rule capable of naming an approver**. A receipt
that counted gated actions would be red for correct behaviour.

⛔ **Three ways to hold a rule and still name nobody**, each excluded. Counting rows alone would go
green for a tenant whose only rule lapsed last year.

### ⛔ Zero is a TRUE pass here — the opposite of receipt #31

`#31` returns **-1** for an empty window, because an era that produced no runs is a dead pipeline
and green there is a lie. `#32` has no sentinel: **no gated actions genuinely means no requirement
is unattributed.** The two receipts disagree about emptiness **on purpose**, and
`test_zero_is_a_true_pass_here_and_the_contrast_with_the_era_receipt_is_deliberate` pins the
difference so a later reader does not make one consistent with the other.

## 3 · Scenario → result

| Scenario | Result |
|---|---|
| gated actions, no authority rule | ⛔ **FAIL** — `org_66bca…` 182 · `org_e97e86…` 121 · `org_2f1bc0…` 107 · **all orgs 410**, per-org sum exact |
| one in-force rule with an approver is published | → **0, PASS** |
| the only rule has `approver_node_id` null | still FAIL — it names nobody |
| the only rule expired yesterday | still FAIL — not enforceable |
| the only rule starts next quarter | still FAIL — not in force |
| no action requires approval | **0, PASS** — a true pass, not a vacuous one |

## 4 · ⛔ The mutation that found the same half-guard as U1 — in a different file

| | Mutation | Caught? |
|---|---|---|
| **M1** | **`and not exists (` → `and false and not exists (`** | ⛔ **SURVIVED all 10 tests** |
| M2 | drop the `valid_until` check (count expired rules as coverage) | ✅ |
| M3 | `approver_node_id is not null` → `true` | ✅ |
| M4 | count all actions, not only gated ones | ✅ |
| M5 | ⛔ **delete the `unreached` entry** — what the plan told me to do | ✅ **2 tests** |
| M6 | strip the number out of the mover | ✅ |

⛔ **M1 is U1's M2 wearing different clothes.** On production it turns 410 (red) into 0 (green).
It survived because the test asserted `"not exists" in sql` — and after the mutation that
substring is **still there**, with a constant in front of it making the whole subquery irrelevant.

> ⛔ **Presence is not effect.** Twice in two units, the same shape: a test proved a clause was
> *in* the query and nothing proved it was *doing* anything.

Two fixes, because the first is specific and the second generalises:
- the gate and the conjunction must be **contiguous** — `where a.requires_approval and not exists (`
- `test_no_tautology_can_neutralise_either_half` rejects `and false`, `or true`, `and true`,
  `where false`, `where true` and `1=1` anywhere in the query

## 5 · ⛔ And then the suite caught me writing the pattern this codebase had already rejected

`U1`'s test asserted `len(receipts(None)) == 31`. This receipt broke it, so I "fixed" it by moving
the global literal into **this** unit's test as `== 32` and writing a docstring saying it now lived
in exactly one place.

⛔ **The full suite then failed on a test I did not know existed:**
`tests/platform/test_activation_changes_the_pass.py::test_the_l4_receipt_count_grew_by_exactly_three`
— which pins **L4's own** count, and whose docstring had already explained the whole thing:

> *"SCOPED TO L4, AND THAT IS STRICTER THAN THE GLOBAL TOTAL IT REPLACED, NOT LOOSER. The original
> pinned `len(R.receipts(...)) == 26`, so the very next layer to add a receipt of its own broke a
> test about L4 — and the cheap fix for that is to bump the number, **which is how a decision gate
> becomes a rubber stamp.**"*

**My "one global literal" was the rejected design, verbatim.** And
`test_no_receipt_claim_is_duplicated` — the test I had just written into U1's file as a
replacement — **already existed in the same file, eleven lines below the one that failed.**

### ⛔ How I convinced myself there was no canonical guard

I grepped `len(receipts(` across `tests/`, found only my own two, and wrote *"canonical jagah thi
hi nahi"* — there was no canonical place. It existed, counted **per layer**, and the grep could
therefore not see it.

> ⛔ **A grep that finds nothing is not evidence that nothing is there.** Thirteenth instance in
> this programme, and the fourth to be found by the full suite rather than by the files I was
> editing.

### What it is now

| | Before | After |
|---|---|---|
| L4's count | `== 6` | `== 7`, **with the decision written into the docstring** — what the seventh receipt is, what it measured, and that the gate caught its own author |
| U2's test | a global `== 32` literal | asserts only that **its** receipt is the L4 one that moved the number |
| U1's test | a duplicate claim-uniqueness check | asserts only that the era receipt is in the list |

⛔ **The gate worked on the person who did not know it existed, which is the only real test of a
gate.** Two targeted test runs would never have found it: `pytest tests/platform/` was green on my
broken design, because the file that failed is the one I had not thought to run.

## 6 · What is still blocked, and by what

| | Blocked on | Who |
|---|---|---|
| the approver **column** + contract field + migration `0191` | ⛔ `0186`–`0190` have never run | **Harsh** · H1 |
| an answer to put in it | ⛔ the org has published **zero** authority rules | **Rohit** |
| the card actually naming an approver | both of the above | — |

⛔ **Receipt #32 goes green the moment one in-force rule with an approver is published** — before
any wiring exists. That is deliberate: it measures whether the tenant *can* attribute a sign-off,
which is the prerequisite, and the prerequisite is the thing that has not moved.
