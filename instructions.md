### Policies -------------------------------------------------------------------------
cd path/to/epars_policies

pip install -r requirements.txt
python ingest_policies.py   

### ChromaDB - putting in policies ---------------------------------------------------
# 1. Install
pip install -r requirements.txt

# 2. Set your DB credentials
cp .env.example .env 
# open .env and fill in DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
# or skip this and use the .env i sent on wa, with your postgresql creds

# 3. Verify DB connection
python setup_database.py
cd agent
python db.py           # should print: [OK] Connected to PostgreSQL

# 4. Test all tools against your actual data
python tools.py EMP001 TSK0001    # they are real IDs from the DB

### Install PostgreSQL ---------------------------------------------------------------

1. Go to https://www.postgresql.org/download/windows/
2. Download the installer (latest version, e.g. 17.x)
3. Run it — keep all defaults, remember the password you set for the postgres user
4. It installs PostgreSQL + pgAdmin (a GUI tool) automatically

Run this inside psql (sql shell -> search for it in start)
CREATE DATABASE epars_db;
CREATE USER epars_user WITH PASSWORD 'choose_a_password';
GRANT ALL PRIVILEGES ON DATABASE epars_db TO epars_user;
\q

### Setup PostgreSQL -----------------------------------------------------------------

pip install -r requirements.txt

# This creates all 10 tables and loads all CSVs in one shot
python setup_database.py

python agent/db.py             # should print: [OK] Connected to PostgreSQL
python agent/tools.py EMP001 TSK0001   # tests all 7 tools against real data

### RUN AGENT ------------------------------------------------------------------------

cd path\to\epars_agent
python test_agent.py # for 4 standard tests
 
# once that works
python agent/epars_agent.py # for any query

### Folder Structure------------------------------------------------------------------

epars_agent/
├── .env.example        ← rename to .env
├── test_agent.py           ← NEW
├── setup_database.py   ← the new script
├── requirements.txt
├── agent/
├── ├── epars_agent.py      ← NEW
│   ├── db.py
│   └── tools.py
└── dataset/            ← put ALL 10 CSV files here
    ├── employees.csv
    ├── projects.csv
    ├── tasks.csv
    ├── task_assignments.csv
    ├── schedules.csv
    ├── workload_history.csv
    ├── team_formations.csv
    ├── feedback.csv
    ├── performance_reviews.csv
    └── burnout_indicators.csv