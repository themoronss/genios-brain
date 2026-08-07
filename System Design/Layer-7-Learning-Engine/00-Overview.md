[Folder map](README.md) · [System Design index](../README.md)

---

# Layer 7 — The Learning Engine (`feedback/`)

> The layer that closes the loop — and the one that is deliberately the most **conservative** in
> the engine.

Every other layer produces intelligence. Layer 7 asks whether it was any good, and adjusts. But
it may only adjust in one direction, through one door, once a week, within a bounded range, and
never by importing anything above it.

**401 lines. It is the smallest layer, and its restraint is the design.**

---

## §0 · At a glance

| | |
|---|---|
| **Package** | `genios_engine/feedback/` |
| **Layer number** | 7 |
| **Size** | 2 files · 401 lines |
| **Input** | canonical human judgments on cards (Layer 6) |
| **Output** | `rule_mutes` rows + `lvl3_config.scoring_defaults.rule_offsets` (Layer 3 data) |
| **May import** | everything below. **Nothing imports it** |
| **Writes upward?** | **Never.** It writes **down, as data** |
| **LLM calls** | Zero |
| **Cadence** | **once per UTC week**, per pack, per org — claimed atomically |
| **Migration** | `0012_l6_feedback.sql`, `0034_l4_learning_authority.sql` |

---

---

## §1 · What was supposed to be built

From the layer map:

> **`feedback/` — Layer 7 — Learning Engine.** Precision windows, nudges, mutes, MACV. **Writes
> learned state DOWN as data** (`rule_mutes`, `lvl3_config`) — **never imported upward.**

Which implies four requirements:

| # | Requirement | Why it is non-negotiable |
|---|---|---|
| 1 | **Learn from labels, not from silence** | an ignored card is not a rejected card |
| 2 | **Bounded, reversible adjustments** | a learner that can move a threshold arbitrarily is a second reasoning engine |
| 3 | **One write path, respecting pins** | *the calibrator gets no private door* |
| 4 | **Exactly one run per period, atomically** | a double-run would double-step every nudge |

---

---

## §2 · What exists

```mermaid
flowchart LR
    subgraph IN ["Signals it reads"]
        A["card impressions<br/>*observability only*"]
        B["canonical human judgments<br/>run_play · do_it_myself · wrong:*"]
    end
    subgraph CALC ["feedback/calibrate.py"]
        C["precision_28d<br/>Wilson interval per rule"]
        D["run_calibration<br/>weekly, atomic, claimed"]
    end
    subgraph OUT ["What it writes — DOWN, as data"]
        E["rule_mutes<br/>*stop firing this rule*"]
        F["lvl3_config.rule_offsets<br/>*±5, bounded ±15*"]
        G["calibration_nudges<br/>*the audit ledger*"]
        H["calibration_runs<br/>*the claim + the result*"]
    end
    A --> C
    B --> C
    C --> D
    D --> E
    D --> F
    D --> G
    D --> H
    F -.->|"read by the L3 merge"| L3["Layer 3 effective config"]
    E -.->|"read by the L4 runner"| L4["Layer 4"]
```

**Nothing in Layer 7 imports Layer 3 or Layer 4.** The loop closes through *tables*.

---

---

## §4 · The workflows

### W1 · One weekly calibration

```mermaid
sequenceDiagram
    participant H as maintenance sweep (weekly)
    participant C as run_calibration
    participant TP as tenant_packs
    participant CR as calibration_runs
    participant J as canonical judgments (28d)
    participant RM as rule_mutes
    participant NL as calibration_nudges

    H->>C: per org, per active pack
    C->>TP: SELECT ... FOR UPDATE
    C->>CR: claim (org, pack, version, week)
    alt already claimed
        CR-->>C: prior result → already_ran
    end
    C->>J: precision per rule, Wilson bounds
    Note over C: impressions counted but NOT labelled<br/>timing complaints excluded
    C->>C: drop rules not in the current manifest
    C->>C: HOLD rules with ambiguous lineage
    loop each scored rule
        alt ub < 0.25 and judgments ≥ 12
            C->>RM: mute
        else lb ≥ 0.25 and muted
            C->>RM: recover
        end
        alt eligible and not muted and not pinned
            C->>C: lb ≥ 0.70 → offset −5   (loosen)
            C->>C: ub < 0.40 → offset +5   (tighten)
        end
    end
    C->>TP: guarded UPDATE lvl3_config + authority_revision++
    C->>C: expire open signals/cards for newly muted rules
    C->>NL: one row per change, with its statistics
    C->>CR: completed + result
```

### W2 · How a nudge reaches a decision

```mermaid
flowchart LR
    A["Layer 7 writes<br/>lvl3_config.rule_offsets[champion_quiet] = +5"] --> B["tenant_packs row"]
    B --> C["**Layer 3 merge**<br/>LVL1 → LVL2 → LVL3<br/>then pins, then guardrails"]
    C --> D["effective config<br/>+ NEW snapshot_id"]
    D --> E["**Layer 4** runs with it"]
    E --> F["every signal stamps<br/>the new config_snapshot_id"]
    F --> G["the change is<br/>attributable, forever"]
```

**No import. No call. A table.**

---

---

## §5 · Strategies

### S1 · Silence is not a label

Impressions are observability. Only an explicit human judgment moves anything.

### S2 · Separate "wrong about the world" from "wrong moment"

`bad_timing` and `snooze` are excluded from precision. **A delivery problem must never mute a
correct rule.**

### S3 · Always compare against the harder bound

Mute on the **upper** bound, recover on the **lower** bound, loosen on the **lower**, tighten on
the **upper**. Small samples cannot act.

### S4 · Harder to silence than to tune

`MUTE_MIN_JUDGMENTS` (12) > `MIN_JUDGMENTS` (8), *because a mute stops the rule producing the
judgments that would let it recover.*

### S5 · Bounded and slow

±5 per week, ±15 total. **Learning may nudge; it may never redefine.**

### S6 · Never pool across lineages

Outcomes belong to the exact pack version that produced them. Ambiguity → **hold**, and report it.

### S7 · One transaction, one week, one claim

Serialised on the tenant-pack row, claimed on `(org, pack, version, week)`, guarded on
`authority_revision`.

### S8 · A mute takes effect immediately

Open signals and queued cards for a newly muted rule are expired in the same commit.

### S9 · Write down, never up

The only outputs are rows. Nothing in `feedback/` is imported by anything.

---

---

## §7 · The map

### 7.1 Files

| Concern | File |
|---|---|
| Everything | `feedback/calibrate.py` |
| The judgment CTEs it builds on | `reason/authority.py` (`AUDITED_CARD_JUDGMENTS_CTES`) |
| The write path it uses | `packs/registry.py` (`write_lvl3_offset`) — *and its own guarded UPDATE* |
| Where its output is consumed | `packs/merge.py` (LVL3), `reason/runner.py` (`rule_mutes`) |

### 7.2 Tables

`rule_mutes` · `calibration_runs` · `calibration_nudges` · `tenant_packs.lvl3_config` ·
`tenant_packs.authority_revision`

### 7.3 Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /feedback/calibrate` | force a pass |
| `GET /feedback/precision` | the 28-day precision table with Wilson bounds |
| `GET /v1/expertise/learned` | the nudges + auto-mutes this tenant has accrued |

### 7.4 Where it runs

Inside `run_maintenance_sweep`, **weekly**, per active pack per org — after distribution, before
graph maintenance. Every failure is caught per org: *one org's failure ≠ the rest.*

### 7.5 Scorecard against §1

| Required | Status |
|---|---|
| Learn from labels, not silence | ✅ impressions are diagnostics only |
| Bounded, reversible adjustments | ✅ ±5/week, ±15 total, mutes recover |
| One write path, respecting pins | ✅ pin checked in Python **and** in SQL |
| Exactly one run per period, atomically | ✅ row lock + claim + revision guard, one transaction |
| Statistically honest | ✅ Wilson bounds, harder-bound comparisons |
| Never imported upward | ✅ the loop closes through tables |
| **Learns whether acting on it *worked*** | ❌ **`execution_outcomes` unread** |
