# Deploy EPARS: Shared Dev Database + Hosting Plan

## Context
EPARS (Employee Performance Analyzer and Recommendation System) currently has no working code on `main` — the real implementation lives on the `develop` branch: a Python backend (FastAPI + LangChain/Anthropic agent + ChromaDB for RAG over policy docs + PostgreSQL via SQLAlchemy/psycopg2), plus a `schema_specification.md` defining the relational schema. No frontend exists yet.

The team of 4 needs:
1. A shared free Postgres database everyone can point their local dev environments at, instead of each person running their own.
2. A place to deploy the app (frontend in JS + the existing Python backend) so it's demoable, ideally still free.

Decisions made with the user: keep the backend in Python as-is (do not rewrite in Node), build the frontend in JS (React), and the user has prior experience with **Render** and **Supabase** but is open to better options.

## Recommendation

### Shared database: Supabase (Postgres)
- Free tier gives a single shared Postgres instance with a web dashboard/table editor — easiest for 4 people to inspect data and share one connection string without setting up their own local Postgres.
- Free projects pause after ~1 week of inactivity but wake up automatically on the next request/login — fine for a class project with intermittent dev activity.
- **Bonus**: Supabase Postgres supports the `pgvector` extension. Recommend using it to store the RAG embeddings (currently local ChromaDB files in `epars_policies/`) directly in Postgres instead of on-disk Chroma. This matters because Render's free web service has **no persistent disk** — anything ChromaDB writes to disk is wiped on every redeploy/restart. Storing embeddings in Supabase via `pgvector` sidesteps that entirely and keeps everything in one DB. This is a moderate code change (swap the Chroma client for a `pgvector`-backed retriever in `epars_policies/rag_query.py` / `ingest_policies.py`) — worth doing before deploying, not required to start local dev.
- One shared `.env` (via `epars_agent/.env.example` as the template) holding the Supabase connection string, distributed to the 4 devs (not committed).

### Backend hosting: Render (free web service)
- User already knows it; free tier (750 instance-hours/month) comfortably covers a small team demo.
- Caveat to plan for: free instances spin down after 15 min idle and cold-start on the next request (~30-50s) — acceptable for a project demo, not for production SLAs.
- Deploy `epars_agent/` (FastAPI + uvicorn) as a Render Web Service, pointing `DATABASE_URL` at the Supabase instance. Needs a `requirements.txt` (already present on `develop`) and a start command (`uvicorn epars_agent:app ...` — confirm the actual entrypoint file/app object once on `develop`).

### Frontend hosting: Vercel
- Best free-tier fit for a JS frontend (React/Vite or Next.js) — automatic deploys from git, generous free tier, zero config for standard React setups.
- Frontend calls the Render-hosted FastAPI backend via its public URL (set as an env var, e.g. `VITE_API_URL`).

## Action Plan
1. **Merge/rebase `develop` onto `main`** (or agree as a team which branch is the real trunk) so the actual working code isn't stranded off `main`. Confirm with the user/team before doing this — it's a branch decision, not purely technical.
2. **Create the Supabase project**, run `setup_database.py` (from `develop`) against it to create the schema from `schema_specification.md`, and share the connection string with the 4 devs via `.env` (based on `epars_agent/.env.example`).
3. **(Recommended) Migrate RAG storage from local ChromaDB to pgvector on Supabase** so the backend has no dependency on local/ephemeral disk before deploying to Render.
4. **Deploy backend to Render**: connect the repo, set root dir to `epars_agent/` (or wherever the FastAPI app lives on `develop`), set env vars (`DATABASE_URL`, Anthropic API key, etc.), deploy.
5. **Scaffold the JS frontend** (React via Vite recommended for simplicity) if it doesn't exist yet, pointing API calls at the Render backend URL.
6. **Deploy frontend to Vercel**, connect repo, set `VITE_API_URL` (or equivalent) env var to the Render backend's public URL.
7. **Add `.env.example`, `Dockerfile`(optional), and deployment docs to `README.md`** so the whole team has one source of truth for setup — currently the README only covers branching conventions.

## Verification
- Confirm all 4 devs can connect to the shared Supabase DB locally using the shared connection string and run the backend against it.
- Hit the deployed Render backend's health/docs endpoint (FastAPI auto-generates `/docs`) to confirm it's live and can reach Supabase.
- Load the deployed Vercel frontend URL and confirm it successfully calls the Render backend end-to-end (e.g. a simple GET request round-trip).

## Account Setup Steps (do these first, one person can do it and invite the other 3)

### Supabase
1. Go to supabase.com and sign up (GitHub login is easiest for a dev team).
2. Click "New project" → pick an org (or create one for the team) → name it (e.g. `epars`) → set a strong DB password (save it, you'll need it for the connection string) → pick the region closest to the team → create.
3. Wait ~2 min for provisioning. Once ready, go to Project Settings → Database → copy the connection string (URI format) — this is what goes in `DATABASE_URL`.
4. Project Settings → Team → invite the other 3 devs by email so everyone can see the dashboard/table editor, not just share the password.
5. (For step 3 in the Action Plan) Table Editor → SQL Editor → run `create extension if not exists vector;` once, to enable pgvector before migrating RAG storage.

### Render
1. Go to render.com and sign up (GitHub login recommended — lets you connect the repo directly).
2. Once logged in: New → Web Service → connect your GitHub account → select the EPARS repo → pick the branch (`develop`, or `main` after the merge in step 1).
3. Set Root Directory to `epars_agent` (or wherever the FastAPI app ends up living).
4. Environment: Python 3. Build command: `pip install -r requirements.txt`. Start command: `uvicorn <module>:app --host 0.0.0.0 --port $PORT` (confirm the actual module/app object name once `develop` is merged).
5. Instance type: Free.
6. Add environment variables: `DATABASE_URL` (from Supabase), `ANTHROPIC_API_KEY` (or whichever LLM key `epars_agent` uses), and any others found in `.env.example`.
7. Create Web Service — Render will build and deploy automatically on every push to the selected branch. Invite the other 3 devs under Account Settings → Team so they can see logs/redeploys, not just one person owning the service.

### Vercel
1. Go to vercel.com and sign up (GitHub login recommended).
2. Add New → Project → import the EPARS repo → set Root Directory to the frontend folder (once scaffolded) → framework preset should auto-detect (Vite/React or Next.js).
3. Add environment variable `VITE_API_URL` (or `NEXT_PUBLIC_API_URL`) pointing at the Render backend's public URL (e.g. `https://epars-backend.onrender.com`).
4. Deploy — Vercel builds and gives a public URL, auto-redeploying on every push.
5. Settings → Members → invite the other 3 devs (Vercel's free "Hobby" plan is single-owner for production deploys but team members can still be added as collaborators for preview deploys — if everyone needs full deploy rights, consider Vercel's free team tier limitations, or just have one person own it and others push via git).

## Local ChromaDB vs pgvector (Supabase)

| | Local ChromaDB (current) | pgvector on Supabase (recommended for deploy) |
|---|---|---|
| **What it is** | An embedded vector database that writes its index to files on local disk (`epars_policies/` persistence dir) | A Postgres extension that adds a `vector` column type + similarity-search operators to regular Postgres tables |
| **Where data lives** | Local disk, wherever the process runs | Inside the same Supabase Postgres DB already storing employee/task data |
| **Problem on Render free tier** | Render's free web service has **no persistent disk** — every redeploy or restart (including the free-tier idle-spindown/wake cycle) wipes the filesystem, so the Chroma index would need to be rebuilt from scratch on every cold start | No problem — data lives in the DB, which persists independently of the backend process |
| **Setup** | `chromadb` Python client, separate persistence directory, separate query API (`epars_policies/rag_query.py`) | `pgvector` Postgres extension (`CREATE EXTENSION vector;`) + a `vector` column in a table, queried with normal SQL (`ORDER BY embedding <-> query_embedding`) |
| **Team collaboration** | Each dev who runs the ingestion script locally gets their own separate index — not shared | One shared index in the shared Supabase DB — everyone sees the same ingested policy docs |
| **Migration effort** | — | Moderate: change `ingest_policies.py` to insert embeddings into a Postgres table instead of `chromadb.Client()`, and change `rag_query.py` to run a SQL similarity query instead of a Chroma query. The embedding model (sentence-transformers) stays the same — only the storage/query layer changes |
| **Recommendation** | Fine for solo local dev/testing | Do this before deploying to Render, so the RAG feature actually works in production instead of resetting on every cold start |
