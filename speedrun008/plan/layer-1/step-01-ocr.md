# Step 1 — OCR: establish the real state, then drain

**Status:** 1-U1 COMPLETE (2026-09-23) · 1-U2+ **BLOCKED on a deploy** · **Effort:** hours · **Depends on:** nothing · **Engine:** D (deterministic)
**Moves:** metric 1 — attachments never read, **159 → 0**

---

## 1. Why this step exists

On the pilot run of 849 objects, **159 attachments were captured, parked, and never read**:

| Park code | Meaning | Count |
|---|---|---|
| `DOC-02` | unsupported binary type | 119 |
| `DOC-06` | has pages, no OCR engine wired | 25 |
| `DOC-05` | attachment download failed | 15 |

An unread attachment is the worst kind of loss in Layer 1, because a document is the *highest
authority artifact the layer handles*. ALG-14 ranks a signed PDF above an email above a chat
aside — so the layer is discarding exactly the material it weighs most. The benchmark's P2 and P5
both turn on contract and proposal contents.

This is also the cheapest step in the entire plan. The OCR stack is already in the deploy image
(`Dockerfile`: `tesseract-ocr`, `tesseract-ocr-eng`, `poppler-utils`; pip: `pytesseract`, `Pillow`,
`pdf2image`). **Nothing needs to be built.**

## 2. Current status — with evidence

**A correction that matters.** The funnel doc (2026-09-08) says OCR is off. That is now **stale**.
Since then:

```python
# genios_engine/platform/config.py:207-212
# Default ON since the deploy image gained both halves of the stack (apt: tesseract-ocr,
# tesseract-ocr-eng, poppler-utils; pip: pytesseract, Pillow, pdf2image). Flipping the
# default cannot break a host that lacks them: `make_ocr` asks `tesseract_available()`
enable_ocr: bool = True
ocr_enabled_orgs: str = ""
ocr_disabled_orgs: str = ""
```

So the instruction is **not** "turn on a flag". `enable_ocr` is already `True`. Three other things
can still be false, and **which one it is has never been checked**:

| Possibility | How it presents | Where |
|---|---|---|
| A · the deployed host lacks the binary | `tesseract_available()` returns `False`, OCR silently unavailable | `platform/wiring.py:147-155` |
| B · this org is denylisted | `ocr_disabled_orgs` contains it | `capture/documents/enablement.py:57` |
| C · OCR runs, but the queue was never drained | parked rows sit at `pending` with nothing re-reading them | `capture/parked/drain.py:63-66` |

`DOC-02`, `DOC-05` and `DOC-06` are all in `drain.py`'s drainable set, and
`parked/refetch_policy.py:32-33` states explicitly that these codes are **not terminal** — they
are parked precisely so a later capability change can settle them.

> **Do not skip to the fix.** The whole point of this step is that nobody knows which of A, B or C
> is true, and each has a different action.

## 3. Expected result — the number that must move

| | Before | After |
|---|---|---|
| `DOC-06` parked (pages, no engine) | **25** | **0** |
| `DOC-05` parked (download failed) | **15** | 0 if transient; a terminal state with a reason if not |
| `DOC-02` parked (unsupported type) | **119** | whatever OCR + native cannot read, **each with an explicit reason** |
| Documents with empty text and **no** `ocr_failed` marker | must be 0 | must stay 0 — this is gate G2's criterion |

**Prediction to write down before starting:** `DOC-06` → 0 and `DOC-05` → near 0. `DOC-02` is the
uncertain one; 119 is large and its composition is unknown. **If `DOC-02` does not fall
substantially, the cause is a file-type mix the router genuinely cannot read**, and that is a
finding to record, not a failure to hide.

## 4. Edge cases and failure scenarios

| # | Scenario | What must happen | Why |
|---|---|---|---|
| E1 | OCR engine crashes on a page | marker `ocr_failed`, **never an empty string** | an unmarked empty document is indistinguishable from one that said nothing — G2's whole criterion |
| E2 | OCR returns only whitespace | marker `ocr_failed` | `ocr_policy.py:63` — "beats confidence" |
| E3 | OCR returns text below the confidence floor | `DOC-04`, parked, retryable | a bad read is not a good read |
| E4 | The binary is missing on the host | `resolve_ocr_availability` says unavailable; events park `DOC-06` and **say so** | must not look like "the document was empty" |
| E5 | A 400-page PDF | chunking preserves offsets into the **original**; spans must still resolve | ALG-08 and the evidence binder both resolve against it |
| E6 | The same attachment is re-fetched | dedup must not create a second event | three distinct dedup jobs exist; do not disturb them |
| E7 | An encrypted / password-protected PDF | terminal, with its own reason | retrying forever is a cost leak |
| E8 | Draining 159 at once | must not starve live capture | the drain is a background path; check it is rate-limited |
| E9 | A drained attachment now produces a signal | it must flow through the **full** pipeline — gate, extraction, ESQE, publish | a recovered event flips to `emitted`; it must not bypass qualification |

## 5. How to do it — unit by unit

### 1-U1 · Establish the truth (no code change)
Answer, in order, and **write each answer into STATUS.md**:
1. Is `tesseract_available()` `True` on the deployed host?
2. Is the pilot org in `ocr_enabled_orgs`, in `ocr_disabled_orgs`, or in neither?
3. What is the current count per park code for that org?
4. Of the 119 `DOC-02`, what is the **file-type histogram**? (This decides whether step 1 ends at
   0 or at an honest remainder.)

### 1-U2 · Act on what U1 found
* **A (no binary):** the deploy lacks the image layer. Fix the deploy, not the code.
* **B (denylisted):** remove the org from `ocr_disabled_orgs`.
* **C (never drained):** run the parked drain for this org and watch the codes fall.

### 1-U3 · Drain and verify
Run the drain. Then re-run the funnel report and diff every park code.

### 1-U4 · Record the remainder
Whatever `DOC-02` does not clear gets a one-line reason per file type. **A remainder with a
reason is a pass; a remainder without one is not.**

## 6. Test cases

Nothing new is built here, so the tests are **existing gate criteria re-run**, plus one new
regression:

| Test | Asserts | New? |
|---|---|---|
| `tests/capture/documents/` | native, OCR, policy, chunking behaviour | existing |
| G2 criterion | **0 documents with empty text and no `ocr_failed` marker** | existing |
| G2 criterion | 0 structural-token offset round-trip failures after chunking | existing |
| **new** | a drained `DOC-06` event reaches `emitted` and produces at least one extraction — i.e. the recovered event walks the **whole** pipeline, not just the document stage | **yes** |

The new one exists because edge case E9 is the only way this step can silently half-work: the
attachment becomes readable, and its content still never becomes a signal.

## 7. Verify commands

```bash
# the document suite
uv run --no-sync pytest tests/capture/documents -q -p no:randomly

# the parked suite — 14 files, the drain paths
uv run --no-sync pytest tests/capture/parked -q -p no:randomly

# the S1 report: park codes and their counts
python scripts/l1_s1_report.py --org <org> --database-url "<url>"

# the funnel, before and after — the number that matters
python scripts/pipeline_funnel_report.py --org <org> --database-url "<url>"
```

## 8. Done criteria

Full detail: **[`findings/step-01-ocr.md`](findings/step-01-ocr.md)**.

- [x] **U1's four answers recorded**, including the `DOC-02` type histogram — 2026-09-23
- [ ] `DOC-06` count is **0** — currently **28** (21 png + 7 jpeg). **Blocked on the deploy**
- [ ] `DOC-05` is 0 or terminal — **13 PDFs, all `fetch_failed`.** ~~needs its own unit~~ **PREMISE
      CORRECTED 2026-09-24: the unit already exists and is already wired.** `parked/refetch.py`'s
      five-rung ladder with a dead letter runs on the HEARTBEAT (`api/routes.py:1039` →
      `_drain_attachment_refetch`), it is passed an OCR engine, and it exposes
      `GET /parked/refetch` for status. Nothing is left to build. So 13 rows sitting at
      `fetch_failed` means one of three OPERATIONAL things, and the endpoint says which:
      the heartbeat is not running in production · they are mid-ladder and will clear ·
      they dead-lettered and the reason is recorded. **Moved to Harsh** — see
      [`HARSH-ORDER.md`](../../HARSH-ORDER.md) item 14
- [x] **`DOC-02`'s remainder has a per-type reason** — 79 are `.ics` calendar files. **OCR can never read one**; routing defect, logged as a new unit
- [x] **0 documents with empty text and no `ocr_failed` marker** — G2's criterion holds in production
- [ ] the E9 regression — a drained attachment produces an extraction. **Cannot be written until the engine exists**
- [x] **the report was run against production and its park table recorded**

### What U1 changed about this step

| | Before | After |
|---|---|---|
| Target | 159 unread attachments | **28 images.** 79 are `.ics`, 13 are failed downloads |
| Cause | one of three possibilities | **A confirmed** — `ocr_engine=None` on every `document_jobs` row; the image has never reached the host |
| Action | "flip two env vars" | **no env var changes.** A deploy, and it is the CTO's |
| Baseline | the 2026-09-08 pilot | **that corpus no longer exists** — the tenant re-synced on 19 Sept |

### Two units this step produced, neither of them OCR

1. **`.ics` routing** — 79 calendar attachments parked as "unsupported binary", in a queue that can
   never drain; 23 have already dead-lettered.
2. **`DOC-05` fetch failures** — 13 PDFs whose download failed. A network/permission path, untouched
   by anything in this plan.

Handoff to the CTO: **[`../../HANDOFF-CTO.md`](../../HANDOFF-CTO.md)**

## 9. What this step must NOT do

- **Do not change the OCR confidence floor** to make more documents pass. A bad read that is
  accepted is worse than a park that is honest.
- **Do not mark a failed read as empty.** E1 and E2 exist because that was the original defect.
- **Do not add a global flag.** If a per-org control is needed, it is a row.
- **Do not touch chunking offsets.** Spans resolve against them; G2 asserts the round-trip.
