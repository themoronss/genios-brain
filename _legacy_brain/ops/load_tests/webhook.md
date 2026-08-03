# Webhook delivery load test (harness setup)

Unlike Pull/Ingest, webhook delivery is outbound from the brain. So we test by:
1. Seeding N recommendations into the staging tenant
2. Having its `webhook_config.url` point at a controlled receiver
3. Measuring delivery latency, retry behavior, and dead-letter count

## 1. Receiver

Use a cheap echo endpoint that sleeps to simulate slow consumer:

```python
# ops/load_tests/receiver.py — run on a small VM or locally-tunneled (ngrok)
from flask import Flask, request
import time, random

app = Flask(__name__)
stats = {"received": 0, "dropped": 0}

@app.post("/hook")
def hook():
    stats["received"] += 1
    # Simulate slow consumer 5% of the time
    if random.random() < 0.05:
        time.sleep(2.0)
    # Simulate 503 2% of the time (forces retry)
    if random.random() < 0.02:
        stats["dropped"] += 1
        return "", 503
    return "", 200

@app.get("/stats")
def s(): return stats
```

Run: `python -m flask --app receiver run --port 5055`

## 2. Seed 1000 recommendations

```bash
cd genios-brain && source venv/bin/activate
python3 -c "
import sys; sys.path.insert(0, '.')
from app.database import engine
from sqlalchemy import text
from uuid import uuid4
ORG = 'your-staging-org-uuid'
with engine.connect() as c:
    for i in range(1000):
        c.execute(text(\"\"\"
            INSERT INTO recommendations
                (id, org_id, subject_entity_id, insight_type, priority, confidence, title, reason, action)
            VALUES
                (:id, :org, NULL, 'loadtest', 0.8, 0.8, :t, 'load test reason', 'load test action')
        \"\"\"), {'id': str(uuid4()), 'org': ORG, 't': f'load #{i}'})
    c.commit()
print('seeded 1000 recommendations')
"
```

## 3. Point webhook_config at the receiver

```sql
UPDATE webhook_config
SET url = 'http://<receiver-host>:5055/hook', is_active = TRUE
WHERE org_id = '<your-staging-org-uuid>';
```

## 4. Observe

- Beat picks up every 30s, delivers in batches of 50
- Check `delivery_attempts` over 5 min:
  ```sql
  SELECT status, COUNT(*)
  FROM delivery_attempts
  WHERE org_id = '<org>' AND scheduled_at > NOW() - INTERVAL '10 minutes'
  GROUP BY status;
  ```
- Target: ≤ 5% retries, 0 dead letters
- Compare `stats.received` from receiver vs `delivered_at IS NOT NULL` count
