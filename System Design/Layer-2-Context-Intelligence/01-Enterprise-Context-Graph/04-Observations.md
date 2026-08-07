# Observations — evidence-backed statements, not alerts

*`graph_observations` · `context/vocabulary.py` · `pipeline.py:norm_obs_kind`*

> A **fact** says what a value *is*: `deal.stage = "negotiation"`.
> An **observation** says what *happened*: `objection_price` — someone pushed back on price.
>
> Facts have a current value that changes. Observations accumulate; they are moments, and
> moments do not get superseded.

---

## §1 · What it is for

Observations are the substrate for **sentiment and momentum**. Layer 3's rules ask questions
like *"has a competitor been mentioned in a live deal?"* — that is not a field with a value, it
is an event that happened at a time.

Critically, an observation is **not an alert**. It is an L3 input. Nothing about writing
`churn_risk` causes anything to fire; a pack rule reads it, weighs it with everything else, and
decides.

---

## §2 · What exists

```sql
create table graph_observations (
    observation_id  text primary key,
    org_id          text not null,
    subject_node_id text,
    kind            text not null,          -- the canonical vocabulary, §3
    occurred_at     timestamptz,
    confidence      numeric(4,3) not null default 0.5,
    status          text not null default 'active',
    created_by_event_id text,
    pack_id         text,                   -- set when a pack wrote it, not L2
    pack_version    text,
    created_at      timestamptz not null default now()
);
create index observations_by_subject on graph_observations (org_id, subject_node_id);
```

No `valid_to`. Observations are **append-only** — a price objection in March is still a thing
that happened in March, even after the customer signs in June.

`confidence` here is the model's `relevance`, unlike facts where confidence is derived from
authority rank. An observation is inherently a reading of tone; there is no system of record for
"they seemed hesitant".

---

## §3 · The vocabulary is owned by Layer 2

`context/vocabulary.py` — and the docstring explains why it moved here:

> *It used to live in `reason/signals_derived` — which forced context to either import upward or
> duplicate the sets.*

Layer 2 emits these kinds, so Layer 2 owns them; Layer 4 imports **downward**.

### Positive — 11 kinds

`budget_approved` · `buying_intent` · `pricing_discussed` · `positive_reply` ·
`champion_engaged` · `next_step_agreed` · `verbal_yes` · `contract_requested` ·
`demo_requested` · `stakeholder_added` · `security_review_started`

### Negative — 17 kinds

`objection` · `objection_price` · `objection_timing` · `objection_security` ·
`objection_authority` · `objection_integration` · `competitor` · `going_dark` ·
`churn_risk` · `negative_reply` · `price_pushback` · `stakeholder_left` ·
`discount_pressure` · `budget_freeze` · `champion_change` · `timeline_slip` ·
`closed_lost_mention`

**Negative outnumbers positive**, and that is not an accident: most of what is worth noticing in
a business conversation is something going wrong, and the failure modes are more varied than the
successes.

Kinds outside both sets (`question`, `mention:person`, `note`) are stored and queryable but do
not contribute to polarity.

---

## §4 · Normalisation — where a mood becomes a rule

The LLM emits free-form kinds. Pack rules match **exact strings**. `_OBS_CANON` in
`pipeline.py` maps synonyms to canonical form **at commit time**:

```python
"budget_confirmed" → "budget_approved"
"has_budget"       → "budget_approved"
"verbal_commitment"→ "verbal_yes"
"agreed_to_proceed"→ "next_step_agreed"
"send_contract"    → "contract_requested"
"security_questionnaire" → "security_review_started"
```

```python
def norm_obs_kind(kind) -> str:
    k = str(kind or "note").strip().lower().replace(" ", "_").replace("-", "_")
    return _OBS_CANON.get(k, k)      # unknown kinds pass through, never dropped
```

**Why at commit and not at read.** Normalising here makes the deep sales corpus fire
deterministically instead of by LLM lottery, and it works identically on a fresh event and on a
cache replay. Doing it at read time would mean every consumer re-implements the mapping.

**Unknown kinds pass through unchanged.** They are stored under their own name rather than
discarded — a kind nobody has canonicalised yet is data, not noise.

---

## §5 · How they are written

Three sources, one table.

| Written by | Subject | Kind |
|---|---|---|
| `pipeline.py` extraction | `content_subject` — the sender, or the **canon node** for company knowledge | from `ex.observations`, normalised |
| `pipeline.py` mention loop | the sender | `mention:person` / `mention:company` / `mention:entity` |
| `pipeline.py` questions | the sender | `question` |
| a pack (L3) | any node | its own; stamped with `pack_id` + `pack_version` |

### Duplicate hygiene

```python
seen_obs: set[tuple[str, str]] = set()      # (kind, evidence_text)
```

One email quoting the same moment twice must not commit it twice — duplicates double-count in
derived sentiment, which feeds attention's `polarity` term.

### Anchorless mentions land here

The **P1 anchor rule**: an entity mentioned without a resolvable anchor does **not** become a
node. It becomes a `mention:<type>` observation on the sender, and its name maps to the sender so
any fact about it still attaches somewhere anchored.

That is what killed the orphan `SAP` / `OpenClaw` / `Product` / `System` dots — without losing a
single extracted fact.

---

## §6 · Who reads them

| Reader | Uses |
|---|---|
| `context/attention.py` | `polarity` — negatives vs positives in the last 90 days; `question` in the last 14 |
| `reason/signals_derived.py` | the sentiment inputs to pack rules |
| `reason/intelligence.py` | evidence surfaced on a card |
| `context/projections.py` | *not directly* — but observations created by a situation's events reach its lens |

Five files under `reason/` and `executive/` read this table.

---

## §7 · Worked example

> *"Thanks — pricing looks high honestly, and we're also talking to Competitor X. Can you send
> the security questionnaire?"*

| Kind emitted | After `norm_obs_kind` | Polarity |
|---|---|---|
| `price_pushback` | `price_pushback` | negative |
| `competitor_mention` | **`competitor`** | negative |
| `security_questionnaire` | **`security_review_started`** | positive |

Two negatives, one positive, all within 90 days → attention's `polarity` term contributes **10**
(trouble leads).

Note the third row: a security questionnaire is a *buying* signal, not a complaint, and the
synonym map is what stops it being stored as some uncounted string.

---

## §8 · Edge cases

| Case | Behaviour |
|---|---|
| Noise email (newsletter/automated/spam) | observations **still written** — facts are kept, only the network graph is skipped |
| `subject_node_id` null | possible for a noise sender with no node; the observation is orphaned and counted by health |
| Same kind, different quote, same email | both stored — two moments, not a duplicate |
| Kind not in either polarity set | stored, queryable, contributes nothing to sentiment |
| Subject node merged | repointed via `merge.py:_NODE_REFERENCES` |

---

*Related: [Facts](02-Facts.md) · [Evidence](05-Evidence.md) · [Attention](../04-Context-Quality-Engine/05-Attention.md)*
