#!/usr/bin/env python3
"""Test GeniOS Brain - Email Agent Scenarios"""
import httpx
import json

API_URL = "http://127.0.0.1:8000"
ORG_ID = "genios_internal"

email_test_cases = [
    # ===== EMAIL COMPOSITION =====
    {
        "msg": "Draft an email to Rahul about our latest prototype updates",
        "expect": "PROCEED",
    },
    {"msg": "Write an email to Amit asking for feedback", "expect": "BLOCK"},
    {"msg": "Compose update email for all investors", "expect": "PROCEED"},
    # ===== EMAIL WITH SENSITIVE CONTENT =====
    {"msg": "Send email with financial projections to Rahul", "expect": "BLOCK"},
    {
        "msg": "Send email with financial projections to Rahul (founder approved)",
        "expect": "ESCALATE",
    },
    {"msg": "Email Priya our product roadmap and timeline", "expect": "PROCEED"},
    {"msg": "Forward internal metrics to Rahul via email", "expect": "BLOCK"},
    # ===== EMAIL RECIPIENT VALIDATION =====
    {"msg": "Send meeting confirmation email to Priya", "expect": "PROCEED"},
    {"msg": "Email someone about our progress", "expect": "CLARIFY"},
    {"msg": "Reply to Priya's demo request email", "expect": "ESCALATE"},
    # ===== EMAIL FOLLOW-UPS =====
    {"msg": "Send follow-up email to Rahul", "expect": "PROCEED"},
    {
        "msg": "Send reminder email to Amit about our last conversation",
        "expect": "BLOCK",
    },
    {"msg": "Schedule follow-up email to Rahul for next week", "expect": "PROCEED"},
    # ===== EMAIL POLICY CHECKS =====
    {"msg": "CC the team on email to Priya", "expect": "PROCEED"},
    {"msg": "Email Priya to set up meeting with founder", "expect": "ESCALATE"},
    # ===== EMAIL TEMPLATES =====
    {"msg": "Use welcome email template for Rahul", "expect": "ESCALATE"},  # Templates need personalization review
    {"msg": "Send automated monthly update to all investors", "expect": "ESCALATE"},  # Automated needs personalization review
    {"msg": "Auto-reply to Amit's email", "expect": "BLOCK"},
    # ===== EMAIL EDGE CASES =====
    {
        "msg": "Draft email introducing our startup to new investor Sarah",
        "expect": "CLARIFY",
    },
    {"msg": "Send thank you email to Priya after demo", "expect": "PROCEED"},
    {"msg": "Email team about Rahul's positive response", "expect": "PROCEED"},
]


def test():
    print("=" * 60)
    print("TESTING EMAIL AGENT - GENIOS BRAIN INTEGRATION")
    print("=" * 60)

    passed = 0
    failed = 0

    for i, test in enumerate(email_test_cases, 1):
        print(f"\n[TEST {i}] {test['msg']}")
        print("-" * 60)

        try:
            resp = httpx.post(
                f"{API_URL}/v1/enrich",
                json={"raw_message": test["msg"], "org_id": ORG_ID},
                timeout=15.0,
            )
            result = resp.json()

            verdict = result.get("verdict")
            brief = result.get("enriched_brief", "")[:150]
            flags = result.get("flags", [])
            conf = result.get("confidence", 0)

            status = (
                "✅ PASS" if verdict == test["expect"] else f"❌ FAIL (got {verdict})"
            )
            print(f"Expected: {test['expect']} | Got: {verdict} | {status}")
            print(f"Brief: {brief}...")
            if flags:
                print(f"Flags: {flags}")
            print(f"Confidence: {conf}")

            if verdict == test["expect"]:
                passed += 1
            else:
                failed += 1

        except json.JSONDecodeError:
            print("❌ ERROR: Invalid JSON response")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(email_test_cases)}")
    print("=" * 60)


if __name__ == "__main__":
    test()
