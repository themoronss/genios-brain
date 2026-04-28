"""
Week 3: Context Bundle Builder
Builds rich context bundles for any entity in the relationship graph
"""

from sqlalchemy import text
from datetime import datetime, timezone
from typing import Dict, List, Optional
from rapidfuzz import process, fuzz

from app.tunables import (
    broadcast_local_regex,
    broadcast_domain_regex,
    BROADCAST_MIN_ONEWAY_COUNT,
)


# Cache compiled regexes at import. Change env → restart process.
_BROADCAST_LOCAL = broadcast_local_regex()
_BROADCAST_DOMAIN = broadcast_domain_regex()


def _is_broadcast_address(email: str) -> bool:
    """Address-pattern check. See app/tunables.py for the configurable lists."""
    if not email:
        return False
    email = email.lower()
    return bool(_BROADCAST_LOCAL.search(email) or _BROADCAST_DOMAIN.search(email))


def _row_to_dict(result) -> Dict:
    return {
        "id": result[0],
        "name": result[1],
        "email": result[2],
        "company": result[3],
        "relationship_stage": result[4],
        "sentiment_avg": result[5],
        "last_interaction_at": result[6],
        "first_interaction_at": result[7],
        "interaction_count": result[8],
        "topics_aggregate": result[9] or [],
        "communication_style": result[10],
        "entity_type": result[11],
        "freshness_score": result[12] if len(result) > 12 else None,
        "confidence_score": result[13] if len(result) > 13 else 0.5,
        "consistency_score": result[14] if len(result) > 14 else 0.5,
        "authority_score": result[15] if len(result) > 15 else 0.5,
        "context_score": result[16] if len(result) > 16 else 0.5,
        "sentiment_ewma": result[17] if len(result) > 17 else 0.0,
        "sentiment_trend": result[18] if len(result) > 18 else "STABLE",
        "response_rate": result[19] if len(result) > 19 else None,
        "avg_response_time_hours": result[20] if len(result) > 20 else None,
        "is_bidirectional": result[21] if len(result) > 21 else False,
        "what_works": result[22] if len(result) > 22 else None,
        "what_to_avoid": result[23] if len(result) > 23 else None,
        "introduced_by": result[24] if len(result) > 24 else None,
        "is_archived": result[25] if len(result) > 25 else False,
        "relationship_summary": result[26] if len(result) > 26 else None,
        "stage_changed_at": result[27] if len(result) > 27 else None,
        "previous_stage": result[28] if len(result) > 28 else None,
        "tags": list(result[29]) if len(result) > 29 and result[29] else [],
        "disclosure_level": result[30] if len(result) > 30 else "public",
        "restricted_to_agents": list(result[31]) if len(result) > 31 and result[31] else [],
    }


_FULL_CONTACT_COLS = """
    id, name, email, company, relationship_stage,
    sentiment_avg, last_interaction_at, first_interaction_at,
    interaction_count, topics_aggregate, communication_style,
    entity_type, freshness_score, confidence_score,
    consistency_score, authority_score, context_score,
    sentiment_ewma, sentiment_trend, response_rate,
    avg_response_time_hours, is_bidirectional,
    what_works, what_to_avoid, introduced_by,
    is_archived, relationship_summary, stage_changed_at,
    previous_stage, tags, disclosure_level, restricted_to_agents
"""


def _fetch_full_contact(db, contact_id: str, org_id: str) -> Optional[Dict]:
    """Fetch full contact row by ID."""
    result = db.execute(
        text(f"SELECT {_FULL_CONTACT_COLS} FROM contacts WHERE id = :id AND org_id = :org_id"),
        {"id": contact_id, "org_id": org_id},
    ).fetchone()
    return _row_to_dict(result) if result else None


def get_contact_by_name(db, org_id: str, entity_name: str) -> Optional[Dict]:
    """
    6-tier entity resolution pipeline (ordered by precision):
      1. Email exact match → confidence 1.0
      2. Name/email exact match → confidence 1.0
      3. Email domain + name fuzzy (>70%) → confidence 0.9
      4. Name exact + company fuzzy (>80%) → confidence 0.85
      5. Name fuzzy >85% → confidence = score/100
      6. Name fuzzy 70-85% → confidence 0.5 (let agent decide)
    Never auto-merges below 0.85 without an email anchor.
    """
    try:
        # ── Tier 1: Exact email match (ground truth) ────────────────────
        if "@" in entity_name:
            result = db.execute(
                text(f"""
                    SELECT {_FULL_CONTACT_COLS} FROM contacts
                    WHERE org_id = :org_id AND LOWER(email) = LOWER(:email)
                    LIMIT 1
                """),
                {"org_id": org_id, "email": entity_name.strip()},
            ).fetchone()
            if result:
                res = _row_to_dict(result)
                res["match_confidence"] = 1.0
                res["matched_from"] = entity_name
                res["resolution_method"] = "email_exact"
                return res

        # ── Tier 2: Name or email pattern exact match ───────────────────
        result = db.execute(
            text(f"""
                SELECT {_FULL_CONTACT_COLS} FROM contacts
                WHERE org_id = :org_id
                AND (TRIM(LOWER(name)) = TRIM(LOWER(:name)) OR LOWER(email) LIKE LOWER(:email_pattern))
                LIMIT 1
            """),
            {
                "org_id": org_id,
                "name": entity_name,
                "email_pattern": f"%{entity_name.lower()}%",
            },
        ).fetchone()

        if result:
            res = _row_to_dict(result)
            res["match_confidence"] = 1.0
            res["matched_from"] = entity_name
            res["resolution_method"] = "name_exact"
            return res

        # ── Fetch all candidates for fuzzy tiers ────────────────────────
        candidates = db.execute(
            text("SELECT id, name, email, company FROM contacts WHERE org_id = :org_id"),
            {"org_id": org_id},
        ).fetchall()

        if not candidates:
            return None

        # ── Tier 3: Email domain + name fuzzy (>70%) → confidence 0.9 ──
        # If entity_name looks like a name (not email), check if any contact
        # shares an email domain AND has a fuzzy name match
        if "@" not in entity_name:
            # Group candidates by email domain
            domain_groups = {}
            for row in candidates:
                if row[2] and "@" in row[2]:
                    domain = row[2].split("@")[1].lower()
                    domain_groups.setdefault(domain, []).append(row)

            for domain, group in domain_groups.items():
                name_choices = {str(r[0]): r[1] for r in group if r[1]}
                if name_choices:
                    match = process.extractOne(
                        entity_name, name_choices, scorer=fuzz.WRatio, score_cutoff=70.0
                    )
                    if match:
                        contact = _fetch_full_contact(db, match[2], org_id)
                        if contact:
                            contact["match_confidence"] = 0.9
                            contact["matched_from"] = entity_name
                            contact["resolution_method"] = "email_domain_name_fuzzy"
                            return contact

        # ── Tier 4: Name exact + company fuzzy (>80%) → confidence 0.85 ──
        name_exact_candidates = [r for r in candidates if r[1] and r[1].strip().lower() == entity_name.strip().lower()]
        if not name_exact_candidates and len(entity_name.split()) >= 2:
            # Try first+last name partial match
            parts = entity_name.strip().lower().split()
            name_exact_candidates = [
                r for r in candidates
                if r[1] and all(p in r[1].lower() for p in parts)
            ]
        if name_exact_candidates and len(name_exact_candidates) > 1:
            # Multiple exact name matches — use company to disambiguate
            company_choices = {str(r[0]): r[3] for r in name_exact_candidates if r[3]}
            if company_choices:
                company_match = process.extractOne(
                    entity_name, company_choices, scorer=fuzz.WRatio, score_cutoff=80.0
                )
                if company_match:
                    contact = _fetch_full_contact(db, company_match[2], org_id)
                    if contact:
                        contact["match_confidence"] = 0.85
                        contact["matched_from"] = entity_name
                        contact["resolution_method"] = "name_exact_company_fuzzy"
                        return contact

        # ── Tier 5 & 6: Name fuzzy matching ─────────────────────────────
        choices = {str(row[0]): row[1] for row in candidates if row[1]}
        best_name = process.extractOne(
            entity_name, choices, scorer=fuzz.WRatio, score_cutoff=70.0
        )

        email_choices = {str(row[0]): row[2] for row in candidates if row[2]}
        best_email = None
        if email_choices:
            best_email = process.extractOne(
                entity_name, email_choices, scorer=fuzz.WRatio, score_cutoff=70.0
            )

        best = best_name
        if best_email and (not best or best_email[1] > best[1]):
            best = best_email

        if best:
            score = best[1]
            matched_id = best[2]

            contact = _fetch_full_contact(db, matched_id, org_id)
            if contact:
                if score >= 85.0:
                    # Tier 5: High-confidence fuzzy (>85%)
                    contact["match_confidence"] = round(score / 100.0, 2)
                    contact["matched_from"] = entity_name
                    contact["resolution_method"] = "name_fuzzy"
                    return contact
                else:
                    # Tier 6: Low-confidence fuzzy (70-85%) — flag for agent
                    contact["match_confidence"] = 0.5
                    contact["matched_from"] = entity_name
                    contact["resolution_method"] = "name_fuzzy_low"
                    return contact

        return None
    except Exception as e:
        print(f"Database error in get_contact_by_name: {str(e)}")
        return None


HALF_LIFE_DAYS = {
    "relationship_stage": 0.5,  # 12 hours
    "role": 30,
    "communication_style": 90,
    "historical": 999999,  # no decay
    "commitment": 999999,  # no decay
    "default": 30,
}


def _recency_weight(interaction_at, fact_type="default") -> float:
    """
    PDF spec: recency_weight = 0.5 ^ (days_ago / half_life)
    Half-life varies by fact type. Commitments and historical facts never decay.
    Relationship stage decays fastest (12h half-life).
    """
    if interaction_at is None:
        return 0.1
    now = datetime.now(timezone.utc)
    if interaction_at.tzinfo is None:
        interaction_at = interaction_at.replace(tzinfo=timezone.utc)
    days_ago = max(0, (now - interaction_at).days)
    half_life = HALF_LIFE_DAYS.get(fact_type, 30)
    return 0.5 ** (days_ago / half_life)


def get_recent_interactions(db, contact_id: str, limit: int = 10) -> List[Dict]:
    """
    Get recent interactions for a contact with recency-weighted ranking.

    PDF spec: recency_weight = 0.5 ^ (days_ago / 30). Commitments never decay (weight=1.0).
    Returns up to `limit` interactions, sorted by composite score:
      composite = recency_weight * signal_score (commitments always weight=1.0)
    """
    results = db.execute(
        text(
            """
            SELECT
                i.subject, i.summary, i.sentiment, i.intent,
                i.topics, i.interaction_at, i.direction, i.interaction_type,
                i.weight_score, i.signal_score, i.reply_time_hours,
                c.freshness_score
            FROM interactions i
            JOIN contacts c ON i.contact_id = c.id
            WHERE i.contact_id = :contact_id
            ORDER BY i.interaction_at DESC
            LIMIT :fetch_limit
        """
        ),
        # Fetch more than needed so we can re-rank by recency weight
        {"contact_id": contact_id, "fetch_limit": limit * 3},
    ).fetchall()

    interactions = []
    for row in results:
        interaction_at = row[5]
        intent = row[3] or ""
        is_commitment = intent == "commitment"

        # Commitments never decay per PDF spec
        rw = 1.0 if is_commitment else _recency_weight(interaction_at)
        signal = float(row[9] or row[8] or 0.5)
        composite = rw * signal

        interactions.append(
            {
                "subject": row[0],
                "summary": row[1],
                "sentiment": row[2],
                "intent": intent,
                "topics": row[4] or [],
                "interaction_at": interaction_at,
                "direction": row[6],
                "interaction_type": row[7],
                "weight_score": row[8],
                "signal_score": row[9],
                "reply_time_hours": row[10],
                "freshness_score": row[11] if row[11] else 1.0,
                "recency_weight": round(rw, 3),
                "_composite": composite,  # internal sort key
            }
        )

    # Sort by composite score descending, surface commitments and recent emails first
    interactions.sort(key=lambda x: x["_composite"], reverse=True)
    # Remove internal sort key before returning
    for i in interactions:
        i.pop("_composite", None)

    return interactions[:limit]


def format_time_ago(dt: datetime) -> str:
    """Format datetime as 'X days ago'."""
    if dt is None:
        return "never"

    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    diff = now - dt
    days = diff.days

    if days == 0:
        hours = diff.seconds // 3600
        if hours == 0:
            return "just now"
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif days == 1:
        return "1 day ago"
    elif days < 7:
        return f"{days} days ago"
    elif days < 30:
        weeks = days // 7
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    elif days < 365:
        months = days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    else:
        years = days // 365
        return f"{years} year{'s' if years != 1 else ''} ago"


def get_sentiment_trend(sentiment_avg: float) -> str:
    """Convert sentiment score to human-readable trend."""
    if sentiment_avg is None or sentiment_avg == 0:
        return "neutral"
    elif sentiment_avg > 0.3:
        return "positive"
    elif sentiment_avg < -0.3:
        return "negative"
    else:
        return "neutral"


def get_open_commitments(interactions: List[Dict]) -> List[str]:
    """Extract all commitments from recent interactions."""
    commitments = []
    for interaction in interactions:
        if interaction.get("commitments"):
            commitments.extend(interaction["commitments"])
    return commitments[:5]  # Limit to 5 most recent


def get_open_commitments_detailed(db, contact_id: str) -> List[Dict]:
    """
    Get open and soft commitments from commitments table with detailed lifecycle info.
    Returns OPEN + OVERDUE (firm) and SOFT (tentative) commitments ranked by due date.
    """
    try:
        results = db.execute(
            text(
                """
                SELECT 
                    commit_text, owner, due_date, status,
                    EXTRACT(DAY FROM (due_date - NOW())) as days_until_due,
                    created_at
                FROM commitments
                WHERE contact_id = :contact_id 
                    AND status IN ('OPEN', 'OVERDUE', 'SOFT')
                ORDER BY 
                    CASE status WHEN 'OVERDUE' THEN 0 WHEN 'OPEN' THEN 1 ELSE 2 END,
                    due_date ASC NULLS LAST,
                    created_at DESC
                LIMIT 10
            """
            ),
            {"contact_id": contact_id},
        ).fetchall()

        commitments = []
        # Dedupe: extractor occasionally double-writes near-identical commits.
        # Key on (owner, normalized_text) — keep the most actionable row
        # (OVERDUE > OPEN > SOFT, then earliest due date).
        seen: dict = {}
        for row in results:
            text_raw = row[0] or ""
            norm = " ".join(text_raw.lower().split())
            key = ((row[1] or "").lower(), norm)
            if not norm:
                continue

            days_until_due = row[4]
            status = row[3]
            rec = {
                "text": text_raw,
                "owner": row[1],
                "due_date": str(row[2]) if row[2] else None,
                "status": status,
                "is_overdue": days_until_due is not None and days_until_due < 0,
                "is_soft": status == "SOFT",
                "days_until_due": int(days_until_due) if days_until_due else None,
                "created_at": str(row[5]),
            }

            if key not in seen:
                seen[key] = rec
                continue

            # keep the more urgent record
            order = {"OVERDUE": 0, "OPEN": 1, "SOFT": 2}
            if order.get(status, 9) < order.get(seen[key]["status"], 9):
                seen[key] = rec
            elif (
                status == seen[key]["status"]
                and row[2] is not None
                and (seen[key]["due_date"] is None or str(row[2]) < seen[key]["due_date"])
            ):
                seen[key] = rec

        return list(seen.values())
    except Exception as e:
        print(f"⚠️ Error fetching commitments: {e}")
        return []


def get_interaction_type_summary(interactions: List[Dict]) -> Dict:
    """
    Summarize interaction types and engagement levels from recent interactions.
    """
    type_counts = {
        "email_reply": 0,
        "email_one_way": 0,
        "commitment": 0,
        "meeting": 0,
        "other": 0,
    }

    for interaction in interactions:
        itype = interaction.get("interaction_type", "other")
        if itype in type_counts:
            type_counts[itype] += 1

    return type_counts


# ── Disclosure Rules — what's safe to share vs avoid ─────────────────────────

def _determine_disclosure_rules(entity_type: str, topics: list) -> Dict:
    """
    Determine what information is safe to share vs avoid with this contact.
    Per PDF spec §5: disclosure_rules with safe/avoid lists.
    Rules based on entity_type and topic sensitivity.
    """
    # Default safe/avoid based on entity type
    rules = {
        "INVESTOR": {
            "safe": ["revenue range", "user count", "retention rate", "growth metrics", "team size"],
            "avoid": ["exact ARR", "cap table details", "other investor terms", "board meeting specifics"],
        },
        "CUSTOMER": {
            "safe": ["product roadmap (high-level)", "feature timeline", "pricing tiers", "support process"],
            "avoid": ["internal metrics", "other customer data", "infrastructure details", "financial internals"],
        },
        "VENDOR": {
            "safe": ["project scope", "timeline", "budget range", "requirements"],
            "avoid": ["internal strategy", "competitor evaluations", "financial details", "team conflicts"],
        },
        "PARTNER": {
            "safe": ["integration plans", "mutual benefits", "market data", "growth trajectory"],
            "avoid": ["exact financials", "other partnership terms", "internal deliberations"],
        },
        "MEDIA": {
            "safe": ["press-approved metrics", "founder story", "product vision", "market opportunity"],
            "avoid": ["unannounced features", "exact revenue", "fundraising details (unless announced)", "internal challenges"],
        },
        "ADVISOR": {
            "safe": ["detailed metrics", "strategic challenges", "team dynamics", "financial overview"],
            "avoid": ["other advisor compensation", "board-only information"],
        },
    }

    default_rules = {
        "safe": ["general business information", "public metrics", "product overview"],
        "avoid": ["financial internals", "confidential strategy", "other contact details"],
    }

    return rules.get(entity_type, default_rules)


# ── Escalation + Action Recommendation ─────────────────────────────

ESCALATION_TOPICS = {
    "investor",
    "board",
    "performance",
    "legal",
    "compliance",
    "acquisition",
    "term sheet",
    "due diligence",
    "equity",
    "fundraising",
    "series a",
    "series b",
    "investment",
}


def determine_action_recommendation(contact: Dict, entity: Dict) -> Dict:
    """
    Determine what action the calling agent should take based on relationship health.
    Returns action_recommendation and escalation_recommended as top-level signals
    so agents don't need to parse the context paragraph to decide.

    action_recommendation values:
      'block'    - DO NOT contact. Relationship is at risk. Escalate to human.
      'escalate' - Draft with extreme care. Must be reviewed by human before sending.
      'warn'     - Relationship needs attention. Use cautious tone.
      'proceed'  - Normal contact. Agent can draft and send.

    Returns:
        Dict with 'action_recommendation', 'escalation_recommended', 'action_reason'
    """
    stage = entity.get("relationship_stage", "")
    sentiment_ewma = entity.get("sentiment_ewma", 0.0)
    topics = [t.lower() for t in entity.get("topics_of_interest", [])]
    entity_type = (contact.get("entity_type") or "").upper()
    overdue = entity.get("overdue_commitments", 0)

    # Rule 1: AT_RISK → hard block
    if stage == "AT_RISK" or sentiment_ewma < -0.5:
        return {
            "action_recommendation": "block",
            "escalation_recommended": True,
            "action_reason": "Relationship is AT_RISK or sentiment strongly negative. Do not auto-contact.",
        }

    # Rule 2: Investor/board topics + ACTIVE relationship → must escalate
    has_sensitive_topic = any(any(et in t for et in ESCALATION_TOPICS) for t in topics)
    is_investor = entity_type in ("INVESTOR", "BOARD")

    if (has_sensitive_topic or is_investor) and stage in ("ACTIVE", "WARM"):
        return {
            "action_recommendation": "escalate",
            "escalation_recommended": True,
            "action_reason": "Investor or board-related contact on sensitive topic. Human review required before sending.",
        }

    # Rule 3: Overdue commitments → warn
    if overdue > 0:
        return {
            "action_recommendation": "warn",
            "escalation_recommended": False,
            "action_reason": f"You have {overdue} overdue commitment(s) with this contact. Address before drafting new outreach.",
        }

    # Rule 4: DORMANT + declining → warn
    if stage == "DORMANT" and entity.get("sentiment_trend") == "DECLINING":
        return {
            "action_recommendation": "warn",
            "escalation_recommended": False,
            "action_reason": "Relationship is dormant and declining. Use re-engagement tone.",
        }

    # Default: proceed normally
    return {
        "action_recommendation": "proceed",
        "escalation_recommended": False,
        "action_reason": "Relationship is healthy. Agent can draft and send.",
    }


_SITUATION_KEYWORDS = {
    "deal_stuck":       ["stuck", "stalled", "no response", "no reply", "blocked", "not moving", "delayed", "no progress"],
    "follow_up":        ["follow up", "follow-up", "check in", "check-in", "reach out", "ping", "nudge", "reconnect"],
    "discovery_call":   ["discovery", "call", "meeting", "demo", "intro call", "first call", "prepare", "briefing"],
    "renewal":          ["renewal", "renew", "contract", "expiry", "expires", "extend", "upsell", "expand"],
    "churn_risk":       ["churn", "at risk", "unhappy", "escalation", "escalated", "cancelling", "leaving", "health"],
    "cold_outreach":    ["cold", "intro", "first time", "never met", "reach out", "new contact", "prospecting"],
    "attrition_risk":   ["resign", "leaving", "quit", "attrition", "retention", "linkedin", "job", "offer"],
}


def _derive_agent_behavior(
    relationship_stage: str, sentiment_ewma: float,
    clm_state: str, context_score: float
) -> str:
    """
    Derive agent behavior from CLM state + context_score.
    Per CLM spec: stage overrides > CLM state > context_score thresholds.
    """
    # AT_RISK always blocks
    if (relationship_stage or "").upper() == "AT_RISK" or sentiment_ewma < -0.3:
        return "block"
    # CLM overrides
    if clm_state == "bootstrapping":
        return "building_context"
    if clm_state == "archived":
        return "block"
    if clm_state == "stale":
        return "escalate_to_human"
    # Context score thresholds
    if context_score >= 0.80:
        return "autonomous"
    if context_score >= 0.60:
        return "safe_execute"
    if context_score >= 0.45:
        return "needs_confirmation"
    return "block"


def _classify_situation(situation: str) -> Optional[str]:
    """Map free-text situation to a situation_type key."""
    if not situation:
        return None
    low = situation.lower()
    for stype, keywords in _SITUATION_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            return stype
    return None


def _get_company_contacts(db, org_id: str, company_name: str, exclude_contact_id: str = None) -> List[Dict]:
    """
    Return all contacts at a given company, ordered by relationship strength.
    Used to surface the full stakeholder map when agent asks about a company or deal.
    """
    try:
        # Match on company name OR company_domain — domain is more reliable
        # because it's derived from email (e.g. techcorp.com) not from a string
        rows = db.execute(text("""
            SELECT id, name, email, relationship_stage, sentiment_ewma,
                   sentiment_trend, last_interaction_at, interaction_count,
                   entity_type, authority_score, company_domain
            FROM contacts
            WHERE org_id = :org_id
              AND is_archived = FALSE
              AND (
                  LOWER(TRIM(company)) = LOWER(TRIM(:company))
                  OR (
                      company_domain IS NOT NULL
                      AND company_domain = (
                          SELECT company_domain FROM contacts
                          WHERE org_id = :org_id
                            AND LOWER(TRIM(company)) = LOWER(TRIM(:company))
                          LIMIT 1
                      )
                  )
              )
              AND (:exclude IS NULL OR id::text != :exclude)
            ORDER BY
                CASE relationship_stage
                    WHEN 'ACTIVE' THEN 1 WHEN 'WARM' THEN 2
                    WHEN 'NEEDS_ATTENTION' THEN 3 WHEN 'DORMANT' THEN 4
                    WHEN 'COLD' THEN 5 ELSE 6
                END,
                interaction_count DESC
            LIMIT 10
        """), {
            "org_id": org_id,
            "company": company_name,
            "exclude": str(exclude_contact_id) if exclude_contact_id else None,
        }).fetchall()

        result = []
        for r in rows:
            last_at = r[6]
            days_ago = None
            if last_at:
                if hasattr(last_at, 'tzinfo') and last_at.tzinfo is None:
                    last_at = last_at.replace(tzinfo=timezone.utc)
                days_ago = (datetime.now(timezone.utc) - last_at).days
            result.append({
                "id": str(r[0]),
                "name": r[1],
                "email": r[2],
                "relationship_stage": r[3],
                "sentiment_ewma": round(float(r[4]), 2) if r[4] is not None else None,
                "sentiment_trend": r[5],
                "last_contact_days_ago": days_ago,
                "interaction_count": r[7] or 0,
                "entity_type": r[8],
                "authority_score": round(float(r[9]), 2) if r[9] is not None else None,
            })
        return result
    except Exception:
        return []


def build_context_bundle(
    db, org_id: str, entity_name: str, situation: str = None,
    plan_tier: str = None, context_size: str = "medium",
    remaining_ms: int = 10_000,
) -> Dict:
    """
    Build complete context bundle for an entity.
    Enhanced with EWMA sentiment, trends, confidence, and commitment tracking.

    Args:
        db: Database session
        org_id: Organization UUID
        entity_name: Name of the person/company
        situation: Optional situation context
        plan_tier: Override plan tier (used when already fetched upstream)

    Returns:
        Dict with entity details, confidence score, and context_for_agent
    """
    # Resolve plan tier once
    if plan_tier is None:
        try:
            from app.plan_enforcer import get_org_plan
            plan_info = get_org_plan(db, org_id)
            plan_tier = plan_info["tier"]
        except Exception:
            plan_tier = "trial"

    # 1. Find the contact
    contact = get_contact_by_name(db, org_id, entity_name)

    if not contact:
        return {
            "error": "Contact not found",
            "entity_name": entity_name,
            "context_for_agent": f"No information found for {entity_name}.",
            "confidence": 0.0,
        }

    # ── Context score floor (PDF spec §Guardrails) ────────────────────────────
    # Use the HIGHEST of confidence_score and context_score — they track
    # different signals and one is often populated while the other is stale.
    # <0.20 → exclude entirely; <0.45 → flag as low confidence.
    conf_raw = contact.get("confidence_score") or 0.0
    ctx_raw = contact.get("context_score") or 0.0
    contact_confidence = max(float(conf_raw), float(ctx_raw), 0.5 if not (conf_raw or ctx_raw) else 0.0)
    if contact_confidence < 0.20:
        return {
            "error": "ENTITY_BELOW_SCORE_FLOOR",
            "entity_name": entity_name,
            "context_for_agent": f"Insufficient data to build context for {entity_name}.",
            "confidence": contact_confidence,
            "confidence_level": "insufficient",
        }

    low_confidence_flag = contact_confidence < 0.45

    # 2. Get recent interactions (limited by plan)
    from app.plan_enforcer import PLAN_CONFIG
    plan_cfg = PLAN_CONFIG.get(plan_tier, PLAN_CONFIG["trial"])
    interaction_limit = plan_cfg["max_interactions_per_entity"]
    interactions = get_recent_interactions(db, contact["id"], limit=interaction_limit)

    # 3. Get open commitments with lifecycle info
    open_commitments = get_open_commitments_detailed(db, contact["id"])

    # 3b. Company-level stakeholder map — all other contacts at the same company
    company_contacts = []
    if contact.get("company"):
        company_contacts = _get_company_contacts(
            db, org_id, contact["company"], exclude_contact_id=contact["id"]
        )

    # Calculate stage_since_days
    stage_since_days = None
    if contact.get("stage_changed_at"):
        stage_changed = contact["stage_changed_at"]
        if stage_changed:
            if hasattr(stage_changed, 'tzinfo') and stage_changed.tzinfo is None:
                stage_changed = stage_changed.replace(tzinfo=timezone.utc)
            stage_since_days = (datetime.now(timezone.utc) - stage_changed).days

    # Determine disclosure rules based on entity_type and topics
    entity_type_upper = (contact.get("entity_type") or "").upper()
    disclosure_rules = _determine_disclosure_rules(entity_type_upper, contact["topics_aggregate"])

    # Resolve communication_style honestly — never report "Unknown" when we
    # have descriptive hints. Prefer explicit style → fall back to what_works
    # → finally an empty string (NOT None — keeps the contract string-typed
    # so existing consumers doing .lower() / concatenation don't break).
    _raw_style = (contact.get("communication_style") or "").strip()
    _what_works = (contact.get("what_works") or "").strip()
    if _raw_style and _raw_style.lower() != "unknown":
        _resolved_style = _raw_style
    elif _what_works:
        _resolved_style = _what_works
    else:
        _resolved_style = ""  # honest absence, still a string

    # ── Broadcast/marketing detector ─────────────────────────────────────────
    # Aligned with /v1/contacts?exclude_broadcast. Two signals, either enough:
    #   1. Address pattern — noreply, info@, vacancy@, contract.notes@, etc.
    #   2. Behavioral     — no replies from us AND they've sent ≥3 times
    # See _is_broadcast_address() below for the exhaustive pattern list.
    _email_lower = (contact.get("email") or "").lower()
    _pattern_hit = _is_broadcast_address(_email_lower)
    _one_way_heavy = (
        (not contact.get("is_bidirectional"))
        and (contact.get("interaction_count") or 0) >= BROADCAST_MIN_ONEWAY_COUNT
    )
    _is_broadcast = _pattern_hit or _one_way_heavy

    # 4. Build entity details with enhanced metrics
    entity = {
        "id": str(contact["id"]) if contact.get("id") else None,
        "name": contact["name"],
        "email": contact.get("email"),
        "company": contact["company"],
        "relationship_stage": contact["relationship_stage"] or "UNKNOWN",
        "stage_since_days": stage_since_days,
        "confidence": contact.get("confidence_score", 0.5),
        "sentiment_avg": round(contact.get("sentiment_avg", 0.0), 2),
        "sentiment_ewma": round(contact.get("sentiment_ewma", 0.0), 2),
        "sentiment_trend": contact.get("sentiment_trend", "STABLE"),
        "last_interaction": format_time_ago(contact["last_interaction_at"]),
        "communication_style": _resolved_style,
        "what_works": contact.get("what_works"),
        "what_to_avoid": contact.get("what_to_avoid"),
        "topics_of_interest": contact["topics_aggregate"][:5],
        # Phase 3.5: suppress commitments from non-bidirectional/broadcast contacts.
        # Newsletter CTAs ("apply for program", "attend event") are extracted
        # at ingestion (P1) but hidden at read time. Only surface commitments
        # from real conversations (is_bidirectional) or manually confirmed.
        "open_commitments": len(open_commitments) if contact.get("is_bidirectional") or not _is_broadcast else 0,
        "open_commitments_detail": open_commitments if contact.get("is_bidirectional") or not _is_broadcast else [],
        "overdue_commitments": (
            sum(1 for c in open_commitments if c.get("is_overdue"))
            if contact.get("is_bidirectional") or not _is_broadcast else 0
        ),
        "interaction_count": contact["interaction_count"] or 0,
        "interaction_types": get_interaction_type_summary(interactions),
        "response_rate": contact.get("response_rate"),
        "avg_response_time_hours": contact.get("avg_response_time_hours"),
        "is_bidirectional": contact.get("is_bidirectional", False),
        "disclosure_rules": disclosure_rules,
        "relationship_summary": contact.get("relationship_summary"),
        "introduced_by": str(contact.get("introduced_by")) if contact.get("introduced_by") else None,
        "tags": contact.get("tags") or [],
        "disclosure_level": contact.get("disclosure_level") or "public",
        "is_broadcast": _is_broadcast,
    }

    # ── Cooldown check (computed early so follow_up situation can use it) ──
    cooldown_active = False
    hours_since_last_outbound = None
    try:
        last_outbound = db.execute(text("""
            SELECT MAX(interaction_at) FROM interactions
            WHERE contact_id = :cid AND direction = 'outbound'
        """), {"cid": str(contact["id"])}).scalar()
        if last_outbound:
            from datetime import timezone as _tz
            if last_outbound.tzinfo is None:
                last_outbound = last_outbound.replace(tzinfo=_tz.utc)
            hours_since_last_outbound = round(
                (datetime.now(_tz.utc) - last_outbound).total_seconds() / 3600, 1
            )
            cooldown_active = hours_since_last_outbound < 72  # 72h email cooldown
    except Exception:
        pass

    # ── Situation classification → targeted extra signals ────────────────────
    # Must run BEFORE context_for_agent is built so the prepend block can use it.
    situation_type = _classify_situation(situation)
    situation_signals: dict = {}

    if situation_type == "deal_stuck":
        try:
            row = db.execute(text("""
                SELECT
                    COUNT(*) FILTER (WHERE direction = 'outbound') AS outbound_count,
                    MAX(interaction_at) FILTER (WHERE direction = 'inbound') AS last_inbound_at,
                    COUNT(*) FILTER (WHERE direction = 'outbound'
                        AND interaction_at > COALESCE(
                            (SELECT MAX(i2.interaction_at) FROM interactions i2
                             WHERE i2.contact_id = interactions.contact_id AND i2.direction = 'inbound'),
                            '1970-01-01'::timestamptz
                        )
                    ) AS unanswered_outbound
                FROM interactions
                WHERE contact_id = :cid AND org_id = :oid
            """), {"cid": str(contact["id"]), "oid": org_id}).fetchone()
            if row:
                last_inbound = row[1]
                days_since_inbound = None
                if last_inbound:
                    if hasattr(last_inbound, 'tzinfo') and last_inbound.tzinfo is None:
                        last_inbound = last_inbound.replace(tzinfo=timezone.utc)
                    days_since_inbound = (datetime.now(timezone.utc) - last_inbound).days
                situation_signals = {
                    "outbound_count": row[0],
                    "days_since_last_inbound": days_since_inbound,
                    "unanswered_outbound": row[2],
                }
        except Exception:
            pass

    elif situation_type == "discovery_call":
        try:
            touchpoints = db.execute(text("""
                SELECT direction, intent, summary, interaction_at
                FROM interactions
                WHERE contact_id = :cid AND org_id = :oid
                ORDER BY interaction_at DESC NULLS LAST
                LIMIT 5
            """), {"cid": str(contact["id"]), "oid": org_id}).fetchall()
            situation_signals = {
                "recent_touchpoints": [
                    {
                        "direction": r[0], "intent": r[1],
                        "summary": _redact_pii(r[2] or "")[:150],
                        "date": str(r[3])[:10] if r[3] else None,
                    } for r in touchpoints
                ],
                "suggested_topics": contact.get("topics_aggregate", [])[:5],
            }
        except Exception:
            pass

    elif situation_type in ("churn_risk", "renewal"):
        try:
            sentiments = db.execute(text("""
                SELECT sentiment, interaction_at
                FROM interactions
                WHERE contact_id = :cid AND org_id = :oid AND sentiment IS NOT NULL
                ORDER BY interaction_at DESC NULLS LAST
                LIMIT 10
            """), {"cid": str(contact["id"]), "oid": org_id}).fetchall()
            vals = [round(float(r[0]), 2) for r in sentiments]
            situation_signals = {
                "sentiment_trajectory": vals,
                "trajectory_direction": (
                    "declining" if len(vals) >= 3 and vals[0] < vals[-1] - 0.2
                    else "improving" if len(vals) >= 3 and vals[0] > vals[-1] + 0.2
                    else "stable"
                ),
                "open_tickets": sum(1 for c in open_commitments if not c.get("is_soft")),
            }
        except Exception:
            pass

    elif situation_type == "follow_up":
        situation_signals = {
            "cooldown_active": cooldown_active,
            "hours_since_last_outbound": hours_since_last_outbound,
            "response_rate": contact.get("response_rate"),
            "days_since_last_contact": (
                (datetime.now(timezone.utc) - contact["last_interaction_at"].replace(tzinfo=timezone.utc)).days
                if contact.get("last_interaction_at") and hasattr(contact["last_interaction_at"], 'replace')
                else None
            ),
        }

    # 5. Generate rich context_for_agent paragraph
    context_for_agent = generate_context_paragraph(
        contact, interactions, entity, open_commitments
    )
    if company_contacts:
        context_for_agent = _append_company_context(context_for_agent, company_contacts)

    # Prepend situation-specific insight line
    if situation_type and situation_signals:
        if situation_type == "deal_stuck":
            unanswered = situation_signals.get("unanswered_outbound", 0)
            days_no_reply = situation_signals.get("days_since_last_inbound")
            if unanswered and days_no_reply is not None:
                context_for_agent = (
                    f"[Situation: deal may be stuck — {unanswered} outbound(s) unanswered, "
                    f"no inbound in {days_no_reply}d] " + context_for_agent
                )
        elif situation_type == "discovery_call":
            topics = situation_signals.get("suggested_topics", [])
            topics_str = ", ".join(topics[:3]) if topics else "unknown"
            context_for_agent = (
                f"[Situation: discovery call — known topics: {topics_str}] " + context_for_agent
            )
        elif situation_type in ("churn_risk", "renewal"):
            traj = situation_signals.get("trajectory_direction", "stable")
            context_for_agent = (
                f"[Situation: {situation_type.replace('_', ' ')} — sentiment trajectory: {traj}] "
                + context_for_agent
            )
        elif situation_type == "follow_up":
            rr = situation_signals.get("response_rate")
            rr_str = f", response rate: {round(rr*100)}%" if rr is not None else ""
            context_for_agent = (
                f"[Situation: follow-up{rr_str}] " + context_for_agent
            )

    # Determine action recommendation and escalation signal
    action = determine_action_recommendation(contact, entity)

    # ── Reconcile with agent_behavior so the two signals never contradict ──
    # agent_behavior is derived separately from context_score/CLM state.
    # If it says "block", action_recommendation must not stay at "proceed".
    # This prevents a permissive LLM from ignoring the stricter block signal.
    _ab = _derive_agent_behavior(
        contact.get("relationship_stage", ""),
        contact.get("sentiment_ewma", 0),
        contact.get("clm_state", "active"),
        contact_confidence,
    )
    if _ab == "block" and action["action_recommendation"] == "proceed":
        action = {
            "action_recommendation": "block",
            "escalation_recommended": True,
            "action_reason": (
                f"Confidence too low ({contact_confidence:.2f}) for safe auto-contact. "
                "Collect more signals before drafting."
            ),
        }
    elif _ab in ("escalate_to_human", "needs_confirmation") and action["action_recommendation"] == "proceed":
        action = {
            "action_recommendation": "warn",
            "escalation_recommended": _ab == "escalate_to_human",
            "action_reason": (
                f"Confidence is {contact_confidence:.2f}. "
                "Draft allowed but human review recommended before sending."
            ),
        }

    # Calculate coverage score (data completeness)
    coverage_parts = 0
    if contact.get("email"): coverage_parts += 1
    if contact.get("company"): coverage_parts += 1
    if interactions: coverage_parts += 1
    if len(interactions) >= 3: coverage_parts += 1
    if contact.get("relationship_stage") and contact["relationship_stage"] not in ("unknown", "COLD"): coverage_parts += 1
    if contact.get("topics_aggregate"): coverage_parts += 1
    if open_commitments: coverage_parts += 1
    coverage_score = round(coverage_parts / 7.0, 2)

    # ── Last signal: most recent meaningful interaction ──────────────────────
    last_signal = None
    try:
        ls_row = db.execute(text("""
            SELECT direction, sentiment, summary, subject, interaction_at, intent, interaction_type
            FROM interactions
            WHERE contact_id = :cid AND org_id = :oid
            ORDER BY interaction_at DESC NULLS LAST
            LIMIT 1
        """), {"cid": str(contact["id"]), "oid": org_id}).fetchone()
        if ls_row:
            ls_at = ls_row[4]
            if ls_at:
                if hasattr(ls_at, 'tzinfo') and ls_at.tzinfo is None:
                    ls_at = ls_at.replace(tzinfo=timezone.utc)
                days_ago = (datetime.now(timezone.utc) - ls_at).days
            else:
                days_ago = None
            last_signal = {
                "days_ago": days_ago,
                "direction": ls_row[0],
                "sentiment": round(float(ls_row[1]), 2) if ls_row[1] is not None else None,
                "summary": _redact_pii(ls_row[2] or ls_row[3]),
                "intent": ls_row[5],
                "interaction_type": ls_row[6],
            }
    except Exception:
        pass

    # Calculate cache_age_seconds (time since bundle generated)
    generated_at = datetime.now(timezone.utc)

    bundle = {
        "entity": entity,
        "match_confidence": contact.get("match_confidence", 1.0),
        "matched_from": contact.get("matched_from", entity_name),
        "resolution_method": contact.get("resolution_method", "exact"),
        "recent_interactions": interactions,
        "context_for_agent": context_for_agent,
        "confidence": contact_confidence,
        "confidence_level": "low" if low_confidence_flag else "normal",
        "flagged": low_confidence_flag,
        "coverage_score": coverage_score,
        # ── Action signals — agents check these first ──
        "action_recommendation": action["action_recommendation"],
        "escalation_recommended": action["escalation_recommended"],
        "action_reason": action["action_reason"],
        # ── V1 Detailing: 5-score system ──
        "scores": {
            "freshness": float(contact.get("freshness_score") or 0.5),
            "confidence": float(contact.get("confidence_score") or 0.5),
            "consistency": float(contact.get("consistency_score") or 0.5),
            "signal": float(contact.get("context_score") or 0.5),
            "authority": float(contact.get("authority_score") or 0.5),
            "composite": float(contact.get("context_score") or 0.5),
        },
        # ── PDF spec: sources_used, confidence_breakdown ──
        "sources_used": ["gmail"],
        "confidence_breakdown": {
            "gmail": float(contact.get("confidence_score") or 0.5),
        },
        "generated_at": generated_at.isoformat(),
        "cache_age_seconds": 0,
        # ── Agent behavior from CLM state + context_score (per CLM spec) ──
        "agent_behavior": _derive_agent_behavior(
            contact.get("relationship_stage", ""),
            contact.get("sentiment_ewma", 0),
            contact.get("clm_state", "active"),
            contact_confidence,
        ),
        "clm_state": contact.get("clm_state", "active"),
        "data_quality": {
            "confidence_score": contact.get("confidence_score", 0.5),
            "coverage_score": coverage_score,
            "last_recalc": contact.get("metadata", {}).get("last_recalc_at", "unknown") if isinstance(contact.get("metadata"), dict) else "unknown",
            "sources": ["gmail"],
        },
        # ── Cooldown: prevent duplicate outreach ──
        "cooldown_active": cooldown_active,
        "hours_since_last_outbound": hours_since_last_outbound,
        # ── Last signal: most recent interaction summary ──
        "last_signal": last_signal,
        # ── Company stakeholder map ──
        "company_contacts": company_contacts,
        # ── Situation intelligence ──
        "situation_type": situation_type,
        "situation_signals": situation_signals if situation_signals else None,
    }

    # ── L5 Anomaly Detection: surface active anomalies for this contact ──
    try:
        anomaly_rows = db.execute(
            text("""
                SELECT anomaly_type, engagement_z, sentiment_z, deviation_score,
                       summary, detected_at
                FROM contact_anomalies
                WHERE contact_id = :cid AND org_id = :oid AND status = 'active'
                ORDER BY deviation_score DESC
                LIMIT 3
            """),
            {"cid": str(contact["id"]), "oid": org_id},
        ).fetchall()
        if anomaly_rows:
            bundle["anomalies"] = [
                {
                    "type": r.anomaly_type,
                    "engagement_z": round(float(r.engagement_z or 0), 2),
                    "sentiment_z": round(float(r.sentiment_z or 0), 2),
                    "deviation_score": round(float(r.deviation_score), 2),
                    "summary": r.summary,
                    "detected_at": r.detected_at.isoformat() if r.detected_at else None,
                }
                for r in anomaly_rows
            ]
            # Prepend anomaly alert to context_for_agent
            top_anomaly = anomaly_rows[0]
            bundle["context_for_agent"] = (
                f"[ANOMALY: {top_anomaly.summary}] " + bundle["context_for_agent"]
            )
    except Exception:
        pass  # Anomaly table might not exist yet; fail silently

    # Add related outbound — cross-contact surface of user's own recent sends
    # on the same theme. Flag-gated via GENIOS_RELATED_OUTBOUND_ENABLED.
    # Purely additive: if the helper returns [] (disabled, no match, or error)
    # the bundle is unchanged.
    try:
        from app.context.related_outbound import (
            get_related_outbound, format_related_outbound_line,
        )
        _topics = contact.get("topics_aggregate") or []
        # Embed the situation only when topics are weak — avoids an extra
        # embedding call on every context request.
        _sit_emb = None
        if situation and (not _topics or len(_topics) < 2):
            try:
                from app.context.situation_embedder import embed_situation
                _sit_emb = embed_situation(situation)
            except Exception:
                _sit_emb = None

        related = get_related_outbound(
            db, org_id,
            contact_id_to_exclude=str(contact.get("id")) if contact.get("id") else None,
            topics=_topics or None,
            situation_embedding=_sit_emb,
            window_days=14,
            limit=5,
        )
        if related:
            bundle["related_outbound"] = related
            line = format_related_outbound_line(related)
            if line:
                bundle["context_for_agent"] += line
    except Exception as e:
        if logger:
            logger.debug(f"related_outbound enrichment skipped: {e}")

    # Add warm intro paths for COLD/DORMANT contacts
    if contact.get("relationship_stage") in ("COLD", "DORMANT"):
        try:
            from app.graph.indirect_edges import find_warm_intro_path
            warm_intros = find_warm_intro_path(db, org_id, str(contact["id"]))
            if warm_intros:
                bundle["warm_intro_paths"] = warm_intros
                intro_names = ", ".join(w["name"] for w in warm_intros[:3])
                bundle["context_for_agent"] += (
                    f" Warm intro possible via: {intro_names}."
                )
        except Exception as e:
            logger.warning(f"Warm intro lookup failed: {e}") if logger else None

    # Add precedents — resolver prefers structured precedent_situations when
    # GENIOS_PRECEDENTS_V2 is enabled, falls back to document_chunks otherwise.
    if situation:
        try:
            from app.context.precedent_search import search_precedents_any
            precedents = search_precedents_any(
                db, org_id, situation,
                stage=(contact.get("relationship_stage") if contact else None),
                situation_category=None,  # bundle flow has no insight_type
                entity_type=(contact.get("entity_type") if contact else None),
                limit=3,
            )
            if precedents:
                bundle["precedents"] = precedents
                top_prec = precedents[0]
                # v2 rows carry extra context ("3/4 RECOVERED when X sent") —
                # include it in the narrative when available.
                if top_prec.get("source") == "precedent_situations":
                    outcome_hint = top_prec.get("outcome", "mixed")
                    n = top_prec.get("n_cases", 0)
                    rate = top_prec.get("success_rate", 0.0)
                    bundle["context_for_agent"] += (
                        f" Historical precedent ({n} similar cases, "
                        f"{outcome_hint}, success rate {rate:.0%})."
                    )
                else:
                    bundle["context_for_agent"] += (
                        f" Similar situation: {top_prec['doc_title']} — {top_prec['situation'][:100]}."
                    )
        except Exception as e:
            logger.warning(f"Precedent search failed: {e}") if logger else None

    # ── L6 Fingerprint-based precedent matching ──
    try:
        from app.graph.fingerprint import build_fingerprint, match_precedents
        fp = build_fingerprint(contact, situation_type)
        fp_matches = match_precedents(db, org_id, fp, limit=5)
        if fp_matches:
            bundle["fingerprint_matches"] = fp_matches
            top_match = fp_matches[0]
            if top_match.get("success_rate") is not None:
                n = top_match["match_pool_size"]
                rate = int(top_match["success_rate"] * 100)
                best_action = top_match.get("action_taken") or "direct engagement"
                bundle["context_for_agent"] += (
                    f" Historical precedent: {n} similar situations, "
                    f"{rate}% recovered. Best action: {best_action}."
                )
    except Exception:
        pass  # Table might not exist yet or no matches

    # Add recent_interactions from raw interactions table (last 10)
    try:
        raw_interactions = db.execute(
            text("""
                SELECT direction, sentiment, summary, subject, interaction_at, intent
                FROM interactions
                WHERE contact_id = :contact_id AND org_id = :org_id
                ORDER BY interaction_at DESC NULLS LAST
                LIMIT 10
            """),
            {"contact_id": contact["id"], "org_id": org_id},
        ).fetchall()

        bundle["recent_interactions"] = [
            {
                "direction": r[0],
                "sentiment": r[1],
                "summary": _redact_pii(r[2] or r[3]),  # summary or subject — PII stripped
                "date": str(r[4]) if r[4] else None,
                "intent": r[5],
            }
            for r in raw_interactions
        ]
    except Exception as e:
        bundle["recent_interactions"] = []

    # ── Context size handling (Phase 3 rename: short/medium/long) ──────────
    # Accept legacy names (small/medium/large) as aliases for 90d per deviation F.
    _SIZE_ALIAS = {"small": "short", "large": "long"}
    HIGH_STAKES_KEYWORDS = [
        "contract", "legal", "first meeting", "board", "term sheet",
        "due diligence", "acquisition", "partnership agreement",
        "series", "funding", "investment", "deal closing",
    ]
    resolved_size = _SIZE_ALIAS.get(context_size or "medium", context_size or "medium")
    if situation and any(kw in (situation or "").lower() for kw in HIGH_STAKES_KEYWORDS):
        resolved_size = "long"

    bundle["context_size"] = resolved_size

    if resolved_size == "short":
        # Strip heavy sections — keep entity basics + commitments + recommended action
        for key in ["recent_interactions", "situational_context", "warm_intro_paths",
                     "precedents", "company_contacts", "situation_signals", "scores",
                     "data_quality", "confidence_breakdown"]:
            bundle.pop(key, None)
    elif resolved_size == "long":
        # Add full score breakdown for long bundles
        bundle["score_breakdown"] = {
            "context_score": bundle.get("confidence", 0.5),
            "confidence": float(contact.get("confidence_score") or 0.5),
            "freshness": float(contact.get("freshness_score") or 0.5),
            "sentiment": round((contact.get("sentiment_ewma", 0) + 1) / 2, 3),
            "authority": float(contact.get("authority_score") or 0.5),
            "consistency": float(contact.get("consistency_score") or 0.5),
        }

    # Phase 3.5 — narrative for medium/long packs (Pull API passes remaining_ms).
    # Programmatic by default (zero LLM tokens). Pass contact metadata so the
    # template-based path can produce a meaningful headline without an LLM.
    if resolved_size in ("medium", "long"):
        try:
            from app.brain.narrative import build_narrative
            facts = bundle.get("recent_interactions") or []
            recent = facts[0] if facts else {}
            contact_meta = {
                "stage": bundle.get("relationship_stage"),
                "sentiment_ewma": (contact.get("sentiment_ewma") if contact else None),
                "open_commitments": bundle.get("open_commitments_count")
                                    or len(bundle.get("open_commitments") or []),
                "last_interaction_at": bundle.get("last_interaction_at")
                                       or recent.get("interaction_at"),
                "last_subject": recent.get("title") or recent.get("subject"),
            }
            narrative = build_narrative(
                org_id=org_id,
                entity=entity_name,
                facts=facts,
                contact_meta=contact_meta,
                pack_size=resolved_size,
                remaining_ms=int(remaining_ms),
            )
            if narrative:
                bundle["narrative"] = narrative
        except Exception as _e:
            pass  # narrative is best-effort

    return bundle


# ── PII Redaction ─────────────────────────────────────────────────────────────

import re as _re

# Patterns that indicate raw email body leaking into summaries
_PII_PATTERNS = [
    (_re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[email]'),
    (_re.compile(r'\b(\+\d{1,3}[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b'), '[phone]'),
    (_re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'), '[card]'),
]

# Rough heuristic: summaries should not be long walls of text (raw body leak)
_MAX_SUMMARY_CHARS = 400


def _redact_pii(text: str) -> str:
    """Strip obvious PII and truncate overly long summaries before they leave the bundle."""
    if not text:
        return text
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    if len(text) > _MAX_SUMMARY_CHARS:
        text = text[:_MAX_SUMMARY_CHARS] + "…"
    return text


def calculate_confidence_score(
    contact: Dict,
    interactions: List[Dict],
    source_last_synced_at=None,
) -> float:
    """
    Calculate confidence score based on data completeness.
    PDF spec: 48h no sync → confidence decay (0.85x penalty).

    Returns: 0.0 to 1.0
    """
    score = 0.0

    # Has basic info (30%)
    if contact.get("email"):
        score += 0.15
    if contact.get("company"):
        score += 0.15

    # Has interaction data (40%)
    if interactions:
        score += 0.2
        if len(interactions) >= 3:
            score += 0.2

    # Has relationship data (30%)
    if contact.get("relationship_stage") and contact["relationship_stage"] != "unknown":
        score += 0.15
    if contact.get("topics_aggregate") and len(contact["topics_aggregate"]) > 0:
        score += 0.15

    # Boost for 20+ interactions (1.1x)
    if len(interactions) >= 20:
        score *= 1.1
    # Penalty for <3 interactions (0.6x)
    elif len(interactions) < 3:
        score *= 0.6

    # PDF spec: source stale detection — 48h no sync → 0.85x penalty
    if source_last_synced_at:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if hasattr(source_last_synced_at, 'replace'):
            source_last_synced_at = source_last_synced_at.replace(tzinfo=timezone.utc)
        hours_since_sync = (now - source_last_synced_at).total_seconds() / 3600
        if hours_since_sync > 48:
            score *= 0.85  # Stale source penalty

    return round(min(max(score, 0.0), 1.0), 2)


def generate_context_paragraph(
    contact: Dict,
    interactions: List[Dict],
    entity: Dict,
    open_commitments: List[Dict] = None,
) -> str:
    """
    Generate the context_for_agent paragraph - the key output.
    Enhanced with EWMA sentiment, trends, confidence, and commitment details.
    This paragraph can be directly prepended to any LLM prompt.
    """
    if open_commitments is None:
        open_commitments = []

    parts = []

    # Line 1: Identity and role
    name = contact["name"]
    company = contact["company"]
    entity_type = contact.get("entity_type", "")

    if company and entity_type:
        parts.append(f"{name} from {company} ({entity_type}).")
    elif company:
        parts.append(f"{name} from {company}.")
    else:
        parts.append(f"{name}.")

    # Line 2: Relationship context with confidence indicator
    stage = entity["relationship_stage"]
    last_interaction = entity["last_interaction"]
    interaction_count = entity["interaction_count"]
    confidence = entity.get("confidence", 0.5)

    confidence_label = (
        "HIGH" if confidence >= 0.75 else "MEDIUM" if confidence >= 0.5 else "LOW"
    )

    if stage != "UNKNOWN":
        parts.append(
            f"Relationship: {stage}. {interaction_count} exchanges. Last contact {last_interaction}. "
            f"(Confidence: {confidence_label}, {confidence})"
        )
    else:
        parts.append(
            f"{interaction_count} interactions total. Last contact {last_interaction}."
        )

    # Line 3: Sentiment with EWMA and trend
    sentiment_ewma = entity.get("sentiment_ewma", 0.0)
    sentiment_trend = entity.get("sentiment_trend", "STABLE")

    if sentiment_trend == "IMPROVING":
        trend_signal = "📈 sentiment improving"
    elif sentiment_trend == "DECLINING":
        trend_signal = "📉 sentiment declining"
    else:
        trend_signal = "sentiment stable"

    if sentiment_ewma > 0.3:
        parts.append(f"Positive dynamics ({trend_signal}).")
    elif sentiment_ewma < -0.3:
        parts.append(f"⚠️ Negative dynamics ({trend_signal}). Use caution.")
    else:
        parts.append(f"Neutral tone ({trend_signal}).")

    # Line 4: Topics - be specific
    topics = entity["topics_of_interest"]
    if topics and len(topics) > 0:
        if len(topics) == 1:
            parts.append(f"Main topic: {topics[0]}.")
        else:
            topics_str = ", ".join(str(t) for t in topics[:3])
            parts.append(f"Primary topics: {topics_str}.")

    # Line 5: Commitments - CRITICAL for n8n/agent decision making
    firm_commitments = [c for c in open_commitments if not c.get("is_soft")]
    soft_commitments = [c for c in open_commitments if c.get("is_soft")]

    if firm_commitments:
        overdue = [c for c in firm_commitments if c.get("is_overdue")]

        if overdue:
            parts.append(f"⚠️ OVERDUE: {len(overdue)} commitment(s) not fulfilled.")
            for commit in overdue[:2]:
                due_str = (
                    f" (due {commit.get('due_date', '')[:10]}"
                    if commit.get("due_date")
                    else ""
                )
                parts.append(f"  - {commit.get('text', 'Unknown')[:100]}{due_str}")
        else:
            parts.append(f"⏳ {len(firm_commitments)} open commitment(s).")
            for commit in firm_commitments[:2]:
                due_str = (
                    f" (due {commit.get('due_date', '')[:10]})"
                    if commit.get("due_date")
                    else ""
                )
                parts.append(f"  - {commit.get('text', 'Unknown')[:100]}{due_str}")

    if soft_commitments:
        parts.append(
            f"~ {len(soft_commitments)} tentative promise(s) (follow up to confirm):"
        )
        for commit in soft_commitments[:2]:
            parts.append(f"  - {commit.get('text', 'Unknown')[:100]}")

    # Line 6: Communication preferences — what_works / what_to_avoid (from PDF spec)
    what_works = contact.get("what_works")
    what_to_avoid = contact.get("what_to_avoid")
    comm_style = contact.get("communication_style")

    if what_works:
        parts.append(f"What works: {what_works}.")
    if what_to_avoid:
        parts.append(f"What to avoid: {what_to_avoid}.")
    if not what_works and not what_to_avoid and comm_style and comm_style != "Unknown":
        parts.append(f"Prefers: {comm_style}.")

    # Line 6b: Response time analysis (from PDF spec §6)
    avg_response = entity.get("avg_response_time_hours")
    if avg_response and avg_response > 0:
        if avg_response < 4:
            parts.append(f"Responds within {round(avg_response, 1)}h (high interest).")
        elif avg_response < 24:
            parts.append(f"Typical reply time: {round(avg_response, 1)}h.")
        else:
            parts.append(f"Slow responder: ~{round(avg_response / 24, 1)} days average reply time.")

    # Line 6c: Disclosure rules
    disclosure = entity.get("disclosure_rules", {})
    if disclosure.get("safe"):
        safe_str = ", ".join(disclosure["safe"][:3])
        parts.append(f"Safe to share: {safe_str}.")
    if disclosure.get("avoid"):
        avoid_str = ", ".join(disclosure["avoid"][:3])
        parts.append(f"Do not share: {avoid_str}.")

    # Line 6d: Relationship summary (for deep relationships with 50+ interactions)
    if contact.get("relationship_summary"):
        parts.append(f"Summary: {contact['relationship_summary'][:300]}")

    # Line 7: Last signal — most recent interaction with direction, intent, sentiment
    if interactions and len(interactions) > 0:
        last = interactions[0]
        summary = (last.get("summary") or "")[:200]
        direction = last.get("direction", "").lower()
        intent = last.get("intent")
        sentiment = last.get("sentiment")
        days_ago = None
        if last.get("interaction_at"):
            try:
                from datetime import timezone as _tz
                ts = last["interaction_at"]
                if isinstance(ts, str):
                    from datetime import datetime as _dt
                    ts = _dt.fromisoformat(ts)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=_tz.utc)
                days_ago = (datetime.now(_tz.utc) - ts).days
            except Exception:
                pass

        timing = f"{days_ago}d ago" if days_ago is not None else "recently"
        direction_label = "them → you" if direction == "inbound" else "you → them"
        intent_label = f", intent: {intent}" if intent and intent != "other" else ""
        sentiment_label = ""
        if sentiment is not None:
            if sentiment > 0.3:
                sentiment_label = ", positive"
            elif sentiment < -0.3:
                sentiment_label = ", negative"
        parts.append(
            f"Last interaction ({timing}, {direction_label}{intent_label}{sentiment_label})"
            + (f": {summary}" if summary else ".")
        )

    # Line 8: Interaction type distribution
    interaction_types = entity.get("interaction_types", {})
    if interaction_types.get("email_reply", 0) > 0:
        parts.append(f"Engaged: {interaction_types.get('email_reply', 0)} replies.")

    # Line 9: Health alert
    if stage == "AT_RISK":
        parts.append("🚨 ALERT: Relationship at risk. Action required.")
    elif stage == "DORMANT" and entity.get("sentiment_trend") == "DECLINING":
        parts.append("⚠️ Dormant + declining. Consider warm re-engagement.")

    return " ".join(parts)


def _append_company_context(context_for_agent: str, company_contacts: List[Dict]) -> str:
    """Append company stakeholder map to context paragraph if other contacts exist."""
    if not company_contacts:
        return context_for_agent
    lines = ["Other contacts at this company:"]
    for c in company_contacts[:5]:
        stage = c.get("relationship_stage", "UNKNOWN")
        days = c.get("last_contact_days_ago")
        timing = f"{days}d ago" if days is not None else "never contacted"
        sentiment = c.get("sentiment_ewma")
        sentiment_note = ""
        if sentiment is not None:
            if sentiment > 0.3:
                sentiment_note = ", positive"
            elif sentiment < -0.3:
                sentiment_note = ", negative"
        lines.append(f"  - {c['name']} ({stage}, last: {timing}{sentiment_note})")
    return context_for_agent + " " + " ".join(lines)
