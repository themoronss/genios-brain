# §7 real cases — how to run the go/no-go experiment

This is GATE 0 (the one experiment that unblocks everything). It proves whether
GeniOS decides as well as / better than a raw LLM on **real** sales decisions,
and measures how often the cheap symbolic pass answers without the LLM (80/20).

## 1. Build the dataset (founder)

Copy the template and fill **15–20 real** cases:

```
cp real_cases.template.jsonl real_cases.jsonl
```

Each line = one real deal's facts + the conclusion a **real salesperson actually
reached** (`human_label`). Source order, best first:

1. a design partner's CRM
2. your own real deals (CrewAI / n8n / Vapi stacks)
3. 20 realistic scenarios labeled by an actual B2B salesperson

**Do not** use the synthetic `labeled_cases.jsonl` — those are circular (the rules
were written to them). Use `human_label: ""` when the right answer is "no action".

## 2. Pre-register the pass thresholds (before running — in writing)

Commit the numbers now so there are no moving goalposts. Example (set your own):

- symbolic resolves **≥ N/20** without the LLM  *(directly tests 80/20 — if N≈4, the thesis is in trouble)*
- GeniOS agrees with the human label on **≥ X/20**
- GeniOS accuracy **≥** raw Sonnet accuracy
- derivation chain present on every fired case *(explainability — Sonnet has none)*

## 3. Run

```bash
# free pre-check: validates the file + prints the symbolic-resolution rate
python -m tools.section7_harness --preflight --cases modules/sales/golden/real_cases.jsonl

# full 3-way experiment — needs ANTHROPIC_API_KEY + DATABASE_URL
python -m tools.section7_harness \
    --cases modules/sales/golden/real_cases.jsonl \
    --org-id genios-eval --out section7_results.json
```

The harness reports numbers only (per-case table + aggregates). It does **not**
pass/fail — you score the output against your pre-registered thresholds.
