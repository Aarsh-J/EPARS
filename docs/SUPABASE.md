# Supabase — Setup, Operations & Troubleshooting

This is the shared Postgres database for ePARS. All 4 devs point their local `.env` at the same
Supabase project instead of running their own local Postgres.

- **Project ref:** `hkxztnlcutzrwsfqoqvg`
- **Dashboard:** https://supabase.com/dashboard/project/hkxztnlcutzrwsfqoqvg
- **Region:** whatever was picked at project creation (check dashboard → Project Settings → General)

---

## 1. What's set up

### 1.1 Connection
One connection string, stored as `DATABASE_URL` in `.env` (project root, gitignored — never commit it):

```
DATABASE_URL=postgresql://postgres:<password>@db.hkxztnlcutzrwsfqoqvg.supabase.co:5432/postgres
```

Both `epars_agent/agent/db.py` and `epars_agent/setup_database.py` read `DATABASE_URL` directly
(they fall back to separate `DB_HOST`/`DB_USER`/etc. vars only if `DATABASE_URL` isn't set — you
don't need those if you're using Supabase).

**If your password contains special characters** (`@`, `#`, `%`, `/`, etc.), they must be
percent-encoded in the URL or the connection string parses incorrectly (see [Bug: password
containing `@` breaks the connection string](#bug-password-containing--breaks-the-connection-string)).

### 1.2 Tables (relational data — 10 tables, loaded from `dataset/*.csv`)

Created and populated by `epars_agent/setup_database.py`:

| Table | Rows (as of last load) |
|---|---|
| `employees` | 1,500 |
| `projects` | 800 |
| `tasks` | 10,000 |
| `task_assignments` | 15,000 |
| `schedules` | 50,000 |
| `workload_history` | 49,500 |
| `team_formations` | 1,000 |
| `feedback` | 20,000 |
| `performance_reviews` | 4,000 |
| `burnout_indicators` | 20,000 |

Schema is defined inline in `setup_database.py` (`TABLES_DDL`) and matches `dataset_schema.md`.

### 1.3 pgvector (RAG policy storage)

The `vector` extension is enabled on this project. One table, `policy_chunks`, stores embedded
chunks of the HR policy docs (`epars_policies/docs/*.md`) for retrieval-augmented generation:

```sql
CREATE TABLE policy_chunks (
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
    embedding    VECTOR(384) NOT NULL,
    updated_at   TIMESTAMP NOT NULL DEFAULT now()
);
-- HNSW index for fast cosine similarity search:
CREATE INDEX policy_chunks_embedding_hnsw_idx
    ON policy_chunks USING hnsw (embedding vector_cosine_ops);
```

This replaced a local ChromaDB setup — see `epars_policies/ingest_policies.py` (writes/updates
embeddings) and `epars_policies/rag_query.py` (queries them). Embedding model: `all-MiniLM-L6-v2`
(384 dimensions), same as before the migration.

---

## 2. Keeping it running

### 2.1 Free tier auto-pause
Supabase free projects **pause after ~1 week with no API/DB activity**. A paused project:
- Shows "Paused" in the dashboard.
- Refuses new connections until you click **Restore** in the dashboard (takes ~1-2 min).

**To avoid this biting you mid-demo:** log into the dashboard or run any query at least once a
week. If the whole team is inactive for a stretch (e.g. between sprints), whoever notices first
should just open the dashboard's SQL editor and run `SELECT 1;` — that's enough to reset the
inactivity clock.

If you deploy the backend (Render) and it's also idle, nothing will ping Supabase automatically —
free Render instances sleep too, so there's no built-in keep-alive. If this becomes a recurring
problem, a simple fix is a scheduled GitHub Action that hits a health-check endpoint on the
deployed backend once every few days.

### 2.2 Connection limits
Free tier caps concurrent direct connections (check dashboard → Database → Connection Pooling for
the current limit). With 4 devs + local scripts + a deployed backend, you can hit this if multiple
people run long-lived scripts simultaneously. Symptoms: `too many connections` errors. Fix: use the
**connection pooler** string (Session or Transaction mode, shown in Project Settings → Database)
instead of the direct `:5432` connection if this happens — swap the host/port in `DATABASE_URL` for
the pooler's host/port (usually `:6543` for transaction mode).

### 2.3 Re-running ingestion after policy doc edits
`policy_chunks` isn't automatically kept in sync with `epars_policies/docs/*.md`. Whenever someone
edits a policy doc, re-run:
```
python epars_policies/ingest_policies.py
```
It's idempotent (safe to re-run — upserts by `chunk_id`, deletes stale/removed chunks). See the
"Local ChromaDB vs pgvector" comparison in `plan.md` for why this exists.

### 2.4 Re-running the full data load
`setup_database.py` uses `CREATE TABLE IF NOT EXISTS`, so re-running it won't destroy existing
tables — but the CSV load step will **duplicate rows** if run twice (it doesn't upsert, it inserts).
Only re-run the CSV load step against a table you've truncated first, or if the table is empty.

---

## 3. Common bugs and solutions

### Bug: password containing `@` breaks the connection string
**Symptom:** connection fails, or worse, silently connects to the wrong host, when the DB password
has an `@`, `%`, `#`, `/`, or space in it.
**Cause:** `postgresql://user:password@host:port/db` uses `@` as the delimiter between credentials
and host — a literal `@` in the password confuses the parser.
**Fix:** percent-encode special characters in the password portion only. `@` → `%40`, `#` → `%23`,
`%` → `%25`, space → `%20`. Example: password `my@pass` becomes `my%40pass` in the URL.

### Bug: `ImportError: cannot import name 'load_dotenv' from 'dotenv' (unknown location)`
**Symptom:** `dotenv`, `pandas`, or other packages fail to import with a vague "unknown location"
error, even though `pip show <package>` reports them as installed.
**Cause:** the package's install directory in `site-packages` is missing its actual `.py` source
files — only a `__pycache__` folder remains (i.e. `dotenv.__path__` resolves but `dotenv.__file__`
is `None`). This happened to **60 of 131 packages** in this project's original venv — some external
process (antivirus quarantine, an aggressive cache-cleaner, a bad `git clean`, etc.) deleted the
source files but left bytecode caches behind.
**Fix:** don't patch package-by-package — if more than a couple of packages show this pattern, the
venv itself is compromised. Recreate it from scratch:
```
python -m venv venv_new
./venv_new/Scripts/python.exe -m pip install -r epars_agent/requirements.txt -r epars_policies/requirements.txt fastapi uvicorn
# verify imports work, then:
rm -rf venv && mv venv_new venv
```
To check how widespread the corruption is before deciding, count how many top-level package dirs
in `site-packages` have zero `.py` files at their top level — if it's more than a handful, recreate
rather than patch.

### Bug: `pip install --force-reinstall` fails with `uninstall-no-record-file`
**Symptom:** `error: uninstall-no-record-file — Cannot uninstall <package> None. The package's
contents are unknown: no RECORD file was found.`
**Cause:** same underlying corruption as above — the package's metadata (`RECORD` file, which
tracks what files pip installed) is missing, so pip refuses to uninstall it blindly.
**Fix (one-off):** `pip install --ignore-installed --no-deps <package>` to force a clean reinstall
of just that package. But if you hit this on a second or third package in the same
`--force-reinstall` run, stop and recreate the venv instead (see above) — it'll keep happening one
package at a time otherwise.

### Bug: Windows console prints `UnicodeEncodeError` for ✓/✗ characters
**Symptom:** scripts that print `✓`/`✗` characters crash with
`UnicodeEncodeError: 'charmap' codec can't encode character '✓'` — but only when run directly
in a Windows terminal, not when redirected to a file.
**Cause:** Windows' default console codepage (`cp1252`) can't represent those Unicode characters;
this is a terminal encoding issue, not a bug in the script or a failed operation.
**Fix:** run with `PYTHONIOENCODING=utf-8` set, e.g.:
```
PYTHONIOENCODING=utf-8 python epars_agent/setup_database.py
```

### Bug: `setup_database.py` / `db.py` ignore `DATABASE_URL`
**Symptom:** connection fails or falls back to `localhost` even though `DATABASE_URL` is set in
`.env`.
**Cause:** older versions of these scripts only read individual `DB_HOST`/`DB_PORT`/`DB_NAME`/
`DB_USER`/`DB_PASSWORD` vars, not a single connection string.
**Fix:** already patched — both scripts now check `os.getenv("DATABASE_URL")` first and use it if
present, falling back to the individual vars otherwise. If you pull an older copy of these files,
re-apply that fallback logic before pointing at Supabase.

### Bug: `requirements.txt` doesn't actually list everything the code imports
**Symptom:** `ModuleNotFoundError` for `pandas`, `langchain_groq`, or `langgraph` even after
installing everything in `requirements.txt`.
**Cause:** these were used directly in `setup_database.py` / `epars_agent.py` but never added to
`epars_agent/requirements.txt`. They only worked before because someone's local venv happened to
have them installed manually.
**Fix:** already added to `requirements.txt`. If you add a new import anywhere in `epars_agent/` or
`epars_policies/`, add its package to the matching `requirements.txt` in the same commit — don't
rely on "it's already in my venv."

### Bug: RAG results look empty or stale after editing a policy doc
**Symptom:** `query_policies()` / `format_policy_context()` returns outdated policy text after a
doc in `epars_policies/docs/` was edited.
**Cause:** `policy_chunks` is only updated when `ingest_policies.py` is re-run — editing the `.md`
file alone doesn't touch the database.
**Fix:** `python epars_policies/ingest_policies.py` after any doc edit (see §2.3).

### Bug: `too many connections` errors under concurrent use
**Symptom:** intermittent connection failures when multiple devs/scripts/the deployed backend hit
the DB at the same time.
**Cause:** free tier connection limit reached via direct (`:5432`) connections.
**Fix:** switch `DATABASE_URL` to the connection pooler string from Project Settings → Database
(see §2.2).

---

## 4. Quick reference

| Task | Command |
|---|---|
| Test connection | `python epars_agent/agent/db.py` |
| Create tables + load CSVs | `python epars_agent/setup_database.py` |
| Enable pgvector (one-time) | `CREATE EXTENSION IF NOT EXISTS vector;` in SQL editor |
| Re-ingest policy docs into pgvector | `python epars_policies/ingest_policies.py` |
| Query policies from Python | `from rag_query import query_policies, format_policy_context` |
