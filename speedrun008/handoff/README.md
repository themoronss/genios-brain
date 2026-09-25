# Harsh — everything blocked on you, across Layer 1 and Layer 2

> # 👉 START AT [`../DO-THIS-NOW.md`](../DO-THIS-NOW.md)
> One file, the whole open list, in the order to do it, with the commands.
> Come back here for the reasoning behind any single item.


**Written 2026-09-25** · branch `speedrun008` · 27 steps complete, **13,122 tests passing**

---

## Read this first

Layers 1 and 2 are **code-complete**. Nothing below is waiting on engineering.

Every item is one of three things:

| | | count |
|---|---|---|
| 🗄 | **apply a migration** — two minutes each, idempotent, safe to re-run | 8 |
| 📊 | **run a read-only script and paste what it prints** | 6 |
| 🤔 | **make a decision** — the number is already measured and written down | 5 |

**Nothing here can break production.** Every script resolves its database through
`scripts/_db.py`, which has **no fallback to `Settings`** — *"nothing in the invocation names
production; you get it by running the script at all"* — and every statement in every one of them
is a `select`.

---

## ⛔ The two that matter more than the rest

### 1 · `fundraising` cannot reach doctrine that already exists

The pilot is a fundraising founder. `sales.sit.live_investor_relationship` and
`sales.sit.live_investor_contact` are **authored, stable and approved**, and behind them sits
`sales.investor_relations.investor_relations` — *"reading and running the relationships with the
people who might fund the company: funds, accelerators, angels."*

**One `None` in one table makes all of it unreachable.** Not a missing corpus — a missing line.

→ [`02-decisions.md`](02-decisions.md) · **D3**

### 2 · The shadow pass has been counting for months and nobody has read it

`shadow_compile` runs on every sweep, tallies, and reports to nobody. **The number that earns the
Layer 2 cutover exists today.** The gate that judges it was written *before* anyone looked, on
purpose.

→ [`01-measurements.md`](01-measurements.md) · **M6**

---

## The files

| | |
|---|---|
| [`00-migrations.md`](00-migrations.md) | 🗄 eight, in order, with what breaks if each is skipped |
| [`01-measurements.md`](01-measurements.md) | 📊 six scripts, each with the exact command and what to do with the output |
| [`02-decisions.md`](02-decisions.md) | 🤔 five, each with the measurement already done |
| [`03-access.md`](03-access.md) | 🔑 the scratch Postgres — **991 of 995 skipped tests are one environment variable** |

The older [`../HARSH-ORDER.md`](../HARSH-ORDER.md) is the long-form version with the full
reasoning behind each item. **These four files are the short version, to work from.**

---

## Suggested order

```
1. 🔑 03-access      the scratch Postgres            → unblocks 618 tests
2. 🗄 00-migrations   all eight, in number order      → ~16 minutes
3. 📊 01-measurements run all six, paste the output   → ~35 minutes
4. 🤔 02-decisions    now every one has its number
```

**Steps 1 and 2 are mechanical. Step 3 is where the product learns what it actually is.**
| [`04-layer-3.md`](04-layer-3.md) | ⛔ **Layer 3, steps 0A–06** — 1 migration (0184), 1 operator call (backfill window), 3 behaviour changes, and **four corrected premises** |

