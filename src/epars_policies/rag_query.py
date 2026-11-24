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
from pathlib import Path
from threading import Lock

import psycopg2
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector

load_dotenv()

TABLE_NAME      = "policy_chunks"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DATABASE_URL    = os.getenv("DATABASE_URL")
MODEL_DIR       = os.getenv("EPARS_RAG_MODEL_DIR")

# ── Lazy process-local singletons ──────────────────────────────────────────────
_model = None
_conn  = None
_model_lock = Lock()
_embedding_lock = Lock()
_conn_lock = Lock()
_query_lock = Lock()


class _OnnxSentenceEncoder:
    def __init__(self, model_path: Path, tokenizer_path: Path):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.enable_cpu_mem_arena = False
        options.enable_mem_pattern = False
        self._session = ort.InferenceSession(
            str(model_path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self._tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self._tokenizer.enable_truncation(max_length=256)

    def encode(self, text: str, normalize_embeddings: bool = True):
        import numpy as np

        encoding = self._tokenizer.encode(text)
        attention_mask = np.asarray([encoding.attention_mask], dtype=np.int64)
        inputs = {}
        for model_input in self._session.get_inputs():
            if model_input.name == "input_ids":
                inputs[model_input.name] = np.asarray([encoding.ids], dtype=np.int64)
            elif model_input.name == "attention_mask":
                inputs[model_input.name] = attention_mask
            elif model_input.name == "token_type_ids":
                inputs[model_input.name] = np.asarray([encoding.type_ids], dtype=np.int64)
            else:
                raise RuntimeError(f"Unsupported RAG ONNX input: {model_input.name}")

        output_names = [output.name for output in self._session.get_outputs()]
        try:
            output_index = output_names.index("last_hidden_state")
        except ValueError as error:
            raise RuntimeError("RAG ONNX model has no last_hidden_state output.") from error

        token_embeddings = self._session.run(None, inputs)[output_index]
        mask = attention_mask[:, :, None].astype(np.float32)
        embeddings = (token_embeddings * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1e-9)
        if normalize_embeddings:
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = np.divide(
                embeddings,
                norms,
                out=np.zeros_like(embeddings),
                where=norms != 0,
            )
        return embeddings[0]


def _create_model():
    if MODEL_DIR:
        model_dir = Path(MODEL_DIR)
        model_path = model_dir / "onnx" / "model.onnx"
        tokenizer_path = model_dir / "tokenizer.json"
        if not model_path.is_file() or not tokenizer_path.is_file():
            raise FileNotFoundError(
                f"RAG ONNX model files are missing from {model_dir}."
            )
        return _OnnxSentenceEncoder(model_path, tokenizer_path)

    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = _create_model()
    return _model


def _get_conn():
    global _conn
    with _conn_lock:
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

    with _embedding_lock:
        query_embedding = model.encode(query, normalize_embeddings=True)

    with _query_lock:
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


_POLICY_TOOL_UNINITIALIZED = object()
_policy_tool = _POLICY_TOOL_UNINITIALIZED
_policy_tool_lock = Lock()


def __getattr__(name):
    if name != "policy_tool":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    global _policy_tool
    with _policy_tool_lock:
        if _policy_tool is _POLICY_TOOL_UNINITIALIZED:
            try:
                from langchain.tools import Tool
            except ImportError:
                _policy_tool = None
            else:
                _policy_tool = Tool(
                    name="retrieve_hr_policy",
                    func=lambda q: format_policy_context(q, n_results=3),
                    description=(
                        "Retrieves relevant HR policies, SOPs, and guidelines from the "
                        "organizational policy database. Use this tool before making any "
                        "decision about task assignment, team formation, burnout response, "
                        "leave handling, performance actions, or promotion eligibility. "
                        "Input should be a natural language description of the decision "
                        "you are trying to make. Returns relevant policy excerpts."
                    ),
                )
        return _policy_tool


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
