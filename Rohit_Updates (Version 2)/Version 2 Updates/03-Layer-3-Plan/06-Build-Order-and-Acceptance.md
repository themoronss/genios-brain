# Layer 3 v2 — Build Order and Acceptance Gates

> Waves are prefixed **Y** (L1=W, L2=X). Gates are **J**. Same discipline: units first,
> a parent never before its children are green, a skip is not a pass.

---

## The six waves

| Wave | Builds | Depends on | Gate |
|---|---|---|---|
| **Y0** | Contracts: package extensions, `l3_activation` (doc 05) | — | J0 |
| **Y1** | **Typed consumers**: CLG-06 rule compiler, CLG-08 citations, CLG-07 play cap (doc 03) | Y0 | **J1** |
| **Y2** | **Admin corpus V1**: route the 21, author #13/#14, sharpen #6/#7, defer facilities/travel (doc 04 U1–U5) | — (corpus-only) | J2 |
| **Y3** | Compiler input changes: analytic predicates, pattern_id routing, stale-comment fix (doc 01) | Y0; full value after L2 X4/X6 | J3 |
| **Y4** | **Brain pipelines**: N-3 org discovery, N-4 behavior distillation (doc 02) + N-2/N-5 tooling (doc 04 U6–U7) | Y0; N-4 needs L2 X1–X4 | J4 |
| **Y5** | **Pilot activation**: `l3_activation` flip for one tenant, Admin domain | J1+J2 minimum | **J5** |

**Parallelism:** Y1, Y2 and Y4(N-3) are three independent tracks from day one. Y2 is
pure corpus work and can run entirely outside the engine.

**The one ordering that must not be violated: Y1 before Y5.** Flipping activation
without typed consumers produces the fake success the adapter's own docstring warns
about — *"activation would LOOK successful while producing generic output."*

### Cross-layer dependency picture

```
L1: W0..W10 ────────────────┐
L2: X0..X4 (analytic) ──────┼──> Y4 N-4 (behavior distillation reads L2.4)
L2: X6 (patterns) ──────────┼──> Y3 pattern_id routing (fallback works without it)
                            └──> Y5 pilot is meaningful even before L1/L2 finish:
                                 the compiler runs on TODAY's situations; each upstream
                                 wave landing enriches the same packages in place.
```

---

## Acceptance gates

### J0 — Contracts
```
pytest tests/contracts/test_l3_contracts.py tests/test_layer_topology.py -q
```
Old-shaped package still constructs; citation byte-identity validator enforced.

### J1 — Typed consumers (the weld)
```
pytest tests/reason/adapters -q
python scripts/weld_report.py --fixtures
```
| Metric | Gate |
|---|---|
| artifact classes with a typed consumer | **5/5** |
| blocking-rule fixture eliminates a candidate, named in `alternatives_rejected` | passes |
| UNKNOWN-predicate rule silently passing or blocking | **0** |
| citation statements byte-identical to authored text | 100% |
| play cap selection: situation-fit beats alphabetical | passes |
| LLM calls in the adapters | **0** |

### J2 — Admin corpus V1
```
python "Domain Expertise/_tools/validate.py" && python "Domain Expertise/_tools/index.py"
pytest tests/packs/test_admin_routing.py -q
```
`routed + deferred == 57`, every deferral reasoned; `opportunity_tracking` and
`goal_and_progress` authored, stamped, routed; deferred categories compile into **0** packages.

### J3 — Compiler inputs
```
pytest tests/packs/compiler -q
```
Byte-identical compile regression (Law 2) still passes; 5 new predicate kinds evaluable;
`UNKNOWABLE` never satisfies `absence`; stamped-vs-draft abstention test passes.

### J4 — Brains fed
```
pytest tests/packs/brains -q
python scripts/brain_content_report.py --org <pilot>
```
| Metric | Gate |
|---|---|
| Org entries (discovered + admin-confirmed) | **>= 3** |
| Behavior entries published through the L6 floors | **>= 1** |
| Adaptive lease from card feedback | **>= 1** |
| writes outside the L6 pipeline | **0** |
| `brain='expert'` write attempt | **DB error, asserted** |

### J5 — 🔴 Pilot activation — the layer's proof
```
python scripts/l3_pilot_report.py --org <pilot> --days 7
```
| Metric | Gate | Why |
|---|---|---|
| packages compiled for the pilot, Admin domain | > 0 | it runs |
| **a card carrying a heuristic/rule citation** | **>= 1** | *"do X because <expert pattern>"* — impossible today |
| **a candidate eliminated by a blocking corpus rule** | **>= 1** | authored doctrine finally binds |
| a package with non-empty Org/Behavior/Adaptive slices | >= 1 | the brains speak |
| abstention downgrades on stamped capabilities | ~0 | the stale-comment world is over |
| byte-identical recompile of any package | exact | Law 2 held under load |
| generic "review the situation" plays emitted | **0** | the fake-success detector |

**J5's citation row is Layer 3's G7/H5-equivalent** — the single measurement that says
the unlock actually reached a card.

---

## What must not regress

| # | Invariant | Where |
|---|---|---|
| 1 | Snapshot pinning — same (situation, snapshot) → byte-identical package | `brain_resolver.py` |
| 2 | **DB check: no `expert` in `learned_brain_entries`** | `migrations/0045:127` |
| 3 | Admission-hash invalidation on content change | `capability_resolver.py:123-131` |
| 4 | `knowledge_suggestions` stops at human review; `expert_brain_changed` always false | `feedback/publisher.py` |
| 5 | Three-state predicates — UNKNOWN never coerced | `context_adapter.py` |
| 6 | Weld receipts — every refusal named and counted | `reason/adapters/expertise.py` |
| 7 | Generated registry never hand-edited | `_tools/index.py` header |
| 8 | One active version per (org, brain, subject); no version noise | `learned_brain_entries` + publisher |
| 9 | L6 promotion floors (`min_observations`/`days`/`entities`) | `learning_policies`, `governance.py` |
| 10 | Package-churn suppression | `e1a0c47` |

---

## Activation & retirement of the global flag

1. Y5 flips `l3_activation(org, 'admin')` for **one** pilot.
2. The compiler's live pass reads `l3_activation`; `use_domain_compiler` becomes a
   read-only global kill switch for one release.
3. After J5 holds for 14 days on the pilot: delete the flag, and delete the stale
   comment block with it.
