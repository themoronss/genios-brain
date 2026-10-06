# STEP-03 · TO BUILD · the gate sets attention, it never deletes

**Owner:** Claude. **Depends on:** `STEP-00`. **Decision:** `06` D4 (how long low-attention mail is
kept). **Moves:** new mail with its content deleted at the gate **258 → 0**; every mail carries an
attention tier and the reason for it.

---

⚠️ **Re-checked against the code on 2026-10-06, claim by claim, and measured on the golden set** (§8).
Every drop the draft named is real, and three more exist; two claims are wrong in production; and
the parts that need the company brief wait for `STEP-07`. **What is being built is §8.3** — tree
block `yc2_w27_s03`, 17 units, on Rohit's go (*"step 3 start karo fully"*).

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

## 8 · The check of 2026-10-06 — what the first draft got right, and wrong

Every claim was re-read against `speedrun008` @ `aaca7e67` by two read-only passes, verified at the
cited lines, and the gate was measured on the golden set (all 40 founder cases, recorded answers).

### 8.1 · Measured — what the gate does to the golden set today

86 mail objects across the 40 cases: **51 emitted, 2 parked, 33 dropped with their content gone** —
`N-02` 16, `N-03` 8, `N-06` 4, `llm_junk` 4, `N-07` 1.

| Where it hurts | Objects dropped | Code |
|---|---|---|
| Boardy's intros and nudges (F03–F09) | 13 | `N-02` (the unsubscribe header) |
| Government portals (F01, F02, F23) | 7 | `N-06` (Promotions), `N-03` (no-reply) |
| A bounce report (F16) | 1 | `N-03` |
| Brief-only programme mail (F18, F21, F22) | 4 | `llm_junk`, `N-02` |
| Newsletters, receipts, digests (F32–F34, F37) — must not become cards | 8 | `N-02`, `N-03`, `N-06`, `N-07` |

**Found measuring it:** in F09 the founder had replied to Boardy and Boardy's answer was still
dropped. `sender_known`'s sent-folder half (`api/routes.KNOWN_FROM_SENT_SQL`) counts only mail sent by
an address in `org_seats`, and the golden tenant has no seat — so W-01 never fires on the golden set.
In production it holds only if the seat's address is the connected mailbox; that is `STEP-04`'s
question ("who is us"), and the runner gains a seat there.

### 8.2 · The claims

| Claim | Verdict |
|---|---|
| every noise rule is a drop | ✅ — N-01/02/03/04/06/07/08/09 each `return (code, "drop")`. ⚠️ Three more drops the draft missed: N-10 (empty body), S0 `out_of_scope`, S2 `llm_junk`. N-05 no longer drops |
| a drop keeps no body | ✅ — only kept mail and the one judged drop (`llm_junk`) keep a payload; ⚠️ and much dropped mail never had a body to keep: the connector fetches only the list snippet for N-09/06/07/03 and confident `llm_junk` (`composio.py:454-507`) — so keeping content is a connector change too |
| a dropped mail can never come back | ✅ for N-code drops (dedup ignores outcome; no payload). ⚠️ `llm_junk` drops DO come back: `drain_parked` flips judged drops to `emitted` on every heartbeat without re-running the gate (`capture/parked/drain.py:131-201`) |
| the 30-day emitted TTL strands events | ✅ — `_pull` inner-joins `raw_payloads`; after the purge the row stays `emitted` and is never drained; `_pending_count` counts it forever |
| the S2 park reason is thrown away | ❌ in production — the model's parks are `llm_junk_unconfident` and keep their reason; `low_relevance` (no reason) is reachable only with the rule-based classifier |
| Boardy can never be an agent | ✅ — `actor_type="external_contact"` is hard-coded (`composio.py:364, 609, 696`). ⚠️ And stamping it would not be enough: only `sender_known` skips the AI filter, whose prompt still lists "automated matchmaking" as a drop class |
| no tenant allow-list exists | ✅ — `approved_sender`, `sender_blocked` are read and written nowhere; the comment "fed by tenant config" is false |
| the relay detector says an address introduces people | ❌ — it decides whether a From address relayed a message, and runs only after the gate (`context/pipeline.py:1101-1107`) |
| the AI filter decides existence, blind | ✅, blinder than drafted — no company context and not even the sender's name or address in the prompt; it answers keep/drop only |
| promotion through `STEP-05`'s re-process path | ❌ — no path selects "joined a workstream"; `find_unread` reads only `emitted` rows; `STEP-05` §3.5 is unbuilt |
| a new outcome value is cheap | ⚠️ — `sync_runner` does `setattr(summary, outcome, …)`: an outcome with no `SyncSummary` field raises; nine readers of `dropped` (receipts, scripts, six test files) |

### 8.3 · What is being built — tree block `yc2_w27_s03`, before `STEP-07`

The parts that need the company brief (the AI filter reading with context; a connector list) wait for
`STEP-07`; promotion out of archive waits for `STEP-05`; the founder's seat in the golden runner moves
to `STEP-04` (it is "who is us", and measuring STEP-03 cleanly means not moving W-01 in the same
block). What is built now is the whole of "never delete":

| # | Unit | Where | What |
|---|---|---|---|
| 1 | `M21.C1.L-contract.V0.U01` | `migrations/0192_attention_and_archive.sql` | `source_events.attention` (deep · skim · archive) and `attention_reason`; `l1_sync_runs.archived` |
| 2 | `M21.C1.L-contract.V0.U02` | `contracts/trace.py` | `archive` is a stage action |
| 3 | `M21.C1.L-contract.V0.U03` | `capture/attention.py` | the tiers, and which one an outcome gets, with its reason |
| 4 | `M21.C1.L-data.V1.U04` | `capture/journey.py` | `archive` stops an event — the per-event walk says where |
| 5 | `M21.C2.L-logic.V1.U01` | `capture/gate/gate.py` | every mail drop (N-01…N-10, S2 `llm_junk`) becomes `archive` with its code; S0 `out_of_scope` stays a drop |
| 6–7 | `M21.C3.L-data.V2.U01–U02` | `capture/landing/repository.py`, `pg_repository.py` | the attention columns written |
| 8 | `M21.C3.L-logic.V3.U03` | `capture/pipeline.py` | an archived mail keeps its payload and prepared text for 180 days and is read by no model; the emitted TTL goes 30 → 180 days |
| 9–13 | `M21.C4.*` | `sync_runner`, `api/routes`, `parked/drain`, `platform/receipts`, `scripts/workstream_funnel` | every reader of `dropped` learns `archived`; the drain treats an archived `llm_junk` exactly as it treated a dropped one (F55) |
| 14–16 | `M21.C5.*` | the golden set | `archived` in the case contract; the marking; **the acceptance: 0 drops across all 40 cases** |
| 17 | `M21.C6.L-interface.V5.U01` | `scripts/pipeline_health.py` | no mail captured in a day was dropped |

**Decided here, with the reason:** S0 `out_of_scope` stays a drop — it is a scope exclusion, and no
caller passes it today. `skim` is declared and not written: it is the tier the brief assigns
(`STEP-07`). Parked mail is `deep` — it is waiting to be read.

The production number, after the deploy: new mail with its content deleted at the gate, 258 of 395
→ **0** (`select count(*) from source_events where org_id = :o and outcome = 'dropped' and captured_at > :deploy`).
