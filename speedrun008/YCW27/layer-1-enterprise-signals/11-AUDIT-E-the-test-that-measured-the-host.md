# AUDIT E · the one red test in 14,513 — it was measuring the host, not the product

Measured 2026-10-01. This test has been the suite's only failure for the entire session, and it
was carried as *"L1's known `pytesseract`-missing test"* — a known-failure label, which is the
thing that stops a test from being read.

---

## PART 0 · WHAT WAS RED

    tests/capture/documents/test_ocr_enablement.py
      ::test_the_wiring_returns_no_engine_rather_than_one_that_raises      FAILED

    >   assert engine is not None and engine.name == "tesseract-eng"
    E   assert (None is not None)

---

## PART 1 · THE PRODUCT IS CORRECT. THE TEST WAS INCOMPLETELY STUBBED.

`capture/documents/tesseract.tesseract_available()` requires **two** things, and says why:

    if shutil.which(TESSERACT_BINARY) is None:
        return False
    return all(importlib.util.find_spec(m) is not None for m in ("pytesseract", "PIL"))

The test stubbed `shutil.which` and left `find_spec` to whatever the host had. Its **first**
assertion — binary absent → `None` — passed. Its **second** stubbed the binary present and then
asserted an engine comes back, while `pytesseract` and `PIL` are not installed on this host. The
probe correctly answered False, and the test read that correct answer as a product failure.

> ⛔ **A test that leaves one prerequisite to the host is not asserting a product property.** On a
> machine with the bindings it passed and proved the wiring; on a machine without them it failed
> and proved only what was installed. Either way the thing it claimed to measure was not the
> thing deciding the result.

Two assertions had this shape — line 89 and line 94.

---

## PART 2 · AND THE HALF IT LEFT TO THE HOST IS THE HALF THAT ACTUALLY BROKE PRODUCTION

`tesseract.py:26`, in its own words:

> *"The bindings are checked too, and that is not belt-and-braces: the deploy image gained the apt
> packages while `pytesseract` and `Pillow` were in no requirements file, so the binary probe said
> yes, an engine was wired, and every scanned document came back `ocr_failed:
> ModuleNotFoundError`. A probe that answers 'installed' for a stack that cannot run is worse than
> no probe, because it moves the failure past the point where the reason is still legible."*

**Zero tests covered that half.** Proved by mutation — the bindings check replaced with
`return True`:

    before this unit   the suite was GREEN with the bindings check deleted
    after  this unit   3 tests fail:
        test_the_binary_without_its_bindings_wires_nothing[pytesseract]
        test_the_binary_without_its_bindings_wires_nothing[PIL]
        test_the_probe_is_not_answered_by_the_binary_alone

The binary-present case is exactly the state that makes a one-input probe dangerous, and it was
the state no test could reach, because reaching it required stubbing the thing the test did not
stub.

---

## PART 3 · WHAT LANDED

**E1 · `_bindings(monkeypatch, *, present=...)`** — puts *both* halves of the probe under the
test's control. It delegates to the real `find_spec` for every module outside `("pytesseract",
"PIL")`, so stubbing the probe cannot quietly change how anything else imports. The existing test
now proves the wiring logic deterministically on every host.

**E2 · `test_the_binary_without_its_bindings_wires_nothing`**, parametrised over both bindings —
because `all()` over two names is one `and` away from checking one, and a test that only removes
`pytesseract` would not notice `PIL` being dropped from the list.

**E3 · `test_the_probe_is_not_answered_by_the_binary_alone`** — records which module names the
probe asks `find_spec` about and asserts it is exactly both. Without this, E2 could be satisfied
by a probe that happens to fail for an unrelated reason.

    tests/capture/documents/test_ocr_enablement.py    19 passed    (was 18 passed, 1 failed)

### ⛔ THIS IS NOT A VERIFY WEAKENED TO MAKE IT PASS

The distinction is provable and was proved both ways:

* The **product code was not touched.** `tesseract.py`, `enablement.py` and `wiring.make_ocr` are
  unchanged. Their behaviour was right: binary absent → `None`; bindings absent → `None`.
* The **mutant that the old suite accepted, the new suite rejects.** Coverage went up by three
  tests over a path that had none.

What was removed was not strictness — it was a dependency on the host, which is the opposite of
strictness. The rule: *a verify that can only run on one machine is not a verify, it is a local
observation.*

---

## PART 4 · WHAT THIS DOES **NOT** FIX, AND MUST NOT BE READ AS FIXING

### ⛔ ALARM E-A1 — 872 `document_jobs` are still unreadable, and the receipt still FAILS

    [L1] attachments carry readable text      872      FAIL

The L1 receipt and this test shared a root cause but not a fix. The test was measuring the host;
the receipt is measuring the **deploy image**, and it is right to fail. `pytesseract` and `Pillow`
are still in no requirements file and the Tesseract binary is still absent from the image, so 872
scanned attachments park unread. **Nothing in this unit puts one word of text into one document.**

Whose: **Harsh** — the two Python packages in `requirements`, and the apt package in the image.
Both, together, in that order, or `tesseract_available()` keeps answering False and keeps being
right to.

The receipt is the honest surface for this and stays red until the deploy changes. The green test
now says something narrower and true: *when the stack is present the wiring builds an engine, and
when either half is missing it builds nothing.*
