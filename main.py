from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from context.retriever import ContextRetriever
from reasoning.engine import ReasoningEngine
from supabase import create_client
import os, re
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="GeniOS Brain Prototype")

retriever = ContextRetriever()
engine = ReasoningEngine()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


class EnrichRequest(BaseModel):
    org_id: str
    raw_message: str
    entity_name: Optional[str] = None


def extract_entity_name(message: str) -> str:
    """Simple entity extraction - looks for capitalized names"""
    # Common investor names to check
    known_entities = ["Rahul", "Priya", "Amit"]
    message_lower = message.lower()
    for entity in known_entities:
        if entity.lower() in message_lower:
            return entity
    return None


@app.post("/v1/enrich")
async def enrich(request: EnrichRequest):
    # Extract entity if not provided
    entity = request.entity_name or extract_entity_name(request.raw_message)

    # Fetch structured context
    context = retriever.get_context(
        intent=request.raw_message, org_id=request.org_id, entity_name=entity
    )

    # Reason and enrich
    result = engine.enrich(
        intent=request.raw_message, context=context, entity_name=entity
    )

    # Log interaction
    try:
        supabase.table("interaction_log").insert(
            {
                "org_id": request.org_id,
                "intent": request.raw_message,
                "context_used": context,
                "enriched_output": result.get("enriched_brief"),
                "verdict": result.get("verdict"),
                "confidence": result.get("confidence", 0.0),
            }
        ).execute()
    except Exception as e:
        print(f"[WARN] Failed to log interaction: {e}")

    return result


@app.get("/health")
async def health():
    return {"status": "alive", "service": "GeniOS Brain Prototype"}


@app.get("/v1/logs/{org_id}")
async def get_logs(org_id: str, limit: int = 20):
    """Get recent interaction logs for an organization"""
    try:
        result = (
            supabase.table("interaction_log")
            .select("*")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return {"org_id": org_id, "logs": result.data, "count": len(result.data)}
    except Exception as e:
        return {"error": str(e), "org_id": org_id, "logs": []}


class WebhookPayload(BaseModel):
    task_description: str
    result: str
    entities: Optional[list] = []
    org_id: str = "genios_internal"


@app.post("/v1/openclaw-webhook")
async def openclaw_webhook(payload: WebhookPayload):
    """Capture OpenClaw task outcomes and store as new context for learning"""
    try:
        from context.store import store_context

        # Store outcome as decision context
        content = f"Task: {payload.task_description}. Result: {payload.result}"
        entity = payload.entities[0] if payload.entities else None

        store_context(payload.org_id, "decision", content, entity)

        return {"status": "logged", "task": payload.task_description}
    except Exception as e:
        return {"status": "error", "message": str(e)}
