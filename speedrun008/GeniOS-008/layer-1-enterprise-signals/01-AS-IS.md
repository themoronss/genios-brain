# L1 Enterprise Signals — as it is (checked against the code, 17 Oct 2026)

**Measured at:** `origin/speedrun008` `6e8f5b12`. Paths are under `genios_engine/` unless they say
otherwise. "Reached" means a production caller chain exists (scheduler → sweep → this code).

**Production is not this code.** Production runs `harsh/mvp` `84f00a40`, **815 commits behind**. Every
"works" below is true of the code; it reaches the founder only after Harsh's deploy
(`YC-II W27/08-FOR-HARSH-deploy-and-after.md` §0).

---

## 1 · What was already there

`capture/` is about 48,800 lines of Python in 35 packages and modules. It already has the shape the Layer 1
Blueprint asked for — not under the Blueprint's names, and that is fine:

| The job | Where it lives |
|---|---|
| Sources and connections | `connectors/` (Gmail `composio.py`, Calendar `calendar.py`, Drive, HubSpot, Linear, Notion), `connections/`, `source_registry.py` |
| Fetching on a schedule, backfill, catch-up | `acquire/` (`sync_runner.py` `run_sync`, `backfill_drain`, `cadence.py`, `catchup.py`) |
| Landing once, never twice | `landing/` (`normalize.py` dedup key, `pg_repository.py` *on conflict do nothing*) |
| Cleaning the text | `preprocess/` (quoted text, PII), `documents/` (attachments, OCR routing), `transcripts/` |
| Deciding what deserves attention | `gate/` (rules S0–S2, the junk filter), `attention.py`, `triage/` |
| Reading meaning | `semantic/` (extractor, open lane), `structural/` (threads, ball in court), `domain/` |
| Checking the model's work | `validate/` (spans, dates, money, schema, canonical, confidence, conflict, authority) |
| Qualifying and publishing signals | `esqe/` (importance, lifecycle, publisher, bundle, finalize) |
| Knowing what we saw and did not see | `coverage/` (window, declaration, store, symmetry) |
| Being able to retry | `parked/` (drain, refetch, recapture) |

## 2 · What works

| What | Evidence | Reached |
|---|---|---|
| **The gate never deletes.** A rule or junk "drop" becomes an archive, body kept, reason recorded | `capture/gate/gate.py:22-24` `_never_delete`; `pipeline.py:1641-1696` | yes |
| **A sender the company brief names is never junked** (W-07) | `gate/rules.py:298`; `gate.py:156` | yes — but only for senders in an accepted brief |
| **The provider's own count is kept** — "read 18 of about 465" is sayable | `connectors/composio.py` `_to_batch` (`resultSizeEstimate`); `acquire/sync_runner.py` `claimed_total` | yes |
| **A sweep says whether it finished**, and who stopped it | `sync_runner.py` `cursor_exhausted`, `page_budget_spent`; written to `l1_sync_runs` by `api/routes.py:_run_ledger` | yes |
| **A window is never called healthy on a failure** — UNKNOWN / FAILED / PARTIAL / SUCCESS_EMPTY / HEALTHY | `coverage/window.py:175-190` | yes, read by `context/coverage_receipt.py` and the morning brief |
| **The history window is per connection**, 1–3650 days | `connectors/backfill.py:37-46`; `PATCH /connections/{id}/backfill-window` | yes — the default is still **60** |
| **The same mail never lands twice** | `landing/normalize.py:42`; `landing/pg_repository.py:28` | yes |
| **A failed attachment parks only the attachment**, not the mail | `composio.py:754-758`; `gate/rules.py:343` | yes |
| **A bounce is detected and tied to the mail it bounced** | `capture/delivery_status.py` (detect); `context/delivery.py` (link, in L3) | yes |
| **Commitments and open questions are typed objects** | `contracts/extraction.py:242`, `:569` | yes |
| **Importance (ALG-17) and expiry (ALG-19)** | `esqe/importance.py:789`; `esqe/lifecycle.py:357`, `:437` | yes |
| **Publication checks V-1…V-7** — envelope, closed type, importance range, evidence present, spans, confidence ceiling, no floats | `contracts/publication.py:105-119`; `esqe/publisher.py:768` | yes |
| **Anything the 16 signal types cannot hold goes to the open lane**, not to nothing | `semantic/open_lane.py`; `pipeline.py:836` | yes |
| **The golden set**: 49 of 53 must-detect, 14 of 14 must-abstain, 0 forbidden outputs | `YC-II W27/03-FINDINGS.md:901-905` | — judged with recorded "ideal reader" answers, not a real model |

## 3 · What does not work

| # | What is wrong | Evidence | What it costs the founder |
|---|---|---|---|
| W1 | **A failed provider call reads as an empty inbox.** Composio reports a failure inside the answer (`"successful": false`); the Gmail list and the shared executor (Calendar, Drive, HubSpot, Linear, Notion) never checked it, so the sweep was filed as finished and empty | `connectors/composio.py:288`; `connectors/composio_base.py:51` | an expired login looks like "nobody wrote to you". **Fixed 17 Oct** — `03-LOG.md` |
| W2 | **The junk filter is told to drop two things a founder needs**: *"automated matchmaking"* (Boardy introductions) and *"subscription / plan / account notices"* (a vendor's +32% renewal — golden F56) | `capture/gate/relevance.py:79-81` and the batch prompt `:108` | introductions and price changes archived unread |
| W3 | ⛔ *Retracted 17 Oct — see `02-PLAN` B3.* **The junk filter judges the list snippet**, and a confident drop is never fetched whole | `connectors/composio.py` `_skip_body` (fast path) | the model decides on two lines of preview |
| W4 | **Layer 1's model calls have never been measured on a real model.** Five sites: junk filter (single, batch), relevance, domains, extraction | `tests/replays/harness.py:88-117`; no `scores/` for these sites | we do not know how often the real model junks an investor |
| W5 | **Bundles are built and thrown away.** `finalize_l1` passes no store, nothing writes `signal_bundles`, nothing reads it | `esqe/finalize.py:134`; `esqe/publisher.py:1248` | the cross-signal grouping L1 computes never reaches L2 |
| W6 | *Deferred 17 Oct — see `02-PLAN` C1.* **A request for missing evidence can never be met.** The executor runs every sweep, but has no fetcher | `acquire/need_executor.py:214` `build_fetchers() → {}` | "fetch the older thread" is always refused |
| W7 | ⛔ *Retracted 17 Oct — not a defect, see `02-PLAN` C2.* **When a name could be two people, the candidates are thrown away** | `validate/canonical.py:542-544` (`apply_to` returns the mention without `alternatives`) | doubt becomes "unresolved", the options are lost |
| W8 | **A missing timestamp silently becomes "now"** in nine connectors | `composio.py:226`, `calendar.py:30`, `transcripts/ingest.py:229`, `intake.py:46`, drive, notion, hubspot, linear, database | an old mail can look like today's |
| W9 | **The Gmail cursor is a date, not `historyId`**, and a saved page token is re-used with a new query | `composio.py:313`; `acquire/sync_runner.py:623` | a reset cursor never triggers a backfill |
| W10 | **L1 writes columns L2 never reads**: `thread_key`, `direction`, `turn_index`, `thread_depth`, `ball_in_court`, `coverage`, `due_at`, `effective_at`, `qualification_reason` | `esqe/signal_store.py:57-73` vs `context/situation_bso.py:525-548` | whose turn it is, and what L1 saw, stop at the table |
| W11 | **Four extraction fields carry no evidence check**: `implied_actions`, `topics`, `relationships`, `scheduling_proposals` | `semantic/extractor.py:1603-1630` | a model claim with no quote behind it |
| W12 | **No thread-level end state** (resolved / abandoned / waiting on them / waiting on us) — only per-signal states and `ball_in_court` | `structural/threads.py:318`; `esqe/lifecycle.py` | "is this conversation over?" is answered per signal, not per thread |
| W13 | **A condition that is not a promise has no object** ("if X then Y") | `contracts/extraction.py:268` (only `Commitment.is_conditional`) | conditional triggers that nobody promised are lost |
| W14 | **One workspace Gmail per org**; a second mailbox only as a member seat, and coverage cannot name what is NOT connected | `api/routes.py:3191`; `context/coverage_receipt.py` | "you never replied" may be a reply from `ceo@thegenios.com` |
| W15 | **The history window defaults to 60 days** (decision D5 recommends 365) | `connectors/backfill.py:37` | July's investor threads are outside memory |

## 4 · What is not wrong, though a document said it was

| Claim | Truth |
|---|---|
| "L1 has no absence signals" | Absence lives in L3 on purpose (`context/waiting.py`, `outreach_situations.py`, `meeting_days.py`): "no reply" needs memory | ⛔ **Wrong under the new architecture (18 Oct)** — this judged the claim by today's OLD flow; Atlas v2 puts it in L1. See `02-PLAN` Group E
| "No delivered/read status" | Gmail does not provide delivered or read. Bounce is the only status there is, and it is read |
| "A meeting → follow-up link is missing" | It is in L3 (`context/meeting_days.py:183`), where the meeting's memory is | ⛔ **Wrong under the new architecture (18 Oct)** — this judged the claim by today's OLD flow; Atlas v2 puts it in L1. See `02-PLAN` Group E
| "The coverage snapshot is not on each signal" | It is (`qualified_signals.coverage`), but L2 does not read it — that is W10 |
| "A 60-day wall" | It is a per-connection default, not a wall — that is W15 |
| W3 "the junk filter judges a snippet" (my own, 17 Oct) | Any mail from a known counterparty or a brief-named sender is fetched whole (`gate/relevance.py:200` `keeps_whole`), and every unconfident drop is fetched whole (`_skip_body`) |
| W7 "entity doubt is thrown away" (my own, 17 Oct) | No hint on a contested alias is the canonicalizer's contract; identity, including two people with one name, is L3's (`context/identity.py`) |
