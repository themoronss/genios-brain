> **Created:** 2026-08-25 · **Status:** Active
> **Purpose:** Switch card generation from the legacy pack rules to the compiled L3 capability corpus. One plumbing step remains.

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
| L5 deliver | Cards visible in the desktop app (13). Still authored by the LEGACY rules — `cards.capability_key` is NULL on all of them. |
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

## The one step left

`domain_shadow.shadow_compile(live=True)` must persist the audit bundle and then the signal.
The code was written and reverted while blocker #8 was still open; #8 is now fixed.

- `_persist_live(store, org_id, node_id, package, execution, eval_time)`:
  call `reason.audit.persist_execution(store=ReasoningStore(engine=store.engine), execution=...)`
  FIRST — `signals` carries six FKs into the reasoning audit tables and a hand-made run id fails
  all of them — then, in its own transaction, `PostgresExpertisePublisher(conn).publish(package)`
  and `_emit_capability_signal(...)` using the returned `run_id` and the request's
  `config_snapshot_id`.
- Per-situation transactions, NOT one for the loop: a single wrapping transaction meant one
  unroutable row aborted the other 58 with `InFailedSqlTransaction` (`error: 58`).
- Column shapes already learned the hard way: `signals.pack_version` and `rule_version` are
  INTEGER (the capability's hash goes in `capability_version`, which is text);
  `authority_pack_revision` must be > 0 when `authority_binding_version = 1`; naming a
  `reasoning_run_id` obliges a `config_snapshot_id`.

### Where the live path stops today (walked end to end, 2026-08-25)

Every schema obstacle below was hit in order and solved; they are listed so the next attempt does
not rediscover them:

1. one transaction for the whole loop → one bad row aborts 58 (`error: 58`) → per-situation txn;
2. `pack_version` / `rule_version` are INTEGER, not the capability's hash;
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

**9 — THE OPEN ONE.** The signal insert now fails only on `signals_reasoning_candidate_fk`
`(org_id, reasoning_run_id, reasoning_candidate_id)` → `reasoning_candidates`. Candidates ARE
written, so the mismatch is which RUN they belong to: `persist_execution` is idempotent on
`idempotency_key`, so a re-run returns an EARLIER bundle whose candidate ids differ from the
decision now in hand. Either take the candidate id from the returned bundle rather than from
`decision.selected_candidate_id`, or make the idempotency key vary with the decision content.
Check `bundle["candidates"]` against `decision.selected_candidate_id` first — one print settles it.

**Superseded.** `ReasoningStore.persist_complete` (store.py:925) requires
`config.snapshot_id == recomputed_config_id` and `config_pack == capability_pack`. A hand-made
`cfg_{version}` id cannot satisfy the first: the store recomputes the snapshot id from the
`effective` config content. So the compiled lane needs a config snapshot built the way the store
recomputes it — same canonical `effective` payload, same pack id as the capability's domain —
rather than a synthetic row. Read `_recomputed_config_id` in store.py and mint the snapshot
through the same function the legacy lane uses.

Then: verify `signals.capability_id IS NOT NULL` is non-zero and cards render from it, and only
then flip `GENIOS_USE_DOMAIN_COMPILER=true`.

## Do not flip the env var before that

With the compiler on but nothing emitted, the new brain reasons and produces no cards, and the
legacy rules keep producing all thirteen. Turning it on early changes nothing except spend.

## Known open, beyond the cutover

- Only 1 of 152 capabilities routes (`expertise.opportunity`); 17 of 60 situations find no route
  and 23 are incomplete. Routing is a corpus question, not a code one.
- `deal.value` is absent and deliberately never derived — no honest way to infer a number nobody
  stated, and a wrong one flows straight into prioritisation.
- L2 worker count: confirm from `/health/readiness` before changing it. Every previous estimate
  was inference, and inference has been wrong here repeatedly.
