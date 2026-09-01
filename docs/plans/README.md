# genios-brain — Plans Index

Repo-local plans. The **master index across the whole workspace** is `../../../docs/plans/README.md`,
which lists these files too (via `../../genios-brain/docs/plans/…` links). Keep both in step.

Convention (from the workspace `CLAUDE.md`, mandatory): every plan carries a header block —
`> **Created:** YYYY-MM-DD · **Status:** Active | Post-trial | Reference | Done` plus a one-line
**Purpose** — and a row here. When a plan is completed or superseded: update its Status, move the
file to `docs/_archive/plans/`, and update its row.

*Last audited against code: 2026-08-30 (HEAD `0eaf94e`).*

| Plan | Created | Status | What it is, and what is actually left |
|---|---|---|---|
| [INTELLIGENCE_REMAINING.md](INTELLIGENCE_REMAINING.md) | 2026-09-01 | 🟢 Active | What is left after the L2→L4 chain work, ranked by effect on a real card rather than by the audit's order. **D** `outreach.objective` writer (in progress) · **E** the three surfaces that bypass the pipeline (morning-brief is literally hardcoded empty) · **F** cohort engine (needs D) · **G** the four brains reaching a decision (deliberately last — `learned_brain_entries` is near-empty, so a consumer changes nothing visible yet). Names what is NOT being done and why. |
| [L2_L4_INTELLIGENCE_CHAIN.md](L2_L4_INTELLIGENCE_CHAIN.md) | 2026-08-31 | 🟢 Active | Why every card read alike, and the three passes that fixed it: facts derived from silence (`context/waiting.py`), situations named after what is HAPPENING (`awaiting_response`, `commitment_overdue`, `meeting_follow_through`), a card vocabulary of 13 slots instead of 7, truthful `missing_fields`, and stale cards that rebuild in place (migration `0077`). Corpus routes 0 unrouted globally. **Left: apply `0076`+`0077` to production, then set `GENIOS_USE_DOMAIN_COMPILER` for one tenant.** `outreach.objective` still has no writer and is the largest remaining lift in card quality. |
| [ADR_RATIFICATION.md](ADR_RATIFICATION.md) | 2026-08-24 | 🟢 **Active — blocked on a human** | Ten drafted ADRs, each with a grounded recommendation. **0 of 10 ticked.** No engineering work moves this; it needs the owner to read and tick. `IMPLEMENTATION_PROGRAM.md` makes ADR-02 and ADR-07 preconditions for its Phase 1, so this is a live blocker, not paperwork. |
| [ADMIN_SUPPORT_WIRING.md](ADMIN_SUPPORT_WIRING.md) | 2026-08-27 | 🟢 Active | Admin + CS wired end to end, then the `deal.status` double-writer, the `expertise_packages` growth that took production read-only, and the meeting lane. **Numbers inside are stale** — routing is now **121 routed / 32 named-pending / 0 silent of 153** (was 85, then 108). **Two items blocked on a human:** lift the production read-only state + apply migration `0076`, then set `GENIOS_USE_DOMAIN_COMPILER`. Several sections have closed outright (the pack-registration test hazard; the "recommended order"). |
| [NEW_BRAIN_CUTOVER.md](NEW_BRAIN_CUTOVER.md) | 2026-08-25 | 🟢 Active | Switch card generation from legacy pack rules to the compiled capability corpus. **The flip has not happened** — `use_domain_compiler` is `False` at `platform/config.py:110` and set in no environment. Most Phase-2 blockers closed (0 hollow, 153/153 admitted, Admin/CS packs exist); two survive: `CardStore.claim_build` ignores card expiry (`deliver/store.py:49,55`), and the deploy-time L2 worker count. |
| [INTELLIGENCE_SURFACES.md](INTELLIGENCE_SURFACES.md) | 2026-08-26 | 🟢 Active — partially shipped | One intelligence, four surfaces. **Item 1 done** (`0075`, `card_builder._surfaces`). **Item 2 half done** — the app filter shipped (`deliver/store.py:310`), **the agent gateway never got its filter** (`deliver/agent_api.py:82`). Item 3 partial (`why_now` covers 3 reason codes). Item 4 needs one real agent round-trip. Item 5 (package surface) not started. |
| [IMPLEMENTATION_PROGRAM.md](IMPLEMENTATION_PROGRAM.md) | 2026-08-23 | 🟢 Active for **six** gaps only | The Secret War register — 106 gaps across 7 layers. Its old status ("awaiting owner approval to start Phase 0/0B") was **false when written**: Phases 0-7 shipped in `944b4f7`, the same commit that added the file. ~97 closed there, L3-09 closed by the corpus programme. **Open: X-07, X-01, L1-13, L5-06b, L3-11, and L7-04 (unverified).** The file holds no closure record of its own — that lives only in `git show 944b4f7`. |
| [L2_L3_GAP_ANALYSIS.md](L2_L3_GAP_ANALYSIS.md) | 2026-08-27 | 🔵 Reference — headline now false | Why a complete Sales corpus changed nothing live. **L2-1 (no `deal` node) is fixed**, Admin/CS have a pack lane, 0 hollow capabilities, Sales routes 43/47. **Still open: L2-2** (11 observation kinds emitted by nothing), **L2-3** (no commitment backfill), **L2-4** (no stage history). |
| [PERFORMANCE_HARDENING.md](PERFORMANCE_HARDENING.md) | 2026-08-11 | 🟢 Active — 2 of 6 open | L1→L4 speed. P1 bulk reads, P2 no-op audit skip, P4 L2 parallel extraction, P5 L1 paging all shipped. **P2b (batch the audit writes) and P3 (skip nodes that cannot fire) are open.** The wall-time and emission numbers in the body have not been re-measured. |
| [INTELLIGENCE_SHALLOWNESS_ROOT_CAUSE.md](INTELLIGENCE_SHALLOWNESS_ROOT_CAUSE.md) | 2026-08-22 | 🔵 Reference | 10-agent root-cause of why suggestions read as "no intelligence". **Substantially remediated** — the central finding (no counterparty, no direction) is fixed in `context/extract/envelope.py` + `prompt.py`; the constant Impact is gone. Read for reasoning, not as a to-do. The `champion_quiet` / `MappingProxyType` finding is **unverified** either way. |
| [INTELLIGENCE_QA_ROHIT_AUDIT.md](INTELLIGENCE_QA_ROHIT_AUDIT.md) | 2026-08-12 | 🔵 Reference | 4-agent QA audit against the design partner's real org. RC1/RC2/RC3 closed; RC4 and RC5 partial. What survives is owned elsewhere: the commitment backfill (`L2_L3_GAP_ANALYSIS.md` L2-3) and the reasoning-write batching (`PERFORMANCE_HARDENING.md` P2b). |

**Status legend:** 🟢 Active (work pending) · 🟡 Post-trial (on hold) · 🔵 Reference (read-only; anything still open is named in the row) · ✅ Done → move to `docs/_archive/plans/`.

## Archived

| Plan | Archived | Why |
|---|---|---|
| [ONBOARDING_SYNC_PROGRESS.md](../_archive/plans/ONBOARDING_SYNC_PROGRESS.md) | 2026-08-30 | All four parts shipped — backfill ceilings raised (`api/routes.py:1104,1106`), `onboarding_progress` + `platform/progress.py` + `home_routes.py:137`, the dashboard `<SyncProgress>` poller, and the Anthropic/Composio timeouts. The plan's prod phase-by-phase observation was not re-run. |
