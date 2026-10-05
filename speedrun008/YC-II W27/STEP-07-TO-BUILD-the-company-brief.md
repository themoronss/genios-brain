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
