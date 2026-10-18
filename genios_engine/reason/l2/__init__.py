"""GeniOS-008 Layer 2 — the LLM-led reasoning layer of the new architecture (`speedrun008/GeniOS-008/`).

L1 bundles in (`inputs`), a bounded snapshot (`snapshot`), comparable past work (`history`), the expertise and
the file (`reason/expert/dossier`, reused whole), the tools' arithmetic (`tools`), the depth (`plan`), ONE
judgment through R-9's gate (`judge`, `prompt`, `dossier`), the evidence loop (`evidence`), one write per sweep
(`store`), replay with no model (`replay`). `sweep.l2_pass` runs it, in SHADOW, from `reason/runner.run_all`.
"""
