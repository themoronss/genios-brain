"""
Phase 6: Proactive Intelligence — the scanner.

Per L2 spec: GeniOS fires without asking. No agent called anything.
Every 6h (and on new data events), the scanner:

1. Runs L5 anomaly detection (reuses anomaly_scanner)
2. For each active anomaly, runs L6 root cause analysis
3. Judge step (Phase 1 / Item #2): LLM decides keep vs. dismiss
   so we don't notify on every detector hit
4. Predictive cold window (Phase 1 / Item #5) + channel
   recommendation (Phase 1 / Item #6) attached to root_cause_data
5. Runs L7 synthesis (LLM generates memory_view + genios_view,
   validated against the strict insight_schema — Phase 1 / Item #4)
6. Stores insight in `insights` table (with judge verdict, predictive
   fields, channel)
7. Delivers via webhook (Phase 6.3)

Credits: 0 (included in Startup plan, per L2 spec).
"""
import json
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import text
from app.database import SessionLocal
from app.graph.baselines import predict_cold_window
from app.graph.channels import get_contact_channel_profile, channel_action_verb
from app.brain.prompts.judge import JUDGE_SYSTEM, JUDGE_USER_TEMPLATE
from app.brain.prompts.insight_schema import InsightOutput

logger = logging.getLogger(__name__)


def _compute_priority(
    anomaly_type: str,
    confidence_score: float,
    relationship_stage: str | None,
    open_commitments: int,
    days_since_last: int | None,
) -> str:
    """Dynamic insight priority — closes the outcome → priority loop.

    confidence_score is fed from context_outcomes by confidence_updater, so a
    brain that has been right about this contact promotes its own future
    alerts; one that has been wrong demotes them.
    """
    base = {"gone_silent": 3, "sentiment_drop": 3, "engagement_drop": 2, "response_slowdown": 1}.get(anomaly_type, 2)
    if confidence_score >= 0.7:
        base += 1
    elif confidence_score < 0.3:
        base -= 1
    stage = (relationship_stage or "").upper()
    if stage in ("NEEDS_ATTENTION", "AT_RISK"):
        base += 1
    elif stage in ("DORMANT", "COLD"):
        base -= 1
    if open_commitments and open_commitments >= 2:
        base += 1
    if days_since_last and days_since_last > 90:
        base -= 1
    if base >= 4:
        return "high"
    return "medium" if base >= 2 else "low"


# ── Judge step (Item #2) ─────────────────────────────────────────────────
_VALID_VERDICTS = {
    "keep",
    "dismiss_low_signal",
    "dismiss_stale",
    "dismiss_pattern_match",
    "dismiss_one_way_pattern",
}


def _judge_insight(judge_context: dict, org_id: str | None = None) -> dict:
    """LLM-based keep/dismiss decision for a detected anomaly.

    Fallback (non-negotiable): on any failure return keep=true with
    verdict='judge_unavailable' so we degrade to the previous
    "notify everything" behavior rather than silently losing alerts.
    """
    try:
        from app.llm import llm_client
        raw = llm_client.call(
            org_id=org_id,
            purpose="judge_insight",
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user",   "content": JUDGE_USER_TEMPLATE.format(
                    context_json=json.dumps(judge_context, indent=2, default=str),
                )},
            ],
            temperature=0.0,
            max_tokens=256,
        )
        parsed = _parse_json_block(raw)
        if parsed is None:
            raise ValueError("judge returned non-JSON output")

        verdict = str(parsed.get("verdict", "")).strip().lower()
        if verdict not in _VALID_VERDICTS:
            raise ValueError(f"judge returned unknown verdict: {verdict!r}")

        try:
            confidence = float(parsed.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        keep = bool(parsed.get("keep", verdict == "keep"))
        reasoning = str(parsed.get("reasoning", ""))[:600]
        return {"keep": keep, "verdict": verdict, "confidence": confidence, "reasoning": reasoning}
    except Exception as e:
        logger.info(f"judge unavailable, defaulting to keep: {e}")
        return {
            "keep": True,
            "verdict": "judge_unavailable",
            "confidence": 0.5,
            "reasoning": "judge_unavailable",
        }


def _parse_json_block(raw: str) -> dict | None:
    """Strip markdown fences + extract first {...} JSON object."""
    if not raw:
        return None
    s = raw.strip()
    if s.startswith("```"):
        parts = s.split("```")
        if len(parts) >= 3:
            s = parts[1]
        else:
            s = parts[-1]
        if s.lstrip().startswith("json"):
            s = s.lstrip()[4:]
    s = s.strip()
    if not s.startswith("{"):
        lo, hi = s.find("{"), s.rfind("}")
        if lo >= 0 and hi > lo:
            s = s[lo:hi + 1]
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None


def _generate_insight_text(
    anomaly: dict, contact: dict, precedents: list, org_id: str | None = None,
) -> dict:
    """
    L7 Synthesis: generate memory_view + genios_view from structured data.

    LLM does NOT generate intelligence — it formats intelligence the
    detectors and the judge have already produced. One retry with stricter
    instructions on parse failure; final fallback is a deterministic,
    contact-specific message (Item #4: never the old generic
    "Review this contact" string).
    """
    root_cause_data = {
        "contact_name": contact.get("name", "Unknown"),
        "company": contact.get("company"),
        "relationship_stage": contact.get("relationship_stage"),
        "anomaly_type": anomaly.get("anomaly_type"),
        "anomaly_summary": anomaly.get("summary"),
        "engagement_z": anomaly.get("engagement_z"),
        "sentiment_z": anomaly.get("sentiment_z"),
        "days_since_last": contact.get("days_since_last"),
        "precedent_count": len(precedents),
        "precedent_success_rate": precedents[0].get("success_rate") if precedents else None,
        "best_historical_action": precedents[0].get("action_taken") if precedents else None,
        "open_commitments": contact.get("open_commitments", 0),
        "predicted_cold_in_days": contact.get("predicted_cold_in_days"),
        "recommended_channel": contact.get("recommended_channel"),
        "channel_reason": contact.get("channel_reason"),
    }

    base_prompt = f"""You are formatting a relationship intelligence insight. The analysis is already done — you are converting structured data into two readable views.

Structured data:
{json.dumps(root_cause_data, indent=2, default=str)}

Generate TWO views:

1. memory_view: ONE sentence (<= 240 chars). Just the raw fact. What the data shows.
   Example: "No response from Priya in 28 days."

2. genios_view: 2-3 sentences (<= 600 chars). The analyzed insight WITH a specific action recommendation.
   - If `recommended_channel` is provided, prefix the action with that channel verb (e.g. "Call her this week", "DM him in Slack").
   - If `predicted_cold_in_days` is provided and < 14, mention the window explicitly (e.g. "You have ~4 days before cold").
   - If `best_historical_action` exists, reference what worked last time.
   - Every sentence must reference the actual data. No generic advice.

Return ONLY valid JSON, no markdown:
{{"memory_view": "...", "genios_view": "..."}}"""

    prompt = base_prompt
    last_error: Exception | None = None

    for attempt in (1, 2):
        try:
            from app.llm import llm_client
            raw = llm_client.call(
                org_id=org_id, purpose="narrative",
                prompt=prompt, temperature=0.2, max_tokens=512,
            )
            parsed = _parse_json_block(raw)
            if parsed is None:
                raise ValueError("narrative LLM returned non-JSON")
            validated = InsightOutput(**parsed)
            return validated.model_dump()
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            last_error = e
            if attempt == 1:
                logger.info(f"insight parse failed (attempt 1), retrying: {e}")
                prompt = base_prompt + (
                    "\n\nIMPORTANT: Return ONLY valid JSON matching the exact "
                    "schema. genios_view MUST end with a specific action "
                    "(verb + who + when). memory_view MUST be one short sentence."
                )
                continue
            break
        except Exception as e:
            # Provider error (rate limit etc.) — llm_client already handled
            # provider fallback internally; if it still failed, we use the
            # structured fallback.
            last_error = e
            break

    logger.warning(f"insight gen failed after retries: {last_error}")
    return _structured_fallback(anomaly, contact)


def _structured_fallback(anomaly: dict, contact: dict) -> dict:
    """Contact-specific fallback when LLM output is unusable (Item #4).

    Replaces the old generic 'Review this contact' string with something
    that references the actual contact + anomaly so the customer still
    gets a usable signal.
    """
    name = contact.get("name") or "this contact"
    atype = (anomaly.get("anomaly_type") or "anomaly").replace("_", " ")
    days = contact.get("days_since_last")
    days_str = f"{days} days" if days else "an unusual period"

    cold_in = contact.get("predicted_cold_in_days")
    channel = contact.get("recommended_channel")
    verb = channel_action_verb(channel) if channel else "Reach out to"

    memory_view = f"{name}: {atype} pattern detected ({days_str} since last interaction)."

    action_map = {
        "gone_silent": f"{verb} {name} on the channel they last replied to.",
        "engagement_drop": f"{verb} {name} with a value-led check-in, not a status request.",
        "sentiment_drop": f"{verb} {name} to address concerns directly before they harden.",
        "response_slowdown": f"{verb} {name} with a specific, low-effort ask.",
    }
    action = action_map.get(
        anomaly.get("anomaly_type"),
        f"{verb} {name} about the recent change in interaction pattern.",
    )

    cold_str = ""
    if cold_in is not None and cold_in < 14:
        cold_str = f" You have ~{cold_in} days before cold."

    genios_view = f"{name} is showing signs of {atype}.{cold_str} {action}"

    # Ensure length bounds.
    return {
        "memory_view": memory_view[:240],
        "genios_view": genios_view[:600],
    }


def run_proactive_scan(org_id: str = None):
    """
    Full proactive scan: anomalies → judge → predictive enrichment → synthesis
    → store insights.

    Per L2 spec: runs every 6h via Celery Beat.
    For Startup plan only (hustler gets reactive only).
    """
    db = SessionLocal()
    try:
        # Step 1: Run anomaly detection (reuse Phase 4)
        from app.tasks.anomaly_scanner import run_anomaly_scan
        anomaly_result = run_anomaly_scan(org_id)
        logger.info(f"Anomaly scan: {anomaly_result}")

        # Step 2: Get all active anomalies that don't have insights yet
        where = "ca.status = 'active'"
        params = {}
        if org_id:
            where += " AND ca.org_id = :org_id"
            params["org_id"] = org_id

        anomalies = db.execute(
            text(f"""
                SELECT ca.id, ca.contact_id, ca.org_id, ca.anomaly_type,
                       ca.engagement_z, ca.sentiment_z, ca.deviation_score,
                       ca.summary,
                       c.name, c.email, c.company, c.relationship_stage,
                       c.entity_type, c.sentiment_ewma, c.sentiment_trend,
                       c.last_interaction_at, c.interaction_count,
                       COALESCE(c.confidence_score, 0.5) AS confidence_score,
                       (SELECT COUNT(*) FROM commitments cm
                        WHERE cm.contact_id = ca.contact_id AND cm.status = 'OPEN'
                       ) AS open_commitments
                FROM contact_anomalies ca
                JOIN contacts c ON ca.contact_id = c.id
                WHERE {where}
                  AND NOT EXISTS (
                      SELECT 1 FROM insights i
                      WHERE i.anomaly_id = ca.id AND i.is_dismissed = FALSE
                  )
                  -- Brain learning: if the user has dismissed >= 2 insights for
                  -- this (contact, anomaly_type) pair within the last 30 days,
                  -- mute it for the cooldown period. The brain treats repeated
                  -- dismissal as a signal that this alert is noise to this user.
                  AND COALESCE((
                      SELECT COUNT(*) FROM insights di
                      JOIN contact_anomalies dca ON di.anomaly_id = dca.id
                      WHERE di.contact_id = ca.contact_id
                        AND dca.anomaly_type = ca.anomaly_type
                        AND di.is_dismissed = TRUE
                        AND di.generated_at > NOW() - INTERVAL '30 days'
                  ), 0) < 2
                  -- Brain judgment: one-way senders (newsletters that got past
                  -- the broadcast filter, e.g. niche programs) shouldn't fire
                  -- relationship-cooling insights — silence is normal there.
                  AND (c.is_bidirectional IS TRUE OR ca.anomaly_type NOT IN ('gone_silent', 'engagement_drop'))
                ORDER BY ca.deviation_score DESC
                LIMIT 20
            """),
            params,
        ).fetchall()

        if not anomalies:
            logger.info("No new anomalies to generate insights for.")
            return {"anomalies": anomaly_result, "insights_generated": 0, "dismissed_by_judge": 0}

        insights_created = 0
        dismissed_by_judge = 0

        for anomaly in anomalies:
            # Step 3: L6 — find precedent matches for this contact
            try:
                from app.graph.fingerprint import build_fingerprint, match_precedents
                contact_data = {
                    "relationship_stage": anomaly.relationship_stage,
                    "entity_type": anomaly.entity_type,
                    "sentiment_ewma": float(anomaly.sentiment_ewma or 0),
                    "sentiment_trend": anomaly.sentiment_trend,
                    "last_interaction_at": anomaly.last_interaction_at,
                }
                fp = build_fingerprint(contact_data)
                precedents = match_precedents(db, str(anomaly.org_id), fp)
            except Exception:
                precedents = []

            # Compute days_since_last once — used by judge + synthesis + cold.
            days_since = None
            if anomaly.last_interaction_at:
                last_at = anomaly.last_interaction_at
                if hasattr(last_at, "tzinfo") and last_at.tzinfo is None:
                    last_at = last_at.replace(tzinfo=timezone.utc)
                days_since = (datetime.now(timezone.utc) - last_at).days

            # Step 4 (Item #5): predict cold window from baselines.
            predicted_cold_in_days = predict_cold_window(
                db, str(anomaly.org_id), str(anomaly.contact_id), days_since or 0,
            ) if days_since is not None else None

            # Step 5 (Item #6): channel recommendation from interaction history.
            channel_profile = get_contact_channel_profile(str(anomaly.contact_id), db)
            recommended_channel = channel_profile.get("recommended")
            channel_reason = channel_profile.get("reason")

            # Step 6 (Item #2): judge keep/dismiss BEFORE running narrative LLM.
            judge_context = {
                "contact_name": anomaly.name,
                "company": anomaly.company,
                "entity_type": anomaly.entity_type,
                "relationship_stage": anomaly.relationship_stage,
                "interaction_count": int(anomaly.interaction_count or 0),
                "sentiment_ewma": float(anomaly.sentiment_ewma or 0),
                "anomaly_type": anomaly.anomaly_type,
                "anomaly_summary": anomaly.summary,
                "engagement_z": float(anomaly.engagement_z or 0),
                "sentiment_z": float(anomaly.sentiment_z or 0),
                "deviation_score": float(anomaly.deviation_score or 0),
                "days_since_last": days_since,
                "open_commitments": int(anomaly.open_commitments or 0),
                "precedent_count": len(precedents),
                "precedent_best_action": precedents[0].get("action_taken") if precedents else None,
                "precedent_success_rate": precedents[0].get("success_rate") if precedents else None,
                "predicted_cold_in_days": predicted_cold_in_days,
                "recommended_channel": recommended_channel,
            }
            verdict = _judge_insight(judge_context, org_id=str(anomaly.org_id))

            if not verdict["keep"]:
                dismissed_by_judge += 1
                logger.info(
                    f"judge DISMISSED insight contact={anomaly.name} type={anomaly.anomaly_type} "
                    f"verdict={verdict['verdict']} conf={verdict['confidence']}: {verdict['reasoning']}"
                )
                # Audit trail: record the dismissed insight so it shows in
                # superadmin tooling, but mark is_dismissed=TRUE so the
                # webhook delivery never fires for it.
                try:
                    db.execute(
                        text("""
                            INSERT INTO insights
                                (id, org_id, insight_type, priority, category,
                                 title, detail, contact_id, contact_name,
                                 memory_view, genios_view,
                                 anomaly_id, source_type, delivery_status,
                                 generated_at, is_dismissed,
                                 judge_verdict, judge_confidence, judge_reasoning,
                                 predicted_cold_in_days, recommended_channel,
                                 recommended_channel_reason)
                            VALUES
                                (:id, :oid, 'anomaly', 'low', :category,
                                 :title, :detail, :cid, :cname,
                                 :memory_view, :genios_view,
                                 :anomaly_id, 'proactive', 'dismissed_by_judge',
                                 NOW(), TRUE,
                                 :verdict, :conf, :reasoning,
                                 :cold, :channel, :channel_reason)
                        """),
                        {
                            "id": str(uuid4()),
                            "oid": str(anomaly.org_id),
                            "category": _category_for_anomaly(anomaly.anomaly_type),
                            "title": f"{anomaly.name}: {anomaly.anomaly_type.replace('_', ' ')} (dismissed)",
                            "detail": verdict["reasoning"],
                            "cid": str(anomaly.contact_id),
                            "cname": anomaly.name,
                            "memory_view": anomaly.summary or "",
                            "genios_view": verdict["reasoning"],
                            "anomaly_id": str(anomaly.id),
                            "verdict": verdict["verdict"],
                            "conf": verdict["confidence"],
                            "reasoning": verdict["reasoning"],
                            "cold": predicted_cold_in_days,
                            "channel": recommended_channel,
                            "channel_reason": channel_reason,
                        },
                    )
                    db.commit()
                except Exception as e:
                    db.rollback()
                    logger.warning(f"Failed to persist dismissed insight for {anomaly.name}: {e}")
                continue

            # Step 7: L7 — synthesize insight text (with predictive context).
            insight_text = _generate_insight_text(
                anomaly={
                    "anomaly_type": anomaly.anomaly_type,
                    "summary": anomaly.summary,
                    "engagement_z": float(anomaly.engagement_z or 0),
                    "sentiment_z": float(anomaly.sentiment_z or 0),
                },
                contact={
                    "name": anomaly.name,
                    "company": anomaly.company,
                    "relationship_stage": anomaly.relationship_stage,
                    "days_since_last": days_since,
                    "open_commitments": anomaly.open_commitments or 0,
                    "predicted_cold_in_days": predicted_cold_in_days,
                    "recommended_channel": recommended_channel,
                    "channel_reason": channel_reason,
                },
                precedents=precedents,
                org_id=str(anomaly.org_id),
            )

            # Step 8: Store insight (with judge + predictive + channel fields).
            try:
                insight_id = str(uuid4())
                priority = _compute_priority(
                    anomaly_type=anomaly.anomaly_type,
                    confidence_score=float(anomaly.confidence_score or 0.5),
                    relationship_stage=anomaly.relationship_stage,
                    open_commitments=int(anomaly.open_commitments or 0),
                    days_since_last=days_since,
                )

                db.execute(
                    text("""
                        INSERT INTO insights
                            (id, org_id, insight_type, priority, category,
                             title, detail, contact_id, contact_name,
                             memory_view, genios_view,
                             anomaly_id, source_type, delivery_status,
                             generated_at, is_dismissed,
                             judge_verdict, judge_confidence, judge_reasoning,
                             predicted_cold_in_days, recommended_channel,
                             recommended_channel_reason)
                        VALUES
                            (:id, :oid, 'anomaly', :priority, :category,
                             :title, :detail, :cid, :cname,
                             :memory_view, :genios_view,
                             :anomaly_id, 'proactive', 'pending',
                             NOW(), FALSE,
                             :verdict, :conf, :reasoning,
                             :cold, :channel, :channel_reason)
                    """),
                    {
                        "id": insight_id,
                        "oid": str(anomaly.org_id),
                        "priority": priority,
                        "category": _category_for_anomaly(anomaly.anomaly_type),
                        "title": f"{anomaly.name}: {anomaly.anomaly_type.replace('_', ' ')}",
                        "detail": insight_text["genios_view"],
                        "cid": str(anomaly.contact_id),
                        "cname": anomaly.name,
                        "memory_view": insight_text["memory_view"],
                        "genios_view": insight_text["genios_view"],
                        "anomaly_id": str(anomaly.id),
                        "verdict": verdict["verdict"],
                        "conf": verdict["confidence"],
                        "reasoning": verdict["reasoning"],
                        "cold": predicted_cold_in_days,
                        "channel": recommended_channel,
                        "channel_reason": channel_reason,
                    },
                )
                db.commit()
                insights_created += 1
            except Exception as e:
                db.rollback()
                logger.warning(f"Failed to store insight for {anomaly.name}: {e}")

        logger.info(
            f"Proactive scan: {insights_created} insights generated, "
            f"{dismissed_by_judge} dismissed by judge, "
            f"from {len(anomalies)} candidate anomalies"
        )
        return {
            "anomalies": anomaly_result,
            "insights_generated": insights_created,
            "dismissed_by_judge": dismissed_by_judge,
        }
    finally:
        db.close()


def _category_for_anomaly(anomaly_type: str | None) -> str:
    """Map anomaly type → insight category enum used by webhook payload."""
    return {
        "gone_silent": "relationship_cooling",
        "engagement_drop": "engagement_risk",
        "sentiment_drop": "sentiment_alert",
        "response_slowdown": "response_risk",
    }.get(anomaly_type or "", "other")
