"""FastAPI application: creates the app, connects the routers and serves the frontend.

Run with:  uv run uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers import applications, candidates, jobs, recommendations

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once when the server starts: create the tables if they do not exist yet."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Job and Internship Recommendation System",
    description="Deterministic, rule-based job recommendations for students and recent graduates.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: allows the frontend to call the API even when the page is opened from
# another address (for example directly from disk or from VS Code Live Server).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(candidates.router)
app.include_router(recommendations.router)
app.include_router(applications.router)

# The frontend is also served by FastAPI:
# http://127.0.0.1:8000/frontend/index.html?candidate_id=1
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


@app.get("/", tags=["Info"])
def root():
    """Simple check that the API is running."""
    return {
        "status": "ok",
        "docs": "/docs",
        "frontend": "/frontend/index.html?candidate_id=1",
    }
