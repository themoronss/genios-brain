# Known limitations — stated, not hidden

*Decisions and gaps in `correlation.py`, written down so they stay decisions rather than becoming
surprises.*

---

## §1 · Two deals at one company merge, with no CRM connected

**The behaviour.** Acme has two live opportunities — a renewal and a new-region expansion. With
no CRM connected, both correlate into **one situation**.

**Why.** The anchor is `(entity, domain)`. Both are Acme, both are sales, both are this quarter,
often the same people. Nothing deterministically available distinguishes them.

**Why not fix it by looking at the wording.** That is exactly the over-correlation this engine
refuses, run in reverse — guessing a split from prose is the same coin-flip as guessing a join.
The governing principle is:

> Wrongly **splitting** one situation costs a duplicate card. Wrongly **merging** two builds a
> chimera and reasons about it at full confidence.

Splitting on a guess would produce two half-evidenced situations that each look confident.

**When it goes away.** Connect a CRM. A deal node then anchors above the company
(`ANCHOR_PRIORITY = ('deal', 'project', 'company', 'person')`), and the two separate cleanly.

**Pinned by two tests**, so this stays a decision:

| Test | Asserts |
|---|---|
| `test_two_deals_at_one_company_separate_when_the_deals_are_known` | different base keys |
| `test_two_deals_at_one_company_merge_when_no_crm_is_connected` | the same base key |

---

## §2 · Internal-only situations do not correlate

**The behaviour.** *"Engineering release blocked"*, *"Hiring pipeline stalled"* — the spec's own
examples — produce no situation.

**Why.** Anchors are **counterparties**. Our own seats and our own company are stripped before
`choose_anchors` runs, because anchoring on ourselves would file every outbound email into one
enormous situation containing the whole business.

An internal-only conversation therefore anchors nothing.

**What would fix it.** A non-counterparty anchor that is not "us" — a project, a candidate, a
release. `project` **already works**: a Slack thread naming a project brief correlates under it
(see [Canon](../02-Graph-Engine/03-Canon.md)). Hiring and releases need entities nothing
currently produces.

**Honest under-correlation**, not a bug. An internal team email is not a customer situation, and
inventing one would be worse than the silence.

---

## §3 · Domain separation is coarse

**The behaviour.** L1 emits only `sales`, `support` and `admin`, and only on a keyword match or
a source prior (`capture/domain/hints.py`). Everything else lands in `general`.

Consequences:

| | |
|---|---|
| Most email has no keyword | most situations are `general` |
| Two unrelated `general` conversations with one company, no threads | **merge** |
| A fourth domain cannot be produced at all | nothing upstream emits one |

**Mitigated by threads.** Real conversations stay together through thread inheritance regardless
of domain, so the merge case needs *two separate threadless conversations* with the same company
in the same 45 days.

**Not fixed here.** Better domain assignment is Layer 1's job (richer hints) or Layer 3's (real
domain expertise). Layer 2 is already domain-agnostic — see
[Domain Specs](../05-Business-Situation-Engine/04-Domain-Specs.md).

---

## §4 · An undated event never correlates

```python
if event_at is None:
    return False        # joins_window
```

An event with no `occurred_at` cannot join an existing group, because letting it in would
silently stretch a situation's span to include a period nothing happened in.

It can still **open** a group (an empty group accepts its first event), which leaves that group
with a null span acting as a magnet until a dated event arrives and fixes the boundaries.

Rare in practice — connectors almost always supply a timestamp — but worth knowing when a
manual or agent event behaves oddly.

---

## §5 · Correlation is per-event and never revisits

Once an event is a member of a correlation, nothing re-evaluates that membership. If entity
resolution later proves two companies were one, the **merge** folds their correlations
(`merge.py:_merge_correlations`) — but no background pass re-correlates history in light of new
knowledge.

**Consequence.** Improving `domain_hints`, or connecting a CRM, does not retroactively re-split
existing situations. Only new events use the better information.

**Workaround.** Clear `context_correlation_members` for the org and re-run
[backfill](../02-Graph-Engine/05-Backfill.md). Destructive to situation history, and it discards
human resolutions — not a routine operation.

---

## §6 · The generation window is one global constant

`CORRELATION_WINDOW_DAYS = 45`, for every tenant, every domain, every entity.

A support case that goes quiet for six weeks is genuinely over. An enterprise deal that goes
quiet for six weeks during procurement is **not** — and its next email opens a second situation.

**Not yet configurable.** Making it per-domain is a small change (the domain is already on the
correlation row); it has not been done because nothing has yet demonstrated the right values, and
a tunable with no evidence behind it is a knob people turn at random.

---

## §7 · What this page is not

These are limitations of **correlation**. Two neighbouring gaps that are frequently confused with
them:

| Gap | Actually lives in |
|---|---|
| Cross-domain links, dependency chains | [The Eight Correlators §4](05-The-Eight-Correlators.md) — not built |
| Situations not consumed by Layer 4 | [Output §6](../Output-To-Layer-3-and-4.md) — an adoption gap, not a correlation one |

---

*Related: [Anchoring](01-Anchoring.md) · [Time Windows](02-Time-Windows-and-Generations.md) · [The Eight Correlators](05-The-Eight-Correlators.md)*
