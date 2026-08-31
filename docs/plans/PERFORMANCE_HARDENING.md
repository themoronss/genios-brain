> **Created:** 2026-08-11 · **Status:** Active — P1, P2, P4, P5 shipped; **P2b and P3 are the only open items** (see the re-verified status at the foot of this file)
> **Purpose:** Make the pipeline fast across all layers (L1→L4) without increasing Supabase load — the reasoning pass currently takes ~30 min for one org's month of data because it does thousands of small, per-node DB round-trips.

## Measured problem (this session)

A full L3 reasoning pass over the Rohit org (463 graph nodes) ran **30+ min and never reached signal emission** — 7 eligible signals were computed but never surfaced. Root cause is **DB round-trip volume**, not compute:

- `run()` in `reason/runner.py` loops over **every** node (463) and calls `_load_context` + `load_node_metrics` **per node** → ~2-3 queries × 463 = ~1000+ reads, each with correlated subqueries.
- It then persists a **full audit** (reasoning_runs + run_outputs + context_snapshots + ~6 reasoner_results) for **every node×rule evaluation, even non-firing ones** → 5,800+ runs / 24,000+ reasoner_results per org.
- Over a remote link each round-trip is 20–150 ms → the pass crawls.

This is also why it looked like a "hang": the loop never finishes, so the emission barrier (where the 7 signals would surface) is never reached.

## Principle
Fewer, batched queries = faster **and** less Supabase load. Every fix below reduces total query count.

## Fixes by layer (priority order)

| # | Layer | Fix | Impact |
|---|---|---|---|
| P1 | L3 reads | Bulk-load facts / metrics / observations for ALL nodes in a handful of queries, index by node_id in memory; loop reads from memory | ~1000 reads → ~4 |
| P2 | L3 writes | Do not persist the full audit for evaluations that produce no candidate (only persist matched/blocked/failed); batch the inserts that remain | ~24,000 rows → ~600 |
| P3 | L3 scope | Skip nodes that cannot fire any rule before loading their context | fewer iterations |
| P4 | L2 | Parallelise / batch the per-email LLM extraction (already partly concurrent — verify + widen) | first-sync time |
| P5 | L1 | Confirm Composio pulls are paged/parallel, not serial per-item | first-sync time |
| X | Cross-cutting | Session pooler (5432) + connection reuse everywhere (done in `db.py`: keepalives/timeouts) | fewer reconnects |

## Method (non-negotiable — it is production)
1. Implement on local, **measure query count + wall-time before/after**.
2. Prove the SAME signals emit (no regression) on the Rohit org.
3. Only then commit + deploy to prod.

## Status (2026-08-11 eve)
- **P1 DONE + deployed** (harsh/mvp): `_bulk_load_facts`/`_bulk_load_obs` in runner.py, wired into `run()`. Parity-proven (bulk context == per-node byte-for-byte) → reads 3min→4s. Zero quality impact.
- **P2 DONE + deployed**: in `run()`, before persist, skip pure no-op evals (`not reasoned.matched and outcome not in {FAILED,INSUFFICIENT_CONTEXT,BLOCKED}`). Matched/blocked/failed still persist full → signals unchanged. Write rate 95→10/min. Works.
- **Result:** Rohit org reasoning "never completes" → **~10 min**. But 9 eligible candidates → **0 signals emitted**: the ~10-min window lets the graph drift, so the emission barrier (`AUTHORITATIVE_SIGNAL_PREDICATE` needs `authority_ctx.graph_version == current max`) fails. **Emission is tied to speed — make reasoning ~1 min and the drift window disappears → signals emit.**
- **P2b = NEXT / finish line:** batch the audit WRITES. `persist_execution` (reason/audit.py `_write_execution_bundle`) writes capability+context+run+results+candidates+checks+output in its OWN transaction per matched/blocked eval (~1500) = the remaining wall. KEY levers: `execution.trace.run_id` is already in memory (no write needed to get the run_id); `_write_execution_bundle` accepts a caller `connection=`. So collect executions in the loop and bulk-write once before the emission barrier (or share one connection). Parity gate: SAME signals. Then ~1 min → signals emit → app test.
- P3 (skip non-firing nodes), P4 (L2 parallel LLM), P5 (L1 paged): after P2b if still needed.
- Deployed alongside: db.py keepalives/timeouts. Prod DB :5432 (session, fast); local :6543. Mac app (genios-dashboard/Extension, Tauri) ready to point at prod for the intelligence test once signals surface.

## Re-verified against code — 2026-08-30

The 2026-08-11 status above is preserved as written. What is actually in the tree today:

| # | Fix | State | Evidence |
|---|---|---|---|
| P1 | Bulk-load L3 reads | **DONE** | `reason/runner.py` — `_bulk_load_facts` (:128), `_bulk_load_obs` (:175), `_bulk_load_metrics` (:283), `_bulk_load_situations` (:262), `_bulk_last_signal_at` (:196), `_bulk_recent_signals` (:410), all wired into `run()` at :814-824. The plan's P1 shipped and then grew — four more bulk loaders exist than it described. |
| P2 | Skip audit for non-firing evals | **DONE** | The no-op skip is in `run()`; only matched / blocked / failed persist. |
| **P2b** | **Batch the audit WRITES** | **OPEN — still the finish line** | `persist_execution` is still called once per execution inside the loop (`reason/runner.py:917` and `:1025`), each in its own transaction. `audit.py:98 _write_execution_bundle` does accept `connection=` (`:207` forwards it) — the seam the plan identified is there and unused. Nothing collects executions for a bulk write. |
| **P3** | **Skip nodes that cannot fire any rule** | **OPEN — not started** | No eligibility pre-filter exists in `reason/runner.py`. |
| P4 | Parallelise L2 LLM extraction | **DONE** | `context/runner.py:240` — `ThreadPoolExecutor(max_workers=_MAX_WORKERS)` over the per-email extraction. |
| P5 | L1 pulls paged/parallel | **DONE** | `capture/connectors/composio.py:361,372` and `capture/acquire/sync_runner.py:202` (`_CAPTURE_WORKERS`); `composio_base.py:31,47` bounds every Composio call with an explicit timeout. |

**Not re-measured.** The wall-time and signal-emission numbers in the 2026-08-11 status were taken against the design partner's live org. This pass verified only what is in the code; the claim that reasoning now completes in ~10 min, and the claim that emission is starved by graph drift, are **UNVERIFIED as of 2026-08-30** and should be re-measured before P2b is scoped.
