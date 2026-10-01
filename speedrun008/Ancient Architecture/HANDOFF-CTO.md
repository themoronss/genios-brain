# Handoff — for Harsh

> ## ⚠️ SUPERSEDED, 2026-09-24 — read [`HARSH-ORDER.md`](HARSH-ORDER.md) instead.
> This file covered steps 1–3 only. Steps 4 and 5 have since added two decisions, one migration
> and one measurement, and `HARSH-ORDER.md` carries all nine items in the order to do them.
> Kept because its step-by-step detail on OCR and the first two migrations is still accurate.

> **From:** Layer 1 investigation on branch `speedrun008`, 2026-09-23
> **What this is:** the things that are blocked on you. Everything else is being done in the repo.
> **Read time:** 4 minutes. Two actions, one question.

---

## TL;DR

| # | Action | Why it is yours | Effort |
|---|---|---|---|
| **1** | **Deploy an image built from `Dockerfile`** | OCR has never run once in production. It is not a flag or a code problem — the image has never reached the host | ~1 hour |
| **2** | **Give us a scratch Postgres URL** | 618 of 13,660 tests cannot run without one, and they are exactly the L1→L2 seam tests | ~30 min |
| **3** | **Apply `migrations/0176_delivery_failure.sql`** | a CHECK constraint refuses the new signal type; without it every bounce signal fails to insert | minutes |
| **4** | **Apply `migrations/0177_qualified_signals_subject_key.sql`** | the widened projection READS this column; deploy without it and every situation read fails | minutes |
| **5** | **Answer one question** — was the 19 Sept tenant re-sync intentional? | the pilot corpus vanished; it changes what our baseline means | 2 min |

> Action 4's full runbook: **[`plan/layer-1/STEP-03-PENDING-HARSH.md`](plan/layer-1/STEP-03-PENDING-HARSH.md)**.
> **Apply 0176 and 0177 in number order, both BEFORE the code that uses them.**
>
> Action 3's full runbook: **[`plan/layer-1/STEP-02-PENDING-HARSH.md`](plan/layer-1/STEP-02-PENDING-HARSH.md)** —
> the bounce path is built and green; the migration and a replay are what remain.

---

## Action 1 · Deploy the OCR image

> **Full runbook — what to check, what to do, how to verify, and what it will *not* fix:**
> **[`plan/layer-1/STEP-01-PENDING-HARSH.md`](plan/layer-1/STEP-01-PENDING-HARSH.md)**
> The summary below is the short version.

### What we measured, in production, today

`document_jobs` for `org_e97e86f858ad48b2bbf64b8a`:

```
ocr_unavailable · image/png       21    ocr_engine=None   ocr_pages=0
ocr_unavailable · image/jpeg       7    ocr_engine=None   ocr_pages=0
unsupported     · text/calendar   57    ocr_engine=None   ocr_pages=0
unsupported     · application/ics 22    ocr_engine=None   ocr_pages=0
fetch_failed    · application/pdf 13    ocr_engine=None   ocr_pages=0
```

**Not one row carries an `ocr_engine`. `ocr_pages` is 0 everywhere. OCR has never succeeded once.**

Those events were captured **19–23 September** — **nine days after** `enable_ocr` defaulted to
`True` (`fb1d5c0b`, 10 Sept). So the flags are already correct and `tesseract_available()` is still
returning `False` on the host.

### The most likely cause, and it is checkable in ten seconds

```
Dockerfile present on origin/harsh/mvp ....... YES   (landed ed1b10c3, 7 Sept)
Dockerfile present on origin/main ............ NO
origin/main is behind origin/harsh/mvp by .... 455 commits
```

**If the App Platform component builds from `main`, it never sees the Dockerfile**, falls back to
the buildpack, and the buildpack image has no `tesseract` binary and no `poppler`. That is exactly
the failure the Dockerfile's own header was written to fix.

> Production data *does* contain recent L1 v2 output (`qualified_signals` with importance
> components, `availability_change` signals), so the running code is not 455 commits old. The two
> facts together suggest the component either builds from a branch without the Dockerfile, or has
> not been rebuilt since 7 September. **Please confirm which** — we could not determine it from the
> repo.

### What to check

1. In DO App Platform → the component's **source branch** and **source directory**.
2. Confirm the Dockerfile is at the component root for that branch (it is at the repo root).
3. Confirm the last build used **Dockerfile**, not the buildpack.

### What to do

Deploy an image built from `Dockerfile`. It installs three apt packages — `tesseract-ocr`,
`tesseract-ocr-eng`, `poppler-utils` — and `requirements.txt` already pins the Python halves
(`pytesseract==0.3.13`, `Pillow==11.3.0`, `pdf2image==1.17.0`).

**No environment variable needs to change.** `enable_ocr` already defaults to `True`,
`ocr_enabled_orgs` and `ocr_disabled_orgs` are both empty, and
`resolve_ocr_availability`'s rule 4 gives an org the engine on the fleet default alone. *(The
Dockerfile's deploy note used to claim two env vars were still required. That was stale and has
been corrected on `speedrun008`.)*

### How we will know it worked

`tesseract_available()` flips to `True`, `make_ocr` returns an engine, and the heartbeat drain in
`api/routes.py` already requeues dead letters bounded to rows untouched for a week. **The 28 images
should clear themselves** — no further action.

Verify:

```bash
python -m scripts.l1_s1_report --org org_e97e86f858ad48b2bbf64b8a --database-url "<url>"
```

`DOC-06` should go to **0**.

### What deploying will NOT fix — please do not expect it to

| Parked | Count | Why OCR is irrelevant |
|---|---|---|
| `text/calendar` + `application/ics` | **79** | `.ics` invite files. Structured calendar data — OCR cannot read one and never will |
| `application/pdf` (`DOC-05`) | **13** | the *download* failed. A fetch/permission problem |
| **images (`DOC-06`)** | **28** | **this is the real OCR backlog** |

**66% of the "unread attachment" backlog is calendar invites.** We are handling that separately —
see "What we are doing" below.

---

## Action 2 · A scratch Postgres

### The problem

```
tests collected ....... 13,660
runnable here ......... 13,042
require Postgres ......    618   ← cannot run on this machine
```

No local Postgres, no Docker on the dev box. The hermetic lane silently skips those 618, and
`conftest.py` already documents why that matters: the hermetic lane once hid ~800 tests, and a
scratch database surfaced 12 failures the green suite never showed.

**Those 618 are not incidental.** They are the L1→L2 seam tests —
`test_l2_reads_what_l1_publishes.py`, `test_l1_seam_activation.py` — which are exactly what our
next step (widening the seam, 9 of 28 columns currently cross) must prove.

### What we need

A throwaway Postgres 15/16 we can point `GENIOS_TEST_DATABASE_URL` at. **Not production, not a
production copy** — the suite drops and recreates schema, and `tests/conftest.py` was written
after a "rolled back" fixture held locks on a paying tenant.

Any of these is fine: a Supabase free project · a DO managed dev DB · a container we can run if
Docker is enabled on this machine · a local install.

### Why not just use production

`scripts/_db.py` refuses a Supabase host unless `GENIOS_ALLOW_PROD_WRITE=1`, by design, because
`rebuild_graph.py` **wipes eight projection tables** and used to resolve production by default.
We have read production once today, read-only, with Rohit's explicit authorisation. **We will not
run the test suite against it.**

---

## Action 3 · One question

`source_events` for the pilot org now runs **2026-09-19 06:14 → 2026-09-23 12:50**, 1,202 events.

The pilot funnel (`docs/plans/L1_L4_PILOT_FUNNEL.md`) measured **849 events from 12 Aug – 8 Sep**.
**Those events are gone.**

> **Was the 19 September re-sync intentional?**

It matters because every baseline in our plan was taken from the September funnel, and if the
tenant is periodically reset then no before/after comparison survives across a reset. We have
already replaced the one baseline this affects, but we need to know whether to expect it again.

---

## What we are doing, so you do not have to

These are in progress on `speedrun008` and need nothing from you:

| | Work |
|---|---|
| ✅ | Corrected the `Dockerfile` deploy note — it claimed two env vars were still required |
| ▶ | **The bounce path.** `gate/rules.py` N-01 and N-03 **delete every delivery-status notification by design** — *"a bounce carries no business signal ever"*. Three pitch emails on 11 Aug never reached Afore and Surge, and nothing in the product can say so. New `DELIVERY_FAILURE` signal type, joined back to the sent message |
| ▶ | **The `.ics` routing defect.** 79 calendar attachments parked as "unsupported binary needing OCR", in a queue that can never drain; 23 have already dead-lettered |
| ▶ | **The seam.** L1 writes 28 columns to `qualified_signals`; Layer 2's projection selects **9**. `subject_key` — the key ALG-19 supersedes on — has a column on the drop ledger and **none on the published signal** |
| ▶ | **The two-tier contract.** 7 of 15 claim types are `list[str]` / `list[dict]` and **structurally cannot hold an evidence span**. `relationship_change` therefore scores 880–1200 bp, the lowest band of any type |

Full plan: `speedrun008/plan/` — 17 steps, `STATUS.md` is the live state, and
`plan/layer-1/ARCHITECTURE.md` is the map if you want the whole picture.

---

## Things that are healthy — for balance

The September prose is gloomier than the current database:

| Check | Result |
|---|---|
| documents with empty text and no `ocr_failed` marker | **0** — G2's criterion holds |
| structural-token offset round-trip failures | **0** over 728 re-scanned documents |
| parks stuck in `NEEDS_RECAPTURE` over 3 days | **0** |
| emit rate | **31%** (375 of 1,205), up from the pilot's 27% |
| signal types firing | **12 of 15**, up from 11 |
| dead modules in `capture/` | **0** of 119, by AST audit |

The layer is in better shape than the docs suggest. The failures we are chasing are **narrow and
specific**, and the biggest one on your side is a deploy.
