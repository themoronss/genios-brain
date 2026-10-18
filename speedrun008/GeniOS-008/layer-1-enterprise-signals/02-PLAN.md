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
| A3 | W8 | A connector's no-time fallback returns `InferredInstant` (`connectors/base.py`), not a bare `now()`. `RawObject` turns it into `occurred_at_inferred = True`, a plain `datetime`, and `raw["occurred_at_inferred"]`; `run_sync` counts it (`SyncSummary.time_inferred`), logs it, and never lets it move the cursor. Gmail, Calendar, Drive, HubSpot, Linear, Notion, the database connector and transcripts. The manual upload door is left alone: there "now" is when it was uploaded, which is true | Refusing the mail would lose it; guessing silently makes old mail look new and pushes the cursor past mail not yet fetched. A `datetime` subclass changes one line per connector and nothing downstream sees it | `tests/capture/connectors/test_a_time_we_could_not_read_is_never_passed_off_as_now.py`, 9 tests; three mutations caught | Claude · ✅ built 17 Oct |
| A4 | W9 | Gmail incremental sync keyed on `historyId` (Gmail's own change cursor). A saved page token is never sent with a different query; an expired `historyId` (Gmail's 404) starts a bounded backfill of the gap and records it | A date watermark re-reads the boundary day and cannot see a reset; `historyId` is what Gmail offers for exactly this | needs ONE live response shape from Composio's `GMAIL_LIST_HISTORY` first | Harsh records the shape · Claude builds |

## Group B — the junk filter: measure first, then fix

| # | Fixes | The change | Why this way | Proof | Owner · state |
|---|---|---|---|---|---|
| B1 | W4 | Run the golden set's Layer 1 model sites on the real model: `scripts/golden_eval.py --live --site junk_gate_batch`, `--site relevance`, `--site extraction` (Haiku 4.5, ≈ $1.02 in all). Scorecard into `YC-II W27/scores/` | The golden board judges the engine with an ideal reader. Production junked real investor mail — only a live pass says how often the real model does | the scorecard: per case, what the model kept vs what the case needs | ⛔ Rohit: a key in `GENIOS_GOLDEN_LIVE_KEY` and a yes · then Claude |
| B2 | W2 | The junk filter's prompt (`gate/relevance.py:79-81`, `:108`): remove the matchmaking DROP line; *"an introduction to one named person is KEEP, whoever sent it"*; *"a price or plan change from a tool the company pays for is KEEP"*. Re-record the junk cassettes with the ideal reader | It is the prompt that says drop; the model obeys it. Decision D29 holds this until B1 has measured the filter | B1 re-run: F56 kept; Boardy intros kept; must-abstain unchanged (14/14) | ⛔ after B1 · Claude |
| B3 | W3 | ~~re-judge risky snippet drops~~ **Retracted 17 Oct — already built.** `RelevanceGate.keeps_whole` (`gate/relevance.py:200`) makes the connector fetch in full any mail from a known counterparty or a sender the brief names, and `_skip_body` fetches every unconfident drop. What is left is the prompt itself — B2 | — | — | — |

## Group C — what Layer 1 knows must reach the next layer

| # | Fixes | The change | Why this way | Proof | Owner · state |
|---|---|---|---|---|---|
| C1 | W6 | ~~wire the evidence fetcher~~ **Deferred 17 Oct, measured.** The only filer of needs (`context/evidence_needs.py:need_from_residue`) asks one diagnostic question — *"a published verdict nobody read: is there source material we have not fetched?"* — which no thread fetch answers. And a closure is PERMANENT (`need_executor.py` docstring): a fetcher built against a Composio shape nobody has recorded would close real questions as "found nothing". Comes back when L3/L2 file a need a fetch can answer, with one recorded live response | — | — | revisit in L3 |
| C2 | W7 | ~~carry entity doubt~~ **Retracted 17 Oct — not a defect.** L1's canonicalizer is a small shipped alias table (`validate/canonical.py:440`); returning no hint on a contested alias IS its contract (*"ambiguity is not a match; L2 owns identity"*). People's identity — the two-Priya case — is resolved in L3 `context/identity.py`, which handles ambiguity. Carrying the alternatives would be a field nothing reads | — | — | — |
| C3 | W11 | `relationships` and `scheduling_proposals` have no span; their `evidence_text` is their only receipt and L3 files it as the fact's evidence. A quote the mail does not contain (case- and space-blind, quote marks ignored) is now CLEARED; the entry stays (`semantic/extractor.py` `_open_lane_entries`). `topics` and `implied_actions` are labels, not quotes, and are read only as hints (`esqe/detector.py:405`, the decider's prompt) — left as they are | Clearing the invented quote stops a fabricated sentence being stored as something someone said, without changing what L3 believes (the judgement is ranked lowest already) | `tests/capture/semantic/test_an_open_lane_quote_must_be_in_the_mail.py`, 4 tests; mutation caught | Claude · ✅ built 17 Oct |
| C4 | W10 | **Moved to L3/L2 17 Oct.** Reading `ball_in_court`, `thread_key`, `due_at`, `coverage` is only worth it with a consumer that USES them in the situation, and that consumer is `context/` (L3) and `packs/`+`reason/` (L2). Adding them to a select nobody uses is one more column carried and never read. It is the first item of the L3 folder | — | — | L3 |
| C5 | W5 | ⛔ Bundles: either L2 reads `signal_bundles` (and `finalize_l1` stores them), or the bundle code is retired | A table with no reader is cost with no use; wiring a reader is a design choice in L2 | — | ⛔ Rohit decides |

## Group D — new objects Layer 1 does not have

| # | Fixes | The change | Why this way | Proof | Owner · state |
|---|---|---|---|---|---|
| D1 | W12 | **Moved to L3 17 Oct.** "Is this conversation over?" needs the thread's history and coverage, which L3 holds (`context/open_loops.py`, `context/waiting.py`); an L1 object would have no reader. Item in the L3 folder | — | — | L3 |
| D2 | W13 | **Moved to L3 + L1 together, 17 Oct.** A standalone condition needs an extraction prompt change (134 recorded extraction calls re-recorded) AND a reader in `context/condition_situations.py`; built only one-sided it is write-only. Planned as one item in the L3 folder, with its L1 half | — | — | L3 |

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
