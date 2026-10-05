# STEP-05 · TO BUILD · every kept mail, meeting and screen item enters memory

**Owner:** Claude. **Depends on:** `STEP-03` (nothing is deleted any more) and `STEP-04` (who is
us). **Moves:** items in memory **~27 of 395 mails · 2 of 34 meetings → ≥ 95%**.

---

## 1 · What is true now

| | Evidence |
|---|---|
| L2 pulls only events with an **active qualified signal** | `[CODE]` `context/runner.py:244-254` — an inner lateral join; and an inner join on `raw_payloads` (`:242`) |
| An event with no signal waits forever | `[CODE]` `context/runner.py:162-167` `held_missing_qes_extraction`; `context/pipeline.py:862-871` raises without an extraction and a model |
| Read mail that fitted no box never reaches the graph | `[CODE]` `capture/esqe/qualification.py:857-861`; `[PROD]` Neel Jain (Insight), Theresa, Hub71's applications, Sal Stabler, Manik — read, no signal, not in memory |
| Meetings become deadlines, then expire | `[CODE]` `capture/structured/mapper.py:392-394` → `capture/esqe/detector.py:267-274, 347-351` (`DEADLINE_STATED`) → expires 30 days after the date (`capture/esqe/lifecycle.py:357-375`); a meeting 30–60 days old is published already expired and never drained `[inference]`. `[PROD]` 18 of 20 expired; 2 meeting nodes |
| Recovery is a flag flip | `[CODE]` `capture/parked/drain.py:151-154`, `api/routes.py:2453-2473`, `capture/parked/refetch.py:849-851`, `capture/parked/recapture.py:262-274`; extraction parks and `poison_quarantine` are in no drain set |
| Screen items attach only to people who already exist | `[CODE]` `reason/moments/screen_memory.py:52-102`; screen-session events carry no semantic lane `[inference]` |
| The no-model writers already exist | `[CODE]` `context/pipeline.py`: `_person` 970-1007, `_works_at` 1011-1043, recipients and `corresponded_with` 1183-1225, outbound direction and ball-in-court 1233-1301, `_thread_node` 466-488, inbound 1719-1760; meetings `context/structured.py:36-142` |
| Already better on `harsh/mvp` | `adb04093`: a re-admitted park now gets a `route`, so **new** recoveries reach extraction. Old rows stay unrouted |

## 2 · Why

The expert's files (`STEP-09`) are built from memory. Today memory holds 7% of the mail and 6% of
the meetings — the rest is the work Startup India, Boardy and the investors live in.

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | pull everything kept | `context/runner.py:218-270` | the signal join becomes a **left** join; `raw_payloads` becomes a left join with fallbacks to `source_events.actor`, `recipients`, `parent_object_id` and `prepared_content.direction`; `_pending_count` (`api/routes.py:3297-3317`) kept in step |
| 3.2 | the skeleton path | `context/runner.py:162-167`; `context/extract/extractor.py:16-54` | an event with no signal gets an **empty `Extraction`** → the existing writers record person, company, thread, edges, direction and ball-in-court, **with no model call**. A new run status, `skeleton`, is re-admitted when a signal lands later, so the event is upgraded rather than skipped |
| 3.3 | metadata-only memory for archived mail | same | an `archive`-tier mail still yields its skeleton: who wrote to whom, when, in which thread. That alone would have made Pankaj, Silas and Ori people in the graph |
| 3.4 | meetings stay meetings | `context/runner.py:138-156`; `capture/structured/registry.py:197-211`; `context/meeting_lifecycle.py` | a calendar event always takes the structured lane and becomes a meeting node with attendees, organizer, start, end and status — **whether or not it has a signal**. A `DEADLINE_STATED` signal may still exist; its expiry no longer hides the meeting |
| 3.5 | recovery is a real re-run | generalise `_reread_unread` (`api/routes.py:1512-1579`) and `capture/landing/unread.py:37-142` | one re-process path — set aside the dedup key, re-land, finalise L1, restore on failure — used by the parked drain, manual recover, attachment refetch, recapture, extraction parks and `poison_quarantine`. It carries the original outcome and a recovery flag so the gate cannot re-drop |
| 3.6 | repair what is stranded | `scripts/reprocess_stranded.py` (Claude writes, Harsh runs) | the unrouted emitted rows and the 69 S2-junked mails that still have their encrypted payload → through 3.5, once |
| 3.7 | screen joins the people | `reason/moments/screen_memory.py:52-102` | when a follow-up names a counterparty the graph does not have, a weak person node is created instead of writing onto the seat's own node |

## 4 · What will happen

| | Today | After |
|---|---|---|
| Neel Jain's mail, 27 Sep | read, no signal, never in memory | skeleton: person Neel · company Insight Partners · thread · ball with you |
| The 8 Oct calendar invite with insightpartners.com | a `DEADLINE_STATED` signal | a meeting node with Neel as attendee — **linked** to his thread |
| Boardy's intro of Pankaj (archived, content gone until `STEP-08`) | nothing | person Pankaj, `corresponded_with` edges to you and to Boardy, the date |
| The 13 Aug call with Lalitha (52 days ago) | expired, vanished | a past meeting, still there for `STEP-09` to ask *"was anything promised?"* |

## 5 · Expected

| Measure | Before | After |
|---|---|---|
| Kept events with an L2 run within two sweeps | ~27 of 395 | **≥ 95%** |
| Meeting nodes | 2 | **34** — every calendar event |
| Boardy's seven contacts as people | 3 (Maria, Nitesh, Lalitha) | **7** |
| Events in a recovery state with no re-run | the 77 unrouted, plus the 69 junked | **0** |

## 6 · Verify

```
GENIOS_TEST_DATABASE_URL=… .venv/bin/python -m pytest tests/context/test_every_kept_event_enters_memory.py -q
#   an event with no signal gets a skeleton and zero model calls; a later signal upgrades it;
#   a meeting with no signal is a meeting node; a recovered park is re-processed, not flipped —
#   each by mutation (reverting the left join, the empty Extraction, the status, the re-run)
.venv/bin/python -m pytest tests/replays -q
# production, read-only:
#   share of kept events with an l2_processing_runs row; count of meeting nodes vs calendar events
```

## 7 · Risks

| Risk | Guard |
|---|---|
| Thousands of skeleton writes on the first sweep | the drain's existing batch size and lease; skeletons need no model |
| Self-identity errors multiplied across all memory | `STEP-04` lands first — that is the dependency |
| A re-run re-drops what it recovered | the recovery flag the gate honours (3.5) |
