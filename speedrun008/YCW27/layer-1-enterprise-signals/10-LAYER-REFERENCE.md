# L1 · Enterprise Signals — `capture/`

**154 files · 46,377 lines · 19 subsystems.** Milestone **M9**, 9 units.

> What happened, how reliable is it, and which of the incoming signals belong together?

L1 decides what a message **says** — never what it means for the company, and never what to do.
Its job is to hand reasoning facts that are sourced, typed, dated, deduplicated and honest about
coverage.

---

## What it owns

| Subsystem | Owns | Touch when |
|---|---|---|
| `connectors/ connections/ acquire/` | OAuth, cursors, webhooks, backfill windows | a new source is added |
| `landing/` | durable source events, idempotent insert, dedupe | something arrives twice or not at all |
| `preprocess/ documents/ transcripts/` | normalisation, PII, attachments, meeting transcripts | a number or date extracts wrong |
| `gate/ domain/ triage/` | S0–S2 admission, domain pre-class, P0–P3 | noise gets in, or signal is parked |
| `esqe/` (17 files · 9,278 lines) | the qualification engine — detector, classifier, ALG-17 importance, ALG-19 expiry, publisher | a signal type is missing or mis-scored |
| `coverage/` | ⛔ the coverage receipts the Atlas thinks do not exist | an absence claim needs its proof |
| `screen/` | ScreenSignal, entering like any other signal | Screen evidence changes shape |

**The one crossing out** is `esqe/publisher.py`, and it says so itself: *"the L1 → L2 boundary, and
the last thing Layer 1 does… There is exactly one crossing and this is it."* It wires
`contracts/publication.py::validate_publication` (V-1…V-7) rather than re-implementing the rules,
because *"a second implementation would fork from the first the day either was edited."*

---

## Measured today

| | |
|---|---|
| Domain coverage | 125 of 162 tagged (77%) · 37 with no domain |
| Relevance | top bucket `no_model_wired` = **251** — no model wired in prod |
| Threads | 705 messages · 358 (51%) multi-message · 132 threads · longest 9 |
| Joinability | 83 of 85 (97.6%) |
| OCR | 122 rows, **not one** carried an engine · 830 `ocr_unavailable` |
| Backfill window | **60 days** — a 6- or 12-month question is structurally unanswerable |
| Coverage receipts | ✅ built — per source, frozen at capture, unknown stays `None` |

⛔ **Two bugs fixed on 29 Sep that had been silently losing data:** every `qualified_signals`
INSERT was refused for a missing bind (**321 signals lost in one run**, reported as success because
`put()` swallows by design), and `teams` was allowed-but-never-read on every tenant.

---

## What changes — M9

### `M9.C1` The signal bundle

| Unit | What |
|---|---|
| `U01` | `QualifiedEnterpriseSignalBundle` contract — signals, entities, candidate relationships, `unresolved[]`, and a coverage receipt that **reuses** `SourceCoverage` rather than blending a new number |
| `U02` | the bundle table, keyed so a replayed signal is idempotent |
| `U03` | the grouper — **incoming signals only**, joined by entity, thread, time window, commitment, meeting. It does not read the graph |
| `U04` | the coverage receipt assembled onto the bundle — per source, never blended |
| `U05` | the publisher emits a bundle **beside** `qualified_signals`, both counted on one sweep before either is retired |

⛔ `U03`'s "does not read the graph" is not a style note — it is what keeps decision 2 honest. The
moment bundling reads `context/`, L1 imports L3 and the topology test fails the build.

### `M9.C2` The evidence-need door

| Unit | What |
|---|---|
| `U06` | `EvidenceNeed` — question, why it changes the decision, acceptable and unacceptable sources, time range, visibility, cost limit, expiry, idempotency key |
| `U07` | `evidence_needs` — open / met / unavailable, never hard-deleted |
| `U08` | the executor — fetch the thread, backfill history, re-extract an attachment, bounded by the need's own cost limit |
| `U09` | ⛔ **the wire that does not exist**: `residue.signal_unreached` already measures *"the Layer 1 verdicts no Layer 2 reading consumes"* and reaches only the angles. It raises an `EvidenceNeed` instead |

---

## Two costs the missing wire is charging today

- **The 60-day window.** P3 asks six months, P4 twelve; the connection fetches 60 days. Those
  benchmarks are not unproven — they are **structurally impossible**, because the mail was never
  fetched.
- **`"message 1 of 1"`.** Every prompt L1 ever sent told the model this was the only message in its
  thread, including on a twelve-message negotiation. Fixed — but only for mail arriving from now
  on, because nothing can ask for the old mail again.

## Open, not in M9

Absence-derived signals sit in `context/quality/` today, one layer above where the Atlas puts them.
Moving them is a real decision, not a bug — record it before anyone moves a file.

## Read these first

`capture/esqe/publisher.py` · `capture/coverage/signal_coverage.py` · `context/residue.py`
