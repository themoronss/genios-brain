# Analyzer, Calculator and Evaluator

## Analyzer / Calculator

Each accepted directive creates one source observation, one independent ref, explicit metadata and
10,000 bp confidence. This expresses authenticated explicitness, not learned permanence. Subject is
`memory:<pattern_key>` and the value is copied exactly from the frozen event.

## Evaluator

Preflight requires complete lineage/source refs, a valid audience, `metadata.explicit=true`, a
future expiry and a lease no longer than the tenant maximum (720 hours by default). This happens
before proposed value persistence. Valid Runtime context bypasses ordinary multi-observation
permanence gates, becomes `temporary` and is written to the lease store in the same governed
operation. It cannot wait in human review.

Runtime can never carry a permanent target and non-Runtime objects can never carry an expiry. The
owner policy API rejects Runtime as a review target, migration `0047` normalizes legacy rows before
freezing them, and the database constraint prevents direct reintroduction. The retention transaction
runs before weekly claims and even while new learning is disabled.
