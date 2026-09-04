"""
modules/ml/llm_client.py
=============================
Single shared ChatGroq client for direct (non-agent, no tool-loop) LLM calls
used by justification.py and reassignment.py. Same model/config as
src/epars_agent/agent/burnout_monitor.py's module-level instantiation.
"""

import json
import os

try:
    from langchain_groq import ChatGroq
    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        temperature=0,
        api_key=os.getenv("GROQ_API_KEY"),
    )
except ImportError:
    llm = None
    print("[WARN] langchain_groq not installed. Run: pip install langchain-groq")


def invoke_json(prompt: str) -> dict | None:
    """
    Calls the LLM with a prompt that asks for a strict JSON object response.
    Returns the parsed dict, or None if the LLM is unavailable or the
    response can't be parsed (never raises).
    """
    if llm is None:
        return None
    try:
        response = llm.invoke(prompt)
        text = response.content.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception:
        return None
