"""
api/main.py — SportsPoll API.

Run from the repo root: uvicorn api.main:app --reload --port 8000
data/ and utils/ resolve as top-level packages exactly like they do for
app.py today — no path hacks needed.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.routers import auth, tournaments

app = FastAPI(title="SportsPoll API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(tournaments.router, prefix="/tournaments", tags=["tournaments"])


@app.get("/health")
def health():
    return {"ok": True}
