# 🤔 Decisions — five, each with its measurement already done

None of these is an engineering question. Each is *"here is the number, what do you want."*

---

## D1 · Flip the 24 authored situations that are stuck at `draft`?

**Measured, in repo, no database needed:**

| domain | situations | `draft` |
|---|---|---|
| Admin | 34 | **8** |
| Sales | 15 | 0 |
| **Customer Support** | 20 | **16** |
| | **69** | **24** |

⛔ **What a `draft` situation costs, from the rule's own docstring:** the package goes
`review_state='draft'`, `_apply_abstention` **downgrades the card to an OBSERVATION** — *"the
intelligence still ships; it stops instructing."*

So a Customer Support situation routing through one of those sixteen produces a card that says
*what is happening* and cannot say *what to do*.

**The question:** is each of the 24 genuinely unfinished, or finished and never flipped?
`identity.status: draft → stable`, one word per file. `python scripts/unroutable_report.py
--corpus-only` lists them by id.

> **Likely the cheapest quality win in the product.** No code, no migration, reversible.

---

## D2 · Arm V-9 and V-10?  *(needs M1)*

Two laws were added to the Layer 2 gate and both are declared **`OBSERVE`**: they record and the
situation still publishes. Nothing that shipped yesterday stopped shipping.

| law | what it sees |
|---|---|
| **V-9** | an interpretation that cites nothing. `Anomaly`, `MetricCorrelation`, `CohortPosition` and `ImportanceAttribution` carried **no evidence reference at all** — while `MatchedCondition` has enforced the same rule on itself for months |
| **V-10** | an empty `missing_facts` on a situation whose coverage was never good enough to conclude nothing was missing |

**Why they are not armed:** arming refuses live situations and **nobody has counted how many.**
Read `BY LAW` from M1.

| count | what it means |
|---|---|
| **low** | arm it — one line in `LAW_ACTIONS` — and L2 stops publishing interpretations nobody can check |
| **high** | the producers owe receipts first, and the report names which |

---

## D3 · ⛔ Point `fundraising` at the `sales` corpus?  *(needs M3)*

**The single largest thing in Layer 2, and it is one line.**

The plan said the pilot's dominant domain was dark because *"no fundraising corpus exists — the
fix is authoring, not code."* Measured against the catalog:

```
sales.sit.live_investor_relationship      stable · approved
   "An ongoing relationship with a party that might fund us, read at the ACCOUNT level:
    the fund, the accelerator, the syndicate"
sales.sit.live_investor_contact           stable · approved
sales.investor_relations.investor_relations
   "Reading and running the relationships with the people who might fund the company:
    funds, accelerators, angels and the operators who introduce them."
```

**It was authored inside the Sales corpus**, and `_L2_TO_L3_DOMAIN["fundraising"]` answers `None`.

### Why it is safe, and how we know

The old objection was *"mapping fundraising onto admin would put Admin doctrine on a fundraising
situation."* True — and **routing is per situation TYPE, not a domain blanket:**

| fundraising mints | routes to |
|---|---|
| `investor_relationship` | `sales.sit.live_investor_relationship` |
| `investor_contact` | `sales.sit.live_investor_contact` |

Those are the **only two types** fundraising can mint, and both land on investor doctrine. **No
generic deal doctrine is reachable.** A test proves it and keeps proving it.

### The change

```python
# genios_engine/reason/domain_shadow.py
"fundraising": "sales",     # was None — see CANDIDATE_ROUTES
```

**Two switches, not one.** `live_lane` still requires the tenant to have activated the `sales`
corpus, so this makes fundraising *activatable*, not live. Reversible by restoring the `None`.

> ⛔ **`general` is NOT the same decision and must not be bundled with it.** Its `relationship`
> type is claimed by **all three** corpora, so routing it means picking one by hand — which is how
> Admin doctrine lands on a support thread. It stays dark until a census says what actually lands
> there.

---

## D4 · Activate the Context Reasoner?  *(needs 0183 and M2)*

The first model Layer 2 has ever run. **One call per SITUATION, never per event.** Off on every
tenant; the sweep today runs exactly as it did yesterday.

| | per sweep | per month, daily |
|---|---|---|
| **all Haiku** | **$0.52** | **~$15.64** |
| all Sonnet | $1.04 | ~$31.28 |
| 25% escalating | $0.78 | ~$23.31 |

*(159 active situations × a 1,279-token p50 slice, both measured.)*

### What protects you

| | |
|---|---|
| the gate | activation, budget, cache, retry, deterministic fallback, **one ledger** — nothing new was built |
| the validator | **six deterministic checks** before anything is recorded |
| the law | ⛔ **it cannot raise a confidence**, only lower one |
| authority | it may propose **14** fields and **may never** write an observation, a receipt, or who may see a situation |
| the fallback | **silence.** No key, no budget, no answer → the sweep proceeds exactly as without it |
| replay | every reading is stored **with the slice it was made from** |

```sql
insert into l4_activations (org_id, feature, activated_by)
values ('<pilot>', 'situation_reasoner', 'harsh');
```

Reversible by deleting the row. **Nothing it proposes is committed to the graph.**

---

## D5 · ⛔ S01b — pay for `last_inbound_at`?  *(Rohit's, and it is priced)*

Layer 1's one open scenario. Two benchmark objects — `who_sent_last`, `p3_who_sent_last` — need
*"the previous inbound time"*, which **cannot be known from a single message.**

**Three routes, measured 2026-09-25, and only one is correct:**

| route | cost | correct? |
|---|---|---|
| read siblings from `source_events` | a migration (no index on `(org_id, parent_object_id, occurred_at)`), a connection plumbed into `_thread_context` which has none, and **one read per threaded event on a module that today issues ONE `.execute(` in its entirety** | ✅ |
| read from `qualified_signals` by `thread_key` | the index already exists — **free** | ⛔ **wrong.** Signals are a subset of events (eight drop paths), so it answers *"the last inbound we published a signal for"* |
| a thread object from the connector | — | ⛔ none is stored |

**What it buys: 2 benchmark objects, 24 → 26 of 38.**

The seam is already correct — `_thread_context`'s own comment says *"passing them costs nothing
and means the seam is already correct the day a caller supplies the sibling messages."* **This is
a supplier decision, not a code gap.**

> **The question:** a structural change to the leanest, hottest path in the product, for +2 of 38.

---

## D6 · Raise the 60-day backfill window?

Benchmark **P3** asks about 6 months and **P4** about 12. A default connection holds **60 days**.

Until it is raised, P3 and P4 are **impossible, not unproven** — and the STATUS says so rather
than citing them.

| option | |
|---|---|
| **A — raise it for the benchmark tenant only** *(recommended)* | one admin write, one connection, no deploy, bounded cost, reversible |
| B — raise the default | the slow-first-sync problem comes back for everyone |
| C — leave it | P3 and P4 stay impossible and **we stop citing them** |
