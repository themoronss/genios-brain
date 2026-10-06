# STEP-05 · TO BUILD · every kept mail, meeting and screen item enters memory

**Owner:** Claude. **Depends on:** `STEP-03` (nothing is deleted any more) and `STEP-04` (who is
us). **Moves:** items in memory **~27 of 395 mails · 2 of 34 meetings → ≥ 95%**.

---

⚠️ **Re-checked against the code on 2026-10-06, claim by claim (§8), after STEP-02, STEP-03 and
STEP-04 landed.** The direction holds; the design changes in four places: a mail with no signal
enters memory **with its L1 extraction** — it was already read, so it costs no model call — not as a
bare skeleton; archived mail enters as metadata only; every recovery path ends in a re-read, because
no code reads the `route` the drain sets; and screen does not create people (a deliberate privacy
rule). §3 below is the draft; §8.4 is what is built. Rohit's go, 2026-10-06: *"step 5 start karo"*,
with D20–D22 at their defaults.

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

---

## 8 · The check of 2026-10-06 — what the draft got right, and wrong

Every claim was re-read against `speedrun008` @ `c0e24f00` (STEP-02, STEP-03 and STEP-04 built) by a
read-only pass and the decisive ones by hand. Production was not read.

### 8.1 · Measured — on the golden set

| | |
|---|---|
| must-detect cases lost **before memory** | **10 of 32** — F04, F05, F06, F07, F10, F11, F19, F24, F26 (each "dropped at the qualification floor", finding F44) and case F44 (a Gmail investor's ask). Each was **read** by L1 — its extraction exists — and has no active signal, so `_pull` never takes it |
| must-abstain cases **not exercised** | **4 of 12** — F36, F39, F41, F43: the founder's own sent mail never reaches memory, so the decision not to card it is never made |
| what L2 can see of a kept mail with no signal | **nothing** — `context/runner._pull` inner-joins an active signal (`:237-247`), inner-joins `raw_payloads` (`:235`) and takes `outcome = 'emitted'` only (`:250`) |

### 8.2 · The claims

| Claim | Verdict |
|---|---|
| L2 pulls only events with an active qualified signal | ✅ — `context/runner.py:235-250` (lines moved −7) |
| an event with no signal "waits forever" in `held_missing_qes_extraction` | ⚠️ the effect is true, the mechanism is not: an event with no signal is never pulled at all and gets no ledger row. `held` is for an event that HAS a signal whose extraction row is missing (`runner.py:153-158`, `:291-298`) |
| read mail that fitted no box never reaches the graph | ✅ — `capture/esqe/qualification.py:857-861`; and a second gate the draft did not cite: the publication floor (`DEFAULT_FLOOR_BP = 2500`, `:78`) |
| meetings become deadlines, then expire | ✅ — mapper → `DEADLINE_STATED` → expiry, all lines exact. `commit_structured` is the ONLY writer of a `meeting` node, and only for a pulled event |
| recovery is a flag flip | ⚠️ partly — the parked drain, manual recover, refetch and recapture still only flip `outcome`; ❌ "extraction parks are in no drain set" is no longer true (`STEP-18` B18 re-reads them, `capture/landing/unread.py:145-292`); `poison_quarantine` still is |
| "already better on `harsh/mvp`: `adb04093` — new recoveries reach extraction" | ❌ **no code reads `source_events.route`.** L1 extraction runs only inline at capture; a re-admitted row gets no extraction and no signal, so `_pull` never takes it. Every recovery path ends where it began |
| screen items attach only to people who exist | ✅ — and that is a **deliberate privacy rule** (`reason/moments/screen_memory.py:10-15`: *"A screen never CREATES a person: nodes are listed org-wide"*). The draft's 3.7 would reverse it |
| the no-model writers exist | ✅ — `process_event` with an empty `Extraction` makes no model call and writes person, company, thread, edges, direction and ball-in-court; seven tests already drive it |
| (new) a kept mail with no signal already has its L1 extraction | ✅ — `l1_extraction_results` holds it (indexed by event, `migrations/0080`); the QES adapter can project it with no model call |
| (new) a skeleton committed as `committed` is billed as a message read | ✅ — `api/routes._BILLABLE_L2_OUTCOMES` |
| (new) archived mail must expose no text (`03` F37, F57) | ✅ — every reader of words selects by correlation membership; an archived mail has no prepared text, and `_clean_for_llm` would otherwise decrypt and preprocess its body |

### 8.3 · What changes in the design

1. **Memory is not gated on a signal — and a mail with no signal is not a skeleton.** Its L1 extraction
   already exists, so L2 reads it with **no model call**, at the confidence it scored, marked as below
   the floor. The floor goes on deciding what becomes a SIGNAL (an alert); it stops deciding what is
   REMEMBERED. Neel Jain's question, Manik's traction ask and Theresa's update enter memory with their
   words, not just their names.
2. **An archived mail becomes metadata only:** who wrote to whom, when, in which thread — from the
   ledger's own columns, with no text and no decryption, no ball-in-court and no correlation (it was
   judged noise). Pankaj, Silas and Ori become people.
3. **A calendar event is always a meeting**, signal or not — with its organizer, and the latest
   version winning.
4. **Every recovery is a re-read**, not a flag: a kept mail with no L1 extraction (a re-admitted
   park, a refetch, a recapture) is queued into the re-read ladder STEP-18 B18 built, so it gets an
   extraction and then memory. **Promotion out of archive** — the half STEP-03 handed to this step —
   is the same re-read, started by a rule (a connector the brief names) or by hand.
5. **Screen does not create people** (the draft's 3.7 is dropped): a private WhatsApp contact must
   not appear org-wide, and graph nodes carry no visibility. Revisit with seat-private nodes in
   `STEP-09`.
6. **Guarded volume and cost:** the first sweep after the deploy commits hundreds of events; every
   L2 transaction takes the org's graph-version lock, so it is serial — the existing batch limits
   hold, and a new subject is decided once (`STEP-02`'s gate), not every sweep.

### 8.4 · What will be built — tree block `yc2_w27_s05` (milestone M23), proposed

| # | Units | Where | What |
|---|---|---|---|
| C1 | 1 | new `context/memory_lanes.py` | which road a kept event takes into memory, decided in one pure function: **signal** (as today), **below the floor** (its L1 extraction, no model), **metadata** (archived: the ledger's columns), **calendar** (always structured) — and none for a screen session |
| C2 | 2 | `context/runner._pull`, `api/routes._pending_count` | the pull admits every kept event — the signal join and the payload join become left joins, `archived` is admitted, `se.recipients` and the event's own L1 extraction are selected; a row with a run already settled is never re-pulled (no starving the drain); the pending count asks the same question |
| C3 | 5 | `context/qes_adapter.py`, `context/runner._process_one`, `context/pipeline.process_event`, `context/structured.py`, `api/routes._BILLABLE_L2_OUTCOMES` | the adapter projects an extraction with no signal at its own confidence, marked below the floor; the drain dispatches by road; a metadata event writes people, companies, the thread and `corresponded_with` — no text, no ball-in-court, no correlation; a meeting keeps its organizer and the newest version wins; a metadata write is not billed (D21) |
| C4 | 4 | `capture/landing/unread.py`, new `capture/landing/promote.py`, `scripts/promote_archived.py`, `scripts/reprocess_stranded.py` | any kept mail with no L1 extraction is queued into B18's re-read ladder — so every recovery path ends in a read, not a flag; promotion out of archive is the same re-read, by rule or sender, dry run first; the stranded rows from before, through the same ladder, once |
| C5 | 3 | `tests/replays/` | the golden board re-recorded — the ten cases lost before memory now reach it, the four not-exercised are exercised, every move named; the acceptance on every case: every kept mail has entered memory, every calendar event is a meeting, no archived mail's words are readable, no screen contact became a person |
| C6 | 2 | `platform/receipts.py`, `scripts/pipeline_health.py` | *every kept event has entered memory*; *every calendar event is a meeting* — read-only |

**17 units.** Order: C1 → C2 → C3 → C4 → C6 → C5 (the board and the acceptance last). Not in this block,
with the reason: the meeting ↔ thread link (no writer exists; `STEP-09` groups them); screen-made people
(D22); `poison_quarantine` (nothing stored — a connector re-fetch, `STEP-08`).

### 8.5 · Decisions

| | Question | Default, if you say nothing |
|---|---|---|
| D20 | a kept mail with no signal enters memory **with its L1 extraction** (its words, at the confidence it scored) — or as names and dates only? | **with its extraction** — the asks the expert needs are in it, and it costs no model call |
| D21 | is a memory write with no model read — an archived mail's metadata — billed as a message read? | **no** — only what a model read is billed |
| D22 | the draft's 3.7 (screen creates people) — drop it from STEP-05? | **yes, drop** — privacy; revisit with seat-private nodes in `STEP-09` |

### 8.6 · Production — the numbers to read after the deploy (read-only)

```
-- kept events with an L2 run, share (target ≥ 95%)
select count(*) filter (where r.event_id is not null)::float / nullif(count(*), 0)
  from source_events se left join l2_processing_runs r on r.org_id = se.org_id and r.event_id = se.event_id
 where se.org_id = :o and se.outcome in ('emitted', 'archived');
-- meetings vs calendar events (target equal)
select (select count(*) from graph_nodes where org_id = :o and node_type = 'meeting' and valid_to is null),
       (select count(distinct source_object_id) from source_events where org_id = :o and source = 'gcal');
```
