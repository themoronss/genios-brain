# STEP-01 · PENDING — owner: Rohit (push, batched; labels) and Harsh (deploy) · the golden set — your mailbox becomes the exam

**Owner:** Claude builds · Rohit labels (`06-DECISIONS.md` D12). **Depends on:** the database suite
green — tree `yc2_w27/M16`: the runner runs on Postgres, and on a red suite no case's verify can be
read. **Order (Rohit, 2026-10-05):** after the database part, B17–B19 and B1 (`yc2_w27/M16–M18`);
this step is `yc2_w27/M19`. **Moves:** a before-score exists, and every later step is judged
against it.

⚠️ **Re-checked against the code on 2026-10-05, claim by claim** (§9). The runner described in the
first draft would have flattered the engine; §3 is rewritten from what the check found.

✅ **Everything that is Claude's is done** — 2026-10-06, tree `yc2_w27/M19`, all 18 units green (§10):

- 40 synthetic founder cases, each with its cassette, replayed through the real chain on Postgres
  and marked; each of the 23 that cannot pass yet is a strict xfail that names its gap;
- the Atlas replays 01–07 judged on the engine's output, no longer on their own strings;
- the board (`scripts/golden_score.py`), the live evaluation (`scripts/golden_eval.py` — not run,
  `06` D12c) and a `golden-pg` CI job;
- the before-score in `03-FINDINGS.md` §F.1, which `golden_score.py --assert-recorded` holds every
  later run to.

⏳ **What is left, and whose:**

- **Rohit** — push the batch (`06` D10). The `golden-pg` job runs for the first time on that push.
- **Rohit** — the forty labels are mine, every row marked as mine (`06` D12a, the default). Correct
  any row of `golden-labels.md`: a changed row fails `tests/replays/test_founder_cases.py` until its
  case is rewritten to match, so a label can never silently disagree with its case.
- **Harsh** — deploy. Three engine fixes the golden set found (§10) ship with the batch.

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
   capability lands. The specs were added on 24 Aug (`944b4f76` — the first draft of this file said
   12 Sep), and several `blocked_on` texts were stale from the start. This step makes the replays
   drive the engine.
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

## 3 · How — the units of tree `yc2_w27/M19`

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | the founder case · `M19.C1.L-contract.V0.U01` | `tests/replays/founder_case.py`; specs in `tests/replays/specs/founder/` | its own dataclass and loader — `load_specs` reads no subfolder (`tests/replays/harness.py:125`) and the contract test pins exactly 12 Atlas specs. A case holds: the sweep instants; synthetic `RawObject`s that keep the real header class (labels, `List-Unsubscribe`, an attachment as the `fetch_failed` stub production gets); the expected gate code, memory, lane and card identity across sweeps; forbidden names and phrases; an `expressible` map; and **a witness for every must-abstain case** — today nothing gets a card, so an abstain case would otherwise pass on nothing |
| 3.2 | recorded model answers · `M19.C1.L-logic.V0.U02` · `M19.C1.L-logic.V1.U03` | `tests/replays/harness.py`; `tests/replays/model_sites.py` | `RecordedLLM`, keyed by `LLMClient.content_hash` (`context/llm/client.py:106`), thread-safe (`run_sync` runs a pool), and a miss **raises** naming the site and the hash. Every model site the chain can reach is listed and held equal to `_SITES` — the junk filter included: with no key, the tests' default, it never runs, so a mail production junked would pass |
| 3.3 | one clock · `M19.C2.L-logic.V0.U01` | `api/routes.py` `_run_l2_chain` | an optional `eval_time` threaded to every stage and to the funnel's `sweep_at`. Today the chain reads `now()` (`:718`) and cannot replay an instant |
| 3.4 | **the engine-driving runner** · `M19.C3.L-integration.V2.U01` | `tests/replays/engine_runner.py` | provisions the org and makes it live; lands the case's objects through `run_sync` with the recorded model; runs **`finalize_l1`** — without it `_pull` drains nothing, because it needs an active `qualified_signals` row (`context/runner.py:244-254`); then `_run_l2_chain(eval_time=…)` per sweep instant, returning each stage's output. ⛔ It pins the scratch database **before** importing `api.routes`, whose stores bind at import (`api/routes.py:62-70`), and refuses to start without one. Negative control: at the production floor (2,500) the e2e mail of `tests/test_e2e_all_layers.py` yields 0 cards — that test passes only because it sets the floor to 1 and asserts a dict |
| 3.5 | your label sheet · `M19.C4.L-data.V0.U01` | `golden-labels.md` | the real items by sender and date only, one question each: *should this have reached you?* — yes · no · in the morning brief only (`06` D12) |
| 3.6 | the cases · `M19.C4.L-data.V3.U02` | `tests/replays/specs/founder/` | ~40 synthetic cases, invented names and text, with their cassettes. Several need more than one sweep (2, 3, 8, 12, 14, 24); case 30 needs the screen door |
| 3.7 | the Atlas replays, scored · `M19.C4.L-logic.V3.U03` | `tests/replays/test_golden_replays.py` | a mutation's pass condition becomes a check on the runner's output, so a blocked one can XPASS the day its capability lands; one that cannot be expressed yet is counted apart from *blocked* |
| 3.8 | the board · `M19.C5.L-interface.V4.U01` | `scripts/golden_score.py` | the table in §5; exits non-zero without a scratch database |
| 3.9 | a live evaluation, outside CI · `M19.C5.L-interface.V4.U02` | `scripts/golden_eval.py --live` | the real model on the same cases; a scorecard — recall, precision, forbidden outputs, tokens, cost — in `speedrun008/YC-II W27/scores/`; re-records cassettes only when asked. Spend is your call (`06` D12) |
| 3.10 | Postgres in CI · `M19.C5.L-integration.V5.U03` | `.github/workflows/ci.yml` | a separate `golden-pg` job (`postgres:17`); the hermetic job deselects it; the full database suite joins after `STEP-17` §3.0. It first runs when you push the batch (`06` D10) |
| 3.11 | the before-score · `M19.C5.L-integration.V5.U04` | `03-FINDINGS.md` §F | written with the commit it was measured at; `golden_score.py --assert-recorded` agrees with it |

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
GENIOS_TEST_DATABASE_URL=postgresql+psycopg://…/genios_test python scripts/golden_score.py

founder golden set     must-detect  __/30    must-abstain  __/10    forbidden outputs  __
atlas replays 01–07    passing      __/80    blocked       __/80    not expressible    __
```

The blanks are filled by this step's run. They are the **before** numbers. Every later step file
quotes this board before and after, and none is DONE while its target rows have not moved.

✅ **Filled 2026-10-06** — measured at `7caed608` and recorded in `03-FINDINGS.md` §F.1, where it is
explained case by case:

```
founder golden set   must-detect  4/30 (8 not expressible)   must-abstain  5/10 (2 not exercised)   forbidden outputs  4
atlas replays 01–07  passing  0/80   blocked  7/80   not expressible  73
must-detect cases lost at:  gate 5  memory 9  reasoning 3
```

The board gained two counts this plan did not have, both so that nothing passes on nothing: a
must-detect case that cannot be judged yet (a *brief only* answer before `STEP-15`, the screen door)
is counted apart, not as a pass or a fail; and a must-abstain case whose witness never reached the
decision it is about is **not exercised** — not a pass.

## 6 · Expected

- ≥ 40 founder specs committed, each with `expected` and `forbidden`.
- The before-score written into `03-FINDINGS.md` §F, with the commit it was measured at.
- `golden-labels.md` filled in by you — or by me, every row marked as mine.

**What happened (2026-10-06):**

- ✅ 40 specs, `tests/replays/specs/founder/F01–F40.json`, each with the cards it expects and a
  witness for every must-abstain case. ⚠️ 23 of the 40 forbid nothing (`forbidden` is empty), so
  their verdict rests on the expected cards alone — a follow-up, §10.
- ✅ the before-score in `03-FINDINGS.md` §F.1, measured at `7caed608` from cassettes recorded at
  `b47239c9`.
- ✅ `golden-labels.md` labelled by me, all 40 rows marked `claude` (22 *yes*, 8 *brief only*,
  10 *no*) — the D12a default, until you correct them.

## 7 · Verify

```
GENIOS_TEST_DATABASE_URL=postgresql+psycopg://postgres:scratch@127.0.0.1:55432/genios_test \
  .venv/bin/python -m pytest tests/replays -q        # exits 0; 0 skipped; xfails counted, each naming its gap
GENIOS_TEST_DATABASE_URL=postgresql+psycopg://postgres:scratch@127.0.0.1:55432/genios_test \
  .venv/bin/python scripts/golden_score.py           # prints the board; exits 0
```

The runner refuses to start without a scratch database — a golden set that skips is the
*"a pass over an empty table"* defect this repository already paid for once.

As built, the `golden-pg` CI job runs exactly this, with the skip turned into a failure:

```
GENIOS_TEST_DATABASE_URL=… GENIOS_GOLDEN_REQUIRED=1 \
  .venv/bin/python -m pytest -q tests/replays tests/test_golden_labels_sheet.py
GENIOS_TEST_DATABASE_URL=… .venv/bin/python scripts/golden_score.py \
  --assert-recorded "speedrun008/YC-II W27/03-FINDINGS.md"     # exit 1 if the board moved unrecorded
```

and the hermetic job leaves the set out: `pytest -q -m "not golden"`.

## 8 · Risks

| Risk | Guard |
|---|---|
| Cases written to flatter the implementation | they are written **in this step, before any implementation**, from the real metadata; an `expected` value is never edited to make a later step pass — the repo's rule, *never weaken a verify* |
| One mailbox flatters the sent-side prompts (L1's own audit, E4) | add a second founder's mailbox before any number is quoted outside |
| A cassette goes stale when a prompt changes | a cassette miss **fails** the test; re-recording is a deliberate act with the live scorecard attached |

## 9 · The check of 2026-10-05 — what the first draft got wrong

Every claim in this file was re-read against `speedrun008` @ `e96787d8`, and the existing end-to-end
pattern was run on a scratch database.

| Claim | Verdict |
|---|---|
| 12 replays, 153 mutations; 01–07 are 80; `33 passed, 150 xfailed` | ✅ true |
| the harness never calls the engine | ✅ true — an unconditional `pytest.fail` at `test_golden_replays.py:41-47`; `NoLLM` is injected nowhere |
| the specs date from 12 Sep | ❌ 24 Aug (`944b4f76`) |
| a founder case is the `ReplaySpec` shape plus `events` / `expected` | ⚠️ partly — the loader reads no subfolder and the contract pins 12 specs, so it needs its own type (3.1) |
| the chain is `capture_event → process_pending → run_all → build_cards_for_org` | ⚠️ partly — it omits `finalize_l1`, provisioning, the post-passes and the funnel counts, and has no clock (3.3, 3.4) |
| `NoLLM` serves every deterministic layer | ⚠️ partly — no mail reaches memory without a model answer: one mail costs about three calls (relevance twice, extraction once) |
| the runner fails rather than skips | ⚠️ today every database test skips in CI, including the "never skip" gates |
| `expected` holds workstream, stage and lane | ⚠️ the engine produces no workstream or stage yet (`STEP-09`), and the lane column is written NULL (F10) — those fields are `expressible: false` until then |
| the Atlas lines quoted in §2 and §3.2 | `[ATLAS]` — from the Atlas you shared; that file is not in the repository |

**Known causes the before-score will show.** These cases stay in the set and fail until the cause
is fixed — that is what a before-score is for:

- **F04** (a meeting becomes a deadline that expires): 7, 12, 26–29, 40;
- **F14** (Boardy can never be an agent sender) and the N-02 drop on its unsubscribe header: 3–9, 37;
- **B2** and **B19** are fixed before this step (`yc2_w27/M16`, `M17`); before those fixes they would
  have blocked 10–15 and 25–29, and 17, 22, 24 and 25 `[inference]`.

## 10 · Built — 2026-10-06 (`yc2_w27/M19`, 18 units green)

**How to run it.**

```
export GENIOS_TEST_DATABASE_URL=postgresql+psycopg://postgres:scratch@127.0.0.1:55432/genios_test
GENIOS_GOLDEN_REQUIRED=1 .venv/bin/python -m pytest tests/replays -q   # the set — it never skips
.venv/bin/python scripts/golden_score.py                               # the board
.venv/bin/python scripts/golden_eval.py --dry-run     # what one live pass would cost; no database
.venv/bin/python scripts/golden_eval.py --record F07  # re-record a case's cassette after a prompt change
```

`--dry-run` today: 288 model calls, 493,738 tokens in, 27,638 out — **≈ $0.63** for one live pass
on Haiku 4.5 at list price (the token counts are the ideal reader's estimates).

**What each piece is.**

| Piece | Where |
|---|---|
| a case: provider-shaped mail and calendar, the sweep instants, what must and must never show, a witness, the declared gaps | `tests/replays/founder_case.py`; the 40 in `tests/replays/specs/founder/` |
| the recorded model, keyed by the prompt's hash — fence nonces and minted ids normalised, nothing else | `tests/replays/harness.py` |
| every model site, recorded or off with its reason, held equal to `_SITES` | `tests/replays/model_sites.py` |
| the ideal reader that wrote the cassettes — a faithful reading of each prompt as written | `tests/replays/ideal_reader.py` |
| a case's cassette: written once, replayed exactly, never carrying a real name | `tests/replays/cassettes.py`; `tests/replays/specs/founder/cassettes/` |
| the runner — the production sync door, `finalize_l1`, `_run_l2_chain` at the case's instants, the model doors, a pinned world, the tenant removed on every exit | `tests/replays/engine_runner.py` |
| the marking — pass, fail, not exercised, not expressible; and where a case was lost | `tests/replays/marking.py` |
| the Atlas mutations a case drives, and why the rest cannot be driven yet | `tests/replays/atlas_expression.py` |
| CI | the `golden-pg` job in `.github/workflows/ci.yml` — it first runs when you push the batch |

**What the numbers judge.** The ENGINE, given a faithful reader of every prompt — not the model.
Where production's model went wrong (it junked the real investor mails; it wrote *"Send Mr Rohit
Swerashi…"*), a case passes or fails here on the engine alone. The model's half is
`golden_eval.py --live` — your call (`06` D12c).

**What the build found, and fixed on the way** — each a unit of `yc2_w27/M19.C3`:

- the narrator was asked two different questions about one situation on identical runs — the
  quotes of one message and the card's facts came back in a different order (`03` F39;
  `M19.C3.L-logic.V1.U02`, `V1.U03`);
- a statement nobody could resolve was anchored on a person chosen by random node id — on the
  founder's own sent mail, the founder, shown as the counterparty of the founder's own words
  (`03` F40; `M19.C3.L-logic.V1.U04`).

**What it found and left for its step** (`03-FINDINGS.md` F38, F41–F49): the floor (2,500) is where
the founder set dies — 9 of the 18 failing must-detect cases are lost before memory, every one at
the floor; a paid relevance call on every calendar event; the domain proposer wired nowhere; L2's
fixpoint not converging on 3 cases; evidence that quotes the sender's name; accelerators framed as
investors; a follow-through narrator told a meeting happened; one ask making several cards; and the
engine's own nondeterminism, which the runner pins and `STEP-17` must remove.

**Added in build** (each in `tree.yaml`): `M19.C1.L-logic.V1.U04` the ideal reader, `V1.U05` the
marking, `M19.C4.L-data.V2.U04` the cassette file, `M19.C3.L-logic.V1.U02–U04` the three engine
fixes.

**Follow-ups — proposed, not yet units.** Found by the crosscheck of the build; none blocks the push.

| | What | Proposed |
|---|---|---|
| a | the set drives the 6-hourly sweep door only. The first-connect door (`api/routes._process_and_reason_unlocked`) is a second chain with its own order, and no case runs it | a runner mode for it — `yc2_w27/M19.C3.L-integration.V3.U05` |
| b | 23 of the 40 cases forbid nothing, so their verdict rests on the expected cards alone | a forbidden list per case (the founder as the person to reply to, a payment nobody stated) — `yc2_w27/M19.C4.L-data.V3.U06` |
| c | the forbidden phrase *happened* is matched as a substring: a card saying *"nothing happened"* would trip it | match the forbidden claim, not the word |
| d | the engine's own nondeterminism (`03` F38, F41) is pinned by the runner, not removed | `STEP-17`; its probe is every case run twice unpinned, prompts compared |

**Unknowns.**

- Production's `GENIOS_L4_LLM_DECISION_MAKER` today. The runner switches the decider on, as
  `speedrun008/YCW27/STATUS.md` records production; `YCW27` decision R1
  (`19-PENDING-who-owns-what.md`) recommended `false`. If production runs it off, the golden set
  runs a decider production does not — one look at the deploy's environment (Rohit or Harsh).
- Whether `golden-pg` is green on GitHub — Python 3.12 there, against cassettes recorded on 3.13.
  Known at the first push.
- What the real model answers to these prompts — the live evaluation, not run (D12c).
