"""The gate — deterministic only (no per-item LLM in L1).

S0 scope → S1 hard rules + whitelist → S1.5 structured short-circuit → route.
Every stage records its decision (pass/drop/park/short_circuit) with a reason code
into the event trace, so you can see exactly what filtered where and why.
"""
