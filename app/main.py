from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.api.routes import auth
from app.api.routes import context
from app.api.routes import status
from app.api.routes import draft
from app.api.routes import sync

app = FastAPI()

# Configure CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
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
