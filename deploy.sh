#!/bin/bash
# GeniOS Brain - Railway Deployment Script

echo "================================================"
echo "GeniOS Brain - Railway Deployment"
echo "================================================"
echo ""

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found. Installing..."
    npm install -g @railway/cli
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install Railway CLI"
        echo "Please install manually: npm install -g @railway/cli"
        exit 1
    fi
    echo "✅ Railway CLI installed"
fi

echo ""
echo "Step 1: Login to Railway"
echo "------------------------"
railway login

if [ $? -ne 0 ]; then
    echo "❌ Railway login failed"
    exit 1
fi

echo ""
echo "Step 2: Initialize Project"
echo "--------------------------"
railway init

if [ $? -ne 0 ]; then
    echo "❌ Railway init failed"
    exit 1
fi

echo ""
echo "Step 3: Deploy to Railway"
echo "-------------------------"
railway up

if [ $? -ne 0 ]; then
    echo "❌ Deployment failed"
    exit 1
fi

echo ""
echo "✅ Deployment successful!"
echo ""
echo "================================================"
echo "NEXT STEPS:"
echo "================================================"
echo ""
echo "1. Add environment variables in Railway dashboard:"
echo "   - GEMINI_API_KEY"
echo "   - QDRANT_URL"
echo "   - QDRANT_API_KEY"
echo "   - SUPABASE_URL"
echo "   - SUPABASE_KEY"
echo "   - ORG_ID=genios_internal"
echo ""
echo "2. Get your public URL:"
echo "   railway open"
echo ""
echo "3. Test deployment:"
echo "   curl https://your-app.railway.app/health"
echo ""
echo "4. Test enrich endpoint:"
echo "   curl -X POST https://your-app.railway.app/v1/enrich \\"
echo "     -H \"Content-Type: application/json\" \\"
echo "     -d '{\"org_id\":\"genios_internal\",\"raw_message\":\"test\"}'"
echo ""
echo "5. Follow DEPLOYMENT_CHECKLIST.md for full testing"
echo ""
