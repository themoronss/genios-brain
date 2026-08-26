> **Created:** 2026-08-25 · **Status:** Active
> **Purpose:** Switch card generation from the legacy pack rules to the compiled L3 capability corpus. The live path is DONE and proven on the design partner's org; the env var is the remaining flip.

# Where we actually are

## The issue, in one paragraph

The compiled brain (152 authored capabilities, 1300 corpus files) was built in SHADOW mode from
the first commit — `0849508 "port Domain Expertise compiler (shadow/dark)"`, `9c7ce4c "live shadow
wiring"`, `7da562e "...SHADOW mode + live_delivery_enabled=False (nothing persisted/emitted)"`.
Every commit says so. It was reported as "wired", which was true of the pipes and not of the
valve, and the distinction was never made explicit. Three switches were off simultaneously:
`use_domain_compiler=False`, `publisher=None`, `live_delivery_enabled=False`. So every card every
tenant has ever seen came from the legacy `sales_v1` / `general_v1` rules.

That is the whole answer to "purana kyun chal raha hai". Not a regression, not a bug — a final
step that was never taken, described as if it had been.

## Layer status (verified against the design partner's live org, 2026-08-25)

| Layer | State |
|---|---|
| L1 capture | Fixed and deployed. 59 → 94 emails/min (page prefetch overlaps the ~16s provider wait with the ~16s capture). |
| L2 context | `derived.*` now has a writer (was read by every deep rule and written by nothing). Deal + commitment roll-ups added. Worker count still resolves to ~3, not 8 — read `/health/readiness` `concurrency` after deploy before tuning. |
| L3 reason | Compiled brain now DECIDES: 18 decisions, 72 eligible candidates, up from 18 × INSUFFICIENT_CONTEXT. |
| L5 deliver | **The compiled brain now authors cards.** 18 of the 28 queued cards carry `capability_key='expertise.opportunity'`; the other 10 are the legacy rules, running alongside. Verified through `GET /cards` — the desktop app's own endpoint. |
| L6 learn | Untouched today. |
| L7 feedback | Untouched today. |

## What was fixed today (all pushed, 1640 tests green)

1. `derived.engagement` / `.sentiment` / `.momentum` had no writer at all. Read by the sales pack
   (`derived.engagement <= 0.5`) and required by every compiled capability. This is why the queue
   is nine `unanswered_email` cards out of thirteen: the shallowest rule is the only one whose
   inputs existed. → `context/derived.py`, deterministic, no LLM.
2. Situations anchor on a `company`, and 15 of 18 companies hold zero facts — everything lives on
   the people and threads beneath. The neighbourhood reached the compiler but not the reasoner.
3. Nothing was ever published: `publisher=None`, `expertise_packages` had 0 rows.
4. A signal could not name which brain authored it → migration 0074.
5. Commitments sit two hops out (company → person → commitment); a 1-hop neighbourhood cannot see
   them. Also a name gap: the pipeline writes `commitment.text`, readers ask for `commitment.action`.
6. `required_fields` answered two questions with one value — what to PULL and what GATES a
   decision. One value-dependent pattern (`deal.value`) vetoed whole capabilities. Split into
   `required_fields` (gate) and `selection_fields` (pull).
7. `selection_fields` was added to the dataclass but not `to_semantic_dict()`, so
   `capability_snapshot_id` and the audit store's hash diverged and NO manifest could be audited.
8. `version` was `exp.{knowledge_hash}` while the manifest also varies per situation, so two
   manifests shared one version and the immutability guard refused the write.

## The step that was left — now done

`domain_shadow.shadow_compile(live=True)` persists the audit bundle and then the signal. Built and
proven live on 2026-08-25; the shape below is what it does.

- `_persist_live(store, org_id, node_id, package, execution, eval_time, pack)`:
  call `reason.audit.persist_execution(store=ReasoningStore(engine=store.engine), execution=...)`
  FIRST — `signals` carries six FKs into the reasoning audit tables and a hand-made run id fails
  all of them — then, in its own transaction, `PostgresExpertisePublisher(conn).publish(package)`
  and `_emit_capability_signal(...)` using the returned `run_id` and the request's
  `config_snapshot_id`.
- Per-situation transactions, NOT one for the loop: a single wrapping transaction meant one
  unroutable row aborted the other 58 with `InFailedSqlTransaction` (`error: 58`).
- Column shapes already learned the hard way: `signals.rule_version` is INTEGER (`pack_version` is
  TEXT and holds the tenant pack's version, e.g. `1.13.0`; the capability's hash goes in
  `capability_version`, which is text);
  `authority_pack_revision` must be > 0 when `authority_binding_version = 1`; naming a
  `reasoning_run_id` obliges a `config_snapshot_id`.

### Where the live path stops today (walked end to end, 2026-08-25)

Every schema obstacle below was hit in order and solved; they are listed so the next attempt does
not rediscover them:

1. one transaction for the whole loop → one bad row aborts 58 (`error: 58`) → per-situation txn;
2. `rule_version` is INTEGER, not the capability's hash (`pack_version` is TEXT — the earlier note
   said both were INTEGER; only `rule_version` is);
3. `authority_pack_revision` must be > 0 when `authority_binding_version = 1`;
4. naming a `reasoning_run_id` obliges a `config_snapshot_id`
   (`signals_linked_run_requires_config`);
5. six FKs into the reasoning audit tables → call `audit.persist_execution` first, never
   hand-make a run id;
6. `config_snapshots` PK is `(org_id, snapshot_id)`, not `snapshot_id`;
7. `request_id` is derived from request content, so a `config_snapshot_id` injected with
   `dataclasses.replace` AFTER reasoning invalidates it — the snapshot must exist before
   `reason_native_capability` is called and be passed in as an argument.

**8 — SOLVED.** Mint the config snapshot through `packs.snapshot.snapshot_id` over
`{"pack_id": capability.domain, "version": ..., "capability_id": ...}`, write it to
`config_snapshots` with `pack_id = capability.domain`, and pass the id into
`reason_native_capability` BEFORE reasoning. With that, `persist_execution` succeeds — the audit
bundle (run, results, candidates, checks, output) now commits, verified live: real `rrun_…` ids in
`reasoning_runs` and `cand_…` rows in `reasoning_candidates`.

**9 — SOLVED, and the stated hypothesis was wrong.** The signal insert failed on
`signals_reasoning_candidate_fk` because a persisted candidate id is NOT the contract id the
decision holds. `ReasoningStore._prepare_candidates` mints the DB key as
`stable_id("cand", {run_id, candidate_hash})` and keeps the contract id only as an in-memory alias
(`external_candidate_id`) that is never written — deliberately, since a contract candidate id is
semantic and repeats across replays while the DB key is tenant-wide. So
`decision.selected_candidate_id` names a row that cannot exist. Idempotency was a red herring:
printing the bundle proved it (`idempotent_reuse: False` on a fresh run, ids still disjoint).

The fix is to read every audit id off the persisted bundle rather than off the decision:
`bundle["output"]["selected_candidate_id"]` (the alias already resolved to the row's real key),
`bundle["output"]["decision_hash"]` (the store's hash, not the contract's — `signals` has an FK on
that too), and `bundle["run"]["config_snapshot_id"]`. That also makes an idempotent reuse correct
for free: the ids then belong to whichever run actually holds the rows.

**Superseded.** `ReasoningStore.persist_complete` (store.py:925) requires
`config.snapshot_id == recomputed_config_id` and `config_pack == capability_pack`. A hand-made
`cfg_{version}` id cannot satisfy the first. Resolved not by minting a synthetic row but by using
the tenant's REAL effective config — `registry.effective(org_id, pack_id)`, the same snapshot the
legacy lane already consumes — with `pack_id` taken from the capability's `domain` (`sales`, for
this corpus). See obstacle 12: that is also the only config a card can be delivered under.

### Four more obstacles, found past the signal insert (2026-08-25)

Emitting the signal was not the last step; the delivery authority predicate then rejected all 18.
`AUTHORITATIVE_SIGNAL_PREDICATE` re-derives a signal's projection from the audit bundle and drops
anything it cannot reproduce, so each of these was a silent zero-card outcome:

10. **`signals.score` must equal `(selected_rc.final_utility_bp + 50) / 100`** — the selected
    candidate's utility, not the decision's confidence. A projection that disagrees with the
    audited decision is exactly what the check exists to catch.
11. **`rule_id` and `reason_code` must both be the capability id's last segment** —
    `expertise.opportunity` -> `opportunity` (`regexp_replace(rr.capability_id, '^.*\.', '')`).
    The compiled lane therefore cannot live in a private `pack_id='expertise'` lane: the signal has
    to sit in the tenant's own pack, bound to its active version and `authority_revision`. The two
    brains still cannot evict each other, because the open-signal key includes `rule_id` and no
    legacy rule id collides with a situation type (checked: 25 rules across sales 1.13.0 and
    general 1.4.0). A future collision is refused and logged rather than silently overwriting.
12. **`live_delivery_enabled` must be true on the capability snapshot.** The adapter hardcoded
    `False` ("advisory until cutover"); the predicate reads it directly, so no compiled decision
    could ever have become a card. It is now a parameter, False by default and True only on the
    cutover path.
13. **The delivery query never selected the capability columns.** `card_builder` has read
    `signal["capability_id"]` since 0074, but `_open_signals_without_cards` did not carry it, so
    `cards.capability_key` was NULL for compiled and legacy signals alike — the cutover could not
    be measured from `cards` at all, because NULL meant both things at once.

Two more things the live path needed to be sweep-safe rather than merely correct once:

* **A cooldown.** The legacy lane will not re-publish a rule/node inside its cooldown window. The
  compiled lane had no equivalent, so every sweep would expire and rebuild all 18 cards — a queue
  that reshuffles under the user, and an LLM render paid for each time. It now leaves a signal
  alone while its own authority window still stands. (A decision-hash comparison cannot serve:
  `expires_at` derives from the evaluation time, so the hash differs every sweep regardless.)
* **Per-situation transactions, and a publisher that owns its own.** The compiler is built once and
  holds its publisher for the whole loop, so the publisher — not the loop — has to open the
  transaction (obstacle 1).

### Verified live on the design partner's org, 2026-08-25

Every claim below was run against `org_e97e86f858ad48b2bbf64b8a`, not against tests.

| Check | Result |
|---|---|
| `signals.capability_id IS NOT NULL` | **18** (was 0) — all open, `pack_id='sales'`, `pack_version='1.13.0'`, `authority_pack_revision=5` |
| `cards.capability_key` | **18 of 28** queued cards carry `expertise.opportunity`; 10 are legacy |
| Desktop app | `GET /cards` (the app's own endpoint) returns 28 cards, 18 of them compiled-brain |
| Re-run | second live pass reports `standing: 18`, `emitted: 0` — no card churn |
| Tests | 1640 passed, 15 skipped, 152 xfailed |

## Flip the env var now — and know what it does

`GENIOS_USE_DOMAIN_COMPILER=true` on the backend. One correction to the earlier note: the flag used
to run a MEASUREMENT pass, so flipping it would have produced packages, decisions and no cards —
a switch that reads as a cutover and behaves as a dry run. It now runs the live pass. Measurement
remains available to any caller as `shadow_compile(live=False)`, which is what the tests use.

The compiled brain runs ALONGSIDE the legacy rules, not instead of them: separate rule ids,
separate signals, both delivering. That is the point — it is how the two get compared on live
traffic instead of being swapped blind.

## Known open, beyond the cutover

- Only 1 of 152 capabilities routes (`expertise.opportunity`); 17 of 60 situations find no route
  and 23 are incomplete. Routing is a corpus question, not a code one. This is now the LARGEST
  remaining gap: the cutover works, and it currently carries one capability's worth of advice.
- Every compiled card renders as an `observation`, never a prescription, because no capability in
  the corpus has been accepted by a named reviewer (`review_state='draft'`). That is the abstention
  gate behaving correctly, not a defect — but it means the compiled brain describes rather than
  instructs until the admission ceremony is run on real content.
- 11 of the 18 compiled cards rendered `raw_slot` rather than `llm` — a fallback body, not authored
  copy. The renderer's grounding rejected the compiled situation text for those 11. Worth a look
  before the corpus widens, since it is the difference between a card that reads as advice and one
  that reads as a stub.
- `CardStore.claim_build` refuses a claim when ANY card row exists for the signal, including an
  expired one — so the pipeline's "an expired card reopens the door for a rebuild" comment is not
  true in practice. Pre-existing, found while rebuilding cards during this work; not fixed here.
- `deal.value` is absent and deliberately never derived — no honest way to infer a number nobody
  stated, and a wrong one flows straight into prioritisation.
- L2 worker count: confirm from `/health/readiness` before changing it. Every previous estimate
  was inference, and inference has been wrong here repeatedly.

---

# Phase 2 — the corpus, not the code

> Surveyed 2026-08-25. Worked in three batches on 2026-08-26 — commits `9ddeeed`, `087d4e6`,
> and the one carrying this edit. Every number below was measured against
> `org_e97e86f858ad48b2bbf64b8a`, not against tests.

## Where Phase 2 stands

| Measure | Before (2026-08-25) | Now |
|---|---|---|
| Situations routing | 52 / 60 | **55 / 60** |
| Compiled / decided | 52 / 52 | **55 / 55** |
| `no_route` | 6 | **3** |
| `required_missing` | 2 | 2 (unchanged) |
| Compiled cards rendering `raw_slot` | 11 of 18 | **the four causes are fixed; see below** |
| Live routes compiling through a placeholder capability | 3 of 4 types | **0 of 3 sales types** |
| Tests | 1640 | **1675** |

## Batch 1 — the compiled brain now writes its own cards (`9ddeeed`)

Eleven of eighteen compiled cards rendered `raw_slot`, and ten shipped the literal word "open" as
their situation line. Four independent causes:

1. **No template.** `card_builder` reads `effective["templates"][reason_code]` from the TENANT
   PACK; a compiled signal's reason_code is its situation type, which no pack authors. Empty
   render_hint meant no guidance in the prompt (all eighteen cards read alike); empty fallback
   meant a rejected line shipped the default `{stage}` slot. Fixed by authoring the copy in the
   corpus: situation files carry a `render:` block that travels situation → RoutePlan →
   ExpertisePackage → CapabilityManifest → `rcap.manifest` → the delivery SELECT. The wording is
   pinned to the capability version that produced it.
2. **Sentinel slots were handed to the model as facts.** `compute_slots` fills an absent fact with
   a placeholder so the deterministic template stays grammatical; the prompt presented all of them
   as "Key slots" and the model wrote down what it was told. On live facts the model's slot set
   drops from seven values to two, both real.
3. **V-01 threw away a good sentence.** Ten of eighteen situations came back 142–158 characters
   against a 140 cap. An over-cap line now drops whole trailing SENTENCES while any complete
   leading sentence fits; Law 3 holds (nothing cut mid-word).
4. **V-02 rejected contractions as invented companies.** "We've" → "Weve" → not in any dictionary
   → invented entity. Eight of eleven artifact rejections were this.

## Batch 2 — three of the six `no_route` were a vocabulary gap (`087d4e6`)

- **`investor_company` (1)** — `investor` is the model's word for the registered `fundraising`
  domain; they never met, so the type fell to the generic `<domain>_<anchor>`.
  `domain_spec._ALIASES` canonicalises at `resolve_domain`, and `refresh_situations` re-derived the
  org's 83 situations. Routes and delivers.
- **`recruiting_company` on `thegenios.com` (1)** — `is_platform_sender` kept the product's own
  address out of the person graph but `_works_at` still minted the company node, so the product's
  own website was a counterparty inside a customer's graph. Fixed for everything created from here;
  the one existing correlation row is stale data, left rather than deleted from a live org unasked.
- **`account_admin` (2)** — Admin had 57 authored capabilities and zero situation files, so the
  domain was content with no door. `admin.sit.live_account_admin` authored on `commitment_tracking`.
- **`recruiting_company` + `partnerships_company` on `boardy.ai` (2)** — NOT authored, deliberately.
  boardy.ai is an introduction bot the pipeline already classifies as non-anchoring infrastructure,
  and no Recruiting or Partnerships expertise exists in any corpus. Authoring a domain to serve an
  introduction bot would be authoring a corpus for noise.

## Batch 3 — the stubs that were actually on a live route

`identity.stub` had already been flipped to `false` across the corpus, so `index.py` reported
"0 stub" while 136 capabilities carried a name, a sentence, a question and nothing else — every one
of them `status: stable`, `review_status: approved` and hash-pinned. **The admission ceremony asks
whether a named human approved these exact bytes and never asked whether there were any bytes worth
approving.**

Promoted the three that were on a live route: `account_research` (reached by all 55 routed
situations, serving all three sales types), `lead_generation` (18), `expansion` (23). Every sales
situation type on the live org now compiles entirely through capabilities that carry real
expertise — measured, not assumed:

| type | capabilities | hollow |
|---|---|---|
| `opportunity` | 4 | 0 (was 2) |
| `relationship` | 3 | 0 (was 2) |
| `investor_relationship` | 2 | 0 (was 1) |
| `account_admin` | 3 | 3 — the whole Admin domain is unpromoted |

Hollowness is now **reported and not gated**, in two places: `_tools/admit.py --check` prints a
per-domain promotion queue, and the compiler records `hollow_capability_ids` on the package. It is
deliberately kept OUT of `admission_gaps`, because that list drives `review_state`, which decides
whether a card may instruct — folding a content observation into it would make "thin" silently mean
"unauthorised". Gating it today would un-route `account_admin` entirely and take coverage backwards.

## What is left, and the honest blockers

1. **`account_admin` routes but CANNOT DELIVER.** `ReasoningStore.persist_complete` refuses a write
   unless `config_pack == capability_pack`. The capability's domain is `admin`; the only pack
   modules that exist are `sales_v1` and `general_v1`, and the tenant holds sales@1.13.0 +
   general@1.4.0. A live compile counts these under `no_tenant_pack` and emits nothing. **The same
   is true of all 49 Customer Support capabilities.** This is the largest structural gap left: the
   corpus can author a domain the tenant has no lane for, and nothing in the authoring path says so.
   The honest unblock is an `admin` pack module plus a tenant promotion.
2. **136 hollow capabilities** — 57 admin, 40 customer_support, 39 sales. Only the sales ones can
   reach a user today. Promote in the order their situation types actually occur.
3. **`required_missing` (2)** — two `relationship` situations want
   `customer_support.obj.core.{customer_account,named_contact,support_plan}`, which are referenced
   and not authored. A Customer Support object gap reached through a sales route.
4. **`recruiting_company` / `partnerships_company` (3)** — see Batch 2; not a corpus gap.
5. **`review_state` is still `draft` on every live package**, so every compiled card is an
   `observation`. That is the abstention gate behaving correctly. It flips only when
   `require_admission=True` compiles find no admission gaps at all.
6. **`CardStore.claim_build` refuses a claim when ANY card row exists for the signal**, including an
   expired one — so the pipeline's "an expired card reopens the door for a rebuild" comment is not
   true in practice. Pre-existing, unfixed.
7. **`deal.value`** is absent and deliberately never derived.
8. **L2 worker count**: confirm from `/health/readiness` before changing it.

## How to re-measure

```
PYTHONPATH=. .venv/bin/python scripts/corpus_route_probe.py          # per-type route coverage
PYTHONPATH=. .venv/bin/python "Domain Expertise/_tools/admit.py" --check   # admission + hollow queue
```
