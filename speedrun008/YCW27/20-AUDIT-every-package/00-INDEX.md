# 20 · THE AUDITING REPORT — every package, file by file

**Written for:** Rohit, and whoever picks this up after him. **Measured 2026-10-03.**

⛔ **GENERATED, NOT WRITTEN.** Every page in this folder is the output of one command, so it can be
re-run instead of re-read:

```
python scripts/context_coverage_report.py <package> > speedrun008/YCW27/20-AUDIT-every-package/<package>.md
```

`context/` lives at [`../layer-3-context-graph/05-AUDIT-context-file-by-file.md`](../layer-3-context-graph/05-AUDIT-context-file-by-file.md)
because its audit has a findings document beside it.

---

## The whole engine, on six numbers

| package | files | lines | writers | ⛔ tables, no receipt | declared silences | ⛔ no test names it |
|---|---:|---:|---:|---:|---:|---:|
| ⛔⛔ [`api`](api.md) | 44 | 19,498 | 20 | **28** | **2** | **11** |
| [`context`](../layer-3-context-graph/05-AUDIT-context-file-by-file.md) | 124 | 50,885 | 37 | 33 | 23 | 2 |
| ⛔ [`reason`](reason.md) | 121 | 41,363 | 21 | 29 | 14 | **14** |
| [`capture`](capture.md) | 158 | 47,184 | 25 | 19 | 7 | 1 |
| ⛔ [`platform`](platform.md) | 49 | 12,651 | 18 | 25 | 26 | 0 |
| [`contracts`](contracts.md) | 41 | 14,617 | **0** | 0 | 8 | 3 |
| [`deliver`](deliver.md) | 41 | 10,020 | 10 | 10 | 23 | 0 |
| [`packs`](packs.md) | 35 | 8,188 | 2 | 2 | 3 | 1 |
| [`executive`](executive.md) | 27 | 6,230 | 3 | 6 | 14 | 1 |
| [`feedback`](feedback.md) | 15 | 4,461 | 7 | 9 | 17 | 0 |
| [`mcp`](mcp.md) | 2 | 594 | 1 | 1 | 0 | 0 |

```
packages above   657 files · 215,691 lines   (the eleven package directories, summed)
whole engine     660 files · 215,992 lines   ⛔ measured directly — 3 more files, 301 more lines
receipts         42
tables           189 known to the migrations
```

⛔ **The two file counts disagree on purpose and both are right.** The per-package pages count what
is inside the eleven package directories; the engine total counts `genios_engine/` whole, which
also holds `LAYERS.py`, `main.py` and the other root modules — and counts a file once where a
package page may list it under a subdirectory. ⛔ **This block was wrong TWICE.** It first said `657 files · 215,591 lines` — the file count was
right and the line count was not. ⛔ Then the correction said `667 · 215,091`, and **the file count
I had just broken had been correct**. Both numbers are now computed by one script that prints the
package sum, the engine total and the difference between them, which is the only version that
cannot drift. *A total is a measurement — and a correction needs the same measurement the original
needed.*

---

## ⛔⛔ What the table says, and it is not what `S7` said

`S7` ranked packages by **lines per receipt** and the answer was `context/`. ⛔ **That ranking
could not see the worst case**, because a ratio with a **zero denominator** does not sort:

```
api        19,498 lines · ⛔ 0 receipts · 42 tables written · 28 with no receipt
platform   12,651 lines · ⛔ 1 receipt  · 29 tables written · 25 with no receipt
contracts  14,617 lines ·    0 receipts · ✅ 0 tables written   ← the control
```

⛔ **`api/` is the least-guarded package in the product on three columns at once** — most
unreceipted tables, fewest declared silences, and the most modules no test names. And it is the
layer a customer actually touches.

⛔ **`contracts/` is the control that makes the receipt column readable**: 14,617 lines, zero
receipts, and **zero tables written**. It holds no state, so its zero is correct rather than a gap.
A package's receipt count means nothing without the tables-written column beside it.

> ⛔ **Print the raw terms beside the ratio.** Third measurement artifact of this kind in two
> steps, after `[a-z_]+` swallowing `l2_convergence` and a pair-tuple turning `node_id` into a
> table.

---

## ⛔ Two columns that are easy to misread, and how to read them

**`tables, no receipt`** — the package writes the table and no receipt asks anything of it in
production. ⛔ It does **not** mean untested: `tests/` is large and green. It means *if this went
wrong on a tenant, nothing would notice.* The ranked list per package is in each page's second
section, busiest reader first, because the cost of a missing receipt scales with how many readers
trust the table.

**`no test names it`** — no test file imports the module by its dotted path. ⛔ It does **not** mean
untested either: a module reached only through a heavily-tested caller appears here, and so does one
whose functions a test calls under a different import form. ⛔ **When this ran for `context/`, BOTH
rows turned out to be live and reached.** Each row needs its callers checked before it is called a
gap — which is why `api`'s **11** and `reason`'s **14** are a reading list, not a defect list.

---

## ⛔ Two defects in this report, both found before it shipped

| | |
|---|---|
| **the declaration column read 0 for four packages** | It imported `genios_engine.<package>.<package>_health`, and the modules are named for what they describe, not their directory — `delivery_health`, `reasoning_health`, `pack_health`, and `executive/unreached.py`, which has no `health` in it at all. ⛔ So `deliver` showed **0** silences with **23** declared. *A name derived from a directory is a guess; a name found on disk is a measurement.* |
| **a context-specific paragraph in a reusable tool** | The `no test names it` caveat named `lifecycle/resolution.py` and `correlation_membership` — true for `context/`, a **lie** on the other ten pages. Replaced with the rule and the reason, which hold for every package |

⛔ Both are the same class as the findings this report exists to surface. *A report whose own
numbers are wrong is worse than no report*, because it is read as a measurement.

---

## How to use this

1. **Pick the package with the most unreceipted tables that a customer touches.** That is `api/`.
2. **Read its second section** — the ranked `table → external readers` list. The top row is the
   receipt that costs the most to be missing.
3. ⛔ **Derive the claim from the module's own words.** The `context/` audit produced receipt 42
   from `merge.py`'s own sentence, and deliberately did **not** produce one for `graph_nodes`,
   because that claim would have had to be invented. *A gate derived from an invented claim is a
   gate nobody reads.*
4. **Check every candidate finding against five traps** before writing it down — a reader in
   `scripts/`, a mention that is prose, SQL held in a module constant, a table name in a name
   constant, and that constant passed as a function argument. ⛔ **Six of the `context/` audit's
   own findings died to those five.**
