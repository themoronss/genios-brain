# STEP-01 · NEXT · the golden set — your mailbox becomes the exam

**Owner:** Claude builds · Rohit labels (`06-DECISIONS.md` D12). **Depends on:** nothing — it can
run while `STEP-00` is being merged. **Moves:** a before-score exists, and every later step is
judged against it.

---

## 1 · What

Two exams, both run on every change.

1. **The twelve Atlas golden replays**, already in the repo (`tests/replays/`, specs transcribed
   from `Rohit_Updates/Secret War Updates/09-Golden-Replays/`): 153 mutations. Replays 01–07 —
   Theresa, Boardy, reschedule, already-replied, meeting recap, closed/deferred, missing expertise
   — are *your* cases, 80 mutations. `[TEST]` `pytest tests/replays -q` → `33 passed, 150 xfailed`.
   ⛔ **But that number measures nothing about the engine.** `[CODE]` The harness never calls the
   engine: a "runnable" mutation only asserts its strings are non-empty, and a blocked one runs
   `pytest.fail(...)` unconditionally under `xfail(strict=True)`
   (`tests/replays/test_golden_replays.py:34-48`) — so it **cannot** start passing when the
   capability lands. The specs date from 12 Sep and several `blocked_on` texts are already stale.
   This step makes the replays drive the engine.
2. **A founder-mailbox set**, new: about 40 synthetic cases modelled on the real items in
   `04-NOW-VS-SHOULD-VS-EXPECTED.md` — the same shapes, with invented names and text, so no real
   content enters the repository. Each case holds the input events (mail headers and body,
   calendar entries, screen items), the expected workstream, stage, lane, what the card must say,
   and what it must never say.

## 2 · Why

Without a fixed exam, every later step can claim progress and none can prove it. The Secret War
audit puts this first (`CP-0`: *freeze fixtures and baseline before changing architecture*), and
the Atlas states the stakes plainly (V.4): *if a frontier model with the same connectors matches
GeniOS on the long-horizon prompts, the thesis is false, and the company should know it early.*

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | the case format | `tests/replays/specs/founder/*.json` | the existing `ReplaySpec` shape (`tests/replays/harness.py`), plus `events` (synthetic input) and `expected` (workstream, stage, lane, card fields, forbidden phrases and targets) |
| 3.2 | **an engine-driving runner** | `tests/replays/engine_runner.py` | seeds a scratch org from a case's `events`, runs the real chain — `capture_event` → `process_pending` → `run_all` → `build_cards_for_org` — and returns what each stage produced: gate verdict, nodes, situations, signals, lane, card. It runs on the real-Postgres seam the suite already has (`GENIOS_TEST_DATABASE_URL`, `tests/conftest.py:79-138`), because the pipeline's SQL is Postgres SQL — and without it the test **fails** rather than skips |
| 3.3 | deterministic replays of a model step | `tests/replays/harness.py` | the harness's `NoLLM` stays for every deterministic layer. Every model site gets a **`RecordedLLM`**: a cassette keyed by prompt hash that **fails on a miss**. The CI exam stays deterministic — the Atlas's own replay law: *"replay reads the receipt; it never calls the model again"* |
| 3.4 | the strict xfails made real | `tests/replays/test_golden_replays.py` | a blocked mutation asserts its pass condition **through the runner**, so the day the capability lands it XPASSes and the marker must come off. A mutation that cannot be expressed as a runner assertion yet says so in its spec |
| 3.5 | Postgres in CI | `.github/workflows/ci.yml` | a `postgres` service and `GENIOS_TEST_DATABASE_URL`, so the exam — and the 150 pg-gated test files — run on every push (absorbs half of `STEP-17`) |
| 3.6 | a live evaluation, outside CI | `scripts/golden_eval.py --live` | runs the real model on the same cases and writes a scorecard — recall, precision, forbidden outputs, tokens, cost — to `speedrun008/YC-II W27/scores/`. Used to compare prompts and models *before* a change ships |
| 3.7 | the scoreboard | `scripts/golden_score.py` | one table: founder must-detect, must-abstain, forbidden outputs; Atlas replays 01–07 passing vs blocked |
| 3.8 | your label sheet | `speedrun008/YC-II W27/golden-labels.md` | the real items below, by sender and date only, one question each: *should this have reached you?* — yes · no · in the morning brief only |

## 4 · The cases — first draft

Labels are mine until you replace them. "Replay" names the Atlas golden replay the case also
exercises.

### Must reach you

| # | Real item | Workstream | What a correct GeniOS does | Replay |
|---|---|---|---|---|
| 1 | Startup India / DPIIT, 24 Sep | compliance | stage update → card or brief line, same day | — |
| 2 | DPIIT 29 Sep, 30 Sep ×2; DigiLocker 23 Sep | compliance | **the same card updates**, it does not multiply | — |
| 3 | Boardy → Pankaj (saka.vc), 3 Sep, nudged 4 and 7 Sep | intro | its own file; Investigation (*is saka.vc a fund?*) | 02 |
| 4 | Boardy → Sal, 6 Aug; Sal replied the same day | intro | reply owed by you, per contact | 02 |
| 5 | Boardy → Maria, 6 Aug; Maria replied 11 Aug | intro | reply owed by you | 02 |
| 6 | Boardy → Nitesh, 6 Aug; Nitesh wrote 9 Aug | intro | reply owed — his scheduling question | 02 · 03 |
| 7 | Boardy → Lalitha, 12 Aug; replies; call 13 Aug | intro + meeting | after the call: *was anything promised?* | 02 · 05 |
| 8 | Boardy → Silas 4 Aug, Ori 6 Aug — both silent | intro | Monitor, then close with a reason | 02 |
| 9 | Boardy, 29 Sep — you replied, Boardy answered | connector | a separate *Boardy-as-target* item, never merged into a contact's | 02 (m04) |
| 10 | Khushi Agarwal, 247VC, 18 Sep | investor | reply owed | — |
| 11 | Troy Kirwin, a16z, 15 Sep | investor | read; reply owed if asked | — |
| 12 | Neel Jain, Insight Partners, 27 Sep + call 8 Oct | investor + meeting | prep card ≥ 24 h before the call | 03 · 05 |
| 13 | Manik, Titan, 8 Aug | investor | his ask, owed by you — **never** *"send Mr Rohit Swerashi…"* | 01 |
| 14 | Theresa, Antler — four updates from you, silence since 7 Aug | investor, conditional | update only on a material milestone; otherwise wait | 01 · 06 |
| 15 | The 11 Aug wave, ~11 funds | investor wave | the follow-up decision: who, with what, who to close | — |
| 16 | Bounce reports, 11–14 Aug | your outbound | which address failed → fix and resend | — |
| 17 | Hub71, 1 Oct, after your 26 Aug reply | application | stage update | 12 |
| 18 | iHub Gujarat (investments@), 1 Oct | investor / program | read and triaged | — |
| 19 | IIITD-IC — Navin, Rajni, Naresh, Esha (7–24 Sep) | program | who wants what from you | — |
| 20 | FITT IIT Delhi — Saket Raj, 13 Sep | program | read | — |
| 21 | IIM Lucknow EIC, 16 and 21 Sep | program | read | — |
| 22 | GUSEC grants, 7 Sep | grant | read; deadline if any | — |
| 23 | StartinUP — 5, 15, 25 Sep, 5 Oct | government program | stage | — |
| 24 | NSRCEL — Deepthi: assignments, Phase-1 review | program | deadline cards, two days ahead | 05 |
| 25 | Khushi — Founding AI Engineer offer, 5 Aug | hiring | **one** file and one card, not six | 06 |
| 26 | Evokoa — 16 Aug, 22 Sep, 30 Sep + call | partner | confirm the call time (already a good card) | 03 |
| 27 | Tejas, Tryclean — 30 Sep + call 9 Oct | partner | prep | 03 |
| 28 | Aditi, Noveum — 29 Sep + call 8 Oct | partner | prep | 03 |
| 29 | Asmit, Supymem — 27 Sep + calls 5 Oct | partner | prep, then follow-up | 03 |
| 30 | WhatsApp — your 13 open promises | screen | in the morning brief, in the right files | — |

### Must not become a card

| # | Item | Correct behaviour | Replay |
|---|---|---|---|
| 31 | NSRCEL cohort sessions (~54 founders each) | no recap card — only the assignment deadline | 05 |
| 32 | Program newsletters — SINE, Sankalp, NSRCEL social, accubate notifications | archive; surfaced only when they carry a deadline for something you applied to | — |
| 33 | Vendor marketing and receipts — Apple, Google, Composio, Stripe, Notion | archive | — |
| 34 | YC co-founder matching digests, the Z Fellows newsletter | archive | — |
| 35 | *"nsrcel — a dated payment obligation is open"* | never claim money without money in the evidence | — |
| 36 | Your own sent mail, shown as *"awaiting reply"* from you | never | — |
| 37 | Boardy as the person to reply to | never — the contact is the target | 02 |
| 38 | A thread you already answered in another channel | suppressed, with the reason | 04 |
| 39 | Your own availability proposal | wait — it is not a deliverable | 03 |
| 40 | A meeting nobody confirmed took place | ask; never recap | 05 |

## 5 · What will happen

When this step is done, one command prints the board:

```
python scripts/golden_score.py

founder golden set     must-detect  __/30    must-abstain  __/10    forbidden outputs  __
atlas replays 01–07    passing      __/80    blocked       __/80
```

The blanks are filled by this step's run. They are the **before** numbers. Every later step file
quotes this board before and after, and none is DONE while its target rows have not moved.

## 6 · Expected

- ≥ 40 founder specs committed, each with `expected` and `forbidden`.
- The before-score written into `03-FINDINGS.md` §F, with the commit it was measured at.
- `golden-labels.md` filled in by you — or by me, every row marked as mine.

## 7 · Verify

```
GENIOS_TEST_DATABASE_URL=postgresql://…/scratch \
  .venv/bin/python -m pytest tests/replays -q        # exits 0; 0 skipped; xfails counted, each naming its gap
.venv/bin/python scripts/golden_score.py             # prints the board; exits 0
```

The runner refuses to start without a scratch database — a golden set that skips is the
*"a pass over an empty table"* defect this repository already paid for once.

## 8 · Risks

| Risk | Guard |
|---|---|
| Cases written to flatter the implementation | they are written **in this step, before any implementation**, from the real metadata; an `expected` value is never edited to make a later step pass — the repo's rule, *never weaken a verify* |
| One mailbox flatters the sent-side prompts (L1's own audit, E4) | add a second founder's mailbox before any number is quoted outside |
| A cassette goes stale when a prompt changes | a cassette miss **fails** the test; re-recording is a deliberate act with the live scorecard attached |
