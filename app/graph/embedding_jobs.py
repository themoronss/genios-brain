from sqlalchemy import text
from app.database import SessionLocal
from app.graph.embedder import embed_text


def embed_contacts(org_id):
    """
    Generate embeddings for contacts using name, company, and recent interaction context.

    This creates richer embeddings that improve semantic search by including:
    - Contact name
    - Company affiliation
    - Last 3 interaction summaries
    """
    db = SessionLocal()

    rows = db.execute(
        text(
            """
        SELECT id, name, email, company
        FROM contacts
        WHERE org_id = :org_id
        AND embedding IS NULL
        """
        ),
        {"org_id": org_id},
    ).fetchall()

    if not rows:
        print("No contacts need embeddings")
        return

    for r in rows:
        # Fetch last 3 interactions for this contact
        interactions = db.execute(
            text(
                """
            SELECT summary
            FROM interactions
            WHERE contact_id = :contact_id
            AND summary IS NOT NULL
            ORDER BY interaction_at DESC
            LIMIT 3
            """
            ),
            {"contact_id": r.id},
        ).fetchall()

        # Build rich embedding text with name, company, and interaction context
        name_part = r.name or ""
        company_part = r.company or ""

        # Combine name and company
        text_parts = []
        if name_part:
            text_parts.append(name_part)
        if company_part:
            text_parts.append(company_part)

        # Add interaction summaries
        if interactions:
            text_parts.append("Recent discussions:")
            for interaction in interactions:
                if interaction.summary:
                    text_parts.append(interaction.summary)

        # Fallback to email if no other data
        if not text_parts and r.email:
            text_parts.append(r.email)

        text_data = " ".join(text_parts)

        # Generate embedding
        vector = embed_text(text_data)

        # Store embedding
        db.execute(
            text(
                """
            UPDATE contacts
            SET embedding = :embedding
            WHERE id = :id
            """
            ),
            {"id": r.id, "embedding": vector},
        )

    db.commit()

    print(f"Embeddings created for {len(rows)} contacts")


def embed_interactions(org_id):
    """
    Generate embeddings for email interactions using subject and summary.

    This enables semantic search over interaction content to find
    relevant conversations and email history.
    """
    db = SessionLocal()

    rows = db.execute(
        text(
            """
        SELECT id, subject, summary
        FROM interactions
        WHERE org_id = :org_id
        AND embedding IS NULL
        """
        ),
        {"org_id": org_id},
    ).fetchall()

    if not rows:
        print("No interactions need embeddings")
        return

    for r in rows:
        # Build embedding text from subject and summary
        text_parts = []

        if r.subject:
            text_parts.append(r.subject)

        if r.summary:
            text_parts.append(r.summary)

        # Skip if no content
        if not text_parts:
            continue

        text_data = ". ".join(text_parts)

        # Generate embedding
        vector = embed_text(text_data)

        # Store embedding
        db.execute(
            text(
                """
            UPDATE interactions
            SET embedding = :embedding
            WHERE id = :id
            """
            ),
            {"id": r.id, "embedding": vector},
        )

    db.commit()

    print(f"Embeddings created for {len(rows)} interactions")
