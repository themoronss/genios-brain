# GeniOS Brain - Deployment Checklist

Complete this checklist before deploying and testing with OpenClaw.

---

## Pre-Deployment Checks

### ✅ Code Validation
- [ ] All 10 core tests passing (`python3 test_system.py`)
- [ ] Edge cases tested (Amit + financials, unknown investor, etc.)
- [ ] No errors in logs
- [ ] API responds to all endpoints

### ✅ Environment Variables Ready
Create a file with these values to copy to Railway:

```
GEMINI_API_KEY=your_key_here
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
ORG_ID=genios_internal
```

- [ ] All API keys valid and working locally
- [ ] Qdrant collection `genios_context` exists
- [ ] Supabase tables created (org_context, entity_state, interaction_log)
- [ ] Seed data loaded and verified

### ✅ Seed Data Quality
- [ ] At least 3 investors with different statuses (warm/cold)
- [ ] At least 6 critical policies loaded
- [ ] Entity states match relationship data
- [ ] Test retrieval returns relevant results

---

## Railway Deployment Steps

### 1. Install Railway CLI
```bash
npm install -g @railway/cli
```
- [ ] Railway CLI installed

### 2. Login and Initialize
```bash
railway login
railway init
```
- [ ] Logged into Railway
- [ ] Project initialized

### 3. Deploy
```bash
railway up
```
- [ ] Deployment successful
- [ ] No build errors
- [ ] Service is running

### 4. Configure Environment
In Railway dashboard:
- [ ] All environment variables added
- [ ] Variables match local `.env`
- [ ] No syntax errors in values

### 5. Get Public URL
- [ ] Public URL obtained: `https://_____.railway.app`
- [ ] Note URL here: ___________________________________

### 6. Test Deployment
```bash
# Test health endpoint
curl https://your-app.railway.app/health

# Test enrich endpoint
curl -X POST https://your-app.railway.app/v1/enrich \
  -H "Content-Type: application/json" \
  -d '{"org_id":"genios_internal","raw_message":"follow up with Rahul"}'
```
- [ ] Health endpoint responds
- [ ] Enrich endpoint returns valid JSON
- [ ] No 500 errors
- [ ] Response includes verdict, enriched_brief, flags

---

## OpenClaw Integration Prep

### 1. Update OpenClaw System Prompt
- [ ] Copy system prompt from `OPENCLAW_INTEGRATION.md`
- [ ] Replace `your-app.railway.app` with actual URL
- [ ] Save OpenClaw configuration

### 2. Baseline Test Preparation
- [ ] Review test prompts in `test_openclaw_comparison.py`
- [ ] Prepare notebook/doc to record outputs
- [ ] Disable GeniOS integration (for baseline)

### 3. Run Baseline Tests (WITHOUT GeniOS)
Run these 5 critical prompts in OpenClaw and save outputs:

- [ ] "Follow up with investors who haven't responded"
- [ ] "Send prototype update to warm investors"  
- [ ] "Can I share financial projections with a new investor?"
- [ ] "Reach out to Rahul about scheduling a demo"
- [ ] "Who should I contact today?"

Document for each:
- Is output generic or specific?
- Does it mention policy?
- Does it use past context?
- Is it personalized?

### 4. Enable GeniOS Integration
- [ ] Update OpenClaw system prompt with GeniOS call
- [ ] Verify OpenClaw can reach Railway URL
- [ ] Test one prompt to confirm integration works

### 5. Run Enhanced Tests (WITH GeniOS)
Run the SAME 5 prompts:

- [ ] "Follow up with investors who haven't responded"
- [ ] "Send prototype update to warm investors"
- [ ] "Can I share financial projections with a new investor?"
- [ ] "Reach out to Rahul about scheduling a demo"
- [ ] "Who should I contact today?"

Document for each:
- Does it use specific names?
- Does it reference policy?
- Does it mention past interactions?
- Is it personalized to investor thesis?

---

## Comparison & Validation

### Side-by-Side Comparison
For each test prompt, rate 1-5:

| Metric | Without | With | Score |
|--------|---------|------|-------|
| Specific names used | ❌ | ✅ | /5 |
| Policy awareness | ❌ | ✅ | /5 |
| Past context | ❌ | ✅ | /5 |
| Personalization | ❌ | ✅ | /5 |
| Risk flagging | ❌ | ✅ | /5 |

- [ ] At least 3/5 tests show clear improvement
- [ ] Average score improvement >= 2 points
- [ ] GeniOS adds measurable intelligence lift

### Success Criteria

✅ **Prototype Validated** if:
- [ ] OpenClaw consistently uses specific context from GeniOS
- [ ] Policy violations are flagged
- [ ] Outputs are noticeably more personalized
- [ ] Cold investors are avoided
- [ ] Past interactions are referenced

❌ **Needs Improvement** if:
- [ ] Output quality barely changes
- [ ] GeniOS context not used by OpenClaw
- [ ] Retrieval returns irrelevant results
- [ ] Reasoning prompts need refinement

---

## Post-Validation

### Document Results
- [ ] Save 5-10 side-by-side examples
- [ ] Screenshot or copy full outputs
- [ ] Note specific improvements
- [ ] Note areas still needing work

### Identify Gaps
- [ ] What context is missing from seed data?
- [ ] Which policies need clarification?
- [ ] Are there investor states not captured?
- [ ] Does reasoning prompt need refinement?

### Next Steps Decision
- [ ] **Move to Segment 5:** Full validation suite (20 tests)
- [ ] **Improve & Re-test:** Fix gaps, run again
- [ ] **Move to MVP:** Add hard enforcement, expand use cases

---

## Quick Reference

**Local API:** `http://127.0.0.1:8000`
**Railway API:** `https://_____.railway.app`

**Test endpoints:**
```bash
# Health
curl https://your-url/health

# Enrich
curl -X POST https://your-url/v1/enrich \
  -H "Content-Type: application/json" \
  -d '{"org_id":"genios_internal","raw_message":"test intent"}'

# Logs
curl https://your-url/v1/logs/genios_internal
```

**Railway commands:**
```bash
railway logs          # View logs
railway status        # Check deployment
railway open          # Open dashboard
railway down          # Stop service
```

---

## Deployment Complete ✅

Date deployed: _____________
Railway URL: _______________
OpenClaw integration: ❌ / ✅
Baseline tests: ❌ / ✅
Enhanced tests: ❌ / ✅
Validation result: PASS / NEEDS_WORK

Notes:
