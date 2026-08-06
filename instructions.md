# AGENTIC AI With CALENDAR SETUP And Burnout Monitoring
## Policies 
```
cd path/to/epars_policies

pip install -r requirements.txt
python ingest_policies.py   
```

## ChromaDB - putting in policies 
1. Install
```
pip install -r requirements.txt
```
2. Set your DB credentials
```
cp .env.example .env 
```
open .env and fill in DB_HOST, DB_NAME, DB_USER, DB_PASSWORD or skip this and use the .env sent on wa, with your postgresql creds

3. Verify DB connection
```
python setup_database.py
cd agent
python db.py           # should print: [OK] Connected to PostgreSQL
```

## Install PostgreSQL 

1. Go to https://www.postgresql.org/download/windows/
2. Download the installer (latest version, e.g. 17.x)
3. Run it — keep all defaults, remember the password you set for the postgres user
4. It installs PostgreSQL + pgAdmin (a GUI tool) automatically

Run this inside psql (sql shell -> search for it in start)
```sql
CREATE DATABASE epars_db;
CREATE USER epars_user WITH PASSWORD 'choose_a_password';
GRANT ALL PRIVILEGES ON DATABASE epars_db TO epars_user;
\q
```

## Setup PostgreSQL 
```
pip install -r requirements.txt
```
This creates all 10 tables and loads all CSVs in one shot
```
python setup_database.py
python agent/db.py             # should print: [OK] Connected to PostgreSQL
```
Add google_event_id columns
```sql
ALTER TABLE task_assignments ADD COLUMN google_event_id TEXT; ALTER TABLE schedules ADD COLUMN google_event_id TEXT;
```

## Google Calendar setup
1. Go to Google Cloud Console (console.cloud.google.com) → create/select a project
2. Enable the Google Calendar API (APIs & Services → Library → search "Google Calendar API")
3. Create a Service Account: APIs & Services → Credentials → Create Credentials → Service Account
4. Generate a key for it: Click into the service account → Keys tab → Add Key → Create new key → JSON → download it, rename to sa_key.json, place in epars_agent/agent/ → this file is gitignored — DO NOT commit it. Use the shared one if using the shared team calendar.
5. Share the team Google Calendar with the service account: Open the calendar in Google Calendar → Settings → "Share with specific people" → paste the service account's email (looks like xxx@xxx.iam.gserviceaccount.com) → permission: "Make changes to events"
6. Get the Calendar ID: Calendar Settings → "Integrate calendar" → copy the Calendar ID
7. Open agent/calendar_client.py and paste your Calendar ID into the CALENDAR_ID variable near the top of the file (or ask for the shared one if using the team calendar).

Test if it works: 
```
cd agent python calendar_client.py
```

## Test all tools against data
```
python tools.py EMP001 TSK0001    # or any real IDs from the DB. It tests all 10 tools against real data
```

## Run Agent 
```
cd path\to\epars_agent
python test_agent.py # for 4 standard tests
 
# once that works
python agent/epars_agent.py # for any query
```

## Run Burnout Monitor (Threshold=0.7)
Uses LLM to reschedule/reassign/no action per task. 
```
python burnout_monitor.py
```

## Folder Structure

epars_agent/ 
├── .env.example          ← rename to .env (needs DB_*, GROQ_API_KEY) 
├── test_agent.py 
├── setup_database.py 
├── burnout_monitor.py    ← burnout monitoring loop 
├── requirements.txt 
├── agent/ 
│   ├── epars_agent.py 
│   ├── db.py 
│   ├── tools.py               ← now 10 tools (7 + 3 calendar) 
│   ├── calendar_client.py     ← Google Calendar API wrapper 
│   └── sa_key.json            ← Google service account key (gitignored) 
└── dataset/ 
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
