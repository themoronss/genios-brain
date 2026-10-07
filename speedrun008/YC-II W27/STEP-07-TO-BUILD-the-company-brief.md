# STEP-07 · TO BUILD · the company brief — what a chief of staff knows on day one

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
