#!/usr/bin/env python3
"""
OpenClaw Integration Example
Shows exactly how to integrate GeniOS API into OpenClaw
"""

import httpx

# ========== YOUR CONFIGURATION ==========
GENIOS_API_URL = "https://YOUR_RENDER_URL/v1/enrich"  # Replace with your actual URL
ORG_ID = "genios_internal"


# ========== BEFORE: OpenClaw WITHOUT GeniOS (Dumb Agent) ==========
def openclaw_without_genios(user_intent):
    """This is how OpenClaw responds WITHOUT intelligence"""

    # OpenClaw just processes the intent directly - no context, no intelligence
    if "follow up" in user_intent.lower():
        return "I'll send a follow-up email."

    elif "share financial" in user_intent.lower():
        return "I'll share the financial projections."

    elif "reach out" in user_intent.lower():
        return "I'll reach out to them."

    else:
        return "I'll help with that."


# ========== AFTER: OpenClaw WITH GeniOS (Smart Agent) ==========
def openclaw_with_genios(user_intent):
    """This is how OpenClaw responds WITH GeniOS intelligence"""

    # Step 1: Call GeniOS API BEFORE doing anything
    try:
        response = httpx.post(
            GENIOS_API_URL, json={"intent": user_intent, "org_id": ORG_ID}, timeout=10.0
        )
        enrichment = response.json()
    except Exception as e:
        print(f"⚠️ GeniOS API error: {e}")
        return "Error connecting to GeniOS Brain"

    # Step 2: Check the verdict and respond accordingly
    verdict = enrichment.get("verdict")
    brief = enrichment.get("enriched_brief", "")
    action = enrichment.get("recommended_action", "")
    flags = enrichment.get("flags", [])

    # BLOCK = Don't do it, policy violation
    if verdict == "BLOCK":
        response = f"❌ **Cannot proceed**\n\n{brief}"
        if flags:
            response += f"\n\n⚠️ Issues: {', '.join(flags)}"
        return response

    # ESCALATE = Need approval first
    elif verdict == "ESCALATE":
        response = (
            f"⚠️ **Needs approval**\n\n{brief}\n\n**Recommended Action:** {action}"
        )
        if flags:
            response += f"\n\n📌 Flags: {', '.join(flags)}"
        response += "\n\nShould I proceed?"
        return response

    # CLARIFY = Need more information
    elif verdict == "CLARIFY":
        return f"🤔 **Need clarification**\n\n{brief}\n\n{action}"

    # PROCEED = Execute with enriched context
    else:  # PROCEED
        response = (
            f"✅ **Proceeding with context**\n\n{brief}\n\n**Next Step:** {action}"
        )
        if flags:
            response += f"\n\n📌 Notes: {', '.join(flags)}"
        return response


# ========== COMPARISON TEST ==========
if __name__ == "__main__":
    print("=" * 80)
    print("OPENCLAW INTELLIGENCE COMPARISON")
    print("=" * 80)

    # Test cases
    test_cases = [
        "Follow up with Rahul about our prototype",
        "Share financial projections with Rahul",
        "Reach out to Amit",
        "Priya wants to schedule a demo",
    ]

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'=' * 80}")
        print(f"TEST {i}: {test}")
        print("=" * 80)

        # WITHOUT GeniOS
        print("\n🔴 WITHOUT GeniOS (Dumb):")
        print("-" * 80)
        without = openclaw_without_genios(test)
        print(without)

        # WITH GeniOS
        print("\n\n🟢 WITH GeniOS (Smart):")
        print("-" * 80)
        with_genios = openclaw_with_genios(test)
        print(with_genios)

        print("\n")


# ========== WHAT YOU NEED TO DO ==========
"""
1. Replace GENIOS_API_URL with your actual Render URL
2. Add the openclaw_with_genios() function to your OpenClaw code
3. Call it BEFORE OpenClaw executes any action

THAT'S IT! OpenClaw will now:
- ✅ Know specific investor names and details
- ✅ Block policy violations automatically
- ✅ Provide personalized context
- ✅ Flag risks
- ✅ Suggest smart next steps
"""
