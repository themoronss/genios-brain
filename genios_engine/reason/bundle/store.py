"""Where a narrative lives, and where every consult is receipted (migration 0120).

**Two guarantees this module owes the rest of the wave.**

1. *A stored bundle is re-validated on the way OUT.* `ReasoningBundle`'s constructor verifies
   `bundle_hash` against the content when one is supplied, so rehydrating through the constructor
   is what makes a tampered or half-written row fail closed rather than render. `reason/store.py`
   earned that discipline for the audit bundle; this is the same rule for the prose.
2. *A cache hit is only a hit for the SAME decision.* The key is `(org_id, decision_hash)` and the
   row also carries `decision_id` and `action_id`, so a row read back for a decision whose action
   has moved is refused at the read. Doc 09 case 2 is the worst output this layer can produce, and
   a cache is the one place a correct bundle can arrive attached to the wrong decision.

**Reads fail closed and never raise.** A narration pass that cannot read the cache must narrate
(or fall back), never crash the sweep it runs at the end of. Writes DO raise: a bundle that was
generated, paid for, and then silently not stored is a bill with no product, and it would show up
as an eternal 0% cache-hit rate that nobody could explain.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from genios_engine.contracts.reasoning import ReasoningBundle
from genios_engine.platform.logging import get_logger

from .sites import require_outcome, require_site

_log = get_logger("genios.reason.bundle.store")

BUNDLE_TABLE = "l4_reasoning_bundles"
CALL_TABLE = "l4_r_site_calls"


@dataclass(frozen=True, slots=True)
class StoredBundle:
    """One row of `l4_reasoning_bundles`, with the bundle already back through its constructor."""

    bundle: ReasoningBundle
    generation: str
    rendered: Mapping[str, Any]
    gauntlet: Sequence[Mapping[str, Any]]
    attempts: int
    cost_micro_usd: int
    run_id: str | None
    created_at: datetime | None


def _jsonable(value: Any) -> Any:
    """Mappings and tuples all the way down, as plain JSON types.

    `json.dumps(..., default=str)` is NOT enough and the failure is silent: `ReasoningBundle`
    carries its citations as `MappingProxyType`, which `json` cannot serialise, so `default=str`
    turned each one into the STRING `"{'artifact_id': ...}"`. The row then wrote, read back, and
    failed re-validation — which the fail-closed read reported as a cache miss, so the only visible
    symptom was a narrative that regenerated forever.
    """
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _json(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"))


def _loaded(value: Any) -> Any:
    """A jsonb column psycopg may hand back as text — the same defence `intelligence_routes._jsonish`
    makes at the API edge, made here so no caller has to know which driver it is talking to."""
    if isinstance(value, (Mapping, list)):
        return value
    if value is None:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def _bundle_from_row(payload: Mapping[str, Any]) -> ReasoningBundle:
    """Rehydrate THROUGH the constructor, hash and all — see guarantee 1."""
    data = dict(payload)
    citations = tuple(dict(item) for item in (data.pop("citations", None) or ()))
    return ReasoningBundle(
        decision_id=data["decision_id"], action_id=data["action_id"],
        headline=data["headline"], situation_summary=data["situation_summary"],
        why_it_matters=data["why_it_matters"], root_cause=data["root_cause"],
        recommendation_rationale=data["recommendation_rationale"],
        expected_effect=data["expected_effect"],
        alternatives_narrative=data.get("alternatives_narrative"),
        citations=citations,
        evidence_refs=tuple(data.get("evidence_refs") or ()),
        numbers_used=dict(data.get("numbers_used") or {}),
        generation=data["generation"],
        bundle_hash=data.get("bundle_hash"))


class BundleStore:
    """The narrative's persistence. Constructed from an engine the caller already holds."""

    def __init__(self, engine) -> None:
        self._engine = engine

    @property
    def engine(self):
        return self._engine

    # ── the cache (doc 11 guard 2) ───────────────────────────────────────────────────────────

    def get(self, *, org_id: str, decision_hash: str,
            expect_action_id: str | None = None) -> StoredBundle | None:
        """The stored narrative for this decision, or None. Never raises; never returns a bundle
        whose action disagrees with `expect_action_id`."""
        if self._engine is None:
            return None
        from sqlalchemy import text
        try:
            with self._engine.connect() as conn:
                row = conn.execute(text(
                    f"select bundle, bundle_hash, generation, rendered, gauntlet, attempts, "
                    f"cost_micro_usd, run_id, action_id, created_at from {BUNDLE_TABLE} "
                    "where org_id = :o and decision_hash = :d"),
                    {"o": org_id, "d": decision_hash}).first()
        except Exception as exc:      # noqa: BLE001 — an unreadable cache is an EMPTY cache
            _log.warning("could not read %s for org=%s: %s", BUNDLE_TABLE, org_id, exc)
            return None
        if row is None:
            return None
        if expect_action_id is not None and row.action_id != expect_action_id:
            # Doc 09 case 2, caught at the one place a correct bundle can meet the wrong decision.
            _log.warning("stored bundle for org=%s decision=%s narrates action %s, decision "
                         "committed to %s — refusing the cache hit",
                         org_id, decision_hash, row.action_id, expect_action_id)
            return None
        payload = _loaded(row.bundle)
        if not isinstance(payload, Mapping):
            return None
        try:
            bundle = _bundle_from_row({**payload, "bundle_hash": row.bundle_hash})
        except Exception as exc:      # noqa: BLE001 — a row that does not re-validate is not a hit
            _log.warning("stored bundle for org=%s decision=%s failed re-validation: %s",
                         org_id, decision_hash, exc)
            return None
        return StoredBundle(
            bundle=bundle, generation=row.generation,
            rendered=_loaded(row.rendered) or {}, gauntlet=_loaded(row.gauntlet) or [],
            attempts=int(row.attempts or 0), cost_micro_usd=int(row.cost_micro_usd or 0),
            run_id=row.run_id, created_at=row.created_at)

    def put(self, *, org_id: str, decision_hash: str, bundle: ReasoningBundle,
            gauntlet: Sequence[Mapping[str, Any]] = (), attempts: int = 0,
            cost_micro_usd: int = 0, run_id: str | None = None,
            store_decision_hash: str | None = None) -> bool:
        """Store one narrative. True when this call wrote NEW PROSE.

        **The prose is never overwritten; the pointer is.** Two things can bring the same decision
        back: a concurrent sweep narrating it at the same moment, and the same situation being
        re-decided next sweep — which produces a NEW run and a new `reasoning_run_outputs`
        decision_hash while the contract hash, and therefore the narrative, is unchanged. Both must
        end with one narrative and a pointer that reaches today's card:

        * `do update` on `store_decision_hash` and `run_id` — otherwise the newly published signal
          would join to nothing and its card would never carry prose, and the sweep would keep
          re-listing it forever;
        * everything else left alone — re-rendering a customer's card because a concurrent pass
          finished second is exactly the prose drift doc 05 §7 caches against.

        `xmax = 0` is PostgreSQL's own answer to "did this upsert insert or update", which is what
        makes the return value mean "new prose" rather than "a statement ran".
        """
        from sqlalchemy import text
        with self._engine.begin() as conn:
            row = conn.execute(text(
                f"insert into {BUNDLE_TABLE} (org_id, decision_hash, decision_id, action_id, "
                "run_id, store_decision_hash, bundle, bundle_hash, generation, rendered, "
                "gauntlet, attempts, cost_micro_usd) values (:o, :d, :did, :aid, :run, :sdh, "
                "cast(:b as jsonb), :bh, :g, cast(:r as jsonb), cast(:gl as jsonb), :a, :c) "
                "on conflict (org_id, decision_hash) do update set "
                f"  store_decision_hash = coalesce(excluded.store_decision_hash, "
                f"                                 {BUNDLE_TABLE}.store_decision_hash), "
                f"  run_id = coalesce(excluded.run_id, {BUNDLE_TABLE}.run_id) "
                "returning (xmax = 0) as inserted"),
                {"o": org_id, "d": decision_hash, "did": bundle.decision_id,
                 "aid": bundle.action_id, "run": run_id, "sdh": store_decision_hash,
                 "b": _json(bundle.to_semantic_dict()), "bh": bundle.bundle_hash,
                 "g": bundle.generation, "r": _json(dict(bundle.render())),
                 "gl": _json(list(gauntlet)), "a": int(attempts),
                 "c": int(cost_micro_usd)}).first()
        return bool(row is not None and row.inserted)

    # ── the consult ledger (doc 01 C5 step 2) ────────────────────────────────────────────────

    def record_call(self, *, org_id: str, site: str, outcome: str, tier: str, cache_key: str,
                    model: str | None = None, input_tokens: int = 0, output_tokens: int = 0,
                    cost_micro_usd: int = 0, attempts: int = 0,
                    reason_codes: Sequence[str] = ()) -> None:
        """One row per gate outcome, INCLUDING every skip. Never raises.

        Never raises because this is a receipt, and a receipt that can abort the thing it is a
        receipt for turns an accounting failure into a product failure. A lost row costs a
        mis-stated rate on a dashboard; a raised exception here would cost the narration pass.
        """
        require_site(site)
        require_outcome(outcome)
        if self._engine is None:
            return
        from sqlalchemy import text
        try:
            with self._engine.begin() as conn:
                conn.execute(text(
                    f"insert into {CALL_TABLE} (org_id, site, outcome, tier, cache_key, model, "
                    "input_tokens, output_tokens, cost_micro_usd, attempts, reason_codes) "
                    "values (:o, :s, :out, :t, :k, :m, :i, :ot, :c, :a, cast(:rc as jsonb))"),
                    {"o": org_id, "s": site, "out": outcome, "t": tier, "k": cache_key,
                     "m": model, "i": int(input_tokens), "ot": int(output_tokens),
                     "c": int(cost_micro_usd), "a": int(attempts),
                     "rc": _json(list(reason_codes))})
        except Exception as exc:      # noqa: BLE001 — see the docstring
            _log.warning("could not record an R-site consult for org=%s site=%s: %s",
                         org_id, site, exc)

    # ── what K4 is measured on ───────────────────────────────────────────────────────────────

    def stats(self, *, org_id: str, since: datetime | None = None) -> dict[str, Any]:
        """K4's numbers, from the rows rather than from a counter kept in a process.

        `fallback_rate_bp` is basis points, not a percentage, for the same reason every other rate
        in this codebase is: K4's gate is "< 15%" and a float rate compared against 0.15 is a
        comparison whose answer depends on the machine.
        """
        from sqlalchemy import text
        since = since or datetime(1970, 1, 1, tzinfo=timezone.utc)
        with self._engine.connect() as conn:
            bundles = conn.execute(text(
                "select count(*) as n, "
                "count(*) filter (where generation = 'template_fallback') as fallback, "
                "coalesce(sum(cost_micro_usd), 0) as cost "
                f"from {BUNDLE_TABLE} where org_id = :o and created_at >= :s"),
                {"o": org_id, "s": since}).first()
            outcomes = conn.execute(text(
                "select outcome, count(*) as n, coalesce(sum(cost_micro_usd), 0) as cost "
                f"from {CALL_TABLE} where org_id = :o and created_at >= :s group by outcome"),
                {"o": org_id, "s": since}).all()
        total = int(bundles.n or 0)
        fallback = int(bundles.fallback or 0)
        by_outcome = {row.outcome: int(row.n) for row in outcomes}
        ran = by_outcome.get("ran", 0)
        cached = by_outcome.get("cached", 0)
        return {
            "bundles": total,
            "template_fallback": fallback,
            # Integer basis points, computed on integers. 0 bundles is 0 bp rather than an
            # undefined rate reported as zero — the caller has `bundles` to tell them apart.
            "fallback_rate_bp": (fallback * 10_000 // total) if total else 0,
            "cost_micro_usd": int(bundles.cost or 0),
            "consults": dict(sorted(by_outcome.items())),
            "cache_hit_rate_bp": (cached * 10_000 // (ran + cached)) if (ran + cached) else 0,
            "consult_cost_micro_usd": sum(int(row.cost) for row in outcomes),
        }

    def spent_today_micro_usd(self, *, org_id: str, now: datetime | None = None) -> int:
        """The number `NarrativeBudget` opens its day from. Here rather than there so the SQL for
        one table lives in one module."""
        from sqlalchemy import text
        with self._engine.connect() as conn:
            return int(conn.execute(text(
                f"select coalesce(sum(cost_micro_usd), 0) from {CALL_TABLE} "
                "where org_id = :o and created_at >= date_trunc('day', :now)"),
                {"o": org_id, "now": now or datetime.now(timezone.utc)}).scalar() or 0)

    def undecorated_decisions(self, *, org_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """PUBLISHED decisions on this tenant that carry no narrative yet — the sweep's worklist.

        A published decision is an OPEN signal that points at a Layer 4 reasoning run: that is what
        publication means on the compiled lane (`reason/domain_shadow._emit_capability_signal`
        writes exactly those columns), and it is the only definition under which doc 11 guard 3 —
        "suppressed and DEFERred decisions generate no bundle" — is true by construction rather
        than by a filter somebody has to remember to write. A suppressed decision never becomes a
        signal row, so it cannot appear here.

        Newest first and capped, because a tenant switched on after a month of history must not
        narrate a month of decisions in one sweep — doc 11's per-org daily cap would stop the spend
        but the first day would be spent entirely on cards nobody is going to read.
        """
        from sqlalchemy import text
        with self._engine.connect() as conn:
            rows = conn.execute(text(
                "select s.signal_id, s.reasoning_run_id, s.reasoning_decision_hash, "
                "s.subject_node_id, s.capability_id, s.rule_id, s.eval_time "
                "from signals s "
                f"left join {BUNDLE_TABLE} b on b.org_id = s.org_id "
                # The STORE's hash, which is what this column points at — see the migration.
                "  and b.store_decision_hash = s.reasoning_decision_hash "
                "where s.org_id = :o and s.status = 'open' "
                "  and s.reasoning_run_id is not null "
                "  and s.reasoning_decision_hash is not null "
                "  and b.decision_hash is null "
                "order by s.eval_time desc, s.signal_id limit :l"),
                {"o": org_id, "l": max(1, int(limit))}).all()
        return [{"signal_id": r.signal_id, "run_id": r.reasoning_run_id,
                 "decision_hash": r.reasoning_decision_hash, "node_id": r.subject_node_id,
                 "capability_id": r.capability_id, "rule_id": r.rule_id,
                 "eval_time": r.eval_time} for r in rows]


def bundles_for_cards(engine, *, org_id: str, card_ids: Sequence[str]) -> dict[str, dict]:
    """The READ a card surface makes: `{card_id: the rendered narrative}` for a page of cards.

    Keyed on `card_id` rather than on the signal, because that is what a feed already holds — a
    read that obliged its caller to add a column to two queries is a read that does not get wired,
    and an unwired narrative is this wave repeating Layer 1's six unreached units.

    One query for the page rather than one per card, and the RENDERED form rather than the bundle:
    the whole mechanism is that the digits a customer reads are the engine's digits, so a second
    substitution at the API edge is a second place they can be wrong.

    Fails closed to `{}`. A feed whose narrative column is unavailable renders exactly as it
    renders today, which is the state every card is in.
    """
    if engine is None or not card_ids:
        return {}
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "select k.card_id, b.rendered, b.generation, b.bundle "
                "from cards k join signals s on s.signal_id = k.signal_id and s.org_id = k.org_id "
                f"join {BUNDLE_TABLE} b on b.org_id = s.org_id "
                "  and b.store_decision_hash = s.reasoning_decision_hash "
                "where k.org_id = :o and k.card_id = any(:ids)"),
                {"o": org_id, "ids": list(card_ids)}).all()
    except Exception as exc:      # noqa: BLE001 — see the docstring
        _log.warning("could not read narratives for org=%s: %s", org_id, exc)
        return {}
    out: dict[str, dict] = {}
    for row in rows:
        rendered = _loaded(row.rendered)
        if not isinstance(rendered, Mapping):
            continue
        payload = _loaded(row.bundle) or {}
        out[row.card_id] = {
            **dict(rendered),
            # LABELLED, always. Doc 05 §6: a fallback is plainer and never less true, and nobody
            # may mistake one for a narrative — including a client rendering this JSON.
            "generation": row.generation,
            "citations": payload.get("citations") or [],
            "evidence_refs": payload.get("evidence_refs") or [],
        }
    return out


__all__ = ["BUNDLE_TABLE", "BundleStore", "CALL_TABLE", "StoredBundle", "bundles_for_cards"]
