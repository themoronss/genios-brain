> **Created:** 2026-09-08 · **Status:** 🟢 Active — Wave A landed and measured; Wave B named, not built
>
> **Purpose:** Close the defect Layer 3 shipped with — the four brains hold knowledge and cannot
> bind it to a live situation — by giving a situation and a brain entry ONE address vocabulary, and
> by connecting the activation table that already exists to the runtime that never read it.

# Layer 3 · brain binding

## 0. The one-sentence diagnosis

Layer 3's problem was never missing expertise. It was **addressability**: the corpus, the tenant's
policies, its measured behaviour and its stated preferences all existed, and nothing could answer
*"which of this applies to THIS situation?"* — so none of it applied to any of them.

`scripts/l3_pilot_report.py` measured the end state and could not explain it:

```
packages_with_a_brain_slice     0     across 4 compiled packages
learned_brain_entries_active    organization 5, behavior 6
adaptive_leases_active          1
```

Full brains. Zero reach.

---

## 1. What was verified in code before anything was changed

Every row re-checked against the working tree, not read from a report.

| # | Claim | Verified at |
|---|---|---|
| 1 | The per-domain activation table has **no production caller** | `reason/runner.py:1394` read `get_settings().use_domain_compiler`; `activated_domains()` appeared only in tests, `api/admin_routes.py` and the pilot report |
| 2 | `brain_subject_keys` has **two readers and no writer** | `contracts/domain_expertise.py:506`, `contracts/situation.py:832`; no writer anywhere in `genios_engine/` |
| 3 | The Adaptive lease store is **never read** | `PostgresRuntimeBrains.snapshot` selected `learned_brain_entries` only; leases live in `temporary_memories` (migration 0045) |
| 4 | Organization entries **cannot match** | subject is `orgrule:<category>:<subject_type>` (`org_discovery.py:254`) and the value carries no `capability_id` |
| 5 | Behaviour identities **cannot meet** situation identities | subject is `behavior:<metric>:<node_id>`; `gather_members` groups by `actor->>'email'` (`situation_bso.py:783`) |
| 6 | SQL and Python **disagreed** about the same match | the Postgres prefilter's `':'||sel||':'` substring test matched colon-bearing selectors that `set(subject.split(":"))` then discarded |
| 7 | `works_at` direction | `pipeline._works_at` writes person → company; `derived.compute_deal_view` read `e.from_node_id as company`, with no node-type filter and no `valid_to is null` |
| 8 | A percentage threshold costs the whole rule | `org_discovery.gate_candidates` validated `threshold_as_written` through ALG-10, a **Money** parser |
| 9 | The expert's sentence never reaches the card | `deliver/` had **zero** readers of `signals.citations` |

Two more were found only by driving the fixed path, and both were invisible behind the others:

| # | Found while fixing | Why it was invisible |
|---|---|---|
| 10 | **Every L6-published brain entry crashed the compiler's row mapper.** `contracts/learning.Visibility.derived_from` is a `list`; `contracts/visibility.Visibility.derived_from` is a `str`. `RuntimeBrainEntry.__post_init__` raised, `shadow_compile` caught per situation, and the **whole package** — not just the brain slice — was never built | the selector never returned a row, so the mapper was never reached |
| 11 | Putting the address in the situation's content hash **re-mints an expertise package every sweep** | it could only appear once an address existed; caught by `l3_pilot_report`'s `worst_addresses_per_situation`, which read **3** for one situation. This is the mechanism of the 995 MB read-only incident |

---

## 2. Wave A — landed

### A1 · One address vocabulary — `contracts/brain_address.py` (new)

A situation and a brain entry now speak the same language: a **set of `kind:value` tokens**, and
selection is set intersection.

```
org · orgwide · domain · capability · object · situation · situation_type
node · email · person · company · jurisdiction · metric · actor
```

Deliberate properties:

* **A set, not a path.** A rule can be about a company AND a capability AND a jurisdiction at once;
  a hierarchy would force an author to file it under one.
* **No wildcards.** A token matches itself. `orgwide` is the single "this tenant, everywhere" token,
  minted only by `org_scope`, and `BrainAddress` **refuses** it for Behaviour and Adaptive — an
  observation that bound everywhere would be a rule nobody approved.
* **Legacy subjects still resolve.** `legacy_tokens` derives what an address-less subject implies,
  so pre-contract rows bind with **no backfill** — Layer 6 owns publication and Layer 3 does not
  rewrite what it is handed.

### A2 · The writer — `situation_bso.gather_brain_subject_keys`

Resolves the situation's **email-keyed** members to their graph node ids through
`graph_nodes.canonical_key` (one indexed query per situation) and emits both identities under their
own token kinds. This is the hop that lets a Behaviour pattern measured on a node reach a situation
known by address. Wired into `domain_shadow` beside the other gathers.

### A3 · Selection with receipts — `packs/compiler/runtime_brains.py`

`_relevant` returns **the matched tokens**, not a boolean, and they land on every evidence row as
`selection_basis`. Four match paths in descending trust: address → the entry's own `capability_id` →
whole subject key → `:`-segment intersection (reported as `legacy_segment`, so a match resting on
the pre-address heuristic is visible). The SQL prefilter was widened to agree with Python.

### A4 · The reader that never existed

`PostgresRuntimeBrains.snapshot` now unions `temporary_memories`, filtered on
`expires_at > :eval_time` — **the sweep's frozen clock, threaded from `SituationContextSlice`**,
never `now()`. With no evaluation time it reads **no** leases: a missing clock is a reason to apply
no preference, not a licence to invent one.

### A5 · Activation actually decides

`runner.run_all` reads `activated_domains(engine, org_id)` once per sweep and passes it to
`shadow_compile`, which now holds **two compilers on one connection** and picks per situation from
`l3_domain_for(row["domain"])`. Admin live and Sales shadow in the same sweep, from the same read.
`use_domain_compiler` is untouched and still forces live everywhere — it is now a kill switch, which
is what the L3 plan says it should become.

### A6 · `works_at` direction, node type, edge validity

`derived.compute_deal_view`'s two remaining roll-ups now traverse **both** directions, decide
membership on **node type**, and honour `e.valid_to is null` — the rule `_person_neighbours`'
docstring already stated and fixed only for itself.

### A7 · A percentage is a threshold

`contracts/units.Ratio` + `parse_ratio` (deterministic, total, locale-free). The CLG-09 gate reads
the same characters a second time and refuses only when **both** dimensions fail. The bound survives
into `authority_rules.threshold_basis_points`, mutually exclusive with the money column by contract
and by check constraint — a discount rule projected with both columns null would read as "any
discount needs the founder", stricter than the policy, written by an omission.

### A8 · The quote reaches the human

`deliver/pipeline` selects `s.citations`; `card_builder._why` carries up to two authored statements,
**verbatim**, tagged `source: "expertise"`.

### A9 / A10 · The two found-while-fixing defects

`_normalize_l6_visibility` now absorbs the `derived_from` list→string difference as well as the
scope alias. `BusinessSituationObject.address_free_metadata` keeps `brain_subject_keys` **out of the
content address** — the address decides which knowledge is selected, and the selected knowledge is
itself part of the package, so the package still addresses differently when the knowledge differs.

### Migration

`migrations/0127_l3_brain_binding.sql` — additive and idempotent. Two GIN indexes
(`jsonb_path_ops`) on `value->'address'->'tokens'`, `authority_rules.threshold_basis_points`, and
two `NOT VALID`-then-validate check constraints. **No backfill**, by design.

---

## 3. Measured, not asserted

Driven through the production publishers and the production compile on a scratch Postgres.

```
J5 · scripts/l3_pilot_report.py --org pk_l3_brains_speak

  packages_with_a_brain_slice              2      (was 0)
  cards_quoting_the_claim_in_their_own_copy 2     (was 0 on every card ever built)
  worst_addresses_per_situation            1      (no package churn)
  passed                                   true   (8 of 8 checks)
```

All three brains reach a compiled package, each was blocked by a different fault, and the control
holds: a Behaviour pattern measured on a person **no** situation is about does **not** bind. Every
applied entry names the token that selected it and **none** rests on the legacy heuristic.

**Suite: 9,629 passed · 152 xfailed · 0 skipped · 0 failed**, against a pristine Postgres — the
zero-skip proof §5 of the build record said did not exist (it reported 334 passed / 108 skipped).

New tests: `test_all_three_runtime_brains_reach_a_compiled_package`,
`test_an_expired_adaptive_lease_is_not_applied`,
`test_a_percentage_threshold_now_reaches_the_brain_with_its_bound_intact`.

---

## 4. What is NOT done

### 4.1 The audit-readiness situation is not built, and Anisha was an example

The scenario was an illustration of the general failure, not a requirement, so **no audit-specific
register, object or route was built** — that would have been a special case for one shape while the
mechanism stayed broken for every other. What Wave A fixes is the mechanism, and `audit_support`
remains deferred in `Domain Expertise/Admin Expertise/deferrals.yaml:153` as `no_runtime_trigger`,
for the reason authored there and still correct: *an audit request arrives as an email and is
indistinguishable from any other information request.*

Un-deferring it needs a **trigger that is not a guess** — an executable audit situation with a
declared requirement population — and that is a business-model decision, not a Layer 3 one.

### 4.2 The two `BusinessSituationObject` contracts are still two

`contracts/domain_expertise.py:405` (the v1 dataclass the live publisher builds) and
`contracts/situation.py:551` (the strict v2 model). `models.entity_fields()` absorbs the difference
at the compiler boundary. Unifying them touches every L2/L3/L4 path and belongs in its own wave with
its own gate — not folded into a round that changes selection.

### 4.3 Behaviour binds only through the anchor on today's fixtures

`gather_members` returns `[]` for the pilot seed's situations, so the email→node hop is exercised by
`gather_brain_subject_keys` directly rather than end-to-end on a correlated situation. On a real
tenant with correlated correspondence it is the main path. Worth re-measuring on the design
partner's org.

### 4.4 Pre-address entries still bind through `legacy_segment`

Intentional — nothing that binds today stops binding — but it is reported per entry, so the
population can be counted and the legacy lane deleted when it reaches zero.

### 4.5 Test isolation

`tests/reason/adapters/test_l3_pilot_report.py` accumulates packages across runs against a warm
scratch database and then trips its own `worst_addresses_per_situation` guard. **Drop and recreate
the scratch database between full runs.** Pre-existing; not introduced here.

---

## 5. What has to be done outside the code

1. **Apply `0127_l3_brain_binding.sql` to production.** Additive, no backfill, no lock of
   consequence. `python -m genios_engine.platform.migrate`.
2. **Activate one tenant, one domain** — the switch now does something:
   `POST /v1/admin/l3/activate {"org_id": "<pilot>", "domain": "admin"}`.
   Leave `use_domain_compiler` unset; it is the kill switch, not the unlock.
3. **Confirm the pending policy proposals** for that tenant, or the Organization brain stays empty:
   `GET /v1/learning/objects?state=human_review&target=organization` →
   `POST /v1/learning/objects/<id>/review {"approve": true}`.
4. **Let the weekly learning pass run** so Behaviour patterns exist to bind.
5. **Read the row after seven days:**
   `python scripts/l3_pilot_report.py --org <pilot> --days 7 --database-url "<url>"`.
6. **Resolve the repository's half-finished merge** — 28 unmerged index entries with no `MERGE_HEAD`
   (`app/`, `_legacy_brain/`, `genios-dashboard/`). It blocks committing.

---

## 6. Plan alignment

* *No global boolean flags; activation is a table* — A5 is that rule applied to the seam its own
  standing counterexample (`use_domain_compiler`) was left dark by.
* *A layer isn't done until every piece is present or flagged* — §4 flags five, including the two
  this round deliberately did not take.
* *Store, don't delete* — no pre-address entry is rewritten or dropped; `legacy_tokens` reads them
  where they are.
* *No claim without a receipt* — `selection_basis` on every applied entry.
* *v1/v2 is internal* — no user-facing string here names either.
