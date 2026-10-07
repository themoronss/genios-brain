# STEP-07 · PENDING — owner Rohit (push; accept the brief) and Harsh (deploy, migration 0195; draft it) · the company brief — what a chief of staff knows on day one

**Owner:** Claude builds · **Rohit confirms** the brief (two minutes, then weekly diffs).
**Depends on:** `STEP-04`, `STEP-05`. **Moves:** a versioned brief exists and is in **100%** of
model prompts that judge or read; the gate (`STEP-03` §3.5) starts using it.

---

## 1 · What is true now

| | Evidence |
|---|---|
| **No prompt carries any company context** | `[CODE]` every prompt template enumerated: the decider (`reason/llm_decision_maker.py:496` — *"You are the chief of staff of a busy founder…"*) receives the corpus capability's goal, not the company's; R-6 receives a slice; the AI filter receives one email; screen memory receives only *"The manager: {seat email and name}"* and the time (`reason/moments/screen_memory_batch.py:59-61`) |
| The stores that look like a profile feed nothing | `[CODE]` `context/tenant_profile.py` — `declare` has no production caller · canon kinds `goal`, `kpi`, `icp`, `product`, `org_structure`, `project` (`capture/internal_knowledge.py:40-60`) arrive via `POST /api/org/{org}/knowledge` and only `project` anchors a situation · `user_models` (voice, decision policy, priorities, relationships, red lines) is CRUD with no reader · `user_model_proposals` has no writer · `seat_objectives` holds one domain per seat · `seat_profiles` feeds only the screen prompt |
| They are empty anyway | `[PROD]` `seat_objectives` 0 · `org_mission_critical_entities` 0 · `user_models` 0 · `learned_brain_entries` 0 |
| One store **is** read live | `[CODE]` `org_mission_critical_entities` is read by L1 importance on both ticks (`capture/esqe/baseline_reader.py:208-229`) |

## 2 · Why

Every judgment in your mailbox turned on context nobody gave the system: that you are raising,
that you applied for DPIIT recognition, that Boardy works for you, that NSRCEL is your program.
A 30-year expert reads everything *through* that context.

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | the brief contract | new `contracts/company_brief.py` | versioned; sections: **company** (name, product in one line, stage) · **people who are us** (from `STEP-04`) · **goals now** · **work in motion** (seeds for `STEP-09`: fundraising, applications, compliance filings, hires, partners) · **key people and their role** · **connectors** (Boardy) · **watchlist** (domains whose mail always matters: `sampark.gov.in`, `startinup.in`, `hub71.com`, `nsrcel.iimb.ac.in`, …) · **preferences and red lines**. A rendered budget of ~800 tokens, truncation reported |
| 3.2 | where it lives | existing stores, no new graph table | company facts and goals → canon nodes (`goal`, `product`, `project`); preferences and red lines → `user_models`; key counterparties → `org_mission_critical_entities` (already read live); connectors and watchlist → a canon kind added beside `org_structure`. `platform/company_brief.py` `brief_for(conn, org_id)` **composes** it, deterministically, with a version id |
| 3.3 | the first draft | `reason/brief_drafter.py` — one model call, Sonnet-class | reads memory **patterns**, not mail text: who you write to and how often, which domains carry deadlines, the 11 Aug wave, the cohort calendar, the government senders, Boardy's intros. It writes each line as a **proposal** into `user_model_proposals` (the unused approval queue, `api/usermodel_routes.py:146-184`) |
| 3.4 | you confirm | the dashboard: one screen, accept / edit / remove per line | accepted lines are applied by the existing route (`usermodel_routes.py:180`) or written to canon |
| 3.5 | every model site reads it | the AI filter (`capture/gate/relevance.py`), the reader (`capture/semantic/extractor.py`), screen memory, the expert pass (`STEP-12`), card copy (`STEP-14`) | each prompt carries the brief text and its version id; a version change is part of `STEP-02`'s fingerprint, so a changed brief re-thinks the files it touches — once |
| 3.6 | it stays current | weekly, inside the learning sweep (`api/routes.py:1310`) | the expert proposes a diff — *"a new application appears to be live: ___"*, *"NSRCEL has had no session for three weeks — finished?"* — as proposals; nothing changes until you accept |

## 4 · What will happen — the first draft, from metadata alone `[MODELLED]`

```
Company      GeniOS — "Palantir for company managers" · pre-seed · raising
Us           mrrohitswerashi@gmail.com · ceo@thegenios.com · thegenios.com
Goals now    raise the pre-seed round · DPIIT recognition · get into accelerator and incubator
             programs · hire a founding AI engineer · land design partners
In motion    Fundraising — 11 funds written to on 11 Aug; Titan, Antler, Insight, 247VC, a16z engaged
             Programs — NSRCEL (active cohort), Hub71, IIITD-IC, FITT, IIM Lucknow EIC, GUSEC, StartinUP, EF
             Compliance — Startup India / DPIIT recognition
             Hiring — Khushi, offer sent 5 Aug
             Partners — Evokoa, Engramme, Supymem, Tryclean, Noveum, Reticle
Connectors   Boardy (boardy@boardy.ai) — an AI agent that introduces you to people
Watchlist    sampark.gov.in · digilocker.gov.in · startinup.in · hub71.com · nsrcel.iimb.ac.in · iiitdic.in · fitt-iitd.in · …
Preferences  (yours to add)
```

Every line is a proposal you accept, edit or delete.

## 5 · Expected

- a brief exists, versioned, accepted by you;
- 100% of judging and reading prompts carry a brief version id (asserted in the prompt builders);
- the golden must-detect score rises once the gate reads it — measured, not assumed.

## 6 · Verify

```
.venv/bin/python -m pytest tests/platform/test_company_brief.py -q
#   composed deterministically from the stores; same inputs → same version id; over budget → reported, not cut
.venv/bin/python -m pytest tests/test_every_prompt_carries_the_brief.py -q
#   an AST walk over every prompt builder that judges or reads — fails if one omits brief_for()
```

## 7 · Risks

| Risk | Guard |
|---|---|
| A wrong line steers every judgment | nothing enters the brief without your acceptance; every prompt names the version it used, so a bad line is traceable |
| The brief grows into a dump | the token budget and the fixed sections |
| Private material leaks into prompts | the brief is composed from what you accepted, not from raw mail |

---

## 8 · The check of 2026-10-07 — what the 5 Oct plan got right, and wrong

Every claim above was re-read against `speedrun008` @ `18b41f0f` (STEP-02 to STEP-06 built), by hand
and by three read-only traces — every model call site, every store the plan names, and the capture
gate end to end — whose claims were checked line by line before use. The golden set was measured from
its cassettes (no spend). Production was not read; §8.7 is for Harsh.

### 8.1 · Measured — on the golden set (44 cases, 368 recorded model calls)

| | |
|---|---|
| calls that judge or read | **316 of 368** — the junk filter 59 (batched), the relevance page 58, extraction 48, resolution 46, the decider 63, R-1 42 |
| calls that write | 52 — the card narrator 25, the bundle narrator 27 (card copy, `STEP-14`) |
| prompts carrying any company context | **0** — no prompt anywhere names the company, its goals, its people or a watchlist |
| must-detect cases lost at the gate | 5 — F01, F02 (a portal: Promotions, no-reply, the AI filter), F03, F09 (the intro agent: List-Unsubscribe), F16 (a bounce) |
| what stops the portal's and the intro agent's mail | four stages in a row, each keyed on "is the sender known": the noise rules, the AI filter, the relevance page's service-account and bulk rungs, the bulk check before extraction (`capture/esqe/relevance.py:500-560`, `capture/pipeline.py:782-785`). A whitelist skips only the first |
| case objects that would reach a reader for the first time | F02 `locker`, `received`, `granted`; F03 `nudge1`, `nudge2` — no authored extraction: the ideal reader refuses until one is written |

### 8.2 · The claims

| Claim (5 Oct) | Verdict (7 Oct) |
|---|---|
| no prompt carries company context; the decider gets the capability's goal | ✅ — 28 model sites, none with a company, goals, people or watchlist. Closest: the screen lanes' `{me}` line and the seat's weekly profile (`reason/moments/screen_insight.py:355`) |
| `tenant_profile.declare` has no production caller | ✅ (tests only); it writes two axes (category, reader role) as tenant-node facts |
| canon kinds arrive via `POST /api/org/{org}/knowledge`; only `project` anchors | ✅ — and ⚠️ worse: the door passes no semantic lane, and Layer 2 pulls only events with a signal, an extraction, an archive or a mapping, so knowledge-door text may never reach the graph at all; nothing reads `goal`, `kpi`, `icp` or `product` nodes |
| `user_models` CRUD with no reader; `user_model_proposals` has no writer | ✅ — and the approve route replaces one whole persona column for one PERSON, approves even when the person has no row, and takes `decided_by` from the request body (`api/usermodel_routes.py:159-187`). It cannot hold line-level company proposals |
| `seat_objectives` one domain per seat; `seat_profiles` feed only the screen prompt | ✅ |
| production: those stores are empty | ✅ (`01-CROSSCHECK.md:98-101`): 0, 0, 0, 0 — `seat_profiles` 1 |
| `org_mission_critical_entities` is read live | ✅ — by L1 importance, by ORGANISATION NAME only (`fold_entity_key`; `sampark.gov.in` folds to `gov`). Watchlist domains and people cannot go there |
| 3.3 · the drafter writes proposals into `user_model_proposals` | ❌ — see above; a proposal needs a section, a line, and a value (an address or a domain) |
| 3.4 · accepted lines applied by `usermodel_routes.py:180` or written to canon | ❌ — the same; and canon is wiped by `/reset` while `user_models` is not |
| 3.4 · "the dashboard: one screen" | ⚠️ the dashboard is a separate repository (`genios-dashboard`, `main.py:118-129`). This repository gives it the routes; the screen is the dashboard's |
| 3.5 · the AI filter, the reader, screen memory read the brief | ✅ the sites exist; ⚠️ for the gate, a brief in the filter's PROMPT does not get the portal's mail read — three later stages stop it on "unknown sender". The deterministic answer is to make the brief's senders KNOWN |
| 3.5 · a brief version change re-thinks once via `STEP-02`'s fingerprint | ✅ possible — `reason/fingerprint.MaterialInputs` carries `decider`; the brief's version joins it. ⚠️ and three caches key on a version STRING, not the prompt: the decider's and R-1's in-process caches and the R-site generation cache (`reason/llm_sites.py:163-172`) — each must take the brief's version, or a changed brief is served the old answer |
| 3.6 · weekly, inside the learning sweep at `api/routes.py:1310` | ⚠️ moved to `:1497-1509`, and it runs inside one database transaction per tenant — a model call does not belong there. Its own weekly block, with its own week claim, beside it |
| (new) the word "brief" | ⚠️ already means three things — the Decision Brief (`executive/brief.py`), the L4 `brief` feature and daily ranking (`reason/brief_ranking.py`), the morning brief. This one is always the **company brief** |
| (new) a "connector" already exists for cards | `_BOT_DOMAINS = {"boardy.ai"}` and `_is_connector` (`api/routes.py:5021-5049`) tell the card to reply to the introduced people; `capture/landing/promote.py:11-14` waits for "a connector the brief names" |
| (new) the fast path | the onboarding backfill and `_sync_source` gate on the list snippet (`capture/connectors/composio.py:425-512`): a brief-named sender filed under Promotions would be kept as a snippet. The brief's senders are exempt there too |

### 8.3 · What changes in the design

1. **The company brief has its own table** (`company_brief_lines`, migration `0195`): one row per
   line — section, text, an optional address or domain, status (proposed · accepted · rejected ·
   removed), who proposed it and on what evidence, who decided and when. One writer
   (`platform/company_brief_store.py`). Nothing counts until accepted; nothing is deleted, so the
   brief in force at any instant can be rebuilt. The plan's four stores are left as they are: none of
   them can hold a line, and two of them would start feeding the brief into readers that never asked.
2. **`platform/company_brief.brief_for(conn, org_id)` composes it**, deterministically: the company
   (`orgs.company`, `orgs.name`), the people who are us (`STEP-04`), and the accepted lines in fixed
   sections, rendered under ~800 tokens (truncation reported), with a version `cb-<12 hex>`.
   No accepted line → **no brief, and no prompt changes at all** — a tenant without one sees the
   engine exactly as today.
3. **Every model site that judges or reads carries it** — twelve: the junk filter, the relevance
   page, extraction, resolution, R-1 (both), R-6, the decider, screen insight, screen memory, draft
   review, org-rule extraction. The block sits before each prompt's content, never inside a fence,
   never in a cached prefix. Writing sites (narrators, drafts, Ask) are `STEP-14`'s; a guard holds the
   two lists equal to the metered register, both ways.
4. **The gate reads it deterministically.** A sender the brief names — a connector's or a key
   person's address, a watchlist domain — is a KNOWN sender (`api/routes._sender_resolver_for`), so
   all four stages let it through, and the gate records why: **W-07**, *named in the company brief*.
   The fast path never leaves such a mail as a snippet.
5. **A changed brief re-decides each subject once** (the fingerprint), and no cache serves an answer
   made under an older brief.
6. **The drafter proposes; the founder decides.** One Sonnet-class call over memory PATTERNS —
   counts, domains, dates, meeting series, waves; never a message body — writes proposals. A line may
   only name an address or domain the patterns contain. Weekly, the same drafter proposes a diff.
7. **The golden founder gets the brief §4 would draft**, in the golden world's names
   (StartupSetu, Introly, Lakshya, the funds and programs of the cases). Every judge/read prompt in
   every case then carries it, and the board moves only where the gate's deterministic reading moves
   it — the model's use of the brief is the live run's to measure (D12c).

### 8.4 · Decisions

| | Question | Default |
|---|---|---|
| D26 | Run STEP-08 before the brief is accepted? | No (STEP-08 §8.5) |
| D27 | Who may accept a line: the account owner only, or admins too? | **The owner** — the brief steers every judgment |
| D28 | The drafter's model, and the weekly diff | **Sonnet-class, one call to draft, one a week** — about $0.05 each |
| D29 | Should the AI filter's archive now stand (end `03` F55's re-admission)? | **No** — not until a live run measures the filter with the brief |

### 8.5 · What will be built — tree block `yc2_w27_s07` (milestone M25), proposed

| Category | Units | What |
|---|---|---|
| C1 · the company brief | 4 | `contracts/company_brief.py` (sections, line, render under budget, version); migration `0195` (`company_brief_lines`, `company_brief_reviews`) and the tenant reset; `platform/company_brief_store.py`, the one writer; `platform/company_brief.py` — `brief_for`, the named-sender test, a short per-process cache |
| C2 · the founder confirms | 2 | `api/company_brief_routes.py` — read the brief and its proposals, add a line, accept (or edit) or reject a proposal, remove a line; the owner only (D27); accepting a named sender promotes that sender's archived mail. `scripts/company_brief.py` — the same for Harsh, on Rohit's word, until the dashboard has the screen |
| C3 · the drafter | 4 | `reason/brief_patterns.py` — memory patterns, never a body; `reason/brief_drafter.py` — one call, proposals only, every address or domain from the patterns; `scripts/draft_company_brief.py` — dry run, then `--apply`; the weekly review in the heavy tick, with its own week claim |
| C4 · the gate reads it | 5 | W-07 *named in the company brief*; the resolver's reason reaches the gate; `_sender_resolver_for` — known counterparties and the brief's senders; the fast path never keeps them as a snippet; the junk filter carries the brief, skips known senders in its batch (F79) and sends the masked subject (F78) |
| C5 · every judging and reading prompt | 13 | extraction, the relevance page, resolution, R-1 (the interpreter and the test-mode reader), R-6, the decider, screen insight, screen memory, draft review, org-rule extraction — each carrying the block when a brief exists and its version in every cache key; the change gate's fingerprint; the guard that holds the two lists equal to the metered register |
| C6 · the check | 1 | `scripts/pipeline_health.py` — *the company brief exists and is current* |
| C7 · the golden set | 3 | the golden founder's brief, seeded as signup and the founder would; the cassettes re-recorded and the newly reached objects authored; the acceptance — every judge/read prompt of every case carries the brief, the brief's senders are W-07, and the board is re-recorded with every move named |

32 units. Critical path, 7: the contract → the composer → the resolver → the gate's reason →
the golden brief → the re-record → the acceptance. The thirteen prompt units depend only on the
contract and the composer, and touch one file each.

## 9 · Built — 2026-10-07 (`yc2_w27_s07`, 34 units green: 32 drawn + 2 found)

### 9.1 · What was built

| | Where | What it does |
|---|---|---|
| the brief, in its own table | `contracts/company_brief.py`, migration `0195_company_brief` | one row per line — section (company, goals, in motion, people, connectors, watchlist, preferences; *us* is composed, never written), text ≤ 200 characters, an address for a connector, a domain for the watchlist — proposed · accepted · rejected · removed, never deleted. Composed under 3,200 characters, whole lines only, what the budget leaves out named; version `cb-<12 hex>`. Survives `/reset` |
| one writer, one composer | `platform/company_brief_store.py`, `platform/company_brief.py` | propose (no repeats; a rejected line is not proposed again for 90 days), accept (as written or in the founder's words), reject, remove, add; `brief_for(conn, org, at=…)` rebuilds the brief in force at any instant; `current` holds it a minute per process, dropped on every write, EMPTY on any failure |
| the founder decides | `api/company_brief_routes.py`, `scripts/company_brief.py` | read the brief, its proposals and its last weekly review; add, accept (or edit), reject, remove — the account owner only (`06` D27). Accepting a connector, key person or watchlist line promotes what the gate archived from that sender (`capture/landing/promote.promote_named_sender`; a public mail host never) |
| the drafter | `reason/brief_patterns.py`, `reason/brief_drafter.py`, `scripts/draft_company_brief.py` | one Sonnet-class call (`Settings.company_brief_model`, D28) over memory PATTERNS — correspondents, domains, outbound waves, introducers read off the envelope, meeting series, the domains that carry deadlines, thread objectives; no subject, no body, nothing private. Proposals only, each with the pattern items it rests on; a line naming an address or domain the patterns never showed is refused. `--patterns` (no model), a dry run, `--apply` |
| the weekly review | `reason/brief_review.py`, the heavy tick (`api/routes.run_maintenance_sweep`) | once per tenant per ISO week, for a tenant with an accepted line: the drafter again, with the brief in force, for what is missing — claimed in `company_brief_reviews`, its own block and transactions, off with no model |
| the gate reads it | `capture/gate/rules.py` W-07, `api/routes._sender_resolver_for`, the fast path, the junk filter | a sender the brief names is KNOWN to all four stages that asked "is the sender known" — the noise rules, the AI filter, the relevance page's first rung, the bulk check — and the gate says why: **W-07**, *named in the company brief*, attention `deep`. The fast path fetches it whole. The junk filter carries the brief, skips its senders in the batch (`03` F79), sends the masked subject (F78) |
| every judging and reading prompt | twelve sites | the junk filter, the relevance page, extraction (the per-call envelope), resolution, R-1 (both), R-6, the decider, screen insight, screen memory, draft review, org-rule extraction, the drafter — the block after each prompt's opening, never in a fence or a cached prefix; every cache that keys on a version string takes the brief's version — only when there is one |
| the change gate | `reason/fingerprint.MaterialInputs.brief` | the brief's version is a fingerprint input when a brief exists: a changed brief re-decides each subject once; with none, every fingerprint is the pre-STEP-07 one (pinned) |
| the guard | `tests/test_every_prompt_carries_the_company_brief.py` | the model-site register split in two — 12 that carry the brief, 10 that do not, each with its reason — held equal to it both ways; by the AST every builder takes the block and every caller passes it; a planted site that omits it is caught at every link |
| the check | `scripts/pipeline_health.py` | *the company brief exists and is current* — fails while no line is accepted; names the version, the proposals waiting, what the budget left out, the last weekly review |
| the golden set | `tests/replays/specs/founder/brief/company_brief.json`, `engine_runner`, the cassettes | the golden founder holds §4's draft in the golden world's names; every cassette re-recorded (no spend); the acceptance `test_the_company_brief_is_in_every_prompt.py` on every case |
| found while building | `tests/test_recode_parked_documents.py`, `tests/test_no_two_test_modules_share_an_import_name.py` | the dash-key flake closed (`03` F71); no two test files import under one name |

### 9.2 · Measured

| | Before (§8.1) | After |
|---|---|---|
| golden: prompts that carry any company context | 0 of 368 | every judging and reading prompt of every case — **321 of 373** — once, under its version |
| golden: writing prompts (card narrator, bundle narrator) | 52 | 52, **byte for byte** — every cassette key identical in all 44 cases |
| golden: mail the gate archived | 33 objects | **12** — the other 21 are mail the brief names (StartupSetu, DigiVault, every Introly mail, the State Startup Mission, Lakshya's community mail), now kept and read: W-07, `deep` |
| golden: model calls by site | extraction 48 · resolution 46 · R-1 42 · decider 63 · junk filter 59 · relevance page 58 | 69 · 57 · 48 · 68 · **37** · **42** — the kept mail is read; the filter and the page are not asked about a sender the brief names |
| the golden board | must-detect 11/32 · must-abstain 11/12 · forbidden 4 · Atlas 4/80 | **unchanged** (`golden_score.py --assert-recorded` matches). Lost at the gate **5 → 1** (F16, a bounce); lost in reasoning 7 → 11 (F01, F02, F03, F09 — read now, no card yet: §9.3) |
| a tenant with no brief | — | byte for byte as before: every site's builder run beside the old module, by the workers who built them; the fingerprints pinned to their pre-STEP-07 values; the golden lane replayed unchanged before the golden brief was seeded |
| production | no brief | ⏳ none until Rohit accepts the first draft (§9.5) |

### 9.3 · Found while building — each a measurement

- **The sweep's junk filter carried no brief.** The scheduled sweep and `/ingest/all` build one
  classifier with no tenant and re-bind it per connection (`api/routes._bind_gate_costs`); the re-bind
  bound the cost sink only. Found by writing the guard, fixed in `740e13bc` (`03` F84).
- **The four cases the gate now keeps are lost in reasoning.** F01, F02: the portal's notices reach
  memory and no situation forms about the application (STEP-09). F03: the intro's situations anchor on
  the CONNECTOR — the extraction's role `connector` is free text the graph never reads as an introducer
  (F80). F09: the connector's ask forms an investor situation in the fundraising domain, which is not
  active. And the legacy rule raises the connector as a person owed a reply in six cases; the decider,
  reading the brief, defers it (F81).
- **What a changed brief does not re-judge.** Answers stored per item — the screen lanes' 24-hour
  verdicts, M-4's resolution claims, N-3's per-document-version ledger — are verdicts, not caches (F82).
  The resolution claim row does not name the brief it was made under; the model-run row does (F83).
- **A write-only table, caught by the resolver's pin.** `company_brief_reviews` had a writer and no
  reader; `platform/company_brief.last_review` is its reader (the confirm route and the health check).
- **The golden reader would have answered every prompt the same.** A `when` term the brief also names
  (Introly, Kavitha Nair) matches every prompt that carries the brief; the ideal reader now takes the
  block out before matching (`ideal_reader.without_company_brief`, with its own test).
- **My own mutation poisoned a guard run.** A same-size mutation restored within a second left its
  `.pyc` valid; two tests read red on code no longer in the file. The mutation runner now drops the
  `.pyc` and writes none.
- **Two test files, one import name — the whole suite stopped at collection.** The contract's test and
  the composer's test were both `test_company_brief.py`, in two folders with no `__init__.py`: green in
  every per-folder guard run, a collection error in QA's one-process run — and CI's hermetic job is that
  run. Renamed, and a guard computes every test file's import name as pytest does (`1f0beffa`, minted
  `M25.C8.L-integration.V0.U02`).
- **A flake I numbered twice.** The dash-key flake is `03` F71 (recorded at STEP-05); fixed here
  (`175ea9f1`, minted `M25.C8.L-integration.V0.U01`) — the commit message calls it F80.
- R-6's prompt says *"the only thing you may reason from"* right after the brief (F85); a watchlist
  DOMAIN keeps a program's newsletters deep (F86).
- Pins: statements 2,967 → 2,984, table usage 191 → 192 — each per file, with its reason.

### 9.4 · QA

`baseline/yc2w27-s07-qa/qa_record.txt` — run 2 at `1f0beffa`, green on every tier, a database created for
every check, re-run whole after run 1 (at `73f9c949`) stopped at collection: two test files imported under
one name (§9.3). The units 38 / 0 / 0 (4 tree checks + 34 units); the whole database suite 18,276 passed,
0 failed (the same four optional skips, re-listed with their reasons); the golden lane 682 passed, 87
xfailed, 0 skipped; the board matches — the two lines unchanged (must-detect 11/32, must-abstain 11/12,
Atlas 4/80), lost at the gate 1 and in reasoning 11; 0 golden tenants left; the hermetic job 16,497
passed, 1,473 skipped (the database tests, run in tier 2), 323 deselected, 72 xfailed in 828.57s
(0:13:48). Crosscheck: verdict ship (`.trace/reports/crosscheck-yc2_w27_s07-20261007T104500Z.md`), with
an addendum — QA run 1 contradicted one of its rows.

### 9.5 · The deploy, and what comes after

Migration **`0195_company_brief`** ships with `0191`–`0194`; the boot applies it. Nothing changes for
the design partner until a line is accepted — then every judging prompt carries it. In this order
(`08` §3.6):

1. `scripts/draft_company_brief.py --org … --patterns` — what the drafter will read; no model.
2. The dry run (one Sonnet call, ≈ $0.05) — every proposed line with what it rests on; Harsh sends it.
3. `--apply` — the lines become proposals; nothing is accepted.
4. Rohit decides each line (`scripts/company_brief.py --org … show`, then `accept` / `reject` /
   `add`), until the dashboard has its screen. Accepting the Boardy connector line promotes Boardy's
   archived introductions — D23's promotion, by the brief.
5. `scripts/pipeline_health.py --org …` — *the company brief exists and is current* passes.
6. Weekly, by itself: the review proposes what is missing; Rohit decides again.

STEP-08 (the re-sync) runs after the brief is accepted (`06` D26).
