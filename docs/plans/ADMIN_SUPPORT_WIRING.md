> **Created:** 2026-08-27 · **Status:** Active
> **Purpose:** Wire the Admin and Customer Support domains end to end, the way Sales was. Every number below was measured against `org_e97e86f858ad48b2bbf64b8a`. Nothing was deleted.

# The one-sentence finding

Admin and Customer Support were not under-authored — they were **unreachable**, in three
independent ways, and each one alone was enough to make the other two invisible.

| # | Blocker | Where | Cost |
|---|---|---|---|
| 1 | No pack module, so no tenant pack, so no authority lane | `packs/` had only `sales_v1` and `general_v1` | **106 capabilities** compiled, reasoned over, and thrown away under `no_tenant_pack` |
| 2 | Three required Customer Support core objects did not exist | `customer_account`, `named_contact`, `support_plan` | **4 live situations** routed *nothing at all* — a missing required object kills a route, it does not degrade it |
| 3 | `domain_spec` described Admin's company anchor and not its person anchor | `context/domain_spec.py` | a person-anchored admin situation typed as `admin_person`, a name no situation file claims and the registry cannot resolve |

All three are fixed and proven on the live org. The authoring debt behind them is real, is
partly paid, and is quantified at the bottom rather than described as finished.

---

# Blocker 1 — the pack lane

`ReasoningStore.persist_complete` (`reason/store.py:928`) refuses a write unless the config
snapshot's `pack_id` equals the capability's `domain`. `domain_shadow._tenant_pack` resolves that
snapshot from `tenant_packs`, and there was no `admin` or `customer_support` row because there was
no such pack module. Every Admin and Customer Support capability therefore reached
`domain_shadow.py:387`, was counted under `no_tenant_pack`, and emitted nothing.

Not judged and rejected. Never looked at.

**Fixed** — `packs/admin_v1.py` and `packs/support_v1.py`, registered in `wiring.py` and added to
`DEFAULT_PACKS`, promoted onto the live org with `scripts/promote_packs.py`.

Four decisions inside those files are worth reading before anyone edits them:

* **The pack id is the CORPUS domain id, not the Layer 1 domain hint.** Support is where they
  differ — the hint is `support`, the corpus folder and therefore `manifest.domain` is
  `customer_support`. A pack named after the hint would resolve nothing and reproduce the exact bug.
* **`rules: []` is the design.** The compiled Layer 3 brain is the lane; its rule ids are capability
  ids. The daily signal budget is shared org-wide, so a restated `unanswered_email` would emit a
  duplicate card under a second `pack_id` for the same node and spend the budget twice to say one
  thing. And everything genuinely admin/support-native — an approval past its threshold, an SLA
  clock, an invoice that does not match its PO — rests on facts Layer 2 does not write.
* **`schema.fields` declares only fields Layer 2 really writes**, cross-checked against the
  `substrate` block and against `select distinct field from graph_facts` on the live org. This is
  not decoration: `extract/vocab.py::field_vocabulary` unions every pack's fields into the L2
  extraction prompt. A test pins that the vocabulary is byte-identical before and after, so shipping
  these packs cannot change what gets captured. `commitment.text`, `commitment.status` and
  `party.role` were deliberately dropped from the first draft — the pipeline writes them itself, and
  naming them would ask the model to invent a value the pipeline already owns.
* **Version 1.0.1, not 1.0.0.** 1.0.0 was registered into `pack_registry` from that pre-review draft
  during a test run (`make_registry()` resolves its URL from global settings, so a test import
  writes to whatever `GENIOS_DATABASE_URL` points at — see the hazard note below). Published bytes
  are immutable by design, so the correction is a version, not an edit. 1.0.0 holds no tenant, no
  snapshot and no signal.

## Two engine fixes that came with it

* **The L3 compile moved from `run()` to `run_all()`.** It sat at the top of the per-pack function,
  which `run_all` calls once per tenant pack — so the whole corpus compiled, reasoned and emitted
  **twice** on every sweep, and would have compiled **four times** once these packs became defaults.
  Every production caller enters through `run_all`.
* **An early return for a pack with nothing to evaluate.** A rule-free pack with no native
  capability has nothing to do per node, so the graph read, the P90 overlay, the baseline rebuild,
  the neighbour index and a full pass over every node would all run to produce an empty Counter.
* `shadow_compile` now takes an injectable `registry`, for the same reason `run()` does: a caller
  holding a different store was silently resolving the tenant pack from the wrong database and
  counting every capability as `no_tenant_pack` — the symptom this work removes, arriving from the
  harness instead of from the code.

---

# Blocker 2 — three Customer Support objects

`customer_account`, `named_contact` and `support_plan` were referenced by 16, 4 and 10 capabilities
respectively and did not exist. All three are authored, at the `requester.yaml` standard, all 23
sections.

The inference-pattern ratios are the finding, not a shortfall:

| Object | Patterns | Executable | Why |
|---|---|---|---|
| `customer_account` | 14 | 6 | correspondence carries whose turn it is, cadence against the account's own baseline, broken promises, tone. ARR, renewal date and ticket volume have no writer. |
| `named_contact` | 14 | 8 | `party.role`, `ball_in_court`, commitment dates and the observation stream. Seniority and budget authority have no writer. |
| `support_plan` | 10 | **2** | a support plan is a CONTRACTUAL object and nothing in a correspondence-only substrate carries a contract. Its most valuable output on this tenant is `entitlement_confidence` reporting LOW — which is what stops a defaulted tier being quoted to a customer as their agreement. |

The `exceptions` sections are where the value is, and they are the part no vendor's account-health
model contains: silence from a self-serve account means nothing; the angriest account is usually the
most committed; precedent outranks the contract once you have over-delivered for six months; a
free-tier design partner may be the most strategic customer you have.

---

# Blocker 3 — Admin's person anchor

`domain_spec` registered Admin with `situation_types={"company": "account_admin"}` and nothing else.
A person-anchored admin situation therefore fell through `type_for`'s generic `<domain>_<anchor>`
default and became `admin_person` — absent from `_schema/vocabulary.yaml`, claimed by no situation
file, unresolvable by the registry. The same fault, in the same shape, as the `general_deal` gap
that kept the whole deal lane dark.

Fixed as a set of three, because none of them is sufficient alone: the `domain_spec` entry
(`person → admin_contact`), the vocabulary entry, and `admin.sit.live_admin_contact` to claim it.

---

# Measured on the live org

Read-only probe, `scripts/corpus_route_probe.py`, before and after.

| | before | after |
|---|---|---|
| Situations routed | 47 / 83 (56%) | **51 / 83 (61%)** |
| `relationship` routed | 33 / 37 | **37 / 37** |
| `required_missing` | 4 | **0** |
| Customer Support capabilities reached | **0** | **3**, × 4 situations each |
| Admin/CS pack lanes resolving | `None` | `admin` rev 1, `customer_support` rev 1 |
| `admin_person` situations | 1 | 0 — re-derived to `admin_contact` |
| Signals in the `customer_support` pack | **0** | **4** |
| Cards from the `customer_support` lane | **0** | **4**, all LLM-rendered, all prescriptive, zero audit defects |

The three Customer Support capabilities now reached are `expectation_setting`,
`entitlement_verification` and `account_relationship_management` — all three of which this session
also promoted out of stub, so what reaches the compiler is real expertise rather than a name.

## The full chain, run end to end

`backfill_layer2` -> `shadow_compile(live=True)` -> `build_cards_for_org` -> `card_audit`, in that
order, on the live org.

```
shadow_compile   situations 83 · compiled 52 · reasoned 52 · decided 52
                 standing 47 · emitted 2 · no_route 21 · incomplete 10
                 no_tenant_pack ABSENT FROM THE COUNTS
build_cards      built 4 · llm 4 · raw_slot 0 · unrouted 0
```

`no_tenant_pack` not appearing in the tally at all is the result this whole piece of work is
measured by. Before, it was the terminal state of every Admin and Customer Support capability.

The four cards the Customer Support lane produced, against every check `card_audit.py` runs:

| Check | The 4 CS cards |
|---|---|
| says it has nothing to say | 0 |
| template copy, not authored (`raw_slot`) | 0 |
| abstains instead of advising | 0 |
| no action offered | 0 |
| raw serialisation / sentinel words / truncation | 0 |

All four rendered `llm` and `prescriptive`. The 48 defects the audit does report on this org are
entirely in the pre-existing lanes — 29 in `sales`, 17 in `general` — and none is introduced here.
They are the queue-quality backlog the audit script was written for, not a regression.

The graph was backed up to `*_bak_20260827_adminsupport` before anything was written, including
`tenant_packs`.

---

# Authoring: complete

| | at start | now |
|---|---|---|
| Admin capabilities hollow | 51 / 57 | **0 / 57** |
| Customer Support hollow | 40 / 49 | **0 / 49** |
| Sales hollow | 0 / 47 | 0 / 47 |
| Incomplete playbooks + heuristics | 190 | **0** |
| Corpus validate errors | 380 | **0** |
| Whole-corpus `yaml.safe_load` failures | — | **0** (1351 files) |

**153 of 153 capabilities authored**, all three domains at the same standard. Every capability is
three real files:

* `capability.yaml` — 5–6 outcomes *including the negative one*, 5–6 failure modes written as how a
  competent-looking person gets it wrong, 4–5 KPIs, handoffs, applies_to. No numbers: thresholds
  are Layer 4's and live in the pack.
* a **playbook** — `when_to_use` with `do_not_use_when`, ordered steps each with an observable
  `done_when`, limits, failure modes, model variants, references.
* a **heuristic** — statement, why, `confidence_bp`, `applies_when`, and `breaks_down_when`, which
  is the field carrying most of the value.

## The measurements this corpus argues for

Almost every capability is built around a number the function does not normally report, and in
several cases around the *inversion* of the one it does:

| Instead of | Because |
|---|---|
| actuals | **committed spend** — a line at 60% consumed with three open orders against it is overspent, and every actuals report says it is healthy |
| deflection rate | **net deflection + escalation temperature** — a customer who gave up counts identically to one who was helped |
| macro usage rate | **edit-before-send** — usage rate rewards exactly the send-as-is behaviour that destroys the trust macros save time to build |
| time-to-close | **reopen rate, and reopen *friction*** — closure is ours to control, reopening is not; where reopening is hard the check is as gameable as the thing it checks |
| article count | **article deflection yield** — count rises monotonically and says nothing |
| attrition | **after-hours creep, QA drift, and the lead-indicator gap** — the team that burned out in March resigns in September |
| ticket volume as support performance | **ticket volume as a product metric** — treated as ours it rewards deflecting the report rather than removing the cause |
| count-based load fairness | **weighted variance beside perceived fairness** — count variance can be zero while the team can see the spread, and asserting fairness they know is false damages every other number |

Several KPIs are deliberately **target bands rather than directions**, which is the least obvious
call in the corpus and always argued in the file: `near_miss_reports` (zero means nobody is
reporting, not that nothing happened), `stand_down_rate` (cheap declaration requires cheap
de-declaration), `returned_to_supplier_rate` (zero means we absorb supplier errors forever),
`refused_claim_count` (zero means every requested number was produced regardless of what the data
supports), `policy_count` (the one metric in Admin whose right direction is sometimes downward).

## Genuine professional tensions, recorded not smoothed

`contradicts` is used throughout to name conflicts a practitioner actually holds, rather than
presenting a brain more confident than the profession is. Among them: small-promises vs
breach-clustering (under load they point at different tickets); silence-is-the-promise-breaker vs
every-reply-sets-the-tone (send now vs send well); everything-kept-is-discoverable vs
audit-pain-measures-record-debt (keep less vs keep more, resolved per record class); friction-begets-
shadow-procurement vs auto-renewals-are-decisions (reviews push spend out of view);
unminuted-decisions-dissolve vs governance-is-retrospective-evidence (what to omit is a governance
judgement); SOPs-are-resilience vs workarounds-mark-the-real-process-map (which process to write
down).

## What is still NOT done

* **`investor_contact` is unrouted globally** — 7 live situations on the design partner's org,
  emitted by Layer 2 and bound by no domain. It is the single remaining routing warning from
  `validate.py`, it is a Sales/fundraising corpus gap, and it is the largest routing loss left
  after `deal`.
* **`fundraising_deal` × 4** — same generic-fallback fault that produced `admin_person`. One line
  in `domain_spec.py` plus a situation.
* **17 Customer Support core objects referenced and unauthored** — `issue`, `conversation`,
  `support_agent`, `queue`, `backlog` and others. They block only situations bound to
  `pending_l2_situation_types` that nothing emits, so authoring them changes no routing until a
  support L2 extraction lane exists. Tracked in `Customer Support Expertise/domain.yaml`.
* **The 384 warnings are the real backlog** and they are honest: planned-but-unauthored object
  references, and 15 situation triggers bound to L2 types no pack emits. `registry/signal-backlog.md`
  ranks them.

## A hazard worth knowing before the next session

Running the test suite **registers every pack in `BUILTIN_PACKS` into whatever
`GENIOS_DATABASE_URL` points at**, because `make_registry()` with no argument resolves its URL from
global settings. It is harmless while pack bytes never change and it is how `admin@1.0.0` reached
production's `pack_registry` from a draft. The practical rule: **bump the pack version whenever pack
bytes change**, which is the convention anyway. The underlying test-isolation issue is pre-existing
and untouched.

---

# Recommended order from here

1. **`investor_contact` and `fundraising_deal`** — 11 live situations, two small corpus/spec fixes,
   and the largest routing gain left on this org. Sales lane.
2. **The remaining 166 skeleton playbooks and heuristics**, in the same batches as their
   capabilities. This is what takes validate errors to zero.
3. **The 76 hollow capabilities**, last for the same reason batches 1 and 2 were ordered as they
   were: until a domain has situations Layer 2 can emit, authoring behind them changes nothing that
   can be measured.
4. **A support or admin L2 extraction lane** — `planned_substrate` names 25 Admin and 20 Customer
   Support situation types and roughly 70 fact paths with no writer. That, not authoring, is what
   makes these two domains something other than a correspondence reader wearing a support hat.
