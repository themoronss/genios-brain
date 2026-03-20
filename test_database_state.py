"""
Verify database state after v1.1 implementation
"""

import os
import sys
sys.path.insert(0, '/home/harshtripathi/Desktop/genios-brain')

from app.database import get_db_connection
from datetime import datetime

print("\n" + "="*70)
print("Database State Verification")
print("="*70 + "\n")

try:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Check interactions table for signal_score
    print("1️⃣ Checking interactions table...")
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(signal_score) as scored,
            ROUND(AVG(signal_score)::numeric, 3) as avg_score,
            ROUND(MIN(signal_score)::numeric, 3) as min_score,
            ROUND(MAX(signal_score)::numeric, 3) as max_score
        FROM interactions
        WHERE org_id IS NOT NULL
    """)
    result = cursor.fetchone()
    print(f"   Total interactions: {result[0]}")
    print(f"   With signal_score: {result[1]}")
    print(f"   Avg signal_score: {result[2]}")
    print(f"   Min/Max: {result[3]} - {result[4]}\n")
    
    # 2. Check contacts table for freshness_score
    print("2️⃣ Checking contacts table...")
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(freshness_score) as scored,
            ROUND(AVG(freshness_score)::numeric, 3) as avg_score,
            ROUND(MIN(freshness_score)::numeric, 3) as min_score,
            ROUND(MAX(freshness_score)::numeric, 3) as max_score
        FROM contacts
        WHERE org_id IS NOT NULL
    """)
    result = cursor.fetchone()
    print(f"   Total contacts: {result[0]}")
    print(f"   With freshness_score: {result[1]}")
    print(f"   Avg freshness_score: {result[2]}")
    print(f"   Min/Max: {result[3]} - {result[4]}\n")
    
    # 3. Check state_events table
    print("3️⃣ Checking state_events table...")
    cursor.execute("""
        SELECT type, COUNT(*) as count
        FROM state_events
        GROUP BY type
        ORDER BY count DESC
    """)
    results = cursor.fetchall()
    print(f"   Total state_events: {sum(r[1] for r in results)}")
    for event_type, count in results:
        print(f"      {event_type}: {count}")
    print()
    
    # 4. Verify indexes exist
    print("4️⃣ Checking indexes...")
    cursor.execute("""
        SELECT indexname 
        FROM pg_indexes 
        WHERE tablename IN ('interactions', 'contacts', 'state_events')
        AND indexname LIKE 'idx_%'
        ORDER BY tablename, indexname
    """)
    indexes = cursor.fetchall()
    index_tables = {}
    for idx in indexes:
        idx_name = idx[0]
        table = idx_name.split('_')[1] if '_' in idx_name else 'unknown'
        if table not in index_tables:
            index_tables[table] = []
        index_tables[table].append(idx_name)
    
    for table in sorted(index_tables.keys()):
        print(f"   {table}:")
        for idx in index_tables[table]:
            print(f"      - {idx}")
    print()
    
    # 5. Sample query showing new sorting capability
    print("5️⃣ Sample: Top 3 interactions by signal_score...")
    cursor.execute("""
        SELECT 
            i.id::text as interaction_id,
            i.subject,
            ROUND(i.signal_score::numeric, 3) as signal,
            ROUND(c.freshness_score::numeric, 3) as freshness
        FROM interactions i
        JOIN contacts c ON i.contact_id = c.id
        WHERE i.org_id IS NOT NULL
        ORDER BY i.signal_score DESC, c.freshness_score DESC
        LIMIT 3
    """)
    results = cursor.fetchall()
    for row in results:
        print(f"   ID: {row[0][:8]}...")
        print(f"      Subject: {row[1][:50]}...")
        print(f"      Signal: {row[2]}, Freshness: {row[3]}")
    print()
    
    cursor.close()
    conn.close()
    
    print("="*70)
    print("✅ Database verification complete!")
    print("="*70)
    
except Exception as e:
    print(f"❌ Error querying database: {e}")
    import traceback
    traceback.print_exc()
