← [api/ — the transport surface](03-API-and-The-Heartbeat.md) · [Folder map](README.md) · → [Gaps and the Map](05-Gaps.md)

---

# The Topology Ratchet

---

## §6 · The topology ratchet

`tests/test_layer_topology.py` reads `genios_engine/LAYERS.py` and walks every import in the
package.

```mermaid
flowchart TB
    L1["1 capture"] --> L2["2 context"] --> L3["3 packs"] --> L4["4 reason"] --> L5["5 executive"] --> D52["5.2 deliver"] --> LEARN6["6 feedback"]
    LEARN6 -. "**data only** — rule_mutes · lvl3_config" .-> L3
    X1["contracts/"] -.->|"may import"| X2["platform/"]
    X3["api/"] -.->|"may import anything"| LEARN6
```

**Rules:**

1. A package may import **same-or-lower import ranks** only.
2. `contracts/` may import **only `platform`** and stdlib.
3. `platform/` and `api/` may import anything.
4. Anything else is **a build failure, not a review nit.**

> It is the mechanism that keeps **domain knowledge out of the engine** and **context out of
> expertise.**

Three places in this codebase exist *because* of that rule, and each is better for it:

| Situation | Resolution |
|---|---|
| Layer 5 must send a message, but may not import Layer 5.2 | Layer 5 **writes its decision down**; `deliver/executive_bridge.py` reads it. **The send has one owner, not two** |
| Layer 6 Learning must retune Layer 3/4 | it writes **rows**; the merge reads them. *The consumer stays free to change its mind about what it wants to learn* |
| Layer 5.2 Delivery must know who owns a commitment | it **delegates downward** to `executive/assignment.py` |

---
