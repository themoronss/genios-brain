from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.platform import card_lifecycle
from genios_engine.platform.canonical import stable_id
from genios_engine.reason.authority import (
    AUDITED_CARD_JUDGMENTS_CTES,
    authority_time,
)

# Learning is deliberately conservative: passive impressions are observability, not labels.
# Only canonical human judgments enter confidence and eligibility calculations.
#: ⛔ The single vocabulary, imported. `contracts/` is cross-cutting, so `feedback` (7) may import
#: it; a second copy of the reason list in this file is a second source of truth.
from genios_engine.contracts.learning_attribution import ATTRIBUTION as _ATTRIBUTION
from genios_engine.contracts.learning_attribution import PrecisionRole as _PrecisionRole

#: The reasons that count against a rule's precision, as a SQL literal list. Sorted so the emitted
#: statement is byte-stable: a query text that reorders itself between runs is a query nobody can
#: diff, and `_PRECISION_SQL` is compared in tests.
_PRECISION_DENOMINATOR_SQL = ", ".join(
    f"'{reason.value}'" for reason, att in sorted(_ATTRIBUTION.items(), key=lambda kv: kv[0].value)
    if att.precision is _PrecisionRole.DENOMINATOR)

WINDOW_DAYS = 28
MIN_JUDGMENTS = 8
MUTE_PRECISION = 0.25
MUTE_MIN_JUDGMENTS = 12
LOOSEN_ABOVE = 0.70
TIGHTEN_BELOW = 0.40
OFFSET_STEP = 5
OFFSET_BOUND = 15

TAXONOMY = {
    "run_play": {"label": "positive_strong", "precision": "numerator"},
    "do_it_myself": {"label": "positive_moderate", "precision": "numerator"},
    "snooze": {"label": "timing", "precision": "none"},
    "requeue": {"label": "window_mgmt", "precision": "none"},
    # ⛔ THE ELEVEN `wrong:*` KEYS ARE GENERATED FROM `contracts/learning_attribution.ATTRIBUTION`,
    # NOT WRITTEN OUT HERE. This map held three by hand; the vocabulary now has eleven, and two
    # hand-written lists of one vocabulary is precisely how `FEATURE_CARDS_FROM_SITUATIONS` became
    # a lane no tenant could switch on — *"the reader was looking for a word the writer rejected."*
    #
    # The `label` is derived rather than restated, so a new reason cannot arrive with a label
    # nobody chose:
    #   denominator            -> negative_relevance   (it counts against the rule)
    #   none, and about WHEN   -> timing
    #   none, and about FIT    -> fit
    #
    # ⛔ `fit` IS A NEW LABEL AND IT HAD TO BE. The first version of this expression mapped every
    # `none` reason to `timing`, which would have recorded `wrong_person` and `wrong_playbook` as
    # scheduling complaints — a quiet falsehood in a column, and the kind that survives because
    # nothing crashes. The old four-word label vocabulary was designed for three reasons.
    #
    # ⛔ AND `label` HAS NO CODE READER TODAY. Grepped: `TAXONOMY` is read by
    # `attribution.timing_never_grades_accuracy` (which reads `precision`) and named in two
    # comments. This is near-miss territory for "built and called by nothing" — it predates this
    # work and is documentation-only, so it is recorded here rather than removed, because deleting
    # a field two comments describe is a bigger change than labelling it correctly.
    #
    # ⛔ The three original spellings and their three original roles come out of this expression
    # UNCHANGED — `attribution.every_legacy_reason_still_grades_the_way_it_did` is the test that
    # says so, and it matters because every judgment already recorded grades on those words.
    **{f"wrong:{reason.value}": {
           "label": ("negative_relevance" if att.precision is _PrecisionRole.DENOMINATOR
                     else "timing" if reason.value in ("bad_timing", "stale_data") else "fit"),
           "precision": att.precision.value}
       for reason, att in _ATTRIBUTION.items()},
}

_PRECISION_SQL = text(
    "with " + AUDITED_CARD_JUDGMENTS_CTES + " "
    ", impression_counts as ("
    "select pack_id, pack_version, authority_pack_revision, capability_id, "
    "capability_version, rule_id, "
    "count(*) as impressions from audited_impressions "
    "where occurred_at >= :since and pack_id=:p and pack_version=:pv "
    "and authority_pack_revision=:pr "
    "group by pack_id, pack_version, authority_pack_revision, capability_id, "
    "capability_version, rule_id), judgment_counts as ("
    "select pack_id, pack_version, authority_pack_revision, capability_id, "
    "capability_version, rule_id, "
    "count(*) filter (where cause='run_play') as run_play, "
    "count(*) filter (where cause='do_it_myself') as diy, "
    # PRESCRIBING CARDS ONLY IN THE PRECISION DENOMINATOR.
    #
    # `wrong:not_relevant` and `wrong:wrong_facts` are claims that the RECOMMENDATION was bad,
    # and a card at `review` or `observation` never made one — the first says only a person can
    # decide, the second says nothing needs doing. A human closing either has ANSWERED it, and
    # counting that as a precision failure made answering the system's own question evidence the
    # system was wrong.
    #
    # `card_level in ('prescriptive','predictive')` is `abstention.ACTIONABLE`, and a NULL level
    # is excluded rather than assumed: a card whose level nobody recorded is ungradeable, and
    # defaulting it to "instruction" is how the old behaviour comes back.
    # ⛔ THE DENOMINATOR IS BUILT FROM THE ATTRIBUTION MAP, AND WIDENING IT WAS NOT OPTIONAL.
    # This literal held two reasons. The vocabulary now has SIX that count against a rule
    # (`misread_source`, `wrong_subject`, `bad_link`, `bad_reasoning`, plus the two originals) and
    # five that do not. Leaving the literal at two would have let four real quality failures be
    # recorded by a founder and counted by nothing — the same absence in the other direction from
    # the one this milestone exists to fix, and the harder one to notice, because nothing breaks
    # and precision merely looks better than it is.
    "count(*) filter (where cause='wrong' and (detail->>'reason') "
    "in (" + _PRECISION_DENOMINATOR_SQL + ") "
    "and card_level in ('prescriptive','predictive')) as rel_wrong "
    "from canonical_judgments where occurred_at >= :since "
    "and pack_id=:p and pack_version=:pv and authority_pack_revision=:pr "
    "group by pack_id, pack_version, authority_pack_revision, capability_id, "
    "capability_version, rule_id), cohort as ("
    "select pack_id, pack_version, authority_pack_revision, capability_id, "
    "capability_version, rule_id from impression_counts union "
    "select pack_id, pack_version, authority_pack_revision, capability_id, "
    "capability_version, rule_id from judgment_counts) "
    "select cohort.pack_id, cohort.pack_version, cohort.authority_pack_revision, "
    "cohort.capability_id, cohort.capability_version, cohort.rule_id, "
    "coalesce(impressions.impressions,0) as impressions, "
    "coalesce(judgments.run_play,0) as run_play, "
    "coalesce(judgments.diy,0) as diy, "
    "coalesce(judgments.rel_wrong,0) as rel_wrong "
    "from cohort left join impression_counts impressions "
    "using (pack_id,pack_version,authority_pack_revision,capability_id,capability_version,rule_id) "
    "left join judgment_counts judgments "
    "using (pack_id,pack_version,authority_pack_revision,capability_id,capability_version,rule_id) "
    "order by cohort.capability_id, cohort.capability_version"
)


def _wilson_interval(wins: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = wins / n
    z2 = z * z
    center = p + z2 / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n)
    divisor = 1 + z2 / n
    return max(0.0, (center - margin) / divisor), min(1.0, (center + margin) / divisor)


def _pack_version(conn, org_id: str, pack_id: str, *, lock: bool = False):
    suffix = " for update" if lock else ""
    return conn.execute(text(
        "select version, state, lvl3_config, pins, authority_revision from tenant_packs "
        "where org_id=:o and pack_id=:p" + suffix),
        {"o": org_id, "p": pack_id}).first()


def _precision_rows(conn, org_id: str, pack_id: str, pack_version: str,
                    authority_revision: int, now: datetime) -> dict[str, dict]:
    since = now - timedelta(days=WINDOW_DAYS)
    out: dict[str, dict] = {}
    params = {"o": org_id, "p": pack_id, "pv": pack_version,
              "pr": authority_revision,
              "since": since, "as_of": now}
    for row in conn.execute(_PRECISION_SQL, params):
        wins = int(row.run_play) + int(row.diy)
        losses = int(row.rel_wrong)
        judgments = wins + losses
        precision = (wins / judgments) if judgments else None
        lower, upper = _wilson_interval(wins, judgments)
        key = f"{row.capability_id}@{row.capability_version}"
        out[key] = {
            "pack_id": row.pack_id,
            "pack_version": row.pack_version,
            "capability_id": row.capability_id,
            "capability_version": row.capability_version,
            "authority_revision": int(row.authority_pack_revision),
            "rule_id": row.rule_id,
            "impressions": int(row.impressions),
            "judgments": judgments,
            "run_play": int(row.run_play),
            "diy": int(row.diy),
            "rel_wrong": losses,
            "precision": precision,
            "precision_lb": lower,
            "precision_ub": upper,
            "eligible": judgments >= MIN_JUDGMENTS,
        }
    return out


def precision_28d(store, org_id: str, *, pack_id: str = "sales",
                  pack_version: str | None = None,
                  authority_revision: int | None = None,
                  eval_time: datetime | None = None) -> dict[str, dict]:
    """Exact-pack precision over the trailing 28 days.

    Impressions remain visible for coverage diagnostics. Eligibility and confidence are based
    only on labeled outcomes, so twelve ignored cards plus one click can never mute a rule.
    """
    now = authority_time(eval_time)
    with store.engine.connect() as conn:
        if pack_version is None or authority_revision is None:
            pack = _pack_version(conn, org_id, pack_id)
            if pack is None or pack.state != "active":
                return {}
            if pack_version is not None and str(pack.version) != pack_version:
                return {}
            pack_version = str(pack.version)
            authority_revision = int(pack.authority_revision)
        return _precision_rows(conn, org_id, pack_id, pack_version,
                               int(authority_revision), now)


def muted_rules(store, org_id: str, *, pack_id: str = "sales",
                pack_version: str | None = None) -> set[str]:
    with store.engine.connect() as conn:
        if pack_version is None:
            pack = _pack_version(conn, org_id, pack_id)
            if pack is None:
                return set()
            pack_version = str(pack.version)
        return {row.rule_id for row in conn.execute(text(
            "select rule_id from rule_mutes where org_id=:o and pack_id=:p "
            "and pack_version=:pv and active"),
            {"o": org_id, "p": pack_id, "pv": pack_version})}


def _week_start(now: datetime) -> datetime:
    utc = authority_time(now)
    return (utc - timedelta(days=utc.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)


def _json(value, default):
    if isinstance(value, type(default)):
        return value
    try:
        decoded = json.loads(value or ("{}" if isinstance(default, dict) else "[]"))
        return decoded if isinstance(decoded, type(default)) else default
    except (TypeError, ValueError):
        return default


def run_calibration(store, org_id: str, *, registry=None, pack_id: str = "sales",
                    eval_time: datetime | None = None, apply: bool = False) -> dict:
    """At most one atomic calibration for an exact pack version and UTC week.

    The tenant-pack row is the serialization lock. The run claim, mutes, learned config and
    nudge ledger share the same transaction; a crash therefore commits all of them or none.
    ``registry`` is retained only for API compatibility—the guarded SQL update is the sole write.

    ⛔ SHADOW UNLESS ``apply`` (STEP-18 B1). It has errored on every run since 2026-09-10, so it has
    never muted or nudged anything; the one-line fix that makes it run would, alone, have switched
    on unattended muting. So by default it scores every rule, records what it WOULD mute, recover
    and nudge (``would_*`` in ``calibration_runs.result``), claims the week, and writes nothing
    else: no ``rule_mutes``, no gate offset, no authority revision, no expired signal or card. The
    sweep passes ``apply`` from the tenant's ``calibration_apply`` L4 feature, which is never
    default-on (decision D13). A week claimed in shadow is not re-run when the feature is armed;
    the first applied run is the next week's.
    """
    del registry
    now = authority_time(eval_time)
    period_start = _week_start(now)
    with store.engine.begin() as conn:
        pack = _pack_version(conn, org_id, pack_id, lock=True)
        if pack is None or pack.state != "active":
            return {"org_id": org_id, "pack_id": pack_id, "applied": False,
                    "reason": "pack_not_active", "window_days": WINDOW_DAYS}
        pack_version = str(pack.version)
        authority_revision = int(pack.authority_revision)
        run_id = stable_id("calrun", {
            "org_id": org_id, "pack_id": pack_id,
            "pack_version": pack_version, "period_start": period_start,
        })
        claimed = conn.execute(text(
            "insert into calibration_runs "
            "(run_id,org_id,pack_id,pack_version,authority_revision,period_start,"
            "evaluation_time,status) "
            "values (:id,:o,:p,:pv,:pr,:period,:at,'started') "
            "on conflict (org_id,pack_id,pack_version,period_start) "
            "do nothing "
            "returning run_id"),
            {"id": run_id, "o": org_id, "p": pack_id, "pv": pack_version,
             "pr": authority_revision,
             "period": period_start, "at": now}).first()
        if claimed is None:
            prior = conn.execute(text(
                "select run_id, result from calibration_runs where org_id=:o and pack_id=:p "
                "and pack_version=:pv and period_start=:period"),
                {"o": org_id, "p": pack_id, "pv": pack_version,
                 "period": period_start}).first()
            result = _json(prior.result, {}) if prior is not None else {}
            return {**result, "org_id": org_id, "pack_id": pack_id,
                    "pack_version": pack_version,
                    "run_id": prior.run_id if prior is not None else run_id,
                    "applied": False, "already_ran": True,
                    "window_days": WINDOW_DAYS}

        lineage_stats = _precision_rows(
            conn, org_id, pack_id, pack_version, authority_revision, now)
        manifest_row = conn.execute(text(
            "select manifest from pack_registry where pack_id=:p and version=:pv"),
            {"p": pack_id, "pv": pack_version}).first()
        manifest = _json(manifest_row.manifest, {}) if manifest_row is not None else {}
        current_rules = {str(rule.get("id")) for rule in manifest.get("rules", [])
                         if isinstance(rule, dict) and rule.get("id")}
        by_rule: dict[str, list[dict]] = {}
        for value in lineage_stats.values():
            if value["rule_id"] in current_rules:
                by_rule.setdefault(value["rule_id"], []).append(value)
        stats: dict[str, dict] = {}
        ambiguous_lineages: list[str] = []
        for rule_id, variants in by_rule.items():
            if len(variants) == 1:
                stats[rule_id] = variants[0]
            else:
                # Never pool two materially distinct capability snapshots. A pack can opt into
                # transfer later with explicit compatibility metadata; absence means HOLD.
                ambiguous_lineages.append(rule_id)

        active_mutes = {row.rule_id for row in conn.execute(text(
            "select rule_id from rule_mutes where org_id=:o and pack_id=:p "
            "and pack_version=:pv and active"),
            {"o": org_id, "p": pack_id, "pv": pack_version})}
        muted: list[str] = []
        recovered: list[str] = []
        audit_rows: list[dict] = []

        for rule_id, stat in stats.items():
            p = stat["precision"]
            judgments = stat["judgments"]
            harmful = (p is not None and judgments >= MUTE_MIN_JUDGMENTS
                       and stat["precision_ub"] < MUTE_PRECISION)
            recovered_enough = (p is not None and judgments >= MIN_JUDGMENTS
                                and stat["precision_lb"] >= MUTE_PRECISION)
            values = {"o": org_id, "p": pack_id, "pv": pack_version, "r": rule_id,
                      "precision": p, "lb": stat["precision_lb"],
                      "ub": stat["precision_ub"], "i": stat["impressions"],
                      "j": judgments, "pr": authority_revision,
                      "cap": stat["capability_id"], "capv": stat["capability_version"]}
            if harmful and rule_id not in active_mutes:
                if apply:
                    conn.execute(text(
                        "insert into rule_mutes "
                        "(org_id,pack_id,pack_version,rule_id,active,reason,precision,"
                        "precision_lb,precision_ub,impressions,judgments,source_authority_revision,"
                        "source_capability_id,source_capability_version) "
                        "values (:o,:p,:pv,:r,true,'low_precision',:precision,:lb,:ub,:i,:j,"
                        ":pr,:cap,:capv) "
                        "on conflict (org_id,pack_id,pack_version,rule_id) do update set "
                        "active=true,reason='low_precision',precision=:precision,precision_lb=:lb,"
                        "precision_ub=:ub,impressions=:i,judgments=:j,"
                        "source_authority_revision=:pr,source_capability_id=:cap,"
                        "source_capability_version=:capv,muted_at=clock_timestamp()"),
                        values)
                active_mutes.add(rule_id)
                muted.append(rule_id)
                audit_rows.append({"rule_id": rule_id, "param": "rule.mute",
                                   "direction": "mute", "before": 0, "after": 1,
                                   "stat": stat})
            elif rule_id in active_mutes and recovered_enough:
                if apply:
                    conn.execute(text(
                        "update rule_mutes set active=false,precision=:precision,"
                        "precision_lb=:lb,precision_ub=:ub,impressions=:i,judgments=:j "
                        "where org_id=:o and pack_id=:p and pack_version=:pv and rule_id=:r"),
                        values)
                active_mutes.remove(rule_id)
                recovered.append(rule_id)
                audit_rows.append({"rule_id": rule_id, "param": "rule.mute",
                                   "direction": "unmute", "before": 1, "after": 0,
                                   "stat": stat})

        lvl3 = _json(pack.lvl3_config, {})
        pins = _json(pack.pins, [])
        offsets = dict(((lvl3.get("scoring_defaults") or {}).get("rule_offsets") or {}))
        offset_path_pinned = any(str(pin).startswith("scoring_defaults.rule_offsets")
                                 for pin in pins)
        nudges: list[dict] = []
        if not offset_path_pinned:
            for rule_id, stat in stats.items():
                p = stat["precision"]
                if not stat["eligible"] or p is None or rule_id in active_mutes:
                    continue
                if stat["precision_lb"] >= LOOSEN_ABOVE:
                    delta, direction = -OFFSET_STEP, "loosen"
                elif stat["precision_ub"] < TIGHTEN_BELOW:
                    delta, direction = OFFSET_STEP, "tighten"
                else:
                    continue
                current = int(offsets.get(rule_id, 0))
                updated = max(-OFFSET_BOUND, min(OFFSET_BOUND, current + delta))
                if updated == current:
                    continue
                offsets[rule_id] = updated
                nudges.append({"rule_id": rule_id, "before": current, "after": updated,
                               "direction": direction, "precision": round(p, 3)})
                audit_rows.append({"rule_id": rule_id, "param": "gate.s_min",
                                   "direction": direction, "before": current,
                                   "after": updated, "stat": stat})

        if nudges:
            scoring = dict(lvl3.get("scoring_defaults") or {})
            scoring["rule_offsets"] = offsets
            lvl3["scoring_defaults"] = scoring
        new_authority_revision = authority_revision
        if apply and audit_rows:
            bumped = conn.execute(text(
                "update tenant_packs set lvl3_config=cast(:cfg as jsonb), "
                "authority_revision=authority_revision+1,updated_at=clock_timestamp() "
                "where org_id=:o and pack_id=:p and version=:pv "
                "and authority_revision=:pr returning authority_revision"),
                {"cfg": json.dumps(lvl3, sort_keys=True, separators=(",", ":")),
                 "o": org_id, "p": pack_id, "pv": pack_version,
                 "pr": authority_revision}).first()
            if bumped is None:
                raise RuntimeError("tenant pack authority changed while calibration row was locked")
            new_authority_revision = int(bumped.authority_revision)
        if apply and muted:
            # A newly harmful rule must stop being actionable in the same commit as its mute.
            # The pack epoch bump revokes every old projection; explicit lifecycle closure makes
            # that revocation visible even to historical/non-authority UI surfaces.
            signal_ids = [row.signal_id for row in conn.execute(text(
                "select signal_id from signals where org_id=:o and pack_id=:p "
                "and pack_version=:pv and rule_id=any(:rules) and status='open'"),
                {"o": org_id, "p": pack_id, "pv": pack_version,
                 "rules": muted}).fetchall()]
            if signal_ids:
                # STEP-06: a muted rule's cards leave saying so (`06` D13: only on an armed tenant).
                card_lifecycle.expire_cards(conn, org_id=org_id, cause=card_lifecycle.RULE_MUTED,
                                            signal_ids=signal_ids)
                conn.execute(text(
                    "update signals set status='expired' where org_id=:o "
                    "and signal_id=any(:ids) and status='open'"),
                    {"o": org_id, "ids": signal_ids})

        for item in (audit_rows if apply else ()):
            stat = item["stat"]
            nudge_id = stable_id("nudge", {
                "run_id": run_id, "rule_id": item["rule_id"], "param": item["param"]})
            conn.execute(text(
                "insert into calibration_nudges "
                "(id,org_id,pack_id,pack_version,rule_id,param,before_val,after_val,"
                "offset_cumulative,direction,precision,precision_lb,precision_ub,impressions,"
                "judgments,calibration_run_id,period_start,authority_revision) "
                "values (:id,:o,:p,:pv,:r,:param,:before,:after,:after,:direction,:precision,"
                ":lb,:ub,:i,:j,:run,:period,:pr)"),
                {"id": nudge_id, "o": org_id, "p": pack_id, "pv": pack_version,
                 "r": item["rule_id"], "param": item["param"],
                 "before": item["before"], "after": item["after"],
                 "direction": item["direction"], "precision": stat["precision"],
                 "lb": stat["precision_lb"], "ub": stat["precision_ub"],
                 "i": stat["impressions"], "j": stat["judgments"],
                 "run": run_id, "period": period_start, "pr": authority_revision})

        # In shadow the would_* lists are the whole output: nothing above wrote them anywhere.
        result = {"org_id": org_id, "pack_id": pack_id, "pack_version": pack_version,
                  "mode": "apply" if apply else "shadow",
                  "source_authority_revision": authority_revision,
                  "resulting_authority_revision": new_authority_revision,
                  "run_id": run_id, "period_start": period_start.isoformat(),
                  "rules_scored": len(stats),
                  "muted": muted if apply else [], "recovered": recovered if apply else [],
                  "nudges": nudges if apply else [],
                  "would_mute": muted, "would_recover": recovered, "would_nudge": nudges,
                  "ambiguous_lineages_held": sorted(ambiguous_lineages),
                  "applied": apply, "already_ran": False,
                  "window_days": WINDOW_DAYS}
        conn.execute(text(
            "update calibration_runs set status='completed',result=cast(:result as jsonb),"
            "completed_at=clock_timestamp() where run_id=:id"),
            {"id": run_id,
             "result": json.dumps(result, sort_keys=True, separators=(",", ":"))})
        return result


__all__ = [
    "MIN_JUDGMENTS", "MUTE_MIN_JUDGMENTS", "MUTE_PRECISION", "OFFSET_BOUND",
    "OFFSET_STEP", "TAXONOMY", "WINDOW_DAYS", "_PRECISION_SQL", "muted_rules",
    "precision_28d", "run_calibration",
]
