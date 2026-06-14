"""
ePARS Policy ChromaDB Ingestion Script
=======================================
Loads all synthetic HR/policy documents into ChromaDB as
semantically chunked embeddings, ready for RAG queries
from the Agentic AI layer.

Usage:
    python ingest_policies.py

Requirements:
    pip install chromadb sentence-transformers
"""

import os
import re
import json
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

# ── Configuration ──────────────────────────────────────────────────────────────
POLICY_DOCS_DIR = "./docs"          # Folder containing the .md policy files
CHROMA_DB_PATH  = "./chroma_db"     # Persistent ChromaDB storage path
COLLECTION_NAME = "epars_policies"  # Name of the ChromaDB collection
CHUNK_SIZE      = 400               # Target chunk size in characters
CHUNK_OVERLAP   = 80                # Overlap between chunks to preserve context
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Lightweight, fast, good for semantic search

# ── Embedding Function ─────────────────────────────────────────────────────────
print(f"[INFO] Loading embedding model: {EMBEDDING_MODEL}")
ef = SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL
)

# ── ChromaDB Client ────────────────────────────────────────────────────────────
print(f"[INFO] Connecting to ChromaDB at: {CHROMA_DB_PATH}")
client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

# Delete existing collection if it exists (for clean re-ingestion)
existing = [c.name for c in client.list_collections()]
if COLLECTION_NAME in existing:
    print(f"[INFO] Deleting existing collection '{COLLECTION_NAME}' for fresh ingestion...")
    client.delete_collection(COLLECTION_NAME)

collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=ef,
    metadata={"hnsw:space": "cosine"}  # Cosine similarity for semantic search
)
print(f"[INFO] Collection '{COLLECTION_NAME}' ready.")


# ── Helper: Smart Text Chunker ─────────────────────────────────────────────────
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Splits text into overlapping chunks, preferring to break at
    paragraph/sentence boundaries to preserve semantic coherence.
    """
    # Split on double newlines (paragraphs) first
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        # If adding this paragraph keeps us under chunk_size, add it
        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk = (current_chunk + "\n\n" + para).strip()
        else:
            # Save current chunk if non-empty
            if current_chunk:
                chunks.append(current_chunk)
            
            # If the paragraph itself is larger than chunk_size, split it by sentence
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
                # Start new chunk with overlap from the end of the last chunk
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
    """
    Pulls doc_id, version, and title from the markdown header lines.
    """
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
    exit(1)

print(f"\n[INFO] Found {len(md_files)} policy documents to ingest.\n")

all_ids        = []
all_documents  = []
all_metadatas  = []
ingestion_log  = []

for filename in md_files:
    filepath = os.path.join(POLICY_DOCS_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        raw_text = f.read()

    metadata = extract_metadata(raw_text, filename)
    chunks   = chunk_text(raw_text)

    print(f"  [{metadata.get('doc_id', filename)}] '{metadata.get('title', filename)}'")
    print(f"    → {len(chunks)} chunks generated")

    for i, chunk in enumerate(chunks):
        chunk_id = f"{metadata.get('doc_id', filename.replace('.md',''))}_chunk_{i:03d}"
        chunk_meta = {
            **metadata,
            "chunk_index": i,
            "chunk_count": len(chunks),
            "char_length": len(chunk),
        }

        all_ids.append(chunk_id)
        all_documents.append(chunk)
        all_metadatas.append(chunk_meta)

    ingestion_log.append({
        "file": filename,
        "doc_id": metadata.get("doc_id", "unknown"),
        "title": metadata.get("title", "unknown"),
        "chunks": len(chunks),
        "total_chars": len(raw_text),
    })

# ── Batch Upsert into ChromaDB ─────────────────────────────────────────────────
print(f"\n[INFO] Upserting {len(all_ids)} chunks into ChromaDB...")
BATCH_SIZE = 50
for start in range(0, len(all_ids), BATCH_SIZE):
    end = start + BATCH_SIZE
    collection.upsert(
        ids=all_ids[start:end],
        documents=all_documents[start:end],
        metadatas=all_metadatas[start:end],
    )
    print(f"  Upserted chunks {start}–{min(end, len(all_ids))-1}")

print(f"\n[SUCCESS] Ingestion complete. {len(all_ids)} total chunks stored.")
print(f"          Collection '{COLLECTION_NAME}' now has {collection.count()} documents.\n")

# ── Save Ingestion Log ─────────────────────────────────────────────────────────
log_path = "./ingestion_log.json"
with open(log_path, "w") as f:
    json.dump(ingestion_log, f, indent=2)
print(f"[INFO] Ingestion log saved to: {log_path}")


# ── Quick Smoke Test ───────────────────────────────────────────────────────────
print("\n[TEST] Running sample queries to verify the collection...\n")

test_queries = [
    "What should happen if an employee has high burnout?",
    "What are the rules for assigning critical P1 tasks?",
    "How is a team lead selected?",
    "What happens when an employee scores below 50 in PEM?",
    "How many tasks can an employee have at one time?",
]

for query in test_queries:
    results = collection.query(
        query_texts=[query],
        n_results=2,
        include=["documents", "metadatas", "distances"],
    )
    top_doc   = results["documents"][0][0]
    top_meta  = results["metadatas"][0][0]
    top_score = 1 - results["distances"][0][0]  # Convert cosine distance to similarity

    print(f"  Query : {query}")
    print(f"  Match : [{top_meta.get('doc_id')}] {top_meta.get('title')} (similarity: {top_score:.3f})")
    print(f"  Chunk : {top_doc[:120].strip()}...")
    print()

print("[DONE] ChromaDB is ready for the Agentic AI layer.")
