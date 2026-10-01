# Step 1 — PENDING · owner: Harsh (CTO)

> **Status:** PENDING · not blocked on any code in this repo · **owner: Harsh**
> **Why it is yours:** the fix is a deploy. No change in `genios-brain` can move this number.
> **Written:** 2026-09-23 from a read-only production measurement.
> **Evidence:** [`findings/step-01-ocr.md`](findings/step-01-ocr.md) · **Spec:** [`step-01-ocr.md`](step-01-ocr.md)

---

## 1. The finding, in one line

**OCR has never run once in production.** Every `document_jobs` row for the pilot tenant carries
`ocr_engine = None` and `ocr_pages = 0`, and 28 image attachments sit at `ocr_unavailable` —
captured 19–23 September, **nine days after** `enable_ocr` defaulted to `True`.

So the flags are already correct. **`tesseract_available()` is answering `False` on the host,
which means the Tesseract stack is not in the running image.**

---

## 2. The most likely cause — checkable in ten seconds

```
Dockerfile on origin/harsh/mvp ........ PRESENT   (landed ed1b10c3, 7 Sept 2026)
Dockerfile on origin/main ............. ABSENT
origin/main is behind origin/harsh/mvp  455 commits
```

DigitalOcean App Platform prefers a Dockerfile over its buildpack **only when one exists at the
component's source root, on the branch it builds**. If the component builds from `main`, it never
sees the Dockerfile, falls back to the buildpack, and the buildpack image has no `tesseract`
binary and no `poppler`.

> **One thing does not fit, and you are the only one who can resolve it.** Production contains
> recent L1 v2 output — `qualified_signals` with importance components, `availability_change`
> signals, events from 19–23 Sept. So the running code is *not* 455 commits old. Either the
> component builds from `harsh/mvp` but **has not been rebuilt since 7 September**, or it builds
> from somewhere else. **Please check which before changing anything.**

---

## 3. What to do

### 3.1 · Check first

| # | Check | Where |
|---|---|---|
| 1 | The component's **source branch** | DO App Platform → app → component → Settings → Source |
| 2 | The component's **source directory** — the Dockerfile is at the **repo root** | same screen |
| 3 | The last build's **strategy** — `Dockerfile` or `Buildpack` | Activity → last deployment → build log |
| 4 | The last build's **date** — anything before 7 Sept predates the Dockerfile | same |

### 3.2 · Then deploy

Deploy the component so it builds from `Dockerfile`. Depending on what §3.1 shows, that is one of:

* the branch already has it → **trigger a rebuild** (a redeploy from the current commit is enough);
* the branch does not have it → **point the component at a branch that does**, or merge the
  Dockerfile forward into the deployed branch.

The Dockerfile installs three apt packages:

```
tesseract-ocr        the engine documents/tesseract.py shells to
tesseract-ocr-eng    the language data — the engine package alone reads nothing
poppler-utils        the rasterizer pdf2image needs for a scanned PDF
```

and `requirements.txt` already pins the Python halves: `pytesseract==0.3.13`, `Pillow==11.3.0`,
`pdf2image==1.17.0`.

### 3.3 · Do NOT set any environment variable

This is the part most likely to be got wrong, because the Dockerfile's own header used to say
otherwise. **It was stale and has been corrected on `speedrun008`.**

| Setting | Current | Change needed |
|---|---|---|
| `GENIOS_ENABLE_OCR` | defaults to `True` since `fb1d5c0b` (10 Sept) | **none** |
| `GENIOS_OCR_ENABLED_ORGS` | empty | **none** |
| `GENIOS_OCR_DISABLED_ORGS` | empty | **none** |

`resolve_ocr_availability` precedence: engine present → not denylisted → not allowlisted → **fleet
default decides → enabled**. The allowlist exists to turn OCR on for one org *while the fleet
default is off*. That is no longer the case, so it does nothing.

**Setting either list would be a no-op that looks like a fix.**

---

## 4. How the pieces connect — what happens on its own after the deploy

Nothing else needs doing. The chain is already wired:

```
deploy lands
     │
     ▼
tesseract_available()  →  True                    capture/documents/tesseract.py
     │
     ▼
make_ocr(org)  →  returns a TesseractOcr           platform/wiring.py:150
     │
     ▼
heartbeat drain runs                               api/routes.py
  · allowlisted orgs first, each with its own engine
  · then a fleet pass with make_ocr(None)
  · requeues dead letters, bounded to rows untouched for 7 days
  · ONLY when an engine actually exists  ← this is the gate that has never opened
     │
     ▼
parked DOC-06 attachments re-attempt  →  text  →  extraction  →  signals  →  Layer 2
```

The dead-letter requeue matters: **19 of the 28 images have already dead-lettered.** Without that
requeue they would stay dead for ever, and "turn OCR on" would silently mean "turn OCR on **and
also** go and requeue". It runs automatically, and only once an engine exists.

---

## 5. Cross-check — the procedure, in order

Same shape as steps 2 and 3. Every step is runnable, and each is a gate on the next.

### 5.0 · BEFORE — record these, or "it moved" is unprovable

```bash
python -m scripts.l1_s1_report --org org_e97e86f858ad48b2bbf64b8a --database-url "<url>"
```

```sql
-- has OCR EVER produced text for this tenant? (expect: no)
select status, format, ocr_engine, count(*), sum(ocr_pages)
  from document_jobs where org_id = 'org_e97e86f858ad48b2bbf64b8a'
 group by 1,2,3 order by 4 desc;
```

Today every row reads `ocr_engine = NULL`, `ocr_pages = 0`. **Write that down.**

---

### 5.1 · GATE 1 — the image really has the stack

Inside the running container, not on your laptop:

```bash
tesseract --version
python -c "from importlib.util import find_spec; \
           print(all(find_spec(m) for m in ('pytesseract','PIL','pdf2image')))"
```

**PASS: both.** `tesseract_available()` requires the binary **and** the bindings, and the check
exists because the image once gained the apt packages while `pytesseract` and `Pillow` were in no
requirements file — the binary probe said yes, an engine was wired, and every scanned document
came back `ocr_failed: ModuleNotFoundError`.

**If either half is missing, stop and tell us which.** That is a repo fix, not a deploy one.

---

### 5.2 · GATE 2 — the engine is actually wired for the org

`make_ocr` logs its decision either way — *"deliberately-off is a legitimate state; a silent None
was not"*. After a deploy, grep the app log for:

```
OCR not wired (org=..., <availability>): <detail>
```

**PASS: the line is absent.** If it appears, the `availability` value names the cause exactly:
`engine_missing` (gate 1 lied) · `disabled_for_tenant` (a denylist entry exists — there should be
none) · `disabled_globally` (the fleet default was turned off).

---

### 5.3 · GATE 3 — the backlog drains itself

No action needed: the heartbeat drain in `api/routes.py` requeues dead letters bounded to rows
untouched for seven days, **and only once an engine exists**. Give it a cycle, then:

```bash
python -m scripts.l1_s1_report --org org_e97e86f858ad48b2bbf64b8a --database-url "<url>"
```

| Park code | Before | After |
|---|---|---|
| `DOC-06` pages, no OCR engine | **28** (9 pending + 19 dead-lettered) | **0** |
| `DOC-05` download failed | 13 | **unchanged** — a fetch problem, not an OCR one |
| `DOC-02` unsupported binary | 79 | **unchanged** — 79 of them are `.ics` calendar files |

```sql
-- OCR has now actually run
select count(*) from document_jobs
 where org_id = 'org_e97e86f858ad48b2bbf64b8a' and ocr_engine is not null;   -- expect > 0
```

---

### 5.4 · GATE 4 — the three things that must NOT happen

```sql
-- 1 · no document may come back empty without saying why. This is G2's own criterion and it is
--     the defect the `ocr_failed` marker was invented for: an unmarked empty document is
--     indistinguishable from one that genuinely said nothing.
--     The S1 report asserts this directly — it must stay PASS at 0.

-- 2 · a BAD read must not be accepted as a good one
select count(*) from document_jobs
 where org_id = 'org_e97e86f858ad48b2bbf64b8a' and status = 'ocr_review_required';
-- Non-zero is FINE and expected. Zero alongside a large drain is suspicious — it would mean
-- the confidence floor is passing everything.

-- 3 · the corpus must not re-land
select count(*) from source_events where org_id = 'org_e97e86f858ad48b2bbf64b8a';
-- PASS: unchanged. A drained attachment is the SAME event recovered, not a new one.
```

---

### 5.5 · GATE 5 — nothing else moved

```bash
python -m scripts.pipeline_funnel_report --org org_e97e86f858ad48b2bbf64b8a --database-url "<url>"
```

**PASS:** captured / emitted / dropped counts unchanged except that some parked attachments have
become emitted. **This step reads documents that were already captured.** It does not change what
is captured, so if the capture numbers move, something else changed with it.

---

### 5.6 · Send back

| | BEFORE | AFTER |
|---|---|---|
| `DOC-06` parks | 28 | ? *(expect 0)* |
| `document_jobs` rows with an `ocr_engine` | 0 | ? *(expect > 0)* |
| `DOC-02` / `DOC-05` | 79 / 13 | ? *(expect unchanged — see §6)* |
| Documents empty with no `ocr_failed` marker | 0 | ? *(must stay 0)* |
| New signals produced | — | ? *(honest expectation: **0–2** — see §6)* |

**That last row is the one to read before celebrating.** See §6.

## 6. What this will NOT fix — please calibrate expectations

We checked what the 28 images actually are, by joining them back to the emails that carried them:

```
Mail Delivery Subsystem — Delivery Status Notification  (×3)
Foundation for I… — FITT FORWARD 2026, IIT Delhi
Navin Gaur — Fwd: Alumni Talk by Ms. Ramya Yellapragada
GUSEC · IBM Talent Acquisition · IIM Lucknow · Nasscom · PML School
Luke Jones · Naresh Sood · Saket Raj
```

These are **event invitations, institutional newsletters and talent-acquisition mail**. Their
attached images are almost certainly **banners, logos and event posters — not scanned contracts or
invoices.**

> **Honest expectation: this deploy will probably produce 0–2 new business signals on this tenant.**
> It will not move the importance ceiling, because banners carry no amounts.

**It is still worth doing**, for three reasons:

1. A capability that has never run once cannot be trusted on the day a tenant *does* send a scanned
   contract. This is the only way to find out it works.
2. `DOC-06 → 0` is a real metric moving, and the plan's rule is that a step is done when its number
   moves.
3. Until it runs, **every future document finding is unfalsifiable** — we could never tell "there
   was nothing in it" from "we never read it".

### And what it definitely does not touch

| Parked | Count | Why OCR is irrelevant |
|---|---|---|
| `text/calendar` + `application/ics` | **79** | `.ics` invite files — structured calendar data |
| `application/pdf` (`DOC-05`) | **13** | the **download** failed — a fetch/permission problem |

**66% of the backlog is calendar invites.** Both of these are **ours**, not yours — see §8.

---

## 7. If §3.1 shows the Dockerfile IS already being used

Then the cause is something else, and the next probe is a runtime one. Add a line to whatever
health endpoint you prefer, or run inside the container:

```bash
tesseract --version
python -c "from importlib.util import find_spec; print(all(find_spec(m) for m in ('pytesseract','PIL','pdf2image')))"
```

`tesseract_available()` requires **both** — the binary **and** the bindings. The check exists
because the image once gained the apt packages while `pytesseract` and `Pillow` were in no
requirements file: the binary probe said yes, an engine was wired, and every scanned document came
back `ocr_failed: ModuleNotFoundError`.

**Tell us which half is missing and we will fix the repo side.**

---

## 8. What stays with us — do not wait on these

Step 1 produced two units that are **not** yours and not OCR:

| Unit | What |
|---|---|
| **`.ics` routing** | 79 calendar attachments parked as "unsupported binary needing OCR", in a queue that can **never** drain; 23 have already dead-lettered. Either route `text/calendar` to the structured lane, or refuse it with a terminal reason that does not imply "we will look again" |
| **`DOC-05` fetch failures** | 13 PDFs whose download failed. These are the ones most likely to be **real documents**, and the path is untouched by anything in the plan |

We are also proceeding to **Step 2** (the bounce path) while this is pending. Nothing there needs a
deploy.

---

## 9. The two other things we need from you

Both are in [`../../HANDOFF-CTO.md`](../../HANDOFF-CTO.md); repeated here so this file stands alone.

1. **A scratch Postgres URL.** 618 of 13,660 tests cannot run without one, and they are exactly the
   L1→L2 seam tests that Step 3 must prove. **Not production, not a copy of it** — the suite drops
   and recreates schema.
2. **Was the 19 September tenant re-sync intentional?** The pilot's 849 events from 12 Aug – 8 Sep
   no longer exist; every row is from 19 Sept onward. Every baseline in our plan came from that
   older corpus.
