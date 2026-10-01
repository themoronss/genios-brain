# L3-03 · `scoped_absence()` — findings

**Run:** 2026-09-25 · premise checked before any code · **no migration · no model call**

---

## 1. ⛔ The gate already existed, and it was stronger than the one I planned

The plan said *"build `scoped_absence()` — one pure function, six predicates, refusing by
default."*

**Four of the six were already enforced, and not at a call site — at the TYPE.**

`contracts/quality.py`:

> *"`licenses_negative_inference` is **COMPUTED and cannot be supplied**… `GENUINELY_ABSENT` is
> **unconstructible** without `coverage_ready=True` and a non-empty `coverage_basis`."*

`context/quality/missing.py` carries the five-way cascade — `PRESENT · STALE · NOT_EXPECTED ·
UNKNOWABLE · GENUINELY_ABSENT` — and says why it cannot be talked past:

> *"This module cannot talk itself past those rules, which is the point: **the argument for an
> exception is always persuasive at the call site and always wrong**."*

⛔ **A separate `scoped_absence()` would have been a second, weaker gate beside a stronger one.**
It was not built.

### 1.1 · The two ingredients that were missing are the two L3-02 measured

| spec ingredient | state before this step |
|---|---|
| a precise expected item | ✅ `Expectation` ＋ `expectations_from_spec` |
| the source it must appear in | ✅ `coverage_basis` |
| access to that source | ✅ `coverage_ready`, tri-state, `None` refuses |
| **complete enough indexing** | ⛔ **absent** |
| **a healthy watermark through the interval** | ⛔ **absent** |
| no qualifying match | ✅ the cascade |

---

## 2. ⛔ The hole, stated exactly

**`coverage_ready` is a fact about the TENANT. It is not a fact about the SWEEP.**

```
lens.ready_for(domain) is True    →  "a connected, fresh source COULD have carried this"
                                     ⛔ says nothing about how much of the window was read
```

So a tenant with Gmail connected and a sweep that read **37 of about 465** threads passed both
gates and reached `GENUINELY_ABSENT` — **a licensed negative inference over 8% of a mailbox.**

⛔ **That is the 23 Sept benchmark's failure surviving inside the module built to prevent it.** The
module's own docstring calls that outcome the worst thing the quality group can emit:

> *"`UNKNOWABLE` read as `GENUINELY_ABSENT`… a false negative inference about a customer delivered
> with a confident receipt."*

**Connected is not read, and only one of the two was a gate.**

---

## 3. What was built

`window_ok: bool | None` threaded through `classify_absence → missing_fact → classify_all →
detect_missing → refresh_typed_absences`, refusing **last**, after both existing gates.

| | |
|---|---|
| `True` | the sources covering this span exhausted their cursors **and** have a denominator |
| `False` | ⛔ downgrade to `UNKNOWABLE` — what not knowing spells |
| `None` | the caller did not ask · unchanged · **declared in `WINDOW_UNCHECKED`** |

### 3.1 · ⛔ Why `None` passes, when this module's own rule is that `None` is not `True`

**It is a different `None`.** `lens.ready_for` returns it about a **tenant** — a domain nobody
declared — and refusing there is correct. This one is about a **caller**.

Making it refuse would silently empty the Ownership surface — **which is built entirely on typed
absence** — for every caller not yet updated. **A safety improvement turned into an outage.**

### 3.2 · So the exemption is a LIST, not a default

`WINDOW_UNCHECKED`, guarded by `test_every_caller_either_asks_or_is_declared`, which reads the
source tree for calls into the cascade and fails on one that neither asks nor is declared.

⛔ **`window_ok=None` leaving behaviour unchanged is exactly how a gate comes to be reached by
nothing on a real path — the defect this project has caught six times. The seventh occurrence is
now a build failure.** Same idiom as `DARK_DOMAINS`, `SILENT_LANES`, `EMPTY_BY_DESIGN`.

### 3.3 · The order is the safety rule, and it is unchanged

The window gate is **last**. A perfect sweep over a domain with no coverage is still `UNKNOWABLE` —
if the check ran earlier, **a well-read window would launder a tenant that has no source at all**,
which is the more dangerous direction. `PRESENT` and `STALE` are never touched: coverage of a
window says nothing about a fact we already hold.

### 3.4 · Per subject, not per sweep — and one rule, not two

Each situation reasons over its own evidence span, so the answer differs between a situation whose
evidence starts in March and one whose starts yesterday. **A sweep-wide flag would give every
situation the first situation's answer** — L3-02b's memo-key mistake, one layer up.

And the gate is **the same function that produces the card's sentence**: `window_coverage_gaps(...)
== ()` means every source covering the span can bear the claim. ⛔ **Two rules would drift within a
month, and the drift would be invisible — a card saying "we only read part of this" beside an
absence asserted as fact.**

---

## 4. Result

```
FULL SUITE   13,186 passed · 1,061 skipped · 152 xfailed · 14 failed
                                                          └── all 14 pre-existing
before L3-03: 13,176 passed · 14 failed
```

**+10 tests · 0 regressions · no migration · no model call.**

**Technique 3 — five mutations, all red:** remove the gate; make `None` refuse (the outage
version); the producer stops asking; undated evidence guessed as OK; a real caller exempted with a
token reason.

## 5. What this step does NOT do

* **It does not build `scoped_absence()`.** A second gate beside a stronger one would be the
  scaffolding this plan exists to avoid. ⛔ **The plan's unit list was wrong and the finding is why.**
* **It does not change any existing caller's behaviour.** Only `refresh_situations` asks; every
  other path is `None` and unchanged, by declaration.
* ⛔ **It does not gate the CARD.** An absence that became `UNKNOWABLE` stops licensing a negative
  inference, and `licenses_negative_inference` is what `deliver/` must read. **Whether every
  renderer reads it is not claimed here.**
