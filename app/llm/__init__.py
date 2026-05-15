"""Unified LLM client. Every LLM call in genios-brain goes through llm_client.

Anthropic-primary for reasoning, classification, extraction, drafting.
Gemini for embeddings + chat. Groq retained as the first fallback rung.
Provider fallback chain: Anthropic → Groq → Gemini (transient-failure safe).
"""
from app.llm.client import llm_client, LLMClient, TenantCostGuardrailExceeded

__all__ = ["llm_client", "LLMClient", "TenantCostGuardrailExceeded"]
