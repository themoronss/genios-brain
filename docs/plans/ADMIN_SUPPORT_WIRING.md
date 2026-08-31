> **Created:** 2026-08-27 · **Status:** Active — **and its numbers are nine commits behind.** Routing is **121 routed / 32 named-pending / 0 silent of 153**, not the 85 or 108 written below. Exactly two things are blocked on a human; several sections have closed entirely. Re-verified 2026-08-30.
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

## Session 2 — making a sync produce intelligence, and what that uncovered

The brief was "wire it so that whenever data syncs, intelligence gets built properly". Three
routing faults were closed, and chasing the proof on the live org surfaced a production incident
that had nothing to do with routing.

### Routing: 50/80 → 73/80, and `no_route_type` is now zero

| Fault | Live effect | Fix |
|---|---|---|
| `deal.status` had two writers, one of which did not normalise, at authority_rank 100 | every sync overwrote the canonical `open` with `engaged`/`evaluating`/`new`; all three Sales deal situations gate on `open`, so the deal lane emptied on every sync and refilled on every backfill | `derived.compute_deal_view` routes through `_normalise_deal_status` and publishes the rich word as `deal.stage`; deal 0 → 13 routed |
| `investor_contact` claimed by no situation file | 6 live situations matched nothing, every sweep | `sales.sit.live_investor_contact` |
| `fundraising` had no `deal` anchor, so `type_for` fell to its generic default | `fundraising_deal` × 4, unclaimable by construction | `domain_spec` maps it to `investor_relationship`; also makes `lift_companies_to_their_deals` safe in fundraising for the first time |

`test_no_producible_situation_type_is_globally_unrouted` is now a standing guard: a future L2 type
without a door fails the suite instead of quietly emptying a lane. The 7 situations still unrouted
are `lost` deals, which is the correct answer.

Compile on the live org after the fixes: **80 situations → 73 compiled → 73 reasoned → 73 decided**,
562 capability instances, and `no_tenant_pack` / `required_missing` / `incomplete` all absent.

### The incident: `expertise_packages` took production read-only

Found while trying to back up the live org before a live compile — `CREATE TABLE AS` was refused
with `cannot execute in a read-only transaction`. The production database has
`default_transaction_read_only = on` and `pg_is_in_recovery = false`: it is the primary, and
Supabase had put the project into read-only for crossing its disk quota. **Every write the product
makes was failing** — syncs, facts, signals, cards, not only the compile.

`expertise_packages` was **995 MB of a 1489 MB database — 67%** — holding 4,086 rows for 127
distinct situations, every row's payload averaging 238 kB and every row's `semantic_hash` distinct.
That last number is the tell. The publisher's `on conflict (org_id, expertise_id) do nothing` is
correct and never fired, because the id it conflicts on was new every time.

Two fields were being hashed as content when both are observation metadata:

* `ExpertisePackage.trace_id` — `domain_shadow` mints `new_id("trace")` per situation per sweep;
* `SituationContextSlice.evaluation_time` — the wall clock, reaching the package's content address
  through `context_slice_hash` in its metadata.

`test_contract_envelope_and_compiler_are_deterministic` asserted `first.id == second.id` and passed
throughout, because its fixture supplies a constant trace id and a constant `NOW`. It proved the
compiler deterministic in every field except the two that are never constant in production.

**Fixed**: both are out of the content address (`to_semantic_dict` and `expertise_id`, which must
agree or the id and the hash disagree about what the package is). Migration **0076** drops
`trace_id` from `expertise_payload_projection` — left alone the clause does not fail, it evaluates
to NULL and a CHECK passes on NULL, so the constraint would keep its name and silently stop
checking.

**Not fully fixed by content-addressing, and this is stated rather than left to be discovered**:
`SituationContextSlice.graph_version` is ORG-GLOBAL, so any write anywhere in the tenant advances
the version every situation's slice carries. A package therefore legitimately mints a new id on
each sync that touched anything — ~17 MB per sync for this org's 73 situations. Removing
`graph_version` from the address too would bound it harder and was deliberately NOT done: it is
what binds a package to the graph it observed and what the reasoning snapshot's integrity guard
compares. `purge_superseded_expertise_packages` keeps the newest 3 per (org, situation) and runs on
the maintenance heartbeat. Three, not one, because the newest is what the current card cites and
the ones behind it are what an audit of yesterday's card replays against.

### The test suite could write to production, in two independent ways

Both are pre-existing, both are now closed, and the second is how a draft `admin@1.0.0` reached
production's `pack_registry` in session 1.

1. **Nine `conn` fixtures** resolved their URL from `get_settings().database_url` and opened a
   transaction against it. On CI, with no `.env`, they skipped and looked harmless; on a developer
   machine they held row and tuple locks on a paying tenant's `execution_outcomes`, `learning_runs`
   and `delivery_*` tables for the length of each test. A pytest process killed mid-test never
   reaches the rollback, and Supabase runs `idle_in_transaction_session_timeout = 0`, so the locks
   are held until a human notices. One such leak blocked this suite for hours and read as a flaky
   test.
2. **Nine more modules** call `make_registry()` at import time, which resolves its URL from global
   settings and registers every pack in `BUILTIN_PACKS` into whatever it finds.

`tests/conftest.py` now pins `GENIOS_DATABASE_URL` for the whole test process — to the scratch
database when `GENIOS_TEST_DATABASE_URL` is set, and to empty otherwise, which is exactly the state
CI has always run in. Migrations are applied at conftest import because the second class of caller
runs during collection, before any fixture. `tests/test_tests_never_touch_production.py` guards
both halves and is mutation-tested.

Side effect worth having: the real-Postgres lane went from 315s to ~41s. Most of that time was
round-trips to a database in another region.

## Session 3 — every capability now has a door or a named reason it has none

The brief was to finish the wiring. The finding that shaped it: all 10 declared situation types
were already producible, so nothing was blocked by Layer 2 typing. **113 of 153 capabilities were
simply not named by any registry map entry**, because `situation-capability-map.yaml` is GENERATED
from situation files and there were 25 of them for 153 capabilities.

### Final accounting

| | count |
|---|---|
| capabilities authored | 153 |
| **routed** — a live L2 type reaches them | **85** |
| **pending** — bound to a named L2 type that nothing emits | **68** |
| **silent orphans** | **0** |

Situation files 25 → 40. Corpus stays at 0 validate errors.

### The meeting lane, and the two faults under it

62 meeting nodes, 331 facts, 140 `attended` edges — and no situation about any of them. They were
never unreachable: they arrive in the neighbour facts of every person-anchored slice, measured
through `runner._neighborhood`. Two faults made them untrustworthy first:

* `general`, `admin` and `customer_support` declared the five DERIVED lifecycle fields in
  `schema.fields`, which is the L2 extraction whitelist, so a model was asked to guess five
  booleans it cannot see — `meeting.scheduled` held `'Monday 10 Aug 2026, 10:30am -'` on 30 person
  nodes. `COMPUTED_FIELDS` strips them from the prompt while leaving the declaration (the same
  mechanism that already existed for `derived.*`).
* `meeting.status` arrived as both `cancelled` and `canceled`, and every authored predicate
  compares the literal. `_normalise_meeting_status` collapses it at the write path, importing the
  synonym set from `meeting_lifecycle` rather than restating it.

`meeting` was deliberately NOT made an anchor type: `choose_anchors` returns only the strongest
tier, so that would have moved 62 events out of the relationship situations that work.

### Three objects the wiring exposed

Routing the intake and voice-of-customer capabilities onto `relationship` cost one live situation:
the route probe went 73 → 72 with `required_missing`. A missing REQUIRED object fails a route
closed rather than degrading it — the same mechanism as Blocker 2 in session 1 — and the three
missing ones were `customer_support.obj.core.conversation`, `issue` and `satisfaction_score`,
declared required by eighteen capabilities between them.

All three are now authored, and two of them are deliberately honest about being nearly empty on
this substrate:

* **conversation** — the real one. Every executable pattern rests on a fact with a writer
  (`thread.ball_in_court`, `thread.last_inbound/outbound`, `derived.*`, `commitment.*`). The
  glossary already separated it from a ticket, and on a tenant with no helpdesk it is the only
  half of that pair that exists.
* **issue** — one weak executable pattern and four `needs_signal`. The substrate has no issue
  identity, no reproduction and no resolution kind, and approximating any of them would let eight
  capabilities give confident advice about a defect nobody diagnosed.
* **satisfaction_score** — one executable pattern, and it is a GUARD that yields nothing:
  `derived.sentiment` sits one field away from every capability that wants a satisfaction number,
  the substitution is trivial and would be undetectable in the output. Loading the object makes the
  absence explicit instead.

Corpus warnings fell 394 → 325 as a side effect — 69 planned-object references closed.

### Why 68 are pending rather than routed

`select distinct field from graph_facts` on the live org returns eleven prefixes: meeting, other,
thread, relationship, derived, deal, party, commitment, role, company, attendees. There is no
`document.*`, `invoice.*`, `asset.*`, `employee.*`, `compliance.*`, `ticket.*` or `sla.*`. Routing
those subdomains anyway would report coverage the system does not have — which for
`compliance_and_governance` is not a missed insight but a false assurance. Each pending file
records, in the corpus's existing house format: what the type must mean, what would emit it, what
goes wrong today, and specifically why the nearest available binding would be wrong.

**One Layer 2 mechanism unblocks 22 capabilities across all three domains**: tenant-anchored
periodic situations. Named identically in `admin.sit.admin_service_under_load`,
`customer_support.sit.queue_period_review` and `sales.sit.pipeline_period_review` so it reads as
one build rather than three coincidences.

## Session 4 — the period mechanism, built

The largest single item in the pending list was not a connector. Twenty-three capabilities across
all three domains asked about a WINDOW rather than a subject, and none could route because
`context_situations` anchors on a graph node and no node's facts are "the whole queue this month".
Three corpus files named it in identical words so it would read as one build.

**The design, and why it adds no new concept.** `context/periodic.py` mints a `tenant` node per
org, writes the window's aggregates onto it as ordinary facts — exactly as `derived.py` writes
engagement onto people — and opens one situation per domain anchored there. `_load_context`,
`_neighborhood`, `build_context_slice` and the whole compile path work unchanged. Teaching the
compiler about anchorless situations would have put a second situation shape into a pipeline that
has one.

The tenant node is deliberately absent from `ANCHOR_PRIORITY`. `choose_anchors` returns only the
strongest tier present, so a tenant node reachable from correspondence would fuse every
conversation in the org into a single situation.

Domains opt in by declaring `"tenant": "<domain>_period_review"` in `domain_spec`; the module asks
the registry rather than listing domains. The first version listed them and
`test_domain_names_appear_in_exactly_one_file_in_the_context_layer` rejected it, correctly — a
domain named in Layer 2 means adding a domain requires editing Layer 2.

**What it carries, and what it refuses to.** Counts and their previous-window twins, because one
number is not a finding. No targets, no thresholds, no verdicts: whether 25 open deals is coverage
or a drought needs a target nobody has stated, and inventing one would put a fabricated benchmark
under every forecast. The absent inputs stay listed in `missing` on every situation.

Measured read-only on the live org (production is read-only, so nothing was written): 25 open
deals; 472 events this window against 750 last; 63 counterparties waiting on us; **32 commitments
open and 30 of them overdue**; 80 active situations. That last pair is exactly the kind of finding
no per-subject situation can surface.

**Routing: 85 → 108 of 153.** Pending 68 → 45.

**One correction to session 3.** `admin.sit.document_under_control` claimed the records subdomain
needed a document-store connector. `capture/connectors/drive.py` already exists and is already
dispatched — it lists Drive, downloads each file and extracts the text. What it does not do is
project the file metadata it already receives (`id`, `version`, `modifiedTime`,
`lastModifyingUser`) into `document.*` facts. The build is a projection and a node type, not a
connector, and the file now says so.

## What is still NOT done

* **Production is read-only right now, and only you can lift it.** Supabase releases it from the
  dashboard. Freeing space means deleting `expertise_packages` rows on the live org — a
  stop-and-ask, so it has not been touched. Nothing in sessions 2 or 3 is deployed.
* **`GENIOS_USE_DOMAIN_COMPILER` is unset**, so the compiled brain does not run in a normal sweep.
  The whole chain behind it is verified. It is an env change on the DO app, so it is a deploy, so
  it is yours to call — and it must not be turned on before the `expertise_packages` fix ships.
* **Evidence, not routing, is now the constraint.** Measured per anchor: `relationship` 9.2 facts,
  `deal` 4.3, `investor_relationship` (company) 1.4, `opportunity` 0.5, `support_case` 0.0. Person
  nodes hold 1,279 facts across 129; company nodes hold 18 across 40. Account-level extraction is
  the next real build.
* **The 68 pending capabilities need Layer 1 connectors**, not corpus work: a document store, a
  compliance register, an HRIS, an asset register, a finance system, a helpdesk, a dialler. Each
  is named in the file that waits on it.

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

## Re-verification — 2026-08-30

This file was the frontier when it was written and much of it has since shipped. Corrections, in the order the claims appear.

### The routing number

**121 routed / 32 named-pending / 0 silent, of 153.** Sales 43/47, Admin 36/57, Customer Support 42/49 — read from the `stats:` block of each domain's `registry/situation-capability-map.yaml`. So the two counts in this file (85 at lines 312-314, 108 at line 409) are both superseded; commit `68a4a8f`'s claim of 108 → 121 is confirmed. **"0 silent" still holds** — every one of the 32 orphans is named by a situation bound to a pending L2 type.

Offline corroboration: `Domain Expertise/_tools/admit.py --check` → *174 already admitted, 0 stamped, 0 drifted, 28 blocked, **0 HOLLOW*** (the 28 blocked are `*.sit.*` situations, which `admit.py:16-18` says the resolver does not gate on). `_tools/validate.py` → **0 errors**, 283 warnings.

> Note for whoever re-measures: `scripts/corpus_route_probe.py` **requires a database** (it dies at `reason/runner.py:487` without one). The offline path is `_tools/admit.py --check` plus the `stats:` blocks. `_tools/index.py` recomputes them but **writes three files**, so it is not a read-only check.

### Still blocked on a human — both, still

1. **Production is read-only and migration `0076` is pending.** Confirmed by `a0a397e`'s own commit body, which quotes production: *"1 migration(s) pending and the database is in read-only mode: 0076_expertise_payload_drops_trace_id.sql"*. What changed since this file was written is that the app now **degrades instead of crash-looping** — `platform/migrate.py`, `main.py`, and a 503 before the LLM call in `api/intelligence_routes.py`, guarded by `tests/test_migrate_read_only.py` and `tests/test_read_only_outage_behaviour.py`. The read-only lift itself is still yours. **Live state UNVERIFIED** — this audit had no DB access.
2. **`GENIOS_USE_DOMAIN_COMPILER` is still unset.** `platform/config.py:110` — `use_domain_compiler: bool = False`, read at exactly one site (`reason/runner.py:1373`), and absent from `.env`, `.env.production`, `.env.example`, `Procfile` and every yaml/json in the repo. The precondition this file states — read-only lift and `0076` first, then the flip — is still the right order.

The `expertise_packages` fix itself **is in code**: `contracts/domain_expertise.py:102-145` and `:349-392` drop `trace_id` from `to_semantic_dict`, `:395-408` strips it in `expertise_id()`, and `:217-259` drops `trace_id` + `evaluation_time` from the slice address (`graph_version` deliberately kept, line 244). It is `0076` that has not been applied.

### Sections that have closed

- **"The 68 pending capabilities need Layer 1 connectors" (lines 430-432) — now 32**, and this file's own document-store item is closed (`context/document_register.py`, `context/documents.py`, the `capture/connectors/drive.py` projection). The 32 that remain: Admin 21 (compliance, facilities, people, travel, PO, budget), CS 7 (diagnosis-and-resolution ×4, escalation-and-incident ×3), Sales 4 (`demo`, `tam_sam_som`, `cold_calling`, `linkedin_outreach`).
- **"A hazard worth knowing" (lines 434-441)** — that running the suite registers `BUILTIN_PACKS` into whatever `GENIOS_DATABASE_URL` points at — **is CLOSED.** `tests/conftest.py:41-47` pins `GENIOS_DATABASE_URL` (to `GENIOS_TEST_DATABASE_URL`, else `""`), and `tests/test_tests_never_touch_production.py` guards it (`d860b8e`, `ae63ef9`). That section should be read as history.
- **"Recommended order from here" (lines 445-456) is entirely stale.** Item 1 was done in this file's own session 2; items 2 and 3 ("166 skeleton playbooks", "76 hollow capabilities") are contradicted by `admit.py --check` → 0 hollow and `validate.py` → 0 errors; item 4 (an Admin/CS L2 lane) is largely built — `context/support_situations.py`, `context/periodic.py`, `context/document_register.py`.
- **"Evidence, not routing, is now the constraint" (lines 426-429) — partially closed.** `97aeb46` shipped the account-level roll-up (`derived.contact_frequency` + `contact_rate_per_account` across `works_at`, written by `reason/baselines.py`); `867dae8` fixed `actor.name` at capture, where 69 of 115 cards had been headlining an email address; `0eaf94e` split the overloaded name into `derived.person_contact_rate` and `derived.account_distinct_contacts`. Both new names are in `planned_substrate` with **no writer yet**. Live per-anchor fact density: **UNVERIFIED**.
