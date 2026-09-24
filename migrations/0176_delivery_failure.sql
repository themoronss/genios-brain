-- 0176 · SignalType member sixteen: `delivery_failure`.
--
-- WHY THIS IS REQUIRED AND NOT OPTIONAL. 0092 closed `qualified_signals.signal_type` and
-- `qualification_drops.signal_type` with CHECKs over doc 08's fourteen members, so that a type
-- ALG-16/17 cannot rank is refused at the table rather than stored unrankable. 0139 widened both
-- by one word for `availability_change`. Without the same widening here, **every delivery-failure
-- signal fails to insert** — the detector fires, the floor override lets it through, and the
-- write is refused by the constraint. The step would produce nothing and look like it worked.
--
-- WHAT THE TYPE IS. A message the tenant SENT did not arrive, and will not — a permanent delivery
-- failure reported by the receiving side (`capture/delivery_status.py`). The only member of the
-- taxonomy that is a fact about the tenant's own action rather than about something that happened
-- to them. A DELAY is deliberately not this: a message Gmail is still retrying has not failed.
--
-- MEASURED CAUSE, pilot org, 2026-09-23. Three pitches to Afore and Surge on 11 August never
-- arrived. All five delivery-status notifications were captured and `emitted`, every one
-- short-circuited at `envelope_bulk_headers`, and **no signal of any kind came out** — so a
-- founder who believes they pitched two funds did not, and nothing in the product could say so.
--
-- It now has a precedence position (second, above every claim-derived type), an ALG-17 weight
-- (9000, tied top), three normalize policy rows, a qualification override and a Layer 2 meaning
-- row in `context/observations/kinds.yaml`. So the CHECKs are widened by exactly that one word —
-- re-created, not dropped: the set stays closed.
--
-- Idempotent: drop-if-exists + add, in one transaction per table, safe to re-run.
do $$
begin
    alter table qualified_signals drop constraint if exists qualified_signals_signal_type;
    alter table qualified_signals add constraint qualified_signals_signal_type check (
        signal_type in ('commitment_made', 'commitment_due', 'deadline_stated',
                        'decision_pending', 'decision_made', 'approval_requested',
                        'escalation', 'risk_flagged', 'opportunity_signal',
                        'relationship_change', 'financial_obligation', 'contract_renewal',
                        'anomaly', 'information_conflict', 'availability_change',
                        'delivery_failure'));
    alter table qualification_drops drop constraint if exists qualification_drops_signal_type;
    alter table qualification_drops add constraint qualification_drops_signal_type check (
        signal_type in ('commitment_made', 'commitment_due', 'deadline_stated',
                        'decision_pending', 'decision_made', 'approval_requested',
                        'escalation', 'risk_flagged', 'opportunity_signal',
                        'relationship_change', 'financial_obligation', 'contract_renewal',
                        'anomaly', 'information_conflict', 'availability_change',
                        'delivery_failure'));
end $$;
