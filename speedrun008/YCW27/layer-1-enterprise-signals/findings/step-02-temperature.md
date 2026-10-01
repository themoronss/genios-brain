# Evidence · step 2 · `temperature` refused

Source: `llm_costs`, read-only, 2026-09-30.

```sql
select purpose, count(*) filter (where success) ok,
       count(*) filter (where not success) bad
  from llm_costs where model like 'claude-sonnet-5%' group by 1;
```

```
  l4_bundle    ok=0    failed=600
```

```sql
select purpose, count(*) n, min(created_at), max(created_at)
  from llm_costs
 where model like 'claude-sonnet-5%' and not success and error like '%temperature%'
 group by 1;
```

```
  l4_bundle    n=600    2026-09-13 13:03  ->  2026-09-25 10:46
```

Error text, verbatim:

```
Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error',
  'message': '`temperature` is deprecated for this model.'}, 'request_id': ...}
```

**Zero successes across twelve days on the only purpose that uses this model.** The narrator has
never produced a bundle.

## The call site

`context/llm/client.py` hardcoded `temperature=0` on every `messages.create`.

`reason/llm_decision_maker.py` already held `_NO_SAMPLING_PREFIXES` listing exactly these models,
and avoided the problem by constructing **its own thin client** — so decisions worked and every
other lane on the shared client did not.
