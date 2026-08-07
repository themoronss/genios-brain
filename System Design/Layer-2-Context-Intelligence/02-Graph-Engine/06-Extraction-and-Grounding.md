# Extraction and grounding — the only LLM call in Layer 2

*`context/extract/extractor.py` · `context/extract/prompt.py` · `context/llm/client.py` ·
`context/llm/parse.py` · `context/guard.py`*

> **One model call per unstructured event.** Everything before it is routing; everything after
> it is arithmetic. That single boundary is why a rebuild produces byte-identical results.

---

## §1 · What it is for

An email is prose. The graph stores typed, evidenced, authority-ranked rows. Something has to
cross that gap, and only a language model can.

The design question was never *whether* to use one — it was **how much to let it decide.** The
answer, enforced structurally:

| The model MAY | The model MAY NOT |
|---|---|
| read prose and propose candidates | write to the graph |
| quote the text that supports a candidate | assign confidence |
| score its own interest (`relevance`) | gate anything |
| guess a domain | resolve identity |

Its output is **candidates**, not rows. B4 validates the evidence, B5 resolves identity, B7
commits. Three deterministic stages stand between the model and the graph.

---

## §2 · One combined call, not five

```python
def extract(llm, *, source, content) -> Extraction
```

Returns **eight things from one request**:

| Field | Becomes |
|---|---|
| `relevance` | the fact's `relevance` column — may rank, never gate |
| `noise_type` | `none` \| `newsletter` \| `automated` \| `personal` \| `spam` |
| `domains` | *(captured, but correlation uses L1's deterministic hints instead)* |
| `entity_mentions` | person/company nodes, or `mention:*` observations |
| `fact_candidates` | `graph_facts` rows at R2 |
| `commitments` | `commitment.due_at` facts |
| `questions` | `question` observations |
| `observations` | the canonical signal-kind vocabulary |

**Why one call and not five specialised ones.** Five calls cost five times as much, take five
times as long, and — worse — can disagree with each other. A single pass over the text produces
one coherent reading, and the extraction cache has one key instead of five.

Content is truncated to **8,000 characters** (`build_prompt`). Longer documents arrive already
chunked by Layer 1.

---

## §3 · Determinism, and what is left to chance

```python
resp = client.messages.create(model=..., max_tokens=4096, temperature=0, ...)
```

**`temperature=0`.** Not a preference — a requirement. The extraction cache is keyed on
`hash(org_id + PROMPT_VERSION + content)`, and a cache is only sound if identical input yields
identical output.

### One repair retry

```python
res = llm.call(prompt)
if not res.ok:
    res = llm.call(prompt)      # temp-0 wobble / truncation
```

Exactly one. Not a loop — a second identical failure is a real failure, and retrying forever
against a broken model burns a tenant's budget silently.

### Errors are returned, never raised

```python
except Exception as e:
    return LLMResult(parsed={}, raw="", ok=False, error=str(e)[:400], ...)
```

A network blip must not take down a drain that is mid-batch. The runner converts a failure into
a retry count and, after `_MAX_ATTEMPTS = 3`, parks the event as `model_unavailable`.

---

## §4 · Lenient JSON parsing

`llm/parse.py` — two defences against a model that is 99% right.

| Function | Handles |
|---|---|
| `strip_code_fence` | ```` ```json ```` wrappers the prompt asked it not to emit |
| `parse_json_lenient` | truncation — a response cut off at `max_tokens` mid-object |

Haiku truncates. Strict `json.loads` would throw away a response that contained eight valid
facts and one unterminated string.

Unparseable output is not a crash — it is `ok=False, error="unparseable JSON"`, and the raw text
is kept for debugging.

---

## §5 · The B4 grounding guard — the anti-hallucination gate

`context/guard.py:keep_grounded` is the most important twelve lines in the extraction path.

A candidate survives **only if its `evidence_text` is a genuine substring of the source.**

```python
ents  = keep_grounded(content, ex.entity_mentions)
facts = keep_grounded(content, ex.fact_candidates)
obs   = keep_grounded(content, ex.observations)
```

### Dropped, not down-weighted

A candidate that fails grounding is **discarded**. It is not stored at low confidence.

> A hallucinated claim with a bad score is still in the graph, and something downstream will
> eventually surface it. A hallucinated claim that was never written cannot.

### This is why R2 is worth 0.85

We are not trusting that the model was *right*. We are checking that the source actually **said
the words**. What remains uncertain is only the interpretation — which is why an
evidence-backed extraction sits just below a system of record (0.90) rather than far below it.

See [Facts §3](../01-Enterprise-Context-Graph/02-Facts.md).

---

## §6 · `PROMPT_VERSION` — the cache invalidation lever

```python
PROMPT_VERSION = "b3-2"     # pipeline.py:72
```

Part of the cache key. Bumping it means:

- **new events** extract against the new prompt immediately, at no extra cost
- **the existing backlog** keeps its old extractions until somebody deliberately re-extracts

That asymmetry is deliberate. A prompt change must never silently re-charge a tenant for
re-processing a year of history.

The current value's history is itself instructive: `b3-2` added the canonical **signal kinds**
vocabulary to the prompt, which made the sales corpus fire deterministically instead of by
whatever wording the model happened to choose.

---

## §7 · The prompt's own defences

`extract/prompt.py:B3_PROMPT` does three things beyond asking for JSON.

**It demands evidence per item.** Every candidate shape has an `evidence_text` field. Without
that requirement B4 would have nothing to check, and the whole grounding guarantee collapses.

**It enumerates the signal kinds.** Observations must use exact strings from a listed
vocabulary, with the instruction: *"emit only when the message clearly states it; omit if
unsure — a wrong signal is worse than none."*

**It asks for a relevance judgement openly.** Rather than pretending the model has no opinion,
the prompt asks for one and the pipeline then confines it to a column that may only rank.

Synonyms that slip through anyway are normalised at commit by `_OBS_CANON` — see
[Observations §4](../01-Enterprise-Context-Graph/04-Observations.md).

---

## §8 · Cost accounting

Every call records its tokens:

```python
store.record_cost(org_id=..., model=llm.model, purpose="extract",
                  input_tokens=ex.input_tokens, output_tokens=ex.output_tokens,
                  success=ex.ok, error=ex.error, event_id=event_id)
```

Written to `llm_costs`, per org, **including failures** — a tenant whose events keep failing is
still consuming budget, and hiding that would make the bill unexplainable.

This is the only place in Layer 2 that spends money. Correlation, situations, identity, health
and projections are free.

---

## §9 · Worked example

Input, after Layer 1's PII masking:

> *"Thanks — pricing looks high honestly. Can you send the security questionnaire? I'll get you
> a decision by Friday."*

| Model output | After B4 | Committed as |
|---|---|---|
| `relevance: 0.8` | — | the fact's `relevance` column |
| obs `price_pushback`, evidence *"pricing looks high"* | ✅ substring | observation, negative polarity |
| obs `security_questionnaire`, evidence *"send the security questionnaire"* | ✅ | normalised → `security_review_started` |
| commitment *"decision by Friday"* | ✅ | `commitment.due_at` fact, R2, conf 0.85 |
| fact `budget = "approved"`, evidence *"they have budget"* | ❌ **not in the text** | **dropped** |

That last row is the guard doing its job on a plausible-sounding invention.

---

## §10 · What has no LLM at all

| Stage | |
|---|---|
| Structured lane | fields are already typed |
| Identity resolution | exact match only |
| Correlation | deterministic anchors and windows |
| Situations, confidence, lifecycle | arithmetic and date comparisons |
| Health, projections | SQL |

If the model is unavailable, the structured lane keeps working and the whole graph-maintenance
machinery keeps working. Only unstructured extraction stops — and those events stay pending
rather than being lost.

---

*Related: [Facts](../01-Enterprise-Context-Graph/02-Facts.md) · [Evidence](../01-Enterprise-Context-Graph/05-Evidence.md) · [Observations](../01-Enterprise-Context-Graph/04-Observations.md) · [Input from Layer 1](../Input-From-Layer-1.md)*
