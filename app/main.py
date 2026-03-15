from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging

from app.api.routes import health
from app.api.routes import auth
from app.api.routes import context
from app.api.routes import status
from app.api.routes import draft
from app.api.routes import sync

logger = logging.getLogger(__name__)


async def nightly_refresh_loop():
    """
    Background task that runs the nightly relationship refresh every 24 hours.
    Starts at server boot then waits 24h between runs.
    For production, replace with a real cron or APScheduler.
    """
    # Wait 60 seconds after startup before first run (let server stabilise)
    await asyncio.sleep(60)

    while True:
        try:
            logger.info("🌙 Running nightly relationship refresh...")
            # Import here to avoid circular imports at module load time
            from app.tasks.nightly_refresh import run_nightly_refresh
            # Run in thread pool so it doesn't block the event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, run_nightly_refresh)
            logger.info("✓ Nightly refresh complete")
        except Exception as e:
            logger.error(f"✗ Nightly refresh failed: {e}")

        # Wait 24 hours before next run
        await asyncio.sleep(24 * 60 * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage background tasks for the FastAPI app lifecycle."""
    # Start nightly refresh loop as background task
    refresh_task = asyncio.create_task(nightly_refresh_loop())
    logger.info("✓ Nightly refresh scheduler started")
    yield
    # Shutdown: cancel the background task cleanly
    refresh_task.cancel()
    try:
        await refresh_task
    except asyncio.CancelledError:
        pass
    logger.info("Nightly refresh scheduler stopped")


app = FastAPI(lifespan=lifespan)

# Configure CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "https://genios-brain.vercel.app"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(context.router)
app.include_router(status.router)
app.include_router(draft.router)
app.include_router(sync.router)


@app.get("/")
def root():
    return {"message": "GeniOS Brain running"}
