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
