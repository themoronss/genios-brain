← [Exact-Pack Lineage and the Weekly Claim](03-Lineage-and-The-Weekly-Claim.md) · [Folder map](README.md) · → [Gaps](05-Gaps.md)

---

# Mutes, Nudges and the Audit Ledger

---

## A mute must take effect in the same commit

```python
if muted:
    # A newly harmful rule must stop being actionable in the same commit as its mute.
    update cards   set state  = 'expired'  where signal_id = any(:ids) and state in (...)
    update signals set status = 'expired'  where signal_id = any(:ids) and status = 'open'
```

> The pack epoch bump revokes every old projection; **explicit lifecycle closure makes that
> revocation visible even to historical / non-authority UI surfaces.**

Without this, a rule could be muted on Monday and its already-queued cards would keep asking
people to act on it.

---

## The pin check — the calibrator gets no private door

```python
offset_path_pinned = any(str(pin).startswith("scoring_defaults.rule_offsets") for pin in pins)
if not offset_path_pinned:
    ... compute nudges ...
```

An admin who pins `scoring_defaults.rule_offsets` **freezes learning for that tenant.** Layer 7
still computes precision, still mutes and recovers, and simply does not nudge.

The same guard exists a second time, in SQL, inside
`PackRegistry.write_lvl3_offset` ([Layer 3 §3.4](../Layer-3-Domain-Expertise/00-Overview.md)) — *two
independent enforcements of one rule.*

---

## The audit ledger

Every mute, unmute and nudge writes a `calibration_nudges` row carrying:

```text
rule_id · param · before_val · after_val · offset_cumulative · direction
· precision · precision_lb · precision_ub · impressions · judgments
· calibration_run_id · period_start · authority_revision
```

**The statistics that justified the change travel with the change.** Six months later, *"why is
`champion_quiet` offset by +10?"* is answerable from the row, not from a reconstruction.

`nudge_id = stable_id("nudge", {run_id, rule_id, param})` — content-addressed, so a retried
transaction cannot double-write.

---
