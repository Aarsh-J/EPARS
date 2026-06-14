"""
ePARS Policy RAG Query Utility
================================
This module is called by the Agentic AI layer to retrieve
relevant policy context before making decisions.

Import and use `query_policies()` as a tool in your LangChain agent.
"""

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from dataclasses import dataclass

CHROMA_DB_PATH  = "./chroma_db"
COLLECTION_NAME = "epars_policies"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ── Singleton client (initialised once at import time) ─────────────────────────
_client     = None
_collection = None

def _get_collection():
    global _client, _collection
    if _collection is None:
        ef = SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        _collection = _client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=ef
        )
    return _collection


@dataclass
class PolicyResult:
    text: str
    doc_id: str
    title: str
    similarity: float
    chunk_index: int


def query_policies(query: str, n_results: int = 3) -> list[PolicyResult]:
    """
    Query the ChromaDB policy store for the most relevant policy
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
    collection = _get_collection()

    raw = collection.query(
        query_texts=[query],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    results = []
    for doc, meta, dist in zip(
        raw["documents"][0],
        raw["metadatas"][0],
        raw["distances"][0],
    ):
        results.append(PolicyResult(
            text        = doc,
            doc_id      = meta.get("doc_id", "unknown"),
            title       = meta.get("title", "unknown"),
            similarity  = round(1 - dist, 4),  # cosine distance → similarity
            chunk_index = meta.get("chunk_index", 0),
        ))

    return results


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
