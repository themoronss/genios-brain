# Step 1 · OCR — findings

**Run:** 2026-09-23 · branch `speedrun008` · code + git, then PRODUCTION read-only on Rohit's
explicit authorisation. **No write was issued.**
**Step file:** `../step-01-ocr.md` · **Verdict:** 1-U1 COMPLETE · 1-U2+ BLOCKED on a deploy

---
## Unit 1-U1 findings

### The timeline, and it changes the step's premise

| Date | Event | Source |
|---|---|---|
| 2026-09-07 | Dockerfile lands — `tesseract-ocr`, `tesseract-ocr-eng`, `poppler-utils` | `ed1b10c3` |
| 2026-09-08 | Heartbeat OCR drain lands, incl. dead-letter requeue | `0d000719` |
| **2026-09-08** | **Pilot funnel measured — the "159 parked attachments" number** | `68091262` |
| **2026-09-10** | **`enable_ocr` default flips to `True`** | `fb1d5c0b` |

> **The 159 number predates the fix by two days.** It was measured on a run where OCR was off by
> default. **Metric 1's START value in this file is stale** and must not be treated as today's
> state.

### The four questions

**Q1 · Is the engine present on the deployed host?**
Repo side: **both halves are in place.** `Dockerfile` installs the three apt packages;
`requirements.txt` pins `pytesseract==0.3.13`, `Pillow==11.3.0`, `pdf2image==1.17.0`. The
Dockerfile's own deploy note records that DigitalOcean App Platform prefers a Dockerfile at the
component root over its buildpack, so the first deploy after 2026-09-07 switched build strategy.
**Unverifiable from here** — needs a deploy log or a runtime probe.
*Local host: `tesseract` is NOT installed, so `tesseract_available()` is `False` locally and OCR
cannot be exercised end-to-end on this machine.*

**Q2 · Is the pilot org allowlisted or denylisted?**
**Neither. `.env` contains no OCR key at all.** Code defaults apply: `enable_ocr = True`,
`ocr_enabled_orgs = ""`, `ocr_disabled_orgs = ""`. Walking
`resolve_ocr_availability`'s precedence — engine present → not denied → not allowlisted → fleet
default `True` — the org resolves to **ENABLED**.
→ **Possibility B (denylisted) is ELIMINATED.**

**Q3 · Current count per park code** — **BLOCKED.** See below.
**Q4 · `DOC-02` file-type histogram** — **BLOCKED.** See below.

### What this eliminates

| Possibility | Verdict |
|---|---|
| A · the deployed host lacks the binary | **the only one still open** on the code side |
| B · this org is denylisted | **ELIMINATED** — no OCR keys exist |
| C · OCR runs but the queue was never drained | **ELIMINATED in code** — `api/routes.py` drains on the heartbeat, allowlisted orgs first with their own engine, then a fleet pass with `make_ocr(None)`, and requeues dead letters bounded to rows untouched for a week — **but only when an engine actually exists** |
| **D · it already drained and nobody re-measured** | **NEW — and given the timeline, the most likely** |

### Why Q3/Q4 are blocked, and it is deliberate

`.env`'s `GENIOS_DATABASE_URL` points at **production Supabase**. `scripts/_db.py` refuses to
resolve a target implicitly — no fallback to `Settings`, a URL must be named via `--database-url`
or `GENIOS_TARGET_DATABASE_URL`, and **a Supabase host is refused a second time unless
`GENIOS_ALLOW_PROD_WRITE=1` is exported for that command.** Its docstring states the intent:
*"touching production is always two deliberate acts."*

That guard exists because `scripts/rebuild_graph.py` once resolved production by default and
**wipes eight projection tables**. Reading production is a decision for the operator, not for a
tooling run. **Awaiting that decision.**

### One defect found on the way — actionable now, no database needed

`Dockerfile`'s deploy note still says:

> *"Enabling OCR itself is still two deliberate acts after that — `GENIOS_ENABLE_OCR=true` plus
> the org allowlist `GENIOS_OCR_ENABLED_ORGS`."*

**Both clauses are now false.** `enable_ocr` has defaulted to `True` since `fb1d5c0b`, and
`resolve_ocr_availability` rule 4 means the allowlist is **not required** when the fleet default is
on — the allowlist exists to turn OCR on for one org *while the fleet default is off*. Anyone
following that note today would set two env vars that change nothing, and could reasonably
conclude OCR is off when it is on. **Fix pending.**

### Q3 and Q4 — answered against PRODUCTION, read-only, on Rohit's explicit authorisation

Run 2026-09-23 via `scripts/l1_s1_report.py` (declares itself read-only; grep confirms SELECT
only) plus two ad-hoc SELECTs. Target printed by the guard: Supabase `aws-0-ap-southeast-1`,
credentials redacted. **No write was issued.**

#### First, a correction that invalidates the baseline

```
source_events for this org:  2026-09-19 06:14  →  2026-09-23 12:50   ·  1,202 events
```

**The pilot corpus is gone.** The funnel's 849 events from 12 Aug – 8 Sep no longer exist for this
tenant; every row is from a re-sync that began 19 September. So the "159 parked attachments" is not
a stale number to be adjusted — **it describes a corpus that no longer exists.** Metric 1's START
value is replaced outright below.

#### Q3 · park counts today

| Code | Meaning | pending | dead_letter | total |
|---|---|---|---|---|
| DOC-02 | unsupported binary | 56 | 23 | **79** |
| DOC-06 | pages, no OCR engine | 9 | 19 | **28** |
| DOC-05 | attachment download failed | 6 | 7 | **13** |
| | | **71** | **49** | **120** |

`low_relevance` · **321 pending** — the largest park bucket in the tenant, larger than every DOC
code combined, and it appears nowhere in this plan. **Flagged for triage.**

#### Q4 · the file-type histogram — and it shrinks the step by 77%

| Code | Format | pending | dead | total | Is OCR the answer? |
|---|---|---|---|---|---|
| DOC-02 | `text/calendar` | 38 | 19 | **57** | **No** — structured calendar data |
| DOC-02 | `application/ics` | 18 | 4 | **22** | **No** — same |
| DOC-06 | `image/png` | 6 | 15 | **21** | **Yes** |
| DOC-06 | `image/jpeg` | 3 | 4 | **7** | **Yes** |
| DOC-05 | `application/pdf` | 6 | 7 | **13** | **No** — the *download* failed |

> **79 of 120 parked attachments (66%) are `.ics` calendar invite files.** OCR cannot read one and
> never will. **13 are PDFs whose fetch failed** — a network/permission problem, not an OCR one.
> **The true OCR-addressable backlog is 28 images.**

#### Q1 · answered definitively — the engine is NOT on the deployed host

```
document_jobs, this org:
  ocr_unavailable · image/png   21     ocr_engine=None   ocr_pages=0
  ocr_unavailable · image/jpeg   7     ocr_engine=None   ocr_pages=0
  unsupported     · text/calendar 57   ocr_engine=None   ocr_pages=0
  unsupported     · application/ics 22 ocr_engine=None   ocr_pages=0
  fetch_failed    · application/pdf 13 ocr_engine=None   ocr_pages=0
```

**Not one row carries an `ocr_engine`. `ocr_pages` is 0 everywhere. OCR has never run once on this
tenant.** And these events were captured **19–23 September — nine days after `enable_ocr` defaulted
to `True`.** So `tesseract_available()` is returning `False` in production.

→ **Possibility A confirmed: the running deployment is not built from the `Dockerfile`.**
The image exists in the repo and has never reached the host. **This is a deploy action, not a code
change.**

### What the report's other three metrics say — all PASS

| Metric | Result |
|---|---|
| documents with empty text and **no** `ocr_failed` marker | **0** — G2's criterion holds |
| structural-token offset round-trip failures | **0** over 728 re-scanned documents |
| parks stuck in `NEEDS_RECAPTURE` over 3d | **0** |

The layer is in better shape than the September prose suggests. The failure is narrow and it is
operational.

### New finding — `.ics` parked as "unsupported binary" is arguably a routing defect

An `.ics` attached to an email is **structured calendar data**, not a document awaiting OCR.
Parking 79 of them under `DOC-02` puts them in a queue that **can never drain**, and 23 have
already dead-lettered. Either the gate should route `text/calendar` to the structured lane, or it
should refuse it with a terminal reason that does not imply "we will look again". **New unit —
belongs in step 16 (source field coverage) or its own; not a silent fix.**

### Metric 1 · START, corrected

| | Old (stale, different corpus) | **Corrected, 2026-09-23** |
|---|---|---|
| "Attachments never read" | 159 | **120 parked · of which 28 are OCR-addressable** |
| OCR-addressable target | 159 → 0 | **28 → 0** |
| Non-OCR remainder | — | 79 `.ics` (routing) · 13 PDF (fetch) |

### Status

**Step 1 · 1-U1: COMPLETE.** All four questions answered.
**Step 1 · 1-U2 onward: BLOCKED on a deploy.** The action is to make the running deployment build
from the `Dockerfile`; no code change in this repo will move the number. Once deployed,
`tesseract_available()` flips, the heartbeat drain requeues dead letters, and the 28 images should
clear themselves.

**Also pending from this unit, and doable without a deploy:**
1. Correct the stale `Dockerfile` deploy note (both clauses now false).
2. Decide the `.ics` routing question.
3. Triage `low_relevance` · 321 pending.
