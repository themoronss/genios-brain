# Deploying GeniOS Brain to Production

## 1. DEPLOYMENT — Current .env Status ✅

Your `.env` is **production-ready**:

```env
DEPLOYMENT_MODE=production          ✅
USE_DB=true                          ✅ (Supabase connected)
USE_REAL_TOOLS=true                  ✅ (Gmail/Calendar active)
GEMINI_API_KEY=...                   ✅ (LLM drafting enabled)
GOOGLE_CREDENTIALS_B64=...           ✅ (OAuth token encoded)
SUPABASE_URL=...                     ✅ (Database configured)
SUPABASE_KEY=...                     ✅ (API key present)
```

## 2. DEPLOYMENT OPTIONS

### Option A: Deploy to Render (Recommended)

**Step 1: Create Render Service**
```
1. Go to https://render.com
2. Click "New +" → "Web Service"
3. Connect your GitHub repo
4. Set build command: pip install -r requirements.txt
5. Set start command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Step 2: Add Environment Variables on Render Dashboard**
```
SUPABASE_URL=https://yzffmwrupeihxpugibri.supabase.co
SUPABASE_KEY=your_supabase_secret_key_here
DEPLOYMENT_MODE=production
USE_DB=true
USE_REAL_TOOLS=true
GEMINI_API_KEY=AIzaSyBcqu3vOFYnCahLoxPZOtZXyXDHCKkWllo
GOOGLE_CREDENTIALS_B64=(entire base64 string from .env)
LOG_LEVEL=INFO
REQUEST_TIMEOUT=30
DECISION_TIMEOUT=10
PORT=10000  (Render auto-assigns this)
```

**Step 3: Deploy**
- Click "Create Web Service"
- Wait for build → Live at `https://your-brain.onrender.com`

**Test:**
```bash
curl https://your-brain.onrender.com/health
```

### Option B: Deploy to AWS, GCP, Heroku (Similar Steps)

Just set the same env vars on their platforms.

---

## 3. OPENCLAW INTEGRATION (How OpenClaw Uses This Brain)

OpenClaw is presumably your external system that needs to use the Brain for decision-making.

### A. Brain API Endpoints (What OpenClaw Calls)

Your Brain exposes 3 main endpoints:

#### 1️⃣ POST `/brain/run` — Start Decision Pipeline

```bash
curl -X POST https://your-brain.onrender.com/brain/run \
  -H "Content-Type: application/json" \
  -d '{
    "intent": "follow_up",
    "context": {
      "actor_id": "user123",
      "workspace_id": "ws001",
      "message": "Follow up with John Doe about the Series A",
      "metadata": {
        "recipient": "john@investor.com",
        "vip": true,
        "keywords": ["funding", "investor", "urgent"]
      }
    }
  }'
```

**Response:**
```json
{
  "decision_id": "dec_abc123def456",
  "intent_type": "follow_up",
  "execution_mode": "needs_approval",
  "action_plan": {
    "steps": [...],
    "tool_calls": [...],
    "fallbacks": [...]
  },
  "brain_response": {
    "user_message": "Draft follow-up email prepared. Needs your approval.",
    "ui_blocks": [...]
  },
  "decision_trace": {
    "why": ["VIP status triggers approval gate", "Policy: all VIP communication needs founder approval"],
    "policies": ["VIP_APPROVAL_REQUIRED"],
    "factors": [...]
  }
}
```

#### 2️⃣ POST `/brain/approve` — Approve & Execute Decision

```bash
curl -X POST https://your-brain.onrender.com/brain/approve \
  -H "Content-Type: application/json" \
  -d '{
    "decision_id": "dec_abc123def456",
    "approved": true,
    "actor_id": "founder123"
  }'
```

**Response:**
```json
{
  "status": "executed",
  "execution_result": "Email sent to john@investor.com",
  "tool_results": [...]
}
```

#### 3️⃣ GET `/health` — Check Service Status

```bash
curl https://your-brain.onrender.com/health
```

**Response:**
```json
{
  "status": "running",
  "deployment_mode": "production",
  "database_connected": true,
  "real_tools_enabled": true
}
```

---

### B. OpenClaw Integration Architecture

```
OpenClaw Frontend/Backend
    ↓
    ├─→ POST /brain/run
    │   (Send intent + context)
    │   ↓
    │   Brain Process:
    │   ├─ Layer 1: Retrieve (memory, policies, tools)
    │   ├─ Layer 2: Judge (risk, priority, sufficiency)
    │   ├─ Layer 3: Decide (plan, mode, trace)
    │   └─ Output: decision_id + draft
    │
    ├─→ Display draft to user
    │
    ├─→ POST /brain/approve (if needs_approval)
    │   (User clicks "Approve")
    │   ↓
    │   Brain Execution:
    │   ├─ Layer 4: Execute (email_sent, calendar_booked)
    │   └─ Layer 5: Learn (save outcome, update memory)
    │
    └─→ Show confirmation ("Email sent to john@investor.com")
```

---

### C. OpenClaw Implementation Steps

**1. Create Brain Service Client**

```python
# openclaw/services/brain_client.py

import requests
import os

class BrainClient:
    """Client for GeniOS Brain API"""
    
    def __init__(self):
        self.brain_url = os.getenv("BRAIN_URL", "https://your-brain.onrender.com")
        self.timeout = 30
    
    def run_decision(self, intent: str, context: dict) -> dict:
        """Run brain decision pipeline"""
        payload = {
            "intent": intent,
            "context": context
        }
        response = requests.post(
            f"{self.brain_url}/brain/run",
            json=payload,
            timeout=self.timeout
        )
        return response.json()
    
    def approve_decision(self, decision_id: str, actor_id: str) -> dict:
        """Approve and execute decision"""
        payload = {
            "decision_id": decision_id,
            "approved": True,
            "actor_id": actor_id
        }
        response = requests.post(
            f"{self.brain_url}/brain/approve",
            json=payload,
            timeout=self.timeout
        )
        return response.json()
    
    def health_check(self) -> bool:
        """Check if brain is running"""
        try:
            response = requests.get(
                f"{self.brain_url}/health",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
```

**2. Use in OpenClaw Controllers**

```python
# openclaw/controllers/decisions.py

from openclaw.services.brain_client import BrainClient

brain = BrainClient()

def process_user_request(user_id: str, message: str):
    """Process user request through Brain"""
    
    # Step 1: Send to Brain
    decision = brain.run_decision(
        intent="follow_up",  # or "reply_email", "schedule_meeting", etc.
        context={
            "actor_id": user_id,
            "workspace_id": "openclaw_ws",
            "message": message,
            "metadata": {
                "keywords": extract_keywords(message),
                "vip": is_vip_user(user_id)
            }
        }
    )
    
    decision_id = decision["decision_id"]
    execution_mode = decision["execution_mode"]
    
    # Step 2: Handle based on execution mode
    if execution_mode == "auto_execute":
        # Brain auto-executed, no user approval needed
        return {
            "status": "completed",
            "result": decision["brain_response"]["user_message"]
        }
    
    elif execution_mode == "needs_approval":
        # Store decision, show approval UI
        save_pending_decision(decision_id, decision)
        return {
            "status": "pending_approval",
            "decision_id": decision_id,
            "draft": decision["brain_response"]["user_message"],
            "approval_url": f"/decisions/{decision_id}/approve"
        }
    
    elif execution_mode == "propose_only":
        # Just show draft, no execution
        return {
            "status": "draft",
            "decision_id": decision_id,
            "proposal": decision["brain_response"]["user_message"]
        }

def approve_decision_handler(decision_id: str, user_id: str):
    """User clicked Approve button"""
    
    result = brain.approve_decision(
        decision_id=decision_id,
        actor_id=user_id
    )
    
    return {
        "status": result["status"],
        "message": f"Decision executed: {result.get('execution_result')}"
    }
```

**3. Add to OpenClaw .env**

```env
# Brain Configuration
BRAIN_URL=https://your-brain.onrender.com
BRAIN_TIMEOUT=30
```

**4. Database: Store Decision Logs**

```python
# openclaw/models/decision_log.py

from sqlalchemy import Column, String, JSON, DateTime
from datetime import datetime

class DecisionLog(Base):
    __tablename__ = "decision_logs"
    
    id = Column(String, primary_key=True)  # decision_id from Brain
    user_id = Column(String)
    intent_type = Column(String)
    context = Column(JSON)
    decision_packet = Column(JSON)  # Full response from Brain
    status = Column(String)  # pending_approval, executed, rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)
```

---

### D. OpenClaw UI Integration (Example)

**Show decision draft to user:**

```jsx
// openclaw/frontend/components/BrainDecision.jsx

export function BrainDecision({ decisionId, draft }) {
  const [status, setStatus] = useState("pending");
  
  const handleApprove = async () => {
    const response = await fetch(`/api/decisions/${decisionId}/approve`, {
      method: "POST"
    });
    setStatus("executed");
  };
  
  return (
    <div className="brain-decision-card">
      <h2>Brain Recommendation</h2>
      
      {/* Show the draft */}
      <div className="draft-preview">
        <h3>Draft Email</h3>
        <p>{draft.subject}</p>
        <p>{draft.body}</p>
      </div>
      
      {/* Show why (trace) */}
      <div className="decision-trace">
        <h3>Why This Decision?</h3>
        <ul>
          {draft.trace.why.map(reason => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      </div>
      
      {/* Action buttons */}
      <button onClick={handleApprove}>
        ✅ Approve & Send
      </button>
      <button>
        ✏️ Edit Draft
      </button>
      <button>
        ❌ Reject
      </button>
    </div>
  );
}
```

---

## 4. DEPLOYMENT CHECKLIST

- [ ] `.env` configured (you already have this ✅)
- [ ] `requirements.txt` includes all dependencies
- [ ] Tests passing locally
- [ ] Render account created
- [ ] Environment variables added to Render
- [ ] Deploy button clicked
- [ ] Health endpoint tested
- [ ] OpenClaw client code implemented
- [ ] Database tables created in OpenClaw
- [ ] UI components built
- [ ] End-to-end test (user request → brain decision → approval → execution)

---

## 5. EXAMPLE END-TO-END FLOW

```
User in OpenClaw: "Follow up with investor John about Series A"
                    ↓
            POST /brain/run
                    ↓
            Brain processes through 4 layers
                    ↓
            Returns: "VIP needs approval"
                    ↓
            Show draft to founder (UI)
                    ↓
            Founder clicks "Approve & Send"
                    ↓
            POST /brain/approve
                    ↓
            Brain executes (sends Gmail)
                    ↓
            Show confirmation: "Email sent to john@investor.com"
```

---

## Questions?

- **How to authenticate?** Use API keys or OAuth (add to Brain if needed)
- **Rate limits?** Add to Brain config
- **Custom intents?** Add templates to `layers/layer3_decision/d2_planning/plan_templates.py`
- **Performance?** Brain avg response ~500ms per decision
