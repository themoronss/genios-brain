# The new architecture, mapped onto the code that exists

**Written:** 2026-09-24, against `speedrun008` at commit `c98e9eff`
**Purpose:** before planning Layer 2, establish what the new names actually cost.

---

## 1. The new architecture as stated

```
L1  Enterprise Signals
L2  Signals Qualification      (Signals + Domain Expertise = Reasoning)  →  Business Situation
L3  Context Graph              (holds the Business Situation)            →  Decision Object
L4  Executive Layer
L5  Delivery Layer
L6  Learning Layer

Layer D  Domain Expertise      — same as before, renamed
Layer R  Reasoning Engine      — same as before, renamed
```

---

## 2. ⛔ The renumbering costs NOTHING, and the code already said so

`genios_engine/LAYERS.py`, unprompted, in its own docstring:

> *"Package names carry semantics, never digits: **the numbers have already changed twice across
> specs while the code did not**, so no digit ever appears in a package name."*

**This is the third renumbering, and the file was built for it.** Not one module, import or test
changes because of the new numbers.

| package | today | NEW name | cost |
|---|---|---|---|
| `capture` | 1 · Enterprise Sources | **L1 Enterprise Signals** | docstring |
| `context` | 2 · Context Intelligence | **splits — §3** | ⛔ real work |
| `packs` | 3 · Domain Expertise | **Layer D** | docstring |
| `reason` | 4 · Reasoning Engine | **Layer R** | docstring |
| `executive` | 5 · Executive Engine | **L4 Executive** | docstring |
| `deliver` | 6 · Distribution | **L5 Delivery** | docstring |
| `feedback` | 7 · Learning Engine | **L6 Learning** | docstring |

Two files carry the numbers: `LAYERS.py` and `docs/LAYER_MAP.md`. That is the whole rename.

### 2.1 · D and R becoming LETTERS is the meaningful part

Numbers imply a pipeline position. **D and R are not stages — they are what L2 reasons *with*.**
Letters say that, and the old numbering actively misled: `packs`=3 and `reason`=4 read as *"after
context"*, when in the new reading they are *"alongside, feeding L2"*.

---

## 3. The one real structural change — `context` splits in two

| New | What it owns | Output |
|---|---|---|
| **L2 Signals Qualification** | L1 signals + Layer D expertise, reasoned by Layer R | **Business Situation** |
| **L3 Context Graph** | holds Business Situations and their detail | **Decision Object** → L4 |

Today both live inside `context/`, which holds **10 situation producers** *and* `graph_store.py`,
the correlators and the entity graph. The split is a real boundary, not a rename.

---

## 4. ⛔ THE FINDING: Layer 2 already exists, and it is running in SHADOW

`reason/domain_shadow.py` does **exactly** what the new L2 describes — L1 signals + Layer D
expertise, reasoned, into a package. It is **wired into the live sweep** at
`reason/runner.py:1451`, gated per tenant on `l1_seam_enabled`.

**And `live=False` is the default for every existing caller.** It compiles the package and drops it
on the floor. Its own docstring:

> *"Until this existed the corpus was 152 authored capabilities that could not produce a single
> card: the compile ran (behind a flag that is off), published nothing, and reasoned in SHADOW."*

**So Layer 2's job is not to build it. It is to turn it on and prove it is right.** That is a very
different plan from the one a blank page would produce.

### 4.1 · Cutover flips three things together, and one alone is useless

From `shadow_compile`'s contract:

1. **a real publisher** — otherwise `expertise_packages` is never written;
2. **`require_admission=True`** — only capabilities a named reviewer accepted may carry authority.
   Measurement mode deliberately relaxes this; live must not;
3. **`ExecutionMode.LIVE` + an emitted `signals` row** — otherwise delivery cannot build a card,
   and the card cannot say which brain authored it.

---

## 5. ⛔ The import inversion that ISN'T one

The new diagram has **L2 consuming D and R**. Today `packs`(3) and `reason`(4) sit **above**
`context`(2) and read *from* it — and `tests/test_layer_topology.py` enforces that a package may
import same-or-lower only.

**Read naively, the new architecture inverts an enforced rule.** It does not, and the reason
matters for every later decision:

* **the orchestration lives in `reason`**, the higher package, pulling from `context` and `packs`.
  Verified: `grep` shows `context` imports neither, and `domain_shadow` imports both.
* so the **data** flows exactly as the new diagram says — signals + expertise → reasoning →
  situation — while the **imports** stay legal.

**`tests/test_layer_topology.py` does not change.** "Layer 2" in the new architecture is a
**pipeline stage composed of three packages**, not a Python package. Trying to make one package
called L2 that imports `packs` would break the topology test for no gain.

---

## 6. What already exists, with its real name

| New concept | Exists as | State |
|---|---|---|
| **Business Situation** | `contracts/domain_expertise.BusinessSituationObject` | ✅ **live** — producer + 5 `packs` consumers |
| Business Situation **v2** | `contracts/situation.BusinessSituationObject` (*"D-01 v2"*) | ⚠️ **one importer** — §6.2 |
| **Decision Object** | `contracts/reasoning.DecisionCandidate` | to confirm against L4's intake |
| L2 → L3 boundary builder | `context/situation_bso.py` | ✅ live |
| the qualification pass | `reason/domain_shadow.shadow_compile` | ⚠️ **shadow only** |
| Layer D corpus | `packs/` + the tenant's DB | ⚠️ **size is a DB question — §6.1** |

### 6.1 · How big is the Layer D corpus? Nobody can say from the code

`packs/` holds four hand-written rule/play packs (`admin_v1`, `sales_v1`, `support_v1`,
`general_v1`) and five capability modules. **The authored capability catalog is not in the
repository** — the compiler reads it plus the tenant's active `learned_brain_entries`.

Two different numbers are in circulation and **neither can be checked without a database**:

* `domain_shadow`'s docstring says **152** authored capabilities;
* the working note carried into this session says **211** Admin capabilities.

They may both be right at different dates, or one may be stale. **It matters**, because it is the
denominator of every coverage claim Layer 2 will make — and "how much of the corpus did we route"
is exactly the `18 threads of 18` mistake Layer 1 spent three steps learning to refuse.

**→ a measurement, and it needs Harsh item 1.**

### 6.2 · Two `BusinessSituationObject`s, and they were never reconciled

* `domain_expertise.py:405` — a **dataclass**, imported by the producer, `reasoning.py` and **five**
  `packs/compiler` modules. **This is the live one.**
* `situation.py:551` — a **frozen Pydantic model** calling itself *"D-01 v2 · Layer 2's complete,
  immutable output to Layer 3"*, reached only through `context/situation_publisher` ←
  `reason/domain_shadow`.

Both docstrings claim to be *"Layer 2's complete, immutable output"*. **They cannot both be.**
`upgrade_situation`, the function that would migrate v1 → v2, has **zero callers.**

Given the new architecture names Business Situation as L2's product, **deciding which of these two
IS it is the first contract question of Layer 2** — not a cleanup.

---

## 7. Parked work that must be dealt with first

`stash@{0}` — *"outbound-is-evidence + meeting situations (parked before YC-W27 switch)"*, six
finished L2 units, on branch `rohit/outbound-is-evidence`.

⛔ **Recover by inspection, never by `git stash pop`.** A previous pop corrupted five files. The
safe read is `git stash show -p stash@{0}`, then apply deliberately.

---

## 8. What this map does NOT settle

* **where the L2/L3 line falls inside `context/`** — 10 situation producers on one side, the graph
  and correlators on the other, and several modules read both;
* **whether `DecisionCandidate` is the Decision Object** the new L3 should emit, or whether L4
  expects something else today;
* **what Layer 6 (Learning) consumes** under the new numbering — `feedback/` imports `context` in
  **zero** files today, which is worth a second look;
* **the cutover gate** — what parity the shadow pass must show before `live=True`. That is a
  measurement, and measurements in this project have needed the corpus.
