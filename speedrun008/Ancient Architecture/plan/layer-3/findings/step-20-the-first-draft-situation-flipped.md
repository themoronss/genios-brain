# L3-20 findings · the first draft situation flipped — and why only one

**2026-09-26** · corpus change only · no code · no migration
**`admit.py --check`: 201 admitted · 0 drifted · 23 blocked · 0 HOLLOW**

> ⛔ **This file exists because a test asked for it.**
> `test_a_draft_situation_is_reported_because_its_card_cannot_instruct` pinned the draft count at 24
> with the message: *"If this **FELL**, say so in the findings — it is the cheapest quality win in
> Layer 2 and it is authoring, not code."* It fell to 23. This is saying so.

---

## 1 · What changed

`admin.sit.document_under_control` · `identity.status: draft → stable`, then re-stamped with
`Domain Expertise/_tools/admit.py --accept admin.sit.document_under_control`.

```
before : 200 admitted · 24 blocked ·  Admin unreviewed 8
after  : 201 admitted · 23 blocked ·  Admin unreviewed 7 ·  0 drifted · 0 HOLLOW
```

## 2 · ⛔ Why this one, and why it was verified rather than trusted

It was the **only** draft situation whose block was a **LAG rather than a review**. It already
carried `review_status: approved` and `reviewed_by: harsh` — a human had read it — and only
`identity.status` was still `draft`.

Its own note said the gap it was authored to name *"turned out to be a projection rather than a
connector: the file metadata was already arriving and being discarded… **and now bound**."*

**That note was checked before the flip, not taken on trust:**

| check | result |
|---|---|
| which domains declare the `document` anchor | ⛔ **`('admin',)` — Admin, and only Admin** |
| `spec_for("admin").type_for("document")` | `document_under_control` |
| what the situation file matches on | `l2_situation_types: [document_under_control]` — **exact** |
| who writes that situation type | `context/document_register.py` |

**So the binding is real and the `draft` was stale.** The flip is a measurement, not an opinion.

## 3 · ⛔ Why the remaining 23 are not one more edit each

**Admin's seven split two ways, and the split matters more than the count.**

### Four are declared pending and MUST NOT be flipped

`asset_in_custody` · `employee_lifecycle_event` · `obligation_falls_due` ·
`spend_against_a_commitment` — all four are listed in
`registry/situation-capability-map.yaml::pending_l2_types`, and `deferrals.yaml` carries a reason
per entry with three named kinds (`out_of_v1_scope` · `blocked_on_l2_type` · `no_runtime_trigger`).

⛔ `obligation_falls_due`'s own note: *"the most explicit about why it **must not be faked**. Every
other gap in this corpus costs a missed insight; **this one would cost a false assurance**, and the
two are not the same kind of wrong."*

### Three are finished and awaiting a named human

| situation | anchor | declared by | type match | block |
|---|---|---|---|---|
| `campaign_awaiting_reply` | `campaign` | ✅ `('admin',)` | ✅ | `review_status: unreviewed` |
| `condition_awaiting_review` | `condition` | ✅ `('admin',)` | ✅ `condition_in_review` | `review_status: unreviewed` |
| `organization_gone_quiet` | `organization` | ✅ `('admin',)` | ✅ | `review_status: unreviewed` |

All three carry the corpus's most rigorous notes — *"**EVERY PREDICATE HAS A LIVE WRITER**, checked
against the tenant rather than assumed. Live read on 2026-09-09: two campaigns, 7 and 6
recipients"* — and their anchors and types are verified above.

⛔ **The block is the half of the ceremony no tool may perform.** `admit.py` says it itself: *"It
deliberately does NOT grant review. `--accept` refuses anything the reviewer has not already marked
approved with their name on it."* A name typed by a machine is the exact failure the hash pin exists
to prevent.

**MOVES WHEN** Rohit or Harsh puts their name on them.

---

## 4 · ⛔ Two pins moved, and both were designed to

The full suite went from 14 pre-existing failures to 16. **Both new failures were baseline pins
doing their job**, not breakage:

| pin | was | now |
|---|---|---|
| `assert unreviewed == 24` | 24 | **23** |
| `_BASELINE_ADMIN_DRAFTS` | 8 | **7** |

**Updated deliberately, with the reason recorded at each pin — not loosened.** The second one's
purpose is to prove the count is *unchanged by an edit* (that the capability ceremony is not applied
to situations), so it needed the new Admin baseline and nothing else.

---

## 5 · ⛔ A premise this corrected — P4 is not what the plan said

While measuring which family to author next, the planned target collapsed.

**The plan said:** add `reads:` for the 61 unconsumed substrate families — starting with
`mailbox.*` (17) — to the Admin capabilities that should own them.

**Measured, that is wrong twice over:**

1. **Capabilities carry no `reads:` at all.** It lives in heuristics — and heuristics carry **no
   `admission` block**, so editing them breaks no hash. Capabilities do carry one, and
   `capability_resolver` compares it: *"an edit after review **silently un-accepts**, which is the
   point."*

2. ⛔ **All seven "desk" anchors are declared by SUPPORT ONLY:**

```
thread · backlog_item · escalation · contact_intent · topic · mailbox · workaround
                    ⛔ Admin declares none of them
```

The engine writes `mailbox.*` on every tenant — `refresh_support_situations` runs in the L2 sweep
with no domain gate — but the **situation** only forms for `support`. So authoring Admin doctrine
over those fields would build for a situation that never forms: the twelve-times-counted defect.

**~40 of the 61 belong to Support's anchors, and Support is on hold.**

### What IS Admin's, measured

| family | fields | written by | Admin-readable |
|---|---|---|---|
| `document.*` | 8 | `context/document_register.py` — not a desk anchor | ✅ |
| `derived.history.*` | 4 | `correlation_history.py` — reaches its anchor through `signals.subject_node_id`, domain-agnostic | ✅ |

⛔ **And `admin.sit.document_under_control` — the situation flipped above — reads ZERO of the eight
`document.*` fields.** That is the next real authoring step, and it now has a `stable` home to land
in.
