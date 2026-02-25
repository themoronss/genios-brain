from fastapi import FastAPI
from pydantic import BaseModel
from core.orchestrator.brain_orchestrator import BrainOrchestrator

app = FastAPI()
brain = BrainOrchestrator()


class BrainRequest(BaseModel):
    intent: str
    workspace_id: str
    actor_id: str


@app.post("/brain/run")
def run_brain(request: BrainRequest):
    result = brain.run(
        intent=request.intent,
        workspace_id=request.workspace_id,
        actor_id=request.actor_id,
    )

    # Convert Pydantic models to dict
    return {
        "context": result["context"].dict(),
        "judgement": result["judgement"].dict(),
        "decision": result["decision"].dict(),
        "learning": result["learning"].dict(),
    }
