#!/usr/bin/env python3
"""
OpenClaw + GeniOS Comparison Test Suite
Tests the intelligence lift when GeniOS is integrated with OpenClaw
"""

import json
from datetime import datetime

# Test prompts to run in OpenClaw (both WITH and WITHOUT GeniOS)
TEST_PROMPTS = [
    {
        "id": 1,
        "prompt": "Follow up with investors who haven't responded in a week",
        "category": "investor_outreach",
        "expect": "Should identify specific investors by name and status",
    },
    {
        "id": 2,
        "prompt": "Send an update about our prototype progress",
        "category": "communication",
        "expect": "Should personalize based on investor thesis and status",
    },
    {
        "id": 3,
        "prompt": "Reach out to Investor Rahul about scheduling a demo",
        "category": "meeting_scheduling",
        "expect": "Should use Rahul's specific context, last contact, interests",
    },
    {
        "id": 4,
        "prompt": "Can I share financial projections with a new investor?",
        "category": "policy_check",
        "expect": "Should block and reference founder approval policy",
    },
    {
        "id": 5,
        "prompt": "Who should I contact today?",
        "category": "decision_support",
        "expect": "Should prioritize based on entity state and follow-up timing",
    },
    {
        "id": 6,
        "prompt": "Draft an email to Amit about our progress",
        "category": "investor_outreach",
        "expect": "Should block - Amit said no, cold status",
    },
    {
        "id": 7,
        "prompt": "Priya responded positively to our last email",
        "category": "response_handling",
        "expect": "Should escalate to founder per policy",
    },
    {
        "id": 8,
        "prompt": "What's the status of our investor pipeline?",
        "category": "information",
        "expect": "Should provide structured summary with entity states",
    },
    {
        "id": 9,
        "prompt": "Schedule follow-ups for all warm investors",
        "category": "task_creation",
        "expect": "Should list specific warm investors with context",
    },
    {
        "id": 10,
        "prompt": "Send our pitch deck to all investors",
        "category": "bulk_action",
        "expect": "Should flag personalization policy and exclude cold investors",
    },
]


def print_header():
    print("\n" + "=" * 80)
    print("OpenClaw + GeniOS Brain - Intelligence Comparison Test")
    print("=" * 80)
    print("\nThis test helps you compare OpenClaw's outputs WITH and WITHOUT GeniOS.\n")


def print_instructions():
    print("📋 INSTRUCTIONS:")
    print("\n1. BASELINE TEST (Without GeniOS):")
    print("   - Run each prompt in OpenClaw WITHOUT GeniOS integration")
    print("   - Copy OpenClaw's full response")
    print("   - Paste it when prompted")
    print("   - Observe: Generic? Missing context? Policy-blind?")

    print("\n2. ENHANCED TEST (With GeniOS):")
    print("   - Enable GeniOS integration in OpenClaw")
    print("   - Run the SAME prompts again")
    print("   - Copy OpenClaw's full response")
    print("   - Paste it when prompted")
    print("   - Observe: Specific names? Context-aware? Policy-aware?")

    print("\n3. COMPARISON:")
    print("   - View side-by-side comparison")
    print("   - Score intelligence lift")
    print("   - Document results")

    print("\n" + "=" * 80 + "\n")


def collect_baseline_outputs():
    print("\n🔵 PHASE 1: BASELINE (Without GeniOS)")
    print("-" * 80)
    print("Run these prompts in OpenClaw WITHOUT GeniOS integration:")
    print("(Press Enter after pasting each response, type 'SKIP' to skip this phase)\n")

    baseline_outputs = {}

    for test in TEST_PROMPTS:
        print(f"\n[Test {test['id']}] PROMPT:")
        print(f"  → {test['prompt']}")
        print(f"\nExpected behavior: {test['expect']}")
        print("\nRun this in OpenClaw and paste the response below:")
        print("(Type your response, then press Enter twice)\n")

        lines = []
        while True:
            line = input()
            if line == "SKIP":
                return None
            if line == "" and lines:
                break
            lines.append(line)

        baseline_outputs[test["id"]] = {
            "prompt": test["prompt"],
            "category": test["category"],
            "expect": test["expect"],
            "output": "\n".join(lines),
        }

    # Save baseline
    with open(
        f"baseline_outputs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "w"
    ) as f:
        json.dump(baseline_outputs, f, indent=2)

    print("\n✅ Baseline outputs saved!")
    return baseline_outputs


def collect_enhanced_outputs():
    print("\n🟢 PHASE 2: ENHANCED (With GeniOS)")
    print("-" * 80)
    print("Now enable GeniOS integration and run the SAME prompts:")
    print("(Press Enter after pasting each response)\n")

    enhanced_outputs = {}

    for test in TEST_PROMPTS:
        print(f"\n[Test {test['id']}] PROMPT:")
        print(f"  → {test['prompt']}")
        print(f"\nExpected behavior: {test['expect']}")
        print("\nRun this in OpenClaw WITH GeniOS and paste the response below:")
        print("(Type your response, then press Enter twice)\n")

        lines = []
        while True:
            line = input()
            if line == "" and lines:
                break
            lines.append(line)

        enhanced_outputs[test["id"]] = {
            "prompt": test["prompt"],
            "category": test["category"],
            "expect": test["expect"],
            "output": "\n".join(lines),
        }

    # Save enhanced
    with open(
        f"enhanced_outputs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "w"
    ) as f:
        json.dump(enhanced_outputs, f, indent=2)

    print("\n✅ Enhanced outputs saved!")
    return enhanced_outputs


def compare_outputs(baseline, enhanced):
    print("\n" + "=" * 80)
    print("📊 COMPARISON RESULTS")
    print("=" * 80)

    comparison_scores = []

    for test_id in baseline.keys():
        b_out = baseline[test_id]["output"]
        e_out = enhanced[test_id]["output"]

        print(f"\n[Test {test_id}] {baseline[test_id]['prompt']}")
        print("-" * 80)

        print("\n❌ WITHOUT GENIOS:")
        print(b_out[:300] + ("..." if len(b_out) > 300 else ""))

        print("\n✅ WITH GENIOS:")
        print(e_out[:300] + ("..." if len(e_out) > 300 else ""))

        print("\n📝 Score the improvement (1-5):")
        print("1 = No improvement, 5 = Dramatic improvement")

        while True:
            try:
                score = int(input("Score: "))
                if 1 <= score <= 5:
                    break
            except:
                pass
            print("Please enter 1-5")

        notes = input("Quick notes on the difference: ")

        comparison_scores.append(
            {
                "test_id": test_id,
                "prompt": baseline[test_id]["prompt"],
                "score": score,
                "notes": notes,
            }
        )

    # Save comparison
    with open(
        f"comparison_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "w"
    ) as f:
        json.dump(comparison_scores, f, indent=2)

    # Print summary
    avg_score = sum(c["score"] for c in comparison_scores) / len(comparison_scores)

    print("\n" + "=" * 80)
    print("🎯 SUMMARY")
    print("=" * 80)
    print(f"\nAverage Intelligence Lift Score: {avg_score:.1f}/5.0")
    print(f"Total Tests: {len(comparison_scores)}")
    print(f"Scores: {[c['score'] for c in comparison_scores]}")

    if avg_score >= 4.0:
        print("\n🎉 EXCELLENT: GeniOS provides dramatic intelligence lift!")
        print("✅ Ready to move forward with OpenClaw integration")
    elif avg_score >= 3.0:
        print("\n👍 GOOD: GeniOS adds meaningful value")
        print("⚠️  Consider: Improve seed data or reasoning prompts for bigger lift")
    else:
        print("\n⚠️  NEEDS WORK: Intelligence lift is minimal")
        print(
            "❌ Review: Seed data completeness, retrieval quality, prompt effectiveness"
        )

    print("\n📁 Results saved to comparison_results_*.json")


def quick_test_mode():
    """For quick automated testing"""
    print("\n🚀 QUICK TEST MODE")
    print("Running automated comparison with sample data...\n")

    from test_system import API_URL
    import httpx

    results = []

    for test in TEST_PROMPTS[:5]:  # Test first 5 prompts
        print(f"Testing: {test['prompt']}")

        try:
            resp = httpx.post(
                f"{API_URL}/v1/enrich",
                json={"org_id": "genios_internal", "raw_message": test["prompt"]},
                timeout=30,
            )
            result = resp.json()

            print(f"  Verdict: {result.get('verdict')}")
            print(f"  Brief: {result.get('enriched_brief', '')[:100]}...")
            print(f"  Flags: {result.get('flags', [])}")

            results.append(
                {
                    "prompt": test["prompt"],
                    "verdict": result.get("verdict"),
                    "has_flags": len(result.get("flags", [])) > 0,
                    "brief_length": len(result.get("enriched_brief", "")),
                }
            )

        except Exception as e:
            print(f"  Error: {e}")

        print()

    print(f"✅ Quick test complete. {len(results)} prompts tested.")
    print("For full comparison, run manual mode.")


def main():
    print_header()
    print_instructions()

    mode = input(
        "Choose mode:\n1. Full manual comparison\n2. Quick automated test\n\nChoice (1 or 2): "
    )

    if mode == "2":
        quick_test_mode()
        return

    print("\nStarting full comparison test...\n")
    input("Press Enter when ready to start BASELINE testing...")

    baseline = collect_baseline_outputs()

    if baseline is None:
        print("\n⏭️  Skipped baseline collection.")
        print("Load previous baseline or run in quick test mode.")
        return

    input("\n✅ Baseline complete. Press Enter when ready for ENHANCED testing...")

    enhanced = collect_enhanced_outputs()

    print("\n📊 Both phases complete. Generating comparison...")
    compare_outputs(baseline, enhanced)

    print("\n✅ Comparison test complete!")
    print("Review the saved JSON files for full details.")


if __name__ == "__main__":
    main()
