"""
Google OAuth Setup — Run this ONCE to authorize Gmail + Calendar access.

Usage:
    python scripts/setup_google_auth.py

This will:
    1. Open your browser for Google OAuth consent
    2. Request read-only access to Gmail and Calendar
    3. Save the token to credentials/token.json

Prerequisites:
    1. Create a project at https://console.cloud.google.com
    2. Enable Gmail API and Calendar API
    3. Create OAuth 2.0 credentials (Desktop application)
    4. Download the JSON file
    5. Save it as: credentials/client_secret.json
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.tools.google_auth import get_google_credentials, TOKEN_PATH, CLIENT_SECRET_PATH


def main():
    print("=" * 50)
    print("  GeniOS Brain — Google OAuth Setup")
    print("=" * 50)
    print()

    if not CLIENT_SECRET_PATH.exists():
        print("❌ Missing: credentials/client_secret.json")
        print()
        print("To fix this:")
        print("  1. Go to https://console.cloud.google.com/apis/credentials")
        print("  2. Create OAuth 2.0 Client ID (type: Desktop application)")
        print("  3. Download the JSON file")
        print("  4. Save it as: credentials/client_secret.json")
        print()
        return

    print("🔑 Requesting read-only access to:")
    print("   • Gmail (list emails/threads)")
    print("   • Calendar (list events)")
    print()

    if TOKEN_PATH.exists():
        print(f"⚠  Token already exists: {TOKEN_PATH}")
        answer = input("   Re-authorize? (y/N): ").strip().lower()
        if answer != "y":
            print("   Keeping existing token.")
            return
        TOKEN_PATH.unlink()

    print("🌐 Opening browser for authorization...")
    print()

    try:
        creds = get_google_credentials()
        print(f"✅ Token saved to: {TOKEN_PATH}")
        print(f"   Valid: {creds.valid}")
        print(f"   Scopes: {creds.scopes}")
        print()
        print("You can now use the Brain with use_db=True and real Gmail/Calendar data!")
    except Exception as e:
        print(f"❌ Authorization failed: {e}")


if __name__ == "__main__":
    main()
