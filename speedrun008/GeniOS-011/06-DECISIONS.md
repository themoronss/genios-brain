# 06 · Decisions — what only Rohit (sometimes with Harsh) can decide

**Written for:** Rohit.

Each decision below shows what is true in the code today and the recommended answer. **A decision left unanswered takes its recommended default** (GeniOS-008 `01-RULES`). Nothing here blocks the units Claude is building now. Each decision blocks only the step it names.

## The five that matter this week

1. **Production read permission** (S01.U2). Allow the read-only SQL of [04](04-FOR-HARSH.md), or run it yourself. Without it every cause stays a guess.
2. **Your org's plan** (S02.U1). Put it on a non-expiring internal plan so the sweep runs for it.
3. **Spend for one real-model pass** (S07.U2). The live key and a cap. The first run is ~$2–5 after a 2-call probe.
4. **Goals** (S26.U1).
   - May L2 propose goals from what is in motion? Recommended: **yes, as proposals you approve in one click**.
   - At which grain: one per workstream (e.g. "Antler Singapore admission").
   - Through the brief door that already exists.
5. **Branch protection** (S03.U2). Require green CI on the prod branch, and deploy only green SHAs.


## Decision units in the plan

| Unit | Decision | Done when |
|---|---|---|
| [S03.U3](02-PLAN.md#s03) | One branch, one push owner, repository visibility | speedrun008 is fast-forwarded to origin/harsh/mvp; GeniOS-011 00-START-HERE states the rule (all code lands on speedrun008 through green CI; harsh/mvp only fast-forwards to a green speedrun008 SHA); the push owner is fixed (or a Bash permission rule allows fast-forward pushes to speedrun008); the default branch is moved off main; Rohit decides public vs private (and a CI-annotation token if private). |
| [S09.U3](02-PLAN.md#s09) | History window decision (D16, 365 recommended) | Rohit's number is recorded in GeniOS-011 03-LOG. |
| [S12.U1](02-PLAN.md#s12) | Rohit's L1 contract decisions | Rohit picks the kinds to add (recommended introduction, meeting, investor_interest, application_status), answers E5 (recommended: absence stays L2 tool evidence) and E7 (rule for new→active and the revoke detector), and confirms Plane D owns metric definitions (C4 default); recorded in 03-LOG. |
| [S13.U2](02-PLAN.md#s13) | Bundle road decision | Rohit (with the S12 vocabulary) picks (a) a bundle also carries below-floor extractions and open-lane observations as unqualified members, or (b) the L2 pass also seeds subjects from L3 files that got new events this sweep. |
| [S17.U4](02-PLAN.md#s17) | One authority scale (R16/R17, H9) | Rohit decides R16/R17; Harsh runs the H9 read; Claude builds the chosen remap of rank-100 rows. |
| [S20.U1](02-PLAN.md#s20) | Rohit decides STEP-13b and the claim-check product calls | Rohit chooses merge (port the ladder, dossier enrichment and check.v5 into reason/l2) or retire; answers F302 (recommended: a confirmed answer is a source event), F216, F292, F306; recorded in 03-LOG. |
| [S23.U1](02-PLAN.md#s23) | Rohit's playbook and reply-time decisions | Rohit chooses D1 (review the two sheets line by line, or run labelled 'playbook not yet reviewed'), approves re-pointing B10 to we_evaluate_them, and answers D42/D43/D44; recorded in 03-LOG. |
| [S26.U1](02-PLAN.md#s26) | Rohit's goal decisions | Rohit answers D9 (L2 may propose goals; recommended yes), D10 (child goals under umbrella goals; yes), D11 (door: company_goals direct with the brief kept in sync), D12 (cap, 3 a week), confirms D1/D2/D7/D8, chooses the internal-knowledge 'goal' door, and gives the Rule 1.4 yes to the architecture change; recorded in 03-LOG. |
| [S27.U4](02-PLAN.md#s27) | Rohit reads and decides the proposals | Rohit approves or rejects the drafted goal lines in production (read via S01's brief query). |
| [S33.U1](02-PLAN.md#s33) | Rohit defines value and the metrics | Rohit defines recovered value and the anti-double-count rule (D4), the AER/HIR formulas, and whether Agents unlock. |
| [S37.U1](02-PLAN.md#s37) | Channel and provider | Rohit confirms B3's default (email to <founder Gmail> first, Slack later) and the transactional provider account. |
| [S38.U1](02-PLAN.md#s38) | Go to merge desktop-ux | Rohit approves the fast-forward of origin/rohit/desktop-ux (ed2724d) into dashboard main. |
| [S39.U3](02-PLAN.md#s39) | Placeholder pages | Rohit decides which locked pages stay visible and which leave the nav. |
| [S40.U1](02-PLAN.md#s40) | Rohit's learning decisions | Per ledger keep-with-reader or retire; which preference kinds the founder can state (Atlas L7 #1); ADR-10; D13 (arm calibration or not). |
| [S42.U2](02-PLAN.md#s42) | Receipt label decision | Rohit decides whether to relabel Receipt.layer; until then counts never filter by the label. |
| [S43.U2](02-PLAN.md#s43) | STEP-19 and Sole Mate placement | Rohit decides that the blind benchmark re-run (D17) is GeniOS-011's closing step and where Sole Mate's tenant (D19) goes. |

## Every open decision, with what is true today and the recommended answer

<a id="l2-d1-founder-playbooks-unreviewed-compiled-lane-refuses"></a>
### GeniOS-008 D1 / YC-II D45, D3: founder playbooks are unreviewed; the compiled lane refuses every Founder Office situation

`l2-d1-founder-playbooks-unreviewed-compiled-lane-refuses` · **P0** · partial · owner **rohit** · decision · step **S23**

- **Expected:** D1 default: 'Run labelled until you review' — fundraising/programme advice runs with 'playbook not yet reviewed', for Rohit's org. _(source: speedrun008/GeniOS-008/03-QUESTIONS.md D1; YC-II W27/06-DECISIONS.md D3, D45)_
- **Actual:** The review sheets are untouched: investor 146 lines and program 121 lines, all with decision ''. All 6 Founder Office capabilities are status: draft (Admin's 59 are stable). The compiled pack lane raises UnsupportedCoverage('unreviewed') when no routed capability is admitted, so fundraising, programme, intro, compliance, hiring and meetings situations produce no compiled card. Only the expert dossier (R-7) and the L2 dossier label it 'not yet reviewed' and continue, and both are per-tenant switches that default off. The default is taken only on the expert path.
- **Evidence (measured):** `speedrun008/YC-II W27/review/investor.review.yaml (146× `decision: ''`), program.review.yaml (121× `decision: ''`)`; Domain Expertise/Founder Office Expertise/capabilities/01-fundraising/investor-relations/capability.yaml:19 status: draft; 02-programs-and-applications/program-applications/capability.yaml:25 status: draft (6/6 draft); Admin Expertise capabilities 59× status: stable; `genios_engine/packs/compiler/capability_resolver.py:815-823 (raise UnsupportedCoverage 'unreviewed')`; genios_engine/reason/domain_shadow.py:921-923 ('until the founder's review, a fundraising situation on the pilot is refused as unreviewed'); `genios_engine/reason/expert/dossier.py:535-541 (expert path labels '(not yet reviewed)')`
- **What Rohit sees:** Investor, incubator/accelerator (e.g. the Antler Singapore admission), intro, DPIIT/compliance and hiring files get no compiled card. They can only become a card if expert_review or l2_cards is on for the org, which explains fewer cards and missing fundraising cards.
- **Where the mistake was:** D1's default ('run labelled') was recorded as taken, but it was implemented only in the expert dossier. The compiled lane kept the D45 refusal.
- **Fix:** Rohit chooses one of two options. (a) Review the two sheets line by line (accept/edit/reject). (b) Confirm D1's default, in which case Claude makes the compiled lane admit draft Founder Office capabilities for Rohit's org labelled 'playbook not yet reviewed' (mirroring card_builder.PLAYBOOK_NOT_YET_REVIEWED) instead of refusing them.
- **Verified:** confirmed by the skeptic (Every point checks out. investor.review.yaml has 146 of 146 `decision: ''` and program.review.yaml has 121 of 121. All 6 Founder Office capability.yaml files are `status: draft`; investor-relations has reviewed_by "" and review_status: unreviewed at :148-150. All 59 Admin capabilities are stable and approved. capability_resolver.py:770-775 skips an unadmitted capability when require_admission is set, and the live compile passes require_admission=True (domain_shadow.py:1585). With no capability left, :815-823 raises UnsupportedCoverage('unreviewed'). The '(not yet reviewed)' label exists only in reason/expert/dossier.py:535-541. The L2 dossier carries it only because it embeds the expert file dossier (reason/l2/dossier.py:167-168; sweep.py:253 build_dossier).)

<a id="goals-decision-goal-granularity-and-door"></a>
### Decision needed: may L2 propose goals, at what granularity, and through which door

`goals-decision-goal-granularity-and-door` · **P1** · missing · owner **rohit** · decision · step **S26**

- **Expected:** One recorded answer before G1 is built, because it changes G1's schema and the G3 prompt. _(source: speedrun008/GeniOS-009/08-DECISIONS.md D2, D7 (defaults only); GeniOS-010/03-GOALS/README.md D-010-G2)_
- **Actual:** D7 defaults to 'yes, as proposed', but names only the drafter. Nothing decides: (a) whether the R-9 L2 judgment may propose goals; (b) granularity: an umbrella goal ('Get into accelerator programs') with child goals per workstream ('Antler Singapore admission') through parent_goal_id, or links only; (c) the door: keep the brief as the only door and add a proposal jsonb to company_brief_lines, or let L3 write company_goals(status='proposed') directly with POST /v1/goals/{id}/approve; (d) a weekly cap on new proposals.
- **Evidence (doc_claim):** `speedrun008/GeniOS-009/08-DECISIONS.md D7`; `speedrun008/GeniOS-009/STEP-G1-the-goal-object.md §2.1 ('The brief stays the door')`; `speedrun008/GeniOS-010/03-GOALS/README.md §4 D-010-G2`
- **Fix:** Rohit answers D9 (L2 may propose: yes or no), D10 (child goals under umbrella goals: yes or no), D11 (door: brief plus proposal jsonb, or company_goals direct), and D12 (cap, default 3 a week). Recommended defaults: yes; yes; company_goals direct with the brief kept in sync; 3 a week.
- **Blocked on:** Rohit
- **Verified:** confirmed by the skeptic (08-DECISIONS D7's default names only the drafter, and STEP-G1 §2.1 says 'The brief stays the door'. D-010-G2 assumes parent_goal_id children. No recorded answer covers (a)–(c). On (d): the drafter path already has a de facto cap, at most 8 goal proposals per weekly draft (brief_drafter.py:39,180), plus store dedupe and the rejected-line quiet window (company_brief_store.py:107-117). Nothing would cap an L2 proposer. This needs Rohit's product decision.)

<a id="goals-g009-d1-d2-d8-goal-model-defaults-unbuilt"></a>
### GeniOS-009 D1, D2, D8: the goal model decisions are on their defaults, and nothing they unblock (G1, G6) is built

`goals-g009-d1-d2-d8-goal-model-defaults-unbuilt` · **P1** · missing · owner **rohit** · decision · step **S26**

- **Expected:** D1 department = live domain. D2 L3 holds a company_goals object, with Plane D reading a pinned copy. D8 board grouped by goal, then lane, with 'Not linked to a goal' counted. _(source: speedrun008/GeniOS-009/08-DECISIONS.md D1, D2, D8; 09-HARSH-HANDOVER.md §4; 04-FOR-HARSH.md group table)_
- **Actual:** Goals exist only as free-text company_brief lines in section 'goals'. There is no company_goals table and no goal_refs/goal_impacts anywhere (migrations stop at 0250_screen_followup_read_path). The dashboard already renders 'Cards not linked to a goal yet' for every card.
- **Evidence (measured):** `genios_engine/contracts/company_brief.py:38, 55 (section 'goals' = 'Goals now')`; `grep company_goals|goal_refs|goal_impacts in genios_engine and migrations: 0 hits`; `dashboard origin/main src/app/dashboard/cards/page.tsx:925; src/product/internal/dashboard/goals/live.ts:13`
- **What Rohit sees:** No card carries a goal, and the board cannot group by goal.
- **Fix:** Rohit confirms D1/D2/D8, or the defaults stand per 08-DECISIONS. Claude/Harsh build G1 (company_goals + revisions, GET /v1/goals) and then G2–G6 in shadow behind their switches.
- **Depends on:** [l2-a2-a3-per-type-cutover-not-built](#l2-a2-a3-per-type-cutover-not-built)
- **Verified:** confirmed by the skeptic (contracts/company_brief.py:37-38 SECTIONS includes 'goals', titled 'Goals now' at :55. A grep for company_goals|goal_refs|goal_impacts in genios_engine and migrations finds nothing. The last migration is 0250_screen_followup_read_path.sql. Dashboard origin/main src/app/dashboard/cards/page.tsx:925-926 hard-codes 'Not linked to a goal yet'. src/product/internal/dashboard/goals/live.ts:1-14 says target, owner, progress and linked cards are not there yet (G1, G5, G4), and every open card sits under 'Cards not linked to a goal yet'.)

<a id="goals-g009-d7-inferred-goals-only-from-brief-patterns"></a>
### GeniOS-009 D7: inferred goals come only from the brief drafter's memory patterns, never from L3 situations, so the Antler admission never becomes a proposed goal

`goals-g009-d7-inferred-goals-only-from-brief-patterns` · **P1** · missing · owner **rohit** · decision · step **S26**

- **Expected:** D7 default: GeniOS may propose goals it infers, as 'proposed', shown for approval, never active without a human. _(source: speedrun008/GeniOS-009/08-DECISIONS.md D7)_
- **Actual:** The only proposer is reason/brief_drafter.py (section 'goals'), fed by memory PATTERNS, never by the graph's situations. No unit infers a goal from an L3 situation or an L2 judgment. The 'or later L2's' path has no step.
- **Evidence (mixed):** `genios_engine/reason/brief_drafter.py:4, 61 (drafts goals among brief sections)`; `genios_engine/contracts/company_brief.py:38`; `speedrun008/GeniOS-009/08-DECISIONS.md D7 ('the brief drafter already proposes ... same door')`
- **What Rohit sees:** Antler Singapore (Theresa) and similar admissions sit in the graph but never become goals, so no card can say which goal it moves.
- **Fix:** Rohit confirms D7 and whether L2 may propose goals. Then add a G1 follow-up: an admitted L2 judgment whose kind is program/investor with a stated deadline or outcome yields a `proposed` goal through the same accept door.
- **Depends on:** [goals-g009-d1-d2-d8-goal-model-defaults-unbuilt](#goals-g009-d1-d2-d8-goal-model-defaults-unbuilt)
- **Verified:** confirmed by the skeptic (reason/brief_drafter.py:1-7 proposes from memory PATTERNS and never reads a message. Its prompt (:55-61) lists goals among the sections. The only other brief proposer is reason/expert/kind_proposal.py:131-138, which proposes section='in_motion' lines (work kinds) from an expert review, never 'goals'. capture/internal_knowledge.py:92 maps an uploaded doc tagged goals/okr to kind 'goal'; that is a manual upload, not inference. No unit infers a goal from an L3 situation or an L2 judgment. GeniOS-009 08-DECISIONS.md:16 D7 names the brief drafter as 'same door'.)

<a id="l2-b10-vendor-renewal-gate-can-never-fire"></a>
### YC-II STEP-18 B10 / s18-D2 (+F56): the Admin vendor-renewal situation is gated on a value the extractor never writes

`l2-b10-vendor-renewal-gate-can-never-fire` · **P1** · broken · owner **rohit** · decision · step **S23**

- **Expected:** A vendor's renewal or price-change notice (golden F56: login vendor renews at 32% more) reaches a renewal card. _(source: speedrun008/YC-II W27/STEP-18-TO-BUILD-known-bugs.md B10 ('left — a decision'); 07-WHAT-IS-DONE.md §9 s18-D2; tests/replays/specs/founder/F56.json)_
- **Actual:** vendor-relationship-live.yaml requires relationship.direction = outbound. The only writer of relationship.direction accepts just they_evaluate_us / we_evaluate_them / peer, so the situation can never match. F56 is one of the 4 failing golden cases: since B2 (19 Oct) the notice passes the junk gate but reasons only as a generic unanswered email (reply/wait).
- **Evidence (measured):** Domain Expertise/Admin Expertise/capabilities/05-contract-and-vendor-administration/renewal-management/situations/vendor-relationship-live.yaml:35-38 (when relationship.direction = outbound); `genios_engine/context/pipeline.py:419 (_RELATIONSHIP_DIRECTIONS = they_evaluate_us, we_evaluate_them, peer)`; `genios_engine/context/pipeline.py:2114-2118 (only those values are written)`; `tests/replays/specs/founder/F56.json:155 (blocked_on: no vendor-renewal kind or play)`
- **What Rohit sees:** No Admin card ever says a tool renews on a date at a higher price, so a live Admin domain loses its renewal cards.
- **Where the mistake was:** The corpus gate was authored against a vocabulary (outbound) the extractor never had. The fix was parked as 'a decision' in STEP-18 and never asked.
- **Fix:** Rohit, as corpus owner (D45), approves re-pointing the gate to `we_evaluate_them` (the supplier reading). Claude changes the YAML gate, adds a vendor-renewal play for the 'vendor' kind (D18), and re-records F56.
- **Verified:** confirmed by the skeptic (vendor-relationship-live.yaml:35-38 requires relationship.direction = outbound. The only writer of the fact is context/pipeline.py:2114-2118, which writes only values in _RELATIONSHIP_DIRECTIONS = {they_evaluate_us, we_evaluate_them, peer} (:419). No 'outbound' mapping exists for this field in context/ or packs/. capture/structured/apply.py:99 carries an edge direction, not this fact. F56.json:155 blocked_on matches, and 01-AS-IS-CARDS.md:124 lists F56 as failing and silent.)

<a id="l2-f302-confirmed-answer-gets-no-card"></a>
### YC-II F302 (+F216, F292, F306): claim-check product calls still open; a move resting on the founder's confirmed answer is held with no card

`l2-f302-confirmed-answer-gets-no-card` · **P1** · broken · owner **rohit** · decision · step **S20**

- **Expected:** Rohit decides whether a confirmed answer counts as a source event (F302), whether the quote rule covers wait/nothing/blocked verdicts (F216), how an answered ask is found (F292), and the F15 label rule (F306). _(source: speedrun008/YC-II W27/03-FINDINGS.md F216, F292, F302, F306; 07-WHAT-IS-DONE.md §9)_
- **Actual:** Still as found. A judgment whose facts cite no event gets NO_EVENT_BP = 4,000, under the 4,500/6,000 floors, so a move resting only on the founder's 'Yes' DEFERs to monitor with no card. Confidence comes from the count of cited source events only.
- **Evidence (mixed):** `genios_engine/reason/expert/decide.py:170-172 (ONE_EVENT_BP = floor; NO_EVENT_BP = 4_000)`; `genios_engine/reason/expert/decide.py:482-487 (_confidence: no events → NO_EVENT_BP)`; `speedrun008/YC-II W27/03-FINDINGS.md:333 F302, :237 F216, :323 F292, :337 F306 (all 'Rohit's call')`
- **What Rohit sees:** After Rohit answers a question card, the move that answer unlocks can silently become no card (monitor lane).
- **Fix:** Rohit answers F302 (recommended: a confirmed answer is a source event for the move it confirms) and F216/F292/F306. Claude then adds the answer ids to the evidence refs that _confidence counts, with a mutation test.
- **Verified:** confirmed by the skeptic (decide.py:170-172 has ONE_EVENT_BP = DEFAULT_DECISION_FLOOR_BP (6,000, reason/output_lane.py:51) and NO_EVENT_BP = 4,000, below DEFAULT_CONFIDENCE_FLOOR_BP 4,500 (decision_maker.py:108). is_event (:179-181) counts only ids without a ':' kind, so a founder answer or reading id is not an event. _confidence (:482-493) returns NO_EVENT_BP when no events are cited. The last commits touching decide.py (245f2bc3, 4b9f42b4, e8241798) did not change this. 03-FINDINGS.md:333 F302, :237 F216, :323 F292 and :337 F306 are all still open and 'Rohit's call'.)

<a id="l2-founder-playbooks-gated-on-unread-review"></a>
### The investor and programme playbooks were gated on a 267-line YAML review that was never done, and the Sales investor copy was retired

`l2-founder-playbooks-gated-on-unread-review` · **P1** · built, not live · owner **rohit** · decision · step **S23**

- **Expected:** A fundraising founder's main workstreams (investors, accelerators such as Antler) get expert cards from the Founder Office corpus, switched on for Rohit's org. _(source: speedrun008/YC-II W27/06-DECISIONS.md:52 (D45); memory/card-quality-diagnosis.md; memory/admin-domain-only.md (D2))_
- **Actual:** D45 admits a playbook only after Rohit accepts every line. review/investor.review.yaml has 146 lines and review/program.review.yaml has 121, and every one has decision: ''. domain_shadow.py says that until the founder's review a fundraising situation on the pilot is refused as 'unreviewed'. Sales' investor relations were retired. On 22 Oct Rohit removed Founder Office from the dashboard, and goals/live.ts folds founder_office into Admin.
- **Evidence (measured):** `speedrun008/YC-II W27/review/investor.review.yaml (146 lines with decision: '')`; `speedrun008/YC-II W27/review/program.review.yaml (121 lines with decision: '')`; `speedrun008/YC-II W27/06-DECISIONS.md:52 (D45 'Waiting for your review')`; `genios_engine/reason/domain_shadow.py:918-927, :1011-1013`; `dashboard origin/main src/product/internal/dashboard/goals/live.ts:25`
- **What Rohit sees:** On the compiled lane every investor or programme situation ends 'unreviewed' and gets no card, unless the R-7 expert covers the file. That includes the kind of situation the Antler admission is.
- **Where the mistake was:** A plan gate put a 267-line review on the founder before his most valuable cards could exist, and the plan never flagged it as blocking.
- **Fix:** Rohit decides between two options: review only the lines a card prints, or admit on use with per-card feedback. Until then, the dashboard says fundraising is waiting for his review.
- **Blocked on:** set transaction read only; select outcome, reason, count(*) from situation_outcomes where org_id='<ORG>' and last_seen_at >= '2026-10-18' group by 1,2 order by 3 desc;
- **Verified:** confirmed by the skeptic (investor.review.yaml has 146 entries and program.review.yaml has 121, each with decision: '' (the files are 1,374 and 1,201 text lines). D45 at 06:52 says 'Waiting for your review'. domain_shadow.py:915-925 retires the Sales copy and refuses fundraising as 'unreviewed'. All 36 Founder Office Expertise documents are status: draft with reviewed_by: ''. Dashboard goals/live.ts:25 FOLDED_INTO_ADMIN includes founder_office.)

<a id="l2-llm-decider-without-fallback-in-production"></a>
### The LLM decision maker ran in production for every org with no fallback, and a spend limit then stopped all cards from 25 Sep

`l2-llm-decider-without-fallback-in-production` · **P1** · partial · owner **rohit+harsh** · decision · step **S02**

- **Expected:** A measurement mode is not the production mode. A model outage or a budget stop degrades output; it does not silence it (DECISION #5, option C). _(source: memory/why-no-cards-since-25-sep.md)_
- **Actual:** Measured 1 Oct: GENIOS_L4_LLM_DECISION_MAKER=true with no org allowlist, and the Anthropic spend limit refusing every call since 25 Sep 11:09 UTC. llm_decision_maker.py:20 says 'Failure is DEFER, never the formula', giving 2,669 defers, 0 decisions and 0 signals. Two confident guesses were wrong before the stages were measured. The code default is now off (config.py:110), but the production env value is not recorded, and B9's 400-a-day cap has never bound because the count lives in one process (F274).
- **Evidence (mixed):** `memory/why-no-cards-since-25-sep.md; memory/measure-which-things-stopped.md`; `genios_engine/reason/llm_decision_maker.py:20`; `genios_engine/platform/config.py:110-111`; `speedrun008/YC-II W27/03-FINDINGS.md:295 (F274 open)`; `memory/production-funnel-2026-10-04.md (57% DEFER, about 3,600 calls a day for 6 cards)`
- **What Rohit sees:** No cards from 25 Sep to about 3 Oct; after that, flip-flopping defers and about 3,600 model calls a day for 6 cards.
- **Where the mistake was:** Shipped the measurement mode as the production mode, and guessed the cause twice before measuring which stage had stopped.
- **Fix:** Harsh states the production env value. Rohit picks the cap and the dollar governor default (F274). 'Which stage stopped' stays the first diagnostic step.
- **Blocked on:** The production env value of GENIOS_L4_LLM_DECISION_MAKER (Harsh); set transaction read only; select date_trunc('day',created_at)::date d, purpose, model, count(*), sum(output_tokens) from llm_costs where org_id='<ORG>' and created_at >= '2026-10-10' group by 1,2,3 order by 1;
- **Verified:** confirmed by the skeptic (llm_decision_maker.py:20 says 'Failure is DEFER, never the formula'. config.py:110 l4_llm_decision_maker defaults to False, and :111 orgs is empty (empty = every org when on). _take_budget keeps the 400 cap in the in-process _calls_by_org_day (llm_decision_maker.py:216-228). F274 is open (03:295). Memory why-no-cards (2,669 defers, 0 decisions) and production-funnel (57% DEFER, ~3,600 calls a day). The production env value is not in the repo.)

<a id="l2-step13b-built-on-local-branches-never-merged"></a>
### YC-II D63/D64 (STEP-13b): the GeniOS Engine in the expert's hands was built but sits on local-only branches; F63/F219/F239/F266 stay open

`l2-step13b-built-on-local-branches-never-merged` · **P1** · built, not live · owner **rohit** · decision · step **S20**

- **Expected:** D64 (Rohit, 12 Oct: go): the expert's dossier carries Plane D Domain Expertise (capabilities and playbook claims, citable), the reasoning units' measurements, and the company's own record (D63: F52's question the founder already answered on another file). Cheap models first, Opus only when needed. _(source: speedrun008/YC-II W27/06-DECISIONS.md D63, D64; STEP-13b-TO-BUILD-the-engine-in-the-experts-hands.md; GeniOS-008 layer-2-reasoning/00-START-HERE.md L2-B3 ('Plane D domain packages for a seed subject are not folded in yet'))_
- **Actual:** 43 STEP-13b commits (≈3,000 insertions over 24 engine files, base c1df07ac) are on local branches yc2w27-s13b (1eb37eb1), yc2w27-haikufix (60f716a3) and yc2w27-int13b (42d61e8f, merge of s13b). None is an ancestor of the production head 0cc8d83c, none is on origin/speedrun008, and no origin branch holds them. Golden F63 fails with blocked_on 'owner STEP-13b'. The s13b decisions (Opus rung, ladder start, s13b-D8 +$15) are unanswered.
- **Evidence (measured):** git: yc2w27-s13b 1eb37eb1 / yc2w27-int13b 42d61e8f not ancestors of HEAD 0cc8d83c; `git branch -r` lists no 13b branch; origin/speedrun008 does not contain 1eb37eb1; `git diff --stat c1df07ac yc2w27-s13b -- genios_engine: 24 files, 2997+/266-`; `tests/replays/specs/founder/F63.json:129 (blocked_on ... owner STEP-13b)`; `speedrun008/YC-II W27/03-FINDINGS.md F219, F239, F266 (open → STEP-13b)`
- **What Rohit sees:** The expert/L2 judgment cannot cite domain expertise or what the company said of itself on another file. So it asks questions the founder already answered (F52/D63) and misses the ask for a missing address (F63), which reads as weak or 'no reasoning'.
- **Where the mistake was:** STEP-13b was built on 17 Oct and left unpushed. GeniOS-008 started on 18 Oct and froze YC-II W27 (03-QUESTIONS E3), stranding finished work. No log names the branches.
- **Fix:** Rohit decides: port STEP-13b's dossier enrichment into reason/l2 (the R-9 dossier, as L2-B3's unfinished half), or abandon it. If he ports it, Claude rebases the units onto the head file by file, re-records with the ideal reader, and closes F63/F219/F266.
- **Verified:** confirmed by the skeptic (Measured with git. yc2w27-s13b is 1eb37eb1, yc2w27-haikufix 60f716a3, yc2w27-int13b 42d61e8f. `git merge-base --is-ancestor` is false for all three against HEAD 0cc8d83c and against origin/speedrun008. `git branch -r --contains 1eb37eb1` is empty. c1df07ac..yc2w27-s13b holds 43 non-merge commits, and `git cherry HEAD yc2w27-s13b c1df07ac` gives 43 '+' (no patch-equivalent in HEAD). The diff is 24 engine files, +2997/-266. New files such as reason/expert/ladder.py, file_units.py, file_engine.py, contracts/engine_read.py, contracts/model_ladder.py and context/company_record.py do not exist in HEAD. F63.json:129 blocked_on names owner STEP-13b. s13b-D8 (+$15) is open as D81 on the branch's 06-DECISIONS ('Open — Rohit's call'). Extra: the branch adds migrations/0250_expert_review_attempts.sql, which collides with HEAD's 0250_screen_followup_read_path.sql. Merging it now needs a renumber.)

<a id="process-repo-is-public-with-real-data"></a>
### The production repository is public and carries Rohit's personal address, the production org id and real counterparties' names

`process-repo-is-public-with-real-data` · **P1** · broken · owner **rohit** · decision · step **S03**

- **Expected:** Production code, plan documents with production measurements, and real contacts are not publicly readable. _(source: Rohit's ownership of the data (no explicit doc). The Dockerfile already keeps tests/ out of the image for leaking scratch URLs (Dockerfile:79-81).)_
- **Actual:** The GitHub API reports themoronss/genios-brain as visibility=public, private=false. In the tree, <founder Gmail> appears in 33 files, <ORG> in 46, and 'Theresa' in 27. CI logs and annotations are publicly readable, and the sessions rely on that.
- **Evidence (measured):** `GitHub API /repos/themoronss/genios-brain: visibility public, private false`; grep -rl '<founder Gmail>' . (excluding .git) → 33 files; '<ORG>' → 46; 'Theresa' in speedrun008+tests → 27
- **Fix:** Rohit decides whether to make the repository private. If yes, add a GitHub token for reading CI annotations (memory notes rely on the public API). Scrub real addresses from new plan documents.
- **Verified:** confirmed by the skeptic (GitHub API /repos/themoronss/genios-brain returns visibility=public, private=false. In origin/harsh/mvp, '<founder Gmail>' appears in 33 files and '<ORG>' in 46. 'Theresa' appears in 27 files under speedrun008+tests and in 80 files repo-wide. The run annotations (check-runs/*/annotations) were readable unauthenticated in this audit. The secret-pattern hits were only a dummy test URL (tests/test_scripts_db_guard.py:142); .env.example was not read. The dashboard repo is private: the unauthenticated API returns 404.)

<a id="process-step13b-ladder-left-unpushed"></a>
### The only expert pass that met its live target (STEP-13b ladder) exists only on local, unpushed branches

`process-step13b-ladder-left-unpushed` · **P1** · built, not live · owner **rohit** · decision · step **S20**

- **Expected:** Built work is reused, not rebuilt. When STEP-13b ships, the expert runs Haiku first, repairs once and climbs to Sonnet, with the live scorecards kept in the repo. _(source: speedrun008/GeniOS-008/01-RULES.md Rule 2.6; 08-FOR-HARSH-deploy-and-after.md §0.5 ('When STEP-13b ships…'))_
- **Actual:** yc2w27-s13b (44 commits beyond production) and yc2w27-haikufix (50) are not on origin. They hold the ladder (9858d62b, 9ff24d47), the dossier v2 and check v5, and the 17 Oct live pass: Haiku held share 18.5% (79% before), precision 0.915, recall 0.509, 190 calls, $4.963. Their scorecards are under speedrun008/YC-II W27/scores/, which does not exist on the production branch. No GeniOS-008, 009 or 010 document mentions STEP-13b. Its migration is numbered 0250, which production now uses for another file.
- **Evidence (measured):** `git branch -r | grep -iE 's13b|haikufix' → none`; `git rev-list --count origin/harsh/mvp..yc2w27-s13b → 44; ..yc2w27-haikufix → 50`; `git show -s 73d9f804 (live pass numbers)`; `git ls-tree -d origin/harsh/mvp 'speedrun008/YC-II W27/' → baseline, review (no scores)`; `grep -rn 13b speedrun008/GeniOS-008 GeniOS-009 GeniOS-010 → no match`; `git ls-tree yc2w27-s13b migrations/ → 0250_expert_review_attempts.sql vs prod 0250_screen_followup_read_path.sql`
- **What Rohit sees:** If expert_review is on in production, R-7 runs the pre-ladder expert, whose Haiku reviews were held 79% of the time, so a held review is a file with no card. The work exists only on one laptop.
- **Where the mistake was:** When the programme moved to GeniOS-008 on 18 Oct, STEP-13b was neither pushed, merged nor retired in writing.
- **Fix:** Rohit decides whether to merge or retire it. To merge: push the branch, renumber 0250 to the next free number, merge into speedrun008 on top of Harsh's rebuild, re-record cassettes, and keep the scorecards. To retire: record it in GeniOS-008 03-LOG and push the branch for safekeeping.
- **Verified:** confirmed by the skeptic (The GitHub branches API lists 10 remote branches (antler-inception, claude/notion-file-reference-RwWqb, g010-desktop, harsh/mvp, main, mvp, rohit-yc-brain, speedrun008, supabase, y-combinator-w27), and none is a 13b/haikufix branch. origin/harsh/mvp..yc2w27-s13b is 44 commits and ..yc2w27-haikufix is 50. 9858d62b (the ladder) and 9ff24d47 (golden_eval ladder) are also on the local-only yc2w27-int13b (43 ahead), yc2w27-left13 (50) and yc2w27-left14 (62). d9f19991 names expert-review.v5, dossier.v2 and check.v5. The 73d9f804 numbers match: held 18.5% against 79%, precision 0.915, recall 0.509, 190 calls, $4.963. 'speedrun008/YC-II W27/' on harsh/mvp has only baseline/ and review/, while s13b also has scores/. No GeniOS-008/009/010 .md mentions STEP-13b; the only '13b' hit is an unrelated string in a JSON measurement. The 0250 collision is confirmed.)

<a id="goals-g009-d4-macv-ledger-value-rule"></a>
### GeniOS-009 D4: what counts as recovered value in macv_ledger (the North Star) is undecided, and the table has no writer

`goals-g009-d4-macv-ledger-value-rule` · **P2** · missing · owner **rohit** · decision · step **S33**

- **Expected:** Rohit defines the value rule. G9 writes goal progress, and money value only after D4. _(source: speedrun008/GeniOS-009/08-DECISIONS.md D4)_
- **Actual:** macv_ledger (migration 0012) has no writer. The API returns value_state 'unavailable_macv_ledger_has_no_writer'.
- **Evidence (measured):** `genios_engine/api/intelligence_routes.py:795-815`; `migrations/0012_l6_feedback.sql`
- **Fix:** Rohit defines the rule (e.g. distinct-deal SUM + non-deal COUNT). Claude adds one writer from verified outcomes (G9).
- **Verified:** confirmed by the skeptic (api/intelligence_routes.py:795-815 returns value_recovered_inr None and value_state 'unavailable_macv_ledger_has_no_writer'. A grep for macv_ledger finds only migrations 0012 and 0033, platform/table_coverage.py, the account_routes.py deletion list and intelligence_routes.py. There is no insert anywhere.)

<a id="l1-e1-bundles-read-only-in-shadow"></a>
### Bundles (E1) are written every sweep, but their only reader is the L2 pass, which is off unless l2_reasoning is on

`l1-e1-bundles-read-only-in-shadow` · **P2** · shadow / switched off · owner **rohit+harsh** · decision · step **S25**

- **Expected:** The bundle is the contract L2 reasons over. _(source: GeniOS-008/00-ARCHITECTURE.md 'The flow'; 01-RULES (built beside, switched per situation type))_
- **Actual:** Bundles are written (publisher.py:1247-1251; finalize.py:138; routes.py:94,123; upload_routes.py:148). They are read only by reason/l2 (inputs.read_subjects, inputs.py:208-218), and l2_pass returns 'skipped' unless FEATURE_L2_REASONING is active (reason/l2/sweep.py:176-178). l2_reasoning and l2_cards are OFF by default (platform/l4_activation.py:115-123). Today's cards still come from the old path.
- **Evidence (measured):** `genios_engine/capture/esqe/publisher.py:1247-1251`; `genios_engine/reason/l2/inputs.py:208-218`; `genios_engine/reason/l2/sweep.py:176-178`; `genios_engine/platform/l4_activation.py:115-123`
- **What Rohit sees:** What L1 now carries (ball_in_court, coverage, conflicts) does not reach any card yet.
- **Fix:** This is the L2 cutover decision: switch l2_reasoning (then l2_cards) on for Rohit's org once the golden comparison of the new path against the old passes. L1 needs nothing more here.
- **Blocked on:** Production: select feature, enabled_at, disabled_at from l4_activation where org_id='<ORG>'; select count(*), max(created_at) from signal_bundles where org_id='<ORG>';
- **Verified:** confirmed by the skeptic (Writers: publisher.py:1239-1251 through finalize.py:138, routes.py:94/123 and upload_routes.py:148. Readers: only reason/l2 (inputs.py:212 read_bundles_since; sweep.py:107-108 read_bundles_by_id). reason/bundle/* is the unrelated ReasoningBundle. l2_pass returns skipped without l2_reasoning (sweep.py:176-178). l2_reasoning and l2_cards are off unless a tenant has an l4_activation row (l4_activation.py:111-122, 454). Also see the bundle entity-join defect (bundle.py:74 reads a non-existent `entities`). Prod SQL: select feature from l4_activation where org_id='<ORG>' and disabled_at is null;)

<a id="l1-e10-metric-definitions-owner"></a>
### Business metric definitions (what 'sales' means: booked, collected or signed) have no owner (E10)

`l1-e10-metric-definitions-owner` · **P2** · missing · owner **rohit** · decision · step **S12**

- **Expected:** Metric definitions exist and an owner (L1 or Plane D) is confirmed. _(source: 02-PLAN E10)_
- **Actual:** No metric-definition object exists in capture/. The only MetricDefinition is L3's analytic sampler (context/analytic/history.py, sampler.py:342), which is a different concept. 02-PLAN says the owner is still to be confirmed.
- **Evidence (mixed):** `genios_engine/context/analytic/sampler.py:342`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/02-PLAN.md Group E status E10`
- **Fix:** Rohit names the owner (Plane D recommended, since it is domain expertise), then it is built there.
- **Verified:** confirmed by the skeptic (capture/ has no business-metric definition object. MetricDefinition exists only in context/analytic (history.py, sampler.py:342). platform/metrics.py is GeniOS's own product-analytics dictionary (accounts, MRR, LLM cost), not the tenant's definition of 'sales'. 02-PLAN.md:102: owner still to confirm.)

<a id="l1-e5-absence-signals"></a>
### Absence-derived signals (no reply, no owner, no approval, no delivery) are not L1 signals (E5)

`l1-e5-absence-signals` · **P2** · missing · owner **rohit** · decision · step **S12**

- **Expected:** L1 publishes absence-derived signals, each carrying the coverage receipt that makes it sayable. _(source: GeniOS-008/00-ARCHITECTURE.md 'Inside L1'; 02-PLAN E5)_
- **Actual:** SignalType has no absence member (signal.py:210-300). Absence is computed as L2 tool evidence (reason/l2/tools.py:47-69, tool:whose_turn and tool:unanswered_inbound) and in L3 (context/waiting.py). L2's EXPECTED_REPLY_ABSENT trigger comes only from expert-pass file kinds (reason/l2/sweep.py:159-166). 02-PLAN E5 is marked as a decision for Rohit.
- **Evidence (measured):** `genios_engine/contracts/signal.py:210-300`; `genios_engine/reason/l2/tools.py:47-69`; `genios_engine/reason/l2/sweep.py:159-166`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/02-PLAN.md Group E status E5`
- **What Rohit sees:** A silence never creates a bundle, so 'they never replied' surfaces only through the old expert-pass path.
- **Fix:** Rohit decides whether absence stays in L2 tools or joins L1's taxonomy. If it joins L1, Claude adds the members with their coverage-receipt requirement (signal.py:809-834 already refuses an absence with no coverage).
- **Blocked on:** Rohit's E5 decision
- **Verified:** confirmed by the skeptic (SignalType has no absence member (signal.py:239-300). Absence exists as L2 tool evidence: tool:whose_turn and tool:unanswered_inbound (reason/l2/tools.py:44-70). EXPECTED_REPLY_ABSENT is produced only by _trigger_of from expert-handed file kinds (sweep.py:159-166), and it is the only use of the constant outside its definition. context/waiting.py exists. 02-PLAN.md:99 marks E5 as Rohit's decision.)

<a id="l1-e5-e7-absence-signals-and-lifecycle-states"></a>
### L1 E5, E7: two of Rohit's L1 decisions are unanswered (absence as L1 signals; 'new'/'revoked' signal states)

`l1-e5-e7-absence-signals-and-lifecycle-states` · **P2** · missing · owner **rohit** · decision · step **S12**

- **Expected:** Atlas v2 / Blueprint: absence-derived signals published by L1 with a coverage receipt (E5). A signal lifecycle with new and revoked (E7). _(source: speedrun008/GeniOS-008/layer-1-enterprise-signals/02-PLAN.md Group E rows E5, E7 and status lines 99-101)_
- **Actual:** SIGNAL_STATES = {active, superseded, expired, resolved} (DB check constraint the same). Absence is computed only as L2 tools / context waiting. The questions ('keep absence in L2's tools or add to L1's taxonomy?'; 'when does new become active?') have no answer.
- **Evidence (measured):** `genios_engine/contracts/signal.py:104`; `migrations/0093_signal_lifecycle.sql:52`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/02-PLAN.md:99-101`
- **Fix:** Rohit answers E5 (recommended: keep absence as L2 tool evidence until a reader needs an L1 absence signal) and E7 (the rule for new→active, and revoked's detector). Claude builds whatever he chooses.
- **Verified:** confirmed by the skeptic (contracts/signal.py:104 has SIGNAL_STATES = {active, superseded, expired, resolved}. migrations/0093_signal_lifecycle.sql:51-52 has the same check constraint, and no later migration changes it or adds 'revoked'. L1 02-PLAN.md:99 marks E5 and :101 E7 as '⏳ not built — decision for Rohit', each with its question. Absence lives as L2 tool evidence (tool:unanswered_inbound etc., per the same row).)

<a id="l1-e7-lifecycle-new-revoked"></a>
### Signal lifecycle has no 'new' or 'revoked' state (E7)

`l1-e7-lifecycle-new-revoked` · **P2** · missing · owner **rohit** · decision · step **S12**

- **Expected:** Version and supersession lifecycle including new and revoked, with dates. _(source: GeniOS-008/00-ARCHITECTURE.md 'Inside L1'; 02-PLAN E7)_
- **Actual:** SIGNAL_STATES = {active, superseded, expired, resolved} (contracts/signal.py:104). There is no revoke detector. 02-PLAN marks it a decision for Rohit, because 'new' would hide signals from every reader that filters state='active'.
- **Evidence (measured):** `genios_engine/contracts/signal.py:104`; `speedrun008/GeniOS-008/layer-1-enterprise-signals/02-PLAN.md Group E status E7`
- **What Rohit sees:** A retracted statement ('ignore my last mail') stays active.
- **Fix:** Rohit sets the rule for when 'new' becomes 'active'. Then Claude adds both states to the lifecycle table and builds a revoke detector.
- **Blocked on:** Rohit's E7 decision
- **Verified:** confirmed by the skeptic (SIGNAL_STATES = {active, superseded, expired, resolved} (signal.py:104). A grep for 'revok' in capture/ finds only an attachment-share comment (parked/refetch_policy.py:21), so no revoke detector exists. 02-PLAN.md:101 marks E7 as Rohit's decision.)

<a id="l1-f263-indian-public-mail-hosts"></a>
### YC-II F263 (S18-X13): Indian public mail hosts are missing from the public-host list, so their senders become company nodes

`l1-f263-indian-public-mail-hosts` · **P2** · broken · owner **rohit+harsh** · decision · step **S08**

- **Expected:** Rohit picks which Indian public hosts join the one list. Harsh counts and merges or retires the company nodes already minted from them (dry run first). _(source: speedrun008/YC-II W27/03-FINDINGS.md F263; 07-WHAT-IS-DONE.md §9)_
- **Actual:** capture/pipeline._FREE_MAIL has 8 hosts (including yahoo.co.in), but none of yahoo.in, outlook.in, hotmail.co.in, live.in, ymail.com or zohomail.in appears anywhere in the engine.
- **Evidence (measured):** `genios_engine/capture/pipeline.py:174-175`; `grep yahoo.in|zohomail.in|hotmail.co.in in genios_engine: 0 hits`
- **What Rohit sees:** A person writing from yahoo.in or zohomail.in is grouped under a fake company 'yahoo.in', which produces wrong correlation and wrong card subjects.
- **Fix:** Rohit approves the six hosts. Claude adds them to the one canonical list, with tests. Harsh runs the merge/retire dry run for existing nodes.
- **Verified:** confirmed with a correction by the skeptic: The item names the wrong list. The 'one list' that decides company identity is CONSUMER_EMAIL_DOMAINS (capture/validate/canonical.py:185-191, 26 hosts including yahoo.co.in, live.com, zoho.com and rediffmail.com), re-exported as platform/self_identity.PUBLIC_MAIL_DOMAINS (:32) and used by capture/structured/apply.py. capture/pipeline._FREE_MAIL (:174-175, 8 hosts) only emits company hints that, per F263 itself (03-FINDINGS.md:284), nothing reads. The missing Indian hosts must go into canonical.CONSUMER_EMAIL_DOMAINS. Also, retire or fold _FREE_MAIL.

<a id="l1-internal-knowledge-goal-door-unlinked"></a>
### A second goal door that GeniOS-009 never mentions: internal knowledge of kind 'goal', 'okr' or 'objective' lands at rank 4 and never becomes a goal

`l1-internal-knowledge-goal-door-unlinked` · **P2** · missing · owner **rohit** · decision · step **S26**

- **Expected:** A goal the company writes down (an OKR doc, uploaded or posted) reaches the same goal object, as a proposal or an approved goal, rather than living in a separate store. _(source: GeniOS-009/05-THE-SOURCE.md N1 ('goals are first-class objects'); STEP-G1 (one door))_
- **Actual:** capture/internal_knowledge.py:56 declares the kind 'goal', and :92 maps goals/okr/okrs/objective to it. POST /api/org/{org_id}/knowledge (api/knowledge_routes.py:58) lands it as company canon at authority rank 4. GeniOS-009 never mentions this door (no hit for internal_knowledge or /knowledge in its docs), and G1 syncs only from company_brief_lines.
- **Evidence (measured):** `genios_engine/capture/internal_knowledge.py:56,92`; `genios_engine/api/knowledge_routes.py:58`; `grep -rn 'internal_knowledge|/knowledge' speedrun008/GeniOS-009 → only false matches`
- **What Rohit sees:** An OKR the founder uploads is canon in the graph but is never a goal, and no card links to it.
- **Fix:** Rohit chooses: G1's sync also proposes goals from internal-knowledge 'goal' documents (status proposed, source document), or the knowledge route refuses kind=goal and points to the brief.
- **Blocked on:** Rohit
- **Depends on:** [goals-g1-goal-object-missing](#goals-g1-goal-object-missing)
- **Verified:** confirmed by the skeptic (capture/internal_knowledge.py:56 declares 'goal', and :92 maps goals/okr/okrs/objective to it. Every INTERNAL_KINDS kind lands at CANON_AUTHORITY_RANK=4 (:80,:123-127) through POST /api/org/{org_id}/knowledge (api/knowledge_routes.py:58). A recursive grep of the GeniOS-009 plan docs for internal_knowledge or /knowledge found 0 hits, not even false matches. Only the source chat (source/GeniOS-Goal-Achievement-Loop-Chat.md:1137) says L1 should pull goal evidence from OKRs and company plans, which supports the expectation. A third unlinked goal-like store is team_milestones (migration 0151).)

<a id="l2-c4-e10-metric-definitions-owner"></a>
### GeniOS-008 C4 / L1 E10: who owns metric definitions ('sales' = booked/collected/signed) is unconfirmed

`l2-c4-e10-metric-definitions-owner` · **P2** · missing · owner **rohit** · decision · step **S12**

- **Expected:** Default: Plane D corpus (reviewed YAML), not L1 code. _(source: speedrun008/GeniOS-008/03-QUESTIONS.md C4; layer-1-enterprise-signals/02-PLAN.md E10)_
- **Actual:** The L1 plan still lists E10 as 'open: confirm owner (L1 vs Plane D)'. Nothing is built in either place.
- **Evidence (doc_claim):** `speedrun008/GeniOS-008/layer-1-enterprise-signals/02-PLAN.md:85, 102`
- **Fix:** Rohit confirms Plane D. Claude authors metric definitions in the corpus with a reviewer stamp.
- **Verified:** confirmed with a correction by the skeptic: The owner is not unconfirmed under the programme's own rule. GeniOS-008 03-QUESTIONS.md:3-4 says 'A question you skip takes its recommended default, and the work goes ahead on it', and C4 (:32) defaults to 'Plane D corpus (reviewed YAML), not L1 code'. So the owner defaults to Plane D. The L1 plan's E10 'open' row is stale against 03-QUESTIONS. The real gap is that no Plane D metric-definition unit has been drawn or built.

<a id="l2-d42-d44-reply-time-rules"></a>
### YC-II D42, D43, D44 (F107, F114, F105): reply-time decisions unanswered; 'reply owed' is still a fixed two days

`l2-d42-d44-reply-time-rules` · **P2** · missing · owner **rohit** · decision · step **S23**

- **Expected:** D42: 'reply owed' comes from Rohit's own measured reply time per counterparty, overall, and two days below both. D43: show a connector's rate on its brief entry. D44: re-point the corpus rules written to mean THEIR reply time. _(source: speedrun008/YC-II W27/06-DECISIONS.md D42, D43, D44; 07-WHAT-IS-DONE.md §9)_
- **Actual:** _REPLY_OWED_AFTER_DAYS = 2 is still the threshold (default as today). The corpus still has 131 'reply_cadence' references, unchanged (D44 default). D43 is on its default.
- **Evidence (measured):** `genios_engine/context/outreach_situations.py:757-758, 802`; `grep -rn reply_cadence 'Domain Expertise' → 131 hits`
- **What Rohit sees:** Reply-owed cards fire after two days regardless of Rohit's normal pace.
- **Fix:** Rohit answers D42/D43/D44. Claude measures D42 on the golden set before arming.
- **Verified:** confirmed by the skeptic (context/outreach_situations.py:757 has _REPLY_OWED_AFTER_DAYS = 2, used at :802 (`if owed < _REPLY_OWED_AFTER_DAYS: continue`). `grep -rn reply_cadence 'Domain Expertise'` gives 131 hits across 57 files. No measured per-counterparty threshold exists on this path. The expert trigger's our_usual (reason/expert/triggers.py:138-147) is a separate re-review trigger, not the 'reply owed' situation.)

<a id="l3-two-authority-scales"></a>
### graph_facts.authority_rank holds a 0-6 ladder and a derived default of 100 in the same column

`l3-two-authority-scales` · **P2** · broken · owner **rohit+harsh** · decision · step **S17**

- **Expected:** One dense authority ladder: a signed document (6) beats a stated aside. _(source: memory/two-authority-scales-in-one-column.md)_
- **Actual:** context/analytic/publish.py:102 has DEFAULT_AUTHORITY_RANK = 100. graph_store compares raw integers, so a rank-100 row can never be superseded, and a signed contract arriving against one is dropped as a discrepancy. This is declared, not fixed (receipt 46, UNINTERPRETABLE_RANKS). R16/R17 belong to Rohit and H9 to Harsh.
- **Evidence (measured):** `genios_engine/context/analytic/publish.py:102`; `genios_engine/capture/validate/authority.py:527 (UNINTERPRETABLE_RANKS)`
- **What Rohit sees:** Measured as not firing on 3 Oct (a lower bound), so cards are not shown to be affected today.
- **Where the mistake was:** Two writers chose numbers for one column independently.
- **Fix:** Rohit decides R16/R17, and Harsh runs H9.
- **Blocked on:** H9: set transaction read only; select field, count(*) from graph_facts group by field having bool_or(authority_rank <= 6) and bool_or(authority_rank > 6);
- **Verified:** confirmed by the skeptic (context/analytic/publish.py:102 DEFAULT_AUTHORITY_RANK = 100. capture/validate/authority.py:527 UNINTERPRETABLE_RANKS declares 100 as 'OFF THE LADDER ENTIRELY' (:548). graph_store write_fact compares held_rank against new authority_rank as raw ints (graph_store.py:742-757). This is declared, not fixed.)

<a id="l6-adaptive-distinct-days-trap"></a>
### The durable ADAPTIVE recommendation-learning write is closed only by arithmetic (distinct_days=1); fixing it opens an auto-promoted write

`l6-adaptive-distinct-days-trap` · **P2** · shadow / switched off · owner **rohit** · decision · step **S40**

- **Expected:** The adaptive authority is decided by ADR-10 before any repair. _(source: memory the-obvious-repair-can-be-the-trap.md)_
- **Actual:** feedback/units.py:498 passes distinct_days=1 into validate_learning, which holds it below the default of 2. The tripwire test exists. The constant is unchanged, so the path is still closed.
- **Evidence (measured):** `genios_engine/feedback/units.py:498`; `tests/feedback/test_the_declared_violation_is_blocked_by_arithmetic.py`
- **Fix:** Leave it as is. Rohit ratifies or rejects ADR-10 first. Only then measure distinct days, with govern before validate and a clamp on min_distinct_days.
- **Blocked on:** Rohit's OK for: select unit, result_state, sink_reason, count(*) from learning_object_evaluations where unit='recommendation_learning' group by 1,2,3;
- **Verified:** confirmed by the skeptic (units.py:498 sets distinct_days=1 on the recommendation_learning ADAPTIVE object. tests/feedback/test_the_declared_violation_is_blocked_by_arithmetic.py exists. Caveat: the threshold is per-tenant policy (learning policy row: min_distinct_days read at orchestrator.py:94-134, seeded from the default of 2; feedback_health.py:94-97). A tenant policy row with min_distinct_days <= 1 would open the path in production. Read: select org_id, min_distinct_days from learning_policies; (table name per orchestrator.py:94).)

<a id="l6-macv-and-aer-empty"></a>
### The North Star ledger macv_ledger has no writer, and AER and time_saved are hard-coded 0

`l6-macv-and-aer-empty` · **P2** · missing · owner **rohit** · decision · step **S33**

- **Expected:** The value the customer can verify (caught → acted → resolved), and AER/HIR on the home. _(source: migrations/0012_l6_feedback.sql comment; memory the-north-star-ledger-has-no-writer.md, aer-and-hir-metrics.md)_
- **Actual:** /v1/insights/stats returns value_recovered_inr: None with value_state 'unavailable_macv_ledger_has_no_writer'. The stats route returns 'aer': 0, 'time_saved_hours': 0 and empty trends as literals.
- **Evidence (measured):** `genios_engine/api/intelligence_routes.py:800-822`; `genios_engine/api/routes.py:4619-4623`
- **Fix:** Rohit defines recovered value and the anti-double-count rule, and the AER/HIR formulas. Then build one macv writer at outcome closure and compute AER from executions and delegations. Until then, show 'not measured' rather than 0.
- **Verified:** confirmed by the skeptic (/v1/insights/stats (intelligence_routes.py:747) returns value_recovered_inr None and value_state 'unavailable_macv_ledger_has_no_writer' (intelligence_routes.py:795-822). macv_ledger exists only in migrations 0012:37 and 0033:84, and no INSERT appears in genios_engine or scripts. The literal aer:0 and time_saved_hours:0 come from GET /dashboard/metrics (routes.py:4582, literals at 4619-4623). No AER/HIR computation exists anywhere in genios_engine. The dashboard's actions-card.tsx reads value_recovered_inr but is unmounted, per the comment at intelligence_routes.py.)

<a id="l6-north-star-ledger-no-writer"></a>
### macv_ledger, the North Star value ledger, was created in 0012 and has never had a writer; docs claimed feedback/ wrote it

`l6-north-star-ledger-no-writer` · **P2** · missing · owner **rohit** · decision · step **S33**

- **Expected:** 'The number the customer can verify': caught -> acted -> resolved, distinct-deal SUM plus non-deal COUNT. _(source: migrations/0012_l6_feedback.sql (its comment))_
- **Actual:** There is no 'insert into macv_ledger' anywhere in genios_engine/ or scripts/. The endpoint says value_state 'unavailable_macv_ledger_has_no_writer'. docs/LAYER_MAP.md had claimed a writer (since corrected).
- **Evidence (measured):** `grep 'insert into macv_ledger' genios_engine scripts -> none`; `genios_engine/api/intelligence_routes.py:815`; `memory/the-north-star-ledger-has-no-writer.md`
- **What Rohit sees:** The dashboard cannot show recovered value.
- **Where the mistake was:** A headline metric was declared in a migration and never specified.
- **Fix:** Rohit decides what counts as recovered value and how it is attributed; then one unit builds it.
- **Verified:** confirmed by the skeptic (grep -rni 'macv_ledger' over genios_engine, scripts and migrations finds only the 0012 create, the 0033 FK, the erasure list (account_routes.py:688), comments, and intelligence_routes.py:815 'unavailable_macv_ledger_has_no_writer'. There is no insert. docs/LAYER_MAP.md:15 carries the 2026-10-02 correction.)

<a id="process-asked-what-the-data-answered"></a>
### Rohit was asked questions the data or the code already answered

`process-asked-what-the-data-answered` · **P2** · done (lesson only) · owner **claude** · decision · step **S42**

- **Expected:** Look before asking. _(source: memory/rohit-data-mailbox-is-mrrohitswerashi.md; memory/l5-plan-and-the-cutover-rule.md)_
- **Actual:** 06 D6 asked Rohit which address is his, and every 'no reply' was hedged with 'maybe from <founder company mailbox>'. Rohit, 5 Oct: 'ye hai mera email address idiot'. Separately, L5 STEP-16 asked whether a per-recipient hourly ceiling should exist, though deliver/timing.py already has one.
- **Evidence (doc_claim):** `memory/rohit-data-mailbox-is-mrrohitswerashi.md`; `memory/l5-plan-and-the-cutover-rule.md (fourth retraction, of a question)`
- **What Rohit sees:** Rohit's trust.
- **Where the mistake was:** Questions that read as not having looked.
- **Fix:** Search the data and the code under every name before asking.
- **Verified:** confirmed by the skeptic (Memory rohit-data-mailbox-is-mrrohitswerashi:11-16 (D6 asked; the <founder company mailbox> hedge; 'ye hai mera email address idiot', 5 Oct). l5-plan…:57-58: STEP-16 asked about an hourly ceiling that deliver/timing.py already enforces (_BURST_WINDOW = 1 hour, timing.py:59). The matching folder file is STEP-16-WITHDRAWN-the-hourly-ceiling-already-exists.md.)

<a id="process-d12a-golden-labels-all-by-claude"></a>
### YC-II D12a: all 67 golden cases are labelled by Claude; Rohit has labelled none

`process-d12a-golden-labels-all-by-claude` · **P2** · missing · owner **rohit** · decision · step **S07**

- **Expected:** Rohit spends ten minutes confirming the golden labels (rows 45–47 and the founder cases). Until then Claude's labels are marked 'claude'. _(source: speedrun008/YC-II W27/06-DECISIONS.md D12; 07-WHAT-IS-DONE.md §9; GeniOS-009 09-HARSH-HANDOVER §8 (golden goal labels: Rohit confirms))_
- **Actual:** 67 of 67 case specs have "labelled_by": "claude". Together with the ideal reader (F5), the board measures Claude's expectations, not Rohit's.
- **Evidence (measured):** `grep '"labelled_by"' tests/replays/specs/founder/*.json → 67× claude`
- **Fix:** Rohit reviews the label sheet (especially the 4 failing cases and the investor/programme ones). Claude moves the board deliberately per answer.
- **Verified:** confirmed by the skeptic (tests/replays/specs/founder/ holds 67 .json case specs, and `grep -h '"labelled_by"'` gives 67 of 67 `"labelled_by": "claude"`. F19.json, for example, is labelled 'claude'.)

<a id="process-d17-d19-step19-and-sole-mate"></a>
### YC-II D17, D19: the blind benchmark re-run (STEP-19) was never written, and Sole Mate's team tenant has no home after YC-II was frozen

`process-d17-d19-step19-and-sole-mate` · **P2** · missing · owner **rohit** · decision · step **S43**

- **Expected:** D17: STEP-19 re-runs the benchmark's five shapes (F48–F52) blind with five ledgers, after STEP-16. D19: Sole Mate is the block after YC-II W27, once the founder path shows verified outcomes. _(source: speedrun008/YC-II W27/06-DECISIONS.md D17, D19)_
- **Actual:** There is no STEP-19 file in YC-II W27 (STEP-18 is the last), and GeniOS-008/009 do not mention it. STEP-16 is built. YC-II is frozen as history (GeniOS-008 E3), so both decisions have no folder to land in.
- **Evidence (measured):** `ls 'speedrun008/YC-II W27' (STEP-00 … STEP-18 only)`; `speedrun008/GeniOS-008/03-QUESTIONS.md E3`
- **Where the mistake was:** Freezing YC-II (E3) orphaned two accepted-by-default steps without carrying them forward.
- **Fix:** Rohit decides whether a blind benchmark re-run (and later Sole Mate) becomes a GeniOS-011 step.
- **Verified:** confirmed by the skeptic ('speedrun008/YC-II W27/' has STEP-00 … STEP-18 plus STEP-13b, and no STEP-19 file. 06-DECISIONS.md:24 D17 says 'not written yet', and :26 D19 is the block after YC-II. A grep for 'STEP-19' and 'Sole Mate' in GeniOS-008/009/010 finds nothing. GeniOS-008 03-QUESTIONS.md:47 E3 freezes YC-II as history.)

<a id="process-proposed-formula-decides"></a>
### 'Turn the LLM decider off and let the formula decide' (W4) was proposed against Rohit's product direction

`process-proposed-formula-decides` · **P2** · done (lesson only) · owner **claude** · decision · step **S42**

- **Expected:** The LLM is the expert, with code as memory, calculator and checker. _(source: memory/llm-as-the-expert-not-the-formula.md)_
- **Actual:** Rohit rejected it on 5 Oct ('ek company formula and rules pe nhi chalti').
- **Evidence (doc_claim):** `memory/llm-as-the-expert-not-the-formula.md`; `memory/improvement-plan-w1-w8.md`
- **Where the mistake was:** Optimised for stability over intelligence.
- **Fix:** Get stability from the material-change gate, not by removing the model.
- **Verified:** confirmed by the skeptic (Memory llm-as-the-expert-not-the-formula:3 and :12: W4 ('flag off, formula decides') was rejected on 5 Oct ('ek company formula and rules pe nhi chalti').)

<a id="process-push-ownership-flip-flop"></a>
### Who pushes changed several times (Rohit, then Claude, then classifier-denied, then Rohit), so commits sat local and CI failures went unread

`process-push-ownership-flip-flop` · **P2** · partial · owner **rohit** · decision · step **S03**

- **Expected:** One fixed push owner, and CI read after every push. _(source: memory/claude-pushes-and-keeps-github-synced.md)_
- **Actual:** D10 (5 Oct): Rohit pushes the batch. 11 Oct: Claude pushes itself, after Rohit 'lost a night waiting on a push' and the 10 Oct red run (F145) went unread. 14 Oct and 22 Oct: direct pushes denied by the auto-mode classifier ('Out-of-Place Publication'). 16 Oct: 'Rohit pushes'.
- **Evidence (doc_claim):** `memory/claude-pushes-and-keeps-github-synced.md`; `memory/step14-close-2026-10-16.md`; `memory/mac-app-ux-rebuild-22-oct.md (g010-desktop push denied)`
- **What Rohit sees:** Delays; red CI found late.
- **Where the mistake was:** Process ownership left undecided.
- **Fix:** A Bash permission rule for fast-forward pushes to speedrun008, or one fixed owner.
- **Verified:** confirmed by the skeptic (D10 at 06:17 says 'You push the whole batch at once, later'. Memory claude-pushes: 11 Oct Claude pushes ('he lost a night waiting on a push'; the 10 Oct red F145 went unread); on 14 Oct the push of 33c6fb1f was denied ('Out-of-Place Publication'). step14-close: 'Rohit pushes; auto-mode denies my push'. mac-app-ux-rebuild:78: the 22 Oct direct push to speedrun008 was denied.)

<a id="process-receipt-label-miscount"></a>
### Production guards per package were counted with the hand-written Receipt.layer label, and STEP-10's headline was wrong in eleven documents

`process-receipt-label-miscount` · **P2** · partial · owner **rohit** · decision · step **S42**

- **Expected:** Resolve the table each receipt queries and map it to its writing package. _(source: memory/a-receipt-label-is-not-a-package.md)_
- **Actual:** deliver/ had 5 receipts with 4 working, not '2 and 1'. The labels mix two vocabularies, and relabelling them is still Rohit's call.
- **Evidence (mixed):** `speedrun008/YCW27/layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md`; `memory/a-receipt-label-is-not-a-package.md`
- **Where the mistake was:** Repeating a number is not corroborating it.
- **Fix:** Rohit decides on relabelling; until then, never count by the label.
- **Verified:** confirmed by the skeptic (speedrun008/YCW27/layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md:3 lists 11 corrected documents. :18 says deliver/ carried 5 receipts, not 2, and 4 of 5 worked, not 1. :98 says 'eleven places'. §8 (:116-121): relabelling is Rohit's call, still open.)

<a id="process-started-layer-unasked"></a>
### Two read-only Layer 2 audits were launched right after L1 was pushed, without Rohit opening L2

`process-started-layer-unasked` · **P2** · done (lesson only) · owner **claude** · decision · step **S42**

- **Expected:** Rohit opens each layer, including any read-only audit. _(source: speedrun008/GeniOS-008/01-RULES.md:43 (Rule 4.1); memory/wait-for-rohit-to-open-a-layer.md)_
- **Actual:** 18 Oct. Rohit: 'jab maine kuch bola hi nahi to?'
- **Evidence (doc_claim):** `memory/wait-for-rohit-to-open-a-layer.md`
- **Where the mistake was:** Unrequested work spent his quota and attention.
- **Fix:** Rule 4.1.
- **Verified:** confirmed by the skeptic (Memory wait-for-rohit-to-open-a-layer:11: on 18 Oct two read-only L2 audits were launched right after the L1 push. Rohit: 'jab maine kuch bola hi nahi to?')

<a id="surfaces-placeholder-pages"></a>
### Several reachable pages and surfaces are placeholders: Memory providers (all locked), Agents (locked), trial-locked governance, and a demo-only browser extension

`surfaces-placeholder-pages` · **P2** · shadow / switched off · owner **rohit** · decision · step **S39**

- **Expected:** 'Show only what we are building'. Locked items say what they unlock. _(source: memory dashboard-navigation-22-oct.md (Rohit's grouping); speedrun008/GeniOS-010/01-NAVIGATION/README.md)_
- **Actual:** Context ▸ Sources ▸ Memory is a static page of locked providers with disabled Connect buttons and no brain call. Agents is a lock panel. Reports, Policies and Approvals are locked by TRIAL_GOVERNANCE.auditOnly. Extension/browser-extension is 'a local product-demo overlay' with scripted scenarios.
- **Evidence (measured):** `dashboard origin/main:src/components/sources/memory-providers-page.tsx:180-208,308-346`; `dashboard origin/main:src/app/dashboard/agents/page.tsx`; `dashboard origin/main:src/lib/governance-trial.ts:8-30`; `dashboard origin/main:Extension/browser-extension/manifest.json:5; content.js:301-304`
- **Fix:** Rohit decides which of these stay visible-and-locked and which leave the nav until built.
- **Verified:** confirmed by the skeptic (memory-providers-page.tsx has no API import. Its Connect buttons are disabled with Lock icons (:273-274, :312-316, :344), and the sidebar links it as Context ▸ Memory (sidebar.tsx:138-141; route src/app/dashboard/integrations/memory/page.tsx). agents/page.tsx is a fixed lock panel ('Agents are locked for this release'). governance-trial.ts:8-28 has auditOnly: true and locks Reports, Policies and Approvals. Extension/browser-extension/manifest.json:5 says 'A local product-demo overlay…', and content.js:299-305 has demo-scenario previous/next navigation.)
