import google.generativeai as genai
import os
import json
import re


class ReasoningEngine:
    def __init__(self):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel(model_name="gemini-2.5-flash")

    def _extract_json(self, text: str) -> dict:
        """
        Robust JSON extraction from model response.
        Handles all common markdown/formatting variations.
        """
        # List of extraction strategies to try in order
        strategies = []

        # Strategy 1: ```json...``` (with possible newlines inside)
        match = re.search(r"```\s*json\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            strategies.append(("markdown_json_with_newlines", match.group(1).strip()))

        # Strategy 2: ```json...``` (any whitespace)
        match = re.search(r"```\s*json\s*(.*?)```", text, re.DOTALL)
        if match:
            strategies.append(("markdown_json_flexible", match.group(1).strip()))

        # Strategy 3: ```...``` (generic code block)
        match = re.search(r"```\s*(.*?)```", text, re.DOTALL)
        if match:
            strategies.append(("markdown_generic", match.group(1).strip()))

        # Strategy 4: Find first { and last } (raw JSON extraction)
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            strategies.append(("raw_brace_extraction", text[start_idx : end_idx + 1]))

        # Strategy 5: Try raw text as-is
        strategies.append(("raw_text", text.strip()))

        # Try each strategy
        last_error = None
        for strategy_name, json_candidate in strategies:
            try:
                result = json.loads(json_candidate)
                print(f"[SUCCESS] JSON extraction successful using: {strategy_name}")
                return result
            except json.JSONDecodeError as e:
                last_error = (strategy_name, str(e), json_candidate[:100])
                continue

        # All strategies failed
        error_msg = (
            f"All JSON extraction strategies failed. Last attempt: {last_error[0]}"
        )
        print(f"[ERROR] {error_msg} - {last_error[1]}")
        print(f"[DEBUG] Last candidate text (first 100 chars): {last_error[2]}")

        raise json.JSONDecodeError(error_msg, text, 0)

    def enrich(self, intent: str, context: dict, entity_name: str = None):
        """Enhanced reasoning with policy evaluation and structured output"""

        # Build context sections
        policies_text = "\n".join(
            [f"- {p['content']}" for p in context.get("policies", [])]
        )
        relationships_text = "\n".join(
            [f"- {r['content'][:200]}" for r in context.get("relationships", [])]
        )
        profile_text = context.get("profile", "No profile available")
        entity_state_text = str(context.get("entity_state", "No entity state found"))

        prompt = f"""
You are GeniOS Brain - the cognitive decision layer for AI agents.

Your job: Analyze the user's intent against organizational context and policies, then return a structured decision.

=== USER INTENT ===
{intent}

=== ORGANIZATION PROFILE ===
{profile_text}

=== ACTIVE POLICIES ===
{policies_text if policies_text else "No policies retrieved"}

=== RELEVANT RELATIONSHIPS ===
{relationships_text if relationships_text else "No relationships found"}

=== ENTITY STATE (if applicable) ===
{entity_state_text}

=== DECISION RULES (in priority order) ===
1. Information requests (asking "what is", "tell me about", policy questions) → PROCEED with the requested information.
2. Internal communications (to "team", "staff", internal updates) → PROCEED unless policy conflict.
3. If entity is TRULY vague (e.g., "someone", "a person", no context) AND action requires specific person → CLARIFY who specifically.
4. Sharing financial data/projections:
   - If founder approval NOT mentioned → BLOCK and flag policy violation.
   - If founder approval IS mentioned → ESCALATE to founder for final confirmation.
5. If investor said no recently (cold status, said_no=true) → BLOCK from contacting.
6. If positive investor response or meeting requested → ESCALATE to founder.
7. If policy explicitly restricts this action → ESCALATE with policy reference.
8. Otherwise → PROCEED with enriched context.

=== REQUIRED OUTPUT ===
Return ONLY valid JSON (no markdown, no code blocks):

{{
  "verdict": "PROCEED | ESCALATE | BLOCK | CLARIFY",
  "enriched_brief": "3-5 sentences explaining the context, what the agent should know, and personalized guidance",
  "recommended_action": "Specific next step the agent should take",
  "flags": ["list", "of", "policy violations or concerns if any"],
  "key_context_used": ["fact 1", "fact 2", "fact 3"],
  "confidence": 0.85
}}
"""

        response = self.model.generate_content(prompt)

        try:
            result = self._extract_json(response.text)
            # Ensure all required fields exist
            if "flags" not in result:
                result["flags"] = []
            if "key_context_used" not in result:
                result["key_context_used"] = []
            return result
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON parsing failed: {str(e)}")
            print(f"[DEBUG] Full model response:\n{response.text}")
            return {
                "verdict": "ERROR",
                "enriched_brief": f"Failed to parse model response. Error: {str(e)[:100]}",
                "recommended_action": "Manual review required",
                "flags": ["json_parse_error"],
                "key_context_used": [],
                "confidence": 0.0,
            }
        except Exception as e:
            print(f"[ERROR] Unexpected error: {str(e)}")
            return {
                "verdict": "ERROR",
                "enriched_brief": f"Unexpected error: {str(e)[:100]}",
                "recommended_action": "Manual review required",
                "flags": ["unexpected_error"],
                "key_context_used": [],
                "confidence": 0.0,
            }
