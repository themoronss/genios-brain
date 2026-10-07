# STEP-08 · PENDING — owner: Harsh · re-read the mailbox, so the deleted mail comes back

**Depends on:** `STEP-03`, `STEP-04`, `STEP-05`, `STEP-07` deployed — re-reading through the old gate
would delete the same mail again. **Decision:** `06` D5 (how far back; recommended 180 days).
**Moves:** the 258 content-less mails come back with content; the funnel probe is re-run.

⛔ **Also depends on `STEP-18` B20** (found 2026-10-05; tree `yc2_w27/M17.C2.L-data.V0.U02`). A
message that already went through the semantic lane holds a fingerprint claim, and the claim
outlives its event. Re-landed through `set_aside`, or after a disconnect-with-wipe and reconnect,
the copy gets a new event id and is skipped as *seen on screen* — silently, extracting nothing.
The tenant reset (`50c50073`) deletes the fingerprints; the other paths do not.

---

## 1 · What is true now `[CODE]`

| | Evidence |
|---|---|
| A dropped mail cannot be re-fetched | dedup ignores outcome (`capture/pipeline.py:105-107`; `capture/landing/pg_repository.py:44, 58-60`); recovery mode re-scans 7 days and lands everything as duplicates (`capture/acquire/sync_runner.py:589-590`) |
| The only key-freeing code is narrow | `capture/landing/unread.py:57-60` `set_aside`, limited to `outcome='emitted'` |
| The destructive paths | the org reset `POST /api/org/{org_id}/reset` (`api/account_routes.py:907-929`) — on `harsh/mvp` it now erases every org-scoped conclusion table (`50c50073`); disconnect with `wipe_data` (`api/routes.py:3018-3063`); scripts (`scripts/wipe_org_data.py`, `restore_reingest.py`, `regmail_sync.py`) |
| The window | `capture/connectors/backfill.py:37` `DEFAULT_BACKFILL_DAYS = 60`; per connection `PATCH /connections/{id}/backfill-window` (`api/routes.py:2509-2540`) |
| Not a re-sync | `organization_resets` only expires temporary memories (`feedback/reset.py:43-84`) |

## 2 · Two ways, one recommended

| | What | Keeps | Loses |
|---|---|---|---|
| **A · targeted re-fetch** ✅ | `scripts/refetch_dropped.py` (Claude writes it): for every mail event with no content, free its dedup key the way `set_aside` does, re-fetch it by provider id, and re-land it through the new gate | cards, feedback, the brief, everything else | nothing |
| B · reset and backfill | `POST /reset`, set the window to D5, full backfill | — | every card, verdict and conclusion; the brief |

## 3 · Harsh's runbook (A)

1. Confirm `STEP-03`, `STEP-04`, `STEP-05`, `STEP-07` are deployed (`git log` on the deployed commit).
2. Set the window: `PATCH /connections/{gmail}/backfill-window` → D5 days; the same for calendar.
3. `python scripts/refetch_dropped.py --org <org> --dry-run` → the count, by sender domain.
4. Run it for real; watch `scripts/pipeline_health.py`.
5. Re-run the funnel probe and keep the output in `baseline/<date>-after-resync/`.

## 4 · Expected

- every mail event in the window has content, or a stated reason why not (provider says deleted);
- Startup India, Boardy, SINE, Sankalp are back, read through the new gate;
- with your permission (`06` D12), the golden labels are re-checked against the real text.

## 5 · Verify

```
# production, read-only:
#   select count(*) from source_events se where org_id = :o and source = 'gmail'
#     and not exists (select 1 from raw_payloads rp where rp.org_id = se.org_id and rp.event_id = se.event_id)
#     and occurred_at > now() - interval '<D5> days';     -- 0, or each row names its reason
```

---

## 8 · The check of 2026-10-07 — what the 5 Oct plan got right, and wrong

Every claim above was re-read by hand against `speedrun008` @ `18b41f0f` (STEP-02 to STEP-06 built,
STEP-07 not yet). The mechanism was **measured on the golden set**, with cassettes and no spend
(`baseline/yc2w27-s08-check/`: `measure_resync.py`, `resync.json`, `summary.txt`): six cases' noise
mail, archived by today's gate, rewritten to the exact shape production holds for the 258 deleted
mails — `outcome = 'dropped'`, no payload, no prepared text, no attention tier. Production was not
read (Claude's production reads need Rohit's permission); §8.7 is the read-only SQL for Harsh.

### 8.1 · Measured — on the golden set (F01 F02 F03 F09 F16 F32, 13 mails in the deleted shape)

| | Result |
|---|---|
| the same messages listed again, as the code is today | **15 of 15 `duplicate`** (the 13, and two of the founder's own sent mails) — nothing comes back |
| `unread.set_aside` on those rows | **frees 0** — it matches `outcome = 'emitted'` only |
| a deleted row set aside the way `set_aside` does, then `recover_orphans` (it runs at the start of every pass) | comes back as **`emitted` with 0 payloads** — in all six cases. Reusing `set_aside` for deleted mail would forge emitted rows with no content |
| the key freed, the outcome left `dropped`, the messages listed again | **13 of 13 land again** through today's gate, each **with its payload** |
| the finish: every old row whose key the new capture took | **13 superseded**; a second listing lands nothing (all `duplicate`) |
| model calls the cassettes did not hold | **0** |
| what the 13 came back as | **all archived** — kept, readable, not read. Without the company brief (`STEP-07`) the portal's mail (F01, F02) and the intro agent's (F03, F09) return as noise again. They come back **deep**, i.e. read, only when the brief makes their senders known to all four stages that stop them today: the noise rules, the AI filter, the relevance page's service-account and bulk rungs, and the bulk check before extraction (`capture/esqe/relevance.py:500-560`, `capture/pipeline.py:782-785`) |

### 8.2 · The claims

| Claim (5 Oct) | Verdict (7 Oct) |
|---|---|
| a dropped mail cannot be re-fetched — dedup ignores the outcome | ✅ `capture/pipeline.py:106` asks `repo.exists(org, dedup_key)`; `capture/landing/pg_repository.py:46` has no outcome in it. Measured: 15 of 15 `duplicate` |
| recovery mode re-scans 7 days and lands everything as duplicates | ✅ the same dedup (`capture/acquire/sync_runner.py:594`) |
| the only key-freeing code is `set_aside`, limited to `emitted` | ✅ `capture/landing/unread.py:39-42`. ⛔ **New: reusing it is unsafe** — `recover_orphans` (`unread.py:59-71`) turns every `superseded` row whose original key is still free back into `emitted`, so a deleted mail set aside that way and not yet landed again becomes an emitted row with no content (measured, six of six) |
| the destructive paths: the reset, disconnect with wipe, the wipe scripts | ✅ still destructive; and from `STEP-07` the reset erases the company brief too (its table joins `_ORG_SCOPED_TABLES`). Way B stays rejected |
| the window: `DEFAULT_BACKFILL_DAYS = 60`, set per connection by `PATCH …/backfill-window` | ✅ `capture/connectors/backfill.py:37`; `api/routes.py:2730`. ⚠️ **But the window is "how far back a FIRST sync reaches"** (`backfill.py:1-22`): raising it changes nothing until `POST /connections/{id}/backfill` (`api/routes.py:1862`) drains it — the owner-triggered door, which lands through the same gate, sender resolver and semantic lane as every sync and then rebuilds situations over the history it landed (`_replay_l2_history`, `api/routes.py:660`). ⚠️ The window counts back from the day it runs (`newer_than:{days}d`, `backfill.py:63-65`). The first sync after the 3 Oct reset reached back 60 days, to about 4 Aug — already 64 days back today — so **60 days can no longer reach the oldest deleted mail**; §8.7's second query gives the exact day |
| §2 A: re-fetch each deleted mail by its provider id | ⚠️ **Not needed.** A freed key is all a deleted mail needs: the drain re-lists the window and lands it (13 of 13). The by-id call exists (`ComposioGmailConnector.fetch_content` → `GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID`, `capture/connectors/composio.py:288`) but would be a second capture door to keep equal to the first |
| §4: Startup India, Boardy, SINE, Sankalp come back, read through the new gate | ⚠️ back, yes; **read only with `STEP-07`** (§8.1). SINE and Sankalp are newsletters and come back archived — right |
| (new) the fast path | ✅ not on STEP-08's door. The manual backfill builds its connector with no classifier (`make_connector_for(conn)`, `api/routes.py:1876`) — the legacy path, every message fetched in full — so what STEP-08 lands keeps its body even when archived. The fast path (list snippet only for rule-junk and confident AI-junk, `composio.py:425-512`, `03` F58) runs in the onboarding backfill and `_sync_source` (`api/routes.py:3394-3409, 3577-3578`); `STEP-07` must exempt the brief's senders there. The golden runner builds the mailbox with `relevance=None` (`tests/replays/engine_runner.py:245`), so the golden set never exercises the fast path |
| (new) attachments | ⚠️ `capture/landing/reread.drop_reread_attachments` drops a listing's attachment copies by asking whether the PARENT message's key exists. A freed parent key lets its attachments land again — right when they were deleted with the message, **a duplicate** when an attachment survived its deleted message (`attachment_overrides_junk`, `composio.py:828`) |
| (new) calendar | ✅ structured — short-circuited at S1.5 before any noise rule (`capture/gate/gate.py`, `capture/pipeline.py` "gcal etc. always have a mapping"). **STEP-08 is Gmail only** |
| (new) what a re-listing costs | dedup runs at capture, after the connector has listed and full-fetched each kept message (`sync_runner.py:45`, `composio._to_batch`): re-listing the 60 days already synced costs Composio calls and the junk filter's batched calls again — no extraction, no reasoning |

### 8.3 · What changes in the design

1. **One door, not a new one.** Free the deleted mails' keys, widen the window, run the existing
   backfill drain. It lands them through today's gate together with the older history D5/D16 asks
   for, and rebuilds situations over all of it. No new fetch code.
2. **A deleted row stays `dropped` while its key is freed** (marked `#resync:<event_id>`), and becomes
   `superseded` only once the new capture holds its key — never before, or `recover_orphans`
   forges it into an emitted row.
3. **The finish names every outcome**: landed again (superseded, with the new event), or not listed
   (deleted at Gmail, or outside the window) — left `dropped`, with that reason in its trace.
4. **An attachment copy lands only if the earlier copy of that attachment was deleted too.**
5. **After the brief.** `STEP-07`'s accepted brief first, so the portal's and the intro agent's
   mail comes back read, not archived and waiting for a promotion.
6. **The window is Rohit's (D5/D16)** — and 60 cannot reach the oldest deleted mail any more.

### 8.4 · What will be built — tree block `yc2_w27_s08` (milestone M26), proposed

| Category | Units | What |
|---|---|---|
| C1 · the resync ledger | 1 | `capture/landing/resync.py` — `free_deleted` (Gmail rows `dropped` with no payload, inside the window: key marked, outcome kept, one trace row each) and `finish` (superseded where the new capture holds the key, its trace naming the new event; not-listed counted) |
| C2 · attachments | 1 | `capture/landing/reread.py` — a listing's attachment copy is dropped when an attachment of the same message landed kept, and lands when it was deleted with it |
| C3 · the script | 1 | `scripts/resync_deleted_mail.py` — dry run by default (counts by rule, sender domain and month; the oldest; the window it needs), `--apply --days N`, `--finish`; the production guard of `scripts/_db` |
| C4 · what can be read | 2 | `capture/journey` — a superseded deleted row names the event that replaced it; `scripts/pipeline_health.py` — *every Gmail message in the window has its content, or a stated reason* (red until STEP-08 runs) |
| C5 · the golden set | 1 | `tests/replays/test_the_deleted_mail_comes_back.py` — §8.1 as a test: the six cases, a mail Gmail no longer lists (reported, not superseded), an attachment that survived its message (not duplicated), a second run that changes nothing |

6 units, in `tree.yaml` block `yc2_w27_s08` (M26; M25 is kept for STEP-07). Critical path, 3: `C1` →
`C3` → `C5`. The runbook and the decision land in this file and in `08` when the block is built.
Built after `STEP-07` or beside it — nothing here touches what STEP-07 changes.

### 8.5 · Decisions

| | Question | Recommended | Default |
|---|---|---|---|
| D5 · D16 | How far back does the re-sync reach? | **365 days** (`09` D16): P4 needs a year and the 3one4 deferral is from 2 Apr. 180 (`06` D5) loses both | none that works — `06`'s default, 60, cannot reach the oldest deleted mail; **the run waits for Rohit's number** |
| D26 | Run STEP-08 before Rohit has accepted the brief? | **No** — the portal's and the intro agent's mail would come back archived, and need a promotion | no |

### 8.6 · Harsh's runbook — replaces §3

0. Deployed and done first: `STEP-03` … `STEP-07` live; the STEP-04 repair (D14); the STEP-05
   promotion (D23); the brief accepted (`STEP-07`).
1. `python scripts/resync_deleted_mail.py --org $ORG --database-url "$URL"` — the dry run: how many,
   by rule, sender domain and month; the oldest; the window it needs. Send it to Rohit.
2. Rohit names the window (D5/D16).
3. `PATCH /connections/{gmail}/backfill-window` with that number of days.
4. `… --apply --days <N>` — frees the keys; prints how many.
5. `POST /connections/{gmail}/backfill` — wait for `backfill drain done` in the log; re-run while
   it says `TRUNCATED`.
6. `… --finish` — superseded, and not listed with its reason.
7. `scripts/pipeline_health.py` and the funnel probe; keep both outputs in
   `baseline/<date>-after-resync/`.

### 8.7 · Production — the numbers to read first (read-only, for Harsh)

```
-- the deleted Gmail mail, by month and the rule that deleted it (5 Oct: 258 messages)
select date_trunc('month', se.occurred_at) as month, t.reason_code, se.object_type, count(*)
  from source_events se
  left join lateral (select reason_code from event_trace x where x.org_id = se.org_id
                      and x.event_id = se.event_id and x.action = 'drop'
                      order by x.at desc limit 1) t on true
 where se.org_id = :o and se.source = 'gmail' and se.outcome = 'dropped'
   and not exists (select 1 from raw_payloads p where p.org_id = se.org_id and p.event_id = se.event_id)
 group by 1, 2, 3 order by 1, 2, 3;
-- the oldest deleted mail — the shortest window that reaches it
select min(occurred_at), current_date - min(occurred_at)::date as days_back
  from source_events where org_id = :o and source = 'gmail' and outcome = 'dropped';
-- attachments that survived their deleted message (C2's case)
select count(*) from source_events a
  join source_events m on m.org_id = a.org_id and m.source_object_id = a.parent_object_id
                      and m.object_type = 'email_message' and m.outcome = 'dropped'
 where a.org_id = :o and a.object_type = 'email_attachment' and a.outcome <> 'dropped';
-- the Gmail connection's window today
select connection_id, capture_scope ->> 'backfill_days' as backfill_days
  from connections where org_id = :o and source_type = 'gmail';
```

### 8.8 · What it costs `[MODELLED]`

From `03` §F (5 Oct): 395 messages in the 60-day window — about 65% deleted by a rule (no model
call), 17% judged junk by the AI filter, 18% read. A message read costs one extraction (Haiku 4.5,
about $0.01); the filter and the relevance page are batched (12 a call). So the 258 come back for a
few cents beyond the ~37 the brief names (Startup India 5, Boardy 31 → read, about $0.40). Each extra
180 days of history is about 1,200 messages: ~220 read, ~$2.5; 365 days, ~$5. One time. The dry run
prints the real counts before anything is spent.

### 8.9 · Risks

| Risk | Guard |
|---|---|
| a burst of old cards (August's intros and investor mail) | the decider reads age; Rohit sees the first queue; every expiry says why (`STEP-06`) |
| the drain stops half-way (a deploy, a restart) | dedup makes it resumable — run `/backfill` again; `--finish` touches only rows whose mail landed |
| model spend over the daily caps | the caps hold; the backlog drains over days |
| a freed key whose mail never returns | `--finish` reports it; the row stays `dropped`, with its reason |
| an attachment twice | C2, and the acceptance's control |
