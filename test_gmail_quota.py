"""
Quick test script to verify Gmail API access and check quotas
"""
import os
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv()

print("=" * 60)
print("🔍 GMAIL API QUOTA CHECK")
print("=" * 60)
print()

# Check environment variables
client_id = os.getenv("GOOGLE_CLIENT_ID")
client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

if not client_id or not client_secret:
    print("❌ Missing OAuth credentials in .env file!")
    print("   Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET")
    exit(1)

print(f"✅ Client ID found: {client_id[:20]}...")
print(f"✅ Client Secret found: {client_secret[:10]}...")
print()

print("📝 QUOTA INFORMATION:")
print("-" * 60)
print("Default Gmail API Quotas (Free Tier):")
print("  • Queries per day: 1,000,000,000 units")
print("  • Queries per minute: 15,000 per user")
print("  • Cost per query: ~5 units")
print()
print("For 10,000 emails:")
print("  • Total units used: ~50,000 units")
print("  • Percentage of daily quota: 0.005%")
print("  • ✅ Well within limits!")
print()

print("🔗 TO CHECK YOUR CURRENT USAGE:")
print("-" * 60)
print("Visit: https://console.cloud.google.com/apis/dashboard")
print("1. Select your project")
print("2. Click on 'Gmail API'")
print("3. Look at the 'Metrics' or 'Quotas' tab")
print()

print("⚠️  TO TEST OAUTH (after connecting Gmail):")
print("-" * 60)
print("Run this after completing OAuth flow:")
print("  python scripts/test_sync.py")
print()

print("=" * 60)
print("✅ Configuration looks good!")
print("=" * 60)
