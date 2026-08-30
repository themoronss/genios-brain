> **Created:** 2026-08-24 · **Status:** Active — BLOCKED ON A HUMAN, not on code
> **Verified:** 2026-08-30 — 0 of 10 boxes ticked. No engineering work will move this; it needs the owner to read ten paragraphs and tick or override. It is the oldest genuinely open item in either plan directory.
> **Purpose:** The ten unratified ADRs (X-07), each drafted with a recommendation grounded in what the code already does — so ratification is reading and ticking, not researching. Tick `[x] RATIFIED` (or write the alternative you choose) and the decision is made.

# ADR Ratification — the ten open decisions

Every recommendation below follows one principle: **ratify what the shipped code already does
where it is defensible, and name the change explicitly where it is not.** A decision that
contradicts running code is a migration project; a decision that blesses it is a sentence.

---

## ADR-01 · Channel/recipient ownership
**Question:** Who owns "which channel, which person" — Layer 5 (executive) or Layer 6 (delivery)?
**Code today:** Executive owns assignment + communication plan (`executive/assignment.py`,
`communication.py`); deliver executes the plan (LAYERS.py, LAYER_MAP.md now agree).
**Recommendation:** Ratify the code: **L5 owns who/where; L6 owns how/when.** The shadow-resolve
pass already measures the v2 path under exactly this split.
- [ ] RATIFIED · alternative: ____________

## ADR-02 · First authoritative expertise lane
**Question:** Which corpus lane goes live first, evaluated on what?
**Code today:** `sales.sit.inbound_fit_check` routes WITHOUT the `ball_in_court=us` narrowing
(deliberate — "a fit check must fire before a deal record exists"); `inbound_lead` narrows to
~9% of founder-inbox persons.
**Recommendation:** Lane = `inbound_fit_check` via `demo_requested` + `intro_followup` (the
observations Rohit's data actually has). **Do not re-route through `inbound_lead`** — that
silently re-imposes the 9% gate. Second design partner running ordinary B2B sales before the
pilot denominator is treated as real.
- [ ] RATIFIED · alternative: ____________

## ADR-03 · Organization Brain source of truth
**Question:** Declared config (ICP forms) or learned entries (`learned_brain_entries`)?
**Code today:** Only `learned_brain_entries` exists; publish path live (review → publish_brain
→ versioned row); runner consumes via `contracts/learned_state.snapshot_all`.
**Recommendation:** **Learned entries are the single store.** Declared config, when built,
enters as a learning object with `unit='declared'` and evidence=owner-assertion — one
versioning, one rollback, one consumption path, no second source to drift.
- [ ] RATIFIED · alternative: ____________

## ADR-04 · Confidence surface
**Question:** One number or a vector, and whose?
**Code today:** L2 computes the five-dimension vector per situation; cards carry
`confidence_vector`; the API sources identity/situation from L2 or reports null — never
invents (L4-11 fix).
**Recommendation:** Ratify: **vector, sourced per-layer, null over invented.** The one number
shown in compact UI is `evidence` alone, labelled as such.
- [ ] RATIFIED · alternative: ____________

## ADR-05 · Canonical lifecycle IDs
**Question:** What identifies one piece of work across layers?
**Code today:** `open_loop_id` (content-addressed: subject+kind+thread) for requests;
`signal_id` for decisions; `card_id` for surfaces; `execution_id` for commitments;
`delivery_id` for sends. Each layer's id, joined by columns, no universal id.
**Recommendation:** Ratify the five-id chain. A universal id would re-key five ledgers for
zero query the joins cannot already answer. `open_loop_id` is the only cross-layer SEMANTIC
identity (the request), and it is deterministic by construction.
- [ ] RATIFIED · alternative: ____________

## ADR-06 · Outcome/value attribution
**Question:** What counts as an outcome, attributed how?
**Code today:** `execution_outcomes` labels (`succeeded` / `completed_unproven` /
`expired_in_progress` / failure); `llm_costs.subject_ref` joins spend to signals; verdicts
grade rules with `bad_timing` excluded from accuracy.
**Recommendation:** Outcome = **scoped success evidence within the play's window** (already
the L5 monitor's definition). Value = outcome × deal value where linked, else counted not
priced. Never infer success from silence — `completed_unproven` stays its own bucket.
- [ ] RATIFIED · alternative: ____________

## ADR-07 · LLM budget authority
**Question:** Who may spend, capped by whom?
**Code today:** Platform daily cap checks calls AND USD (`_llm_over_daily_cap`); every call
lands in `llm_costs`; gate spend bound per-org.
**Recommendation:** Ratify: **platform cap is the authority; layers request, never own.**
Per-org monthly ceiling added at plan level (Startup = ₹25k/mo price ⇒ cap engine spend at a
named % of it; propose 15%).
- [ ] RATIFIED · % = ____ · alternative: ____________

## ADR-08 · Organization review-to-publish state machine
**Question:** May an approved Organization value publish without a second gate?
**Code today:** governed → human_review → (approve) → publish_brain, same transaction,
`expert_brain_changed:false` always.
**Recommendation:** Ratify the single human gate. A second reviewer would double the latency
of a loop that has produced ONE proposal in its lifetime; revisit at >20 proposals/month.
Rollback (`rollback_brain`) is the safety valve and already works.
- [ ] RATIFIED · alternative: ____________

## ADR-09 · Learning-policy fidelity
**Question:** Must the persisted policy round-trip byte-faithfully?
**Code today:** Reload carries both prohibition columns; seed writes empty-not-NULL; revision
>1 with NULL prohibitions aborts the tenant run (`policy_incomplete`).
**Recommendation:** Ratify fail-closed round-trip fidelity as written.
- [ ] RATIFIED · alternative: ____________

## ADR-10 · Adaptive TTL/decay target
**Question:** May ADAPTIVE publish into `learned_brain_entries` with an expiry, or does
temporary guidance live only as Runtime leases?
**Code today:** ADAPTIVE approval publishes into `temporary` (a lease) — `_target_state_for`
routes it there precisely because a mandatory expiry governs it; `learned_brain_entries` has
no expiry column.
**Recommendation:** **Branch B — keep ADAPTIVE as Runtime leases.** No migration, no pivot
invalidation machinery, and the highest-precedence brain stays incapable of going stale by
construction. Revisit only if a lease renewal pattern emerges that wants durable versioning.
- [ ] RATIFIED · alternative: ____________
