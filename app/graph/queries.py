from sqlalchemy import text


def search_contacts_by_embedding(db, org_id, query_vector, limit=3):
    """
    Search for contacts using pgvector cosine similarity search with improved ranking.

    Filters out low-signal contacts (newsletters, notifications, alerts) and ranks by:
    1. Vector similarity
    2. Interaction count (more interactions = higher priority)
    3. Last interaction recency

    Args:
        db: SQLAlchemy database session
        org_id: Organization ID to filter contacts
        query_vector: The embedding vector to search with (list of floats)
        limit: Maximum number of results to return (default: 3)

    Returns:
        List of contact dictionaries with id, name, email, company, and relationship_stage
    """
    # Convert Python list to PostgreSQL array format
    vector_str = "[" + ",".join(str(x) for x in query_vector) + "]"

    # First try: Apply strict filters for automated emails
    result = db.execute(
        text(
            """
            SELECT 
                c.id, 
                c.name, 
                c.email, 
                c.company, 
                c.relationship_stage,
                COUNT(i.id) as interaction_count,
                MAX(i.interaction_at) as last_interaction_at
            FROM contacts c
            LEFT JOIN interactions i ON i.contact_id = c.id
            WHERE c.org_id = :org_id
            AND c.embedding IS NOT NULL
            AND c.email NOT LIKE '%noreply%'
            AND c.email NOT LIKE '%no-reply%'
            AND c.email NOT LIKE '%alerts%'
            AND c.email NOT LIKE '%notifications%'
            AND c.email NOT LIKE '%notification@%'
            AND c.email NOT LIKE '%newsletter%'
            AND c.email NOT LIKE '%@linkedin.com%'
            AND c.email NOT LIKE '%@substack.com%'
            AND c.email NOT LIKE '%donotreply%'
            AND c.email NOT LIKE '%do-not-reply%'
            AND c.email NOT LIKE '%digest%'
            GROUP BY c.id, c.name, c.email, c.company, c.relationship_stage, c.embedding
            HAVING COUNT(i.id) >= 1
            ORDER BY 
                c.embedding <=> CAST(:query_vector AS vector),
                COUNT(i.id) DESC,
                MAX(i.interaction_at) DESC NULLS LAST
            LIMIT :limit
        """
        ),
        {"org_id": org_id, "query_vector": vector_str, "limit": limit},
    )

    rows = result.fetchall()

    # If strict filters return results, use them
    if rows:
        contacts = []
        for row in rows:
            contacts.append(
                {
                    "id": row[0],
                    "name": row[1],
                    "email": row[2],
                    "company": row[3],
                    "relationship_stage": row[4],
                }
            )
        return contacts

    # Fallback: If no results with strict filters, use relaxed filters
    # This handles cases where the database only has automated contacts
    result = db.execute(
        text(
            """
            SELECT 
                c.id, 
                c.name, 
                c.email, 
                c.company, 
                c.relationship_stage,
                COUNT(i.id) as interaction_count,
                MAX(i.interaction_at) as last_interaction_at
            FROM contacts c
            LEFT JOIN interactions i ON i.contact_id = c.id
            WHERE c.org_id = :org_id
            AND c.embedding IS NOT NULL
            GROUP BY c.id, c.name, c.email, c.company, c.relationship_stage, c.embedding
            HAVING COUNT(i.id) >= 2
            ORDER BY 
                c.embedding <=> CAST(:query_vector AS vector),
                COUNT(i.id) DESC,
                MAX(i.interaction_at) DESC NULLS LAST
            LIMIT :limit
        """
        ),
        {"org_id": org_id, "query_vector": vector_str, "limit": limit},
    )

    # Convert rows to dictionaries
    rows = result.fetchall()
    contacts = []
    for row in rows:
        contacts.append(
            {
                "id": row[0],
                "name": row[1],
                "email": row[2],
                "company": row[3],
                "relationship_stage": row[4],
            }
        )

    return contacts
