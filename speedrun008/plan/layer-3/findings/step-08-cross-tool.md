# L3-08 · Cross Tool — findings

**Run:** 2026-09-25 · premise checked before any code · **no migration · no model call**

---

## 1. ⛔ The premise was wrong for the sixth time — and this one was the plan's #4 priority

The plan said, in four documents:

> *"⛔ **Cross Tool is the only correlator with no module — and the only one whose inputs both
> exist today.** Gmail ↔ Calendar is the entire two-connector pilot. It owns CT-01…CT-12 alone."*

**There is no `correlation_tool.py` because the join does not need one.** It happens one layer down,
in identity:

```python
# context/pipeline.py:1131
s_node = _person(s_email)          # an attendee anchored by their address
# context/pipeline.py:1317
conn, org_id=org_id, node_type="person", canonical_key=email
```

**Calendar attendees and email participants resolve to the same `person` nodes; companies to the
same `company` node by domain.** The correlation engine then anchors on
`(counterparty entity, domain)` — so an email and a calendar event about the same people land in
the same correlation **without any correlator knowing about tools at all.**

⛔ **And that is stronger than the correlator the spec asks for.** CT-01's test is *"renaming the
event without changing purpose or identifiers leaves the association intact"* — a title-based join
would break; an identity-based one cannot.

### 1.1 · The other CT cases, measured

| | case | state |
|---|---|---|
| CT-07 | a cancelled occurrence must not cancel the series | ✅ meetings are keyed by the calendar event's own `id`, and each occurrence has a distinct one |
| CT-06 | one message mirrored into several artefacts | ✅ `capture/screen/fingerprint` writes one ref with `independence_group='same_message:'+fp` |
| CT-02 | Calendar unavailable ≠ no meeting | ✅ L3-02/03 |
| **CT-10** | **a draft is not a send** | ⛔ **LIVE DEFECT** |

**A capability lost along the way, recorded:** `calendar.py:172` reads `ev.get("recurringEventId")`
and reduces it to `bool(...)` for `meeting_kind`. **The series link itself is discarded**, so *"is
this recurring review still happening"* cannot be asked. That is a missing **feature**, not a
correctness bug, and it is not built here.

---

## 2. ⛔ THE DEFECT — an unsent draft counted as a reply

```python
def direction_of(message: ThreadMessage) -> Direction:
    if not identities or not message.actor_email: return Direction.unknown
    return (Direction.outbound if message.actor_email in identities else Direction.inbound)
```

**One question: is the author one of us. A draft is authored by us. So it returned `outbound`.**

And `outbound` is read everywhere as *"we replied"*:

* `ball_in_court` flips to `them`
* a waiting relationship reads as **answered**
* ⛔ **the 23 September benchmark's headline finding — *"you have sent zero emails in 28 days"*,
  with four investor-adjacent people waiting 46–77 days — would have read *"you sent two"* on the
  strength of two drafts sitting in a folder**

### 2.1 · The label was captured and read by nobody

Gmail states it: `labelIds` contains `DRAFT`. It is on the raw payload of **every** message
(`composio.py:588`). `light_junk` reads that same list for `SPAM`, `TRASH`,
`CATEGORY_PROMOTIONS` and `CATEGORY_SOCIAL`.

⛔ **`DRAFT` appears nowhere in the engine.** And the Gmail query carries **no label filter**, so
drafts are ingested as ordinary messages.

### 2.2 · Two decisions inside the fix

**⛔ The draft is refused, not dropped.** *"You drafted a reply three weeks ago and never sent it"*
is one of the most useful things in a founder's mailbox — **the defect was calling it a send, not
keeping it.** `DRAFT` deliberately does **not** join the junk labels, and a test pins that.

**⛔ The direction becomes `unknown`, not a fourth enum value.** That is this enum's own doctrine:
*"a message whose direction nobody can derive… the honest value keeps it out of every rule that
means 'they said' or 'we said'."* Between *"we do not know"* and *"it was sent"*, the refusal is
correct. `is_draft` travels so a later reading can build the positive finding.

**⛔ And the flag is tri-state.** `None` means the connector carried no labels at all — **a source
that cannot speak about drafts must not be read as denying one** — so every caller written before
this field behaves exactly as it did.

---

## 3. Result

```
FULL SUITE   13,224 passed · 1,061 skipped · 152 xfailed · 14 failed
                                                          └── all 14 pre-existing
before L3-08: 13,216 passed · 14 failed
```

**+8 tests · 0 regressions · no migration · no model call.**

**Technique 3 — five mutations, all red:** remove the refusal; make `None` refuse too; case-bind the
label check; read "no labels" as "not a draft"; drop drafts as junk.

## 4. What this step does NOT do

* ⛔ **It does not build a Cross Tool correlator.** The join is entity resolution and is stronger
  than the correlator would be. Sixth "already built" in this layer.
* **It does not recover the recurring-series link.** `recurringEventId` is still reduced to a
  boolean. Recorded as a lost capability, not fixed.
* ⛔ **It does not surface "drafted but never sent" as intelligence.** The flag now travels; the
  reading that uses it is a card, and no card is claimed here.
