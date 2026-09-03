"""
modules/agent/routes.py
==========================
Thin HTTP wrapper around the existing LangGraph agent — reuses run_agent()
unchanged (the exact function src/epars_agent/test_agent.py already calls).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from epars_agent import run_agent

router = APIRouter(prefix="/agent", tags=["agent"])


class QueryRequest(BaseModel):
    query: str


@router.post("/query")
def query_agent(body: QueryRequest):
    try:
        return run_agent(body.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
