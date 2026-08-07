# The eight correlators — spec versus code

*An honest mapping. Three exist, three are emergent, two are not built.*

> The Atlas lists eight named correlators as separate components. The code has **one engine**
> with a small set of deterministic rules. Some of the spec's eight fall out of those rules for
> free; some genuinely do not exist.
>
> This page says which is which, so nobody plans work on a component that was never written.

---

## §1 · The mapping

| # | Spec correlator | Status | Where it lives |
|---|---|---|---|
| 1 | **Cross Tool** | ✅ **built** | the anchor key — one entity + domain groups events from every source |
| 2 | **Cross Timeline** | ✅ **built** | `joins_window` / `merged_span` — generations |
| 3 | **Cross Conversation** | ✅ **built** | thread inheritance (`thread_correlations`) |
| 4 | **Cross User** | 🟡 **emergent** | two people on one anchor land in one group, but nothing *reports* the overlap |
| 5 | **Cross Resource** | 🟡 **emergent** | a document's facts join its situation via the member-event join; no doc-level dedup |
| 6 | **Cross Organization** | 🟡 **emergent** | one counterparty across contexts unifies via entity resolution, not correlation |
| 7 | **Cross Domain** | ❌ **not built** | domain *separates* situations by design; nothing links a sales event to its legal consequence |
| 8 | **Dependency** | ❌ **not built** | no blocked-by relationship exists in the graph |

---

## §2 · The three that are built

### 1 · Cross Tool — the headline case

The reason the engine exists. Anchoring on `(entity, domain)` rather than on a source means
Slack, email, calendar and CRM all reach the same group without any pairwise comparison.

```
Slack   "need pricing approval"   ─┐
Email   "customer is waiting"     ─┤ anchor = (acme.io, sales)
Calendar "Pricing Review tmrw"    ─┤ ─────────────────────────→  ONE situation
CRM     deal = Enterprise         ─┘                              4 pieces of evidence
```

Cost is O(1) per event: compute a key, look it up. A pairwise correlator would be O(n²) rows
and O(n²) comparisons, which is why the spec's framing as eight independent scanners would not
have survived real volume.

**Verified by:** `test_correlation.py::test_the_structured_lane_correlates_too` — a real bug
once meant CRM and calendar never correlated at all, so two of those four arrows silently did
not exist.

### 2 · Cross Timeline — generations

`joins_window` tests an event against a group's **span**, not its latest event:

```python
(group_first - 45d) <= event_at <= (group_last + 45d)
```

Outside that, a new **generation** opens: the renewal lost in March is not the renewal being
worked in September, and both stay findable.

Span rather than latest is deliberate — a connector recovering from an outage delivers old
events after new ones, and measuring from the latest would fork one situation in two.

### 3 · Cross Conversation — thread inheritance

`parent_object_id` (the provider's thread id) is a **hard join**. An event sharing a thread with
already-correlated events joins those correlations whatever its own anchor says.

Without it, a bare *"sounds good, thanks"* — no company named, no keyword, nothing anchored —
becomes its own island, and correlation looks like it is working while doing nothing.

Thread is checked **first**; the anchor key is consulted only when the thread is silent.

---

## §3 · The three that are emergent

Real behaviour, but a consequence of other rules rather than a component. Nobody should look
for a file called `cross_user.py`.

**4 · Cross User.** Two reps emailing the same buyer both produce events anchored on that
buyer's company, so both land in one situation. What is *missing* is the report: nothing says
*"two people are working this independently."* That is a detection, and detection is Layer 4.

**5 · Cross Resource.** A proposal's facts reach its situation through the member-event join in
`projections.py:_REACHED` and `situations.py`. But there is no document-identity engine: the
same PDF arriving from Drive and from an email attachment is two objects, and nothing notices.

**6 · Cross Organization.** An investor who is also a customer's board member unifies because
**entity resolution** gave them one node — see [Entity Resolution](../02-Graph-Engine/01-Entity-Resolution.md).
Correlation then follows for free. The credit belongs to `identity.py`, not here.

---

## §4 · The two that are not built

Stated plainly so they can be planned rather than assumed.

### 7 · Cross Domain — *not built, and partly deliberate*

Domain is part of the anchor key. Acme's renewal and Acme's outage are **deliberately** two
situations — filing them together would be exactly the over-correlation this engine refuses.

But the spec means something else: *a sales event with legal or finance consequences.* A deal
closing that needs an unapproved discount is one business reality spanning two domains.

Nothing links them today. Two honest reasons:

1. **It is a judgement.** "This sales event has a legal consequence" requires knowing what
   legal consequences look like — domain expertise, Layer 3.
2. **The vocabulary is not there.** L1 only ever emits `sales`, `support` and `admin`
   (`capture/domain/hints.py`). There is no `legal` domain to cross *to*.

**What it would need:** a `related_situations` link, populated by a Layer 4 detector, not by
this engine.

### 8 · Dependency — *not built*

*"A is blocked on B, and B is silent."* There is no `blocked_by` edge type, no dependency
resolution, and no way to express it.

The nearest thing is `commitment.due_at` — a single obligation with a date. That is not a
dependency graph.

**What it would need:** a new edge type, a source that produces it (Jira/Linear connectors are
declared but `buildable=False`), and cycle detection. It is a real gap, not a rename.

---

## §5 · Why one engine instead of eight

| | Eight scanners | One keyed engine |
|---|---|---|
| Cost per event | eight passes, several pairwise | one key, one lookup |
| Determinism | eight independently tunable heuristics | one rule set, replayable |
| Failure mode | one scanner over-merges; hard to attribute | one place to look |
| Adding a source | consider all eight | none — anchoring is source-agnostic |

The engine's governing principle is why the collapse is safe:

> **Under-correlate rather than over-correlate.** Wrongly splitting one situation costs a
> duplicate card. Wrongly merging two builds a chimera and reasons about it at full confidence.

Eight independent scanners each looking for a reason to join things is a design that fails in
the expensive direction.

---

## §6 · How to check this page is still true

```bash
# built: the three rules
grep -n "thread_correlations\|joins_window\|choose_anchors" genios_engine/context/correlation.py

# not built: these should return nothing
grep -rn "blocked_by\|cross_domain\|related_situations" --include='*.py' genios_engine/context/
```

If the second command starts returning results, this page is out of date — fix it in the same
change.

---

*Related: [Anchoring](01-Anchoring.md) · [Time Windows](02-Time-Windows-and-Generations.md) · [Thread Continuity](03-Thread-Continuity.md) · [Known Limitations](06-Known-Limitations.md)*
