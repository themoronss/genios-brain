# Step 8 — PENDING · OCR has never run · owner: Harsh (CTO)

> **Status:** PENDING · **not blocked on any code in this repo** · **owner: Harsh**
> **Why it is yours:** the fix is a deploy.
> **Carried forward from** `../../Ancient Architecture/plan/layer-1/STEP-01-PENDING-HARSH.md`,
> still true on 2026-09-30.

---

## 1 · The finding

| | Measured 29–30 Sep |
|---|---|
| `document_jobs` rows | **122** |
| rows that ever carried an engine | **0** |
| `ocr_unavailable` rows | **830** |
| attachments stuck at `fetch_failed` | **341** |

The `enable_ocr` flag has been correct since 10 September. `tesseract_available()` answers **False**
on the host, which means the Tesseract stack is not in the running image.

## 2 · What to check, then do

1. DO App Platform → component → **Settings → Source**: which **branch**, which **source directory**
2. **Activity → last deployment → build log**: `Dockerfile` or `Buildpack`, and the **date**
3. Deploy so the component builds from the **Dockerfile** at the repo root

## 3 · ⛔ A related defect in our own test suite, and it is ours not yours

`tests/capture/documents/test_ocr_enablement.py::test_the_wiring_returns_no_engine_rather_than_one_that_raises`
**fails on any machine without `pytesseract` installed.**

`tesseract_available()` checks the binary **and** the Python bindings — and its own docstring says
why: *"the deploy image gained the apt packages while `pytesseract` and `Pillow` were in no
requirements file."* The test patches only the binary half, so it passes where `pytesseract` happens
to be installed and fails where it is not.

**This is the 1 failure in our otherwise-green 13,365-test run.** The fix is a decision: patch the
second half in the test, or put the bindings in a requirements file. It belongs with this step.

## 4 · Scenario → expected result, after the deploy

| Scenario | Expected |
|---|---|
| a scanned PDF arrives | `document_jobs.ocr_engine = 'tesseract-eng'`, `ocr_pages > 0` |
| the binary is still absent | `make_ocr` returns **None** and the document **parks recoverably** — it must never wire an engine that raises inside a sync batch |

---

## 5 · 2026-10-01 · section 3 is CLOSED. Section 2 is still yours.

Section 3 offered a choice — *"patch the second half in the test, or put the bindings in a
requirements file."* **The test was patched.** Full audit:
`11-AUDIT-E-the-test-that-measured-the-host.md`.

The requirements-file option was **not** taken, and deliberately: adding `pytesseract` and `Pillow`
to requirements would make the test pass by changing the deploy, which is section 2's job and
Harsh's call about image size. A test should not be the reason a dependency enters the image.

    tests/capture/documents/test_ocr_enablement.py    19 passed    (was 18 passed, 1 failed)

**What was added, beyond making the red one green.** The half the test left to the host is the half
that actually broke production, and it had **no coverage at all** — proved by mutation: with
`tesseract_available()`'s bindings check replaced by `return True`, the old suite stayed **green**.
Three new tests now fail on that mutant, one per binding plus one asserting the probe asks about
both. The product code was not touched.

### ⛔ What this does NOT change

| | |
|---|---|
| `[L1] attachments carry readable text` | **still FAILS at 872** |
| `tesseract_available()` on this host | **still False, and still right** |
| Documents newly readable | **zero** |

Section 2 is unchanged and still yours: the two Python packages in `requirements`, and the apt
package in the image, both together. Until then the receipt stays red, which is the honest surface
for a missing deploy — and the green test now claims something narrower and true: *when the stack
is present the wiring builds an engine; when either half is missing it builds nothing.*

The stale count in section 3 — *"the 1 failure in our otherwise-green 13,365-test run"* — was true
when written. The suite is now 14,5xx; this line is corrected here rather than edited above.
