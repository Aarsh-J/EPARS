"""Thread-safe lazy ChatGroq client for direct, non-agent LLM calls."""

import json
import logging
import os
from threading import Lock
from typing import Any

_LOGGER = logging.getLogger(__name__)
_CLIENT_LOCK = Lock()
_CLIENT_UNINITIALIZED = object()
_client: Any = _CLIENT_UNINITIALIZED


def get_llm() -> Any | None:
    """Create the shared Groq client only when an LLM-backed operation is used."""
    global _client
    with _CLIENT_LOCK:
        if _client is not _CLIENT_UNINITIALIZED:
            return _client

        if not os.getenv("GROQ_API_KEY"):
            _LOGGER.warning("GROQ_API_KEY is not configured; LLM explanations are unavailable.")
            _client = None
            return None

        try:
            from langchain_groq import ChatGroq
        except ImportError:
            _LOGGER.warning("langchain_groq is not installed; LLM explanations are unavailable.")
            _client = None
            return None

        _client = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0,
            api_key=os.getenv("GROQ_API_KEY"),
        )
        return _client


def invoke_json(prompt: str) -> dict | None:
    """
    Calls the LLM with a prompt that asks for a strict JSON object response.
    Returns the parsed dict, or None if the LLM is unavailable or the
    response can't be parsed (never raises).
    """
    client = get_llm()
    if client is None:
        return None
    try:
        response = client.invoke(prompt)
        text = response.content.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception:
        return None
