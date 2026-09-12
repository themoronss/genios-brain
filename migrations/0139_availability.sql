-- 0139 · SignalType member fifteen: `availability_change`.
--
-- 0092 closed `qualified_signals.signal_type` and `qualification_drops.signal_type` with CHECKs
-- over doc 08's fourteen members, so that a type ALG-16/17 cannot rank is refused at the table.
-- `availability_change` (an explicit leave / out-of-office / auto-reply window, or a calendar
-- OOO block) now has a precedence position, a weight, an expiry window and a normalize row, so
-- the CHECKs are widened by exactly that one word — re-created, not dropped: the set stays closed.
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
                        'anomaly', 'information_conflict', 'availability_change'));
    alter table qualification_drops drop constraint if exists qualification_drops_signal_type;
    alter table qualification_drops add constraint qualification_drops_signal_type check (
        signal_type in ('commitment_made', 'commitment_due', 'deadline_stated',
                        'decision_pending', 'decision_made', 'approval_requested',
                        'escalation', 'risk_flagged', 'opportunity_signal',
                        'relationship_change', 'financial_obligation', 'contract_renewal',
                        'anomaly', 'information_conflict', 'availability_change'));
end $$;
