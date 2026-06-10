import sys

sys.path.insert(0, "/home/harshtripathi/Desktop/genios-brain")

from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Check all contacts with interaction counts
result = db.execute(
    text(
        """
        SELECT 
            c.id,
            c.name,
            c.email,
            c.company,
            COUNT(i.id) as interaction_count,
            MAX(i.interaction_at) as last_interaction
        FROM contacts c
        LEFT JOIN interactions i ON i.contact_id = c.id
        WHERE c.org_id = '87b0235e-e29d-468a-b841-522c13546515'
        AND c.embedding IS NOT NULL
        GROUP BY c.id, c.name, c.email, c.company
        ORDER BY COUNT(i.id) DESC
        LIMIT 20
    """
    )
)

print("\n=== Top 20 Contacts with Embeddings ===\n")
for row in result:
    print(f"Name: {row[1]}")
    print(f"Email: {row[2]}")
    print(f"Company: {row[3]}")
    print(f"Interaction Count: {row[4]}")
    print(f"Last Interaction: {row[5]}")
    print("-" * 60)
