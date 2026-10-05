# STEP-03 · TO BUILD · the gate sets attention, it never deletes

**Owner:** Claude. **Depends on:** `STEP-00`. **Decision:** `06` D4 (how long low-attention mail is
kept). **Moves:** new mail with its content deleted at the gate **258 → 0**; every mail carries an
attention tier and the reason for it.

---

## 1 · What is true now

| | Evidence |
|---|---|
| Every noise rule is a **drop** | `[CODE]` `capture/gate/rules.py:335-382` — N-09, N-08, N-06, N-07, N-01, N-03, N-04, N-02 |
| A drop keeps no body | `[CODE]` `capture/pipeline.py:1567-1640`: `prepared_content` only if kept; `raw_payloads` only if kept or a *judged* drop (TTL parked 365 d, judged drop 90 d, emitted **30 d**, `:179-187`); the event returns before the semantic lane |
| A dropped mail can never come back | `[CODE]` dedup ignores outcome (`capture/pipeline.py:105-107`; `capture/landing/pg_repository.py:44, 58-60`); a re-sync lands it as a duplicate |
| The AI filter decides existence, blind | `[CODE]` drop below relevance 0.25 (`capture/gate/relevance.py:15`; `capture/gate/gate.py:121-132`); its prompt (`relevance.py:65-122`) has no company context and lists *"automated, one-to-many, self-service"* and *"automated matchmaking"* as drop classes |
| Boardy can never be whitelisted as an agent | `[CODE]` Gmail senders are hard-coded `actor_type="external_contact"` (`capture/connectors/composio.py:575`); W-03 needs `agent` (`rules.py:276`) |
| No tenant allow-list exists | `[CODE]` `approved_sender` and `sender_blocked` are read (`rules.py:274, 345`) and written nowhere |
| The S2 park reason is thrown away | `[CODE]` every S2 park is recorded as `low_relevance` (`gate.py:133-135`) |
| What it cost | `[PROD]` 258 mails with no content — all six Startup India / DigiLocker / MSME mails but one, 31 of Boardy's 35, SINE's 13, Sankalp's 12 |
| Already better on `harsh/mvp` | `48768ca7`: `sender_known` includes everyone the account has **written to** (11 → 29 people). Boardy qualifies — you wrote to `boardy@boardy.ai` on 12 Aug and 29 Sep |

## 2 · Why

An expert cannot reason over what was thrown away. The Atlas says it as a rule (RULE 04):
*uncertainty routes, it never deletes.*

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | the attention tier | migration (next free number) | `source_events.attention` ∈ `deep` · `skim` · `archive`, plus `attention_reason`. `dropped` stops being written for mail |
| 3.2 | noise becomes a feature | `capture/gate/rules.py` `noise_rule`, `light_junk` | the N-codes still compute — they become the *reason* for `archive`, never a drop. `light_junk` (`composio.py:406-422`) decides how much to fetch (skim: headers and snippet), never whether the mail exists |
| 3.3 | keep the content | `capture/pipeline.py:1609-1631`; TTLs `:179-187` | every kept tier stores the encrypted payload **and** the prepared text, expiring after D4 (recommended 180 days). The 30-day emitted TTL goes too: `_pull` inner-joins `raw_payloads` (`context/runner.py:242`), so a 30-day TTL quietly strands any event not drained in a month |
| 3.4 | known people and connectors get attention | `rules.py:269-284`; `composio.py:575` | a known counterparty (with `48768ca7`'s sent-folder widening) → `deep`. An address the brief names as a **connector** (Boardy) is stamped `actor_type="agent"` → W-03 → `deep`. Until `STEP-07` exists, the bootstrap is: *the account has written to this address, and the relay detector (`rules.py:121-190`) says it introduces people* |
| 3.5 | the AI filter decides attention, with context | `capture/gate/relevance.py:65-122, 233-268` | **after `STEP-07`:** the prompt carries the brief's excerpt — the company, its live workstreams, a watchlist of programs, funds and government portals — and the sender's history with you. It returns a tier and a reason, not keep/drop. The *"automated matchmaking"* clause goes; a matchmaking agent you use is named in the brief |
| 3.6 | keep the reason | `capture/gate/gate.py:133-135` | the classifier's own reason code is stored, not collapsed into `low_relevance` |
| 3.7 | promotion | `capture/pipeline.py`; `STEP-05`'s re-process path | an `archive` mail is promoted to `deep` and **read** when its sender or thread later joins a workstream — the way Pankaj's intro should have been, once Boardy was known |

## 4 · What will happen

| Mail | Today | After |
|---|---|---|
| A Boardy intro carrying `List-Unsubscribe` | `N-02` → deleted | bulk header noted; Boardy is a correspondent you have written to → `deep` → read → becomes an intro file in `STEP-09` |
| A Startup India portal mail filed under Promotions | `N-06` → deleted | kept as `archive` at worst; with the brief saying *"DPIIT recognition: in progress"* and `sampark.gov.in` on its watchlist → `deep` → read the same day |
| Khushi's mail from 247VC | AI filter: junk → text gone | the brief knows you are raising; a named person at a fund → `deep` |
| A Composio product announcement | `N-02` → deleted | `archive` — kept encrypted for 180 days, never read by a model unless promoted |

## 5 · Expected

| Measure | Before | After |
|---|---|---|
| New mail with its content deleted at the gate | 258 of 395 | **0** |
| Golden must-detect cases reaching `deep` | measured in `STEP-01` | **≥ 95%** |
| Golden noise cases landing in `archive` | measured in `STEP-01` | **≥ 90%** |
| Mail the model reads | every S2 candidate, blind | only `deep` — about 10–20 a day here `[MODELLED]` |
| Storage | — | `[MODELLED]` ~250 archived mails per two months × ~20 KB ≈ 2.5 MB a month |

## 6 · Verify

```
.venv/bin/python -m pytest tests/capture/gate -q
#   every N-code lands as archive with payload and prepared text, never dropped — one mutation per code
#   a connector address is stamped agent and reaches W-03
#   the S2 reason survives to the trace
.venv/bin/python -m pytest tests/replays -q          # founder cases 1–3, 10–11, 17–23 reach deep; 32–34 archive
# production, read-only, after deploy:
#   select attention, count(*) from source_events where org_id = :o and captured_at > :deploy group by 1;
#   select count(*) from source_events where org_id = :o and captured_at > :deploy and outcome = 'dropped';  -- 0
```

## 7 · Risks

| Risk | Guard |
|---|---|
| Keeping marketing mail longer than before | encrypted, unread by any model, expiring; D4 is yours |
| Too much reaches `deep` and the reading bill rises | the S2 budget stays; the golden noise cases gate precision; the tier is visible per mail, so drift is measurable |
| A connector list that grows by accident | it is a line in the brief, which you confirm (`STEP-07`) |
