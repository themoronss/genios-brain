"""The Layer 1 supply a seeded tenant needs before Layer 2 will admit its situations.

WHY THIS EXISTS. L2's admission gate (`context/situation_publisher`, migration 0122) refuses to
publish a situation that carries no VERIFIED EVIDENCE SPAN, and a verified span is only ever
published on a `qualified_signals` row. That half of the gate is fail-closed, unconditional and
correct — it is "no claim without a receipt" at the one door into Layer 3 — and it sits ahead of
the L3 compile and the whole of L4. A fixture that commits correspondence and goes straight to
`refresh_situations` produces a tenant whose every situation is HELD; `shadow_compile` then
reports a clean `admission_hold` and reasons about nothing.

Every seed in this suite predates the gate and none of them supplied that half. This is the half,
written once: the `qualified_signals` rows a real tenant's Layer 1 pass would have written for the
same correspondence, attached to each situation's own correlation members.

NOT A RELAXATION OF ANYTHING. The gate is untouched and still refuses a tenant that lacks these
rows; what changed is that the fixtures now supply what a customer supplies. The span takes
`verify_evidence_spans`' documented third branch -- "no source text (retention window passed) ->
Layer 1's flag stands, as l1_verified" -- which is a real production state, and the one these
fixtures are in: they seed `source_events` directly and never write `prepared_content`.

TWO SUPPLIES, NOT ONE, because Layer 1 publishes two and they are different facts:

  * SCORED (`scored=True`) -- ALG-17 produced a number. `importance_source` reads
    `l1_qualified_signals` and the ranker's sixth component is real.
  * UNSCORED (`scored=False`) -- the signal QUALIFIED, with its receipts, and the floor could not
    measure it (`capture/esqe/qualification`: "a floor must never refuse what it could not
    measure"). It publishes at 0 with `importance_version` reading `unscored`, Layer 2 reads that
    as an ABSENCE rather than a low score, `importance_base` answers `l1_unscored` and DECLARES
    the 5,000 fallback, and Layer 4's honesty guard reweighs the remaining five components and
    records `L2_IMPORTANCE_NOT_ACTIVE`.

A fixture whose subject is the absent-importance guard MUST take the second one. Handing it the
first would make the guard's test pass while proving nothing, which is worse than red.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import text

#: Quoted verbatim, and its offsets must agree with its length or `EvidenceSpan` refuses it and
#: the receipt silently stops counting. That is exactly how this fixture failed the first time.
QUOTE = "the quoted sentence"

#: `capture.esqe.qualification.UNSCORED_VERSION` and `context.situation_bso.UNSCORED_VERSION`,
#: spelled rather than imported for the reason both of them are: a fixture that imported a capture
#: module to learn one word would be the only thing in this suite taking that dependency, and
#: `tests/test_l2_reads_what_l1_publishes.py` already pins the two spellings together.
UNSCORED_VERSION = "unscored"


def attach_l1_signals(store, org_id: str, *, eval_time: datetime,
                      scored: bool = True,
                      base_importance_bp: int = 1_500, step_bp: int = 137) -> int:
    """One span-verified `qualified_signals` row per situation. Returns how many.

    Call it AFTER `refresh_situations` (the correlations and situations must exist) and BEFORE
    `shadow_compile`. It re-runs `refresh_situation_importance` itself, because the composed
    importance on the situation row is derived from exactly these signals.
    """
    from genios_engine.context.situation_bso import refresh_situation_importance

    with store.engine.begin() as conn:
        rows = conn.execute(text(
            "select s.situation_id, s.correlation_id, min(m.event_id) as event_id "
            "from context_situations s "
            "join context_correlation_members m "
            "  on m.correlation_id = s.correlation_id and m.org_id = s.org_id "
            "where s.org_id = :o group by s.situation_id, s.correlation_id "
            "order by s.situation_id"), {"o": org_id}).all()
        made = 0
        for index, row in enumerate(rows):
            # ORG-SCOPED. `qualified_signals.signal_id` is the primary key and is NOT scoped by
            # org — so a bare `sig_l1supply_0` meant the SECOND tenant seeded on one database
            # collided with the first's row, and (with the `do nothing` this insert used to
            # carry) silently got no supply at all while this function still returned 1. Every id
            # minted here carries the org for that reason.
            signal_id = f"sig_l1supply_{org_id}_{index}"
            refs = [{"source_ref": f"prepared_content:{row.event_id}", "quote": QUOTE,
                     "start_offset": 0, "end_offset": len(QUOTE),
                     "verified": True, "signal_id": signal_id}]
            done = conn.execute(text(
                "insert into qualified_signals (signal_id, org_id, event_id, trace_id, "
                " signal_type, importance_bp, importance_version, confidence_bp, visibility, "
                " extraction_ref, evidence_refs, importance_components, state, occurred_at) "
                "values (:s,:o,:e,:tr,'commitment_made',:i,:iv,:cf,"
                " cast('{\"scope\": \"org\"}' as jsonb), :x, cast(:refs as jsonb), "
                " cast(:comp as jsonb), 'active', :t) "
                # RE-STATE, do not skip. `on conflict do nothing` made this helper silently
                # non-idempotent: a second run against a database that already held these rows
                # inserted none, `made` came back 0, and — worse — a tenant re-seeded with
                # `scored=False` kept the SCORED rows an earlier run had left it. Upserting the
                # judgement columns and leaving `created_at` alone is exactly what the production
                # writer (`capture/esqe/signal_store.PostgresSignalStore.put`) does, and for the
                # same reason: a replayed sweep re-states what it concluded.
                "on conflict (signal_id) do update set "
                "importance_bp=excluded.importance_bp, "
                "importance_version=excluded.importance_version, "
                "importance_components=excluded.importance_components, "
                "confidence_bp=excluded.confidence_bp, "
                "evidence_refs=excluded.evidence_refs, "
                "state=excluded.state, occurred_at=excluded.occurred_at"),
                {"s": signal_id, "o": org_id, "e": row.event_id,
                 "tr": f"tr_l1supply_{org_id}_{index}",
                 # Spread, not a constant: a fixture whose every situation scored the same number
                 # cannot tell a ranker that reads importance from one that ignores it. An
                 # unscored row publishes at 0 — the column is NOT NULL and 0 beside
                 # `importance_version = 'unscored'` is how Layer 1 spells "no number", which is
                 # the state Layer 2 must read as an absence.
                 "i": (base_importance_bp + (index * step_bp) % 7_000) if scored else 0,
                 "iv": "alg17-v1" if scored else UNSCORED_VERSION,
                 "cf": 5_000 + (index * 53) % 4_000, "x": f"ex_l1supply_{org_id}_{index}",
                 "refs": json.dumps(refs),
                 "comp": json.dumps({"base_bp": 4_000} if scored else {}),
                 "t": eval_time - timedelta(hours=index)})
            # `rowcount`, not `+= 1`: an optimistic counter is exactly how the id collision above
            # stayed invisible while the tenant got no supply at all.
            made += done.rowcount or 0
    if made:
        refresh_situation_importance(store, org_id, eval_time=eval_time)
    return made


__all__ = ["QUOTE", "UNSCORED_VERSION", "attach_l1_signals"]
