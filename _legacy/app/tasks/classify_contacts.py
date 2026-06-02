"""
Phase 3.2: Batched LLM contact classification.

Picks up contacts with classification='unknown' (headers couldn't determine),
sends batches of 10 to Gemini/Groq, updates the classification columns.

Run after each Gmail sync, or on a daily schedule.
Per Principle P1: tags only, never deletes. override always wins.
"""
import json
import logging
import os
import time

from sqlalchemy import text
from app.database import SessionLocal

logger = logging.getLogger(__name__)

BATCH_SIZE = int(os.getenv("GENIOS_CLASSIFY_BATCH_SIZE", "10"))
MAX_PER_RUN = int(os.getenv("GENIOS_CLASSIFY_MAX_PER_RUN", "50"))


def _build_batch_prompt(contacts: list[dict]) -> str:
    """Build a single prompt that classifies N contacts at once."""
    entries = []
    for i, c in enumerate(contacts):
        subjects = c.get("recent_subjects") or []
        subj_str = "; ".join(s[:80] for s in subjects[:3]) if subjects else "no subjects"
        entries.append(
            f'{i+1}. name="{c["name"]}", email="{c["email"]}", '
            f'company="{c.get("company") or "unknown"}", '
            f'interaction_count={c.get("interaction_count", 0)}, '
            f'is_bidirectional={c.get("is_bidirectional", False)}, '
            f'recent_subjects=[{subj_str}]'
        )

    contacts_block = "\n".join(entries)

    return f"""Classify each contact as exactly one of: real_person, newsletter, bot, transactional.

Rules:
- real_person: a human who writes personal emails (even if via a company address)
- newsletter: marketing, announcements, digests, program invitations, event promotions
- bot: automated AI agents, product notifications, system alerts
- transactional: receipts, invoices, shipping, OTP, password reset

Contacts:
{contacts_block}

Return ONLY valid JSON array. One object per contact, same order:
[
  {{"index": 1, "classification": "real_person", "confidence": 0.85}},
  ...
]

No explanations. No markdown. JSON only."""


def _call_llm(prompt: str, org_id: str = None) -> list[dict]:
    """Batch classification via unified LLMClient (Groq primary, Gemini fallback)."""
    from app.llm import llm_client
    try:
        raw = llm_client.call(
            org_id=org_id, purpose="classify_email",
            prompt=prompt, temperature=0.1, max_tokens=1024,
        )
    except Exception as e:
        logger.warning(f"LLM classification failed: {e}")
        return []

    # Parse JSON from response
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        results = json.loads(raw.strip())
        return results if isinstance(results, list) else []
    except json.JSONDecodeError:
        logger.warning(f"LLM returned invalid JSON for classification: {raw[:200]}")
        return []


def run_classify_contacts(org_id: str = None):
    """
    Classify contacts with classification='unknown' using batched LLM calls.
    Respects classification_override (never touches overridden contacts).
    """
    db = SessionLocal()
    try:
        where = """
            c.classification = 'unknown'
            AND c.classification_override IS NULL
            AND (c.classified_at IS NULL OR c.classified_at < NOW() - INTERVAL '30 days')
        """
        params = {"limit": MAX_PER_RUN}
        if org_id:
            where += " AND c.org_id = :org_id"
            params["org_id"] = org_id

        rows = db.execute(
            text(f"""
                SELECT c.id, c.org_id, c.name, c.email, c.company,
                       c.interaction_count, c.is_bidirectional,
                       (SELECT array_agg(i.subject ORDER BY i.interaction_at DESC)
                        FROM (SELECT subject, interaction_at FROM interactions
                              WHERE contact_id = c.id AND subject IS NOT NULL
                              LIMIT 3) i
                       ) AS recent_subjects
                FROM contacts c
                WHERE {where}
                ORDER BY c.interaction_count DESC
                LIMIT :limit
            """),
            params,
        ).fetchall()

        if not rows:
            logger.info("No contacts need LLM classification.")
            return 0

        logger.info(f"Classifying {len(rows)} contacts via LLM...")
        classified = 0

        # Process in batches
        for batch_start in range(0, len(rows), BATCH_SIZE):
            batch = rows[batch_start:batch_start + BATCH_SIZE]
            contacts_data = [
                {
                    "id": str(r.id),
                    "org_id": str(r.org_id),
                    "name": r.name,
                    "email": r.email,
                    "company": r.company,
                    "interaction_count": r.interaction_count or 0,
                    "is_bidirectional": r.is_bidirectional or False,
                    "recent_subjects": r.recent_subjects or [],
                }
                for r in batch
            ]

            prompt = _build_batch_prompt(contacts_data)
            results = _call_llm(prompt, org_id=str(batch[0].org_id) if batch else None)

            for result in results:
                idx = result.get("index", 0) - 1
                if idx < 0 or idx >= len(contacts_data):
                    continue
                contact = contacts_data[idx]
                cls = result.get("classification", "unknown")
                conf = min(1.0, max(0.0, float(result.get("confidence", 0.5))))

                if cls not in ("real_person", "newsletter", "bot", "transactional"):
                    cls = "unknown"
                    continue

                try:
                    db.execute(
                        text("""
                            UPDATE contacts
                            SET classification = :cls,
                                classification_confidence = :conf,
                                classification_method = 'llm',
                                classified_at = NOW()
                            WHERE id = :cid
                              AND classification_override IS NULL
                        """),
                        {"cid": contact["id"], "cls": cls, "conf": conf},
                    )
                    db.commit()
                    classified += 1
                except Exception as e:
                    db.rollback()
                    logger.warning(f"Failed to update classification for {contact['email']}: {e}")

            # Rate limit between batches
            time.sleep(2)

        logger.info(f"Classification complete: {classified}/{len(rows)} classified")
        return classified

    finally:
        db.close()
