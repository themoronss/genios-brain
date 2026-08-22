# Source and Commit Manifest

## Frozen branch state

| Role | Branch | Commit | Remote alignment at audit start |
|---|---|---|---|
| Code analysis source | `harsh/mvp` | `b739bd5ca682d09550acc400ed2892c38c8518f8` | `0 ahead / 0 behind` from `origin/harsh/mvp` |
| Documentation target | `rohit-yc-brain` | baseline `30cc800` | `0 ahead / 0 behind` before this build |
| Output root | `rohit-yc-brain` | uncommitted during build | `Rohit_Updates/Secret War Updates/` |

All current-code claims in this update refer to `harsh/mvp@b739bd5` unless a different commit is stated. Later commits can invalidate implementation counts; they do not retroactively alter this audit.

## Primary evidence

| Source | Claim class | Use in this update | Limitation |
|---|---|---|---|
| `/Users/rohitswerashi/MacBook Air Professional/My Repos/genios-brain` | [CODE] | Current implementation, tests, configuration, generated Sales registry | Checkout evidence does not prove deployed tenant state |
| `/Users/rohitswerashi/Blue Films/GeniOS-System-Design-Atlas.md` | [ATLAS] | Expected component ownership, boundary objects, LLM policy, failure behavior | `GeniOS-System-Design-Atlas.md` is specification, not implementation proof |
| `/Users/rohitswerashi/Downloads/genios-five-applications (1).html` | [MODELLED]/reference | Five operating shapes, card standard, confidence vector, privacy and integration pressure tests | Contains researched, modelled, and proposed material that must remain separated |
| Customer/founder expectation attachment `c9ff1fb4.../pasted-text.txt` | [CUSTOMER] | Executive-level intelligence, zero-overhead operation, trust, ROI and pilot metrics | First-person requirement evidence, not a verified market sample |
| Prior audit attachment `26cf87fc.../pasted-text.txt` | [INFERENCE] | Failure taxonomy and claims to re-check against current code | Earlier conclusions may be stale |
| Twelve supplied screenshots dated 2026-08-22 | [SCREENSHOT] | Visible generic cards, person aggregation, recap and stale-loop symptoms | UI state does not expose the entire upstream trace |

## Canonical repository references

| Area | Reference |
|---|---|
| Layer numbering | `docs/LAYER_MAP.md`, `genios_engine/LAYERS.py` |
| Layer 1 | `genios_engine/capture/`, `genios_engine/contracts/source_event.py` |
| Layer 2 | `genios_engine/context/`, especially `pipeline.py`, `situation_bso.py`, `domain_spec.py` |
| Layer 3 | `Domain Expertise/`, `genios_engine/packs/`, `reason/domain_shadow.py`, `reason/adapters/expertise.py` |
| Layer 4 | `genios_engine/reason/`, legacy `packs/sales_v1.py`, `packs/general_v1.py` |
| Layer 5 | `genios_engine/executive/`, `contracts/execution.py` |
| Layer 6 | `genios_engine/deliver/`, delivery and intelligence API routes |
| Layer 7 | `genios_engine/feedback/`, execution outcomes and feedback routes |
| Persistent contracts | `migrations/`, `genios_engine/contracts/` |
| Existing failure analysis | `Rohit_Updates/new-updates/`, `Rohit-Updates.md` |

## Commands executed before documentation

| Command | Result | Meaning |
|---|---|---|
| `git fetch --prune origin harsh/mvp rohit-yc-brain` | success | Remote refs refreshed |
| `git rev-list --left-right --count harsh/mvp...origin/harsh/mvp` | `0 0` | Source branch aligned at audit start |
| `git rev-list --left-right --count rohit-yc-brain...origin/rohit-yc-brain` | `0 0` | Target branch aligned before edits |
| `check-tree.sh` | `PASS: 72 units, 5 milestones, graph acyclic` | Build plan mechanically valid |
| `pytest -q` on target baseline | `9 failed, 1314 passed, 39 skipped` | Product baseline is red before documentation |

## Baseline failure ledger

| Cluster | Current proof | Documentation consequence |
|---|---|---|
| Corpus fireability | Six rules now reach the score gate but remain in `KNOWN_UNFIREABLE` | Generated/rule-health claims need fresh commands, not copied counts |
| Executive authority | Four tests require a latest graph-version authority predicate missing from current SQL | Executive “current truth” filtering is an active gap |
| Migration portability | Four SQLite tests receive PostgreSQL-style connection arguments | Full-suite green cannot be claimed |

These are not Secret War documentation regressions. They remain visible in the final scorecard and command manifest.

## Drift rules

- Generated Sales counts are always stamped with `b739bd5`.
- Validator warning totals are rerun before publication or labelled historical.
- Runtime claims require a replay, database, or delivery receipt.
- A test skip remains a skip.
- Public-company facts from the HTML remain “artifact-reported” unless their original source is separately verified.
- HKS remains the user’s literal label until its expansion is confirmed; the update will not invent one.


<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "01-Evidence-Authority-and-Claim-Classes.md" (M1.C1.L-contract.V0.U01)
include "02-Layer-Numbering-and-Semantic-Map.md" (M1.C1.L-contract.V1.U01)
-->
