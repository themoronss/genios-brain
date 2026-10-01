# Step 9 — Claim directness

**Status:** NOT STARTED · **Effort:** days · **Depends on:** 4 · **Engine:** L proposes, D validates

## 1. Why this step exists

A CEO writing *"I heard Acme is leaving"* and a CEO writing *"Acme is leaving, I spoke to their
CFO"* are **indistinguishable** in Layer 1 today. Both score `actor_authority = HIGH`.

ALG-14 answers *who typed it*. Nothing answers *whether they witnessed it*. So hearsay from a
high-authority actor outranks a first-hand account from a lower-authority one — which is backwards,
and is exactly how a rumour becomes a card.

## 2. Current status
`validate/authority.py` ALG-14 — a 0..6 table over **artifact type** (signed contract > email >
chat aside) · `esqe/source_analyzer.py` — provenance and actor authority · **no directness field
anywhere** in `contracts/extraction.py`.

## 3. Expected result
A `claim_directness` axis: `firsthand` / `reported` / `speculative` / `unknown`, **default
`unknown`, never guessed**. ALG-13's Rule 11 clamp reads it: a reported claim may not compose above
a firsthand one.

## 4. Edge cases
E1 the model cannot tell → `unknown`, which is a real answer and must not be a guess · E2 a
forwarded message is structurally reported — the thread reconstructor already knows a forward
restarts the turn index · E3 directness is a **separate axis from artifact authority** and must
never be folded into ALG-14's table · E4 a first-hand claim from a low-authority actor should not
suddenly outrank everything — it is one input to Rule 11's clamp, not a new ranking · E5 old
extractions have no directness → `unknown`, which composes conservatively.

## 5. How to do it
| Unit | What |
|---|---|
| 9-U1 | `claim_directness` on the extraction contract, `unknown` default |
| 9-U2 | the extractor proposes it **with a span**; `validate/` resolves the span like any other claim |
| 9-U3 | ALG-13 reads it — **Rule 11's clamp already exists**; this adds one input |
| 9-U4 | ALG-14's table gains **no** new rank |

## 6. Test cases
T1 *"I heard X"* → `reported` (RED today: no field) · T2 a CEO's hearsay composes **below** the same
CEO's first-hand claim · T3 missing directness → `unknown`, composes conservatively · T4 ALG-14's
ranks are unchanged (**regression guard**) · T5 Rule 11's existing clamp still holds:
`corroborate(100, 9000) = 1882`, not 9002.

## 7. Verify
```bash
uv run --no-sync pytest tests/capture/validate/test_confidence.py tests/capture/validate/test_authority.py -q -p no:randomly
uv run --no-sync pytest tests/capture/semantic -q -p no:randomly
```

## 8. Done criteria
**Ticked 2026-09-24. All four closed — nothing open, and nothing for Harsh.**

- [x] **the field exists, defaults to `unknown`, and is never guessed** —
      `ConfidenceSource.directness`, default `Directness.UNKNOWN`. A quote with no marker reads
      `unknown` and never `firsthand`: most business prose states facts flatly, and reading that
      as witnessed would make the DEFAULT the strongest value, which is the one direction this
      axis may never fail in.
- [x] **T2 passes — hearsay ranks below first-hand** — driven end to end through the arithmetic
      the publisher runs, same author and same authority, differing only in the span's own words.
      Wired at BOTH `ConfidenceSource` call sites in the tree, asserted by count, because wiring
      one would discount hearsay on one route and not the other.
- [x] **ALG-14's table is untouched** — all seven ranks pinned exactly
      (`SIGNED_DOCUMENT 6 … INFERRED 0`). E3 holds: directness is a separate axis and is never
      folded into the authority ladder.
- [x] **Rule 11's measured clamp is unchanged** — `corroborate(100, 9000, INFERRED) = 1882`, and
      the whole ladder up to `SIGNED_DOCUMENT 4555` is now pinned rather than one point of it.

### 8.1 · The correction the existing suite forced

`UNKNOWN`'s multiplier was **9000** for half an hour, reading E5's *"composes conservatively"* as a
discount. **Eight tests in `test_confidence.py` went red** — every caller passes the default, so it
silently lowered every composition in the system by ten percent.

| | |
|---|---|
| **conservative** | does not INFLATE on no evidence → **10000** ✅ |
| **punitive** | DEDUCTS on no evidence → 9000 ❌ |

I had written that exact risk into my own docstring and built it anyway. The suite caught it in
under a minute, and `UNKNOWN = 10000` now carries the failure that produced it.

## 9. Must NOT do
Do not fold directness into the authority table. Do not default to `firsthand`. Do not let it become
a sixth weight in ALG-17 — the weights sum to 10000 and that check stays.
