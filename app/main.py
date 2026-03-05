from fastapi import FastAPI

from app.api.routes import health
from app.api.routes import auth

app = FastAPI()

app.include_router(health.router)
app.include_router(auth.router)


@app.get("/")
def root():
    return {"message": "GeniOS Brain running"}