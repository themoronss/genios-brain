"""Unified LLM client. Every LLM call in genios-brain goes through llm_client.

Phase 1: Groq + Gemini wired. Anthropic stubbed off (flip GENIOS_ANTHROPIC_ENABLED).
"""
from app.llm.client import llm_client, LLMClient, TenantCostGuardrailExceeded

__all__ = ["llm_client", "LLMClient", "TenantCostGuardrailExceeded"]
