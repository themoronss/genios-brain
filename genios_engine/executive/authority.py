"""Layer 5's read-only bridge to the Layer 4 decision authority contract.

``signals`` is a lifecycle projection.  Its identifiers and open/closed state are useful,
but its decision fields are not executive truth.  These expressions deliberately project
the immutable completed run, selected candidate, and effective config snapshot instead.
"""
from __future__ import annotations

from genios_engine.reason.authority import (
    AUTHORITATIVE_REASON_CODE_SQL,
    AUTHORITATIVE_SCORE_INPUTS_SQL,
    AUTHORITATIVE_SCORE_SQL,
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
    authority_time,
)


EXECUTIVE_RULE_ID_SQL = "regexp_replace(rr.capability_id, '^.*\\.', '')"

# Legacy rule level is part of the immutable effective config bytes.  Native capabilities
# currently emit prescriptive decisions and do not yet carry a separate level contract.
EXECUTIVE_LEVEL_SQL = (
    "case when rr.capability_id like 'legacy.%' then coalesce(("
    "select executive_rule->>'level' "
    "from jsonb_array_elements(coalesce(authority_cfg.effective->'rules','[]'::jsonb)) "
    "executive_rule where executive_rule->>'id'=(" + EXECUTIVE_RULE_ID_SQL + ") "
    "limit 1), 'prescriptive') else 'prescriptive' end"
)


EXECUTIVE_ATTENTION_AUTHORITY_JOIN = (
    "left join (select rr.root_node_id as node_id, max(" + AUTHORITATIVE_SCORE_SQL + ") "
    "as max_signal_score from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
    "where s.org_id=:o and s.status='open' and " + AUTHORITATIVE_SIGNAL_PREDICATE + " "
    "group by rr.root_node_id) executive_authority "
    "on executive_authority.node_id=a.node_id "
)


# ``context_attention`` predates candidate-bound signal authority.  Preserve all of its
# non-signal components, but replace its cached raw-signal contribution with the current audited
# maximum.  This keeps executive priority surfaces useful without trusting the old projection.
EXECUTIVE_ATTENTION_SCORE_SQL = (
    "least(100, greatest(0, "
    "coalesce((a.inputs->>'recency')::int,0) + "
    "coalesce((a.inputs->>'ball')::int,0) + "
    "coalesce((a.inputs->>'commitment')::int,0) + "
    "coalesce((a.inputs->>'question')::int,0) + "
    "coalesce((a.inputs->>'polarity')::int,0) + "
    "least(20, coalesce(executive_authority.max_signal_score,0) / 5)))"
)


def authoritative_play_win_rates(store, org_id: str, *, eval_time=None) -> dict:
    """Measured play outcomes grouped by the audited candidate, never ``signals.play``.

    These are historical outcome observations, so current expiry/pack/graph predicates would
    incorrectly erase earned evidence.  The query instead proves the immutable decision binding
    and that the event occurred inside that decision's authority window.
    """
    from genios_engine.reason.foresight import play_win_rates

    return play_win_rates(store, org_id, eval_time=eval_time)


__all__ = [
    "AUTHORITATIVE_REASON_CODE_SQL",
    "AUTHORITATIVE_SCORE_INPUTS_SQL",
    "AUTHORITATIVE_SCORE_SQL",
    "AUTHORITATIVE_SIGNAL_JOINS",
    "AUTHORITATIVE_SIGNAL_PREDICATE",
    "EXECUTIVE_ATTENTION_AUTHORITY_JOIN",
    "EXECUTIVE_ATTENTION_SCORE_SQL",
    "EXECUTIVE_LEVEL_SQL",
    "EXECUTIVE_RULE_ID_SQL",
    "authoritative_play_win_rates",
    "authority_time",
]
