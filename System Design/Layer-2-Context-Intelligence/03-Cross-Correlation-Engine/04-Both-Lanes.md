# Both lanes must correlate

*`context/pipeline.py` · `context/structured.py` · `correlation.py:lift_people_to_their_companies`*

> The headline case is four systems reporting one reality. **Correlation originally ran in only
> one of the two lanes** — so the CRM deal and the calendar invite never joined anything, and
> two of those four arrows silently did not exist.
>
> The engine looked like it was working. Half its inputs were missing.

---

## §1 · The two lanes

Layer 1 hands events to Layer 2, which routes each one deterministically:

| | Extraction lane | Structured lane |
|---|---|---|
| Entry point | `pipeline.py:process_event` | `structured.py:commit_structured` |
| Chosen when | no mapping in `capture/structured/registry.py` | a mapping exists for `(source, object_type)` |
| Carries | email, Slack, uploads, written knowledge | CRM deals, calendar events, subscriptions, client DB rows |
| LLM | one combined call | none |
| Authority | R2, or R4 for canon | R3 system-of-record |

Both call `correlate_event` **inside the same transaction as their graph writes** — because a
situation must never reference nodes that rolled back.

```python
# pipeline.py — extraction lane
correlations = [] if is_noise else correlate_event(
    conn, org_id=org_id, event_id=event_id, occurred_at=occurred_at,
    thread_id=thread_id,
    node_types={n: t for n, t in touched.items() if n not in internal_nodes},
    domain_hints=domain_hints)

# structured.py — structured lane
correlations = correlate_event(
    conn, org_id=org_id, event_id=event_id, occurred_at=occurred_at,
    thread_id=None, node_types=touched, domain_hints=domain_hints)
```

---

## §2 · What each lane contributes to `node_types`

### Extraction lane

Built during processing, in `touched`:

| Source | Node type |
|---|---|
| the sender | `person` |
| recipients (≤10) | `person` |
| `_works_at` company | `company` |
| a resolved company mention | `company` |
| a resolved canon mention | its real type (`project`, …) |
| a canon document being written | its kind |

### Structured lane

| Source | Node type |
|---|---|
| the event's own object | `deal`, `meeting`, `subscription`, `product_account` |
| mapped relations | `person` (deal contacts, meeting attendees) |

Note the asymmetry: the structured lane's **own node** is often the anchor (a deal), while the
extraction lane's own subject (the sender) is usually *not* — a meeting is evidence *within* a
situation, not a situation.

---

## §3 · Our own people are stripped, in both lanes

```python
# extraction lane
{n: t for n, t in touched.items() if n not in internal_nodes}

# structured lane
if rel["node_type"] == "person" and key in internal:
    continue
```

Anchors are **counterparties**. Two ways our own side leaks in, and both are removed:

| Leak | Where |
|---|---|
| Every **outbound** email passes through our own domain, so `_works_at` creates *our* company node | extraction |
| Every **calendar invite** lists us as attendees | structured |

Without this, anchoring on ourselves would file the entire company into **one enormous situation
containing everything.** `internal_emails` comes from `org_seats`, queried once per drain.

---

## §4 · The lane-crossing bug — one person, two anchors

Even with both lanes correlating, the same human anchored **differently** depending on which
lane saw them:

| Lane | What it builds for `john@acme.io` | Anchor |
|---|---|---|
| Extraction | person node **plus** a company node from the email domain | **Acme** (company beats person) |
| Structured | a bare attendee person node — no `works_at` edge | **John** (person) |

An email and a meeting about **one deal** would therefore live in two situations that never meet
— exactly the "four systems, one reality" failure, one level deeper.

### The fix: lift people to their companies

```python
def lift_people_to_their_companies(conn, *, org_id, node_types):
    """... c.canonical_key = split_part(p.canonical_key, '@', 2) ..."""
```

Before planning, every `person` in the anchor pool is checked for a company node matching their
email domain. If one exists, the company joins the pool and wins by priority.

**Read-only by design.** If no company node exists yet, the person stays the anchor — correlation
merges reality, it does not invent entities in order to merge them.

Runs inside `correlate_event`, so **both lanes get it** without either knowing about it.

---

## §5 · Noise is excluded — from the extraction lane only

```python
correlations = [] if is_noise else correlate_event(...)
```

A newsletter naming one of your contacts must not become evidence in their live deal.

The mention loop still creates the node and every fact is still committed — **only the grouping
is skipped**, matching how noise already gets no network edges.

The structured lane has no equivalent: a CRM row or a calendar event is never "noise".

---

## §6 · Worked example — the headline case, end to end

Acme, one week, four systems:

| Day | Event | Lane | `node_types` after lifting | Result |
|---|---|---|---|---|
| Mon | Slack: *"need pricing approval"* | extraction | `{acme.io: company}` | opens correlation `acme.io / sales / gen 1` |
| Tue | Email from john@acme.io | extraction | `{john: person, acme.io: company}` | joins — company anchor |
| Wed | Calendar: *Pricing Review*, john attending | **structured** | `{meeting, john: person}` → **lifted to `{…, acme.io: company}`** | joins |
| Thu | HubSpot deal updated | **structured** | `{deal_88: deal, john: person}` | **deal outranks company** → its own correlation |

Rows 1–3 are one situation with three sources — `evidence` confidence 100 (3 events × 8 = 24
volume, 3 sources × 25 = 60 capped at 60... 24 + 60 = 84).

Row 4 correctly separates: a known deal is more specific than the company, and that is the
mechanism that resolves the
[two-deals-one-company limitation](06-Known-Limitations.md#1--two-deals-at-one-company-merge-with-no-crm-connected).

---

## §7 · Verified by

| Test | Prevents |
|---|---|
| `test_the_structured_lane_correlates_too` | the original bug — deals and meetings outside every situation |
| `test_the_structured_lane_correlates_before_committing` | a situation referencing rolled-back nodes |
| `test_our_own_attendees_never_anchor_a_meeting` | every meeting in one company-wide group |
| `test_our_own_company_never_anchors_a_situation` | every outbound email in one group |
| `test_a_person_is_lifted_to_their_company_before_anchoring` | the lane-crossing split |
| `test_lifting_never_creates_the_company_it_looks_for` | correlation inventing entities |
| `test_a_newsletter_never_joins_a_customers_situation` | marketing blasts as deal evidence |

---

*Related: [Anchoring](01-Anchoring.md) · [Input from Layer 1 §4](../Input-From-Layer-1.md) · [Known Limitations](06-Known-Limitations.md)*
