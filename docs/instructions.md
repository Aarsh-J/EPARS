> These are the quick day-to-day commands. For full setup, the shared Supabase DB, and
> troubleshooting, see [`SUPABASE.md`](SUPABASE.md). For the deployment plan, see [`plan.md`](plan.md).

### 1. Install dependencies
```bash
cd path/to/epars_agent
pip install -r requirements.txt

cd path/to/epars_policies
pip install -r requirements.txt
```

### 2. Configure `.env`
Create a single `.env` in the **project root** (not inside `epars_agent/` or
`epars_policies/` — every script finds it automatically by walking up directories):
```
DATABASE_URL=postgresql://postgres:<password>@<supabase-host>:5432/postgres
GROQ_API_KEY=gsk_...
ANTHROPIC_API_KEY=sk-ant-...
```
Get the real `DATABASE_URL` from whoever set up the shared Supabase project (see
`SUPABASE.md`) — don't create your own local Postgres instance, everyone shares one DB.

### 3. Load the dataset (one-time, already done for the shared DB)
```bash
cd path/to/epars_agent
python setup_database.py
# Creates all 10 tables and loads all 10 CSVs from ../dataset/
```

### 4. Embed the policy docs into pgvector (one-time, already done for the shared DB)
```bash
cd path/to/epars_policies
python ingest_policies.py
# Safe to re-run any time a doc under epars_policies/docs/ changes
```

### 5. Verify everything connects
```bash
python epars_agent/agent/db.py            # should print: [OK] Connected to PostgreSQL
python epars_policies/rag_query.py        # runs sample policy queries
cd epars_agent && python agent/tools.py EMP001 TSK0001   # use real IDs from your DB
```

### 6. Run the agent
```bash
cd path/to/epars_agent
python test_agent.py       # 4 standard test queries (needs GROQ_API_KEY)

# once that works, run any custom query:
python agent/epars_agent.py
```

### Folder Structure
```
epars_agent/
├── .env.example        ← template only; the real .env lives in the project root
├── test_agent.py
├── setup_database.py
├── requirements.txt
├── agent/
│   ├── epars_agent.py
│   ├── db.py
│   └── tools.py
└── (dataset/ lives at the project root, not here)

epars_policies/
├── docs/                ← the 8 policy markdown files
├── ingest_policies.py
├── rag_query.py
└── requirements.txt
```
