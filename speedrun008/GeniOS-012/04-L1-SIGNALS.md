# 04 · L1 Signals (`capture/`): bring the founder's work in, whole and named (D4–D13)

**Written for:** coding agents (units) and Harsh (the production runs).
**Fixes:** D4–D13 of [02](02-THE-PATH-OF-ONE-MAIL.md).
**Atlas v2 target for L1** ([GeniOS-008 00-ARCHITECTURE](../GeniOS-008/00-ARCHITECTURE.md)): L1 captures what the sources hold, qualifies it, and publishes a `QualifiedEnterpriseSignalBundle` with a **coverage receipt** that says what was and was not read. L1 never decides what a mail *means for the business*; that is L2.

**Cards this file unlocks** (with later steps): `i1`, `i2`, `i4`, `i6`, `s1`, `s2`, `h1`, `b3`, `l1` (the window); `b1`, `b3`, `f3` (Boardy); `f2`, `l1`, `c1` (portals); `f1`, `i3`, `b2` (calendar); `p1` (sent claims).

---

## Part A · The history window (D4, D5, D6)

### What happened, and how

- Onboarding asks the founder how far back to read. The answer is stored in `integration_preferences…historical_backfill`, but **nothing writes it to the connection**. Capture reads only `connections.capture_scope.backfill_days` (`capture/connectors/backfill.py:73` `backfill_window_for`), default **60** (`:37`).
- 60 days was chosen to bound the first sync's cost and time. It is right as a default for a stranger; it is wrong for a founder whose fundraise started 6–11 months ago. The benchmark of September (P3/P4, 6- and 12-month questions) already showed that a 60-day window makes long-horizon questions unanswerable.
- When L2 asks for more evidence, the window fetcher is built by `api/routes.py:3596-3611` `_need_fetchers` with `Connection(config={})`, so it also uses 60 days, even after an admin widened the connection.

### Units

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **S09.U3** | Rohit | Decide the window | Recommended **365 days** for founders (covers every card on `/preview`); 180 loses the April cases. GeniOS-011 [06 D16](../GeniOS-011/06-DECISIONS.md). | one line in [13-LOG](13-LOG.md) | 🔒 Rohit |
| **S09.U1** | Claude | The window the founder picks is the window captured | Write `historical_backfill` through to `capture_scope.backfill_days` when the founder saves it (`api/account_routes.py`), and when a connection is created; the coverage receipt (`capture/coverage/window.py`) states the window actually read. | a new connection with "12 months" chosen syncs `newer_than:365d`; the receipt says 365. Mutation: drop the write-through → red | 🔨 (GeniOS-011) |
| **U12-04** | Claude | Evidence fetchers use the connection's real window | In `_need_fetchers`, build the `Connection` from `_saved_connection_config` (`routes.py:3754`) instead of `config={}` | a test connection with `backfill_days=365` gives a window fetcher whose query is `newer_than:365d`. Mutation: back to `{}` → red | ⬜ |
| **S13.U4** | Harsh (+Claude wiring) | Arm the evidence fetchers | `GENIOS_NEED_FETCHERS=on` in the deploy env (`capture/acquire/need_fetchers.py:34-39`). Claude: the HOLD → EvidenceNeed → resolve wiring (`needs_from_holds`, `resolve_hold` have no production caller). | `evidence_needs` rows move off `open` within a sweep | 🔒 Harsh · ⬜ wiring |
| **S09.U2** | Claude | Business facts for old mail | `backfill_business_facts` has no caller, so mail filed before the fix never got `thread.objective` / `party.role`. Give it one caller, after a resync, bounded per run. | after a resync, old threads carry `thread.objective` | ⬜ |
| **S09.U4** | Harsh, after Rohit's spend yes | The 365-day resync for Rohit's Gmail and Calendar | The runbook is the docstring of `scripts/resync_deleted_mail.py` (STEP-08 §8.6), in this order:<br>1. `python scripts/resync_deleted_mail.py --org <ORG> --days 365` (a **dry run** by default, read-only): counts by deleting rule, month and sender domain, and what the window leaves out. Send it to Rohit.<br>2. **Cost estimate before any spend:** the dry run's message count × (gate batch share + extraction calls per kept mail). Rohit says yes to the number. No paid pass without it.<br>3. `PATCH /connections/{gmail}/backfill-window` with 365 (and the Calendar connection), unless S09.U1 already did.<br>4. `… --apply --days 365`: frees the keys of the mail the old gate deleted (it refuses while the connection lists fewer days). Needs `GENIOS_ALLOW_PROD_WRITE=1`.<br>5. `POST /connections/{gmail}/backfill`: the legacy door, every message fetched **in full**. **Never** `/integrations/gmail/sync`, which keeps rule-junk as a list snippet. Wait for `backfill drain done` in the log; a `TRUNCATED` drain spent its page budget, so run it again with a larger page (`?limit=100`).<br>6. `… --finish`: supersedes what came back and says why the rest did not.<br>7. `python scripts/pipeline_health.py`: *every Gmail message in the window has its content, or a stated reason* must pass.<br>8. Re-file into L3 with `backfill_correlations` (**not** `rebuild=True`, see [05 D23](05-L3-CONTEXT-GRAPH.md)), then S09.U2.<br>9. Watch the ingestion meter: a 365-day sync can fill the quota (the `sync_quota` gate). | `pipeline_health` passes; `daily_health` funnel "events in" rises; the August accelerator thread is a `source_events` row with its body | 🔒 |

**Page ceiling (D5):** `_BACKFILL_MAX_ROUNDS = 200` (`routes.py:3617`) ≈ 5,000 messages per source. Enough for Rohit. For a customer with a large mailbox, the coverage receipt must say "stopped at 5,000 of N" rather than imply the window was read whole. That is part of **S10.U1** (`l1_sync_runs` carries what was skipped).

---

## Part B · The gate: founder mail is not newsletters (D7, D8, D9)

### What happened, and how

The gate exists because the old pipeline drowned in newsletters (the 4 Oct audit: "S1 drop DELETES content" for 258 mails). Its deterministic rules are cheap and mostly right. Three founder-specific mail shapes look exactly like newsletters to them:

| Shape | Rule that archives it | Why it looks like a newsletter | Cards |
|---|---|---|---|
| **Intro platforms** (Boardy) | N-02: `List-Unsubscribe`/`List-Id`/`List-Post`/`Feedback-ID` header (full-fetch stage) | the platform sends every personal intro through a bulk mailer | `b1`, `b3`, `f3` |
| **Programme and government portals** | N-03: no-reply / notify local part, no attachment; N-06: Promotions tab | portals send from `no-reply@` and Gmail tabs them as Promotions | `f2`, `l1`, `c1` |
| **Short investor replies** | the batch judge (`relevance.py:113`, `prime` `:266-293`) at relevance < 0.25 | it sees a masked subject + 600-character snippet, **no sender, no domain, no "replies to us"**; the prompt has no application/programme status class | risk to `i1`, `i2` |

The bypasses that should save them exist but are empty for Rohit: **W-07** (a sender named in the company brief), **W-01** (a known counterparty), **W-02** (starred). A soft rule is overruled only when the batch verdict says keep at ≥ 0.70 (`_overruling_keep`, `gate/gate.py:53-66`).

### Units

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **S02.U4** | Rohit + Harsh | Name the senders in the brief (W-07) | See [03 Part B](03-RUN-GATE-AND-SWITCHES.md). Domains, not only addresses: the intro platform, each portal, each fund and programme. | a fresh portal mail's gate trace shows `W-07` | 🔒 |
| **S06.U4** | Rohit reads, Harsh runs | Bring back what was already archived | `python scripts/promote_archived.py --org <ORG> --rule N-02 --sender-domain boardy.ai` (dry run) → Rohit reads the list → `--apply --crypto-key …` with `GENIOS_ALLOW_PROD_WRITE=1`. Since S06.U2 it re-fetches each body first; a mail it cannot fetch stays archived ("NOT FETCHED"). Repeat with the portal domains under N-03/N-06. Then re-file (`backfill_correlations`), because archived mail was never correlated ([05 D14](05-L3-CONTEXT-GRAPH.md)). | promoted mail has full bodies and is in a file | 🔒 |
| **S08.U1** | Claude | The judge sees who wrote | Pass sender display name, sender domain, `reply_to_us` (the thread holds our outbound) and `has_attachment` into `prime` and `classify` (`gate/relevance.py`), unmasked for the domain only. Bump the gate version so S06.U1's re-judgment covers old verdicts. | golden F18 (a real fund archived as junk) is kept; the junk-rate on the golden newsletters does not rise. Measured with the live pass S07.U3 | ⬜ |
| **U12-05** | Claude | Founder mail classes in the gate | (1) Add an **application / programme status** class to `_GATE_PROMPT` and `_GATE_BATCH_PROMPT` as ALWAYS KEEP, next to introductions. (2) Let N-02 be overruled below 0.70 when the sender domain is a known intro platform (a reviewed list in `capture/gate/`, starting with one entry) or the batch verdict says `introduction`. Files: `capture/gate/relevance.py`, `capture/gate/rules.py`, `capture/gate/gate.py`, tests with synthetic mail (no real names). | a synthetic platform intro with List-Unsubscribe is kept; a synthetic newsletter from the same mailer software is archived; a synthetic "your application is incomplete" portal mail is kept. Mutation per rule → red | ⬜ |
| — | Claude | Wire the whole-message reader | follow-up (a) of GeniOS-011: call `composio.whole_message_reader` from `api/routes._reread_unread`, and add a re-fetch rung for DOC-05 email parks. | a DOC-05 park re-fetches on the next sweep | ⬜ |

**Note on D9 and cost:** mail the judge confidently calls junk keeps only its list snippet in the archive (`_skip_body`, `composio.py:723`). That is a deliberate cost choice. With S08.U1 and U12-05 the judge errs less; promotion re-fetches the body when it does.

---

## Part C · Words for the founder's work (D10, D11)

### What happened, and how

The 16 `SignalType` members (`contracts/signal.py:210-299`) were designed for an operations admin: commitments, deadlines, decisions, approvals, renewals, obligations, risks. A founder's week is intros, meetings, investor interest, applications and requests. With no word for them, the extractor picks the nearest wrong word or none, and the open lane (`unclassified_observations`) has no reader.

### The choice (Rohit, S12.U1)

| Road | What | For | Against |
|---|---|---|---|
| **A. New L1 words** (recommended in GeniOS-011) | add `introduction`, `meeting`, `investor_interest`, `application_status` (and optionally `request`) to `SignalType` | every downstream layer can trigger on them; the L2 pass starts on them | touches the enum, the classifier precedence, the ALG-17 importance weights, normalization, the detector, and a migration widening the CHECKs on `qualified_signals`/`qualification_drops` |
| **B. Keep L1 generic, name it in L2** | founder concepts become Founder Office situations, triggered by any signal on a file whose kind (brief line) is investor/program/intro | no L1 contract change | the L2 pass still never starts on mail that produced no signal at all, which is the problem |

### Units

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **S12.U1** | Rohit | Pick the road and the words | default road A, four words | logged | 🔒 |
| **S12.U2** | Claude | The new types end to end | `contracts/signal.py` (enum + docstring "16" → "20"), `capture/esqe/classifier.PRECEDENCE`, `esqe/importance.py` (ALG-17 weights for the new types), `esqe/normalize.py`, `esqe/detector._detect_all` (one detector per type, each needing an object and a counterparty), migration `02xx_signal_types_founder.sql` widening the CHECK constraints, and the extraction prompt's type list. Synthetic golden cases: an intro, an application reminder, an investor's "come back when", a booked meeting. | each synthetic case produces exactly its type; the 16 old types' golden results are unchanged | ⬜ after S12.U1 |
| **U12-06** | Claude | The open lane is read | A weekly count of `unclassified_observations` by the extractor's proposed label, in `daily_health` (or a staff route), so new words are chosen from data, never guessed again | the count exists; the top labels are visible | ⬜ |

---

## Part D · The calendar (D12)

### What happened, and how

- `capture/connectors/calendar.py` fetches events (`_fetch` `:66`, `_to_raw` `:109-191`). They take the **structured path** (`capture/structured/registry.py:203-218` `gcal.event.v1` → `mapper.py:392,410-416`): a `meeting` node with title, start, end, status and organizer, plus `attended` edges to attendees. No model call.
- There is no meeting signal type. The intent maps to `schedule`; start/end become `dates_mentioned`, so the only predicate that can fire is `DEADLINE_STATED` (`stated_date_without_commitment`).
- The follow-through reading (`context/meeting_touch.py`, `_MEETINGS` `:81`) needs an external attendee and a meeting in the past, and drops cohort or internal meetings. `context/lane_health.py` lists `meeting` among the **dormant** readings.
- Measured 4 Oct: **0 of 22** past meetings reached the graph as anything a card could use.

### Units

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **U12-07** | Claude | A meeting is an event the chain can use | (1) With road A: map `gcal.event.v1` to the new `meeting` type (registry intent `schedule` → `meeting`), with the external attendees as the counterparty. (2) Make `meeting_touch` read meetings whose organizer is us and whose attendees include an external person, past and coming. (3) Correlate the meeting into the attendee's file (L3), so the dossier's "its own meetings" (D25) has it. Files: `capture/structured/registry.py`, `mapper.py`, `capture/esqe/detector.py`, `context/meeting_touch.py`, `context/meeting_situations.py`. | on a synthetic calendar of 22 past external meetings, 22 reach files; a past meeting with no mail after it gives one `meeting_without_follow_through` situation; `lane_health` no longer lists `meeting` dormant | ⬜ after S12.U2 |
| **S36.U1** | Claude (built) | The meeting follow-up card opens (was a 404) | ✅ `f3579b0d` | — | ✅ |

---

## Part E · The founder's own claims (D13; the L3 half is in [05](05-L3-CONTEXT-GRAPH.md))

### What happened, and how

Sent mail is captured and marked outbound (`capture/pipeline.py:515`). Extraction fills `ExtractionResult.amounts`, but **`context/pipeline.py` never writes amounts to the graph**. There is no lane for "what we said about ourselves". So when the founder tells four investors four different traction numbers, nothing in the product can see it.

### Units

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **N1a** (07's N1, capture half) | Claude | Extract the founder's quantitative self-claims | New `capture/extract/self_claims.py`: for **outbound** messages only, take each quantitative claim about us (metric, value, unit, period, date, recipients). Metric names come from a reviewed vocabulary in Plane D (`S12.U4` metric definitions): `arr`, `mrr`, `customers`, `partners`, `pilots`, `users`, `revenue`. An unknown metric is kept as `other.<word>` and never compared. | a synthetic sent mail "we're at $10k ARR" gives one claim `arr=10000 USD`; a received mail's number gives none. Mutation: drop the outbound filter → red | ⬜ |

---

## Part F · Bounces (D21, L1 side)

Nothing to fix in L1. A real delivery report is recognised (`gate/rules.py:219` `is_a_delivery_report`), kept, never shown to the junk judge, fetched whole, and can emit `DELIVERY_FAILURE`. The loss is in L3 and L5: see [05 Part F](05-L3-CONTEXT-GRAPH.md) (N4).

---

## Part G · Connector hardening (keep the mail coming)

| Unit | What | Status |
|---|---|---|
| **S11.U1** (Harsh) | record the production Composio toolkit versions and a live history fixture | 🔒 |
| **S11.U2** | pin toolkit versions; refuse `dangerously_skip_version_check=True` | ⬜ |
| **S11.U3** | Gmail incremental sync keyed on `historyId`, with a bounded gap backfill (today it keys on a date, `composio.py:418-430`) | ⬜ |
| **S10.U2** | Sync now runs the sweep's chain (today it runs a second copy with no funnel numbers and no post-passes) | ⬜ |

---

## After this file: what should be true

1. Rohit's Gmail and Calendar are read back 365 days, with a receipt that says so.
2. Boardy intros, portal mail and short investor replies are kept, and the old ones are promoted with full bodies.
3. Founder work carries founder words (`introduction`, `meeting`, `investor_interest`, `application_status`).
4. Past and coming external meetings are events in their attendees' files.
5. The founder's own numeric claims are captured from sent mail.

**Expected after Steps 1–3 (old lanes):** `f4`, `i6`, `b1`, `b3`, `l1`, and with the new words `f1`, `f2`, `i3`, `b2`. Record what actually appears in [13-LOG](13-LOG.md).
