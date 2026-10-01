# Evidence · step 3 · five days with no model

Source: `llm_costs`, read-only, 2026-09-30, all orgs.

## Last success anywhere in the product

```
2026-09-25 11:09:30.774661+00   l4_llm_decision   claude-haiku-4-5-20251001
```

## Failures carrying "usage limits", by day

| Day | Count | First at |
|---|---|---|
| 2026-09-16 | 1,339 | 09:59:14 |
| 2026-09-17 | 640 | 00:12:53 |
| *18–24 Sep* | *clean — it recovered on its own* | |
| 2026-09-25 | 256 | 11:09:30 |
| 2026-09-26 | 2,062 | 08:11:44 |
| 2026-09-27 | 1,836 | 00:12:45 |
| 2026-09-28 | 2,993 | 00:12:55 |
| 2026-09-29 | 3,152 | 00:02:11 |
| 2026-09-30 | 1,240 | 00:00:00 |

**Two separate occurrences. Neither alerted.**

## By purpose, last 6 days

| Purpose | ok | failed |
|---|---|---|
| `l4_llm_decision` | 385 | 1,758 |
| `l4_llm_r1` | 273 | 1,677 |
| `l1_relevance` | 91 | 384 |
| `relevance_gate` | 88 | 308 |
| `moment.screen_insight` | 11 | 48 |
| `l1_extract` | **0** | 11 |
| `screen_memory_batch` | 90 | 0 |

`l1_extract` at zero is the extraction call — nothing was being extracted from any message.

## Error text, verbatim

```
Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error',
  'message': 'You have reached your specified API usage limits. ...'}}
```

## Is it a retry loop? — no

29 September, failures only:

| Purpose | Calls | Distinct subjects | Calls per subject |
|---|---|---|---|
| `l4_llm_decision` | 1,319 | 178 | 7.4 |
| `l4_llm_r1` | 1,213 | 165 | 7.4 |

Busiest single subject: `node:node_209421bb35fe4140b2`, **24 attempts, 00:40:58 → 21:12:19** —
about one an hour. A periodic sweep meeting a closed door, not a runaway loop.

⛔ **This contradicts the baseline's claim that the heartbeat does not run in production.**
Something fired hourly across 21 hours. Either a second scheduler drives the decision lane, or the
heartbeat runs and only some drains are wired. Unresolved.
