# L3-00 · The layer vocabulary — findings

**Run:** 2026-09-25 · premise checked before any code · **no migration · no model call**

---

## 1. ⛔ Premise check — the documentation half was almost free, and it found a live hole

The step was written as *"add a fourth column to `LAYERS.py` and `docs/LAYER_MAP.md`."* That part
is real and was done. But the premise check asked a second question — **what does this file
actually enforce?** — and the answer had a gap in it.

### 1.1 · `genios_engine/mcp/` was in neither `LAYERS` nor `CROSS_CUTTING`

```
on disk : api capture context contracts deliver executive feedback mcp packs platform reason
declared: api capture context contracts deliver executive feedback     packs platform reason
                                                            ⛔ mcp
```

### 1.2 · And an unmapped package escapes the ratchet in BOTH directions

```python
for pkg, layer in LAYERS.items():                 # ⛔ mcp is never a SOURCE — not in LAYERS
    for imported in _imports_of(py):
        if imported in CROSS_CUTTING or imported not in LAYERS:
            continue                              # ⛔ mcp is never a TARGET either
        if LAYERS[imported] > layer: FAIL
```

**So `capture` (1) could import `mcp`, which imports `feedback` (7), and the import ratchet — the
mechanism this repo relies on to keep domain knowledge out of the engine — would stay green on an
upward path laundered through a package nobody declared.**

### 1.3 · Nothing has gone through the hole yet

`mcp/` is **2 files**. It imports `platform` ×6, `reason` ×4, `deliver` ×2, `api` ×2, `executive`,
`contracts`, `context` — all downward — and only `main.py` imports it. **It behaves exactly like
`api/`: a transport surface.**

⛔ **But it behaves that way by accident, not by declaration.** It is now declared transport, and
the guard that was missing now fires when the next unmapped package appears.

### 1.4 · Honest scope of the fix

Declaring `mcp` cross-cutting **does not constrain `mcp`** — cross-cutting packages are exempt from
the direction rule, exactly as `api` is. **What the fix buys is the totality guard**: a future
package that appears unmapped can no longer be invisible to the ratchet.

---

## 2. ⛔ The blunt-grep mistake, made a fourth time and caught by its own probe

My first draft of the translation-table test was:

```python
assert f"`{pkg}/`" in doc          # ⛔ anywhere in the file
```

**Its mutation probe stayed green.** Removing `feedback/` from one of the document's two tables
still left it mentioned elsewhere, so the assertion passed on a document that no longer mapped it.

**This is the same mistake recorded at L1 step 14, L1 step 18 and L2-6** — an assertion about the
*text* of a thing rather than the *structure* the thing is trusted for. It now requires the package
to be **the first cell of a table row**, which is the only position that makes it a mapping, and
the probe that proves it includes the prose-only case the first draft allowed.

**Four times. The pattern is: when a guard greps, ask what it would accept.**

---

## 3. What was built

| | |
|---|---|
| **00-U1** | the product vocabulary as a fourth column in `LAYERS.py`'s docstring and `docs/LAYER_MAP.md` |
| **00-U2** | ⛔ `mcp` declared cross-cutting, with the reasoning in the comment |
| **00-U3** | ⛔ `ALL_DECLARED` ＋ `test_every_package_is_mapped` — the missing reverse guard |
| **00-U4** | `test_cross_cutting_and_layers_do_not_overlap` — a package cannot be both |
| **00-U5** | `test_the_translation_table_lists_exactly_the_layer_packages` — the doc cannot drift |

## 4. What is recorded, not fixed

**Two packages are not one-to-one with the product vocabulary, and that is a fact about the
packages rather than a defect:**

* `context` spans product **L2 and L3** — it assembles situations *and* holds the graph they are
  derived from.
* `reason` spans product **L2 and L4** — `domain_shadow` is expertise reasoning; `runner`,
  `composer` and `store` choose an action.

Their own docstrings say so **in the old numbering, in the same package.** `LAYERS.py` already
declares both to be **planes, not stages**, and the import rule is correct under every vocabulary.
⛔ **Recorded so nobody later reads a package boundary as a layer boundary.**

## 5. Result

```
FULL SUITE   13,135 passed · 1,061 skipped · 152 xfailed · 14 failed
                                                          └── all 14 pre-existing
before L3-00: 13,132 passed · 14 failed
```

**+3 tests · 0 regressions · no migration · no model call · `vocabulary_fingerprint` untouched.**

**Technique 3 — four mutations, all red:** un-declare `mcp`; declare a package as both layer and
cross-cutting; remove a package's row from the table; ⛔ **leave it in prose only** — the case the
first draft of the test wrongly allowed.
