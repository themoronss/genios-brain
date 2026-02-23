#!/bin/bash
# Simple API Test Script - Use this to verify API before n8n integration

API_URL="http://127.0.0.1:8000"  # Change to your Render URL in production

echo "=========================================="
echo "Testing GeniOS API for n8n Integration"
echo "=========================================="

# Test 1: Health check
echo -e "\n[1] Health Check:"
curl -s "$API_URL/health" | jq .

# Test 2: Simple email to warm investor
echo -e "\n[2] Draft email to warm investor (should PROCEED):"
curl -s -X POST "$API_URL/v1/enrich" \
  -H "Content-Type: application/json" \
  -d '{
    "raw_message": "Draft follow-up email to Rahul",
    "org_id": "genios_internal"
  }' | jq '.verdict, .enriched_brief'

# Test 3: Email to cold investor
echo -e "\n[3] Email to cold investor (should BLOCK):"
curl -s -X POST "$API_URL/v1/enrich" \
  -H "Content-Type: application/json" \
  -d '{
    "raw_message": "Send email to Amit",
    "org_id": "genios_internal"
  }' | jq '.verdict, .enriched_brief'

# Test 4: Share financial data
echo -e "\n[4] Share financial projections (should BLOCK):"
curl -s -X POST "$API_URL/v1/enrich" \
  -H "Content-Type: application/json" \
  -d '{
    "raw_message": "Email financial projections to Rahul",
    "org_id": "genios_internal"
  }' | jq '.verdict, .enriched_brief'

# Test 5: Internal team email
echo -e "\n[5] Internal team email (should PROCEED):"
curl -s -X POST "$API_URL/v1/enrich" \
  -H "Content-Type: application/json" \
  -d '{
    "raw_message": "Email the team about our progress",
    "org_id": "genios_internal"
  }' | jq '.verdict, .enriched_brief'

echo -e "\n=========================================="
echo "API Test Complete!"
echo "=========================================="
