"""
ePARS Policy RAG Query Utility
================================
This module is called by the Agentic AI layer to retrieve
relevant policy context before making decisions.

Backed by pgvector (Postgres) — see ingest_policies.py for how the
`policy_chunks` table is populated.

Import and use `query_policies()` as a tool in your LangChain agent.
"""

import os
from dataclasses import dataclass

import psycopg2
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer

load_dotenv()

TABLE_NAME      = "policy_chunks"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DATABASE_URL    = os.getenv("DATABASE_URL")

# ── Singletons (initialised once at import time) ───────────────────────────────
_model = None
_conn  = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _get_conn():
    global _conn
    if _conn is None or _conn.closed:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL not set. Check your .env file.")
        _conn = psycopg2.connect(DATABASE_URL)
        register_vector(_conn)
    return _conn


@dataclass
class PolicyResult:
    text: str
    doc_id: str
    title: str
    similarity: float
    chunk_index: int


def query_policies(query: str, n_results: int = 3) -> list[PolicyResult]:
    """
    Query the pgvector policy store for the most relevant policy
    chunks matching the given query string.

    Args:
        query      : Natural language query from the agent.
        n_results  : Number of top results to return (default 3).

    Returns:
        List of PolicyResult objects sorted by descending similarity.

    Example:
        results = query_policies("can I assign a new task to a high burnout employee?")
        for r in results:
            print(r.doc_id, r.similarity, r.text[:200])
    """
    model = _get_model()
    conn  = _get_conn()

    query_embedding = model.encode(query, normalize_embeddings=True)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT content, doc_id, title, chunk_index,
                   1 - (embedding <=> %s) AS similarity
            FROM {TABLE_NAME}
            ORDER BY embedding <=> %s
            LIMIT %s;
            """,
            (query_embedding, query_embedding, n_results),
        )
        rows = cur.fetchall()

    return [
        PolicyResult(
            text        = content,
            doc_id      = doc_id or "unknown",
            title       = title or "unknown",
            similarity  = round(similarity, 4),
            chunk_index = chunk_index or 0,
        )
        for content, doc_id, title, chunk_index, similarity in rows
    ]


def format_policy_context(query: str, n_results: int = 3) -> str:
    """
    Convenience function that returns policy context as a
    formatted string ready to inject into an LLM prompt.

    Args:
        query     : The agent's decision context as a natural language string.
        n_results : Number of policy chunks to retrieve.

    Returns:
        A formatted string with the relevant policy excerpts.
    """
    results = query_policies(query, n_results=n_results)

    if not results:
        return "No relevant policy found for this query."

    lines = ["=== Relevant Policy Context ===\n"]
    for i, r in enumerate(results, 1):
        lines.append(
            f"[{i}] {r.title} ({r.doc_id}) — Relevance: {r.similarity:.2f}\n"
            f"{r.text.strip()}\n"
        )
    lines.append("=== End of Policy Context ===")
    return "\n".join(lines)


# ── LangChain Tool Wrapper ─────────────────────────────────────────────────────
# Use this if you're building your agent with LangChain.
# Add `policy_tool` to your agent's tools list.
try:
    from langchain.tools import Tool

    policy_tool = Tool(
        name="retrieve_hr_policy",
        func=lambda q: format_policy_context(q, n_results=3),
        description=(
            "Retrieves relevant HR policies, SOPs, and guidelines from the "
            "organizational policy database. Use this tool before making any "
            "decision about task assignment, team formation, burnout response, "
            "leave handling, performance actions, or promotion eligibility. "
            "Input should be a natural language description of the decision you "
            "are trying to make. Returns policy excerpts relevant to that decision."
        ),
    )
    print("[INFO] LangChain policy_tool registered successfully.")
except ImportError:
    policy_tool = None
    print("[WARN] LangChain not installed. policy_tool not registered. "
          "Use format_policy_context() directly instead.")


# ── Quick CLI Test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_cases = [
        "Employee has burnout score 0.82. Should I assign them a new task?",
        "Forming a team for a 6-month software project. What are the rules?",
        "Employee PEM score dropped from 78 to 41 in one quarter. What do I do?",
        "Task is 7 days past its deadline. What is the escalation procedure?",
        "Employee wants a promotion but has only been in the role for 8 months.",
    ]

    for query in test_cases:
        print(f"\nQuery: {query}")
        print("-" * 60)
        print(format_policy_context(query, n_results=2))
