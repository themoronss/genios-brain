# Admin-only cross-check — what exists, what does not

**2026-09-25** · scope: **Admin Expertise only.** Sales and Customer Support are on hold.
Everything below is measured against the tree, not assumed.

---

# A · The Admin corpus — ⛔ it is genuinely well written

`corpus_health()` run against the live catalogue, using the rules the compiler actually admits with:

| domain | capabilities | admitted | inadmissible | hollow | situations | draft |
|---|---|---|---|---|---|---|
| **admin** | **59** | **59** | **0** | **0** | 34 | **8** |
| customer_support | 49 | 49 | 0 | 0 | 20 | 16 |
| sales | 47 | 47 | 0 | 0 | 15 | 0 |

⛔ **59 of 59 admitted. Zero inadmissible. Zero hollow.** Every Admin capability clears the
admission ceremony — `identity.status: stable`, an approved reviewer, and an
`accepted_content_hash` matching the routed bytes. **Rohit is right: it is properly written.**

**Routing is correct:** `admin → admin`. No dark route, no candidate, nothing unresolved.

### What the 211 files under `capabilities/` actually are

An earlier count said "211 capabilities". It is **211 files**, which is:

```
59 × capability.yaml  +  59 × knowledge.yaml  +  59 × objects.yaml  +  34 situations  =  211
```

**59 capabilities. All `stable`.**

### The rest of the corpus, by folder

| folder | files | draft | stable |
|---|---|---|---|
| capabilities | 211 | 8 *(situations)* | 85 |
| heuristics | 60 | **44** | 16 |
| playbooks | 58 | **44** | 14 |
| objects | 25 | **25** | 0 |
| models | 20 | **20** | 0 |
| offerings | 15 | **15** | 0 |
| rules | 9 | 0 | **9** |

⛔ **`status` on a heuristic or a playbook is not the same gate as on a capability** — the
admission ceremony runs over capabilities, and all 59 pass. The drafts above are an authoring
signal, not an admission failure.

### ⛔ The 8 draft situations, by name

```
admin.sit.asset_in_custody              admin.sit.employee_lifecycle_event
admin.sit.campaign_awaiting_reply       admin.sit.obligation_falls_due
admin.sit.condition_awaiting_review     admin.sit.organization_gone_quiet
admin.sit.document_under_control        admin.sit.spend_against_a_commitment
```

**What a draft costs:** the package goes `review_state='draft'`, `_apply_abstention` downgrades the
card to an **OBSERVATION** — *"the intelligence still ships; it stops instructing."* So 8 of Admin's
34 situations produce cards that say **what is happening** and cannot say **what to do**.

**Fix: one word per file, `draft → stable`.** No code, no migration, reversible.

---

# B · The substrate — ⛔ Admin asks for a third of what the engine offers

The vocabulary declares **141** fact paths to capability authors. Measured against the **Admin
corpus alone**:

| | |
|---|---|
| declared to authors | **141** |
| ⛔ **Admin consumes** | **46** |
| Admin never names | **95** (79 on the strictest reading) |

### The 95 split into two very different problems

**① 18 fields Admin does not read, but Sales/Support do** — arguably fine, they are other domains'
vocabulary: `deal.status`, `deal.value`, `backlog.*`, `workaround.*`, `derived.momentum` …

**② ⛔ 61 fields NO domain reads at all — and most of them are Admin's own territory:**

| family | fields | what they are |
|---|---|---|
| `mailbox.*` | **17** | backlog age p50/p90, oldest, over-14d, loops opened/closed/reopened, flow ratio, arrival vs baseline, **threads awaiting us** |
| `knowledge.*` | **9** | asks this/prev window, distinct askers, distinct accounts, answered count, first/last asked |
| `document.*` | **8** | title, owner_email, location, modified_at, last_modified_by, shared, mime |
| `escalation.*` | **7** | ask_text, origin, receiver_named, requester, status, thread_id, account |
| `cohort.*` | 5 | replied, reply_rate_bp, median_reply_days, cadence_known, organization_count |
| `derived.history.*` | 4 | ⛔ *"we already told them this and they marked it wrong"* |
| `repeat.*` · `period.*` · `backlog.*` · `response.*` · `party.*` · `outreach.*` | 11 | repeat asks, overdue commitments, reply cadence |

⛔ **`mailbox.threads_awaiting_us` · `mailbox.backlog_oldest_days` · `escalation.status` ·
`document.owner_email`** — this is *exactly* what an executive assistant's work is made of, and
Admin's capabilities never name a single one of them.

**The engine computes and writes all 61 on every sweep. Nothing reads them.**

---

# C · The reasoning plane — ⛔ the larger gap, and it DEPENDS on B

`reason/` is **Plane R**. `reason/unit.py` is the unit framework — *"you do not build seventeen
systems, you build one framework and seventeen implementations of it."*

| | |
|---|---|
| units registered (`CORE_UNITS` + `SUPPLEMENTARY_UNITS`) | **23** |
| ⛔ **scheduled by `_default_dag`** | **6** |

```python
return (context, risk, constraint, priority, confidence, planning)   # expertise.py, _default_dag
```

### ⛔ The twelve `core.*` units that have never run on this lane

```
core.alternative   core.cost         core.dependency   core.impact
core.opportunity   core.policy       core.recommendation  core.resource
core.scheduling    core.timeline     core.tradeoff     core.validation
```

plus `TemporalReasoner` and `RelationshipReasoner`, which produces the second finding:

### ⛔ And the six that DO run, run half-blind

From the module's own Z1 block:

> *"the six that DO run, run half-blind: `core.risk` reads `drop_bp` from `core.temporal` and
> `coverage_bp` from `core.relationship`, and neither was scheduled, so **two of its three plugins
> have been correctly silent since the day it shipped**."*

### ⛔ The mechanism is built and has never been switched on

> *"`reason/plan.py` has carried a deterministic, receipted Unit Selector since it was written and
> **no manifest has ever switched it on**."*

`roster_v2` is that switch. `roster_v2=False` builds the six-unit DAG; `roster_v2=True` *"declares
the full family, binds each unit's inputs to the fact paths this expertise actually reads, and
switches on the planner's Unit Selector."*

## ⛔⛔ CORRECTED THE SAME DAY — the claim below was measured and is WRONG

**What this section originally said:** *"B and C are not two problems. C cannot be fixed without B"*
— that adding `reads:` for the 61 unread families would wake the dormant units.

**Measured against the actual roster (`_ROSTER` in `reason/adapters/expertise.py`), that is false.**

With `roster_v2` on, for Admin: **15 of 20 roster units BIND. 5 drop.** And the roster does not gate
on `mailbox.*`, `escalation.*`, `document.*` or `knowledge.*` at all. It gates on a small, specific
set of roles, and here is every field that would bind the five that drop:

| dropped unit | role it needs | candidate fields | in the vocabulary? |
|---|---|---|---|
| `core.relationship` | `status_field` | `deal.status` | ✅ declared |
| `core.policy` | 4 roles | `deal.value` · `deal.approval_status` · `contact.do_not_contact` · `contact.consent_status` | 1 of 4 |
| `core.opportunity` | `status_field` · `owner_field` | `deal.status` · `deal.owner` | 1 of 2 |
| `core.resource` | `owner_field` | `deal.owner` | ⛔ **not declared** |
| `core.scheduling` | `quiet_until_field` | `schedule.quiet_until` | ⛔ **not declared** |

⛔ **Four of the five drops are CORRECT.** They are DEAL-shaped units, and **Admin has no deals.**
The selector dropping them is the selector working.

⛔ **And five of the seven fields do not exist in the vocabulary at all**, so no amount of authoring
can bind them — Layer 1 or Layer 2 would have to emit them first.

**So B and C are two SEPARATE problems, not one:**

* **C (the roster)** is in good shape for Admin — 15 of 20, with the drops explained. It is gated on
  deal/contact/schedule fields, not on the unread substrate.
* **B (the 61 unread fields)** changes what a capability can **SAY** — the content of the card — not
  **which units RUN**. Still worth doing, for a completely different reason than this document
  originally gave.

**The original claim conflated the roster's role-binding with the corpus's fact consumption. They
are different mechanisms reading different lists.**

---

## The dependency that IS real

## The roster's own binding rule


**B and C are not two problems. C cannot be fixed without B.**

The roster declares a unit **only if the expertise reads a field that unit can use** — from the Z1
block:

> *"A unit whose roles bind nothing is **left out with a receipt** naming its candidates, rather
> than declared with fields no authored pattern ever asked for."*

**So switching `roster_v2` on today would declare the full family and then drop most of it**, with
an honest receipt, **because Admin's corpus names only 46 of 141 fact paths.** A unit that reasons
about escalations cannot bind when nothing reads `escalation.*`.

```
Admin capability adds  reads: escalation.status
        ↓
roster_v2 binds core.policy / core.validation to that path
        ↓
Unit Selector schedules the unit instead of dropping it
        ↓
the card can finally say something about the escalation
```

**The corpus is the input to the roster. Authoring comes first; the switch comes second.**

⛔ **AND THE SWITCH IS PROBABLY ALREADY THROWN.** `roster_v2` sits in `L4_DEFAULT_FEATURES`,
so any tenant provisioned through `make_tenant_live` has it on. If the pilot does, then the
full family is already declared on every pass and the Unit Selector is already dropping
twelve units **with an honest receipt naming what they could not bind to** — which means
the receipts themselves are the authoring worklist, and item 2 is not one lever of two.
**It is the only one.**

---

# D · What is NOT broken — checked, so nobody spends time here

| | state |
|---|---|
| Admin admission ceremony | ✅ 59/59, 0 hollow |
| Admin routing (`admin → admin`) | ✅ |
| the 23 units themselves | ✅ built, tested, green |
| the Unit Selector (`reason/plan.py`) | ✅ built, deterministic, receipted |
| `roster_v2` activation machinery | ✅ registered, waved, preconditioned, in `L4_DEFAULT_FEATURES` |
| the L3 activation path for `admin` | ✅ `L3_DOMAINS` resolves it from the authored corpus |
| Layer 3 engine code | ✅ 26/26 steps, 13,301 passed, 0 regressions |

---

# E · The work — ⛔ rewritten after measuring items 3, 4 and 5

| # | what | measured outcome |
|---|---|---|
| **1** | Flip the 8 draft Admin situations | ⛔ **NOT one word per file.** 4 are declared `pending_l2_types` in the registry and **must not be flipped** — one says flipping it *"would cost a false assurance"*. 3 are verified working and need **a named human reviewer**. 1 says its gap is *"now bound"* and needs confirming. **Cannot be done without Rohit or Harsh signing.** |
| **3** | Confirm `roster_v2` on the pilot | ✅ registered, waved, preconditioned, and **in `L4_DEFAULT_FEATURES`** — so `make_tenant_live` switches it on at provisioning. **One read-only query on the pilot to confirm; it is Harsh's to run.** |
| **4** | Which units bind for Admin | ✅ **DONE — measured. 15 of 20 bind, 5 drop.** 4 of the 5 drops are CORRECT (deal-shaped units; Admin has no deals). 5 of the 7 fields that would bind them **are not in the vocabulary at all** |
| **5** | Get `core.temporal` / `core.relationship` scheduled so `core.risk` stops running half-blind | ⚠️ **HALF DONE BY DESIGN, AND THE REST IS REFUSED IN WORDS.** `core.temporal` **binds** for Admin via `derived.engagement`, so `drop_bp` works. `core.relationship` **drops correctly** — its only candidate is `deal.status`, and the module says binding it to anything else *"would put a false reading in the trace to keep a unit busy"*. **So `core.risk` runs on 2 of 3 plugins for Admin, and the third is honestly silent, not broken.** |

## ⛔ What is genuinely left

| | what | owner |
|---|---|---|
| **a** | Sign or refuse the **3 verified** draft situations; confirm `document_under_control` | ⛔ **Rohit / Harsh — a human signature, and forging it would defeat the whole ceremony** |
| **b** | Confirm `roster_v2` is on for the pilot | Harsh · one query |
| **c** | Item 2 — add `reads:` to Admin capabilities | ⛔ **authoring. See §F for exactly what it buys and what it does not** |
| **d** | `deal.owner` · `deal.approval_status` · `contact.do_not_contact` · `contact.consent_status` · `schedule.quiet_until` are **not in the vocabulary** | a Layer 1/2 decision, not authoring |

---

# F · ⛔ What item 2 actually buys — stated correctly

**It does NOT wake dormant reasoning units.** That was this document's original claim and it is
false: the roster gates on deal/contact/schedule roles, and Admin already binds 15 of 20.

**What it DOES buy is what a card can SAY.** A capability's `reads:` is the list of facts its
heuristic is allowed to reason from. Admin reads 46 of 141. The 61 nobody reads include the
families that ARE an assistant's job:

| family | fields | a card could then say |
|---|---|---|
| `mailbox.*` | 17 | *"your backlog's oldest thread is 23 days old and the p90 has doubled this fortnight"* |
| `escalation.*` | 7 | *"this ask was escalated, named a receiver, and the receiver has not replied"* |
| `document.*` | 8 | *"the contract was last modified by someone outside the company"* |
| `knowledge.*` | 9 | *"four different people asked this in ten days and it was answered once"* |
| `derived.history.*` | 4 | *"we already sent this card and they marked it wrong"* |

⛔ **Today Admin's capabilities cannot express any of these**, not because the engine lacks the
data — it computes and writes all of it every sweep — but because no authored heuristic names the
field.
