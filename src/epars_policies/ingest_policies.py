"""
ePARS Policy pgvector Ingestion Script
=======================================
Loads all synthetic HR/policy documents into Postgres (pgvector) as
semantically chunked embeddings, ready for RAG queries from the
Agentic AI layer.

Usage:
    python ingest_policies.py

Requirements:
    pip install -r requirements.txt

Make sure DATABASE_URL is set in your .env (project root) and the
`vector` extension is enabled on that Postgres instance:
    CREATE EXTENSION IF NOT EXISTS vector;
"""

import os
import re
import json
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer

load_dotenv()

# ── Configuration ──────────────────────────────────────────────────────────────
POLICY_DOCS_DIR = "./docs"          # Folder containing the .md policy files
TABLE_NAME      = "policy_chunks"   # Postgres table storing chunks + embeddings
CHUNK_SIZE      = 400               # Target chunk size in characters
CHUNK_OVERLAP   = 80                # Overlap between chunks to preserve context
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Lightweight, fast, good for semantic search
EMBEDDING_DIM   = 384                 # Output dimension of the model above

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("[ERROR] DATABASE_URL not set. Check your .env file.")

# ── Embedding Model ────────────────────────────────────────────────────────────
print(f"[INFO] Loading embedding model: {EMBEDDING_MODEL}")
model = SentenceTransformer(EMBEDDING_MODEL)

# ── DB Connection ──────────────────────────────────────────────────────────────
print("[INFO] Connecting to Postgres...")
conn = psycopg2.connect(DATABASE_URL)
register_vector(conn)

with conn.cursor() as cur:
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            chunk_id     TEXT PRIMARY KEY,
            doc_id       TEXT,
            title        TEXT,
            source_file  TEXT,
            version      TEXT,
            owner        TEXT,
            chunk_index  INTEGER,
            chunk_count  INTEGER,
            char_length  INTEGER,
            content      TEXT NOT NULL,
            embedding    VECTOR({EMBEDDING_DIM}) NOT NULL,
            updated_at   TIMESTAMP NOT NULL DEFAULT now()
        );
    """)
    # HNSW index for fast cosine similarity search
    cur.execute(f"""
        CREATE INDEX IF NOT EXISTS {TABLE_NAME}_embedding_hnsw_idx
        ON {TABLE_NAME} USING hnsw (embedding vector_cosine_ops);
    """)
conn.commit()
print(f"[INFO] Table '{TABLE_NAME}' ready.")


# ── Helper: Smart Text Chunker ─────────────────────────────────────────────────
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Splits text into overlapping chunks, preferring to break at
    paragraph/sentence boundaries to preserve semantic coherence.
    """
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk = (current_chunk + "\n\n" + para).strip()
        else:
            if current_chunk:
                chunks.append(current_chunk)

            if len(para) > chunk_size:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                sent_chunk = ""
                for sentence in sentences:
                    if len(sent_chunk) + len(sentence) + 1 <= chunk_size:
                        sent_chunk = (sent_chunk + " " + sentence).strip()
                    else:
                        if sent_chunk:
                            chunks.append(sent_chunk)
                        sent_chunk = sentence
                if sent_chunk:
                    current_chunk = sent_chunk
                else:
                    current_chunk = ""
            else:
                if chunks and overlap > 0:
                    overlap_text = chunks[-1][-overlap:]
                    current_chunk = (overlap_text + " " + para).strip()
                else:
                    current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


# ── Helper: Extract Document Metadata from Markdown ───────────────────────────
def extract_metadata(text: str, filename: str) -> dict:
    """Pulls doc_id, version, and title from the markdown header lines."""
    meta = {"source_file": filename}

    title_match = re.search(r'^#\s+(.+)', text, re.MULTILINE)
    if title_match:
        meta["title"] = title_match.group(1).strip()

    doc_id_match = re.search(r'\*\*Document ID:\*\*\s*(\S+)', text)
    if doc_id_match:
        meta["doc_id"] = doc_id_match.group(1).strip()

    version_match = re.search(r'\*\*Version:\*\*\s*(\S+)', text)
    if version_match:
        meta["version"] = version_match.group(1).strip()

    owner_match = re.search(r'\*\*Owner:\*\*\s*(.+)', text)
    if owner_match:
        meta["owner"] = owner_match.group(1).strip()

    return meta


# ── Main Ingestion Loop ────────────────────────────────────────────────────────
md_files = sorted([
    f for f in os.listdir(POLICY_DOCS_DIR) if f.endswith(".md")
])

if not md_files:
    print(f"[ERROR] No .md files found in '{POLICY_DOCS_DIR}'. Exiting.")
    raise SystemExit(1)

print(f"\n[INFO] Found {len(md_files)} policy documents to ingest.\n")

rows = []            # (chunk_id, doc_id, title, source_file, version, owner,
                      #  chunk_index, chunk_count, char_length, content, embedding)
ingestion_log  = []
seen_doc_ids   = []

for filename in md_files:
    filepath = os.path.join(POLICY_DOCS_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        raw_text = f.read()

    metadata = extract_metadata(raw_text, filename)
    doc_id   = metadata.get("doc_id", filename.replace(".md", ""))
    chunks   = chunk_text(raw_text)
    seen_doc_ids.append(doc_id)

    print(f"  [{doc_id}] '{metadata.get('title', filename)}'")
    print(f"    → {len(chunks)} chunks generated")

    embeddings = model.encode(chunks, normalize_embeddings=True)

    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_id = f"{doc_id}_chunk_{i:03d}"
        rows.append((
            chunk_id,
            doc_id,
            metadata.get("title", filename),
            filename,
            metadata.get("version"),
            metadata.get("owner"),
            i,
            len(chunks),
            len(chunk),
            chunk,
            embedding,
        ))

    ingestion_log.append({
        "file": filename,
        "doc_id": doc_id,
        "title": metadata.get("title", "unknown"),
        "chunks": len(chunks),
        "total_chars": len(raw_text),
    })

# ── Upsert into Postgres ───────────────────────────────────────────────────────
print(f"\n[INFO] Upserting {len(rows)} chunks into '{TABLE_NAME}'...")
with conn.cursor() as cur:
    psycopg2.extras.execute_values(
        cur,
        f"""
        INSERT INTO {TABLE_NAME}
            (chunk_id, doc_id, title, source_file, version, owner,
             chunk_index, chunk_count, char_length, content, embedding, updated_at)
        VALUES %s
        ON CONFLICT (chunk_id) DO UPDATE SET
            doc_id       = EXCLUDED.doc_id,
            title        = EXCLUDED.title,
            source_file  = EXCLUDED.source_file,
            version      = EXCLUDED.version,
            owner        = EXCLUDED.owner,
            chunk_index  = EXCLUDED.chunk_index,
            chunk_count  = EXCLUDED.chunk_count,
            char_length  = EXCLUDED.char_length,
            content      = EXCLUDED.content,
            embedding    = EXCLUDED.embedding,
            updated_at   = now();
        """,
        rows,
        template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())",
    )

    # Drop stale chunks: ones from a doc that shrank (old chunk_id no longer
    # produced this run) and ones from a .md file removed from ./docs entirely.
    cur.execute(
        f"DELETE FROM {TABLE_NAME} WHERE doc_id = ANY(%s) AND chunk_id != ALL(%s);",
        (seen_doc_ids, [r[0] for r in rows]),
    )
    cur.execute(
        f"DELETE FROM {TABLE_NAME} WHERE doc_id != ALL(%s);",
        (seen_doc_ids,),
    )
conn.commit()

with conn.cursor() as cur:
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME};")
    total_count = cur.fetchone()[0]

print(f"\n[SUCCESS] Ingestion complete. {len(rows)} chunks upserted.")
print(f"          Table '{TABLE_NAME}' now has {total_count} rows.\n")

# ── Save Ingestion Log ─────────────────────────────────────────────────────────
log_path = "./ingestion_log.json"
with open(log_path, "w") as f:
    json.dump(ingestion_log, f, indent=2)
print(f"[INFO] Ingestion log saved to: {log_path}")


# ── Quick Smoke Test ───────────────────────────────────────────────────────────
print("\n[TEST] Running sample queries to verify the table...\n")

test_queries = [
    "What should happen if an employee has high burnout?",
    "What are the rules for assigning critical P1 tasks?",
    "How is a team lead selected?",
    "What happens when an employee scores below 50 in PEM?",
    "How many tasks can an employee have at one time?",
]

with conn.cursor() as cur:
    for query in test_queries:
        query_embedding = model.encode(query, normalize_embeddings=True)
        cur.execute(
            f"""
            SELECT doc_id, title, content, 1 - (embedding <=> %s) AS similarity
            FROM {TABLE_NAME}
            ORDER BY embedding <=> %s
            LIMIT 2;
            """,
            (query_embedding, query_embedding),
        )
        top = cur.fetchone()
        doc_id, title, content, similarity = top
        print(f"  Query : {query}")
        print(f"  Match : [{doc_id}] {title} (similarity: {similarity:.3f})")
        print(f"  Chunk : {content[:120].strip()}...")
        print()

conn.close()
print("[DONE] pgvector is ready for the Agentic AI layer.")
