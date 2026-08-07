# 1 · Decision Interpreter

**Status:** Built

Turns an authoritative Layer 4 decision into an execution-shaped context, or refuses it with a typed reason before operational work exists.

| Boundary | Value |
|---|---|
| Input | Layer 4 decision, capability/play metadata, organization identity and an explicit observation time |
| Output | `Interpretation` containing an immutable `ExecutionContext`, or a named `RefusalCode` |
| Primary code | `genios_engine/executive/interpret.py` |
| Invariant | Classification and extraction are deterministic; a read-only or human-gated instruction cannot silently become autonomous external action. |
| Honest gap | No Atlas-core gap. Natural-language invention is intentionally excluded. |

## Atlas-named component map

| Atlas component | Live implementation |
|---|---|
| Decision Parser | decision/play field validation and `classify_execution` in `interpret.py` |
| Goal Extractor | goal/objective projection into `ExecutionContext` |
| Dependency Extractor | declared play dependency extraction; detailed DAG normalization occurs in Planning |
| Priority Extractor | authoritative priority/band metadata projection |
| Deadline Extractor | declared deadline/window projection with explicit time |
| Metadata Loader | tenant, subject, capability/play lineage and confidence metadata |
| Execution Context | immutable successful output consumed by Execution Planning |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, planning and calculation](02-Analysis-Planning-and-Calculation.md)
3. [Evaluation, build, execution and output](03-Evaluation-Build-Execution-and-Output.md)

The files group adjacent Atlas pipeline boxes; they do not claim nonexistent runtime services.
