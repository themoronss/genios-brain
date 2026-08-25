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

# Phase 2 — the corpus, not the code (surveyed 2026-08-25)

The cutover works. What limits it now is authored content, and the survey is not what the
capability count suggests:

| Module | capabilities | Phase-1 stubs | situation files |
|---|---|---|---|
| Sales | 46 | **43** | 7 (only 1 account-scoped) |
| Customer Support | 49 | 0 | 14 |
| Admin | 57 | **0** | **0** |

Two different problems wearing one label:

- **Sales** — 43 of 46 capabilities carry identity, purpose and an object load-set and nothing
  else ("Phase 1 stub — promote by adding outcomes, playbooks, heuristics, mental_models, kpis,
  handoffs and situations"). The tenant is on the `sales` pack, so this is what the design partner
  actually sees.
- **Admin** — fully authored and completely unroutable: zero situation files, so no L2 output can
  ever reach any of its 57 capabilities. Content without a route is invisible.
- **Customer Support** — the only module with both halves.

## Why 18 cards read identically

`routes` is built per L2 `situation_type` from the situation files, and a route only forms through
a capability that is not a stub. Sales has exactly one account-scoped situation
(`inbound_fit_check` → `opportunity`), so every company-anchored situation compiles through one
capability and produces one template with the domain name swapped.

L2 emits seven types on the design partner's org: `relationship` (25), `opportunity` (18),
`investor_relationship` (11), `account_admin` (2), `recruiting_company` (2),
`partnerships_company` (1), `investor_company` (1). Six of the seven have no account-scoped route.

## Work order, highest leverage first

1. **Promote `sales.post_sale_and_growth.customer_success`** out of stub, then
   `sales.sit.live_account_relationship` (already written, loads, waiting on its owner) starts
   routing — 25 situations, the largest single bucket.
2. **Author `investor_relationship`** — 11 situations. NOT a sales situation: an investor is not a
   customer, which is why `relationship.nature` distinguishes them. It needs its own capability
   whose failure mode is treating a fundraising conversation as a lost deal.
3. **Give Admin its situation files** — 57 authored capabilities currently unreachable. Start with
   `account_admin`.
4. **Promote the remaining Sales stubs** in the order their situation types actually occur.

## What is NOT the problem

Code. Capture, context, reasoning, delivery and the audit chain are all live and verified against
the real org. Nothing below this line needs an engineer; it needs authored expertise.
