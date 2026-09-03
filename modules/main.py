"""
modules/main.py — ePARS API entrypoint
=========================================
Run:  uvicorn modules.main:app --reload --port 8000   (from the backend/ worktree root)

Exposes src/epars_agent and src/epars_policies over HTTP for the frontend.
Does not contain business logic itself — every route calls straight into the
existing, independently-testable functions in src/. See docs/API-Contracts.md
for the full route reference.
"""

import os
import sys
from pathlib import Path

# src/epars_agent/agent's own files use bare sibling imports (`from db import ...`,
# `from tools import ...`) rather than package-relative ones — mirror the exact sys.path
# setup src/epars_agent/test_agent.py already uses, so routers can import the same way
# instead of requiring changes inside src/.
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR / "epars_agent" / "agent"))
sys.path.insert(0, str(SRC_DIR / "epars_policies"))

from dotenv import load_dotenv

load_dotenv()

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .performance.routes import router as performance_router  # noqa: E402  (needs SRC_DIR on path first)
from .burnout.routes import router as burnout_router  # noqa: E402
from .agent.routes import router as agent_router  # noqa: E402
from .ml.loader import preload_models  # noqa: E402

from modules.task_assignment.routes import router as task_assignment_router

logger = logging.getLogger("epars.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    errors = preload_models()
    for name, err in errors.items():
        logger.error("Failed to load %s model at startup: %s", name, err)
    yield


app = FastAPI(title="ePARS API", lifespan=lifespan)

_default_origins = "http://localhost:5173"
allowed_origins = os.getenv("FRONTEND_ORIGIN", _default_origins).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(performance_router, prefix="/api")
app.include_router(burnout_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(task_assignment_router)


@app.get("/health")
def health():
    return {"status": "ok"}
