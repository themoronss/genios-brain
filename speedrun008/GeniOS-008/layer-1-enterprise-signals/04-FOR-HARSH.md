# L1 Enterprise Signals — for Harsh

**Written for:** Harsh, who deploys and runs production. **Date:** 18 Oct 2026. **From:** the Layer 1 pass in
`speedrun008/GeniOS-008/`.

Read this file top to bottom once. Every command is here or in the deploy runbook it points to. Nothing in Layer 1
needs a decision from you; the decisions are Rohit's and are listed at the end so you know what may come next.

---

## 1 · In one paragraph

Layer 1 (`genios_engine/capture/`) is what reads Gmail and Calendar, decides what deserves attention, extracts
what was said, and publishes signals with their evidence. We checked all of it against the code on 17 Oct. Most
of it is built and works. We found that **production does not run any of it**: production is on `harsh/mvp`
`84f00a40`, 815+ commits behind `speedrun008`. We fixed four Layer 1 defects. **None of them needs a migration,
a new environment variable or a data step.** They reach production with the same deploy you already have a
runbook for.

## 2 · What was there before

| | |
|---|---|
| Production branch | `harsh/mvp` `84f00a40` (10 Oct), schema at `0190_card_lane` |
| `speedrun008` | everything since: the gate keeps every mail (STEP-03), every kept item enters memory (STEP-05), nothing lost silently (STEP-06), the company brief (STEP-07), the resync (STEP-08), workstreams (STEP-09), the expert's numbers (STEP-10) … through STEP-18 |
| What the founder sees today | only `harsh/mvp`'s behaviour — mail deleted at the gate, ~27 of ~470 emails reaching memory (measured 4 Oct), no brief |

## 3 · What we changed in Layer 1 (17–18 Oct)

| # | The defect | The fix | Files | Proof |
|---|---|---|---|---|
| A1 | Composio reports a failure **inside** its answer (`"successful": false`). The Gmail list call and the shared executor (Calendar, Drive, HubSpot, Linear, Notion) never checked it, so an expired login was filed as a finished, **empty** sync — "nobody wrote to you" | A refusal now raises `ProviderRefused`. The sync retries, then writes the run to `l1_sync_runs` **with its error**, and coverage reads that window as FAILED | `capture/connectors/composio_base.py`, `capture/connectors/composio.py` | 6 tests; pushed `e0996e6c` |
| A2 | A poll that ran out of pages wrote `cursor_exhausted = NULL` ("not applicable") | It now writes `cursor_exhausted = false`, `page_budget_spent = true` | `capture/acquire/sync_runner.py` | same tests; pushed `e0996e6c` |
| A3 | Nine connectors used `now()` when a message had no readable time: an old mail looked like today's, and the sync cursor jumped to "now" | The object is captured, marked `occurred_at_inferred`, counted, logged — and never moves the cursor | `capture/connectors/base.py` + each connector, `capture/transcripts/ingest.py`, `capture/acquire/sync_runner.py` | 9 tests |
| C3 | A relationship or meeting-proposal quote the mail does not contain could be stored as something someone said | Such a quote is cleared; the entry stays | `capture/semantic/extractor.py` | 4 tests |

**Not changed:** no migration, no table, no column, no env var, no prompt. The junk-filter prompt is unchanged
(its fix waits on Rohit — §7).

## 4 · What you need to do, in order

### H1 · Deploy `speedrun008` to production — the one that matters

**Why:** every Layer 1 improvement since 10 Oct — and A1–A3, C3 — reaches the founder only through this.

**How:** follow `speedrun008/YC-II W27/08-FOR-HARSH-deploy-and-after.md` **§0**, step by step (23 steps: before
probes, the branch, the twenty migrations `0191`→`0242`, the environment, the first passes, the data steps, the
switches for Rohit's org). That runbook was written for `speedrun008` at `c1df07ac`. The commits after it are
this Layer 1 pass and documents; they add **no migration and no environment variable**, so §0 applies unchanged
to the current head. Before you start, confirm the head you deploy:

```
git fetch origin
git log --oneline -1 origin/speedrun008
git rev-list --count origin/harsh/mvp..origin/speedrun008     # how far behind production is
git rev-list --count origin/speedrun008..origin/harsh/mvp     # must be 0, or §0 step 3 (the merge back)
```

**You should see after the deploy (Layer 1 only):**
- the sweep's log shows sync runs with `error` filled when Composio refuses — no longer silent;
- `select count(*) from l1_sync_runs where cursor_exhausted is false and page_budget_spent;` — rows appear for polls
  that ran out of pages (they used to be NULL);
- mail is archived, not deleted (`STEP-03`), and the funnel counts in §0 move.

**It went wrong if:** sync runs suddenly all show `error` — that is a real, previously hidden failure (most likely an
expired Composio connection). Do **not** roll back for it; reconnect the account. Before A1 the same failure was
recorded as an empty inbox.

**Roll back:** as §0 says. A1–A3 and C3 have no data effects to undo.

### H2 · Record one live Gmail history response

**Why:** item A4 — keying the Gmail sync cursor on Gmail's `historyId` instead of a date — cannot be built
against a response shape nobody has seen. Today the cursor is a day-granular date (`after:YYYY/MM/DD`); a reset
cursor is never noticed.

**How:** on the design partner's connection, call Composio's Gmail history tool once (the Gmail toolkit's
history listing, e.g. `GMAIL_LIST_HISTORY` — use whichever name the pinned toolkit exposes), with a
`start_history_id` taken from any recent message's `historyId`. Save the full JSON response, with message bodies
and addresses replaced by placeholders, as
`tests/capture/connectors/fixtures/gmail_history_live.json`, and commit it. Also save the response to an
**expired** `start_history_id` (Gmail answers 404) as `gmail_history_expired_live.json`.

**Then:** Claude builds A4 against those two files.

### H3 · Pin the Composio toolkit versions

**Why:** every call runs with `dangerously_skip_version_check=True`. A toolkit change arrived unannounced on 3 Oct
(`file_name` became required) and refused 88 of 88 attachment fetches.

**How:** `yc2_w27` unit `M17.C3.L-integration.V2.U04` (blocked on the SDK version the production image runs — you
have it). Pin the Gmail and Google Calendar toolkits at the versions production uses today.

### H4 · After the deploy: re-queue the attachments the old refusal dead-lettered

**How:** `scripts/requeue_refused_attachments.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL"`
first without `--apply` (dry run, read its count), then with `--apply`. Details: `08` §3.1. Run it only once the
deploy is live — before it, every row is refused again.

### H5 · Watch two log lines for the first week

| Log line | Means | Do |
|---|---|---|
| `time inferred: org=… conn=… source=… — N object(s) had no readable time` | A3: a provider stopped sending a message's time | if N > 0 on Gmail or Calendar, save one such raw object (redacted) and tell Claude — a connector's time field changed shape |
| `L1 sync failed for org_id=… connection_id=…` with `ProviderRefused: composio <TOOL> refused: …` in the traceback, and an ops alert `sync_failed` (`api/routes.py:920-926`, `platform/ops_alert`) | A1: a provider refused a call. **New after this deploy** — the same refusal used to pass silently as an empty inbox, so expect alerts that never fired before | an expired or revoked connection — reconnect it; the window reads FAILED until a clean run |

### H6 · Only if Rohit says yes (R3, R4)

- **R3 — a second mailbox (`ceo@thegenios.com`)**: connect it as a **seat** connection for Rohit's org; the seat
  path already gives it its own connection id and its own Composio user (`api/routes.py:3191`).
- **R4 — the history window 60 → 365 days**: `PATCH /connections/{id}/backfill-window` with `365` on the Gmail and
  Calendar connections, then STEP-08's resync run (`08`, the STEP-08 section).

## 5 · What not to do

- Do not edit the junk-filter prompt (`capture/gate/relevance.py`) — it waits on a live measurement (§7, B1).
- Do not "fix" sync runs that now show an error by suppressing the error — the error is the fix.
- Do not run any Layer 1 script with `--apply` before its dry run has been read.

## 6 · How to plan your Layer 1 time

1. **H1 first** — it is the largest effect on what the founder sees, and every other item assumes it.
2. **H4 and H5 the same day** as H1 (they are minutes each).
3. **H3 and H2** in the same sitting — both need the production SDK and a live connection.
4. **H6** only when Rohit decides.

## 7 · What is still open in Layer 1, and whose it is

| # | What | Whose |
|---|---|---|
| B1 | Measure Layer 1's model calls on the real model (≈ $1, Haiku) | Rohit: a key and a yes |
| B2 | Remove "drop matchmaking / plan notices" from the junk-filter prompt, after B1 | Claude, after B1 |
| C5 | Bundles: wire an L2 reader, or retire | Rohit decides |
| A4 | The Gmail cursor on `historyId` | Claude, after your H2 |
| C4, D1, D2 | whose turn it is, a thread's end state, conditions | moved to the L3 folder — they need a reader there |

The full picture: `00-START-HERE.md` (one screen), `01-AS-IS.md` (what works and what did not, with file:line),
`02-PLAN.md` (every item), `03-LOG.md` (what was done, with commit and proof).
