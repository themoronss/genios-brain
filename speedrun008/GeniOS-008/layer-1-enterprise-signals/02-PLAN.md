# L1 Enterprise Signals — what must change, in order

Every item points to its problem in `01-AS-IS.md` (W1…W15). Each item is one unit: one change, its own
test, a mutation (the fix removed → the test fails), and the repo-wide guards per group of 2–3 units.
**No new groups or sections.** The structure in `capture/` stays; these are changes inside it.

Order: first, the things that make Layer 1 **lie** (it says "empty" or "now" when it does not know).
Then the things it **loses** (evidence that never reaches the next layer). Then the **new** objects.
Items that need a decision from Rohit are marked ⛔ and wait for it; nothing else waits.

---

## Group A — Layer 1 must never say something it does not know

| # | Fixes | The change | Why this way | Proof | Owner · state |
|---|---|---|---|---|---|
| A1 | W1 | A Composio answer with `successful: false` raises `ProviderRefused` — in the shared executor (`connectors/composio_base.py`) and on the Gmail list call (`connectors/composio.py`). The retry runs; a run that still fails is written to `l1_sync_runs` WITH its error, and coverage reads it as FAILED | One check at the one seam every connector shares, instead of six. A raised error already has a correct path (`_fetch_page` retries, the ledger records `error`) — no new path was needed | `tests/capture/connectors/test_a_provider_refusal_is_never_an_empty_page.py`, 6 tests; three mutations, each caught | Claude · ✅ built 17 Oct, guards running |
| A2 | — (found building A1) | A poll whose page budget runs out with a live cursor records `cursor_exhausted = False`, `page_budget_spent = True` instead of `None` ("not applicable") | `None` is the webhook's answer; a truncated poll must say who stopped it | same test file, `test_a_poll_that_ran_out_of_pages_says_we_stopped` | Claude · ✅ built 17 Oct |
| A3 | W8 | A connector that cannot read a message's time marks the object `occurred_at_inferred = True` (in `raw`), counts it on the sweep (`SyncSummary.time_inferred`), and the landing keeps the flag. Nine connectors, one helper | Refusing the mail would lose it; guessing silently makes old mail look new. Marked, counted and kept is the honest middle | per connector: a payload without a date lands flagged; the count reaches the summary | Claude · next |
| A4 | W9 | Gmail incremental sync keyed on `historyId` (Gmail's own change cursor). A saved page token is never sent with a different query; an expired `historyId` (Gmail's 404) starts a bounded backfill of the gap and records it | A date watermark re-reads the boundary day and cannot see a reset; `historyId` is what Gmail offers for exactly this | needs ONE live response shape from Composio's `GMAIL_LIST_HISTORY` first | Harsh records the shape · Claude builds |

## Group B — the junk filter: measure first, then fix

| # | Fixes | The change | Why this way | Proof | Owner · state |
|---|---|---|---|---|---|
| B1 | W4 | Run the golden set's Layer 1 model sites on the real model: `scripts/golden_eval.py --live --site junk_gate_batch`, `--site relevance`, `--site extraction` (Haiku 4.5, ≈ $1.02 in all). Scorecard into `YC-II W27/scores/` | The golden board judges the engine with an ideal reader. Production junked real investor mail — only a live pass says how often the real model does | the scorecard: per case, what the model kept vs what the case needs | ⛔ Rohit: a key in `GENIOS_GOLDEN_LIVE_KEY` and a yes · then Claude |
| B2 | W2 | The junk filter's prompt (`gate/relevance.py:79-81`, `:108`): remove the matchmaking DROP line; *"an introduction to one named person is KEEP, whoever sent it"*; *"a price or plan change from a tool the company pays for is KEEP"*. Re-record the junk cassettes with the ideal reader | It is the prompt that says drop; the model obeys it. Decision D29 holds this until B1 has measured the filter | B1 re-run: F56 kept; Boardy intros kept; must-abstain unchanged (14/14) | ⛔ after B1 · Claude |
| B3 | W3 | A junk "drop" decided from the list snippet is re-judged on the full body when the sender has ever been written to by the founder, or the snippet names a person, money or a date | The model cannot judge two lines; fetching every body costs ~16 s a page. Re-judging only the risky drops keeps the speed | a case whose snippet looks like a newsletter and whose body is an intro: kept | Claude · after B2 |

## Group C — what Layer 1 knows must reach the next layer

| # | Fixes | The change | Why this way | Proof | Owner · state |
|---|---|---|---|---|---|
| C1 | W6 | `build_fetchers()` returns a real Gmail thread fetcher for `FETCH_THREAD` (and `REEXTRACT` from the stored payload). What it fetches goes through the normal gate and capture, never around them | The executor, the queue and the contract are built and called every sweep; only the fetcher is missing. Through the normal door, so a fetched mail is checked like any other | a need for an older thread is met; a refused provider leaves the need open, never "found nothing" | Claude |
| C2 | W7 | The ambiguous resolver's `alternatives` reach the stored mention (`EntityMention.candidates`), and the L3 resolver reads them instead of guessing | The doubt is computed and then discarded one line later; carrying it is cheaper than recomputing it | two "Priya"s → one mention, two candidates, no merge | Claude |
| C3 | W11 | `implied_actions`, `topics`, `relationships`, `scheduling_proposals` carry an evidence span and pass `validate/spans.py` like every other claim; a claim with no span is kept at reduced confidence, as the others are | One rule for every claim the model makes | a `relationships` entry with no quote is down-weighted | Claude |
| C4 | W10 | L2's projection (`context/situation_bso.py` `_L1_SELECT`) reads `ball_in_court`, `thread_key`, `direction`, `due_at`, `coverage` — and the situation uses them (whose turn; what was seen) | Layer 1 already decided these; L2 re-derives worse versions or none | `test_l2_reads_what_l1_publishes` extended; a situation knows whose turn it is from L1 | Claude |
| C5 | W5 | ⛔ Bundles: either L2 reads `signal_bundles` (and `finalize_l1` stores them), or the bundle code is retired | A table with no reader is cost with no use; wiring a reader is a design choice in L2 | — | ⛔ Rohit decides |

## Group D — new objects Layer 1 does not have

| # | Fixes | The change | Why this way | Proof | Owner · state |
|---|---|---|---|---|---|
| D1 | W12 | A thread end state per thread: `waiting_on_us`, `waiting_on_them`, `resolved`, `abandoned` (no message for N days, N from the thread's own reply rhythm), `unknown`. Built from `ball_in_court` + the last message + coverage; `unknown` whenever the thread's window is not HEALTHY | `ball_in_court` already answers half; the other half is time and coverage, both already in L1 | golden threads: each ends in the right state; a thread in a FAILED window is `unknown` | Claude |
| D2 | W13 | A `Condition` object: who, the condition, the action it unlocks, its evidence; extracted beside commitments, validated by spans | Today only a promise can carry a condition; "if the round closes we'll hire" is lost | the benchmark's 3one4 condition is extracted with its quote | Claude |

## Decisions only Rohit can make

| # | Question | Recommendation |
|---|---|---|
| ⛔ R1 | Spend ≈ $1 on the Layer 1 live pass (B1)? | Yes — the junk filter cannot be fixed blind |
| ⛔ R2 | Bundles: wire an L2 reader, or retire (C5)? | Retire for now; L3's correlation already groups by thread and subject |
| ⛔ R3 | A second mailbox for `ceo@thegenios.com` (W14)? | Yes, as a seat connection — the seat path exists (`api/routes.py:3191`); only the connect flow for Rohit's own second address is missing |
| ⛔ R4 | The history window: 60 → 365 days (W15, D5)? | 365 — it brings back July's investor threads |

## Not doing (and why)

- **New groups G1–G7, new algorithm numbers, renaming V-1…V-7** — the structure exists; renaming
  it moves nothing and breaks every citation.
- **Absence signals inside L1** — absence needs memory; it stays in L3.
- **Delivered / read status** — Gmail does not provide it.
- **The database-load fixes (5.1–5.4)** — real, but in L2 `reason/`, L3 `context/analytic/` and L5
  `deliver/`. They go in those layers' folders. 5.3's mechanism does not match the code (an unchanged
  value is not written, `publish.py:305`), so it needs one production query before any fix.
