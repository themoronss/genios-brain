# DO THIS NOW — the whole open list, in execution order

**Branch `speedrun008` · updated 2026-09-25 · Layers 1, 2 and 3 all closed in code.**

> **Harsh: work top to bottom. Do not skip and do not reorder — steps 2 and 3 have a hard ordering
> constraint and step 3 makes a real problem worse if step 2 has not landed.**
>
> Every other file in `speedrun008/` explains *why*. This one is *what*.

**Time: about 90 minutes of work, plus one overnight sweep before the measurements mean anything.**

---

# PART A — Harsh. Four things, in this order.

## ① Point the suite at a scratch Postgres · 5 minutes · ⛔ do this first

```bash
export GENIOS_TEST_DATABASE_URL="postgres://user:pass@host:5432/genios_scratch"
.venv/bin/python -m pytest -m pg -q
```

**Why first:** 991 of 995 skipped tests are this one variable. **A skip is not a pass.** Until this
exists, every step in three layers ends with *"verified hermetically, real-DB proof pending"*, and
Layer 1's adversarial suite cannot run at all. **This unblocks 618 tests.**

Any throwaway Postgres 15+ works.

> ## ⛔⛔ IT MUST NOT BE PRODUCTION. THE SUITE DROPS AND RECREATES THE SCHEMA.
>
> Production access is **read-only** and is only for the queries in Part B.

**Done when:** `pytest -m pg` runs and reports passes instead of skips.

---

## ② Apply the nine migrations · 20 minutes · ⛔ in number order

```bash
psql "$DATABASE_URL" -f migrations/0176_delivery_failure.sql
psql "$DATABASE_URL" -f migrations/0177_qualified_signals_subject_key.sql
psql "$DATABASE_URL" -f migrations/0178_sync_completeness.sql
psql "$DATABASE_URL" -f migrations/0179_signal_world_instants.sql
psql "$DATABASE_URL" -f migrations/0180_signal_coverage.sql
psql "$DATABASE_URL" -f migrations/0181_signal_conversation.sql
psql "$DATABASE_URL" -f migrations/0182_signal_situation.sql
psql "$DATABASE_URL" -f migrations/0183_situation_interpretations.sql
psql "$DATABASE_URL" -f migrations/0184_graph_recorded_at.sql
```

All idempotent (`if not exists`), all safe to re-run, ~2 minutes each.

⛔ **Order is not cosmetic.** `0177`, `0179`, `0180`, `0181`, `0182` are hard constraints — the
signal store already names those columns, so **every signal INSERT fails until they land.** `0178`
is worse than a crash: its writer is wrapped in a `try/except` that never raises, so syncs keep
working and simply stop being recorded.

**Full table of what each one does and what breaks without it:** [`handoff/00-migrations.md`](handoff/00-migrations.md)

**Done when:** all nine return without error. Nothing to verify by hand — `0184`'s new column is
nullable and old rows fall through `coalesce(recorded_at, valid_from)` to exactly today's behaviour.

---

## ③ Widen the pilot backfill window, 60 → 365 days · 10 minutes · ⛔ only after ②

**Why it matters:** five of the benchmark's eight waiting relationships sit outside 60 days. At the
current window the engine cannot see them at all, so no amount of reasoning finds them.

⛔ **`0184` MUST already be applied.** Widening the window backdates a year of edges into the as-of
history; `0184` is what stops that rewriting what we knew and when.

The operator call and its exact parameters: [`handoff/04-layer-3.md` §1.2](handoff/04-layer-3.md)
· full reasoning: [`HARSH-ORDER.md` item 21](HARSH-ORDER.md)

**Then `POST /backfill`, and let one full sweep run.**

**Done when:**
- the drain reports `moved=True`. ⛔ **`moved=False` after a first widened drain is a signal to
  investigate** — it means the rebuild ran and found nothing, which on freshly landed history
  should not happen.
- `TRUNCATED` is **not** a failure — the older tail remains, re-run `POST /backfill` to resume.

---

## ④ Run the six read-only measurements · 30 minutes · after one full sweep

Every query is in [`handoff/01-measurements.md`](handoff/01-measurements.md). **All read-only.**

| | what it answers | unblocks |
|---|---|---|
| **M1** | what Layer 2 refused, and why | decision **D2** |
| **M2** | what a context slice actually costs | decision **D4** |
| **M3** | what no authored corpus can read | decision **D3** |
| **M4** | what the founder actually sees | — (needs `0182`) |
| **M5** | relevance and domain-coverage | — |
| **M6** | the shadow pass's tallies | the Layer 2 cutover gate |

⛔ **Three more from Layer 3, same rules — read-only, one query each:**

- **`edge_type` audit** — [`handoff/04-layer-3.md` §4.5](handoff/04-layer-3.md). Any value outside
  the six closed types is a row written before the vocabulary closed.
- **the three-vocabulary audit** — §4.6. `edge_type`, `residue_kind`, `node_type` together.
- **`unclassified_licensed` ratio** — §5.1. Read it after a pilot sweep, not before.

**Done when:** the numbers are written into `handoff/01-measurements.md` beside each query.
**Decisions D2, D3 and D4 are blocked until then — do not guess them.**

---

# PART B — Rohit. Four decisions. Nobody else can make these.

> These are not engineering tasks. Each one changes what the product *claims*, not how it runs.

## ① ⛔ Who writes capabilities against the unused substrate? — **the biggest one**

The engine declares **141** substrate fields to capability authors. **70 are used by ZERO of your
1,425 capabilities.**

The sharpest case: the system computes *"we already told them this and they marked it wrong"*
(`derived.history.prior_card_verdict`) **on every sweep**, and offers it in the same list as
`derived.momentum` / `engagement` / `sentiment`, which authors use **83 / 191 / 154** times.

**It has been used zero times.**

⛔ **Nothing in the code is broken and no wiring change fixes this.** Roughly half of what the
engine produces is never asked for. **Someone has to author capabilities that use these fields.**

**Your call: who, and when.** Detail: [`plan/layer-3/step-14-the-corpus-does-not-ask.md`](plan/layer-3/step-14-the-corpus-does-not-ask.md)

## ② `freshness_half_life_days` is misnamed — A, B or C?

It is an **e-folding** constant, not a half-life (0.368 at 30 days, not 0.5).

**Recommendation: A now, B when packs are next versioned.** ⛔ **C is a silent global re-scoring of
every decision the product makes — do not take it as "a small maths fix."**

Three options with blast radius: [`handoff/04-layer-3.md` §1.3](handoff/04-layer-3.md)

## ③ The four Layer 2 decisions still open

| | question | needs |
|---|---|---|
| **D1** | flip the 24 authored situations stuck at `draft`? | — |
| **D2** | arm V-9 and V-10? | M1 |
| **D3** | point `fundraising` at the `sales` corpus? | M3 |
| **D4** | activate the Context Reasoner? | 0183 + M2 |
| **D5** | ⛔ pay for `last_inbound_at`? | **yours, and it is priced** |

All five: [`handoff/02-decisions.md`](handoff/02-decisions.md)

## ④ ✅ ALREADY DECIDED — 2026-09-25

**Should a pack-lane signal carry the situation sitting on its subject? → HOLD.**
Recorded in `reason/situation_binding.py`, [`handoff/04-layer-3.md` §1.4](handoff/04-layer-3.md)
and `plan/STATUS.md`. **Moves when `CardSource` gains a third value.** Nothing to do.

---

# PART C — later, and only after the comparison runs

## ⑤ Turn the card cutover on, one tenant at a time

`cards_from_situations` is now a registered Layer 4 feature. ⛔ **It was not one before** — the name
was a literal that `require_feature` **refused**, so no tenant could ever be switched on.

```python
from genios_engine.platform.l4_activation import activate, missing_cross_layer_preconditions

missing_cross_layer_preconditions(engine, org_id, "cards_from_situations")   # ⛔ CHECK FIRST
activate(engine, org_id, feature="cards_from_situations", by="harsh")
```

> ## ⛔ If that returns `("l3_domain",)`, DO NOT switch it on.
> Without a live L3 domain nothing writes `signals.situation_id`, so every card groups into the
> NULL bucket and reads **UNINTERPRETED** — while the console says `live`.

⛔ **`make_tenant_live` does not turn this on, deliberately.** It is a cutover, and switching it on
at provisioning would mean no tenant ever runs the comparison it exists for.

Detail: [`handoff/04-layer-3.md` §1.5](handoff/04-layer-3.md)

---

# ⛔ Three traps — read these before you touch anything

**1 · `signals.situation_id` is null on almost every row. DO NOT "fix" it.**
It looks like a three-line win. It was considered and **refused on 2026-09-25**: four of the five
signal writers never reason over the situation, so writing it would claim a provenance that does not
exist and would corrupt the very measurement that decides the cutover. `reason/situation_binding.py`
holds the reason and the build will stop you.

**2 · Never run the test suite against production.** It drops and recreates the schema.
`scripts/_db.py` requires `GENIOS_TARGET_DATABASE_URL` **plus** `GENIOS_ALLOW_PROD_WRITE=1` for any
Supabase host — that friction is deliberate, do not remove it.

**3 · Never suppress a `git stash` error.** A prior stash-pop corrupted five files. Recover with
`git stash show -p stash@{0}`, **never `pop`**.

---

# Where everything else lives

| | |
|---|---|
| ⛔ [`plan/layer-3/PENDING-layer-3-architecture-and-completion.md`](plan/layer-3/PENDING-layer-3-architecture-and-completion.md) | **Layer 3 end to end** — how it runs, how it integrates, Admin's measured state, every trap, and what is pending. **Read this before touching Layer 3 or the corpus.** |
| ⛔ [`plan/layer-4/`](plan/layer-4/) | **Layer 4 (Executive)** — it already runs on every tick. [`00-STATUS`](plan/layer-4/00-STATUS.md) the step table · [`01-WHAT-HARSH-DOES`](plan/layer-4/01-WHAT-HARSH-DOES.md) ⛔ **your list** · [`02-THE-REMAINING-STEPS`](plan/layer-4/02-THE-REMAINING-STEPS.md) the seven steps |
| [`handoff/`](handoff/) | the short form, sorted by kind of thing — **start here for detail** |
| [`HARSH-ORDER.md`](HARSH-ORDER.md) | the long form: same items, full reasoning behind each |
| [`plan/STATUS.md`](plan/STATUS.md) | every step in all three layers with its outcome |
| [`plan/layer-3/findings/`](plan/layer-3/findings/) | what each Layer 3 step measured, including the premises that turned out wrong |

**State of the tree right now:** `13,301 passed · 1,061 skipped · 14 pre-existing failures · 0 regressions.`
The 14 failures predate this branch and are unrelated; the 1,061 skips are mostly **item ①**.
