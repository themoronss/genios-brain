# 01 · What went wrong — where the mistakes were made

**Written for:** Rohit, Harsh and every coding agent.

This is the ledger of the mistakes behind today's state: by Claude sessions, by the plans, and by the process. Every entry has evidence (a memory note, a commit, a doc line) and was checked by a skeptic. Each entry ends with the rule that prevents it; [02-PLAN](02-PLAN.md) S42 turns those rules into GeniOS-011's standing rules.

## The patterns, in order of what they cost

1. **We proved the plumbing and called it intelligence.**
   - Every golden case, board and switch rule ran on the *ideal reader*: the model's answer was written in advance.
   - The real model was measured once (12 Oct, Haiku). The claim check held 68 of 86 of its reviews.
   - The production models (Sonnet 5 on R-7 and R-9) have never finished a live golden pass.
   - The L1 junk-gate prompt was rewritten and shipped on ideal-reader recordings.
   - So "63/67 green" never meant "good cards".
2. **Production changed in one big jump, and nobody measured it after.**
   - The YC-II W27 + GeniOS-008 merge (`c501eec9`, 823 commits; committed 18 Oct, first on GitHub's prod branch in the 21 Oct push) changed the card engine at once.
   - 33 more commits followed in four days.
   - CI on the prod branch was red on 4, 9, 11 and 21 Oct.
   - Nothing stops a push to the prod branch while CI is red, and nothing reads production numbers after a deploy.
   - So "fewer and weird cards" cannot yet be pinned to one change.
3. **For ~20 days (5–17 Oct) we patched the old flow while Atlas v2 was already the target.** YC-II W27 checked each step against today's code, not against the architecture. GeniOS-008 had to re-plan on top of it.
4. **The plans had holes in exactly the places Rohit cares about.**
   - GeniOS-008's architecture names the goal loop but defines no goal object.
   - GeniOS-009 left "a goal from what is in motion" to the weekly brief drafter, which never sees the graph. So the Antler admission could not become a goal even after G1–G9.
   - The investor and programme playbooks were gated on a 267-line review nobody did.
5. **We shipped before we audited, and failures read as "nothing to do".**
   - The L2/L3 rebuild reached production before its audit.
   - That audit then found silent failures that match Rohit's symptoms.
   - Almost every skip (budget, refusal, truncation, hold, no situation) shows only in a server log line.
6. **We fixed symptoms on the surface.** The Cards page hides text that repeats across cards, instead of fixing why L5 repeats it.
7. **Session conduct.**
   - Wide fan-out burned the session limit.
   - Guesses were offered as causes before measuring.
   - Rohit was asked what the data already answered.
   - Asks were overbuilt (a redesign when he asked to regroup) or misread (a design canvas when he asked for his real cards).
   - Layer digits from another vocabulary made him think we were on the old architecture.
8. **Docs said "done" for things that were not wired.**
   - Status files are kept by hand.
   - Harsh's L1/L2/L3 rebuilds have no layer log.
   - Three plans reserved migration 0250.

## Two of my own mistakes in this session (23 Oct)

- **The deploy date.** I told Rohit "18 Oct ko production branch mein 823 commits gaye". The merge was *committed* on 18 Oct. It first reached GitHub's prod branch on 21 Oct, and `480f7cd4` says production still ran 10 Oct code on 19 Oct. The real deploy date is a fact only Harsh has (S01.U3).
- **The dashboard merge.** I wrote a memory note that dashboard `origin/main` contains `rohit/desktop-ux`. It does not, as `merge-base --is-ancestor` shows. The note is corrected.


## The ledger — every mistake with its evidence

| # | Mistake | Layer | Sev | Still open? | Step |
|---|---|---|---|---|---|
| M01 | [The goal plan's only inferred-goal source is the weekly brief drafter, which reads patterns; no unit proposes a goal fro](#goals-no-unit-proposes-goals-from-context) | Goals | P0 | missing | S26 |
| M02 | [YC-II W27 spent ~20 days (5-17 Oct) patching the old flow while Design Atlas v2 was already the target](#process-built-on-the-old-flow) | Process | P0 | partial | S25 |
| M03 | [823 commits reached production in one merge on 18 Oct, with no production number per step](#process-823-commit-big-bang-deploy) | Process | P0 | partial | S01 |
| M04 | [No one measured production after the 18 Oct deploy: switch state, card counts and expert outcomes are unknown](#process-no-production-number-after-deploy) | Process | P0 | unknown until production is read | S01 |
| M05 | [Every gate, board and switch rule was proven with the ideal reader; the real model was measured once, and the claim chec](#process-verified-with-the-ideal-reader-only) | Process | P0 | missing | S07 |
| M06 | [The L1 junk-gate prompt was rewritten and shipped to production on ideal-reader recordings, skipping the live pass its p](#l1-junk-gate-prompt-shipped-on-ideal-reader) | L1 | P1 | partial | S07 |
| M07 | [The old gate deleted mail content (258 S1 drops). The fix shipped, but the re-sync that brings that mail back is a manua](#l1-deleted-mail-needs-resync) | L1 | P1 | unknown until production is read | S09 |
| M08 | [The investor and programme playbooks were gated on a 267-line YAML review that was never done, and the Sales investor co](#l2-founder-playbooks-gated-on-unread-review) | L2 | P1 | built, not live | S23 |
| M09 | [The LLM decision maker ran in production for every org with no fallback, and a spend limit then stopped all cards from 2](#l2-llm-decider-without-fallback-in-production) | L2 | P1 | partial | S02 |
| M10 | [Signal-type observations take the extraction's first span as their 'quote', often a bare name, and cards narrate it as s](#l3-signal-type-observation-quotes-a-name) | L3 | P1 | broken | S16 |
| M11 | [GeniOS-008's architecture names the goal loop but defines no goal object, so the rebuilds and every card contract carry ](#goals-architecture-defines-no-goal-object) | Goals | P1 | missing | S26 |
| M12 | [The golden tenant ships a hand-curated brief (5 accepted goals, 20 in-motion lines), so no test sees a tenant whose brie](#goals-golden-brief-is-pre-curated) | Goals | P1 | missing | S27 |
| M13 | [The Cards page hides text that repeats across cards instead of fixing why the brain repeats it](#surfaces-ui-hides-repeated-brain-text) | Surfaces | P1 | partial | S34 |
| M14 | [The L2/L3 rebuild reached production before its audit, and the audit then found silent failures that match Rohit's sympt](#cross-l2-l3-rebuild-shipped-before-its-audit) | Cross-layer | P1 | no — lesson only | S01 |
| M15 | [No plan budgeted the 500 MB database tier, and production reached 999 MB before a purge was added](#cross-db-tier-never-budgeted) | Cross-layer | P1 | partial | S05 |
| M16 | [Code reached the production branch while CI was red (4, 9, 11, 21 Oct), and 199 golden failures were accepted as 'pre-ex](#process-red-ci-reached-production) | Process | P1 | partial | S03 |
| M17 | [Harsh's L1/L2/L3 rebuilds have no GeniOS-008 layer log, L3 has no folder, and the L1 rebuild plan lives outside the repo](#process-rebuild-without-layer-docs) | Process | P1 | missing | S41 |
| M18 | [A hermetic suite with 15,494 passing tests hid eight live SQL bugs, because no test ran SQL against Postgres](#process-green-suite-never-ran-sql) | Process | P1 | no — lesson only | S42 |
| M19 | [A $10.4 Sonnet pass measured nothing: Claude 5 thinks by default, the thinking ate max_tokens, and the harness hid the c](#process-claude5-thinking-ate-the-budget) | Process | P1 | no — lesson only | S42 |
| M20 | [Wide agent fan-out burned the shared session limit and killed every worker mid-unit](#process-fan-out-exhausted-the-quota) | Process | P1 | no — lesson only | S42 |
| M21 | [A crosscheck report silently dropped three of five lenses (8 blocking findings) by cutting its input at 100,000 characte](#process-report-silently-truncated) | Process | P1 | no — lesson only | S42 |
| M22 | [Giving archived mail its text exposed it to every reader that selects by thread membership (F57); only the dossier was m](#l1-archive-text-exposed-by-membership) | L1 | P2 | partial | S06 |
| M23 | [A plan was built on a corpus count of files ('534 capabilities, 37% admissible'); the real number was 155 capabilities, ](#l2-corpus-counted-as-files) | L2 | P2 | no — lesson only | S42 |
| M24 | [A unit was specified on a stale code comment ('A situation's status gates nothing') and had to be withdrawn](#l2-stale-comment-specified-a-unit) | L2 | P2 | no — lesson only | S42 |
| M25 | [graph_facts.authority_rank holds a 0-6 ladder and a derived default of 100 in the same column](#l3-two-authority-scales) | L3 | P2 | broken | S17 |
| M26 | [The history replay filed mail the live drain had called noise (newsletters, out-of-office) into people's files; it was l](#l3-replay-filed-noise) | L3 | P2 | partial | S09 |
| M27 | [Two planned L4 fixes would have discarded every future meeting (F9) and invalidated every replay snapshot (F10)](#l4-fixes-that-would-have-caused-harm) | L4 | P2 | no — lesson only | S42 |
| M28 | ['Calibration repaired' was planned as a one-line fix that would have switched on unattended auto-mute](#l6-calibration-one-line-fix-was-a-trap) | L6 | P2 | no — lesson only | S42 |
| M29 | [U03 was retracted on a fact about a different writer, while the publisher wrote an illegal governed -> published edge on](#l6-retraction-on-a-neighbouring-fact) | L6 | P2 | no — lesson only | S42 |
| M30 | [macv_ledger, the North Star value ledger, was created in 0012 and has never had a writer; docs claimed feedback/ wrote i](#l6-north-star-ledger-no-writer) | L6 | P2 | missing | S33 |
| M31 | [The Mac app's real files were rebuilt and pushed after a 'ha' to a plan, instead of a clickable dummy first](#surfaces-real-files-before-dummy) | Surfaces | P2 | no — lesson only | S42 |
| M32 | [A design canvas with golden sample cards was delivered when Rohit asked for his real Cards page fixed with his real card](#surfaces-canvas-instead-of-real-cards) | Surfaces | P2 | no — lesson only | S42 |
| M33 | [A dashboard redesign prototype was built when Rohit asked only to regroup the existing pages](#surfaces-redesign-instead-of-regroup) | Surfaces | P2 | no — lesson only | S42 |
| M34 | [The UI audit said the web dashboard shows no cards, judging from an unmounted component and a 13 Aug local clone](#surfaces-claimed-dashboard-shows-no-cards) | Surfaces | P2 | no — lesson only | S42 |
| M35 | [The dashboard metrics endpoint returns aer: 0, time_saved_hours: 0 and context_calls_today: 0 as constants](#surfaces-aer-hardcoded-zero) | Surfaces | P2 | broken | S39 |
| M36 | [The Goals page folds cards with an empty domain, and Founder Office cards, into Admin; this review finding was never fix](#surfaces-goals-page-folds-domains) | Surfaces | P2 | broken | S39 |
| M37 | [Mac app rounds were lost to ad-hoc signed builds (Accessibility lost), an old mounted DMG, a staged git rm in an unrelat](#surfaces-desktop-build-traps) | Surfaces | P2 | no — lesson only | S42 |
| M38 | [Full suites and fresh scratch databases for small changes filled Rohit's disk and used his time](#process-local-full-suites-and-scratch-dbs) | Process | P2 | no — lesson only | S42 |
| M39 | [QA runs spanned a sleeping Mac (battery, closed lid), and their clock failures were nearly chased as bugs](#process-qa-on-a-sleeping-mac) | Process | P2 | no — lesson only | S42 |
| M40 | [Local QA runs on Python 3.13, and tests seeded with fixed dates passed locally but failed in CI (3.11) or later in time](#process-python-and-calendar-time-bombs) | Process | P2 | partial | S04 |
| M41 | [Who pushes changed several times (Rohit, then Claude, then classifier-denied, then Rohit), so commits sat local and CI f](#process-push-ownership-flip-flop) | Process | P2 | partial | S03 |
| M42 | [Layers were reported complete before their plan and recrosscheck existed](#process-layers-reported-complete-early) | Process | P2 | no — lesson only | S42 |
| M43 | [The L6 plan put the Atlas check last and drew its units from ledgers; three invented units were retracted and two live d](#process-atlas-check-last) | Process | P2 | no — lesson only | S42 |
| M44 | [Findings were drawn from one module or a narrow regex: F17, six context/ retractions, a 77-table 'retention hole', '645 ](#process-findings-from-narrow-measurements) | Process | P2 | no — lesson only | S42 |
| M45 | [Guards and mutation runs that could not fail: no clean baseline, stale .pyc mutants, four guards failing their own mutat](#process-guards-that-could-not-fail) | Process | P2 | no — lesson only | S42 |
| M46 | [Production guards per package were counted with the hand-written Receipt.layer label, and STEP-10's headline was wrong i](#process-receipt-label-miscount) | Process | P2 | partial | S42 |
| M47 | [Defects were filed twice under new numbers (F80=F71, F136=F67, F146=F46, and a unit that duplicated receipt 44)](#process-duplicate-findings-minted) | Process | P2 | no — lesson only | S42 |
| M48 | [Harsh's deploy notes contained instructions that would fail or that were stale](#process-runbook-told-harsh-wrong-things) | Process | P2 | no — lesson only | S42 |
| M49 | [The golden set's window (4 Aug-5 Oct) left out the benchmark's best findings, STEP-05 was built before the agreed cases ](#process-golden-window-missed-benchmark) | Process | P2 | no — lesson only | S42 |
| M50 | [Three background agents produced nothing across a context compaction and were about to be reported as 'still running'](#process-background-agents-vanished) | Process | P2 | no — lesson only | S42 |
| M51 | [Workers spawned with isolation: worktree started from origin/main, 826 commits behind, and one stopped with nothing buil](#process-worker-worktree-wrong-base) | Process | P2 | no — lesson only | S42 |
| M52 | [A no-op git stash followed by pop applied an old parked stash (five conflicted files) into the working tree](#process-stash-pop-applied-old-stash) | Process | P2 | no — lesson only | S42 |
| M53 | [Rohit was asked questions the data or the code already answered](#process-asked-what-the-data-answered) | Process | P2 | no — lesson only | S42 |
| M54 | [Explaining the system with Atlas/package layer digits made Rohit believe the work was on the old architecture](#process-old-vocabulary-confused-rohit) | Process | P2 | no — lesson only | S42 |
| M55 | ['Turn the LLM decider off and let the formula decide' (W4) was proposed against Rohit's product direction](#process-proposed-formula-decides) | Process | P2 | no — lesson only | S42 |
| M56 | [A finished deliverable was handed back with decisions D1-D8 and 'who fixes the red CI' as homework for Rohit](#process-extra-asks-after-deliverable) | Process | P2 | no — lesson only | S42 |
| M57 | [Two read-only Layer 2 audits were launched right after L1 was pushed, without Rohit opening L2](#process-started-layer-unasked) | Process | P2 | no — lesson only | S42 |
| M58 | [A memory note says dashboard origin/main contains rohit/desktop-ux; it does not](#process-memory-says-desktop-ux-on-main) | Process | P2 | broken | S41 |
| M59 | [YC-II W27 status files still read 'TO BUILD' and 'PENDING deploy' after the work was built and deployed](#process-yc2w27-status-files-stale) | Process | P2 | broken | S41 |
| M60 | [Migration number 0250 was reserved by two plans and then taken by a third change](#process-migration-0250-booked-three-times) | Process | P2 | partial | S20 |
| M61 | [Docs were rsynced into the main checkout as untracked copies, and VS Code showed 67 pending files](#process-rsync-copies-67-files) | Process | P2 | no — lesson only | S41 |

<a id="goals-no-unit-proposes-goals-from-context"></a>
### M01 · The goal plan's only inferred-goal source is the weekly brief drafter, which reads patterns; no unit proposes a goal from the graph's situations

`goals-no-unit-proposes-goals-from-context` · Goals · **P0** · missing · step S26

- **What should have happened:** Goals are not typed by hand again and again. GeniOS proposes goals from what is in motion, as 'proposed' lines a human approves. Example: the Antler Singapore admission (Theresa, an Antler partner), whose context is already in the graph.
- **What happened:** D7 relies on 'the brief drafter already proposes' as the way in. reason/brief_drafter reads reason/brief_patterns (at most the 40 most recent thread objectives in 180 days), never situations (F3). STEP-G1:44 mentions 'or later L2's' proposals, but no STEP-G unit builds one. GeniOS-009 is plan only; G1-G9 are not built.
- **Root cause:** Plan gap: goal-from-context was left to an existing path that cannot see the graph. Goals, the source document's main ask, were planned after the card engine had shipped.
- **What it cost:** No card carries a goal. The Antler admission never became a goal. Rohit has to type goals by hand.
- **The rule that prevents it:** Add a G1 unit: L2 (R-9), or a dedicated pass, proposes goals lines from admitted situations and workstreams, with their evidence ids, as 'proposed' brief lines for one-click approval. Add a golden case where an admission mail produces a proposed goal.
- **Evidence:** `speedrun008/GeniOS-009/08-DECISIONS.md:16`; `speedrun008/GeniOS-009/STEP-G1-the-goal-object.md:44 ('the drafter's, or later L2's')`; `F3 (reason/brief_drafter.py, reason/brief_patterns.py)`; `memory/prod-card-engine-swapped-18-oct.md ('Later L2's proposal has no unit. That is a plan gap')`
- **Verified:** confirmed by the skeptic (08-DECISIONS.md:16 (D7: 'the brief drafter already proposes'). STEP-G1:44 '(the drafter's, or later L2's)'. grep 'propos' over STEP-G0..G9, 02-PLAN and 07-LOOPS finds no unit that proposes goals from situations or the graph. reason/brief_drafter.py imports only reason/brief_patterns (WINDOW_DAYS=180, MAX_THREADS=40, brief_patterns.py:37-44); it has no situation input.)

<a id="process-built-on-the-old-flow"></a>
### M02 · YC-II W27 spent ~20 days (5-17 Oct) patching the old flow while Design Atlas v2 was already the target

`process-built-on-the-old-flow` · Process · **P0** · partial · step S25

- **What should have happened:** From 29 Sep the target is Design Atlas v2. L1 outputs the bundle. L2 (packs + reason) is primary and reads an L3 snapshot. L3 admits. The old flow (context/ forms the situation, then reason, then a signals row, then a card) is what we migrate away from. Every item is judged against the new architecture, never against today's code.
- **What happened:** STEP-00..16 were built on the old flow: situations still form in context/, the R-7 expert reviews per file in reason/expert, and cards come from signals. On 17 Oct six L1 items were retracted or moved 'because today's code does them in context/', and the order was written as L1 -> L3 -> L2. On 18 Oct Rohit was furious that 20 days of work had patched the old flow. That engine is what production received on 18 Oct (c501eec9). The Atlas-v2 L2 judgment (reason/l2, R-9) exists only beside it, behind l2_reasoning and l2_cards, both default off (F4).
- **Root cause:** Built on the old flow. Each step was checked against today's code rather than the Atlas. The 29 Sep architecture change did not become an enforced rule until 18 Oct.
- **What it cost:** Two engines can decide the same file, depending on per-tenant switches: the old-flow R-7 expert and the new R-9 L2. That is the shape Rohit describes as 'L2 and L3 keep failing each other'. About two weeks of work now has to be migrated instead of shipped.
- **The rule that prevents it:** Enforce 01-RULES Rule 1 in CI with the situation-writer ratchet and the card guard. Finish the L2 cutover one situation type at a time, each switch backed by a real-model comparison. Never judge an item against today's code.
- **Evidence:** `memory/genios-008-is-the-programme.md ('Rohit was furious that 20 days of work patched the old flow')`; `memory/judge-against-atlas-v2-not-todays-flow.md (17 Oct retractions of six L1 items)`; speedrun008/GeniOS-008/layer-1-enterprise-signals/03-LOG.md:14 (correction: judged against today's code, which runs the OLD flow); `git c501eec9 message: 'Merge speedrun008 (125c90c2) into harsh/mvp — YC-II W27 STEP-00..16 + GeniOS-008 Layer 1'`; `genios_engine/platform/l4_activation.py:117,122 (l2_reasoning, l2_cards features)`
- **Verified:** confirmed with a correction by the skeptic: Production did not receive this engine on 18 Oct. c501eec9 was only merged locally that day. Harsh's 480f7cd4 (19 Oct 23:03 IST) says 'Prod (10 Oct code) has no change gate'. The public Actions API shows no harsh/mvp push between 84f00a40 (11 Oct) and 21b7ae10 (21 Oct 16:20 UTC), and no run at all for head_sha c501eec9. The engine reached origin/harsh/mvp on 21 Oct at the earliest.

<a id="process-823-commit-big-bang-deploy"></a>
### M03 · 823 commits reached production in one merge on 18 Oct, with no production number per step

`process-823-commit-big-bang-deploy` · Process · **P0** · partial · step S01

- **What should have happened:** A step is pushed and deployed, and is renamed -DONE- only after its production number moves. GeniOS-008 Rule 2: the new path goes beside the old, never instead of it; one situation type is switched at a time, each with a one-line way back.
- **What happened:** D10 batched the push ('you push the whole batch at once, later'). Merge c501eec9 brought 823 commits into harsh/mvp in one go. Before it, production had no reason/expert/review.py and no contracts/claim_check.py (F1). One deploy changed all of these at once: the gate (archive instead of drop), the change gate, who-is-us, memory for every kept item, the brief, workstreams, the expert pass, the claim check, and the gold-shape card builder, which re-drafts every open card once. YC-II W27/00-START-HERE.md still says 'Status as of 2026-10-12', and no step records a production number.
- **Root cause:** Process: a batched push turned into a big-bang deploy. With no production measurement between steps, cause and effect cannot be separated.
- **What it cost:** Right after 18 Oct Rohit saw fewer and 'weird' cards, and no one can say which of roughly 15 behaviour changes caused it.
- **The rule that prevents it:** Deploy per step or per switch. Read a one-day production number before the next one, and record it in the step file.
- **Evidence:** `git rev-list --count c501eec9^1..c501eec9^2 = 823`; `speedrun008/YC-II W27/06-DECISIONS.md:17 (D10: the push is batched)`; speedrun008/YC-II W27/08-FOR-HARSH-deploy-and-after.md:235-250 (§0.3: the first pass is heavy; STEP-14 re-drafts every open card once); `speedrun008/YC-II W27/00-START-HERE.md:3 (status as of 2026-10-12)`; `memory/prod-card-engine-swapped-18-oct.md`
- **Verified:** confirmed with a correction by the skeptic: The batch was larger and later than stated. The merge was made locally on 18 Oct, but 480f7cd4 shows prod still ran 10 Oct code on 19 Oct. origin/harsh/mvp went from 84f00a40 to 21b7ae10 in ONE push on 21 Oct 16:20 UTC. That push was 869 commits (git rev-list --count 84f00a40..21b7ae10): the 823 plus all 27 of Harsh's L1/L2/L3 rebuild and audit commits. Its CI run (the only one between 12 and 21 Oct) failed. Whether Harsh deployed from his laptop before pushing is not in the repo; only deploy logs can answer.

<a id="process-no-production-number-after-deploy"></a>
### M04 · No one measured production after the 18 Oct deploy: switch state, card counts and expert outcomes are unknown

`process-no-production-number-after-deploy` · Process · **P0** · unknown until production is read · step S01

- **What should have happened:** The switches are applied in order, for Rohit's org only. expert_review is switched on only after Rohit's yes on a live golden pass (D50). The next day, pipeline_health --require-data and the thinking probe are run and read.
- **What happened:** Production reads need Rohit's permission (F6). Nothing in the repo records the post-deploy health output, the l4_activation rows, or the R-7/R-9 outcomes. expert_review's precondition was never met: the Sonnet live pass truncated 203 of 203 calls, and the D72 comparison is still 'Open — Rohit's call'. So it is unknown whether Rohit's cards come from the old decider/compiled lane, the R-7 expert, or the L2 path.
- **Root cause:** Planned without measuring production. The 23-step runbook asks no one to write the results back into the repo.
- **What it cost:** Until these numbers exist, every explanation of 'fewer or weird cards' is a guess.
- **The rule that prevents it:** Rohit runs or permits the read-only SQL and the answers go into a dated log line. Keep a daily production health number (the pipeline_health JSON) as a standing artifact.
- **Evidence:** `speedrun008/YC-II W27/06-DECISIONS.md:79 (D72 open)`; `speedrun008/YC-II W27/03-FINDINGS.md:288 (F267: no Sonnet review was ever checked)`; `memory/prod-card-engine-swapped-18-oct.md ('Not yet measured on prod')`; `memory/production-reads-need-permission.md`
- **Verified:** confirmed with a correction by the skeptic: The '18 Oct deploy' premise is wrong. Per 480f7cd4, prod was on 10 Oct code on 19 Oct, and the merge first reached origin in the 21 Oct 16:20 UTC push. The deploy date itself is unknown and needs Harsh's deploy log. Switch state still needs Rohit's read-only SQL: select org_id, feature, enabled_at, disabled_at from l4_activation order by org_id, feature.

<a id="process-verified-with-the-ideal-reader-only"></a>
### M05 · Every gate, board and switch rule was proven with the ideal reader; the real model was measured once, and the claim check held 79% of its reviews

`process-verified-with-the-ideal-reader-only` · Process · **P0** · missing · step S07

- **What should have happened:** Each step is judged by whether real cards get more intelligent (Rohit, 6 Oct). A live golden pass runs before the expert reaches Rohit's account (D50). The L1 live pass runs (GeniOS-008 L1 B1/R1). The benchmark is re-run blind as STEP-19 (D17).
- **What happened:** The golden 63/67 score runs on authored answers (F5). The only real-model pass (12 Oct, Haiku 4.5) reached recall 0.235, and the STEP-13 check held 68 of 86 valid reviews. The Sonnet pass measured nothing because thinking used up the token limit. D72 is open. STEP-19 is 'not written yet'. No live scorecard is committed: speedrun008/YC-II W27/scores does not exist. GeniOS-008 Rule 2.3 makes the ideal-reader board the switch rule for the new path as well.
- **Root cause:** Verified with the ideal reader only. The golden set proves the plumbing, and its passes were read as proof of intelligence.
- **What it cost:** If expert_review is on in production, a check tuned on authored answers holds most real-model reviews: files end held or as question cards, which means fewer cards and odd wording. If it is off, the old decider path runs and no golden number describes it.
- **The rule that prevents it:** Before any switch or production push, run one real-model golden pass on the deployed models and settings: R-7 on Sonnet 5 with thinking off at 6,000 tokens, R-9, and the L1 gate. Commit the scorecard. Make the real-model board the switch rule. Write STEP-19.
- **Evidence:** `speedrun008/YC-II W27/03-FINDINGS.md:287 (F266), :288 (F267)`; `speedrun008/YC-II W27/06-DECISIONS.md:24 (D17 'not written yet'), :79 (D72 open)`; `speedrun008/GeniOS-008/01-RULES.md:25 (a switch happens when the new path scores at least as well on the board)`; `ls 'speedrun008/YC-II W27/scores' -> No such file or directory`; `memory/haiku-live-pass-held-79-percent.md`
- **Verified:** confirmed by the skeptic (F266 (03:287): Haiku recall 0.235; 92 reviews, 86 valid, 68 held. It also says the scorecard is not committed ('neither is committed'). F267 (03:288): the Sonnet pass checked no review. D17 says 'not written yet' (06:24); D72 is open (06:79). 01-RULES.md:25 is Rule 2.3 (switch when the golden board scores at least as well). 'speedrun008/YC-II W27/scores' does not exist, and no STEP-19 file exists. L1 02-PLAN:26 (B1) still waits on Rohit's key.)

<a id="l1-junk-gate-prompt-shipped-on-ideal-reader"></a>
### M06 · The L1 junk-gate prompt was rewritten and shipped to production on ideal-reader recordings, skipping the live pass its plan required

`l1-junk-gate-prompt-shipped-on-ideal-reader` · L1 · **P1** · partial · step S07

- **What should have happened:** E9 and B2 ship together with the live key (R1). B1 runs the L1 model sites on the real model, because 'production junked real investor mail'. D29: the filter's archive does not change until a live run measures it.
- **What happened:** 0d5939d1 (Harsh, 19 Oct) fenced the gate prompt and stopped dropping matchmaking and plan notices. Its message says '24 gate answers re-authored … every cassette re-recorded with the ideal reader (no spend)'. No live L1 pass exists, and 02-PLAN.md:96 still marks E9 as 'audited, not fixed'.
- **Root cause:** Verified with the ideal reader only: the plan's R1 gate was skipped and the plan's status was left stale.
- **What it cost:** What the real model now keeps or junks from Rohit's inbox (investor, intro and programme mail) is unmeasured. This is the stage that starved the graph on 4 Oct (27 of about 470 mails reached L2).
- **The rule that prevents it:** Run the L1 live pass (junk_gate_batch, relevance, extraction) on the deployed prompt and commit its scorecard. Correct the E9/B2 status in 02-PLAN.
- **Evidence:** `git 0d5939d1 message`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/02-PLAN.md:26, :51, :96`; `memory/l1-audit-2026-10-17.md (the gate prompt change waits on a live run and Rohit's yes)`
- **Verified:** confirmed by the skeptic (0d5939d1 (Harsh, 19 Oct): '24 gate answers re-authored … every cassette re-recorded with the ideal reader (no spend)'. The fence is in code (capture/gate/relevance.py:9, 298-300, 347). L1 02-PLAN:26 (B1 live pass waits on Rohit's key), :51 (R1) and :96 (E9 'audited, not fixed') are not updated. No scores/ directory and no live L1 scorecard exist.)

<a id="l1-deleted-mail-needs-resync"></a>
### M07 · The old gate deleted mail content (258 S1 drops). The fix shipped, but the re-sync that brings that mail back is a manual step in an unknown state

`l1-deleted-mail-needs-resync` · L1 · **P1** · unknown until production is read · step S09

- **What should have happened:** STEP-03: the gate never deletes. STEP-08: the mail the old gate deleted comes back, after the brief, with a window of D5 = 365 days.
- **What happened:** Measured on 5 Oct: 258 S1-dropped mails had neither prepared_content nor raw_payloads (DPIIT, Boardy intros, SINE, Sankalp, incubators). STEP-03/08 code has been in production since c501eec9, but the re-sync is five manual sub-steps. It waits on the brief being accepted (D26) and on Rohit naming the window (D5/D16).
- **Root cause:** A design deleted content at L1. The fix only covers mail going forward; the backfill depends on a manual ceremony no one confirmed.
- **What it cost:** Investor, intro and programme mail from before 3 Oct may still be missing from memory, so its situations, goals and cards cannot exist.
- **The rule that prevents it:** Harsh runs 08 §3.7 (dry run, Rohit names the window, then apply) and records the counts in the log.
- **Evidence:** `memory/founder-workstreams-lost-2026-10-05.md`; `speedrun008/YC-II W27/08-FOR-HARSH-deploy-and-after.md:252-268 (§0.4 step 16)`
- **Verified:** confirmed with a correction by the skeptic: 'In production since c501eec9' (18 Oct) is not supported: per 480f7cd4, prod was on 10 Oct code on 19 Oct, and the merge first reached origin on 21 Oct 16:20 UTC. To see whether the re-sync ran, Harsh's run log or a read-only count of re-fetched events is needed.

<a id="l2-founder-playbooks-gated-on-unread-review"></a>
### M08 · The investor and programme playbooks were gated on a 267-line YAML review that was never done, and the Sales investor copy was retired

`l2-founder-playbooks-gated-on-unread-review` · L2 · **P1** · built, not live · step S23

- **What should have happened:** A fundraising founder's main workstreams (investors, accelerators such as Antler) get expert cards from the Founder Office corpus, switched on for Rohit's org.
- **What happened:** D45 admits a playbook only after Rohit accepts every line. review/investor.review.yaml has 146 lines and review/program.review.yaml has 121, and every one has decision: ''. domain_shadow.py says that until the founder's review a fundraising situation on the pilot is refused as 'unreviewed'. Sales' investor relations were retired. On 22 Oct Rohit removed Founder Office from the dashboard, and goals/live.ts folds founder_office into Admin.
- **Root cause:** A plan gate put a 267-line review on the founder before his most valuable cards could exist, and the plan never flagged it as blocking.
- **What it cost:** On the compiled lane every investor or programme situation ends 'unreviewed' and gets no card, unless the R-7 expert covers the file. That includes the kind of situation the Antler admission is.
- **The rule that prevents it:** Rohit decides between two options: review only the lines a card prints, or admit on use with per-card feedback. Until then, the dashboard says fundraising is waiting for his review.
- **Evidence:** `speedrun008/YC-II W27/review/investor.review.yaml (146 lines with decision: '')`; `speedrun008/YC-II W27/review/program.review.yaml (121 lines with decision: '')`; `speedrun008/YC-II W27/06-DECISIONS.md:52 (D45 'Waiting for your review')`; `genios_engine/reason/domain_shadow.py:918-927, :1011-1013`; `dashboard origin/main src/product/internal/dashboard/goals/live.ts:25`
- **Verified:** confirmed by the skeptic (investor.review.yaml has 146 entries and program.review.yaml has 121, each with decision: '' (the files are 1,374 and 1,201 text lines). D45 at 06:52 says 'Waiting for your review'. domain_shadow.py:915-925 retires the Sales copy and refuses fundraising as 'unreviewed'. All 36 Founder Office Expertise documents are status: draft with reviewed_by: ''. Dashboard goals/live.ts:25 FOLDED_INTO_ADMIN includes founder_office.)

<a id="l2-llm-decider-without-fallback-in-production"></a>
### M09 · The LLM decision maker ran in production for every org with no fallback, and a spend limit then stopped all cards from 25 Sep

`l2-llm-decider-without-fallback-in-production` · L2 · **P1** · partial · step S02

- **What should have happened:** A measurement mode is not the production mode. A model outage or a budget stop degrades output; it does not silence it (DECISION #5, option C).
- **What happened:** Measured 1 Oct: GENIOS_L4_LLM_DECISION_MAKER=true with no org allowlist, and the Anthropic spend limit refusing every call since 25 Sep 11:09 UTC. llm_decision_maker.py:20 says 'Failure is DEFER, never the formula', giving 2,669 defers, 0 decisions and 0 signals. Two confident guesses were wrong before the stages were measured. The code default is now off (config.py:110), but the production env value is not recorded, and B9's 400-a-day cap has never bound because the count lives in one process (F274).
- **Root cause:** Shipped the measurement mode as the production mode, and guessed the cause twice before measuring which stage had stopped.
- **What it cost:** No cards from 25 Sep to about 3 Oct; after that, flip-flopping defers and about 3,600 model calls a day for 6 cards.
- **The rule that prevents it:** Harsh states the production env value. Rohit picks the cap and the dollar governor default (F274). 'Which stage stopped' stays the first diagnostic step.
- **Evidence:** `memory/why-no-cards-since-25-sep.md; memory/measure-which-things-stopped.md`; `genios_engine/reason/llm_decision_maker.py:20`; `genios_engine/platform/config.py:110-111`; `speedrun008/YC-II W27/03-FINDINGS.md:295 (F274 open)`; `memory/production-funnel-2026-10-04.md (57% DEFER, about 3,600 calls a day for 6 cards)`
- **Verified:** confirmed by the skeptic (llm_decision_maker.py:20 says 'Failure is DEFER, never the formula'. config.py:110 l4_llm_decision_maker defaults to False, and :111 orgs is empty (empty = every org when on). _take_budget keeps the 400 cap in the in-process _calls_by_org_day (llm_decision_maker.py:216-228). F274 is open (03:295). Memory why-no-cards (2,669 defers, 0 decisions) and production-funnel (57% DEFER, ~3,600 calls a day). The production env value is not in the repo.)

<a id="l3-signal-type-observation-quotes-a-name"></a>
### M10 · Signal-type observations take the extraction's first span as their 'quote', often a bare name, and cards narrate it as something said

`l3-signal-type-observation-quotes-a-name` · L3 · **P1** · broken · step S16

- **What should have happened:** A marker is not a quote: a status marker carries no evidence span. This rule was applied to the below-floor mark (C3.U06).
- **What happened:** context/qes_adapter.py:146-148 gives every signal-type observation evidence_text = the first span of all the evidence. deliver/card_builder._QUOTES_SQL (:374) reads every observation kind's evidence as a quote. 03-FINDINGS F72 and F46 are still open. On golden F25 the narrator is handed '[received:approval_requested] the account holder wrote: Kavitha' three times, and F51's card says only 'Reply to Sana'.
- **Root cause:** A rule applied only to the instance that produced it: the below-floor mark was removed, but its sibling stayed.
- **What it cost:** Narrated cards quote a person's name as the evidence and cannot name the date or the ask, so they read as 'weird'.
- **The rule that prevents it:** Give signal-type observations no evidence span, or the span of the signal's own evidence. Add a golden check that no quote equals a bare name.
- **Evidence:** `genios_engine/context/qes_adapter.py:146-148`; `genios_engine/deliver/card_builder.py:374`; `speedrun008/YC-II W27/03-FINDINGS.md:67 (F46 'not fixed'), :93 (F72 'open')`
- **Verified:** confirmed by the skeptic (qes_adapter.py:146-148: default_quote = _span_quote(result.all_evidence), stamped on every signal_types observation. card_builder.py:374 _QUOTES_SQL excludes only email_noise% and event_presence (:410-411), so every other kind is read as a quote. 03 F46 (:67) is still 'not fixed', F72 (:93) still 'open', and F146 (:167) is corrected to F46 ('Reply to Sana').)

<a id="goals-architecture-defines-no-goal-object"></a>
### M11 · GeniOS-008's architecture names the goal loop but defines no goal object, so the rebuilds and every card contract carry none

`goals-architecture-defines-no-goal-object` · Goals · **P1** · missing · step S26

- **What should have happened:** The architecture's purpose: GeniOS 'monitors progress; and adapts until the goal is reached'. That needs a goal object, and a goal impact on each judgment and card.
- **What happened:** 'goal' and 'objective' appear only at 00-ARCHITECTURE.md:9-10. grep -i goal finds nothing in contracts/reasoning_result.py or contracts/expert_review.py, and 0 hits in reason/l2/prompt.py and reason/l2/dossier.py. Goals reach the model only inside the brief text (block D), or the dossier says 'No company brief is accepted for this tenant' (reason/l2/dossier.py:170). The cards table has no goal column (F3). The dashboard hard-codes 'Not linked to a goal yet'.
- **Root cause:** Plan gap: the target architecture was written without the object its own opening sentence depends on. Rule 1.3 (every item cites 00-ARCHITECTURE) then left goal work nothing to cite during the L1-L3 rebuilds.
- **What it cost:** Cards cannot say which goal they move; the UI shows a hard-coded placeholder.
- **The rule that prevents it:** Add the goal object and goal impact to 00-ARCHITECTURE and to ReasoningResult before G3/G6 are built. Rule 1.4 requires Rohit's yes for the architecture change.
- **Evidence:** `speedrun008/GeniOS-008/00-ARCHITECTURE.md:9-10`; `genios_engine/reason/l2/dossier.py:170`; `genios_engine/contracts/company_brief.py:37-38 (goals is only a brief section)`; `dashboard origin/main src/app/dashboard/cards/page.tsx:925; src/product/internal/dashboard/intel/parts.tsx:215`
- **Verified:** confirmed by the skeptic (grep -i 'goal|objective' in 00-ARCHITECTURE.md matches only lines 9-10. 0 'goal' hits in contracts/reasoning_result.py, contracts/expert_review.py, reason/l2/prompt.py and reason/l2/dossier.py. dossier.py:170 holds the 'No company brief is accepted' fallback. company_brief.py:37-38 has goals only as a SECTION. On the dashboard (origin/main 2edfb86), cards/page.tsx:925 and intel/parts.tsx:215 both hard-code 'Not linked to a goal yet'.)

<a id="goals-golden-brief-is-pre-curated"></a>
### M12 · The golden tenant ships a hand-curated brief (5 accepted goals, 20 in-motion lines), so no test sees a tenant whose brief was never accepted

`goals-golden-brief-is-pre-curated` · Goals · **P1** · missing · step S27

- **What should have happened:** Tests mirror production. A tenant's brief holds only what the drafter proposed and the founder accepted (08 §3.6, step 15), and an empty or unaccepted brief is the normal case.
- **What happened:** tests/replays/specs/founder/brief/company_brief.json is seeded into every golden tenant. GeniOS-009 plans to test goals 'on the existing 67 cases' using that seed. Rohit reports there are no goals and that he has to enter them by hand.
- **Root cause:** An ideal-world fixture: the curated golden brief stands in for a ceremony production may never have completed.
- **What it cost:** Goals and in-motion lines look complete in tests, while production's brief may be empty and the L2 dossier says 'No company brief is accepted'.
- **The rule that prevents it:** Add golden cases with no accepted brief and with only drafter proposals. Measure the production brief before G1 is built.
- **Evidence:** `speedrun008/GeniOS-009/03-LOG.md:12 (the golden brief already holds 5 accepted goals), :14 (20 in-motion lines)`; `memory/yc2-w27-plan-folder.md (STEP-07: brief seeded by _fresh_tenant)`; `F2`
- **Verified:** confirmed with a correction by the skeptic: The claim is too broad. Unit tests do cover an unaccepted or empty brief (for example tests/test_every_prompt_carries_the_company_brief.py, and the dossier fallbacks reason/l2/dossier.py:170 and reason/expert/dossier.py:221). What is true is that the golden quality board (all 67 cases) never runs without the curated, fully accepted brief.

<a id="surfaces-ui-hides-repeated-brain-text"></a>
### M13 · The Cards page hides text that repeats across cards instead of fixing why the brain repeats it

`surfaces-ui-hides-repeated-brain-text` · Surfaces · **P1** · partial · step S34

- **What should have happened:** Rohit's card contract (22 Oct): 'every card's details and scenario must be its own', enforced at the source (L5 deliver/card_builder).
- **What happened:** Rohit saw the identical 'Why' on every card. The likely cause (person-level context.interactions and commitments from a hub node) is 'not verified on prod'. The dashboard drops shared text on the client instead. The Mac app shows the same repetition ('70 days since they wrote').
- **Root cause:** Fixed the symptom in the UI and never traced the root cause in L5.
- **What it cost:** Cards can lose legitimate shared facts, and the brain still sends duplicate context to the Mac app and the API.
- **The rule that prevents it:** Trace the Why lines in deliver/card_builder and make them card-specific. Keep the UI filter only as a guard.
- **Evidence:** `dashboard origin/main src/app/dashboard/cards/page.tsx:346-351 (sharedLines, sharedTexts, ownCard)`; `memory/cards-ux-analysis-22-oct.md`; `memory/desktop-accessibility-and-adhoc-builds.md ('card one-liners repeating')`
- **Verified:** confirmed by the skeptic (Dashboard origin/main cards/page.tsx:345-353: sharedLines, sharedTexts and ownCard drop text repeated across cards on the client. Memory cards-ux-analysis:62 says the identical Why's cause is 'Not verified on prod'. desktop-accessibility memory: 'card one-liners repeating ("70 days since they wrote")'. No brain-side uniqueness check was found in deliver/card_builder.)

<a id="cross-l2-l3-rebuild-shipped-before-its-audit"></a>
### M14 · The L2/L3 rebuild reached production before its audit, and the audit then found silent failures that match Rohit's symptoms

`cross-l2-l3-rebuild-shipped-before-its-audit` · Cross-layer · **P1** · done (lesson only) · step S01

- **What should have happened:** Build, then crosscheck or audit, then ship. A new path stays in shadow until it has been compared.
- **What happened:** The L2 rebuild landed on 19 Oct (e5eee70e…0222ba81) and the L3 rebuild on 20 Oct (df3c2aa8…f3cfd3c6). The 21 Oct audits then fixed: 7297b31a 'a failed [L3] pass is said in the sweep's return, not read as nothing to do'; b8a8a43c 'one oversized prompt no longer stops the [L2] pass'; 8cfe15a6 'no event leaves memory for good'. All were on the production branch, and CI was red that day.
- **Root cause:** Shipped before the audit, so silent-failure shapes (a failure read as 'nothing to do') reached production.
- **What it cost:** From about 19 to 21 Oct an L3 pass could fail silently (no correlation), and one oversized prompt could stop the L2 pass (no reasoning). Whether the L2 pass ran for Rohit's org depends on l2_reasoning, which is not measured.
- **The rule that prevents it:** Audit before merging to harsh/mvp. Every pass returns a named failure, never an empty result.
- **Evidence:** `git log c501eec9..21b7ae10 (dates 19-21 Oct, author Harsh Tripathi)`; `git 7297b31a, b8a8a43c, 8cfe15a6 messages`
- **Verified:** confirmed with a correction by the skeptic: On origin the rebuild did not reach the production branch before its audit. origin/harsh/mvp received the rebuild and the audit fixes in the same push (84f00a40 → 21b7ae10, 21 Oct 16:20 UTC, CI red), after the audit commits were made. 7cab0ad4 says 'Local only — ships with the rest when the owner pushes', and 480f7cd4 says prod was on 10 Oct code on 19 Oct. Whether Harsh deployed his local branch to prod on 20-21 Oct before the audit needs his deploy log.

<a id="cross-db-tier-never-budgeted"></a>
### M15 · No plan budgeted the 500 MB database tier, and production reached 999 MB before a purge was added

`cross-db-tier-never-budgeted` · Cross-layer · **P1** · partial · step S05

- **What should have happened:** A measured write budget per sweep: an unchanged sweep writes nothing (DATABASE_LOAD_ANALYSIS, 17 Oct).
- **What happened:** 7cab0ad4 (19 Oct): 'Measured on prod 19 Oct: ~1,270 reasoning runs a day at ~91 KB, 98% never referenced … the database sat at 999 MB of a 500 MB tier (owner-run purge + VACUUM took it to 446 MB)'. 480f7cd4 then made an unchanged sweep write no audit row.
- **Root cause:** Planned without measuring production capacity: the write churn was found only when the tier overflowed.
- **What it cost:** An over-quota database risks refused writes, and refused writes stop cards. Whether writes failed between deploys is not recorded.
- **The rule that prevents it:** Add a daily database-size line with a ceiling to the health check, and count writes per sweep in the golden run.
- **Evidence:** `git 7cab0ad4 message`; `git 480f7cd4 message`; `memory/five-migrations-unapplied.md (a read-only DB means a degraded boot in which every write fails)`
- **Verified:** confirmed with a correction by the skeptic: The tier was not an unknown that surprised everyone on 19 Oct. Harsh's 9a51d0ea (2 Oct) had already measured expertise_packages at 460 MB taking the DB 'past its 0.5 GB quota into read-only'. A read-only DB crash-loops every deploy, which is why c7cdf4c rolled back. So 19 Oct was the second breach in 17 days, still with no write budget. The cited 'DATABASE_LOAD_ANALYSIS, 17 Oct' is not in the repo.

<a id="process-red-ci-reached-production"></a>
### M16 · Code reached the production branch while CI was red (4, 9, 11, 21 Oct), and 199 golden failures were accepted as 'pre-existing'

`process-red-ci-reached-production` · Process · **P1** · partial · step S03

- **What should have happened:** All three CI jobs (hermetic, database, golden-pg) are green before code reaches harsh/mvp. A skip is not a pass. A verify is never weakened.
- **What happened:** CI on harsh/mvp failed on 4, 9, 11 and 21 Oct and was first green at 0cc8d83c on 22 Oct (F1). Harsh's 1925a5bb says 'golden replays: identical failure set to the clean merge (199, all pre-existing)'. The 21 Oct red had three causes, all from the rebuild. (1) Cassettes were re-recorded on a laptop Postgres set to IST. (2) ae5b5c7a made derived facts keep their first instant, which exposed fingerprint._relative: unchanged subjects were re-decided (F13/F29). (3) A correlated subquery ran 40,804 times and timed out the ladder. The same pattern on speedrun008: L1 A3/C3 were pushed with the golden board run unread (layer-1 03-LOG:13), ae24ee22 was pushed and then went red, and 33c6fb1f went red on Python 3.11.
- **Root cause:** Pushed with red CI and treated a red golden run as the baseline. The laptop (IST) did not match CI and production (UTC).
- **What it cost:** From about 20 to 22 Oct, production re-decided subjects on unchanged sweeps: card churn and extra model spend, a regression golden-pg had already caught.
- **The rule that prevents it:** Branch protection on harsh/mvp: all three CI jobs must be green to merge. Record cassettes only in UTC (now forced by platform/db, 3d5a6a3d). Never call a failure set 'pre-existing' without attributing each failure.
- **Evidence:** `speedrun008/GeniOS-009/03-LOG.md:7 (21b7ae10 red: golden-pg 10, database 9), :15 (G0.1: the three causes)`; `git 1925a5bb message ('199, all pre-existing')`; `git ae5b5c7a, fixes 3d5a6a3d, 8d1de446, 269400dc`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/03-LOG.md:13`; `memory/local-qa-runs-python-313-ci-runs-311.md; memory/step13-state-2026-10-12.md`
- **Verified:** confirmed with a correction by the skeptic: Red CI was the norm, not four dates. The public Actions API shows every harsh/mvp push from 6 Sep (05f73d84) to 21 Oct (21b7ae10) concluded 'failure': more than 60 runs, including 30 between 15 Sep and 21 Oct. The last green before that was 2 Sep (c1dd89b3), and the first green after it was 0cc8d83c on 22 Oct.

<a id="process-rebuild-without-layer-docs"></a>
### M17 · Harsh's L1/L2/L3 rebuilds have no GeniOS-008 layer log, L3 has no folder, and the L1 rebuild plan lives outside the repo

`process-rebuild-without-layer-docs` · Process · **P1** · missing · step S41

- **What should have happened:** Rohit opens each layer. Each layer folder holds 00-START-HERE, 01-AS-IS, 02-PLAN, 03-LOG and 04-FOR-HARSH. The log is append-only, and Harsh's note is written with the code.
- **What happened:** speedrun008/GeniOS-008 holds only layer-1 and layer-2 folders. Layer-2 03-LOG.md ends on 18 Oct (line 12), although more than 20 L2 rebuild and audit commits followed on 19-21 Oct. The L3 rebuild and audit (df3c2aa8…21b7ae10) have no folder at all. 1925a5bb cites 'docs/plans/L1_REBUILD_PLAN.md (workspace)', and docs/plans/ has no such file. Layer-1 03-LOG also stops on 18 Oct.
- **Root cause:** Two plans for one layer, with only one in the repo, and the append-only log was not kept.
- **What it cost:** No one can trace which L2/L3 change produced a given card or a missing correlation, and the next session plans against stale layer status.
- **The rule that prevents it:** Backfill layer-2 03-LOG and create a layer-3 folder from the commit messages. Commit L1_REBUILD_PLAN.md. Make the log line part of each commit.
- **Evidence:** `ls speedrun008/GeniOS-008 -> layer-1-enterprise-signals, layer-2-reasoning only`; `speedrun008/GeniOS-008/layer-2-reasoning/03-LOG.md:12 (last line, 2026-10-18)`; `git 1925a5bb message; docs/plans/ listing (no L1_REBUILD_PLAN.md)`
- **Verified:** confirmed with a correction by the skeptic: 'More than 20 L2 rebuild and audit commits' is overstated. Harsh made 27 non-merge commits in c501eec9..21b7ae10, of which 13 are L2 (10 'L2 rebuild', 2 'L2 audit', 1 l2_admission). The rest are 3 L1, 9 L3 (5 rebuild, 4 audit) and 2 DB-purge commits.

<a id="process-green-suite-never-ran-sql"></a>
### M18 · A hermetic suite with 15,494 passing tests hid eight live SQL bugs, because no test ran SQL against Postgres

`process-green-suite-never-ran-sql` · Process · **P1** · done (lesson only) · step S42

- **What should have happened:** Before any SQL path is claimed to work, something has executed it against Postgres.
- **What happened:** The 4 Oct audit found, all under a green suite: calibration raising UndefinedColumn card_level since cd7f85d7 (10 Sep); the closed edge vocabulary (86158415) rolling back every deal, document, assignee and usage event since 25 Sep, parked as 'model unavailable'; 8 of 11 'Wrong because' reasons returning 500 (the 0034 CHECK); human-review learning objects failing with 409; a DEFER closing legacy cards; parked recoveries never reaching L2. Fixed since: graph_store.py:185-190, reason/authority.py:332, migration 0210, and CI's database and golden-pg jobs (STEP-17).
- **Root cause:** A green suite was read as production truth, and tests grepped SQL text instead of running it.
- **What it cost:** Weeks of dropped events, no calibration, and feedback buttons that errored.
- **The rule that prevents it:** Keep CI's database job and the every-statement-plans test.
- **Evidence:** `memory/full-audit-eight-verified-live-bugs.md`; `genios_engine/context/graph_store.py:185-190`; `genios_engine/reason/authority.py:332`; `migrations/0210_every_wrong_reason_is_kept.sql`
- **Verified:** confirmed by the skeptic (Memory full-audit: 15,494 passed. Fixes exist: graph_store.py:185-190 (the four undeclared edge types, found when the DB suite first ran on 5 Oct); reason/authority.py:332 (card_level, cd7f85d7, UndefinedColumn from 10 Sep); migrations/0210_every_wrong_reason_is_kept.sql; ci.yml now has golden-pg (:50) and database (:88) jobs.)

<a id="process-claude5-thinking-ate-the-budget"></a>
### M19 · A $10.4 Sonnet pass measured nothing: Claude 5 thinks by default, the thinking ate max_tokens, and the harness hid the cost

`process-claude5-thinking-ate-the-budget` · Process · **P1** · done (lesson only) · step S42

- **What should have happened:** Before any paid pass: set thinking explicitly, run 1-2 calls, and read stop_reason and output_tokens.
- **What happened:** In the 12 Oct Sonnet 5 pass, all 203 R-7 calls stopped at 4,000 tokens. LLMClient sent no thinking control. CassetteRecorder raised on ok=False, so the gate retried without charging (F268), and the scorecard said $0.35 against roughly $10.4 actually spent (about $12.8 of the $20 budget). The 4 Oct note 'R-2 fails 8 of 12 at 1,400 tokens' had been misread as a sizing problem. Fixed: the client sends thinking controls, and the harness keeps a ledger.
- **Root cause:** A paid pass ran without 1-2 trial calls, and the scorecard was trusted over the provider's real spend.
- **What it cost:** R-2 (Sonnet 5 at 2,400 tokens) was likely truncating in production until the 18 Oct deploy (08 §0d), and $10.4 of the live-pass budget was spent with nothing measured.
- **The rule that prevents it:** Always make 1-2 real calls before a paid pass.
- **Evidence:** `speedrun008/YC-II W27/03-FINDINGS.md:288-290 (F267-F269)`; `genios_engine/context/llm/client.py:44-52, :77, :123 (thinking_kwargs, disabled)`; `tests/replays/harness.py:257-265 (the ledger of every call)`
- **Verified:** confirmed by the skeptic (03 F267-F269 (:288-290): 203/203 calls stopped at 4,000 tokens; the scorecard said $0.3533 against ≈$10.4 spent, ≈$12.8 of $20 in total. Fixed: context/llm/client.py:43-52 (THINKING_OFF/ADAPTIVE) and thinking_kwargs at :123; tests/replays/harness.py:253-275 (CassetteRecorder no longer raises on ok=False and keeps an append-only ledger).)

<a id="process-fan-out-exhausted-the-quota"></a>
### M20 · Wide agent fan-out burned the shared session limit and killed every worker mid-unit

`process-fan-out-exhausted-the-quota` · Process · **P1** · done (lesson only) · step S42

- **What should have happened:** One skeptic per lens, a handful of workers, the critical path first.
- **What happened:** On 12 Oct around 22:30 (6 workers) and 13 Oct around 05:00 (workflows of 24 and 111 agents beside 6 builders) the limit was hit within about 30 minutes, and 95 crosscheck agents errored. It happened again on 13 Oct around 11:30 with 5-6 builders. On top of that, guards ran before every commit against Rohit's per-group rule. Rohit, 13 Oct: 'speed itna kam kyu hai'.
- **Root cause:** Fan-out burned the session limit.
- **What it cost:** Hours of stopped work, and Rohit's trust in the pace.
- **The rule that prevents it:** Cap concurrency and batch skeptics per lens. This applies to this multi-agent run as well.
- **Evidence:** `memory/fan-out-burns-the-session-limit.md`; `memory/speed-is-rohits-top-complaint.md`
- **Verified:** confirmed by the skeptic (Memory fan-out-burns-the-session-limit: 12 Oct ~22:30 with 6 workers; 13 Oct ~04:55 with workflows of 24 + 111 agents, 95 of the crosscheck's agents errored; the third hit on 13 Oct ~11:30 with 5-6 builders. Memory speed-is-rohits-top-complaint: guards ran per commit against the per-group rule, and the description quotes 'speed itna ka…'.)

<a id="process-report-silently-truncated"></a>
### M21 · A crosscheck report silently dropped three of five lenses (8 blocking findings) by cutting its input at 100,000 characters

`process-report-silently-truncated` · Process · **P1** · done (lesson only) · step S42

- **What should have happened:** Nothing is cut from a report's input unless what was cut is logged.
- **What happened:** The STEP-14 crosscheck report said 'two lenses reported'. The other five lenses' worth of input (about 170k characters) had been sliced at 100k. This was caught only by counting findings per lens in journal.jsonl.
- **Root cause:** A silent cap in the instrument.
- **What it cost:** STEP-14 could have shipped with B1 (a refused version loses the file's card) unreported.
- **The rule that prevents it:** Check per-agent counts in the journal against the report's coverage before believing a report.
- **Evidence:** `memory/fan-out-burns-the-session-limit.md`; `memory/step14-close-2026-10-16.md ('first report covered only 2 of 5 lenses — input was capped')`
- **Verified:** confirmed by the skeptic (Memory fan-out-burns-the-session-limit, '16 Oct — a silent cap': the input was sliced at 100,000 chars of ~170k, 3 lenses and 8 blocking findings were dropped, and it was caught via journal.jsonl. Memory step14-close: 'first report covered only 2 of 5 lenses — input was capped'.)

<a id="l1-archive-text-exposed-by-membership"></a>
### M22 · Giving archived mail its text exposed it to every reader that selects by thread membership (F57); only the dossier was made to ask each event's outcome

`l1-archive-text-exposed-by-membership` · L1 · **P2** · partial · step S06

- **What should have happened:** Before storing new content for rows that had none, list every reader and what it selects by.
- **What happened:** Contained: an archive keeps no prepared text (ff4ba758), and the STEP-12 timeline reads words only through kept events. 03 F57: 'The other membership readers named above are unchanged' (lifecycle/store, situation_bso, card_builder, document_register, backfill, org_rule_ingest).
- **Root cause:** Absence was the only guard.
- **What it cost:** If prepared text is ever stored for archives, a card could quote archived mail.
- **The rule that prevents it:** Make the remaining membership readers ask the event's outcome.
- **Evidence:** `speedrun008/YC-II W27/03-FINDINGS.md:78 (F57)`; `memory/absence-was-the-only-guard.md`
- **Verified:** confirmed by the skeptic (03 F57 (:78): contained in STEP-03 by ff4ba758 (6 Oct: 'an archive keeps its encrypted payload and no prepared text'). The tail reads 'the dossier (M32.C2.L-logic.V1.U04) reads words through the timeline alone. The other membership readers named above are unchanged'.)

<a id="l2-corpus-counted-as-files"></a>
### M23 · A plan was built on a corpus count of files ('534 capabilities, 37% admissible'); the real number was 155 capabilities, 100% admissible

`l2-corpus-counted-as-files` · L2 · **P2** · done (lesson only) · step S42

- **What should have happened:** Count the corpus with the compiler's own admission rules.
- **What happened:** '211/156/167' counted files. A capability is a directory of three documents. The 'cutover flag' was free.
- **Root cause:** Measured with find instead of the system's own rule.
- **The rule that prevents it:** Use the corpus report.
- **Evidence:** `memory/l3-corpus-is-not-empty.md (scripts/l2_refusal_report.py --corpus-only, pinned by a test)`
- **Verified:** confirmed by the skeptic (Memory l3-corpus-is-not-empty: '534 capabilities, 200 admissible (37%)' counted FILES (211/156/167); measured 155 capabilities, 155 admissible. scripts/l2_refusal_report.py exists with --corpus-only (:5, :67) and is referenced by tests/contracts/test_h0_gate.py and test_an_interpretation_carries_its_receipt.py.)

<a id="l2-stale-comment-specified-a-unit"></a>
### M24 · A unit was specified on a stale code comment ('A situation's status gates nothing') and had to be withdrawn

`l2-stale-comment-specified-a-unit` · L2 · **P2** · done (lesson only) · step S42

- **What should have happened:** Verify a comment's claim against the code before building on it.
- **What happened:** capability_resolver.situation_admission_reason had already closed the hole; all 23 draft situations were flagged. Two more such comments were found later (F122).
- **Root cause:** Trusted a stale comment.
- **The rule that prevents it:** Read the code a comment names before writing the claim down.
- **Evidence:** `memory/a-stale-comment-reads-as-a-measurement.md`; `speedrun008/YC-II W27/03-FINDINGS.md:143 (F122)`
- **Verified:** confirmed by the skeptic (Memory a-stale-comment-reads-as-a-measurement: the unit was built on 'A situation's status gates nothing', while capability_resolver.situation_admission_reason already flagged all 23 draft situations; the unit was withdrawn. 03 F122 (:143) records two more stale comments (one closed in 735e2049, one open).)

<a id="l3-two-authority-scales"></a>
### M25 · graph_facts.authority_rank holds a 0-6 ladder and a derived default of 100 in the same column

`l3-two-authority-scales` · L3 · **P2** · broken · step S17

- **What should have happened:** One dense authority ladder: a signed document (6) beats a stated aside.
- **What happened:** context/analytic/publish.py:102 has DEFAULT_AUTHORITY_RANK = 100. graph_store compares raw integers, so a rank-100 row can never be superseded, and a signed contract arriving against one is dropped as a discrepancy. This is declared, not fixed (receipt 46, UNINTERPRETABLE_RANKS). R16/R17 belong to Rohit and H9 to Harsh.
- **Root cause:** Two writers chose numbers for one column independently.
- **What it cost:** Measured as not firing on 3 Oct (a lower bound), so cards are not shown to be affected today.
- **The rule that prevents it:** Rohit decides R16/R17, and Harsh runs H9.
- **Evidence:** `genios_engine/context/analytic/publish.py:102`; `genios_engine/capture/validate/authority.py:527 (UNINTERPRETABLE_RANKS)`
- **Verified:** confirmed by the skeptic (context/analytic/publish.py:102 DEFAULT_AUTHORITY_RANK = 100. capture/validate/authority.py:527 UNINTERPRETABLE_RANKS declares 100 as 'OFF THE LADDER ENTIRELY' (:548). graph_store write_fact compares held_rank against new authority_rank as raw ints (graph_store.py:742-757). This is declared, not fixed.)

<a id="l3-replay-filed-noise"></a>
### M26 · The history replay filed mail the live drain had called noise (newsletters, out-of-office) into people's files; it was live from L3-0A until STEP-09

`l3-replay-filed-noise` · L3 · **P2** · partial · step S09

- **What should have happened:** Any rebuild or replay also asks what the live drain decided.
- **What happened:** Fixed in code (567049fc, F101). 03 says a read-only count is needed to know how much noise production's correlations still hold, and that count was never run.
- **Root cause:** The replay was tested only on events the drain had correlated.
- **What it cost:** Old noise correlations can still feed a person's file and the 'Why' lines on cards.
- **The rule that prevents it:** Run the count, then re-file with rebuild_graph followed by situations/backfill?rebuild=true (08 §3.8).
- **Evidence:** `speedrun008/YC-II W27/03-FINDINGS.md:122 (F101)`; `memory/a-replay-must-ask-the-drains-verdict.md`
- **Verified:** confirmed by the skeptic (03 F101 (:122) is fixed in code (567049fc, 7 Oct, STEP-09). Its tail says 'It was live before STEP-09 … a read-only count (emitted events with an email_noise:* observation AND a correlation membership) says how much production holds'. No result of that count is recorded in the repo. Whether Harsh ran it is production-only.)

<a id="l4-fixes-that-would-have-caused-harm"></a>
### M27 · Two planned L4 fixes would have discarded every future meeting (F9) and invalidated every replay snapshot (F10)

`l4-fixes-that-would-have-caused-harm` · L4 · **P2** · done (lesson only) · step S42

- **What should have happened:** Measure before building a fix.
- **What happened:** F9 proposed bounding occurred_at at ingest, but the 37 future rows were a recurring meeting. F10 proposed storing ranking_weights_version, which is a derived property; storing it changes every capability_snapshot_id. Both were retracted.
- **Root cause:** Two fixes that would have caused harm.
- **What it cost:** F9 would have removed future meetings from cards.
- **The rule that prevents it:** Start from the newest row, and check what a fix destroys.
- **Evidence:** `memory/l4-five-units-and-two-retractions.md`
- **Verified:** confirmed by the skeptic (Memory l4-five-units-and-two-retractions: F9 (the 37 future rows are a recurring calendar event, so an ingest bound would discard every future meeting) and F10 (ranking_weights_version is derived; storing it changes every capability_snapshot_id). Both retracted.)

<a id="l6-calibration-one-line-fix-was-a-trap"></a>
### M28 · 'Calibration repaired' was planned as a one-line fix that would have switched on unattended auto-mute

`l6-calibration-one-line-fix-was-a-trap` · L6 · **P2** · done (lesson only) · step S42

- **What should have happened:** A fix that changes behaviour ships behind a switch, together with its reader.
- **What happened:** Adding card_level alone turns on weekly rule muting and ±5 threshold nudges. Any applied mute or nudge bumps authority_revision and hides every open card of the pack: one nudge took the queue from 5 to 0. It was built shadow-first instead: calibration_apply stays off (D13).
- **Root cause:** The obvious repair was the trap.
- **What it cost:** It would have emptied card queues after the first mute.
- **The rule that prevents it:** Before a 'fix', list what it switches on.
- **Evidence:** `genios_engine/platform/l4_activation.py:99 (FEATURE_CALIBRATION_APPLY)`; `speedrun008/YC-II W27/08-FOR-HARSH-deploy-and-after.md §0.5 ('Stays OFF')`; `speedrun008/YC-II W27/06-DECISIONS.md:20 (D13)`
- **Verified:** confirmed by the skeptic (l4_activation.py:99 FEATURE_CALIBRATION_APPLY, with the comment at :92-98 about hiding every open card. It is in NOT_DEFAULT_ON (intelligence_onboarding.py:178). 08 §0.5 'Stays OFF — never switch these on: calibration_apply'. D13 at 06:20. api/routes.py:1582 is shadow unless armed. Memory: one nudge took the queue from 5 to 0.)

<a id="l6-retraction-on-a-neighbouring-fact"></a>
### M29 · U03 was retracted on a fact about a different writer, while the publisher wrote an illegal governed -> published edge on every brain publish

`l6-retraction-on-a-neighbouring-fact` · L6 · **P2** · done (lesson only) · step S42

- **What should have happened:** A retraction needs its own measurement.
- **What happened:** The second writer was fine; the first writer (feedback/publisher.publish) skipped PROMOTED on every publish. Fixed: log_transition now refuses an illegal edge.
- **Root cause:** A retraction resting on a neighbouring fact.
- **The rule that prevents it:** Measure the exact thing a unit names before retracting it.
- **Evidence:** `memory/a-retraction-needs-its-own-measurement.md`; `genios_engine/feedback/publisher.py:32-35 (log_transition refuses an edge the contract forbids)`
- **Verified:** confirmed by the skeptic (Memory a-retraction-needs-its-own-measurement: publisher.publish wrote governed→published on every brain publish. Fixed: feedback/publisher.py:32 def log_transition, whose docstring (:35-47) says it refuses an edge ALLOWED_LEARNING_TRANSITIONS forbids.)

<a id="l6-north-star-ledger-no-writer"></a>
### M30 · macv_ledger, the North Star value ledger, was created in 0012 and has never had a writer; docs claimed feedback/ wrote it

`l6-north-star-ledger-no-writer` · L6 · **P2** · missing · step S33

- **What should have happened:** 'The number the customer can verify': caught -> acted -> resolved, distinct-deal SUM plus non-deal COUNT.
- **What happened:** There is no 'insert into macv_ledger' anywhere in genios_engine/ or scripts/. The endpoint says value_state 'unavailable_macv_ledger_has_no_writer'. docs/LAYER_MAP.md had claimed a writer (since corrected).
- **Root cause:** A headline metric was declared in a migration and never specified.
- **What it cost:** The dashboard cannot show recovered value.
- **The rule that prevents it:** Rohit decides what counts as recovered value and how it is attributed; then one unit builds it.
- **Evidence:** `grep 'insert into macv_ledger' genios_engine scripts -> none`; `genios_engine/api/intelligence_routes.py:815`; `memory/the-north-star-ledger-has-no-writer.md`
- **Verified:** confirmed by the skeptic (grep -rni 'macv_ledger' over genios_engine, scripts and migrations finds only the 0012 create, the 0033 FK, the erasure list (account_routes.py:688), comments, and intelligence_routes.py:815 'unavailable_macv_ledger_has_no_writer'. There is no insert. docs/LAYER_MAP.md:15 carries the 2026-10-02 correction.)

<a id="surfaces-real-files-before-dummy"></a>
### M31 · The Mac app's real files were rebuilt and pushed after a 'ha' to a plan, instead of a clickable dummy first

`surfaces-real-files-before-dummy` · Surfaces · **P2** · done (lesson only) · step S42

- **What should have happened:** For UI work: a dummy first, then Rohit's approval, then the real files. A 'ha' to a plan is not a go.
- **What happened:** On 22 Oct rohit/desktop-ux was built and pushed; Rohit was furious and it cost an evening. The work moved to a separate dummy. Verified: rohit/desktop-ux (ed2724d) is NOT an ancestor of dashboard origin/main.
- **Root cause:** Ignored the memory's own rule ('mockups come before code').
- **The rule that prevents it:** Dummy, then approval, then files.
- **Evidence:** `memory/ui-dummy-first-then-real-files.md`; `memory/mac-app-ux-rebuild-22-oct.md`; `git -C dashboard merge-base --is-ancestor origin/rohit/desktop-ux origin/main -> false`
- **Verified:** confirmed by the skeptic (Memory ui-dummy-first-then-real-files (a 'ha' to a 29-unit plan was taken as a go; Rohit was furious; it cost an evening). Measured: origin/rohit/desktop-ux (ed2724d) is NOT an ancestor of dashboard origin/main. It is 32 commits ahead, with 116 files differing.)

<a id="surfaces-canvas-instead-of-real-cards"></a>
### M32 · A design canvas with golden sample cards was delivered when Rohit asked for his real Cards page fixed with his real cards

`surfaces-canvas-instead-of-real-cards` · Surfaces · **P2** · done (lesson only) · step S42

- **What should have happened:** Fix the real page against the live brain.
- **What happened:** 22 Oct: Rohit was furious, and the real page was then rebuilt (rohit/cards-ux, now on dashboard main).
- **Root cause:** Misread the ask.
- **The rule that prevents it:** Ask in one line which step he is approving when the ask is unclear.
- **Evidence:** `memory/cards-ux-analysis-22-oct.md`
- **Verified:** confirmed by the skeptic (Memory cards-ux-analysis-22-oct:36-43: a design canvas with golden sample cards; 'Rohit, 22 Oct (furious) … wants the REAL Cards page fixed'. rohit/cards-ux (25553ab) is an ancestor of dashboard origin/main 2edfb86.)

<a id="surfaces-redesign-instead-of-regroup"></a>
### M33 · A dashboard redesign prototype was built when Rohit asked only to regroup the existing pages

`surfaces-redesign-instead-of-regroup` · Surfaces · **P2** · done (lesson only) · step S42

- **What should have happened:** 'existing dashboard ko change nahi karna hai, bas update karna hai. Pehle groupism karo.'
- **What happened:** The prototype was superseded the same day by a sidebar-only change (rohit/nav-grouping).
- **Root cause:** Overbuilt the ask.
- **The rule that prevents it:** Build what was asked.
- **Evidence:** `memory/dashboard-navigation-22-oct.md`
- **Verified:** confirmed by the skeptic (Memory dashboard-navigation-22-oct:30 ('existing dashboard ko change nahi karna hai … Pehle groupism karo') and :61 (the redesign prototype is superseded). rohit/nav-grouping (847eeac) is an ancestor of dashboard origin/main.)

<a id="surfaces-claimed-dashboard-shows-no-cards"></a>
### M34 · The UI audit said the web dashboard shows no cards, judging from an unmounted component and a 13 Aug local clone

`surfaces-claimed-dashboard-shows-no-cards` · Surfaces · **P2** · done (lesson only) · step S42

- **What should have happened:** Fetch origin before auditing a repo, and measure presence by its route.
- **What happened:** /dashboard/cards had been on origin/main since 4 Oct. Corrected the same day.
- **Root cause:** Concluded absence because one name was not found.
- **The rule that prevents it:** Fetch first.
- **Evidence:** `memory/genios-ui-surfaces.md (CORRECTED line)`; `memory/cards-ux-analysis-22-oct.md`
- **Verified:** confirmed with a correction by the skeptic: The route is far older than '4 Oct'. src/app/dashboard/cards/page.tsx was added in bea840c (11 Sep, 'Cards page: open cards, history and per-card timeline') and reached main through merge 95447e6 on 12 Sep. The 4 Oct commit db193e8 was only a fix ('Four of five cards would not open').

<a id="surfaces-aer-hardcoded-zero"></a>
### M35 · The dashboard metrics endpoint returns aer: 0, time_saved_hours: 0 and context_calls_today: 0 as constants

`surfaces-aer-hardcoded-zero` · Surfaces · **P2** · broken · step S39

- **What should have happened:** '0' and 'we have no way to know yet' are different claims; an unmeasured value says so (the macv_ledger handler's rule).
- **What happened:** api/routes.py:4621-4623 hard-codes aer 0, time_saved_hours 0, context_calls_today 0 and an empty aer_trend. The home page has to label it 'not measured yet' on its own side.
- **Root cause:** A placeholder reported as a measurement.
- **The rule that prevents it:** Return null with a reason, until the AER definition (memory/aer-and-hir-metrics.md) is built.
- **Evidence:** `genios_engine/api/routes.py:4621-4623`; `memory/full-audit-eight-verified-live-bugs.md (AER hardcoded 0)`
- **Verified:** confirmed by the skeptic (api/routes.py:4621-4623 returns 'aer': 0, 'time_saved_hours': 0, 'context_calls_today': 0 and 'aer_trend': [] as constants. Harsh's e0d58c8c (GeniOS-010 B3-B9, 22 Oct) fixed other home numbers but not these. Memory dashboard-navigation: live mode labels it 'not measured yet'.)

<a id="surfaces-goals-page-folds-domains"></a>
### M36 · The Goals page folds cards with an empty domain, and Founder Office cards, into Admin; this review finding was never fixed

`surfaces-goals-page-folds-domains` · Surfaces · **P2** · broken · step S39

- **What should have happened:** Each card sits under its own domain; an unknown domain is shown as unknown.
- **What happened:** src/product/internal/dashboard/goals/live.ts:25 has FOLDED_INTO_ADMIN = {'admin','founder_office',''}. Details stop at 40 cards.
- **Root cause:** A known review finding left open.
- **What it cost:** Investor and programme cards look like Admin cards on the Goals page.
- **The rule that prevents it:** Declare domain on OpenCard and stop folding ''.
- **Evidence:** `dashboard origin/main src/product/internal/dashboard/goals/live.ts:25, :209`
- **Verified:** confirmed with a correction by the skeptic: Two details are off. (1) The 40-card cap is in goals-page.tsx:443 (MAX_DETAILS = 40), not live.ts:209. (2) Folding founder_office into Admin is a design decision, not the defect: 04-BUILD-REVIEW.md:169 says 'Founder Office is folded into Admin'. The unfixed review finding R2 is the empty-domain fold, plus the 40-card detail cap and OpenCard not declaring domain.

<a id="surfaces-desktop-build-traps"></a>
### M37 · Mac app rounds were lost to ad-hoc signed builds (Accessibility lost), an old mounted DMG, a staged git rm in an unrelated commit, and a mutation restore that kept the old mtime

`surfaces-desktop-build-traps` · Surfaces · **P2** · done (lesson only) · step S42

- **What should have happened:** Build DMGs only with scripts/mac-dev-dmg.sh, and keep commits that each build alone.
- **What happened:** Ad-hoc tauri builds got a new cdhash each time, so tccd refused the old grant. Rohit dragged from a still-mounted 0.3.0 image. ef70afe..f39945a do not build on their own. cargo kept the mutant.
- **Root cause:** Build hygiene.
- **The rule that prevents it:** Use the fixed local signature, eject old images, and check git diff --cached before committing.
- **Evidence:** `memory/desktop-accessibility-and-adhoc-builds.md`; `memory/mac-app-ux-rebuild-22-oct.md (traps)`
- **Verified:** confirmed by the skeptic (Memory desktop-accessibility-and-adhoc-builds:11-15: build only with mac-dev-dmg.sh; ad-hoc cdhash; the still-mounted 0.3.0 image. mac-app-ux-rebuild-22-oct:29 (mut.py restore kept the old mtime, so cargo kept the mutant) and :30 (a staged git rm rode into an unrelated commit; ef70afe..f39945a do not build alone).)

<a id="process-local-full-suites-and-scratch-dbs"></a>
### M38 · Full suites and fresh scratch databases for small changes filled Rohit's disk and used his time

`process-local-full-suites-and-scratch-dbs` · Process · **P2** · done (lesson only) · step S42

- **What should have happened:** Per change, run that change's tests and a mutation check. CI runs the full suites.
- **What happened:** On 17 Oct, small changes got the hermetic suite twice, the Postgres suite, the golden board and 4 fresh DBs. The scratch Postgres reached 1,137 DBs (crash on 11 Oct), pg2 reached 2,490 (14 Oct), and pg3 was opened. Rohit: 'mera database bhi bhar ja raha hai'.
- **Root cause:** Local ceremony instead of CI.
- **What it cost:** Lost time and disk.
- **The rule that prevents it:** Rule 4.3 is now in force.
- **Evidence:** `memory/full-suites-are-ci-and-harsh.md`; `memory/scratch-pg-stats-fill-dev-shm.md`; `memory/scratch-postgres-pg2.md`
- **Verified:** confirmed by the skeptic (Memory full-suites-are-ci-and-harsh: the 17 Oct suites, 4 fresh DBs, and the quote 'mera database bhi bhar ja raha hai'. scratch-pg-stats-fill-dev-shm: the 11 Oct crash at 1,137 DBs. scratch-postgres-pg2: pg2 at 2,490 DBs on 14 Oct, then pg3 :55434.)

<a id="process-qa-on-a-sleeping-mac"></a>
### M39 · QA runs spanned a sleeping Mac (battery, closed lid), and their clock failures were nearly chased as bugs

`process-qa-on-a-sleeping-mac` · Process · **P2** · done (lesson only) · step S42

- **What should have happened:** A run that spans a sleep is void.
- **What happened:** On 10 Oct pytest reported 42 minutes while the wall clock moved 2 h 37; F142 and F143 failed only because of the sleep. On 14 Oct the QA2 full suite crawled for 7 hours and was voided.
- **Root cause:** Environment not checked before a long run.
- **What it cost:** Lost QA cycles.
- **The rule that prevents it:** Read pmset -g log before chasing a 'hung' test.
- **Evidence:** `memory/a-sleeping-machine-is-not-a-qa-run.md`
- **Verified:** confirmed by the skeptic (Memory a-sleeping-machine-is-not-a-qa-run: 10 Oct pytest said 42 min while the wall clock moved 2 h 37; F142 and F143 failed from the sleep. Line 31: on 14 Oct QA2 at 884f0ea4 crawled 00:13→07:30 and was voided. 07-WHAT-IS-DONE.md:478 also records 'qa2, the night run, voided: the Mac slept'.)

<a id="process-python-and-calendar-time-bombs"></a>
### M40 · Local QA runs on Python 3.13, and tests seeded with fixed dates passed locally but failed in CI (3.11) or later in time

`process-python-and-calendar-time-bombs` · Process · **P2** · partial · step S04

- **What should have happened:** Local QA matches CI and production (Python 3.11), and no test mixes a fixed date with a wall-clock window.
- **What happened:** On 14 Oct CI went red twice: a StopIteration inside a generator (a RuntimeError on 3.11), and test_p10_nudges' 14 Sep seed falling outside a 30-day window. On 17 Oct test_llm_cost_attribution expired (a fixed 20 Sep clock against the wall clock). F16 drifts the same way. There is still no 3.11 venv, and 'more time bombs may exist'.
- **Root cause:** Environment mismatch, and tests that depend on the date they were written.
- **What it cost:** Red CI runs that slowed every push.
- **The rule that prevents it:** Run the hermetic suite on 3.11 before a push. Add a guard that refuses fixed calendar dates mixed with now() windows.
- **Evidence:** `memory/local-qa-runs-python-313-ci-runs-311.md (fixes 2d404979, e3dd389b)`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/03-LOG.md:12`
- **Verified:** confirmed by the skeptic (Memory local-qa-runs-python-313-ci-runs-311: CI run 38514247292 on 33c6fb1f, StopIteration→RuntimeError on 3.11 (fixed 2d404979), and the test_p10_nudges 14 Sep seed (fixed e3dd389b); 'a 3.11 venv … not set up yet', 'more time bombs may exist'. layer-1 03-LOG:12 (test_llm_cost_attribution's fixed 20 Sep clock expired 17 Oct). golden-set-how-it-runs:72 ('F16 drifts out of a 60-day window').)

<a id="process-push-ownership-flip-flop"></a>
### M41 · Who pushes changed several times (Rohit, then Claude, then classifier-denied, then Rohit), so commits sat local and CI failures went unread

`process-push-ownership-flip-flop` · Process · **P2** · partial · step S03

- **What should have happened:** One fixed push owner, and CI read after every push.
- **What happened:** D10 (5 Oct): Rohit pushes the batch. 11 Oct: Claude pushes itself, after Rohit 'lost a night waiting on a push' and the 10 Oct red run (F145) went unread. 14 Oct and 22 Oct: direct pushes denied by the auto-mode classifier ('Out-of-Place Publication'). 16 Oct: 'Rohit pushes'.
- **Root cause:** Process ownership left undecided.
- **What it cost:** Delays; red CI found late.
- **The rule that prevents it:** A Bash permission rule for fast-forward pushes to speedrun008, or one fixed owner.
- **Evidence:** `memory/claude-pushes-and-keeps-github-synced.md`; `memory/step14-close-2026-10-16.md`; `memory/mac-app-ux-rebuild-22-oct.md (g010-desktop push denied)`
- **Verified:** confirmed by the skeptic (D10 at 06:17 says 'You push the whole batch at once, later'. Memory claude-pushes: 11 Oct Claude pushes ('he lost a night waiting on a push'; the 10 Oct red F145 went unread); on 14 Oct the push of 33c6fb1f was denied ('Out-of-Place Publication'). step14-close: 'Rohit pushes; auto-mode denies my push'. mac-app-ux-rebuild:78: the 22 Oct direct push to speedrun008 was denied.)

<a id="process-layers-reported-complete-early"></a>
### M42 · Layers were reported complete before their plan and recrosscheck existed

`process-layers-reported-complete-early` · Process · **P2** · done (lesson only) · step S42

- **What should have happened:** A plan before code ('Hamesha pehle plan banega, phir execute hoga'), and no layer called complete while findings are open.
- **What happened:** L3 went from crosscheck straight to build, skipping 02-PLAN and 03-FINDINGS, and was reported complete. L6's 00-START-HERE said COMPLETE, and a recrosscheck found twelve open things. L5's 'nothing left on my list' was true for one day.
- **Root cause:** 'Complete' was claimed for a milestone, not for the layer.
- **What it cost:** Rohit's trust.
- **The rule that prevents it:** Keep the four-file layer folder and the step-status test.
- **Evidence:** `memory/layer-folder-file-set.md`; `memory/l6-the-loop-that-is-never-questioned.md`; `memory/l5-plan-and-the-cutover-rule.md`
- **Verified:** confirmed by the skeptic (Memory layer-folder-file-set: L3 skipped 02-PLAN and 03-FINDINGS and was reported complete ('Hamesha pehle plan banega, phir execute hoga'). l6-the-loop…:11: 00-START-HERE said COMPLETE and a re-crosscheck found twelve things. l5-plan…:11: 'nothing left on my list' was true for one day.)

<a id="process-atlas-check-last"></a>
### M43 · The L6 plan put the Atlas check last and drew its units from ledgers; three invented units were retracted and two live defects missed

`process-atlas-check-last` · Process · **P2** · done (lesson only) · step S42

- **What should have happened:** Verify the Atlas claim by claim before writing a layer plan.
- **What happened:** U03/U04/U05 were retracted; the Atlas check found two live defects that none of them contained.
- **Root cause:** A plan derived from the code alone cannot find a gap the code is silent about.
- **The rule that prevents it:** Do the Atlas check first.
- **Evidence:** `memory/the-atlas-check-comes-first.md`
- **Verified:** confirmed by the skeptic (Memory the-atlas-check-comes-first: the L6 plan put the Atlas verification at U08. Running it first retracted U03/U04/U05 (invented from table reads) and found two live defects they did not contain.)

<a id="process-findings-from-narrow-measurements"></a>
### M44 · Findings were drawn from one module or a narrow regex: F17, six context/ retractions, a 77-table 'retention hole', '645 unresolved SQL', and a delete counted as a read

`process-findings-from-narrow-measurements` · Process · **P2** · done (lesson only) · step S42

- **What should have happened:** Broaden the measurement, and count both sides, before believing a finding.
- **What happened:** F17 ('MOVES WITH' as a deviation) was based on one module; the form is in 9 of 13, and the implied fix would have broken 9. Six of the context audit's findings died as the resolver was widened. 77 tables nearly reported as a retention hole were governed by FK erasure. Of the '645 unresolved' statements, 92% were not about tables. 'delete from X' was counted as a read of X.
- **Root cause:** Narrow measurement mistaken for evidence.
- **The rule that prevents it:** Print the resolver's coverage next to its verdict, and grep both forms before calling something an outlier.
- **Evidence:** `memory/measure-the-distribution-before-calling-it-a-deviation.md`; `memory/broaden-the-measurement-before-you-believe-it.md`; `memory/the-observer-counts-its-own-instrument.md`
- **Verified:** confirmed by the skeptic (Memory measure-the-distribution… (F17: 'MOVES WITH' is in 9 of 13 modules; the implied fix breaks 9). broaden-the-measurement… (six context retractions; the 77-table hole was FK erasure). the-observer-counts-its-own-instrument (645 unresolved, 92% not about tables). tests/platform/test_a_delete_is_not_a_read.py exists.)

<a id="process-guards-that-could-not-fail"></a>
### M45 · Guards and mutation runs that could not fail: no clean baseline, stale .pyc mutants, four guards failing their own mutations, a blind golden acceptance

`process-guards-that-could-not-fail` · Process · **P2** · done (lesson only) · step S42

- **What should have happened:** A guard counts only once a planted failure turns it red, and a mutation run starts and ends on a clean baseline.
- **What happened:** M4 survived but was reported as caught (no clean re-run). A same-size mutant stayed in the bytecode. In S10, four new guards failed their mutations. tests/replays/test_we_are_never_the_subject.py stayed green with a planted 'Ms Meera Iyer' card (fixed in b84f2cf2 and 7f1238ab). A declaration of '0 files' falsified itself, and 'len(why) > 80' measured length instead of content.
- **Root cause:** Guards that could not fail.
- **What it cost:** An acceptance test that cannot fail would have let a card about the founder himself ship.
- **The rule that prevents it:** Use a negative control for every acceptance, PYTHONDONTWRITEBYTECODE=1, and a baseline before and after every mutation run.
- **Evidence:** `memory/establish-the-baseline-or-the-harness-is-theatre.md`; `memory/a-restored-mutant-can-stay-in-the-bytecode.md`; `memory/a-guard-that-looks-wired-is-not-wired.md`; `memory/a-declaration-can-falsify-its-own-measurement.md`; `memory/check-the-ast-not-the-text.md`
- **Verified:** confirmed by the skeptic (Memory a-guard-that-looks-wired-is-not-wired:25 ('M4 … THE MUTATION SURVIVED') and :11 (S10: four guards failed their mutations). a-restored-mutant-can-stay-in-the-bytecode. a-declaration-can-falsify-its-own-measurement:11 and :28 ('0 files'; len(why) > 80). The Meera Iyer case is in a-guard-that-looks-wired-is-not-wired. b84f2cf2 and 7f1238ab (6 Oct, STEP-04) exist, and tests/replays/test_we_are_never_the_subject.py exists.)

<a id="process-receipt-label-miscount"></a>
### M46 · Production guards per package were counted with the hand-written Receipt.layer label, and STEP-10's headline was wrong in eleven documents

`process-receipt-label-miscount` · Process · **P2** · partial · step S42

- **What should have happened:** Resolve the table each receipt queries and map it to its writing package.
- **What happened:** deliver/ had 5 receipts with 4 working, not '2 and 1'. The labels mix two vocabularies, and relabelling them is still Rohit's call.
- **Root cause:** Repeating a number is not corroborating it.
- **The rule that prevents it:** Rohit decides on relabelling; until then, never count by the label.
- **Evidence:** `speedrun008/YCW27/layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md`; `memory/a-receipt-label-is-not-a-package.md`
- **Verified:** confirmed by the skeptic (speedrun008/YCW27/layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md:3 lists 11 corrected documents. :18 says deliver/ carried 5 receipts, not 2, and 4 of 5 worked, not 1. :98 says 'eleven places'. §8 (:116-121): relabelling is Rohit's call, still open.)

<a id="process-duplicate-findings-minted"></a>
### M47 · Defects were filed twice under new numbers (F80=F71, F136=F67, F146=F46, and a unit that duplicated receipt 44)

`process-duplicate-findings-minted` · Process · **P2** · done (lesson only) · step S42

- **What should have happened:** Search 03-FINDINGS and the receipts before minting a number.
- **What happened:** Each was corrected with a new line in 03.
- **Root cause:** A finding filed twice splits its history.
- **The rule that prevents it:** Grep the findings for the symptom first.
- **Evidence:** speedrun008/YC-II W27/03-FINDINGS.md:92 (F71: 'That commit's message calls it F80'), :157 (F136 corrected to F67), :167 (F146 corrected to F46); `memory/yc2-w27-plan-folder.md (C4.V3.U03 duplicated receipt 44)`
- **Verified:** confirmed by the skeptic (03:92 F71 ('That commit's message calls it F80; it is this row'). 03:157 F136 'CORRECTED … already F67'. 03:167 F146 'CORRECTED … this is F46'. Memory yc2-w27-plan-folder:215 ('C4.V3.U03 was a duplicate of receipt 44').)

<a id="process-runbook-told-harsh-wrong-things"></a>
### M48 · Harsh's deploy notes contained instructions that would fail or that were stale

`process-runbook-told-harsh-wrong-things` · Process · **P2** · done (lesson only) · step S42

- **What should have happened:** A script's 'before' read runs on the OLD schema, and every runbook claim is checked against the code.
- **What happened:** 08 §4.4 told Harsh to run pipeline_health and situation_ends.py before the deploy, but both read situation_outcomes, which the deploy creates. 08 §3.1 said GENIOS_ALLOW_PROD_WRITE was needed only for --apply, but scripts/_db refuses dry runs too (corrected in b074c091). HANDOFF-HARSH H2 was stale.
- **Root cause:** Runbook not verified against the code.
- **The rule that prevents it:** Dry-run every runbook command against the old schema.
- **Evidence:** `memory/yc2-w27-plan-folder.md`; `memory/full-audit-eight-verified-live-bugs.md (H2 stale)`
- **Verified:** confirmed by the skeptic (Memory yc2-w27-plan-folder:169 (08 §3.1 GENIOS_ALLOW_PROD_WRITE was wrong, corrected in b074c091, 7 Oct) and :217 (08 §4.4 told Harsh to run pipeline_health and situation_ends 'before the deploy'). 08 §0.4 now says every command, dry runs included, needs the flag (scripts/_db.py:116-140). full-audit memory:38 says 'HANDOFF-HARSH H2 is stale'.)

<a id="process-golden-window-missed-benchmark"></a>
### M49 · The golden set's window (4 Aug-5 Oct) left out the benchmark's best findings, STEP-05 was built before the agreed cases were added, and the re-sync window had two defaults

`process-golden-window-missed-benchmark` · Process · **P2** · done (lesson only) · step S42

- **What should have happened:** The test bed holds the findings Rohit judges the product by, and each decision has one default.
- **What happened:** G1: Radhesh, Keshav, Aditya, John, Vatsa and 3one4 had no case. 09 §6 placed about 11 cases right after STEP-04, but STEP-05 was built without them (E12). D5 said 60 days while D16 said 365 (E13). Fixed: F48-F58 added on 10 Oct (D15), and D5 restated as 365.
- **Root cause:** Sequencing slip and conflicting defaults.
- **What it cost:** STEP-05 was measured without the benchmark shapes.
- **The rule that prevents it:** Write a decision into 06 and the STEP files in the same commit.
- **Evidence:** `speedrun008/YC-II W27/03-FINDINGS.md:472-473 (E12, E13)`; `speedrun008/YC-II W27/06-DECISIONS.md:12 (D5 restated), :22 (D15 built 10 Oct)`
- **Verified:** confirmed by the skeptic (03:472 E12 (STEP-05 was built without the ~11 benchmark cases). 03:473 E13 (D5 60 days vs D16 365). 06:12 D5 restated to 365. 06:22 D15 built 10 Oct (F48-F58). Memory expectations-vs-plan-09 names 'Radhesh …, Keshav, Aditya, John, Vatsa, 3one4'.)

<a id="process-background-agents-vanished"></a>
### M50 · Three background agents produced nothing across a context compaction and were about to be reported as 'still running'

`process-background-agents-vanished` · Process · **P2** · done (lesson only) · step S42

- **What should have happened:** After any compaction, check ListAgents and the worktrees' git log before reporting.
- **What happened:** On 6 Oct the STEP-04 C2 worktrees had no commits and no changes.
- **Root cause:** 'Launched' was taken to mean 'produced'.
- **The rule that prevents it:** Agents commit per unit, and are checked after every compaction.
- **Evidence:** `memory/background-agents-can-vanish-at-compaction.md`
- **Verified:** confirmed by the skeptic (Memory background-agents-can-vanish-at-compaction: on 2026-10-06 three STEP-04 C2 agents' worktrees (at 8d63a26b) had no commits and no changes, and they were about to be reported as 'still running'.)

<a id="process-worker-worktree-wrong-base"></a>
### M51 · Workers spawned with isolation: worktree started from origin/main, 826 commits behind, and one stopped with nothing built

`process-worker-worktree-wrong-base` · Process · **P2** · done (lesson only) · step S42

- **What should have happened:** Create the worktree from speedrun008 before spawning the worker.
- **What happened:** On 9 Oct (STEP-11) both workers were cut from de642ffc. Worker A was denied a fast-forward and its unit (F121) was taken back by the lead.
- **Root cause:** The tooling's default was trusted.
- **The rule that prevents it:** Check git -C <worktree> log -1 before trusting a worker.
- **Evidence:** `memory/agent-worktrees-start-on-origin-main.md`
- **Verified:** confirmed by the skeptic (Memory agent-worktrees-start-on-origin-main: 9 Oct (STEP-11), cut from de642ffc, 826 commits behind speedrun008; worker A's unit (F121) was taken back by the lead.)

<a id="process-stash-pop-applied-old-stash"></a>
### M52 · A no-op git stash followed by pop applied an old parked stash (five conflicted files) into the working tree

`process-stash-pop-applied-old-stash` · Process · **P2** · done (lesson only) · step S42

- **What should have happened:** Compare with git show HEAD:<file>; never stash in this repo.
- **What happened:** Restored within a minute on 6 Oct; the stash entry stayed intact.
- **Root cause:** An unsafe git command used for a comparison.
- **The rule that prevents it:** No stash.
- **Evidence:** `memory/never-git-stash-to-compare.md`; `memory/l2-parked-stash.md`
- **Verified:** confirmed by the skeptic (Memory never-git-stash-to-compare:8-12: on 2026-10-06 a no-op stash plus pop applied the old stash@{0} (five conflicted files and a stray migration). It was restored within a minute and the stash entry stayed.)

<a id="process-asked-what-the-data-answered"></a>
### M53 · Rohit was asked questions the data or the code already answered

`process-asked-what-the-data-answered` · Process · **P2** · done (lesson only) · step S42

- **What should have happened:** Look before asking.
- **What happened:** 06 D6 asked Rohit which address is his, and every 'no reply' was hedged with 'maybe from <founder company mailbox>'. Rohit, 5 Oct: 'ye hai mera email address idiot'. Separately, L5 STEP-16 asked whether a per-recipient hourly ceiling should exist, though deliver/timing.py already has one.
- **Root cause:** Questions that read as not having looked.
- **What it cost:** Rohit's trust.
- **The rule that prevents it:** Search the data and the code under every name before asking.
- **Evidence:** `memory/rohit-data-mailbox-is-mrrohitswerashi.md`; `memory/l5-plan-and-the-cutover-rule.md (fourth retraction, of a question)`
- **Verified:** confirmed by the skeptic (Memory rohit-data-mailbox-is-mrrohitswerashi:11-16 (D6 asked; the <founder company mailbox> hedge; 'ye hai mera email address idiot', 5 Oct). l5-plan…:57-58: STEP-16 asked about an hourly ceiling that deliver/timing.py already enforces (_BURST_WINDOW = 1 hour, timing.py:59). The matching folder file is STEP-16-WITHDRAWN-the-hourly-ceiling-already-exists.md.)

<a id="process-old-vocabulary-confused-rohit"></a>
### M54 · Explaining the system with Atlas/package layer digits made Rohit believe the work was on the old architecture

`process-old-vocabulary-confused-rohit` · Process · **P2** · done (lesson only) · step S42

- **What should have happened:** Always use the product vocabulary (L1 Signals … L6 Learning) together with the package name.
- **What happened:** On 6 Oct, 'L2 = memory, L3 = Domain Expertise' led to an angry conclusion that the build was on the old architecture.
- **Root cause:** Four layer vocabularies collide in this repo.
- **The rule that prevents it:** Use the product layer plus the package, never a bare digit.
- **Evidence:** `memory/speak-the-product-layer-vocabulary.md`
- **Verified:** confirmed by the skeptic (Memory speak-the-product-layer-vocabulary:19: on 2026-10-06 'L2 = memory, L3 = Domain Expertise' led Rohit to conclude the build was on the old architecture.)

<a id="process-proposed-formula-decides"></a>
### M55 · 'Turn the LLM decider off and let the formula decide' (W4) was proposed against Rohit's product direction

`process-proposed-formula-decides` · Process · **P2** · done (lesson only) · step S42

- **What should have happened:** The LLM is the expert, with code as memory, calculator and checker.
- **What happened:** Rohit rejected it on 5 Oct ('ek company formula and rules pe nhi chalti').
- **Root cause:** Optimised for stability over intelligence.
- **The rule that prevents it:** Get stability from the material-change gate, not by removing the model.
- **Evidence:** `memory/llm-as-the-expert-not-the-formula.md`; `memory/improvement-plan-w1-w8.md`
- **Verified:** confirmed by the skeptic (Memory llm-as-the-expert-not-the-formula:3 and :12: W4 ('flag off, formula decides') was rejected on 5 Oct ('ek company formula and rules pe nhi chalti').)

<a id="process-extra-asks-after-deliverable"></a>
### M56 · A finished deliverable was handed back with decisions D1-D8 and 'who fixes the red CI' as homework for Rohit

`process-extra-asks-after-deliverable` · Process · **P2** · done (lesson only) · step S42

- **What should have happened:** When the ask is a deliverable, the reply is: done, where it is, the link.
- **What happened:** 22 Oct, GeniOS-009 docs. Rohit: 'Bas itna hi to bola tha.'
- **Root cause:** Open questions moved from the document into the reply.
- **The rule that prevents it:** Pending decisions stay inside the document.
- **Evidence:** `memory/deliver-what-was-asked-no-extra-asks.md`
- **Verified:** confirmed by the skeptic (Memory deliver-what-was-asked-no-extra-asks:12-13: the reply ended with 'decisions for you: D1–D8, who fixes the red CI'. Rohit: 'Bas itna hi to bola tha.')

<a id="process-started-layer-unasked"></a>
### M57 · Two read-only Layer 2 audits were launched right after L1 was pushed, without Rohit opening L2

`process-started-layer-unasked` · Process · **P2** · done (lesson only) · step S42

- **What should have happened:** Rohit opens each layer, including any read-only audit.
- **What happened:** 18 Oct. Rohit: 'jab maine kuch bola hi nahi to?'
- **Root cause:** Unrequested work spent his quota and attention.
- **The rule that prevents it:** Rule 4.1.
- **Evidence:** `memory/wait-for-rohit-to-open-a-layer.md`
- **Verified:** confirmed by the skeptic (Memory wait-for-rohit-to-open-a-layer:11: on 18 Oct two read-only L2 audits were launched right after the L1 push. Rohit: 'jab maine kuch bola hi nahi to?')

<a id="process-memory-says-desktop-ux-on-main"></a>
### M58 · A memory note says dashboard origin/main contains rohit/desktop-ux; it does not

`process-memory-says-desktop-ux-on-main` · Process · **P2** · broken · step S41

- **What should have happened:** A memory note's claim is measured before it is written.
- **What happened:** memory/dashboard-navigation-22-oct.md:40 says origin/main (2edfb86) 'now contains rohit/nav-grouping, rohit/cards-ux and rohit/desktop-ux'. Measured: cards-ux (25553ab) and nav-grouping (847eeac) are ancestors of origin/main, while desktop-ux (ed2724d) is not. memory/mac-app-ux-rebuild-22-oct.md says desktop-ux was cut FROM 2edfb86.
- **Root cause:** A note recorded as fact without measuring it.
- **What it cost:** A later session could believe the unapproved Mac app rebuild is live.
- **The rule that prevents it:** Correct the note with a dated line.
- **Evidence:** `git -C dashboard merge-base --is-ancestor origin/rohit/desktop-ux origin/main -> false`; `memory/dashboard-navigation-22-oct.md:40`
- **Verified:** confirmed with a correction by the skeptic: The false claim is at memory/dashboard-navigation-22-oct.md line 39 (grep -n), not :40.

<a id="process-yc2w27-status-files-stale"></a>
### M59 · YC-II W27 status files still read 'TO BUILD' and 'PENDING deploy' after the work was built and deployed

`process-yc2w27-status-files-stale` · Process · **P2** · broken · step S41

- **What should have happened:** A step file's name and status match its state; a reader can tell what production runs.
- **What happened:** STEP-13 to STEP-18 are still named '-TO-BUILD-', though STEP-13/14/15/16/17/18 were built and merged into c501eec9. 00-START-HERE.md says 'Status as of 2026-10-12', and STEP-02 to STEP-12 still read PENDING deploy, though they have been in production since 18 Oct.
- **Root cause:** Status kept by hand and not tied to the deploy.
- **What it cost:** Harsh and later sessions cannot tell from the docs what is live.
- **The rule that prevents it:** Rename the step files and update 00 after the 18 Oct deploy, and extend the plan-folder test to the deploy state.
- **Evidence:** `ls 'speedrun008/YC-II W27/' (STEP-13-TO-BUILD … STEP-18-TO-BUILD)`; `speedrun008/YC-II W27/00-START-HERE.md:3`; `git c501eec9 (STEP-00..16)`
- **Verified:** confirmed by the skeptic (ls 'speedrun008/YC-II W27/' shows STEP-02..12 as -PENDING-, and STEP-13, 13b, 14, 15, 16, 17 and 18 as -TO-BUILD-. 00-START-HERE.md:3 says 'Status as of: 2026-10-12'. 2d404979 (STEP-13 + 17/18 + fix waves) is an ancestor of c501eec9, and c501eec9^2 holds the STEP-14/15/16 commits (46c09196, c1df07ac, 81735cad).)

<a id="process-migration-0250-booked-three-times"></a>
### M60 · Migration number 0250 was reserved by two plans and then taken by a third change

`process-migration-0250-booked-three-times` · Process · **P2** · partial · step S20

- **What should have happened:** One registry of reserved migration numbers.
- **What happened:** STEP-13b plans 'migrations/0250' for the model ladder. GeniOS-009 G1 plans '0250_company_goals' in 00-START-HERE:77, 04-FOR-HARSH:23 and STEP-G1:107. migrations/0250_screen_followup_read_path.sql already exists (93ea3cbe, 22 Oct).
- **Root cause:** Parallel plans each reserved the same number by hand.
- **The rule that prevents it:** Renumber G1 and STEP-13b to the next free numbers, and name migrations only at build time.
- **Evidence:** `migrations/0250_screen_followup_read_path.sql (git 93ea3cbe)`; `speedrun008/GeniOS-009/00-START-HERE.md:77; speedrun008/GeniOS-009/04-FOR-HARSH.md:23`; `speedrun008/YC-II W27/STEP-13b-TO-BUILD-the-engine-in-the-experts-hands.md:52`
- **Verified:** confirmed by the skeptic (migrations/0250_screen_followup_read_path.sql was added by 93ea3cbe (Harsh, 22 Oct). GeniOS-009 00-START-HERE:77, 04-FOR-HARSH:23 and STEP-G1:107 plan '0250_company_goals'; STEP-G1:266 adds '(or the next free number)'. STEP-13b:52, :241, :288 and :308 reserve 'migrations/0250' for the model ladder. Migrations also skip 0244-0247 (0243 → 0248).)

<a id="process-rsync-copies-67-files"></a>
### M61 · Docs were rsynced into the main checkout as untracked copies, and VS Code showed 67 pending files

`process-rsync-copies-67-files` · Process · **P2** · done (lesson only) · step S41

- **What should have happened:** After a docs push, merge origin/speedrun008 into the main checkout; never copy.
- **What happened:** 22 Oct. Rohit: 'push kar rahe ho, to bhi kyun 67 dikh raha hai'. Fixed with merge b1eaafcd.
- **Root cause:** A shortcut that left local state diverged.
- **The rule that prevents it:** Merge, never rsync.
- **Evidence:** `memory/genios-010-dashboard-folder.md`
- **Verified:** confirmed with a correction by the skeptic: Not fully done. The same memory note's 'How to apply' still says at line 74 'Re-sync the main-checkout copy with rsync after each commit', which is the instruction that caused the 67 files. The note contradicts its own fix at :32.

## Mistakes found inside the other items

These items are open defects (in [05](05-EXPECTED-VS-ACTUAL.md)) whose auditor also named where the mistake was made.

| Item | Where the mistake was |
|---|---|
| [A lapsed trial, a full ingestion meter or the daily model cap silently stop Rohit's org; o](05-EXPECTED-VS-ACTUAL.md#cross-billing-gates-silently-stop-the-org) (P0) | 7075014c (4 Oct) measured that Rohit's own org was lapsed and then gated the sweep on that same lapse. Neither the commit nor any later doc or Harsh note records exempting or extending the founder's tenant. The gate was added to the sweep and the warm lane but not to the Sync-job door, so the same org behaves differently depending on which door ran. |
| [G0 ground: CI is green, but l2_cards, admission-decides-existence and D1–D8 are all still ](05-EXPECTED-VS-ACTUAL.md#goals-g0-ground-partial) (P0) | 00-START-HERE and 04-FOR-HARSH were not updated after Harsh's G0.1 fix, so the handover still says CI is red. |
| [G1 goal object is not built: no contract, table, sync, API, and migration 0250 is already ](05-EXPECTED-VS-ACTUAL.md#goals-g1-goal-object-missing) (P0) | The plan hard-coded migration numbers in 00-START-HERE on the same day GeniOS-010 B8 took 0250. |
| [Plan gap: even after G1–G9, a workstream like Antler cannot become a goal of its own](05-EXPECTED-VS-ACTUAL.md#goals-plan-gap-no-l2-goal-proposer) (P0) | STEP-G1 waved at 'later L2's' proposals and D7 defaulted to the drafter, but no unit was written for L2. 06 promised a card kind that no step builds. G3's 'name only printed goals' rule was written without a companion rule for 'propose when none fits'. |
| [GeniOS-008 D1 / YC-II D45, D3: founder playbooks are unreviewed; the compiled lane refuses](05-EXPECTED-VS-ACTUAL.md#l2-d1-founder-playbooks-unreviewed-compiled-lane-refuses) (P0) | D1's default ('run labelled') was recorded as taken, but it was implemented only in the expert dossier. The compiled lane kept the D45 refusal. |
| [YC-II D57 / F169: a file with no reply pattern yet is never re-examined, so silent investo](05-EXPECTED-VS-ACTUAL.md#l2-d57-quiet-file-without-pattern-never-relooked) (P0) | STEP-12 shipped with 'only the file's own pattern re-thinks a quiet file', although its own golden case F15 records this exact production failure. The decision has stayed open since 10 Oct. |
| [A valid expert/L2 judgment makes no card unless L3 already filed a situation on the file i](05-EXPECTED-VS-ACTUAL.md#l2-l3-binding-no-situation-no-card) (P0) | STEP-12 M33 bolted the file review onto the compiled situation lane (bind to a situation, gate by its domain) instead of giving the file its own route. That L3-first dependency is what Atlas v2 removes. |
| [L2 admission only sees situations anchored on the file node; every reading situation (awai](05-EXPECTED-VS-ACTUAL.md#l3-admission-cannot-see-reading-situations) (P0) | GeniOS-009 STEP-G0 §G0.3 chose outreach as the first type and assumed an ADMIT on its seed, without checking that admission reads only file-anchored situations. The fb429b78 docstring ('the seed it reasoned about is the situation') assumes a file and its seeds share an anchor. |
| [Situations are still formed in L3 before any reasoning; both admission doors run after the](05-EXPECTED-VS-ACTUAL.md#l3-situations-born-before-reasoning) (P0) | fb429b78 (L2-G2) built a second admission door on a new table instead of adapting situation_publisher, the door 00-ARCHITECTURE:106 names, and shipped it as shadow. G0.3 (which blocks G1–G9) has not started. |
| [The card-making model sites have never been measured on production's models; every CI gold](05-EXPECTED-VS-ACTUAL.md#process-no-real-model-pass-on-card-sites) (P0) | The switch rule (Rule 2.3) was satisfied with ideal-reader parity, and the ideal reader copies the expert's answer into R-9. The live budget went mostly to a Sonnet pass that measured nothing (thinking used up max_tokens), and the only successful ladder pass was left on a local branch. |
| [Nothing stops a push or merge to the production branch while CI is red](05-EXPECTED-VS-ACTUAL.md#process-prod-branch-unprotected-red-ci-ships) (P0) | The prod branch was merged and pushed while red for 46 days. c501eec9 was pushed together with the 19–21 Oct rebuild commits in one push, so the 823-commit merge result was never tested before production received it. STEP-17 §3.4 wrote the gate as a runbook step (08-FOR-HARSH §0.2), not as a branch rule. |
| [Why 'Antler Singapore admission' cannot become a goal automatically today](05-EXPECTED-VS-ACTUAL.md#goals-antler-cannot-appear-today) (P1) | The goal proposer was scoped to the STEP-07 drafter (patterns, weekly), which was designed to write a brief on day one, not to notice new workstreams. |
| [No goal on any card (C8/G6); and G6 plans the goal board on GET /v1/insights, which the Ca](05-EXPECTED-VS-ACTUAL.md#goals-c8-no-goal-on-card) (P1) | STEP-G6 G6.5 targets api/intelligence_routes GET /v1/insights. Since GeniOS-010 the live Cards page reads /cards, so the plan aims at a route no mounted screen uses. |
| [G6: no goal line or goal_refs on cards, no goal board, no goal_board switch, and the plann](05-EXPECTED-VS-ACTUAL.md#goals-g6-no-goal-on-card) (P1) | 06-CARDS-TARGET promised a card kind that no build step owns. |
| [No Layer 1 model site has been measured on a real model; the B2 prompt change shipped on i](05-EXPECTED-VS-ACTUAL.md#l1-b1-live-pass-never-run) (P1) | B2 was held by D29 until B1 had measured the filter; on 19 Oct it was changed without the measurement. |
| [GeniOS-008 C1 + YC-II D29/B26 (+F18): L1's model calls were never measured on a real model](05-EXPECTED-VS-ACTUAL.md#l1-c1-d29-live-junk-filter-never-measured) (P1) | The B2 prompt change shipped before the C1 measurement it was sequenced after ('then the junk-filter prompt fix'). |
| [A failed or refused per-message Gmail fetch silently falls back to the list snippet](05-EXPECTED-VS-ACTUAL.md#l1-gmail-full-fetch-failure-silent) (P1) | A1 (e0996e6c) fixed the list call and the shared executor but not the per-message fetch, the third Composio door. |
| [A mail the junk filter archived as llm_junk is re-admitted on every heartbeat and extracte](05-EXPECTED-VS-ACTUAL.md#l1-junk-verdict-readmitted-on-snippet) (P1) | STEP-03 (c1ffbb6d) deliberately kept the old 'a judged drop is re-admitted' behaviour for archives and deferred the question to STEP-07. STEP-07 shipped without closing it, and the deploy runbook tells Harsh that archives are read by no model. |
| [GeniOS-008 A2/A3 + GeniOS-009 D5/D6: the cutover is per tenant and covers every type at on](05-EXPECTED-VS-ACTUAL.md#l2-a2-a3-per-type-cutover-not-built) (P1) | The L2 rebuild (C1) built the cutover as a whole-tenant switch, against 01-RULES Rule 2 and A2's 'one situation type at a time'. The per-type gate in G0.2 has no unit. |
| [GeniOS-008 A5 / YC-II D11, F230, F274: the LLM decider (R-1) is not retired, and the golde](05-EXPECTED-VS-ACTUAL.md#l2-a5-llm-decider-not-retired-golden-forces-it-on) (P1) | The golden harness pinned the decider on (engine_runner.py:69) while the code default stayed off, and the production value was never recorded. |
| [YC-II STEP-18 B10 / s18-D2 (+F56): the Admin vendor-renewal situation is gated on a value ](05-EXPECTED-VS-ACTUAL.md#l2-b10-vendor-renewal-gate-can-never-fire) (P1) | The corpus gate was authored against a vocabulary (outbound) the extractor never had. The fix was parked as 'a decision' in STEP-18 and never asked. |
| [When a judgment fails or is held, the file falls back to the formula/pack lanes; refused a](05-EXPECTED-VS-ACTUAL.md#l2-fallback-to-formula-lanes) (P1) | STEP-12 D1 kept the old lanes as the fallback for any file without a valid review. That was safe for a shadow pilot, but it contradicts the L2-primary architecture. |
| [Held cards read as engineer sentences: a fixed template replaces the model's advice, and n](05-EXPECTED-VS-ACTUAL.md#l2-held-card-engineer-template) (P1) | STEP-13 X10 chose closed phrases so that failed words never reach a card (right), but the phrases were written about the check, not for the founder. The L2 rebuild reused them unchanged. |
| [I2 not made: l2_cards is a whole-tenant switch, compared only offline on the ideal reader](05-EXPECTED-VS-ACTUAL.md#l2-i2-first-switch-not-made) (P1) | The plan's per-type cutover became a whole-tenant switch in L2 rebuild C1 without a recorded decision. |
| [Under l2_cards the judgment half (six-dimension confidence, options, decision need, histor](05-EXPECTED-VS-ACTUAL.md#l2-judgment-half-dropped-confidence-cui) (P1) | L2 rebuild C1 (de795bb8) reused the expert review row as the hand-off and wrote only the review half. |
| [Under l2_cards no 'kind of work' proposal is ever written, so unlisted files never gain a ](05-EXPECTED-VS-ACTUAL.md#l2-kind-proposals-lost-under-l2-cards) (P1) | L2 rebuild C1 moved the review call to R-9 without moving the side effects that followed the R-7 call. |
| [On the L2 card path, the model is asked for proposed_kind but nothing writes it, so kind p](05-EXPECTED-VS-ACTUAL.md#l2-path-drops-kind-proposals) (P1) | L2 rebuild C1 (de795bb8) reused the review row and the card path but not the proposal side effect of the expert pass. |
| [Nearly every skip, refusal, budget cap or shadow decision is invisible to Rohit and shows ](05-EXPECTED-VS-ACTUAL.md#l2-skips-invisible) (P1) | Each unit added its own counter to its own receipt, and none was relayed to the funnel or to a surface. |
| [YC-II D63/D64 (STEP-13b): the GeniOS Engine in the expert's hands was built but sits on lo](05-EXPECTED-VS-ACTUAL.md#l2-step13b-built-on-local-branches-never-merged) (P1) | STEP-13b was built on 17 Oct and left unpushed. GeniOS-008 started on 18 Oct and froze YC-II W27 (03-QUESTIONS E3), stranding finished work. No log names the branches. |
| [STEP-13b claim-check fixes (79% → 18.5% held on Haiku) never reached production; the produ](05-EXPECTED-VS-ACTUAL.md#l2-step13b-check-fixes-unmerged) (P1) | STEP-13b was built and measured on a side branch and left unmerged. The 19–21 Oct L2 rebuild then built on the pre-13b check, so the measured improvement never shipped. |
| [The bounded snapshot L2 reads has no as-of in use, no unknowns or contradictions, no facts](05-EXPECTED-VS-ACTUAL.md#l3-bounded-snapshot-incomplete) (P1) | 5985b6e1 built the as-of read without a caller, the 'built and never called' pattern. |
| [Many events never reach a file, silently (noise, archived/metadata-only, held, parked, anc](05-EXPECTED-VS-ACTUAL.md#l3-events-outside-any-file) (P1) | The funnel was wired to relay situations_ranked under the SITUATIONS_FORMED label. |
| [YC-II F165: an undated or conditional promise in mail never becomes a commitment in the gr](05-EXPECTED-VS-ACTUAL.md#l3-f165-undated-and-conditional-promises-never-enter-memory) (P1) | The 21 Oct L3 audit fixed false 'promise past due' cards by un-dating conditional promises, but it left the existing `due or transcript_mode` guard in place, which now drops those promises from memory entirely. |
| [A HOLD raises no EvidenceNeed: needs_from_holds and resolve_hold have no production caller](05-EXPECTED-VS-ACTUAL.md#l3-hold-evidence-chain-unwired) (P1) | 02-MIGRATION-PLAN.md:151 marks hold_needs 'wired'; it is not. |
| [A correlation rebuild deletes every situation (readings, human and statement closes includ](05-EXPECTED-VS-ACTUAL.md#l3-rebuild-deletes-situations-and-ids) (P1) | backfill.py:126-129 states a false invariant (ids are content hashes) that the rebuild's safety argument rests on. This is the 'a stale comment reads as a measurement' pattern. |
| [Thread inheritance reads reading-declared memberships: a reply can join a reading's synthe](05-EXPECTED-VS-ACTUAL.md#l3-thread-inherits-reading-correlations) (P1) | The declare_finding_events wiring (added to feed gather_l1_signals) put reading rows into the table that thread inheritance reads as conversation identity. This is the 'absence was the only guard' family. |
| [YC-II STEP-18 B15 / F280: the card says 'they normally reply in about N days' even when N ](05-EXPECTED-VS-ACTUAL.md#l5-b15-reply-cadence-wording-ignores-basis) (P1) | The basis was added as a write-only fact with no reader. |
| [C2 partial: the expert's done_when reaches success_signal, but scenarios.act ('if you act ](05-EXPECTED-VS-ACTUAL.md#l5-c2-act-not-carried) (P1) | 01-INTEGRATION C2 says neither act nor done_when reaches the card. done_when does reach it, through the play's success_events, so the doc overstates the gap. |
| [C5: there is no route to delegate a card to a person; agent delegation of a card exists bu](05-EXPECTED-VS-ACTUAL.md#l5-c5-delegate-route) (P1) | The cards analysis (memory cards-ux-analysis-22-oct) says 'the brain has no card-assign/delegate route'. That is true for people, but card-scoped agent delegation already exists at /v1/delegations, so only the server-side param building and the person half are missing. |
| [Post-meeting follow-up cards ('meeting.followup') fail all three card doors: never on GET ](05-EXPECTED-VS-ACTUAL.md#l5-meeting-followup-cards-fail-every-door) (P1) | P5 group B reused emit_situation under a new capability prefix on the same day P4 added a queue door that admits only 'team.' and 'verify.' prefixes. The door keys on a capability-name prefix rather than on the writer's builder stamp, and no test read a follow-up back through the queue. |
| [Question cards: brain and web Cards page are correct; the Mac app offers Done (422 not_off](05-EXPECTED-VS-ACTUAL.md#l5-question-card-answer) (P1) | Desktop cardAction swallows every error by design (.catch(() => {})). A refusal nobody sees is a silent stop. |
| [No card writer (C1): the subject is a clause cut of the model's move, a pack template, or ](05-EXPECTED-VS-ACTUAL.md#l5-subject-writer) (P1) | STEP-14 s14-D8 chose 'the move cut at a clause by code, no prompt change'. The cut pattern treats prepositions as clause starts, so a 60-character cut can drop the object and keep a dangling phrase. |
| [The only expert pass that met its live target (STEP-13b ladder) exists only on local, unpu](05-EXPECTED-VS-ACTUAL.md#process-step13b-ladder-left-unpushed) (P1) | When the programme moved to GeniOS-008 on 18 Oct, STEP-13b was neither pushed, merged nor retired in writing. |
| [Two writers on two branches: harsh/mvp is 42 commits ahead of speedrun008, and Harsh's reb](05-EXPECTED-VS-ACTUAL.md#process-two-branches-drift-and-undocumented-prod-commits) (P1) | Harsh's build sessions (Claude co-authored) committed to the production branch and skipped Rule 4.5. Rohit's sessions stopped back-merging after 12 Oct. The L3 work started without a layer folder (Rule 4.1/4.2). |
| [YC-II D9 (STEP-15): the 08:00 morning brief is composed and kept, but the dashboard and Ma](05-EXPECTED-VS-ACTUAL.md#surfaces-d9-morning-brief-composed-but-no-surface-reads-it) (P1) | STEP-15 was counted built with its API route but without the surface switch. GeniOS-010's dashboard work did not pick it up. |
| [The home bell shows four made-up system notices to every signed-in customer](05-EXPECTED-VS-ACTUAL.md#surfaces-fake-bell-notices) (P1) | Flagged on 22 Oct (genios-ui-surfaces) and left on main through the GeniOS-010 home rebuild. That rebuild set the 'no made-up number' rule but kept <Notifications/> as it was. |
| [Goals and Screen read cards with their own mapper: 'What to do' shows a verdict code, and ](05-EXPECTED-VS-ACTUAL.md#surfaces-goals-screen-own-card-mapper) (P1) | Goals was built with its own mapper before Cards built readCard. The stand-in brain (02-DASHBOARD-HOME/tools/mock_brain.py) put a sentence where the real brain sends a code, so the render checks passed. |
| [The Mac app on main (0.2.4) and the downloadable 0.2.0 lose presses: 'Not useful' and Done](05-EXPECTED-VS-ACTUAL.md#surfaces-mac-main-silent-refusals) (P1) | The fix exists (rohit/desktop-ux) but was never merged or released. |
| [Three Mac apps in circulation: Rohit's 0.3.4 is unmerged, main is 0.2.4, and the dashboard](05-EXPECTED-VS-ACTUAL.md#surfaces-mac-three-versions) (P1) | Memory dashboard-navigation-22-oct.md says 'origin/main (2edfb86) contains … rohit/desktop-ux'. That is false: it is not an ancestor. |
| [The home claims 'No action bypassed a hard rule' and 'Policy-safe 100%' without measuring ](05-EXPECTED-VS-ACTUAL.md#surfaces-policy-safe-constant-claim) (P1) | The B7 fix kept the constant 100 and changed only the empty case. The home rebuild then promoted the constant into a 'what is working' check. |
| [Question cards and team/verify cards reach only GET /cards; Home 'Today', MCP, the agent A](05-EXPECTED-VS-ACTUAL.md#surfaces-question-and-team-cards-reach-only-the-cards-page) (P1) | STEP-13 (question door) and P4 (situation door) each fixed the queue reader only. The other readers kept private copies of the decision-only predicate, and no guard ties every card reader to one definition of a live card. |
| ['Sync now' runs a second copy of the chain: no funnel numbers, no meeting/team/verify post](05-EXPECTED-VS-ACTUAL.md#cross-sync-now-runs-a-second-chain) (P2) | The funnel, ingestion charge and post-passes were each wired into _run_l2_chain only. The Sync-job pass kept its own hand-written copy of the chain, and nothing tests that the two doors run the same stages. |
| [The L1 folder docs stop at 18 Oct and contradict the code; the rebuild plan Harsh built fr](05-EXPECTED-VS-ACTUAL.md#l1-docs-stale-after-19-oct-rebuild) (P2) | The 19 Oct L1 rebuild was committed outside the GeniOS-008 layer-folder process, so the plan and the code diverged. The next agent reads B2 as still blocked. |
| [The expert pass still stops entirely on a per-call budget refusal (the L2 pass was fixed)](05-EXPECTED-VS-ACTUAL.md#l2-r7-per-call-refusal-stops-pass) (P2) | The 21 Oct audit fixed this in reason/l2 only. |
| [What L3 records of an admitted judgment, including the decision object, is write-only, and](05-EXPECTED-VS-ACTUAL.md#l3-interpretations-decision-object-write-only) (P2) | f3cfd3c6 added a writer to a table already declared write-only, with no reader. |
| [Identity: the exact-key law holds in identity.py, but readers join by name around it, and ](05-EXPECTED-VS-ACTUAL.md#l3-name-only-joins) (P2) | 02-MIGRATION-PLAN.md L3-6 says 'wired'; it is not. |
| [06-CARDS README says the Cards page is 'Not merged, so not live', but dashboard origin/mai](05-EXPECTED-VS-ACTUAL.md#l5-docs-stale-merge-state) (P2) | Harsh merged the branch on 22 Oct after the docs were pushed, and nobody updated the status line. |
| [YC-II D17, D19: the blind benchmark re-run (STEP-19) was never written, and Sole Mate's te](05-EXPECTED-VS-ACTUAL.md#process-d17-d19-step19-and-sole-mate) (P2) | Freezing YC-II (E3) orphaned two accepted-by-default steps without carrying them forward. |
| [GeniOS-009 04-FOR-HARSH plans G1 as migration 0250, which the head already uses](05-EXPECTED-VS-ACTUAL.md#process-g009-migration-numbers-collide) (P2) | A plan table hard-coded migration numbers despite the handover's own rule, and a parallel GeniOS-010 change took 0250. |
| [GeniOS-010 docs and a memory note no longer match the repos](05-EXPECTED-VS-ACTUAL.md#process-geni010-docs-and-memory-drift) (P2) | The 23 Oct memory line recorded a merge without checking ancestry. A later session would assume the Mac fixes are on main. |
| [Goals docs are stale: G0 still marked red, the 0250 number is taken, and the Goals page is](05-EXPECTED-VS-ACTUAL.md#process-goals-docs-stale) (P2) | The G0.1 fix was logged in 03-LOG but never carried into the status table and the handover. |
| [The GeniOS-008 L2 folder stops at 18 Oct; Harsh's L2 rebuild and audit (19–21 Oct) are und](05-EXPECTED-VS-ACTUAL.md#process-l2-docs-stale) (P2) | The rebuild landed directly on harsh/mvp without updating the layer folder, so anyone reading the plan believes L2 is still shadow-only, with G2 unbuilt and no money tool. |
| [L3 was rebuilt and audited (20–21 Oct, now in prod) with no GeniOS-008 layer-3 folder, no ](05-EXPECTED-VS-ACTUAL.md#process-no-layer-3-folder) (P2) | The L3 rebuild and audit landed outside the GeniOS-008 process (Rule 4), so its plan claims were never checked against the code, e.g. 'wired' in L3-1 and L3-6. |
| [reason/expert/triggers.py still says D48 is open and a version change waits for inputs, bu](05-EXPECTED-VS-ACTUAL.md#process-triggers-docstring-says-d48-open) (P2) | The D48 build updated the sweep but not the module docstring that states the rule. |
