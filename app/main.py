from fastapi import FastAPI
from pydantic import BaseModel
from core.orchestrator.brain_orchestrator import BrainOrchestrator

app = FastAPI(title="GeniOS Brain", version="1.0")

# Two modes: mock (fast, for testing) and db (Supabase-backed)
brain_mock = BrainOrchestrator(use_db=False)
brain_db = None  # lazy init to avoid startup errors


class BrainRequest(BaseModel):
    intent: str
    workspace_id: str
    actor_id: str
    use_db: bool = False


@app.get("/health")
def health_check():
    return {"status": "ok", "layers": 4, "version": "v1"}


@app.post("/brain/run")
def run_brain(request: BrainRequest):
    global brain_db

    if request.use_db:
        if brain_db is None:
            brain_db = BrainOrchestrator(use_db=True)
        brain = brain_db
    else:
        brain = brain_mock

    result = brain.run(
        intent=request.intent,
        workspace_id=request.workspace_id,
        actor_id=request.actor_id,
    )

    return {
        "context": result["context"].model_dump(),
        "judgement": result["judgement"].model_dump(),
        "decision": result["decision"].model_dump(),
        "learning": result["learning"].model_dump(),
    }
