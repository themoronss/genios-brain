# 05 · Expected vs actual — every open item, layer by layer

**Written for:** Rohit, Harsh and every coding agent.

Measured on 23 Oct 2026 at the production head `0cc8d83c` (origin/harsh/mvp, CI green). Read-only: nine auditors, one skeptic per slice who tried to refute every item against the code, then a completeness critic. **Production was not read** — where only production can answer, the item says so and gives the read-only SQL (collected in [04-FOR-HARSH](04-FOR-HARSH.md)).

⚠ Where an item says the big merge `c501eec9` reached production on 18 Oct, read: *committed* on 18 Oct, first on GitHub's prod branch in the 21 Oct push; the real deploy date is Harsh's fact (see [03-LOG](03-LOG.md), S01.U3).

Mistakes are in [01-WHAT-WENT-WRONG](01-WHAT-WENT-WRONG.md) and decisions in [06-DECISIONS](06-DECISIONS.md); they are not repeated here. Each item names the step of [02-PLAN](02-PLAN.md) that fixes it.

| Layer | P0 | P1 | P2 | total |
|---|---|---|---|---|
| [L1 Enterprise Signals (capture/)](#layer-l1) | 0 | 17 | 7 | 24 |
| [L2 Signals Qualification (packs/ + reason/)](#layer-l2) | 2 | 18 | 3 | 23 |
| [L3 Context Graph (context/)](#layer-l3) | 2 | 12 | 6 | 20 |
| [L4 Executive (executive/)](#layer-l4) | 0 | 3 | 2 | 5 |
| [L5 Delivery (deliver/)](#layer-l5) | 0 | 13 | 4 | 17 |
| [L6 Learning (feedback/)](#layer-l6) | 0 | 0 | 4 | 4 |
| [Goals (GeniOS-009)](#layer-goals) | 3 | 14 | 1 | 18 |
| [Surfaces (web dashboard, Mac app)](#layer-surfaces) | 0 | 13 | 11 | 24 |
| [Cross-layer seams](#layer-cross-layer) | 2 | 5 | 2 | 9 |
| [Process (verification, release, docs)](#layer-process) | 4 | 7 | 15 | 26 |
| **all** | **13** | **102** | **55** | **170** |

<a id="layer-l1"></a>
## L1 Enterprise Signals (capture/)

> Most of Layer 1 (capture/) is built and is in production since merge c501eec9 (18 Oct). That includes the gate that archives instead of deleting, provider refusals that raise instead of reading as an empty inbox, inferred timestamps, bundles stored for L2 (E1/E8), and Harsh's 19 Oct rebuild (1925a5bb, a8dbefa2, 0d5939d1). That rebuild also fenced the junk gate (E9) and dropped the "drop matchmaking / plan notices" lines (B2). Nine items listed in the docs are confirmed closed in code. What remains is mostly about how good the junk filter is and how much L1 actually carries forward. First, a confident `llm_junk` verdict does not stand: the parked drain re-admits it on every heartbeat, and the re-read skips the gate, so newsletter snippets get extracted anyway. Second, the gate judges "is a human writing?" without ever seeing the sender. Third, no L1 model site has ever been run on a real model; B2 shipped on answers written by the ideal reader. Fourth, a failed per-message Gmail fetch silently falls back to the list snippet. Downstream in the new architecture, the L1→L2 bundle carries only published signals, and the closed 16-type vocabulary has no word for intros, meetings, fundraising or applications. Those workstreams never trigger L2's R-9 pass, whose only bundle reader is off by default anyway. The EvidenceNeed fetchers (E2) are also not armed, so every L2 request for more evidence stays open. That helps explain "sometimes no reasoning" and thin correlation. E3–E7 and E10 are unbuilt; E5 and E7 wait on Rohit's decisions, and E4/E6 wait on the live key. Production has not been measured since the deploy (F6), so whether the 4 Oct funnel loss (27 of ~470 mails, 0 of 22 meetings) is actually fixed, and whether the resync, attachment requeue and company brief happened, needs the read-only SQL given in each item. The L1 folder docs stop at 18 Oct and contradict the code.

| Item | Sev | Status | Owner | Step |
|---|---|---|---|---|
| [No Layer 1 model site has been measured on a real model; the B2 prompt change shipped on ideal-reader answers](#l1-b1-live-pass-never-run) | P1 | missing | rohit | S07 |
| [GeniOS-008 C1 + YC-II D29/B26 (+F18): L1's model calls were never measured on a real model; the junk prompt ch](#l1-c1-d29-live-junk-filter-never-measured) | P1 | partial | rohit | S07 |
| [GeniOS-008 C3 / YC-II D5, D16, D26: the history window is still 60 days in code; the 365-day resync needs a pr](#l1-c3-d16-history-window-still-60-days) | P1 | unknown until production is read | rohit+harsh | S09 |
| [The gate's protections for founder workstreams depend on accepted company-brief lines; production state is unk](#l1-company-brief-gate-dependence) | P1 | unknown until production is read | rohit | S02 |
| [EvidenceNeed fetchers (E2) are built but not armed, so every request L2 makes for more evidence stays open](#l1-e2-need-fetchers-armed-off) | P1 | built, not live | harsh | S13 |
| [L1 E2 / YC-II F224 + L2 G-1: evidence-need fetchers are built but unarmed, so L2's questions are never answere](#l1-e2-need-fetchers-armed-off-2) | P1 | built, not live | harsh | — |
| [Condition, delivery-status link, meeting follow-up link and thread end state are not L1 objects (E4)](#l1-e4-six-object-types) | P1 | missing | claude | S12 |
| [The junk gate asks 'is a specific human writing?' but never sees who sent the mail](#l1-gate-judges-without-sender) | P1 | partial | claude | S08 |
| [A failed or refused per-message Gmail fetch silently falls back to the list snippet](#l1-gmail-full-fetch-failure-silent) | P1 | partial | claude | S06 |
| [Composio toolkit versions are still unpinned (dangerously_skip_version_check=True)](#l1-h3-composio-toolkit-unpinned) | P1 | missing | harsh | S11 |
| [L1 H3: Composio toolkit versions are still unpinned (dangerously_skip_version_check=True)](#l1-h3-composio-toolkits-unpinned) | P1 | missing | claude+harsh | S11 |
| [Whether the attachments refused since 3 Oct were requeued after the deploy is unknown (H4)](#l1-h4-refused-attachments-requeue) | P1 | unknown until production is read | harsh | S09 |
| [A mail the junk filter archived as llm_junk is re-admitted on every heartbeat and extracted from its list snip](#l1-junk-verdict-readmitted-on-snippet) | P1 | broken | claude | S06 |
| [The 4 Oct funnel loss is fixed in code, but production's funnel has not been measured since the 18 Oct deploy](#l1-post-deploy-funnel-unmeasured) | P1 | unknown until production is read | rohit+harsh | S01 |
| [The founder's second mailbox (<founder company mailbox>) is not connected, so 'you never replied' can be false](#l1-r3-second-mailbox) | P1 | missing | rohit+harsh | S08 |
| [Mail the old gate deleted, and anything older than 60 days, stay outside memory until Rohit picks the window a](#l1-resync-and-history-window) | P1 | unknown until production is read | rohit+harsh | S09 |
| [The closed 16-type signal vocabulary has no word for the founder's main workstreams, and the open lane is neve](#l1-signal-vocabulary-16-types) | P1 | missing | rohit | S12 |
| [Gmail incremental sync keys on a date, not historyId (A4)](#l1-a4-gmail-historyid-cursor) | P2 | missing | harsh | S11 |
| [GeniOS-008 C2: <founder company mailbox> as a second (seat) mailbox, default yes, not known to be connected](#l1-c2-second-mailbox) | P2 | unknown until production is read | rohit+harsh | S08 |
| [YC-II D23 + B27/F58: promoting Boardy's archived intros (pending Rohit's list read) would read only the stored](#l1-d23-b27-promoted-archive-reads-only-the-snippet) | P2 | partial | claude+harsh | S06 |
| [Entity doubt is thrown away, and a person known only by name never joins a bundle (E3)](#l1-e3-entity-doubt-and-person-joins) | P2 | partial | claude | S13 |
| [Roles are free text: sender, promisor, owner and approver are not a closed set (E6)](#l1-e6-closed-roles) | P2 | missing | claude | S12 |
| [L1 H2 → A4: the Gmail cursor is still a day-granular date; the live historyId fixtures were never recorded](#l1-h2-a4-gmail-history-cursor) | P2 | missing | claude+harsh | S11 |
| [A3's count of mail with an inferred timestamp lives only in a log line, not in l1_sync_runs](#l1-time-inferred-not-ledgered) | P2 | partial | claude | S10 |

<a id="l1-b1-live-pass-never-run"></a>
### No Layer 1 model site has been measured on a real model; the B2 prompt change shipped on ideal-reader answers

`l1-b1-live-pass-never-run` · **P1** · missing · owner **rohit** · paid_run · step **S07**

- **Expected:** Before the junk prompt changes, a live pass measures junk_gate_batch, relevance and extraction on Haiku (≈$1). Blueprint Phase 5 runs the five benchmark prompts against the actual source enumeration. A model's own confidence is never ground truth. _(source: GeniOS-008/layer-1-enterprise-signals/02-PLAN.md B1, B2 ('⛔ after B1'), R1; YC-II W27 06 D29; 05-BLUEPRINT Part 6 Phase 5)_
- **Actual:** 0d5939d1 (19 Oct) changed the gate prompt (B2 + E9), and its message says 24 gate answers were re-authored and every cassette re-recorded with the ideal reader at no spend. scripts/golden_eval.py:66 writes live scorecards to 'speedrun008/YC-II W27/scores', and that directory does not exist. The only real-model pass was the 12 Oct Haiku run on the expert site (F5). RESCUE_AT 0.70 and DROP_BELOW_RELEVANCE 0.25 (relevance.py:17,23) are unmeasured.
- **Evidence (measured):** `git show 0d5939d1 (message: 're-authored', 'ideal reader (no spend)')`; `scripts/golden_eval.py:66`; `ls 'speedrun008/YC-II W27/scores' → absent`; `genios_engine/capture/gate/relevance.py:17,23`
- **What Rohit sees:** We cannot say how often the real model archives an investor, intro or portal mail, which is the top suspect for 'fewer cards'.
- **Where the mistake was:** B2 was held by D29 until B1 had measured the filter; on 19 Oct it was changed without the measurement.
- **Fix:** Rohit sets GENIOS_GOLDEN_LIVE_KEY and says yes. Claude runs golden_eval.py --live for --site junk_gate_batch, relevance and extraction (Haiku, ≈$1, after testing 1–2 calls first), compares each case with what it needs, and tunes RESCUE_AT and the prompt from that measurement.
- **Blocked on:** Rohit: the live key and a yes (R1)
- **Verified:** confirmed with a correction by the skeptic: No L1 model site (junk_gate, junk_gate_batch, relevance, extraction) has ever had a recorded live pass, and the 0d5939d1 message does say 're-authored' and 'ideal reader (no spend)'. But the 12 Oct pass was not the only real-model pass. Commit 73d9f804 (17 Oct) recorded live expert-site passes: a Haiku-only T1 ladder over 67 cases, recall 0.509 and held 18.5% at $4.96, plus a T1/T2 smoke run. Its scorecards sit in 'speedrun008/YC-II W27/scores' on branches yc2w27-s13b and yc2w27-haikufix. That commit, 117f90c6 and fc37f82b are not ancestors of HEAD 0cc8d83c, which is why the directory is missing in prod. RESCUE_AT 0.70 and DROP_BELOW_RELEVANCE 0.25 (relevance.py:17,23) are still unmeasured.

<a id="l1-c1-d29-live-junk-filter-never-measured"></a>
### GeniOS-008 C1 + YC-II D29/B26 (+F18): L1's model calls were never measured on a real model; the junk prompt changed anyway, and the fund-round notice is still archived

`l1-c1-d29-live-junk-filter-never-measured` · **P1** · partial · owner **rohit** · paid_run · step **S07**

- **Expected:** C1: spend ~$1 on a live Haiku pass of L1's model calls (junk filter, relevance, extraction), THEN fix the junk-filter prompt (B2). D29: the AI filter's archive stands until a live run measures the filter with the brief. Attention tiers instead of keep/drop (F02). _(source: speedrun008/GeniOS-008/03-QUESTIONS.md C1; layer-1-enterprise-signals/04-FOR-HARSH.md §7 B1/B2; YC-II W27/06-DECISIONS.md D29; STEP-18 B26; 03-FINDINGS.md F02)_
- **Actual:** No live L1 pass is recorded (the L1 03-LOG has no C1/B1 run). Harsh's 0d5939d1 (19 Oct) still changed the junk prompt, removing 'automated matchmaking' and 'plan notices' and adding always-KEEP for intros and vendor price changes. All 24 gate answers were re-authored by the ideal reader, not measured. The prompt still answers keep|drop and still DROPs 'self-service'. Golden F18 (a state innovation fund opens a round) fails because the gate archives it as not_business (D29).
- **Evidence (measured):** `genios_engine/capture/gate/relevance.py:80-93 (DROP '...self-service...'; ALWAYS KEEP intros/price changes)`; `genios_engine/capture/gate/relevance.py:111 (`"disposition":"keep"|"drop"`)`; `git show 0d5939d1 ('24 gate answers re-authored ... ideal reader (no spend)')`; `tests/replays/specs/founder/F18.json:74 (blocked_on: 06 D29)`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/03-LOG.md (no live-pass entry)`
- **What Rohit sees:** Round notices from funds and programmes, and possibly other investor/incubator mail, are archived at the gate, so no file, no review and no card exist for them. The new prompt's real-model behaviour is unknown.
- **Where the mistake was:** The B2 prompt change shipped before the C1 measurement it was sequenced after ('then the junk-filter prompt fix').
- **Fix:** Rohit says yes to C1 (≈$1, key in GENIOS_GOLDEN_LIVE_KEY; test 1–2 calls first). Claude runs `scripts/golden_eval.py --live` on the junk/relevance/extract sites, reads keep/drop against the golden labels, and then Rohit decides D29 (re-admit fund/programme notices: attention tier instead of archive).
- **Verified:** confirmed by the skeptic (capture/gate/relevance.py:79-80 still DROPs 'automated, one-to-many, or self-service' mail. :93-98 adds the two ALWAYS KEEP kinds (intros, price/plan/renewal changes). :111 still returns keep|drop. `git show 0d5939d1` (Harsh, 19 Oct): 'Golden: 24 gate answers re-authored to the new prompt ... ideal reader (no spend)'. The L1 03-LOG has no live-pass entry; its only C1 row (:9) is the L1 plan's own C1 'Deferred'. GeniOS-008 03-QUESTIONS.md:29 C1 (the $1 live pass, then B2) defaults to yes, and B2 shipped without the pass. F18.json:74 blocked_on is 06 D29, and 01-AS-IS-CARDS.md:86 lists F18 as failing and silent.)

<a id="l1-c3-d16-history-window-still-60-days"></a>
### GeniOS-008 C3 / YC-II D5, D16, D26: the history window is still 60 days in code; the 365-day resync needs a production action

`l1-c3-d16-history-window-still-60-days` · **P1** · unknown until production is read · owner **rohit+harsh** · prod_action · step **S09**

- **Expected:** History window 60 → 365 days, then the STEP-08 resync, run only after the company brief is accepted (D26). _(source: speedrun008/GeniOS-008/03-QUESTIONS.md C3; YC-II W27/06-DECISIONS.md D5, D16, D26; 03-FINDINGS.md E13; layer-1-enterprise-signals/04-FOR-HARSH.md H6 R4)_
- **Actual:** DEFAULT_BACKFILL_DAYS = 60. A connection gets 365 only via PATCH /connections/{id}/backfill-window, stored in connections.capture_scope.backfill_days. The resync script refuses --apply without --days. Whether Harsh did either is unknown.
- **Evidence (measured):** `genios_engine/capture/connectors/backfill.py:34, 37 (BACKFILL_DAYS_KEY, DEFAULT_BACKFILL_DAYS = 60)`; `genios_engine/api/routes.py:2850-2873 (PATCH backfill-window)`; `scripts/resync_deleted_mail.py:1-18, 104 (--days default None; refuses a window shorter than the connection's)`
- **What Rohit sees:** Mail older than 60 days, such as the 3one4 deferral (2 Apr) and the March Neon exchanges, is not in memory, so no file, pattern or card can rest on it.
- **Fix:** Harsh reads the window. If it is unset or 60, Rohit's 365 (default) stands. Harsh PATCHes Gmail and Calendar to 365, runs the resync dry run → Rohit reads it → --apply --days 365, after the brief is accepted (D26).
- **Blocked on:** select connection_id, source_type, status, capture_scope->>'backfill_days' as backfill_days from connections where org_id='<ORG>';
- **Verified:** confirmed by the skeptic (capture/connectors/backfill.py:33 is BACKFILL_DAYS_KEY and :36 DEFAULT_BACKFILL_DAYS = 60. Migration 0082 stamps 60 on existing connections. PATCH /connections/{id}/backfill-window is at api/routes.py:2850. scripts/resync_deleted_mail.py:114 refuses --apply without --days, and :200-203 refuses while the connection's window is shorter. Whether Harsh raised the window or ran the resync needs production. Read-only SQL: `select connection_id, source_type, capture_scope->>'backfill_days' from connections where org_id = '<rohit_org>';`)

<a id="l1-company-brief-gate-dependence"></a>
### The gate's protections for founder workstreams depend on accepted company-brief lines; production state is unknown

`l1-company-brief-gate-dependence` · **P1** · unknown until production is read · owner **rohit** · prod_action · step **S02**

- **Expected:** Senders the founder names (Boardy, the DPIIT portal, accelerators) are whitelisted (W-07), fetched whole, and the gate prompt carries company context. _(source: STEP-07 (YC-II W27); memory founder-workstreams-lost-2026-10-05 ('the S2 prompt has no company context'))_
- **Actual:** W-07 and keeps_whole fire only for senders in accepted brief lines (relevance.py:215-229, 239-245; gate/rules.py:323-330). The brief block is empty when no line is accepted (platform/company_brief.py:37-41). Whether Rohit's org has accepted lines is a production question.
- **Evidence (measured):** `genios_engine/capture/gate/relevance.py:215-245`; `genios_engine/capture/gate/rules.py:323-330`; `genios_engine/platform/company_brief.py:37-41`
- **What Rohit sees:** Without accepted lines, intros and portal mail rely on the unmeasured junk prompt alone.
- **Fix:** Rohit reviews and accepts the drafted brief lines (names: Boardy, the sampark.gov.in portal, accelerators, investors). Harsh confirms the counts.
- **Blocked on:** Production: select section, status, count(*) from company_brief_lines where org_id='<ORG>' group by 1,2;
- **Verified:** confirmed by the skeptic (W-07 fires only on ctx.named_in_brief (rules.py:327-331). named_sender reads current(), which reads brief_for(), which reads accepted lines only (platform/company_brief.py:37-48, 122-125). keeps_whole and _named_in_brief go through the same resolver (relevance.py:214-245; routes._sender_resolver_for). An empty brief gives an empty prompt block, and the prompt is then unchanged byte for byte (relevance.py:146-152). Production state is unknown. SQL: select section, count(*) from company_brief_lines where org_id='<ORG>' and accepted_at is not null and removed_at is null group by section;)

<a id="l1-e2-need-fetchers-armed-off"></a>
### EvidenceNeed fetchers (E2) are built but not armed, so every request L2 makes for more evidence stays open

`l1-e2-need-fetchers-armed-off` · **P1** · built, not live · owner **harsh** · prod_action · step **S13**

- **Expected:** L2 asks L1 for the one missing fact (fetch the thread, backfill a window, re-extract) and L1 fetches it. _(source: GeniOS-008/00-ARCHITECTURE.md flow diagram and 'How today's code differs' row 'Missing evidence'; 02-PLAN E2)_
- **Actual:** build_fetchers returns {} unless GENIOS_NEED_FETCHERS=on and a factory is registered (need_executor.py:224-246; need_fetchers.py:34). The variable is set in no deploy file (Procfile, Dockerfile), and 04-FOR-HARSH §8 says to leave it OFF until Harsh runs one trial fetch. REEXTRACT is not wired (02-PLAN E2 status). R-9 files needs on every pass (reason/l2/sweep.py header R8), and they wait forever.
- **Evidence (mixed):** `genios_engine/capture/acquire/need_executor.py:224-246`; `genios_engine/capture/acquire/need_fetchers.py:34`; `Procfile; Dockerfile (no GENIOS_NEED_FETCHERS)`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/04-FOR-HARSH.md §8`
- **What Rohit sees:** An L2 judgment that needs an older thread stays 'insufficient evidence'. This contributes to 'sometimes no reasoning'.
- **Fix:** Harsh runs 04-FOR-HARSH §8 steps 1–3 on Rohit's org, sends the printed report, then sets GENIOS_NEED_FETCHERS=on. Claude wires REEXTRACT from the stored payload.
- **Blocked on:** Production (Rohit's permission): select state, count(*) from evidence_needs where org_id='<ORG>' group by state; plus whether GENIOS_NEED_FETCHERS is set in the App Platform env
- **Verified:** confirmed by the skeptic (build_fetchers returns {} unless armed() and _FACTORY are both set (need_executor.py:240-246; need_fetchers.py:34-38). The factory is registered (routes.py:3550-3552). GENIOS_NEED_FETCHERS appears in no deploy file (Procfile, Dockerfile). The host's runtime environment is not in the repo, so whether it is set in prod is a prod check. Needs do get expires_at = +7 days (reason/l2/evidence.py:30,64), but read_open_needs selects state='open' with no expiry filter (context/evidence_need_store.py:54-59). A refused pass closes nothing, so an expired need stays open. R-9 files needs only for tenants with l2_reasoning on (sweep.py:176-178), and domain_shadow.py:694 also drives run_needs.)

<a id="l1-e2-need-fetchers-armed-off-2"></a>
### L1 E2 / YC-II F224 + L2 G-1: evidence-need fetchers are built but unarmed, so L2's questions are never answered and holds never resolve

`l1-e2-need-fetchers-armed-off-2` · **P1** · built, not live · owner **harsh** · prod_action · step **—**

- **Expected:** L2 raises EvidenceNeeds and L1 fetches the thread/window. Holds resolve on the need's outcome. Arm GENIOS_NEED_FETCHERS=on after one hand-run fetch for Rohit's org. _(source: speedrun008/GeniOS-008/layer-1-enterprise-signals/04-FOR-HARSH.md §8 E2; layer-2-reasoning/04-FOR-HARSH.md 'The evidence fetchers'; YC-II W27/03-FINDINGS.md F224)_
- **Actual:** Fetchers are registered (api/routes.py:3537-3552), but build_fetchers returns {} unless GENIOS_NEED_FETCHERS is armed. The hold chain (hold_needs.needs_from_holds → hold_resolution.resolve_hold) is declared UNREACHED with no production caller. L2 needs ('l2need:') stay open.
- **Evidence (measured):** `genios_engine/capture/acquire/need_executor.py:224-246 (`if not armed() or _FACTORY is None: return {}`)`; `genios_engine/api/routes.py:3537-3552 (register_fetcher_factory)`; `genios_engine/context/context_health.py:42-48 (resolve_hold, needs_from_holds UNREACHED)`
- **What Rohit sees:** Investigation-lane questions stay open forever and a held situation stays held, so cards wait or never appear ('sometimes no correlation').
- **Fix:** Harsh runs the one-org hand fetch in 04-FOR-HARSH §8 step 2 and sends the report. If it returns met/unavailable correctly, Harsh sets GENIOS_NEED_FETCHERS=on. Claude then wires resolve_hold to the met outcomes (the chain 'moves together').
- **Blocked on:** select need_id, state, created_at from evidence_needs where org_id='<ORG>' and need_id like 'l2need:%' order by created_at desc limit 20;
- **Verified:** confirmed by the skeptic (need_executor.py:240-241: `if not armed() or _FACTORY is None: return {}`. armed() (need_fetchers.py:39-40) reads the GENIOS_NEED_FETCHERS env var. The factory is registered at api/routes.py:3536-3552. hold_resolution.resolve_hold and hold_needs.needs_from_holds have no caller outside their own modules (grep), and context_health.py:42-48 declares them UNREACHED. L2 needs use the prefix 'l2need' (reason/l2/evidence.py:28). The one run_needs caller is reason/domain_shadow.py:694. Whether GENIOS_NEED_FETCHERS is set in the production env is unverified; the code default is unarmed.)

<a id="l1-e4-six-object-types"></a>
### Condition, delivery-status link, meeting follow-up link and thread end state are not L1 objects (E4)

`l1-e4-six-object-types` · **P1** · missing · owner **claude** · code · step **S12**

- **Expected:** L1 delivers six object types: commitment, condition, open question, delivery status, meeting follow-up link, thread terminal state. _(source: GeniOS-008/00-ARCHITECTURE.md 'Inside L1'; 02-PLAN E4; 05-BLUEPRINT benchmarks P4 (meetings and follow-ups), P5 (conditional triggers))_
- **Actual:** Commitment and open question exist (contracts/extraction.py). A condition exists only as Commitment.is_conditional and condition_text (extraction.py:243-280), and there is no Condition class in contracts/. Delivery status is bounce only (capture/delivery_status.py), linked in L3 (context/delivery.py). The meeting→follow-up link exists only in context/meeting_days.py, and thread end only as ball_in_court. 02-PLAN E4 status: not built, needs the live key for the re-record.
- **Evidence (measured):** `genios_engine/contracts/extraction.py:243-280`; `genios_engine/capture/delivery_status.py`; `genios_engine/context/delivery.py`; `genios_engine/context/meeting_days.py`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/02-PLAN.md Group E status E4`
- **What Rohit sees:** 'If X then Y' triggers nobody promised are lost, and meeting follow-ups depend on the old L3 path.
- **Fix:** Add a Condition object, an outbound delivery-status link, a meeting→follow-up link and a per-thread terminal state to the extraction contract, each with a reader in the L2 dossier. Re-record extraction once R1 is given.
- **Blocked on:** live key (R1)
- **Depends on:** [l1-b1-live-pass-never-run](#l1-b1-live-pass-never-run)
- **Verified:** confirmed by the skeptic (contracts/extraction.py has Commitment (242), OpenQuestion (569) and no Condition class. The only Condition in the codebase is context/analytic/cohort.py:367, an unrelated concept. A condition exists only as is_conditional plus condition_text (extraction.py:267-271). capture/delivery_status.py is bounce-only. Thread end exists only as ball_in_court (capture/structural/threads.py:15). No commit after 18 Oct touches this (git log 1925a5bb^..HEAD on capture/ and contracts/). 02-PLAN.md:98 marks E4 not built.)

<a id="l1-gate-judges-without-sender"></a>
### The junk gate asks 'is a specific human writing?' but never sees who sent the mail

`l1-gate-judges-without-sender` · **P1** · partial · owner **claude** · code · step **S08**

- **Expected:** The filter separates machine noise from meaningful automated or first-contact mail. Its own test is whether a named person is writing, and investors from unfamiliar domains must survive it. _(source: capture/gate/relevance.py:75-78 (the prompt's test); 05-BLUEPRINT Part 6 golden matrix 'Filtering: machine noise, meaningful automated alerts'; memory founder-workstreams-lost-2026-10-05 (Khushi/247VC, Troy/a16z S2-junked))_
- **Actual:** The batch path sends only the masked subject plus the snippet, cut to 600 chars (relevance.py:279-286). The single path sends prepared.clean_text, which is subject plus body (pipeline.py:1622-1626; relevance.py:339). The only SOURCE line is the source name, e.g. 'gmail' (relevance.py:108). There is no sender name or domain, no 'reply to our mail' flag, and no attachment flag. Known and brief-named senders skip the gate (W-01/W-07), but a stranger is judged blind. Golden F18 (a fund's round notice) is still archived at the gate after B2.
- **Evidence (measured):** `genios_engine/capture/gate/relevance.py:279-286`; `genios_engine/capture/gate/relevance.py:339`; `genios_engine/capture/gate/relevance.py:108`; `genios_engine/capture/pipeline.py:1618-1626`; `tests/replays/specs/founder/F18.json blocked_on ('the fund's round notice is archived at the gate')`
- **What Rohit sees:** First-contact investor, accelerator or fund mail can be archived. It then reaches L3 as metadata only (no words, no correlation), so no card appears.
- **Fix:** Give each fenced item the sender's display name and domain (not the full address), an is-reply-to-us flag (from In-Reply-To/References against our sent ids) and has_attachment. Re-record the gate cassettes, and measure in the B1 live pass before relying on it.
- **Depends on:** [l1-b1-live-pass-never-run](#l1-b1-live-pass-never-run)
- **Verified:** confirmed by the skeptic (Batch path: masked subject plus snippet, cut to 600 chars (relevance.py:282-286). Single path: prepared.clean_text cut to 1500 chars (relevance.py:339). The only SOURCE line is in the single prompt (relevance.py:108); the batch prompt has none. Neither prompt carries a sender, domain, reply flag or attachment flag. W-01 known senders return keep before any call (relevance.py:329-330), and W-07 skips S2 (gate.py:166). F18 still fails: the re-recorded cassette after 0d5939d1 still holds disposition 'drop' (tests/replays/specs/founder/cassettes/F18.json), and F18.json blocked_on still says 'archived at the gate'.)

<a id="l1-gmail-full-fetch-failure-silent"></a>
### A failed or refused per-message Gmail fetch silently falls back to the list snippet

`l1-gmail-full-fetch-failure-silent` · **P1** · partial · owner **claude** · code · step **S06**

- **Expected:** A provider that says no is never read as an answer (A1's rule). A partial fetch is recorded, and a body we did not get is never passed off as the body. _(source: 02-PLAN A1; composio_base.ProviderRefused docstring (composio_base.py:12-22); 05-BLUEPRINT Part 7 'Negative-result honesty', Part 6 'Ingestion: partial fetch')_
- **Actual:** fetch_content calls _execute without raise_if_refused (composio.py:354-355). _full_message turns every exception into {} (composio.py:358-366), and _to_objects uses `src = full or m` (composio.py:696-697), so the list message's text or snippet becomes raw['body'] with no marker. The Gmail connector's _execute also has no hard deadline, unlike ComposioExec (composio.py:309-322 vs composio_base.py:63-77). A1 guarded only the list call (composio.py:334) and the shared executor (composio_base.py:74).
- **Evidence (measured):** `genios_engine/capture/connectors/composio.py:354-366`; `genios_engine/capture/connectors/composio.py:696-697`; `genios_engine/capture/connectors/composio.py:334`; `genios_engine/capture/connectors/composio_base.py:63-77`
- **What Rohit sees:** Cards built on two lines of preview, with nothing in the trace saying why.
- **Where the mistake was:** A1 (e0996e6c) fixed the list call and the shared executor but not the per-message fetch, the third Composio door.
- **Fix:** Apply raise_if_refused in fetch_content. When a keeper's full fetch fails, retry once. If it still fails, park the mail as NEEDS_REFETCH (or mark raw['body_fetch']='failed' so extraction refuses it) instead of extracting the snippet. Count it in SyncSummary and l1_sync_runs. Test plus mutation.
- **Verified:** confirmed by the skeptic (fetch_content calls _execute with no raise_if_refused (composio.py:354-355). _full_message turns any exception into {} (composio.py:358-366), and a refusal envelope {successful:false,data:{}} also yields {} through r.get('data', r). The fallback is src = full or m (composio.py:697), and _body_and_snippet uses the list messageText or preview (composio.py:208). No marker is written into raw. raise_if_refused guards only the list call (composio.py:334) and ComposioExec.execute (composio_base.py:74). One detail to add: the Gmail client does have an httpx timeout=60 (composio.py:306-311). What it lacks is the 90 s executor deadline (composio_base.py:9, 63-77).)

<a id="l1-h3-composio-toolkit-unpinned"></a>
### Composio toolkit versions are still unpinned (dangerously_skip_version_check=True)

`l1-h3-composio-toolkit-unpinned` · **P1** · missing · owner **harsh** · mixed · step **S11**

- **Expected:** Toolkit versions are pinned so an upstream change cannot silently break capture. _(source: 00-START-HERE H3; 04-FOR-HARSH H3 (on 3 Oct a toolkit change broke every attachment fetch))_
- **Actual:** Both the Gmail _execute and the shared executor pass dangerously_skip_version_check=True, with 'TODO(prod): pin' (composio.py:318-321; composio_base.py:60).
- **Evidence (measured):** `genios_engine/capture/connectors/composio.py:318-321`; `genios_engine/capture/connectors/composio_base.py:60`
- **What Rohit sees:** The next unannounced toolkit change can stop attachments or mail with no code change on our side.
- **Fix:** Harsh reads the production SDK's current toolkit versions and pins toolkit_versions for gmail, googlecalendar and googledrive. Claude adds a test that fails if the flag returns.
- **Verified:** confirmed by the skeptic (dangerously_skip_version_check=True at composio.py:321 and composio_base.py:60, and no toolkit_versions anywhere. Minor detail: the 'TODO(prod): pin' comment is only at composio.py:318. composio_base.py:60 has no TODO.)

<a id="l1-h3-composio-toolkits-unpinned"></a>
### L1 H3: Composio toolkit versions are still unpinned (dangerously_skip_version_check=True)

`l1-h3-composio-toolkits-unpinned` · **P1** · missing · owner **claude+harsh** · mixed · step **S11**

- **Expected:** Pin the Gmail and Google Calendar toolkits at production's versions (unit M17.C3.L-integration.V2.U04). An unannounced toolkit change on 3 Oct refused 88/88 attachment fetches. _(source: speedrun008/GeniOS-008/layer-1-enterprise-signals/04-FOR-HARSH.md §4 H3; 00-START-HERE.md H3)_
- **Actual:** Every Composio call still runs with dangerously_skip_version_check=True.
- **Evidence (measured):** `genios_engine/capture/connectors/composio_base.py:60`; `genios_engine/capture/connectors/composio.py:321`
- **What Rohit sees:** The next silent toolkit change can again stop every attachment or mail fetch, with sweeps reading as empty or failed and cards stopping.
- **Fix:** Harsh reads the toolkit versions the production SDK resolves today. Claude pins them (version argument per toolkit) and removes the skip flag, with a test that fails if the flag returns.
- **Blocked on:** Harsh: the Composio SDK and toolkit versions in the production image (not SQL)
- **Verified:** confirmed by the skeptic (composio_base.py:60 and composio.py:321 both pass dangerously_skip_version_check=True. composio.py:318 still reads 'TODO(prod): pin toolkit_versions={"gmail": "<ver>"}'. toolkit_versions is used nowhere else in genios_engine. drive.py:187 relies on the same skip.)

<a id="l1-h4-refused-attachments-requeue"></a>
### Whether the attachments refused since 3 Oct were requeued after the deploy is unknown (H4)

`l1-h4-refused-attachments-requeue` · **P1** · unknown until production is read · owner **harsh** · prod_action · step **S09**

- **Expected:** After the deploy, scripts/requeue_refused_attachments.py runs as a dry run, then with --apply, for Rohit's org. _(source: 04-FOR-HARSH H4; YC-II W27/08 §3.1)_
- **Actual:** The script exists (scripts/requeue_refused_attachments.py). No commit or log in the repo records that it ran after c501eec9.
- **Evidence (doc_claim):** `scripts/requeue_refused_attachments.py`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/04-FOR-HARSH.md §4 H4`
- **What Rohit sees:** Decks and contracts attached to investor or vendor mail are missing from memory.
- **Fix:** Harsh runs the dry run, reads the count, then runs --apply.
- **Blocked on:** Production (Rohit's permission): select reason_code, status, refetch_failure_kind, count(*) from parked_events where org_id='<ORG>' and reason_code like 'DOC-%' group by 1,2,3;
- **Verified:** unverifiable without production: The script exists (scripts/requeue_refused_attachments.py, commit 8ca130a3, 5 Oct). No commit or doc since 18 Oct records a run; the only mentions are run instructions (04-FOR-HARSH.md:110; 08-FOR-HARSH:818-819). Only production can answer. Read-only SQL: select status, count(*), count(*) filter (where refetch_last_error like 'requeued after the file_name fix%') as requeued from parked_events where org_id='<ORG>' and source='gmail' and reason_code like 'DOC-%' group by status;

<a id="l1-junk-verdict-readmitted-on-snippet"></a>
### A mail the junk filter archived as llm_junk is re-admitted on every heartbeat and extracted from its list snippet, skipping the gate

`l1-junk-verdict-readmitted-on-snippet` · **P1** · broken · owner **claude** · code · step **S06**

- **Expected:** A junk disposition is a recorded verdict that stands until a gate re-judges it, and an archived mail is 'read by no model'. Re-judging should mean running the current gate again on the full body. _(source: speedrun008/YC-II W27/08-FOR-HARSH-deploy-and-after.md:582 (archive = read by no model); 05-BLUEPRINT Part 7 'Filter accountability'; YC-II W27/03-FINDINGS.md:76 F55 (whether the filter's verdict should stand left to STEP-07))_
- **Actual:** drain_parked runs on every heartbeat (routes.py:1450; limit 200; no org filter) and treats llm_junk and llm_junk_unconfident as RE_ADJUDICABLE (drain.py:44-49). Every archived llm_junk mail that has a payload (archives keep one: pipeline.py:1679-1701) is flipped to outcome='emitted', route='needs_extraction' without running the gate (drain.py:166-247). queue_unread then files it into the re-read ladder (unread.py:338-389), and a re-read skips S2 (gate.py:166-179). On the Gmail fast path a confident drop is never full-fetched, so its stored payload holds only the list fields and snippet (composio.py:602-628). Result: the junk filter delays mail rather than filtering it, and marketing snippets become extraction claims (L3 below_floor lane) and can publish signals.
- **Evidence (measured):** `genios_engine/capture/parked/drain.py:44-49`; `genios_engine/capture/parked/drain.py:166-247`; `genios_engine/api/routes.py:1450`; `genios_engine/capture/landing/unread.py:338-389`; `genios_engine/capture/gate/gate.py:166-179`; `genios_engine/capture/connectors/composio.py:602-628`; `genios_engine/capture/pipeline.py:1679-1701`; `speedrun008/YC-II W27/03-FINDINGS.md:76 (F55, 'preserved on purpose')`
- **What Rohit sees:** Weird cards and noisy memory: newsletter and promotion snippets are extracted a heartbeat after being judged junk, can publish signals, and spend extraction calls.
- **Where the mistake was:** STEP-03 (c1ffbb6d) deliberately kept the old 'a judged drop is re-admitted' behaviour for archives and deferred the question to STEP-07. STEP-07 shipped without closing it, and the deploy runbook tells Harsh that archives are read by no model.
- **Fix:** Re-admission must re-judge, not skip the judge. The drain re-admits an llm_junk archive only when the gate's prompt version has changed since the verdict, and then it full-fetches the body and runs the current gate (the S2 skip for re-reads must not apply to these). Otherwise the archive stays archived. Add a test on the drain→re-read path and a mutation that brings back the bypass. Correct the 08 runbook line.
- **Blocked on:** Production size (needs Rohit's permission): select attention_reason, count(*) from source_events where org_id='<ORG>' and attention_reason like 'readmitted:%' and captured_at >= '2026-10-18' group by 1;
- **Verified:** confirmed by the skeptic (Every cited line holds. RE_ADJUDICABLE includes llm_junk (drain.py:44-49). The drain's union selects archived source_events whose event_trace reason_code is in that set and that have a payload (drain.py:159-172), then flips them to emitted/needs_extraction/P3 without running the gate (drain.py:233-247). It runs on every heartbeat with no org filter and limit 200 (routes.py:1449-1450). queue_unread files it into the re-read ladder (unread.py:338-389). to_raw_object sets rereading (unread.py:96), so whitelist returns W-06 (rules.py:326-327) and S2 is skipped (gate.py:166). The code says this is deliberate: gate.py:172-176 ('the parked drain re-admits an archived llm_junk mail exactly as it re-admitted a dropped one (03 F55)'). A confident drop keeps its light object (composio.py:615-626), and pipeline.py:1683-1686 says the archive holds 'the list snippet and headers'. One caveat: the body is whatever GMAIL_FETCH_EMAILS returned in messageText (composio.py:682-684, _body_and_snippet:208). The repo has no live list response to confirm it is snippet-only.)

<a id="l1-post-deploy-funnel-unmeasured"></a>
### The 4 Oct funnel loss is fixed in code, but production's funnel has not been measured since the 18 Oct deploy

`l1-post-deploy-funnel-unmeasured` · **P1** · unknown until production is read · owner **rohit+harsh** · prod_action · step **S01**

- **Expected:** Every eligible source record has a traceable terminal state, and kept mail and past meetings reach memory (4 Oct baseline: 27 of ~470 emails, 0 of 22 meetings). _(source: 05-BLUEPRINT Phase 1 exit test; memory production-funnel-2026-10-04)_
- **Actual:** In code: S1 'drop' becomes archive (gate.py:13-24). A failed attachment parks only itself (composio.py:826-837). A re-admitted park gets route and lane (drain.py:215-247). Every kept, unread mail is queued (unread.py:338-389). L3 pulls by memory lane — signal, below_floor, metadata, calendar (memory_lanes.py:42-56; a9411a70). Meetings always take the calendar lane (gcal.event.v1, structured/registry.py:203-219). Not fixed: mail deleted before STEP-03 (resync item); an archived mail enters L3 as metadata only, with no words and no correlation (memory_lanes.py:13-14); a parked mail enters only after its re-read. Production has not been read since the deploy (F6).
- **Evidence (measured):** `genios_engine/capture/gate/gate.py:13-24`; `genios_engine/capture/connectors/composio.py:826-837`; `genios_engine/capture/parked/drain.py:215-247`; `genios_engine/capture/landing/unread.py:338-389`; `genios_engine/context/memory_lanes.py:13-14,42-56`; `genios_engine/capture/structured/registry.py:203-219`
- **What Rohit sees:** This is the measurement that says whether L1 is behind 'fewer cards since 18 Oct'.
- **Fix:** With Rohit's permission, Harsh runs the read-only funnel queries and the result is compared with the 4 Oct numbers. Any stage still losing mail becomes its own unit.
- **Blocked on:** Production (Rohit's permission): select source, outcome, attention, count(*) from source_events where org_id='<ORG>' and captured_at >= '2026-10-18' group by 1,2,3 order by 4 desc; select et.stage, et.action, et.reason_code, count(*) from event_trace et where et.org_id='<ORG>' and et.at >= '2026-10-18' and et.stage in ('S1','S2') group by 1,2,3 order by 4 desc; select signal_type, state, count(*) from qualified_signals where org_id='<ORG>' group by 1,2; select disabled_at from l1_semantic_activation where org_id='<ORG>';
- **Verified:** confirmed by the skeptic (All cited code holds: gate.py:11-24; composio.py:826-837 (fetch_failed stub per attachment); drain.py:233-247; unread.py:338-389; memory_lanes.py:13-14, 42-56; registry.py:203-219. a9411a70 is in HEAD. Nuance: lane_for gives CALENDAR only to kept outcomes, emitted or archived (memory_lanes.py:38, 46). A calendar event the gate parks (for example visibility_unknown, or the S0.5 versionability park) does not enter memory until it is recovered. Prod has not been read since the 18 Oct deploy (F6). SQL: select source, outcome, count(*) from source_events where org_id='<ORG>' and captured_at >= '2026-10-18' group by 1,2 order by 1,2;)

<a id="l1-r3-second-mailbox"></a>
### The founder's second mailbox (<founder company mailbox>) is not connected, so 'you never replied' can be false

`l1-r3-second-mailbox` · **P1** · missing · owner **rohit+harsh** · mixed · step **S08**

- **Expected:** Coverage can say what is not connected, and the founder's own second address is captured as a seat connection. _(source: 02-PLAN R3 (W14); memory founder-workstreams-lost-2026-10-05 (only one Gmail + one Calendar connection))_
- **Actual:** The connect flow supports scope workspace|seat (api/routes.py:3189-3203). No connection for the second address is known, and coverage_receipt cannot name a mailbox that is not connected (01-AS-IS W14).
- **Evidence (mixed):** `genios_engine/api/routes.py:3189-3203`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/01-AS-IS.md W14`
- **What Rohit sees:** Wrong 'no reply from you' absences, and the founder's pitch threads are missing.
- **Fix:** Rohit says yes to R3. Harsh connects <founder company mailbox> as a seat for Rohit's org. Claude makes coverage name the unconnected addresses that the brief lists as ours.
- **Blocked on:** Rohit's R3 answer
- **Verified:** unverifiable without production: The code side holds. The connect flow takes scope workspace|seat (routes.py:3189-3203). Coverage works per capability, connected/stale/not_connected (capture/coverage/declaration.py:46-53; model.py:136), so it cannot name a second address that is not connected (01-AS-IS W14). Whether <founder company mailbox> is connected now is a production fact, last measured as not connected on 5 Oct (memory founder-workstreams-lost). Read-only SQL: select id, source, status, seat_id, external_account_id from connections where org_id='<ORG>' and source in ('gmail','composio_gmail');

<a id="l1-resync-and-history-window"></a>
### Mail the old gate deleted, and anything older than 60 days, stay outside memory until Rohit picks the window and Harsh runs the resync

`l1-resync-and-history-window` · **P1** · unknown until production is read · owner **rohit+harsh** · mixed · step **S09**

- **Expected:** The history window is 365 days (D16 restates D5's 180, which would lose 3one4 on 2 Apr). STEP-08's resync frees the keys of mail the old gate deleted and captures it again. _(source: speedrun008/YC-II W27/06-DECISIONS.md D16; 02-PLAN R4; YC-II W27/08-FOR-HARSH-deploy-and-after.md STEP-08 (lines ~943-964))_
- **Actual:** DEFAULT_BACKFILL_DAYS = 60 (connectors/backfill.py:36). resync_deleted_mail.py exists, and its --apply refuses without --days (D16). On 4 Oct prod was re-captured from 3 Oct with a 60-day window, so July's investor threads were gone, and 258 S1 drops kept no payload (memory production-funnel / founder-workstreams). The dashboard never calls /connections/{id}/backfill-window (git grep origin/main), so the window is API-only. Whether the resync ran in prod is unknown.
- **Evidence (mixed):** `genios_engine/capture/connectors/backfill.py:36`; `scripts/resync_deleted_mail.py`; `genios_engine/capture/landing/resync.py (e8a794bd)`; `genios_engine/api/routes.py:2850 (PATCH backfill-window)`; `speedrun008/YC-II W27/06-DECISIONS.md:23 (D16)`
- **What Rohit sees:** Old investor and accelerator threads (July and earlier) cannot be correlated or reasoned about. No history means no 'cold thread' cards.
- **Fix:** Rohit gives the number (365 recommended). Harsh then patches backfill-window on the Gmail and Calendar connections, runs resync_deleted_mail.py --days 365 as a dry run and then with --apply, and waits for the backfill drain.
- **Blocked on:** Rohit's window decision (R4/D16). Production: select connection_id, source_type, status, capture_scope->>'backfill_days' from connections where org_id='<ORG>'; select count(*) from source_events where org_id='<ORG>' and dedup_key like '%#resync:%';
- **Verified:** confirmed with a correction by the skeptic: 'The window is API-only' is incomplete. The dashboard at origin/main 2edfb86 has a 'Historical backfill' control in the Sources modal: options 30d, 90d, 180d (default '6 months') and 365d (src/components/sources/source-preferences.ts:67-72, 467-468; sources-page.tsx:1334-1338, 1610-1615). It PUTs to /api/org/{org}/integrations/{tool}/config, which stores integration_preferences.sync_settings.historical_backfill (account_routes.py:299-317). No capture code reads that value. Connectors take only connections.capture_scope.backfill_days, default 60 (backfill.py:33-36; coverage/window.py:127). The founder can pick '6 months' or '12 months' and still get 60 days. The post-connect copy says 'pulling your last 2 months' (sources-page.tsx:1349). The rest holds: DEFAULT_BACKFILL_DAYS=60 (backfill.py:36); --apply refuses without --days (scripts/resync_deleted_mail.py:114-115); PATCH backfill-window (routes.py:2850); D16 says 365 (06-DECISIONS.md:23). Whether the resync ran in prod is unknown.

<a id="l1-signal-vocabulary-16-types"></a>
### The closed 16-type signal vocabulary has no word for the founder's main workstreams, and the open lane is never promoted

`l1-signal-vocabulary-16-types` · **P1** · missing · owner **rohit** · mixed · step **S12**

- **Expected:** Every candidate is qualified, rejected, parked or unresolved with a reason. The taxonomy covers the benchmark's work (relationship ledger, commitments, cold threads, meetings, conditions). Anything without a word goes to the open lane, which is reviewed weekly and promoted. _(source: 05-BLUEPRINT Part 6 Phase 3 and Phase 5 (P1–P5); contracts/signal.py:223-225 (open lane 'reviewed weekly'))_
- **Actual:** SignalType has 16 members (signal.py:239-300; check constraint migrations/0176_delivery_failure.sql:30). None of them covers an introduction, a meeting held or scheduled, investor or fundraising interest, an application or portal status, or a plain request. Measured on prod on 5 Oct: meetings were typed deadline_stated (18 of 20 expired) and the 11 Aug fund outreach was typed contract_renewal. Open lane: 698 candidates, 0 promoted (context/lane_health.py:75), and open_lane.py:630-745 is its only reader. Adding a member requires ALG-16, ALG-17, the check constraint and the pins (signal.py:227-230).
- **Evidence (mixed):** `genios_engine/contracts/signal.py:210-300`; `migrations/0176_delivery_failure.sql:30`; `genios_engine/context/lane_health.py:75`; `genios_engine/capture/semantic/open_lane.py:630-745`; `memory founder-workstreams-lost-2026-10-05.md (prod 5 Oct)`
- **What Rohit sees:** Fewer and mislabelled cards: meetings expire as deadlines, fund outreach reads as a renewal, and intros or portal updates make no signal, so they never form a bundle.
- **Fix:** Rohit picks the kinds to add (recommended: introduction, meeting, investor_interest, application_status). Claude adds each with its ALG-16 precedence, ALG-17 weight, ALG-19 expiry, a check-constraint migration and the pins, and promotes the matching open-lane kinds. Re-record extraction with the live key.
- **Blocked on:** Rohit's choice of kinds; the live key (R1) for the extraction re-record
- **Depends on:** [l1-b1-live-pass-never-run](#l1-b1-live-pass-never-run)
- **Verified:** confirmed with a correction by the skeptic: The substance holds. There are 16 members (signal.py:239-300), the check constraint matches (migrations/0176_delivery_failure.sql:30), and later migrations do not change it. There is no member for a meeting held or scheduled, investor or fundraising interest, an application or portal status, or a plain request. Two details are wrong. (1) '698 candidates, 0 promoted' is a 17 Sep in-code measurement (context/lane_health.py:75, a string dated 2026-09-17). Production on 5 Oct measured 118 unclassified_observations, 0 reviewed (memory founder-workstreams-lost-2026-10-05). (2) Introductions have nominal near-fits, though not dedicated members: RELATIONSHIP_CHANGE covers 'a new counterparty' (signal.py:262-264) and OPPORTUNITY_SIGNAL covers a 'referral' (signal.py:260).

<a id="l1-a4-gmail-historyid-cursor"></a>
### Gmail incremental sync keys on a date, not historyId (A4)

`l1-a4-gmail-historyid-cursor` · **P2** · missing · owner **harsh** · mixed · step **S11**

- **Expected:** Incremental sync keyed on Gmail's historyId. An expired historyId starts a bounded backfill, and a saved page token is never reused with a new query. _(source: 02-PLAN A4 (fixes W9); 05-BLUEPRINT Phase 1 'cursor recovery')_
- **Actual:** incremental_changes builds `after:YYYY/MM/DD` from the watermark (composio.py:345-352). historyId is only declared in the manifest (connectors/manifest.py:105). The build waits on H2, one live GMAIL_LIST_HISTORY response.
- **Evidence (measured):** `genios_engine/capture/connectors/composio.py:345-352`; `genios_engine/capture/connectors/manifest.py:105`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/00-START-HERE.md H2`
- **What Rohit sees:** A reset cursor never triggers a backfill, so mail can be silently skipped.
- **Fix:** Harsh records one redacted live history response as a fixture (H2). Claude then builds the historyId cursor and its gap backfill.
- **Blocked on:** H2 fixture from the production Composio connection
- **Verified:** confirmed by the skeptic (incremental_changes builds after:YYYY/MM/DD (composio.py:345-352), and no code reads historyId. One thing to add: manifest.py:105-108 marks historyId as deliberately NOT taken ('a second cursor would be a second source of truth about what we have read'). That contradicts A4's target, so building A4 means first resolving that recorded design choice, not only waiting on H2.)

<a id="l1-c2-second-mailbox"></a>
### GeniOS-008 C2: <founder company mailbox> as a second (seat) mailbox, default yes, not known to be connected

`l1-c2-second-mailbox` · **P2** · unknown until production is read · owner **rohit+harsh** · prod_action · step **S08**

- **Expected:** Connect <founder company mailbox> as a seat connection for Rohit's org. _(source: speedrun008/GeniOS-008/03-QUESTIONS.md C2; layer-1-enterprise-signals/04-FOR-HARSH.md H6 R3)_
- **Actual:** The seat path exists (api/routes.py seat connection). Whether the mailbox was connected is a production fact that was not read.
- **Evidence (doc_claim):** `speedrun008/GeniOS-008/layer-1-enterprise-signals/04-FOR-HARSH.md §4 H6 (R3: api/routes.py:3191 seat path)`
- **What Rohit sees:** Work that reaches the company address is invisible, which also keeps the golden set at one founder mailbox (D52, F114 'revisit with a second mailbox').
- **Fix:** Rohit confirms. Harsh connects it as a seat connection and checks l1_sync_runs for it.
- **Blocked on:** select connection_id, source_type, seat_id, status, created_at from connections where org_id='<ORG>';
- **Verified:** unverifiable without production: The seat connect path exists: api/routes.py:3189-3199 ConnectLink scope 'seat', /integrations/{tool}/connect, and _first_pull_seat at :3305. L1 04-FOR-HARSH.md:121-123 H6 says 'Only if Rohit says yes'. GeniOS-008 03-QUESTIONS.md:30 C2 defaults to Yes, and its header says a skipped question takes its default. Whether <founder company mailbox> is connected is a production fact. Read-only SQL: `select connection_id, source_type, seat_id, status, created_at from connections where org_id = '<rohit_org>';`

<a id="l1-d23-b27-promoted-archive-reads-only-the-snippet"></a>
### YC-II D23 + B27/F58: promoting Boardy's archived intros (pending Rohit's list read) would read only the stored list snippet

`l1-d23-b27-promoted-archive-reads-only-the-snippet` · **P2** · partial · owner **claude+harsh** · mixed · step **S06**

- **Expected:** D23: Harsh runs promote_archived dry, Rohit reads the ids/dates, --apply, and the next chain pass reads the promoted mail's words. _(source: speedrun008/YC-II W27/06-DECISIONS.md D23; STEP-18-TO-BUILD-known-bugs.md B27; 03-FINDINGS.md F58)_
- **Actual:** A confident junk drop keeps only its light list-snippet object. Promotion re-reads the stored payload (to_raw_object), never fetching the body, so a promoted intro is read from its ~snippet. Whether D23 was run in production is unknown. Since B2 (19 Oct) new intros are always KEEP, so this concerns the old archive only.
- **Evidence (measured):** `genios_engine/capture/connectors/composio.py:623 ('CONFIDENT junk keeps its light (snippet) object')`; `genios_engine/capture/landing/unread.py:74-96 (to_raw_object: the stored payload)`; `scripts/promote_archived.py:37-42 (dry run unless --apply)`
- **What Rohit sees:** Old Boardy introductions stay archived or snippet-only, so no intro cards come from them.
- **Fix:** Claude makes a promotion re-fetch the body through the connector (B27's design) before reading. Then Harsh runs promote_archived dry, Rohit reads, --apply.
- **Blocked on:** `python scripts/promote_archived.py --org <ORG> --rule N-02 --sender-domain boardy.ai --database-url <prod>` (dry run)
- **Depends on:** [l1-c3-d16-history-window-still-60-days](#l1-c3-d16-history-window-still-60-days)
- **Verified:** confirmed by the skeptic (composio.py:619-627 skips the full fetch for confident junk (and for rule junk that is not rescued); it keeps 'its light (snippet) object'. A promotion is read back by api/routes.py:1827-1890 _reread_unread through unread.to_raw_object (capture/landing/unread.py:74-96), which returns the stored payload. ingest_pushed_objects (push_ingest.py:142-175) fetches no body. scripts/promote_archived.py:41 makes --apply opt-in. Whether D23 ran in production is unverifiable.)

<a id="l1-e3-entity-doubt-and-person-joins"></a>
### Entity doubt is thrown away, and a person known only by name never joins a bundle (E3)

`l1-e3-entity-doubt-and-person-joins` · **P2** · partial · owner **claude** · code · step **S13**

- **Expected:** Entity resolution keeps its doubt ('probably the same person' stays probable). Correlation covers same person, similar names and uncertain matches. _(source: GeniOS-008/00-ARCHITECTURE.md 'Inside L1'; 02-PLAN E3; 05-BLUEPRINT golden matrix 'Correlation')_
- **Actual:** CanonicalHint.alternatives is computed, but apply_to writes only canonical_hint (validate/canonical.py:530-544). G6 (0d5939d1) keeps name-only people as unresolved candidates on the bundle (bundle.py:84-117), which is partial. L1's canonicalizer is a small alias table, so most people carry no hint and person joins by proximity effectively never fire.
- **Evidence (measured):** `genios_engine/capture/validate/canonical.py:530-544`; `genios_engine/capture/esqe/bundle.py:84-117`; `git show 0d5939d1 (G6.3/G6.5)`
- **What Rohit sees:** Contributes to 'no correlation': two mails about one person in different threads arrive at L2 as unrelated.
- **Fix:** Carry the alternatives and their basis on the mention, and read them where L3 or L2 resolves identity (built with the L3 identity work, so the field has a reader).
- **Verified:** confirmed with a correction by the skeptic: 'Doubt is thrown away' holds: apply_to writes only canonical_hint and drops alternatives (canonical.py:532-544). The mechanism behind the person-join claim is wrong. (1) Most people do carry a hint. On a miss in the alias table, propose_canonical gives a PERSON a NORMALISED_FORM hint equal to the normalised name (canonical.py:600-604; platform/identity.py:133-143), and the extractor applies it to every mention (extractor.py:1645). Measured: 'Priya' gets hint 'priya'. So G6.3's 'no canonical hint' test (bundle.py:93-99, 106-112) would almost never mark a person as name-only. (2) Proximity joins never fire for any entity, people or companies, because bundle.py reads extraction.entities while the field is entity_mentions (extraction.py:639). Measured: entity_keys() returns frozenset() on a real ExtractionResult. G6's name-only candidates and entity links are therefore never produced in production, and G6 is effectively unbuilt rather than partial.

<a id="l1-e6-closed-roles"></a>
### Roles are free text: sender, promisor, owner and approver are not a closed set (E6)

`l1-e6-closed-roles` · **P2** · missing · owner **claude** · code · step **S12**

- **Expected:** The published signal carries a closed role set (sender ≠ promisor ≠ owner ≠ approver). _(source: GeniOS-008/00-ARCHITECTURE.md 'Inside L1'; 02-PLAN E6)_
- **Actual:** RoleAssertion(party, role) has a free-text role (contracts/extraction.py:481-500). 02-PLAN marks E6 not built because it needs the extraction re-record.
- **Evidence (measured):** `genios_engine/contracts/extraction.py:481-500`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/02-PLAN.md Group E status E6`
- **What Rohit sees:** The wrong person can be named as owing the move.
- **Fix:** Close the role vocabulary in the extraction schema, then re-record with the live key.
- **Blocked on:** live key (R1)
- **Depends on:** [l1-b1-live-pass-never-run](#l1-b1-live-pass-never-run)
- **Verified:** confirmed by the skeptic (RoleAssertion.role is free text, and the docstring explicitly refuses a closed vocabulary (extraction.py:481-507). No closed role set appears anywhere on the published signal. 02-PLAN.md:100 marks E6 not built.)

<a id="l1-h2-a4-gmail-history-cursor"></a>
### L1 H2 → A4: the Gmail cursor is still a day-granular date; the live historyId fixtures were never recorded

`l1-h2-a4-gmail-history-cursor` · **P2** · missing · owner **claude+harsh** · mixed · step **S11**

- **Expected:** Harsh records one live Gmail history response and one expired-historyId 404 as fixtures, then Claude keys the Gmail cursor on historyId. _(source: speedrun008/GeniOS-008/layer-1-enterprise-signals/04-FOR-HARSH.md §4 H2; 00-START-HERE.md A4)_
- **Actual:** No gmail_history_live.json fixture exists under tests/capture/connectors/fixtures. historyId appears only as a manifest field.
- **Evidence (measured):** `genios_engine/capture/connectors/manifest.py:105 (Field('historyId', ...))`; `ls tests/capture/connectors/fixtures | grep history → none`
- **What Rohit sees:** A reset cursor goes unnoticed, so mail can be missed or re-read silently.
- **Fix:** Harsh saves the two redacted responses as fixtures. Claude builds A4 against them.
- **Verified:** confirmed by the skeptic (The tests/capture/connectors/fixtures directory does not exist. No test file named *history*.json relates to Gmail. GMAIL_LIST_HISTORY/list_history appears nowhere in genios_engine or tests. The cursor is still date-granular: composio.py:347-350 builds `after:{since:%Y/%m/%d}`. historyId appears only as a declined manifest field (manifest.py:105-108). L1 04-FOR-HARSH.md:85-98 (H2) is still the precondition.)

<a id="l1-time-inferred-not-ledgered"></a>
### A3's count of mail with an inferred timestamp lives only in a log line, not in l1_sync_runs

`l1-time-inferred-not-ledgered` · **P2** · partial · owner **claude** · code · step **S10**

- **Expected:** Per-stage counts are measurable from stored data, not from grepping logs. _(source: 05-BLUEPRINT Part 7 'Production observability'; 04-FOR-HARSH H5)_
- **Actual:** SyncSummary.time_inferred is counted and logged (sync_runner.py:362, 902, 931), but the l1_sync_runs insert does not name it (routes.py:530-560). H5 asks Harsh to grep the worker log.
- **Evidence (measured):** `genios_engine/capture/acquire/sync_runner.py:362,902,931`; `genios_engine/api/routes.py:530-560`
- **Fix:** Add a time_inferred column (migration) and name it in the insert. Test plus mutation.
- **Verified:** confirmed by the skeptic (SyncSummary.time_inferred is defined, counted, logged and summed (sync_runner.py:362, 902, 931-934, 1016). The l1_sync_runs INSERT does not name it (routes.py:531-560). No migration has a time_inferred column (grep migrations/ shows no hits).)

<a id="layer-l2"></a>
## L2 Signals Qualification (packs/ + reason/)

> L2 has the right parts, but production does not run them as the main path. The parts that exist and work: a bounded judgment pass (R-9, reason/l2) with a six-block dossier, the claim check, a code-chosen lane and replay; the STEP-12 expert pass (R-7); and the L3 admission of L2's proposals. Thinking-off on all R-sites, the money tool, L1 conflicts reaching the judgment and the oversized-prompt fix are all on the production head. Even so, a card exists only when L3 has already filed a situation on the file and that situation's domain maps to an activated corpus. Situations in `general`, the fallback domain whenever no keyword hint fires, are decided in shadow only, so no card. A judgment that is refused, truncated, failed, over budget or held at admission is handed back to the formula lanes (the 23 reasoners and the per-pack rules). Those lanes also spend the shared 7-a-day signal cap before the expert's files are decided. Together these explain "fewer and weird" cards and "L2 and L3 failing each other". Held moves never get a repair call: the founder gets a fixed engineer's sentence from verify.py:787-793 plus claim_check.HELD_BECAUSE in place of the advice. The STEP-13b check fixes that cut Haiku's held share from 79% to 18.5% sit on an unmerged branch, and the production model (Sonnet 5) has never had a completed live golden pass. Under `l2_cards`, the six-dimension confidence, options, decision need and history are dropped where the result is written as an expert review, so the card still shows the formula's {C, U, I}. Admission stays in shadow and never creates a situation. A subject with no file can never become a card. Domain expertise (Plane D) reaches the model only through one Founder Office playbook, and only for files the brief names. Goals reach the judgment only as background lines with no ids. Nothing in the prompt asks about them and nothing in the output can carry one, so no card can name a goal. Almost every skip shows only in a server log line. The production state (which switches are on, held share, card sources) was not read; the SQL is in each item's blocked_on.

| Item | Sev | Status | Owner | Step |
|---|---|---|---|---|
| [YC-II D57 / F169: a file with no reply pattern yet is never re-examined, so silent investor outreach never res](#l2-d57-quiet-file-without-pattern-never-relooked) | P0 | missing | rohit | S21 |
| [GeniOS-008 A4 + L2 04-FOR-HARSH §3: Founder Office, expert_review and l2_reasoning activation for Rohit's org ](#l2-founder-office-and-expert-switches-prod-state) | P0 | unknown until production is read | rohit+harsh | S02 |
| [GeniOS-008 A2/A3 + GeniOS-009 D5/D6: the cutover is per tenant and covers every type at once, not one situatio](#l2-a2-a3-per-type-cutover-not-built) | P1 | missing | rohit+harsh | S25 |
| [GeniOS-008 A5 / YC-II D11, F230, F274: the LLM decider (R-1) is not retired, and the golden set always runs wi](#l2-a5-llm-decider-not-retired-golden-forces-it-on) | P1 | partial | rohit+harsh | S25 |
| [Up to six producers can make a card today, each with its own switch; the L2 judgment is off by default](#l2-card-paths-six-producers) | P1 | partial | claude+harsh | S25 |
| [With l2_cards on but l2_reasoning off (or no R-9 client), nobody judges a moved file](#l2-cards-precondition-not-enforced) | P1 | broken | claude | S18 |
| [The shared 7-per-day signal cap is spent by formula situations before the expert/L2 file decisions get a turn](#l2-daily-cap-formula-first) | P1 | broken | claude | S18 |
| [F15 (five funds, eight weeks silent): today's path makes 0 cards, the L2 path splits it into 5 held question c](#l2-f15-five-held-cards) | P1 | broken | claude | S21 |
| [When a judgment fails or is held, the file falls back to the formula/pack lanes; refused and truncated answers](#l2-fallback-to-formula-lanes) | P1 | partial | claude | S19 |
| [H1–H3 not done: 23 formula reasoners, the LLM decider and the per-pack rule lane still decide](#l2-h1-h3-formula-lanes-still-decide) | P1 | missing | claude+harsh | S25 |
| [Held cards read as engineer sentences: a fixed template replaces the model's advice, and nothing repairs befor](#l2-held-card-engineer-template) | P1 | broken | claude | S20 |
| [I2 not made: l2_cards is a whole-tenant switch, compared only offline on the ideal reader](#l2-i2-first-switch-not-made) | P1 | unknown until production is read | rohit+harsh | S25 |
| [Under l2_cards the judgment half (six-dimension confidence, options, decision need, history) is dropped; the c](#l2-judgment-half-dropped-confidence-cui) | P1 | partial | claude | S22 |
| [Since 21 Oct an overdue move, an 'unknown' confidence or an unnamed decider turns the move into a held questio](#l2-judgment-holds-overdue-and-unknown) | P1 | broken | claude | S20 |
| [Under l2_cards no 'kind of work' proposal is ever written, so unlisted files never gain a playbook](#l2-kind-proposals-lost-under-l2-cards) | P1 | broken | claude | S19 |
| [On the L2 card path, the model is asked for proposed_kind but nothing writes it, so kind proposals stop when l](#l2-path-drops-kind-proposals) | P1 | broken | claude | S19 |
| [Domain expertise (Plane D) barely reaches the judgment: one Founder Office playbook, only when the brief names](#l2-plane-d-thin) | P1 | partial | claude | S22 |
| [A subject with no file (a first mail, a new admission) is judged but can never become a card](#l2-seed-subject-no-card) | P1 | missing | claude | S21 |
| [Nearly every skip, refusal, budget cap or shadow decision is invisible to Rohit and shows only in a server log](#l2-skips-invisible) | P1 | missing | claude | S18 |
| [STEP-13b claim-check fixes (79% → 18.5% held on Haiku) never reached production; the production model has no c](#l2-step13b-check-fixes-unmerged) | P1 | built, not live | claude+harsh | S20 |
| [YC-II D72, D73 + F267–F269, s13b-D8: whether R-7 / the brief drafter should think, and live-eval spend beyond ](#l2-d72-d73-thinking-and-live-eval-budget) | P2 | shadow / switched off | rohit | S07 |
| [L2 raises evidence needs, but the fetchers are off, so no re-entry happens and no card says 'waiting on X'](#l2-evidence-loop-not-armed) | P2 | built, not live | harsh | S13 |
| [The expert pass still stops entirely on a per-call budget refusal (the L2 pass was fixed)](#l2-r7-per-call-refusal-stops-pass) | P2 | broken | claude | S18 |

<a id="l2-d57-quiet-file-without-pattern-never-relooked"></a>
### YC-II D57 / F169: a file with no reply pattern yet is never re-examined, so silent investor outreach never resurfaces

`l2-d57-quiet-file-without-pattern-never-relooked` · **P0** · missing · owner **rohit** · mixed · step **S21**

- **Expected:** D57 recommendation: re-think a quiet file at its playbook's stage prior, else at the day ladder's rungs (7, 14, 30 days) while our ask or theirs is open. _(source: speedrun008/YC-II W27/06-DECISIONS.md D57; 03-FINDINGS.md F169; 05-HOW-THE-EXPERT-THINKS §5)_
- **Actual:** The default ('as built') still holds. Expert triggers fire on time only via reply_overdue/past_normal, which need the file's own measured usual gap. A one-touch wave has none, so after the first review ('wait') nothing re-thinks it. The fingerprint's 'quiet' rung changes, but a fingerprint change alone is explicitly not a trigger. Golden F15 (outreach to five funds, eight weeks of silence) is one of the 4 failing cases and carries this blocked_on.
- **Evidence (measured):** genios_engine/reason/expert/triggers.py:24-30 ('Time passing is no trigger either, unless it crosses one of the file's own patterns'); `genios_engine/reason/expert/triggers.py:150-173 (_crossings returns nothing when their_usual/our_usual is None)`; `genios_engine/reason/expert/fingerprint.py:84 ('quiet' in inputs) vs sweep.py:243-247 (no trigger → untouched)`; `tests/replays/specs/founder/F15.json:309 (blocked_on: 03 F169, 06 D57)`
- **What Rohit sees:** A fundraising founder's investor wave that goes silent produces one 'wait' review and then never a card. Combined with the compiled lane refusing fundraising (D1), silent investors produce no card at all.
- **Where the mistake was:** STEP-12 shipped with 'only the file's own pattern re-thinks a quiet file', although its own golden case F15 records this exact production failure. The decision has stayed open since 10 Oct.
- **Fix:** Rohit takes D57's recommendation. Claude adds a trigger: while an ask is open and the file has no usual, crossing the playbook's stage prior (card_lines.STAGE_PRIOR exists) or, failing that, DAY_LADDER rungs 7/14/30 brings the file back. The same rule goes into the L2 sweep's subject selection. Re-record F15 with the ideal reader.
- **Depends on:** [l2-d1-founder-playbooks-unreviewed-compiled-lane-refuses](#l2-d1-founder-playbooks-unreviewed-compiled-lane-refuses)
- **Verified:** confirmed by the skeptic (triggers.py:24-30 says time passing is no trigger unless it crosses the file's own patterns. their_usual (:127-135) returns None without a measured reply time or usual_gap. _crossings (:150-173) then fires nothing: REPLY_OVERDUE needs `usual`, PAST_NORMAL needs longest_gap_days, which a one-touch file lacks. fingerprint.py:86 puts 'quiet' in the inputs. sweep.py:243-247 leaves the file untouched when no trigger fires, and re-reviews only when a version moved and the file moved (:250-265). F15.json:309 carries the blocked_on. GeniOS-009 01-AS-IS-CARDS.md:25, 83 lists F15 as failing and wrongly silent on today's path. Note: on the L2 path, F15 instead produces 5 held investigation cards (01-AS-IS-CARDS.md:54). It still fails, but it is not silent there.)

<a id="l2-founder-office-and-expert-switches-prod-state"></a>
### GeniOS-008 A4 + L2 04-FOR-HARSH §3: Founder Office, expert_review and l2_reasoning activation for Rohit's org is unverified; all default off

`l2-founder-office-and-expert-switches-prod-state` · **P0** · unknown until production is read · owner **rohit+harsh** · prod_action · step **S02**

- **Expected:** Rohit's org: Admin and Founder Office live, Sales/Support off. expert_review activated after the deploy, then l2_reasoning in shadow with its first rows read. _(source: speedrun008/GeniOS-008/03-QUESTIONS.md A4; layer-2-reasoning/04-FOR-HARSH.md §2-§3 and G-1 'Switch it on'; YC-II W27/06-DECISIONS.md D2 (activate_tenant.py --domains admin,founder_office))_
- **Actual:** Founder Office is default_on: false. expert_review, l2_reasoning and l2_cards are never default-on. The golden runner turns founder_office, expert_review (and l2_* under GENIOS_GOLDEN_L2) on for every golden tenant, so the golden board assumes switches that production only has if Harsh flipped them. Production was not read.
- **Evidence (measured):** `Domain Expertise/Founder Office Expertise/domain.yaml:45 (default_on: false)`; `genios_engine/platform/l4_activation.py:100-104, 117-122 (expert_review / l2_reasoning / l2_cards off by default)`; tests/replays/engine_runner.py:345, 395-400 (golden switches on founder_office), :419-427 (expert_review, l2_reasoning, l2_cards)
- **What Rohit sees:** With Founder Office or expert_review off, no Founder Office file reaches a card through any path (see the D1 item). That is fewer cards and no fundraising/programme cards.
- **Fix:** Harsh runs the two read-only queries. If founder_office or expert_review is off for Rohit's org, Rohit approves and Harsh runs `scripts/activate_tenant.py --domains admin,founder_office` and activates expert_review (then l2_reasoning in shadow), reading the first rows as 04-FOR-HARSH G-1 says.
- **Blocked on:** select domain, enabled_at, disabled_at from l3_activation where org_id='<ORG>'; select feature, enabled_at, disabled_at from l4_activation where org_id='<ORG>';
- **Verified:** unverifiable without production: The code facts are confirmed. Founder Office domain.yaml:45 has default_on: false. l4_activation.py:100-122 has expert_review, l2_reasoning and l2_cards off by default, and activated_features (:440-463) reads only explicit rows. No migration activates any of them; a grep of migrations for founder_office/expert_review/l2_cards found no activation inserts. The golden runner switches on founder_office (engine_runner.py:345, 395-400), expert_review (:413-421) and l2_* (:422-427). Memory admin-domain-only.md records the 9 Oct decision to activate Founder Office for Rohit's org via scripts/activate_tenant.py; that is a decision, not a measurement. Only production can answer. Read-only SQL: `select org_id, feature, activated_at, deactivated_at from l4_activation where feature in ('expert_review','l2_reasoning','l2_cards') order by org_id;` plus the matching select on the L3 domain activation table for domain='founder_office'.

<a id="l2-a2-a3-per-type-cutover-not-built"></a>
### GeniOS-008 A2/A3 + GeniOS-009 D5/D6: the cutover is per tenant and covers every type at once, not one situation type at a time

`l2-a2-a3-per-type-cutover-not-built` · **P1** · missing · owner **rohit+harsh** · mixed · step **S25**

- **Expected:** New path built beside the old one in shadow, scored by the golden set, then switched one situation type at a time, starting with 'awaiting reply / outreach'. G0.2: l2_cards on one tenant, then admission gates one type. _(source: speedrun008/GeniOS-008/03-QUESTIONS.md A2, A3; layer-2-reasoning/00-START-HERE.md L2-Q4, L2-I2; GeniOS-009/08-DECISIONS.md D5, D6; 09-HARSH-HANDOVER.md §4 G0)_
- **Actual:** `l2_cards` is a per-tenant switch with no situation-type filter. Once on, every admitted L2 judgment of every file becomes that file's review and card. L3 admissions are written in shadow only. Their reader `admitted()` has no production caller, and context_health declares it unreached ('nothing makes a card from it yet'). No per-type gate exists anywhere.
- **Evidence (measured):** `genios_engine/reason/l2/sweep.py:330-333 (makes_cards = FEATURE_L2_CARDS in activated; no type filter in the loop)`; `genios_engine/context/l2_admission.py:24 ('SHADOW: nothing here touches context_situations')`; `genios_engine/context/context_health.py:37-40 (l2_admission.admitted listed UNREACHED)`; `genios_engine/platform/l4_activation.py:117-122 (l2_reasoning, l2_cards default off)`; `grep: the only l2_admissions readers are context/l2_admission.py:200 and the erasure list api/account_routes.py:942`
- **What Rohit sees:** With l2_cards on, every file's card changes at once, so a regression in one type cannot be isolated. With it off (the default), no L2 judgment reaches a card. That is one reason Rohit sees 'sometimes no reasoning'.
- **Where the mistake was:** The L2 rebuild (C1) built the cutover as a whole-tenant switch, against 01-RULES Rule 2 and A2's 'one situation type at a time'. The per-type gate in G0.2 has no unit.
- **Fix:** Rohit confirms A3: is the first type still awaiting-reply/outreach, or does l2_cards stay all-types for his org? Then Claude adds a per-type gate: l2_cards admits a file's card only for situation types on a per-tenant allow-list, and admission reads it. Then Harsh switches l2_reasoning → l2_cards on Rohit's org (D6).
- **Blocked on:** Production state of the switches: select feature, enabled_at, disabled_at from l4_activation where org_id='<ORG>';
- **Depends on:** [l2-founder-office-and-expert-switches-prod-state](#l2-founder-office-and-expert-switches-prod-state)
- **Verified:** confirmed with a correction by the skeptic: The detail 'every admitted judgment becomes the file's review and card' is not exact. sweep.py:378-384 writes the file review for any judgment L3 ADMITTED **or REJECTED**, unless one of its admissions is a HOLD. A rejected judgment ('nothing owed') becomes a review that stands the old lane down and makes no card. The L2 path also does more than shadow writes: record_interpretations (l2_admission.py:176-196) appends rows to situation_interpretations. It still never touches context_situations. l2_cards takes effect only when expert_review is also on, because the expert sweep returns early without it (reason/expert/sweep.py:166, 171).

<a id="l2-a5-llm-decider-not-retired-golden-forces-it-on"></a>
### GeniOS-008 A5 / YC-II D11, F230, F274: the LLM decider (R-1) is not retired, and the golden set always runs with it on

`l2-a5-llm-decider-not-retired-golden-forces-it-on` · **P1** · partial · owner **rohit+harsh** · mixed · step **S25**

- **Expected:** Retire the LLM decider: the model may not choose DECISION vs DEFER. The one bounded judgment pass replaces it. _(source: speedrun008/GeniOS-008/03-QUESTIONS.md A5; 00-ARCHITECTURE.md 'the model rules'; layer-2-reasoning/00-START-HERE.md L2-H2)_
- **Actual:** reason/llm_decision_maker.py is still live code. Its docstring says 'the model decides — act now (DECISION) or not yet (DEFER)', gated by GENIOS_L4_LLM_DECISION_MAKER (default False). Retirement is marked 'at cutover' (L2-H2), and there is no per-type cutover (see l2-a2-a3). The golden runner forces the decider on for every org, so 63/67 measures a configuration production runs only if the env var is set. Whether it is on in production was asked in YC-II 07 §9 and L2 04-FOR-HARSH §3.1 and never answered. B9/F274: its 400/day cap is per process and has no dollar governor (Rohit's call). F230: its lane rides on the model's own confidence.
- **Evidence (mixed):** `genios_engine/platform/config.py:110-111 (l4_llm_decision_maker False; _orgs '')`; `genios_engine/reason/llm_decision_maker.py:9 and :118-128 (enabled_for)`; `tests/replays/engine_runner.py:69-70 (golden sets l4_llm_decision_maker True for every org)`; `speedrun008/YC-II W27/07-WHAT-IS-DONE.md §9 row 'is GENIOS_L4_LLM_DECISION_MAKER on in production?'`; `speedrun008/YC-II W27/03-FINDINGS.md F230, F274`
- **What Rohit sees:** If the decider is off in production, compiled-lane cards come from the formula while the golden set measures the model's decisions. 'Golden green' then says little about what Rohit sees.
- **Where the mistake was:** The golden harness pinned the decider on (engine_runner.py:69) while the code default stayed off, and the production value was never recorded.
- **Fix:** Harsh reports the production env value. Rohit confirms A5 (retire). Claude then (a) makes the golden runner run the production configuration, or scores both, and (b) removes R-1 from the lanes as each type cuts over, so B9/F274 and F230 become moot.
- **Blocked on:** Harsh reads GENIOS_L4_LLM_DECISION_MAKER and GENIOS_L4_LLM_DECISION_MAKER_ORGS from the production service environment (not SQL)
- **Depends on:** [l2-a2-a3-per-type-cutover-not-built](#l2-a2-a3-per-type-cutover-not-built)
- **Verified:** confirmed with a correction by the skeptic: The production state is not wholly unknown. Prior-session memory why-no-cards-since-25-sep.md, measured 2026-10-01, records production with GENIOS_L4_LLM_DECISION_MAKER = true and no org allowlist, so it was ON for every org. The model then DEFERred every candidate during the 25 Sep spend-limit outage. The golden runner's own comment labels PRODUCTION_SWITCHES (engine_runner.py:67-70) as 'Production's overrides of the code's defaults'. So the golden setting matches production as last measured; it is not a configuration production lacks. Whether it is still on after the 18 Oct deploy needs a production env read.

<a id="l2-card-paths-six-producers"></a>
### Up to six producers can make a card today, each with its own switch; the L2 judgment is off by default

`l2-card-paths-six-producers` · **P1** · partial · owner **claude+harsh** · mixed · step **S25**

- **Expected:** One path: L1 bundle → L2 judgment (ReasoningResult) → L3 admits → L4 → L5 card. The new path is built beside the old one and switched per situation type once the golden set says it is at least as good; the formula reasoners, the LLM decider and the per-pack rule lane then retire. _(source: speedrun008/GeniOS-008/00-ARCHITECTURE.md 'The flow' + 'Cutover rule'; layer-2-reasoning/02-PLAN.md §7 (H1–H3, I1–I2))_
- **Actual:** Traced from api/routes._run_l2_chain (routes.py:738): process_pending (L3 forms situations first, :799) → reason/runner.run_all (:823) → deliver.build_cards_for_org (:844) → post passes (:854). Producers and their switches: (1) the legacy per-pack rule lane, run() for every tenant_packs pack in state active/shadow (runner.py:1958-1959). Default packs are sales, general, admin and customer_support (packs/wiring.py:30-31), so it is always on. (2) The compiled L3 lane, domain_shadow.shadow_compile (runner.py:1925): L3 situation → ExpertisePackage → deterministic R-units → DecisionMaker. It is entered if the global use_domain_compiler is set, an l3_activation row exists (Admin default_on: true in Domain Expertise/Admin Expertise/domain.yaml:50; Founder Office default_on: false) or the L1 seam is on. Each situation is live only when its domain is activated (domain_shadow.py:968-995). (3) The LLM decision maker inside DecisionMaker.decide for lanes 1–2 (decision_maker.py:1120-1126). It is switched by the env vars GENIOS_L4_LLM_DECISION_MAKER and _ORGS (platform/config.py:110-111), and any failure DEFERs (llm_decision_maker.py:20-22). (4) The expert R-7 file review → covered → _decide_covered_files → signal expert.file_review, plus the founder-question card (runner.py:1901; domain_shadow.py:712-868). Switch: l4 `expert_review`, not default-on (platform/intelligence_onboarding.py:183-187). (5) The L2 R-9 judgment → written as the file's review → same path as (4) (reason/l2/sweep.py:332, 381-384). Switches: `l2_cards` + `l2_reasoning` + `expert_review` (l4_activation.py:117-127, 197-200), file subjects only, and no admission HOLD. (6) Post passes team/verify/meetings, which make deterministic cards with no switch (reason/team/postpass.py:26-30). Not producers: `situation_reasoner` R-6 is retired and its switch is refused (l4_activation.py:153-163); `cards_from_situations` only regroups what lanes 1–5 made and is off by default (intelligence_onboarding.py:172-177); `l2_reasoning` without `l2_cards` is shadow only (runner.py:1903-1910). Narration (`bundle`, R-2, default-on) changes words, never whether a card exists.
- **Evidence (measured):** `genios_engine/api/routes.py:738-858`; `genios_engine/reason/runner.py:1895-1960`; `genios_engine/reason/domain_shadow.py:712-868, 968-995`; `genios_engine/reason/decision_maker.py:1120-1126`; `genios_engine/platform/config.py:110-111`; `genios_engine/platform/l4_activation.py:117-127, 153-163, 197-200`; `genios_engine/platform/intelligence_onboarding.py:167-206`; `genios_engine/packs/wiring.py:30-31`; `genios_engine/reason/team/postpass.py:26-30`; `Domain Expertise/Admin Expertise/domain.yaml:50`
- **What Rohit sees:** Cards come from up to six producers with different rules and voices: formula/pack cards, expert file cards, question cards and deterministic team/verify cards. Rohit cannot tell which made a card, and the mixture reads as 'weird'.
- **Fix:** Make the L2 judgment the one producer, one situation type at a time (I2). Write the active producer on every card (capability_key already exists) and count per producer on the funnel. Retire lanes 1–3 per type at cutover (H1–H3).
- **Blocked on:** Production state not read. Rohit to run (read-only): select org_id, feature, enabled_at, disabled_at from l4_activation where feature in ('expert_review','l2_reasoning','l2_cards','cards_from_situations','bundle') order by 1,2; select org_id, domain, enabled_at, disabled_at from l3_activation order by 1,2; select capability_key, builder_version, output_lane, count(*) from cards where org_id='<ORG>' and created_at >= '2026-10-18' group by 1,2,3 order by 4 desc; plus Harsh: the value of GENIOS_L4_LLM_DECISION_MAKER(_ORGS) in the prod environment.
- **Depends on:** [l2-i2-first-switch-not-made](#l2-i2-first-switch-not-made), [l2-h1-h3-formula-lanes-still-decide](#l2-h1-h3-formula-lanes-still-decide)
- **Verified:** confirmed with a correction by the skeptic: Substance holds: six producers exist and the L2 judgment is off by default. One detail is wrong. Producer (5), the L2 R-9 card path, does not need expert_review in code. l2_pass checks only l2_reasoning (reason/l2/sweep.py:177-178) and l2_cards (makes_cards, sweep.py:335). When those two are on, a file judged through its own bundles is written as a review and covered (sweep.py:381-384, 431-433), and the compiled lane decides it. expert_review adds only two things: it hands over the moved files (to_l2_files, reason/expert/sweep.py:277-286), and it covers files from reviews that already stand. PRECONDITIONS lists expert_review (l4_activation.py:196-201), but that list is not enforced (l4_activation.py:164-168; activate() at :551-600 checks only names and retired features).

<a id="l2-cards-precondition-not-enforced"></a>
### With l2_cards on but l2_reasoning off (or no R-9 client), nobody judges a moved file

`l2-cards-precondition-not-enforced` · **P1** · broken · owner **claude** · code · step **S18**

- **Expected:** l2_cards requires l2_reasoning and expert_review: the pass that judges, and the review path its result decides through. _(source: genios_engine/platform/l4_activation.py:197-200 PRECONDITIONS)_
- **Actual:** PRECONDITIONS are 'NOT enforced … REPORTED' (l4_activation.py:166-170). expert_pass sees l2_cards, builds no R-7 client and hands every moved file to L2 (reason/expert/sweep.py:171-176, 277-286). l2_pass then returns {'skipped': 'l2_reasoning_not_activated'} or 'no_model_configured' (reason/l2/sweep.py:177-181), and neither is logged. Moved files lose cover and fall to the formula lanes.
- **Evidence (measured):** `genios_engine/platform/l4_activation.py:166-170, 197-200`; `genios_engine/reason/expert/sweep.py:171-176, 277-286`; `genios_engine/reason/l2/sweep.py:177-181`
- **What Rohit sees:** Silent stop: no new file judgments, and only stale or formula cards. This is latent until the switches are mismatched.
- **Fix:** In expert_pass, set l2_judges = l2_cards AND l2_reasoning AND a buildable R-9 client. Otherwise the expert reviews as before and logs a warning. Add a test with l2_cards on and l2_reasoning off where R-7 must still run.
- **Blocked on:** Whether production is in this state: select org_id, feature, disabled_at from l4_activation where feature in ('l2_cards','l2_reasoning','expert_review');
- **Verified:** confirmed by the skeptic (PRECONDITIONS is 'NOT enforced … REPORTED' (l4_activation.py:164-168), and activate() (:551-600) checks only require_feature and RETIRED_FEATURES. Under l2_cards, expert_pass builds no client and returns to_l2_files (expert/sweep.py:171-176, 270-277). l2_pass then returns {'skipped': 'l2_reasoning_not_activated'} or 'no_model_configured' (l2/sweep.py:177-181) without logging. The moved files were never covered (they were appended to due, not _cover'ed), so they fall to the formula lanes. The reverse failure is also unenforced: with l2_cards and l2_reasoning on but expert_review off, the expert pass skips, so standing reviews are not covered and moved files are not handed over. Only bundle-touched files are judged.)

<a id="l2-daily-cap-formula-first"></a>
### The shared 7-per-day signal cap is spent by formula situations before the expert/L2 file decisions get a turn

`l2-daily-cap-formula-first` · **P1** · broken · owner **claude** · code · step **S18**

- **Expected:** The expert's judgment decides what matters; a busy day shows the nearest deadlines first. _(source: genios_engine/reason/expert/sweep.py:17-21 docstring (06 D1, D7); speedrun008/GeniOS-008/00-ARCHITECTURE.md L2 primary)_
- **Actual:** One cap covers every lane: _daily_allowance = pack budget_per_day (default 7) × active seats − every signal row of the org created today (domain_shadow.py:165-186; reason/runner.py:551-555). Inside shadow_compile, the situation loop spends it first (domain_shadow.py:1913-1944). Covered expert/L2 files are decided after the loop (domain_shadow.py:2016-2021). A spent cap drops the file's decision as `budget_exhausted` (domain_shadow.py:813-816), which appears only in the log line. Signals from earlier sweeps of the same day, from any lane, are already subtracted.
- **Evidence (measured):** `genios_engine/reason/domain_shadow.py:165-186`; `genios_engine/reason/runner.py:551-555`; `genios_engine/reason/domain_shadow.py:1913-1944`; `genios_engine/reason/domain_shadow.py:2016-2021`; `genios_engine/reason/domain_shadow.py:806-816`
- **What Rohit sees:** Fewer expert cards on busy days, while formula cards take their slots.
- **Fix:** Decide covered files before the situation loop, or give file decisions their own allowance. Count budget_exhausted on the funnel. Add a test where 7 formula situations are emitted, then 1 expert file, and the expert card must exist.
- **Blocked on:** select created_at::date d, rule_id, count(*) from signals where org_id='<ORG>' and created_at>='2026-10-18' group by 1,2 order by 1,3 desc;
- **Verified:** confirmed by the skeptic (_daily_allowance is budget_per_day (default 7) × _active_seats − _budget_used (domain_shadow.py:165-186). _budget_used counts every signals row of the org with created_at::date = today, whatever its lane or status (runner.py:551-555). The situation loop spends the cap first (domain_shadow.py:1912-1944), and covered files are decided after it (:2016-2021). For a file, budget_exhausted applies only to a shown move: a NO_MOVE outcome, a question, a renewal or a small move is exempt (:813). Its trace is a change-gate row with outcome 'indeterminate' (:815), so it is retried next sweep, and the reason itself appears only in the log line at :2054.)

<a id="l2-f15-five-held-cards"></a>
### F15 (five funds, eight weeks silent): today's path makes 0 cards, the L2 path splits it into 5 held question cards; expected 1

`l2-f15-five-held-cards` · **P1** · broken · owner **claude** · code · step **S21**

- **Expected:** Exactly one card for the investor wave: who to follow up, with what, who to close. _(source: tests/replays/specs/founder F15 via speedrun008/GeniOS-009/01-AS-IS-CARDS.md A2; STEP-G0-the-ground.md G0.2.a)_
- **Actual:** Measured on the ideal reader (no model quality involved): L2 path 5 investigation cards, each 'What is the next step with <fund>? We held the one we found: a fact your move rests on quotes nothing from the mail it cites.' Today's path makes 0. Causes: the subject is one file per counterparty and there is no wave subject (reason/l2/inputs.py:208-218; reason/l2/sweep.py:210-219). The decisive fact cites the founder's own sent mail with no counterparty quote, so it is dropped as UNQUOTED and the move is held (reason/expert/verify.py:1009-1013, 1236-1238). F15 is blocked_on 03 F169 / 06 D57: silence is never re-checked.
- **Evidence (measured):** `speedrun008/GeniOS-009/measurements/golden-cards-2026-10-22.json F15 (today 0 cards; l2 5 cards)`; `genios_engine/reason/l2/inputs.py:208-218`; `genios_engine/reason/expert/verify.py:1004-1021, 1232-1238`; `speedrun008/GeniOS-009/STEP-G0-the-ground.md:60-73`
- **What Rohit sees:** Fundraising outreach shows up as N identical engineer-worded question cards, or as nothing.
- **Fix:** G0.2.a: a wave subject (files of one kind with the same unanswered ask) judged once. A fact about our own sent mail or a silence should ground on our own mail's words or a tool line, not need a counterparty quote. Fix the held wording (l2-held-card-engineer-template). Keep F15 strict-xfail until then and never edit its expectation.
- **Depends on:** [l2-held-card-engineer-template](#l2-held-card-engineer-template)
- **Verified:** confirmed by the skeptic (In golden-cards-2026-10-22.json, F15 shows today: 0 cards, and l2: 5 card rows, all lane 'investigation' with the held template, one naming 'latticecap.test'. The file's own verdict string says '4 cards about …', apparently because the domain-named card does not match the fund names. The card dump has 5. L2 subjects are per file or seed (l2/inputs.py:197-218), with no wave subject, although context/correlation_conversation.find_waves exists and the expert dossier cites wave:… ids. The UNQUOTED drop rule is at verify.py:1008-1021, and its use in the held question is at :1236-1239. The 'founder's own sent mail' cause was not traced through the L2 ideal reader (tests/replays/ideal_reader.py:179-190 reuses the case's expert answer). The fix is planned in STEP-G0 G0.2.a.)

<a id="l2-fallback-to-formula-lanes"></a>
### When a judgment fails or is held, the file falls back to the formula/pack lanes; refused and truncated answers are never retried

`l2-fallback-to-formula-lanes` · **P1** · partial · owner **claude** · code · step **S19**

- **Expected:** No formula decides meaning. A failure gives a partial result plus EvidenceNeeds, 'never a forced conclusion'. Malformed output gets one bounded repair, then a failure status. _(source: speedrun008/GeniOS-008/layer-2-reasoning/02-PLAN.md §0, §5 failure table, §8; memory llm-as-the-expert-not-the-formula)_
- **Actual:** A file is covered only by a VALID review. A file whose review was refused (nothing stands), truncated, failed, over budget, carried past MAX_PER_PASS=10, or (under l2_cards) whose admission came back HOLD 'is decided as before, situation by situation'. That means the compiled formula lane and the per-pack rules decide it (reason/expert/sweep.py:39-50 docstring, :262-264, :296-309; reason/l2/sweep.py:378-384; reason/runner.py:1958-1959). REFUSED and TRUNCATED are STANDING statuses, so the same fingerprint is never asked again until the file moves (reason/expert/store.py:62; reason/l2/store.py:57). R-9's 8,000-token ceiling is modelled, not measured (reason/bundle/sites.py:142-146; 04-FOR-HARSH G-1 'If a row is truncated, tell me').
- **Evidence (measured):** `genios_engine/reason/expert/sweep.py:39-50, 262-264, 296-309`; `genios_engine/reason/l2/sweep.py:378-384`; `genios_engine/reason/expert/store.py:58-62`; `genios_engine/reason/l2/store.py:57`; `genios_engine/reason/runner.py:1925-1960`; `genios_engine/reason/bundle/sites.py:142-146`
- **What Rohit sees:** Weird cards. The same counterparty can get a formula/pack card (Admin-rule wording) in place of, or next to, the expert's file card.
- **Where the mistake was:** STEP-12 D1 kept the old lanes as the fallback for any file without a valid review. That was safe for a shadow pilot, but it contradicts the L2-primary architecture.
- **Fix:** Keep a file covered by its last valid review (shown 'as of <date>') when the new one fails, instead of handing it to the formula lanes. Retry a truncated answer once at a larger ceiling. Give a refused answer one repair with the verdicts. Count 'fell back' per sweep.
- **Blocked on:** select status, left(reason,120) r, count(*) from expert_reviews where org_id='<ORG>' and reviewed_at>='2026-10-18' and status<>'valid' group by 1,2 order by 3 desc; select status, count(*) from reasoning_results where org_id='<ORG>' group by 1;
- **Depends on:** [l2-held-card-engineer-template](#l2-held-card-engineer-template)
- **Verified:** confirmed by the skeptic (The expert sweep docstring (sweep.py:41-52) says that refused, cut, failed-waiting, carried and unreadable files are 'decided as before, situation by situation'. Code: _waiting at :124-133, OVER_BUDGET break at :304-306, and the cap of 10 at :92 and :289-291. In the L2 sweep, only an admitted or rejected result with checked becomes a review (reason/l2/sweep.py:378-384); a HOLD, or a result that never ended, writes nothing. STANDING = (VALID, REFUSED, TRUNCATED) at expert/store.py:62, and (RESULT, REFUSED, TRUNCATED) at l2/store.py:57. The 8,000-token ceiling is labelled [MODELLED] at bundle/sites.py:142-146. Uncovered files fall to shadow_compile and the pack loop (runner.py:1925-1960).)

<a id="l2-h1-h3-formula-lanes-still-decide"></a>
### H1–H3 not done: 23 formula reasoners, the LLM decider and the per-pack rule lane still decide

`l2-h1-h3-formula-lanes-still-decide` · **P1** · missing · owner **claude+harsh** · mixed · step **S25**

- **Expected:** H1: formula reasoners become tools whose scores decide nothing. H2: retire llm_decision_maker. H3: retire the per-pack rule lane at cutover, per situation type. _(source: speedrun008/GeniOS-008/layer-2-reasoning/02-PLAN.md §7 Group H; 06-GAP-ANALYSIS.md §4)_
- **Actual:** reason/reasoners/ (25 files, 8,038 LOC) still drives the compiled lane. DecisionMaker.decide still hands every non-terminal decision to llm_decision_maker when GENIOS_L4_LLM_DECISION_MAKER is on (decision_maker.py:1120-1126; config.py:110-111), and any failure DEFERs (llm_decision_maker.py:20-22). The legacy run() runs for every tenant pack on every sweep (runner.py:1958-1959).
- **Evidence (measured):** `wc -l genios_engine/reason/reasoners/*.py → 8038 total`; `genios_engine/reason/decision_maker.py:1120-1126`; `genios_engine/reason/llm_decision_maker.py:1-25, 120-130`; `genios_engine/reason/runner.py:1958-1959`
- **What Rohit sees:** The formula and pack cards that read as 'weird' keep coming, and with the LLM decider on, a model failure or spent budget DEFERs them.
- **Fix:** After I2 succeeds for a type, stop the compiled/pack lanes for that type. Move date and number logic behind reason/l2/tools. Remove the LLM decider once no type depends on it.
- **Blocked on:** Harsh: the production value of GENIOS_L4_LLM_DECISION_MAKER and GENIOS_L4_LLM_DECISION_MAKER_ORGS (env, not SQL).
- **Depends on:** [l2-i2-first-switch-not-made](#l2-i2-first-switch-not-made)
- **Verified:** confirmed by the skeptic (reason/reasoners/ holds 25 .py files and 8,038 LOC (wc), which is 23 reasoner modules plus __init__ and common. DecisionMaker.decide hands off to llm_dm when enabled_for(org) (decision_maker.py:1120-1126; llm_decision_maker.py:118-129). Failure → DEFER is documented at llm_decision_maker.py:20-22. The pack loop is at runner.py:1958-1959. The plan rows L2-H1/H2/H3 are at layer-2-reasoning/02-PLAN.md:279-281. Whether GENIOS_L4_LLM_DECISION_MAKER is set in production is an environment fact that only Harsh or Rohit can confirm.)

<a id="l2-held-card-engineer-template"></a>
### Held cards read as engineer sentences: a fixed template replaces the model's advice, and nothing repairs before holding

`l2-held-card-engineer-template` · **P1** · broken · owner **claude** · code · step **S20**

- **Expected:** The card speaks in the founder's words, shows the move, and asks one clear question only when it must. The held wording is rewritten in the reader's words (GeniOS-009 G0.2.b). _(source: speedrun008/GeniOS-009/STEP-G0-the-ground.md G0.2.b; 01-AS-IS-CARDS.md A2; memory dashboard-visual-style ('one clear line'))_
- **Actual:** The template is reason/expert/verify.py:787-793 `_held_question`: "What is the next step with {counterparty name or key}? We held the one we found: {why}." The `why` comes from the closed phrases in contracts/claim_check.py:131-153 HELD_BECAUSE, e.g. UNQUOTED (:134) "a fact your move rests on quotes nothing from the mail it cites", plus the four JUDGMENT_HOLDS phrases added 21 Oct (:78-82, :149-152). The card's second line is reason/expert/asks.py:69-79 WHY_*, e.g. "we could not confirm what it rests on from what it cites". question_words takes checked.question for a held file (asks.py:181-189). The model's move is deliberately withheld (verify.py:787-792 'NEVER THE WORDS THAT FAILED'; the headline is set only when shown, verify.py:1310-1316). The counterparty falls back to a bare domain ('latticecap.test'). Nothing repairs first: R-7 repairs syntax only (reason/expert/review.py:171), and R-9 repairs other failures only at deep depth (reason/l2/judge.py:115-119). A held fate never raises, only REFUSED does (judge.py:105-108), so a citation slip becomes a question to Rohit and the model never gets a second try.
- **Evidence (measured):** `genios_engine/reason/expert/verify.py:787-793`; `genios_engine/contracts/claim_check.py:126-153`; `genios_engine/reason/expert/asks.py:69-79, 144-189`; `genios_engine/reason/expert/verify.py:1232-1241, 1288-1293, 1310-1321`; `genios_engine/reason/expert/review.py:167-171`; `genios_engine/reason/l2/judge.py:99-119`; `speedrun008/GeniOS-009/measurements/golden-cards-2026-10-22.json F15.l2.cards (5 headlines with this template)`
- **What Rohit sees:** Weird wording: question cards whose headline is an internal check result, with no advice on them.
- **Where the mistake was:** STEP-13 X10 chose closed phrases so that failed words never reach a card (right), but the phrases were written about the check, not for the founder. The L2 rebuild reused them unchanged.
- **Fix:** (1) Rewrite HELD_BECAUSE, _held_question and asks.WHY_* in the founder's voice, leading with the move to confirm (e.g. 'Follow up with Cobalt Peak? I couldn't find the line in their mail this rests on — confirm and I'll keep it'). Never print a bare domain as a name. (2) Before holding, make one repair call that carries the check's verdicts, at every depth and on both R-7 and R-9 (STEP-13b's repair). (3) Test with a golden headline assertion on F15 and a mutation on the template.
- **Blocked on:** Share of held cards in production: select checked->>'fate' fate, checked->>'because' because, count(*) from expert_reviews where org_id='<ORG>' and reviewed_at>='2026-10-18' and status='valid' group by 1,2 order by 3 desc;
- **Depends on:** [l2-step13b-check-fixes-unmerged](#l2-step13b-check-fixes-unmerged)
- **Verified:** confirmed by the skeptic (_held_question is at verify.py:787-793 and is used at :1239, :1242 and :1290. HELD_BECAUSE is at claim_check.py:131-153 (UNQUOTED :134, MOVE_DATE_PASSED :152), and the JUDGMENT_HOLDS reasons are at :78-82. WHY_* are at asks.py:69-79, and question_words takes checked.question for a held file at asks.py:183-189. The headline and draft are blanked unless shown (verify.py:1309-1316). R-7 runs with repair=REPAIR_SYNTAX (review.py:171), and gate.py:380-382 breaks on any refusal that is not MALFORMED. R-9 uses REPAIR_ANY only at deep depth (judge.py:115-119). Only a REFUSED fate raises SiteRejection (judge.py:105-108), so a held fate is never retried at any depth. The golden dump (measurements/golden-cards-2026-10-22.json, F15.l2.cards) shows 5 headlines in this template, one naming 'latticecap.test'.)

<a id="l2-i2-first-switch-not-made"></a>
### I2 not made: l2_cards is a whole-tenant switch, compared only offline on the ideal reader

`l2-i2-first-switch-not-made` · **P1** · unknown until production is read · owner **rohit+harsh** · mixed · step **S25**

- **Expected:** First switch per situation type (awaiting reply/outreach), after I1 shows the new path is at least as good. GeniOS-009 D5/D6: l2_cards on Rohit's org after G0.1, then one week side by side. _(source: speedrun008/GeniOS-008/layer-2-reasoning/02-PLAN.md §7 L2-I2; 00-START-HERE.md L2-Q4; GeniOS-009/08-DECISIONS.md D5, D6; STEP-G0 G0.2.c-d)_
- **Actual:** l2_cards is per tenant with no situation-type gate anywhere in reason/l2 (l4_activation.py:117-127; grep shows no type gate). The comparison so far is offline on the ideal reader: 63/4 on both paths, 57 vs 62 cards (GeniOS-009/01-AS-IS-CARDS §1). The G0.2 side-by-side week has not run, and production's switch state is unknown.
- **Evidence (mixed):** `genios_engine/platform/l4_activation.py:117-127`; `speedrun008/GeniOS-009/01-AS-IS-CARDS.md §1`; `speedrun008/GeniOS-009/STEP-G0-the-ground.md G0.2`
- **What Rohit sees:** While it is off, every card is the old path's. If it was switched on whole-tenant, the held and dropped-judgment issues above apply to all of Rohit's files.
- **Where the mistake was:** The plan's per-type cutover became a whole-tenant switch in L2 rebuild C1 without a recorded decision.
- **Fix:** Rohit decides whether the cutover is whole-tenant (as built) or per type (as planned). Then Harsh switches l2_cards for Rohit's org, and one week of l2_shadow_report.py plus the funnel is compared, with no card lost.
- **Blocked on:** select org_id, feature, enabled_at, disabled_at from l4_activation where feature in ('l2_reasoning','l2_cards','expert_review'); select status, lane, count(*), sum(cost_micro_usd)/1e6 usd from reasoning_results where org_id='<ORG>' group by 1,2;
- **Depends on:** [l2-step13b-check-fixes-unmerged](#l2-step13b-check-fixes-unmerged), [l2-cards-precondition-not-enforced](#l2-cards-precondition-not-enforced)
- **Verified:** confirmed by the skeptic (l2_cards is a per-tenant row (l4_activation.py:117-121). reason/l2 has no situation-type gate: grep for situation_type finds only history.py:28 and :66, which are display. The offline result is 63/4 on both paths, 57 vs 62 cards (01-AS-IS-CARDS.md:22-23). GeniOS-009/03-LOG.md has no G0.2 row. D5/D6 are at 08-DECISIONS.md:14-15, and the plan rows L2-I1/I2 are at 02-PLAN.md:282-283. Production switch state needs Rohit's permission for a read: select org_id, feature, enabled_at, disabled_at from l4_activation where feature in ('expert_review','l2_reasoning','l2_cards') order by org_id, feature;)

<a id="l2-judgment-half-dropped-confidence-cui"></a>
### Under l2_cards the judgment half (six-dimension confidence, options, decision need, history) is dropped; the card still shows formula {C,U,I} (L2-9)

`l2-judgment-half-dropped-confidence-cui` · **P1** · partial · owner **claude** · code · step **S22**

- **Expected:** A lane plus a six-dimension confidence vector (evidence · frame · temporal · causal · authority · coverage), each a level with its reason, and no single scalar floor. The card shows options, decision need and authority. _(source: speedrun008/GeniOS-008/00-ARCHITECTURE.md 'Cards — five lanes, a confidence vector'; 02-MIGRATION-PLAN.md:140 L2-9; GeniOS-009 STEP-G6 §5)_
- **Actual:** L2Judgment carries the six dimensions, options, decision_need, history_used and second_order (contracts/reasoning_result.py:73-75, 227-238). When an L2 result becomes the file's review, only result.review and result.checked are written (reason/l2/sweep.py:121-139). write_review has no judgment field (reason/expert/store.py:194-199). decide and the card never see the judgment half; it lives only in reasoning_results. The card's confidence_vector comes from the formula's C/U/I/R SQL (deliver/card_builder.py:1369-1370; reason/authority.py:105-115). The expert decision's confidence is code counting cited events, with a 6,000 bp scalar floor and 4,000 bp below it (reason/expert/decide.py:41-49, 170-172). Golden: 49/57 cards carry {C,I,U} (01-AS-IS-CARDS §2). The key names also differ: code uses 'framing' (reasoning_result.py:73) where Atlas and G6 say 'frame'.
- **Evidence (measured):** `genios_engine/contracts/reasoning_result.py:73-75, 227-238`; `genios_engine/reason/l2/sweep.py:121-139`; `genios_engine/reason/expert/store.py:194-199`; `genios_engine/deliver/card_builder.py:1366-1370`; `genios_engine/reason/authority.py:105-115`; `genios_engine/reason/expert/decide.py:41-49, 170-172`; `speedrun008/GeniOS-009/01-AS-IS-CARDS.md §2`
- **What Rohit sees:** Confidence on the card is an opaque formula number. The L2 reasoning Rohit was promised (options, who decides, history) never appears.
- **Where the mistake was:** L2 rebuild C1 (de795bb8) reused the expert review row as the hand-off and wrote only the review half.
- **Fix:** Carry the judgment half to the card: store it with the review row, or join reasoning_results by fingerprint in decide. Render the six named levels with reasons, options and decision need. Drop the scalar floor for L2 cards (the lane already encodes it). Align the key 'framing' vs 'frame'.
- **Verified:** confirmed with a correction by the skeptic: Substance holds: under l2_cards the review row has no judgment field (expert/store.py:194-199), and _file_review copies only result.review and result.checked (l2/sweep.py:121-139). The card shows the formula C/U/I (card_builder.py:1369-1370; authority.py:105-115), and the expert confidence is the event-count floor (decide.py:41-49, 168-172). Two details are wrong. (1) 'decide and the card never see the judgment half' is false since 9794dfec (21 Oct): lane_for (computed from evidence and framing confidence, open_conflict) and decision_need/by_when reach the card through judgment_hold. That turns the move into a held question (judge.py:102-104; reasoning_result.py:447-480; verify.py:1287-1293). (2) 'it lives only in reasoning_results' is false: since f3cfd3c6 (20 Oct) an admitted judgment's frame, intervention_mode and decision object are appended to situation_interpretations (context/l2_admission.py:141-201). Nothing reads that table. The six dimensions, options and history_used still reach no card.

<a id="l2-judgment-holds-overdue-and-unknown"></a>
### Since 21 Oct an overdue move, an 'unknown' confidence or an unnamed decider turns the move into a held question

`l2-judgment-holds-overdue-and-unknown` · **P1** · broken · owner **claude** · code · step **S20**

- **Expected:** Uncertainty routes a finding to a lane; it never deletes it. review_required means a person looks first, not that the advice is withheld. _(source: speedrun008/GeniOS-008/00-ARCHITECTURE.md 'Cards'; layer-2-reasoning/02-PLAN.md §5)_
- **Actual:** judgment_hold (contracts/reasoning_result.py:462-480, added in 9794dfec on 21 Oct, on the production head) holds an act's move as one question in four cases: the move's by_when is before the run (MOVE_IN_THE_PAST, :396-398); a decision is needed and nobody is named (:392-393); evidence or framing confidence is low or 'unknown' (lane_for → monitor, :447-459); or a conflict is open. The prompt itself says 'Unknown is an answer when it is said why' (reason/l2/prompt.py:57-59). verify.py:1288-1293 then produces 'What is the next step with X? We held the one we found: the date the move was for has already passed.'
- **Evidence (measured):** `genios_engine/contracts/reasoning_result.py:390-398, 447-480`; `genios_engine/reason/expert/verify.py:1288-1293`; `genios_engine/contracts/claim_check.py:78-82, 149-152`; `genios_engine/reason/l2/prompt.py:57-59`; `git 9794dfec (Harsh, 2026-10-21)`
- **What Rohit sees:** The most urgent (overdue) moves arrive as questions, not actions.
- **Fix:** Show an overdue move as overdue, re-dated to today. Show weak ground as a monitor card that keeps the move as a 'watch'. For a solo-founder tenant, default the decider to 'you'. Hold only an open conflict.
- **Blocked on:** select checked->>'because', count(*) from expert_reviews where org_id='<ORG>' and prompt_version like 'l2-%' and checked->>'fate'='held' group by 1;
- **Verified:** confirmed by the skeptic (9794dfec (Harsh, 2026-10-21) is in HEAD. In validate_judgment: DECISION_WITHOUT_OWNER at reasoning_result.py:392-393 and MOVE_IN_THE_PAST at :395-397. lane_for maps low or unknown evidence/framing to LANE_MONITOR (:447-459), and judgment_hold maps conflict, no decider, past date and monitor to the hold reasons (:462-480). verify.py:1287-1293 holds only an act move that would otherwise be shown, and the headline is blanked unless shown (:1313). The prompt says 'Unknown is an answer when it is said why' (l2/prompt.py:57-59). In effect this only reaches cards under l2_cards; in shadow the held fate is stored in reasoning_results.)

<a id="l2-kind-proposals-lost-under-l2-cards"></a>
### Under l2_cards no 'kind of work' proposal is ever written, so unlisted files never gain a playbook

`l2-kind-proposals-lost-under-l2-cards` · **P1** · broken · owner **claude** · code · step **S19**

- **Expected:** A valid review that proposes a kind of work writes the founder a proposal (kind_proposal.propose_kind). _(source: genios_engine/reason/expert/sweep.py:22-23 docstring)_
- **Actual:** propose_kind runs only after an R-7 call (reason/expert/sweep.py:310-321). With l2_cards the expert pass returns earlier (sweep.py:277-286), and reason/l2 never calls propose_kind (grep: 0 hits). The ExpertReview half of the L2 answer may carry proposed_kind, but it is dropped.
- **Evidence (measured):** `genios_engine/reason/expert/sweep.py:277-286, 310-321`; `grep propose_kind genios_engine/reason/l2/ → none`
- **What Rohit sees:** Files stay without a work kind, so no playbook, no history and weaker cards. This only matters once l2_cards is on.
- **Where the mistake was:** L2 rebuild C1 moved the review call to R-9 without moving the side effects that followed the R-7 call.
- **Fix:** In reason/l2/sweep.py, when a file review is written, call propose_kind if result.review.proposed_kind stands the check. Test that a file with a proposed kind gets a brief proposal under l2_cards.
- **Verified:** confirmed by the skeptic (propose_kind's only caller is reason/expert/sweep.py:310-321, after an R-7 call. Under l2_cards the pass returns at :270-277 before that point. A grep for propose_kind or kind_proposal across genios_engine/reason/l2 returns 0 hits. A proposed_kind carried in the L2 review half is written into expert_reviews.review, but nothing proposes it.)

<a id="l2-path-drops-kind-proposals"></a>
### On the L2 card path, the model is asked for proposed_kind but nothing writes it, so kind proposals stop when l2_cards is on

`l2-path-drops-kind-proposals` · **P1** · broken · owner **claude** · code · step **S19**

- **Expected:** With l2_cards on, an admitted L2 judgment 'decides it exactly as an expert review does' (platform/l4_activation.py:118-121), including the founder-facing kind proposal that the R-7 path writes. _(source: genios_engine/platform/l4_activation.py:118-121; STEP-12/16 kind proposal (reason/expert/kind_proposal.py docstring))_
- **Actual:** The L2 prompt schema is expert.SCHEMA merged with L2_SCHEMA (reason/l2/prompt.py:126), so it asks for proposed_kind (reason/expert/prompt.py:203). reason/l2/sweep.py never calls propose_kind; only reason/expert/sweep.py:310-316 does. With l2_cards on, the R-7 call is not made (l4_activation.py:118-121), so the expert's kind proposals and corrections (F53, F132, F157) silently stop. No test under tests/reason/l2 covers it.
- **Evidence (measured):** `genios_engine/reason/l2/prompt.py:126`; `genios_engine/reason/expert/prompt.py:203`; `grep -n propose_kind genios_engine/reason/l2/sweep.py → 0 hits`; `genios_engine/reason/expert/sweep.py:310-316`; `genios_engine/platform/l4_activation.py:118-121`
- **What Rohit sees:** After G0.2 switches l2_cards on, a fund misfiled as sales or a programme behaving like its fund is never offered for correction, so its cards read the wrong playbook.
- **Where the mistake was:** L2 rebuild C1 (de795bb8) reused the review row and the card path but not the proposal side effect of the expert pass.
- **Fix:** In reason/l2/sweep.py, for each admitted file result with result.review.proposed_kind and checked.stands('kind'), call kind_proposal.propose_kind inside the write step. Add a PG test on the L2 path plus a mutation proof. The goal proposer must be wired the same way.
- **Verified:** confirmed by the skeptic (reason/l2/prompt.py:126 merges expert.SCHEMA, which includes proposed_kind (reason/expert/prompt.py:203). The parsed ExpertReview carries it, and reason/expert/verify.py:1140 checks it. But reason/l2/sweep.py (_file_review :120-138, _write_file_review :141-157) never calls propose_kind; grep finds it only in reason/expert. With l2_cards on, the expert sweep sets l2_judges (reason/expert/sweep.py:171) and returns at :277-285, before any R-7 call or propose_kind. No test under tests/reason/l2 references proposed_kind or propose_kind.)

<a id="l2-plane-d-thin"></a>
### Domain expertise (Plane D) barely reaches the judgment: one Founder Office playbook, only when the brief names the file's kind

`l2-plane-d-thin` · **P1** · partial · owner **claude** · code · step **S22**

- **Expected:** R4: one version-pinned ExpertisePackage (domain knowledge, patterns and counter-patterns, cases, evidence standards, brief, brains, playbooks) with one hash in the receipt. _(source: speedrun008/GeniOS-008/layer-2-reasoning/02-PLAN.md §1 R4, §7 L2-B3; 00-ARCHITECTURE.md 'Plane D')_
- **Actual:** reason/l2 imports nothing from packs/ (grep). A file's expertise is the STEP-12 dossier's playbook section (reason/expert/dossier.py:495-546, 772-784), chosen by work_kind. A file has a work_kind only if an accepted brief in_motion line names its address or domain (context/workstreams.py:19-25, 298-310). 'partner' maps to no capability (packs/compiler/playbook_reader.py:48-55). Seeds get only the brief (reason/l2/dossier.py:169-172). Comparable history is empty without a kind (reason/l2/history.py comparable()). expertise_ref is a hash of the dossier digest, brief and prompt, not of a package (reason/l2/sweep.py:342-343). The default-on Admin corpus reaches only the formula lane.
- **Evidence (measured):** `genios_engine/reason/l2/sweep.py:338-343`; `genios_engine/reason/expert/dossier.py:495-546, 772-784`; `genios_engine/context/workstreams.py:19-25, 298-310`; `genios_engine/packs/compiler/playbook_reader.py:48-55, 206-226`; `genios_engine/reason/l2/history.py (comparable: no kind → no cases)`
- **What Rohit sees:** Generic advice on any work the founder did not list in the brief, with no expert prior or history to draw on.
- **Fix:** Fold the compiled ExpertisePackage of the subject's routed capability (patterns, counter-patterns, evidence standards, heuristics) into block D with its hash. Let the judgment infer a kind when the brief names none, and propose it (see l2-kind-proposals-lost).
- **Depends on:** [l2-kind-proposals-lost-under-l2-cards](#l2-kind-proposals-lost-under-l2-cards)
- **Verified:** confirmed with a correction by the skeptic: Substance holds: reason/l2 imports nothing from packs/ (grep returns 0). The expertise is the expert dossier's playbook section, chosen by work_kind (expert/dossier.py:495-546, 772-784). work_kind comes only from an in_motion brief line (context/workstreams.py:298-310). Seeds get the brief only (l2/dossier.py:167-172), comparable() returns nothing without a kind (l2/history.py:43-47), and expertise_ref hashes the dossier digest + brief + prompt (l2/sweep.py:339-340). Two details are wrong. It is not 'one Founder Office playbook': KIND_CAPABILITY maps 6 of the 7 kinds, 5 to Founder Office capabilities and 'vendor' to admin.contract_and_vendor.renewal_management (packs/compiler/playbook_reader.py:48-56), with only 'partner' → None. So 'the default-on Admin corpus reaches only the formula lane' is also wrong: Admin's renewal_management playbook reaches the dossier of every vendor-kind file.

<a id="l2-seed-subject-no-card"></a>
### A subject with no file (a first mail, a new admission) is judged but can never become a card

`l2-seed-subject-no-card` · **P1** · missing · owner **claude** · code · step **S21**

- **Expected:** The subject is the file when one exists, else the seed thread/entity (L2-Q6). L2 forms the situation and L3 admits it. _(source: speedrun008/GeniOS-008/layer-2-reasoning/00-START-HERE.md L2-Q6; 06-GAP-ANALYSIS.md §4; 00-ARCHITECTURE.md 'The flow')_
- **Actual:** Seed subjects are read and judged with the brief as block D (reason/l2/sweep.py:210-219, 338-341; reason/l2/dossier.py:169-172). Only file subjects are written as a review that can make a card (reason/l2/sweep.py:381: `parts is not None`). A seed's `create` proposal is HOLD at subject level, 'no situation seed for this subject yet — no join has filed it' (context/l2_admission.py:97-102). There is no applier and no EvidenceNeed.
- **Evidence (measured):** `genios_engine/reason/l2/sweep.py:210-219, 338-341, 381`; `genios_engine/reason/l2/dossier.py:167-172`; `genios_engine/context/l2_admission.py:97-102`
- **What Rohit sees:** Fewer cards. New work that no file or situation yet holds (e.g. the Antler Singapore admission thread) cannot get an L2 card.
- **Fix:** Build an L3 applier for an admitted `create` on a seed (GeniOS-009 G0.3, one type first), and a card path for a seed's result (subject = the thread's counterparty node).
- **Depends on:** [l2-admission-g2-shadow](#l2-admission-g2-shadow)
- **Verified:** confirmed by the skeptic (A seed subject gets brief_block in place of a file dossier (l2/sweep.py:335-338; l2/dossier.py:167-172, which says 'No file holds this subject … judge from the brief'). A review is written only if parts is not None (l2/sweep.py:381). A seed create becomes HOLD with NO_SITUATION and the reason 'no situation seed for this subject yet — no join has filed it' (context/l2_admission.py:97-102). Nothing reads that HOLD. needs_from may still file the result's own evidence needs (l2/sweep.py:364-366), but no need is raised for the hold itself.)

<a id="l2-skips-invisible"></a>
### Nearly every skip, refusal, budget cap or shadow decision is invisible to Rohit and shows only in a server log line

`l2-skips-invisible` · **P1** · missing · owner **claude** · code · step **S18**

- **Expected:** 'A SKIP IS A ROW', and a refusal nobody can see is a silent stop. Each pass's receipt is readable by an operator, and Rohit can tell why a file has no card. _(source: migrations/0120_l4_reasoning_bundles.sql:107-111; memory a-fail-closed-after-the-claim-loses-the-week; 04-FOR-HARSH G-1 'You should see')_
- **Actual:** Skip points and where each one shows: (1) Expert not activated or no model: returns {'skipped':…} (reason/expert/sweep.py:163-176). run_all only returns it (runner.py:2011-2012) and _run_l2_chain never logs it (api/routes.py:822-823). (2) Expert cap of 10 a pass and $2/day at $0.10/call (sweep.py:92, 296-309; reason/bundle/budget.py:63-64), failed-waits-6h and over-budget-waits-a-day (sweep.py:96, 140-149). These are logged only when something was reviewed or carried (sweep.py:324-325). (3) Refused and truncated reviews stand (store.py:62). (4) L2 not activated or no model (reason/l2/sweep.py:177-181) is never logged. The L2 cap of 10 at $2/day and $0.15/call (sweep.py:62, 296-300; budget.py:68-71) is logged only when rows or carried exist (sweep.py:443-444). (5) Covered-file outcomes covered_without_situation, expert_no_tenant_pack, expert_shadow, budget_exhausted and expert_small_move (domain_shadow.py:744, 755, 797, 815, 824) appear in one 'domain-compiler' log line (domain_shadow.py:2054). (6) R-site ledger rows exist for every consult outcome (l4_r_site_calls; sites.py:181-207). Operator surfaces: scripts/pipeline_health.py reads expert_reviews (:925-975) but not reasoning_results or R-9; scripts/l2_shadow_report.py; the funnel has five stages and none for judged/held/refused/fell-back (platform/funnel.py:60-61). No API route reads expert_reviews, reasoning_results or l4_r_site_calls except the erasure lists (api/account_routes.py:662, 683, 940). Rohit sees only the held question card.
- **Evidence (measured):** `genios_engine/reason/expert/sweep.py:163-176, 296-309, 324-325`; `genios_engine/reason/l2/sweep.py:177-181, 296-300, 443-444`; `genios_engine/reason/domain_shadow.py:744, 755, 797, 815, 824, 2054`; `genios_engine/api/routes.py:822-823`; `genios_engine/platform/funnel.py:60-61`; `scripts/pipeline_health.py:925-975`; `genios_engine/api/account_routes.py:662, 683, 940`
- **What Rohit sees:** Silent stops: when cards drop, neither Rohit nor an operator can see which gate dropped them without reading server logs.
- **Where the mistake was:** Each unit added its own counter to its own receipt, and none was relayed to the funnel or to a surface.
- **Fix:** Add funnel counts written by run_all: judged, held, refused, truncated, carried_budget, fell_back, covered_not_carded, budget_exhausted. Always log the expert/L2 'skipped' reason. Add R-9/reasoning_results to pipeline_health. Add one admin route plus a 'why no card' line on the file page.
- **Verified:** confirmed with a correction by the skeptic: Substance holds: the skips, caps, refusals and shadow outcomes are not visible to Rohit on any surface he uses. One detail is wrong: an API route does read expert_reviews. GET /v1/workstreams/{file_id} returns the file's latest STANDING review (valid, refused or truncated, with its reason, model, cost, check fate, question and verdicts) and its latest valid review (api/workstream_routes.py:153-167, reading reason/expert/store). The dashboard does not call it: git grep for 'workstream' at dashboard origin/main 2edfb86 returns 0 hits. reasoning_results, l2_admissions and l4_r_site_calls are still read by no route except the erasure lists (account_routes.py:662, 683, 940, 942).

<a id="l2-step13b-check-fixes-unmerged"></a>
### STEP-13b claim-check fixes (79% → 18.5% held on Haiku) never reached production; the production model has no completed live golden pass

`l2-step13b-check-fixes-unmerged` · **P1** · built, not live · owner **claude+harsh** · mixed · step **S20**

- **Expected:** The check holds what is wrong, not formatting slips (model-agnostic goal, YC-II W27 06 D64). A live golden pass runs on the production model before the expert reaches Rohit's account (06 D50). _(source: speedrun008/YC-II W27/06-DECISIONS.md D50, D64, D72; memory haiku-live-pass-held-79-percent)_
- **Actual:** Production runs check.v4 (contracts/claim_check.py:38). STEP-13b sits on branches yc2w27-int13b / yc2w27-s13b (117f90c6 'STEP-13b built', 73d9f804 live passes). It includes: a line cited by its words is read as that line; ordinary words are not invented names; repair once with the verdicts; the model ladder; check.v5. Neither commit is an ancestor of HEAD 0cc8d83c or of origin/speedrun008 (git merge-base --is-ancestor). Measured on that branch on 17 Oct (73d9f804 message): Haiku held share 18.5% (79% before), recall 0.509 (0.235), but still 3 forbidden outputs and only 10 of 14 must-abstain cases right. Production R-7 and R-9 both run claude-sonnet-5 (reason/llm_sites.py:290-295). The 12 Oct Sonnet pass was void (203/203 truncated, memory claude5-thinks-by-default), R-9 has never had a live pass, and golden 63/67 uses the ideal reader (F5).
- **Evidence (mixed):** `genios_engine/contracts/claim_check.py:38 (CHECK_VERSION = 'check.v4')`; `git: 117f90c6 and 73d9f804 not ancestors of HEAD 0cc8d83c nor origin/speedrun008`; `git show 73d9f804 (17 Oct live pass numbers)`; `genios_engine/reason/llm_sites.py:290-295`; `speedrun008/YC-II W27/06-DECISIONS.md:57 (D50), :79 (D72)`
- **What Rohit sees:** More held question cards than necessary on the production model, and model quality in production is unmeasured.
- **Where the mistake was:** STEP-13b was built and measured on a side branch and left unmerged. The 19–21 Oct L2 rebuild then built on the pre-13b check, so the measured improvement never shipped.
- **Fix:** Rebase STEP-13b onto speedrun008. The L2 judge reuses check_review and the expert dossier, so resolve check.v5 against reason/l2/judge.py and the judgment holds. Re-record the golden set, then run one capped live pass on Sonnet 5 for both R-7 and R-9 (test 1–2 calls first). After that Harsh deploys.
- **Blocked on:** Rohit's yes for the live-pass spend (D72-style cap, about $7), and the production held share (SQL in l2-held-card-engineer-template).
- **Verified:** confirmed by the skeptic (I ran git merge-base --is-ancestor: 117f90c6 and 73d9f804 are ancestors of neither HEAD 0cc8d83c, origin/speedrun008 nor origin/harsh/mvp. They are contained only in yc2w27-haikufix, int13b, left13, left14 and s13b. HEAD has CHECK_VERSION='check.v4' (claim_check.py:38), while 117f90c6 has 'check.v5' (:42). reason/expert/ladder.py is absent from HEAD; the diff HEAD..117f90c6 adds ladder.py plus ~2,239 lines across contracts/ and reason/expert. HEAD has no live-pass score files: the speedrun008/YC-II W27/scores directory exists only on 73d9f804. The 73d9f804 message gives the cited numbers. R-7 and R-9 are both TIER_T2 (bundle/sites.py:85, :88), and tier_model('T2') returns 'claude-sonnet-5' (llm_sites.py:290-292). The Sonnet void pass and R-9 having no live pass rest on memory notes and the absence of any score file, not on a measured artifact.)

<a id="l2-d72-d73-thinking-and-live-eval-budget"></a>
### YC-II D72, D73 + F267–F269, s13b-D8: whether R-7 / the brief drafter should think, and live-eval spend beyond D65, are unanswered

`l2-d72-d73-thinking-and-live-eval-budget` · **P2** · shadow / switched off · owner **rohit** · paid_run · step **S07**

- **Expected:** D72: run the off-vs-adaptive comparison on 20 golden cases (≈$4.5, stop at $7) and keep thinking only if it wins. D73: compare the drafter's modes (≈$0.35). s13b-D8 asks $15 more. _(source: speedrun008/YC-II W27/06-DECISIONS.md D72, D73; 03-FINDINGS.md F267-F269; GeniOS-008 03-QUESTIONS.md E2 ($20))_
- **Actual:** The defaults are in code: every site including R-7 (6,000) and R-9 (8,000) asks with thinking OFF, and the drafter is off at 4,000. No comparison was run.
- **Evidence (measured):** `genios_engine/reason/bundle/sites.py:132, 155-165 (SITE_THINKING all off)`; `genios_engine/reason/brief_drafter.py:41-44, 224 ('06 D73 (open)'; THINKING_OFF)`
- **Fix:** Rohit says yes or no to the D72 run under GeniOS-008 E2's $20 (test 1–2 calls first). Claude runs `scripts/golden_eval.py --live --site expert ...` and records the result.
- **Verified:** confirmed by the skeptic (reason/bundle/sites.py:132 has SITE_EXPERT 6000 and :147 SITE_REASON 8000. SITE_THINKING (:155-166) sets every site, including SITE_EXPERT and SITE_REASON, to _THINKING_OFF. reason/brief_drafter.py:40-44 has MAX_TOKENS 4000 with '06 D73 (open)', and :224 sends THINKING_OFF. No record of a comparison run was found.)

<a id="l2-evidence-loop-not-armed"></a>
### L2 raises evidence needs, but the fetchers are off, so no re-entry happens and no card says 'waiting on X'

`l2-evidence-loop-not-armed` · **P2** · built, not live · owner **harsh** · prod_action · step **S13**

- **Expected:** R8: a decision-changing unknown raises one EvidenceNeed, L1 fetches it, and L2 re-enters once. A budget-out result is incomplete with its open needs. _(source: speedrun008/GeniOS-008/layer-2-reasoning/02-PLAN.md §1 R8, §5; 06-GAP-ANALYSIS.md R8)_
- **Actual:** Needs are raised (reason/l2/evidence.py:55-65) and stored, but the L1 fetchers are armed only by GENIOS_NEED_FETCHERS=on (capture/acquire/need_fetchers.py:6, 34; need_executor.py:236), which 04-FOR-HARSH says to leave off. Needs stay open, re-entry never fires, and nothing shows them on a card.
- **Evidence (measured):** `genios_engine/reason/l2/evidence.py:55-65`; `genios_engine/capture/acquire/need_fetchers.py:6, 34`; `genios_engine/capture/acquire/need_executor.py:236`; `speedrun008/GeniOS-008/layer-2-reasoning/04-FOR-HARSH.md 'The evidence fetchers'`
- **What Rohit sees:** Unknowns that would change the move are never fetched, so the card stays a guess or a question.
- **Fix:** Harsh runs one fetch by hand for Rohit's org, then arms GENIOS_NEED_FETCHERS. Show open needs as 'waiting on' on the card.
- **Blocked on:** select count(*), state from evidence_needs where org_id='<ORG>' and need_id like 'l2need:%' group by 2;
- **Verified:** confirmed by the skeptic (needs_from is at reason/l2/evidence.py:55-65 and needs are stored at l2/sweep.py:425. need_fetchers.armed() reads GENIOS_NEED_FETCHERS (need_fetchers.py:6, 34-38), and build_fetchers returns {} unless armed AND a factory is registered (need_executor.py:236-240; factory registered at api/routes.py:3550). 'Leave it off' appears at layer-2-reasoning/04-FOR-HARSH.md:140-144 and layer-1-enterprise-signals/04-FOR-HARSH.md:166. Re-entry reads only MET needs (l2/sweep.py:220-225). No deliver/ code renders open needs. Whether the env var is set in production is a deployment fact for Harsh.)

<a id="l2-r7-per-call-refusal-stops-pass"></a>
### The expert pass still stops entirely on a per-call budget refusal (the L2 pass was fixed)

`l2-r7-per-call-refusal-stops-pass` · **P2** · broken · owner **claude** · code · step **S18**

- **Expected:** One oversized prompt is that subject's problem, not the day's (the fix b8a8a43c made in the L2 pass). _(source: genios_engine/reason/l2/sweep.py:398-405)_
- **Actual:** reason/expert/sweep.py:307-309 breaks the whole pass on any OVER_BUDGET, including a per-call refusal. Computed at the 60,000-character dossier bound (reason/expert/dossier.py:88) plus about 8,500 characters of fixed prompt: the R-7 estimate is $0.094 against the $0.10 per-call cap (estimate_micro_usd), so the margin is thin, and a repair prompt grows it.
- **Evidence (measured):** `genios_engine/reason/expert/sweep.py:305-309`; `genios_engine/reason/l2/sweep.py:398-405`; `genios_engine/reason/expert/dossier.py:88`; `genios_engine/reason/bundle/budget.py:63-64 (computed estimate 94,258 µ$ vs 100,000)`
- **What Rohit sees:** Latent silent stop: one large file sorted first could carry every other file every day.
- **Where the mistake was:** The 21 Oct audit fixed this in reason/l2 only.
- **Fix:** Port the L2 fix: on a REASON_PER_CALL refusal, carry that file and continue.
- **Verified:** confirmed by the skeptic (OUTCOME_NO_BUDGET maps to OVER_BUDGET (expert/review.py:70-75), and expert/sweep.py:304-306 breaks the pass on any OVER_BUDGET, with no per-call distinction. The L2 pass has that distinction (l2/sweep.py:398-405, b8a8a43c). I recomputed with T2 = 200/1000 cents per Mtok (capture/semantic/batch.py:139-142): 68,500 chars /4 = 17,125 tokens in (34,250 µ$) + 6,000 out (60,000 µ$) = 94,250 µ$ against the 100,000 per-call cap (budget.py:63-64), which matches the item. DOSSIER_CHARS = 60,000 (expert/dossier.py:88). This only bites tenants with expert_review on and l2_cards off, because under l2_cards R-7 makes no call.)

<a id="layer-l3"></a>
## L3 Context Graph (context/)

> L3 (context/) is the most fully built layer, and today it, not L2, decides what exists. In process_pending, every event is correlated by thread first, then by (anchor node, keyword-derived domain, 45-day generation). Nine writers then form situation rows before any reasoning runs. Only after that does reason.runner.run_all (R-7 expert, then R-9 L2 judgment, then the compiled lane, then pack rules) reason over those rows, and the cards are built from them. The new admission door (context/l2_admission, fb429b78) runs in shadow only and only when l2_reasoning is on. Nothing reads its output, and it can only see situations anchored on the file's own node. Every reading situation (awaiting reply, commitment overdue, support, period, meeting, document) is anchored on a synthetic node, so admission cannot see it, and GeniOS-009 G0.3's planned first switch (outreach seeds) cannot work as designed. Correlation fails silently in several places that leave L2 with nothing to reason on: (1) noise, archived and held events are never filed; (2) a reply can inherit a reading's synthetic correlation and land in no file; (3) a bundle that is not yet filed is judged as a contextless 'seed' whose HOLD has no applier and raises no EvidenceNeed; (4) a bundle spanning two files is judged under the first only; (5) correlations whose anchor node vanished (rebuild_graph, merges) are silently dropped from files. One counterparty usually holds several live situations: one per keyword domain (with an 'admin' fallback) and one per 45-day generation. So the L2 judgment HOLDs instead of admitting, and under l2_cards the file falls back to the old lane. This is a likely code-level source of the 'sometimes no correlation, sometimes no reasoning' and duplicate or odd cards. Rebuild paths are risky: any history backfill that mints a deal node deletes every situation and re-mints random ids, which orphans admissions, resolution claims and human closes (the docstring wrongly says the ids are content hashes). Harsh's 20–21 Oct L3 fixes are real and in the code. However, the as-of read and situation_interpretations are built with no caller or reader, and the plan's 'wired' claims for hold→EvidenceNeed and for identity candidates are false. L3 has no goal object or goal link at all. Production was not read; the size of each failure needs the read-only SQL given in blocked_on.

| Item | Sev | Status | Owner | Step |
|---|---|---|---|---|
| [L2 admission only sees situations anchored on the file node; every reading situation (awaiting reply, commitme](#l3-admission-cannot-see-reading-situations) | P0 | broken | claude | S15 |
| [Situations are still formed in L3 before any reasoning; both admission doors run after the row exists and gate](#l3-situations-born-before-reasoning) | P0 | shadow / switched off | claude | S24 |
| [The bounded snapshot L2 reads has no as-of in use, no unknowns or contradictions, no facts, and a visibility f](#l3-bounded-snapshot-incomplete) | P1 | partial | claude | S16 |
| [YC-II D14, D35 (+F96): whether Rohit's company domain is declared as 'us' and the self-identity repair was run](#l3-d14-d35-self-identity-declaration-and-repair) | P1 | unknown until production is read | rohit+harsh | S02 |
| [A situation's domain is a per-message keyword decision with an 'admin' fallback; fundraising situations route ](#l3-domain-routing-fundraising) | P1 | partial | rohit+harsh | S15 |
| [Many events never reach a file, silently (noise, archived/metadata-only, held, parked, anchorless, private), a](#l3-events-outside-any-file) | P1 | partial | claude | S14 |
| [YC-II F165: an undated or conditional promise in mail never becomes a commitment in the graph (widened by the ](#l3-f165-undated-and-conditional-promises-never-enter-memory) | P1 | broken | claude | S16 |
| [A HOLD raises no EvidenceNeed: needs_from_holds and resolve_hold have no production caller, though the plan sa](#l3-hold-evidence-chain-unwired) | P1 | missing | claude | S13 |
| [l2_admissions is shadow only: written only when l2_reasoning is on, read by nothing, HOLDs have no applier, me](#l3-l2-admissions-shadow-status) | P1 | shadow / switched off | claude+harsh | S24 |
| [One counterparty file holds many live situations (one per keyword domain × 45-day generation, plus readings), ](#l3-one-subject-many-situations) | P1 | broken | claude | S15 |
| [Anchoring depends on arrival order: a person is lifted to their company only if the company node already exist](#l3-person-company-lift-order) | P1 | partial | claude | S15 |
| [A correlation rebuild deletes every situation (readings, human and statement closes included) and re-mints ran](#l3-rebuild-deletes-situations-and-ids) | P1 | broken | claude | S14 |
| [scripts/rebuild_graph.py wipes graph_* but keeps correlations, members, situations and open loops; replayed ev](#l3-rebuild-graph-keeps-stale-correlations) | P1 | broken | claude | S14 |
| [Thread inheritance reads reading-declared memberships: a reply can join a reading's synthetic correlation and ](#l3-thread-inherits-reading-correlations) | P1 | broken | claude | S14 |
| [A failed L3 pass now appears in the sweep's return but only in an INFO log line, and the first derived pass ca](#l3-failed-pass-visibility) | P2 | partial | claude | S17 |
| [What L3 records of an admitted judgment, including the decision object, is write-only, and its outcome column ](#l3-interpretations-decision-object-write-only) | P2 | built, not live | claude | S24 |
| [The chain's stage names and loggers still use the old layer numbering: L3 work is logged as 'l2', and the L2 j](#l3-layer-names-in-code) | P2 | partial | claude | S17 |
| [L3 still calls a model every sweep (resolution detection) and still recomputes clock-relative values and rewri](#l3-model-call-and-clock-values-in-l3) | P2 | partial | claude | S17 |
| [Identity: the exact-key law holds in identity.py, but readers join by name around it, and ambiguity is never s](#l3-name-only-joins) | P2 | partial | claude | S15 |
| [The 9 sweep writers that form situations before reasoning are all live, and the CI ratchet that should only le](#l3-nine-situation-writers-and-missing-ratchet) | P2 | missing | claude | S04 |

<a id="l3-admission-cannot-see-reading-situations"></a>
### L2 admission only sees situations anchored on the file node; every reading situation (awaiting reply, commitment overdue, support, period, meeting touch, document) is invisible to it

`l3-admission-cannot-see-reading-situations` · **P0** · broken · owner **claude** · code · step **S15**

- **Expected:** G0.3: outreach / awaiting-reply situations become seeds that an ADMIT on the L2 judgment flips to active. One situation per subject; a card is a living view of one situation. _(source: GeniOS-009/STEP-G0-the-ground.md §G0.3 steps 1-3; GeniOS-008/00-ARCHITECTURE.md:117)_
- **Actual:** decide() receives only parts.lifecycle.situations, which is lifecycle_for(file_id): context_situations WHERE anchor_node_id = the file's node, at most 10. Every reading mints its own anchor node. Outreach readings use find_or_create_node(node_type=anchor_node_type(anchor)): 'outreach', 'reading:commitment', 'cohort', 'condition', the firm. Support, periodic and document readings mint their own nodes, and meeting_touch anchors on the meeting node. None of these rows ever reaches decide(), so an outreach seed can never be ADMITted, held or rejected by the file's judgment.
- **Evidence (measured):** `genios_engine/reason/l2/sweep.py:373-375 (situations = parts.lifecycle.situations)`; `genios_engine/reason/expert/dossier.py:783 lifecycle_for(file_id)`; `genios_engine/context/workstreams.py:321-325 (_SITUATIONS where anchor_node_id = :f), :314 LIFECYCLE_LIMIT = 10`; genios_engine/context/outreach_situations.py:113-129 (reading anchor types), :1823 find_or_create_node(node_type=anchor_node_type(anchor)), :1903 _upsert(node_id=…); `genios_engine/context/support_situations.py:1575, :1674 (anchor_node_id = :n, the reading's node)`; `genios_engine/context/meeting_touch.py:237-251 (corr_touch_<domain>_<meeting node>, anchor = meeting node)`; `genios_engine/context/periodic.py:99 (own period node)`
- **What Rohit sees:** The founder's investor follow-up cards (awaiting reply, overdue promises) can never become L2-admitted. If the card path switches to admitted() (Phase C), these cards would disappear.
- **Where the mistake was:** GeniOS-009 STEP-G0 §G0.3 chose outreach as the first type and assumed an ADMIT on its seed, without checking that admission reads only file-anchored situations. The fb429b78 docstring ('the seed it reasoned about is the situation') assumes a file and its seeds share an anchor.
- **Fix:** Before any seed switch, attach each reading situation to the file it concerns. Either store the counterparty/file node beside the synthetic anchor (finding.concerns_node already exists) and include those rows in lifecycle_for and decide(), or move the readings into L2 as inputs (L2-11). Then rewrite G0.3's design accordingly.
- **Verified:** confirmed with a correction by the skeptic: Substance holds. decide() gets parts.lifecycle.situations (sweep.py:373-375). That list is lifecycle_for(file_id) (dossier.py:783): _SITUATIONS where anchor_node_id = :f, limit LIFECYCLE_LIMIT=10 (workstreams.py:314, :321-325). Each reading anchors on its own node. Outreach readings use find_or_create_node(node_type=anchor_node_type(anchor)) (outreach_situations.py:1820-1823). The organization reading's key is 'organization:<company node>' (:1304), a separate node from the company file. Support anchors on its own node (support_situations.py:1575, :1674). Documents anchor on the artefact node (document_register.py:574-591). meeting_touch anchors on the meeting node (:237-251); meetings are not an anchor tier (correlation.py:109-110 _SHIPPED_TIERS = deal, subscription, product_account, company, person). One detail is wrong: periodic.py does not mint its own period node. It anchors on the TENANT node (periodic.py:99-101 _ensure_tenant_node, node_type 'tenant', 'This organisation').

<a id="l3-situations-born-before-reasoning"></a>
### Situations are still formed in L3 before any reasoning; both admission doors run after the row exists and gate nothing

`l3-situations-born-before-reasoning` · **P0** · shadow / switched off · owner **claude** · code · step **S24**

- **Expected:** L2 forms the situation from bundle + snapshot + expertise; L3 only remembers what L2 concluded and admits it (ADMIT/HOLD/REJECT). A situation row exists only after an ADMIT. Switch one type first (outreach / awaiting reply). _(source: speedrun008/GeniOS-008/00-ARCHITECTURE.md:38, :106, :138; 02-MIGRATION-PLAN.md §3.3 L3-1 and §4; layer-2-reasoning/05-SPEC-layer-2.md:599; GeniOS-009/STEP-G0-the-ground.md §G0.3)_
- **Actual:** context.runner.process_pending writes context_situations through nine writers before reason.runner.run_all runs. context/l2_admission.decide runs inside the L2 pass after the rows exist and writes only l2_admissions; its own docstring says 'SHADOW: nothing here touches context_situations'. admitted(), the card read, has no production caller. No 'seed' status exists. The Atlas door (situation_publisher) is called only from shadow_compile, after the row exists, and writes a different table (situation_admission_decisions). So there are two ADMIT/HOLD/REJECT vocabularies on two tables, and neither decides existence.
- **Evidence (measured):** `genios_engine/api/routes.py:797-823 (process_pending, then run_all)`; `genios_engine/context/l2_admission.py:1-26 ('SHADOW'), :199-206 admitted()`; `genios_engine/context/context_health.py:37-40 (l2_admission.admitted declared UNREACHED)`; migrations/0038_l2_situations.sql:25 status = active|dormant|resolved|archived; no 'seed' anywhere in context/ or migrations/; genios_engine/reason/domain_shadow.py:1748 publish_situation called inside shadow_compile; migrations/0122_l2_situation_admission.sql:2 situation_admission_decisions; `migrations/0249_l2_admissions.sql (fb429b78, 'SHADOW')`
- **What Rohit sees:** Every card Rohit sees is a view of a row formed by joins and keyword readings, never by reasoning. The L2 judgment cannot stop a wrong situation or create a missing one.
- **Where the mistake was:** fb429b78 (L2-G2) built a second admission door on a new table instead of adapting situation_publisher, the door 00-ARCHITECTURE:106 names, and shipped it as shadow. G0.3 (which blocks G1–G9) has not started.
- **Fix:** Build G0.3 properly, after l3-admission-cannot-see-reading-situations is fixed. Add status 'seed'. Make the first type's writer write seeds only. An ADMIT flips a seed to active, a REJECT archives it with resolved_by='admission', and a HOLD keeps it a seed with its reason. The card source reads only admitted rows. Merge the two doors into one: have situation_publisher take L2's proposal, or retire it.
- **Depends on:** [l3-admission-cannot-see-reading-situations](#l3-admission-cannot-see-reading-situations), [l3-one-subject-many-situations](#l3-one-subject-many-situations)
- **Verified:** confirmed with a correction by the skeptic: The ordering holds: routes.py:797-823 runs process_pending, then run_all. The nine writers create context_situations rows before any reasoning. l2_admission writes only l2_admissions and has no 'seed' status. admitted() has no caller. situation_publisher writes situation_admission_decisions (0122). Neither door decides whether a row exists. But 'gate nothing' is wrong for both doors. (a) Atlas door: in shadow_compile, when publish_situation returns HOLD or REJECT the compiled lane skips that situation and compiles or decides nothing for it (domain_shadow.py:1765-1772, 'HOLD/REJECT is the output … continue'). It records a decision only when live_row is set (:1760). (b) l2_admission: with l2_cards on, any HOLD among a file's decisions stops the L2 file review being written. That review is the file's card source and covers it (reason/l2/sweep.py:376-383). So each door gates downstream reasoning or cards; neither gates existence.

<a id="l3-bounded-snapshot-incomplete"></a>
### The bounded snapshot L2 reads has no as-of in use, no unknowns or contradictions, no facts, and a visibility field nothing applies

`l3-bounded-snapshot-incomplete` · **P1** · partial · owner **claude** · code · step **S16**

- **Expected:** Bounded query API: seeds, hops, max nodes, unknowns and contradictions; bitemporal as-of. _(source: GeniOS-008/00-ARCHITECTURE.md:107; 02-MIGRATION-PLAN.md L3-3)_
- **Actual:** read_snapshot calls ReadRequest(seeds, max_nodes) with no as_of, although 5985b6e1 added it ('no caller changes'). BoundedView holds only node ids, edges, revision and truncation. The snapshot keeps node names and edges and no facts. ReadRequest.visibility is declared and never read by expand or sql_neighbours, and graph_edges has no visibility column.
- **Evidence (measured):** `genios_engine/reason/l2/snapshot.py:72-90`; genios_engine/context/bounded_read.py:58-65 (visibility, as_of), :80-92 (BoundedView), :103-157 (expand never reads visibility); `migrations/0004_l2_context_graph.sql:61-74 (graph_edges, no visibility_scope)`; `commit 5985b6e1`
- **What Rohit sees:** A thin context for the judgment, and replays read today's graph.
- **Where the mistake was:** 5985b6e1 built the as-of read without a caller, the 'built and never called' pattern.
- **Fix:** Pass as_of=eval_time. Add unknowns (typed absences) and contradictions (discrepancies, signal_conflicts) to the view. Either apply visibility or delete the dead field.
- **Verified:** confirmed by the skeptic (Verified. read_snapshot calls ReadRequest(seeds, max_nodes) with no as_of (snapshot.py:77). 5985b6e1 added as_of, and its message says 'No instant = the read exactly as before (no caller changes)'. BoundedView has node_ids, edges, revision, truncated, hops_walked and truncated_by (bounded_read.py:80-96). Snapshot keeps names and edges only (snapshot.py:38-52). The only 'visibility' in bounded_read.py is the field declaration at :58-60; expand and sql_neighbours never read it. graph_edges has no visibility column (0004:61-74; later adds are only interaction_count, last_seen_at and recorded_at). The L2 pass does get L1 contradictions and file facts by other routes: read_open_conflicts / signal_conflicts (inputs.py OPEN_CONFLICTS, sweep.py:198-204) and the file dossier. They just do not come through the bounded snapshot.)

<a id="l3-d14-d35-self-identity-declaration-and-repair"></a>
### YC-II D14, D35 (+F96): whether Rohit's company domain is declared as 'us' and the self-identity repair was run is unknown

`l3-d14-d35-self-identity-declaration-and-repair` · **P1** · unknown until production is read · owner **rohit+harsh** · prod_action · step **S02**

- **Expected:** D35: Rohit declares his company's domain as ours, once (scripts/declare_self_identity.py). D14: Harsh runs repair_self_identity dry, Rohit reads the list, then --apply retires cards and signals whose subject is the founder. _(source: speedrun008/YC-II W27/06-DECISIONS.md D14, D35; 03-FINDINGS.md F96; 07-WHAT-IS-DONE.md §8 step 6)_
- **Actual:** Both scripts exist and are read-only until --apply. D35's own default is 'no', so a portal notice naming the company files it under 'us' as a counterparty until Rohit declares the domain. Production was not read.
- **Evidence (mixed):** `scripts/declare_self_identity.py:32 (insert into org_self_identities)`; `scripts/repair_self_identity.py:1-30 (dry run default; retires cards whose subject is us)`; `speedrun008/YC-II W27/06-DECISIONS.md:42 D35 ('Default: no')`
- **What Rohit sees:** Cards about the founder himself ('Send Mr Rohit Swerashi your traction metrics') and stray 'us' files, which are weird cards.
- **Fix:** Rohit says yes to D35. Harsh runs declare_self_identity for the domain, then repair_self_identity dry → Rohit reads → --apply, then the health check reads 0 and 0.
- **Blocked on:** select kind, value, declared_by from org_self_identities where org_id='<ORG>'; then `python scripts/repair_self_identity.py --org <ORG> --database-url <prod>` (dry run, no --apply)
- **Verified:** unverifiable without production: The code facts are confirmed. scripts/declare_self_identity.py:31-33 inserts into org_self_identities. scripts/repair_self_identity.py:1-30 is a dry run unless --apply, and it retires cards and signals whose subject is us. 06-DECISIONS.md:21 D14 and :42 D35 ('Default: no'). No migration or engine code inserts into org_self_identities, so a declaration exists only if someone ran the script. Read-only SQL: `select org_id, kind, value, declared_by, created_at from org_self_identities where org_id = '<rohit_org>';` and `select count(*) from card_events where cause = 'subject_is_us';`

<a id="l3-domain-routing-fundraising"></a>
### A situation's domain is a per-message keyword decision with an 'admin' fallback; fundraising situations route only to Founder Office, which is off by default

`l3-domain-routing-fundraising` · **P1** · partial · owner **rohit+harsh** · mixed · step **S15**

- **Expected:** L2 frames the situation with expertise (the model judges in words; it never routes). Rohit's org has Admin plus Founder Office live (decision D2, 9 Oct). _(source: GeniOS-008/00-ARCHITECTURE.md:38, :123; memory admin-domain-only.md (D2))_
- **Actual:** resolve_domain picks the domain by hint origin: scope, then model, then keyword or fallback. An emitted mail with no keyword gets the gate's 'admin' fallback. capability_resolver maps fundraising→founder_office. Founder Office has default_on: false; only Admin has default_on: true. A situation whose domains are all un-activated raises NoExpertiseRoute in the compiled lane.
- **Evidence (measured):** `genios_engine/context/correlation.py:192-219`; `genios_engine/capture/domain/hints.py:11-15 (source priors), :78 FALLBACK_DOMAIN='admin', :222-224`; `genios_engine/capture/pipeline.py:1670-1671`; `genios_engine/packs/compiler/capability_resolver.py:45, :605-609`; Domain Expertise/Founder Office Expertise/domain.yaml:45 default_on: false; Domain Expertise/Admin Expertise/domain.yaml:50 default_on: true
- **What Rohit sees:** Investor and accelerator threads that lack a keyword are typed Admin and read by the Admin corpus. If Founder Office is off, fundraising situations reach no expertise at all.
- **Fix:** Confirm founder_office is activated for Rohit's org (a Harsh production action if it is missing). Longer term, let the L2 judgment frame the domain and drop the keyword 'admin' fallback as a correlation key.
- **Blocked on:** Production read: select * from l3_activation where org_id='<rohit_org>'; select domain, situation_type, status, count(*) from context_situations where org_id='<rohit_org>' group by 1,2,3 order by 4 desc;
- **Depends on:** [l3-one-subject-many-situations](#l3-one-subject-many-situations)
- **Verified:** confirmed by the skeptic (Verified. Hint ranks are scope 0, model 1, keyword 2, and an unknown origin ('fallback') is _UNRANKED=2 (correlation.py:192-219). FALLBACK_DOMAIN='admin' is applied to emitted mail only (capture/pipeline.py:1667-1671). fundraising and investor map to founder_office (capability_resolver.py:45-52). Domains that are not activated raise NoExpertiseRoute (:605-609). default_on is false for Founder Office and true for Admin. Additional measured fact: the 'model' hints the pipeline appends (context/pipeline.py:432-447) are, in the drain, the qualified signal's domain_hints (runner.py:191, qes_adapter._domains). Those come from tag_domains with no proposer and no fallback (capture/pipeline.py:1309), so they repeat L1's scope and keyword hints and are deduplicated. The model's own domain judgment that pipeline.py:2334-2343 describes no longer reaches the correlation key. Founder Office activation for Rohit's org has no migration; it comes from scripts/activate_tenant.py, so only production can confirm it: select org_id, domain from l3_activation where org_id = '<rohit org>';)

<a id="l3-events-outside-any-file"></a>
### Many events never reach a file, silently (noise, archived/metadata-only, held, parked, anchorless, private), and the funnel cannot show it

`l3-events-outside-any-file` · **P1** · partial · owner **claude** · code · step **S14**

- **Expected:** Nothing is lost silently: every kept event is either in memory and filed, or carries a receipt saying why not. The funnel shows where the loss is. _(source: GeniOS-008/02-MIGRATION-PLAN.md §2 (STEP-06 'nothing lost silently' → L3 situation end receipts); 00-ARCHITECTURE.md L1 'coverage receipt')_
- **Actual:** correlate_event is skipped for noise and for metadata-only (archived) mail. An event whose QES pointer is missing is held with 0 attempts and no cap, and is re-pulled every sweep. After 3 failures an event is parked and re-offered daily. An event that anchors nothing correlates to nothing ('a real answer'). Private events are excluded from files. The funnel has no 'events filed' stage. SITUATIONS_FORMED relays situations_ranked, which counts every non-archived situation of the org (a stock), not what this sweep formed.
- **Evidence (mixed):** `genios_engine/context/pipeline.py:2326 (no correlation when is_noise or metadata_only)`; genios_engine/context/runner.py:179-183 held_missing_qes_extraction; :436-443 _record_hold attempts 0; :419-433 park after _MAX_ATTEMPTS; PENDING_FROM in runner.py (parked re-offered after 1 day); `genios_engine/context/correlation.py:259, :629-630 (empty plan → [])`; `genios_engine/context/workstreams.py:168 (private excluded)`; `genios_engine/platform/funnel.py:54-58 (five stages, none for filing)`; genios_engine/api/routes.py:818-819 SITUATIONS_FORMED = situations_ranked; genios_engine/context/situation_bso.py:1999-2010 (all non-archived); `memory production-funnel-2026-10-04.md (27 of ~470 emails reached the graph; history)`
- **What Rohit sees:** Fewer cards, with no number anywhere that says which mail never reached a file.
- **Where the mistake was:** The funnel was wired to relay situations_ranked under the SITUATIONS_FORMED label.
- **Fix:** Add a funnel number per sweep: events drained versus events in an engine-owned correlation, broken down by reason (noise, metadata, held, parked, anchorless). Make SITUATIONS_FORMED count the situations this sweep opened or changed. Cap and report held_missing_qes_extraction.
- **Blocked on:** Production read: select se.outcome, se.source, count(*) as events, count(*) filter (where exists (select 1 from context_correlation_members m join context_correlations c on c.org_id=m.org_id and c.correlation_id=m.correlation_id where m.org_id=se.org_id and m.event_id=se.event_id)) as in_a_file from source_events se where se.org_id='<rohit_org>' and se.occurred_at > now() - interval '60 days' group by 1,2 order by 3 desc; plus: select status, left(last_error,60), count(*) from l2_processing_runs where org_id='<rohit_org>' and status in ('held','parked','failed') group by 1,2;
- **Depends on:** [l3-thread-inherits-reading-correlations](#l3-thread-inherits-reading-correlations)
- **Verified:** confirmed by the skeptic (Verified. Correlation is skipped for noise and for metadata-only events (context/pipeline.py:2326). held_missing_qes_extraction is recorded with attempts 0 (runner.py:187-189, :436-443). PENDING_FROM excludes only 'done' and parked rows younger than 1 day, so held rows are re-pulled every sweep (runner.py:380-394). Events park after _MAX_ATTEMPTS=3 (:54, :419-433). choose_anchors returns [] and correlate_event returns [] (correlation.py:259, :629-630). Private events are excluded from files (workstreams.py:168). The funnel has five closed stages with no filing stage (platform/funnel.py:54-58). SITUATIONS_FORMED relays situations_ranked (routes.py:818-819), which counts every non-archived situation (situation_bso.py:1954-1957). The only 'unfiled' report is the manual script scripts/pipeline_health.py:735 (Workstreams.unfiled). It covers brief-named senders only and treats any membership as filed.)

<a id="l3-f165-undated-and-conditional-promises-never-enter-memory"></a>
### YC-II F165: an undated or conditional promise in mail never becomes a commitment in the graph (widened by the 21 Oct L3 audit)

`l3-f165-undated-and-conditional-promises-never-enter-memory` · **P1** · broken · owner **claude** · code · step **S16**

- **Expected:** Every promise said in mail, ours or theirs, enters memory. An undated one stays an open promise, a conditional one is tracked by the decision it waits on, and the expert/L2 dossier's 'PROMISES IN ITS MAIL' shows them. _(source: speedrun008/YC-II W27/03-FINDINGS.md F165 ('the cause is Layer 3's'); 06-DECISIONS.md D56 ('soon' stays an open promise))_
- **Actual:** context/pipeline writes the commitment node only `if subj and (due or transcript_mode)`. The 21 Oct L3 audit now sets due = None for every conditional promise, so conditional promises are dropped from memory too, not just undated ones. The file dossier's promises come only from graph `commitment.text` facts, so the expert and L2 see 'No promise was found in its mail.'
- **Evidence (measured):** `genios_engine/context/pipeline.py:2196-2206 (conditional → due None; `if subj and (due or transcript_mode):`)`; `genios_engine/reason/expert/dossier.py:655-674 (_PROMISES reads commitment.text / commitment.due_at facts)`; `genios_engine/reason/expert/dossier.py:408-410 ('No promise was found in its mail.')`
- **What Rohit sees:** Promises like 'we'll send the agreement once you confirm' or 'I'll intro you soon' vanish, so there is no reasoning or card about them and the judgment misses half of what was owed.
- **Where the mistake was:** The 21 Oct L3 audit fixed false 'promise past due' cards by un-dating conditional promises, but it left the existing `due or transcript_mode` guard in place, which now drops those promises from memory entirely.
- **Fix:** Claude writes the commitment node for every extracted promise (undated → no due fact; conditional → `commitment.condition` fact and status `conditional`), keeping 'never a deadline'. Then a mutation test, and re-record the cases whose dossiers change (ideal reader).
- **Verified:** confirmed by the skeptic (pipeline.py:2203-2205 sets `due = None` when is_conditional is True. That came in commit bda38c3d ('L3 audit: a conditional promise mints no due date'), which is in HEAD. Then `if subj and (due or transcript_mode):` (:2206) skips the commitment node and every commitment.* fact for undated or conditional mail promises. Only transcripts write undated ones (:2263). The comment says the promise 'is tracked by the decision it waits on', but no such tracking exists; the promise is simply not written. commitment.text has one writer (pipeline.py:2265). The dossier's _PROMISES (reason/expert/dossier.py:655-677) reads only commitment.text, and _promises (:408-410) prints 'No promise was found in its mail.')

<a id="l3-hold-evidence-chain-unwired"></a>
### A HOLD raises no EvidenceNeed: needs_from_holds and resolve_hold have no production caller, though the plan says 'wired'

`l3-hold-evidence-chain-unwired` · **P1** · missing · owner **claude** · code · step **S13**

- **Expected:** A HOLD raises an EvidenceNeed, L1 fetches it, and the hold resolves. _(source: GeniOS-008/00-ARCHITECTURE.md:106; 02-MIGRATION-PLAN.md:151 (L3-1 '(hold_needs.py, wired)'))_
- **Actual:** context_health declares hold_needs.needs_from_holds and hold_resolution.resolve_hold UNREACHED. A grep finds no caller in genios_engine/ or scripts/. l2_admission HOLDs only write a row. Its note also records that L1's need executor has no fetchers wired.
- **Evidence (mixed):** `genios_engine/context/context_health.py:42-48`; `genios_engine/context/l2_admission.py:96-97, :104-105, :115-116 (HOLD rows only)`; `speedrun008/GeniOS-008/02-MIGRATION-PLAN.md:151`
- **What Rohit sees:** A held file stays held. Nothing goes and fetches the missing fact.
- **Where the mistake was:** 02-MIGRATION-PLAN.md:151 marks hold_needs 'wired'; it is not.
- **Fix:** Wire HOLD → needs_from_holds → store_needs in the L2 pass's transaction, and resolve_hold on the need's outcome. Correct 02-MIGRATION-PLAN L3-1.
- **Blocked on:** L1 need executor fetchers (capture/acquire/need_executor.build_fetchers is empty; Harsh's, per context_health.py:43-44)
- **Verified:** confirmed with a correction by the skeptic: The main claim holds. needs_from_holds and resolve_hold have no caller outside their own modules (grep of genios_engine/ and scripts/ finds only __all__ entries and context_health.py:42-48), and l2_admission HOLDs only write a row. But the note the item relies on is stale. context_health.py:44 says build_fetchers 'is empty', yet GeniOS-008 L1 E2 wired it. build_fetchers returns a factory's fetchers when GENIOS_NEED_FETCHERS is on (need_executor.py:224-246, need_fetchers.armed :39-40). api/routes.py:3550-3552 registers the factory (register_fetcher_factory(_need_fetchers)). work_the_needs runs each pass (domain_shadow.py:2027-2029). So L1 CAN meet a need once the env switch is armed. Whether GENIOS_NEED_FETCHERS is on in production is Harsh's env, which I cannot check.

<a id="l3-l2-admissions-shadow-status"></a>
### l2_admissions is shadow only: written only when l2_reasoning is on, read by nothing, HOLDs have no applier, merge/link have no applier

`l3-l2-admissions-shadow-status` · **P1** · shadow / switched off · owner **claude+harsh** · mixed · step **S24**

- **Expected:** L3 admission decides existence (ADMIT/HOLD/REJECT); HOLD raises an EvidenceNeed; card path reads admitted situations (Phase C). _(source: GeniOS-008/00-ARCHITECTURE.md:106; migrations/0249_l2_admissions.sql header; fb429b78 message)_
- **Actual:** The L2 pass returns before any read when l2_reasoning is not activated, and the feature is off by default. The admission write happens inside a savepoint, so a failure only sets receipt['admissions_failed']. admitted() has no caller. merge and link proposals are always HOLD ('no applier yet'). Only the latest decision per (subject, situation) is kept, keyed by situation ids that a rebuild re-mints.
- **Evidence (measured):** `genios_engine/reason/l2/sweep.py:177 (l2_reasoning gate), :421-429 (savepoint write)`; `genios_engine/platform/intelligence_onboarding.py NOT_DEFAULT_ON l2_reasoning / l2_cards`; `genios_engine/context/l2_admission.py:49, :104-105 (merge/link held), :120-125 (upsert latest)`; `genios_engine/context/context_health.py:37-40`
- **What Rohit sees:** None today, because it is shadow. That is the problem: L2's verdicts never change what Rohit sees.
- **Fix:** After l3-admission-cannot-see-reading-situations and G0.3: make admitted() the card source for the first type, build merge and link appliers, and add the HOLD→EvidenceNeed link. Until then, report admission counts in the sweep or funnel so the shadow can be read.
- **Blocked on:** Production read: select * from l4_activation where org_id='<rohit_org>' and feature in ('expert_review','l2_reasoning','l2_cards','cards_from_situations'); select decision, op, count(*) from l2_admissions where org_id='<rohit_org>' group by 1,2 order by 3 desc;
- **Depends on:** [l3-situations-born-before-reasoning](#l3-situations-born-before-reasoning), [l3-admission-cannot-see-reading-situations](#l3-admission-cannot-see-reading-situations)
- **Verified:** confirmed with a correction by the skeptic: The table claims hold. The pass returns before any read when l2_reasoning is off (sweep.py:176-178). l2_reasoning and l2_cards are in NOT_DEFAULT_ON (intelligence_onboarding.py:193-203). The write is in a savepoint and failure sets admissions_failed (sweep.py:421-429). merge and link are always HOLD (l2_admission.py:49, :104-105). The upsert keeps the latest decision (:120-125). admitted() has no caller; the only other reference to l2_admissions is the /reset list (account_routes.py:942). But 'shadow only' is not true of the DECISIONS once l2_cards is on. In the same pass, an ADMIT or REJECT writes the file's review and a HOLD suppresses it (sweep.py:376-383). That review covers the file for the expert pass and the compiled lane, so admission changes cards for an l2_cards tenant even though nothing reads the table.

<a id="l3-one-subject-many-situations"></a>
### One counterparty file holds many live situations (one per keyword domain × 45-day generation, plus readings), so the L2 judgment is HELD instead of admitted

`l3-one-subject-many-situations` · **P1** · broken · owner **claude** · code · step **S15**

- **Expected:** One situation per subject; a card is a living view of one situation (versions, not new pings). _(source: GeniOS-008/00-ARCHITECTURE.md:117; layer-2-reasoning/05-SPEC-layer-2.md:51)_
- **Actual:** The correlation key is (anchor node, domain, generation). The domain is chosen per message: the L1 keyword hint, otherwise the gate's fallback 'admin' for every emitted mail with no keyword. So an invite titled 'Theresa <> Rohit' and an email that says 'investor', both with the same company, open two correlations, and refresh_situations writes one situation per correlation. A file unions them (workstreams), but decide() HOLDs 'one of several live situations, and the judgment named none of them'. With l2_cards on, a HOLD file gets no L2 file review and no R-7 call, so its cards come from the old lane.
- **Evidence (measured):** genios_engine/context/correlation.py:175 (base_key = node + domain), :426-456 (find_or_open by anchor+domain, new generation after the window), :76 CORRELATION_WINDOW_DAYS = 45; `genios_engine/context/situations.py:1178-1222 (one row per correlation)`; `genios_engine/capture/domain/hints.py:78 FALLBACK_DOMAIN = 'admin'; genios_engine/capture/pipeline.py:1670-1671`; `genios_engine/context/correlation.py:192-196 ('fallback' origin not ranked, so _UNRANKED = 2)`; `genios_engine/context/l2_admission.py:112-116 (HOLD when several live)`; genios_engine/reason/l2/sweep.py:381-383 (no file review on HOLD); genios_engine/reason/expert/sweep.py:168-175 (no R-7 call with l2_cards)
- **What Rohit sees:** Duplicate or split cards for one counterparty. The L2 judgment's conclusion is never admitted, and the old lane's card stands instead.
- **Fix:** Make the subject the unit: one live situation per file, with the domain as an attribute and not part of the key, or a file-level admission that names a primary situation. Let the judgment cite sit:<id>, since the dossier already prints it. Close the generation split for kinds with a declared window. Measure with the SQL first.
- **Blocked on:** Production read (Rohit's permission): select anchor_node_id, count(*) filter (where status in ('active','partial')) as live, array_agg(distinct domain) as domains, array_agg(distinct situation_type) as types from context_situations where org_id='<rohit_org>' group by anchor_node_id having count(*) filter (where status in ('active','partial')) > 1 order by live desc limit 30;
- **Verified:** confirmed with a correction by the skeptic: The mechanism holds. The key is node + domain + generation (correlation.py:173-175, :426-456). The domain is per message, with an 'admin' fallback (hints.py:78, capture/pipeline.py:1670-1671). refresh_situations writes one row per correlation (situations.py:1178-1222). The HOLD path is at l2_admission.py:112-116 and sweep.py:381-382. The expert pass makes no R-7 call under l2_cards (expert/sweep.py:166-171). Two details are wrong. (1) Generations add little to the LIVE count. An old generation goes dormant at DORMANT_AFTER_DAYS=45 (situations.py:87), the same clock that opens the next one. The window is also not always 45 days: a file's kind can stretch it, e.g. investor or program to 90 days via file_quiet_days (correlation.py:395-413, :437-438). So live multiplicity comes mainly from domains. (2) It is worse than stated. When the judgment names ONE of several live situations, every other live unnamed one is still HOLD (l2_admission.py:99-116, the else branch). Any HOLD blocks the file review (sweep.py:381-382). So a file with two or more live situations gets an L2 file review only when the judgment names all of them or proposes create.

<a id="l3-person-company-lift-order"></a>
### Anchoring depends on arrival order: a person is lifted to their company only if the company node already exists, and thread-first never re-anchors, so one counterparty can become two files

`l3-person-company-lift-order` · **P1** · partial · owner **claude** · code · step **S15**

- **Expected:** Four systems, one reality: all of a counterparty's mail and meetings meet in one situation. _(source: genios_engine/context/correlation.py:1-13, :482-492)_
- **Actual:** lift_people_to_their_companies is a read-only join on the email domain, so it does nothing if no company node exists yet. Free-mail people never lift. Thread-first inheritance keeps every later reply on the first anchor. Only backfill(rebuild=True) re-derives anchors, and it never runs incrementally. Duplicates are only proposed for merge; resolve_alias_candidates has no caller; and L2's merge/link proposals have no applier.
- **Evidence (measured):** `genios_engine/context/correlation.py:496-511, :315-328`; `genios_engine/context/backfill.py:117-124`; `genios_engine/context/context_health.py:58-60 (resolve_alias_candidates UNREACHED)`; `genios_engine/context/l2_admission.py:49`
- **What Rohit sees:** L2 judges half a relationship, or two cards appear for one counterparty.
- **Fix:** Add an incremental re-anchor when a person's company node appears, the analogue of lift_companies_to_their_deals. Give L2's link/merge proposals an applier so the judgment can join split files.
- **Verified:** confirmed by the skeptic (Verified. lift_people_to_their_companies is a read-only join on split_part(email,'@',2) = company canonical_key (correlation.py:482-511), so it does nothing without an existing company node. Free-mail domains are excluded from company creation (context/pipeline.py:225, _PERSONAL_DOMAINS). Thread-first inheritance is at correlation.py:325-328. Re-anchoring happens only on rebuild (backfill.py:117-124). resolve_alias_candidates is UNREACHED (context_health.py:58-60). merge and link proposals are HOLD (l2_admission.py:49).)

<a id="l3-rebuild-deletes-situations-and-ids"></a>
### A correlation rebuild deletes every situation (readings, human and statement closes included) and re-mints random ids, orphaning admissions, claims and interpretations; any history backfill that mints a deal triggers it, outside the org lease

`l3-rebuild-deletes-situations-and-ids` · **P1** · broken · owner **claude** · code · step **S14**

- **Expected:** A situation you cannot rebuild is one you cannot trust. The rebuild should return identical ids, and human decisions should survive. _(source: genios_engine/context/backfill.py:126-129 (its own claim); genios_engine/context/situations.py:1087-1091)_
- **Actual:** backfill_correlations(rebuild=True) deletes context_situations, members and correlations for the org. backfill_layer2 forces a rebuild whenever backfill_deal_nodes minted a deal. _replay_l2_history runs it after every backfill drain, and it does so outside warm_lane.run_exclusive. refresh_situations mints new_id('sit') (uuid4), contrary to the docstring's claim that 'a situation's id is a content hash … come back identical'. Tables keyed by situation_id keep the old ids: situation_resolution_claims (0101), situation_interpretations (0183), situation_outcomes (0194), l2_admissions (0249). _MOVED_KEYS includes situations_written, which is >0 whenever any correlation exists, so the chain runs twice after every backfill.
- **Evidence (measured):** `genios_engine/context/backfill.py:131-135, :434-435`; `genios_engine/api/routes.py:2025-2034 (replay after _run_l2, outside the lease) vs :677-680`; `genios_engine/context/situations.py:1220 new_id('sit'); genios_engine/platform/ids.py:6-8 uuid4`; `genios_engine/context/situations.py:1259-1281 (written += 1 per correlation); genios_engine/api/routes.py:688, :733`
- **What Rohit sees:** After a history backfill, handled cards can come back, statement-resolved ones reopen, and card feedback and history detach from their situations.
- **Where the mistake was:** backfill.py:126-129 states a false invariant (ids are content hashes) that the rebuild's safety argument rests on. This is the 'a stale comment reads as a measurement' pattern.
- **Fix:** Derive situation_id deterministically from correlation_id. Never delete reading rows or rows with a human or statement resolution during a rebuild. Run the replay under the org lease. Drop situations_written from _MOVED_KEYS, or count only changed rows. Correct the docstring.
- **Verified:** confirmed by the skeptic (Verified. rebuild deletes context_situations, members and correlations for the org (backfill.py:131-135). The backfill forces a rebuild when deal_nodes_created is set (:432-435). The docstring claims content-hash ids (:125-128), but refresh_situations mints held.situation_id or new_id('sit') (situations.py:1220), which is uuid4 (platform/ids.py:6-8). The replay runs after _run_l2 in a background task, outside warm_lane.run_exclusive (routes.py:2025-2034 vs :677-680). situations_written is in _MOVED_KEYS (routes.py:688), so any written situation re-runs the chain (:733, :2033-2034). These tables are keyed by situation_id: 0101 resolution_claims, 0183 interpretations, 0194 outcomes, 0249 l2_admissions.)

<a id="l3-rebuild-graph-keeps-stale-correlations"></a>
### scripts/rebuild_graph.py wipes graph_* but keeps correlations, members, situations and open loops; replayed events rejoin old correlations whose anchors are gone, and files_for silently drops those files

`l3-rebuild-graph-keeps-stale-correlations` · **P1** · broken · owner **claude** · code · step **S14**

- **Expected:** A rebuild replays exactly as the live drain files, and re-filing history is one step. _(source: memory a-replay-must-ask-the-drains-verdict.md; scripts/rebuild_graph.py:1-25)_
- **Actual:** _GRAPH_TABLES lists only graph_source_refs, graph_facts, graph_observations, graph_edges, discrepancies, graph_change_outbox, graph_nodes and graph_versions. Node ids are re-minted with new_id. Thread-first inheritance rejoins the old correlation ids, whose anchor_node_id no longer exists. files_for skips any anchor with no live node ('merged away since: re-derived later'), so that history drops out of every file. The fix requires a manual second call, POST /situations/backfill?rebuild=true, which the script neither runs nor mentions in its output.
- **Evidence (measured):** `scripts/rebuild_graph.py:59-60 (_GRAPH_TABLES), :181, :196-201`; `genios_engine/context/graph_store.py:470 new_id('node')`; `genios_engine/context/correlation.py:325-328, :340-363`; `genios_engine/context/workstreams.py:474-475 (if node is None: continue)`; `genios_engine/api/situation_routes.py:154`
- **What Rohit sees:** After a graph rebuild, whole counterparties disappear from files: no expert review, no L2 subject and no card until someone runs the second step.
- **Fix:** After the replay, rebuild_graph should call backfill_layer2(rebuild=True), with the fix from l3-rebuild-deletes-situations-and-ids applied first. Otherwise it should also wipe context_correlation*, context_situations and open_loops and re-derive them. files_for should report dropped anchors instead of skipping them silently.
- **Depends on:** [l3-rebuild-deletes-situations-and-ids](#l3-rebuild-deletes-situations-and-ids)
- **Verified:** confirmed by the skeptic (Verified. _GRAPH_TABLES lists exactly the 8 graph tables (scripts/rebuild_graph.py:59-60). The script wipes them plus l2_processing_runs (:176-180). Nodes are re-minted with new_id('node') (graph_store.py:470). Thread-first inheritance applies (correlation.py:325-328, :340-363). files_for skips anchors that have no live node (workstreams.py:474-475). The re-derive route is POST /api/org/{org_id}/situations/backfill?rebuild=true (situation_routes.py:133, :154), and the script never calls or names it. graph_aliases is not in _GRAPH_TABLES either, so name and email aliases survive pointing at wiped node ids. I did not trace what that does.)

<a id="l3-thread-inherits-reading-correlations"></a>
### Thread inheritance reads reading-declared memberships: a reply can join a reading's synthetic correlation and no file, and the backfill and the 'filed' health check count those events as filed

`l3-thread-inherits-reading-correlations` · **P1** · broken · owner **claude** · code · step **S14**

- **Expected:** Under-correlate rather than over-correlate, but never lose an event from its conversation. Only the correlation engine owns membership of real correlations. _(source: genios_engine/context/correlation.py:1-50 (module law); genios_engine/context/correlation_membership.py:92-98 ('a reading only claims its own correlation'))_
- **Actual:** Readings write context_correlation_members rows under synthetic ids (joined_via='reading'). thread_correlations returns every correlation id with a member in the thread and does not check that a context_correlations row owns it. If that list has one id, _the_parties_files returns it unchanged and the new event joins only that id. The id is synthetic, so the event is in no file, because files join context_correlations. If the list has several ids and the reply touches none of their anchors, the reply also joins every reading correlation. The non-rebuild backfill skips any event already in context_correlation_members, and _NAMED_MAIL counts any membership as 'filed'.
- **Evidence (measured):** genios_engine/context/correlation_membership.py:126-130 (insert members, joined_via 'reading'); callers outreach_situations.py:1875, support_situations.py:1606, meeting_touch.py:243, document_register.py:580; genios_engine/context/correlation.py:358-363 (no ownership/joined_via filter), :592-599 (one id returned as-is; none touched keeps all), :632-638 (joins inherited ids only); `genios_engine/context/workstreams.py:162-169 (_MEMBERS joins context_correlations: synthetic ids are no file)`; `genios_engine/context/backfill.py:143-144 (skips any already-member event)`; `genios_engine/context/workstreams.py:230-233 (_NAMED_MAIL filed = any membership)`
- **What Rohit sees:** A reply that belongs in an investor's file lands in none, and L2 judges it as a contextless seed ('no correlation').
- **Where the mistake was:** The declare_finding_events wiring (added to feed gather_l1_signals) put reading rows into the table that thread inheritance reads as conversation identity. This is the 'absence was the only guard' family.
- **Fix:** In thread_correlations, the backfill skip and _NAMED_MAIL, count only engine-owned ids: join context_correlations, or filter joined_via <> 'reading'. Add a PG test where a reading declared the only earlier event of a thread and assert that the reply joins the counterparty's file.
- **Blocked on:** Production read to size it: select count(*) from context_correlation_members m where m.org_id='<rohit_org>' and m.joined_via='thread' and not exists (select 1 from context_correlations c where c.org_id=m.org_id and c.correlation_id=m.correlation_id); and: select count(*) from (select m.event_id from context_correlation_members m left join context_correlations c on c.org_id=m.org_id and c.correlation_id=m.correlation_id where m.org_id='<rohit_org>' group by m.event_id having bool_and(c.correlation_id is null)) x;
- **Verified:** confirmed by the skeptic (Verified. declare_finding_events inserts members with joined_via='reading', and only for ids no context_correlations row owns (correlation_membership.py:116-130). thread_correlations has no ownership or joined_via filter (correlation.py:358-363). _the_parties_files returns a single id unchanged (:578-579). With several ids, it keeps every id, reading ids included, when no owned anchor was touched (:580-585). Every inherited id gets a member (:632-638). _MEMBERS joins context_correlations, so synthetic ids are no file (workstreams.py:162-169). The backfill skips any event that is already a member (backfill.py:~141-142). _NAMED_MAIL counts any membership as filed (workstreams.py:230-233).)

<a id="l3-failed-pass-visibility"></a>
### A failed L3 pass now appears in the sweep's return but only in an INFO log line, and the first derived pass can still take six passes down with it

`l3-failed-pass-visibility` · **P2** · partial · owner **claude** · code · step **S17**

- **Expected:** A failed pass is never a quiet sweep, with one boundary per pass. _(source: commit 7297b31a; genios_engine/context/runner.py:800-811)_
- **Actual:** failed_passes goes onto the stage dict and is printed by stage_timer's log line only: no funnel row, no alert. compute_derived and compute_deal_view sit inside the outer try only. If either fails, the account view, waiting, periodic, support, meeting touch, the first outreach pass and the document register are all skipped for that sweep.
- **Evidence (measured):** `genios_engine/api/routes.py:803-804`; `genios_engine/platform/stage_timer.py:58`; `genios_engine/context/runner.py:828-837, :922-924`
- **What Rohit sees:** Stale waiting days and missing support, period and meeting cards for a sweep, with nothing visible.
- **Fix:** Wrap compute_derived and compute_deal_view individually, and write failed_passes to the funnel or ops_alert.
- **Verified:** confirmed with a correction by the skeptic: The structure holds. failed_passes becomes only a count on the stage dict (routes.py:803-804), printed by stage_timer's INFO line (stage_timer.py:58). It has no funnel row, and failed_passes has no other reader (grep finds only runner.py:1762 and routes.py:804). compute_derived and compute_deal_view sit inside the outer try only (runner.py:828-838, outer except :922-924), so their failure skips account view, waiting, periodic, support, meeting touch, the first outreach pass and the document register. One detail is wrong: the failure is not only an INFO line. Each failed pass is also logged at ERROR with its traceback, through get_logger('genios.l2').exception; _PassFailures captures exactly those records (runner.py:665-698). There is no Sentry or other alert hook in genios_engine (grep for sentry_sdk finds nothing).

<a id="l3-interpretations-decision-object-write-only"></a>
### What L3 records of an admitted judgment, including the decision object, is write-only, and its outcome column holds a different vocabulary

`l3-interpretations-decision-object-write-only` · **P2** · built, not live · owner **claude** · code · step **S24**

- **Expected:** L3 records the DecisionObject without reasoning, and L4 reads it. _(source: GeniOS-008/00-ARCHITECTURE.md:48; 02-MIGRATION-PLAN.md L3-4; f3cfd3c6 message ('no reader yet — L4's'))_
- **Actual:** record_interpretations appends to situation_interpretations, which table_coverage declares write-only. The decision object is an untyped JSON dict with no reader. The outcome column (documented as accept|unknown|escalate|refuse in 0183) receives op values instead (create, update, unchanged, close). Nothing is written unless l2_reasoning is on.
- **Evidence (measured):** `genios_engine/context/l2_admission.py:141-196`; `genios_engine/platform/table_coverage.py:133-141`; `migrations/0183_situation_interpretations.sql (outcome comment)`; `genios_engine/reason/l2/sweep.py:177`
- **Where the mistake was:** f3cfd3c6 added a writer to a table already declared write-only, with no reader.
- **Fix:** Type the DecisionObject (L0-2), give it the L4 reader, and either align the outcome column or use a column of its own.
- **Depends on:** [l3-l2-admissions-shadow-status](#l3-l2-admissions-shadow-status)
- **Verified:** confirmed by the skeptic (Verified. record_interpretations appends with outcome = adm.op (l2_admission.py:176-196). The decision is an untyped dict inside proposal (:157-165). 0183 documents accept|unknown|escalate|refuse and has no check constraint, so op values are accepted. No select from situation_interpretations exists in genios_engine/ or scripts/. The write is gated by l2_reasoning (sweep.py:177). table_coverage.py:133-141 still names context/interpretation_store.py as the writer, but the live writer is now l2_admission.record_interpretations; interpretation_store's caller was retired with R-6 (context_health.py:115). The 'write-only' declaration is right, but the module it names is stale.)

<a id="l3-layer-names-in-code"></a>
### The chain's stage names and loggers still use the old layer numbering: L3 work is logged as 'l2', and the L2 judgment is staged as 'l4'

`l3-layer-names-in-code` · **P2** · partial · owner **claude** · code · step **S17**

- **Expected:** Speak the product layer vocabulary: L1 capture, L2 reason/packs, L3 context, L4 executive. _(source: memory speak-the-product-layer-vocabulary.md; GeniOS-008/00-ARCHITECTURE.md:44-52)_
- **Actual:** stage('l2.process_pending') is used for context/. reason.runner.run_all is imported as run_l3 and staged 'l4.run_all'. Every context pass logs on 'genios.l2', and _PassFailures listens there.
- **Evidence (measured):** `genios_engine/api/routes.py:798, :821-822`; `genios_engine/context/runner.py:684, :850, :862`
- **Fix:** Rename the stages and loggers to the GeniOS-008 layers, keeping old aliases where log alerts depend on them.
- **Verified:** confirmed by the skeptic (Verified. stage('l2.process_pending') is at routes.py:798. 'run_all as run_l3' and stage('l4.run_all') are at :821-822. _PassFailures listens on logging.getLogger('genios.l2') (runner.py:684, :696). The passes log on get_logger('genios.l2') (e.g. :850, :862).)

<a id="l3-model-call-and-clock-values-in-l3"></a>
### L3 still calls a model every sweep (resolution detection) and still recomputes clock-relative values and rewrites every situation row each sweep

`l3-model-call-and-clock-values-in-l3` · **P2** · partial · owner **claude** · code · step **S17**

- **Expected:** L3 makes no model calls. Values computed against 'now' become L2 tools on the snapshot, which ends the every-sweep rewrite. _(source: GeniOS-008/00-ARCHITECTURE.md:48 (L3 model: none); 02-MIGRATION-PLAN.md L3-5, L3-7)_
- **Actual:** detect_resolutions makes an llm.call per unexamined message, called from process_pending with the chain's client. compute_waiting(now) and the readings run every sweep. ae5b5c7a and 34779fe0 stopped rewriting unchanged derived facts and receipts, but the situation upserts still update every row unconditionally (computed_at), and the importance pass UPDATEs every situation every sweep.
- **Evidence (measured):** `genios_engine/context/lifecycle/resolution.py:232 llm.call`; `genios_engine/context/runner.py:1087-1089, :857-863`; `genios_engine/context/situations.py:1237-1259 (no change guard)`; `genios_engine/context/situation_bso.py:1963 (_STORE_IMPORTANCE per situation)`
- **Fix:** Move resolution into L2 (L2-12). Add a value-moved guard to the situation upserts and the importance update. Move days-waiting and ages into L2 tools.
- **Verified:** confirmed by the skeptic (Verified. detect_resolutions calls llm.call per unexamined message that passes the gate (lifecycle/resolution.py:232). It is bounded by per-situation and per-org daily call caps and MAX_ATTEMPTS_PER_MESSAGE (:190-208), and is called from process_pending with the chain's llm (runner.py:1087-1089). compute_waiting runs every sweep (runner.py:857-859). ae5b5c7a and 34779fe0 cover derived facts and receipts only. refresh_situations' on-conflict update has no WHERE or change guard and always sets computed_at (situations.py:1237-1259). support _upsert does the same (support_situations.py:1680-1700). _STORE_IMPORTANCE updates every non-archived situation each sweep (situation_bso.py:1954-1963).)

<a id="l3-name-only-joins"></a>
### Identity: the exact-key law holds in identity.py, but readers join by name around it, and ambiguity is never shown

`l3-name-only-joins` · **P2** · partial · owner **claude** · code · step **S15**

- **Expected:** Exact key equality is the only auto-merge. An ambiguous name resolves to nobody. Identity keeps its candidates (resolve_alias_candidates, wired). _(source: genios_engine/context/identity.py:1-32; 02-MIGRATION-PLAN.md L3-6)_
- **Actual:** pipeline._business_subject matches lower(display_name)=name and takes the single row, bypassing alias contention. correlation_people.load_directory reads person_name aliases without excluding origin='contended', so resolve() can award a contended name to its first claimant, which resolve_alias refuses. The pipeline comment at :1576-1580 says same-name people resolve to the first holder (stale; the code refuses). resolve_alias_candidates has no caller.
- **Evidence (measured):** `genios_engine/context/pipeline.py:599-616`; `genios_engine/context/correlation_people.py:179-183, :205-206`; `genios_engine/context/identity.py:276-279`; `genios_engine/context/pipeline.py:1576-1580`; `genios_engine/context/context_health.py:58-60`
- **What Rohit sees:** Occasionally a fact or commitment is attached to the wrong same-named person (team situations, business facts).
- **Where the mistake was:** 02-MIGRATION-PLAN.md L3-6 says 'wired'; it is not.
- **Fix:** Route the name lookups through resolve_alias, exclude contended aliases in load_directory, fix the comment, and surface candidates where a merge or disambiguation UI exists. Correct 02-MIGRATION-PLAN L3-6.
- **Verified:** confirmed by the skeptic (Verified. _business_subject matches lower(canonical_key) or lower(display_name) and returns the single row; it refuses 2+ but never consults alias contention (context/pipeline.py:599-616). load_directory reads person_name aliases with no origin filter (correlation_people.py:202-206), and resolve() awards on one hit (:179-183). resolve_alias excludes origin='contended' (identity.py:276-279), and resolve_person_name goes through it (:340-355). The comment at pipeline.py:1576-1580 ('resolves to the first-anchored holder') contradicts identity.py:347-350. resolve_alias_candidates has no caller.)

<a id="l3-nine-situation-writers-and-missing-ratchet"></a>
### The 9 sweep writers that form situations before reasoning are all live, and the CI ratchet that should only let that list shrink does not exist

`l3-nine-situation-writers-and-missing-ratchet` · **P2** · missing · owner **claude** · code · step **S04**

- **Expected:** The list of places in context/ that create or refresh a situation can only shrink, and a new site turns CI red (the ratchet starts at 9). _(source: GeniOS-008/01-RULES.md:36-37 (Rule 3.2); 02-MIGRATION-PLAN.md L0-5, L3-2)_
- **Actual:** The nine writers: (1) situations.refresh_situations, def situations.py:1086, insert :1222, called runner.py:1042. (2) situations.age_uncorrelated_situations, def :1033, update :1019, called runner.py:1058. (3) support_situations.refresh_support_situations, def :1538, insert :1674, called runner.py:882. (4) outreach_situations.refresh_state_situations, def :1782, writes through support_situations._upsert (imported :59-64, call :1903), called runner.py:906 and again in the second pass at runner.py:1681. (5) periodic.refresh_period_situations, def :170, insert :222, called runner.py:870. (6) meeting_touch.refresh_channel_touch_situations, def :186, insert :251, called runner.py:893. (7) document_register.refresh_document_situations, def :523, insert :631, called runner.py:917. (8) situation_bso.refresh_situation_importance, def :1969, update :1963, called runner.py:1466 and again at runner.py:1707. (9) lifecycle/store.apply_lifecycle, def :319, update :331, called lifecycle/resolution.py:294 via runner.py:1088. Writers outside the list: merge.py:165/174/450, backfill.py:133-135/405, situations.resolve_situation :1330 (API), and each reading's _reconcile. The existing guards pin only the five modules that INSERT; a new writer that calls _upsert (as outreach does) or UPDATEs would pass.
- **Evidence (measured):** `genios_engine/context/runner.py:870, :882, :893, :906, :917, :1042, :1058, :1088, :1466, :1681, :1707`; `tests/context/test_situation_importance.py:512-547 (_KNOWN_SITUATION_WRITERS, 5 INSERT modules)`; `tests/context/test_l2_must_not_regress.py:547-548 (SITUATION_WRITERS, 5)`
- **What Rohit sees:** None directly. Without the ratchet, the migration to 'L2 proposes, L3 admits' can regress silently.
- **Fix:** Add a guard listing the nine call sites, using AST qualified calls rather than text, and failing on any new create/refresh call or UPDATE of context_situations. Shrink the list by one per switched type.
- **Verified:** confirmed by the skeptic (All def, insert, update and call lines match: runner.py 870, 882, 893, 906, 917, 1042, 1058, 1088, 1466, 1681, 1707. Also situations.py:1019 _SET_STATUS, :1222 insert; lifecycle/store.py:319/:331; resolution.py:294 apply_lifecycle. The outreach writer imports _upsert from support_situations (outreach_situations.py:59-62, :1903). The guards are text greps for 'insert into context_situations' over 5 modules (tests/context/test_situation_importance.py:511-547; test_l2_must_not_regress.py:547-548). No test pins UPDATE writers or callers of _upsert, and no ratchet of 9 exists.)

<a id="layer-l4"></a>
## L4 Executive (executive/)

> I read the code at 0cc8d83c and the dashboard at origin/main 2edfb86. I did not read production.
> 
> What works: the card plumbing is sound. GET /cards reads through three doors: decision, team/verify situation, and question. GET /cards/{id} returns the full row plus context, actionability, the decision projection and annotated actions. The action route takes Done, Later, Wrong (with the founder's words and a scope) and Answer. Your words are kept, and the next expert/L2 review reads them. Every Wrong reason a card offers is now storable (migration 0210). Six of the eight live bugs from 4 Oct are fixed in the code (1, 2, 3, 4, 5, 7). Bug 6 is closed only according to an earlier note, and bug 8 is half verified. The web Cards page with Answer and Feedback is merged into dashboard main; the 06-CARDS README still says it is not merged.
> 
> What does not work against Rohit's card contract:
> - No brain change C1 to C8 is built. There is no card writer (no deliver/card_copy.py, no cards.copy column), so the subject is the expert's move cut at 60 characters, or a formula template, or the l5_render model line. On review-level cards a "Needs a decision —" prefix leaves only 41 characters for the body.
> - The queue row carries 13 fields, not the face's two lines.
> - The expert's "if you act now" (scenarios.act) never reaches the card. An expert card has no steps (How), and formula cards get stock steps.
> - Context is person-level (the subject's last 4 meetings and 3 promises), and several stock sentences repeat, so cards read the same.
> - Quotes carry no sender or date.
> - There is no goal anywhere.
> - There is no person-delegate route. Card-scoped agent delegation already exists (POST /v1/delegations with card_id, and /v1/insights/{id}/handoff), but the client must supply a typed play and its params, and the dashboard keeps Delegate locked.
> - There is no "this is right" verdict.
> 
> The Mac app still offers Done on question cards and sends Wrong with no reason. The server refuses both with a 422, the app swallows the error, and the card comes back, so those presses never reach learning.
> 
> L4 still auto-plans executions from every authoritative signal on each heartbeat. The DecisionObject that L3 writes goes into situation_interpretations, which nothing reads. No human decides first.
> 
> Delivery is pull-only. Slack is the only push adapter, the dashboard has no screen to set it up, and provisioning registers only in_app. So the STEP-15 kept brief and the L4 reminders reach no one, and the dashboard reads an older brief route instead.
> 
> L6 runs, but its outputs stay internal. learning_metrics, human_events and card_feedback_revisions have no reader. Learning transitions, evaluations and rejections are read only by count receipts. Calibration runs in shadow and its would-mute results are seen by nobody. The inbox's moment feedback is loaded and dropped. Human-review learning objects have no screen. macv_ledger and AER are still empty.
> 
> Plan problem: GeniOS-009 G6 would serve the goal board on GET /v1/insights?group=goal. The Cards page reads /cards, and the only dashboard reader of /v1/insights (decision-inbox) is not mounted.

| Item | Sev | Status | Owner | Step |
|---|---|---|---|---|
| [L4 auto-plans executions from every authoritative signal on each heartbeat; the DecisionObject is written to a](#l4-auto-plans-no-human-decides) | P1 | missing | claude | S32 |
| [GeniOS-008 B1/B2: no human approval before work is planned; plan_commitments turns every authoritative decisio](#l4-b1-b2-human-approval-before-planning-missing) | P1 | missing | claude | S32 |
| [R-1 model decider: GENIOS_L4_LLM_DECISION_MAKER defaults off, but it was on in production on 1 Oct, which DEFE](#l4-llm-decision-maker-env) | P1 | unknown until production is read | harsh | S02 |
| [Half of planned actions require approval but nothing can name the approver; there is no engine writer for org ](#l4-approver-and-org-data-writer) | P2 | missing | claude | S32 |
| [The STEP-15 kept morning brief has no reader on any surface; the dashboard reads an older brief built only fro](#l4-morning-brief-unreached) | P2 | built, not live | claude | S36 |

<a id="l4-auto-plans-no-human-decides"></a>
### L4 auto-plans executions from every authoritative signal on each heartbeat; the DecisionObject is written to a table nothing reads; no human decides first

`l4-auto-plans-no-human-decides` · **P1** · missing · owner **claude** · code · step **S32**

- **Expected:** L4's input is a DecisionObject that a human decides (approve, reject, defer, choose). Only an approved choice becomes an ExecutionObject carrying goal_refs and decision_request_id. Auto-planning from signals stops (human_decides per tenant). _(source: speedrun008/GeniOS-008/00-ARCHITECTURE.md 'The layers' L4 row; 02-MIGRATION-PLAN.md §1 'L4 input … REPLACE' and §3.4 L4-1; GeniOS-009 STEP-G8 §2)_
- **Actual:** api/routes.py heartbeat calls run_executive for every org. plan_commitments turns each row of _PLANNABLE_SIGNALS into an execution with resolve_owner, with no human step. execution.v1 has goal: str and no goal id. None of these exist: executive/decisions.py, api/decision_routes.py, a decision_requests migration, a human_decides feature, context/checkin.py. L3's DecisionObject ({needed, who, what, by_when}) is written inside situation_interpretations.proposal, and that table is declared in UNREAD_WRITES ('nothing selects from it').
- **Evidence (measured):** `genios_engine/api/routes.py:1512-1547`; `genios_engine/executive/sweep.py:173-238,483-493`; `genios_engine/contracts/execution.py:385 (goal: str)`; `genios_engine/context/l2_admission.py:141-167 (decision inside the interpretation)`; `genios_engine/platform/table_coverage.py UNREAD_WRITES['situation_interpretations']`; `ls executive/decisions.py api/decision_routes.py context/checkin.py → No such file`
- **What Rohit sees:** Commitments and reminders exist that no person chose. A decision card has no owner or decider and no link from Rohit's choice to the work.
- **Fix:** Build GeniOS-009 STEP-G8: migration decision_requests, contracts/decision.py, executive/decisions.py (open_requests_from_interpretations reading situation_interpretations, then decide, then to_execution), the human_decides feature in l4_activation, and the plan_commitments skip. Add GET/POST /v1/decisions and the record_result → reported_complete hook. Rohit switches human_decides on per tenant.
- **Depends on:** [goals-c8-no-goal-on-card](#goals-c8-no-goal-on-card)
- **Verified:** confirmed by the skeptic (The heartbeat calls run_executive for each org in _executive_orgs, meaning every org with an active tenant_pack (routes.py:1517-1535, 1674-1687). No l4_activation feature gates it. plan_commitments goes from _PLANNABLE_SIGNALS through resolve_owner to build_execution and store.persist, with no human step (sweep.py:74-95, 173-238). run_executive is at sweep.py:483-493. execution.v1 has goal: str (contracts/execution.py:385). executive/decisions.py, api/decision_routes.py and context/checkin.py do not exist. No 'decision_request' or 'human_decides' appears in genios_engine or migrations. interpretation_of puts the decision {needed, who, what, by_when} in the interpretation (l2_admission.py:141-167, insert at 168-169). No code or script SELECTs from situation_interpretations, and it is listed in UNREAD_WRITES (table_coverage.py:133-140).)

<a id="l4-b1-b2-human-approval-before-planning-missing"></a>
### GeniOS-008 B1/B2: no human approval before work is planned; plan_commitments turns every authoritative decision into a commitment

`l4-b1-b2-human-approval-before-planning-missing` · **P1** · missing · owner **claude** · code · step **S32**

- **Expected:** For the decision lane a human (Rohit, the only approver; Harsh a seat without approval rights) approves before any work is planned. Monitor and investigation need no approval. _(source: speedrun008/GeniOS-008/03-QUESTIONS.md B1, B2; GeniOS-009 STEP-G8 ('for that tenant plan_commitments plans nothing'))_
- **Actual:** plan_commitments: 'Turn every authoritative, uncommitted decision for this org into a commitment.' There is no approval gate. `human_decides` / decision_requests (G8, migration 0254) do not exist.
- **Evidence (measured):** `genios_engine/executive/sweep.py:173-176`; `grep 'human_decides|decision_requests' in genios_engine and migrations: 0 hits`
- **What Rohit sees:** Work can be planned from a decision Rohit never approved. The card's 'decide' step is not a real gate.
- **Fix:** Build GeniOS-009 G8 behind the `human_decides` switch: a decision-lane card requests approval, and plan_commitments plans only approved ones. B2's approver list comes from the company brief.
- **Depends on:** [goals-g009-d1-d2-d8-goal-model-defaults-unbuilt](#goals-g009-d1-d2-d8-goal-model-defaults-unbuilt)
- **Verified:** confirmed with a correction by the skeptic: There is no approval gate before planning, but approval does exist at the step level. contracts/execution.py:229-231 `autonomous_allowed` returns False when requires_approval is set, and executive/interpret.py:57-64 maps execution_boundary 'human_approval_required' and approval tags to a human gate. That only stops a machine from executing a planned step; the commitment is still planned. Nothing resolves WHO approves: assignment.resolve_approver_seat has no production caller (executive/unreached.py:127-140). So B1 (Rohit approves before work is planned) and B2 (Rohit as the only approver) are both unbuilt.

<a id="l4-llm-decision-maker-env"></a>
### R-1 model decider: GENIOS_L4_LLM_DECISION_MAKER defaults off, but it was on in production on 1 Oct, which DEFERred every decision; current production value unknown

`l4-llm-decision-maker-env` · **P1** · unknown until production is read · owner **harsh** · prod_action · step **S02**

- **Expected:** L4 never lets a model decide; the model only words things. _(source: speedrun008/GeniOS-008/00-ARCHITECTURE.md layer table (L4 'Never: a model deciding'); 02-MIGRATION-PLAN.md §1 'llm_decision_maker … REPLACE')_
- **Actual:** config.l4_llm_decision_maker = False by default, with an org allow-list. receipts.py says production ran with it on on 2026-10-01 while the spend limit refused every call, so every decision became DEFER and no cards came out. The code still exists (reason/llm_decision_maker.py).
- **Evidence (mixed):** `genios_engine/platform/config.py:110-111`; `genios_engine/platform/receipts.py:355-358`
- **What Rohit sees:** If on with refused calls, decisions DEFER and cards disappear.
- **Fix:** Harsh confirms the production env has GENIOS_L4_LLM_DECISION_MAKER unset or false. Per the migration plan, retire the model-decides path (REPLACE).
- **Blocked on:** Harsh: read the production env for GENIOS_L4_LLM_DECISION_MAKER and GENIOS_L4_LLM_DECISION_MAKER_ORGS (env, not .env file contents shared here).
- **Verified:** confirmed by the skeptic (config.py:110-113: l4_llm_decision_maker=False and an orgs allow-list (empty with the switch on means every org), with a 400 calls/org/day cap. receipts.py:355-358 records that on 2026-10-01 GENIOS_L4_LLM_DECISION_MAKER=true and the spend limit together produced DEFER; this is a doc_claim. The code is wired: llm_decision_maker.py:124-127 checks the switch, and it is imported by decision_maker.py:1123, orchestrator.py:263 and llm_interpretation.py. The current production value is unverifiable from the repo. Harsh can read the deploy env, or a read-only proxy: select org_id, date_trunc('day',created_at) d, count(*) from llm_costs where purpose='l4_llm_decision' and created_at > now() - interval '14 days' group by 1,2 order by 2;)

<a id="l4-approver-and-org-data-writer"></a>
### Half of planned actions require approval but nothing can name the approver; there is no engine writer for org data (seats, reports_to, responsibilities)

`l4-approver-and-org-data-writer` · **P2** · missing · owner **claude** · code · step **S32**

- **Expected:** execution.v1 carries an approver (resolve_approver_seat), and a writer fills org data at onboarding and from the company brief. _(source: speedrun008/GeniOS-008/02-MIGRATION-PLAN.md §3.4 L4-2, L4-3)_
- **Actual:** receipts.py records production on 2026-10-01: 410 of 794 execution_actions have requires_approval, authority_rules has 0 rows, and resolve_approver_seat returns None every time. A grep finds no INSERT into seat_responsibilities in genios_engine; the only mention is the account delete list.
- **Evidence (mixed):** `genios_engine/platform/receipts.py:255-275 (measured note 2026-10-01)`; grep 'insert into seat_responsibilities' genios_engine → none; genios_engine/api/account_routes.py:748-753 (delete list only)
- **What Rohit sees:** A card or execution that 'needs sign-off' cannot say whose.
- **Fix:** Build L4-3: a writer for seat responsibilities and reports_to from onboarding and from accepted company-brief lines, owner-confirmed. Build L4-2: resolve the approver from it, and say 'no approver named' on the card rather than nothing.
- **Blocked on:** Read-only: select count(*) filter (where requires_approval) as gated, count(*) from execution_actions where org_id=:org; select count(*) from authority_rules where org_id=:org;
- **Verified:** confirmed with a correction by the skeptic: Two details. (1) resolve_approver_seat does not 'return None every time'; it has no caller. It is defined at executive/assignment.py:479, has no call site in genios_engine, and is declared unreached in executive/unreached.py:128 ('nothing ever resolves WHO must sign'). (2) authority_rules does have an engine writer. feedback/org_rule_ingest.py:331-345 (_AUTHORITY_UPSERT, executed at ~404) publishes approval rules from active organization-brain entries (learned_brain_entries subject like 'org_rule:approval:%'). It skips entries with no approver (authority_pending). That path depends on human-approved org-rule proposals, and those have no review surface (see l6-human-review-no-surface).

<a id="l4-morning-brief-unreached"></a>
### The STEP-15 kept morning brief has no reader on any surface; the dashboard reads an older brief built only from decision-door cards

`l4-morning-brief-unreached` · **P2** · built, not live · owner **claude** · code · step **S36**

- **Expected:** The morning brief is an L5 surface the founder reads, and it reads executions and decisions too. _(source: speedrun008/GeniOS-008/02-MIGRATION-PLAN.md §2 (STEP-15 → L5 surface) and §3.4 L4-5)_
- **Actual:** executive/morning.compose (STEP-15) is served at GET /morning and /morning/{day}, and is the digest payload. No dashboard or Mac code calls /morning. The dashboard's Today card calls /api/org/{org}/morning-brief, which is workspace_routes.build_morning_brief, a different implementation that joins AUTHORITATIVE_SIGNAL_PREDICATE only. So it misses question cards and situation cards. The digest needs a push channel, which does not exist (l5-delivery-only-in-app).
- **Evidence (measured):** `genios_engine/api/executive_routes.py:129-168`; `genios_engine/api/workspace_routes.py:243-275`; `genios_engine/api/intelligence_routes.py:1233-1237`; `genios_engine/deliver/outbox.py:315-329,800-815`; `dashboard origin/main src/lib/api.ts:2424 (only /api/org/{orgId}/morning-brief)`
- **What Rohit sees:** Two different briefs exist, and the one STEP-15 built and checked is seen by nobody.
- **Fix:** Pick one brief. Either point the dashboard Today card and the Mac app at GET /morning (the kept STEP-15 brief, with line marks), or make build_morning_brief read the kept brief. Retire the other.
- **Depends on:** [l5-delivery-only-in-app](#l5-delivery-only-in-app)
- **Verified:** confirmed with a correction by the skeptic: The STEP-15 routes are under the router prefix /v1/executive (executive_routes.py:26): GET /v1/executive/morning (line 129), GET /v1/executive/morning/{day} (line 157) and POST /v1/executive/morning/lines/{line_id}/mark (line 170). They are not served at bare /morning.

<a id="layer-l5"></a>
## L5 Delivery (deliver/)

| Item | Sev | Status | Owner | Step |
|---|---|---|---|---|
| [YC-II STEP-18 B15 / F280: the card says 'they normally reply in about N days' even when N is the firm's, the t](#l5-b15-reply-cadence-wording-ignores-basis) | P1 | broken | claude | S23 |
| [GeniOS-008 B3: a card or reminder cannot reach Rohit by email; there is no email transport](#l5-b3-email-delivery-channel-missing) | P1 | missing | claude+harsh | S37 |
| [C2 partial: the expert's done_when reaches success_signal, but scenarios.act ('if you act now') never reaches ](#l5-c2-act-not-carried) | P1 | partial | claude | S34 |
| [C5: there is no route to delegate a card to a person; agent delegation of a card exists but needs a client-bui](#l5-c5-delegate-route) | P1 | partial | claude | S35 |
| [C6 unbuilt: card context is the subject node's last 4 meetings and 3 promises, plus stock sentences, so detail](#l5-c6-person-level-context) | P1 | missing | claude | S34 |
| [Rohit's binding card contract vs what GET /cards and GET /cards/{id} return, field by field](#l5-card-contract-vs-routes) | P1 | partial | claude | S34 |
| [Cards read thin, repeated or garbled on every surface: the card writer (C1), the expert's result (C2) and per-](#l5-card-writer-c1-c2-c6-unbuilt) | P1 | missing | claude | S34 |
| [Delivery is pull-only: provisioning registers only in_app, Slack is the only push adapter and has no dashboard](#l5-delivery-only-in-app) | P1 | missing | claude+harsh | S37 |
| [Fewer cards since 18 Oct: L5's own drop paths are recorded but have no surface, and production was not read](#l5-fewer-cards-refusals-unmeasured) | P1 | unknown until production is read | rohit+harsh | S01 |
| [Post-meeting follow-up cards ('meeting.followup') fail all three card doors: never on GET /cards, and 'Open ca](#l5-meeting-followup-cards-fail-every-door) | P1 | broken | claude | S36 |
| [Question cards: brain and web Cards page are correct; the Mac app offers Done (422 not_offered, swallowed) and](#l5-question-card-answer) | P1 | partial | claude | S38 |
| [No card writer (C1): the subject is a clause cut of the model's move, a pack template, or the l5_render line; ](#l5-subject-writer) | P1 | missing | claude | S34 |
| [The Mac app's 'Not useful' sends 'wrong' with no reason; the brain refuses it (422 invalid_wrong_reason) and t](#l5-wrong-without-reason) | P1 | broken | claude | S38 |
| [C3 unbuilt: the queue lacks what the list draws, so the dashboard makes up to 40 detail calls, each with N+1 g](#l5-c3-queue-fields) | P2 | missing | claude | S35 |
| [C4 unbuilt: quotes on a card are bare strings with no sender or date](#l5-c4-quote-sender-date) | P2 | missing | claude | S35 |
| [C7 unbuilt: no 'this is right' verdict; the action set has 'wrong' and nothing positive](#l5-c7-no-right-verdict) | P2 | missing | claude | S35 |
| [C9 and version: the brain keeps each version's words and change, but the dashboard counts only card.rebuilt an](#l5-version-count-dashboard) | P2 | partial | claude | S35 |

<a id="l5-b15-reply-cadence-wording-ignores-basis"></a>
### YC-II STEP-18 B15 / F280: the card says 'they normally reply in about N days' even when N is the firm's, the tenant's or a floor

`l5-b15-reply-cadence-wording-ignores-basis` · **P1** · broken · owner **claude** · code · step **S23**

- **Expected:** The card's cadence line states whose normal it is. The basis fact exists exactly to stop that overclaim. _(source: speedrun008/YC-II W27/STEP-18-TO-BUILD-known-bugs.md B15 ('left — s18-F10, the lead's'); 03-FINDINGS.md F280)_
- **Actual:** context/outreach_situations writes outreach.their_normal_reply_basis, but deliver/slots.py fills their_cadence from the number alone and never reads the basis. The Admin template renders 'they normally reply in about {their_cadence} days'.
- **Evidence (measured):** `genios_engine/context/outreach_situations.py:712-719 (basis written)`; `genios_engine/deliver/slots.py:212 (cadence read without basis)`; `grep their_normal_reply_basis: only the writer at outreach_situations.py:719`; Domain Expertise/Admin Expertise/capabilities/01-executive-support/inbox-and-correspondence/situations/outbound-awaiting-reply.yaml:145
- **What Rohit sees:** Awaiting-reply cards assert a personal reply habit that was never measured for that person, which is part of the 'weird' wording.
- **Where the mistake was:** The basis was added as a write-only fact with no reader.
- **Fix:** Claude adds a `their_cadence_basis` slot. The template says 'they' only on a person basis, 'people at <firm>' on a firm basis, and drops the clause on tenant/floor. Re-record golden F55's narrator answer (ideal reader).
- **Verified:** confirmed by the skeptic (context/outreach_situations.py:712-719 writes outreach.their_normal_reply_basis from party.reply_cadence_basis, whose levels are person/firm/tenant/floor (context/waiting.py:287-290). deliver/slots.py:212 reads the cadence number only, and :255 fills their_cadence from it. A grep for their_normal_reply_basis finds only the writer. outbound-awaiting-reply.yaml:145 renders 'they normally reply in about {their_cadence} days'. Seven template lines in Domain Expertise use their_cadence.)

<a id="l5-b3-email-delivery-channel-missing"></a>
### GeniOS-008 B3: a card or reminder cannot reach Rohit by email; there is no email transport

`l5-b3-email-delivery-channel-missing` · **P1** · missing · owner **claude+harsh** · mixed · step **S37**

- **Expected:** Beyond the in-app view, cards and reminders reach Rohit by email to <founder Gmail> first, Slack later. _(source: speedrun008/GeniOS-008/03-QUESTIONS.md B3)_
- **Actual:** The channel registry has exactly two transports, slack (webhook) and agent_push. There is no email adapter, so deliverable_channels can never contain email, and the 08:00 digest (the kept morning brief) can go only to Slack if one is configured.
- **Evidence (measured):** `genios_engine/deliver/channels/base.py:23-32 (get_channel: slack, agent_push, else None)`; `genios_engine/deliver/units.py:88-95 (_implemented_channels)`; `genios_engine/deliver/outbox.py:316-330 (digest payload = kept morning brief)`
- **What Rohit sees:** Nothing is pushed to Rohit outside the app. Cards and the morning brief are seen only if he opens the app.
- **Fix:** Claude adds an email channel adapter (transactional provider, recipient from the seat/owner address, never the mail body of others), registers it in get_channel, and adds org_channels 'email' for Rohit's org (Harsh).
- **Blocked on:** select channel, active, last_digest_date from org_channels where org_id='<ORG>';
- **Verified:** confirmed by the skeptic (deliver/channels/base.py:21-31 get_channel returns slack or agent_push, else None. deliver/channels/ has only agent.py, base.py and slack.py. units.py:88-95 lists 'email' in PUSH_REQUIRES_ADAPTER but _implemented_channels drops it because there is no adapter. A grep for smtp|sendgrid|GMAIL_SEND_EMAIL|send_email|postmark in genios_engine finds nothing. The digest payload is the kept morning brief (outbox.py:316-330).)

<a id="l5-c2-act-not-carried"></a>
### C2 partial: the expert's done_when reaches success_signal, but scenarios.act ('if you act now') never reaches the card

`l5-c2-act-not-carried` · **P1** · partial · owner **claude** · code · step **S34**

- **Expected:** 'What doing it gets you' shows the expert's own result, as checked words. _(source: 06-CARDS/01-INTEGRATION.md §5 C2; 02-CARD-DEFINITION.md §3.7)_
- **Actual:** The gold block holds subject, company, kind_of_work, role, why_now, what_remains, recommended, alternative, wait_or_stop and window. It has no act and no result. done_when does reach the card: _done() puts it in the play's success_events, and card_builder._play_success reads it into success_signal. When the check withheld it, the line is '{headline} — done'. ExpertReview.scenarios.act exists in the contract but is not carried, and no 'result' key exists on cards.
- **Evidence (measured):** `genios_engine/reason/expert/decide.py:323-333 (gold keys), 266-271 (_done)`; `genios_engine/contracts/expert_review.py:228-230 (Scenarios.act)`; `genios_engine/deliver/card_builder.py:225-238 (_play_success reads play_success_events)`
- **What Rohit sees:** No card says what acting gets you; the line is either 'done when' or stock.
- **Where the mistake was:** 01-INTEGRATION C2 says neither act nor done_when reaches the card. done_when does reach it, through the play's success_events, so the doc overstates the gap.
- **Fix:** Hold scenarios.act through the check (reason/expert/verify) like the other sentences. Add gold.act and have card_builder write a result field; it needs a column or should live in C1's copy. Correct the 01-INTEGRATION C2 note: done_when already reaches the card as success_signal.
- **Verified:** confirmed by the skeptic (The gold dict has exactly subject, company, kind_of_work, role, why_now, what_remains, recommended, alternative, wait_or_stop and window (decide.py:323-330). CardWords has no act field (contracts/claim_check.py:214-232). Scenarios.act exists (expert_review.py:229). It is carried only into ReasoningResult.consequences (contracts/reasoning_result.py:543-546), which goes to reasoning_results and never to cards. Additional defect: _done (decide.py:266-271) falls back to review.wait_or_stop, the RAW review field, not the checked words.wait_or_stop, when both done_when and headline are withheld. Unchecked model words can therefore reach success_events and so success_signal (decide.py:282-284 WATCH play). This contradicts _render's own rule that a withheld line is empty.)

<a id="l5-c5-delegate-route"></a>
### C5: there is no route to delegate a card to a person; agent delegation of a card exists but needs a client-built play, and the dashboard keeps Delegate locked

`l5-c5-delegate-route` · **P1** · partial · owner **claude** · code · step **S35**

- **Expected:** POST /cards/{card_id}/delegate. {to_seat}: set the assignee, write a card event and an L1 human event, owner/admin only. {agent_id}: build the play's params on the server and call delegation.create_proposal(card_id=…); the founder approves before anything runs. _(source: 06-CARDS/01-INTEGRATION.md §5 C5; GeniOS-009 STEP-G8 §1–§2)_
- **Actual:** No /cards/{id}/delegate route exists, and no route reassigns a card to another seat. The only UPDATE of cards.assignee is the builder's version write. The agent half already exists twice: POST /v1/delegations accepts card_id with play and params, and POST /v1/insights/{id}/handoff calls DLG.propose_action. Both need the client to supply a typed play and strict params, and neither builds them from the card. The dashboard has DELEGATE_LIVE = false and locked Hand over and Ask it buttons.
- **Evidence (measured):** `genios_engine/api/routes.py:5418-5606 (the /cards routes: sweep, list, history, timeline, detail, action — no delegate)`; `genios_engine/api/delegation_routes.py:42-50,85-98 (ProposeBody card_id, play, params, agent_id)`; `genios_engine/api/intelligence_routes.py:1202-1230 (handoff → propose_action)`; `genios_engine/executive/delegation.py:401-425 (create_proposal accepts card_id)`; `dashboard origin/main src/app/dashboard/cards/page.tsx:85 (DELEGATE_LIVE = false), 1232-1254`
- **What Rohit sees:** Delegate shows people and agents but cannot hand anything over.
- **Where the mistake was:** The cards analysis (memory cards-ux-analysis-22-oct) says 'the brain has no card-assign/delegate route'. That is true for people, but card-scoped agent delegation already exists at /v1/delegations, so only the server-side param building and the person half are missing.
- **Fix:** Add POST /cards/{card_id}/delegate. For {to_seat} (owner/admin only): update cards.assignee, write a human.card_action card_event with cause 'delegate', write a human_events row, and the card then appears in that seat's queue through seat_access. For {agent_id}: build the play and params from the card on the server (for example email.follow_up_draft with the card's thread and draft) and reuse executive/delegation.create_proposal(card_id=…). Then set DELEGATE_LIVE = true in the dashboard.
- **Verified:** confirmed with a correction by the skeptic: There is more than one assignee writer. Besides the version write (store.py:66 _VERSION_WORDS), insert_card's upsert sets assignee=excluded.assignee (store.py, the on-conflict clause after line 473). reason/team/emit.py:250 also updates cards.assignee when it refreshes a situation card. All three are builder-side; none is a person reassigning a card. POST /v1/executive/commitments/{id}/reassign (executive_routes.py:331) reassigns an execution, not a card.

<a id="l5-c6-person-level-context"></a>
### C6 unbuilt: card context is the subject node's last 4 meetings and 3 promises, plus stock sentences, so details repeat across cards

`l5-c6-person-level-context` · **P1** · missing · owner **claude** · code · step **S34**

- **Expected:** Every card's details and scenario are its own. Context is kept only when tied to this card's thread or evidence. _(source: 06-CARDS/01-INTEGRATION.md §5 C6; README §4; Rohit round 3–5 ('sabhi kardon ke vivaran alag-alag hon'))_
- **Actual:** _card_intelligence resolves the signal's subject_node_id and attaches _meeting_neighbors (one hop, top 4) and _commitment_neighbors (top 3) for the node, with no thread or evidence filter. Every card anchored on one node gets the same meetings and promises. These are N+1 queries, one per neighbour.

Stock sentences that repeat:
- every question card: QUESTION_SUCCESS_SIGNAL and QUESTION_DO_NOTHING;
- every expert card whose do-nothing line failed the check: DO_NOTHING_WITHHELD;
- the projection's avoid lines ('Don't mark done until the success signal is observed');
- the formula steps in _ASK_STEP;
- the play's success line (_play_success).

The dashboard hides repeats with sharedTexts/ownCard, which treats the symptom.
- **Evidence (measured):** genios_engine/api/routes.py:5225-5247 (_commitment_neighbors), 5250-5274 (_meeting_neighbors), 5317-5372 (_card_intelligence by node_id); `genios_engine/deliver/pipeline.py:238-239 (QUESTION_SUCCESS_SIGNAL, QUESTION_DO_NOTHING)`; `genios_engine/reason/expert/decide.py:350 (DO_NOTHING_WITHHELD)`; `genios_engine/api/routes.py:5029-5037 (_ASK_STEP), 5126-5131`; `genios_engine/deliver/card_builder.py:225-238 (_play_success)`
- **What Rohit sees:** 'Poora Y har card mein same': the same meetings, promises and lines on several cards.
- **Fix:** In _card_intelligence, filter meetings and commitments to the card's own thread id or to events among its why[] evidence and sentence sources. Batch the neighbour reads. Add a test that two cards on one person with different threads show different context. Replace the stock sentences with C1's per-card result; meanwhile omit them rather than repeat them.
- **Blocked on:** To confirm live cards anchor on one node: select s.subject_node_id, count(*) from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id where k.org_id=:org and k.state in ('queued','surfaced','snoozed','claimed','delivered') group by 1 order by 2 desc;
- **Verified:** confirmed by the skeptic (_card_intelligence resolves the signal's subject_node_id (routes.py:5326-5333). It then calls _meeting_neighbors (top 4) and _commitment_neighbors (top 3) with no thread or evidence filter (routes.py:5346-5347, 5225-5274). Each neighbour runs its own graph_facts query, an N+1 inside the loop. Stock repeat lines are confirmed: pipeline.py:238-239 and 314; decide.py:343 DO_NOTHING_WITHHELD; routes.py:5029-5037 _ASK_STEP and 5124-5131 stock avoid lines; card_builder.py:225-238 _play_success.)

<a id="l5-card-contract-vs-routes"></a>
### Rohit's binding card contract vs what GET /cards and GET /cards/{id} return, field by field

`l5-card-contract-vs-routes` · **P1** · partial · owner **claude** · code · step **S34**

- **Expected:** Face: a subject that is a clear action, then 1–2 lines on what to do and how. Opened: the recommendation; what · why · how; what doing it gets you; the goal it moves; the deadline; the details; where the data came from. Every card's details are its own and never repeated across cards. _(source: speedrun008/GeniOS-010/06-CARDS/README.md 'What Rohit asked' round 5; 02-CARD-DEFINITION.md §2–§3; memory cards-ux-analysis-22-oct.md 'Round 3: his card contract (binding)')_
- **Actual:** GET /cards returns 13 fields per row: card_id, signal_id, assignee, domain, urgency_band, headline, subject_node_id, situation, score, state, render_mode, created_at, expires_at (plus your_part for a seat). It does not return recommended, output_lane, why_now, actions, context_tags, version or by_when.

GET /cards/{id} returns k.* plus three more columns, context, actionability, decision, actions and screen_items. Field by field:
- Subject = headline. Clarity is not guaranteed; see l5-subject-writer.
- Two lines = recommended.what, on expert/L2 cards only; formula cards have only the projection.
- Recommendation = recommended{who,what,for_whom,by_when} plus decision.recommendation. The projection's steps are empty on expert cards (the play has no steps) and stock on formula cards.
- What = situation (the expert's reading, labelled an inference).
- Why = why_now / unresolved_item.
- How = steps (see above).
- What it gets you = success_signal (expert: done_when from the play's success_events; formula: the play's stock line) plus do_nothing_consequence. scenarios.act is absent.
- Goal: no field exists.
- Deadline = recommended.by_when, outcome_window_days, and the person-level commitments[].due_at.
- Details = business_subject, relationship_role, why[] (bare quote strings) and person-level context.
- Where the data came from = context_tags plus why[].source. This works.
- Own details: violated by person-level context and stock sentences.
- **Evidence (measured):** `genios_engine/deliver/store.py:772-788 (the three queue SELECTs)`; `genios_engine/api/routes.py:5454-5476 (list_cards), 5567-5591 (get_card)`; genios_engine/deliver/store.py:658-690 (get_authoritative_card selects k.* + candidate_steps, rejected_candidates, decision_uncertainty); `genios_engine/api/routes.py:5104-5161 (_decision_projection)`; `genios_engine/deliver/card_builder.py:1335-1375 (build_draft fields)`; `genios_engine/reason/expert/decide.py:266-271,323-333 (_done; gold without act)`; `dashboard origin/main src/app/dashboard/cards/page.tsx:925 (Goal row hard-coded 'Not linked to a goal yet')`
- **What Rohit sees:** Cards read as a kind of card rather than this situation: unclear subjects, empty or stock How, a result that is often stock, no goal, and the same details on several cards.
- **Fix:** Build C6 → C2 → C1 → C4 → C3 → C5 → C7 → C8 in that order (01-INTEGRATION §5). Each is listed as its own item below.
- **Depends on:** [l5-subject-writer](#l5-subject-writer), [l5-c6-person-level-context](#l5-c6-person-level-context), [l5-c2-act-not-carried](#l5-c2-act-not-carried), [l5-c3-queue-fields](#l5-c3-queue-fields), [l5-c4-quote-sender-date](#l5-c4-quote-sender-date), [goals-c8-no-goal-on-card](#goals-c8-no-goal-on-card)
- **Verified:** confirmed with a correction by the skeptic: One detail is wrong: the reason expert steps are empty. The expert play does have a step. decide.py:287 builds MOVE_PLAY with steps=(words.headline,), and decision_maker.py:898 copies play.steps into the candidate parameters. The step is lost because the compiled/expert signal insert (reason/domain_shadow.py:343-357) never writes signals.candidate_steps; only the legacy runner path writes it (runner.py:806 via _decision_payload). So get_card's s.candidate_steps is NULL, and _decision_projection (routes.py:5118-5128) gets no decided_steps. On an actionable expert card it drops to the else branch with steps=[]. On a non-actionable card it uses the stock line 'Open the source and review the request'.

<a id="l5-card-writer-c1-c2-c6-unbuilt"></a>
### Cards read thin, repeated or garbled on every surface: the card writer (C1), the expert's result (C2) and per-card context (C6) are unbuilt

`l5-card-writer-c1-c2-c6-unbuilt` · **P1** · missing · owner **claude** · mixed · step **S34**

- **Expected:** Each card has its own clear subject, two lines (what to do and how), steps, the result of doing it, and context tied to its own thread. 'Every card's details and scenario must be its own.' _(source: speedrun008/GeniOS-010/06-CARDS/01-INTEGRATION.md §5 C6, C2, C1; 06-CARDS/02-CARD-DEFINITION.md; memory cards-ux-analysis-22-oct round 3)_
- **Actual:** No deliver/card_copy.py and no cards.copy column. The gold block has no act/done_when, so 'what doing it gets you' is stock or empty. _meeting_neighbors and _commitment_neighbors attach the subject node's last 4 meetings and 3 promises to every card on that node. The surfaces then hide every text another open card repeats (sharedTexts/sharedLines) and count it as 'N lines read the same', so cards come out thin. Garbled headlines ('Send calendar invites with meeting link to body') and repeated one-liners ('70 days since they wrote') come from the brain's writer.
- **Evidence (mixed):** `grep genios_engine and migrations: no card_copy, cards.copy, goal_refs`; `genios_engine/reason/expert/decide.py:323-330 (gold without act/done_when)`; `genios_engine/api/routes.py:5225-5272 (neighbors by node, out[:3], out[:4])`; `dashboard origin/main:src/lib/card-read.ts:513-560 (sharedTexts/ownCard drop repeats)`; memory desktop-accessibility-and-adhoc-builds.md ('card one-liners repeating'); cards-ux-analysis-22-oct.md ('Open: garbled headlines')
- **What Rohit sees:** Fewer distinct lines per card, identical details across cards, no 'what doing it gets you', and unclear headlines. This is the 'weird' cards complaint (F2).
- **Fix:** In order: C6 (keep only meetings and commitments on this card's thread or evidence), then C2 (gold.act and done_when as checked words → card result and success_signal), then C1 (deliver/card_copy.py, one claim-checked model call per new card version, its own budget, migration for cards.copy). Before any paid pass, test one or two live calls with max_tokens sized for thinking.
- **Blocked on:** select subject_node_id, count(*) from cards c join signals s on s.signal_id=c.signal_id where c.org_id='<rohit org>' and c.state in ('queued','surfaced','snoozed','delivered') group by 1 order by 2 desc limit 10;
- **Depends on:** [Rohit's OK for a read-only production query to confirm cards anchor on one node (C6)](#Rohit's OK for a read-only production query to confirm cards anchor on one node (C6)), [a paid-run budget for C1](#a paid-run budget for C1)
- **Verified:** confirmed with a correction by the skeptic: C1 and C6 hold, but the C2 detail is overstated. done_when does reach the card. reason/expert/decide.py:278-291 puts the checked done_when into the play's success_events (_done at :266-271 falls back to '<headline> — done' when the check withholds it). deliver/pipeline.py:90 carries those as play_success_events, and card_builder._play_success (:233-236) writes them to success_signal. What never reaches the card is the expert's scenarios.act ('if you act now'). It exists in contracts/expert_review.py (Scenarios, :228; serialised at :374) but nothing reads it into the card. So 'what doing it gets you' is the checked done_when, or the stock '<move> — done', never the expert's result. The gold block at decide.py:323-330 does lack act and done_when, as stated.

<a id="l5-delivery-only-in-app"></a>
### Delivery is pull-only: provisioning registers only in_app, Slack is the only push adapter and has no dashboard setup, and there is no email channel

`l5-delivery-only-in-app` · **P1** · missing · owner **claude+harsh** · mixed · step **S37**

- **Expected:** A push channel (Slack or email) beyond in_app. _(source: speedrun008/GeniOS-008/02-MIGRATION-PLAN.md §1 'Push to people' and §3.5 L5-3)_
- **Actual:** Provisioning inserts only in_app, the pull surface. channels/base.get_channel knows only 'slack'. PUT /api/org/{org}/channels/slack exists, but the dashboard never calls it. deliverable_channels drops in_app, so enqueue_pending and the digest have nowhere to go. A code comment records production on 2026-09-17: all three orgs register only in_app. Consequences:
- executive_bridge reminders and escalations reach no one;
- the STEP-15 kept brief, which is the digest payload, is never sent.
- **Evidence (mixed):** `genios_engine/platform/seats.py:72-91 (inserts PULL_SURFACE only)`; `genios_engine/deliver/channels/base.py:23-26 (only slack)`; `genios_engine/api/channel_routes.py:61-75`; `genios_engine/deliver/outbox.py:343-380 (deliverable_channels), 576-582 (prod note 2026-09-17)`; `genios_engine/deliver/outbox.py:315-329 (digest = kept brief)`; `dashboard origin/main: no match for 'channels/slack' under src/`
- **What Rohit sees:** Cards appear only when Rohit opens the dashboard or the Mac app. No ping, no morning digest, no reminder.
- **Fix:** Rohit picks the first push channel (Slack webhook or email). Then add a dashboard Settings screen that calls PUT /api/org/{org}/channels/slack, or build an email adapter in deliver/channels and register it in get_channel. Harsh sets it for Rohit's org and checks one digest and one high-band card arrive.
- **Blocked on:** Read-only: select org_id, channel, active, last_digest_date, updated_at from org_channels order by 1,2;
- **Verified:** confirmed by the skeptic (seats.py:85-91 inserts only PULL_SURFACE. get_channel knows only 'slack' (plus agent_push for machines) (channels/base.py:23-30). Only slack.py and agent.py adapters exist. deliverable_channels drops in_app (outbox.py:343-380). The production note is at outbox.py:576-582. The digest payload is the kept brief (outbox.py:320-334). Dashboard origin/main has no match for '/channels' under src or Extension/src. The Mac app has no notification or stream code for cards; it polls /cards. Whether production has added a Slack row since 17 Sep is unverifiable without a read: select org_id, channel, active from org_channels;)

<a id="l5-fewer-cards-refusals-unmeasured"></a>
### Fewer cards since 18 Oct: L5's own drop paths are recorded but have no surface, and production was not read

`l5-fewer-cards-refusals-unmeasured` · **P1** · unknown until production is read · owner **rohit+harsh** · mixed · step **S01**

- **Expected:** Nothing is lost silently. Every suppress or hold carries a why-not receipt that a person can see. _(source: speedrun008/GeniOS-008/02-MIGRATION-PLAN.md §3.5 L5-2; migrations/0222_card_refusals.sql header)_
- **Actual:** L5 can withhold a card at several points:
- the card contract (us / internal / money / quote / number), written to card_refusals and retried after REFUSAL_RETRY;
- insert_card refusing a blank headline or situation, returned as 'not created' and counted nowhere;
- refused_subject_is_us, absorbed_by_cohort and version_refused counters, returned only in the build_cards_for_org dict;
- an expert card graded REVIEW, which loses Done.
card_refusals is read only by the pipeline's retry and by scripts/pipeline_health; no API or dashboard shows it. Whether L5 explains 'fewer cards' needs production.
- **Evidence (measured):** `migrations/0222_card_refusals.sql:1-30`; `genios_engine/deliver/pipeline.py:605-650 (refusals kept), 804-830 (counters)`; `genios_engine/deliver/store.py:372-386 (blank card refused, reported as not created)`; `genios_engine/deliver/card_builder.py:1175-1182 (expert grade → review, only wrong+snooze)`
- **What Rohit sees:** Cards may be dropped by the contract or blank-guard with nothing on screen saying so.
- **Fix:** First read production; see blocked_on. Then expose why-not counts per sweep, from card_refusals plus blank and lease refusals, on an admin route and as a line on the Cards page ('3 cards held back today: quote not found…').
- **Blocked on:** Rohit's OK for read-only SQL: (1) select builder_version, output_lane, render_mode, state, count(*) from cards where org_id=:org and created_at >= '2026-10-11' group by 1,2,3,4 order by 5 desc; (2) select rule, writer, count(*), max(refused_at) from card_refusals where org_id=:org and refused_at >= '2026-10-11' group by 1,2; (3) select date_trunc('day', created_at) d, count(*) from cards where org_id=:org and created_at >= '2026-10-01' group by 1 order by 1;
- **Verified:** confirmed by the skeptic (Every cited drop path holds. card_refusals is created in 0222 with CHECK rule in (us, internal, money, quote, number). Its readers are pipeline._recently_refused (pipeline.py:607-622) and scripts/pipeline_health.py:1098-1118. Writers are pipeline and reason/team/emit.py:131. No API or dashboard reads it; api/account_routes.py:645 has it only in the delete list. A blank headline/situation returns (None, False, False) (store.py:395-397). Counters live in the build_cards_for_org dict (pipeline.py:804-830). The heartbeat keeps only 'built' in the funnel (routes.py:844-847); the rest are dropped, except by the internal POST /cards/sweep, which returns the dict (routes.py:5414). An expert grade reduces actions to wrong+snooze (card_builder.py:1180-1182). Whether this explains fewer cards needs production reads, for example: select writer, rule, count(*) from card_refusals where refused_at >= '2026-10-18' group by 1,2; select date_trunc('day',created_at) d, builder_version, count(*) from cards where created_at >= '2026-10-01' group by 1,2 order by 1; select kind, cause, count(*) from card_events where occurred_at >= '2026-10-18' and kind in ('card.expired','card.retired','card.dismissed','card.versioned') group by 1,2;)

<a id="l5-meeting-followup-cards-fail-every-door"></a>
### Post-meeting follow-up cards ('meeting.followup') fail all three card doors: never on GET /cards, and 'Open card' gives a 404

`l5-meeting-followup-cards-fail-every-door` · **P1** · broken · owner **claude** · code · step **S36**

- **Expected:** A P-16 post-meeting follow-up is a durable card in the founder's Cards queue, and the desktop moment's pinned open_card action opens it. _(source: genios_engine/reason/meetings/passes.py:1-30 (SCREEN_INTEL_P5 §3, P-16); genios_engine/reason/team/emit.py:1-25 (card + moment, 'readable … through the moment's open_card'))_
- **Actual:** emit_followups calls emit_situation with capability_id='meeting.followup' (reason/meetings/passes.py:46, 360-368). The emitter writes the signal with rule_id = capability_id = 'meeting.followup' and no reasoning run (reason/team/emit.py:279-299).

No door admits that card:
- The P4 situation door requires split_part(capability_id, '.', 1) in ('team', 'verify') (deliver/store.py:29-31). 'meeting' fails it.
- The decision door needs a reasoning run.
- The question door needs the founder_question builder.

So the card is missing from queue() (deliver/store.py:777-788) and get_authoritative_card returns None (deliver/store.py:650-691). GET /cards/{id} then answers 404 'card not found or no longer actionable' (api/routes.py:5401-5406, 5568-5571). The desktop moment's open_card goes to /dashboard/cards?card=<id> (dashboard origin/main Extension/src-tauri/src/moments/actions.rs:106), which hits that 404. Team ('team.deadline_at_risk', 'team.readiness') and verify ('verify.situation') cards pass, so only meeting follow-ups are lost. No test reads a follow-up card back through the queue (tests/test_meetings_pg.py).
- **Evidence (measured):** `genios_engine/reason/meetings/passes.py:9, 46, 360-368`; `genios_engine/reason/team/emit.py:18-20, 279-299`; `genios_engine/deliver/store.py:28-31, 650-691, 777-788`; `genios_engine/api/routes.py:5401-5406, 5567-5571`; `genios_engine/reason/team/away.py:28; genios_engine/reason/team/readiness.py:29 (team.* capabilities pass)`; `dashboard origin/main Extension/src-tauri/src/moments/actions.rs:106`; `git: a7e05da3 (13 Sep, P4 door 'team'/'verify') and da5d486a (13 Sep, P5 meeting.followup) landed the same day`
- **What Rohit sees:** Every meeting follow-up ('You: … · they: … · Decided: …') is written and then hidden. The Cards page never lists it, and opening it from the desktop toast shows 'card not found'. That is fewer cards, and lost meeting outcomes.
- **Where the mistake was:** P5 group B reused emit_situation under a new capability prefix on the same day P4 added a queue door that admits only 'team.' and 'verify.' prefixes. The door keys on a capability-name prefix rather than on the writer's builder stamp, and no test read a follow-up back through the queue.
- **Fix:** Admit 'meeting' in SITUATION_CARD_SQL, or better, key the door on builder_version = 'team.emit.v1' plus 'no reasoning run' instead of on a capability prefix. Add a test that emits a meeting follow-up and reads it back through queue() and GET /cards/{id}.
- **Blocked on:** Production impact, read-only: select count(*) as followup_cards, count(*) filter (where k.state in ('queued','surfaced','snoozed')) as open_ones, min(k.created_at), max(k.created_at) from cards k join signals s on s.signal_id = k.signal_id and s.org_id = k.org_id where k.org_id = '<ORG>' and s.capability_id = 'meeting.followup'; select status, count(*) from transcripts where org_id = '<ORG>' group by 1;
- **Verified:** added by the completeness critic, checked against the code by it

<a id="l5-question-card-answer"></a>
### Question cards: brain and web Cards page are correct; the Mac app offers Done (422 not_offered, swallowed) and no Answer

`l5-question-card-answer` · **P1** · partial · owner **claude** · code · step **S38**

- **Expected:** A question card offers Answer, Later and Don't-ask-me, never Done. A refused press says why and stays visible. _(source: 06-CARDS/02-CARD-DEFINITION.md §2.7; 03-WHAT-WAS-THERE.md M-list)_
- **Actual:** Brain: question cards offer answer, snooze and wrong (pipeline.py:316-320). Any other action returns 422 not_offered, and an answered card offers only snooze/requeue (actions.py:196-202).

Web: dashboard origin/main 2edfb86 has merged rohit/cards-ux, which has an Answer box and no Done on question cards.

Mac app (origin/main): DesktopAdvisor draws Done on every loop (line 492) and has no answer flow. act() removes the card optimistically and calls cardAction, whose request ends in .catch(() => {}). So the 422 is swallowed and the card returns on the next poll.
- **Evidence (measured):** `genios_engine/deliver/pipeline.py:226,316-320`; `genios_engine/deliver/actions.py:43,196-204`; `dashboard origin/main Extension/src/desktop/DesktopAdvisor.tsx:320-327,492`; `dashboard origin/main Extension/src/desktop/api.ts:372-385 (.catch(() => {}))`; `dashboard origin/main src/app/dashboard/cards/page.tsx:378,860 (Answer on web)`
- **What Rohit sees:** On the Mac, pressing Done on a question card does nothing and the card comes back, so the founder's answer is never given.
- **Where the mistake was:** Desktop cardAction swallows every error by design (.catch(() => {})). A refusal nobody sees is a silent stop.
- **Fix:** Mac app: read render_mode and actions[] from the card (the readCard approach) and draw only offered buttons, adding an Answer box. Show refusals instead of swallowing them, undo the optimistic removal on failure, and send surface:'desktop'.
- **Verified:** confirmed by the skeptic (Brain: QUESTION_ACTIONS=(answer, snooze, wrong) (pipeline.py:226, 316-320). QUESTION_OFFERS also admits requeue (actions.py:43). An answered card accepts only snooze/requeue (ANSWERED_OFFERS, actions.py:61, 196-200). Other actions return not_offered, which the route turns into 422 (routes.py:5631-5634). Mac app (dashboard origin/main): DesktopAdvisor act() removes the card optimistically (DesktopAdvisor.tsx:320-329). Done/Snooze/Not useful are drawn on every loop (lines 491-499). There is no answer flow. cardAction ends with .catch(() => {}) (api.ts:372-381). The app reads /cards (api.ts:303-304), so question cards reach it. Web: a question card shows Answer instead of Done (page.tsx:701-704) and has an answer textarea (page.tsx:850-863).)

<a id="l5-subject-writer"></a>
### No card writer (C1): the subject is a clause cut of the model's move, a pack template, or the l5_render line; garbled headlines come from this chain

`l5-subject-writer` · **P1** · missing · owner **claude** · code · step **S34**

- **Expected:** The subject starts with a verb, is at most about 10 words, names the person or thing, and is never a cut sentence or placeholder ("…to body"). It is written once per card version by deliver/card_copy.py into cards.copy, and every sentence is checked. _(source: speedrun008/GeniOS-010/06-CARDS/02-CARD-DEFINITION.md §2.1; 01-INTEGRATION.md §5 C1)_
- **Actual:** deliver/card_copy.py and a cards.copy column do not exist. Headlines have four writers:
1. Expert/L2 cards: reason/expert/decide._render puts the model's checked headline (words.headline) into fallback.headline. card_builder._gold_template then applies gold_headline(), which cuts to HEADLINE_CAP=60 at _GOLD_CUT. That pattern splits before 'to', 'with', 'for', 'on', 'in' and similar words, which start phrases, not clauses. render._fallback re-caps it, and pipeline.py:1003 state_not_command adds 'Needs a decision — ' / 'Unresolved — ' to review- and observation-level cards. That leaves 41 characters for the body, which _cap fits by sentence, then clause, then word.
2. Formula cards: render.render_copy (model site l5_render, max_tokens=600), trimmed by _fit/_fit_clauses, or on failure the pack template, e.g. packs/general_v1.py:174 'Deliver {action} to {entity} today'.
3. Question cards: the model's question text.
4. executive_bridge reminders: '{frame} — {goal}'.
The phrase 'Send calendar invites with meeting link to body' is not in the repo. Without the production row I cannot tell which of writers 1–3 produced it.
- **Evidence (mixed):** `ls genios_engine/deliver/card_copy.py → No such file`; `genios_engine/reason/expert/decide.py:305-333 (_render: fallback.headline = _braces(words.headline))`; `genios_engine/deliver/card_builder.py:868-916 (FUNCTION_WORDS, _GOLD_CUT, gold_headline, _gold_template)`; genios_engine/deliver/render.py:26 (HEADLINE_CAP=60), 217-255 (state_not_command: room = 60 - len(prefix)), 323-340 (_fallback), 559-617 (render_copy, purpose l5_render); `genios_engine/deliver/pipeline.py:980-1003 (render_copy with llm=None for expert; then state_not_command)`; `genios_engine/packs/general_v1.py:174,181 (formula templates)`; `genios_engine/deliver/executive_bridge.py:79,103`
- **What Rohit sees:** Subjects that are cut, stiff ('Needs a decision — …') or garbled, like 'Send calendar invites with meeting link to body'.
- **Where the mistake was:** STEP-14 s14-D8 chose 'the move cut at a clause by code, no prompt change'. The cut pattern treats prepositions as clause starts, so a 60-character cut can drop the object and keep a dangling phrase.
- **Fix:** Build C1 as specified: deliver/card_copy.py, called after build_draft and the claim check, once per new card version and never per view. It writes subject, summary, steps, result and goal, each with rests_on, and a sentence that rests on nothing is dropped. Add a migration for cards.copy jsonb, serve copy.subject and copy.summary from CardStore.queue, and give it its own model site and budget, failing closed to today's fields. Separately, stop gold_headline cutting before prepositions: cut only at real clause punctuation, else keep the whole move under recommended and leave the subject to C1. Run one or two live calls first (Claude 5 thinking eats max_tokens).
- **Blocked on:** To find the writer of the garbled headline (read-only, Rohit's permission): select card_id, builder_version, render_mode, capability_key, level, headline, recommended->>'what' as move, reject_code, reject_detail, created_at from cards where org_id=:org and (headline ilike '%calendar invite%' or headline ilike '%to body%'); then: select kind, cause, detail->'words' from card_events where card_id=:card order by occurred_at;
- **Verified:** confirmed with a correction by the skeptic: There are at least five headline writers, not four. The fifth is the P4 team/verify situation cards (builder team.emit.v1 = SITUATION_CARD_BUILDER, store.py:28). reason/team/emit._write_card writes their headline with clip(headline, HEADLINE_MAX=60) (emit.py:62, 81-83, 244), which hard-cuts at 59 characters and adds an ellipsis ('…'). Second detail: the 41-character body budget applies only to the 'Needs a decision — ' frame (60-19). For 'Unresolved — ' the budget is 47 (render.py:248-255).

<a id="l5-wrong-without-reason"></a>
### The Mac app's 'Not useful' sends 'wrong' with no reason; the brain refuses it (422 invalid_wrong_reason) and the app swallows it, so no verdict reaches L6

`l5-wrong-without-reason` · **P1** · broken · owner **claude** · code · step **S38**

- **Expected:** Every 'wrong' carries one of the closed reasons the card offers (actions[].reasons / reason_groups), and a refusal is shown. _(source: genios_engine/deliver/card_builder.py:1150-1170 (reasons offered); 06-CARDS/03-WHAT-WAS-THERE.md M1)_
- **Actual:** Brain: ingest_action returns invalid_wrong_reason when reason is not in WRONG_REASONS, and the route turns that into 422. Mac: cardAction(loop.card_id, 'wrong') with reason '' sends reason: null, then .catch(() => {}). The web Feedback menu does send a reason.
- **Evidence (measured):** `genios_engine/deliver/actions.py:102-104`; `genios_engine/api/routes.py:5631-5634`; `dashboard origin/main Extension/src/desktop/DesktopAdvisor.tsx:321-327,498`; `dashboard origin/main Extension/src/desktop/api.ts:372-385`
- **What Rohit sees:** Pressing 'Not useful' on the Mac hides the card for a moment; it comes back, and calibration and corrections learn nothing.
- **Fix:** Mac app: open a reason picker from the card's reason_groups (four headings), with optional words, and send {action:'wrong', reason, words, scope, surface:'desktop'}. Surface the error. Do not default a reason server-side; the vocabulary rule says a verdict requires a closed reason.
- **Blocked on:** To size it (read-only): select type, detail->>'surface' as surface, detail->>'reason' as reason, count(*) from human_events where org_id=:org and type like 'card.%' and occurred_at >= '2026-10-01' group by 1,2,3 order by 4 desc; a missing 'desktop' wrong means every Mac 'Not useful' was lost.
- **Verified:** confirmed by the skeptic (actions.py:102-104 returns invalid_wrong_reason when reason is not in WRONG_REASONS, and routes.py:5631-5634 maps it to 422. Mac 'Not useful' calls act(loop,'wrong') (DesktopAdvisor.tsx:497-499). cardAction then sends reason: reason || null and swallows the error (api.ts:372-381). The web FeedbackMenu sends a reason group (page.tsx:995, 1103) and shows the invalid_wrong_reason error (page.tsx:203).)

<a id="l5-c3-queue-fields"></a>
### C3 unbuilt: the queue lacks what the list draws, so the dashboard makes up to 40 detail calls, each with N+1 graph reads

`l5-c3-queue-fields` · **P2** · missing · owner **claude** · code · step **S35**

- **Expected:** CardStore.queue (all three doors) returns output_lane, business_subject, relationship_role, recommended->>'by_when', version, context_tags and a from_screen flag, and the list needs no detail calls. Also GeniOS-008 L5-4: bulk card loads. _(source: 06-CARDS/01-INTEGRATION.md §5 C3; speedrun008/GeniOS-008/02-MIGRATION-PLAN.md §3.5 L5-4)_
- **Actual:** The three SELECTs project 13 columns, with no lane, subject, role, by_when, version, tags or actions. The dashboard calls GET /cards/{id} for up to 40 cards on every 45-second poll. Each call runs _card_intelligence: signal, facts, observations, situation and the neighbour loops.
- **Evidence (measured):** `genios_engine/deliver/store.py:772-788`; `genios_engine/api/routes.py:5317-5372`; `speedrun008/GeniOS-010/06-CARDS/01-INTEGRATION.md §2 (MAX_DETAILS 40, 45 s poll)`
- **What Rohit sees:** A slow list. A Done/Answer button or tag can be missing until each card's detail call returns.
- **Fix:** Add the C3 columns to all three queue SELECTs (store.py:772, 779, 785). The version count comes from cards.version, which already exists (0220). Then have the dashboard load details only for the opened card.
- **Verified:** confirmed with a correction by the skeptic: The dashboard does not make up to 40 detail calls on every 45-second poll. loadDetails filters out card ids already in detailsRef.current (dashboard origin/main src/app/dashboard/cards/page.tsx:239-243). Up to 40 GET /cards/{id} calls happen on first load. After that, each poll fetches only cards not yet cached, plus a forced re-fetch of a card just acted on (page.tsx:381). POLL_MS=45_000 and MAX_DETAILS=40 are at page.tsx:76-78. Each detail call does run _card_intelligence with its N+1 neighbour reads.

<a id="l5-c4-quote-sender-date"></a>
### C4 unbuilt: quotes on a card are bare strings with no sender or date

`l5-c4-quote-sender-date` · **P2** · missing · owner **claude** · code · step **S35**

- **Expected:** Each quote is {text, from, at, event_id}, so the panel can say '— Divya Raman, 13 Sep'. _(source: 06-CARDS/01-INTEGRATION.md §5 C4; 02-CARD-DEFINITION.md §2.4)_
- **Actual:** sources_of carries words.quotes, a tuple of strings built from run.quotes[n]. _sentence_sources copies them into why[] unchanged.
- **Evidence (measured):** `genios_engine/reason/expert/verify.py:812,1023,1315 (quotes: dict[int,str] → tuple of strings)`; `genios_engine/reason/expert/decide.py:366-383 (sources_of)`; `genios_engine/deliver/card_builder.py:841-855 (_sentence_sources)`
- **What Rohit sees:** Details cannot say who said a line or when.
- **Fix:** Resolve each quote's evidence id to its source event (sender, occurred_at, event_id) when the card is built, and store it as objects in why[]. In readCard, accept either a string or an object.
- **Verified:** confirmed with a correction by the skeptic: The sources_of citation is wrong. sources_of is at reason/expert/decide.py:346-367; decide.py:366-383 is capability_for. The substance holds.

<a id="l5-c7-no-right-verdict"></a>
### C7 unbuilt: no 'this is right' verdict; the action set has 'wrong' and nothing positive

`l5-c7-no-right-verdict` · **P2** · missing · owner **claude** · code · step **S35**

- **Expected:** Feedback can say what is right as well as what is wrong, with the same words and scope, recorded to the same learning ledger. _(source: 06-CARDS/01-INTEGRATION.md §5 C7; Rohit round 4 ('kya galat hai, kya sahi hai'))_
- **Actual:** BUTTONS = {run_play, do_it_myself, snooze, wrong, requeue, answer}. No 'right' action exists, and verdicts.VERDICT_CAUSES has no positive cause.
- **Evidence (measured):** `genios_engine/deliver/actions.py:36 (BUTTONS)`; `genios_engine/deliver/actions.py:100-104 (unknown action refused)`
- **What Rohit sees:** Only negative feedback reaches learning.
- **Fix:** Add a 'right' action that writes a verdict through deliver/verdicts with the card's binding, plus optional words and scope as a founder correction. Leave the card's state unchanged, and keep it out of the precision 'wrong' set. Add a migration if the verdict CHECK constraint lists causes.
- **Verified:** confirmed with a correction by the skeptic: VERDICT_CAUSES does contain positive causes: {run_play, do_it_myself, wrong} (deliver/verdicts.py:54). Acting on a card is recorded as a verdict. What is missing is an explicit 'this is right' verdict that needs no action and carries reasons, words and scope the way 'wrong' does (actions.py:36 BUTTONS; verdicts.py:132-137 allows a reason only on 'wrong').

<a id="l5-version-count-dashboard"></a>
### C9 and version: the brain keeps each version's words and change, but the dashboard counts only card.rebuilt and ignores card.versioned and cards.version

`l5-version-count-dashboard` · **P2** · partial · owner **claude** · code · step **S35**

- **Expected:** The panel says 'version N — what changed' (C9). _(source: 06-CARDS/01-INTEGRATION.md §3 (Version) and §5 C9)_
- **Actual:** Brain: file cards are versioned through card_lifecycle.version_card, which writes card.versioned with cause = the change, and version_of computes the changed fields and whether they are material. cards.version exists (0220) and GET /cards/{id} returns it via k.*. A formula refresh writes card.rebuilt with its words. Dashboard: versionOf counts only 'card.rebuilt' events, so an expert/L2 file card that was versioned shows the wrong version. 'What changed' is not shown.
- **Evidence (measured):** `genios_engine/platform/card_lifecycle.py:147,265`; `genios_engine/contracts/card_version.py:191-205 (version_of: change, changed, material)`; `genios_engine/deliver/store.py:566-585 (card.rebuilt with words)`; `migrations/0220_the_living_card.sql:31 (cards.version)`; `dashboard origin/main src/lib/card-read.ts:595-597`
- **What Rohit sees:** The version number is wrong on versioned file cards, and the panel cannot say what changed.
- **Fix:** Dashboard: read card.version from the detail, and show the latest card.versioned cause and changed fields as 'what changed'. Brain: optionally serve the last change on GET /cards/{id}.
- **Verified:** confirmed by the skeptic (card_lifecycle.py:147 VERSIONED='card.versioned' is written by version_card with cause=version.change (card_lifecycle.py:263-268). version_of computes change, changed and material (contracts/card_version.py:191-205). cards.version comes from migrations/0220_the_living_card.sql:31. card.rebuilt events carry words and version (store.py:575-581). Dashboard card-read.ts:595-598 counts only 'card.rebuilt', and page.tsx:785 uses that count. 'What changed' is never shown.)

<a id="layer-l6"></a>
## L6 Learning (feedback/)

| Item | Sev | Status | Owner | Step |
|---|---|---|---|---|
| [Calibration now runs (bug 1 fixed in shadow), but its would-mute and would-nudge results are read by nobody; t](#l6-calibration-shadow-unread) | P2 | shadow / switched off | claude | S40 |
| [Human-review learning objects now reach the human_review state (bug 4 fixed) but no dashboard or Mac screen li](#l6-human-review-no-surface) | P2 | built, not live | claude | S40 |
| [Moment feedback (Mac Useful / Not useful) is written to learning_event_inbox, loaded every week, and dropped: ](#l6-inbox-dropped) | P2 | missing | rohit+harsh | S40 |
| [L6 and L5 write ledgers that nothing reads, or that only a count(*) receipt reads](#l6-unread-ledgers) | P2 | partial | claude | S40 |

<a id="l6-calibration-shadow-unread"></a>
### Calibration now runs (bug 1 fixed in shadow), but its would-mute and would-nudge results are read by nobody; the B22–B24 traps are still in the apply path

`l6-calibration-shadow-unread` · **P2** · shadow / switched off · owner **claude** · mixed · step **S40**

- **Expected:** Shadow calibration shows what it would do, so Rohit can decide whether to arm it (D13). Mutes are recorded, can be lifted, and never hide unrelated cards. _(source: memory calibration-fix-arms-auto-mute.md; genios_engine/platform/l4_activation.py:89-97 (calibration_apply))_
- **Actual:** The canonical_judgments CTE projects card_level (184269a0, in prod history), and run_calibration(apply=False) is the default. would_mute and would_nudge are stored only in calibration_runs.result. Readers are the idempotency check in calibrate.py:283 and a count(*) receipt. In the apply path, an applied mute or nudge still bumps tenant_packs.authority_revision, which hides every open card of the pack; a muted rule expires its signals' cards. No B22–B24 fix is present.
- **Evidence (measured):** `genios_engine/reason/authority.py:329-336`; `git merge-base --is-ancestor 184269a0 HEAD → in prod`; `genios_engine/feedback/calibrate.py:239-253,402-430,451-466`; `genios_engine/platform/receipts.py:1813`
- **What Rohit sees:** None today in shadow. Armed without fixes, one nudge empties the pack's queue.
- **Fix:** Show the last shadow result (would_mute, would_nudge, with precision and n) on GET /feedback/precision or a learning screen. Do not arm calibration_apply until B22–B24 are fixed and Rohit answers D13.
- **Blocked on:** Read-only: select run_id, status, completed_at, result->'would_mute' wm, result->'would_nudge' wn, result->'rules_scored' rs from calibration_runs where org_id=:org order by completed_at desc nulls last limit 5;
- **Verified:** confirmed with a correction by the skeptic: 'No B22–B24 fix is present' overstates it. B22, the part where a muted rule's cards vanish with no record, is addressed: the apply path expires them through card_lifecycle.expire_cards with cause RULE_MUTED, one card.expired event each (calibrate.py:415-430; card_lifecycle.py:65,109-121; added in 15a9bd70 on 2026-10-07). B24 is still present: an applied mute or nudge bumps tenant_packs.authority_revision (calibrate.py:401-413). l4_activation.py:296-301 still says arm only after B22-B24. A recovery 'unmute' branch exists (calibrate.py:356-367, since Aug), but whether a muted rule can ever accrue the judgments to recover (B23) was not verified.

<a id="l6-human-review-no-surface"></a>
### Human-review learning objects now reach the human_review state (bug 4 fixed) but no dashboard or Mac screen lists or reviews them

`l6-human-review-no-surface` · **P2** · built, not live · owner **claude** · code · step **S40**

- **Expected:** A founder can see and approve or reject org-rule and knowledge proposals. _(source: genios_engine/api/learning_routes.py:122-125 docstring; memory full-audit-eight-verified-live-bugs.md #4)_
- **Actual:** publisher._rest_for_review moves the row to human_review, and POST /v1/learning/objects/{id}/review works. No dashboard or Extension code calls /v1/learning/*, so proposals wait forever.
- **Evidence (measured):** `genios_engine/feedback/publisher.py:281-300`; `genios_engine/api/learning_routes.py:36-109,122-137`; `dashboard origin/main: git grep 'v1/learning' src Extension/src → no match`
- **What Rohit sees:** Learned org rules never become live without a hand-run API call.
- **Fix:** Add a Learning screen (owner only) over GET /v1/learning/objects?state=human_review and /v1/learning/suggestions, with Approve/Reject calling the review route.
- **Verified:** confirmed with a correction by the skeptic: Partly listed, never reviewable. KNOWLEDGE proposals resting at human_review get a knowledge_suggestions row (publisher.py:199-206), and GET /api/org/{org}/brain includes them via _suggestion_records (brain_routes.py:172-229). The dashboard Brain page (src/app/dashboard/brain/page.tsx:33, getCompanyBrain → api-brain.ts:195) shows them read-only as learning candidates awaiting review. The Brain page has no approve or reject action, and no dashboard or Extension code calls /v1/learning/*. So proposals still cannot be decided, and org-rule learning_objects at human_review are not listed. Objects stuck at 'governed' from before the STEP-18 fix move only if the one-off scripts/rest_stuck_reviews.py --apply was run in production, which is unknown.

<a id="l6-inbox-dropped"></a>
### Moment feedback (Mac Useful / Not useful) is written to learning_event_inbox, loaded every week, and dropped: the preference and temporary-memory units return []

`l6-inbox-dropped` · **P2** · missing · owner **rohit+harsh** · mixed · step **S40**

- **Expected:** Behaviour and adaptive evolution units consume typed events (GeniOS-008 L6-2). _(source: speedrun008/GeniOS-008/02-MIGRATION-PLAN.md §3.6 L6-2; memory l6-the-loop-that-is-never-questioned.md S5)_
- **Actual:** unit_preference_learning and unit_temporary_memory both return []. run_learning counts the rows as inbox_unconsumed in learning_runs.counts. Every row is payload.kind == 'moment_feedback'.
- **Evidence (measured):** `genios_engine/feedback/units.py:182-206,209-230`; `genios_engine/feedback/orchestrator.py:200-215,324`
- **What Rohit sees:** 'Not useful' on Mac moments never shapes later cards.
- **Fix:** Rohit decides which preference kinds the founder can state (Atlas L7 #1). Then implement unit_temporary_memory over moment_feedback as a leased, expiring TEMPORARY memory, using the existing lease machinery. Use typed evidence only, no model.
- **Verified:** confirmed by the skeptic (unit_preference_learning (units.py:182-206) and unit_temporary_memory (units.py:209-230) both return []. inbox_unconsumed is computed at orchestrator.py:215 and persisted into learning_runs.counts (orchestrator.py:318-327). The only writer of learning_event_inbox is reason/moments/store.py:146-158, with payload.kind='moment_feedback', for every new action including 'shown'. Today it is reached from api/moment_routes.py:783, not the :746 the comments cite. This is moment and popup feedback, separate from the Mac card 'Not useful', which goes to /cards/{id}/action.)

<a id="l6-unread-ledgers"></a>
### L6 and L5 write ledgers that nothing reads, or that only a count(*) receipt reads

`l6-unread-ledgers` · **P2** · partial · owner **claude** · mixed · step **S40**

- **Expected:** Each write-only table is retired or given a reader (GeniOS-008 L6-3). _(source: speedrun008/GeniOS-008/02-MIGRATION-PLAN.md §3.6 L6-3; memory l6-the-loop-that-is-never-questioned.md)_
- **Actual:** Declared UNREAD_WRITES (no select anywhere): learning_metrics (every METRICS proposal), human_events (written by every card press), card_feedback_revisions, agent_metering, delivery_rate_windows, and situation_interpretations (the DecisionObject). Read only by platform/receipts.py presence counts, with no product surface: learning_transitions, learning_object_evaluations (plus target_policy's sizing query), learning_input_rejections, learning_runs and calibration_runs. learning_event_inbox is loaded into every batch, and both units that should use it return [] (see l6-inbox-dropped).
- **Evidence (measured):** genios_engine/platform/table_coverage.py UNREAD_WRITES (9 entries incl. learning_metrics, human_events, card_feedback_revisions, situation_interpretations); `genios_engine/platform/receipts.py:976,1009,1691-1818 (count(*) reads)`; `genios_engine/feedback/publisher.py:188-195 (learning_metrics writer)`
- **What Rohit sees:** What Rohit presses is recorded, but parts of it change nothing he can see.
- **Fix:** Rohit decides, per ledger, whether to keep it with a reader or retire it. Suggested readers:
- precision by layer from learning_metrics on a /v1/learning/scorecard screen;
- a human-action timeline from human_events for outcome reconciliation;
- revisions into the learning batch (Atlas L7 #3).
situation_interpretations gets its reader in G8.
- **Verified:** confirmed with a correction by the skeptic: Small corrections. learning_transitions is also read by the one-off ops script scripts/rest_stuck_reviews.py:42, not only by receipts.py. The receipts reads are count(*) with correctness conditions (e.g. receipts.py:1009 forbidden transitions, 1742-1750), not pure presence counts. learning_event_inbox is read through a dynamic select f'select * from {table}' (feedback/store.py:176, 214, 266-270), which is why a literal grep misses it.

<a id="layer-goals"></a>
## Goals (GeniOS-009)

> Nothing of the GeniOS-009 goal loop exists in code yet, and even a finished plan would not make "Antler Singapore admission" a goal. Of the ground work, only G0.1 is done: Harsh's three CI fixes are in the production head, and CI is green at 0cc8d83c. The rest of G0 is open. `l2_cards` is still off by default. The F15 wave subject is missing, and the held-card text is still written in engineer's words. L3 admission still runs in shadow and writes no seeds. D1–D8 were never answered. G1–G9 are entirely missing: there is no goal contract, table, store, `/v1/goals` route, dossier block G, `goal_impacts` field, link table, progress tool, goal column on cards, check-in state, decision request or progress event. Migration 0250, which the plan reserves for goals, is already taken by GeniOS-010 B8. Today a goal is only a free-text line in the company brief. The only automatic proposer is the weekly brief drafter. It runs only for tenants that already have an accepted line, reads memory patterns rather than situations, files or reasoning, and is told to propose only what is missing. The per-file readers that do see a workstream (R-7 expert, R-9 L2) have no field for proposing a goal. The plan keeps that gap: G1 names the drafter as the only proposer ("or later L2's" has no unit), and G2 never prints proposed goals. G3 refuses any goal that block G did not print, so L2 can only link Antler to an umbrella goal like "Get into accelerator programs". The "Proposed goal" card in 06-CARDS-TARGET has no unit either. On the surfaces, the home page always shows no goals: the live goal list is hard-coded to [], "Goals formed" to 0, and "No goals set yet" always appears, while the Goals page does list the accepted brief goals. The Goals page makes the founder type four free-text answers that end up inside the goal's text, and it never shows the drafter's evidence. One adjacent defect matters for the design: the L2 path asks the model for `proposed_kind` but never writes it, so kind proposals stop as soon as `l2_cards` is switched on. A goal proposer built the same way must be wired into the L2 sweep explicitly. Production was not read: whether Rohit's brief has goal lines, whether the weekly review ran, which switches are on and whether an Antler file exists all need the SQL given in blocked_on.

| Item | Sev | Status | Owner | Step |
|---|---|---|---|---|
| [G0 ground: CI is green, but l2_cards, admission-decides-existence and D1–D8 are all still open](#goals-g0-ground-partial) | P0 | partial | claude+harsh | S24 |
| [G1 goal object is not built: no contract, table, sync, API, and migration 0250 is already taken](#goals-g1-goal-object-missing) | P0 | missing | claude+harsh | S28 |
| [Plan gap: even after G1–G9, a workstream like Antler cannot become a goal of its own](#goals-plan-gap-no-l2-goal-proposer) | P0 | missing | claude | S26 |
| [Why 'Antler Singapore admission' cannot become a goal automatically today](#goals-antler-cannot-appear-today) | P1 | missing | claude | S27 |
| [No goal on any card (C8/G6); and G6 plans the goal board on GET /v1/insights, which the Cards page does not re](#goals-c8-no-goal-on-card) | P1 | missing | claude | S31 |
| [G2: the L2 judgment sees goals only as brief words; no block G, no goal ids, and no re-reasoning when a goal c](#goals-g2-goals-not-in-l2-dossier) | P1 | missing | claude | S29 |
| [G3: neither L2Judgment nor ExpertReview has any goal field](#goals-g3-no-goal-impacts) | P1 | missing | claude | S29 |
| [G4: no goal↔situation links, and the admission they hang on is still shadow](#goals-g4-no-goal-situation-links) | P1 | missing | claude+harsh | S30 |
| [G5: no goal progress tool; progress is never measured, counted or marked unknown](#goals-g5-no-goal-progress) | P1 | missing | claude | S30 |
| [G6: no goal line or goal_refs on cards, no goal board, no goal_board switch, and the planned 'Proposed goal' c](#goals-g6-no-goal-on-card) | P1 | missing | claude | S31 |
| [G7: no check-in states on the situation; 'done when' exists only as a free-text card line](#goals-g7-no-checkin-states) | P1 | missing | claude+harsh | S32 |
| [G8: the DecisionObject is written and nobody reads it; no decision requests; L4 still plans without a human](#goals-g8-no-human-decision-requests) | P1 | missing | claude+harsh | S32 |
| [The judgment cannot propose a goal, so graph context such as the Antler Singapore admission never becomes one](#goals-judgment-cannot-propose-goal) | P1 | missing | rohit | S26 |
| [L3 has no goal object and no goal↔situation link, and the planned link (G4) depends on an admission that canno](#goals-no-goal-in-l3) | P1 | missing | claude | S28 |
| [Goals reach the judgment only as id-less background prose; nothing asks for or carries goal impact](#goals-not-in-judgment) | P1 | missing | claude | S29 |
| [Historical mail never got its business facts (thread.objective, party.role): backfill_business_facts has no ca](#goals-thread-objective-history-missing) | P1 | built, not live | claude+harsh | S09 |
| [No surface can show a goal: GET /v1/goals (B1) is unbuilt, and every goal slot is a fixed string or null](#surfaces-b1-no-goal-on-any-surface) | P1 | missing | claude | S31 |
| [G9: verified outcomes move no goal; no progress events; macv_ledger still has no writer](#goals-g9-outcomes-move-no-goal) | P2 | missing | claude | S33 |

<a id="goals-g0-ground-partial"></a>
### G0 ground: CI is green, but l2_cards, admission-decides-existence and D1–D8 are all still open

`goals-g0-ground-partial` · **P0** · partial · owner **claude+harsh** · mixed · step **S24**

- **Expected:** STEP-G0: (1) CI green; (2) l2_cards on for D6's tenant after F15 gets a wave subject, the held-card text is reworded, and one week side by side loses no card; (3) L3 admission decides that an outreach situation exists (seed row, made visible only by ADMIT); (4) D1–D8 answered or defaults logged. _(source: speedrun008/GeniOS-009/STEP-G0-the-ground.md §G0.1–G0.4; 02-PLAN.md G0)_
- **Actual:** G0.1 is done: 3d5a6a3d, 8d1de446 and 269400dc are in HEAD 0cc8d83c (platform/db.py:76 sends TimeZone=UTC), and CI is green per F1. G0.2 is not done: reason/l2/inputs.py has no wave subject (no 'wave' anywhere in it), the held text 'We held the one we found' is still at reason/expert/verify.py:793, and l2_cards is off by default (platform/l4_activation.py:117-122). G0.3 is not done: context/l2_admission.py:25 says '⛔ SHADOW: nothing here touches context_situations', and no 'seed' status exists anywhere in genios_engine/context. G0.4: 08-DECISIONS.md lists defaults only, and 03-LOG has no line recording a decision.
- **Evidence (measured):** `git merge-base --is-ancestor 3d5a6a3d/8d1de446/269400dc HEAD → all in HEAD`; `genios_engine/reason/expert/verify.py:793`; `genios_engine/platform/l4_activation.py:117-122`; `genios_engine/context/l2_admission.py:25`; `speedrun008/GeniOS-009/08-DECISIONS.md (no answers)`; `speedrun008/GeniOS-009/00-START-HERE.md step table still says 'open — CI red on 21b7ae10'`
- **What Rohit sees:** Goal links can reach a card only through the L2 card path, and that path is off. Until it is on, nothing in G1–G9 can change what Rohit sees.
- **Where the mistake was:** 00-START-HERE and 04-FOR-HARSH were not updated after Harsh's G0.1 fix, so the handover still says CI is red.
- **Fix:** G0.2.a: add the wave subject to reason/l2/inputs.read_subjects and reason/l2/sweep (F15 stays strict-xfail until then). G0.2.b: rewrite the held text in the reader's words at reason/expert/verify.py:793. Rohit names the tenant (D6), Harsh switches on l2_cards, and the side-by-side report runs for a week. G0.3: outreach_situations writes seeds and ADMIT flips them to active. Log D1–D8 as defaults in 03-LOG.
- **Blocked on:** Production state of the switches (read-only): select * from l4_activation where org_id = :org;  select * from l3_activation where org_id = :org;
- **Verified:** confirmed by the skeptic (Measured at HEAD 0cc8d83c. 3d5a6a3d, 8d1de446 and 269400dc are all ancestors of HEAD, and platform/db.py:76 sends '-c TimeZone=UTC'. reason/l2/inputs.py has no 'wave'. The held text is still at reason/expert/verify.py:793. The l2_cards constant is at platform/l4_activation.py:122, and its docstring at :118-121 says it is off by default. context/l2_admission.py:25 is the SHADOW line, and no 'seed' status value exists in genios_engine or migrations (l2_admission.py:41 uses 'seed' only as a concept). 08-DECISIONS has defaults only, and 03-LOG's only G0 row is G0.1 (line 15). 00-START-HERE.md:110 still says 'open — CI red on 21b7ae10'. Whether l2_cards is switched on per tenant in production can only be seen in prod: select org_id, feature, disabled_at from l4_activation where feature in ('l2_cards','l2_reasoning','expert_review');)

<a id="goals-g1-goal-object-missing"></a>
### G1 goal object is not built: no contract, table, sync, API, and migration 0250 is already taken

`goals-g1-goal-object-missing` · **P0** · missing · owner **claude+harsh** · code · step **S28**

- **Expected:** contracts/goal.py (Goal with status proposed|approved|active|completed|superseded|cancelled and source founder|brief|inferred); tables company_goals and company_goal_revisions; context/goals.sync_from_brief as the first sweep stage l3.goals_sync; api/goal_routes.py with GET /v1/goals and PATCH for metric, target, deadline and owner. An inferred goal is never active without approved_by. _(source: speedrun008/GeniOS-009/STEP-G1-the-goal-object.md §2–§3; 02-PLAN.md G1; 08-DECISIONS D2, D7)_
- **Actual:** None of it exists. genios_engine/contracts/goal.py, context/goals.py and api/goal_routes.py are absent, and no route serves /v1/goals. A goal is only a company_brief_lines row with section 'goals' (contracts/company_brief.py:38). Migration 0250 is already migrations/0250_screen_followup_read_path.sql (93ea3cbe, GeniOS-010 B8), so the plan's table '0250_company_goals … 0255' collides.
- **Evidence (measured):** `ls genios_engine/contracts/goal.py genios_engine/context/goals.py genios_engine/api/goal_routes.py → No such file`; `grep -rn '/v1/goals' genios_engine → 0 hits`; `genios_engine/contracts/company_brief.py:38`; `migrations/0250_screen_followup_read_path.sql (commit 93ea3cbe, in HEAD)`; `speedrun008/GeniOS-009/00-START-HERE.md migration table lists 0250_company_goals`
- **What Rohit sees:** No card can carry a goal, because there is no goal id to point at. Every later step needs one.
- **Where the mistake was:** The plan hard-coded migration numbers in 00-START-HERE on the same day GeniOS-010 B8 took 0250.
- **Fix:** Build STEP-G1 at the next free number (0251) and renumber the plan's migration table (0251–0256). Add the structured proposal fields from the design item (proposed metric, target, deadline, owner, parent_goal_id, subject_ref and evidence_refs carried from the proposal), so that approving needs no typing.
- **Depends on:** [goals-g0-ground-partial](#goals-g0-ground-partial)
- **Verified:** confirmed with a correction by the skeptic: The substance holds. contracts/goal.py, context/goals.py and api/goal_routes.py are absent, and genios_engine and migrations have 0 hits for /v1/goals, company_goals or company_goal_revisions. One detail is wrong: a goal is NOT only a company_brief_lines row. Two other goal-like stores exist, and GeniOS-009 mentions neither. (1) team_milestones, migration 0151, whose header says 'A milestone is a dated goal with an owner seat'. It has title, due_at and owner_seat_id, served by POST/GET /v1/team/milestones at api/team_routes.py:84-130, with readiness counted in reason/team/readiness.py. (2) Internal knowledge of kind 'goal' (capture/internal_knowledge.py:56,92). The 0250 collision is real: migrations/0250_screen_followup_read_path.sql comes from 93ea3cbe, which is in HEAD, so F3's 'migrations end at 0249' is also out of date. But 00-START-HERE.md:73 says 'Each number is the next free one at build time; check origin/harsh/mvp first', and STEP-G1:266 says '(or the next free number)'. So this is a stale number in the doc, not a hard design collision.

<a id="goals-plan-gap-no-l2-goal-proposer"></a>
### Plan gap: even after G1–G9, a workstream like Antler cannot become a goal of its own

`goals-plan-gap-no-l2-goal-proposer` · **P0** · missing · owner **claude** · docs · step **S26**

- **Expected:** The plan contains a unit in which the L2 judgment infers a goal from a workstream it reads, L3 admits it as a proposal, and a human approves it (source GOAL-01; 06-CARDS-TARGET §4 'Proposed goal' card). _(source: source/GeniOS-Goal-Achievement-Loop-Chat.md:9818 and :10100-10104; speedrun008/GeniOS-009/06-CARDS-TARGET.md §4)_
- **Actual:** STEP-G1 §2.1 mentions 'the drafter's, or later L2's' proposals, but no unit builds L2's. STEP-G1 §4 says 'The model only proposes, through the existing brief drafter', and 08-DECISIONS D7 names the drafter as the door. STEP-G2 §2.1 never prints proposed goals. STEP-G3 §3.1–§3.2 refuses GOAL_NOT_PRINTED ('Name only goals block G printed'), so L2 can only link Antler to an approved umbrella goal. The STEP-G3 §3.3 labels put the program cases F17, F19, F21, F22, F24 and F67 under 'Accelerator and incubator programs', so a single admission is a link, never its own goal. GeniOS-010 D-010-G2 wants monthly child goals through parent_goal_id, but no unit creates them. STEP-G4 §2 holds links to proposed goals. The 'Proposed goal' card in 06-CARDS-TARGET §4 has no build unit.
- **Evidence (doc_claim):** `speedrun008/GeniOS-009/STEP-G1-the-goal-object.md §2.1, §4`; `speedrun008/GeniOS-009/08-DECISIONS.md D7`; `speedrun008/GeniOS-009/STEP-G2-goals-in-the-snapshot.md §2.1`; `speedrun008/GeniOS-009/STEP-G3-goal-impact-in-the-judgment.md §3.1-§3.3`; `speedrun008/GeniOS-009/STEP-G4-goal-situation-links.md §2 table`; `speedrun008/GeniOS-010/03-GOALS/README.md §4 D-010-G2`; `speedrun008/GeniOS-009/06-CARDS-TARGET.md §4`
- **What Rohit sees:** Built exactly as written, the plan still leaves Rohit's main complaint ('Antler never became a goal') unfixed.
- **Where the mistake was:** STEP-G1 waved at 'later L2's' proposals and D7 defaulted to the drafter, but no unit was written for L2. 06 promised a card kind that no step builds. G3's 'name only printed goals' rule was written without a companion rule for 'propose when none fits'.
- **Fix:** Add units to the plan before building G1–G3: G1.6, a structured goal proposal from L3 admission (the door and its fields); G3.5, L2Judgment.proposed_goal with claim checks; G4.5, context/goal_admission.decide_goal_proposal; G6.8, the proposed-goal chip on the card and on the home page. Add a golden case F72, 'Antler Singapore application becomes a proposed goal', and mutation proofs for 'never active without a human'. Record Rohit's decision on granularity and the door (decision item).
- **Blocked on:** Rohit's decision goals-decision-goal-granularity-and-door
- **Depends on:** [goals-decision-goal-granularity-and-door](#goals-decision-goal-granularity-and-door)
- **Verified:** confirmed by the skeptic (Every cited passage checks out. STEP-G1:44 ('the drafter's, or later L2's') has no unit, and STEP-G1 §4 (:186-189) says 'The model only proposes, through the existing brief drafter'. D7 names the drafter. STEP-G2:23,49,79 never print proposed goals. STEP-G3:76 defines GOAL_NOT_PRINTED, :92 says 'Name only goals block G printed', and :105 maps F17, F19, F21, F22, F24 and F67 to the umbrella goal. STEP-G4:44 holds a link to a proposed goal (goal_not_live). D-010-G2 (GeniOS-010/03-GOALS/README.md:92) needs parent_goal_id children, and no unit creates them. The plan also contradicts itself: 06-CARDS-TARGET.md:101's own example, 'make Join Gulf Launchpad a goal?', is a single-programme goal, the same shape as Antler, yet G3 labels every programme case under the umbrella. Caveat on the source: GOAL-01 (source/GeniOS-Goal-Achievement-Loop-Chat.md:8728) only says an LLM-inferred departmental goal must not become authoritative without approval. The LLM drafter meets its letter. The per-workstream L2 proposer comes from Rohit's F2 and the 06 §4 example, not from GOAL-01. Severity: this is a plan gap for unbuilt work and starves no card today, so P1 fits better than P0.)

<a id="goals-antler-cannot-appear-today"></a>
### Why 'Antler Singapore admission' cannot become a goal automatically today

`goals-antler-cannot-appear-today` · **P1** · missing · owner **claude** · mixed · step **S27**

- **Expected:** A workstream the founder is actively pursuing, whose context is in the graph (Theresa, the Antler partner; the Singapore admission), is proposed as a goal for one-click approval and never becomes active on its own (Rohit's F2; source GOAL-01). _(source: F2 (Rohit); speedrun008/GeniOS-009/source/GeniOS-Goal-Achievement-Loop-Chat.md:10100-10104 (GOAL-01 'LLM infers a new departmental goal — does not become authoritative without approval'))_
- **Actual:** (1) The only automatic goal proposer is the brief drafter. It runs weekly, and only for orgs with at least one accepted brief line (reason/brief_review.py:24-25). A first draft happens only through the operator script scripts/draft_company_brief.py. It needs a real-LLM client (platform/wiring.py:290-297), and a failed draft loses the week (brief_review.py:58-60). (2) The drafter reads memory PATTERNS only: correspondents, domains, waves, introducers, meeting series, deadline domains, and at most the 40 most recent thread objectives in 180 days (reason/brief_patterns.py:37,44,108-113,257-262). It never reads context_situations, workstream files, expert_reviews or reasoning_results. (3) It is told to 'Propose only what is missing — never a line it already says' (brief_drafter.py:83-87), and store dedupe applies (platform/company_brief_store.py:99-118). An umbrella goal like 'Get into accelerator and incubator programs' therefore covers Antler, and the goals section is capped at 8 lines (brief_drafter.py:39). (4) The readers that do see the Antler file, R-7 expert and R-9 L2, cannot propose a goal. ExpertReview proposes only a kind (contracts/expert_review.py:256,279), which is written to section in_motion (reason/expert/kind_proposal.py:132-140). L2Judgment has no proposal field (contracts/reasoning_result.py:241-242). (5) No test expects it. tests/replays/specs/01-theresa… frames Theresa as an investor reconsideration whose business_subject is 'not Antler as an organization', with no goal obligation, and no golden founder case mentions Antler or Theresa.
- **Evidence (measured):** `genios_engine/reason/brief_review.py:24-25,58-60`; `genios_engine/api/routes.py:1610-1625`; `genios_engine/platform/wiring.py:290-297`; `genios_engine/reason/brief_patterns.py:37,44,108-113,257-262`; `genios_engine/reason/brief_drafter.py:39,83-87`; `genios_engine/platform/company_brief_store.py:99-118`; `genios_engine/contracts/expert_review.py:256,279`; `genios_engine/reason/expert/kind_proposal.py:132-140`; `genios_engine/contracts/reasoning_result.py:241-242`; `tests/replays/specs/01-theresa_investor_reconsideration_and_update_cade.json business_subject`; `grep -li 'antler|theresa' tests/replays/specs/founder → 0 files`
- **What Rohit sees:** An active admission or fundraising thread never becomes a goal, so its cards stay 'Not linked to a goal', and nothing on the home page says the founder is pursuing it.
- **Where the mistake was:** The goal proposer was scoped to the STEP-07 drafter (patterns, weekly), which was designed to write a brief on day one, not to notice new workstreams.
- **Fix:** Short term, within the existing door: (a) run the drafter for tenants with no accepted line too (the first draft), and retry a failed week. (b) Add the open situations and workstream files with their kinds, plus the in-motion lines, to brief_patterns as pattern items, so the drafter can propose a goal per active workstream. The real fix is the L2 proposer (design item).
- **Blocked on:** Production (read-only, Rohit's permission): select section,status,proposed_by,left(text,120),proposed_at,accepted_at from company_brief_lines where org_id=:org and section in ('goals','in_motion') order by proposed_at;  select week_key,outcome,proposed,finished_at from company_brief_reviews where org_id=:org order by week_key desc limit 10;  select field,left(value::text,160),occurred_at from graph_facts where org_id=:org and valid_to is null and value::text ilike '%antler%' order by occurred_at desc limit 20;  select file_id,status,reviewed_at from expert_reviews where org_id=:org and (file_id ilike '%antler%' or review::text ilike '%antler%') order by reviewed_at desc limit 10;  select subject_ref,status,lane,reasoned_at from reasoning_results where org_id=:org and (subject_ref ilike '%antler%' or result::text ilike '%antler%') order by reasoned_at desc limit 10;
- **Depends on:** [goals-g1-goal-object-missing](#goals-g1-goal-object-missing)
- **Verified:** confirmed with a correction by the skeptic: The mechanism holds: weekly review only for orgs with an accepted line (reason/brief_review.py:24-25); a failed draft loses the week (:58-60); the only other caller is scripts/draft_company_brief.py, and no API route calls the drafter; it needs a real-LLM client (platform/wiring.py:290-297). The drafter reads only source_events, graph_facts, graph_nodes and orgs (reason/brief_patterns.py:37,44,108-113,257-262). R-7 can propose only an in_motion kind (kind_proposal.py:132-140), and L2Judgment has no proposal field. Four details are wrong. (a) MAX_PER_SECTION=8 (brief_drafter.py:39) caps the goal proposals of ONE draft: the per-section counter in parse() (:156,:180) restarts each call. It does not cap the goals section of the brief. (b) Store dedupe (platform/company_brief_store.py:99-118) blocks only identical normalized text, or the same address or domain. A distinctly worded Antler goal would pass it. What blocks one is the prompt's 'Propose only what is missing' (brief_drafter.py:84) together with an umbrella goal, and the golden brief really holds 'Get into accelerator and incubator programs' (tests/replays/specs/founder/brief/company_brief.json:18-19). (c) Founder golden cases are forbidden by contract to use real names: tests/replays/founder_case.py:84-90 REAL_NAMES includes 'Theresa' and 'Antler'. So no founder case naming them is by design. The synthetic analogue F17 ('An accelerator moves the founder's application to interview') exists, and its authored answer ties it only in words to the umbrella goal ('Getting into accelerator programmes is one of the brief's goals'). (d) There is also replay spec tests/replays/specs/12-antler_exploratory_relationship_and_regional_aut.json (944b4f76). It models the Antler Singapore 2026 application from the program-operator side ([MODELLED]) and also has no goal field.

<a id="goals-c8-no-goal-on-card"></a>
### No goal on any card (C8/G6); and G6 plans the goal board on GET /v1/insights, which the Cards page does not read

`goals-c8-no-goal-on-card` · **P1** · missing · owner **claude** · mixed · step **S31**

- **Expected:** Every card names the goal it moves (or is counted as 'Not linked'), and the Cards list can group by goal. _(source: 06-CARDS/02-CARD-DEFINITION.md §3.8; GeniOS-009 06-CARDS-TARGET.md §2 row 4 and §3; STEP-G6 §2–§3)_
- **Actual:** Established F3: no goal table, no cards.goal_refs or goal_line, and the dashboard hard-codes 'Not linked to a goal yet'. In this slice: deliver/board.py does not exist. G6.5 would put group=goal on GET /v1/insights. The dashboard Cards page reads /cards (api-cards.ts:214-250), and the only dashboard reader of /v1/insights lists is decision-inbox.tsx, which is unmounted. So the board as planned would not appear on the Cards page.
- **Evidence (measured):** `genios_engine/deliver/store.py:446 (F3: no goal column in the insert)`; `ls genios_engine/deliver/board.py → No such file`; `speedrun008/GeniOS-009/STEP-G6-the-goal-on-the-card.md §3 G6.5`; `dashboard origin/main src/lib/api-cards.ts:214-250; src/components/insights/decision-inbox.tsx:25`; `dashboard origin/main src/app/dashboard/cards/page.tsx:925`
- **What Rohit sees:** Rohit sees 'Not linked to a goal yet' on every card. Even after G6 as written, the Cards page would not group by goal.
- **Where the mistake was:** STEP-G6 G6.5 targets api/intelligence_routes GET /v1/insights. Since GeniOS-010 the live Cards page reads /cards, so the plan aims at a route no mounted screen uses.
- **Fix:** After G1/G4 land, implement G6 with the board on GET /cards?group=goal, or on a new /cards/board, not /v1/insights. Carry goal_line and goal_refs on the queue rows (with C3), and let readCard fill the Goal row. Amend STEP-G6 G6.5 and the brief.
- **Verified:** confirmed by the skeptic (deliver/board.py does not exist. No goal_refs or goal_line appears in genios_engine; the only goal_id is the capability goal in contracts/reasoning.py:372. STEP-G6 §3 G6.5 (line 74) plans group=goal on GET /v1/insights. The dashboard Cards page reads /cards (api-cards.ts:4-41). The only /v1/insights list reader is decision-inbox.tsx (listInsights at line 132), and DecisionInbox is imported nowhere. The dashboard Goals page also reads /cards plus up to 40 /cards/{id} (goals-page.tsx:462-474), not /v1/insights, so the planned board would show on neither page. Small update to F3: migrations now end at 0250 (0250_screen_followup_read_path.sql), and there is still no goal table.)

<a id="goals-g2-goals-not-in-l2-dossier"></a>
### G2: the L2 judgment sees goals only as brief words; no block G, no goal ids, and no re-reasoning when a goal changes

`goals-g2-goals-not-in-l2-dossier` · **P1** · missing · owner **claude** · code · step **S29**

- **Expected:** Dossier block G prints the live goals with goal: ids and their progress. The fingerprint gains goal_set and linked_goals. A new trigger goal_changed re-judges linked subjects exactly once. _(source: speedrun008/GeniOS-009/STEP-G2-goals-in-the-snapshot.md §2–§3)_
- **Actual:** The L2 dossier has blocks A–F only (reason/l2/dossier.py:37-40, block order at :178). For a seed subject the brief appears only as text inside block D (dossier.py:170); for a file subject it arrives inside the STEP-12 file dossier. fingerprint_of (reason/l2/sweep.py:74) has no goal input. TRIGGERS (contracts/reasoning_result.py:53-60) has no goal_changed. No file under reason/l2 mentions 'goal'. Design conflict: STEP-G2 §2.1 says 'proposed goals are not printed', so an L2 goal proposer could not see what it already proposed.
- **Evidence (measured):** `genios_engine/reason/l2/dossier.py:37-40,170,178`; `genios_engine/reason/l2/sweep.py:74`; `genios_engine/contracts/reasoning_result.py:53-60`; `grep -n goal genios_engine/reason/l2/*.py → 0 hits`
- **What Rohit sees:** The model cannot name a goal by id, so nothing it says about a goal can be checked or linked.
- **Fix:** Build STEP-G2. Also print the pending proposals as a separate sub-block, marked 'proposed — not the company's goal yet', so L2 can dedupe its own proposals without treating them as goals.
- **Depends on:** [goals-g1-goal-object-missing](#goals-g1-goal-object-missing)
- **Verified:** confirmed by the skeptic (TITLES at reason/l2/dossier.py:37-40 has A–F only. The block order is at :178, and the seed brief text is in block D at :170. fingerprint_of (reason/l2/sweep.py:74-92) has no goal input. TRIGGERS (contracts/reasoning_result.py:53-59) has no goal_changed. grep -n goal reason/l2/*.py gives 0 hits. I tried to refute 'no re-reasoning on goal change' and it held. The brief version is in the file fingerprint (reason/expert/fingerprint.py:89, version = hash of the shown body, contracts/company_brief.py:269), but reason/expert/triggers.py:25-28 (06 D48) says a brief version change alone 'rides along with the next trigger'. L2 subjects come only from new L1 bundles (reason/l2/inputs.py:208-218) or the expert's handoff of triggered files. So accepting or editing a goal re-judges nothing. For seed subjects the brief is not in the fingerprint at all (file_inputs=None). STEP-G2 §2.1 line 49 does say 'The proposed goals are not printed'.)

<a id="goals-g3-no-goal-impacts"></a>
### G3: neither L2Judgment nor ExpertReview has any goal field

`goals-g3-no-goal-impacts` · **P1** · missing · owner **claude** · code · step **S29**

- **Expected:** L2Judgment.goal_impacts with GoalImpact(goal_ref, relation advances|threatens|depends_on|unclear, why, evidence, size_basis), claim-checked by GOAL_NOT_PRINTED, IMPACT_WITHOUT_EVIDENCE, SIZE_NOT_PRINTED and DUPLICATE_GOAL, and asked for in the prompt. _(source: speedrun008/GeniOS-009/STEP-G3-goal-impact-in-the-judgment.md §3)_
- **Actual:** L2Judgment (contracts/reasoning_result.py:227) has KEYS intervention_mode … deeper (:241-242) and no goal field. validate_judgment (:361) has no goal codes. ExpertReview has no goal field (F3; grep 'goal' contracts/expert_review.py → 0). Goals appear only as prose that the expert writes on its own (F02's 'mark the brief's StartupSetu recognition goal as met').
- **Evidence (measured):** `genios_engine/contracts/reasoning_result.py:227,241-242,361`; `grep -n goal genios_engine/contracts/expert_review.py → 0 hits`; `speedrun008/GeniOS-009/01-AS-IS-CARDS.md §1 'cards that name a goal: 0 as a field'`
- **What Rohit sees:** No card says which goal it moves, which is Rohit's 'no card carries a goal'.
- **Fix:** Build STEP-G3. In the same unit, add L2Judgment.proposed_goal (see the design item), so that a subject with no matching printed goal can propose one rather than staying silent.
- **Depends on:** [goals-g2-goals-not-in-l2-dossier](#goals-g2-goals-not-in-l2-dossier)
- **Verified:** confirmed by the skeptic (L2Judgment is at contracts/reasoning_result.py:227, and its KEYS at :241-242 contain no goal field. validate_judgment is at :361. grep -i goal contracts/expert_review.py gives 0 hits, and there is no goal-like field under another name (objective/purpose). reason/expert/verify.py:754-760 only treats the brief's goals as text the founder confirmed. 01-AS-IS-CARDS.md:33 says '0 as a field'.)

<a id="goals-g4-no-goal-situation-links"></a>
### G4: no goal↔situation links, and the admission they hang on is still shadow

`goals-g4-no-goal-situation-links` · **P1** · missing · owner **claude+harsh** · code · step **S30**

- **Expected:** On ADMIT with a live goal, write goal_situation_links rows (many-to-many, revisioned). HOLD a link to a non-live goal. Close a situation's links when it ends. Written in the admission savepoint. _(source: speedrun008/GeniOS-009/STEP-G4-goal-situation-links.md §2–§3)_
- **Actual:** context/goal_links.py and the table are absent. context/l2_admission.py writes l2_admissions and situation_interpretations (the DecisionObject at :163), runs in shadow (:25), and does nothing about goals. The admission call site is reason/l2/sweep.py:421-429.
- **Evidence (measured):** `genios_engine/context/l2_admission.py:25,163`; `genios_engine/reason/l2/sweep.py:421-429`; `grep -rn goal_situation_links genios_engine migrations → 0 hits`
- **What Rohit sees:** Even an impact the model writes would be shadow text with no admitted link, so the card's goal line has nothing to stand on.
- **Fix:** Build STEP-G4 after G0.3 and G3, writing inside the existing begin_nested savepoint.
- **Depends on:** [goals-g3-no-goal-impacts](#goals-g3-no-goal-impacts), [goals-g0-ground-partial](#goals-g0-ground-partial)
- **Verified:** confirmed by the skeptic (context/goal_links.py is absent, and goal_situation_links has 0 hits in genios_engine and migrations. l2_admission writes l2_admissions (:121) and situation_interpretations (insert at :169; the decision dict is at :163) and never mentions goals. The call site is reason/l2/sweep.py:421-429. One nuance: 'shadow' is exact only for context_situations. With l2_cards on, the admission decision already gates the card: at reason/l2/sweep.py:378-384, an ADMIT or REJECT writes the file's review, while a HOLD leaves the file to the old lane.)

<a id="goals-g5-no-goal-progress"></a>
### G5: no goal progress tool; progress is never measured, counted or marked unknown

`goals-g5-no-goal-progress` · **P1** · missing · owner **claude** · code · step **S30**

- **Expected:** A closed METRICS registry (files_at_stage, manual; verified_outcomes added in G9), context/goal_progress.progress_of returning measured, counted or unknown (never 0 for unknown), and tools.goals_tool printed with line ids. _(source: speedrun008/GeniOS-009/STEP-G5-goal-progress.md §2–§3)_
- **Actual:** There is no goals_tool in reason/l2/tools.py, no METRICS, and no context/goal_progress.py. The dashboard already expects pct, progress and counted (GeniOS-010/03-GOALS/README.md §3) and draws every live goal as 'Not measured'.
- **Evidence (measured):** `ls genios_engine/context/goal_progress.py → No such file`; `grep goal genios_engine/reason/l2/tools.py → 0 hits`; `speedrun008/GeniOS-010/03-GOALS/README.md §3`
- **What Rohit sees:** The home page and the Goals page can show no progress, and no goal-at-risk card is possible.
- **Fix:** Build STEP-G5. GET /v1/goals returns progress in the shape GeniOS-010/03-GOALS README §3 lists.
- **Depends on:** [goals-g1-goal-object-missing](#goals-g1-goal-object-missing), [goals-g4-no-goal-situation-links](#goals-g4-no-goal-situation-links)
- **Verified:** confirmed by the skeptic (context/goal_progress.py is absent. reason/l2/tools.py has no goal or METRICS, and progress_of/goals_tool have 0 hits. On the dashboard (origin/main 2edfb86), goals/live.ts:144-146 sets every live goal to status 'unmeasured', pct null, 'no countable measure yet', and goals-page.tsx:78 labels 'unmeasured' as 'Not measured'. GeniOS-010/03-GOALS/README.md:44-45,67-68 defines pct/progress/counted.)

<a id="goals-g6-no-goal-on-card"></a>
### G6: no goal line or goal_refs on cards, no goal board, no goal_board switch, and the planned 'Proposed goal' card has no unit

`goals-g6-no-goal-on-card` · **P1** · missing · owner **claude** · code · step **S31**

- **Expected:** Columns cards.goal_refs and goal_line written by code from admitted links; deliver/board.py with GET /v1/insights?group=goal; 'Not linked to a goal' counted; a goal_board switch per tenant. 06-CARDS-TARGET §4 also promises a 'Proposed goal' card kind. _(source: speedrun008/GeniOS-009/STEP-G6-the-goal-on-the-card.md §2–§3; 06-CARDS-TARGET.md §3–§4)_
- **Actual:** cards has no goal column (deliver/store.py:446, F3). deliver/board.py is absent. goal_board is not in L4_FEATURES (platform/l4_activation.py:131-134). The dashboard hard-codes 'Not linked to a goal yet' (dashboard origin/main src/app/dashboard/cards/page.tsx:925; src/product/internal/dashboard/intel/parts.tsx:215). No unit G6.1–G6.7 (or any other G unit) builds the 'Proposed goal' card kind that 06-CARDS-TARGET §4 lists with the trigger 'G1 inferred goal, waiting for approval'.
- **Evidence (measured):** `genios_engine/deliver/store.py:446`; `genios_engine/platform/l4_activation.py:131-134`; `git show origin/main:src/app/dashboard/cards/page.tsx (line 925)`; `git show origin/main:src/product/internal/dashboard/intel/parts.tsx (line 215)`; `speedrun008/GeniOS-009/06-CARDS-TARGET.md §4 'Proposed goal' row vs STEP-G6 §3 units`
- **What Rohit sees:** Every card reads 'Not linked to a goal yet'.
- **Where the mistake was:** 06-CARDS-TARGET promised a card kind that no build step owns.
- **Fix:** Build STEP-G6 and add a unit G6.8: a 'proposed goal' chip on the card of the subject whose judgment proposed the goal, with one-click Make it a goal / Not a goal (see the design item).
- **Depends on:** [goals-g4-no-goal-situation-links](#goals-g4-no-goal-situation-links), [goals-g5-no-goal-progress](#goals-g5-no-goal-progress), [goals-g0-ground-partial](#goals-g0-ground-partial)
- **Verified:** confirmed by the skeptic (The cards insert at deliver/store.py:446-466 has no goal column, and goal_refs/goal_line/goal_board/group=goal have 0 hits in code and migrations. deliver/board.py is absent. L4_FEATURES is at platform/l4_activation.py:130-133 (not 131-134) and has no goal_board. The dashboard hard-codes 'Not linked to a goal yet' at src/app/dashboard/cards/page.tsx:925 and src/product/internal/dashboard/intel/parts.tsx:215. 06-CARDS-TARGET.md:101 lists the 'Proposed goal' kind. STEP-G6 units G6.1–G6.7 (lines 70-76) do not build it, and neither does any other STEP-G file. G9 builds only 'Goal reached — confirm' and 'Goal at risk'.)

<a id="goals-g7-no-checkin-states"></a>
### G7: no check-in states on the situation; 'done when' exists only as a free-text card line

`goals-g7-no-checkin-states` · **P1** · missing · owner **claude+harsh** · code · step **S32**

- **Expected:** L2Judgment.done_when (DoneWhen with says, evidence_kind, from_whom, by_when); context_situations.resolution_state with seven states; a pure context/checkin.evaluate that never calls overdue without full coverage; resolve only from verified or withdrawn. _(source: speedrun008/GeniOS-009/STEP-G7-check-in-states.md §2–§3)_
- **Actual:** context/checkin.py is absent, and there is no resolution_state column (grep finds only a test name). ExpertReview.done_when (contracts/expert_review.py:277) is a free-text card sentence, not a typed definition of done. L2Judgment has no done_when.
- **Evidence (measured):** `ls genios_engine/context/checkin.py → No such file`; `genios_engine/contracts/expert_review.py:277`; `grep resolution_state genios_engine migrations → 0 hits`
- **What Rohit sees:** A reported 'done' and a proven one look the same, and an unread mailbox can read as silence.
- **Fix:** Build STEP-G7 (with the F68–F70 golden cases).
- **Depends on:** [goals-g0-ground-partial](#goals-g0-ground-partial), [goals-g3-no-goal-impacts](#goals-g3-no-goal-impacts)
- **Verified:** confirmed by the skeptic (context/checkin.py is absent. resolution_state appears only in a test name (tests/capture/validate/test_conflict.py:693). ExpertReview.done_when is a plain str at contracts/expert_review.py:277, and L2Judgment has no done_when. The closest existing thing is per-card outcome states in context/file_outcomes.py:39-48 (verified, replied, taken, called_wrong, lapsed…). Those sit on the card, not the situation, and they do not read coverage.)

<a id="goals-g8-no-human-decision-requests"></a>
### G8: the DecisionObject is written and nobody reads it; no decision requests; L4 still plans without a human

`goals-g8-no-human-decision-requests` · **P1** · missing · owner **claude+harsh** · code · step **S32**

- **Expected:** decision_requests answered by a human; executions only from an approved choice, carrying goal_refs and decision_request_id; a human_decides switch per tenant; an agent's 'done' is only a report. _(source: speedrun008/GeniOS-009/STEP-G8-a-human-decides-then-delegation.md §2–§3)_
- **Actual:** The DecisionObject is written into situation_interpretations (context/l2_admission.py:163), but nothing under genios_engine/executive or deliver references situation_interpretations. executive/decisions.py and contracts/decision.py are absent. execution.v1 has goal as free text (contracts/execution.py:413).
- **Evidence (measured):** `genios_engine/context/l2_admission.py:163`; `grep -rln situation_interpretations genios_engine/executive genios_engine/deliver → 0 files`; `ls genios_engine/executive/decisions.py genios_engine/contracts/decision.py → No such file`; `genios_engine/contracts/execution.py:413`
- **What Rohit sees:** Work is planned from signals, not from a founder's choice, and no execution carries a goal.
- **Fix:** Build STEP-G8 (GeniOS-008 L4-1) behind human_decides.
- **Depends on:** [goals-g4-no-goal-situation-links](#goals-g4-no-goal-situation-links), [goals-g7-no-checkin-states](#goals-g7-no-checkin-states)
- **Verified:** confirmed by the skeptic (This is stronger than stated: nothing anywhere selects or joins situation_interpretations. grep in genios_engine and scripts finds only the inserts, the tenant delete list (api/account_routes.py:937) and prose. The code declares the table write-only itself at platform/table_coverage.py:133-139 ('nothing selects from it … the reader never arrived'). executive/decisions.py and contracts/decision.py are absent, and decision_request and human_decides have 0 hits. contracts/execution.py:413 requires goal as free text.)

<a id="goals-judgment-cannot-propose-goal"></a>
### The judgment cannot propose a goal, so graph context such as the Antler Singapore admission never becomes one

`goals-judgment-cannot-propose-goal` · **P1** · missing · owner **rohit** · mixed · step **S26**

- **Expected:** Inferred goals are proposed for approval and are never active without a human (GeniOS-009 D7). A founder milestone visible in the graph becomes a proposed goal. _(source: speedrun008/GeniOS-009/08-DECISIONS.md D7; F2 (Rohit's Antler report))_
- **Actual:** L2's proposals are situation ops only: create/update/merge/close/link (contracts/reasoning_result.py:93-95). The only automatic goal proposer is the weekly brief drafter, which reads memory patterns, never the graph's situations (F3; reason/brief_drafter.py, reason/brief_patterns.py). D7 keeps that as the only source, and 'or later L2's' has no unit.
- **Evidence (mixed):** `genios_engine/contracts/reasoning_result.py:93-95`; `genios_engine/reason/brief_drafter.py`; `speedrun008/GeniOS-009/08-DECISIONS.md:16 (D7)`
- **What Rohit sees:** No goal: work the founder is plainly pursuing (an accelerator admission) never becomes a goal that cards could link to.
- **Fix:** Add a goal proposal to the judgment's output (e.g. proposed_goal with why and evidence ids), filed through the brief's existing proposal door as 'proposed'. Extend D7 to make L2 a goal source.
- **Blocked on:** Rohit: extend D7 so the L2 judgment may propose goals, in addition to the brief drafter.
- **Depends on:** [goals-not-in-judgment](#goals-not-in-judgment)
- **Verified:** confirmed by the skeptic (MUTATION_OPS is ('create','update','merge','close','link'), situations only (reasoning_result.py:93-95). The L2 judgment has no goal op or field. GeniOS-009/08-DECISIONS.md:16 (D7) names 'the brief drafter' as the door. One adjacent path is not a proposer: capture/internal_knowledge.py:56 and :92 let an uploaded document tagged goal/okr/objective become company canon at authority rank 4. That is a founder-uploaded document, not an inferred goal, and it creates no goal object.)

<a id="goals-no-goal-in-l3"></a>
### L3 has no goal object and no goal↔situation link, and the planned link (G4) depends on an admission that cannot see reading situations

`goals-no-goal-in-l3` · **P1** · missing · owner **claude** · code · step **S28**

- **Expected:** L3 keeps accepted, traceable goal↔situation links (many-to-many), written only on ADMIT for a live goal. _(source: speedrun008/GeniOS-009/STEP-G4-goal-situation-links.md (Status: planned; Needs G3, G0.3))_
- **Actual:** No goal table exists. Migrations end at 0250_screen_followup_read_path.sql, not 0249 as F3 said; 0250 is not about goals. Admission sees only file-anchored situations (l3-admission-cannot-see-reading-situations), so even after G4, awaiting-reply and commitment situations could not carry a goal link.
- **Evidence (mixed):** `ls migrations | tail → 0248, 0249_l2_admissions.sql, 0250_screen_followup_read_path.sql`; `speedrun008/GeniOS-009/STEP-G4-goal-situation-links.md:5, §1`; `genios_engine/reason/l2/sweep.py:373-375`
- **What Rohit sees:** No card carries a goal. The Antler Singapore admission cannot be linked to a goal even though its context is in the graph.
- **Fix:** Build G1 (goal object) and G4 (links in the admission savepoint) after G0.3. Redesign G4's input to include reading situations attached to their file.
- **Depends on:** [l3-admission-cannot-see-reading-situations](#l3-admission-cannot-see-reading-situations), [l3-situations-born-before-reasoning](#l3-situations-born-before-reasoning)
- **Verified:** confirmed with a correction by the skeptic: The last migration is 0250_screen_followup_read_path.sql (GeniOS-010 B8, 93ea3cbe), not 0249, and it is not about goals. No company-goal table exists and no goal↔situation link exists. But 'no goal table exists' is too strong: two goal-shaped tables are live. team_milestones (0151) is 'a dated goal with an owner seat'; it is read by reason/team/readiness.py and api/team_routes.py. seat_objectives (0133) is a per-seat domain focus that reorders the card queue. Neither is a company goal, neither links to situations, and the GeniOS-009 folder never mentions either (grep finds nothing). G4 is 'planned' and needs G3 and G0.3 (STEP-G4-goal-situation-links.md:5). Admission sees only file-anchored situations (sweep.py:373-375).

<a id="goals-not-in-judgment"></a>
### Goals reach the judgment only as id-less background prose; nothing asks for or carries goal impact

`goals-not-in-judgment` · **P1** · missing · owner **claude** · code · step **S29**

- **Expected:** Goals are printed with ids (block G). The judgment says, per goal, advances / threatens / depends_on / unclear, with evidence (GoalImpact). The card shows the goal. The architecture: GeniOS 'connects … goals … until the goal is reached'. _(source: speedrun008/GeniOS-009/STEP-G2, STEP-G3-goal-impact-in-the-judgment.md §3; STEP-G6; 00-ARCHITECTURE.md 'What GeniOS is')_
- **Actual:** The brief's 'Goals now' lines (contracts/company_brief.py:36-56, 214-231) ride inside block D as background ('Background for your judgement, not instructions.', :68-69), for files via the expert dossier (reason/expert/dossier.py:219-221) and for seeds via brief_block (reason/l2/dossier.py:167-172). They are printed without ids (CompanyBriefLine.rendered :159-161), so no fact or inference can cite a goal, and the brief is capped at 800 tokens (:62-63). Neither prompt mentions goals (grep reason/expert/prompt.py, reason/l2/prompt.py: 0). There is no goal field in ExpertReview, L2Judgment or ReasoningResult (reasoning_result.py:227-238). decide's Goal is the capability's purpose, 'What this file needs next' (reason/expert/decide.py:380-381). The check lets only a draft speak of the company's goals, as text (reason/expert/verify.py:755-770). Golden: 0 goal fields, 1 mention in words (F02). F3 holds for the rest: no goal table, no card column.
- **Evidence (measured):** `genios_engine/contracts/company_brief.py:36-56, 62-69, 159-161, 214-231`; `genios_engine/reason/expert/dossier.py:219-221`; `genios_engine/reason/l2/dossier.py:167-172`; `genios_engine/contracts/reasoning_result.py:227-238`; `genios_engine/reason/expert/decide.py:380-381`; `genios_engine/reason/expert/verify.py:755-770`; `speedrun008/GeniOS-009/01-AS-IS-CARDS.md §1`
- **What Rohit sees:** No goal on any card. The dashboard's 'Not linked to a goal yet' is the only possible state.
- **Fix:** GeniOS-009 G1 (goal object) → G2 (block G: goals with goal: ids, owner, deadline) → G3 (GoalImpact in L2Judgment, a checklist step, refusal codes in validate_judgment, carried to the card) → G6 (card shows the goal).
- **Depends on:** [l2-judgment-half-dropped-confidence-cui](#l2-judgment-half-dropped-confidence-cui)
- **Verified:** confirmed by the skeptic (The 'Goals now' section is at company_brief.py:38 and :55, under the header 'Background for your judgement, not instructions.' (:65-66). Lines render as '- text <addr>' with no id (:159-161), and the budget is 800 tokens (:62-63). The brief reaches files through expert/dossier.py:219-221 and seeds through l2/dossier.py:167-172. A grep for 'goal' finds 0 hits in reason/expert/prompt.py, reason/l2/prompt.py, contracts/reasoning_result.py and contracts/expert_review.py. decide's Goal is 'What this file needs next' (expert/decide.py:380-381). about_us includes goals for drafts only (verify.py:757-769). Two side notes: migrations now end at 0250 (0250_screen_followup_read_path.sql, 93ea3cbe, 22 Oct), still with no goal table. 0151 team_milestones ('a dated goal with an owner seat') feeds only reason/team/readiness, not the judgment.)

<a id="goals-thread-objective-history-missing"></a>
### Historical mail never got its business facts (thread.objective, party.role): backfill_business_facts has no caller, so the goal drafter sees objectives only from mail processed after the fix

`goals-thread-objective-history-missing` · **P1** · built, not live · owner **claude+harsh** · mixed · step **S09**

- **Expected:** Every kept item enters memory, and the goal proposer reads the founder's thread objectives. _(source: F3 (reason/brief_patterns reads thread objectives); genios_engine/context/backfill.py:481-498)_
- **Actual:** The function exists to re-grade stored L1 extractions. Measured on the pilot on 15 Sep, the extractor had emitted 1,211 business facts and the graph held 5; 256 of 267 thread.objective were verifiable with no model call. The function has no caller in genios_engine/ or scripts/, and context_health declares it UNREACHED.
- **Evidence (mixed):** `genios_engine/context/backfill.py:481-498`; `genios_engine/context/context_health.py:54-57`
- **What Rohit sees:** The weekly brief drafter's goal proposals miss everything older than mid-September.
- **Fix:** Add a scripts/ runner with a dry run and counts. Harsh runs it once per tenant in a window.
- **Blocked on:** Production read: select date_trunc('month', f.created_at) m, count(*) from graph_facts f where f.org_id='<rohit_org>' and f.field='thread.objective' and f.valid_to is null group by 1 order by 1;
- **Verified:** confirmed with a correction by the skeptic: backfill_business_facts has no caller in genios_engine/ or scripts/; the only references are AST and source inspection in tests/context/test_the_nine_business_nouns_were_never_written.py. context_health.py:54-57 declares it UNREACHED. But it is not the only path that could restore history. scripts/rebuild_graph.py replays every event through runner._safe_process_one → _process_one (rebuild_graph.py:37, :101-113). That path grades the cached extraction (runner.py:195 graded_extraction, added a87a70d8 on 13 Sep), and the script has rebuilt mail since eddc2d2b (12 Oct). So whether the founder's history has thread.objective facts depends on whether that script was run in production after 13 Sep. Only a production read can say: select count(*), min(occurred_at), max(occurred_at) from graph_facts where org_id='<rohit org>' and field='thread.objective' and status='active';

<a id="surfaces-b1-no-goal-on-any-surface"></a>
### No surface can show a goal: GET /v1/goals (B1) is unbuilt, and every goal slot is a fixed string or null

`surfaces-b1-no-goal-on-any-surface` · **P1** · missing · owner **claude** · code · step **S31**

- **Expected:** Every card and item shows the goal it moves ('Goal at stake … advances · due …', goal_refs from G4/G6). Home section 1 shows this month's goals with progress. 'Goals formed' counts goals. _(source: speedrun008/GeniOS-009/06-CARDS-TARGET.md:14,38; speedrun008/GeniOS-010/03-GOALS/01-GOALS-PAGE.md §5; 02-DASHBOARD-HOME/05-BRAIN-WORK.md B1; memory cards-ux-analysis-22-oct (Rohit's card contract: 'the goal it moves'))_
- **Actual:** The brain has no /v1/goals route and no goal fields on cards (F3). The web Cards panel hard-codes 'Not linked to a goal yet'. Mac 0.3.4 sets goal: null on every card and screen item. Goals page live sets linked:false, target 'Not set yet' and puts every card under 'not linked to a goal yet'. Screen sets goals: [].
- **Evidence (measured):** `route list from an AST walk of genios_engine/api/*.py: no path containing 'goals'`; `dashboard origin/main:src/app/dashboard/cards/page.tsx:924-925`; `dashboard origin/rohit/desktop-ux:Extension/src/menu/live.ts:70,103 (goal: null)`; `dashboard origin/main:src/product/internal/dashboard/goals/live.ts:12-14,151-153,215`; `dashboard origin/main:src/product/internal/dashboard/screen/live.ts:198-200`
- **What Rohit sees:** No card carries a goal, which is Rohit's complaint F2. The Antler Singapore goal could not appear on any surface even if it were proposed.
- **Fix:** Build GeniOS-009 G1 (goal object) + G5 (progress) → GET /v1/goals with the fields in 01-GOALS-PAGE.md §5, then G4 links and G6 goal_refs on the card. The dashboard mappers (goals/live.ts, card-read.ts, menu/live.ts) then set linked:true. C1's 'suggested goal' can fill the card row before G4.
- **Blocked on:** Rohit opens GeniOS-009 G1 (plan only today; memory wait-for-rohit-to-open-a-layer)
- **Depends on:** [GeniOS-009 G1](#GeniOS-009 G1), [GeniOS-009 G4](#GeniOS-009 G4), [GeniOS-009 G5](#GeniOS-009 G5), [GeniOS-009 G6](#GeniOS-009 G6), [06-CARDS C1/C8](#06-CARDS C1/C8)
- **Verified:** confirmed by the skeptic (An AST walk of every @router/@app decorator under genios_engine (378 routes; prefixes checked: /v1/executive, /admin, /auth, /v1/mapping) finds no path containing 'goal'. grep finds no goal_refs, goal_id-on-card or card_copy in genios_engine or migrations (migrations now end at 0250, a screen migration). The dashboard side holds: cards/page.tsx:924-925 is the fixed row 'Not linked to a goal yet'. desktop-ux Extension/src/menu/live.ts:70 and :103 set goal: null. goals/live.ts:12-14 (the comment), :151-153 (target 'Not set yet') and :215 (linked:false, every card in unlinked). screen/live.ts:200 sets goals: [].)

<a id="goals-g9-outcomes-move-no-goal"></a>
### G9: verified outcomes move no goal; no progress events; macv_ledger still has no writer

`goals-g9-outcomes-move-no-goal` · **P2** · missing · owner **claude** · code · step **S33**

- **Expected:** goal_progress_events appended only on a verified outcome; completion proposed and confirmed by the founder; goal_outcome learning candidates sent through brain_pipeline (≥3 independent); macv_ledger left until D4. _(source: speedrun008/GeniOS-009/STEP-G9-outcomes-move-goals.md §2–§3)_
- **Actual:** feedback/goal_learning.py and the goal_progress_events table are absent. macv_ledger appears only in comments (platform/table_coverage.py:59,101; api/intelligence_routes.py:795), and no 'insert into macv_ledger' exists.
- **Evidence (measured):** `ls genios_engine/feedback/goal_learning.py → No such file`; `grep -rn 'insert into macv_ledger' genios_engine → 0 hits`; `genios_engine/platform/table_coverage.py:59`
- **What Rohit sees:** No 'Goal reached — confirm' or 'goal at risk' cards are possible.
- **Fix:** Build STEP-G9 after G5, G7 and G8. macv_ledger waits for Rohit's D4.
- **Blocked on:** D4 (what counts as recovered value) for the macv part
- **Depends on:** [goals-g5-no-goal-progress](#goals-g5-no-goal-progress), [goals-g7-no-checkin-states](#goals-g7-no-checkin-states), [goals-g8-no-human-decision-requests](#goals-g8-no-human-decision-requests)
- **Verified:** confirmed with a correction by the skeptic: The substance holds. feedback/goal_learning.py, goal_progress_events and goal_outcome are absent, and no insert or update into macv_ledger exists in genios_engine or scripts. Only migrations 0012 (create) and 0033 (FK) touch the table. One detail is wrong: macv_ledger is not 'only in comments'. It is also in the tenant delete list (api/account_routes.py:688) and in the served value_state string 'unavailable_macv_ledger_has_no_writer' (api/intelligence_routes.py:815).

<a id="layer-surfaces"></a>
## Surfaces (web dashboard, Mac app)

> The web dashboard at origin/main 2edfb86 now contains the GeniOS-010 navigation, home, Goals, Screen and Cards work. That includes Harsh's wiring to B5/B6/B8/B9. On the web Cards page, question cards take an Answer, Done is hidden where the brain refuses it, Feedback carries a reason, your words and a scope, Later takes a picked day, and refusals stay on screen. The routes and response shapes match the brain at 0cc8d83c. Brain items B3, B4, B5, B6, B8 (S1–S6 and S8) and B9 are built and in the production branch. B1 (GET /v1/goals) and B2 (the AER/HIR rollup) are not built, and none of the card-writer items C1–C9 exist. So no surface shows a goal: Cards hard-codes "Not linked to a goal yet", the Mac app sets goal: null, and Goals and Screen list every card as unlinked. The home ignores the brief's accepted goals and always says "No goals set yet". Delegate is drawn but locked on web and Mac, because POST /cards/{id}/delegate does not exist. Two things on the home tell a signed-in customer something false: the bell shows four static notices ("HubSpot sync failed", "Pricing policy blocked 2 actions"), and "No action bypassed a hard rule" / "Policy-safe 100%" is a constant, not a measurement. The Mac app exists in three versions. Rohit runs 0.3.4 from the unmerged branch rohit/desktop-ux. main holds 0.2.4, where "Not useful" sends no reason and Done on a question card is refused, and both refusals are swallowed. The dashboard's download serves a zip from 14 Sep ("Desktop 0.2.0"). The Goals and Screen pages map cards with their own mapper. It shows the brain's verdict code ("reply", "review_source") as "What to do" and inference labels as proof, so one card reads differently on Cards, Goals and Screen. Cards look thin or repeated because the card writer (C1), the expert's result on the card (C2) and per-card context (C6) are unbuilt, and the surfaces' guard hides every line one card shares with another. Two production facts could not be checked without Rohit's permission: whether migration 0250 is applied, and whether the live dashboard was deployed before the brain dropped snapshot.notice (B9).

| Item | Sev | Status | Owner | Step |
|---|---|---|---|---|
| [A failed or partial sync is recorded but the founder never sees it; the ops alert is only a log line unless a ](#l1-refusal-and-coverage-invisible) | P1 | partial | claude+harsh | S10 |
| [The Screen page and the desktop's screen items depend on migration 0250 being applied in production](#surfaces-0250-applied-unverified) | P1 | unknown until production is read | harsh | S02 |
| [B9 removed snapshot.notice, which the old dashboard reads unguarded; the deploy order was never verified](#surfaces-b9-deploy-order-unverified) | P1 | unknown until production is read | harsh | S02 |
| [YC-II D9 (STEP-15): the 08:00 morning brief is composed and kept, but the dashboard and Mac app read the old '](#surfaces-d9-morning-brief-composed-but-no-surface-reads-it) | P1 | built, not live | claude | S36 |
| [Delegate is drawn on every card but cannot be pressed: the brain has no delegate route (C5)](#surfaces-delegate-locked-c5) | P1 | missing | claude | S35 |
| [The home bell shows four made-up system notices to every signed-in customer](#surfaces-fake-bell-notices) | P1 | broken | claude | S39 |
| [Goals and Screen read cards with their own mapper: 'What to do' shows a verdict code, and inference labels sho](#surfaces-goals-screen-own-card-mapper) | P1 | broken | claude | S39 |
| [Home page always says there are no goals, even when the brief holds accepted goals](#surfaces-home-goals-always-empty) | P1 | broken | claude | S27 |
| [The home says 'No goals set yet' and 'Goals are coming next' even when the brief holds accepted goals](#surfaces-home-ignores-brief-goals) | P1 | broken | claude | S27 |
| [The Mac app on main (0.2.4) and the downloadable 0.2.0 lose presses: 'Not useful' and Done on question cards a](#surfaces-mac-main-silent-refusals) | P1 | broken | rohit+harsh | S38 |
| [Three Mac apps in circulation: Rohit's 0.3.4 is unmerged, main is 0.2.4, and the dashboard download is a 0.2.0](#surfaces-mac-three-versions) | P1 | built, not live | rohit+harsh | S38 |
| [The home claims 'No action bypassed a hard rule' and 'Policy-safe 100%' without measuring it](#surfaces-policy-safe-constant-claim) | P1 | partial | claude | S39 |
| [Question cards and team/verify cards reach only GET /cards; Home 'Today', MCP, the agent API, push lanes, /v1/](#surfaces-question-and-team-cards-reach-only-the-cards-page) | P1 | partial | claude | S36 |
| [GeniOS-010 B3, B4, B5, B6, B8 (S1–S6, S8) and B9 are built in the brain and wired in dashboard main](#surfaces-b-items-built) | P2 | done (lesson only) | claude | S42 |
| [AER and HIR have no weekly series (B2): AER is locked and blurred, HIR shows readiness only](#surfaces-b2-aer-hir-rollup-missing) | P2 | missing | claude | S33 |
| [No surface shows the architecture's card parts: the confidence vector, unknowns, options, authority, or why-no](#surfaces-card-shape-vs-architecture) | P2 | missing | claude | S22 |
| [Cards past the 40th never load their detail, even when opened](#surfaces-cards-detail-cap-40) | P2 | partial | claude | S35 |
| [Reports and Memory pages call routes the brain lacks, and the Documentation page advertises seven non-existent](#surfaces-dead-routes-gated-pages-and-docs) | P2 | broken | claude | S39 |
| [Web Cards offers Feedback on answered question cards, which the brain refuses, and the error text says 'give f](#surfaces-feedback-on-answered-card) | P2 | broken | claude | S35 |
| [Goals page draws empty-domain cards under Admin and collapses other domains' cards to a count](#surfaces-goals-domain-fold-r2) | P2 | partial | claude | S39 |
| [Goals page: approval needs typing to be useful, the answers become free text, and the drafter's evidence is ne](#surfaces-goals-page-proposal-flow) | P2 | partial | claude | S27 |
| [Home week tiles are labelled as situations formed and closed, but count recomputed situations and execution ou](#surfaces-home-tiles-measure-other-things) | P2 | partial | claude | S39 |
| [Resources: manual entries vanish on reload, edit and delete hit routes that do not exist, and settings are loc](#surfaces-resources-manual-context-dead-routes) | P2 | broken | claude | S39 |
| [The brain serves which screen items fed a card, but the Cards page never shows it](#surfaces-screen-items-unread-on-cards) | P2 | partial | claude | S35 |

<a id="l1-refusal-and-coverage-invisible"></a>
### A failed or partial sync is recorded but the founder never sees it; the ops alert is only a log line unless a webhook is set

`l1-refusal-and-coverage-invisible` · **P1** · partial · owner **claude+harsh** · mixed · step **S10**

- **Expected:** A refusal nobody can see is a silent stop. The founder can see 'read N of about M' and whether a window failed. _(source: memory a-fail-closed-after-the-claim-loses-the-week ('a refusal nobody can see is a silent stop'); 00-START-HERE ('coverage says 18 of about 465'); 05-BLUEPRINT Part 7 'Negative-result honesty', 'Production observability')_
- **Actual:** On failure the sweep writes the error to l1_sync_runs and calls ops_alert.notify (routes.py:1199-1227, 610-617). notify only logs a warning when GENIOS_OPS_ALERT_WEBHOOK is empty (ops_alert.py:15-21). /coverage, /coverage/declared and /context/coverage-window exist (routes.py:2817, 2830; quality_routes.py:119), but the dashboard at origin/main 2edfb86 calls none of them and shows no archived count and no claimed_total. The sources page shows only a per-tool error state (sources-page.tsx:266, 320). Only an explicit credential refusal marks a connection disconnected (routes.py:1216-1221).
- **Evidence (measured):** `genios_engine/api/routes.py:1199-1227`; `genios_engine/api/routes.py:610-617`; `genios_engine/platform/ops_alert.py:15-21`; `genios_engine/api/routes.py:2817,2830`; `dashboard origin/main: git grep for coverage-window|/coverage|claimed_total → no calls`; `dashboard origin/main:src/components/sources/sources-page.tsx:266,320`
- **What Rohit sees:** Fewer cards with no explanation: a broken or truncated sync looks like a quiet week.
- **Fix:** Harsh sets GENIOS_OPS_ALERT_WEBHOOK in production. Show on the dashboard's Sources page, per connection: the last run, finished or truncated, scanned vs claimed_total, archived, the error, and the coverage window state (Claude adds the endpoint shape, Harsh wires the page).
- **Blocked on:** Production: select finished_at, source, mode, scanned, emitted, archived, parked, duplicate, cursor_exhausted, page_budget_spent, claimed_total, left(error,200) from l1_sync_runs where org_id='<ORG>' and finished_at >= '2026-10-18' order by finished_at desc limit 60;
- **Verified:** confirmed by the skeptic (Cited lines hold (routes.py:1200-1227, 610-617; ops_alert.py:15-21; coverage routes at routes.py:2817/2830 and quality_routes.py:119). The dashboard at origin/main never calls /coverage, /coverage/declared, coverage-window or claimed_total. Stronger than stated: the sources page's per-tool 'error' comes from /integrations/status, where freshness='error' only when the Composio account is not ACTIVE and syncStatus is only running or idle (routes.py:3455-3462). A failed sync in l1_sync_runs never reaches it. l1_sync_runs is read only by the admin console (admin_routes.py:114-117, 341). The home 'coverage' value is decisions/situations (home_routes.py:~275), not capture coverage. _notify_sync_failure also emits a PostHog event (routes.py:613-617), which the founder does not see either.)

<a id="surfaces-0250-applied-unverified"></a>
### The Screen page and the desktop's screen items depend on migration 0250 being applied in production

`surfaces-0250-applied-unverified` · **P1** · unknown until production is read · owner **harsh** · prod_action · step **S02**

- **Expected:** 0250 is applied at boot (apply_migrations), so GET /v1/followups can select read_by and due_phrase. _(source: migrations/0250_screen_followup_read_path.sql; genios_engine/main.py:77-96)_
- **Actual:** followups.listing now selects read_by, due_phrase and graph_written_at. If the database booted read-only ('DEGRADED BOOT') and 0250 did not land, every /v1/followups read fails. Whether it is applied in production is unknown.
- **Evidence (measured):** `genios_engine/reason/moments/followups.py:319,341-342`; `migrations/0250_screen_followup_read_path.sql:12-13`; `genios_engine/main.py:89-96 (boot apply; read-only path logs DEGRADED BOOT)`
- **What Rohit sees:** None on cards. If missing, Screen shows no items and the Mac Pending list loses screen items.
- **Fix:** Harsh runs the read-only check below. If 0250 is missing, apply it (or restart the brain with a writable DB so boot applies it).
- **Blocked on:** select filename from schema_migrations where filename like '0250%'; select column_name from information_schema.columns where table_name='screen_followups' and column_name in ('read_by','due_phrase');
- **Verified:** confirmed with a correction by the skeptic: The dependency is wider than GET /v1/followups. The shared column list _COLS (reason/moments/followups.py:318-319) names read_by, due_phrase and graph_written_at, and every screen_followups path uses it. That covers the device slice open_items (:397), the capture upsert's RETURNING (:654, which also writes read_by and due_phrase), resolve (:712, :715), snooze (:735, :738), get_item (:750) and listing (:781). The moment routes pass read_by and due_phrase to F.upsert (moment_routes.py:515, :610). Without 0250, screen capture writes, the desktop's open-item slice, resolve/snooze and the Screen page would all fail. Not only the Screen read would break. graph_written_at itself comes from 0162, so it is not at risk.

<a id="surfaces-b9-deploy-order-unverified"></a>
### B9 removed snapshot.notice, which the old dashboard reads unguarded; the deploy order was never verified

`surfaces-b9-deploy-order-unverified` · **P1** · unknown until production is read · owner **harsh** · prod_action · step **S02**

- **Expected:** The dashboard ships 238f45e or later (notice-board deleted) before the brain at 0cc8d83c goes live: 'deploy the dashboard first'. _(source: brain commit e0d58c8c message; speedrun008/GeniOS-010/LOG.md (B3–B9 line))_
- **Actual:** The brain no longer sends snapshot.notice. Dashboard 6ddc4db, which memory measured as the live site on 22 Oct, destructures notice from snapshot and renders notice.title. With the new brain that throws, and the home falls to the error boundary. main 2edfb86 has no notice-board. Which dashboard commit is deployed is unknown.
- **Evidence (mixed):** `genios_engine/api/home_routes.py:299-300 (notice dropped, B9)`; `dashboard 6ddc4db:src/product/internal/dashboard/homepage/sections/notice-board.tsx:48,62 (notice.title unguarded)`; `dashboard 6ddc4db:src/product/internal/dashboard/homepage/company-intelligence-home.tsx:72`; `memory genios-ui-surfaces.md (live = 6ddc4db on 22 Oct)`
- **What Rohit sees:** None on Cards. If the order was wrong, the home page fails to render.
- **Fix:** Harsh confirms the DigitalOcean App Platform deployment of brain.thegenios.com is at 2edfb86 or later before or with the brain at 0cc8d83c. If not, redeploy the dashboard.
- **Blocked on:** Production check, not a database read: the deployed commit of the dashboard app (DO App Platform deployments list) vs the brain's deployed commit.
- **Verified:** unverifiable without production: The code facts hold. Brain e0d58c8c (an ancestor of 0cc8d83c) dropped snapshot.notice; the B9 comment is at home_routes.py:303-304, not :299-300. Dashboard 6ddc4db notice-board.tsx:48 destructures notice and :62 renders notice.title unguarded, and 6ddc4db company-intelligence-home.tsx:72 mounts it. 6ddc4db has src/app/dashboard/error.tsx, so a throw lands on the error boundary. main 2edfb86 has no notice-board.tsx, and 238f45e is an ancestor of main. Two facts lower the risk. Harsh committed dashboard 2edfb86 at 2026-10-22 19:35:40 +0530, one minute after brain 0cc8d83c (19:34:42). GeniOS-010/00-START-HERE.md also says 'brain.thegenios.com serves main'. Whether the hosting provider actually deployed 2edfb86, and whether it went live before or after the brain, is visible only on the hosting dashboard or the live site's JS. Harsh or Rohit has to answer, for example by checking the deployed commit SHA in the hosting provider's deployment list.

<a id="surfaces-d9-morning-brief-composed-but-no-surface-reads-it"></a>
### YC-II D9 (STEP-15): the 08:00 morning brief is composed and kept, but the dashboard and Mac app read the old 'brief' endpoint

`surfaces-d9-morning-brief-composed-but-no-surface-reads-it` · **P1** · built, not live · owner **claude** · code · step **S36**

- **Expected:** D9 default: the morning brief arrives on the Dashboard at 08:00 IST (screen reminders inside it, D8). _(source: speedrun008/YC-II W27/06-DECISIONS.md D8, D9; STEP-15-TO-BUILD-the-morning-brief.md)_
- **Actual:** STEP-15 is wired: compose_due runs every sweep after the org's local 08:00 and keeps the brief in morning_briefs, served at GET /v1/executive/morning. The dashboard's Today card calls /api/org/{id}/morning-brief, the older workspace route that ranks existing cards. No file in the dashboard repo (web or Mac app, origin/main 2edfb86) calls /v1/executive/morning.
- **Evidence (measured):** `genios_engine/api/routes.py:1041-1053 (_compose_due_briefs → executive.morning.compose_due)`; `genios_engine/api/executive_routes.py:26, 129-131 (/v1/executive/morning)`; `genios_engine/api/workspace_routes.py:243-247 (old /api/org/{org_id}/morning-brief)`; dashboard origin/main src/components/dashboard/today-card.tsx:7, 31; src/lib/api.ts:2424 (/api/org/${orgId}/morning-brief); `git grep 'executive/morning' on dashboard origin/main: no source hit`
- **What Rohit sees:** The chief-of-staff brief (what changed, stuck, due, screen reminders) is produced daily and seen nowhere. Rohit sees only a ranked list of the same cards.
- **Where the mistake was:** STEP-15 was counted built with its API route but without the surface switch. GeniOS-010's dashboard work did not pick it up.
- **Fix:** Claude, after the dummy-first step for UI changes, re-points the dashboard Today card and the Mac app to GET /v1/executive/morning (one line, five 'today' items, feedback marks), keeping the old route as fallback until a brief is kept.
- **Blocked on:** Whether briefs are being kept in production: select local_date, composed_at from morning_briefs where org_id='<ORG>' order by local_date desc limit 7;
- **Depends on:** [l5-b3-email-delivery-channel-missing](#l5-b3-email-delivery-channel-missing)
- **Verified:** confirmed by the skeptic (api/routes.py:1041-1056 _compose_due_briefs calls executive.morning.compose_due on every sweep. executive_routes.py:26 sets the prefix /v1/executive and :129-131 serves GET /morning. The old route is workspace_routes.py:243-247 /api/org/{org_id}/morning-brief. In the dashboard at origin/main 2edfb86, src/lib/api.ts:2424 calls /api/org/${orgId}/morning-brief, and today-card.tsx:7 says 'Backed by /morning-brief'. `git grep 'executive/morning\|v1/executive'` finds no source hit. The Mac app (Extension/src-tauri/src/moments/daily.rs:1) composes its own device-local morning brief ('no LLM, from the slice only') and does not call the engine's.)

<a id="surfaces-delegate-locked-c5"></a>
### Delegate is drawn on every card but cannot be pressed: the brain has no delegate route (C5)

`surfaces-delegate-locked-c5` · **P1** · missing · owner **claude** · code · step **S35**

- **Expected:** Done · Delegate (a team member, or an agent) · Later · Feedback. Hand-over sets the card's assignee and records a card event; an agent hand-over creates a delegation proposal the founder approves. _(source: speedrun008/GeniOS-010/06-CARDS/01-INTEGRATION.md §4 and §5 C5; memory cards-ux-analysis-22-oct round 2)_
- **Actual:** Web Cards has DELEGATE_LIVE = false: 'Hand over' and 'Ask it' are disabled with a lock. The brain's card action set has no delegate verb, and no /cards/{id}/delegate route exists. Mac 0.3.4 shows Delegate with people: [] (no team members at all) and no press.
- **Evidence (measured):** `dashboard origin/main:src/app/dashboard/cards/page.tsx:79-85,1232-1261`; `genios_engine/deliver/actions.py:36 (BUTTONS has no delegate)`; `route list from genios_engine/api: no /cards/{card_id}/delegate`; `dashboard origin/rohit/desktop-ux:Extension/src/menu/MenuApp.tsx:380`
- **What Rohit sees:** A card that belongs to a teammate cannot be routed from the card, so it stays in the founder's queue.
- **Fix:** Build C5: POST /cards/{card_id}/delegate {to_seat} (owner/admin; set cards.assignee, a human.card_action event with cause delegate). Then set DELEGATE_LIVE=true on the web and give the Mac app the same press and the members list. Keep 'to an agent' locked while Agents stays locked (Rohit's call).
- **Verified:** confirmed with a correction by the skeptic: The web lock, the missing verb and the missing /cards/{id}/delegate route all hold. But the claim that 'the brain has no delegate route' is too broad. The agent half of hand-over already exists: POST /v1/delegations takes {card_id, play, params, agent_id} (delegation_routes.py:85-100), and executive/delegation.create_proposal accepts card_id (executive/delegation.py:402-421). It comes with /v1/delegations/{id}/approve and /reject (:124, :135), and main.py:217-218 registers it. The dashboard already has a client, src/lib/api-delegations.ts (used by components/governance/agent-actions.tsx), but the Cards page does not call it. What is truly missing is the hand-over to a person (set cards.assignee plus a card event) and a server-built play from the card, which is the C5 spec in 06-CARDS/01-INTEGRATION.md §C5. POST /v1/executive/commitments/{execution_id}/reassign (executive_routes.py:331) reassigns commitments, not cards.

<a id="surfaces-fake-bell-notices"></a>
### The home bell shows four made-up system notices to every signed-in customer

`surfaces-fake-bell-notices` · **P1** · broken · owner **claude** · code · step **S39**

- **Expected:** No made-up number or event reaches a signed-in customer: live mode shows real values or says 'not measured yet'. Notices should come from source health (/integrations/status) and plan state (billing). _(source: speedrun008/GeniOS-010/00-START-HERE.md 'Ground rules the design keeps' rule 1; notices.ts own header comment)_
- **Actual:** Notifications renders the static systemNotices array: 'HubSpot sync failed · 12 min ago', 'Drive indexing is behind · 84 documents', 'Credits below 40%', 'Pricing policy blocked 2 actions', with 2 unread on the badge. It sits in the home header for every workspace.
- **Evidence (measured):** `dashboard origin/main:src/product/internal/shared/notices.ts:18-51 (static systemNotices)`; `dashboard origin/main:src/product/internal/shared/page-header.tsx:14,25,60 (reads systemNotices, unread badge)`; dashboard origin/main:src/product/internal/dashboard/homepage/company-intelligence-home.tsx:104 (<Notifications /> on the home); `memory genios-ui-surfaces.md: 'the fake bell notices are in the live JS' (measured live 22 Oct)`
- **What Rohit sees:** None on cards directly. Rohit and customers see false alerts on the first screen (a HubSpot failure and a policy block that never happened).
- **Where the mistake was:** Flagged on 22 Oct (genios-ui-surfaces) and left on main through the GeniOS-010 home rebuild. That rebuild set the 'no made-up number' rule but kept <Notifications/> as it was.
- **Fix:** Build the notices from /integrations/status (a source in error or stale state) and /api/org/{org}/billing/subscription (credits below a threshold). Show no badge when there are none. Delete the static array. Per Rohit's 'dummy first' rule, show him the bell's states before editing the real file.
- **Verified:** confirmed by the skeptic (Re-read on dashboard origin/main 2edfb86. notices.ts:18-51 is a static array of the four made-up notices (HubSpot 12 min ago, Drive 84 docs, Credits below 40%, Pricing policy blocked 2 actions), two of them unread:true. page-header.tsx:14 imports it, :25 counts unread, :60 maps it. company-intelligence-home.tsx:104 renders <Notifications /> with no mode check, so every workspace sees it. One detail is slightly off: the badge itself is a plain dot (page-header.tsx:47-49). The '2 unread' text is in the aria-label (:43) and the panel header (:56). The real sources a fix would read do exist in the brain: GET /integrations/status (routes.py:3414) and GET /api/org/{org_id}/billing/subscription (billing_routes.py:95).)

<a id="surfaces-goals-screen-own-card-mapper"></a>
### Goals and Screen read cards with their own mapper: 'What to do' shows a verdict code, and inference labels show as proof

`surfaces-goals-screen-own-card-mapper` · **P1** · broken · owner **claude** · code · step **S39**

- **Expected:** One reader for a card everywhere (lib/card-read.ts readCard/ownCard). The move is shown in words, quotes are shown, and inference labels never appear as proof. _(source: speedrun008/GeniOS-010/06-CARDS/01-INTEGRATION.md §7; 06-CARDS/03-WHAT-WAS-THERE.md G1/G2 (status Open))_
- **Actual:** goals/live.ts cardItem sets recommended = decision.recommendation.verdict. The brain's projection fills that with codes such as 'review_source', 'reply' or a play id. proofOf prints row.inference ('an inference, not a quote') as evidence and drops quotes. Screen imports the same cardItem for the cards an item fed, so one card reads differently on Cards, Goals and Screen.
- **Evidence (measured):** `dashboard origin/main:src/product/internal/dashboard/goals/live.ts:74-83,94`; `dashboard origin/main:src/product/internal/dashboard/screen/live.ts:19`; `genios_engine/api/routes.py:5120-5137 (verdict codes)`; `speedrun008/GeniOS-010/06-CARDS/03-WHAT-WAS-THERE.md G1 (the stand-in brain hid it by putting a sentence there)`
- **What Rohit sees:** On Goals and Screen, a card's 'what to do' reads as a code ('reply'), and its proof is a label, not a quote.
- **Where the mistake was:** Goals was built with its own mapper before Cards built readCard. The stand-in brain (02-DASHBOARD-HOME/tools/mock_brain.py) put a sentence where the real brain sends a code, so the render checks passed.
- **Fix:** Map Goals' and Screen's cards through readCard/ownCard and render the existing CardItem from a CardRead. Delete proofOf and the verdict read.
- **Verified:** confirmed by the skeptic (goals/live.ts:94 sets recommended = str(rec.verdict). routes.py:5120-5137 fills verdict with codes: 'review_source', card.get('play') or reason_code, 'reply', 'deliver', 'follow_up'. proofOf (goals/live.ts:74-84) prefers statement, field/value, question, inference, because, text. It never reads quotes, and it prints row.inference, which the brain fills with the SITUATION_IS label 'the expert's reading of the file — an inference, not a quote' (decide.py:337; why row at pipeline.py:293). screen/live.ts:19 imports cardItem, and :193 uses it. 06-CARDS/03-WHAT-WAS-THERE.md G1 and G2 list both as Open. One more defect in the same mapper: cardItem maps every entry of decision.confidence (goals/live.ts:100-104), and level() returns 'medium' for anything that is not a number (:67-70). The brain's block (routes.py:5086-5100) has null dimensions, a list 'absent' and a string 'source'. So an absent dimension, plus 'Absent' and 'Source' chips, are all drawn as 'medium' confidence on Goals and Screen (intel/parts.tsx:262-275).)

<a id="surfaces-home-goals-always-empty"></a>
### Home page always says there are no goals, even when the brief holds accepted goals

`surfaces-home-goals-always-empty` · **P1** · broken · owner **claude** · code · step **S27**

- **Expected:** Home §1 'This month's goal' shows the live goals (from GET /v1/goals once G1/G5 exist). Until then it shows at least the accepted brief goals with 'progress unknown'. 'Goals formed' counts approvals this month. The 'No goals set yet' check appears only when there are none. A 'goals waiting for you' line shows pending proposals. _(source: speedrun008/GeniOS-010/03-GOALS/README.md §1, §6 steps 3–5; D-010-G1, D-010-G2)_
- **Actual:** Dashboard origin/main 2edfb86: genios-at-work.tsx:658 sets 'const goals = sample ? SAMPLE_GOALS : []', so live mode always renders MonthOnly. homepage/live.ts:290-298 hard-codes 'Goals formed' as value '0' with the note 'Goals are coming next'. homepage/live.ts:374 always pushes 'No goals set yet…'. The Goals page, by contrast, lists the accepted brief goal lines (goals/live.ts liveGoalsView), so the two surfaces contradict each other.
- **Evidence (measured):** `git show origin/main:src/product/internal/dashboard/homepage/sections/genios-at-work.tsx (line 658)`; `git show origin/main:src/product/internal/dashboard/homepage/live.ts (lines 290-298, 374)`; `git show origin/main:src/product/internal/dashboard/goals/live.ts liveGoalsView`
- **What Rohit sees:** The founder is told he has no goals on the home page while the Goals page lists them.
- **Fix:** Map the accepted brief goal lines into GeniosAtWork now (pct null, i.e. unknown). Count 'Goals formed' by accepted_at this month. Show the 'No goals' check only when there are zero. Add 'N goals waiting for your approval' from pending goal proposals. Switch to GET /v1/goals when G1 and G5 land. Per memory, build a dummy first and get Rohit's approval before real files.
- **Blocked on:** Rohit's approval of the dummy (UI rule); D-010-G1/G2 for status and 'this month'
- **Verified:** confirmed by the skeptic (Dashboard origin/main 2edfb86: genios-at-work.tsx:658 has 'const goals = sample ? SAMPLE_GOALS : []', and :686-687 renders MonthOnly, which draws greyed SAMPLE_GOALS as a placeholder (:388-395). homepage/live.ts:290-298 hard-codes 'Goals formed' as '0' with 'Goals are coming next', and :374 always pushes 'No goals set yet…'. goals/live.ts:201 liveGoalsView maps the accepted brief 'goals' lines into goal cards, so the two surfaces disagree.)

<a id="surfaces-home-ignores-brief-goals"></a>
### The home says 'No goals set yet' and 'Goals are coming next' even when the brief holds accepted goals

`surfaces-home-ignores-brief-goals` · **P1** · broken · owner **claude** · code · step **S27**

- **Expected:** The home's first section shows this month's goals. The Goals page already reads the brief's accepted goal lines live, so the home can show them (progress unknown, not 0). _(source: memory dashboard-visual-style.md (home order: this month's goal first); speedrun008/GeniOS-010/00-START-HERE.md ground rules 1–2)_
- **Actual:** In live mode GeniosAtWork passes goals = []. It draws only how much of the month has gone, over faded SAMPLE_GOALS with the fixed text 'Goals are coming next'. liveChecks always pushes 'No goals set yet…'. 'Goals formed' is a fixed '0', 'Goals are coming next', and links to /dashboard/intelligence, the old query console that is no longer in the nav.
- **Evidence (measured):** `dashboard origin/main:src/product/internal/dashboard/homepage/sections/genios-at-work.tsx:658,686-688,393-401`; `dashboard origin/main:src/product/internal/dashboard/homepage/live.ts:289-300,374`; `dashboard origin/main:src/product/internal/dashboard/goals/goals-page.tsx:462 (Goals page does read getCompanyBrief)`
- **What Rohit sees:** None on cards. The first screen says there are no goals while the Goals page lists them.
- **Fix:** Read /v1/company-brief on the home (same call as the Goals page). Show the accepted goal lines with 'progress unknown'. Push the 'No goals set yet' check only when there are none. Point Goals formed at /dashboard/goals and count goals accepted this month from accepted_at. Show Rohit a dummy first.
- **Verified:** confirmed by the skeptic (genios-at-work.tsx:658 sets goals = sample ? SAMPLE_GOALS : [], so live mode always goes down the MonthOnly branch (:686-687). That branch draws faded SAMPLE_GOALS (:387-397) under the fixed text 'Goals are coming next…' (:398-402). homepage live.ts:289-300 fixes 'Goals formed' at '0' with the note 'Goals are coming next' and href /dashboard/intelligence, and :374 always pushes 'No goals set yet…'. Only goals-page.tsx (:457, :462) calls getCompanyBrief; the home never reads the brief. /dashboard/intelligence is the old query console (src/app/dashboard/intelligence/page.tsx header). The sidebar's Intelligence entry (sidebar.tsx:86-95) has href /dashboard/intelligence, but a group is drawn as a toggle <button> (sidebar.tsx:409-436), not a link, so the nav cannot reach that page.)

<a id="surfaces-mac-main-silent-refusals"></a>
### The Mac app on main (0.2.4) and the downloadable 0.2.0 lose presses: 'Not useful' and Done on question cards are refused and swallowed

`surfaces-mac-main-silent-refusals` · **P1** · broken · owner **rohit+harsh** · mixed · step **S38**

- **Expected:** Only the buttons a card offers are pressable, and a refusal is said, never swallowed (M1–M5 in 06-CARDS/03). surface='desktop' is sent so History can say where you acted. _(source: speedrun008/GeniOS-010/06-CARDS/03-WHAT-WAS-THERE.md M1–M5; 06-CARDS/01-INTEGRATION.md §7)_
- **Actual:** cardAction POSTs {action, reason: reason||null} with no surface and ends in .catch(() => {}). 'Not useful' sends wrong with reason null, and the brain answers 422 invalid_wrong_reason. Done shows on every card, including question cards, which the brain refuses with not_offered. The card is removed optimistically and comes back on refresh. There is no Answer button. Expert why rows render ': undefined'. Who the card is about is guessed from the headline by regex.
- **Evidence (measured):** `dashboard origin/main:Extension/src/desktop/api.ts:371-381`; dashboard origin/main:Extension/src/desktop/DesktopAdvisor.tsx:321-329 (optimistic remove), 492-499 (Done/Snooze/Not useful on every card), 129-135 (whyLine), 156 (entityOf); `genios_engine/deliver/actions.py:102-104 (invalid_wrong_reason), 43, 92-93 (question cards refuse do_it_myself)`; `dashboard origin/main:Extension/src-tauri/tauri.conf.json version 0.2.4`
- **What Rohit sees:** For anyone on 0.2.x, 'Not useful' feedback never reaches L6, question cards cannot be answered from the desktop, and dismissed cards reappear, which reads as 'weird'.
- **Where the mistake was:** The fix exists (rohit/desktop-ux) but was never merged or released.
- **Fix:** Ship rohit/desktop-ux (pressCard with surface='desktop', refusals said, the web reader, Answer on question cards), which fixes M1–M5. See surfaces-mac-three-versions.
- **Depends on:** [surfaces-mac-three-versions](#surfaces-mac-three-versions)
- **Verified:** confirmed with a correction by the skeptic: The behaviour holds, but the brain citations are off. The not_offered refusal for question cards is at deliver/actions.py:201-202 (QUESTION_OFFERS is at :43). For answered cards it is at :199-200. Lines 92-93 are only the ingest_action signature. invalid_wrong_reason is at actions.py:102-104, and routes.py:5626-5628 turns it into an HTTP 422.

<a id="surfaces-mac-three-versions"></a>
### Three Mac apps in circulation: Rohit's 0.3.4 is unmerged, main is 0.2.4, and the dashboard download is a 0.2.0 zip from 14 Sep

`surfaces-mac-three-versions` · **P1** · built, not live · owner **rohit+harsh** · mixed · step **S38**

- **Expected:** One Mac app on main, built and signed by the release workflow, and served by the dashboard's Download link. _(source: speedrun008/GeniOS-010/06-CARDS/01-INTEGRATION.md §7 ('that work is separate, with the Mac release'); dashboard .github/workflows/desktop-release.yml)_
- **Actual:** origin/rohit/desktop-ux (ed2724d, 0.3.4) is not an ancestor of origin/main. Its merge-base is main's tip 2edfb86, so merging it is a fast-forward. main's Tauri app is 0.2.4. /dashboard/download, linked from the sidebar footer, serves public/downloads/GeniOS-desktop-mac.zip, last changed 9f83fc7 on 2026-09-14 ('Desktop 0.2.0'). The only release tag is desktop-v0.1.0. The 07-GENIOS-DESKTOP docs live only on brain branch g010-desktop.
- **Evidence (measured):** `dashboard: git merge-base origin/main origin/rohit/desktop-ux = 2edfb86a (main tip); desktop-ux NOT ancestor of main`; `dashboard origin/rohit/desktop-ux:Extension/src-tauri/tauri.conf.json version 0.3.4 vs origin/main 0.2.4`; `dashboard origin/main:public/downloads/GeniOS-desktop-mac.zip (20.5 MB) last commit 9f83fc7 2026-09-14`; `dashboard origin/main:src/app/dashboard/download/page.tsx:16; src/components/layout/sidebar.tsx:548`; brain origin/g010-desktop:speedrun008/GeniOS-010/07-GENIOS-DESKTOP/00-README.md ('not merged'); not an ancestor of 0cc8d83c
- **What Rohit sees:** Teammates and customers who install from the dashboard get the 0.2.0 card view with silent refusals and no Answer.
- **Where the mistake was:** Memory dashboard-navigation-22-oct.md says 'origin/main (2edfb86) contains … rohit/desktop-ux'. That is false: it is not an ancestor.
- **Fix:** Rohit approves a fast-forward of rohit/desktop-ux into main. Harsh tags desktop-v0.3.x so the workflow builds the installers, and replaces the zip or points DOWNLOAD_URL at the release. A Developer ID signature ends the Accessibility and Keychain re-prompts (memory desktop-accessibility-and-adhoc-builds). Merge g010-desktop docs into speedrun008.
- **Blocked on:** Rohit's go to merge (the auto-mode classifier refused merges to main earlier)
- **Verified:** confirmed by the skeptic (In the dashboard repo, origin/rohit/desktop-ux (ed2724d) is not an ancestor of origin/main. merge-base = 2edfb86 = main's tip, and the branch is 32 commits ahead, so merging is a fast-forward. tauri.conf.json is 0.3.4 on desktop-ux and 0.2.4 on main. public/downloads/GeniOS-desktop-mac.zip (20,505,191 bytes) was last changed in 9f83fc7 on 2026-09-14 ('Desktop 0.2.0'), and its GeniOS.app Info.plist CFBundleShortVersionString is 0.2.0. download/page.tsx:16 serves it, and sidebar.tsx:548 links to it. The only tag is desktop-v0.1.0, even though .github/workflows/desktop-release.yml exists. In the brain repo, origin/g010-desktop (01b31e0a) is not an ancestor of 0cc8d83c, and its 07-GENIOS-DESKTOP/00-README.md:8 says 'not merged'.)

<a id="surfaces-policy-safe-constant-claim"></a>
### The home claims 'No action bypassed a hard rule' and 'Policy-safe 100%' without measuring it

`surfaces-policy-safe-constant-claim` · **P1** · partial · owner **claude** · code · step **S39**

- **Expected:** Policy-safe = the share of this week's gated actions that passed every hard rule, measured from the gate log, or '—' when not measured (B7: 'Better still, measure it'). _(source: speedrun008/GeniOS-010/02-DASHBOARD-HOME/05-BRAIN-WORK.md §B7)_
- **Actual:** The brain sets policy_safe = 100 whenever any row exists in the decisions table this week. Those rows are intelligence-API answers, not gated actions. The home turns '100%' into a green check, 'No action bypassed a hard rule', and shows 'Policy-safe actions 100%' in the brain card. B7 only changed the empty case to '—'.
- **Evidence (measured):** `genios_engine/api/home_routes.py:281 (policy_safe = 100 if decisions_7d else None)`; `genios_engine/api/home_routes.py:287-288 (health row 'No action bypassed a hard rule')`; `genios_engine/api/intelligence_routes.py:114 (the only writer of decisions: the intelligence API)`; `dashboard origin/main:src/product/internal/dashboard/homepage/live.ts:279,372-373`; `dashboard origin/main:src/product/internal/dashboard/homepage/sections/context-moving.tsx:298-300`
- **What Rohit sees:** None on cards. The home asserts a safety property nobody measured.
- **Where the mistake was:** The B7 fix kept the constant 100 and changed only the empty case. The home rebuild then promoted the constant into a 'what is working' check.
- **Fix:** Brain: compute policy_safe from the gate or approval log (gated actions this week, and how many passed every hard rule), or return null. Dashboard: push the good check only when the value is measured.
- **Verified:** confirmed by the skeptic (home_routes.py:281 sets policy_safe = 100 if decisions_7d else None, and :286-287 attaches the fixed note 'No action bypassed a hard rule'. decisions_7d (:220) counts the decisions table. Its only INSERT in genios_engine is intelligence_routes.py:114 (_persist_decision_envelope, called at :433 and :1374), so those rows are intelligence-query answers, not gated actions. Dashboard live.ts:279 passes snapshot.health through, and :372-373 turns value '100%' into the green check 'No action bypassed a hard rule'. One small location fix: the 'Policy-safe actions 100%' figure is drawn in the health strip at the bottom of the context-moving section (context-moving.tsx:298-305), not in a 'brain card'.)

<a id="surfaces-question-and-team-cards-reach-only-the-cards-page"></a>
### Question cards and team/verify cards reach only GET /cards; Home 'Today', MCP, the agent API, push lanes, /v1/insights, Ask and the Context panel read decision cards only

`surfaces-question-and-team-cards-reach-only-the-cards-page` · **P1** · partial · owner **claude** · code · step **S36**

- **Expected:** Uncertainty routes a finding to a lane and never deletes it. A card is a living view of one situation on every surface that shows cards. STEP-13 added the question door precisely because 'a question card written to cards reached nobody'. _(source: speedrun008/GeniOS-008/00-ARCHITECTURE.md 'Cards — five lanes, a confidence vector'; genios_engine/deliver/store.py:40-48 (STEP-13 comment))_
- **Actual:** Only the Cards queue has three doors: decision (AUTHORITATIVE_SIGNAL_PREDICATE), P4 situation (SITUATION_CARD_SQL) and question (QUESTION_CARD_SQL) (deliver/store.py:767-788). The card detail and actions know all three too (deliver/store.py:650-691; deliver/actions.py:157-180). Only deliver/store.py, deliver/actions.py and deliver/pipeline.py reference QUESTION_CARD_SQL or its builder.

Every other card reader joins the decision predicate alone:
- GET /api/org/{org}/morning-brief, which the dashboard Home 'Today' card reads (api/workspace_routes.py:243, 283-293; dashboard origin/main src/components/dashboard/today-card.tsx:7)
- the Context page entity panel (api/workspace_routes.py:425-445)
- GET /v1/insights, where GeniOS-009 G6 plans the goal board (api/intelligence_routes.py:589-656)
- the MCP list_cards tool behind the claude.ai GeniOS connector (mcp/server.py:328-368)
- agent poll /v1/signals (deliver/agent_api.py:79-89)
- agent webhook push (deliver/push.py:56-66)
- the Slack and agent push lanes' PUSHABLE_CARDS_SQL (deliver/outbox.py:512-519, 609, 769)
- Ask's moment recall (reason/moments/recall.py:186-191)
- **Evidence (measured):** `genios_engine/deliver/store.py:767-788 (three doors in queue())`; `genios_engine/api/workspace_routes.py:243, 283-293, 425-445`; `genios_engine/api/intelligence_routes.py:589-656`; `genios_engine/mcp/server.py:328-368`; `genios_engine/deliver/agent_api.py:79-89`; `genios_engine/deliver/push.py:56-66`; `genios_engine/deliver/outbox.py:512-519`; `genios_engine/reason/moments/recall.py:186-191`; `grep: QUESTION_CARD_SQL|QUESTION_CARD_BUILDER appears only in deliver/store.py, deliver/actions.py, deliver/pipeline.py`; `dashboard origin/main src/components/dashboard/today-card.tsx:7 ('Backed by /morning-brief + /tasks')`
- **What Rohit sees:** A held file's question appears on the Cards page but not in Home 'Today', not in the claude.ai GeniOS connector, not in Ask, and never in any push. With L2 now holding overdue and unknown moves as questions, Home shows fewer priorities than the Cards page.
- **Where the mistake was:** STEP-13 (question door) and P4 (situation door) each fixed the queue reader only. The other readers kept private copies of the decision-only predicate, and no guard ties every card reader to one definition of a live card.
- **Fix:** Move the three-door 'live card' FROM/WHERE into one shared fragment in deliver/store.py, and use it in the morning brief, the Context panel, /v1/insights, MCP, agent poll and push, and recall. Decide explicitly whether the push lanes send questions. Add a guard test that every SQL reading open cards uses the shared fragment, so a new door cannot again reach one reader only. Do this before G6 puts the goal board on /v1/insights.
- **Blocked on:** Production share, read-only: select k.builder_version, k.output_lane, count(*) from cards k where k.org_id = '<ORG>' and k.state in ('queued','surfaced','snoozed') group by 1, 2 order by 3 desc;
- **Depends on:** [l4-morning-brief-unreached](#l4-morning-brief-unreached), [goals-c8-no-goal-on-card](#goals-c8-no-goal-on-card), [l2-judgment-holds-overdue-and-unknown](#l2-judgment-holds-overdue-and-unknown)
- **Verified:** added by the completeness critic, checked against the code by it

<a id="surfaces-b-items-built"></a>
### GeniOS-010 B3, B4, B5, B6, B8 (S1–S6, S8) and B9 are built in the brain and wired in dashboard main

`surfaces-b-items-built` · **P2** · done (lesson only) · owner **claude** · code · step **S42**

- **Expected:** B3 rename intervention_rate, B4 per-workspace active, B5 weekly changes, B6 cards_7d, B8 screen links and counts, B9 drop the notice. _(source: speedrun008/GeniOS-010/02-DASHBOARD-HOME/05-BRAIN-WORK.md; 05-SCREEN/01-INTEGRATION.md §5)_
- **Actual:** All present in 0cc8d83c (e0d58c8c and 93ea3cbe are ancestors). B4: active comes from l3_activation.activated_domains. B3: card_action_rate. B5: changes{}. B6: cards_7d. B9: notice gone. B8: read_by, due_phrase, graph_written_at, moment_id, card_ids, remember/keep_reason, screen_items, and weekly screens_read, screens_skipped, threads_to_memory, cards_from_screen. Dashboard main reads them (238f45e, 32787f3). S7 (goal) still waits on GeniOS-009 G4. B7 is only partly done (see surfaces-policy-safe-constant-claim).
- **Evidence (measured):** `git merge-base --is-ancestor e0d58c8c HEAD and 93ea3cbe HEAD: both true`; `genios_engine/api/expertise_routes.py:57-62`; `genios_engine/api/intelligence_routes.py:816-819`; `genios_engine/api/home_routes.py:249-266`; `genios_engine/reason/moments/followups.py:326-342,829-844,858,933,949`; `genios_engine/api/moment_routes.py:515,610`; `dashboard origin/main:src/product/internal/dashboard/screen/live.ts:75-118,205-216; homepage/live.ts:95-130`
- **Fix:** None. Production depends on migration 0250 being applied and on the deploy order (separate items).
- **Depends on:** [surfaces-0250-applied-unverified](#surfaces-0250-applied-unverified), [surfaces-b9-deploy-order-unverified](#surfaces-b9-deploy-order-unverified)
- **Verified:** confirmed by the skeptic (e0d58c8c and 93ea3cbe are both ancestors of HEAD 0cc8d83c (merge-base --is-ancestor true). B4 is at expertise_routes.py:116-124: active = id in l3_activation.activated_domains. The cited :57-62 is the corpus listing. B3 card_action_rate is at intelligence_routes.py:816-819. B6 cards_7d and B5 changes are at home_routes.py:253-273. B9 is at :303-304. B8 is at followups.py:318-319 (_COLS), :326-342, :829-844 (moment_id, card_ids, remember, keep_reason), :858 (screen_items), :933 and :949 (threads_to_memory, cards_from_screen, screens_read, screens_skipped), and at moment_routes.py:515 and :610 (read_by). On the dashboard, 238f45e and 32787f3 are ancestors of origin/main. homepage live.ts:93 reads cards_7d, and :162-221 reads changes. screen/live.ts:75-118 and :205-216 read the B8 fields. Built and merged does not prove it is live in production (see the B9 and 0250 items).)

<a id="surfaces-b2-aer-hir-rollup-missing"></a>
### AER and HIR have no weekly series (B2): AER is locked and blurred, HIR shows readiness only

`surfaces-b2-aer-hir-rollup-missing` · **P2** · missing · owner **claude** · code · step **S33**

- **Expected:** A weekly AER/HIR rollup route feeding the home's trend charts, with 'not enough data (n=…)' instead of 0%. _(source: speedrun008/GeniOS-010/02-DASHBOARD-HOME/03-AER-HIR.md §4; 05-BRAIN-WORK.md B2; memory aer-and-hir-metrics.md)_
- **Actual:** There is no route. The old /v1/metrics/intervention_rate/summary stub was deleted (B3). The home shows AER locked ('Agents are locked for this release') and HIR as '% ready to measure'.
- **Evidence (measured):** `route list: no AER/HIR rollup route`; `dashboard origin/main:src/product/internal/dashboard/homepage/sections/genios-at-work.tsx:700-745`; `genios_engine/api/routes.py:4727 (comment: summary stub gone)`
- **Fix:** After G7 (verified outcomes) and G8 (delegation), add the weekly rollup per 03-AER-HIR.md §4 with fixed completed_by kinds.
- **Depends on:** [GeniOS-009 G7](#GeniOS-009 G7), [GeniOS-009 G8](#GeniOS-009 G8), [Rohit unlocking Agents](#Rohit unlocking Agents)
- **Verified:** confirmed by the skeptic (No AER/HIR rollup route is in the brain's route list. routes.py:4726-4728 records that the intervention_rate/summary stub was deleted (B3). genios-at-work.tsx:703-722 shows AER with metric=null when live and a 'Automation is locked' panel. :732-739 shows HIR with metric=null when live and readiness steps only, 'N% ready' (:558, :609). Separately, GET /dashboard/metrics still returns a fixed "aer": 0 (routes.py:4621).)

<a id="surfaces-card-shape-vs-architecture"></a>
### No surface shows the architecture's card parts: the confidence vector, unknowns, options, authority, or why-not receipts for suppressed findings

`surfaces-card-shape-vs-architecture` · **P2** · missing · owner **claude** · code · step **S22**

- **Expected:** A card is what · why · now · evidence · unknowns · options · authority · actions · receipt. Five lanes, including suppress with a why-not receipt. A six-dimension confidence vector. _(source: speedrun008/GeniOS-008/00-ARCHITECTURE.md 'Cards — five lanes, a confidence vector')_
- **Actual:** The web groups four lanes (decision, conflict, question, waiting) and shows urgency only (06-CARDS/03 C10 Open). card_builder emits the old C/U/I/R scalars. No dashboard file reads confidence_vector, unknowns or why-not. /v1/executive/why-not exists with no surface caller. Quotes carry no sender or date (C4), and there is no 'this is right' verdict (C7).
- **Evidence (measured):** `genios_engine/deliver/card_builder.py:1369`; `genios_engine/api/executive_routes.py:76`; `grep 'why-not|confidence_vector|unknowns' in dashboard origin/main src and Extension/src: no hits`; `genios_engine/reason/expert/decide.py:357 (quotes are bare strings)`; `genios_engine/deliver/actions.py:36 (no 'right')`
- **What Rohit sees:** The founder cannot see how sure GeniOS is, what is unknown, or what was held back.
- **Fix:** After L2's ReasoningResult carries the six dimensions (L2-9), add them to card.v1 and render them as named dots. Add a 'held back, and why' view off /v1/executive/why-not. Build C4 (quote sender and date) and C7 (a 'right' action).
- **Depends on:** [GeniOS-008 L2-9 confidence dimensions](#GeniOS-008 L2-9 confidence dimensions), [06-CARDS C4](#06-CARDS C4), [06-CARDS C7](#06-CARDS C7)
- **Verified:** confirmed with a correction by the skeptic: 'Shows urgency only' holds for the Cards page (06-CARDS/03 C10). The Goals and Screen pages, however, draw a 'Confidence' block (intel/parts.tsx:262-275, fed by goals/live.ts:90-104). It comes from the API's _confidence_block (routes.py:5061-5100): evidence, identity, situation, consistency, recommendation, plus 'absent' and 'source'. That block is not the architecture's six-dimension vector, and its nulls render as 'medium'.

<a id="surfaces-cards-detail-cap-40"></a>
### Cards past the 40th never load their detail, even when opened

`surfaces-cards-detail-cap-40` · **P2** · partial · owner **claude** · code · step **S35**

- **Expected:** Every open card can be opened and acted on. The queue carries what the list draws, and details load only for the opened card (C3). _(source: speedrun008/GeniOS-010/06-CARDS/01-INTEGRATION.md §2 and §5 C3; 04-BUILD-REVIEW.md R2)_
- **Actual:** loadDetails fetches /cards/{id} for the first MAX_DETAILS=40 open cards only, and opening a card does not force its detail. For card 41 and on, the row's tool tags stay a pulsing skeleton, the panel says 'Reading the card…' forever, and the buttons fall back to defaults. The Goals page has the same 40 cap. The brain queue still lacks output_lane, business_subject, by_when and context_tags (C3 unbuilt).
- **Evidence (measured):** `dashboard origin/main:src/app/dashboard/cards/page.tsx:78,239-245,423,548,669,839`; `dashboard origin/main:src/product/internal/dashboard/goals/goals-page.tsx:443,469`; `genios_engine/deliver/store.py:772-786 (queue selects: no output_lane/business_subject/context_tags)`
- **What Rohit sees:** Only bites when more than 40 cards are open. Those cards cannot be read or properly acted on.
- **Fix:** Dashboard: when a card is opened and its detail is missing, call loadDetails with that card forced. Brain: C3 (queue adds output_lane, business_subject, relationship_role, by_when, version, context_tags, from_screen) so the list needs no per-card fetch.
- **Verified:** confirmed by the skeptic (cards/page.tsx:78 MAX_DETAILS=40. At :239-243, loadDetails slices to 40 BEFORE applying force, so even the forced reload after a press (:381) never loads card 41 or later. openCard (:417) only sets selected, and :312 loads the timeline, not the detail. For those cards the row shows a pulsing skeleton for tool tags (:669) and the panel shows 'Reading the card…' (:839). readCard's offers fall back to defaults when there are no actions (card-read.ts:439-441). goals-page.tsx:443 and :469 apply the same cap. Brain CardStore.queue (store.py:772-786, all three doors) selects no output_lane, business_subject, by_when or context_tags, and GET /cards (routes.py:5454) returns queue() as it is.)

<a id="surfaces-dead-routes-gated-pages-and-docs"></a>
### Reports and Memory pages call routes the brain lacks, and the Documentation page advertises seven non-existent routes

`surfaces-dead-routes-gated-pages-and-docs` · **P2** · broken · owner **claude** · code · step **S39**

- **Expected:** Every route a page calls or the docs advertise exists in genios_engine/api. _(source: Slice rule: brain route a page calls must exist with the same shape)_
- **Actual:** Reports (locked in trial, still in code) calls GET /api/org/{org}/live. /dashboard/memory (URL only) calls GET /api/org/{org}/contacts/{id}/why. Neither exists. Documentation (in the nav) lists POST /v1/ingest, POST /v1/context, GET /v1/contacts, GET /v1/sync, GET /v1/org, POST /v1/interaction and POST /v1/outcome. None is served (the brain has /contacts, /v1/insights and /v1/segments only).
- **Evidence (measured):** `dashboard origin/main:src/lib/api-brain.ts:155-157,200-205`; `dashboard origin/main:src/app/dashboard/reports/page.tsx:257,273; src/app/dashboard/memory/page.tsx:21`; `dashboard origin/main:src/components/documentation/docs-page.tsx:714,761-768`; `route list from an AST walk of genios_engine/api/*.py and main.py (375 routes)`
- **Fix:** Rewrite docs-page §8/§10 to the routes that exist. Delete or repoint getLiveActivity/explainContactField, or add the routes if those pages are to reopen.
- **Verified:** confirmed by the skeptic (api-brain.ts:155-157 calls /api/org/{org}/live, and :200-205 calls /api/org/{org}/contacts/{id}/why. reports/page.tsx:273 calls getLiveActivity, and memory/page.tsx:21 calls explainContactField. Neither path is in the brain's route list. My AST walk found 378 decorator routes against the item's 375, which does not change the result. Of the routes docs-page.tsx:714 and :761-768 advertises, /v1/ingest, /v1/context, /v1/contacts (GET), /v1/sync, /v1/org, /v1/interaction and /v1/outcome do not exist. The near names are PUT /v1/contacts/{id}/segment, POST /v1/insights/{id}/outcome, POST /ingest/all and POST /sync/{connection_id}. /v1/insights, /v1/segments and /v1/intelligence/query do exist.)

<a id="surfaces-feedback-on-answered-card"></a>
### Web Cards offers Feedback on answered question cards, which the brain refuses, and the error text says 'give feedback'

`surfaces-feedback-on-answered-card` · **P2** · broken · owner **claude** · code · step **S35**

- **Expected:** Only what the server offers on a card is pressable ('never a button it refuses'). _(source: dashboard origin/main:src/app/dashboard/cards/page.tsx:18 (its own rule); speedrun008/GeniOS-010/06-CARDS/01-INTEGRATION.md §4)_
- **Actual:** The Feedback MenuButton is drawn on every open card. It uses LEGACY_WRONG when the card's actions carry no 'wrong'. An answered question card offers only snooze (ANSWERED_OFFERS = snooze, requeue), so Feedback gets 422 not_offered. The page then says 'This card does not take that. Answer it, put it off, or give feedback.' Mac 0.3.4 locks Feedback in the same state, so the two surfaces disagree.
- **Evidence (measured):** `dashboard origin/main:src/app/dashboard/cards/page.tsx:1020,197-198`; `dashboard origin/main:src/lib/card-read.ts:425-441`; `genios_engine/deliver/actions.py:59,61,90-91`; `dashboard origin/rohit/desktop-ux:Extension/src/menu/MenuApp.tsx:410,419`
- **What Rohit sees:** A press that is refused, with advice to repeat it.
- **Fix:** Draw Feedback only when the card's actions include 'wrong'. Make the not_offered sentence list read.offers rather than fixed advice.
- **Verified:** confirmed with a correction by the skeptic: The behaviour holds, but the brain refusal is at deliver/actions.py:197-200 (an answered question card refuses any action not in ANSWERED_OFFERS), not at :90-91, which is snooze_until. ANSWERED_ACTIONS (:59) offers only snooze and is written onto the card at :354. ANSWERED_OFFERS = {snooze, requeue} is at :61.

<a id="surfaces-goals-domain-fold-r2"></a>
### Goals page draws empty-domain cards under Admin and collapses other domains' cards to a count

`surfaces-goals-domain-fold-r2` · **P2** · partial · owner **claude** · code · step **S39**

- **Expected:** An empty domain shows as 'unknown', not Admin, and details page past 40 (R2). _(source: speedrun008/GeniOS-010/04-BUILD-REVIEW.md §6 R2 and §7 step 7)_
- **Actual:** FOLDED_INTO_ADMIN includes ''. Cards from sales, support and other locked domains show only as a counted line. The OpenCard type now declares domain, so that part of R2 is closed.
- **Evidence (measured):** `dashboard origin/main:src/product/internal/dashboard/goals/live.ts:25,204-215`; `dashboard origin/main:src/lib/api-cards.ts:57 (domain?: string)`
- **What Rohit sees:** A fundraising card routed to the Sales domain does not appear on Goals (it does on Cards).
- **Fix:** Show '' as Unknown. Keep the locked-domain count, but link it to Cards filtered by domain.
- **Verified:** confirmed by the skeptic (goals/live.ts:25 FOLDED_INTO_ADMIN = {admin, founder_office, ''}. At :204-215, any other domain only increments lockedCards. api-cards.ts:57 now declares domain?: string on OpenCard, so that part of R2 (04-BUILD-REVIEW.md:306, :326) is closed. The 40-detail cap remains (goals-page.tsx:443, :469). How many live cards have an empty domain cannot be measured without a production read.)

<a id="surfaces-goals-page-proposal-flow"></a>
### Goals page: approval needs typing to be useful, the answers become free text, and the drafter's evidence is never shown

`surfaces-goals-page-proposal-flow` · **P2** · partial · owner **claude** · code · step **S27**

- **Expected:** A proposed goal shows where GeniOS saw it (its proof) and is approved in one click, with target, deadline and owner pre-filled as structured fields. _(source: speedrun008/GeniOS-010/03-GOALS/01-GOALS-PAGE.md §1.4, §5 ('After G1 they should land as structured fields (PATCH /v1/goals/{id})'); F2)_
- **Actual:** goals-page.tsx:347-396 renders four free-text inputs. finalGoalLine (goals/live.ts:185) joins the answers into the line's text, which decideGoalProposal then sends as the accepted words. Target, deadline and owner therefore end up inside the statement, and G1's sync (STEP-G1 §3 G1.3, words only) would carry them as text with no deadline field. Approve is enabled with zero answers (disabled only for sample/busy), so one click works but yields a goal with no target, deadline or owner. Proof: proofOf (goals/live.ts:74) reads statement/field/question/inference/because/text, but drafter evidence items carry pattern/kind/address/name/about/title/domain/last (reason/brief_drafter.py:200-205; reason/brief_patterns.py:241-262), so every proposal falls back to the generic 'GeniOS proposed it from what it read' (goals/live.ts:179).
- **Evidence (measured):** `git show origin/main:src/product/internal/dashboard/goals/goals-page.tsx (lines 347-396)`; `git show origin/main:src/product/internal/dashboard/goals/live.ts (lines 74, 170-179, 185)`; `genios_engine/reason/brief_drafter.py:200-205`; `genios_engine/reason/brief_patterns.py:241-262`
- **What Rohit sees:** The founder cannot see why GeniOS proposed a goal, and an approved goal has no deadline or target that code can use.
- **Fix:** Render pattern evidence (about, title, address/domain, last date) in proofOf. Once proposals carry structured fields (design item), pre-fill the four answers and send them as fields (PATCH /v1/goals or the approve body), never concatenated into the statement.
- **Depends on:** [goals-g1-goal-object-missing](#goals-g1-goal-object-missing)
- **Verified:** confirmed by the skeptic (goals-page.tsx:363-374 renders four free-text inputs (maxLength 60). The Approve button (:390-396) is disabled only on sample or busy, and it sends finalGoalLine (goals/live.ts:185-193), which folds target, deadline, owner and done-when into the text. That text is cut at 200 characters, the same as MAX_LINE_CHARS (contracts/company_brief.py:63), so long answers are silently truncated. proofOf (live.ts:74-84) reads statement, field, question, inference, because and text. Drafter evidence is {pattern, kind, …pattern fields} (brief_drafter.py:200-205), and every pattern item (brief_patterns.py:164-166, 241-262) lacks all six keys. So every proposal falls back to the generic text at live.ts:179.)

<a id="surfaces-home-tiles-measure-other-things"></a>
### Home week tiles are labelled as situations formed and closed, but count recomputed situations and execution outcomes

`surfaces-home-tiles-measure-other-things` · **P2** · partial · owner **claude** · code · step **S39**

- **Expected:** 'Situations formed' = situations newly formed this week; 'Situations closed' = situations resolved this week with an outcome checked. _(source: speedrun008/GeniOS-010/02-DASHBOARD-HOME/01-SECTIONS.md (week at a glance); 04-BUILD-REVIEW.md §2)_
- **Actual:** situations_7d counts active context_situations with computed_at in 7 days, which includes every recompute, not just new ones. 'Situations closed · outcome checked' is the count of execution_outcomes rows. The brain also still ships unused fixed values: coverageChange 0, intervention delta '+0%' and 12 identical bars.
- **Evidence (measured):** `genios_engine/api/home_routes.py:222-228,298,322-323`; `dashboard origin/main:src/product/internal/dashboard/homepage/live.ts:285-313`
- **Fix:** Count situations by first-seen time (created_at) and resolved situations by resolved_at. Drop the fixed fields from home-summary. In the GeniOS-008 target, read L3-admitted situations.
- **Verified:** confirmed by the skeptic (home_routes.py:222-223 counts active context_situations with computed_at in the last 7 days. The main writer's upsert sets computed_at = excluded.computed_at on every recompute (context/situations.py:1259) and leaves first_seen_at alone, so 'formed' counts recomputes. first_seen_at would be the true formation time. 'Situations closed · outcome checked' reuses the 'verified' card (homepage live.ts:304-313), which is outcomes_7d = execution_outcomes rows (home_routes.py:227-228, :317). The brain still ships coverageChange 0 (:298), intervention delta '+0%' and [max(4, intervention)]*12 bars (:322-323). git grep finds no dashboard src/product reader of coverageChange or the intervention card.)

<a id="surfaces-resources-manual-context-dead-routes"></a>
### Resources: manual entries vanish on reload, edit and delete hit routes that do not exist, and settings are local-only

`surfaces-resources-manual-context-dead-routes` · **P2** · broken · owner **claude** · code · step **S39**

- **Expected:** Manual context can be listed, edited and deleted through brain routes. Controls change brain behaviour or are not shown. _(source: GeniOS-010 ground rule 1 (00-START-HERE); dashboard origin/main:src/lib/api.ts doc comments)_
- **Actual:** The brain has only POST /api/org/{org}/manual-context. listManualContext (GET) is imported but never called, so entries live in local state, seeded from an empty mock, and disappear on reload. deleteManualContext (DELETE …/{id}) and updateManualContext (PATCH …/{id}) have no brain route, and their errors are swallowed with catch {}. 'Extraction Preferences' toggles write only localStorage. 'File Type Authority Weights' is a hard-coded list.
- **Evidence (measured):** `genios_engine/api/workspace_routes.py:335 (only POST)`; `dashboard origin/main:src/lib/api.ts:1633-1641,1852-1861`; `dashboard origin/main:src/components/resources/resources-page.tsx:103,166,285-290,1384-1389,1594,1730-1790`
- **What Rohit sees:** Manual context the founder adds still reaches the brain via POST. The page misreports it.
- **Fix:** Either add GET/PATCH/DELETE manual-context routes in the brain, or remove list/edit/delete and say 'saved to memory' after POST. Remove or wire the local-only toggles and the fixed weights table.
- **Verified:** confirmed by the skeptic (The brain route list has only POST /api/org/{org_id}/manual-context (workspace_routes.py:335): no GET, PATCH or DELETE. Dashboard api.ts:1633-1643 (list, delete) and :1852-1861 (PATCH update) exist. resources-page.tsx imports listManualContext (:31) but never calls it. Entries start from mockManualEntries = [] (:103, :166). handleDeleteEntry swallows errors with catch {} (:285-290), and the edit handler does too (:1384-1389). 'Extraction Preferences' (:1751) reads and writes localStorage 'genios_resource_prefs' (:1732, :1742). 'File Type Authority Weights' (:1797-1810) is a hard-coded list.)

<a id="surfaces-screen-items-unread-on-cards"></a>
### The brain serves which screen items fed a card, but the Cards page never shows it

`surfaces-screen-items-unread-on-cards` · **P2** · partial · owner **claude** · code · step **S35**

- **Expected:** A card fed by the screen says so in Cards too (screen_items[]). _(source: speedrun008/GeniOS-010/04-BUILD-REVIEW.md §4 'Cards, next'; 05-SCREEN/01-INTEGRATION.md S6)_
- **Actual:** GET /cards/{id} returns screen_items[] (B8). readCard, the Cards page and the Mac reader never read the field.
- **Evidence (measured):** `genios_engine/api/routes.py:5582-5590`; `grep 'screen_items' in dashboard origin/main src/lib and src/app/dashboard/cards: no hits`
- **What Rohit sees:** A card cannot say it came from what you saw on screen.
- **Fix:** readCard maps screen_items to 'Fed by your screen · <app>' under 'Where the data came from'.
- **Verified:** confirmed by the skeptic (GET /cards/{card_id} sets card['screen_items'] from followups.screen_items (routes.py:5579-5588). git grep 'screen_items' finds no hits in dashboard origin/main src/ or Extension/src, and none in origin/rohit/desktop-ux Extension/src.)

<a id="layer-cross-layer"></a>
## Cross-layer seams

| Item | Sev | Status | Owner | Step |
|---|---|---|---|---|
| [A lapsed trial, a full ingestion meter or the daily model cap silently stop Rohit's org; only a manual 'Sync n](#cross-billing-gates-silently-stop-the-org) | P0 | unknown until production is read | claude+harsh | S02 |
| [A valid expert/L2 judgment makes no card unless L3 already filed a situation on the file in an activated domai](#l2-l3-binding-no-situation-no-card) | P0 | broken | claude | S18 |
| [The exact order in _run_l2_chain: L3 forms situations, then L2 reasons, then admission runs in shadow beside c](#cross-chain-order) | P1 | partial | claude | S24 |
| [L2 subjects come from L1 bundles matched to L3 files by event: an unfiled bundle becomes a contextless 'seed' ](#cross-l2-subject-to-file-seam) | P1 | broken | claude | S21 |
| [Missing design: L2 proposes a goal from a workstream, L3 admits it as a proposal, the founder approves in one ](#cross-layer-l2-proposes-l3-admits-goal-design) | P1 | missing | claude | S29 |
| [The L1→L2 bundle carries only published signals, so below-floor, archived, calendar-only and open-lane items n](#l1-bundle-carries-only-published-signals) | P1 | partial | claude | S13 |
| [L2-G2 admission is built but shadow: it never creates or changes a situation; a HOLD raises no EvidenceNeed](#l2-admission-g2-shadow) | P1 | built, not live | claude | S24 |
| [The eight live bugs of 4 Oct: six are fixed in code, one is closed by an earlier note only, one is half verifi](#cross-eight-bugs-of-4-oct) | P2 | done (lesson only) | harsh | S13 |
| ['Sync now' runs a second copy of the chain: no funnel numbers, no meeting/team/verify post-passes, and none of](#cross-sync-now-runs-a-second-chain) | P2 | partial | claude | S10 |

<a id="cross-billing-gates-silently-stop-the-org"></a>
### A lapsed trial, a full ingestion meter or the daily model cap silently stop Rohit's org; only a manual 'Sync now' still reasons

`cross-billing-gates-silently-stop-the-org` · **P0** · unknown until production is read · owner **claude+harsh** · mixed · step **S02**

- **Expected:** The founder's own tenant is swept every tick (6 h heavy, 15 min light). Any refusal to sweep is visible to him, never only a log counter: capture is honest and coverage is stated. _(source: speedrun008/GeniOS-008/00-ARCHITECTURE.md 'Inside L1 — capture honestly'; genios_engine/platform/config.py:157-175 (scheduler cadence); F2 (Rohit: fewer cards, sometimes no reasoning))_
- **Actual:** Every signup is a 15-day trial with plan_expires_at set (api/auth_routes.py:79-87). run_billing_tick runs on every heavy tick: it moves a past-due org to 'expired' and gives it a 7-day grace window (platform/billing.py:172, 378-401). Since 7075014c (4 Oct; already on the production branch before the 18 Oct merge), the scheduled sweep skips an expired org's L1 pull (api/routes.py:1152-1155) AND drops it from the L3/L2/L4/L5 pass (api/routes.py:1228-1232). The warm lane also refuses its events (platform/warm_lane.py:171-176), and Ask returns 402 'Your trial has ended' (platform/billing.py:366-371, api/intelligence_routes.py:265-268). That commit measured on production: 'Rohit Swerashi grace closed 21 Sep'. No migration, script or doc after it extends that org's plan.

The dashboard's Sync now goes through a different door: POST /integrations/sync-all, then sync_jobs, then _onboarding_sync_bg. It checks only the daily LLM cap (api/routes.py:3952), then runs the full chain (api/routes.py:4030, 3784-3786). POST /sync/{id} (api/routes.py:923-951) and POST /connections/{id}/backfill (api/routes.py:1981-2040) check neither the plan nor the quota. So on a lapsed org, cards appear only after a manual Sync. Expert cards then drop out of the queue 168 h after their last decision (reason/expert/decide.py:154; reason/authority.py:251-263).

Two more gates also skip a connection. The ingestion meter skips it once source_events captured this period reach the plan's sync_messages (trial 1,000 per 15 days, individual 3,000 per 30 days; platform/billing.py:91-92; platform/quota.py:61-104; api/routes.py:1162-1167). The daily cap skips it at 20,000 calls or $25 of llm_costs (api/routes.py:3880-3914; platform/config.py:86). All three skips are only counters in the scheduler's INFO log line (api/routes.py:1234-1262). No l1_sync_runs row and no founder notice is written.

The 365-day resync's backfill route applies no quota. A large resync can therefore fill the meter, and the automatic sweep then stops polling new mail for the rest of the period. Separately, on a trial or individual tier (Plan.domains=1) the admin route refuses a second domain (api/admin_routes.py:1253-1272). Founder Office can then only be switched on through scripts/activate_tenant.py, which skips that check.
- **Evidence (mixed):** commit 7075014c message: 'Rohit Swerashi grace closed 21 Sep 12,831 calls … The sweep gates the L1 pull AND the L2/L3/L5 pass'; `git merge-base: 7075014c is an ancestor of c501eec9^1 (production before 18 Oct)`; `genios_engine/api/auth_routes.py:79-87 (trial, plan_expires_at = now + TRIAL_DAYS)`; `genios_engine/platform/billing.py:91-92, 172, 338-350, 366-371, 378-401`; `genios_engine/api/routes.py:983-1018 (_plan_expired), 1152-1167, 1228-1232, 1234-1262`; `genios_engine/platform/warm_lane.py:135-158, 171-176`; `genios_engine/platform/quota.py:61-104`; `genios_engine/api/routes.py:3880-3914 (_LLM_DAILY_CAP=20000, daily_llm_usd_cap)`; `genios_engine/platform/config.py:86 (daily_llm_usd_cap = 25.0)`; `genios_engine/api/routes.py:3952, 4029-4030, 4119-4137 (Sync now: only the daily cap is checked)`; `genios_engine/api/routes.py:923-951, 1981-2040 (per-connection sync and backfill: no plan or quota gate)`; `genios_engine/api/admin_routes.py:1253-1272 (DOMAIN_LIMIT_REACHED); genios_engine/platform/billing.py:208-209`; no doc under speedrun008/GeniOS-008, -009 or -010, or YC-II 08-FOR-HARSH, mentions the plan or quota gates on the sweep (grep)
- **What Rohit sees:** If the org is lapsed, no automatic pass runs. Cards arrive only after a manual Sync, and existing expert cards leave the queue within about 7 days, which reads exactly as 'fewer cards' and 'sometimes'. Ask also answers 'Your trial has ended'. A full ingestion meter or the daily cap stops new mail reaching any card for the rest of the period or day, with nothing shown to Rohit.
- **Where the mistake was:** 7075014c (4 Oct) measured that Rohit's own org was lapsed and then gated the sweep on that same lapse. Neither the commit nor any later doc or Harsh note records exempting or extending the founder's tenant. The gate was added to the sweep and the warm lane but not to the Sync-job door, so the same org behaves differently depending on which door ran.
- **Fix:** Harsh: run the SQL below. If Rohit's org (or any design-partner org) is trial, expired or in grace, set it to a non-expiring internal plan (subscription_tier enterprise, plan_status active, plan_expires_at null, grace_until null), and the same for Sole Mate's tenant if it should run.

Claude, in code:
(1) Write every sweep skip (plan_expired, sync_quota, over_budget, paused) as an l1_sync_runs row with a reason, and surface it on the dashboard as one founder-readable line.
(2) Make the Sync job, POST /sync/{id} and the backfill door ask the same plan and quota gates as the sweep, or exempt them explicitly in one place.
(3) Let the resync reserve or bypass the quota by an explicit, logged decision, so it cannot silently starve the next period's polling.
- **Blocked on:** Production read (Rohit's permission). Read-only SQL:
-- A. plan state (expired = sweep, warm lane and Ask all stop)
select id, name, company, email, subscription_tier, plan_status, plan_started_at, plan_expires_at, grace_until, credit_period_start, created_at from orgs where id = '<ORG>' or name ilike '%swerashi%';
select org_id, timestamp, metadata_jsonb from audit_log where action = 'plan_expired' and org_id in (select id from orgs where id = '<ORG>' or name ilike '%swerashi%') order by timestamp;
-- B. paused?
select key, enabled from feature_flags where key in ('kill_switch:<ORG>', 'kill_switch_all');
-- C. ingestion meter this period
select count(*) from source_events where org_id = '<ORG>' and captured_at >= (select coalesce(credit_period_start, plan_started_at, created_at) from orgs where id = '<ORG>');
-- D. automatic sweeps vs manual Sync jobs vs cards, per day
select date_trunc('day', finished_at) d, count(*) l1_runs, sum(emitted) emitted, count(*) filter (where error is not null) errors from l1_sync_runs where org_id = '<ORG>' and finished_at >= '2026-10-01' group by 1 order by 1;
select date_trunc('day', created_at) d, count(*) sync_jobs from sync_jobs where org_id = '<ORG>' and created_at >= '2026-10-01' group by 1 order by 1;
select date_trunc('day', created_at) d, count(*) cards from cards where org_id = '<ORG>' and created_at >= '2026-10-01' group by 1 order by 1;
-- E. model calls per day (cap: 20,000 calls or $25)
select date_trunc('day', created_at) d, count(*) calls, count(*) filter (where not success) failed from llm_costs where org_id = '<ORG>' and created_at >= '2026-10-15' group by 1 order by 1;
- **Depends on:** [process-no-production-number-after-deploy](#process-no-production-number-after-deploy), [l1-resync-and-history-window](#l1-resync-and-history-window), [l1-refusal-and-coverage-invisible](#l1-refusal-and-coverage-invisible)
- **Verified:** added by the completeness critic, checked against the code by it

<a id="l2-l3-binding-no-situation-no-card"></a>
### A valid expert/L2 judgment makes no card unless L3 already filed a situation on the file in an activated domain; 'general' is dark

`l2-l3-binding-no-situation-no-card` · **P0** · broken · owner **claude** · code · step **S18**

- **Expected:** L2 is primary: the situation is formed by reasoning, and L3 only remembers what L2 concluded. A judged file's next move reaches the founder. _(source: speedrun008/GeniOS-008/00-ARCHITECTURE.md 'The flow' ("L2 is the primary layer … L3 only remembers"))_
- **Actual:** _decide_covered_files binds each covered file to a 'home' situation anchored on it, or to one it stood down (_FILES_HOME, domain_shadow.py:546-561). There are three silent ways to get no card. (i) No such situation: `covered_without_situation`, skipped (domain_shadow.py:741-745). (ii) The situation's L2 domain maps to no corpus. `general` → None (domain_shadow.py:952-965; DARK_DOMAINS context/domain_silence.py:45-60), so live_lane is False (domain_shadow.py:993-995) and the decision is made in SHADOW only, `expert_shadow` (domain_shadow.py:796-798). `general` is the fallback whenever no domain hint fired (context/domain_spec.py:142; :660-670 says 'most of it: 23 of one tenant's 30 deal-anchored correlations'). (iii) No tenant pack for the domain: `expert_no_tenant_pack` (domain_shadow.py:754-756). The only record of any of these is one `domain-compiler …` log line (domain_shadow.py:2054).
- **Evidence (mixed):** `genios_engine/reason/domain_shadow.py:546-561`; `genios_engine/reason/domain_shadow.py:741-756`; `genios_engine/reason/domain_shadow.py:796-798`; `genios_engine/reason/domain_shadow.py:952-1000`; `genios_engine/context/domain_silence.py:45-60`; `genios_engine/context/domain_spec.py:142, 660-670`; `genios_engine/reason/domain_shadow.py:2054`
- **What Rohit sees:** Fewer cards. The expert's or L2's best reading of a file can be stored as valid and never shown: no card and no signal, nothing Rohit can see. This is one concrete form of 'L2 and L3 failing each other'.
- **Where the mistake was:** STEP-12 M33 bolted the file review onto the compiled situation lane (bind to a situation, gate by its domain) instead of giving the file its own route. That L3-first dependency is what Atlas v2 removes.
- **Fix:** Bind a covered file's decision to the file itself: its own node as subject, its pack from the file's work kind, or a founder_office/admin default for founder work. Stop requiring an L3 situation plus a mapped domain. Until then, count covered_without_situation / expert_shadow / no_tenant_pack on the funnel and log a warning. Run the 'general' census that DARK_DOMAINS names as its end condition.
- **Blocked on:** How many judged files are lost this way in production. Rohit to run: select s.domain, count(distinct r.file_id) from expert_reviews r join context_situations s on s.org_id=r.org_id and s.anchor_node_id=r.file_id where r.org_id='<ORG>' and r.status='valid' and s.status in ('active','partial') group by 1; select count(distinct r.file_id) from expert_reviews r where r.org_id='<ORG>' and r.status='valid' and not exists (select 1 from context_situations s where s.org_id=r.org_id and s.anchor_node_id=r.file_id);
- **Verified:** confirmed with a correction by the skeptic: Substance holds. The three silent no-card exits are at domain_shadow.py:741-745 (covered_without_situation), :754-756 (expert_no_tenant_pack) and :796-798 (expert_shadow when l3_domain_for('general') is None, :952-965 and :993-995). One detail is overstated: 'the only record is one log line' is true for (i) and (iii) only. For (ii), the shadow decision is also written as a change-gate row: gate.record(key, fingerprint, 'shadow', run_id) at :797, flushed to reasoning_fingerprints with lane='compiled' and outcome='shadow' (domain_shadow.py:1177-1191; fingerprint_store.py:66-82). That row does not say why the decision was shadow; the reason is only in the log line (:2054).

<a id="cross-chain-order"></a>
### The exact order in _run_l2_chain: L3 forms situations, then L2 reasons, then admission runs in shadow beside cards built from the pre-reasoning rows

`cross-chain-order` · **P1** · partial · owner **claude** · code · step **S24**

- **Expected:** L1 bundle → L3 snapshot → L2 forms and proposes → L3 admits → L4 → L5 → L6. _(source: GeniOS-008/00-ARCHITECTURE.md:13-33)_
- **Actual:** _run_l2 (warm_lane lease) → _run_l2_chain. The chain runs: provision_intelligence → _ensure_tenant_live → _reread_unread. Then context.runner.process_pending: drain each event (process_event → correlate_event) → derived, waiting, periodic*, support*, meeting touch*, outreach readings*, document register* → contract spend, cross history, prunes → attention → refresh_situations* → age_uncorrelated* → detect_resolutions (model; apply_lifecycle*) → sampler, trend, anomaly, cohort, baseline, comparison, dependency, timeline, gap-reason → refresh_situation_importance* → patterns (shadow) → residue → evidence needs → campaign candidates → angles → outreach second pass* → importance again* → version bump → convergence. Then reason.runner.run_all (imported as run_l3, staged 'l4.run_all'): expert_pass (R-7) → l2_pass (R-9 + l2_admission shadow) → shadow_compile (compiled lane, situation_publisher) → per-pack run() → narrate_published. Then deliver.build_cards_for_org → post passes → _reclaim_after_sweep. A history backfill adds _replay_l2_history (backfill_layer2) outside the lease, and a second chain run. (* = writes context_situations.)
- **Evidence (measured):** `genios_engine/api/routes.py:664-680, :738-863, :2025-2034`; `genios_engine/context/runner.py:703-1830`; `genios_engine/reason/runner.py:1820-2012`
- **What Rohit sees:** Cards are built from rows formed before the judgment, and the judgment cannot veto or create them.
- **Fix:** Insert admission as a stage between L2 and L4, and make the card source read admitted situations, per type (see l3-situations-born-before-reasoning).
- **Depends on:** [l3-situations-born-before-reasoning](#l3-situations-born-before-reasoning)
- **Verified:** confirmed by the skeptic (Order verified against routes.py:664-680 (lease), :738-863 (chain) and :2025-2034 (replay outside the lease, then a second _run_l2), runner.py:703-1830 (derived :828-924, attention :1019-1025, refresh_situations :1042, age :1058, detect_resolutions :1088, analytic block :1136+, importance :1466, second outreach pass :1681, rank again :1707) and reason/runner.py:1820-2012 (expert_pass, then l2_pass, then shadow_compile only if use_domain_compiler, l3 domains or the l1 seam is on, then per-pack run(), then narrate_published).)

<a id="cross-l2-subject-to-file-seam"></a>
### L2 subjects come from L1 bundles matched to L3 files by event: an unfiled bundle becomes a contextless 'seed' whose HOLD dead-ends, the watermark passes it, and a bundle spanning two files is judged under the first only

`cross-l2-subject-to-file-seam` · **P1** · broken · owner **claude** · code · step **S21**

- **Expected:** Correlation happens before reasoning. L2 reads a bounded snapshot of what the company knows, and a HOLD raises an EvidenceNeed so the gap is fetched. _(source: GeniOS-008/00-ARCHITECTURE.md:13-33 (flow), :106; 02-MIGRATION-PLAN.md L3-1)_
- **Actual:** subjects_for takes files[0] of a bundle's files, sorted by node id, and ignores the rest. With no file the bundle becomes 'seed:<thread>'. decide() on a seed proposing create returns HOLD with situation '-' ('no join has filed it'). No code mints the row later, and the HOLD raises no EvidenceNeed. The seed's snapshot seeds are the nodes its events wrote facts on, at most 5; if there are none the snapshot is EMPTY. The pass then advances its watermark past judged seeds (only unreached subjects hold it back). An event that is filed a sweep later is not re-judged under its file from that bundle.
- **Evidence (measured):** `genios_engine/reason/l2/inputs.py:177-184 (files[0]; seed when none)`; `genios_engine/context/l2_admission.py:94-98 (HOLD '-')`; `genios_engine/reason/l2/snapshot.py:25-30, :62-69, :72-75 (seeds from facts; EMPTY)`; `genios_engine/reason/l2/sweep.py:210 read_subjects; :408-416 watermark`; `genios_engine/context/context_health.py:46-48 (hold_needs.needs_from_holds UNREACHED)`
- **What Rohit sees:** 'Sometimes no correlation': the judgment sees a thread with no file, history or people. No card results, or a context-free one.
- **Fix:** Re-key a seed subject to its file once its events are filed (a re-entry when an event joins a file). Judge a multi-file bundle under each file. Give HOLD '-' either an applier or an EvidenceNeed. Count seed subjects and empty snapshots in the pass receipt.
- **Blocked on:** Production read: select (subject_ref like 'seed:%') as seed, status, lane, count(*) from reasoning_results where org_id='<rohit_org>' and reasoned_at > now() - interval '7 days' group by 1,2,3;
- **Depends on:** [l3-events-outside-any-file](#l3-events-outside-any-file), [l3-thread-inherits-reading-correlations](#l3-thread-inherits-reading-correlations), [l3-hold-evidence-chain-unwired](#l3-hold-evidence-chain-unwired)
- **Verified:** confirmed by the skeptic (Verified. subjects_for takes files[0] of a sorted set; with no file the subject is seed:<thread or subject> (reason/l2/inputs.py:177-184). file_of_event is a dict, so an event in two files keeps only one (inputs.py:216). A seed has no parts, so decide() returns HOLD '-' when it proposes create (l2_admission.py:94-98). Snapshot seeds are at most 5 fact-subject nodes, and there is EMPTY when none (snapshot.py:24-30, :62-76). The watermark is held back only by unreached, unreadable, waiting, too-big or carried subjects (sweep.py:353-356, :398-416). The HOLD itself raises no need. Needs the model's result asks for ARE still filed (sweep.py:356-358, evidence.needs_from), and settled needs re-enter through evidence.reentries (sweep.py:212-217).)

<a id="cross-layer-l2-proposes-l3-admits-goal-design"></a>
### Missing design: L2 proposes a goal from a workstream, L3 admits it as a proposal, the founder approves in one click, and it reaches the card and the home page

`cross-layer-l2-proposes-l3-admits-goal-design` · **P1** · missing · owner **claude** · code · step **S29**

- **Expected:** In GeniOS-008 terms: L2 (R-9 judgment) proposes, with evidence; L3 admits, holds or rejects in code; an inferred goal never becomes active without a human; L5 shows the proposal where the founder already looks, and one click approves it. _(source: speedrun008/GeniOS-008/00-ARCHITECTURE.md 'The model rules' and 'Inside L3'; GeniOS-009/05-THE-SOURCE.md §5 invariants 2 and 7; F2)_
- **Actual:** Nothing exists. There is a precedent to copy: the R-7 expert's kind proposal (ExpertReview.proposed_kind → reason/expert/kind_proposal.propose_kind → company_brief_store.propose(proposed_by='expert_review', evidence=[review, file, cites])) at reason/expert/sweep.py:310-316. It shows that a per-file reader can already write a founder-decided proposal through the brief door.
- **Evidence (mixed):** `genios_engine/reason/expert/kind_proposal.py:1-25,104-155`; `genios_engine/reason/expert/sweep.py:310-316`; `genios_engine/context/l2_admission.py:1-25`; `genios_engine/reason/l2/sweep.py:421-429`; `genios_engine/api/company_brief_routes.py:127-150 (accept with no text already works: decide {decision:'accept'})`
- **What Rohit sees:** With this in place, the Antler card says it moves a goal, the Goals page shows the goal, and home §1 counts it, after one click from the founder.
- **Fix:** CONTRACT (contracts/reasoning_result.py): L2Judgment.proposed_goal: GoalProposal | None. Fields: statement (≤200 chars, founder's words); why (≤300, claim-checked); evidence (printed ids, at least one, and at least one must show the company's own act: an outbound, an application or a meeting held); subject_ref and work_kind (filled by code from the request and the file, never by the model); parent_goal_ref (a goal: id block G printed, giving a child goal under the umbrella); metric (a METRICS key or null); target and deadline (only with a printed tool line or ev id in target_basis/deadline_basis); owner (a person printed in the file; code resolves the seat). Refusals: GOAL_PROPOSAL_NO_EVIDENCE, UNPRINTED_REF, TARGET_NOT_PRINTED, DEADLINE_NOT_PRINTED, PARENT_NOT_PRINTED. A failing proposal is dropped and the run kept. Prompt line: 'If this file is work the company is pursuing (an application, a raise, a certification, a hire) and no goal in block G names it at that level, propose one, citing the lines; never for a monitor or suppress subject.' Block G lists pending proposals separately, for dedupe. Cost: same R-9 call, about 60–120 more output tokens, 0 calls when nothing moved. L3 (new context/goal_admission.py, pure decide plus a write inside the L2 sweep's admission savepoint, reason/l2/sweep.py:421-429): REJECT when the subject's admission is REJECT, or the lane is suppress or monitor. HOLD (reason recorded) when the situation's admission is HOLD, the proposal duplicates a live goal or a pending proposal (same subject_ref or normalized statement), the founder rejected a match within REJECTED_QUIET_DAYS=90, the org's weekly cap (e.g. 3 new proposals) is reached, or no evidence shows the company's own act. ADMIT writes a PROPOSAL only: company_goals with status='proposed', source='inferred', evidence_refs, subject_ref, result_fingerprint and the proposed fields (or a brief goals line with a proposal jsonb, per the decision). Never active; the DB check company_goals_live_is_approved_ck enforces it. ONE CLICK: POST /v1/goals/{id}/approve {revision}, with no text, sets approved_by and approved_at, status active, and copies the proposed metric, deadline, owner and parent; 'Edit' is optional; 'Not a goal' rejects (quiet for 90 days). The Goals page pre-fills the four answers from the proposal and shows its evidence quotes. A 'Make this a goal?' chip appears on the Antler card's Goal row (cards/page.tsx:925), and home §1 shows 'N goals waiting for you' with the same button. AFTER APPROVAL: the next sweep's l3.goals_sync makes it active; G2's goal_set moves the Antler file's fingerprint, so it is re-judged once; G3 writes advances goal:<id>; G4 links it on ADMIT; G6 renders 'Moves: Get admitted to Antler Singapore — advances · <printed date>' on the card; GET /v1/goals serves it to the Goals page, and to home §1 when the deadline falls this month (D-010-G2). TESTS: golden F72 (an Antler application thread, the partner's reply, no matching goal → proposal → admitted as proposed → approve → link and goal line); mutation proofs: an active status without approved_by is refused; skipping dedupe re-proposes on the second sweep; dropping the own-act evidence rule lets a newsletter propose a goal. Wire it on the L2 path explicitly (see the kind-proposal item); optionally mirror it on R-7 ExpertReview the way proposed_kind is, for tenants still on the expert path.
- **Blocked on:** Rohit: the decision item (granularity, door, weekly cap)
- **Depends on:** [goals-g1-goal-object-missing](#goals-g1-goal-object-missing), [goals-g2-goals-not-in-l2-dossier](#goals-g2-goals-not-in-l2-dossier), [goals-g3-no-goal-impacts](#goals-g3-no-goal-impacts), [goals-g4-no-goal-situation-links](#goals-g4-no-goal-situation-links), [goals-g6-no-goal-on-card](#goals-g6-no-goal-on-card), [goals-plan-gap-no-l2-goal-proposer](#goals-plan-gap-no-l2-goal-proposer)
- **Verified:** confirmed by the skeptic (No L2 or L3 goal proposal exists. The only writers of brief proposals are reason/brief_drafter.py:248 and reason/expert/kind_proposal.py:132 (called from reason/expert/sweep.py:310-316). context/founder_corrections.py:177 writes only accepted 'preferences' lines. kind_proposal.py ends at :151, not 155. The precedent holds: proposed_by='expert_review' with evidence [{review, file, cites}]. A one-click accept already works: CompanyBriefDecision.text is optional (api/company_brief_routes.py:57-62), and store.accept keeps the proposal's words when words is None (company_brief_store.py:185).)

<a id="l1-bundle-carries-only-published-signals"></a>
### The L1→L2 bundle carries only published signals, so below-floor, archived, calendar-only and open-lane items never trigger the new L2 pass

`l1-bundle-carries-only-published-signals` · **P1** · partial · owner **claude** · mixed · step **S13**

- **Expected:** The bundle is the L1→L2 contract (signals, entities, candidate relationships, coverage receipt, unresolved), and L2 forms the situation from it. _(source: GeniOS-008/00-ARCHITECTURE.md 'The flow' and the 'L1 → L2' row; 02-PLAN E1)_
- **Actual:** publish_sweep builds bundles from `emitted` published signals only (publisher.py:1233-1253). The L2 pass's R1 reads bundles since its watermark, plus met needs, plus files the expert pass hands over (reason/l2/sweep.py:1-20, 212-216; runner.py:1913), and the expert pass is OFF by default (F4). memory_lanes sends below_floor, metadata and calendar events into L3 (memory_lanes.py:42-56), but none of them ever produces a bundle. Bundles also join only within one sweep's signals (bundle.py module docstring).
- **Evidence (measured):** `genios_engine/capture/esqe/publisher.py:1233-1253`; `genios_engine/reason/l2/sweep.py:1-20,212-216`; `genios_engine/reason/runner.py:1913`; `genios_engine/context/memory_lanes.py:42-56`; `genios_engine/capture/esqe/bundle.py:1-12`
- **What Rohit sees:** With l2_reasoning or l2_cards on, a mail that matters but has no qualified signal (an intro, a meeting, a portal update) is never judged: 'sometimes no reasoning'.
- **Fix:** Decide together with the vocabulary item: either (a) a bundle also carries the sweep's below-floor extractions and open-lane observations as explicitly unqualified members, or (b) the L2 pass also seeds subjects from L3 files that received new events this sweep. Build whichever is chosen, with a golden case for each road.
- **Depends on:** [l1-signal-vocabulary-16-types](#l1-signal-vocabulary-16-types)
- **Verified:** confirmed by the skeptic (Bundles are built from `emitted` (published) signals only (publisher.py:1227-1251). The L2 pass reads bundles since its watermark, plus files_due from the expert pass and evidence reentries (sweep.py:206-226; runner.py:1913). memory_lanes routes below_floor, metadata and calendar into L3 (memory_lanes.py:42-56), and none of those lanes writes a bundle. NEW, same seam: entity proximity joins never fire in production. bundle.py reads extraction.entities (bundle.py:74, 103), but ExtractionResult's field is entity_mentions (contracts/extraction.py:639), and there is no `entities` attribute. I measured it with the venv Python: entity_keys() on a real ExtractionResult returns frozenset(). The tests pass only because their fakes define `.entities` (tests/capture/esqe/test_bundle.py:37-39; test_a_name_is_not_an_identity.py:35). Only thread and subject identity joins work.)

<a id="l2-admission-g2-shadow"></a>
### L2-G2 admission is built but shadow: it never creates or changes a situation; a HOLD raises no EvidenceNeed

`l2-admission-g2-shadow` · **P1** · built, not live · owner **claude** · code · step **S24**

- **Expected:** L3 admits L2's proposed mutations (ADMIT / HOLD / REJECT) as the owner of a situation's existence. A HOLD raises an EvidenceNeed. _(source: speedrun008/GeniOS-008/00-ARCHITECTURE.md 'Inside L3'; layer-2-reasoning/02-PLAN.md §7 L2-G2; GeniOS-009 STEP-G0 G0.3)_
- **Actual:** Built by Harsh on 19 Oct (fb429b78, migration 0249 l2_admissions), but it states 'SHADOW: nothing here touches context_situations' (context/l2_admission.py:22). Situations are still formed by L3 joins before any reasoning (api/routes.py:799 process_pending runs before run_all at :823). merge/link are held with no applier (l2_admission.py:109-110). Several live situations the judgment did not name → HOLD (:122-124). No EvidenceNeed is raised for any HOLD (none in the module). Under l2_cards a HOLD keeps the file from its L2 card (reason/l2/sweep.py:378-384). The 00-START-HERE status ('L3 builds the gate') is stale.
- **Evidence (measured):** `genios_engine/context/l2_admission.py:1-25, 78-125`; `migrations/0249_l2_admissions.sql:19-29`; `genios_engine/api/routes.py:799, 823`; `genios_engine/reason/l2/sweep.py:372-384`; `git fb429b78 (Harsh, 2026-10-19)`
- **What Rohit sees:** No correlation: L2 cannot make or merge a situation, and L3's pre-formed situations decide what L2 may card.
- **Fix:** GeniOS-009 G0.3: admission decides existence for one type first (awaiting reply/outreach). A HOLD files an EvidenceNeed naming what would settle it. Add a merge/link applier, or ask the model to name the sit: id it means.
- **Blocked on:** select decision, op, count(*) from l2_admissions where org_id='<ORG>' group by 1,2;
- **Depends on:** [l2-i2-first-switch-not-made](#l2-i2-first-switch-not-made)
- **Verified:** confirmed by the skeptic (fb429b78 (Harsh, 19 Oct) is in HEAD. The module docstring says 'SHADOW: nothing here touches context_situations' (l2_admission.py:22), and merge/link are held (:109-110). Several live seeds with none named → HOLD (:120-122). The module has no EvidenceNeed. admitted() has no production caller: context_health.py:37 lists it as UNREACHED, 'nothing makes a card from it yet'. Since f3cfd3c6 (20 Oct, in HEAD), admitted judgments are also appended to situation_interpretations (l2_admission.py:166-201), but nothing reads that table. process_pending runs before run_all (routes.py:799, :823). Under l2_cards a HOLD withholds the file review (l2/sweep.py:378-384). 00-START-HERE.md:59 still says 'L3 builds the gate'. The de795bb8 message says 0249 had 'never applied outside local scratch DBs'. Whether it is applied in production needs Rohit's permission for a read: select to_regclass('public.l2_admissions');)

<a id="cross-eight-bugs-of-4-oct"></a>
### The eight live bugs of 4 Oct: six are fixed in code, one is closed by an earlier note only, one is half verified

`cross-eight-bugs-of-4-oct` · **P2** · done (lesson only) · owner **harsh** · prod_action · step **S13**

- **Expected:** All eight fixed on the production head and applied in production. _(source: memory full-audit-eight-verified-live-bugs.md)_
- **Actual:** Fixed in code:
1. Calibration card_level: authority.py:332-336 projects it (184269a0), and calibration runs in shadow.
2. Edge vocabulary: involves, edited, assigned and used are in context/graph_store.EDGE_TYPES (lines 191-199).
3. Eight Wrong reasons hitting the CHECK: migration 0210 widens both verdict constraints to eleven.
4. The human_review route returning 409: publisher._rest_for_review moves the row.
5. A DEFER closing open legacy cards: runner.py:1538-1556 keeps the card ('A DEFER IS NOT A SHADOW RUN').
7. Parked recoveries going nowhere: drain.py:240-247 sets route='needs_extraction' and lane P3.

Closed by an earlier note only: 6. Migration 0189 unapplied; memory five-migrations-unapplied says it was applied on 2 Oct.

Half verified: 8. Per-signal coverage: SyncSummary now has source and started_at (sync_runner.py:706). The 'five conversation columns' half of _row_for was not verified in this slice.
- **Evidence (mixed):** `genios_engine/reason/authority.py:329-336`; `genios_engine/context/graph_store.py:178-205`; `migrations/0210_every_wrong_reason_is_kept.sql:43-57`; `genios_engine/feedback/publisher.py:281-300`; `genios_engine/reason/runner.py:1538-1556`; `genios_engine/capture/parked/drain.py:216-247`; `genios_engine/capture/acquire/sync_runner.py:706,1029`
- **What Rohit sees:** Fixed in code. Unapplied, the eight newer Wrong reasons would still return 500.
- **Fix:** Harsh confirms 0210 is applied in production; see blocked_on. Bug 8's conversation-column half goes to the L1 slice.
- **Blocked on:** Read-only: select conname, pg_get_constraintdef(oid) from pg_constraint where conrelid in ('card_feedback_verdicts'::regclass,'card_feedback_revisions'::regclass) and contype='c'; and select max(completed_at), count(*) from calibration_runs where status='completed';
- **Verified:** confirmed with a correction by the skeptic: Bug 8 is half fixed, not half verified. The coverage half is fixed: SyncSummary(poll, started_at, source) at sync_runner.py:706, read by _coverage_of at publisher.py:1064-1080. The conversation half is still live. capture/esqe/publisher._row_for (publisher.py:580-640) never passes thread_key, direction, turn_index, thread_depth or ball_in_court, although the published signal carries them (_conversation, publisher.py:385-396, 475; contracts/signal.py:591-607). It is the only writer of QualifiedSignalRow (the other constructor, signal_store.py:260, is the read path). So qualified_signals stores NULL for all five conversation columns (signal_store.py:161-165, 253-254, 75). Bug 4 also has a remainder: rows stuck at 'governed' from before the fix move only via the one-off scripts/rest_stuck_reviews.py --apply, and whether that ran in production is unknown.

<a id="cross-sync-now-runs-a-second-chain"></a>
### 'Sync now' runs a second copy of the chain: no funnel numbers, no meeting/team/verify post-passes, and none of the sweep's plan or quota gates

`cross-sync-now-runs-a-second-chain` · **P2** · partial · owner **claude** · code · step **S10**

- **Expected:** One chain with one sweep id: every pass that makes cards relays its five funnel numbers, so production card volume can be measured ('one source per number'). _(source: genios_engine/api/routes.py:767-794 (THE FUNNEL'S ONE SWEEP ID; _count docstring))_
- **Actual:** The scheduled sweep runs _run_l2_chain (api/routes.py:738-864): provision, process_pending (5,000), funnel observe ×5 (793), _charge_ingestion (805), run_all, build_cards, run_post_passes for team, verify and meetings (854), then _reclaim_after_sweep (862).

The dashboard's Sync now runs a different function. It goes POST /integrations/sync-all, then a sync_jobs worker, then _onboarding_sync_bg, then _process_and_reason_unlocked (api/routes.py:3793-3868, 4029-4030, 4043-4078, 4119-4137). That function runs provision, process_pending in 500-event chunks, run_all and build_cards only. It writes no pipeline_counters rows (funnel.observe is called only at api/routes.py:793), runs no post-passes, and charges no ingestion. Its only gate is the daily model cap (api/routes.py:3952). The purge is global, so the next sweep covers it.
- **Evidence (measured):** `genios_engine/api/routes.py:738-864`; genios_engine/api/routes.py:793, 805, 854, 862 (the only call sites of funnel.observe, _charge_ingestion, run_post_passes, _reclaim_after_sweep); `genios_engine/api/routes.py:3793-3868 (_process_and_reason_unlocked)`; `genios_engine/api/routes.py:4029-4030, 4043-4078, 4119-4137`; `genios_engine/platform/funnel.py:54-58, 88 (pipeline_counters)`; `genios_engine/reason/team/postpass.py:24-30 (team, verify, meetings passes)`
- **What Rohit sees:** Cards made by a manual Sync have no funnel trail, so a funnel read undercounts the passes Rohit triggered himself. Meeting follow-ups and team/verify cards wait for the next scheduled sweep, which never comes on a lapsed org.
- **Where the mistake was:** The funnel, ingestion charge and post-passes were each wired into _run_l2_chain only. The Sync-job pass kept its own hand-written copy of the chain, and nothing tests that the two doors run the same stages.
- **Fix:** Make the Sync job call the same chain function as the sweep, keeping its progress callbacks, so both write the same funnel rows and run the same post-passes and gates. Or extract one chain body with the progress hooks as parameters. Add a test that both doors write card_delivered for the same sweep.
- **Blocked on:** Production comparison, read-only: select date_trunc('day', sweep_at) d, sum(n) filter (where stage = 'card_delivered') funnel_cards from pipeline_counters where org_id = '<ORG>' and sweep_at >= '2026-10-15' group by 1 order by 1; select date_trunc('day', created_at) d, count(*) cards_created from cards where org_id = '<ORG>' and created_at >= '2026-10-15' group by 1 order by 1; select date_trunc('day', created_at) d, count(*) sync_jobs from sync_jobs where org_id = '<ORG>' and created_at >= '2026-10-15' group by 1 order by 1;
- **Depends on:** [process-no-daily-production-card-health](#process-no-daily-production-card-health), [l1-post-deploy-funnel-unmeasured](#l1-post-deploy-funnel-unmeasured), [cross-billing-gates-silently-stop-the-org](#cross-billing-gates-silently-stop-the-org)
- **Verified:** added by the completeness critic, checked against the code by it

<a id="layer-process"></a>
## Process (verification, release, docs)

> CI itself is now sound. It has three jobs on Python 3.11 (the same version production runs), a Postgres 17 database suite, a scan that fails on unexplained skips, and a golden set that refuses to run without a database. It went green on the production branch at 0cc8d83c on 22 Oct. But nothing stops red code from reaching production. Branch protection is off on harsh/mvp, speedrun008 and main. The production branch was red on all 61 CI runs from 6 Sep to 21 Oct. The 823-commit merge c501eec9 never had a CI run of its own, and the first run that contained it (21 Oct) was red on bugs already in the production code: subjects re-decided on an unchanged sweep, cassettes recorded on an IST database, and a 24.5 s re-read query. No test calls a real model in CI. All 67 golden cassettes are written by the ideal reader, and the L2-vs-today comparison answers R-9 by copying the case's expert answer. So "63/63 parity" proves plumbing only. The production models of R-7 and R-9 (claude-sonnet-5) and the junk-gate prompt rewritten on 19 Oct have never had a valid real-model pass. The only pass that met its target (the STEP-13b Haiku ladder, held share 79% to 18.5%) sits on local, unpushed branches. Nothing measures production card volume or quality daily: pipeline_health, runtime_receipts and l2_shadow_report are manual scripts, the funnel counters are written every pass but read by nothing, and the dashboard shows only a weekly cards_7d tile. The card path is set by four activation tables plus several env flags. They are flipped by staff routes, by scripts/activate_tenant.py and by make_tenant_live itself, and their production state shows on no surface. Migrations apply at boot, except on a read-only database, where the boot is degraded and only an unmonitored /health says so. Whether 0243–0250 are applied, which commit is live, and which switches are on can only be answered from production. The exact read-only SQL is given in blocked_on. The two branches have drifted: harsh/mvp is 42 commits ahead of speedrun008, and Harsh's 27 rebuild commits of 19–21 Oct went straight to production and changed no plan or log document.

| Item | Sev | Status | Owner | Step |
|---|---|---|---|---|
| [The deploy host builds production on its own; no CI job deploys, and no deploy waits for CI or runs the health](#process-deploy-not-gated-on-ci) | P0 | unknown until production is read | claude+harsh | S03 |
| [The card-making model sites have never been measured on production's models; every CI golden answer is pre-aut](#process-no-real-model-pass-on-card-sites) | P0 | missing | rohit | S07 |
| [Nothing stops a push or merge to the production branch while CI is red](#process-prod-branch-unprotected-red-ci-ships) | P0 | broken | rohit+harsh | S03 |
| [There is no release gate for a 'fully functional' product](#process-release-gate-missing) | P0 | missing | claude+harsh | S05 |
| [The L2-vs-today golden comparison runs by hand, measures the path only, and lacks the L2 scenario kinds the pl](#process-l2-golden-board-not-in-ci) | P1 | partial | claude | S25 |
| [Which commit production runs cannot be read from outside](#process-live-sha-not-observable) | P1 | missing | claude+harsh | S03 |
| [Migrations apply at boot, but a read-only database silently skips them; whether 0243–0250 are applied in produ](#process-migrations-applied-unknown) | P1 | unknown until production is read | harsh | S02 |
| [Nothing measures production card volume or quality daily; the health tools exist but nothing runs or shows the](#process-no-daily-production-card-health) | P1 | missing | claude+harsh | S05 |
| [The three CI guards GeniOS-008 requires (card guard, situation-writer ratchet, model-site guard) do not exist](#process-rule3-ci-guards-not-built) | P1 | missing | claude | S04 |
| [About 20 switches decide the card path; code flips some itself, and their production state is shown nowhere](#process-switch-state-invisible) | P1 | partial | claude+harsh | S05 |
| [Two writers on two branches: harsh/mvp is 42 commits ahead of speedrun008, and Harsh's rebuild commits went st](#process-two-branches-drift-and-undocumented-prod-commits) | P1 | broken | claude+harsh | S03 |
| [The Blueprint's Phase 0 registry and Phase 5 benchmark run were never produced](#l1-blueprint-phase0-and-phase5-missing) | P2 | missing | claude | S43 |
| [The L1 folder docs stop at 18 Oct and contradict the code; the rebuild plan Harsh built from is not in the rep](#l1-docs-stale-after-19-oct-rebuild) | P2 | broken | claude | S41 |
| [06-CARDS README says the Cards page is 'Not merged, so not live', but dashboard origin/main 2edfb86 has merged](#l5-docs-stale-merge-state) | P2 | broken | claude+harsh | S41 |
| [CI takes 1.5 h per push and has no concurrency cancel](#process-ci-slow-no-concurrency) | P2 | partial | claude | S04 |
| [CI structure itself is now right: production's Python, real Postgres, no silent skips, golden set required](#process-ci-structure-sound) | P2 | done (lesson only) | claude | S04 |
| [The Next.js dashboard has no CI on push](#process-dashboard-has-no-ci) | P2 | missing | claude | S04 |
| [GeniOS-009 04-FOR-HARSH plans G1 as migration 0250, which the head already uses](#process-g009-migration-numbers-collide) | P2 | broken | claude | S26 |
| [GeniOS-010 docs and a memory note no longer match the repos](#process-geni010-docs-and-memory-drift) | P2 | broken | claude | S41 |
| [Goals docs are stale: G0 still marked red, the 0250 number is taken, and the Goals page is described as unmerg](#process-goals-docs-stale) | P2 | partial | claude | S26 |
| [A live R-9 pass through golden_eval would ask Haiku instead of production's Sonnet, and would not take the L2 ](#process-golden-eval-r9-wrong-model) | P2 | broken | claude | S07 |
| [The GeniOS-008 L2 folder stops at 18 Oct; Harsh's L2 rebuild and audit (19–21 Oct) are undocumented there](#process-l2-docs-stale) | P2 | missing | claude | S41 |
| [L3 was rebuilt and audited (20–21 Oct, now in prod) with no GeniOS-008 layer-3 folder, no 02-PLAN and no 04-FO](#process-no-layer-3-folder) | P2 | missing | rohit | S41 |
| [The Theresa/Antler acceptance replay has no goal obligation, uses the retired 7-layer vocabulary, and nothing ](#process-theresa-spec-has-no-goal) | P2 | missing | claude | S28 |
| [reason/expert/triggers.py still says D48 is open and a version change waits for inputs, but sweep.py re-checks](#process-triggers-docstring-says-d48-open) | P2 | broken | claude | S41 |
| [About half of the dashboard source is unreachable, and the repo has no test runner](#surfaces-dead-code-and-no-tests) | P2 | partial | claude | S04 |

<a id="process-deploy-not-gated-on-ci"></a>
### The deploy host builds production on its own; no CI job deploys, and no deploy waits for CI or runs the health gate

`process-deploy-not-gated-on-ci` · **P0** · unknown until production is read · owner **claude+harsh** · mixed · step **S03**

- **Expected:** Deploy only a CI-green SHA. Run the health gate right after each deploy and keep its output; a failure blocks the next deploy. _(source: speedrun008/YC-II W27/STEP-17-TO-BUILD-real-tests.md §3.4 and §4; speedrun008/YC-II W27/08-FOR-HARSH-deploy-and-after.md §0.2 step 9 and §0.6 step 23)_
- **Actual:** ci.yml has only test, golden-pg and database. It has no deploy job, no schedule, no workflow_dispatch and no post-deploy step. The Dockerfile's note says DigitalOcean App Platform builds from the Dockerfile on its own. The host's settings are not in the repo, and the runbook itself marks the host 'UNVERIFIED — ask the lead'. No release record (health.json) exists in the repo, and GeniOS-008/009/010 never mention pipeline_health. Whether the host auto-deploys every push to harsh/mvp, including red ones, cannot be seen from the code.
- **Evidence (mixed):** `.github/workflows/ci.yml:23-127 (three jobs; no deploy/schedule/workflow_dispatch/concurrency)`; `Dockerfile:17-21 (DigitalOcean App Platform prefers the Dockerfile at the component root)`; `speedrun008/YC-II W27/08-FOR-HARSH-deploy-and-after.md:91-93 ('Where is the host? … UNVERIFIED — ask the lead')`; `git ls-files | grep health.json → none; grep -rn pipeline_health speedrun008/GeniOS-008 GeniOS-009 GeniOS-010 → none`
- **What Rohit sees:** A red commit can be live before anyone reads CI, and a silent lane after a deploy is noticed only when Rohit sees fewer cards.
- **Fix:** Harsh: in the DO app, switch auto-deploy off (or deploy only from a branch that is fast-forwarded to green SHAs). Claude: add a post-deploy GitHub job (workflow_run on a green ci, or a manual dispatch) that runs scripts/pipeline_health.py --json read-only and uploads the record as an artifact. Run it again the next day with --require-data.
- **Blocked on:** Harsh: report the DO app's auto-deploy setting for harsh/mvp and the deployment history (SHA, time) for 18–22 Oct.
- **Depends on:** [process-prod-branch-unprotected-red-ci-ships](#process-prod-branch-unprotected-red-ci-ships)
- **Verified:** confirmed by the skeptic (ci.yml has 127 lines and three jobs (test, golden-pg, database). Its only triggers are on: push '**' and pull_request. It has no deploy job, schedule, workflow_dispatch or concurrency. Dockerfile:17-21 has the DigitalOcean App Platform note. 08-FOR-HARSH:91-93 says 'UNVERIFIED — ask the lead'. No health.json is tracked. pipeline_health appears in no GeniOS-008/009/010 file; it appears only in YC-II W27 STEP docs, where STEP-17:104 says 'the health gate in deploy … not built — no deploy hook in the repo'. Additional evidence: the GitHub deployments API shows the only integration that posts deployments is vercel[bot]. It creates a 'Production' deployment for every harsh/mvp push within seconds: 0cc8d83c was pushed at 14:29:58Z and its deployment is dated 14:30:07Z, with no wait for CI. There are 40 such deployments, from 12 Sep to 22 Oct. Every one sampled (0cc8d83c, 21b7ae10, 84f00a40, 9a51d0ea) has status failure, 'Deployment has failed'. The real API host (DO App Platform or Railway) posts no deployment or status to GitHub, so whether it builds red pushes still cannot be seen. The status stays unknown.)

<a id="process-no-real-model-pass-on-card-sites"></a>
### The card-making model sites have never been measured on production's models; every CI golden answer is pre-authored

`process-no-real-model-pass-on-card-sites` · **P0** · missing · owner **rohit** · paid_run · step **S07**

- **Expected:** Before a path or prompt goes live, the golden set is run on the real model at its production tier and compared, with a dollar cap: the expert gets a live pass on the D7 model before it reaches Rohit's account (D50), and L1 gets a live pass of junk_gate_batch, relevance and extraction (B1). A switch happens only when the new path scores at least as well. _(source: speedrun008/YC-II W27/06-DECISIONS.md D50, D72; speedrun008/GeniOS-008/layer-1-enterprise-signals/02-PLAN.md:26 (B1) and :51 (R1); speedrun008/GeniOS-008/01-RULES.md Rule 2.3; speedrun008/GeniOS-008/layer-2-reasoning/02-PLAN.md §6)_
- **Actual:** All 67 founder cassettes have source=ideal_reader. CI has no model key and only replays cassettes. Real-model passes so far: 12 Oct Haiku on the expert site (68 of 86 reviews held); 12–13 Oct Sonnet on the expert site, where all 203 calls were cut at max_tokens ('NOT a measure of Sonnet'); and 17 Oct, the Haiku ladder on the unpushed branch yc2w27-s13b. Never run live: R-7 on claude-sonnet-5 (its production model), R-9 reason_l2, the junk gate after its 19 Oct prompt rewrite (0d5939d1: '24 gate answers re-authored to the new prompt'), R-1, the narrator, the decider and extraction. In l2_score, R-9 is answered from the case's own expert answer, so 'a difference is the PATH's, never the model's'. D72 is still open. About $18 of the $20 live budget (D65) is spent.
- **Evidence (measured):** `tests/replays/specs/founder/cassettes/*.json: 67 of 67 source='ideal_reader' (python count)`; `tests/replays/ideal_reader.py:1-17 (the reader serves pre-written answers; live evaluation is golden_eval --live)`; `tests/replays/l2_score.py:1-9 (R-9 answered from the case's own expert answer)`; genios_engine/reason/bundle/sites.py:85,88 (R-7, R-9 = T2); genios_engine/reason/llm_sites.py:294-295 (T2 = claude-sonnet-5); speedrun008/YC-II W27/07-WHAT-IS-DONE.md:433-442 (Haiku 68/86 held; Sonnet pass not a measure; 'Nothing about Sonnet's judgment is known'); `git show -s 0d5939d1 (junk prompt rewritten; gate answers re-authored; cassettes re-recorded with the ideal reader)`; `git show -s 73d9f804 (17 Oct ladder pass; 'Total live spend … ≈ $18.0 of D65's $20'); branch yc2w27-s13b not on origin`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/02-PLAN.md:26 (B1 waits on Rohit's key and yes)`
- **What Rohit sees:** Rohit's 'fewer and weird cards' and 'sometimes no reasoning' cannot be traced to the model or ruled out. The new junk prompt may drop more real mail, and Sonnet's R-7/R-9 judgment on real dossiers has never been scored. Every green golden board says only that the plumbing carries an authored answer.
- **Where the mistake was:** The switch rule (Rule 2.3) was satisfied with ideal-reader parity, and the ideal reader copies the expert's answer into R-9. The live budget went mostly to a Sonnet pass that measured nothing (thinking used up max_tokens), and the only successful ladder pass was left on a local branch.
- **Fix:** (1) Rohit puts a key in GENIOS_GOLDEN_LIVE_KEY and approves a capped budget. (2) Claude runs scripts/golden_eval.py --live --spend-ok --max-usd N on --site junk_gate_batch, relevance and extraction (≈$1.02), then on the expert at claude-sonnet-5 (D72's two arms, capped at $7), then on reason_l2 with GENIOS_GOLDEN_L2=1 (needs process-golden-eval-r9-wrong-model). Scorecards are committed to speedrun008. (3) Add a workflow_dispatch CI job that runs a capped live pass on the sites a PR changes, with the key as a repo secret.
- **Blocked on:** Rohit: a key in GENIOS_GOLDEN_LIVE_KEY and a yes on new spend (D65 is ≈$2 from its cap; L1 R1 ≈$1.02; D72 ≤$7).
- **Verified:** confirmed with a correction by the skeptic: One detail is wrong. 'Never run live: R-7 on claude-sonnet-5' does not hold literally. In the 17 Oct ladder smoke (73d9f804: `--ladder T1,T2 F11 --max-usd 0.40`, 5 calls, $0.263), R-7 climbed to Sonnet and Sonnet's answer stood. That was one case only, and it ran the unpushed STEP-13b prompt (expert-review.v5, dossier.v2), not production's. So R-7 has never been measured on production's prompt and model. Everything else holds. All 67 founder cassettes are source='ideal_reader' (counted). R-7 and R-9 are both TIER_T2 (bundle/sites.py:85,88). tier_model('T2') returns 'claude-sonnet-5' (llm_sites.py:294-295), and the expert sweep uses it (expert/sweep.py:174-177). l2_score.py:1-9 answers R-9 from the case's own expert answer. 0d5939d1 says '24 gate answers re-authored … re-recorded with the ideal reader'. 73d9f804 records '≈ $18.0 of D65's $20'. No commit on any branch since 17 Oct records a live pass (git log --all --since=2026-10-13 grep 'live pass|--live|real model').

<a id="process-prod-branch-unprotected-red-ci-ships"></a>
### Nothing stops a push or merge to the production branch while CI is red

`process-prod-branch-unprotected-red-ci-ships` · **P0** · broken · owner **rohit+harsh** · prod_action · step **S03**

- **Expected:** Code reaches production only from a SHA whose CI is green: CI 'is the safety net every refactor stands on', and the guards 'run in CI' and turn it red. _(source: .github/workflows/ci.yml:1 header; speedrun008/GeniOS-008/01-RULES.md Rule 3; speedrun008/YC-II W27/STEP-17-TO-BUILD-real-tests.md §3.4 ('a failure blocks the next'))_
- **Actual:** There is no branch protection on any branch, and no required status checks. From 6 Sep (05f73d84) to 21 Oct (21b7ae10) the production branch had 61 CI runs, all red. The last green before that was c1dd89b3 on 2 Sep, and the next green was 0cc8d83c on 22 Oct. The 18 Oct merge c501eec9 (823 commits) never had a CI run of its own: harsh/mvp has no run between 84f00a40 (11 Oct) and 21b7ae10 (21 Oct). The first run that contained it, on 21 Oct, was red in golden-pg and database. The causes were cassette misses F03 F07 F14 F24 F55 F56; F13/F29 re-decided on an unchanged sweep (bisected to L3 2b ae5b5c7a); and a re-read ladder statement timeout. All three came from code that had already been merged for production, and all three were fixed only on 22 Oct (G0.1).
- **Evidence (measured):** GitHub API /branches/harsh%2Fmvp, /branches/speedrun008, /branches/main: protected=false, required_status_checks.enforcement_level=off; GitHub API actions/runs?branch=harsh/mvp (247 runs): window 2026-09-02T08:00..2026-10-22T14:00 = 61 runs, 61 failure; last success c1dd89b3 2026-09-02; next success 0cc8d83c 2026-10-22; Run 39633828127 (21b7ae10): golden-pg failure (check-run 119338845374 annotations: CassetteMiss at the expert and r1 sites), database failure (check-run 119338845521: test_the_compiled_lane_skips_an_unchanged_subject F13/F29, test_the_gate_is_counted, test_the_ladder_never_starves_pg QueryCanceled); git log --first-parent origin/harsh/mvp: c501eec9 2026-10-18 → 21b7ae10 2026-10-21 with no CI run between (actions/runs created=2026-10-12..2026-10-23, non-therohitji actors: only 21b7ae10 and 0cc8d83c); `speedrun008/GeniOS-009/03-LOG.md:15 (G0.1: three causes, all from Harsh's rebuild; fixes 3d5a6a3d, 8d1de446, 269400dc)`; `git show 8d1de446: 'F13/F29 re-decided … exposed by L3 2b (ae5b5c7a, bisected)'`
- **What Rohit sees:** From 20 Oct until the 22 Oct fixes were deployed, the production branch carried code that re-decided unchanged subjects (extra model spend and card churn) and a 24.5 s re-read query (40,804 correlated subqueries), and CI flagged it only after the merge. Any future red merge will reach Rohit's cards the same way.
- **Where the mistake was:** The prod branch was merged and pushed while red for 46 days. c501eec9 was pushed together with the 19–21 Oct rebuild commits in one push, so the 823-commit merge result was never tested before production received it. STEP-17 §3.4 wrote the gate as a runbook step (08-FOR-HARSH §0.2), not as a branch rule.
- **Fix:** In GitHub settings, protect harsh/mvp (and speedrun008). Require the status checks test, database and golden-pg, require the branch to be up to date, and forbid force pushes. Harsh merges speedrun008 only at a SHA whose run is green, through a PR into harsh/mvp.
- **Blocked on:** Repository admin rights on themoronss/genios-brain (Rohit or Harsh) to enable branch protection.
- **Verified:** confirmed by the skeptic (Measured via the public GitHub API. /branches for harsh%2Fmvp, speedrun008 and main all return protected=false and required_status_checks.enforcement_level=off. /rules/branches/harsh%2Fmvp and /rulesets are both [], so no ruleset exists either. The 247 harsh/mvp runs are all by hars123h. In the window 2026-09-02T08:00..2026-10-22T14:00 there are 61 runs and all 61 failed. The last success is c1dd89b3 (2026-09-02T07:54Z), the first failure after it is 05f73d84 (2026-09-06), and the next success is 0cc8d83c (2026-10-22T14:29Z). In run 39633828127 (21b7ae10), golden-pg failed on CassetteMiss: F03/F07/F14/F24 at the expert site, F55/F56 at r1. The database job failed on F13/F29 're-decided on an unchanged sweep', test_the_gate_is_counted, and the ladder test's QueryCanceled; the annotations match. 8d1de446 gives the cause as 'exposed by L3 2b (ae5b5c7a, bisected)'. The merge itself is 824 commits including c501eec9 (823 plus the merge). New detail: the GitHub push events show a single push 84f00a40→21b7ae10 at 2026-10-21T16:19:50Z, carrying 869 commits. That push included 75d08481, b9a21d91, 351de120, c501eec9 and all of Harsh's 19–21 Oct work. So nothing reached origin/harsh/mvp between 11 and 21 Oct. c501eec9 could not have had its own run, and its CI result arrived about 1.5 h after it was already on the production branch. Also, every harsh/mvp head carries a failing 'Vercel' commit status (0cc8d83c and 21b7ae10: state failure). A required-checks rule would have to account for that.)

<a id="process-release-gate-missing"></a>
### There is no release gate for a 'fully functional' product

`process-release-gate-missing` · **P0** · missing · owner **claude+harsh** · mixed · step **S05**

- **Expected:** A release passes only with all of these: (a) CI green on the exact SHA deployed; (b) a capped real-model golden pass on every model site the release changed, with the scorecard kept; (c) production health numbers the next day: pipeline_health --require-data, receipts exercised, and cards per day within a band of the baseline; (d) one card path per situation type, switched one type at a time with a one-line rollback and the old path deleted; (e) a canary tenant (Rohit's org) first, then the rest. _(source: Task brief (release-gate definition); STEP-17-TO-BUILD-real-tests.md §3.4, §4; speedrun008/GeniOS-008/01-RULES.md Rule 2.2–2.5)_
- **Actual:** (a) Not enforced (process-prod-branch-unprotected-red-ci-ships). (b) Manual, and never run on production's models (process-no-real-model-pass-on-card-sites). (c) Manual scripts with no runner (process-no-daily-production-card-health). (d) Several card paths are live together: deliver/pipeline.build_cards_for_org builds signal cards, situation-lane cards (cards_from_situations), question cards and file cards, reason/team/emit.py writes cards itself, and l2_cards adds an L2 path. (e) Per-tenant switches give a canary for features only. Prompt and code changes such as the 19 Oct junk-gate rewrite (0d5939d1) reach every tenant on deploy, because l1_llm_gate is a global bool.
- **Evidence (measured):** genios_engine/deliver/pipeline.py:340, 419, 799, 881 (question cards, file-card versioning, build_cards_for_org, situation lane); genios_engine/deliver/store.py:28,40 (SITUATION_CARD_BUILDER team.emit.v1, QUESTION_CARD_BUILDER); genios_engine/reason/team/emit.py (second cards writer); `genios_engine/platform/l4_activation.py:115-128 (l2_reasoning, l2_cards)`; `genios_engine/platform/config.py:233 (l1_llm_gate: global bool)`; `git show -s 0d5939d1`
- **What Rohit sees:** Each deploy is a blind change to every tenant's cards, and nothing says whether a release made cards better or worse.
- **Fix:** Write the gate as one script, scripts/release_gate.py, that exits 0 only if: the CI run for the SHA is green (GitHub API); the scorecards in GeniOS-008/scores cover each site whose prompt hash changed since the last release; the deployed /health SHA matches; and the next day's pipeline_health --require-data plus the card-volume band pass on the canary org. Put prompt changes behind a per-tenant switch or a canary org list. Track the single-card-path cutover per situation type in GeniOS-008 03-LOG.
- **Depends on:** [process-prod-branch-unprotected-red-ci-ships](#process-prod-branch-unprotected-red-ci-ships), [process-deploy-not-gated-on-ci](#process-deploy-not-gated-on-ci), [process-live-sha-not-observable](#process-live-sha-not-observable), [process-no-real-model-pass-on-card-sites](#process-no-real-model-pass-on-card-sites), [process-no-daily-production-card-health](#process-no-daily-production-card-health), [process-switch-state-invisible](#process-switch-state-invisible)
- **Verified:** confirmed by the skeptic (deliver/pipeline.py has _build_question_cards at :340, _version_file_card at :419, build_cards_for_org at :799 and the cards_from_situations lane at :881. deliver/store.py:28 has SITUATION_CARD_BUILDER='team.emit.v1' and :40 QUESTION_CARD_BUILDER. reason/team/emit.py:239/292 writes `insert into cards` directly, outside CardStore.insert_card; its callers are reason/team/passes.py and reason/meetings/passes.py. l2_cards is at l4_activation.py:122. config.py:233 'l1_llm_gate: bool = True' is global. Each sub-claim (a)–(e) is backed by the sibling items verified here.)

<a id="process-l2-golden-board-not-in-ci"></a>
### The L2-vs-today golden comparison runs by hand, measures the path only, and lacks the L2 scenario kinds the plan promised

`process-l2-golden-board-not-in-ci` · **P1** · partial · owner **claude** · code · step **S25**

- **Expected:** The golden set runs the old and the new path side by side as a guard, adds seven new scenario kinds (same email with different history, conflicting stakeholders, and so on), and scores framing, use of history, uncertainty, usefulness, cost and latency. _(source: speedrun008/GeniOS-008/layer-2-reasoning/02-PLAN.md §6; speedrun008/GeniOS-008/01-RULES.md Rule 2.3)_
- **Actual:** tests/replays/l2_score.py is a manual module, not referenced by ci.yml. Its first score was 57 of 63 with six regressions (0941927e). Parity was reached on 19 Oct (66c1f473, e9c8f019) and is reported by hand in commit messages after that. The CI board asserts only today's path, against a history document (YC-II W27/03-FINDINGS.md). There are 67 cases (53 must-detect, 14 must-abstain) and none has been added since 13 Oct (25d0173f). None covers the seven L2 scenario kinds, and none asserts a goal.
- **Evidence (measured):** `tests/replays/l2_score.py:1-9, 36-57 (manual main, ideal reader)`; `.github/workflows/ci.yml:79-86 (golden step + golden_score --assert-recorded 'speedrun008/YC-II W27/03-FINDINGS.md')`; `git show -s 0941927e ('57 of the 63 … 6 regress'); e9c8f019 ('were the 5 regressions left')`; `tests/replays/specs/founder/F*.json kinds: must_detect 53, must_abstain 14; last added F62 25d0173f 2026-10-13`
- **What Rohit sees:** A change to reason/l2 or the admission that loses a card on the L2 path passes CI, even though l2_cards is the cutover that decides Rohit's cards.
- **Fix:** Add a golden-pg step that runs python -m tests.replays.l2_score and exits 1 when the new path loses a case. Move the board's record into GeniOS-008. Author the seven scenario-kind cases (ideal-reader answers marked as such). Add a goal assertion to the cases once G1 lands.
- **Depends on:** [process-no-real-model-pass-on-card-sites](#process-no-real-model-pass-on-card-sites)
- **Verified:** confirmed with a correction by the skeptic: One detail is wrong. The last founder case added is F67 (fb20e7ce, 2026-10-16, STEP-16; F65/F66 the same day in 49fdb2a9/6d44c804), not F62 (25d0173f, 13 Oct). So no case has been added since 16 Oct. Everything else holds. tests/replays/l2_score.py is a manual __main__ module, and nothing in ci.yml or under tests references it or sets GENIOS_GOLDEN_L2. CI's golden-pg job (ci.yml:78-86) runs today's path and golden_score --assert-recorded 'speedrun008/YC-II W27/03-FINDINGS.md'. 0941927e reports '57 of the 63 … 6 regress', and e9c8f019 reports 'were the 5 regressions left'. There are 67 cases: must_detect 53, must_abstain 14. The seven scenario kinds are listed in GeniOS-008/layer-2-reasoning/02-PLAN.md:229-237, and no case is labelled with any of them.

<a id="process-live-sha-not-observable"></a>
### Which commit production runs cannot be read from outside

`process-live-sha-not-observable` · **P1** · missing · owner **claude+harsh** · mixed · step **S03**

- **Expected:** Anyone checking a deploy (08 step 9) can tell which SHA is live and which migration is the schema head. _(source: speedrun008/YC-II W27/08-FOR-HARSH-deploy-and-after.md §0.2 step 9 (reads /health, /config, schema_migrations by hand))_
- **Actual:** GET /health returns only {status, layer} (plus a degraded reason). /config returns env, composio, database and l1_relevance. GENIOS_BUILD_SHA is read only by /v1/benchmarks/scorecard, defaults to 'dev', and is not set in the Dockerfile. So the claim that prod received c501eec9 on 18 Oct cannot be checked against the repo: the first CI run containing it is 21 Oct.
- **Evidence (measured):** `genios_engine/api/routes.py:140-153 (/health body)`; `genios_engine/api/routes.py:280-285 (/config body)`; `genios_engine/api/benchmarks_routes.py:157 (build_sha from GENIOS_BUILD_SHA, default 'dev')`; `Dockerfile:33-87 (no GENIOS_BUILD_SHA)`
- **What Rohit sees:** When cards change, nobody can tie the change to a deploy.
- **Fix:** Bind the DO app's commit hash to GENIOS_BUILD_SHA and return it on /health together with the latest schema_migrations filename. Add a test that /health carries both keys.
- **Verified:** confirmed with a correction by the skeptic: The core claim holds. GET /health (genios_engine/api/routes.py:140-153) returns only status/layer, plus writes/reason when degraded. /config (routes.py:280-285) returns env, composio, database and l1_relevance. GENIOS_BUILD_SHA is read only at benchmarks_routes.py:157, defaults to 'dev', and is set nowhere in the repo, Dockerfile or Procfile. FastAPI version is a fixed '0.1.0' (main.py:128). No route exposes schema_migrations. The detail that is wrong is 'cannot be checked against the repo'. GitHub records show origin/harsh/mvp did not contain c501eec9 until 2026-10-21T16:19:50Z, from three independent sources. First, the push event 84f00a40→21b7ae10. Second, there is no CI run on harsh/mvp between 84f00a40 (2026-10-11) and 21b7ae10 (2026-10-21). Third, there is no Vercel Production deployment between those two either. So if the host builds from GitHub, production could not have run c501eec9 on 18 Oct; '18 Oct' is only its commit date. Which SHA is actually live is still unobservable.

<a id="process-migrations-applied-unknown"></a>
### Migrations apply at boot, but a read-only database silently skips them; whether 0243–0250 are applied in production is unknown

`process-migrations-applied-unknown` · **P1** · unknown until production is read · owner **harsh** · prod_action · step **S02**

- **Expected:** Code and schema deploy together. Before the deploy, default_transaction_read_only is off, and after the boot, schema_migrations shows the newest file. _(source: genios_engine/main.py:76-99 comment; 08-FOR-HARSH-deploy-and-after.md §0.1 step 6, §0.2 step 9)_
- **Actual:** apply_migrations runs at boot and applies pending files in filename order, one transaction per file. On a read-only server it raises ReadOnlyDatabaseError, and the app serves anyway in a DEGRADED BOOT, visible only as status 'degraded' on GET /health. Nothing in the repo monitors /health. The read-only trigger is Supabase's disk quota, and the 19 Oct sweep purge (7cab0ad4) was written because the database was near the 500 MB tier. Since 18 Oct the production branch has added 0243_reasoning_results, 0248_l1_sync_runs_coverage_index, 0249_l2_admissions and 0250_screen_followup_read_path (22 Oct). No newer migration exists on any pushed branch. Only the local-only yc2w27-s13b and yc2w27-haikufix branches carry 0250_expert_review_attempts.sql, which collides by number with production's 0250 (tests/test_migration_numbers_are_unique.py would fail on merge). The earlier 'five migrations unapplied' (0186–0190) note was superseded on 4 Oct.
- **Evidence (mixed):** `genios_engine/platform/migrate.py:135-180 (apply_migrations; ReadOnlyDatabaseError at :161)`; `genios_engine/main.py:84-99 (boot applies; read-only → degraded_read_only)`; `genios_engine/api/routes.py:140-153 (/health reports degraded)`; git log -- migrations/0243*,0248*,0249*,0250*: 62d618f6/d4817942 (0243), 1925a5bb (0248), fb429b78 (0249), 93ea3cbe 2026-10-22 (0250); `git ls-tree yc2w27-s13b migrations/ → 0250_expert_review_attempts.sql; tests/test_migration_numbers_are_unique.py:21-25`; `git show -s 7cab0ad4 ('the DB cannot outgrow the 500 MB tier')`; `memory five-migrations-unapplied.md (superseded: 0186–0190 applied 2026-10-02)`
- **What Rohit sees:** If the database went read-only, 0249 or 0250 would be missing and every card write naming their columns or tables would fail while /health only says 'degraded'. Cards would stop entirely.
- **Fix:** Harsh runs the read-only SQL now. Claude adds the schema head to /health (with process-live-sha-not-observable). Harsh adds an uptime monitor that alerts on /health status != ok. If STEP-13b is merged, renumber its 0250 to the next free number first.
- **Blocked on:** Production read: show default_transaction_read_only; select filename, applied_at from schema_migrations where filename >= '0243' order by filename; (expected: 0243_reasoning_results, 0248_l1_sync_runs_coverage_index, 0249_l2_admissions, 0250_screen_followup_read_path).
- **Verified:** confirmed with a correction by the skeptic: The mechanism is as described. migrate.py:135-180 applies files in filename order, one transaction per file, and raises ReadOnlyDatabaseError at :160-165. main.py:84-99 catches that, logs an ERROR 'DEGRADED BOOT', sets app.state.degraded_read_only and keeps serving. The only outside signal is /health returning status 'degraded'; it is logged, not silent, but no ops_alert is sent. What needs correcting is the scope of the unknown: it is wider than 0243–0250. origin/harsh/mvp sat at 84f00a40 from 11 Oct until the single push of 2026-10-21T16:19Z, and 84f00a40's newest migration is 0190_card_lane.sql. `git diff --name-status 84f00a40 origin/harsh/mvp -- migrations` lists 25 added files: 0191–0202, 0210–0212, 0220–0222, 0230, 0241–0243, 0248, 0249 and 0250. Of these, c501eec9 brought 20 (0191–0242), 0212 is the renumbered device-id migration (351de120), 0243 came with d4817942, 0248 with 1925a5bb, 0249 with fb429b78, and 0250_screen_followup_read_path with 93ea3cbe on 22 Oct. So whether all 25 are applied in production is unknown, not just 0243–0250. The 0250 collision is confirmed. Local-only yc2w27-s13b and yc2w27-haikufix carry 0250_expert_review_attempts.sql, and tests/test_migration_numbers_are_unique.py:21-27 would fail on a merge. The 7cab0ad4 subject reads '…the DB cannot outgrow the 500 MB tier', and its body says the database 'sat at 999 MB of a 500 MB tier'.

<a id="process-no-daily-production-card-health"></a>
### Nothing measures production card volume or quality daily; the health tools exist but nothing runs or shows them

`process-no-daily-production-card-health` · **P1** · missing · owner **claude+harsh** · code · step **S05**

- **Expected:** The health gate runs on every deploy and again the next day with --require-data, and its output is kept. G0.2.d calls for one week side by side with l2_shadow_report and the funnel. The funnel's reads are meant for an operator. _(source: STEP-17-TO-BUILD-real-tests.md §3.4, §4; 08-FOR-HARSH §0.6 step 23; speedrun008/GeniOS-009/STEP-G0-the-ground.md G0.2.d; migrations/0188_pipeline_counters.sql header)_
- **Actual:** scripts/pipeline_health.py (27 checks, exit 1 or 2), scripts/runtime_receipts.py and scripts/l2_shadow_report.py are manual CLIs that need a production database URL. No CI job, scheduler job or route runs them. The scheduler runs only the sync loop. The funnel writes its five pipeline_counters on every pass, but funnel.read_sweep, biggest_loss and read_latest have no caller, as the code itself declares. pipeline_health has no 'cards per day vs baseline' check: check_cards_reach_the_app counts live cards only. The dashboard admin has only the accounts, growth, money and llm-usage tabs. The home page shows cards_7d (this week's cards by band), with no daily trend, no quality signal and no alert. The memory note from 4 Oct says no receipt had ever been executed against a database.
- **Evidence (mixed):** `scripts/pipeline_health.py:1-30 (manual, 'can be a deploy gate'); :275-290 (check_cards_reach_the_app)`; `scripts/runtime_receipts.py:1-18 ('Exit code is 1 … so it can gate a release'); no caller in .github or genios_engine`; `genios_engine/platform/scheduler.py:84-140 (only the sync loop)`; genios_engine/api/routes.py:765-790 (funnel written per sweep); genios_engine/platform/platform_health.py:203-215 (funnel reads UNREACHED); genios_engine/api/home_routes.py:255-306 (cards_7d); dashboard origin/main src/product/internal/dashboard/homepage/live.ts:93; `dashboard origin/main src/components/admin/: accounts-tab, growth-tab, money-tab only`; `memory a-pass-over-an-empty-table-is-not-a-pass.md ('no receipt has ever been executed against a database')`
- **What Rohit sees:** The drop in cards after 18 Oct was found by Rohit's eye, not by a number. Nobody can say on which day volume fell, from which lane (builder_version, output_lane), or whether refusals or held reviews rose.
- **Fix:** Add a daily job (scheduler stage or DO cron) that writes one row per org per day: cards created by builder_version and output_lane, card_refusals by rule, expert_reviews by status, reasoning_results and l2_admissions by status, the funnel's five numbers, and LLM failure and truncation counts. Add a staff route and an admin 'Health' tab with a 30-day chart. Alert when cards per day fall below half of the 14-day median, or when any lane is NO DATA for 24 h. Keep pipeline_health's JSON per deploy.
- **Blocked on:** Production read (Rohit's permission), read-only: select created_at::date d, builder_version, output_lane, count(*) from cards where org_id='<ORG>' and created_at >= now()-interval '45 days' group by 1,2,3 order by 1,2,3; select refused_at::date, writer, rule, count(*) from card_refusals where org_id='<ORG>' and refused_at >= now()-interval '45 days' group by 1,2,3 order by 1; select reviewed_at::date, status, count(*) from expert_reviews where org_id='<ORG>' and reviewed_at >= now()-interval '30 days' group by 1,2 order by 1; select reasoned_at::date, status, count(*) from reasoning_results where org_id='<ORG>' group by 1,2 order by 1; select sweep_at::date, stage, sum(n) from pipeline_counters where org_id='<ORG>' and sweep_at >= now()-interval '30 days' group by 1,2 order by 1,2;
- **Verified:** confirmed with a correction by the skeptic: Two details need correcting. (1) 'No … route runs them' is wrong for the receipts. GET /health/readiness (genios_engine/api/routes.py:156-201) runs platform/receipts.evaluate per tenant. Its own docstring calls that 'the same list the release-gate CLI runs', i.e. scripts/runtime_receipts.py. But nothing calls this route: no CI job, no scheduler job, and no dashboard code (origin/main has no 'health/readiness' reference), so the substance holds. (2) The dashboard admin has three tabs: growth, accounts and money (src/app/dashboard/admin/page.tsx:21-25). llm-usage is an API call inside them (src/lib/api-admin.ts:180,184), not a tab. Everything else holds. pipeline_health.py has 27 check_* functions, exit 1 on a failure and exit 2 under --require-data. check_cards_reach_the_app (:275-290) counts live cards only, and there is no per-day or baseline check. The scheduler (platform/scheduler.py:84-140) runs only the maintenance and light sync sweeps. The funnel's read_sweep, biggest_loss and read_latest have no caller in genios_engine or scripts; platform_health.py:203-215 declares them unreached. home_routes cards_7d is a 7-day band count, with daily series only for decisions, situations and outcomes. The only alerting, ops_alert, fires on a sweep crash or timeout, a sync failure, the LLM cap and warm-lane parks, never on card volume or quality.

<a id="process-rule3-ci-guards-not-built"></a>
### The three CI guards GeniOS-008 requires (card guard, situation-writer ratchet, model-site guard) do not exist

`process-rule3-ci-guards-not-built` · **P1** · missing · owner **claude** · code · step **S04**

- **Expected:** CI fails when a card of a switched type does not trace to a ReasoningResult, when the list of nine situation writers in context/ grows, or when a model call appears outside the places the architecture allows. _(source: speedrun008/GeniOS-008/01-RULES.md Rule 3; speedrun008/GeniOS-008/02-MIGRATION-PLAN.md:107 (L0-5), :152 (the 9 writers))_
- **Actual:** No test lists the nine writers as a ratchet. No test ties a card to a ReasoningResult. No commit mentions L0-5. The nearest guard is tests/test_every_llm_call_site_is_metered.py, a register that fails on any new model call site for billing reasons, but it does not check the architecture's layer placement.
- **Evidence (measured):** `git log --all --grep='L0-5' → only 3bcc1179 (the plan) and d4817942 (merge message)`; grep -rl 'outreach_situations' tests | xargs grep -l situation_bso | xargs grep -l meeting_touch → tests/test_nothing_is_written_and_never_read.py, tests/context/test_situation_publisher.py (neither is a ratchet); `tests/test_every_llm_call_site_is_metered.py:1-30 (metering register, not placement)`
- **What Rohit sees:** New situation-forming sites or model calls in the old places can be added without CI noticing, and that keeps the 'L2 and L3 fail each other' split alive.
- **Fix:** Build the three guards as AST-based tests: (1) a ratchet over the nine named writers (count can only fall); (2) a placement map, site to allowed package, checked against SITE_MARKERS and the metering register; (3) for each type switched to L2, every card's file has an admitted reasoning_results row (a Postgres test on the golden tenant). Each needs a mutation check.
- **Verified:** confirmed with a correction by the skeptic: The card guard and the layer-placement guard are indeed missing. tests/test_every_llm_call_site_is_metered.py is a metering register: it does turn CI red on any new model-call module, but it is not checked against 00-ARCHITECTURE. No test asserts that a card of a switched type traces to a ReasoningResult; tests/reason/l2/* test the L2 path's behaviour, not that invariant. A situation-writer ratchet does exist in partial form under another name. tests/context/test_situation_importance.py:505-547 (`test_a_new_writer_of_context_situations_has_to_be_ranked_too`) runs in CI's test and database jobs. It fails when any module under genios_engine/ or scripts/ contains 'insert into context_situations' outside its 5 known modules (situations, periodic, support_situations, meeting_touch, document_register), and also fails when a declared one stops writing. It is not the 9-writer list in 02-MIGRATION-PLAN L3-2. It misses writers that refresh or update rows (age_uncorrelated_situations, situation_bso.refresh_situation_importance, lifecycle/store.apply_lifecycle) and writers that go through a helper (outreach via support_situations._upsert). It is also not shrink-only. tests/context/test_l2_must_not_regress.py:547 lists the same 5 modules, but only for the axis columns. Minor: `git log --all -F --grep='L0-5'` returns nothing at all, not 3bcc1179/d4817942; pickaxe -S'L0-5' shows the text was added by 3bcc1179, and no commit implements it.

<a id="process-switch-state-invisible"></a>
### About 20 switches decide the card path; code flips some itself, and their production state is shown nowhere

`process-switch-state-invisible` · **P1** · partial · owner **claude+harsh** · mixed · step **S05**

- **Expected:** Switches are flipped one at a time on Rohit's org, with a dry run and a note. Every pushed group records its switches in the layer's 04-FOR-HARSH. An operator can see what is live and what it turned on. _(source: 08-FOR-HARSH-deploy-and-after.md §0.5; speedrun008/GeniOS-008/01-RULES.md Rule 4.5; genios_engine/platform/l4_activation.py PRECONDITIONS docstring)_
- **Actual:** The card path is set by four tables: l1_semantic_activation; l2_v2_activation (analytic, patterns); l3_activation (domains read from Domain Expertise/*/domain.yaml); and l4_activation (12 features). Five L4 features are default-on (roster_v2, ranking_v2, bundle, critique, brief). Seven are not (cards_from_situations, calibration_apply, expert_review, morning_brief, l2_reasoning, l2_cards, and situation_reasoner, which is retired). Env flags add more: l4_llm_decision_maker and _orgs, use_domain_compiler, l1_llm_gate, enable_l1_relevance, warm_lane_enabled, scheduler_enabled, plus budgets of $2 per day for R-7 and R-9. Who flips: Harsh, via scripts/activate_tenant.py or the staff POST/DELETE /admin/l{1..4}-activation routes, and the code itself, via make_tenant_live on sign-in, upload and the chain. Visibility: staff-only GET routes. The dashboard has no switch view, and /config shows none of the env flags. No 03-LOG line records any production flip; the GeniOS-008 layer logs end on 18 Oct.
- **Evidence (measured):** `genios_engine/platform/l4_activation.py:63-135 (12 features)`; `genios_engine/platform/intelligence_onboarding.py:167-206 (NOT_DEFAULT_ON, L4_DEFAULT_FEATURES)`; genios_engine/api/auth_routes.py:115-116, genios_engine/api/upload_routes.py:425-426, genios_engine/api/routes.py:1777-1778 (make_tenant_live callers); `genios_engine/platform/config.py:110-113,160,181,229,233,260 (env flags)`; `genios_engine/api/admin_routes.py:933-1460 (staff activation routes)`; `genios_engine/api/routes.py:280-285 (/config exposes only env, composio, database, l1_relevance)`; `dashboard origin/main: git grep 'activation' in src → no switch view; admin tabs accounts/growth/money only`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/03-LOG.md and layer-2-reasoning/03-LOG.md: last line 2026-10-18`
- **What Rohit sees:** Whether Rohit's cards come from the expert (R-7), the L2 judgment (l2_cards), the compiled lane, the situation lane or the legacy per-signal lane depends on rows nobody can see. 'Sometimes no correlation, sometimes no reasoning' cannot be traced to a switch.
- **Fix:** Add one staff route, GET /admin/live-state/{org}, returning every activation row (live and stamped off), the env flags above, the deployed SHA and the schema head. Show it in an admin 'Switches' tab. Every flip writes a line in the layer's 03-LOG. Harsh first reports today's state with the SQL below.
- **Blocked on:** Production read: select org_id, feature, enabled_at, enabled_by, disabled_at from l4_activation where org_id='<ORG>' order by feature; select * from l3_activation where org_id='<ORG>'; select * from l2_v2_activation where org_id='<ORG>'; select * from l1_semantic_activation where org_id='<ORG>'; plus Harsh reads the host's GENIOS_L4_LLM_DECISION_MAKER, GENIOS_L4_LLM_DECISION_MAKER_ORGS, GENIOS_USE_DOMAIN_COMPILER, GENIOS_L1_LLM_GATE, GENIOS_ENABLE_L1_RELEVANCE values.
- **Verified:** confirmed by the skeptic (l4_activation.py:65-122 defines 12 features. intelligence_onboarding.py:167-206 sets NOT_DEFAULT_ON to situation_reasoner, cards_from_situations, calibration_apply, expert_review, morning_brief, l2_reasoning and l2_cards, which leaves 5 default-on. l2_activation has the analytic and patterns switches (l2_activation.py:68,70). l3_activation reads domain.yaml (:102). make_tenant_live is called at auth_routes.py:115-116, upload_routes.py:425-426 and routes.py:1777-1778. The env flags are at config.py:110-111, 160, 181, 229, 233 and 260. The staff GET/POST/DELETE routes for l1–l4 are at admin_routes.py:933-1460. /config shows none of the flags. The dashboard admin has no switch view (only the growth, accounts and money tabs). No GeniOS-008/009/010 log line records a production flip (grep for 'switched on|flipped|armed|activate' together with prod or Rohit's org found nothing). Both GeniOS-008 layer 03-LOGs end on 2026-10-18.)

<a id="process-two-branches-drift-and-undocumented-prod-commits"></a>
### Two writers on two branches: harsh/mvp is 42 commits ahead of speedrun008, and Harsh's rebuild commits went straight to production without the layer documents

`process-two-branches-drift-and-undocumented-prod-commits` · **P1** · broken · owner **claude+harsh** · mixed · step **S03**

- **Expected:** One branch. All work is pushed to speedrun008, and Harsh deploys it. Each pushed group updates the layer's 03-LOG and 04-FOR-HARSH (changes, migrations, switches, commands, rollback). Each layer has its own folder with the five files. _(source: speedrun008/YC-II W27/STEP-00-PENDING-owner-harsh-one-branch.md; speedrun008/GeniOS-008/01-RULES.md Rule 4.2, 4.3, 4.5)_
- **Actual:** origin/harsh/mvp is 42 commits ahead of origin/speedrun008 and 0 behind. 36 of those are Harsh's non-merge commits. The last back-merge from harsh/mvp to speedrun008 is aa22e395 (12 Oct). Harsh's 27 non-merge commits of 19–21 Oct (L1 rebuild 1925a5bb, junk gate 0d5939d1, L2 rebuild A1–D1, l2_admission, L3 rebuild 1a–5b, L2/L3 audits) changed 0 .md files. The GeniOS-008 layer-1 and layer-2 03-LOGs end on 18 Oct, and there is no layer-3 folder. The rebuilds' golden results exist only in commit messages ('L2 golden 63 -> 63'). Pushers: hars123h made all 247 harsh/mvp runs, therohitji pushes speedrun008. The default branch main last moved on 24 Aug and is 1,448 commits behind production, and agent worktrees are cut from it.
- **Evidence (measured):** `git rev-list --left-right --count origin/speedrun008...origin/harsh/mvp → 0 42`; `git log origin/speedrun008 --merges | grep harsh/mvp → aa22e395 2026-10-12 (latest)`; git log --no-merges --author=Harsh --since=2026-10-19 --until=2026-10-22 --name-only origin/harsh/mvp | grep .md → none (27 commits); `speedrun008/GeniOS-008/ has layer-1-enterprise-signals and layer-2-reasoning only; both 03-LOG last row 2026-10-18`; `git show -s 9794dfec b8a8a43c ('L2 golden 63 -> 63')`; `GitHub API: harsh/mvp runs 247/247 actor hars123h; origin/main de642ffc 2026-08-24, 1448 behind origin/harsh/mvp`; `memory agent-worktrees-start-on-origin-main.md`
- **What Rohit sees:** The next speedrun008 work starts without Harsh's L1/L2/L3 rebuild unless it is merged back. Nobody reading the plan folders can tell what the rebuild changed in the card path, which switches it needs, or how to roll it back.
- **Where the mistake was:** Harsh's build sessions (Claude co-authored) committed to the production branch and skipped Rule 4.5. Rohit's sessions stopped back-merging after 12 Oct. The L3 work started without a layer folder (Rule 4.1/4.2).
- **Fix:** Fast-forward speedrun008 to origin/harsh/mvp now (speedrun008 is 0 ahead). Agree on one rule: all code lands on speedrun008 through green CI, and harsh/mvp only fast-forwards to a green speedrun008 SHA. Backfill the layer-1 and layer-2 03-LOG and 04-FOR-HARSH entries, plus a layer-3 folder, for the 19–21 Oct commits (switches, migrations 0248/0249, rollback). Make speedrun008 or harsh/mvp the default branch, or move main.
- **Verified:** confirmed by the skeptic (`git rev-list --left-right --count origin/speedrun008...origin/harsh/mvp` gives 0 and 42, of which 36 are non-merge commits, all by Harsh Tripathi. The latest harsh/mvp→speedrun008 merge is aa22e395 (2026-10-12). The 27 Harsh non-merge commits of 19–21 Oct (15+6+6) touch 0 .md files. The only .md files in the 42 are GeniOS-009/03-LOG.md and GeniOS-010/LOG.md, both from 22 Oct. GeniOS-008 has only layer-1 and layer-2 folders, and both 03-LOGs end on 2026-10-18. 'L2 golden 63 -> 63' appears only in the 9794dfec and b8a8a43c messages. All 247 harsh/mvp runs are by hars123h, and the push events show therohitji pushing speedrun008. origin/main is de642ffc (2026-08-24), 1,448 commits behind harsh/mvp. Minor: the layer folders hold six or seven files (00–05/06), not five.)

<a id="l1-blueprint-phase0-and-phase5-missing"></a>
### The Blueprint's Phase 0 registry and Phase 5 benchmark run were never produced

`l1-blueprint-phase0-and-phase5-missing` · **P2** · missing · owner **claude** · docs · step **S43**

- **Expected:** Phase 0 maps every existing capture/ file to group → section → function → component → unit with BUILT/RUNNING/TARGET/GAP/UNVERIFIED. Phase 5 runs the five benchmark prompts (P1 relationship ledger, P2 commitments, P3 cold threads, P4 meetings, P5 conditions) against the actual source enumeration. _(source: 05-BLUEPRINT-the-spec.md Part 6 (lines ~2725-2790); 02-PLAN 'Not doing' (L1 re-planned on the Blueprint, Phase 0 first))_
- **Actual:** No L1 Architecture Registry exists in speedrun008/GeniOS-008/layer-1-enterprise-signals/ or docs/plans (grep 'Architecture Registry' matches only the Blueprint). No benchmark P1–P5 run is recorded.
- **Evidence (measured):** `speedrun008/GeniOS-008/layer-1-enterprise-signals/05-BLUEPRINT-the-spec.md:2725-2790`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/02-PLAN.md 'Not doing'`; `grep -rl 'Architecture Registry' speedrun008 docs → only the Blueprint`
- **Fix:** Write the Phase 0 registry from the code (marking RUNNING only where a production caller chain exists). Run Phase 5 together with the B1 live pass.
- **Depends on:** [l1-b1-live-pass-never-run](#l1-b1-live-pass-never-run)
- **Verified:** confirmed with a correction by the skeptic: Phase 0 is missing as stated: 'Architecture Registry' appears only in 05-BLUEPRINT-the-spec.md. 'No benchmark P1-P5 run is recorded' is too strong. A structural P1-P5 scoreboard exists: genios_engine/capture/benchmark.py (24 Sep, commits c98e9eff and c7323afe), machine-checked in CI by tests/golden/l1/test_the_benchmark_scoreboard_is_machine_checked.py. There is also an earlier hand audit, speedrun008/Ancient Architecture/docs/L1_P1_P5_AUDIT.md (16 built, 8 stranded, 14 missing). What was never run is the Blueprint's Phase 5 behavioural run of the five prompts against the actual source enumeration (05-BLUEPRINT:2790ff). benchmark.py refuses to quote a behavioural score until the 425-item corpus and the second mailbox exist (CORPUS_MINIMUM=425; behavioural_score_is_quotable).

<a id="l1-docs-stale-after-19-oct-rebuild"></a>
### The L1 folder docs stop at 18 Oct and contradict the code; the rebuild plan Harsh built from is not in the repo

`l1-docs-stale-after-19-oct-rebuild` · **P2** · broken · owner **claude** · docs · step **S41**

- **Expected:** Four docs per layer, with an append-only log. Every L1 change is recorded with its commit and proof. _(source: memory layer-folder-file-set; GeniOS-008/README; 03-LOG.md header 'append-only')_
- **Actual:** 03-LOG.md's last row is 18 Oct, with no rows for 1925a5bb, a8dbefa2 or 0d5939d1. 00-START-HERE, 02-PLAN and 04-FOR-HARSH still say production is 815 commits behind (false since c501eec9), that B2 waits on R1 and E9 is not fixed (both done in 0d5939d1), and §5 still says 'Do not edit the junk-filter prompt'. 1925a5bb cites docs/plans/L1_REBUILD_PLAN.md '(workspace)', which is absent from the repo. 08-FOR-HARSH:582 says an archive is 'read by no model', which is false for llm_junk.
- **Evidence (measured):** `speedrun008/GeniOS-008/layer-1-enterprise-signals/03-LOG.md (last row 2026-10-18)`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/00-START-HERE.md:3-5,14`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/04-FOR-HARSH.md §5, §7`; `git show 1925a5bb (Plan: docs/plans/L1_REBUILD_PLAN.md (workspace)); ls docs/plans → absent`; `speedrun008/YC-II W27/08-FOR-HARSH-deploy-and-after.md:582`
- **Where the mistake was:** The 19 Oct L1 rebuild was committed outside the GeniOS-008 layer-folder process, so the plan and the code diverged. The next agent reads B2 as still blocked.
- **Fix:** Append 03-LOG rows for 1925a5bb, a8dbefa2 and 0d5939d1, with commit and proof. Update 00/02/04 status (B2, E9, H1 done; B1 still open). Commit L1_REBUILD_PLAN.md. Correct 08:582.
- **Verified:** confirmed with a correction by the skeptic: The substance holds. 03-LOG.md's last rows are dated 2026-10-18. The L1 folder has no mention of 1925a5bb, a8dbefa2 or 0d5939d1. 00-START-HERE.md:3-5 says 'B waits for R1' and that E9 is not fixed. 04-FOR-HARSH.md §5:130 still says 'Do not edit the junk-filter prompt', and §7:144-148 still lists B1, B2 and E9 as open. docs/plans/L1_REBUILD_PLAN.md is absent in every branch (git log --all shows nothing), although docs/plans/ exists. 08-FOR-HARSH:582 says 'read by no model'. Detail fixes: the '815 commits behind' claim is in 00-START-HERE.md:14,39 and 04-FOR-HARSH.md:30, not in 02-PLAN. 02-PLAN is stale in other places: E9 'audited, not fixed' (02-PLAN.md:96) and B2 'after B1' (02-PLAN.md:27). The 19 Oct commits are recorded in another folder, speedrun008/GeniOS-009 (03-LOG.md, STEP-G0-the-ground.md, 01-AS-IS-CARDS.md), but not in the L1 log.

<a id="l5-docs-stale-merge-state"></a>
### 06-CARDS README says the Cards page is 'Not merged, so not live', but dashboard origin/main 2edfb86 has merged rohit/cards-ux

`l5-docs-stale-merge-state` · **P2** · broken · owner **claude+harsh** · docs · step **S41**

- **Expected:** Docs state the true merge and deploy state. _(source: speedrun008/GeniOS-010/06-CARDS/README.md 'Status, 22 Oct 2026')_
- **Actual:** git merge-base --is-ancestor 25553ab origin/main succeeds. origin/main HEAD 2edfb86 is 'Merge origin/rohit/cards-ux into harsh/genios-010-wire'. The README and 01-INTEGRATION still say not merged. Whether brain.thegenios.com redeployed is not known from the repo.
- **Evidence (measured):** `dashboard: git log origin/main -1 → 2edfb86 Merge remote-tracking branch 'origin/rohit/cards-ux'`; `speedrun008/GeniOS-010/06-CARDS/README.md:'Not merged, so not live.'`
- **Where the mistake was:** Harsh merged the branch on 22 Oct after the docs were pushed, and nobody updated the status line.
- **Fix:** Update the 06-CARDS README status and 01-INTEGRATION §7 to 'merged in 2edfb86'. Harsh confirms the dashboard deploy.
- **Verified:** confirmed with a correction by the skeptic: 01-INTEGRATION.md never literally says 'not merged'. Its §7 'Merge notes' (lines 256-259) gives merge instructions, which implies the merge was still pending. The docs that do say 'Not merged' are 06-CARDS/README.md:36 ('Not merged, so not live.') and 04-WHAT-WHY-HOW.md:16 ('Not merged.').

<a id="process-ci-slow-no-concurrency"></a>
### CI takes 1.5 h per push and has no concurrency cancel

`process-ci-slow-no-concurrency` · **P2** · partial · owner **claude** · code · step **S04**

- **Expected:** Fast feedback. Speed is Rohit's top complaint, and full suites are run by CI, not locally. _(source: memory speed-is-rohits-top-complaint.md; memory full-suites-are-ci-and-harsh.md ('why CI checks take 60–90 min'))_
- **Actual:** The 22 Oct run (39796159785) took: test 33 min, database 83 min, golden-pg 97 min. ci.yml has no concurrency/cancel-in-progress and no timeout-minutes, and it runs on every push to every branch ('**'). The hermetic test job re-runs the same -m 'not golden' suite that the database job runs with a database.
- **Evidence (measured):** `GitHub API runs/39796159785/jobs: golden-pg 14:30:00→16:07:01, database 14:30:00→15:53:19, test 14:30:00→15:03:27`; `.github/workflows/ci.yml:23-27 (on: push branches '**'); no 'concurrency' or 'timeout-minutes' (grep)`; `.github/workflows/ci.yml:45 and :119 (same pytest -m 'not golden' selection)`
- **Fix:** Add a concurrency group per ref with cancel-in-progress. Shard the database and golden suites with pytest-xdist or a matrix. Run the hermetic job only for import and no-DB guards. Set timeout-minutes.
- **Verified:** confirmed by the skeptic (Jobs of run 39796159785: test 14:30:00→15:03:27 (33 min), database 14:30:00→15:53:19 (83 min), golden-pg 14:30:00→16:07:01 (97 min). The 21 Oct run took 51/51/84 min. ci.yml:23-26 has on: push branches '**' plus pull_request, and has no 'concurrency' or 'timeout-minutes'. The duplicated selection is at ci.yml:45 (test) and :118 (database), not :119.)

<a id="process-ci-structure-sound"></a>
### CI structure itself is now right: production's Python, real Postgres, no silent skips, golden set required

`process-ci-structure-sound` · **P2** · done (lesson only) · owner **claude** · code · step **S04**

- **Expected:** CI runs on production's Python 3.11, runs the database suite on Postgres, fails on a skip that has no allowed reason, and refuses a golden run without a database. _(source: STEP-17-TO-BUILD-real-tests.md §1, §3.0–3.2, §3.5)_
- **Actual:** Done. All three jobs run on python-version 3.11, matching Dockerfile FROM python:3.11-slim-bookworm (an earlier run used 3.12). The database and golden-pg jobs use a Postgres 17 service. GENIOS_GOLDEN_REQUIRED=1 is set. scripts/qa/database_skips.py fails the job on any unexplained skip. tests/platform/test_every_statement_plans.py and tests/test_programme_step_status_is_consistent.py exist. The production branch went green at 0cc8d83c on 22 Oct.
- **Evidence (measured):** `.github/workflows/ci.yml:33-36, 53-71, 127`; `Dockerfile:33`; `scripts/qa/database_skips.py; tests/platform/test_every_statement_plans.py; tests/test_ci_runs_the_database_suite.py`; `GitHub API run 39796159785: test, database, golden-pg success`
- **Fix:** None. Keep it, and extend it with the L2 board and Rule 3 guards.
- **Verified:** confirmed by the skeptic (All three jobs use python-version '3.11' (ci.yml:35,72,109), matching Dockerfile:33 FROM python:3.11-slim-bookworm. golden-pg and database use a postgres:17 service. GENIOS_GOLDEN_REQUIRED='1' is set (ci.yml:67) and enforced in tests (e.g. tests/replays/test_an_unchanged_sweep_costs_nothing.py:38-39). scripts/qa/database_skips.py exists with ALLOWED and returns 1 on an unexplained skip; it runs with if: success() || failure() (ci.yml:125-127). tests/platform/test_every_statement_plans.py, tests/test_ci_runs_the_database_suite.py and tests/test_programme_step_status_is_consistent.py exist. Run 39796159785 (0cc8d83c) succeeded on all three jobs. Caveat: sound structure does not gate anything, because there is no branch protection (see process-prod-branch-unprotected-red-ci-ships).)

<a id="process-dashboard-has-no-ci"></a>
### The Next.js dashboard has no CI on push

`process-dashboard-has-no-ci` · **P2** · missing · owner **claude** · code · step **S04**

- **Expected:** The surface that shows the cards is type-checked and built before it is merged or deployed. _(source: Same principle as ci.yml's header ('the safety net every refactor stands on'))_
- **Actual:** The dashboard repo's only workflow is desktop-release.yml. It fires on desktop-v* tags, on PRs touching Extension/**, and on manual runs. Nothing type-checks, lints or builds src/ on a push to main.
- **Evidence (measured):** `dashboard origin/main: git ls-tree .github → .github/workflows/desktop-release.yml only`; `dashboard origin/main:.github/workflows/desktop-release.yml:1-22 (triggers)`
- **Fix:** Add a web CI workflow: npm ci, tsc --noEmit, next lint, next build on push and PR.
- **Verified:** confirmed by the skeptic (Dashboard origin/main 2edfb86 has only .github/workflows/desktop-release.yml. It fires on tags desktop-v*, on pull_request with paths Extension/** or the workflow file, and on workflow_dispatch, and its header says 'Nothing here touches the Next.js dashboard'. package.json scripts are dev/build/start/lint. next.config.ts has no typescript.ignoreBuildErrors, so if the host builds with `next build` it would type-check before a deploy, though not before a merge. The repo is private, so its host's deployments cannot be read here.)

<a id="process-g009-migration-numbers-collide"></a>
### GeniOS-009 04-FOR-HARSH plans G1 as migration 0250, which the head already uses

`process-g009-migration-numbers-collide` · **P2** · broken · owner **claude** · docs · step **S26**

- **Expected:** Each planned migration number is free at build time (the 0191 → 0212 lesson). _(source: speedrun008/GeniOS-009/04-FOR-HARSH.md 'Numbering'; 09-HARSH-HANDOVER.md §5 rule 4)_
- **Actual:** The group table names 0250_company_goals … 0255. The head already has migrations/0250_screen_followup_read_path.sql (GeniOS-010 B8, 93ea3cbe), so the planned numbers are off by one at least. The session's established fact 'migrations end at 0249' is also one behind.
- **Evidence (measured):** `migrations/0250_screen_followup_read_path.sql (git log: 93ea3cbe)`; `speedrun008/GeniOS-009/04-FOR-HARSH.md group table G1 → 0250_company_goals`
- **Where the mistake was:** A plan table hard-coded migration numbers despite the handover's own rule, and a parallel GeniOS-010 change took 0250.
- **Fix:** Renumber the table to 'next free at build time (≥0251)' and add the check command to it.
- **Verified:** confirmed with a correction by the skeptic: STEP-G1-the-goal-object.md:266 already hedges with '`migrations/0250_company_goals.sql` (or the next free number)', so the plan is stale rather than unguarded. A second collision is missing from the item: the local-only STEP-13b branch (yc2w27-s13b) also adds migrations/0250_expert_review_attempts.sql. 0250 is claimed three times, and both planned blocks need renumbering at build time.

<a id="process-geni010-docs-and-memory-drift"></a>
### GeniOS-010 docs and a memory note no longer match the repos

`process-geni010-docs-and-memory-drift` · **P2** · broken · owner **claude** · docs · step **S41**

- **Expected:** The start page, LOG and memory say what is merged and live. _(source: memory layer-folder-file-set / genios-010-dashboard-folder ('Append a line to LOG.md for every change'))_
- **Actual:** 00-START-HERE still says 'Built and tested, but not live … not merged'. Dashboard main 2edfb86 now contains rohit/nav-grouping and rohit/cards-ux. LOG's last dashboard line says Harsh's wiring 238f45e is 'Not pushed', but it is in main. The 07-GENIOS-DESKTOP folder exists only on branch g010-desktop. Memory dashboard-navigation-22-oct says main contains rohit/desktop-ux, which is false.
- **Evidence (measured):** `speedrun008/GeniOS-010/00-START-HERE.md 'Status, 22 Oct 2026'`; `speedrun008/GeniOS-010/LOG.md (Harsh wiring line: 'Not pushed')`; dashboard: origin/rohit/nav-grouping and origin/rohit/cards-ux are ancestors of origin/main; origin/rohit/desktop-ux is not; `brain: origin/g010-desktop not an ancestor of 0cc8d83c`
- **Where the mistake was:** The 23 Oct memory line recorded a merge without checking ancestry. A later session would assume the Mac fixes are on main.
- **Fix:** Append LOG lines for the 2edfb86 merge. Update the 00-START-HERE status table. Merge g010-desktop docs. Correct the memory note.
- **Verified:** confirmed by the skeptic (speedrun008/GeniOS-010/00-START-HERE.md:5-6 says 'Built and tested, but not live', and :17 says rohit/nav-grouping is 'not merged'. origin/speedrun008 (c1a6d94c) carries the same stale text. LOG.md:54 marks Harsh's wiring 238f45e 'Not pushed', but 238f45e is an ancestor of dashboard origin/main. In the dashboard repo, origin/rohit/nav-grouping (847eeac) and origin/rohit/cards-ux (25553ab) are ancestors of origin/main, and origin/rohit/desktop-ux (ed2724d) is not. 07-GENIOS-DESKTOP exists only on brain origin/g010-desktop (01b31e0a), which is not an ancestor of 0cc8d83c. The memory note dashboard-navigation-22-oct.md:39 says main contains rohit/desktop-ux, which is false.)

<a id="process-goals-docs-stale"></a>
### Goals docs are stale: G0 still marked red, the 0250 number is taken, and the Goals page is described as unmerged

`process-goals-docs-stale` · **P2** · partial · owner **claude** · docs · step **S26**

- **Expected:** The handover docs state the measured truth, so Harsh and agents do not rebuild what is done or pick a taken migration number. _(source: GeniOS-009/09-HARSH-HANDOVER.md; memory 'a stale comment reads as a measurement')_
- **Actual:** GeniOS-009/00-START-HERE.md's step table says G0 is 'open — CI red on 21b7ae10', and 04-FOR-HARSH.md 'State on 22 Oct' says CI is red, yet 03-LOG's 'G0.1 (Harsh, with Claude)' row records the fix and the fix commits are in HEAD. 00-START-HERE lists 0250_company_goals, but 0250 is migrations/0250_screen_followup_read_path.sql. GeniOS-010/03-GOALS/README.md says the Goals page sits 'on the unmerged branch', but cc1b58f is in dashboard origin/main.
- **Evidence (measured):** `speedrun008/GeniOS-009/00-START-HERE.md step table`; `speedrun008/GeniOS-009/04-FOR-HARSH.md 'State on 22 Oct 2026'`; `speedrun008/GeniOS-009/03-LOG.md G0.1 row`; `migrations/0250_screen_followup_read_path.sql`; `git -C dashboard merge-base --is-ancestor cc1b58f origin/main → true`
- **Where the mistake was:** The G0.1 fix was logged in 03-LOG but never carried into the status table and the handover.
- **Fix:** Update 00-START-HERE (G0.1 done; G0.2–G0.4 open) and 04-FOR-HARSH. Renumber the migration table from 0251. Mark the Goals page as merged in GeniOS-010/03-GOALS. Append a correction line to 03-LOG.
- **Verified:** confirmed by the skeptic (00-START-HERE.md:110 says 'open — CI red on 21b7ae10'. 04-FOR-HARSH.md:6-16 says CI is red. 03-LOG.md:15 records the G0.1 fix, and its commits are in HEAD. 00-START-HERE.md:77 lists 0250_company_goals, but 0250 is screen_followup_read_path; line 73 of the same doc does hedge ('next free one at build time'). GeniOS-010/03-GOALS/README.md:6 says 'on the unmerged branch', but cc1b58f is an ancestor of dashboard origin/main 2edfb86.)

<a id="process-golden-eval-r9-wrong-model"></a>
### A live R-9 pass through golden_eval would ask Haiku instead of production's Sonnet, and would not take the L2 path

`process-golden-eval-r9-wrong-model` · **P2** · broken · owner **claude** · code · step **S07**

- **Expected:** `--site <x>` asks that site's own production tier and settings (the docstring says the expert's is its tier's). _(source: scripts/golden_eval.py:29-37 (--site semantics))_
- **Actual:** SITE_TIERS holds only the expert. For --site reason_l2, model_for returns DEFAULT_MODEL (claude-haiku-4-5), and site_settings (thinking, ceiling) is applied only to sites in SITE_TIERS. golden_eval never sets GENIOS_GOLDEN_L2, so the cases would run today's path, not L2's.
- **Evidence (measured):** `scripts/golden_eval.py:70,72 (DEFAULT_MODEL Haiku; SITE_TIERS = {'expert': 'R-7'})`; `scripts/golden_eval.py:86-95 (model_for)`; `scripts/golden_eval.py:594-596 (site_settings only for SITE_TIERS)`; `grep GENIOS_GOLDEN_L2: only tests/replays/engine_runner.py:431 and tests/replays/l2_score.py`
- **Fix:** Add 'reason_l2': 'R-9' to SITE_TIERS and an --l2-path flag that sets GENIOS_GOLDEN_L2=1. Add a dry-run test asserting the R-9 model is claude-sonnet-5.
- **Verified:** confirmed by the skeptic (scripts/golden_eval.py:70 DEFAULT_MODEL='claude-haiku-4-5-20251001'; :72 SITE_TIERS={'expert':'R-7'}; :86-94 model_for falls back to DEFAULT_MODEL for any site outside SITE_TIERS; :594-596 site_settings is applied only when r_site = SITE_TIERS.get(site). reason_l2 is a valid harness site marker (tests/replays/harness.py:111-112), so `--site reason_l2` is accepted, but it would be priced and asked on Haiku. GENIOS_GOLDEN_L2 / L2_PATH_ENV is set only in tests/replays/l2_score.py and speedrun008/GeniOS-009/measurements/card_dump.py, never in golden_eval.py. A live pass there therefore runs today's expert path, where R-9 is never asked.)

<a id="process-l2-docs-stale"></a>
### The GeniOS-008 L2 folder stops at 18 Oct; Harsh's L2 rebuild and audit (19–21 Oct) are undocumented there

`process-l2-docs-stale` · **P2** · missing · owner **claude** · docs · step **S41**

- **Expected:** Each pushed group writes its section in 04-FOR-HARSH, and 03-LOG is appended per unit with proof. _(source: speedrun008/GeniOS-008/layer-2-reasoning/02-PLAN.md §7 preamble; memory layer-folder-file-set)_
- **Actual:** 00-START-HERE (18 Oct) still says 'no money tool' and that G2 waits for L3 to build the gate. 03-LOG's last entry is 18 Oct. 04-FOR-HARSH has only G-1. 'l2_cards' appears 0 times in speedrun008/GeniOS-008. Meanwhile prod received fb429b78 (admission + 0249), de795bb8 (l2_cards), 11e31e45 (money tool), 9794dfec (judgment hold), b8a8a43c (conflicts and the oversized-prompt fix), e5eee70e and 23555915 (gate and history reorder).
- **Evidence (measured):** `speedrun008/GeniOS-008/layer-2-reasoning/00-START-HERE.md build-status table`; `speedrun008/GeniOS-008/layer-2-reasoning/03-LOG.md (last row 2026-10-18)`; `grep -rn l2_cards speedrun008/GeniOS-008 → 0`; `git log -- genios_engine/reason/l2 (Harsh, 19–21 Oct)`
- **Where the mistake was:** The rebuild landed directly on harsh/mvp without updating the layer folder, so anyone reading the plan believes L2 is still shadow-only, with G2 unbuilt and no money tool.
- **Fix:** Append 03-LOG rows for each rebuild/audit commit, write a G-2 section in 04-FOR-HARSH for l2_cards (switch, what to watch, rollback), and refresh the 00-START-HERE status table.
- **Verified:** confirmed by the skeptic (grep -rn l2_cards over speedrun008/GeniOS-008 returns 0. The last 03-LOG rows are dated 2026-10-18. 04-FOR-HARSH has only the 'G-1' section (:55). 00-START-HERE.md:50 says 'no money tool' and :59 says 'L3 builds the gate'. The last commit to that folder is 391751f7 on 18 Oct. Every cited commit (fb429b78, de795bb8, 11e31e45, 9794dfec, b8a8a43c, e5eee70e, 23555915, plus f3cfd3c6) is Harsh's, dated 19-21 Oct, and is an ancestor of HEAD. The rebuild is described only in commit messages and in GeniOS-009 (22 Oct). context_health.py:39 cites docs/plans/L2_REBUILD_PLAN.md, which does not exist in the worktree.)

<a id="process-no-layer-3-folder"></a>
### L3 was rebuilt and audited (20–21 Oct, now in prod) with no GeniOS-008 layer-3 folder, no 02-PLAN and no 04-FOR-HARSH

`process-no-layer-3-folder` · **P2** · missing · owner **rohit** · docs · step **S41**

- **Expected:** Rohit opens each layer. Each layer folder holds 00-START-HERE, 01-AS-IS, 02-PLAN, 03-LOG and 04-FOR-HARSH, and 04 is written with the code. _(source: speedrun008/GeniOS-008/01-RULES.md Rule 4.1-4.2, 4.5)_
- **Actual:** speedrun008/GeniOS-008 holds only layer-1-enterprise-signals and layer-2-reasoning. Commits f3cfd3c6, 5985b6e1, ae5b5c7a, 34779fe0, df3c2aa8 ('L3 rebuild 1a-5b') and 21b7ae10, 7297b31a, 8cfe15a6, bda38c3d ('L3 audit') cite no plan document; a grep of docs/ and speedrun008/ finds none. 02-MIGRATION-PLAN L3-1…L3-7 carry no status.
- **Evidence (measured):** `ls speedrun008/GeniOS-008/ (no layer-3 folder)`; `git log -- genios_engine/context (Harsh, 2026-10-20/21)`; `speedrun008/GeniOS-008/02-MIGRATION-PLAN.md:147-157`
- **Where the mistake was:** The L3 rebuild and audit landed outside the GeniOS-008 process (Rule 4), so its plan claims were never checked against the code, e.g. 'wired' in L3-1 and L3-6.
- **Fix:** Rohit opens L3. Then write layer-3-context-graph/00-04 from this audit, recording L3-1…L3-7 status and Harsh's nine commits.
- **Verified:** confirmed by the skeptic (Verified. speedrun008/GeniOS-008 holds only layer-1-enterprise-signals and layer-2-reasoning, and no layer-3 path ever existed in git history. All nine L3 rebuild and L3 audit commits are by Harsh, 20-21 Oct. They cite Atlas v2 but no plan file. A grep for 'L3 rebuild' or 'L3 audit' in docs/ and speedrun008/ finds only a GeniOS-009 03-LOG line. 02-MIGRATION-PLAN.md:147-157 has ID and Item columns and no status. Also, the L2 rebuild plan that code cites (context_health.py:40, docs/plans/L2_REBUILD_PLAN.md) does not exist in the repo.)

<a id="process-theresa-spec-has-no-goal"></a>
### The Theresa/Antler acceptance replay has no goal obligation, uses the retired 7-layer vocabulary, and nothing in the founder golden set covers Antler

`process-theresa-spec-has-no-goal` · **P2** · missing · owner **claude** · code · step **S28**

- **Expected:** A founder golden case (founder format, run on the real chain) in which the Antler Singapore application becomes a proposed goal, is approved, and its card carries the goal line. _(source: F2; speedrun008/GeniOS-009/STEP-G3 §3.3 (golden labels); GeniOS-008/00-ARCHITECTURE.md (layer vocabulary))_
- **Actual:** tests/replays/specs/01-theresa_investor_reconsideration_and_update_cade.json (commit 944b4f76) frames Theresa only as an investor reconsideration. Its business_subject is 'not Antler as an organization'. Its layer_obligations run L1–L7 with 'BSO' (the old Atlas). It has no goal field, and every mutation is a strict xfail, 'blocked_missing_capability', whose blocked_on cites '140/152 corpus capabilities are stubs'. No file under tests/replays/specs/founder mentions Antler or Theresa.
- **Evidence (measured):** tests/replays/specs/01-theresa_investor_reconsideration_and_update_cade.json (business_subject, layer_obligations, mutations[].blocked_on); `git log -- that file → 944b4f76`; `grep -li 'antler|theresa' tests/replays/specs/founder/*.json → 0`
- **What Rohit sees:** No test would catch it if Antler-type workstreams never become goals.
- **Fix:** Write founder case F72, 'Antler Singapore application, partner's conditional reply → proposed goal', with expected.proposed_goal and expected.goals, recorded with the ideal reader, strict-xfail until the design lands. Re-state 01-theresa's blocked_on in GeniOS-008 terms, or mark it superseded by F72.
- **Depends on:** [cross-layer-l2-proposes-l3-admits-goal-design](#cross-layer-l2-proposes-l3-admits-goal-design)
- **Verified:** confirmed with a correction by the skeptic: Mostly holds. Spec 01 (944b4f76) frames Theresa as an investor reconsideration ('not Antler as an organization'), its layer_obligations run L1–L7 and mention BSO, and it has 0 'goal' mentions. All 10 mutations are implemented='blocked_missing_capability', which runs as a strict xfail (tests/replays/test_golden_replays.py:101-102). Three details are wrong. (a) Only 1 of the 10 mutations' blocked_on cites '140/152 corpus capabilities are stubs', not every one. (b) Founder cases cannot mention Antler or Theresa because tests/replays/founder_case.py:84-90 forbids real names (REAL_NAMES), so the expected case must be a synthetic analogue. The natural candidate is F17 (accelerator application to interview), which today links the application only in words to the umbrella goal. (c) An Antler-specific replay spec also exists: 12-antler_exploratory_relationship_and_regional_aut.json, an operator-side Singapore 2026 application. 16 of its 17 mutations are blocked, and it has no goal obligation either.

<a id="process-triggers-docstring-says-d48-open"></a>
### reason/expert/triggers.py still says D48 is open and a version change waits for inputs, but sweep.py re-checks and re-reviews on a version move

`process-triggers-docstring-says-d48-open` · **P2** · broken · owner **claude** · docs · step **S41**

- **Expected:** Comments state the current rule. D48 was answered 12 Oct: a prompt or check version change re-checks each standing review, and re-reviews when the dossier moved. _(source: speedrun008/YC-II W27/06-DECISIONS.md D48; memory note 'a stale comment reads as a measurement')_
- **Actual:** triggers.py:28-29 says 'That is 06 D48's default for the prompt (the decision is open; its default "waits for inputs")'. reason/expert/sweep.py:245-265 re-checks a review whose CHECK_VERSION moved and re-reviews when a version moved and the file moved.
- **Evidence (measured):** `genios_engine/reason/expert/triggers.py:28-29`; `genios_engine/reason/expert/sweep.py:250-265 (D48 recheck / version_moved)`
- **Where the mistake was:** The D48 build updated the sweep but not the module docstring that states the rule.
- **Fix:** Claude corrects the docstring to describe what sweep.py does.
- **Verified:** confirmed by the skeptic (reason/expert/triggers.py:27-29 still says 'That is `06` D48's default for the prompt (the decision is open; its default "waits for inputs")'. 06-DECISIONS.md:55 records '✅ Rohit, 12 Oct: yes — and for the expert too: a prompt or check version change re-checks each standing review ... reviewed again only when its dossier changed'. reason/expert/sweep.py:248-265 implements exactly that: recheck on a CHECK_VERSION move, and re-review on version_moved when the file moved (commit e8241798).)

<a id="surfaces-dead-code-and-no-tests"></a>
### About half of the dashboard source is unreachable, and the repo has no test runner

`surfaces-dead-code-and-no-tests` · **P2** · partial · owner **claude** · code · step **S04**

- **Expected:** Code that runs is code that is checked. Old readers of deleted brain routes are removed. _(source: speedrun008/GeniOS-010/04-BUILD-REVIEW.md §5 'Not covered' and R9)_
- **Actual:** An import walk from src/app/**/*.tsx reaches 133 of 249 .ts/.tsx files. 116 are unreachable, among them components/insights/decision-inbox.tsx, components/dashboard/actions-card.tsx (reads the renamed intervention_rate) and lib/api-v2-metrics.ts (calls the deleted /v1/metrics/intervention_rate/*). package.json scripts are dev, build, start and lint only, so there are no tests. The sidebar is a fixed 244px and never collapses below phone width (R10).
- **Evidence (measured):** `scratch import walk over dashboard origin/main src (133 reachable / 116 unreachable)`; `dashboard origin/main:src/components/dashboard/actions-card.tsx:40-56`; `dashboard origin/main:src/lib/api-v2-metrics.ts:63-90`; `dashboard origin/main:package.json:5-10`; `dashboard origin/main:src/components/layout/sidebar.tsx:336`
- **Fix:** Delete the unreachable files in one reviewed commit. Add vitest for lib/card-read.ts and the live.ts mappers (desktop-ux already has refusals.test.ts and rows.test.ts to copy).
- **Verified:** confirmed with a correction by the skeptic: My own import walk over origin/main src/ (entries: every .ts/.tsx under src/app, resolving '@/' to src/, following type imports too) gives 248 files: 132 reachable and 116 unreachable. The item's 249/133/116 is the same result within one file. components/insights/decision-inbox.tsx and components/dashboard/actions-card.tsx are unreachable. lib/api-v2-metrics.ts, however, IS reached, but only through a type-only import (lib/governance-demo.ts:12, from the audit/approvals/policies/reports pages). All of its runtime callers are unreachable: components/dashboard/calibration-chart.tsx, north-star-card.tsx and secondary-metrics-row.tsx. So its calls to the deleted /v1/metrics/intervention_rate* (api-v2-metrics.ts:63-90) never run, but the file itself does not count as unreachable.
