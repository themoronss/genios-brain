from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.orchestrator.brain_orchestrator import BrainOrchestrator
from core.config import Config, validate_config_on_startup

app = FastAPI(
    title="GeniOS Brain",
    version="1.0",
    description="4-Layer Decision Brain (Retrieval → Judgment → Decision → Learning)",
)


# Startup validation
@app.on_event("startup")
async def startup_event():
    """Validate configuration at startup."""
    validate_config_on_startup()


# Initialize brains based on config
brain_mock = BrainOrchestrator(use_db=False)
brain_db = None  # lazy init for Supabase mode

# Store pending decisions for approval lookup
_pending_decisions = {}


class BrainRequest(BaseModel):
    intent: str
    workspace_id: str
    actor_id: str
    use_db: bool = None  # If None, uses Config.USE_DB


class ApprovalRequest(BaseModel):
    decision_id: str
    approved: bool
    user_comment: str = ""


@app.get("/health")
def health_check():
    """Health check endpoint with configuration status."""
    return {
        "status": "ok",
        "layers": 4,
        "version": "v1",
        "mode": Config.DEPLOYMENT_MODE,
        "database": "enabled" if Config.USE_DB else "disabled (mock)",
        "real_tools": "enabled" if Config.USE_REAL_TOOLS else "disabled (simulation)",
    }


@app.post("/brain/run")
def run_brain(request: BrainRequest):
    """
    Run the brain pipeline: Retrieval → Judgment → Decision → Learning.

    Args:
        request: BrainRequest with intent, workspace_id, actor_id

    Returns:
        Decision packet with all layer outputs
    """
    global brain_db

    # Determine which brain to use
    use_db = request.use_db if request.use_db is not None else Config.USE_DB

    if use_db:
        if brain_db is None:
            brain_db = BrainOrchestrator(use_db=True)
        brain = brain_db
    else:
        brain = brain_mock

    try:
        result = brain.run(
            intent=request.intent,
            workspace_id=request.workspace_id,
            actor_id=request.actor_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Brain pipeline error: {str(e)}")

    # Generate decision ID for approval tracking
    import uuid

    decision_id = str(uuid.uuid4())

    # Store if needs approval
    if result["decision"].execution_mode == "needs_approval":
        _pending_decisions[decision_id] = {
            "decision": result["decision"],
            "workspace_id": request.workspace_id,
            "actor_id": request.actor_id,
        }

    return {
        "decision_id": decision_id,
        "context": result["context"].model_dump(),
        "judgement": result["judgement"].model_dump(),
        "decision": result["decision"].model_dump(),
        "learning": result["learning"].model_dump(),
        "execution_status": result["decision"].execution_mode,
    }


@app.post("/brain/approve")
def approve_decision(request: ApprovalRequest):
    """Approve a pending decision and execute it."""
    decision_id = request.decision_id

    if decision_id not in _pending_decisions:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")

    pending = _pending_decisions[decision_id]
    decision = pending["decision"]

    # Execute the approved decision
    from core.execution.executor import ExecutionAdapter

    executor = ExecutionAdapter(use_real_tools=True)
    exec_result = executor.execute(
        plan=decision.action_plan,
        execution_mode="auto_execute",  # Override to auto_execute
    )

    # Run learning with approval feedback
    global brain_db
    brain = brain_db if brain_db else brain_mock

    learning_report = brain.learning_engine.run(
        decision=decision,
        execution_result="approved" if request.approved else "rejected",
        user_feedback="approve" if request.approved else "reject",
        user_comment=request.user_comment,
        workspace_id=pending["workspace_id"],
        actor_id=pending["actor_id"],
    )

    # Clean up
    del _pending_decisions[decision_id]

    return {
        "decision_id": decision_id,
        "approved": request.approved,
        "execution_status": exec_result.status,
        "errors": exec_result.errors,
        "learning": learning_report.model_dump(),
    }
